"""Shared SPLADE-shaped corpus/query generator for the L3 sparse lane.

Faithful port of the engine's LSMSparseVectorIndexLargeBenchmark distribution:
30k-dim vocabulary, 30 nnz per doc with half the nnz in a 1000-dim "head"
(skewed, SPLADE-like), weights 0.1 + U(0,1); queries use 10 nnz with the same
skew. Deterministic per (seed, scale) so adapters and the ground-truth builder
regenerate identical data without shipping corpus files.
"""
import random

DIMENSIONS = 30_000
HEAD_DIMS = 1_000
NNZ_PER_DOC = 30
Q_NNZ = 10
K = 10

SCALE_DOCS = {"micro": 5_000, "tiny": 100_000, "small": 1_000_000,
              "medium": 10_000_000, "large": 20_000_000}
# queries per scale: enough for stable percentiles, bounded GT cost at scale
SCALE_QUERIES = {"micro": 50, "tiny": 200, "small": 500, "medium": 100,
                 "large": 100}

DOC_SEED = 20260707
QUERY_SEED = 424242


def _sparse_vec(rng, nnz):
    picked, idx = set(), []
    while len(idx) < nnz:
        dim = rng.randrange(HEAD_DIMS) if len(idx) < nnz // 2 \
            else rng.randrange(DIMENSIONS)
        if dim not in picked:
            picked.add(dim)
            idx.append(dim)
    vals = [0.1 + rng.random() for _ in idx]
    return idx, vals


def gen_docs(n, seed=DOC_SEED):
    """Yield (ordinal, indices, values). Deterministic stream."""
    rng = random.Random(seed)
    for i in range(n):
        idx, vals = _sparse_vec(rng, NNZ_PER_DOC)
        yield i, idx, vals


def gen_queries(n_queries, seed=QUERY_SEED):
    rng = random.Random(seed)
    return [_sparse_vec(rng, Q_NNZ) for _ in range(n_queries)]
