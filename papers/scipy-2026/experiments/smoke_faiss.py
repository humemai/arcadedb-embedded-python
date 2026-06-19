#!/usr/bin/env python3
"""Smoke test: Faiss exact (recall ground-truth baseline; NOT a competitor)."""
import platform
import time

import numpy as np
import faiss

print(f"faiss {faiss.__version__} | Python {platform.python_version()} | {platform.machine()}")

dim, n = 16, 300
rng = np.random.default_rng(0)
xb = rng.random((n, dim), dtype=np.float32)
xq = rng.random((1, dim), dtype=np.float32)

index = faiss.IndexFlatL2(dim)  # exact, brute force
index.add(xb)

t0 = time.time()
D, I = index.search(xq, 5)
print(f"exact search(k=5) in {(time.time() - t0) * 1000:.1f}ms -> "
      f"ids {I[0].tolist()} dists {[round(float(d), 4) for d in D[0]]}")
print("SMOKE OK")
