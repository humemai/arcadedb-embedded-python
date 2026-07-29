#!/usr/bin/env python3
"""Does #5518's range split return the same DOCUMENT SET as the serial scan,
on a real quantized corpus?

The PR review's one merge-blocking item: the equivalence tests use a tie corpus
whose scores are exactly representable (0.5*4 = 2.0), which removes the ulp, so
the one interaction that can diverge is never exercised. On a real INT8 corpus
exact ties are common, MaxScore sums terms in an order that depends on the
essential/non-essential split, and a range reaches that watermark at a different
point than the serial scan. Two documents tied in serial can end up an ulp apart
in the split, and if they straddle k/(k+1) the retained SET differs.

Our sparse lane already reports recall identical to 4dp across partition
settings, but recall is measured against ground truth: two different sets can
score the same recall. That is consistent with set equality, not proof of it.

This compares the returned ids directly, query by query, serial vs adaptive vs
forced-8, on Big-ANN SPLADE at INT8. One build, three query passes.
"""
import json
import os
import time

os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")

SCALE = os.environ.get("PROBE_SCALE", "small")
OUT = os.environ.get("PROBE_OUT", "/pout/split_setdiff.json")


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

    import jpype
    GC = jpype.JClass("com.arcadedb.GlobalConfiguration")

    runs = {}
    for label, parts in [("serial", 1), ("adaptive", 0), ("forced8", 8)]:
        GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.setValue(jpype.JInt(parts))
        got = GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.getValue()
        print(f"{label}: maxPartitions={got}", flush=True)
        res = []
        for idx, vals in queries:
            res.append(list(be.search(idx, vals, k)))
        runs[label] = res

    base = runs["serial"]
    report = {"scale": SCALE, "n_docs": n_docs, "n_queries": len(queries), "k": k}
    for label in ("adaptive", "forced8"):
        other = runs[label]
        set_diff = order_diff = 0
        examples = []
        for i, (a, b) in enumerate(zip(base, other)):
            if set(a) != set(b):
                set_diff += 1
                if len(examples) < 3:
                    examples.append({"q": i, "only_serial": sorted(set(a) - set(b))[:4],
                                     "only_split": sorted(set(b) - set(a))[:4]})
            elif a != b:
                order_diff += 1
        report[label] = {
            "queries_with_different_SET": set_diff,
            "queries_same_set_different_ORDER": order_diff,
            "examples": examples,
        }
        print(f"RESULT {label} set_diff={set_diff} order_diff={order_diff}", flush=True)

    be.close()
    json.dump(report, open(OUT, "w"))
    print("SETDIFF-DONE " + json.dumps({k2: v for k2, v in report.items()
                                        if k2 != "examples"}), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
