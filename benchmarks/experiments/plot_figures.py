#!/usr/bin/env python3
"""Paper figures from runs.jsonl (matplotlib -> PDF into latex/figures/).

Same dedup policy as summarize.py: latest manifest wins per cell; paper-tier
error-free rows only. Run host-side:
    uv run --no-project --with matplotlib python plot_figures.py
"""
import json
import os
import statistics as st
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FIGDIR = os.path.join(HERE, "..", "latex", "figures")

SCALE_ORDER = ["tiny", "small", "medium", "large"]
SCALE_DOCS_L3 = {"tiny": 1e5, "small": 1e6, "medium": 1e7}

STYLE = {
    "arcadedb_sparse_embedded": dict(color="#c0392b", marker="o",
                                     label="ArcadeDB (embedded)"),
    "arcadedb_sparse_server": dict(color="#e67e22", marker="s",
                                   label="ArcadeDB (server)"),
    "qdrant_sparse": dict(color="#2980b9", marker="^", label="Qdrant"),
    "milvus_sparse": dict(color="#27ae60", marker="v", label="Milvus"),
    "elasticsearch_sparse": dict(color="#8e44ad", marker="D",
                                 label="Elasticsearch"),
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


def fig_l3_scale_sweep(rows):
    """p50 (mean±std over reps) vs corpus size, log-log, per backend."""
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["lane"] == "l3s" and r["scale"] in SCALE_DOCS_L3:
            by[r["backend"]][r["scale"]].append(r["query_p50_ms"])

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for backend, style in STYLE.items():
        xs, ys, es = [], [], []
        for scale in SCALE_ORDER:
            if scale in by[backend] and len(by[backend][scale]) >= 2:
                xs.append(SCALE_DOCS_L3[scale])
                ys.append(st.mean(by[backend][scale]))
                es.append(st.stdev(by[backend][scale]))
        if xs:
            ax.errorbar(xs, ys, yerr=es, capsize=2.5, lw=1.4, ms=4.5, **style)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("corpus size (documents)")
    ax.set_ylabel("query latency p50 (ms)")
    ax.grid(True, which="both", lw=0.3, alpha=0.4)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    out = os.path.join(FIGDIR, "l3_sparse_scale_sweep.pdf")
    fig.savefig(out)
    print(f"wrote {out}")


def main():
    os.makedirs(FIGDIR, exist_ok=True)
    rows = load_rows()
    fig_l3_scale_sweep(rows)


if __name__ == "__main__":
    main()
