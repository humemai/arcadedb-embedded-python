#!/usr/bin/env python3
"""Smoke test: SQLite (tabular OLTP comparator; stdlib, in-process)."""
import platform
import sqlite3
import tempfile
import time

path = tempfile.mkdtemp(prefix="smoke_sqlite_") + "/db.sqlite"
print(f"sqlite3 {sqlite3.sqlite_version} | Python {platform.python_version()} | {platform.machine()}")

con = sqlite3.connect(path)
con.execute("CREATE TABLE task(id INTEGER PRIMARY KEY, title TEXT, score INTEGER)")

n = 500
t0 = time.time()
con.executemany("INSERT INTO task(id, title, score) VALUES (?, ?, ?)",
                [(i, f"task-{i}", i % 100) for i in range(n)])
con.commit()
print(f"insert {n} in {time.time() - t0:.3f}s")

print("count =", con.execute("SELECT count(*) FROM task").fetchone()[0])
print("agg   =", con.execute(
    "SELECT score, count(*) FROM task GROUP BY score ORDER BY score LIMIT 3").fetchall())
print("SMOKE OK")
