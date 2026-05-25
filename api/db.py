"""Read-only access to the processed position statistics database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import chess
import chess.polyglot

DEFAULT_DB = Path("data/processed/position_stats.db")


def position_key_hex(fen: str) -> str:
    board = chess.Board(fen)
    return f"{chess.polyglot.zobrist_hash(board):016x}"


def get_connection(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5.0)


def get_build_meta(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM meta").fetchall()
    return dict(rows)


def get_position_stats(
    conn: sqlite3.Connection,
    fen: str,
) -> dict:
    key_hex = position_key_hex(fen)
    bins = conn.execute(
        """
        SELECT elo_bin, games, wins, losses, draws
        FROM bin_stats
        WHERE position_key = ?
        ORDER BY elo_bin
        """,
        (key_hex,),
    ).fetchall()

    moves = conn.execute(
        """
        SELECT move_uci, SUM(games) AS games
        FROM move_stats
        WHERE position_key = ?
        GROUP BY move_uci
        ORDER BY games DESC
        LIMIT 50
        """,
        (key_hex,),
    ).fetchall()

    bin_rows = []
    for elo_bin, games, wins, losses, draws in bins:
        if games <= 0:
            continue
        bin_rows.append(
            {
                "elo_bin": elo_bin,
                "elo_label": f"{elo_bin}–{elo_bin + 99}",
                "games": games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": wins / games,
                "draw_rate": draws / games,
                "loss_rate": losses / games,
            }
        )

    move_rows = [{"uci": uci, "games": games} for uci, games in moves]

    return {
        "position_key": key_hex,
        "fen": fen,
        "bins": bin_rows,
        "moves": move_rows,
        "total_games": sum(row["games"] for row in bin_rows),
    }
