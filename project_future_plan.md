# Project future plan

Next steps and action items. When an item is completed, move it to `project_history.md` with a date.

---

## Decisions (locked in)

| Decision | Choice | Reference |
|----------|--------|-----------|
| Game database | **Lichess open database** — standard rated chess | https://database.lichess.org/standard/ |
| License | CC0 (commercial use OK) | `purpose.md`, `research/chess open databases.md` |
| Variants | Standard chess only (not Atomic, Chess960, etc.) | — |
| Access model | Bulk monthly `.pgn.zst` download; **no** full-corpus API | `research/lichess database access.md` |
| Raw storage (MVP) | **One recent month only** — single `.pgn.zst` locally (~30 GB); no full archive | `research/lichess database access.md` |

---

## Phase 0 — Discovery and constraints

- [x] Confirm which **open databases** to use and license terms. → **Decided: Lichess standard rated PGN (CC0).** Survey: `research/chess open databases.md`.
- [ ] Decide **minimum data** needed per position: FEN, side to move, game metadata (Elo, time control, date), preceding moves, result.
- [x] Choose **raw Lichess storage strategy** → **One recent month only** (Strategy A). See `research/lichess database access.md`.
- [ ] Define **target user rating bands** (e.g. 800–2400) and whether puzzles are personalized per logged-in rating or chosen manually.
- [ ] Write a one-paragraph **MVP scope**: what the first usable version must do vs. what is deferred.

## Phase 1 — “Interesting position” definition (spec)

- [ ] Pin down the **win-rate gap metric**: absolute difference, ratio, or log-odds; threshold values for “interesting.”
- [ ] Specify **engine / eval source** for win rates at two virtual strengths (player Elo vs. player Elo + 300)—table lookup, neural net, or engine + Elo-adjusted depth.
- [ ] Decide whether gap is measured on **best move vs. played move**, **top-N moves**, or **single critical moment** (blunder / missed win).
- [ ] Document edge cases: equal material but eval swing, forced lines, tablebase, insufficient material, repetition.

## Phase 2 — Data pipeline (design only until build)

### Processed position database (first build stage — current focus)

Raw Lichess PGN is games-centric. We need a **processed, position-centric** store: each entry is a **position** (FEN or equivalent key), with a **list of game occurrences** at that position (game id, player Elos, side to move, ply, result, etc.). This enables searching for the same position across e.g. ~1000-rated and ~1300-rated games.

- [ ] **Design the processed database format** — schema, on-disk format, and indexing strategy optimized for “lookup by position → list of games,” not for storing raw PGN long-term.
- [ ] Compare candidate formats (e.g. SQLite/Parquet/DuckDB, custom binary index, embedded KV) for **one month (~85–100M games)** ingest and query by FEN + Elo band.
- [ ] Define the **position key** (normalized FEN? hash of board + side to move + castling + en passant?) and what metadata each **game occurrence** must carry.
- [ ] Design the **batch pipeline**: stream-parse `.pgn.zst` → emit every position (or filtered plies) → aggregate into position index → write processed DB under `data/` (separate from raw dump).
- [ ] Estimate **processed DB size** vs raw (~27 GB) and expected build time for one month.

### Later pipeline stages

- [ ] Design Lichess ingestion: download **one recent** monthly `.pgn.zst` from `/standard/` → stream-parse (PGN) → extract positions → dedupe → store.
- [ ] Design filtering pipeline: Elo window, move number bounds, exclude openings/book if desired.
- [ ] Design batch job to **score positions** and tag those above the gap threshold.
- [ ] Estimate **storage and compute** for scoring/eval (positions count, eval cost, refresh cadence).

## Phase 3 — Puzzle product shape

- [ ] Define puzzle UX: show position, user finds move, feedback, solution line, optional “what was played in the game.”
- [ ] Decide **difficulty label** (gap size, Elo of game, move complexity).
- [ ] Plan **quality control**: false positives, multiple good moves, human review sample.

## Phase 4 — Tech stack (decision backlog)

- [ ] Choose languages/runtime, DB, and whether eval runs **offline batch** vs. **on-demand**.
- [ ] Choose frontend platform (web first vs. mobile).
- [ ] Sketch repo layout and module boundaries (no code required until stack is chosen).

## Open questions

- Is **+300 Elo** the right offset for all rating bands, or should it scale (e.g. +200 at master level)?
- Do we require **only positions where the player to move is the “hero”** (the side that can improve eval)?
- Legal/compliance: CC0 requires no attribution, but should we still credit Lichess in the app UI anyway?
