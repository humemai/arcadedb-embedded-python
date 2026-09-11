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
                        "unitless ratio", "first pass", "repeat pass"],
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



def _dense_overlay_recall(arm="fp32", scale="deep10m"):
    """recall@10 for one overlay arm, pooled over every warm pass.

    Recall is a property of the index and the query set, not of the pass, so it
    is read from the timed passes without a cold/warm split. Cold pass 0 does
    not record it on every arm, which is the only reason this reads 1: onward.
    """
    import make_paper_tables as _T

    root = _T.dense_mp_dir() if scale == "deep10m" else _T.dense_mp_small_dir()
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


def _dense_overlay_p50(srv=False, arm="fp32", warm=True, scale="deep10m"):
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
    root = _T.dense_mp_dir() if scale == "deep10m" else _T.dense_mp_small_dir()
    hits = sorted(_glob.glob(os.path.join(root, name)))
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
    # label -> (table, row, col, pass): the figure's value at that pass must
    # equal the table's cell. The TS aggregate cell is the 100-iteration
    # median, a repeat-pass number; every other cell is a first pass.
    "Graph 1-hop p50": ("t3_graph.tex", "ArcadeDB (emb) & SF10", 1, "cold"),
    "Sparse 100k p50": ("sparse", "ArcadeDB (emb, int8)", "100k", "cold"),
    "Sparse 1M p50":   ("sparse", "ArcadeDB (emb, int8)", "1M", "cold"),
    "Dense 10M p50":   ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 1, "cold"),
    "TS 12h agg p50":  ("t5_dense_ts.tex", "ArcadeDB (native TS)", 3, "warm"),
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
    got = {e["label"]: e for e in entries}
    arcade, spec = got["Dense 10M p50"]["cold"]
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
    """Assert f4's dense row reads BOTH engines at the same pass, per panel.

    What once shipped: our warm p50 beside Qdrant's single timed pass, 1.35x
    ahead; matched at either end it is 1.37x warm or 0.15x cold. With two
    panels the rule is simpler and stricter: the first-pass pair must be the
    overlay's cold medians for both arms, and the repeat-pass pair its warm
    medians, or the row does not draw.
    """
    got = {e["label"]: e for e in entries}
    if "Dense 10M p50" not in got:
        raise SystemExit("f4 lost its dense entry; the protocol check is blind")
    e = got["Dense 10M p50"]
    for key, warm in (("cold", False), ("warm", True)):
        pair = e.get(key)
        if not pair:
            raise SystemExit(f"f4 dense: no {key} pair")
        ours = _dense_overlay_p50(warm=warm)
        theirs = _dense_overlay_p50(warm=warm, arm="qdrant")
        if ours is None or theirs is None or abs(pair[0] - ours) > 1e-9 or abs(pair[1] - theirs) > 1e-9:
            raise SystemExit(
                f"f4 dense {key}: ({pair[0]}, {pair[1]}) is not the overlay's "
                f"{key} pair ({ours}, {theirs}); both sides must come from "
                "_dense_overlay_p50 at one pass.")
        print(f"    dense protocol   {key}: both sides from the overlay "
              f"({pair[0]:.3f} vs {pair[1]:.3f})")


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
    for e in entries:
        label = e["label"]
        if label not in F4_VS_TABLE:
            print(f"    {label:20} (no table cell to compare)")
            continue
        tab, row, col, which = F4_VS_TABLE[label]
        arcade = (e.get(which) or (None, None))[0]
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


def _sparse_rows_identity():
    import make_paper_tables as _T
    out = set()
    for r in _T._sparse_2681_rows().get("small") or []:
        rc = str(r.get("engine_commit") or "").strip().lower()
        if rc and rc != "none":
            out.add(rc[:9])
        else:
            out.add(str(r.get("engine_version") or "?").split("(")[0].strip())
    return out


def _sparse_overlay_pass(tier, arm, warm):
    """p50 from the pinned sparse multipass overlay the second-pass table
    reads: results/sparse_mp_<pin>/sp_<arm>_<tier>.json, rep 0 cold, reps
    1.. warm (median). None when the file is absent (100k was not run)."""
    import json as _json
    import make_paper_tables as _T
    pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    if not pin:
        raise SystemExit("BENCH_ENGINE_COMMIT is unset: the sparse overlay is pinned only")
    fp = os.path.join(_T.RESULTS, f"sparse_mp_{pin}", f"sp_{arm}_{tier}.json")
    if not os.path.isfile(fp):
        return None
    passes = _json.load(open(fp, encoding="utf-8"))
    sel = [r for r in passes if (r.get("rep", 0) >= 1) == warm]
    v = [r["query_p50_ms"] for r in sel if isinstance(r.get("query_p50_ms"), (int, float))]
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
        # The embedded half comes from whatever _sparse_2681_rows() resolved
        # (the pinned l3s rows when complete, else the 26.8.1 overlay), so its
        # identity is read off those rows, not asserted.
        "Sparse\np50": (_sparse_rows_identity(),
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


def _dense_best_comparator(warm, scale):
    """The fastest overlay comparator whose recall is at least ours, at one
    scale and pass: (backend token, p50). The rule the axis states."""
    ours = _dense_overlay_recall(scale=scale)
    if ours is None:
        raise SystemExit(f"f4: no recall for our dense arm at {scale}")
    elig = []
    for a in ("qdrant", "chroma", "lancedb", "duckvss", "milvus", "sqlitevec"):
        p50 = _dense_overlay_p50(warm=warm, arm=a, scale=scale)
        rec = _dense_overlay_recall(arm=a, scale=scale)
        if p50 is not None and rec is not None and rec >= ours - 1e-9:
            elig.append((p50, a))
    if not elig:
        raise SystemExit(f"f4 dense {scale}: no comparator reaches our recall {ours:.4f}")
    p50, a = min(elig)
    return a, p50


def f4_one_vs_n(rows):
    """ArcadeDB embedded relative to the best specialist on every published
    metric family, log scale, >1 = ArcadeDB ahead, in two panels: the first
    timed pass and the repeat pass. Rows follow the paper's evaluation order
    (documents, graph, dense, sparse, time series, cross-model). A row with
    one pass only draws in the first panel and says so in the second.

    The comparator is chosen on the first pass (fastest, or highest
    throughput; on vector rows the fastest whose recall is at least ours) and
    the SAME engine is read at the repeat pass, so each row compares one pair
    twice rather than two different winners."""
    def sel(lane, scale, wl, be, gav_on=None):
        out = []
        for r in rows:
            if r["lane"] != lane or r["scale"] != scale or r.get("workload") != wl or r["backend"] != be:
                continue
            if gav_on is not None and be.startswith("arcadedb"):
                is_on = str(r.get("gav")) != "False"
                if is_on != gav_on:
                    continue
            out.append(r)
        return out

    def med(lane, scale, wl, be, f, gav_on=None):
        g = [r[f] for r in sel(lane, scale, wl, be, gav_on) if isinstance(r.get(f), (int, float))]
        return st.median(g) if g else None

    def recall(lane, scale, wl, be):
        return med(lane, scale, wl, be, "recall_at_10")

    ts = [r for r in canonical() if r.get("lane") == "l4"]
    if not any(r.get("backend") == "arcadedb_ts_native" for r in ts):
        raise SystemExit("no arcadedb_ts_native rows at the pin (ts_2681 fallback retired 2026-09-08)")

    def tsmed(be, f):
        v = [r[f] for r in ts if r["backend"] == be and isinstance(r.get(f), (int, float))]
        return st.median(v) if v else None

    chosen = {}

    def row(label, hb, ours_cold, ours_warm, comps, note=""):
        """comps: {backend: (cold, warm, recall)}; ours: (value, recall)."""
        a_c, a_rec = ours_cold
        elig = {b: v for b, v in comps.items() if v[0] is not None
                and (a_rec is None or v[2] is None or v[2] >= a_rec - 1e-9)}
        if a_c is None or not elig:
            raise SystemExit(f"f4 {label}: no first-pass value or no eligible comparator ({comps})")
        best = (max if hb else min)(elig.items(), key=lambda kv: kv[1][0])
        b, (s_c, s_w, _) = best
        chosen[label] = b
        warm = (ours_warm, s_w) if (ours_warm is not None and s_w is not None) else None
        return {"label": label, "hb": hb, "note": note, "comparator": b,
                "cold": (a_c, s_c), "warm": warm}

    def comps_rows(lane, scale, wl, backends, cold_f, warm_f, with_recall=False):
        return {b: (med(lane, scale, wl, b, cold_f),
                    med(lane, scale, wl, b, warm_f) if warm_f else None,
                    recall(lane, scale, wl, b) if with_recall else None)
                for b in backends}

    DOC = ("postgres", "postgres_tuned", "duckdb", "sqlite")
    GRAPH = ("ladybug_graph", "neo4j_graph")
    SPARSE = ("qdrant_sparse", "milvus_sparse", "elasticsearch_sparse")
    TSC = ("questdb", "duckdb", "sqlite")

    def dense_row(label, scale):
        ours_c = _dense_overlay_p50(warm=False, scale=scale)
        ours_w = _dense_overlay_p50(warm=True, scale=scale)
        b, s_c = _dense_best_comparator(False, scale)
        s_w = _dense_overlay_p50(warm=True, arm=b, scale=scale)
        chosen[label] = b
        return {"label": label, "hb": False, "note": "", "comparator": b,
                "cold": (ours_c, s_c), "warm": (ours_w, s_w) if (ours_w and s_w) else None}

    def sparse_row(label, tier, warm_tier):
        ours_c = _sparse_overlay_p50(tier)
        ours_rec = None
        import make_paper_tables as _T
        g = _T._sparse_2681_rows().get(tier) or []
        rv = [r["recall_at_10"] for r in g if isinstance(r.get("recall_at_10"), (int, float))]
        ours_rec = st.median(rv) if rv else None
        ours_w = _sparse_overlay_pass(tier, "arc_int8", warm=True) if warm_tier else None
        comps = {}
        for b in SPARSE:
            tok = {"qdrant_sparse": "qdrant", "milvus_sparse": "milvus", "elasticsearch_sparse": "elastic"}[b]
            comps[b] = (med("l3s", tier, "search", b, "query_p50_ms"),
                        _sparse_overlay_pass(tier, tok, warm=True) if warm_tier else None,
                        recall("l3s", tier, "search", b))
        return row(label, False, (ours_c, ours_rec), ours_w, comps, note="" if warm_tier else "one pass")

    entries = [
        # documents
        # The synthetic 20M-order rows (OLTP ops/s, OLAP total) left the page
        # on 2026-09-11; the figure shows what the page's tables show.
        row("TPC-H Q1", False,
            (med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "cold_q1_ms"), None),
            med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "warm_q1_ms"),
            comps_rows("l1tpc", "tpch1", "olap", DOC, "cold_q1_ms", "warm_q1_ms")),
        row("TPC-H Q6", False,
            (med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "cold_q6_ms"), None),
            med("l1tpc", "tpch1", "olap", "arcadedb_embedded", "warm_q6_ms"),
            comps_rows("l1tpc", "tpch1", "olap", DOC, "cold_q6_ms", "warm_q6_ms")),
        row("TPC-C new-order p50", False,
            (med("l1tpc", "tpch1", "oltp", "arcadedb_embedded", "neworder_p50_ms"), None), None,
            comps_rows("l1tpc", "tpch1", "oltp", DOC, "neworder_p50_ms", None), note="one pass"),
        # graph, SF10
        row("Graph point p50", False,
            (med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "point_p50_ms"), None),
            med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "warm_point_p50_ms"),
            comps_rows("l2", "sf10", "oltp", GRAPH, "point_p50_ms", "warm_point_p50_ms")),
        row("Graph 1-hop p50", False,
            (med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop1_p50_ms"), None),
            med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "warm_hop1_p50_ms"),
            comps_rows("l2", "sf10", "oltp", GRAPH, "hop1_p50_ms", "warm_hop1_p50_ms")),
        row("Graph 2-hop p50", False,
            (med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "hop2_p50_ms"), None),
            med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "warm_hop2_p50_ms"),
            comps_rows("l2", "sf10", "oltp", GRAPH, "hop2_p50_ms", "warm_hop2_p50_ms")),
        row("Graph write p50", False,
            (med("l2", "sf10", "oltp", "arcadedb_graph_embedded", "write_p50_ms"), None), None,
            comps_rows("l2", "sf10", "oltp", GRAPH, "write_p50_ms", None), note="one pass"),
        # graph analytics with the view on (the engine's default arm)
        row("Graph top-degree p50", False,
            (med("l2", "sf10", "olap", "arcadedb_graph_embedded", "cold_top_degree_ms", gav_on=True), None),
            med("l2", "sf10", "olap", "arcadedb_graph_embedded", "top_degree_p50_ms", gav_on=True),
            comps_rows("l2", "sf10", "olap", GRAPH, "cold_top_degree_ms", "top_degree_p50_ms")),
        # dense, both sizes, comparator by the recall rule
        dense_row("Dense 1M p50", "small"),
        dense_row("Dense 10M p50", "deep10m"),
        # sparse, three sizes; 100k has no second-pass run
        sparse_row("Sparse 100k p50", "tiny", warm_tier=False),
        sparse_row("Sparse 1M p50", "small", warm_tier=True),
        sparse_row("Sparse 8.84M p50", "medium", warm_tier=True),
        # time series
        row("TS ingest points/s", True,
            (tsmed("arcadedb_ts_native", "ingest_pts_per_s"), None), None,
            {b: (tsmed(b, "ingest_pts_per_s"), None, None) for b in TSC}, note="one pass"),
        row("TS newest reading p50", False,
            (tsmed("arcadedb_ts_native", "q_last_cold_ms") or tsmed("arcadedb_ts_native", "q_last_ms"), None),
            tsmed("arcadedb_ts_native", "q_last_ms"),
            {b: (tsmed(b, "q_last_cold_ms") or tsmed(b, "q_last_ms"), tsmed(b, "q_last_ms"), None) for b in TSC}),
        row("TS 12h agg p50", False,
            (tsmed("arcadedb_ts_native", "q_global_cold_ms") or tsmed("arcadedb_ts_native", "q_global_ms"), None),
            tsmed("arcadedb_ts_native", "q_global_ms"),
            {b: (tsmed(b, "q_global_cold_ms") or tsmed(b, "q_global_ms"), tsmed(b, "q_global_ms"), None) for b in TSC}),
        # cross-model: SurrealDB, the transactional rival, never the composed
        # stack (which has no transaction spanning its engines and is slower)
        row("Cross-model txn p50", False,
            (med("e2", "e2", "hybrid", "arcadedb_e2", "hybrid_p50_ms"), None), None,
            {"surrealdb_e2": (med("e2", "e2", "hybrid", "surrealdb_e2", "hybrid_p50_ms"), None, None)},
            note="one pass"),
    ]
    # TS first-run fields exist only from qDH on; until then the first panel
    # shows the repeat number for those two rows and says so.
    for e in entries:
        if e["label"].startswith("TS ") and "p50" in e["label"] and tsmed("arcadedb_ts_native", "q_global_cold_ms") is None:
            e["note"] = "first run not recorded"
            e["cold"] = None
    print("  f4 comparators: " + ", ".join(f"{k}={v}" for k, v in chosen.items()))
    _check_f4_protocol(entries)
    _check_f4_comparators(entries)
    _check_f4_against_tables(entries)

    def ratio(e, key):
        pr = e.get(key)
        if not pr:
            return None
        a, s_ = pr
        return (a / s_) if e["hb"] else (s_ / a)

    labels = [e["label"] for e in entries]
    n = len(entries)
    ys = list(range(n))[::-1]
    fig, (axc, axw) = plt.subplots(1, 2, sharey=True, figsize=(6.0, 0.21 * n + 0.9),
                                   gridspec_kw={"wspace": 0.06})
    for ax, key, title in ((axc, "cold", "first pass"), (axw, "warm", "repeat pass")):
        for e, y in zip(entries, ys):
            r = ratio(e, key)
            if r is None:
                ax.annotate(e["note"] or "n/a", (1.0, y), fontsize=5.2,
                            color="0.45", ha="center", va="center", style="italic")
                continue
            ax.barh(y, r, color="C0" if r >= 1 else "C3", alpha=0.85, height=0.62)
            text = f"{r:.3g}x" if r < 1 else f"{r:.2g}x"
            ax.annotate(text, (max(r, 0.002), y), textcoords="offset points",
                        xytext=(2.5, -2), fontsize=5.6)
        ax.axvline(1.0, color="k", lw=0.8, ls="--")
        ax.set_xscale("log")
        ax.set_xlim(5e-4, 60)
        ax.set_title(title, fontsize=7, pad=3)
        ax.tick_params(axis="x", labelsize=6)
    # thin separators between the model groups, in the paper's order
    for k in (3, 8, 10, 13, 16):
        for ax in (axc, axw):
            ax.axhline(n - k - 0.5, color="0.85", lw=0.5, zorder=0)
    axc.set_yticks(ys)
    axc.set_yticklabels(labels, fontsize=6.2)
    fig.supxlabel("ArcadeDB (embedded) vs best specialist at equal recall, log scale\n"
                  "unitless ratio of the row's metric; >1 = better",
                  fontsize=6.5)
    # Explicit margins: tight_layout did not reserve room for the row labels
    # beside two shared-y panels and the left column clipped (2026-09-11).
    fig.subplots_adjust(left=0.20, right=0.985, top=0.95, bottom=0.13)
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
