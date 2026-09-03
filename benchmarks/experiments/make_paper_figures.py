#!/usr/bin/env python3
r"""Generate the paper's figures from results/.

PDFs land in $BENCH_PAPER_DIR/figures and are margin-cropped with the two-pass
Ghostscript recipe (verify with pdfinfo; a silent crop failure must not pass).

That directory is OUTPUT, not a manifest. What the paper shows is whatever the
.tex files \includegraphics, and the two drifted apart once already: this
docstring itself still advertised F5 after the paper deleted it. See
_check_no_orphan_figures, which now refuses to let that happen quietly.
"""
import json
import os
import re
import statistics as st
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

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


# Figures that intentionally exist without a paper including them, each with
# the reason. Deliberately empty: earn a line here, do not assume one.
WEB_ONLY_FIGURES = {}


def _check_no_orphan_figures():
    """Fail if a figure is generated that no paper includes.

    f5_sparse_scaling was DELETED FROM THE PAPER in 366f4c1 as a superseded
    pre-MaxScore figure once the 8.84M tier landed and T4 was restructured.
    Nobody deleted the function, so it kept writing a PDF into figures/, and
    that directory was later read as if it were the manifest of "the paper's
    figures". It was not. It is output. The .tex files are the manifest.

    The orphan then rotted unobserved, because the four figures a paper
    includes get re-read every time the paper is read and this one never was:
    it drew ArcadeDB's real 8.84M measurement, labelled it a synthetic corpus,
    and put it at 1e7. That shipped to a public page.

    So: every PDF in figures/ must be cited by some .tex, or be listed in
    WEB_ONLY_FIGURES with a reason. Same shape as f3's refuse-to-draw guard.
    """
    used = set()
    for name in sorted(os.listdir(_PAPER_DIR)):
        if not name.endswith(".tex"):
            continue
        with open(os.path.join(_PAPER_DIR, name), encoding="utf-8") as fh:
            body = fh.read()
        for stem in re.findall(r"\\includegraphics[^{]*\{figures/([^}]+)\}", body):
            used.add(os.path.basename(stem).removesuffix(".pdf"))
    orphans = sorted(
        f.removesuffix(".pdf") for f in os.listdir(FIGS)
        if f.endswith(".pdf")
        and f.removesuffix(".pdf") not in used
        and f.removesuffix(".pdf") not in WEB_ONLY_FIGURES)
    if orphans:
        raise SystemExit(
            "figures generated that no paper includes: " + ", ".join(orphans)
            + "\n  A figure no paper renders is a figure nobody proofreads."
            "\n  Either cite it from a .tex, delete it and its generator "
            "function, or add it to WEB_ONLY_FIGURES with the reason.")
    print(f"figures: {len(used)} generated, all cited by a paper")


# Strings that must survive into the saved PDF. Keep these to labels that
# have actually been at risk or that carry meaning a reader needs.
EXPECT_IN_PDF = {
    "f4_one_vs_n.pdf": ["log scale", "best specialist at equal recall",
                        "unitless ratio", "warm"],
    "f6_memory_ceiling.pdf": ["(#3144)", "raw vectors"],
    "f8_deployment.pdf": ["server cost / embedded"],
    "f7_e2_hybrid.pdf": ["hybrid op p50 (ms)"],
    "f3_sparse_perquery.pdf": ["decile median"],
}


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


def fit_ylim_to_annotations(fig, ax, anns, pad=1.03, iters=8):
    """Raise the y-axis top to just clear the annotations, and no further.

    f7 carried a hand-set ax.set_ylim(0, 30) against a 19.4 ms tallest bar,
    leaving about a tenth of the panel blank. The limit cannot simply be
    max(bar): the outcome labels sit a fixed 10 POINTS above each bar, so
    shrinking the axis raises the bar top in display space and carries the
    label with it. Solve it as the fixed point it is.

    It converges because the offset is a constant fraction of the axes height:
    each pass multiplies the overshoot by (10pt + text height) / axes height,
    well under 1 here, so a few passes settle it. Call AFTER tight_layout, so
    the axes height being solved against is the final one.
    """
    for _ in range(iters):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        inv = ax.transData.inverted()
        top = max(inv.transform((0, a.get_window_extent(renderer).ymax))[1]
                  for a in anns)
        current = ax.get_ylim()[1]
        want = top * pad
        if abs(want - current) <= 0.005 * current:
            return
        ax.set_ylim(0, want)
    raise SystemExit(
        "f7: y-limit did not converge. An annotation is probably tall enough "
        "relative to the axes that shrinking the limit outruns the fit; set a "
        "limit by hand and say why.")


def f7_e2(rows):
    e2 = [r for r in rows if r["lane"] == "e2"]
    order = [("arcadedb_e2", "ArcadeDB\n(one txn)"),
             ("surrealdb_e2", "SurrealDB\n(one txn)"),
             ("composed_qdrant_neo4j", "Qdrant+Neo4j\n(composed)")]
    fig, ax = plt.subplots(figsize=(3.45, 2.0))
    anns = []
    for i, (be, label) in enumerate(order):
        h = [r["hybrid_p50_ms"] for r in e2
             if r["backend"] == be and r["workload"] == "hybrid"]
        a = [r.get("torn_state") for r in e2
             if r["backend"] == be and r["workload"] == "atomicity"]
        torn = sum(bool(t) for t in a)
        med = st.median(h)
        ax.bar(i, med, width=0.55, color="C3" if torn else "C0", alpha=0.85)
        ax.errorbar(i, med, yerr=[[med - min(h)], [max(h) - med]], color="k",
                    capsize=3, lw=1)
        # The label must not read the same way on a pass and on a failure.
        # It used to say "torn state 5/5 crashes" and "atomic 5/5 crashes",
        # so the identical "5/5" meant FAILED on one bar and PASSED on the
        # next, distinguished only by the small word above it -- readers
        # consistently took every bar as a failure count. Two fixes: say what
        # happened in words that carry their own valence, and never print the
        # same fraction for opposite outcomes. "crashes" is also wrong: the
        # injection raises an error inside the operation, it does not kill
        # anything, and the real kill -9 test is a different experiment.
        n = len(a)
        outcome = (f"left half-updated\nin {torn} of {n}" if torn
                   else f"undone cleanly\nall {n}")
        anns.append(ax.annotate(outcome, (i, med), textcoords="offset points",
                                xytext=(0, 10), ha="center", fontsize=6.5))
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([l for _, l in order], fontsize=7)
    ax.set_ylabel("hybrid op p50 (ms)")
    ax.set_ylim(bottom=0)
    # Fitting the limit shrank the range enough that matplotlib dropped to
    # ticks every 10, coarser than the 0..30-by-5 the hand-set limit produced.
    # Ask for the old density back without hardcoding a spacing that a
    # re-measure would invalidate.
    ax.yaxis.set_major_locator(
        mticker.MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    fig.tight_layout()
    fit_ylim_to_annotations(fig, ax, anns)
    path = os.path.join(FIGS, "f7_e2_hybrid.pdf")
    fig.savefig(path)
    plt.close(fig)
    gs_crop(path)



def _dense_overlay_recall(arm="fp32"):
    """recall@10 for one overlay arm, pooled over every warm pass.

    Recall is a property of the index and the query set, not of the pass, so it
    is read from the timed passes without a cold/warm split. Cold pass 0 does
    not record it on every arm, which is the only reason this reads 1: onward.
    """
    import make_paper_tables as _T

    root = os.path.join(_T.RESULTS, "dense_mp5_2681")
    vals = []
    for h in sorted(_glob_json(root, f"mp_{arm}_b*.json")):
        with open(h, encoding="utf-8") as fh:
            for p in json.load(fh)[1:]:
                v = p.get("recall_at_10")
                if isinstance(v, (int, float)):
                    vals.append(v)
    return st.median(vals) if vals else None


def _glob_json(root, pattern):
    import glob as _glob
    return _glob.glob(os.path.join(root, pattern))


def _dense_overlay_p50(srv=False, arm="fp32", warm=True):
    """Dense p50 from the SAME artifacts the tables read, for ANY engine.

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

    WARM VS COLD IS A CLAIM, never a convenience, and the caller must choose.
    The two are different quantities and averaging across the boundary plots
    neither, which is why the cold pass has its own column in T5.

    THE DEFAULT IS WARM AND THAT IS ONLY SAFE WHEN BOTH SIDES USE IT. f4 called
    this for ArcadeDB and read Qdrant from runs.jsonl, a single timed pass, so
    the published bar was our steady state against their first pass. Every
    comparator is within 3% of itself across that boundary and ArcadeDB is
    9.27x, so the mismatch was worth the entire result: 0.15x becomes 1.35x.
    Whenever a figure compares engines, pass warm= explicitly on both sides and
    let _check_f4_protocol prove they match.
    """
    import glob as _glob
    import json as _json
    import make_paper_tables as _T
    # Five independent builds, so warm pools every warm pass of every build
    # (5 x 4 = 20) rather than the four passes of one build, and cold pools the
    # five first passes. Same quantity, more support, no mixing.
    #
    # `arm` names ANY engine in the matched overlay, not just ours.
    # dense_multipass_driver.py put every comparator through the identical
    # build-then-five-passes protocol for exactly this reason, so a comparator
    # read from anywhere else is a different experiment wearing the same axis.
    name = f"mp_{'arcsrv' if srv else arm}_b*.json"
    hits = sorted(_glob.glob(os.path.join(_T.RESULTS, "dense_mp5_2681", name)))
    if not hits:
        return None
    vals = []
    for h in hits:
        passes = _json.load(open(h))
        vals += [p["p50"] for p in (passes[1:] if warm else passes[:1])
                 if isinstance(p.get("p50"), (int, float))]
    return st.median(vals) if vals else None


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
    # T5's dense half is System & Build & Cold p50 & Warm p50 & Cold p99 &
    # Recall, so column 1 is COLD p50 and column 2 is warm. This pointed at
    # warm while the bar's comparator was a cold single pass; the figure now
    # plots cold on both sides, so it pins to the cold column. See the entry's
    # comment for why cold is the defensible choice here.
    "Dense 10M p50":   ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 1),
    "TS 12h agg p50":  ("t5_dense_ts.tex", "ArcadeDB (native TS)", 3),
}


def _check_f4_comparators(entries):
    """On the vector rows, is the plotted engine really the best ELIGIBLE one?

    "Best specialist" is ambiguous exactly where it matters. At DEEP-10M the
    fastest engine outright is Chroma at 0.700 ms, but it returns 93.4% of the
    true neighbours against our 95.1%, so dividing by it would compare us to
    something searching less thoroughly. The rule the figure actually uses is
    the fastest engine whose recall is at least ours, which is Qdrant at 1.342.
    Both readings are defensible; publishing one and labelling it the other is
    not, and until the page published this tier a reader could not tell.

    So the rule is now checked rather than asserted in a caption. Milvus and
    sqlite-vec also clear the recall bar and are slower; Chroma, LanceDB and
    DuckDB-VSS are faster and do not clear it.

    Vector rows only. Elsewhere there is no quality axis, so "best" is just
    fastest and needs no rule.
    """
    ours_recall = _dense_overlay_recall()
    if ours_recall is None:
        raise SystemExit("f4: no recall for our dense arm; eligibility unknown")
    got = dict((e[0], (e[1], e[2])) for e in entries)
    arcade, spec = got["Dense 10M p50"]
    eligible = []
    for a in ("qdrant", "chroma", "lancedb", "duckvss", "milvus", "sqlitevec"):
        p50 = _dense_overlay_p50(warm=False, arm=a)
        rec = _dense_overlay_recall(arm=a)
        if p50 is None or rec is None:
            continue
        if rec >= ours_recall - 1e-9:
            eligible.append((p50, a, rec))
    if not eligible:
        raise SystemExit(
            f"f4 dense: no comparator reaches our recall ({ours_recall:.4f}), "
            "so 'best specialist at equal recall' names nothing. Either the "
            "label or the row has to change.")
    best_p50, best_arm, best_rec = min(eligible)
    if abs(spec - best_p50) > 1e-9:
        faster = [(p, a) for p, a, _ in
                  [(x[0], x[1], x[2]) for x in eligible] if p < spec]
        raise SystemExit(
            f"f4 dense plots {spec:.3f} ms but the fastest engine at recall "
            f">= ours ({ours_recall:.4f}) is {best_arm} at {best_p50:.3f} ms "
            f"(recall {best_rec:.4f}).\n"
            f"  The axis says 'best specialist at equal recall'. Make it true "
            f"or change the axis. {faster}")
    print(f"    dense comparator {best_arm} is fastest at recall >= "
          f"{ours_recall:.4f} ({best_p50:.3f} ms, recall {best_rec:.4f})")


def _check_f4_protocol(entries):
    """Assert f4's dense bar reads BOTH engines at the same pass.

    _check_f4_against_tables compares each bar to its table cell, which is a
    real check and did not catch this one: the bar and T5's warm column agreed
    perfectly, because both were ArcadeDB's warm number. The comparator was the
    thing measured differently, and nothing looked at it.

    What shipped: our warm p50 (0.956, passes 1-4 of the matched overlay) beside
    Qdrant's runs.jsonl row (1.295, a single timed pass). 1.35x ahead. Matched
    at either end it is 1.37x warm or 0.15x cold, so the mismatch was worth the
    whole finding, and in the direction that flattered us.

    Both values must therefore be reproducible from dense_mp5_2681 at ONE pass
    selection. A comparator taken from anywhere else, or read at a different
    pass, fails here rather than becoming a bar.
    """
    got = dict((e[0], (e[1], e[2])) for e in entries)
    if "Dense 10M p50" not in got:
        raise SystemExit("f4 lost its dense entry; the protocol check is blind")
    arcade, spec = got["Dense 10M p50"]
    for warm in (False, True):
        ours = _dense_overlay_p50(warm=warm)
        if ours is None or abs(arcade - ours) > 1e-9:
            continue
        arms = ["qdrant", "chroma", "lancedb", "duckvss", "milvus", "sqlitevec"]
        for a in arms:
            v = _dense_overlay_p50(warm=warm, arm=a)
            if v is not None and abs(spec - v) <= 1e-9:
                print(f"    dense protocol   both sides {'warm' if warm else 'cold'}"
                      f", overlay arm '{a}' ({arcade:.3f} vs {spec:.3f})")
                return
        raise SystemExit(
            f"f4 dense: ArcadeDB is the overlay's "
            f"{'warm' if warm else 'cold'} p50 ({arcade:.3f}) but the "
            f"comparator ({spec:.3f}) matches no overlay arm at that pass.\n"
            "  That is our steady state against somebody else's first pass. "
            "Read both from _dense_overlay_p50 with the same warm=.")
    raise SystemExit(
        f"f4 dense: ArcadeDB's value {arcade:.3f} is neither the overlay's "
        "cold nor its warm median, so the pass it represents is unknown.")


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
            # ONE PIN, TWO VERSION STRINGS. At 8d6af9475 the embedded wheel
            # stamps "26.9.1.dev0" and the server jar "26.9.1-SNAPSHOT", and
            # the string compare below refused f8 across a pair that IS the
            # same engine. engine_commit is the identity (PAGE-SPEC section 1);
            # the version string is only the fallback for rows that predate it.
            rc = str(r.get("engine_commit") or "").strip().lower()
            if rc and rc != "none":
                out.add(rc[:9])
                continue
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
        # warm= spelled out on both sides. Warm is right HERE, unlike in f4:
        # this is one engine against itself across the process boundary, so the
        # pass cancels and what is left is the transport fee. The paper's prose
        # says "0.96 vs 2.10 ms warm" for exactly this pair.
        ("Dense\np50", _dense_overlay_p50(warm=True),
         _dense_overlay_p50(warm=True, srv=True), False),
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
        # SurrealDB, NOT the composed Qdrant+Neo4j stack. The composed stack is
        # 19.43 ms and SurrealDB 7.06, so plotting the stack claimed 10x where
        # the strongest comparator gives 3.8x. Both engines are in the e2 table
        # the page publishes, side by side, so the overstatement was one glance
        # from being caught.
        #
        # The composed stack exists in that lane to show ATOMICITY, not to be a
        # speed baseline: it has no transaction spanning both engines, which is
        # the lane's own stated point. SurrealDB is the engine that does what we
        # do, one transaction across models, and it is faster than the stack.
        # Beating the non-transactional option by 10x is not the claim; beating
        # the transactional rival by 3.8x is, and it is the stronger one.
        ("Cross-model txn p50", med("e2", "e2", "hybrid", "arcadedb_e2", "hybrid_p50_ms"),
         med("e2", "e2", "hybrid", "surrealdb_e2", "hybrid_p50_ms"), False),
        ("OLTP ops/s", med("l1", "medium", "oltp", "arcadedb_embedded", "oltp_ops_per_s"),
         med("l1", "medium", "oltp", "postgres", "oltp_ops_per_s"), True),
        ("Graph 1-hop p50", med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"),
         med("l2", "sf10", "oltp", "ladybug_graph", "hop1_p50_ms"), False),
        ("TS 12h agg p50", _ts_native_med("q_global_ms"),
         tsmed("questdb", "q_global_ms"), False),
        ("Sparse 100k p50", _sparse_overlay_p50("tiny"),
         med("l3s", "tiny", "search", "qdrant_sparse", "query_p50_ms"), False),
        # BOTH SIDES COLD, BOTH FROM THE SAME OVERLAY. This bar used to plot
        # our WARM p50 against Qdrant's runs.jsonl row, which is a single timed
        # pass, i.e. cold. That is task #117's defect: it was fixed in T5, which
        # grew separate Cold and Warm columns, and never fixed here.
        #
        # The comment this replaces said "Qdrant has no overlay". It does:
        # dense_mp5_2681/mp_qdrant_b*.json, five builds, twenty passes, written
        # by dense_multipass_driver.py, whose whole purpose was to give the
        # comparators the multi-pass protocol our rows already had.
        #
        # COLD, not warm, and the reason is that the choice only moves OUR bar:
        #
        #     engine       cold    warm    gain
        #     Qdrant       1.342   1.312   1.02x
        #     Chroma       0.700   0.708   0.99x
        #     LanceDB      3.199   3.154   1.01x
        #     DuckDB-VSS   2.586   2.551   1.01x
        #     ArcadeDB     8.869   0.956   9.27x
        #
        # Every comparator is within 3% of itself, so selecting warm costs them
        # nothing and hands us the entire result: cold/cold is 0.15x, warm/warm
        # is 1.37x. When a knob is free for everyone else and decisive for us,
        # the only defensible setting is the one that does not flatter us.
        # It also matches the rest of this figure, where every other bar is a
        # first-timed-pass number, and T5, which sorts its dense half by cold.
        #
        # The 9.27x itself is a real and interesting property (ArcadeDB pages
        # its index off disk and the comparators are resident from build), so
        # it belongs in the prose, not inside a bar that reads as a like-for-
        # like comparison.
        ("Dense 10M p50", _dense_overlay_p50(warm=False),
         _dense_overlay_p50(warm=False, arm="qdrant"), False),
        ("Sparse 1M p50", _sparse_overlay_p50("small"),
         med("l3s", "small", "search", "qdrant_sparse", "query_p50_ms"), False),
        ("TS ingest pts/s", _ts_native_med("ingest_pts_per_s"),
         tsmed("duckdb", "ingest_pts_per_s"), True),
        ("TPC-H Q1", med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "q1_ms"),
         med("l1tpc", "tpch1", "olap", "duckdb", "q1_ms"), False),
    ]
    # DISPLAY ORDER IS A DECISION, so it is written down rather than inherited
    # from the order someone happened to append tuples in. That order had two
    # faults:
    #
    #   Sparse 100k, Dense 10M, Sparse 1M   the two sparse tiers were split by
    #                                       the dense row, and the two
    #                                       time-series rows sat 4 apart
    #   the three blue bars came first      wins at the top, losses below, which
    #                                       is a flattering arrangement nobody
    #                                       chose but everybody would notice
    #
    # Grouped by model instead: cross-model first because it is the claim the
    # paper is about, then tabular, graph, time series, vector. Within a group,
    # write before read and small before large. That interleaves the colours,
    # which is the honest consequence: this engine wins some rows and loses
    # others, and sorting so the wins arrive first is a thumb on the scale.
    F4_ROW_ORDER = [
        "Cross-model txn p50",
        "OLTP ops/s", "TPC-H Q1",
        "Graph 1-hop p50",
        "TS ingest pts/s", "TS 12h agg p50",
        "Sparse 100k p50", "Sparse 1M p50", "Dense 10M p50",
    ]
    unordered = [e[0] for e in entries if e[0] not in F4_ROW_ORDER]
    if unordered:
        raise SystemExit(
            f"f4: {unordered} have no place in F4_ROW_ORDER. A new row has to "
            "be given one, so that adding a bar is a decision about where it "
            "belongs rather than an append to the end.")
    entries.sort(key=lambda e: F4_ROW_ORDER.index(e[0]))

    _check_f4_protocol(entries)
    _check_f4_comparators(entries)
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
    dense_i = labels.index("Dense 10M p50") if "Dense 10M p50" in labels else -1
    for i, (y, r) in enumerate(zip(ys, ratios)):
        text = f"{r:.3g}x" if r < 1 else f"{r:.2g}x"
        if i == dense_i:
            # INSIDE the bar for this row only. Its warm marker sits at 1.37
            # and the outside label runs right from 0.151, so on a log axis the
            # two overlap and the figure reads "0.151x" with a diamond through
            # it. The bar is wide enough to hold the number, and moving it left
            # leaves the whole right side to the pass comparison, which is the
            # thing this row exists to show.
            ax.annotate(text, (r, y), textcoords="offset points",
                        xytext=(-3, -2), fontsize=6.5, ha="right",
                        color="white")
        else:
            ax.annotate(text, (max(r, 0.002), y), textcoords="offset points",
                        xytext=(3, -2), fontsize=6.5)
    # SHOW BOTH PASSES ON THE DENSE ROW instead of picking one and arguing for
    # it in a caption. Choosing cold was defensible and still required a reader
    # to take our word that warm would have flattered us; drawing both makes the
    # claim self-evident and costs one marker. The bar stays cold, because that
    # is the pass every other row is measured at and a bar is what gets compared
    # across rows, and the diamond marks the same comparison in steady state.
    #
    # Only this row can have it. Every other lane times a single pass, so there
    # is no warm number to mark and inventing one would be worse than the gap.
    warm_a = _dense_overlay_p50(warm=True)
    warm_s = _dense_overlay_p50(warm=True, arm="qdrant")
    if warm_a and warm_s and "Dense 10M p50" in labels:
        yw = list(ys)[labels.index("Dense 10M p50")]
        r_cold = ratios[labels.index("Dense 10M p50")]
        r_warm = warm_s / warm_a
        ax.plot([r_cold, r_warm], [yw, yw], ls=":", lw=0.7, color="0.25",
                zorder=4)
        ax.plot([r_warm], [yw], marker="D", ms=3.2, color="C0", zorder=5)
        ax.annotate(f"{r_warm:.2g}x warm", (r_warm, yw),
                    textcoords="offset points", xytext=(4, 2), fontsize=6,
                    color="C0")
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
    # "at equal recall" is load-bearing, not decoration. Chroma answers the
    # dense 10M tier in 0.700 ms against our 8.869, which would be 0.0789x, but
    # it returns 93.4% of the true neighbours to our 95.1%. A bare "best
    # specialist" promises the fastest engine outright and this row does not
    # use it, which a reader can now check for themselves because the page
    # publishes the whole tier. Say the rule instead of hoping nobody looks.
    # _check_f4_comparators enforces it; EXPECT_IN_PDF pins the wording.
    # TWO LINES, not a smaller font. The honest label does not fit on one line
    # in 3.45in: at 6.2pt it still clipped and _check_labels_intact caught it,
    # which is the failure that guard exists for. Shrinking further would have
    # made the axis unreadable in print to preserve a layout nobody needs.
    # Each line here is shorter than the 48-character label that fitted at 7pt,
    # so the size stays legible and the text stays whole.
    # The axis named the COMPARISON and never the QUANTITY. A reader saw "16x"
    # and "0.151x" with nothing saying these are ratios, nor which direction is
    # good; the colours and the dashed line encode it and neither is explained
    # inside the figure. Both lines are at or under the 48 characters known to
    # fit at 7pt, which is what the two-line split bought.
    # THE AXIS HAS NO UNIT AND HAD TO SAY SO. Each bar divides two measurements
    # of one quantity, so ms and ops/s both cancel; the unit lives in the ROW
    # label (p50 is milliseconds, ops/s is throughput) and the axis carries a
    # bare ratio. Without that stated, "16x" reads as a number missing its unit.
    #
    # "better", not "faster": the rows mix directions. Latency rows divide
    # theirs by ours and throughput rows divide ours by theirs, precisely so
    # that >1 means ArcadeDB ahead on both, and "faster" is wrong for ops/s.
    #
    # Three lines because two could not hold it under the 48 characters that
    # fit at 7pt, and shrinking the font to protect the layout is what produced
    # the clipped "...log sca" this figure once shipped with.
    ax.set_xlabel("ArcadeDB (embedded) vs best specialist\n"
                  "at equal recall, log scale\n"
                  "unitless ratio of the row's metric; >1 = better",
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
    # The claim this used to carry, "build OOMs at 16 GiB heap; needs 19+",
    # was WITHDRAWN after #5412 made the build cache auto-size: the body text
    # now says twice that both quantizations build inside 16 GiB. A figure
    # contradicting its own paper on the exact axis the figure is about is a
    # credibility problem, not a typo, so this annotates the surviving finding
    # instead: the envelope is set by the heap we pin, not by demand.
    ax.annotate("envelope set by the pinned 24 GiB heap,\nnot by demand (#3144)",
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
    f6_memory_ceiling(rows)
    f7_e2(rows)
    f8_deployment(rows)
    _check_no_orphan_figures()


if __name__ == "__main__":
    main()
