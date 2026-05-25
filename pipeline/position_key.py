"""Canonical position identity (transpositions merge)."""

from __future__ import annotations

import chess


def normalized_fen(board: chess.Board) -> str:
    """
    Position key: FEN fields 1–4 only (pieces, side, castling, en passant).

    Omits halfmove clock and fullmove number so transpositions share one key.
    """
    parts = board.fen().split(" ")
    return " ".join(parts[:4])


def elo_bin(elo: int) -> int:
    """100-point bins: 0→[0,99], 100→[100,199], 1523→1500, etc."""
    if elo < 0:
        raise ValueError(f"invalid elo: {elo}")
    return (elo // 100) * 100


def parse_elo(header_value: str | None) -> int | None:
    if header_value is None:
        return None
    value = header_value.strip()
    if not value or value == "?":
        return None
    try:
        elo = int(value)
    except ValueError:
        return None
    if elo < 0:
        return None
    return elo


def outcome_for_player_to_move(board: chess.Board, result: str) -> str | None:
    """
    Return 'win', 'loss', or 'draw' for the side to move, from the game result tag.

    Returns None for unfinished/unknown results (skip stat).
    """
    if result == "1/2-1/2":
        return "draw"
    if result == "1-0":
        return "win" if board.turn == chess.WHITE else "loss"
    if result == "0-1":
        return "loss" if board.turn == chess.WHITE else "win"
    return None
