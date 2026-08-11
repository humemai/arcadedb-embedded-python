#!/usr/bin/env python3
"""Smoke test: Chroma (vector comparator; embedded, pure HNSW via hnswlib)."""
import platform
import tempfile
import time

import numpy as np
import chromadb

print(f"chromadb {chromadb.__version__} | Python {platform.python_version()} | {platform.machine()}")

path = tempfile.mkdtemp(prefix="smoke_chroma_")
client = chromadb.PersistentClient(path=path)
col = client.create_collection("articles", metadata={"hnsw:space": "cosine"})

dim, n = 16, 300
rng = np.random.default_rng(0)
embs = rng.random((n, dim), dtype=np.float32)

t0 = time.time()
col.add(ids=[str(i) for i in range(n)], embeddings=embs.tolist())
print(f"add {n} vectors ({dim}-d) in {time.time() - t0:.3f}s")

q = rng.random((1, dim), dtype=np.float32)
t0 = time.time()
res = col.query(query_embeddings=q.tolist(), n_results=5)
print(f"query(k=5) in {(time.time() - t0) * 1000:.1f}ms -> "
      f"dists {[round(d, 4) for d in res['distances'][0]]}")
print("SMOKE OK")
