# Project history

A chronological log of completed work. When items in `project_future_plan.md` are done, move them here.

---

- **2026-05-25** — Defined project direction: realistic puzzles from open game databases, filtered by win-rate gap between player Elo and Elo + ~300.
- **2026-05-25** — Created planning docs: `purpose.md`, `project_history.md`, `project_future_plan.md`.
- **2026-05-25** — Surveyed chess game databases (free and commercial); wrote `research/chess open databases.md`. Conclusion: Lichess open database (CC0, ~7.8B standard games) is the strongest primary source for this project.
- **2026-05-25** — **Decision:** use the **Lichess open database** (standard rated PGN, CC0) as the sole game source. Documented in `purpose.md`, `research/chess open databases.md`, and `project_future_plan.md`.
- **2026-05-25** — Documented Lichess access model, size (~2.46 TB compressed / ~7.77B games), and bulk-vs-API distinction in `research/lichess database access.md`.
- **2026-05-25** — **Decision:** MVP ingest uses **one recent month** of Lichess standard games only (~30 GB compressed); no full archive download.
- **2026-05-25** — Downloaded `data/lichess_db_standard_rated_2026-04.pgn.zst` (~27.31 GB, April 2026 standard rated games).
- **2026-05-25** — Implemented position statistics pipeline (`pipeline/build_position_db.py`): normalized FEN keys, 100-point Elo bins, W/D/L + move counts; full-month build started → `data/processed/position_stats.db`.
- **2026-05-25** — Initialized git repo; pushed planning docs to https://github.com/IDATgit/chess_realistic_puzzles (raw `.pgn.zst` gitignored).
