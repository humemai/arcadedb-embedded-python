#!/usr/bin/env python3
"""Characterize the Big-ANN-1M sparse latency cliff (100k: 1.4ms -> 1M: 165ms
p50 on ArcadeDB while Qdrant stays low-ms).

Hypothesis: real SPLADE head terms have posting lists covering a large corpus
fraction and the scorer's block-max pruning stops discriminating, so per-query
cost tracks the summed posting length of the query's terms.

Method (black-box, embedded ArcadeDB): build the 1M tier once, then time each
dev query individually and record its term stats against corpus document
frequencies computed from the CSR: nnz, sum_df (total postings touched if no
pruning), max_df, max_df_fraction. Strong rank correlation between latency and
sum_df across queries = pruning is not cutting head terms.

Env: BENCH_SPARSE_SOURCE=bigann BENCH_SPARSE_DATA=/data/sparse
Out: per-query JSONL + a correlation/decile summary line (RESULT ...).
"""
import json
import os
import time

os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")

import numpy as np

import bigann_sparse as src
from l3_sparse import BACKENDS

SCALE = os.environ.get("PROBE_SCALE", "small")  # bigann 1M tier
N_DOCS = src.SCALE_DOCS[SCALE]
K = src.K


def corpus_df(n_docs):
    """Document frequency per dimension, streamed from the corpus CSR."""
    df = np.zeros(src.DIMENSIONS, dtype=np.int64)
    for i, (_rid, idx, _vals) in enumerate(src.gen_docs(n_docs)):
        df[np.asarray(idx, dtype=np.int64)] += 1
        if (i + 1) % 200_000 == 0:
            print(f"df pass {i+1}/{n_docs}", flush=True)
    return df


def main():
    out_path = os.environ.get("PROBE_OUT", "/pout/sparse_cliff.jsonl")
    be = BACKENDS[os.environ.get("PROBE_BACKEND", "arcadedb_sparse_embedded")]()
    print(f"probe backend={be.name} scale={SCALE} n_docs={N_DOCS}", flush=True)

    df = corpus_df(N_DOCS)
    queries = list(src.gen_queries(src.SCALE_QUERIES[SCALE]))

    be.connect()
    t0 = time.perf_counter()
    be.build(N_DOCS)
    print(f"build_s={time.perf_counter()-t0:.1f}", flush=True)

    for qi, (idx, vals) in enumerate(queries[:20]):  # warmup, untimed
        be.search(idx, vals, K)

    recs = []
    with open(out_path, "w") as f:
        for qi, (idx, vals) in enumerate(queries):
            t1 = time.perf_counter()
            be.search(idx, vals, K)
            ms = (time.perf_counter() - t1) * 1e3
            tdf = df[np.asarray(idx, dtype=np.int64)]
            rec = {"q": qi, "ms": round(ms, 3), "nnz": len(idx),
                   "sum_df": int(tdf.sum()), "max_df": int(tdf.max()),
                   "max_df_frac": round(float(tdf.max()) / N_DOCS, 4)}
            recs.append(rec)
            f.write(json.dumps(rec) + "\n")
            if (qi + 1) % 100 == 0:
                print(f"query {qi+1}/{len(queries)}", flush=True)

    ms = np.array([r["ms"] for r in recs])
    sdf = np.array([r["sum_df"] for r in recs], dtype=float)
    nnz = np.array([r["nnz"] for r in recs], dtype=float)
    # Spearman via rank transform (no scipy dependency in the bench image)
    rank = lambda a: np.argsort(np.argsort(a)).astype(float)
    rho = lambda a, b: float(np.corrcoef(rank(a), rank(b))[0, 1])
    dec = np.percentile(sdf, np.arange(0, 101, 10))
    dec_ms = [round(float(np.median(ms[(sdf >= dec[i]) & (sdf <= dec[i + 1])])), 2)
              for i in range(10)]
    summary = {"n_queries": len(recs), "p50_ms": round(float(np.median(ms)), 2),
               "spearman_ms_vs_sum_df": round(rho(ms, sdf), 3),
               "spearman_ms_vs_nnz": round(rho(ms, nnz), 3),
               "decile_median_ms_by_sum_df": dec_ms,
               "sum_df_p10": int(dec[1]), "sum_df_p90": int(dec[9])}
    print("RESULT " + json.dumps(summary), flush=True)
    be.close() if hasattr(be, "close") else None
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
