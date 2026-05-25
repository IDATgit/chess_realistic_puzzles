import sqlite3

c = sqlite3.connect("file:data/processed/position_stats.db?mode=ro", uri=True)
print("meta", dict(c.execute("select key,value from meta").fetchall()))
print("with fen", c.execute("select count(*) from positions where length(fen) > 10").fetchone()[0])
print("total pos", c.execute("select count(*) from positions").fetchone()[0])
print("bin_stats rows", c.execute("select count(*) from bin_stats").fetchone()[0])
