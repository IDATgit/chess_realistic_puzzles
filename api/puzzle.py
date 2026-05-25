"""Puzzle selection: positions where stronger players avoid losses more often."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api.pgn_lookup import iter_pgn_positions, pgn_games_scanned
from pipeline.position_key import elo_bin

DEFAULT_MIN_GAMES = 25
DEFAULT_IMPROVEMENT = 0.10
DEFAULT_MAX_ATTEMPTS = 5000
DEFAULT_ELO_DIFF = 300
DEFAULT_PGN = Path("data/lichess_db_standard_rated_2026-04.pgn.zst")
PROGRESS_EVERY = 25


def rejection_labels(min_games: int, elo_diff: int) -> dict[str, str]:
    return {
        "insufficient_low_games": f"Your Elo band has < {min_games} games",
        "missing_high_bin": f"No stats in +{elo_diff} Elo band",
        "insufficient_high_games": f"+{elo_diff} band has < {min_games} games",
        "insufficient_improvement": "Win+draw improvement below threshold",
        "same_top_move": "Same most popular move at both Elo bands",
    }


def not_loss_rate(wins: int, draws: int, games: int) -> float:
    if games <= 0:
        return 0.0
    return (wins + draws) / games


@dataclass
class SearchStats:
    evaluated: int = 0
    rejections: dict[str, int] = field(default_factory=lambda: {
        "insufficient_low_games": 0,
        "missing_high_bin": 0,
        "insufficient_high_games": 0,
        "insufficient_improvement": 0,
        "same_top_move": 0,
    })
    pgn_games_scanned: int = 0
    phase: str = "idle"
    last_rejection: str | None = None
    rejection_labels: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    def record_rejection(self, reason: str) -> None:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1
        self.last_rejection = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "rejections": dict(self.rejections),
            "rejection_labels": self.rejection_labels,
            "pgn_games_scanned": self.pgn_games_scanned,
            "phase": self.phase,
            "last_rejection": self.last_rejection,
            "settings": self.settings,
        }


@dataclass
class PuzzleResult:
    position_key: str
    fen: str
    player_elo: int
    bin_low: int
    bin_high: int
    bin_low_label: str
    bin_high_label: str
    low_games: int
    low_wins: int
    low_draws: int
    low_losses: int
    high_games: int
    high_wins: int
    high_draws: int
    high_losses: int
    low_not_loss_rate: float
    high_not_loss_rate: float
    improvement: float
    elo_diff: int
    min_games: int
    improvement_threshold: float
    solution_uci: str | None
    player_move_uci: str | None
    low_moves: list[dict[str, int | str]]
    high_moves: list[dict[str, int | str]]
    attempts: int
    search: SearchStats | None = None

    def to_dict(self) -> dict:
        payload = {
            "position_key": self.position_key,
            "fen": self.fen,
            "player_elo": self.player_elo,
            "bin_low": self.bin_low,
            "bin_high": self.bin_high,
            "bin_low_label": self.bin_low_label,
            "bin_high_label": self.bin_high_label,
            "low": {
                "games": self.low_games,
                "wins": self.low_wins,
                "draws": self.low_draws,
                "losses": self.low_losses,
                "not_loss_rate": self.low_not_loss_rate,
            },
            "high": {
                "games": self.high_games,
                "wins": self.high_wins,
                "draws": self.high_draws,
                "losses": self.high_losses,
                "not_loss_rate": self.high_not_loss_rate,
            },
            "improvement": self.improvement,
            "elo_diff": self.elo_diff,
            "min_games": self.min_games,
            "improvement_threshold": self.improvement_threshold,
            "solution_uci": self.solution_uci,
            "player_move_uci": self.player_move_uci,
            "low_moves": self.low_moves,
            "high_moves": self.high_moves,
            "attempts": self.attempts,
        }
        if self.search is not None:
            payload["search"] = self.search.to_dict()
        return payload


def _bin_row(
    conn: sqlite3.Connection,
    position_key: str,
    elo_bin_value: int,
) -> tuple[int, int, int, int] | None:
    row = conn.execute(
        """
        SELECT games, wins, losses, draws
        FROM bin_stats
        WHERE position_key = ? AND elo_bin = ?
        """,
        (position_key, elo_bin_value),
    ).fetchone()
    if row is None:
        return None
    return row[0], row[1], row[2], row[3]


def _top_move(
    conn: sqlite3.Connection,
    position_key: str,
    elo_bin_value: int,
) -> str | None:
    row = conn.execute(
        """
        SELECT move_uci FROM move_stats
        WHERE position_key = ? AND elo_bin = ?
        ORDER BY games DESC
        LIMIT 1
        """,
        (position_key, elo_bin_value),
    ).fetchone()
    return row[0] if row else None


def _moves_for_bin(
    conn: sqlite3.Connection,
    position_key: str,
    elo_bin_value: int,
    *,
    limit: int = 12,
) -> list[dict[str, int | str]]:
    rows = conn.execute(
        """
        SELECT move_uci, games FROM move_stats
        WHERE position_key = ? AND elo_bin = ?
        ORDER BY games DESC
        LIMIT ?
        """,
        (position_key, elo_bin_value, limit),
    ).fetchall()
    return [{"uci": uci, "games": games} for uci, games in rows]


def _resolve_pgn_path(conn: sqlite3.Connection, pgn_path: Path) -> Path | None:
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    source = meta.get("source_pgn")
    if source:
        candidate = Path(source)
        if candidate.exists():
            return candidate
    if pgn_path.exists():
        return pgn_path
    return None


def iter_find_puzzle(
    conn: sqlite3.Connection,
    player_elo: int,
    *,
    pgn_path: Path = DEFAULT_PGN,
    min_games: int = DEFAULT_MIN_GAMES,
    improvement_threshold: float = DEFAULT_IMPROVEMENT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    elo_diff: int = DEFAULT_ELO_DIFF,
) -> Iterator[dict[str, Any]]:
    """
    Stream PGN games, evaluate positions against indexed DB stats.

    Fast path: sequential PGN read + primary-key bin_stats lookups
    (avoids ORDER BY RANDOM() on millions of rows).
    """
    bin_low = elo_bin(player_elo)
    bin_high = elo_bin(player_elo + elo_diff)
    stats = SearchStats(rejection_labels=rejection_labels(min_games, elo_diff))
    stats.settings = {
        "min_games": min_games,
        "improvement_threshold": improvement_threshold,
        "elo_diff": elo_diff,
        "max_attempts": max_attempts,
    }
    resolved_pgn = _resolve_pgn_path(conn, pgn_path)

    if resolved_pgn is None:
        yield {
            "event": "error",
            "reason": "pgn_not_found",
            "message": "Source PGN file not found.",
            "search": stats.to_dict(),
        }
        return

    stats.phase = "scanning_pgn"
    yield {"event": "progress", "search": stats.to_dict()}

    for pos_key, fen in iter_pgn_positions(resolved_pgn):
        stats.evaluated += 1
        stats.pgn_games_scanned = pgn_games_scanned(resolved_pgn)

        if stats.evaluated == 1 or stats.evaluated % PROGRESS_EVERY == 0:
            yield {"event": "progress", "search": stats.to_dict()}

        if stats.evaluated > max_attempts:
            break

        row_low = _bin_row(conn, pos_key, bin_low)
        if row_low is None or row_low[0] < min_games:
            stats.record_rejection("insufficient_low_games")
            continue

        g1, w1, l1, d1 = row_low
        row_high = _bin_row(conn, pos_key, bin_high)
        if row_high is None:
            stats.record_rejection("missing_high_bin")
            continue

        g2, w2, l2, d2 = row_high
        if g2 < min_games:
            stats.record_rejection("insufficient_high_games")
            continue

        rate_low = not_loss_rate(w1, d1, g1)
        rate_high = not_loss_rate(w2, d2, g2)
        improvement = rate_high - rate_low
        if improvement < improvement_threshold:
            stats.record_rejection("insufficient_improvement")
            continue

        solution_uci = _top_move(conn, pos_key, bin_high)
        player_move_uci = _top_move(conn, pos_key, bin_low)

        if (
            solution_uci is not None
            and player_move_uci is not None
            and solution_uci == player_move_uci
        ):
            stats.record_rejection("same_top_move")
            continue

        stats.phase = "found"
        puzzle = PuzzleResult(
            position_key=pos_key,
            fen=fen,
            player_elo=player_elo,
            bin_low=bin_low,
            bin_high=bin_high,
            bin_low_label=f"{bin_low}–{bin_low + 99}",
            bin_high_label=f"{bin_high}–{bin_high + 99}",
            low_games=g1,
            low_wins=w1,
            low_draws=d1,
            low_losses=l1,
            high_games=g2,
            high_wins=w2,
            high_draws=d2,
            high_losses=l2,
            low_not_loss_rate=rate_low,
            high_not_loss_rate=rate_high,
            improvement=improvement,
            elo_diff=elo_diff,
            min_games=min_games,
            improvement_threshold=improvement_threshold,
            solution_uci=solution_uci,
            player_move_uci=player_move_uci,
            low_moves=_moves_for_bin(conn, pos_key, bin_low),
            high_moves=_moves_for_bin(conn, pos_key, bin_high),
            attempts=stats.evaluated,
            search=stats,
        )
        payload = puzzle.to_dict()
        payload["event"] = "puzzle"
        yield payload
        return

    stats.phase = "failed"
    yield {
        "event": "error",
        "reason": "no_puzzle_found",
        "message": "Could not find a puzzle matching your criteria.",
        "search": stats.to_dict(),
    }


def find_puzzle(
    conn: sqlite3.Connection,
    player_elo: int,
    *,
    pgn_path: Path = DEFAULT_PGN,
    min_games: int = DEFAULT_MIN_GAMES,
    improvement_threshold: float = DEFAULT_IMPROVEMENT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    elo_diff: int = DEFAULT_ELO_DIFF,
) -> tuple[PuzzleResult | None, str | None, SearchStats]:
    stats = SearchStats()
    last_reason: str | None = None

    for event in iter_find_puzzle(
        conn,
        player_elo,
        pgn_path=pgn_path,
        min_games=min_games,
        improvement_threshold=improvement_threshold,
        max_attempts=max_attempts,
        elo_diff=elo_diff,
    ):
        if event["event"] == "progress":
            continue
        if event["event"] == "puzzle":
            search_data = event.get("search", {})
            stats = SearchStats(
                evaluated=search_data.get("evaluated", 0),
                rejections=search_data.get("rejections", {}),
                pgn_games_scanned=search_data.get("pgn_games_scanned", 0),
                phase=search_data.get("phase", "found"),
                last_rejection=search_data.get("last_rejection"),
                rejection_labels=search_data.get("rejection_labels", {}),
                settings=search_data.get("settings", {}),
            )
            puzzle = PuzzleResult(
                position_key=event["position_key"],
                fen=event["fen"],
                player_elo=event["player_elo"],
                bin_low=event["bin_low"],
                bin_high=event["bin_high"],
                bin_low_label=event["bin_low_label"],
                bin_high_label=event["bin_high_label"],
                low_games=event["low"]["games"],
                low_wins=event["low"]["wins"],
                low_draws=event["low"]["draws"],
                low_losses=event["low"]["losses"],
                high_games=event["high"]["games"],
                high_wins=event["high"]["wins"],
                high_draws=event["high"]["draws"],
                high_losses=event["high"]["losses"],
                low_not_loss_rate=event["low"]["not_loss_rate"],
                high_not_loss_rate=event["high"]["not_loss_rate"],
                improvement=event["improvement"],
                elo_diff=event.get("elo_diff", DEFAULT_ELO_DIFF),
                min_games=event.get("min_games", DEFAULT_MIN_GAMES),
                improvement_threshold=event.get(
                    "improvement_threshold", DEFAULT_IMPROVEMENT
                ),
                solution_uci=event.get("solution_uci"),
                player_move_uci=event.get("player_move_uci"),
                low_moves=event.get("low_moves", []),
                high_moves=event.get("high_moves", []),
                attempts=event["attempts"],
                search=stats,
            )
            return puzzle, None, stats

        last_reason = event.get("reason")
        search_data = event.get("search", {})
        stats = SearchStats(
            evaluated=search_data.get("evaluated", 0),
            rejections=search_data.get("rejections", {}),
            pgn_games_scanned=search_data.get("pgn_games_scanned", 0),
            phase=search_data.get("phase", "failed"),
            last_rejection=search_data.get("last_rejection"),
            rejection_labels=search_data.get("rejection_labels", {}),
            settings=search_data.get("settings", {}),
        )

    return None, last_reason or "no_puzzle_found", stats
