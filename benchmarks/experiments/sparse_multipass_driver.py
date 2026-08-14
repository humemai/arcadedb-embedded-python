#!/usr/bin/env python3
"""Give the sparse lane the multi-pass protocol the dense lane already has.

l3_sparse.py times ONE pass, for every engine. That is fair, and it is also
blind to a state the dense lane turned out to have: dense_multipass_driver.py
gave the dense comparators our multi-pass protocol and found that only ArcadeDB
moves between the first pass and the rest.

    engine       cold    warm    gain
    Qdrant       1.342   1.312   1.02x
    Chroma       0.700   0.708   0.99x
    LanceDB      3.199   3.154   1.01x
    ArcadeDB     8.869   0.956   9.27x

ArcadeDB pages its index off disk and the comparators are resident from build,
so the first pass costs us 9x and costs them nothing. Whether the same is true
of LSM_SPARSE_VECTOR is unknown: nobody has ever run the sparse lane twice.
Until this runs, the sparse bars on the summary figure are first-pass numbers
that may understate steady state by an unmeasured amount.

WARM QUERIES ARE DISJOINT FROM COLD ONES, and that is the one place this
deliberately does NOT copy the dense driver. The dense driver replays the same
query set on every pass, so its warm number cannot separate two explanations:

    the index is now resident        real, and what a running service gets
    these exact queries were seen    memoisation, which a service does not get

The evidence favours residency, because int8 gains 3.5x and fp32 9.3x while
int8 is four times smaller, so the gain tracks DATA SIZE rather than query
repetition. But that is an inference from a ratio, and a reviewer is entitled
to reject it. Splitting the query set removes the argument: the warm pass here
asks questions the engine has never been asked, against an index it has already
paged in, which is exactly the production condition.

The cost is that cold and warm are measured on different queries, so they are
not paired per-query. That is fine for a median over hundreds of queries and it
is the lesser of the two evils.

    BENCH_SPARSE_SOURCE=bigann BENCH_MP_BACKEND=qdrant_sparse \
        BENCH_MP_SCALE=small PROBE_OUT=/pout/sp_qdrant.json \
        python -u sparse_multipass_driver.py

Mirrors dense_multipass_driver.py's shape so the two differ in the lane and
nothing else.
"""
import json
import os
import statistics
import time

from l3_sparse import (BACKENDS, K, WARMUP, DIMENSIONS, SCALE_DOCS,
                       SCALE_QUERIES, gen_queries, pct, recall_at_k, _src)
from bench_common import run_conditions

# Read with .get so the module can be imported without the run environment;
# the dense driver's contract check broke on a module-level os.environ[...].
BACKEND = os.environ.get("BENCH_MP_BACKEND")
SCALE = os.environ.get("BENCH_MP_SCALE", "small")
PASSES = int(os.environ.get("BENCH_MP_PASSES", "5"))


def _timed_pass(b, queries, gt, offset):
    """One timed sweep. Returns (percentiles, recall).

    Recall resolution stays OUT of the timed section, exactly as l3_sparse
    does it: resolve() is a backend-native id lookup that cost ~4.7s per call
    at 8.84M, and timing it would measure our resolver rather than the engine.
    """
    lats, raw = [], []
    for idx, vals in queries:
        t0 = time.perf_counter()
        ids = b.search(idx, vals, K)
        lats.append(time.perf_counter() - t0)
        raw.append(ids)
    recall = None
    if gt is not None:
        rs = [recall_at_k(b.resolve(ids), gt[offset + qi])
              for qi, ids in enumerate(raw)]
        recall = round(statistics.mean(rs), 4)
    return pct(lats), recall


def main():
    if not BACKEND:
        raise SystemExit("BENCH_MP_BACKEND is required (e.g. qdrant_sparse)")

    n_docs = SCALE_DOCS[SCALE]
    queries = gen_queries(SCALE_QUERIES[SCALE])
    gt = _src.load_gt(SCALE) if os.environ.get(
        "BENCH_SPARSE_SOURCE") == "bigann" else None

    # THE SPLIT. First half answers the cold pass, second half every warm pass.
    # Both halves are drawn from the same dev query set in the same order, so
    # the two are the same KIND of query and differ only in never having been
    # asked. gt is indexed by absolute position, hence the offset.
    half = len(queries) // 2
    cold_q, warm_q = queries[:half], queries[half:]
    if len(warm_q) < 50:
        raise SystemExit(
            f"only {len(warm_q)} warm queries at scale {SCALE!r}; a median "
            "over that few is not worth publishing. Raise SCALE_QUERIES or "
            "run a bigger tier.")

    b = BACKENDS[BACKEND]()
    b.connect()

    t0 = time.perf_counter()
    b.build(n_docs)
    b.post_build()          # the vendor settle step, same as the lane
    build_s = round(time.perf_counter() - t0, 2)
    print(f"BUILD-DONE {build_s}s", flush=True)

    # The lane's own 5 untimed warmups, so pass 0 here and the lane's single
    # pass are the same measurement. Taken from the WARM half, so the cold
    # queries stay genuinely unasked.
    for idx, vals in warm_q[:WARMUP]:
        b.search(idx, vals, K)

    out_reps = []
    for rep in range(0, PASSES + 1):
        cold = rep == 0
        qs, off = (cold_q, 0) if cold else (warm_q, half)
        p, recall = _timed_pass(b, qs, gt, off)
        rec = {"rep": rep, "pass": "cold" if cold else "warm",
               "backend": BACKEND, "scale": SCALE, "lane": "l3s_mp",
               "build_s": build_s, "n_docs": n_docs, "dims": DIMENSIONS,
               "k": K, "n_queries": len(qs),
               "queries": "first half" if cold else "second half",
               "engine_version": getattr(b, "version", "?"),
               # Only Elasticsearch has it, and the 9.0-vs-9.4 recall gap was
               # diagnosable only because the lane recorded it.
               "es_prune": getattr(b, "prune", None),
               "recall_at_10": recall}
        rec.update({f"query_{k2}": v for k2, v in p.items()})
        rec.update(run_conditions(lane="l3s_mp"))
        out_reps.append(rec)
        print("RESULT " + json.dumps(rec), flush=True)

    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        with open(outp, "w") as f:
            json.dump(out_reps, f, indent=1)
    # Same reason as the dense driver: a backend can leave a JVM or a client
    # thread alive and the campaign has lost cells to a driver that finished
    # and never exited.
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(1)
