"""FastAPI server for the position explorer and puzzle frontend."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from api.db import DEFAULT_DB, get_build_meta, get_connection, get_position_stats
from api.puzzle import find_puzzle, iter_find_puzzle

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Chess Realistic Puzzles")


@app.get("/api/health")
def health() -> dict:
    if not DEFAULT_DB.exists():
        return {"ok": False, "error": "database not found"}
    try:
        conn = get_connection()
        meta = get_build_meta(conn)
        conn.close()
        return {
            "ok": True,
            "build_status": meta.get("build_status", "unknown"),
            "games_processed": meta.get("games_processed"),
            "positions_recorded": meta.get("positions_recorded"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@app.get("/api/position/stats")
def position_stats(fen: str = Query(..., min_length=10)) -> dict:
    if not DEFAULT_DB.exists():
        raise HTTPException(503, "Database not found. Is the build running?")
    try:
        conn = get_connection()
        stats = get_position_stats(conn, fen)
        stats["meta"] = get_build_meta(conn)
        conn.close()
        return stats
    except ValueError as exc:
        raise HTTPException(400, f"Invalid FEN: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(503, f"Database error: {exc}") from exc


@app.get("/api/puzzle/next")
def puzzle_next(
    elo: int = Query(..., ge=400, le=3500),
    min_games: int = Query(25, ge=5, le=10_000),
    improvement: float = Query(0.10, ge=0.01, le=0.5),
    max_attempts: int = Query(5000, ge=100, le=50_000),
    elo_diff: int = Query(300, ge=50, le=800),
) -> dict:
    if not DEFAULT_DB.exists():
        raise HTTPException(503, "Database not found. Is the build running?")
    try:
        conn = get_connection()
        puzzle, reason, search = find_puzzle(
            conn,
            elo,
            min_games=min_games,
            improvement_threshold=improvement,
            max_attempts=max_attempts,
            elo_diff=elo_diff,
        )
        meta = get_build_meta(conn)
        conn.close()
    except sqlite3.Error as exc:
        raise HTTPException(503, f"Database error: {exc}") from exc

    if puzzle is None:
        raise HTTPException(
            404,
            detail={
                "message": "Could not find a puzzle matching your criteria.",
                "reason": reason,
                "search": search.to_dict(),
            },
        )

    payload = puzzle.to_dict()
    payload["meta"] = meta
    return payload


@app.get("/api/puzzle/next/stream")
def puzzle_next_stream(
    elo: int = Query(..., ge=400, le=3500),
    min_games: int = Query(25, ge=5, le=10_000),
    improvement: float = Query(0.10, ge=0.01, le=0.5),
    max_attempts: int = Query(5000, ge=100, le=50_000),
    elo_diff: int = Query(300, ge=50, le=800),
) -> StreamingResponse:
    if not DEFAULT_DB.exists():
        raise HTTPException(503, "Database not found. Is the build running?")

    def generate():
        try:
            conn = get_connection()
            for event in iter_find_puzzle(
                conn,
                elo,
                min_games=min_games,
                improvement_threshold=improvement,
                max_attempts=max_attempts,
                elo_diff=elo_diff,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            conn.close()
        except sqlite3.Error as exc:
            payload = {
                "event": "error",
                "reason": "database_error",
                "message": str(exc),
                "search": {"evaluated": 0, "rejections": {}, "pgn_games_scanned": 0},
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/puzzle")
def puzzle_page() -> FileResponse:
    return FileResponse(FRONTEND / "puzzle.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
