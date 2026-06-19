#!/usr/bin/env python3
"""Smoke test: DuckDB (tabular OLAP comparator; in-process)."""
import platform
import tempfile
import time

import duckdb

print(f"duckdb {duckdb.__version__} | Python {platform.python_version()} | {platform.machine()}")

path = tempfile.mkdtemp(prefix="smoke_duckdb_") + "/db.duckdb"
con = duckdb.connect(path)
con.execute("CREATE TABLE task(id INTEGER, title VARCHAR, score INTEGER)")

n = 500
t0 = time.time()
con.executemany("INSERT INTO task VALUES (?, ?, ?)",
                [(i, f"task-{i}", i % 100) for i in range(n)])
print(f"insert {n} in {time.time() - t0:.3f}s")

print("count =", con.execute("SELECT count(*) FROM task").fetchone()[0])
print("agg   =", con.execute(
    "SELECT score, count(*) AS c FROM task GROUP BY score ORDER BY score LIMIT 3").fetchall())
print("SMOKE OK")
