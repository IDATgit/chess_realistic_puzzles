"""Read-only PGN streaming for puzzle sampling (no database writes)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import chess
import chess.pgn
import zstandard

from pipeline.position_key import position_key

_cursor: "PgnGameCursor | None" = None


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


def open_pgn_text(pgn_path: Path) -> io.TextIOBase:
    dctx = zstandard.ZstdDecompressor()
    raw = pgn_path.open("rb")
    reader = dctx.stream_reader(raw)
    return io.TextIOWrapper(reader, encoding="utf-8", errors="replace")


def positions_in_game(game: chess.pgn.Game) -> list[tuple[str, str]]:
    """First-visit mainline positions: (position_key_hex, fen)."""
    board = game.board()
    seen: set[int] = set()
    positions: list[tuple[str, str]] = []
    for move in game.mainline_moves():
        key = position_key(board)
        if key not in seen:
            seen.add(key)
            positions.append((f"{key:016x}", board.fen()))
        board.push(move)
    return positions


class PgnGameCursor:
    """Forward-only game stream."""

    def __init__(self, pgn_path: Path) -> None:
        self.pgn_path = pgn_path
        self._text: io.TextIOBase | None = None
        self._iterator: Iterator[str] | None = None
        self.games_scanned = 0

    def _open(self) -> None:
        if self._iterator is not None:
            return
        self._text = open_pgn_text(self.pgn_path)
        self._iterator = iter_game_texts(self._text)

    def _rewind(self) -> None:
        if self._text is not None:
            self._text.close()
        self._text = None
        self._iterator = None
        self._open()

    def iter_positions(self) -> Iterator[tuple[str, str]]:
        """Yield (position_key_hex, fen) from successive games."""
        self._open()
        assert self._iterator is not None

        while True:
            try:
                game_text = next(self._iterator)
            except StopIteration:
                self._rewind()
                assert self._iterator is not None
                game_text = next(self._iterator)

            self.games_scanned += 1
            game = chess.pgn.read_game(io.StringIO(game_text))
            if game is None:
                continue
            yield from positions_in_game(game)


def iter_pgn_positions(pgn_path: Path) -> Iterator[tuple[str, str]]:
    global _cursor
    resolved = pgn_path.resolve()
    if _cursor is None or _cursor.pgn_path != resolved:
        _cursor = PgnGameCursor(resolved)
    yield from _cursor.iter_positions()


def pgn_games_scanned(pgn_path: Path) -> int:
    global _cursor
    resolved = pgn_path.resolve()
    if _cursor is None or _cursor.pgn_path != resolved:
        return 0
    return _cursor.games_scanned
