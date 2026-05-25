#!/usr/bin/env python3
"""
Stream Lichess standard PGN (.pgn.zst) and build a processed SQLite position database.

Incremental mode (default): WAL + frequent commits so readers can query while building.
"""

from __future__ import annotations

import argparse
import io
import json
import multiprocessing as mp
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import chess
import chess.pgn
import zstandard

from pipeline.position_key import (
    elo_bin,
    outcome_for_player_to_move,
    parse_elo,
    position_key,
)


@dataclass
class BinDelta:
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    moves: dict[str, int] = field(default_factory=dict)


@dataclass
class BatchAccumulator:
    bins: dict[tuple[str, int], BinDelta] = field(default_factory=dict)

    def clear(self) -> None:
        self.bins.clear()

    def add(
        self,
        key_hex: str,
        bin_value: int,
        outcome: str,
        move_uci: str,
    ) -> None:
        bucket = self.bins.get((key_hex, bin_value))
        if bucket is None:
            bucket = BinDelta()
            self.bins[(key_hex, bin_value)] = bucket
        bucket.games += 1
        if outcome == "win":
            bucket.wins += 1
        elif outcome == "loss":
            bucket.losses += 1
        else:
            bucket.draws += 1
        bucket.moves[move_uci] = bucket.moves.get(move_uci, 0) + 1

    def merge(self, other: BatchAccumulator) -> None:
        for key, delta in other.bins.items():
            bucket = self.bins.get(key)
            if bucket is None:
                self.bins[key] = BinDelta(
                    games=delta.games,
                    wins=delta.wins,
                    losses=delta.losses,
                    draws=delta.draws,
                    moves=dict(delta.moves),
                )
            else:
                bucket.games += delta.games
                bucket.wins += delta.wins
                bucket.losses += delta.losses
                bucket.draws += delta.draws
                for move_uci, count in delta.moves.items():
                    bucket.moves[move_uci] = bucket.moves.get(move_uci, 0) + count


class GameStatsVisitor(chess.pgn.BaseVisitor):
    """Single-pass parse: collect position stats while reading moves."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.batch = BatchAccumulator()
        self.white_elo: int | None = None
        self.black_elo: int | None = None
        self.game_result = "*"
        self.seen: set[int] = set()
        self.variation_depth = 0
        self.recorded = 0
        self.skipped = False

    def begin_headers(self) -> dict[str, str]:
        self.headers = {}
        return self.headers

    def visit_header(self, tagname: str, tagvalue: str) -> None:
        self.headers[tagname] = tagvalue

    def end_headers(self) -> None:
        self.white_elo = parse_elo(self.headers.get("WhiteElo"))
        self.black_elo = parse_elo(self.headers.get("BlackElo"))
        self.game_result = self.headers.get("Result", "*")
        self.skipped = self.white_elo is None or self.black_elo is None
        self.seen = set()
        self.recorded = 0

    def begin_variation(self) -> chess.pgn.SkipType | None:
        self.variation_depth += 1
        return chess.pgn.SKIP

    def end_variation(self) -> None:
        self.variation_depth = max(0, self.variation_depth - 1)

    def visit_move(self, board: chess.Board, move: chess.Move) -> None:
        if self.skipped or self.variation_depth > 0:
            return

        key = position_key(board)
        if key in self.seen:
            return

        outcome = outcome_for_player_to_move(board, self.game_result)
        if outcome is None:
            return

        self.seen.add(key)
        player_elo = self.white_elo if board.turn == chess.WHITE else self.black_elo
        assert player_elo is not None
        self.batch.add(
            key_hex=f"{key:016x}",
            bin_value=elo_bin(player_elo),
            outcome=outcome,
            move_uci=move.uci(),
        )
        self.recorded += 1

    def result(self) -> GameStatsVisitor:
        return self


def init_db(
    db_path: Path,
    schema_path: Path,
    *,
    fresh: bool,
    incremental: bool,
) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if fresh and db_path.exists():
        for suffix in ("", "-wal", "-shm"):
            path = db_path if not suffix else db_path.with_name(db_path.name + suffix)
            try:
                path.unlink()
            except OSError:
                pass

    conn = sqlite3.connect(db_path, timeout=60.0)
    if fresh:
        conn.executescript(
            """
            DROP TABLE IF EXISTS move_stats;
            DROP TABLE IF EXISTS bin_stats;
            DROP TABLE IF EXISTS positions;
            DROP TABLE IF EXISTS meta;
            """
        )
    conn.executescript(schema_path.read_text(encoding="utf-8"))

    if incremental:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    else:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")

    conn.execute("PRAGMA cache_size = -512000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.commit()
    return conn


def flush_batch(conn: sqlite3.Connection, batch: BatchAccumulator) -> None:
    if not batch.bins:
        return

    bin_rows = []
    move_rows = []
    position_rows = set()
    for (key_hex, bin_value), delta in batch.bins.items():
        position_rows.add(key_hex)
        bin_rows.append(
            (key_hex, bin_value, delta.games, delta.wins, delta.losses, delta.draws)
        )
        for move_uci, count in delta.moves.items():
            move_rows.append((key_hex, bin_value, move_uci, count))

    conn.executemany(
        "INSERT OR IGNORE INTO positions (position_key, fen) VALUES (?, '')",
        [(key,) for key in position_rows],
    )
    conn.executemany(
        """
        INSERT INTO bin_stats (position_key, elo_bin, games, wins, losses, draws)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(position_key, elo_bin) DO UPDATE SET
          games  = games  + excluded.games,
          wins   = wins   + excluded.wins,
          losses = losses + excluded.losses,
          draws  = draws  + excluded.draws
        """,
        bin_rows,
    )
    conn.executemany(
        """
        INSERT INTO move_stats (position_key, elo_bin, move_uci, games)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(position_key, elo_bin, move_uci) DO UPDATE SET
          games = games + excluded.games
        """,
        move_rows,
    )
    conn.commit()
    batch.clear()


def write_meta(conn: sqlite3.Connection, meta: dict[str, str]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        meta.items(),
    )
    conn.commit()


def iter_game_texts(text: io.TextIOBase) -> Iterator[str]:
    chunks: list[str] = []
    for line in text:
        if line.startswith("[Event ") and chunks:
            yield "".join(chunks)
            chunks = [line]
        else:
            chunks.append(line)
    if chunks:
        yield "".join(chunks)


def process_game_chunk(game_text: str) -> tuple[BatchAccumulator, int, int]:
    visitor = chess.pgn.read_game(
        io.StringIO(game_text),
        Visitor=GameStatsVisitor,
    )
    if visitor is None:
        return BatchAccumulator(), 0, 1
    skipped = 1 if visitor.skipped else 0
    return visitor.batch, visitor.recorded, skipped


def build(
    pgn_path: Path,
    db_path: Path,
    schema_path: Path,
    *,
    fresh: bool = True,
    incremental: bool = True,
    flush_every: int = 5_000,
    max_games: int | None = None,
    progress_every: int = 5_000,
    workers: int = 1,
    chunk_size: int = 256,
) -> dict[str, int | float]:
    conn = init_db(db_path, schema_path, fresh=fresh, incremental=incremental)
    batch = BatchAccumulator()

    started = time.time()
    games_processed = 0
    games_skipped_no_elo = 0
    positions_recorded = 0
    last_flush_at = 0
    last_progress_at = 0

    write_meta(
        conn,
        {
            "build_status": "running",
            "source_pgn": str(pgn_path),
            "games_processed": "0",
            "positions_recorded": "0",
            "started_at": str(int(started)),
            "workers": str(workers),
            "flush_every": str(flush_every),
        },
    )

    def maybe_flush(force: bool = False) -> None:
        nonlocal last_flush_at
        if not force and games_processed - last_flush_at < flush_every:
            return
        flush_batch(conn, batch)
        write_meta(
            conn,
            {
                "build_status": "running",
                "games_processed": str(games_processed),
                "games_skipped_no_elo": str(games_skipped_no_elo),
                "positions_recorded": str(positions_recorded),
                "last_flush_games": str(games_processed),
                "last_flush_at": str(int(time.time())),
                "elapsed_seconds": str(int(time.time() - started)),
            },
        )
        last_flush_at = games_processed

    dctx = zstandard.ZstdDecompressor()
    with pgn_path.open("rb") as raw:
        with dctx.stream_reader(raw) as reader:
            text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")

            if workers <= 1:
                while True:
                    if max_games is not None and games_processed >= max_games:
                        break
                    visitor = chess.pgn.read_game(text, Visitor=GameStatsVisitor)
                    if visitor is None:
                        break
                    batch.merge(visitor.batch)
                    positions_recorded += visitor.recorded
                    if visitor.skipped:
                        games_skipped_no_elo += 1
                    games_processed += 1
                    maybe_flush()
                    if games_processed - last_progress_at >= progress_every:
                        _log_progress(games_processed, positions_recorded, started)
                        last_progress_at = games_processed
            else:
                pending: list[str] = []

                def consume(results: list[tuple[BatchAccumulator, int, int]]) -> None:
                    nonlocal positions_recorded, games_skipped_no_elo
                    for part, recorded, skipped in results:
                        batch.merge(part)
                        positions_recorded += recorded
                        games_skipped_no_elo += skipped

                with mp.Pool(processes=workers) as pool:
                    for game_text in iter_game_texts(text):
                        if max_games is not None and games_processed >= max_games:
                            break
                        pending.append(game_text)
                        games_processed += 1
                        if len(pending) >= chunk_size:
                            consume(pool.map(process_game_chunk, pending))
                            pending.clear()
                            maybe_flush()
                            if games_processed - last_progress_at >= progress_every:
                                _log_progress(games_processed, positions_recorded, started)
                                last_progress_at = games_processed
                    if pending:
                        consume(pool.map(process_game_chunk, pending))

    maybe_flush(force=True)

    elapsed = time.time() - started
    write_meta(
        conn,
        {
            "build_status": "complete",
            "source_pgn": str(pgn_path),
            "games_processed": str(games_processed),
            "games_skipped_no_elo": str(games_skipped_no_elo),
            "positions_recorded": str(positions_recorded),
            "elo_bin_size": "100",
            "position_key": "zobrist_hash_hex",
            "dedupe": "once_per_game_per_position",
            "move_notation": "uci",
            "workers": str(workers),
            "elapsed_seconds": str(int(elapsed)),
            "completed_at": str(int(time.time())),
        },
    )
    conn.close()

    return {
        "games_processed": games_processed,
        "games_skipped_no_elo": games_skipped_no_elo,
        "positions_recorded": positions_recorded,
        "elapsed_seconds": elapsed,
        "workers": workers,
    }


def _log_progress(games_processed: int, positions_recorded: int, started: float) -> None:
    elapsed = time.time() - started
    rate = games_processed / elapsed if elapsed else 0.0
    print(
        f"games={games_processed:,} positions={positions_recorded:,} rate={rate:,.0f} games/s",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pgn",
        type=Path,
        default=Path("data/lichess_db_standard_rated_2026-04.pgn.zst"),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/processed/position_stats.db"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("pipeline/schema.sql"),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=True,
        help="Delete existing DB before build (default: true)",
    )
    parser.add_argument(
        "--no-fresh",
        action="store_false",
        dest="fresh",
        help="Keep existing DB (not recommended mid-build)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="WAL mode + frequent commits for live readers (default: true)",
    )
    parser.add_argument(
        "--flush-every",
        type=int,
        default=5_000,
        help="Commit to SQLite every N games (default: 5000)",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Stop after N games (testing)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Worker processes (default: 1 — best for incremental single-writer)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=256,
        help="Games per multiprocessing batch",
    )
    args = parser.parse_args()

    if not args.pgn.exists():
        parser.error(f"PGN not found: {args.pgn}")

    stats = build(
        args.pgn,
        args.db,
        args.schema,
        fresh=args.fresh,
        incremental=args.incremental,
        flush_every=args.flush_every,
        max_games=args.max_games,
        workers=args.workers,
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
