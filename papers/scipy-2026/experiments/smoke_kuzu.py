#!/usr/bin/env python3
"""Smoke test: Kùzu (graph comparator; embedded, Cypher, in-process)."""
import platform
import tempfile
import time

import kuzu

print(f"kuzu {kuzu.__version__} | Python {platform.python_version()} | {platform.machine()}")

path = tempfile.mkdtemp(prefix="smoke_kuzu_") + "/db"
db = kuzu.Database(path)
conn = kuzu.Connection(db)

conn.execute("CREATE NODE TABLE Person(id INT64, name STRING, PRIMARY KEY(id))")
conn.execute("CREATE REL TABLE Knows(FROM Person TO Person)")

n = 200
t0 = time.time()
for i in range(n):
    conn.execute("CREATE (p:Person {id: $id, name: $name})", {"id": i, "name": f"p-{i}"})
print(f"insert {n} nodes in {time.time() - t0:.3f}s")

t0 = time.time()
for i in range(n - 1):
    conn.execute(
        "MATCH (a:Person), (b:Person) WHERE a.id = $x AND b.id = $y CREATE (a)-[:Knows]->(b)",
        {"x": i, "y": i + 1},
    )
print(f"insert {n - 1} edges in {time.time() - t0:.3f}s")


def scalar(q):
    res = conn.execute(q)
    return res.get_next()[0]


print("nodes =", scalar("MATCH (p:Person) RETURN count(*)"))
print("edges =", scalar("MATCH (:Person)-[:Knows]->(:Person) RETURN count(*)"))
print("2-hop =", scalar("MATCH (a:Person)-[:Knows]->()-[:Knows]->(c:Person) RETURN count(*)"))
print("SMOKE OK")
