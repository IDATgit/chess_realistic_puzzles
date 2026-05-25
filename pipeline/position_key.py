"""Canonical position identity (transpositions merge)."""

from __future__ import annotations

import chess
import chess.polyglot


def position_key(board: chess.Board) -> int:
    """Fast transposition key (Zobrist hash of board + side + castling + en passant)."""
    return chess.polyglot.zobrist_hash(board)


def position_key_hex(board: chess.Board) -> str:
    return f"{position_key(board):016x}"


def storage_fen(board: chess.Board) -> str:
    """Human-readable FEN (4 fields) stored once per position for display/debug."""
    ep = chess.square_name(board.ep_square) if board.ep_square else "-"
    turn = "w" if board.turn else "b"
    return f"{board.board_fen()} {turn} {board.castling_xfen()} {ep}"


def normalized_fen(board: chess.Board) -> str:
    """Alias kept for compatibility with docs/tests."""
    return storage_fen(board)


def elo_bin(elo: int) -> int:
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
    if result == "1/2-1/2":
        return "draw"
    if result == "1-0":
        return "win" if board.turn == chess.WHITE else "loss"
    if result == "0-1":
        return "loss" if board.turn == chess.WHITE else "win"
    return None


def outcome_code(outcome: str) -> int:
    return {"loss": 0, "draw": 1, "win": 2}[outcome]
