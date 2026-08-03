"""Shared dense-vector corpus/query generator for the L3d lane.

Unit-normalized float32 vectors, 1024-dim (mirrors upstream issue #3144's
MSMARCO-shaped 1M x 1024 cell: ~4 GB raw at small scale). Deterministic per
(seed, scale) via numpy PCG64 so adapters and the GT builder regenerate
identical data in any container. Cosine similarity on unit vectors == dot.
"""
import numpy as np

DIMENSIONS = 1024
K = 10
# HNSW operating point, matched across engines (protocol override 3)
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 200
EF_SEARCH_SWEEP = [16, 32, 64, 128, 256]

SCALE_VECTORS = {"micro": 5_000, "tiny": 100_000, "small": 1_000_000,
                 "medium": 2_000_000}
SCALE_QUERIES = {"micro": 50, "tiny": 200, "small": 200, "medium": 100}

DOC_SEED = 20260709
QUERY_SEED = 515151
GEN_CHUNK = 50_000


def gen_vector_chunks(n, seed=DOC_SEED):
    """Yield (start_ordinal, float32 array [chunk, DIMENSIONS]) unit rows."""
    rng = np.random.Generator(np.random.PCG64(seed))
    done = 0
    while done < n:
        m = min(GEN_CHUNK, n - done)
        v = rng.standard_normal((m, DIMENSIONS), dtype=np.float32)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        yield done, v
        done += m


def gen_queries(n_queries, seed=QUERY_SEED):
    rng = np.random.Generator(np.random.PCG64(seed))
    q = rng.standard_normal((n_queries, DIMENSIONS), dtype=np.float32)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return q
