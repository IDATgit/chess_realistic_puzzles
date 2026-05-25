# Pipeline

Build the processed position database from raw Lichess PGN.

## Setup

```bash
pip install -r requirements.txt
```

## Build (test run — 1 000 games)

```bash
python -m pipeline.build_position_db --max-games 1000
```

## Build (full month)

```bash
python -m pipeline.build_position_db
```

Output: `data/processed/position_stats.db`

## Query example

```sql
-- Stats for a position at ~1000 Elo (bin 1000) vs ~1300 Elo (bin 1300)
SELECT elo_bin, games, wins, losses, draws
FROM bin_stats
WHERE position_key = ?
  AND elo_bin IN (1000, 1300);

SELECT move_uci, games
FROM move_stats
WHERE position_key = ? AND elo_bin = 1000
ORDER BY games DESC;
```
