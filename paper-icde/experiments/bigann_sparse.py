"""Real learned-sparse corpus for the L3 sparse lane: Big-ANN 2023 Sparse track
(SPLADE-cocondenser encoding of MS MARCO passages v1), with the challenge's exact
top-k MIPS ground truth.

Drop-in replacement for sparse_common: same DIMENSIONS/K/SCALE_DOCS/SCALE_QUERIES/
gen_docs/gen_queries surface, but streams vectors from the shipped CSR files
instead of generating a synthetic corpus. Selected in l3_sparse via
BENCH_SPARSE_SOURCE=bigann.

Data files (BENCH_SPARSE_DATA, default /data/bigann), fetched from
gs://ann-challenge-sparse-vectors/csr/:
  base_small.csr (100k) / base_1M.csr (1M) / base_full.csr (8.84M)
  queries.dev.csr (6980 queries, shared across tiers)
  base_{small,1M,full}.dev.gt (exact top-10 ids+dists per tier)

CSR binary layout: int64 nrow, ncol, nnz; int64 indptr[nrow+1];
int32 indices[nnz]; float32 data[nnz].
"""
import os
import struct

import numpy as np

DATA = os.environ.get("BENCH_SPARSE_DATA", "/data/bigann")
DIMENSIONS = 30_109  # ncol of the SPLADE vocabulary in this encoding
K = 10

# Map our scale names to the Big-ANN base tiers.
SCALE_FILE = {"tiny": "base_small.csr", "small": "base_1M.csr",
              "medium": "base_full.csr"}
SCALE_GT = {"tiny": "base_small.dev.gt", "small": "base_1M.dev.gt",
            "medium": "base_full.dev.gt"}
SCALE_DOCS = {"tiny": 100_000, "small": 1_000_000, "medium": 8_841_823}
# All tiers share the same 6980 dev queries; cap at 1000 for stable percentiles
# at bounded cost (recall@10 is an average and converges well below 1000; a
# headline serial pass can bump this back to the full 6980 if desired).
SCALE_QUERIES = {"tiny": 1_000, "small": 1_000, "medium": 1_000}

_N_TO_SCALE = {n: s for s, n in SCALE_DOCS.items()}


def _csr_header(fh):
    nrow, ncol, nnz = struct.unpack("<qqq", fh.read(24))
    return nrow, ncol, nnz


def _scale_for_n(n):
    if n in _N_TO_SCALE:
        return _N_TO_SCALE[n]
    # nearest tier at/above n (smoke runs may pass a smaller cap)
    for s in ("tiny", "small", "medium"):
        if n <= SCALE_DOCS[s]:
            return s
    return "medium"


def _stream_csr(path, limit):
    """Yield (ordinal, indices_list, values_list) for the first `limit` rows."""
    with open(path, "rb") as fh:
        nrow, ncol, nnz = _csr_header(fh)
        n = min(limit, nrow) if limit else nrow
        indptr = np.frombuffer(fh.read(8 * (nrow + 1)), dtype="<i8")
        # indices + data are read in row-chunks to bound memory at 8.8M scale
        idx_base = 24 + 8 * (nrow + 1)
        dat_base = idx_base + 4 * nnz
        CH = 200_000
        r = 0
        while r < n:
            r1 = min(r + CH, n)
            lo, hi = int(indptr[r]), int(indptr[r1])
            fh.seek(idx_base + 4 * lo)
            idxs = np.frombuffer(fh.read(4 * (hi - lo)), dtype="<i4")
            fh.seek(dat_base + 4 * lo)
            vals = np.frombuffer(fh.read(4 * (hi - lo)), dtype="<f4")
            for rr in range(r, r1):
                a, b = int(indptr[rr]) - lo, int(indptr[rr + 1]) - lo
                yield rr, idxs[a:b].tolist(), vals[a:b].tolist()
            r = r1


def gen_docs(n, seed=None):
    scale = _scale_for_n(n)
    path = os.path.join(DATA, SCALE_FILE[scale])
    yield from _stream_csr(path, n)


def gen_queries(n_queries, seed=None):
    path = os.path.join(DATA, "queries.dev.csr")
    return [(idx, vals) for _, idx, vals in _stream_csr(path, n_queries)]


def load_gt(scale):
    """Exact top-K neighbour ids, shape (n_queries, K)."""
    with open(os.path.join(DATA, SCALE_GT[scale]), "rb") as fh:
        nq, k = struct.unpack("<II", fh.read(8))
        ids = np.frombuffer(fh.read(4 * nq * k), dtype="<i4").reshape(nq, k)
    return ids.astype(np.int64)
