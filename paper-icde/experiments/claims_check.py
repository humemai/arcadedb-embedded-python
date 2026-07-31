#!/usr/bin/env python3
"""Check every numeric claim in the paper's prose against the data behind it.

The plan's own verification criterion is "every number in prose traces to a
results file". Running that by hand on 2026-07-30 found two real defects, and
also produced THREE false findings, all from the same cause: a hand-rolled
median over `runs.jsonl` is not what the tables do. The generator applies
`load_canonical()` (rc=0, scale in PAPER_SCALES, and dedupe on payload fields
keeping the latest `ts_utc` per rep), which collapses re-run campaigns and
pilot runs to one row per rep. Pooling everything instead pulled two single-rep
E2 pilots into an N=5 measurement, and a correct number in the paper got
replaced with an incorrect one before the mistake was caught.

So this file does not recompute anything its own way. It imports the generator
and asks it, which is the only version of this check that cannot drift from
what the tables actually print.

Each CLAIM below pins one prose number to the selector that produces it. That
mapping is the part a machine cannot infer, so it is written down once here and
re-checked forever after. At the October freeze, running this says exactly
which prose numbers moved and which did not.

    python3 claims_check.py           # check all
    python3 claims_check.py --lane l2 # one lane

Exit status is 1 if any claim disagrees with the data.
"""
import argparse
import os
import re
import statistics as st
import sys

import make_paper_tables as M


def _sel(rows, lane=None, scale=None, backend=None, workload=None):
    out = []
    for r in rows:
        if lane is not None and r.get("lane") != lane:
            continue
        if scale is not None and r.get("scale") != scale:
            continue
        if backend is not None and r.get("backend") != backend:
            continue
        if workload is not None and r.get("workload") != workload:
            continue
        out.append(r)
    return out


def median_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return st.median(g) if g else None


def max_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return max(g) if g else None


def min_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return min(g) if g else None


TABLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                      ".notes", "papers", "icde-2027", "latex", "tables")
PAPER = os.path.join(TABLES, "..", "paper.tex")


def cell(table, row_label, col):
    """Numeric value of one cell in a GENERATED table.

    Sparse and dense rows come from overlay directories, not from
    `load_canonical()`, so re-deriving their selection here would just be a
    second implementation to drift. The tables themselves regenerate
    byte-identical from the data (checked separately), so pinning prose to a
    table cell chains prose -> table -> data without duplicating the middle
    step. `col` is 0-based over the row's own cells, after the label.
    """
    path = os.path.join(TABLES, table)
    for line in open(path):
        line = line.strip()
        if not line.startswith(row_label):
            continue
        cells = [c.strip() for c in line.rstrip("\\\\").split("&")][1:]
        if col >= len(cells):
            return None
        # "11.36 [11.2--11.8]" -> 11.36 ; "306 [306--314]" -> 306
        m = re.match(r"([0-9]*\.?[0-9]+)", cells[col].replace("{", "").replace("}", ""))
        return float(m.group(1)) if m else None
    return None


def gib(rows, field, **kw):
    """MiB field -> GiB. The prose divided by 1000 here and called it GiB,
    which inflated every memory number ~2.4%; the figure pipeline had it right
    all along, so prose and figure disagreed."""
    v = median_of(rows, field, **kw)
    return None if v is None else v / 1024



def ts_arm(field, primitive=True, numpy_cols=True):
    """Median over ONE time-series ingest arm.

    dev21_ts holds three arms (objlist, objnp, prim) and the paper reports the
    prim one, which is the TimeSeriesBatch primitive path. Pooling them gives
    1.29M pts/s where the paper says 1.73M, and every ratio in the prose
    (4.0x QuestDB, 55x the document path, DuckDB ahead by 1.12x) is consistent
    with 1.73M, so the arm is the claim.
    """
    import glob as _glob
    import json as _json
    out = []
    for fp in _glob.glob(os.path.join(M.RESULTS, "dev21_ts", "*.json")):
        d = _json.load(open(fp))
        if bool(d.get("primitive")) == primitive and \
           bool(d.get("numpy_cols")) == numpy_cols and \
           isinstance(d.get(field), (int, float)):
            out.append(d[field])
    return st.median(out) if out else None


def l4_median(field, backend):
    """Median over the l4_tsbs comparator rows."""
    import json as _json
    v = [r[field] for r in
         (_json.loads(l) for l in open(os.path.join(M.RESULTS, "l4_tsbs.jsonl")) if l.strip())
         if r.get("backend") == backend and isinstance(r.get(field), (int, float))]
    return st.median(v) if v else None



def torn_count(backend):
    """Trials in which the atomicity injection left a torn state.

    This is the paper's thesis in one number, so it is pinned like any other.
    Note the asymmetry it does NOT prove: for a single engine `torn_state` is
    False by construction, since tearing is defined as two systems disagreeing
    and there is only one system to ask. The force of the demonstration is
    entirely in the composed stack's 5/5.
    """
    rows = [r for r in M.load_canonical()
            if r.get("lane") == "e2" and r.get("workload") == "atomicity"
            and r.get("backend") == backend]
    return sum(1 for r in rows if r.get("torn_state"))


# The eight rows the dense prose ranks against: T5's dense half minus the
# server row, which is a deployment axis rather than a competitor.
DENSE_ROWS = ["ArcadeDB (emb)", "ArcadeDB (emb, int8, 16", "Qdrant", "Milvus",
              "Chroma", "LanceDB", "sqlite-vec", "DuckDB-VSS"]


def _sparse_reps(n_docs, subdir="dev22_sparse"):
    """How many reps actually stand behind a published sparse cell.

    T4's caption said N=5 for every cell while its 8.84M ArcadeDB row had
    three reps, the comparators in the same column having five. A rep count
    is a claim the caption makes, and nothing was checking it.

    Pinned at 3 deliberately: when the two missing reps land this fails, which
    is the point. The failure is the reminder to drop the caption's exception
    rather than leave a stale disclosure claiming a limitation we fixed.
    """
    import glob as _glob
    import json as _json
    n = 0
    for fp in _glob.glob(os.path.join(M.RESULTS, subdir, "*.json")):
        try:
            d = _json.load(open(fp))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("n_docs") == n_docs \
           and d.get("query_p50_ms") is not None:
            n += 1
    return float(n)


def _dense_rank(col):
    """1-based rank of ArcadeDB (emb) in `col` among DENSE_ROWS, lower better.

    Rank claims rot in a way no ratio claim can catch, because the drift is in
    the ORDERING and every individual cell stays correct. Two such claims were
    already wrong when this was written: the dense prose said "the best tail"
    after Chroma's row had moved ahead of it on p99, and the integration-cost
    prose said "within 2-4x at matched recall" long after the #5412 fixes put
    ArcadeDB second of eight. Both survived a checker that verified only the
    numbers it had been told about. A rank is the claim actually being made,
    so pin the rank.
    """
    mine = cell("t5_dense_ts.tex", "ArcadeDB (emb)", col)
    if mine is None:
        return None
    return 1.0 + sum(1 for s in DENSE_ROWS
                     if s != "ArcadeDB (emb)"
                     and (cell("t5_dense_ts.tex", s, col) or float("inf")) < mine)


# (id, prose value, tolerance, how to compute it, note)
# Tolerance is what the prose's own rounding allows, not a fudge factor: a
# claim printed as "525 ops/s" is satisfied by anything rounding to 525.
CLAIMS = [
    # --- L1 tabular -------------------------------------------------------
    ("l1.arcadedb.oltp", 5929, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "OLTP ops/s embedded"),
    ("l1.server.oltp", 1288, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_server"),
     "OLTP ops/s server (deployment axis)"),
    ("l1.postgres.oltp", 525, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="postgres"), "PostgreSQL ops/s"),
    ("l1.duckdb.oltp", 268, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="duckdb"), "DuckDB ops/s"),
    ("l1.arcadedb.insert_p99", 0.54, 0.01,
     lambda r: median_of(r, "insert_p99_ms", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "insert p99 ms"),

    # --- L2 graph ---------------------------------------------------------
    ("l2.arcadedb.hop2_p50", 1.57, 0.01,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "2-hop median SF10"),
    ("l2.neo4j.hop2_p50", 4.72, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="neo4j_graph"), "Neo4j 2-hop"),
    ("l2.ladybug.hop2_p50", 5.59, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="ladybug_graph"), "LadybugDB 2-hop"),
    ("l2.arcadedb.olap_friendage", 519, 1,
     lambda r: median_of(r, "friend_age_by_city_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP friend-age (WITH GAV)"),
    ("l2.arcadedb.olap_topdeg", 58, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP top-degree (WITH GAV)"),
    ("l2.neo4j.olap_topdeg", 305, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="neo4j_graph"), "Neo4j top-degree"),
    # The two summary figures in the same sentence, both of which were wrong
    # while every cell they summarise was right. "within 15%" was 8% on one
    # pair and 22% on the other; "wins all three by roughly 10x" ran 8.2x to
    # 20.9x. A spread stated as a single number hides its own worst case, so
    # pin the endpoints.
    ("l2.gap.samecity_pct", 22.0, 0.6,
     lambda r: 100.0 * (median_of(r, "same_city_edges_mean_ms", lane="l2",
                                  scale="sf10", workload="olap",
                                  backend="neo4j_graph")
                        / median_of(r, "same_city_edges_mean_ms", lane="l2",
                                    scale="sf10", workload="olap",
                                    backend="arcadedb_graph_embedded") - 1.0),
     "how far Neo4j trails us on same-city (prose: 22%)"),
    ("l2.ratio.ladybug_topdeg", 20.9, 0.3,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded")
               / median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                           workload="olap", backend="ladybug_graph"),
     "LadybugDB's widest OLAP win, the top of the 8--21x range"),
    # "graph loading beats both comparators" beat one. LadybugDB loads SF10
    # in 3.5 s against our 26.2, and the sentence sat in a paragraph headed
    # "competitive on every index-build axis". Pin the ratio to the comparator
    # we LOSE to: a claim of the form "beats both" is only ever falsified by
    # the one that is not beaten, so that is the one worth checking.
    ("l2.load.sf10", 26.2, 0.3,
     lambda r: median_of(r, "build_s", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "SF10 graph load (prose: 26 s)"),
    ("l2.ratio.ladybug_load", 7.4, 0.2,
     lambda r: median_of(r, "build_s", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded")
               / median_of(r, "build_s", lane="l2", scale="sf10",
                           workload="oltp", backend="ladybug_graph"),
     "how far LadybugDB's loader beats ours at SF10"),
    # The unit defect this file exists to stop recurring.
    ("l2.arcadedb.mem_gib", 9.4, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="arcadedb_graph_embedded"),
     "SF10 OLTP peak anon GiB (MiB/1024, NOT /1000)"),
    ("l2.neo4j.mem_gib", 12.9, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="neo4j_graph"), "Neo4j peak anon GiB"),

    # --- E2 hybrid --------------------------------------------------------
    # These are the ones a hand-rolled median got wrong. load_canonical drops
    # the two single-rep pilots, so the N=5 measurement stands alone.
    ("e2.arcadedb.p50", 3.36, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="arcadedb_e2"), "hybrid p50"),
    ("e2.arcadedb.max", 3.49, 0.01,
     lambda r: max_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range max"),
    ("e2.arcadedb.min", 3.20, 0.01,
     lambda r: min_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range min"),
    ("e2.surrealdb.p50", 7.02, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="surrealdb_e2"), "SurrealDB hybrid"),
    ("e2.composed.p50", 22.35, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="composed_qdrant_neo4j"), "composed stack hybrid"),

    # --- L3d dense memory -------------------------------------------------
    # ArcadeDB ran this lane at two pinned heaps and the comparators at one, so
    # the backend alone does not identify an operating point. The figure used to
    # median across both and landed on neither.
    ("l3d.qdrant.mem_gib", 5.97, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l3d", scale="deep10m",
                   backend="qdrant_dense"), "Qdrant dense peak anon GiB"),

    # --- L3s sparse, the paper's centrepiece ------------------------------
    # Pinned to T4's cells: prose -> table -> data. Column layout is
    # 100k(p50,p99,R) 1M(p50,p99,R) 8.84M(p50,p99,R), so 1M p50 is index 3 and
    # 8.84M p50 is index 6.
    ("l3s.arcadedb.1m_p50", 11.4, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 3), "1M p50"),
    ("l3s.arcadedb.full_p50", 83.7, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 6), "8.84M p50"),
    ("l3s.qdrant.full_p50", 16.4, 0.05,
     lambda r: cell("t4_sparse.tex", "Qdrant", 6), "Qdrant 8.84M p50"),
    ("l3s.milvus.full_p50", 40.5, 0.05,
     lambda r: cell("t4_sparse.tex", "Milvus", 6), "Milvus 8.84M p50"),
    # The two ratios the sparse argument turns on, recomputed rather than
    # restated: a ratio that drifts from its operands is the classic stale claim.
    ("l3s.ratio.qdrant_1m", 3.9, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 3)
               / cell("t4_sparse.tex", "Qdrant", 3), "Qdrant ratio at 1M"),
    ("l3s.ratio.qdrant_full", 5.1, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 6)
               / cell("t4_sparse.tex", "Qdrant", 6), "Qdrant ratio at 8.84M"),
    ("l3s.improvement", 14.5, 0.1,
     lambda r: 165.0 / cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 3),
     "1M improvement vs the 165 ms originally filed"),
    # The starting point of the same trajectory, stated as a ratio because the
    # integration-cost prose quotes it that way ("closed from 57x"). That
    # sentence carried 18x -> 13x for weeks after the dev22 refresh made it
    # 57x -> 3.9x: the operands were re-measured and the summary was not.
    ("l3s.ratio.qdrant_1m_orig", 57.0, 0.5,
     lambda r: 165.0 / cell("t4_sparse.tex", "Qdrant", 3),
     "1M Qdrant ratio this work started from"),
    # Rep counts are caption claims too. See _sparse_reps: this is pinned to
    # the CURRENT shortfall so completing it forces the caption to be updated.
    ("l3s.reps.8m84", 3.0, 0.0, lambda r: _sparse_reps(8841823),
     "reps behind the 8.84M cell (caption discloses N=3)"),
    ("l3s.reps.1m", 5.0, 0.0, lambda r: _sparse_reps(1000000),
     "reps behind the 1M cell (caption says N=5)"),

    # --- T5 dense ---------------------------------------------------------
    ("l3d.arcadedb.p50", 0.723, 0.005,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb)", 1), "dense p50 warm"),
    ("l3d.arcadedb.recall", 0.949, 0.001,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb)", 3), "dense recall@10"),
    # Both places the dense prose ranks itself. See _dense_rank for why a rank
    # needs its own claim and cannot be inferred from the cells.
    ("l3d.rank.p50", 2.0, 0.0, lambda r: _dense_rank(1),
     "dense p50 rank of 8 (prose: second, behind Chroma)"),
    ("l3d.rank.p99", 2.0, 0.0, lambda r: _dense_rank(2),
     "dense p99 rank of 8 (prose: second, behind Chroma)"),
    # The deployment prose quoted 0.81 (the #5412 close-out figure) while T5
    # and f8 both said 0.723. Three places, two numbers, same quantity.
    ("l3d.srv.p50", 1.82, 0.01,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv)", 1), "dense server p50"),
    # --- E2 atomicity, the thesis experiment -------------------------------
    ("e2.torn.composed", 5, 0,
     lambda r: torn_count("composed_qdrant_neo4j"), "composed stack torn 5/5"),
    ("e2.torn.arcadedb", 0, 0,
     lambda r: torn_count("arcadedb_e2"), "ArcadeDB torn 0/5"),
    ("e2.torn.surrealdb", 0, 0,
     lambda r: torn_count("surrealdb_e2"), "SurrealDB torn 0/5"),

    # --- L4 time series ---------------------------------------------------
    ("l4.native.ingest", 1.73e6, 5e3,
     lambda r: ts_arm("ingest_pts_per_s"), "native ingest pts/s (prim arm)"),
    ("l4.native.q_global", 29.6, 0.1,
     lambda r: ts_arm("q_global_ms"), "12h aggregation on the native path"),
    ("l4.questdb.ingest", 431305, 500,
     lambda r: l4_median("ingest_pts_per_s", "questdb"), "QuestDB line protocol"),
    ("l4.duckdb.ingest", 1.94e6, 5e3,
     lambda r: l4_median("ingest_pts_per_s", "duckdb"), "DuckDB bulk ingest"),
    ("l4.doc.q_global", 1791.65, 1.0,
     lambda r: l4_median("q_global_ms", "arcadedb"), "12h aggregation, document path (1.8 s)"),
    ("l4.ratio.questdb", 4.0, 0.05,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "questdb"),
     "native vs QuestDB"),
    ("l4.ratio.docpath", 55.0, 0.5,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "arcadedb"),
     "native vs our own document path"),
    ("l4.ratio.duckdb", 1.12, 0.01,
     lambda r: l4_median("ingest_pts_per_s", "duckdb") / ts_arm("ingest_pts_per_s"),
     "DuckDB's remaining lead"),
    # Last-point had the paper claiming a win it did not have. The prose read
    # "It wins the operational lookup: 0.52 ms beats both specialists" in a
    # paragraph whose subject was the NATIVE engine, but 0.52 is the document
    # path; native is 4.16 ms and loses to QuestDB (0.85) and DuckDB (1.40).
    # Two arms of our own system in one table, and the flattering row got
    # attributed to the arm being praised. Pin both arms separately so the
    # attribution cannot drift again.
    ("l4.native.q_last", 4.16, 0.05,
     lambda r: ts_arm("q_last_ms"), "last point, NATIVE arm (loses to both)"),
    ("l4.doc.q_last", 0.520, 0.01,
     lambda r: l4_median("q_last_ms", "arcadedb"),
     "last point, document path (the row that beats both)"),
    ("l4.rank.q_last_native", 3.0, 0.0,
     lambda r: 1.0 + sum(1 for b in ("questdb", "duckdb")
                         if (l4_median("q_last_ms", b) or float("inf"))
                         < (ts_arm("q_last_ms") or 0)),
     "native last-point rank of 3 vs the two specialists (3 = last)"),

    ("l3d.deployment_ratio", 2.52, 0.03,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv)", 1)
               / cell("t5_dense_ts.tex", "ArcadeDB (emb)", 1),
     "dense transport ratio (prose, table and f8 must agree)"),
]


def regen():
    """Do the committed tables still regenerate byte-identically from the data?

    This file's whole premise is the chain prose -> table -> data: claims are
    pinned to table cells rather than re-derived, on the stated grounds that
    "the tables themselves regenerate byte-identical from the data (checked
    separately)". Nothing was doing that separate check, so the middle link
    was the one assumption in the chain that nothing verified.

    It matters more than it sounds. If a committed table drifts from what the
    generator now produces, every claim pinned to a cell keeps passing against
    the stale file, and the checker reports green precisely when prose, table
    and data have come apart.

    Generates into a temp directory and diffs; never writes the real tables.
    """
    import filecmp
    import shutil
    import tempfile
    real = os.path.normpath(TABLES)
    tmp = tempfile.mkdtemp(prefix="tabgen_")
    saved = M.OUT
    try:
        M.OUT = tmp
        M.main()
    except Exception as e:
        print(f"  ERROR regenerating: {e.__class__.__name__}: {e}")
        return 1
    finally:
        M.OUT = saved
    names = sorted(f for f in os.listdir(real) if f.endswith(".tex"))
    bad = 0
    print("=== committed tables vs freshly generated ===")
    for n in names:
        gen = os.path.join(tmp, n)
        if not os.path.exists(gen):
            print(f"  {n:22} BAD committed but the generator no longer emits it")
            bad += 1
        elif filecmp.cmp(os.path.join(real, n), gen, shallow=False):
            print(f"  {n:22} identical")
        else:
            print(f"  {n:22} BAD differs from the data it claims to come from")
            bad += 1
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{bad} table(s) out of sync")
    return bad


def sweep():
    """List every ratio in the prose that no CLAIM pins, with its context.

    The gap this closes is the one that let "13x, closed from 18x" survive:
    CLAIMS verifies what it was told about, so a stale number in a paragraph
    nobody registered is invisible to it, no matter how many claims pass.
    Ratios get swept specifically because they are the summary-shaped numbers,
    the ones restating a comparison made elsewhere, and so the ones that go
    stale when the operands are re-measured.

    This does not judge: an uncovered ratio is not necessarily wrong, and
    several here are legitimately unpinnable (4--5x raw vector size, a
    citation's number). It only makes the uncovered set visible so the freeze
    reviews it deliberately instead of assuming a green CLAIMS run covered
    the prose. Ranges like "3--20x" are reported by their endpoints.
    """
    try:
        body = open(PAPER).read()
    except OSError as e:
        print(f"cannot read paper: {e}")
        return 0
    body = re.sub(r"(?m)^\s*%.*$", "", body)          # drop comment lines
    pinned = [c[1] for c in CLAIMS if isinstance(c[1], (int, float))]

    def covered(v):
        # 2% relative, so 57 covers a prose "57" computed as 56.7
        return any(abs(v - p) <= max(0.02 * abs(p), 0.05) for p in pinned)

    seen, out = set(), []
    # \,{,}\ is LaTeX's thousands separator: without it in the pattern,
    # "41{,}613$\times$" is read as 613 and the sweep quietly reports a
    # different number than the paper prints.
    num = r"[0-9]+(?:\{,\}[0-9]{3})*(?:\.[0-9]+)?"
    for m in re.finditer(rf"({num})(?:--({num}))?\s*\$\\times\$", body):
        for g in (m.group(1), m.group(2)):
            if not g:
                continue
            v = float(g.replace("{,}", ""))
            ctx = " ".join(body[max(0, m.start() - 90):m.end() + 12].split())
            key = (v, ctx[-60:])
            if key in seen:
                continue
            seen.add(key)
            if not covered(v):
                out.append((v, ctx))
    print(f"=== ratios in prose with no CLAIM pinning them ({len(out)}) ===")
    print("(not errors; the set the freeze must review deliberately)\n")
    for v, ctx in out:
        print(f"  {v}x  ...{ctx[-108:]}")
    print(f"\n{len(seen)} ratio mentions scanned, {len(seen) - len(out)} covered")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", help="only claims whose id starts with this")
    ap.add_argument("--sweep", action="store_true",
                    help="list prose ratios that no claim pins, and exit")
    ap.add_argument("--regen", action="store_true",
                    help="check committed tables still regenerate from data")
    args = ap.parse_args()

    if args.sweep:
        return sweep()
    if args.regen:
        return regen()

    rows = M.load_canonical()
    print(f"canonical rows: {len(rows)}  "
          f"(rc=0, PAPER_SCALES, latest ts_utc per lane/scale/workload/backend/rep)\n")

    bad = 0
    checked = 0
    for cid, claimed, tol, fn, note in CLAIMS:
        if args.lane and not cid.startswith(args.lane):
            continue
        checked += 1
        try:
            got = fn(rows)
        except Exception as e:
            print(f"  ERROR  {cid:26s} {e.__class__.__name__}: {e}")
            bad += 1
            continue
        if got is None:
            print(f"  NODATA {cid:26s} claim={claimed}  ({note})")
            bad += 1
            continue
        ok = abs(got - claimed) <= tol
        flag = "ok    " if ok else "MISMATCH"
        print(f"  {flag} {cid:26s} paper={claimed:<9} data={got:<11.4g} {note}")
        if not ok:
            bad += 1

    print(f"\n{checked} claims checked, {bad} disagree")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
