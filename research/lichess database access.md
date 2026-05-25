# Lichess database — what it is and how to access it

Plain-language guide to the **Lichess open database** as used by this project: what the files contain, how big they are, how you get them, and what “API” means (and does not mean) in this context.

*Last updated: 2026-05-25*

Related: `research/chess open databases.md` (why we chose Lichess), `purpose.md` (project goal).

---

## Project decision — MVP ingest scope

**We download one recent month only and build the pipeline on that.**

| Field | Value |
|-------|--------|
| **Scope** | **1 monthly file** — not the full 2.46 TB archive |
| **Which month** | Latest **complete** month listed on [database.lichess.org/standard](https://database.lichess.org/standard/) at download time (e.g. `lichess_db_standard_rated_2026-04.pgn.zst`) |
| **Expected size** | ~**28–32 GB** compressed, ~**85–100 million** games |
| **Local storage** | Keep that single `.pgn.zst` on disk; stream-parse without full decompression |
| **Later** | Add more months only after the pipeline works; revisit rolling window / cloud then |

Decision recorded: **2026-05-25**.

---

## What this database is

The [Lichess open database](https://database.lichess.org/) is **not** a live query service over all Lichess games. It is a set of **static file exports** that Lichess publishes periodically for anyone to download, modify, and redistribute (CC0 license).

For this project we use one slice of it:

| Export | Path | What it is |
|--------|------|------------|
| **Standard rated games** ✅ | https://database.lichess.org/standard/ | Every rated standard-chess game played on lichess.org, one archive per calendar month |

Each game is a **PGN** record: moves plus headers (player names, **Glicko-2 ratings** as `WhiteElo` / `BlackElo`, time control, date, result, opening tags, etc.).

**Important mental model:**

```
Lichess website (live)          database.lichess.org (bulk files)          Our app (future)
─────────────────────          ───────────────────────────────          ────────────────
Billions of games in DB    →    Monthly .pgn.zst downloads          →    Processed puzzle DB
Real-time play / API            Offline batch / research use              Small, fast to query
```

We will **not** point the puzzle app at the raw 2+ TB dump at runtime. We will **download → process offline → store a much smaller derived database** of candidate puzzles.

---

## Size of the full standard database

Official totals from [database.lichess.org](https://database.lichess.org/) (as of early 2026):

| Measure | Value |
|---------|--------|
| **Games** | **~7.77 billion** (7,772,124,731) |
| **Files** | **160** monthly archives (Jan 2013 → present) |
| **Compressed size** | **~2.46 TB** (all `.pgn.zst` files combined) |
| **Uncompressed PGN** | **~7.1× larger** → roughly **~17 TB** if fully expanded to plain PGN |
| **Typical recent month** | **~28–32 GB** compressed, **~85–100 million** games |

Community rule of thumb (Lichess forum): “a little over **2 TB** compressed; plan **~15–18 TB** if you decompress everything to plain PGN.”

### Scale in human terms

- Downloading **everything** is a multi-day transfer on a fast home connection and needs **multi-terabyte disk**.
- A **single recent month** (~30 GB compressed) is a reasonable starting point for prototyping.
- **One year** of recent data is on the order of **~350 GB** compressed — still large, but tractable for a dedicated machine.

### Other Lichess exports (same site, optional later)

| Export | Positions / games | Approx. size | Notes |
|--------|-------------------|--------------|--------|
| **Eval JSONL** (`lichess_db_eval.jsonl.zst`) | ~379M unique FENs with Stockfish evals | ~**17 GB** compressed (~**83 GB** decompressed) | Position lookup, not full games |
| **Puzzles CSV** | ~5.9M Lichess puzzles | Small (~hundreds of MB) | Different puzzle model; useful for comparison |
| **Hugging Face Parquet** ([`Lichess/standard-chess-games`](https://huggingface.co/datasets/Lichess/standard-chess-games)) | Same games as standard dump | Large; partitioned by year/month | Filter with SQL/DuckDB/Pandas without holding all PGN locally |

---

## How the database can be accessed

There are **three different “access patterns”**. Only the first two matter for building our puzzle pipeline.

### 1. Bulk file download (primary — this is how we use it)

**URL pattern:**

```
https://database.lichess.org/standard/lichess_db_standard_rated_YYYY-MM.pgn.zst
```

**Example:**

```
https://database.lichess.org/standard/lichess_db_standard_rated_2025-01.pgn.zst
```

**Helper files for automation:**

| File | URL | Purpose |
|------|-----|---------|
| File list | https://database.lichess.org/standard/list.txt | All download URLs |
| Game counts | https://database.lichess.org/standard/counts.txt | Games per month |
| Checksums | https://database.lichess.org/standard/sha256sums.txt | Verify downloads |

**Also available:** BitTorrent links per month (same page as HTTP downloads).

**Compression:** Zstandard (`.zst`). Tools: `zstd`, `pzstd`, PeaZip, 7-Zip (with plugin).

**Useful properties:**

- **Partial download works** — `.zst` can be truncated and still partially decompressed (good for sampling).
- **Stream without full decompress** — pipe to a parser:

  ```bash
  zstdcat lichess_db_standard_rated_2025-01.pgn.zst | python ingest.py
  ```

- **Do not merge into one giant PGN** unless you have a very good reason; process month-by-month.

**License:** CC0 — no permission needed for download, storage, commercial use, or redistribution of processed derivatives.

---

### 2. Hugging Face Parquet mirror (optional — filter before download)

**URL:** https://huggingface.co/datasets/Lichess/standard-chess-games

Same underlying games, stored as **Parquet** partitioned by `year` and `month`. Intended for **data analysis**: filter by Elo, time control, etc., then export a subset to PGN or process in place.

**When to use:** If you want to avoid downloading months you will immediately discard (e.g. “only blitz, both players 1200–1800, 2023–2024”) without scanning terabytes of PGN locally first.

**Caveat:** Dataset card notes it may still be a work in progress; for canonical PGN, `database.lichess.org` remains the source of truth.

---

### 3. Lichess.org API (NOT for bulk database access)

The [Lichess API](https://lichess.org/api) is for **live site features**, not for mining the full game corpus.

| Endpoint | What it does | Relevant to us? |
|----------|--------------|-----------------|
| `GET /api/games/user/{username}` | Export **one user’s** games (PGN or NDJSON), throttled | No — wrong scale |
| Opening Explorer (`explorer.lichess.org`) | Move statistics for a **single position** | Maybe later — enrichment only |
| Puzzles API | Lichess puzzle training | No — we build our own puzzles |
| OAuth / bot / board APIs | Play, studies, tournaments | No |

**Export throttle (games API):** roughly **20–60 games per second** depending on auth — fine for a user backup, useless for 7.8B games (would take years).

**Bottom line:** There is **no REST API** that says “give me all games where both players are 1500 and move 25 has a big eval swing.” That query runs on **downloaded files** or **our own processed store**.

---

## Are we storing it locally?

**Short answer:** For MVP, we store **one recent monthly file** locally (~30 GB compressed). We do **not** download the full archive. The finished puzzle app uses a **small derived database**, not raw Lichess PGN.

### Architecture (MVP — one month)

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase A — Ingest (MVP)                                         │
│  Download ONE recent monthly .pgn.zst  →  local disk            │
│  (keep compressed; stream-parse)                                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase B — Extract & score (batch)                              │
│  Parse PGN → positions + metadata → run eval / gap model        │
│  Keep only positions passing “interesting” threshold            │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase C — Application database (runtime)                       │
│  Small indexed store: FEN, solution, game link, Elo band, gap   │
│  App reads THIS — not raw Lichess PGN                           │
└─────────────────────────────────────────────────────────────────┘
```

### Storage options

| Strategy | Raw Lichess on disk | Status |
|----------|---------------------|--------|
| **A. Minimal — one month** | 1 recent `.pgn.zst` (~30 GB) | ✅ **Chosen for MVP** |
| **B. Rolling window** | e.g. last 12–24 months (~350–700 GB) | Deferred |
| **C. Full archive** | All 160 files (~2.46 TB) | Deferred |
| **D. Cloud object storage** | S3/GCS/Azure bucket | Deferred |

### What we store per puzzle (derived data — not decided yet)

Likely much smaller than source PGN: FEN, side to move, best move(s), eval gap, source game ID/URL, player Elos, ply, time control. Exact schema = next planning task in `project_future_plan.md`.

---

## What’s inside a standard game file (PGN)

Typical headers (not every tag on every game):

```
[Event "Rated Blitz game"]
[Site "https://lichess.org/abc123"]
[White "player_a"]
[Black "player_b"]
[Result "1-0"]
[UTCDate "2025.01.15"]
[UTCTime "20:31:42"]
[WhiteElo "1523"]
[BlackElo "1487"]
[TimeControl "180+2"]
[ECO "C42"]
[Opening "Petrov Defense"]
```

Moves are standard SAN; some games include `[%clk ...]` clock comments (since ~2017) and occasionally `[%eval ...]` (~**6%** of games in Parquet derivative — not reliable for full coverage).

**Ratings are Glicko-2**, not FIDE Elo. For “player at 1500 vs player at 1800” logic, treat them as the project’s rating axis unless we calibrate later.

---

## Known limitations

From Lichess documentation:

- Monthly files are **not cumulative** — each file is that month only.
- Very large single PGN files **break** desktop tools (ChessBase, SCID); use code (`python-chess`, etc.) or stream.
- Documented **data quality issues** in some date ranges (bad evals, wrong results, variant mis-tags in old months) — filter or exclude those periods when scoring.
- **Eval export** is separate from games; FEN keys may not include en-passant square in all cases — normalize when joining.

---

## How this project will use the database (planned)

1. **Download** one recent monthly standard rated `.pgn.zst` file.
2. **Stream-parse** games; filter by rating band, time control, game phase (e.g. skip opening book).
3. **Extract candidate positions** (likely: moments where the played move exists and we can compare strengths).
4. **Score** each position with our “win-rate gap at Elo vs Elo+300” definition (engine/model TBD).
5. **Persist** passing positions into an application database.
6. **Serve puzzles** from the application database only.

The Lichess dump is **input material**. The puzzle app’s database is **output**.

---

## Quick reference

| Question | Answer |
|----------|--------|
| Full database size? | **~2.46 TB** compressed, **~7.77B** games, **~17 TB** if fully decompressed |
| Is there a query API over all games? | **No** — bulk files + your own pipeline |
| Do we store everything locally? | **No** — MVP keeps **one month** (~30 GB compressed); app uses derived puzzle DB |
| Primary access URL | https://database.lichess.org/standard/ |
| License | **CC0** |
| Rating field in games | `WhiteElo`, `BlackElo` (Glicko-2) |

---

## Sources

- https://database.lichess.org/
- https://database.lichess.org/standard/
- https://lichess.org/api
- https://huggingface.co/datasets/Lichess/standard-chess-games
- https://github.com/lichess-org/database
- Lichess forum discussion on total download size (~2 TB / ~15 TB decompressed)
