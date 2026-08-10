#!/usr/bin/env python3
"""Generate paper figures from results/. Currently: F5 sparse scaling (with
the real-data cliff and the per-query decile inset evidence) and F7 E2
hybrid-transaction latency + atomicity outcome. PDFs land in ../latex/figures
and are margin-cropped with the two-pass Ghostscript recipe (verify with
pdfinfo; a silent crop failure must not pass).
"""
import json
import os
import re
import statistics as st
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
# The paper source is deliberately not in this repository. Point
# BENCH_PAPER_DIR at the directory holding paper.tex and its generated
# tables/ and figures/ subdirectories.
_PAPER_DIR = os.environ.get(
    "BENCH_PAPER_DIR", os.path.join(HERE, "..", "..", "paper"))
FIGS = os.path.join(_PAPER_DIR, "figures")

plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 150})


def canonical():
    """The tables' canonical rule, imported rather than reimplemented.

    This file used to carry its own copy, identical except that it lacked the
    PAPER_SCALES filter. Two copies of a selection rule is how the dense
    figures came to plot pre-#5412 numbers while the table showed post-fix
    ones: nothing forced them to agree. Verified identity-preserving before
    switching, since every lane/scale pair the tables filter out (l1 tiny and
    small, l2 micro/tiny/small/medium, l3d micro, l3s micro) is one no figure
    selects.
    """
    import make_paper_tables as _T
    return _T.load_canonical()


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
    _check_labels_intact(path)


def _check_labels_intact(path, expect=None):
    """Fail if a label in the saved PDF is not the label we asked for.

    f4 shipped with its x-axis reading "...log sca". matplotlib clips a text
    object at the canvas edge when it is wider than the figure, and everything
    downstream then behaved correctly on the truncated input: tight_layout had
    no room to give, the gs bbox measured the ink present, and the crop
    reported a clean size. Every check passed and the figure was wrong.

    So check the OUTPUT against the intent. EXPECT_IN_PDF lists strings whose
    presence in a figure is part of that figure's correctness; a truncation
    removes the tail, which is exactly what a substring test catches.
    """
    want = expect if expect is not None else EXPECT_IN_PDF.get(
        os.path.basename(path))
    if not want:
        return
    txt = subprocess.run(["pdftotext", path, "-"],
                         capture_output=True, text=True).stdout
    flat = " ".join(txt.split())
    missing = [s for s in want if " ".join(s.split()) not in flat]
    if missing:
        raise SystemExit(
            f"{os.path.basename(path)}: label(s) missing or truncated in the "
            f"saved PDF: {missing}\n"
            "  A label wider than the figure is clipped at save time. Shrink "
            "the fontsize or shorten the text; cropping cannot recover it.")


# Strings that must survive into the saved PDF. Keep these to labels that
# have actually been at risk or that carry meaning a reader needs.
EXPECT_IN_PDF = {
    "f4_one_vs_n.pdf": ["log scale", "best specialist"],
    "f6_memory_ceiling.pdf": ["(#3144)", "raw vectors"],
    "f8_deployment.pdf": ["server cost / embedded"],
    "f7_e2_hybrid.pdf": ["hybrid op p50 (ms)"],
    "f3_sparse_perquery.pdf": ["decile median"],
}


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


def f3_sparse_perquery():
    """Per-query latency vs summed posting length (bigann 1M, 1000 dev
    queries): the evidence that pruning is not cutting head terms.

    NOT DRAWN, and refuses to be. sparse_cliff.jsonl holds a median of 228 ms
    against a released engine that answers the same tier at 11.3 ms, so it
    depicts a version the paper does not report. Worse, not one row in it
    carries an engine version, which is why no gate caught the figure sitting
    in the paper long after the tier was re-measured (DECISIONS #43).

    Left in place rather than deleted so the capability survives a re-measure:
    stamp every row with the engine version and drop this guard.
    """
    path = os.path.join(RESULTS, "sparse_cliff.jsonl")
    recs = [json.loads(l) for l in open(path) if l.strip()]
    unstamped = [r for r in recs if not r.get("engine_version")]
    if unstamped:
        print("  f3_sparse_perquery: SKIPPED, %d/%d rows carry no "
              "engine_version (see docstring)" % (len(unstamped), len(recs)))
        return
    x = [r["sum_df"] / 1e6 for r in recs]
    y = [r["ms"] for r in recs]
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    ax.plot(x, y, ".", ms=2.5, alpha=0.35, color="C3", rasterized=True)
    # decile medians as a line
    import numpy as np
    xa, ya = np.array(x), np.array(y)
    qs = np.percentile(xa, np.arange(0, 101, 10))
    cx = [(qs[i] + qs[i + 1]) / 2 for i in range(10)]
    cy = [float(np.median(ya[(xa >= qs[i]) & (xa <= qs[i + 1])]))
          for i in range(10)]
    ax.plot(cx, cy, "-o", color="k", lw=1.2, ms=3, label="decile median")
    ax.set_xlabel("summed posting length of query terms (millions)")
    ax.set_ylabel("query latency (ms)")
    ax.annotate("Spearman $\\rho$ = 0.95", (0.05, 0.9),
                xycoords="axes fraction", fontsize=7)
    ax.legend(fontsize=6.5, loc="lower right")
    fig.tight_layout()
    out = os.path.join(FIGS, "f3_sparse_perquery.pdf")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    gs_crop(out)


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



def _dense_overlay_p50(srv=False):
    """Dense WARM p50 from the SAME artifacts the tables read.

    The dense lane's published numbers do not live in runs.jsonl. They live in
    results/dense_mp_2681/, as one build followed by five passes: pass 0 is
    cold (a page-cache fill) and passes 1-4 are steady state. Reading
    runs.jsonl here plotted the pre-#5412 measurement, so the figures and the
    table disagreed by an order of magnitude on the same quantity.

    THIS FUNCTION BROKE WHEN THE TABLE WAS REBUILT and nothing noticed until
    the figures were regenerated: it called _dev16_dense_rows(), a helper
    deleted along with the dev-era dense path, so make_paper_figures.py raised
    AttributeError on every run. The figure freshness gate caught the
    consequence (five stale PDFs) but not the cause, because a generator that
    cannot start also cannot disagree with a table.

    WARM IS THE CHOICE, and it is a claim rather than a convenience: f4 and f8
    plot a steady-state comparison, and the cold pass is reported separately
    in its own column precisely because the two are different quantities.
    Averaging across the boundary would plot neither.
    """
    import glob as _glob
    import json as _json
    import make_paper_tables as _T
    # Five independent builds now, so this pools every warm pass of every
    # build (5 x 4 = 20) instead of the four passes of a single build. Same
    # quantity, twenty times the support; the cold pass is still excluded
    # because it is a different quantity, as above.
    name = "mp_arcsrv_b*.json" if srv else "mp_fp32_b*.json"
    hits = sorted(_glob.glob(os.path.join(_T.RESULTS, "dense_mp5_2681", name)))
    if not hits:
        return None
    warm = []
    for h in hits:
        passes = _json.load(open(h))
        warm += [p["p50"] for p in passes[1:]
                 if isinstance(p.get("p50"), (int, float))]
    return st.median(warm) if warm else None


# f4 entry label -> the table cell that must agree with it. Only ArcadeDB's
# side is mapped: the comparator columns come from runs.jsonl in both the
# figure and the tables, so they cannot drift apart the way the overlays did.
F4_VS_TABLE = {
    "OLTP ops/s":      ("t2_tabular.tex", "ArcadeDB (emb)", 0),
    # col 0 of this row is the SCALE column ("SF10"), so p50 is col 1.
    "Graph 1-hop p50": ("t3_graph.tex", "ArcadeDB (emb) & SF10", 1),
    # T4 is three rows per system now, so a column index addresses whatever
    # happens to sit there: these two read the literal tier label "100k" as
    # 1e5, and the R@10 column as a latency. The check caught it, which is
    # what it is for, but a second column-index map is a second thing to
    # break. Both go through the tier-aware reader instead.
    "Sparse 100k p50": ("sparse", "ArcadeDB (emb, int8)", "100k"),
    "Sparse 1M p50":   ("sparse", "ArcadeDB (emb, int8)", "1M"),
    # Column 2 is Warm p50 and the label carries its arm: T5's dense half is
    # now System & Build & Cold p50 & Warm p50 & Cold p99 & Recall, and the
    # embedded row split into fp32/int8. Both halves of this entry were stale.
    "Dense 10M p50":   ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 2),
    "TS 12h agg p50":  ("t5_dense_ts.tex", "ArcadeDB (native TS)", 3),
}


def _check_f4_against_tables(entries):
    """Assert f4 plots the same numbers the tables print.

    Three separate times a figure entry and its table cell came from different
    sources and nobody noticed until the two were compared by hand:

      dense 10M   figure read runs.jsonl, table read verify5412b (fixed first)
      sparse 1M   figure read runs.jsonl (dev3), table read dev22:
                  56.8x behind Qdrant plotted against the table's 3.90x
      TS ingest   figure read batch1 (the adapter's per-element arm),
                  table read the dev21 primitive arm: 411k against 1.73M

    Each was fixed in isolation and the next one was found the same way, by
    hand, later. The pattern is not carelessness: a figure and a table can
    quietly select differently forever, because nothing forces them to agree
    and a plotted bar carries no number a reader can check against the table.

    So the generator now checks itself. Runs on every figure build, prints
    every comparison, and raises on mismatch: a wrong figure is worse than a
    missing one, since a bar chart is read as summary and trusted.
    """
    import claims_check as _C
    bad = []
    print("  f4 vs tables:")
    for label, arcade, _spec, _hb in entries:
        if label not in F4_VS_TABLE:
            print(f"    {label:20} (no table cell to compare)")
            continue
        tab, row, col = F4_VS_TABLE[label]
        cell = (_C.sparse_cell(row, col, "p50") if tab == "sparse"
                else _C.cell(tab, row, col))
        if cell is None or arcade is None:
            bad.append(f"{label}: figure={arcade} table={cell}")
            continue
        # 2% covers the tables' own rounding ("1.73M", "29.56", "3.98")
        ok = abs(arcade - cell) <= max(0.02 * abs(cell), 0.02)
        print(f"    {label:20} figure={arcade:<12.4g} table={cell:<10.4g} "
              f"{'ok' if ok else 'MISMATCH'}")
        if not ok:
            bad.append(f"{label}: figure={arcade:.4g} table={cell:.4g}")
    if bad:
        raise SystemExit("f4 disagrees with the tables it summarises:\n  "
                         + "\n  ".join(bad))


def _sparse_overlay_p50(tier):
    """ArcadeDB sparse p50 from the SAME overlays the table reads.

    The identical defect _dense_overlay_p50 documents, left unfixed one lane
    over. The sparse ArcadeDB rows do not live in runs.jsonl either: the table
    takes tiny/small from the dev22 overlay and medium from dev22's 8.84M
    cell, falling back rather than mixing. Reading canonical rows here plotted
    dev0 at 100k and dev3 at 1M, so f4, the figure captioned "the whole
    evaluation in one figure", showed sparse 1M at 56.8x behind Qdrant while
    Table IV two pages later said 3.90x.

    Worth noting which direction it ran: 100k was FLATTERED by the stale data
    (2.12x plotted against 5.84x real) and 1M was punished by it. A figure
    wrong in both directions at once is the signature of stale inputs rather
    than a thumb on the scale, and neither error is one a reader could catch
    without recomputing the figure.

    Mirrors the table's precedence exactly by calling into it.

    THE PRECEDENCE IT MIRRORED IS GONE. T4 now reads results/sparse_2681/
    through _sparse_2681_rows(), one released engine at N=5 across all three
    tiers, which replaced the six-deep dev cascade this function reproduced.
    Left pointing at dev22, the figure plotted 3.98 ms at 100k against the
    table's 4.19 on the same cell: not an order of magnitude, which is
    precisely why it needed the guard rather than an eye. The lesson is the
    one this docstring already recorded and then repeated: mirroring a
    selection rule by COPYING it means the copy has to be updated too, so
    call the table's own function instead of restating what it does.
    """
    import make_paper_tables as _T
    g = _T._sparse_2681_rows().get(tier)
    v = [r["query_p50_ms"] for r in (g or [])
         if isinstance(r.get("query_p50_ms"), (int, float))]
    return st.median(v) if v else None


def f8_deployment(rows):
    """Server/embedded ratio per metric: the transport fee, same engine."""
    def _sel(lane, scale, wl, be):
        return [r for r in rows if r["lane"] == lane and r["scale"] == scale
                and r.get("workload") == wl and r["backend"] == be]

    def _line(rs):
        """The engine LINE a set of rows was measured on, e.g. '26.8.1'.

        Server rows stamp themselves 'server:26.8.1 (build ...)' and embedded
        rows stamp '26.8.1', so the strings never compare equal even when the
        release does. Reduce both to the release they name.

        Not every adapter scrapes a version. l1 records 'server:latest',
        l1tpc 'server', l3d 'unknown (PackageNotFoundError)'. Comparing those
        against the embedded '26.8.1' failed F5 and refused to draw f8, on
        rows that had in fact run the pinned released image: the runner
        records it as server_image_ref, 'arcadedata/arcadedb:26.8.1@sha256:...'
        for every server row in the campaign. So when the label names no
        version, take the release from the image reference, which is the
        stronger witness anyway. If neither names one this still returns the
        uninformative string and F5 still refuses, which is the correct
        outcome for a row that cannot say what served it.
        """
        out = set()
        for r in rs:
            v = str(r.get("engine_version") or r.get("wheel_version") or "?")
            v = v.split("(")[0].replace("server:", "").strip()
            if not re.search(r"\d+\.\d+\.\d+", v):
                ref = str(r.get("server_image_ref") or "")
                m = re.search(r":(\d+\.\d+\.\d+[^@\s]*)@sha256:", ref)
                if m:
                    v = m.group(1)
            out.add(v)
        return out

    def med(lane, scale, wl, be, field):
        rs = _sel(lane, scale, wl, be)
        g = [r[field] for r in rs if isinstance(r.get(field), (int, float))]
        return st.median(g) if g else None

    def line_of(lane, scale, wl, be):
        return _line(_sel(lane, scale, wl, be))

    # EVERY BAR IS AN F5 CLAIM. Each one divides a server measurement by an
    # embedded one and calls the quotient a transport cost, which is only true
    # if both halves ran the same engine. Nothing checked that, and the sparse
    # bar was wrong because of it: runs.jsonl still held the PRE-FIX embedded
    # cliff (165 ms, the number the paper's own sparse subsection says was
    # fixed to 11.3) beside a re-measured 26.8.1 server at 13.3, so the bar
    # showed the server twelve times FASTER than embedded. A reader would have
    # taken that as a finding. It was two engine lines in one division.
    #
    # Sparse embedded now comes from the same released artifacts T4 reads;
    # the server half is already on the release in runs.jsonl.
    _sparse_emb = None
    try:
        import make_paper_tables as _T
        _g = _T._sparse_2681_rows().get("small") or []
        _v = [r["query_p50_ms"] for r in _g
              if isinstance(r.get("query_p50_ms"), (int, float))]
        _sparse_emb = st.median(_v) if _v else None
    except SystemExit:
        _sparse_emb = None

    pairs = [
        ("OLTP\nthroughput", med("l1", "medium", "oltp", "arcadedb_embedded", "oltp_ops_per_s"),
         med("l1", "medium", "oltp", "arcadedb_server", "oltp_ops_per_s"), True),
        ("Insert\np99", med("l1", "medium", "oltp", "arcadedb_embedded", "insert_p99_ms"),
         med("l1", "medium", "oltp", "arcadedb_server", "insert_p99_ms"), False),
        ("Graph\n1-hop p50", med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"),
         med("l2", "sf10", "oltp", "arcadedb_graph_server", "hop1_p50_ms"), False),
        ("Sparse\np50", _sparse_emb,
         med("l3s", "small", "search", "arcadedb_sparse_server", "query_p50_ms"), False),
        # Dense comes from the same overlays T5 uses, NOT from runs.jsonl.
        # runs.jsonl still holds the pre-#5412 dense numbers (embedded 5.45 ms,
        # server 6.82 ms at the 24g heap, and it mixes in the 16g int8 runs on
        # top of that), so reading it here plotted a 1.25x transport ratio while
        # the prose two pages earlier said 2.25x from the post-fix warm-cache
        # measurement. A figure that predates the paper's headline vector fix
        # is worse than no figure.
        ("Dense\np50", _dense_overlay_p50(), _dense_overlay_p50(srv=True), False),
        ("TPC-H Q1", med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "q1_ms"),
         med("l1tpc", "tpch1", "olap", "arcadedb_server", "q1_ms"), False),
    ]
    # F5, mechanised. Both halves of a bar must name the same release, and the
    # bars must agree with each other, or this refuses to draw rather than
    # drawing a version comparison labelled as a deployment cost. Bars whose
    # source is an artifact directory rather than runs.jsonl are checked by the
    # directory being single-version, which _sparse_2681_rows and
    # _dense_multipass already enforce at their own boundary.
    checked = {
        "OLTP\nthroughput": (line_of("l1", "medium", "oltp", "arcadedb_embedded"),
                             line_of("l1", "medium", "oltp", "arcadedb_server")),
        "Insert\np99": (line_of("l1", "medium", "oltp", "arcadedb_embedded"),
                        line_of("l1", "medium", "oltp", "arcadedb_server")),
        "Graph\n1-hop p50": (line_of("l2", "sf10", "oltp", "arcadedb_graph_embedded"),
                             line_of("l2", "sf10", "oltp", "arcadedb_graph_server")),
        "Sparse\np50": ({"26.8.1"},
                        line_of("l3s", "small", "search", "arcadedb_sparse_server")),
        "TPC-H Q1": (line_of("l1tpc", "tpch1", "olap", "arcadedb_embedded"),
                     line_of("l1tpc", "tpch1", "olap", "arcadedb_server")),
    }
    bad, seen = [], set()
    for label, (a, b) in checked.items():
        both = (a | b) - {"?", "server", ""}
        seen |= both
        if len(both) > 1:
            bad.append(f"  {label.replace(chr(10), ' ')}: embedded={sorted(a)} server={sorted(b)}")
    if bad:
        raise SystemExit("f8 would divide across engine lines (F5):\n"
                         + "\n".join(bad)
                         + "\nEvery bar must be one release on both sides.")
    if len(seen) > 1:
        raise SystemExit(f"f8 bars span more than one release: {sorted(seen)}. "
                         "The figure compares deployments, so the release must "
                         "be constant across it.")
    print(f"  f8: all bars on one engine line ({sorted(seen)[0] if seen else '?'})")

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

    import glob as _glob
    # Same precedence as the table's native-TS row, and for the reason its
    # comment gives: the batch1 rows went through the adapter's per-element
    # conversion, so they price OUR adapter, not the engine. The table moved
    # to the dev21 primitive-batch arm; this figure did not, and so plotted
    # 411k pts/s against the table's 1.73M and a 12h aggregation of 14.9 ms
    # against the table's 29.6. Both bars wrong, in opposite directions.
    # IT HAPPENED AGAIN, twice more. The table moved to ts59 while this figure
    # still read dev21_ts, and then the table moved to ts_2681 (the released
    # re-measure) while the fallback chain below still listed the two
    # pre-release rungs.
    #
    # THE FALLBACKS ARE GONE, not reordered. Every one of these desyncs had the
    # same shape: a cascade whose job was to find SOMETHING to plot, which is
    # exactly the behaviour that lets a figure disagree with its own table
    # without failing. One released source, or nothing.
    _native = [json.load(open(fp)) for fp in
               _glob.glob(os.path.join(RESULTS, "ts_2681", "nosettle_r*.json"))]

    def _ts_native_med(f):
        v = [r[f] for r in _native if isinstance(r.get(f), (int, float))]
        return st.median(v) if v else None

    entries = [  # (label, arcade value, best specialist value, higher_better)
        ("Cross-model txn p50", med("e2", "e2", "hybrid", "arcadedb_e2", "hybrid_p50_ms"),
         med("e2", "e2", "hybrid", "composed_qdrant_neo4j", "hybrid_p50_ms"), False),
        ("OLTP ops/s", med("l1", "medium", "oltp", "arcadedb_embedded", "oltp_ops_per_s"),
         med("l1", "medium", "oltp", "postgres", "oltp_ops_per_s"), True),
        ("Graph 1-hop p50", med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"),
         med("l2", "sf10", "oltp", "ladybug_graph", "hop1_p50_ms"), False),
        ("TS 12h agg p50", _ts_native_med("q_global_ms"),
         tsmed("questdb", "q_global_ms"), False),
        ("Sparse 100k p50", _sparse_overlay_p50("tiny"),
         med("l3s", "tiny", "search", "qdrant_sparse", "query_p50_ms"), False),
        # ArcadeDB's side from the overlay T5 uses (post-#5412); Qdrant has no
        # overlay and its runs.jsonl row is current, so it stays as it is.
        ("Dense 10M p50", _dense_overlay_p50(),
         med("l3d", "deep10m", "search", "qdrant_dense", "query_p50_ms"), False),
        ("Sparse 1M p50", _sparse_overlay_p50("small"),
         med("l3s", "small", "search", "qdrant_sparse", "query_p50_ms"), False),
        ("TS ingest pts/s", _ts_native_med("ingest_pts_per_s"),
         tsmed("duckdb", "ingest_pts_per_s"), True),
        ("TPC-H Q1", med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "q1_ms"),
         med("l1tpc", "tpch1", "olap", "duckdb", "q1_ms"), False),
    ]
    _check_f4_against_tables(entries)

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
    # fontsize=7 is load-bearing, not taste. At the default size this label is
    # WIDER THAN THE 3.45in FIGURE, so matplotlib clipped it at the canvas edge
    # and the saved PDF carried the truncated string "...log sca". tight_layout
    # cannot rescue it: that shrinks the axes to fit decorations inside the
    # figure, and nothing can fit a label longer than the figure itself. The
    # gs crop then measured the ink it was given and reported success.
    ax.set_xlabel("ArcadeDB (embedded) vs best specialist, log scale",
                  fontsize=7)
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
        # ArcadeDB ran DEEP-10M at two pinned heaps (16g and 24g) and every
        # comparator ran at one. Taking a plain median over both put the
        # ArcadeDB bars at 24.3 GiB, the midpoint of a ~28.4 GiB cluster and a
        # ~20.3 GiB one, which is neither operating point and is 4 GiB below
        # the 24 GiB configuration the caption says the bars track. It also
        # flattered us, which is the direction that matters. Pin the ArcadeDB
        # bars to the 24 GiB heap the caption claims and the dense table uses.
        want_heap = "24g" if be.startswith("arcadedb") else None
        g = [r["peak_anon_mib_sum"] / 1024 for r in rows
             if r["lane"] == "l3d" and r["scale"] == "deep10m"
             and r["backend"] == be
             and (want_heap is None or r.get("heap") == want_heap)
             and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
        if g:
            labels.append(label)
            vals.append(st.median(g))
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.bar(range(len(vals)), vals, width=0.6, color="C0", alpha=0.85)
    # A LEGEND, not an annotation. Every bar here exceeds the 3.84 GiB line,
    # so there is no clear space adjacent to it: at y=4.1 the dotted rule ran
    # through the glyphs, and lifting it to y=5.0 moved it inside the
    # sqlite-vec bar. Hand-placed coordinates cannot be right for a series
    # whose heights come from data. Let matplotlib find the empty corner.
    ax.axhline(3.84, color="C2", lw=1, ls=":", label="raw vectors 3.8 GiB")
    ax.legend(fontsize=6, loc="upper right", framealpha=0.9,
              handlelength=1.6, borderpad=0.3)
    # "#" not "\\#": these are matplotlib strings, not LaTeX. The escape a
    # .tex file needs renders here as a literal backslash, and the figure
    # shipped reading "(\#3144)".
    ax.annotate("build OOMs at 16 GiB heap;\nneeds 19+ (#3144)",
                (0.4, 17.5), fontsize=6.5, color="C3")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6, rotation=20, ha="right")
    ax.set_ylabel("peak anon (GiB)")
    fig.tight_layout()
    path = os.path.join(FIGS, "f6_memory_ceiling.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)


def main():
    # See make_paper_tables._require_paper_dir: writing into the unset-variable
    # default creates a phantom paper directory that later reads treat as real.
    if not os.path.isdir(_PAPER_DIR):
        raise SystemExit(
            f"BENCH_PAPER_DIR unset or wrong: {os.path.normpath(_PAPER_DIR)} "
            "does not exist.\nSet it to the directory holding paper.tex.")
    os.makedirs(FIGS, exist_ok=True)
    rows = canonical()
    f3_sparse_perquery()
    f4_one_vs_n(rows)
    f5_sparse_scaling(rows)
    f6_memory_ceiling(rows)
    f7_e2(rows)
    f8_deployment(rows)


if __name__ == "__main__":
    main()
