-- Processed position statistics (built by build_position_db.py)

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    position_key TEXT PRIMARY KEY,
    fen          TEXT NOT NULL
);

-- Aggregated per position × 100-point Elo bin (player to move).
CREATE TABLE IF NOT EXISTS bin_stats (
    position_key TEXT NOT NULL,
    elo_bin      INTEGER NOT NULL,
    games        INTEGER NOT NULL DEFAULT 0,
    wins         INTEGER NOT NULL DEFAULT 0,
    losses       INTEGER NOT NULL DEFAULT 0,
    draws        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (position_key, elo_bin),
    FOREIGN KEY (position_key) REFERENCES positions(position_key)
);

-- Move popularity per position × Elo bin (UCI notation).
CREATE TABLE IF NOT EXISTS move_stats (
    position_key TEXT NOT NULL,
    elo_bin      INTEGER NOT NULL,
    move_uci     TEXT NOT NULL,
    games        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (position_key, elo_bin, move_uci),
    FOREIGN KEY (position_key) REFERENCES positions(position_key)
);

-- Indexes support queries while the DB is still being built (WAL mode).
CREATE INDEX IF NOT EXISTS idx_bin_stats_elo ON bin_stats(elo_bin);
CREATE INDEX IF NOT EXISTS idx_move_stats_elo ON move_stats(elo_bin);
CREATE INDEX IF NOT EXISTS idx_bin_stats_position ON bin_stats(position_key);
