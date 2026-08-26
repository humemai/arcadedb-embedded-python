#!/usr/bin/env python3
"""Hot-path driver for CPU profiling: build the index, then run the query
loop for a fixed wall-clock window so async-profiler can be attached from
the host during a steady state.

MODE=sparse: Big-ANN 1M, arcadedb_sparse_embedded (settled), dev queries.
MODE=dense:  DEEP-10M fp32 M=32, arcadedb_dense_embedded, test queries.

Prints QUERY-PHASE-START when the loop begins; loops for PROFILE_SECS.
"""
import os
import time

MODE = os.environ.get("MODE", "sparse")
SECS = int(os.environ.get("PROFILE_SECS", "240"))


def main():
    if MODE == "sparse":
        os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")
        import bigann_sparse as src
        from l3_sparse import BACKENDS
        b = BACKENDS["arcadedb_sparse_embedded"]()
        # The tier is a knob because the whole point of issue #5467 is a per-query
        # cost that a small corpus cannot amortise, and it is invisible at 1M by
        # construction: the scope asked for "a profile at that tier (the existing
        # profile is 1M, where these constants are invisible)" and every profile
        # posted to that thread so far has been the 1M one.
        scale = os.environ.get("PROFILE_SCALE", "small")
        if scale not in src.SCALE_DOCS:
            raise SystemExit(f"PROFILE_SCALE={scale!r}; known: {sorted(src.SCALE_DOCS)}")
        n = src.SCALE_DOCS[scale]
        queries = src.gen_queries(src.SCALE_QUERIES[scale])
        print(f"PROFILE_SCALE={scale} n_docs={n:,} queries={len(queries):,}", flush=True)
        b.connect()
        b.build(n)
        if hasattr(b, "post_build"):
            b.post_build()
        run = lambda i: b.search(*queries[i % len(queries)], 10)
    else:
        import numpy as np
        from l3d_dense import BACKENDS, load_dataset
        train, test, _gt = load_dataset("deep10m")
        b = BACKENDS["arcadedb_dense_embedded"]()
        b.connect()
        b.build(train)
        b.post_build()
        run = lambda i: b.search(test[i % len(test)], 10)

    for i in range(20):
        run(i)
    print("QUERY-PHASE-START", flush=True)
    t0 = time.perf_counter()
    i = 0
    while time.perf_counter() - t0 < SECS:
        run(i)
        i += 1
    print(f"QUERY-PHASE-END n={i}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
