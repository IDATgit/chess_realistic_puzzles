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

## Build (full month, incremental — readable while building)

```bash
python -m pipeline.build_position_db --workers 1 --flush-every 5000
```

Output: `data/processed/position_stats.db` (WAL mode; commits every 5k games)

### Read while building

```sql
-- Progress
SELECT key, value FROM meta ORDER BY key;

-- Example: bin stats for a position hash at 1000 vs 1300 Elo
SELECT elo_bin, games, wins, losses, draws
FROM bin_stats
WHERE position_key = '8714366160a63779' AND elo_bin IN (1000, 1300);
```

Use a read-only SQLite connection (or any reader). WAL allows concurrent reads during writes.
