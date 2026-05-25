#!/usr/bin/env python3
"""
Stream Lichess standard PGN (.pgn.zst) and build a processed SQLite position database.

Each position is keyed by normalized FEN (transpositions merge).
Stats are aggregated in 100-point Elo bins for the player to move.
"""

from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import chess.pgn
import zstandard

from pipeline.position_key import (
    elo_bin,
    normalized_fen,
    outcome_for_player_to_move,
    parse_elo,
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
  """In-memory deltas flushed periodically to SQLite."""

  positions: dict[str, str] = field(default_factory=dict)
  bins: dict[tuple[str, int], BinDelta] = field(default_factory=dict)

  def clear(self) -> None:
    self.positions.clear()
    self.bins.clear()

  def add(
      self,
      position_key: str,
      fen: str,
      bin_value: int,
      outcome: str,
      move_uci: str,
  ) -> None:
    self.positions[position_key] = fen
    key = (position_key, bin_value)
    delta = self.bins.get(key)
    if delta is None:
      delta = BinDelta()
      self.bins[key] = delta
    delta.games += 1
    if outcome == "win":
      delta.wins += 1
    elif outcome == "loss":
      delta.losses += 1
    else:
      delta.draws += 1
    delta.moves[move_uci] = delta.moves.get(move_uci, 0) + 1


def init_db(db_path: Path, schema_path: Path, *, bulk: bool = False) -> sqlite3.Connection:
  db_path.parent.mkdir(parents=True, exist_ok=True)
  if bulk and db_path.exists():
    try:
      db_path.unlink()
    except OSError:
      pass
  conn = sqlite3.connect(db_path)
  if bulk:
    conn.executescript(
        """
        DROP TABLE IF EXISTS move_stats;
        DROP TABLE IF EXISTS bin_stats;
        DROP TABLE IF EXISTS positions;
        DROP TABLE IF EXISTS meta;
        """
    )
  conn.executescript(schema_path.read_text(encoding="utf-8"))
  if bulk:
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
  conn.execute("PRAGMA cache_size = -512000")  # ~512 MiB page cache
  return conn


def flush_batch(conn: sqlite3.Connection, batch: BatchAccumulator) -> None:
  if not batch.positions and not batch.bins:
    return

  conn.executemany(
      "INSERT OR IGNORE INTO positions (position_key, fen) VALUES (?, ?)",
      batch.positions.items(),
  )

  bin_rows = []
  move_rows = []
  for (position_key, bin_value), delta in batch.bins.items():
    bin_rows.append(
        (position_key, bin_value, delta.games, delta.wins, delta.losses, delta.draws)
    )
    for move_uci, count in delta.moves.items():
      move_rows.append((position_key, bin_value, move_uci, count))

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


def process_game(game: chess.pgn.Game, batch: BatchAccumulator) -> int:
  """
  Extract position stats from one game.

  Returns the number of position occurrences recorded.
  Each game contributes at most once per distinct position (first time reached).
  """
  white_elo = parse_elo(game.headers.get("WhiteElo"))
  black_elo = parse_elo(game.headers.get("BlackElo"))
  if white_elo is None or black_elo is None:
    return 0

  result = game.headers.get("Result", "*")
  board = game.board()
  seen: set[str] = set()
  recorded = 0

  for move in game.mainline_moves():
    position_key = normalized_fen(board)
    if position_key not in seen:
      seen.add(position_key)
      player_elo = white_elo if board.turn == chess.WHITE else black_elo
      outcome = outcome_for_player_to_move(board, result)
      if outcome is None:
        board.push(move)
        continue
      batch.add(
          position_key=position_key,
          fen=position_key,
          bin_value=elo_bin(player_elo),
          outcome=outcome,
          move_uci=move.uci(),
      )
      recorded += 1
    board.push(move)

  return recorded


def write_meta(conn: sqlite3.Connection, meta: dict[str, str]) -> None:
  conn.executemany(
      "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
      meta.items(),
  )
  conn.commit()


def build(
    pgn_path: Path,
    db_path: Path,
    schema_path: Path,
    *,
    flush_every: int = 20_000,
    max_games: int | None = None,
    progress_every: int = 10_000,
) -> dict[str, int | float]:
  conn = init_db(db_path, schema_path, bulk=True)
  batch = BatchAccumulator()

  started = time.time()
  games_processed = 0
  games_skipped_no_elo = 0
  positions_recorded = 0

  dctx = zstandard.ZstdDecompressor()
  with pgn_path.open("rb") as raw:
    with dctx.stream_reader(raw) as reader:
      text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
      while True:
        if max_games is not None and games_processed >= max_games:
          break
        game = chess.pgn.read_game(text)
        if game is None:
          break

        white_elo = parse_elo(game.headers.get("WhiteElo"))
        black_elo = parse_elo(game.headers.get("BlackElo"))
        if white_elo is None or black_elo is None:
          games_skipped_no_elo += 1
          games_processed += 1
          continue

        positions_recorded += process_game(game, batch)
        games_processed += 1

        if games_processed % flush_every == 0:
          flush_batch(conn, batch)

        if games_processed % progress_every == 0:
          elapsed = time.time() - started
          rate = games_processed / elapsed if elapsed else 0.0
          print(
              f"games={games_processed:,} positions={positions_recorded:,} "
              f"rate={rate:,.0f} games/s",
              file=sys.stderr,
          )

  flush_batch(conn, batch)

  conn.execute("PRAGMA journal_mode = WAL")
  conn.execute("PRAGMA synchronous = NORMAL")
  conn.commit()

  write_meta(
      conn,
      {
          "source_pgn": str(pgn_path),
          "games_processed": str(games_processed),
          "games_skipped_no_elo": str(games_skipped_no_elo),
          "positions_recorded": str(positions_recorded),
          "elo_bin_size": "100",
          "position_key": "normalized_fen_fields_1_4",
          "dedupe": "once_per_game_per_position",
          "move_notation": "uci",
      },
  )
  conn.close()

  elapsed = time.time() - started
  return {
      "games_processed": games_processed,
      "games_skipped_no_elo": games_skipped_no_elo,
      "positions_recorded": positions_recorded,
      "elapsed_seconds": elapsed,
  }


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "--pgn",
      type=Path,
      default=Path("data/lichess_db_standard_rated_2026-04.pgn.zst"),
      help="Input Lichess monthly PGN (.pgn.zst)",
  )
  parser.add_argument(
      "--db",
      type=Path,
      default=Path("data/processed/position_stats.db"),
      help="Output SQLite database path",
  )
  parser.add_argument(
      "--schema",
      type=Path,
      default=Path("pipeline/schema.sql"),
      help="SQL schema file",
  )
  parser.add_argument(
      "--flush-every",
      type=int,
      default=5_000,
      help="Flush in-memory batch every N games",
  )
  parser.add_argument(
      "--max-games",
      type=int,
      default=None,
      help="Stop after N games (for testing)",
  )
  args = parser.parse_args()

  if not args.pgn.exists():
    parser.error(f"PGN not found: {args.pgn}")

  stats = build(
      args.pgn,
      args.db,
      args.schema,
      flush_every=args.flush_every,
      max_games=args.max_games,
  )
  print(json.dumps(stats, indent=2))


if __name__ == "__main__":
  main()
