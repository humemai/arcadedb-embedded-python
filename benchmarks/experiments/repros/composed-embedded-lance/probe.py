#!/usr/bin/env python3
"""The three measurements behind the composed embedded stack's declarations (COMPARATORS.md, "The composed embedded stack").

Laptop probes, untimed for the page and not a page number: each is a ratio within one engine on one machine.

  1. recall of the vector half at the lane's matched ef (100) and at ef 200, and the nprobes sweep (the table has one IVF partition
     at 50k, so nprobes is idle);
  2. the candidate filter with the BTREE on pid and with it dropped (the F14 declaration's ratio);
  3. why LanceDB is read-only in the operation: 300 updates of 13 rows on a table with a views column, its fragments, the update
     latency first and last, and the vector search before and after.

Run (pin the cores; the laptop's timed queue owns 6 and 7):
  taskset -c 8-15 uv run --no-project --with numpy==2.5.3 --with pandas==3.0.6 --with pyarrow==25.0.1 --with requests \\
      --with lancedb==0.39.0 --with ladybug==0.21.2 python repros/composed-embedded-lance/probe.py 50000
"""
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
os.environ["E2_PRODUCTS"] = str(N)
import e2_hybrid as E  # noqa: E402
import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402

vecs, edges, queries = E.gen_data()
b = E.ComposedEmbeddedE2()
t = time.time()
b.build(vecs, edges)
print(f"build {time.time() - t:.1f} s, index_s {b.index_s}")
qs = queries[:100]


def recall(nprobes, ef):
    b.LANCE_NPROBES, b.LANCE_EF = nprobes, ef
    rec, lat = [], []
    for q in qs:
        t0 = time.perf_counter()
        got = b._vec_topk(q, 10)
        lat.append((time.perf_counter() - t0) * 1000)
        rec.append(E.recall_at_k(got, E.brute_topk(vecs, q, 10)))
    return round(sum(rec) / len(rec), 4), round(statistics.median(lat), 2)


for npb in (10, 20, 50, 100):
    print(f"recall, p50 ms at nprobes {npb}, ef 100: {recall(npb, 100)}")
print(f"recall, p50 ms at nprobes 10, ef 200: {recall(10, 200)}")
b.LANCE_NPROBES, b.LANCE_EF = 10, 100

adj = E.build_adjacency(edges, E.PRODUCTS)
rs = random.Random(1)
starts = [rs.randrange(E.PRODUCTS) for _ in range(100)]


def filtered():
    rec, lat = [], []
    for q, s in zip(qs, starts):
        c = E.neighbourhood(adj, s, 3)
        t0 = time.perf_counter()
        got = b._rank_candidates(q, c, 10)
        lat.append((time.perf_counter() - t0) * 1000)
        rec.append(E.recall_at_k(got, E.brute_topk(vecs, q, 10, c)))
    return round(sum(rec) / len(rec), 4), round(statistics.median(lat), 2)


print("filtered search, recall and p50 ms, with the BTREE on pid:", filtered())
idx = [i.name for i in b.tbl.list_indices() if list(i.columns) == ["pid"]][0]
b.tbl.drop_index(idx)
print("filtered search, recall and p50 ms, WITHOUT it:", filtered())

flat = pa.array(vecs.astype("float32").reshape(-1), type=pa.float32())
b.tbl = b.lance.create_table("product_v", pa.table({
    "pid": pa.array(range(E.PRODUCTS), type=pa.int64()), "views": pa.array([0] * E.PRODUCTS, type=pa.int64()),
    "vector": pa.FixedSizeListArray.from_arrays(flat, E.DIM)}))
b.tbl.create_scalar_index("pid", index_type="BTREE")
b.tbl.create_index(metric="l2", index_type="IVF_HNSW_FLAT", m=16, ef_construction=100)
print("vector search p50 ms and recall BEFORE the updates:", recall(10, 100))
rg = np.random.default_rng(3)
ul = []
for _ in range(300):
    ids = ",".join(str(int(x)) for x in rg.integers(0, E.PRODUCTS, 13))
    t0 = time.perf_counter()
    b.tbl.update(where=f"pid IN ({ids})", values_sql={"views": "views + 1"})
    ul.append((time.perf_counter() - t0) * 1000)
print(f"lance update ms: p50 {statistics.median(ul):.2f}, first 10 mean {statistics.mean(ul[:10]):.2f}, "
      f"last 10 mean {statistics.mean(ul[-10:]):.2f}")
print("fragments:", (b.tbl.stats().get("fragment_stats") or {}).get("num_fragments"))
print("vector search p50 ms and recall AFTER 300 updates:", recall(10, 100))
b.close()
