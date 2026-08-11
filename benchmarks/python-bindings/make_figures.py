#!/usr/bin/env python3
"""Generate the paper's data figures from results/runs.csv (matplotlib).

Outputs PNG (~200 dpi, <1 MB) to figures/:
  fig_throughput.png  OLTP ops/s by backend (tabular + graph), at the largest tier present
  fig_latency.png     OLAP total latency (ms) by backend (tabular + graph)
  fig_memory.png      peak memory (MiB) by backend/lane
  fig_vector.png      vector recall@10 + query latency (arcadedb vs chroma)
  fig_scaling.png     key metrics vs dataset tier (if >=2 tiers present)

Run:  uv run --with matplotlib --with pandas python make_figures.py
Final figures come from the mini run's runs.csv; this also drafts from partial data.
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "results", "runs.csv")
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)
TIER_ORDER = ["tiny", "small", "medium"]
plt.rcParams.update({"font.size": 10, "font.family": "Helvetica", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 200})


def agg(df):
    num = df.select_dtypes("number").columns
    keys = ["lane", "dataset", "backend", "workload"]
    return df.groupby([k for k in keys if k in df], dropna=False)[list(num)].mean().reset_index()


def biggest_tier(df):
    present = [t for t in TIER_ORDER if t in set(df["dataset"])]
    return present[-1] if present else None


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.tight_layout(); fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    print(f"wrote {p} ({os.path.getsize(p)//1024} KB)")


def bar(ax, labels, vals, title, ylab, colors=None):
    ax.bar(labels, vals, color=colors or "#4c78a8")
    ax.set_title(title); ax.set_ylabel(ylab)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:,.0f}" if v >= 10 else f"{v:.2f}", ha="center", va="bottom", fontsize=8)


def main():
    raw = pd.read_csv(CSV)
    # backfill lane='vector' for rows from before vector_bench set it (identified by recall@10)
    if "recall@10" in raw.columns and "lane" in raw.columns:
        m = raw["recall@10"].notna()
        raw.loc[m, "lane"] = raw.loc[m, "lane"].fillna("vector")
    df = agg(raw)
    tier = biggest_tier(df)
    print(f"tiers present: {sorted(set(df['dataset']))} | headline tier: {tier}")
    d = df[df.dataset == tier]

    # throughput (OLTP ops/s) — tabular + graph
    sub = d[(d.workload == "oltp") & d["oltp_ops_per_s"].notna()].sort_values(["lane", "backend"])
    if len(sub):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        bar(ax, [f"{r.backend}\n({r.lane})" for r in sub.itertuples()], list(sub.oltp_ops_per_s),
            f"OLTP throughput — {tier}", "ops / s")
        save(fig, "fig_throughput.png")

    # OLAP latency
    sub = d[(d.workload == "olap") & d["olap_total_ms"].notna()].sort_values(["lane", "backend"])
    if len(sub):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        bar(ax, [f"{r.backend}\n({r.lane})" for r in sub.itertuples()], list(sub.olap_total_ms),
            f"OLAP latency — {tier}", "ms (lower=better)", colors="#e45756")
        save(fig, "fig_latency.png")

    # peak memory by backend/lane
    sub = d[d["peak_mib"].notna()].sort_values("peak_mib")
    if len(sub):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        lbl = [f"{r.backend}/{r.lane}" + (f"/{r.workload}" if isinstance(r.workload, str) else "")
               for r in sub.itertuples()]
        bar(ax, lbl, list(sub.peak_mib), f"Peak memory — {tier}", "MiB")
        ax.tick_params(axis="x", rotation=30)
        save(fig, "fig_memory.png")

    # vector recall + latency
    v = d[d.lane == "vector"]
    if len(v) and "recall@10" in v:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(7, 3.2))
        bar(a1, list(v.backend), list(v["recall@10"]), f"Vector recall@10 — {tier}", "recall", colors="#54a24b")
        a1.set_ylim(0, 1.05)
        bar(a2, list(v.backend), list(v.q_mean_ms), "Vector query latency", "ms", colors="#4c78a8")
        save(fig, "fig_vector.png")

    # scaling across tiers (if >=2)
    tiers = [t for t in TIER_ORDER if t in set(df["dataset"])]
    if len(tiers) >= 2:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(7, 3.2))
        for be in sorted(set(df[df.lane == "tabular"].backend)):
            s = df[(df.lane == "tabular") & (df.backend == be) & (df.workload == "oltp")]
            s = s.set_index("dataset").reindex(tiers)
            a1.plot(tiers, s.oltp_ops_per_s, marker="o", label=be)
        a1.set_title("Tabular OLTP scaling"); a1.set_ylabel("ops/s"); a1.legend(fontsize=8)
        for be in sorted(set(df.backend)):
            s = df[(df.backend == be) & df.peak_mib.notna()].groupby("dataset").peak_mib.mean().reindex(tiers)
            a2.plot(tiers, s, marker="o", label=be)
        a2.set_title("Peak memory scaling"); a2.set_ylabel("MiB"); a2.legend(fontsize=8)
        save(fig, "fig_scaling.png")
    else:
        print("scaling figure skipped (need >=2 tiers; rerun on mini results)")


if __name__ == "__main__":
    main()
