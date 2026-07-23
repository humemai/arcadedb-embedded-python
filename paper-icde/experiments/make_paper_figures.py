#!/usr/bin/env python3
"""Generate paper figures from results/. Currently: F5 sparse scaling (with
the real-data cliff and the per-query decile inset evidence) and F7 E2
hybrid-transaction latency + atomicity outcome. PDFs land in ../latex/figures
and are margin-cropped with the two-pass Ghostscript recipe (verify with
pdfinfo; a silent crop failure must not pass).
"""
import json
import os
import statistics as st
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FIGS = os.path.join(HERE, "..", "..", ".notes", "papers", "icde-2027", "latex", "figures")

plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 150})


def canonical():
    rows = [json.loads(l) for l in open(os.path.join(RESULTS, "runs.jsonl"))
            if l.strip()]
    best = {}
    for r in rows:
        if r.get("rc") != 0:
            continue
        k = (r["lane"], r["scale"], r.get("n_docs"), r.get("workload"),
             r["backend"], r["rep"])
        if k not in best or r["ts_utc"] > best[k]["ts_utc"]:
            best[k] = r
    return list(best.values())


def gs_crop(path, margin=4):
    out = subprocess.run(["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=bbox",
                          path], capture_output=True, text=True)
    bbox = None
    for line in (out.stderr + out.stdout).splitlines():
        if line.startswith("%%BoundingBox:"):
            bbox = [int(x) for x in line.split()[1:5]]
    if not bbox:
        raise RuntimeError(f"gs bbox failed for {path}")
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0 + 2 * margin, y1 - y0 + 2 * margin
    tmp = path + ".crop.pdf"
    subprocess.run(["gs", "-q", "-o", tmp, "-sDEVICE=pdfwrite",
                    f"-dDEVICEWIDTHPOINTS={w}", f"-dDEVICEHEIGHTPOINTS={h}",
                    "-dFIXEDMEDIA", "-c",
                    f"<</PageOffset [{-(x0 - margin)} {-(y0 - margin)}]>> setpagedevice",
                    "-f", path], check=True)
    os.replace(tmp, path)
    info = subprocess.run(["pdfinfo", path], capture_output=True, text=True)
    size = [l for l in info.stdout.splitlines() if l.startswith("Page size")]
    print(f"cropped {os.path.basename(path)}: {size[0].split(':')[1].strip()}")


def f5_sparse_scaling(rows):
    l3s = [r for r in rows if r["lane"] == "l3s"]
    series = {"arcadedb_sparse_embedded": ("ArcadeDB (emb, int8)", "o", "C3"),
              "qdrant_sparse": ("Qdrant", "s", "C0"),
              "milvus_sparse": ("Milvus", "^", "C2"),
              "elasticsearch_sparse": ("Elasticsearch", "d", "C1")}
    scales = [("tiny", 1e5), ("small", 1e6)]
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    for be, (label, mark, color) in series.items():
        xs, ys, lo, hi = [], [], [], []
        for sc, n in scales:
            g = [r["query_p50_ms"] for r in l3s
                 if r["backend"] == be and r["scale"] == sc]
            if not g:
                continue
            xs.append(n)
            ys.append(st.median(g))
            lo.append(st.median(g) - min(g))
            hi.append(max(g) - st.median(g))
        ax.errorbar(xs, ys, yerr=[lo, hi], marker=mark, color=color,
                    label=label, lw=1.2, ms=4, capsize=2)
    # synthetic-corpus contrast for ArcadeDB (10M docs, no cliff), dashed
    syn = [r["query_p50_ms"] for r in l3s
           if r["backend"] == "arcadedb_sparse_embedded"
           and r["scale"] == "medium"]
    if syn:
        ax.plot([1e7], [st.median(syn)], marker="o", mfc="none", color="C3",
                ls="none", ms=5)
        ax.annotate("ArcadeDB, synthetic\ncorpus (no cliff)", (1e7, st.median(syn)),
                    textcoords="offset points", xytext=(-72, 8), fontsize=6.5,
                    color="C3")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("corpus size (documents)")
    ax.set_ylabel("query p50 (ms)")
    ax.legend(fontsize=6.5, loc="upper left", framealpha=0.9)
    fig.tight_layout()
    path = os.path.join(FIGS, "f5_sparse_scaling.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def f7_e2(rows):
    e2 = [r for r in rows if r["lane"] == "e2"]
    order = [("arcadedb_e2", "ArcadeDB\n(one txn)"),
             ("surrealdb_e2", "SurrealDB\n(one txn)"),
             ("composed_qdrant_neo4j", "Qdrant+Neo4j\n(composed)")]
    fig, ax = plt.subplots(figsize=(3.45, 2.0))
    for i, (be, label) in enumerate(order):
        h = [r["hybrid_p50_ms"] for r in e2
             if r["backend"] == be and r["workload"] == "hybrid"]
        a = [r.get("torn_state") for r in e2
             if r["backend"] == be and r["workload"] == "atomicity"]
        torn = sum(bool(t) for t in a)
        med = st.median(h)
        bar = ax.bar(i, med, width=0.55,
                     color="C3" if torn else "C0", alpha=0.85)
        ax.errorbar(i, med, yerr=[[med - min(h)], [max(h) - med]], color="k",
                    capsize=3, lw=1)
        outcome = (f"torn state\n{torn}/{len(a)} crashes" if torn
                   else f"atomic\n{len(a)}/{len(a)} crashes")
        ax.annotate(outcome, (i, med), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=6.5)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([l for _, l in order], fontsize=7)
    ax.set_ylabel("hybrid op p50 (ms)")
    ax.set_ylim(0, 30)
    fig.tight_layout()
    path = os.path.join(FIGS, "f7_e2_hybrid.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def f8_deployment(rows):
    """Server/embedded ratio per metric: the transport fee, same engine."""
    def med(lane, scale, wl, be, field):
        g = [r[field] for r in rows if r["lane"] == lane and r["scale"] == scale
             and r.get("workload") == wl and r["backend"] == be
             and isinstance(r.get(field), (int, float))]
        return st.median(g) if g else None

    pairs = [
        ("OLTP\nthroughput", med("l1", "medium", "oltp", "arcadedb_embedded", "oltp_ops_per_s"),
         med("l1", "medium", "oltp", "arcadedb_server", "oltp_ops_per_s"), True),
        ("Insert\np99", med("l1", "medium", "oltp", "arcadedb_embedded", "insert_p99_ms"),
         med("l1", "medium", "oltp", "arcadedb_server", "insert_p99_ms"), False),
        ("Graph\n1-hop p50", med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"),
         med("l2", "sf10", "oltp", "arcadedb_graph_server", "hop1_p50_ms"), False),
        ("Sparse\np50", med("l3s", "small", "search", "arcadedb_sparse_embedded", "query_p50_ms"),
         med("l3s", "small", "search", "arcadedb_sparse_server", "query_p50_ms"), False),
        ("Dense\np50", med("l3d", "deep10m", "search", "arcadedb_dense_embedded", "query_p50_ms"),
         med("l3d", "deep10m", "search", "arcadedb_dense_server", "query_p50_ms"), False),
        ("TPC-H Q1", med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "q1_ms"),
         med("l1tpc", "tpch1", "olap", "arcadedb_server", "q1_ms"), False),
    ]
    labels, ratios = [], []
    for label, emb, srv, higher_better in pairs:
        if emb is None or srv is None:
            continue
        labels.append(label)
        ratios.append((emb / srv) if higher_better else (srv / emb))
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.bar(range(len(ratios)), ratios, width=0.6, color="C0", alpha=0.85)
    ax.axhline(1.0, color="k", lw=0.8, ls="--")
    for i, v in enumerate(ratios):
        ax.annotate(f"{v:.1f}x", (i, v), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=6.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylabel("server cost / embedded")
    fig.tight_layout()
    path = os.path.join(FIGS, "f8_deployment.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def f4_one_vs_n(rows):
    """ArcadeDB embedded relative to the best specialist per workload,
    log scale; >1 = ArcadeDB ahead. The honest summary figure."""
    def med(lane, scale, wl, be, f):
        g = [r[f] for r in rows if r["lane"] == lane and r["scale"] == scale
             and r.get("workload") == wl and r["backend"] == be
             and isinstance(r.get(f), (int, float))]
        return st.median(g) if g else None

    ts = [json.loads(l) for l in open(os.path.join(RESULTS, "l4_tsbs.jsonl"))
          if l.strip()]

    def tsmed(be, f):
        return st.median([r[f] for r in ts if r["backend"] == be])

    entries = [  # (label, arcade value, best specialist value, higher_better)
        ("Cross-model txn p50", med("e2", "e2", "hybrid", "arcadedb_e2", "hybrid_p50_ms"),
         med("e2", "e2", "hybrid", "composed_qdrant_neo4j", "hybrid_p50_ms"), False),
        ("OLTP ops/s", med("l1", "medium", "oltp", "arcadedb_embedded", "oltp_ops_per_s"),
         med("l1", "medium", "oltp", "postgres", "oltp_ops_per_s"), True),
        ("Graph 1-hop p50", med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"),
         med("l2", "sf10", "oltp", "ladybug_graph", "hop1_p50_ms"), False),
        ("TS last-point p50", tsmed("arcadedb", "q_last_ms"),
         tsmed("questdb", "q_last_ms"), False),
        ("Sparse 100k p50", med("l3s", "tiny", "search", "arcadedb_sparse_embedded", "query_p50_ms"),
         med("l3s", "tiny", "search", "qdrant_sparse", "query_p50_ms"), False),
        ("Dense 10M p50", med("l3d", "deep10m", "search", "arcadedb_dense_embedded", "query_p50_ms"),
         med("l3d", "deep10m", "search", "qdrant_dense", "query_p50_ms"), False),
        ("Sparse 1M p50", med("l3s", "small", "search", "arcadedb_sparse_embedded", "query_p50_ms"),
         med("l3s", "small", "search", "qdrant_sparse", "query_p50_ms"), False),
        ("TS ingest pts/s", tsmed("arcadedb", "ingest_pts_per_s"),
         tsmed("duckdb", "ingest_pts_per_s"), True),
        ("TPC-H Q1", med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "q1_ms"),
         med("l1tpc", "tpch1", "olap", "duckdb", "q1_ms"), False),
    ]
    labels, ratios = [], []
    for label, a, s, hb in entries:
        if a is None or s is None:
            continue
        labels.append(label)
        ratios.append((a / s) if hb else (s / a))
    fig, ax = plt.subplots(figsize=(3.45, 2.5))
    ys = range(len(ratios))[::-1]
    colors = ["C0" if r >= 1 else "C3" for r in ratios]
    ax.barh(list(ys), ratios, color=colors, alpha=0.85, height=0.6)
    ax.axvline(1.0, color="k", lw=0.8, ls="--")
    for y, r in zip(ys, ratios):
        ax.annotate(f"{r:.3g}x" if r < 1 else f"{r:.2g}x", (max(r, 0.002), y),
                    textcoords="offset points", xytext=(3, -2), fontsize=6.5)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.set_xscale("log")
    ax.set_xlim(5e-4, 50)
    ax.set_xlabel("ArcadeDB (embedded) vs best specialist, log scale")
    fig.tight_layout()
    path = os.path.join(FIGS, "f4_one_vs_n.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def f6_memory_ceiling(rows):
    """Peak anon working set at DEEP-10M: memory is the scale ceiling."""
    order = [("arcadedb_dense_embedded", "ArcadeDB (emb)"),
             ("arcadedb_dense_server", "ArcadeDB (srv)"),
             ("duckdb_vss_dense", "DuckDB-VSS"),
             ("lancedb_dense", "LanceDB"), ("chroma_dense", "Chroma"),
             ("milvus_dense", "Milvus"), ("sqlite_vec_dense", "sqlite-vec"),
             ("qdrant_dense", "Qdrant")]
    labels, vals = [], []
    for be, label in order:
        g = [r["peak_anon_mib_sum"] / 1024 for r in rows
             if r["lane"] == "l3d" and r["scale"] == "deep10m"
             and r["backend"] == be
             and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
        if g:
            labels.append(label)
            vals.append(st.median(g))
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.bar(range(len(vals)), vals, width=0.6, color="C0", alpha=0.85)
    ax.axhline(3.84, color="C2", lw=1, ls=":")
    ax.annotate("raw vectors 3.8 GiB", (len(vals) - 3.6, 4.1), fontsize=6.5,
                color="C2")
    ax.annotate("build OOMs at 16 GiB heap;\nneeds 19+ (\\#3144)",
                (0.4, 22), fontsize=6.5, color="C3")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6, rotation=20, ha="right")
    ax.set_ylabel("peak anon (GiB)")
    fig.tight_layout()
    path = os.path.join(FIGS, "f6_memory_ceiling.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def main():
    os.makedirs(FIGS, exist_ok=True)
    rows = canonical()
    f4_one_vs_n(rows)
    f5_sparse_scaling(rows)
    f6_memory_ceiling(rows)
    f7_e2(rows)
    f8_deployment(rows)


if __name__ == "__main__":
    main()
