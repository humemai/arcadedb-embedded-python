#!/usr/bin/env python3
"""Does #5518's range split honour the guarantee it now claims, on a real
quantized corpus?

Background. The PR originally claimed the split returns an identical list to
the serial scan, ties included. That was wrong in one corner and upstream has
since said so (comment 2026-07-29T15:48): MaxScore sums a document's terms in
an order that follows the essential/non-essential split, a range reaches that
watermark at a different point than the whole scan, so two documents that tie
exactly in one shape can sit an ulp apart in the other. The RID tie-break
cannot reach that case, because it only orders scores that are still equal
after rounding.

The guarantee upstream now states, and the one this probe tests:

  1. same number of documents,
  2. rank for rank indistinguishable in score,
  3. nothing ranking below the serial k-th.

In short: never a WORSE answer, possibly a DIFFERENT one among documents that
nothing can tell apart. Their new unit test pins this on a hand-built plateau
of inexact weights. This checks it holds on 1000 real queries against Big-ANN
SPLADE-cocondenser at INT8, which is the corpus class the hand-built fixture
is standing in for.

A set difference is therefore NOT a failure here; it is the expected shape.
The failure is a split-returned document scoring strictly below the serial
k-th by more than float32 rounding can explain. Both are counted separately,
and the raw score deltas are reported so the "indistinguishable" claim is a
measured number rather than an assertion against a tolerance we chose.
"""
import json
import os
import time

os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")

SCALE = os.environ.get("PROBE_SCALE", "small")
OUT = os.environ.get("PROBE_OUT", "/pout/split_setdiff.json")

# float32 machine epsilon. A score is "indistinguishable" when the gap is
# within a few ulp of the larger magnitude; MaxScore sums many terms, so
# allow a modest multiple of eps for accumulated reordering, and report the
# observed maximum next to it so the reader can judge the slack.
F32_EPS = 1.1920929e-7
ULP_SLACK = 32.0


def _tol(a, b):
    return ULP_SLACK * F32_EPS * max(1.0, abs(a), abs(b))


def search_scored(be, idx, vals, k):
    """(rid, score) best-first. Mirrors the backend's own query but keeps the
    score column, which expand() in the benchmark path drops."""
    import jpype
    ji = jpype.JArray(jpype.JInt)(idx)
    jv = jpype.JArray(jpype.JFloat)(vals)
    rows = be.db.query(
        "sql", "SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?))",
        be.idx_name, ji, jv, k).to_json_list()
    return rows


def main():
    import bigann_sparse as src
    from l3_sparse import BACKENDS

    n_docs = src.SCALE_DOCS[SCALE]
    queries = list(src.gen_queries(src.SCALE_QUERIES[SCALE]))
    k = src.K

    be = BACKENDS["arcadedb_sparse_embedded"]()
    be.connect()
    t0 = time.perf_counter()
    be.build(n_docs)
    be.post_build()
    print(f"built {n_docs} docs in {time.perf_counter()-t0:.0f}s", flush=True)

    # Guard before measuring anything: this probe is worthless if the rows do
    # not actually carry a score, and a missing column would otherwise show up
    # as a silent zero-difference "pass". Fail loudly instead.
    probe_rows = search_scored(be, *queries[0][:2], k)
    if not probe_rows:
        raise SystemExit("GUARD FAILED: first query returned no rows")
    if "score" not in probe_rows[0]:
        raise SystemExit(f"GUARD FAILED: no score column; keys={sorted(probe_rows[0])}")
    if len(probe_rows) < k:
        raise SystemExit(f"GUARD FAILED: {len(probe_rows)} rows < k={k}; index not built?")
    print(f"guard ok: {len(probe_rows)} rows, keys={sorted(probe_rows[0])}", flush=True)

    import jpype
    GC = jpype.JClass("com.arcadedb.GlobalConfiguration")

    runs = {}
    for label, parts in [("serial", 1), ("adaptive", 0), ("forced8", 8)]:
        GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.setValue(jpype.JInt(parts))
        got = GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.getValue()
        if int(got) != parts:
            raise SystemExit(f"GUARD FAILED: maxPartitions set {parts}, read back {got}")
        print(f"{label}: maxPartitions={got}", flush=True)
        res = []
        for idx, vals in queries:
            rows = search_scored(be, idx, vals, k)
            res.append([(r["@rid"], float(r["score"])) for r in rows])
        runs[label] = res

    base = runs["serial"]
    report = {"scale": SCALE, "n_docs": n_docs, "n_queries": len(queries), "k": k,
              "ulp_slack": ULP_SLACK}

    for label in ("adaptive", "forced8"):
        other = runs[label]
        stats = {
            "queries_with_different_SET": 0,
            "queries_same_set_different_ORDER": 0,
            "queries_with_different_COUNT": 0,      # guarantee 1
            "queries_rank_score_mismatch": 0,       # guarantee 2
            "queries_below_serial_kth": 0,          # guarantee 3 -- the real failure
            "max_rank_score_delta": 0.0,
            "worst_below_kth_gap": 0.0,
            "examples": [],
        }
        for qi, (a, b) in enumerate(zip(base, other)):
            a_ids = [r for r, _ in a]
            b_ids = [r for r, _ in b]
            a_sc = [s for _, s in a]
            b_sc = [s for _, s in b]

            if len(a) != len(b):
                stats["queries_with_different_COUNT"] += 1

            # guarantee 2: rank for rank indistinguishable in score
            worst = 0.0
            for sa, sb in zip(a_sc, b_sc):
                d = abs(sa - sb)
                worst = max(worst, d)
                if d > _tol(sa, sb):
                    stats["queries_rank_score_mismatch"] += 1
                    break
            stats["max_rank_score_delta"] = max(stats["max_rank_score_delta"], worst)

            # guarantee 3: nothing the split returned ranks below serial's k-th
            if a_sc and b_sc:
                kth = a_sc[-1]
                gap = kth - min(b_sc)
                if gap > _tol(kth, min(b_sc)):
                    stats["queries_below_serial_kth"] += 1
                    stats["worst_below_kth_gap"] = max(stats["worst_below_kth_gap"], gap)

            if set(a_ids) != set(b_ids):
                stats["queries_with_different_SET"] += 1
                if len(stats["examples"]) < 3:
                    only_a = [x for x in a_ids if x not in set(b_ids)]
                    only_b = [x for x in b_ids if x not in set(a_ids)]
                    stats["examples"].append({
                        "q": qi,
                        "only_serial": [(r, dict(a)[r]) for r in only_a[:3]],
                        "only_split": [(r, dict(b)[r]) for r in only_b[:3]],
                        "serial_kth_score": a_sc[-1] if a_sc else None,
                    })
            elif a_ids != b_ids:
                stats["queries_same_set_different_ORDER"] += 1

        report[label] = stats
        print(f"RESULT {label} "
              f"set_diff={stats['queries_with_different_SET']} "
              f"order_diff={stats['queries_same_set_different_ORDER']} "
              f"count_diff={stats['queries_with_different_COUNT']} "
              f"rank_score_mismatch={stats['queries_rank_score_mismatch']} "
              f"BELOW_KTH={stats['queries_below_serial_kth']} "
              f"max_delta={stats['max_rank_score_delta']:.3e}", flush=True)

    # No be.close(): the sparse backends define no close(), and l3_sparse.main()
    # itself tears down with os._exit(). Calling it here would raise
    # AttributeError after the build and all three query passes had completed,
    # i.e. throw away the whole run at the last line.
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1)
    slim = {lbl: {k2: v for k2, v in report[lbl].items() if k2 != "examples"}
            for lbl in ("adaptive", "forced8")}
    print("SETDIFF-DONE " + json.dumps(slim), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
