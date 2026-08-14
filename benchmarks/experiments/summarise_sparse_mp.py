#!/usr/bin/env python3
"""What a second pass buys each SPARSE engine, and whether it reorders T4.

Reads results/sparse_mp/sp_<label>_<scale>.json written by
sparse_multipass_driver.py: rep 0 is the cold pass over the first half of the
dev queries, reps 1..5 are warm passes over the second half.

The ranking block is the point. T4 publishes ONE pass per engine, so if the
cold and warm orders differ, the published order is a property of the operating
point rather than of the engines, and the table has to say which point it used.

    python3 summarise_sparse_mp.py [scale]
"""
import glob
import json
import os
import statistics as st
import sys

# T4 as published (N=5, one timed pass per cell, real Big-ANN SPLADE).
# Printed beside the cold column as a sanity check: rep 0 here should land
# near these, because it is the same measurement.
T4 = {
    "small": {"arc_int8": 11.339, "arc_fp32": 11.521, "arc_srv": 13.608,
              "qdrant": 2.867, "milvus": 9.041, "elastic": 9.829},
    "medium": {"arc_int8": 82.940, "arc_fp32": 86.231, "arc_srv": 89.447,
               "qdrant": 16.119, "milvus": 38.998, "elastic": 55.766},
}
NAMES = {"arc_int8": "ArcadeDB int8", "arc_fp32": "ArcadeDB fp32",
         "arc_srv": "ArcadeDB srv", "qdrant": "Qdrant",
         "milvus": "Milvus", "elastic": "Elasticsearch"}


def load(scale):
    rows = {}
    for fp in sorted(glob.glob(f"results/sparse_mp/sp_*_{scale}.json")):
        label = os.path.basename(fp)[len("sp_"):-len(f"_{scale}.json")]
        try:
            reps = json.load(open(fp))
        except Exception as exc:
            print(f"  !! {fp}: {exc}")
            continue
        cold = [r for r in reps if r.get("rep") == 0]
        warm = [r for r in reps if r.get("rep", 0) >= 1]
        if not cold or not warm:
            print(f"  !! {label}: {len(cold)} cold, {len(warm)} warm; skipped")
            continue
        rows[label] = {
            "cold": cold[0]["query_p50_ms"],
            "warm": st.median(r["query_p50_ms"] for r in warm),
            "warm_n": len(warm),
            "recall_cold": cold[0].get("recall_at_10"),
            "recall_warm": st.median(
                [r["recall_at_10"] for r in warm if r.get("recall_at_10")]
                or [float("nan")]),
            "build_s": cold[0].get("build_s"),
        }
    return rows


def report(scale):
    rows = load(scale)
    if not rows:
        print(f"\n  no {scale} results yet")
        return
    print(f"\n  ===== {scale} =====")
    print(f"  {'engine':16} {'build s':>8} {'cold p50':>9} {'warm p50':>9} "
          f"{'gain':>7} {'T4':>8} {'rec cold':>9} {'rec warm':>9}")
    for k, v in sorted(rows.items(), key=lambda kv: kv[1]["cold"]):
        t4 = T4.get(scale, {}).get(k)
        print(f"  {NAMES.get(k, k):16} {v['build_s'] or 0:8.1f} "
              f"{v['cold']:9.3f} {v['warm']:9.3f} "
              f"{v['cold'] / v['warm']:6.2f}x "
              f"{t4 if t4 else float('nan'):8.3f} "
              f"{v['recall_cold'] or float('nan'):9.4f} "
              f"{v['recall_warm']:9.4f}")

    cold_order = [k for k, _ in sorted(rows.items(), key=lambda kv: kv[1]["cold"])]
    warm_order = [k for k, _ in sorted(rows.items(), key=lambda kv: kv[1]["warm"])]
    print("\n  RANKING (fastest first)")
    print("    cold  " + " < ".join(NAMES.get(k, k) for k in cold_order))
    print("    warm  " + " < ".join(NAMES.get(k, k) for k in warm_order))
    if cold_order == warm_order:
        print("\n    Same order both ways: the operating point does not change")
        print("    the claim, and T4 can keep its numbers with the protocol")
        print("    disclosed.")
    else:
        print("\n    ORDER DEPENDS ON THE OPERATING POINT. T4 and f4 must lead")
        print("    with ONE point applied to every engine, and say which.")

    # The split is only trustworthy if the two query halves are equally hard.
    bad = [k for k, v in rows.items()
           if v["recall_cold"] and abs(v["recall_cold"] - v["recall_warm"]) > 0.02]
    if bad:
        print("\n    WARNING: cold/warm recall differs by >2 points for "
              + ", ".join(NAMES.get(k, k) for k in bad)
              + ".\n    The two query halves may not be equally hard, which "
                "confounds the latency\n    comparison. Check before quoting.")
    else:
        print("\n    Cold and warm recall agree within 2 points everywhere, so")
        print("    the two query halves are comparable and the split is sound.")


if __name__ == "__main__":
    for s in ([sys.argv[1]] if len(sys.argv) > 1 else ["small", "medium"]):
        report(s)
