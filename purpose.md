# Purpose

This project is a **realistic chess puzzle application**.

Unlike typical puzzle apps that use artificial or composed positions, this app draws puzzles from **real games** on **Lichess**, using the [Lichess open database](https://database.lichess.org/) (standard rated games, CC0 license).

The goal is to present positions a player would actually face at their level—moments where strong play matters because the evaluation shifts sharply relative to what someone rated ~300 points higher would expect.

An **interesting position** (a candidate puzzle) is one where there is a **large win-rate gap** between:

- how the position is evaluated for a player at their own rating, and  
- how it is evaluated for a player at roughly **their rating + 300** (or a similar offset).

Those gaps identify moments where the “obvious” or natural move may be weak, while a stronger line is available—making the position teachable and realistic rather than contrived.

The app should help players train on **authentic decision points** from real Lichess games, filtered and ranked by that evaluation gap, so practice feels like improving in real play—not solving unrelated tactical exercises.

## Data source (decided)

| Item | Choice |
|------|--------|
| **Database** | [Lichess open database](https://database.lichess.org/) — **standard rated chess** only |
| **Format** | Monthly PGN dumps (`.pgn.zst`) from `/standard/` |
| **License** | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) — free for commercial use and redistribution |
| **Ratings in data** | Glicko-2 (`WhiteElo`, `BlackElo` in PGN headers) |
| **Optional Lichess add-ons** | Eval JSONL (~379M positions), Hugging Face Parquet mirror for filtering — same CC0 terms |
| **Access & size** | See `research/lichess database access.md` |
| **MVP ingest scope** | **One recent month only** — single `.pgn.zst` file (~30 GB compressed, ~85–100M games); latest complete month on [database.lichess.org/standard](https://database.lichess.org/standard/) |
| **Out of scope** | Other sources (Chess.com, TWIC, ChessBase, etc.) unless explicitly revisited later |
