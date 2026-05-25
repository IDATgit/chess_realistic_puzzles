# Data directory

Raw Lichess standard rated game dumps for local processing.

## Current file

| Field | Value |
|-------|--------|
| **File** | `lichess_db_standard_rated_2026-04.pgn.zst` |
| **Source** | https://database.lichess.org/standard/ |
| **Month** | April 2026 (latest complete month at download) |
| **Format** | PGN compressed with Zstandard (`.zst`) |
| **License** | CC0 |

Decompress or stream-parse with `zstd` / `zstdcat` (do not commit this file to git).

```bash
# Example: stream without full decompress
zstdcat lichess_db_standard_rated_2026-04.pgn.zst | head
```
