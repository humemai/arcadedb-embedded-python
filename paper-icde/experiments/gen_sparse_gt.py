#!/usr/bin/env python3
"""Ground truth for the L3 sparse lane: exact top-K by dot product.

Run ONCE per scale on the host (untimed, not a backend):
    uv run --with scipy python gen_sparse_gt.py --scale tiny
Writes data/sparse/<scale>/gt.npy (n_queries x K doc ordinals, score-desc).
Chunked over the corpus so 10M x 30k stays in memory budget.
"""
import argparse
import os

import numpy as np
from scipy import sparse

from sparse_common import (DIMENSIONS, K, SCALE_DOCS, SCALE_QUERIES,
                           gen_docs, gen_queries)

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK = 500_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", required=True, choices=list(SCALE_DOCS))
    args = ap.parse_args()

    n_docs = SCALE_DOCS[args.scale]
    queries = gen_queries(SCALE_QUERIES[args.scale])
    out_dir = os.path.join(HERE, "data", "sparse", args.scale)
    os.makedirs(out_dir, exist_ok=True)

    # queries as a dense (n_q x dims) matrix — tiny (n_q <= 500)
    qm = np.zeros((len(queries), DIMENSIONS), dtype=np.float32)
    for qi, (idx, vals) in enumerate(queries):
        qm[qi, idx] = vals

    best_scores = np.full((len(queries), K), -1.0, dtype=np.float32)
    best_ids = np.full((len(queries), K), -1, dtype=np.int64)

    rows, cols, vals_l, base = [], [], [], 0
    done = 0

    def flush_chunk(base_ordinal, n_rows):
        nonlocal best_scores, best_ids
        m = sparse.csr_matrix(
            (vals_l, (rows, cols)), shape=(n_rows, DIMENSIONS), dtype=np.float32)
        scores = np.asarray(m.dot(qm.T)).T  # (n_q, n_rows)
        for qi in range(len(queries)):
            merged_s = np.concatenate([best_scores[qi], scores[qi]])
            merged_i = np.concatenate([
                best_ids[qi],
                np.arange(base_ordinal, base_ordinal + n_rows, dtype=np.int64)])
            top = np.argsort(-merged_s, kind="stable")[:K]
            best_scores[qi], best_ids[qi] = merged_s[top], merged_i[top]

    for ordinal, idx, v in gen_docs(n_docs):
        r = ordinal - base
        rows.extend([r] * len(idx))
        cols.extend(idx)
        vals_l.extend(v)
        done += 1
        if done % CHUNK == 0:
            flush_chunk(base, CHUNK)
            rows, cols, vals_l = [], [], []
            base = ordinal + 1
            print(f"  gt: {done:,}/{n_docs:,} docs")
    if rows:
        flush_chunk(base, n_docs - base)

    np.save(os.path.join(out_dir, "gt.npy"), best_ids)
    print(f"wrote {out_dir}/gt.npy  shape={best_ids.shape}")


if __name__ == "__main__":
    main()
