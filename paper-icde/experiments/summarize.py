#!/usr/bin/env python3
"""Summarize runs.jsonl into paper-ready tables (and lists what they came from).

Dedup policy: for each (lane, backend, workload, scale, rep) the row from the
LATEST manifest wins — re-measurements (heap parity, -Xms pinning) supersede
earlier rows without deleting history. Only error-free paper-tier rows are
aggregated; sweep-tier rows are excluded from paper tables by design.

Usage:
    python3 summarize.py                # all lanes/scales found
    python3 summarize.py --lanes l3s --scales medium
Writes results/summary/<lane>_<workload>_<scale>.md and prints them.
"""
import argparse
import json
import os
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

# metrics per lane worth a table column (order = column order)
LANE_METRICS = {
    "l1": ["build_s", "oltp_p50_ms", "oltp_p95_ms", "olap_p50_ms",
           "olap_p95_ms", "qps", "peak_mib_sum"],
    "l2": ["build_s", "point_p50_ms", "hop1_p50_ms", "hop2_p50_ms",
           "write_p50_ms", "top_degree_mean_ms", "same_city_edges_mean_ms",
           "friend_age_by_city_mean_ms", "peak_mib_sum"],
    "l3s": ["build_s", "query_p50_ms", "query_p95_ms", "query_p99_ms",
            "qps", "recall_at_10", "peak_mib_sum"],
}


def load_rows():
    rows = [json.loads(l) for l in open(os.path.join(RESULTS, "runs.jsonl"))]
    latest = {}
    for r in rows:
        if r.get("error") or r.get("tier") != "paper":
            continue
        key = (r.get("lane"), r.get("backend"), r.get("workload"),
               r.get("scale"), r.get("rep"))
        if key not in latest or r.get("manifest", "") > latest[key].get("manifest", ""):
            latest[key] = r
    return list(latest.values())


def fmt(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return "-"
    if len(vals) == 1:
        return f"{vals[0]:.3g}"
    return f"{st.mean(vals):.3g}±{st.stdev(vals):.2g}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", default="")
    ap.add_argument("--scales", default="")
    args = ap.parse_args()

    rows = load_rows()
    lanes = set(args.lanes.split(",")) if args.lanes else {r["lane"] for r in rows}
    scales = set(args.scales.split(",")) if args.scales else \
        {r["scale"] for r in rows}

    outdir = os.path.join(RESULTS, "summary")
    os.makedirs(outdir, exist_ok=True)

    groups = defaultdict(list)
    for r in rows:
        if r["lane"] in lanes and r["scale"] in scales:
            groups[(r["lane"], r["workload"], r["scale"])].append(r)

    for (lane, workload, scale), rs in sorted(groups.items()):
        metrics = [m for m in LANE_METRICS.get(lane, [])
                   if any(m in r for r in rs)]
        by_backend = defaultdict(list)
        for r in rs:
            by_backend[r["backend"]].append(r)
        lines = [f"# {lane} / {workload} / {scale}", ""]
        lines.append("| backend | n | " + " | ".join(metrics) + " | manifests |")
        lines.append("|" + "---|" * (len(metrics) + 3))
        for b, brs in sorted(by_backend.items()):
            cells = [fmt([r.get(m) for r in brs]) for m in metrics]
            mans = ",".join(sorted({r.get("manifest", "?") for r in brs}))
            lines.append(f"| {b} | {len(brs)} | " + " | ".join(cells) +
                         f" | {mans} |")
        text = "\n".join(lines) + "\n"
        path = os.path.join(outdir, f"{lane}_{workload}_{scale}.md")
        with open(path, "w") as f:
            f.write(text)
        print(text)


if __name__ == "__main__":
    main()
