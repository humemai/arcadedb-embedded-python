#!/usr/bin/env python3
"""Smoke test: does arcadedb-embedded run in-process inside a container?

Exercises the three pillars on a tiny scale:
  1. OLTP  — create a document type, transactional inserts, SQL query/count
  2. SQL   — aggregation query
  3. Vector — LSM_VECTOR (HNSW) index build + vectorNeighbors search

Writes the DB under /tmp (not the mounted workdir). Prints timings + a version line.
This is NOT a benchmark — just a "does the JVM-in-Python path work" check.
"""

import platform
import tempfile
import time

import numpy as np

import arcadedb_embedded as arcadedb


def section(title):
    print(f"\n--- {title} ---")


t_import = time.time()
db_path = tempfile.mkdtemp(prefix="smoke_arcadedb_") + "/db"
print(f"arcadedb_embedded {getattr(arcadedb, '__version__', '?')} | "
      f"Python {platform.python_version()} | {platform.machine()}")

t0 = time.time()
with arcadedb.create_database(db_path) as db:
    print(f"create_database + JVM start: {time.time() - t0:.3f}s (cold)")

    # 1. OLTP -----------------------------------------------------------------
    section("OLTP: schema + transactional inserts")
    db.command("sql", "CREATE DOCUMENT TYPE Task")
    db.command("sql", "CREATE PROPERTY Task.title STRING")
    db.command("sql", "CREATE PROPERTY Task.score INTEGER")

    n = 500
    t0 = time.time()
    with db.transaction():
        for i in range(n):
            db.command("sql", "INSERT INTO Task SET title = :t, score = :s",
                       {"t": f"task-{i}", "s": i % 100})
    dt = time.time() - t0
    print(f"inserted {n} docs in {dt:.3f}s ({n / dt:,.0f} ins/s)")

    # 2. SQL ------------------------------------------------------------------
    section("SQL: query + aggregation")
    total = db.count_type("Task")
    top = db.query("sql", "SELECT title, score FROM Task ORDER BY score DESC LIMIT 3").to_list()
    agg = db.query("sql", "SELECT score, count(*) AS c FROM Task GROUP BY score LIMIT 3").to_list()
    print(f"count_type(Task) = {total}")
    print(f"top3 = {[(r['title'], r['score']) for r in top]}")
    print(f"agg sample = {agg}")

    # 3. Vector ---------------------------------------------------------------
    section("Vector: LSM_VECTOR index + vectorNeighbors search")
    dim, nvec = 16, 300
    rng = np.random.default_rng(0)
    db.command("sql", "CREATE DOCUMENT TYPE Article")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")

    t0 = time.time()
    with db.transaction():
        for i in range(nvec):
            vec = rng.random(dim, dtype=np.float32)
            db.command("sql", "INSERT INTO Article SET embedding = :e",
                       {"e": arcadedb.to_java_float_array(vec)})
    print(f"inserted {nvec} vectors ({dim}-d) in {time.time() - t0:.3f}s")

    t0 = time.time()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                          METADATA {{ "dimensions": {dim}, "similarity": "COSINE" }}''')
    print(f"built HNSW index in {time.time() - t0:.3f}s")

    q = arcadedb.to_java_float_array(rng.random(dim, dtype=np.float32))
    t0 = time.time()
    hits = db.query(
        "sql",
        "SELECT distance FROM (SELECT expand(vectorNeighbors(?, ?, ?))) ORDER BY distance",
        "Article[embedding]", q, 5,
    ).to_list()
    print(f"vectorNeighbors(k=5) in {(time.time() - t0) * 1000:.1f}ms -> "
          f"{[round(h['distance'], 4) for h in hits]}")

print(f"\nSMOKE OK (total {time.time() - t_import:.3f}s)")
