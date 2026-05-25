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

Raw Lichess PGN is games-centric. We build a **processed, position-centric** SQLite database under `data/processed/`.

#### Methodology (decided 2026-05-25)

| Topic | Rule |
|-------|------|
| **Position identity** | Normalized FEN = fields 1–4 only (pieces, side to move, castling, en passant). Halfmove/fullmove counters omitted so **transpositions share one key**. |
| **Whose Elo** | Rating of the **player to move** at that position (`WhiteElo` or `BlackElo` from PGN). |
| **Elo binning** | **100-point bins** by floor: 0–99→bin `0`, 100–199→bin `100`, …, 1523→bin `1500`. |
| **Outcome stats** | Per bin: **games**, **wins**, **losses**, **draws** from the **player-to-move** perspective (game `Result` tag). |
| **Move stats** | For each legal **next move actually played**, count games per **UCI** move (e.g. `e2e4`) in that bin. |
| **Dedup within game** | Each game counts **at most once per position** (first time that position is reached). Matches standard opening-database practice; “games” = distinct games reaching the position. |
| **Skip** | Games missing either player rating; unknown/unplayed results (`*`). |
| **Storage** | SQLite: `positions`, `bin_stats`, `move_stats` — see `pipeline/schema.sql`. |
| **Build** | Stream `.pgn.zst` → batch aggregate → flush every 5k games. Script: `pipeline/build_position_db.py`. |

- [x] **Design the processed database format** — SQLite schema in `pipeline/schema.sql`.
- [x] Define the **position key** — normalized FEN (4 fields).
- [x] Design the **batch pipeline** — `pipeline/build_position_db.py`.
- [ ] **Run full build** on `data/lichess_db_standard_rated_2026-04.pgn.zst` → `data/processed/position_stats.db`.
- [ ] Estimate **processed DB size** and wall-clock time after first full run (or large sample).

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
