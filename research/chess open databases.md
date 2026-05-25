# Chess open databases — survey

Survey of chess game and position databases relevant to building a **realistic puzzle app** from real games. Focus: bulk availability, typical metadata (Elo, time control, PGN), and **license / redistribution** constraints.

*Last updated: 2026-05-25*

---

## Project decision

**This project uses the Lichess open database only.**

| Field | Value |
|-------|--------|
| **Source** | [database.lichess.org](https://database.lichess.org/) |
| **Dataset** | Standard rated chess (`/standard/`) |
| **Format** | Monthly PGN archives (`.pgn.zst`) |
| **License** | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| **Scale** | ~7.8B games (monthly files from 2013 onward) |
| **Ratings** | Glicko-2 in PGN headers (`WhiteElo`, `BlackElo`) |
| **Supplementary Lichess exports** (optional, same license) | Eval JSONL, Hugging Face Parquet mirror |
| **Not in scope** | Chess.com, TWIC, FICS, ChessBase, aggregators, variants |

Decision recorded: **2026-05-25**. See also `purpose.md`, `project_future_plan.md` → Decisions, and **`research/lichess database access.md`** (size, download, API vs bulk, local storage model).

**MVP ingest (2026-05-25):** download **one recent month** only — not the full 2.46 TB archive.

---

## Summary table

| Source | Scale (order of magnitude) | Format | Cost | License / access | Best for this project |
|--------|--------------------------|--------|------|------------------|------------------------|
| **Lichess** (`database.lichess.org`) ✅ **CHOSEN** | ~7.8B standard rated games; ~380M eval positions; ~6M puzzles | PGN (monthly), JSONL evals, CSV puzzles | Free | **CC0** — commercial use OK | **Project database** — huge, Elo in headers, optional evals |
| **Chess.com Published Data API** | Per-player archives (no full dump) | JSON + PGN per month | Free API | Public read-only; rate limits; no bulk “all games” | Supplement; scrape ethically per ToS |
| **TWIC** (The Week in Chess) | ~5k games/week; ~4M+ in paid bundle | PGN / CBV weekly | Free weekly; ~£30 one-time mega archive | Free weekly downloads; bundled DB is donation | High-quality OTB; smaller volume |
| **PGN Mentor** | ~1M+ GM games (site claim) | PGN | Free files | Free download; **no explicit CC license** on site | OTB / historical; check redistribution |
| **FICS Games DB** | ~267M stored games | PGN zip | Free | Free download; quota on some archives | Online legacy; variable quality |
| **Lumbra’s Gigabase** | ~18M games (OTB + online) | PGN / Scid | Free | Aggregator; per-source tags in PGN | Convenient merged set; verify sources |
| **Chessmont Open Database** | ~21.5M curated games; FEN indexes | PGN/TSV `.zst` | Free | Community repack; **verify license per upstream** | Pre-filtered 2400+ / 3min+ slices |
| **Hugging Face `Lichess/standard-chess-games`** | Same as Lichess standard | Parquet | Free | Derived from Lichess CC0 dumps | Analytics / SQL-style filtering |
| **ICCF / correspondence** (e.g. Chess Nerd mirrors) | ~1.2M games | PGN | Free mirrors | ICCF site terms + mirror maintainer | Correspondence only — slow, high accuracy |
| **ChessBase Mega Database** | ~11.7M games | CBV / proprietary | ~€230 | **Commercial license** — no free redistribution | OTB reference; not for open product |
| **Chessgames.com** | Very large OTB archive | PGN zip | ~$39/year premium | **Subscription**; premium-only bulk download | Research only unless licensed |
| **Engine test suites** (CCRL, KCEC) | ~2M / ~135k | PGN | Free | Free for research; **computer games** | Not human-realistic puzzles |

---

## Tier 1 — Strong fits (free, large, realistic human games)

### Lichess open database

- **URL:** https://database.lichess.org/
- **License:** [Creative Commons CC0](https://creativecommons.org/publicdomain/zero/1.0/) — explicit permission for research, commercial use, modification, redistribution without permission.
- **What you get:**
  - **Standard rated chess:** ~**7.77 billion** games (monthly `.pgn.zst` files from 2013 onward; each file is one month, not cumulative). Path: `/standard/`.
  - **Variants:** Atomic, Antichess, Chess960, Crazyhouse, Horde, King of the Hill, Racing Kings, Three-check — each with hundreds of millions of games (usually not wanted for standard puzzles).
  - **Evaluations:** ~**379 million** unique FEN positions with Stockfish evals (JSONL, browser-contributed analysis board). Useful if you want precomputed engine lines without running Stockfish yourself.
  - **Puzzles:** ~**5.94 million** rated puzzles (CSV: FEN, solution moves, puzzle rating, themes, link to source game). **Different product model** (composed puzzle pipeline) — still CC0 and useful for comparison/benchmarking.
  - **Opening names dataset:** https://github.com/lichess-org/chess-openings (CC0).
- **PGN headers (typical):** `WhiteElo`, `BlackElo` (Glicko-2), `UTCDate`, `UTCTime`, `TimeControl`, `ECO`, `Opening`, `Result`, etc.
- **Embedded analysis:** Roughly **~6%** of standard games in the Hugging Face derivative include `[%eval ...]` comments from in-browser analysis (not full-game coverage).
- **Hugging Face mirror:** https://huggingface.co/datasets/Lichess/standard-chess-games — Parquet, hive-partitioned for filtering; same underlying CC0 data.
- **Caveats:** Massive storage/bandwidth; need `zstd` decompression; monthly files require aggregation pipeline; variant mis-tags in some 2020–2021 months (documented on site).
- **API (not bulk):** Lichess REST API + **Opening Explorer** at `explorer.lichess.org` (aggregated position stats; masters DB + lichess player games). Good for lookups, not for mining billions of positions.

**Verdict:** **Selected** as the project’s sole game database.

---

### Chess.com — Published Data API (not a single open dump)

- **URL:** https://www.chess.com/news/view/published-data-api (docs also mirrored in community gists)
- **License / terms:** Free **read-only** public API for data visible without login. **No API key.** Not a wholesale database grant — you fetch per player/month.
- **What you get:**
  - Player profile, stats, clubs, tournaments.
  - **Games:** list of monthly archive URLs → JSON game list or **multi-game PGN** per month per username.
  - Headers often include ratings, time class, accuracy (in JSON), ECO, etc. (varies by game type).
- **Bulk access:** Community projects (e.g. **Chessmont**, scrapers) aggregate high-Elo games by crawling many players — subject to **rate limits (429)**, User-Agent etiquette, and Chess.com ToS. No official “download entire site” dump.
- **Caveats:** Cannot redistribute Chess.com’s full corpus as your own “open DB” without legal review; fine for building a private pipeline if compliant with their policies.

**Verdict:** Useful add-on for Chess.com-flavored realism; worse than Lichess for one-shot bulk open redistribution.

---

## Tier 2 — Free archives and aggregators (smaller or curated)

### TWIC — The Week in Chess

- **URL:** https://theweekinchess.com/twic
- **Cost:** Free **weekly** PGN/ChessBase download per issue (~3k–6k games/week).
- **Mega archive:** Donation (~£30) for maintainer’s combined CBV (~**4M+ games**).
- **Content:** OTB tournaments, strong players, international events.
- **License:** Not CC0; free weekly files are a long-standing community resource. Redistribution of the combined commercial bundle follows donation terms.
- **Verdict:** Excellent **quality** per game; poor **scale** vs Lichess unless you only need master-level OTB.

---

### PGN Mentor

- **URL:** https://www.pgnmentor.com/files.html
- **Cost:** PGN files **free**; PGN Mentor **software** is $25.
- **Content:** Large collections by player, opening, event (site claims “over a million Grandmaster games”).
- **License:** Files described as “completely free” download; **no CC0 / SPDX statement** — treat as “free to download,” verify before commercial redistribution.
- **Verdict:** Good curated OTB/historical supplement.

---

### FICS Games Database

- **URL:** https://www.ficsgames.org/ (mirror: https://games.freechess.org/)
- **Scale:** ~**267M** games stored (Free Internet Chess Server, since 1999).
- **Cost:** Free; bandwidth **quotas** on some bulk downloads.
- **Format:** PGN zip; optional move times; Glicko RD in headers (2015+).
- **Filters:** Year, variant, rating floor, titled players, etc.
- **Verdict:** Huge online corpus; older platform, wider rating spread, good for “internet chess” realism.

---

### Lumbra’s Gigabase

- **URL:** https://lumbrasgigabase.com/en/
- **Scale:** ~**10.3M OTB** + ~**7.6M online** (Scid/si4/si5 or PGN chunks).
- **Cost:** Free.
- **Content:** Merged sources (TWIC, ChessBase exports, online sites, etc.) with `SOURCE` tags; monthly updates; quality filters (e.g. drops very low Elo / very short games).
- **License:** Aggregator — **provenance per SOURCE tag**; not a single open license.
- **Verdict:** Practical single download for mixed OTB+online; due diligence on sources if you ship commercially.

---

### Chessmont Open Database

- **URL:** https://database.chessmont.com/en/ | GitHub/Kaggle linked from site
- **Scale (advertised):**
  - **21.5M** deduplicated games (Lichess 2500+, Chess.com top players 2500+, TWIC, PGN Mentor).
  - **1.8B** indexed positions; **1.35B** unique FENs with counts.
- **Cost:** Free download (`.zst`).
- **License:** Repackaged third-party data — **not a new license**; downstream use depends on Lichess (CC0), Chess.com API policy, TWIC, PGN Mentor.
- **Verdict:** Saves preprocessing if filters match your needs (2400+, 3min+); confirm compliance before product launch.

---

### ICCF / correspondence

- **Official:** https://www.iccf.com/ (correspondence chess)
- **Mirrors:** e.g. https://chessnerd.net/pgn-downloads.html — `iccf-*.pgn` ~**1.2M** games (cleaned).
- **Verdict:** High-quality human play, very slow time controls — niche for “realistic blitz/rapid” puzzles.

---

### Legacy / bundled free corpora

| Name | Scale | Notes |
|------|-------|--------|
| **15 Million Games** (SourceForge / Codekiddy) | ~16M total in splits (OTB, online, engines, puzzles) | Dated ~2015; Beta; verify freshness |
| **Chess Nerd** curated PGNs | Various slices (e.g. Chess.com 2500+ checkmate subset) | Maintainer-built; check page for updates |
| **Canbase II** | ~200k historical Canadian OTB | Niche historical |

---

## Tier 3 — APIs and position-level services (not full game dumps)

| Service | What it provides | Bulk? |
|---------|------------------|-------|
| **Lichess Opening Explorer** (`explorer.lichess.org`) | Move statistics for masters / all Lichess / per-player | Query per position |
| **Lichess API** | Games for authenticated user, studies, puzzles API | Per-user / rate-limited |
| **Chess.com PubAPI** | Public player/game JSON + PGN | Per-player/month |
| **Syzygy / Lichess tablebases** | Endgame tablebase probes | Position lookup |

These support **enrichment** (opening stats, tablebase) after you extract candidate positions from PGN.

---

## Tier 4 — Commercial / restricted (not open, but important context)

### ChessBase product line

- **Mega Database 2026:** ~**11.7M** games (1475–2025), ~114k annotated — ~**€230**.
- **Big Database**, **CORR Database**, upgrades, weekly Mega Update (~5k games/week).
- **License:** Proprietary; licensed to purchaser; **redistribution in an app generally prohibited** unless you negotiate with ChessBase.
- **Verdict:** Gold standard for annotated OTB study; **not** an open-source puzzle pipeline foundation.

---

### Chessgames.com

- **Access:** Bulk PGN zip — **Premium** (~**$39/year**).
- **License:** Subscription terms; not an open database.
- **Verdict:** Personal research / comparison; not for a CC0-style product without explicit rights.

---

### Other commercial / closed

| Product | Notes |
|---------|--------|
| **Chess.com internal DB** | No public full dump; API only |
| **365Chess**, **Chessify**, cloud engines | Subscription analysis / DB access |
| **AIM Chess / coaching platforms** | Closed training corpora |
| **Book publishers (Everyman, etc.)** | Annotated PGN sold per title |

---

## Specialized corpora (usually *not* human-realistic puzzles)

| Source | Games | Use case |
|--------|-------|----------|
| **CCRL** (https://computerchess.org/games.html) | ~2M engine vs engine | Engine testing |
| **KCEC** | ~136k engine tournament | Engine testing |
| **TCEC** | Broadcasts / selective PGN | Engine championship |

---

## Lichess vs “made-up” puzzle databases

| Aspect | Lichess puzzle CSV | Your project concept |
|--------|-------------------|----------------------|
| Origin | Curated puzzle generator from real games | Positions filtered from **all** game moves by eval gap |
| Rating | Puzzle difficulty rating | Gap between **player Elo** vs **Elo+300** model |
| License | CC0 | Can use same Lichess **games** + own scoring |

Lichess puzzles are a useful **baseline**, but your definition (“interesting = win-rate gap across strength levels”) requires either the **eval JSONL**, **[%eval]** in PGN, or running your own engine / ML model on extracted FENs.

---

## Practical notes for this project (Lichess-only)

1. **Ingest** Lichess standard rated PGN (CC0) from `/standard/` — monthly `.pgn.zst` files.
2. **Subset early** by `WhiteElo`/`BlackElo`, `TimeControl`, and plies (e.g. middlegame only) before eval work — full 7B+ games is impractical to process naïvely.
3. **Evaluations:** Combine (a) Lichess eval JSONL where FEN matches, (b) on-demand Stockfish for candidate positions, (c) future Elo-conditioned win-probability model for “Elo vs Elo+300 gap.”
4. **Legal:** CC0 places data in the public domain; no permission required for commercial redistribution. Optional UI credit to Lichess is a product choice, not a license requirement.
5. **Other databases in this survey** are retained for reference only — not used unless the decision is explicitly reopened.

---

## Sources consulted

- https://database.lichess.org/
- https://huggingface.co/datasets/Lichess/standard-chess-games
- https://www.chess.com/news/view/published-data-api
- https://theweekinchess.com/twic
- https://www.pgnmentor.com/files.html
- https://www.ficsgames.org/
- https://lumbrasgigabase.com/en/
- https://database.chessmont.com/en/
- https://shop.chessbase.com/en/products/mega_database_2026
- https://www.chessgames.com/perl/zips
- https://computerchess.org/games.html
