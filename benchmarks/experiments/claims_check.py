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


# The paper source is deliberately not in this repository. Point
# BENCH_PAPER_DIR at the directory holding paper.tex and its generated
# tables/ and figures/ subdirectories. Resolved at import but never opened
# here, so make_paper_figures can import this module for its result-loading
# helpers without the paper being present.
_PAPER_DIR = os.environ.get(
    "BENCH_PAPER_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "paper"))
TABLES = os.path.join(_PAPER_DIR, "tables")
PAPER = os.path.join(_PAPER_DIR, "paper.tex")


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
        # "11.36 [11.2--11.8]" -> 11.36 ; "306 [306--314]" -> 306 ;
        # "5.9k [5.5k--6.1k]" -> 5900 ; "1.73M [...]" -> 1730000.
        # The suffixes matter: without them "5.9k" reads as 5.9 and a checker
        # comparing it against 5929 reports a mismatch that is its own.
        txt = cells[col].replace("{", "").replace("}", "")
        m = re.match(r"([0-9]*\.?[0-9]+)\s*([kM])?", txt)
        if not m:
            return None
        return float(m.group(1)) * {"k": 1e3, "M": 1e6}.get(m.group(2) or "", 1)
    return None


def gib(rows, field, **kw):
    """MiB field -> GiB. The prose divided by 1000 here and called it GiB,
    which inflated every memory number ~2.4%; the figure pipeline had it right
    all along, so prose and figure disagreed."""
    v = median_of(rows, field, **kw)
    return None if v is None else v / 1024



def ts_arm(field, primitive=True, numpy_cols=True):
    """Median over ONE time-series ingest arm.

    The published row is the primitive TimeSeriesBatch path with numpy
    columns. The other arms (objlist, objnp) exist to decompose the harness
    correction in the prose (417k -> 1.29M -> 1.73M) and pooling them would
    report a number the paper never claims.

    Reads ts59's NOSETTLE arm, which is the row T5 prints: nothing else in
    the time-series block takes a settle step, and settling is not a uniform
    win here (2.23x faster on the 12-hour aggregation, 2.5x SLOWER on last
    point), so the arm is part of the claim exactly as primitive= is. Falls
    back to the superseded dev21 overlay rather than mixing lines.
    """
    import glob as _glob
    import json as _json
    for sub, pat in (("ts59", "nosettle_r*.json"),
                     ("dev21_ts", "*.json")):
        out = []
        for fp in _glob.glob(os.path.join(M.RESULTS, sub, pat)):
            d = _json.load(open(fp))
            if bool(d.get("primitive")) == primitive and \
               bool(d.get("numpy_cols")) == numpy_cols and \
               isinstance(d.get(field), (int, float)):
                out.append(d[field])
        if out:
            return st.median(out)
    return None


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


# The NINE rows the dense prose ranks against, which is every row of T5's
# dense half including the server. An earlier version listed eight and
# excluded the server as "a deployment axis rather than a competitor". The
# prose now says "sixth of nine", so the universe it ranks in is all of them
# and the checker has to agree with the sentence rather than with an
# argument about what deserves to compete.
#
# LABELS ARE PART OF THE CLAIM. cell() matches by startswith, so when the
# table split ArcadeDB's embedded row into fp32 and int8 arms, the old
# "ArcadeDB (emb)" stopped matching "ArcadeDB (emb, fp32)" -- the next
# character is a comma, not a paren -- and every dense claim went NODATA.
# That was the lucky outcome. Had the labels still matched, the column
# reindexing below would have compared warm p50 against cold p50 and recall
# against p99, and reported all-green.
DENSE_ROWS = ["ArcadeDB (emb, fp32)", "ArcadeDB (emb, int8)", "ArcadeDB (srv)",
              "Qdrant", "Milvus", "Chroma", "LanceDB", "sqlite-vec",
              "DuckDB-VSS"]

# 0-based column offsets into T5's dense half, after the label.
# System & Build (s) & Cold p50 & Warm p50 & Cold p99 & Recall
D_BUILD, D_COLD, D_WARM, D_COLDP99, D_RECALL = 0, 1, 2, 3, 4


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


def _dense_rank(col, row="ArcadeDB (emb, fp32)"):
    """1-based rank of `row` in column `col` among DENSE_ROWS, lower better.

    Rank claims rot in a way no ratio claim can catch, because the drift is in
    the ORDERING and every individual cell stays correct. Two such claims were
    already wrong when this was written: the dense prose said "the best tail"
    after Chroma's row had moved ahead of it on p99, and the integration-cost
    prose said "within 2-4x at matched recall" long after the #5412 fixes put
    ArcadeDB second of eight. Both survived a checker that verified only the
    numbers it had been told about. A rank is the claim actually being made,
    so pin the rank.

    Takes a row now because the cold/warm split made "our rank" four claims
    rather than one, and they disagree: the same engine is sixth cold and
    third warm. A helper that could only ask about one row was structurally
    unable to express what the paper says.
    """
    mine = cell("t5_dense_ts.tex", row, col)
    if mine is None:
        return None
    return 1.0 + sum(1 for s in DENSE_ROWS
                     if s != row
                     and (cell("t5_dense_ts.tex", s, col) or float("inf")) < mine)



def _comparator_engines():
    """Distinct comparator ENGINES the evaluation runs against.

    The abstract said eight. The data has twelve, because a backend name is
    per-lane (qdrant_sparse and qdrant_dense are one engine) and the count was
    written before the dense, time-series and cross-model lanes existed. It
    then never moved, like every other summary number this file now pins.

    Collapses per-lane variants to the engine, drops the composed stack (a
    composition of two engines already counted), and reports specialists
    separately from SurrealDB, which is the multi-model rival rather than a
    specialist and so does not belong in "specialist engines".
    """
    aliases = {"duckdb_vss_dense": "duckdb", "sqlite_vec_dense": "sqlite",
               "qdrant_sparse": "qdrant", "qdrant_dense": "qdrant",
               "milvus_sparse": "milvus", "milvus_dense": "milvus",
               "chroma_dense": "chroma", "lancedb_dense": "lancedb",
               "elasticsearch_sparse": "elasticsearch",
               "neo4j_graph": "neo4j", "ladybug_graph": "ladybug",
               "surrealdb_e2": "surrealdb"}
    names = set()
    for r in M.load_canonical():
        b = r.get("backend")
        if not b or "arcadedb" in b or b == "composed_qdrant_neo4j":
            continue
        names.add(aliases.get(b, b))
    names.add("questdb")  # l4_tsbs.jsonl, not in load_canonical
    return float(len(names - {"surrealdb"}))



_NUMWORDS = {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
             "fifteen": 15}


def _paper_specialist_count():
    """The count the PAPER PROSE states, verified to be stated only once.

    _comparator_engines() checks the DATA yields 11. It cannot check that the
    paper says 11, and that gap is not hypothetical: the abstract was corrected
    from eight to eleven and Section I was not, so the two sat two paragraphs
    apart disagreeing about the same evaluation until 2026-08-01. A reviewer
    reads exactly those two places.

    Returns the single spelled count if every mention agrees, else -1 so the
    claim fails loudly rather than silently checking one site.
    """
    with open(PAPER) as f:
        text = f.read()
    # A number word directly before "specialist", allowing an intervening line
    # break since the prose is hard-wrapped.
    found = re.findall(r"\b(" + "|".join(_NUMWORDS) + r")\s+specialist", text)
    if not found:
        return -1.0
    vals = {_NUMWORDS[w] for w in found}
    return float(next(iter(vals))) if len(vals) == 1 else -1.0


def _tentag(field, tags, arm="prim"):
    """One arm of the matched one-tag/ten-tag A/B.

    The paper reported this schema's cost as 23x, by dividing the TSBS
    campaign's 1.90M pts/s by THIS probe's one-tag rate of 82.5k. Two
    experiments, and the quotient is the gap between them, not the cost of
    ten tags. Within this probe the cost is 1.97x, and the paper's own
    #5411 lesson is that comparing across corpora is exactly this mistake.
    """
    import json as _json
    d = _json.load(open(os.path.join(M.RESULTS, "tentag", "tentag_ab.json")))
    for a in d["arms"]:
        if a["tags"] == tags and a["arm"] == arm:
            return float(a[field])
    return None


def e4_protocol_share(which):
    """Protocol's share of the embedded->containerised-server gap, as a percent.

    Backs the paper's "86--99.8% of the gap to the wire format at every result
    size". Three arms in one run: embedded, an in-process server over loopback
    HTTP, and a server in a separate container. protocol = inproc - embedded,
    boundary = docker - inproc. Reads the artifact rather than a transcribed
    number, because a prose figure with no artifact is exactly what the
    UNSOURCED L1 ingest claim is still failing on.

    which="min" or "max" over the measured sizes.
    """
    import json as _json
    fp = os.path.join(M.RESULTS, "e4decomp", "decomp_full.json")
    if not os.path.exists(fp):
        return None
    d = _json.load(open(fp))
    r = d["results"]
    shares = []
    for size in (str(x) for x in d["meta"]["sizes"]):
        try:
            e = r["embedded"][size]["p50_ms"]
            i = r["inproc_http"][size]["p50_ms"]
            k = r["docker_http"][size]["p50_ms"]
        except KeyError:
            continue
        tot = k - e
        if tot > 0:
            shares.append(100.0 * (i - e) / tot)
    if not shares:
        return None
    return min(shares) if which == "min" else max(shares)


# (id, prose value, tolerance, how to compute it, note)
# Tolerance is what the prose's own rounding allows, not a fudge factor: a
# claim printed as "525 ops/s" is satisfied by anything rounding to 525.
CLAIMS = [
    # --- L1 tabular -------------------------------------------------------
    ("abstract.n_specialists", 11.0, 0.0, lambda r: _comparator_engines(),
     "specialist engines the abstract claims (was 8, data says 11)"),
    ("paper.n_specialists_stated", 11.0, 0.0,
     lambda r: _paper_specialist_count(),
     "every 'N specialist' in paper.tex agrees, and agrees with the data "
     "(-1 means the sites disagree; abstract vs Section I did until 08-01)"),
    ("l1.arcadedb.oltp", 8435, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "OLTP ops/s embedded"),
    ("l1.server.oltp", 1428, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_server"),
     "OLTP ops/s server (deployment axis)"),
    ("l1.postgres.oltp", 525, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="postgres"), "PostgreSQL ops/s"),
    ("l1.duckdb.oltp", 273, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="duckdb"), "DuckDB ops/s"),
    # UNSOURCED, pinned so it cannot ship quietly. The prose reads "the
    # bindings' batched path reaches 36.7k rows/s [36.5--39.5k] ... versus
    # 27.4k per-record". No selection of the L1 data produces that: a brute
    # force over every backend/scale/workload combination in runs.jsonl found
    # zero matches for median 36.7k with that range. The canonical embedded
    # medium ingest is 31.3k and the server's is 27.4k, and the only raw rows
    # near 37-39k are a superseded 2026-07-11 campaign that load_canonical
    # drops. The dedicated #82 probe (results/ingest82, dev23, N=5, conditions
    # stamped) is a different experiment again and much faster: serial SQL
    # 67.3k, insert_many 177.1k, insert_many_parallel 181.7k, async_parallel
    # 122.0k, which does show the "parallel and batched converge" the sentence
    # describes but nowhere near these rates.
    # So the sentence needs a source decision, not a nudge: either it
    # describes the LANE (31.3k, and the 9x-behind-columnar claim moves) or
    # the PROBE (177k, and it moves the other way). Deliberately left failing.
    # Was l1.ingest.batched_UNSOURCED and failed for months. The paper said the
    # "batched path" reached 36.7k [36.5-39.5k]; the canonical lane says 31.3k
    # [30.3-31.6k], a disjoint range, and no selection reproduced 36.7k. Three
    # errors in one sentence: an unsourced number, "batched" applied to a lane
    # that only ever ran per-row SQL, and "27.4k per-record" that is in fact the
    # SERVER row's ingest rate (27,424). Corrected 2026-08-01 to the canonical
    # figures, with the bulk-API gap named from the #82 probe rather than left
    # for a reader to mistake for an engine limit.
    ("l1.ingest.perrow", 29390, 400,
     lambda r: median_of(r, "ingest_rows_per_s", lane="l1", scale="medium",
                         backend="arcadedb_embedded", workload="oltp"),
     "per-row SQL ingest over the 20M-row corpus, the number the lane measures"),
    ("l1.ingest.server", 26460, 300,
     lambda r: median_of(r, "ingest_rows_per_s", lane="l1", scale="medium",
                         backend="arcadedb_server", workload="oltp"),
     "same per-row path through the server; the paper used to call this "
     "'per-record'"),
    ("l1.ingest.columnar_lead", 10.7, 0.3,
     lambda r: median_of(r, "ingest_rows_per_s", lane="l1", scale="medium",
                         backend="duckdb", workload="oltp")
               / median_of(r, "ingest_rows_per_s", lane="l1", scale="medium",
                           backend="arcadedb_embedded", workload="oltp"),
     "how far the columnar loaders lead the per-row path (was stated as 9x, "
     "which followed from the unsourced 36.7k)"),
    ("l1.arcadedb.insert_p99", 0.30, 0.01,
     lambda r: median_of(r, "insert_p99_ms", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "insert p99 ms"),

    # --- L2 graph ---------------------------------------------------------
    ("l2.arcadedb.hop2_p50", 1.62, 0.01,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "2-hop median SF10"),
    ("l2.neo4j.hop2_p50", 4.72, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="neo4j_graph"), "Neo4j 2-hop"),
    ("l2.ladybug.hop2_p50", 5.52, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="ladybug_graph"), "LadybugDB 2-hop"),
    ("l2.arcadedb.olap_friendage", 495, 1,
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
    ("l2.gap.samecity_pct", 24.5, 0.6,
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
    ("l2.load.sf10", 22.8, 0.3,
     lambda r: median_of(r, "build_s", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "SF10 graph load (prose: 26 s)"),
    ("l2.ratio.ladybug_load", 6.3, 0.2,
     lambda r: median_of(r, "build_s", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded")
               / median_of(r, "build_s", lane="l2", scale="sf10",
                           workload="oltp", backend="ladybug_graph"),
     "how far LadybugDB's loader beats ours at SF10"),
    # The unit defect this file exists to stop recurring.
    ("l2.arcadedb.mem_gib", 8.07, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="arcadedb_graph_embedded"),
     "SF10 OLTP peak anon GiB (MiB/1024, NOT /1000)"),
    ("l2.neo4j.mem_gib", 12.9, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="neo4j_graph"), "Neo4j peak anon GiB"),

    # --- E2 hybrid --------------------------------------------------------
    # These are the ones a hand-rolled median got wrong. load_canonical drops
    # the two single-rep pilots, so the N=5 measurement stands alone.
    ("e2.arcadedb.p50", 1.93, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="arcadedb_e2"), "hybrid p50"),
    ("e2.arcadedb.max", 2.11, 0.01,
     lambda r: max_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range max"),
    ("e2.arcadedb.min", 1.87, 0.01,
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
    ("l3s.arcadedb.1m_p50", 11.3, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 3), "1M p50"),
    ("l3s.arcadedb.full_p50", 83.7, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 6), "8.84M p50"),
    ("l3s.qdrant.full_p50", 16.6, 0.05,
     lambda r: cell("t4_sparse.tex", "Qdrant", 6), "Qdrant 8.84M p50"),
    ("l3s.milvus.full_p50", 40.5, 0.05,
     lambda r: cell("t4_sparse.tex", "Milvus", 6), "Milvus 8.84M p50"),
    # The two ratios the sparse argument turns on, recomputed rather than
    # restated: a ratio that drifts from its operands is the classic stale claim.
    ("l3s.ratio.qdrant_1m", 3.9, 0.05,
     lambda r: cell("t4_sparse.tex", "ArcadeDB (emb, int8)", 3)
               / cell("t4_sparse.tex", "Qdrant", 3), "Qdrant ratio at 1M"),
    ("l3s.ratio.qdrant_full", 5.0, 0.05,
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
    # Cold and warm are both claims now, so both are pinned. Pinning only the
    # warm one is how the withdrawn "second of eight" survived as long as it
    # did: it was true of the column being checked.
    ("l3d.arcadedb.p50", 0.92, 0.01,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_WARM),
     "dense fp32 p50 warm"),
    ("l3d.arcadedb.cold", 7.89, 0.02,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_COLD),
     "dense fp32 p50 cold (first pass after build)"),
    ("l3d.arcadedb.recall", 0.953, 0.001,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_RECALL),
     "dense fp32 recall@10"),
    # The four ranks the dense prose states: "Cold, ArcadeDB fp32 is sixth of
    # nine and int8 fourth. Warm, int8 is second and fp32 third, both behind
    # Chroma." The previous pair pinned 2.0 against a sentence the paper had
    # ALREADY withdrawn in the same subsection ("we withdraw it"), so the
    # checker was defending a claim its own paper disowned. See _dense_rank.
    ("l3d.rank.cold.fp32", 6.0, 0.0,
     lambda r: _dense_rank(D_COLD, "ArcadeDB (emb, fp32)"),
     "dense cold p50 rank of 9, fp32 (prose: sixth)"),
    ("l3d.rank.cold.int8", 4.0, 0.0,
     lambda r: _dense_rank(D_COLD, "ArcadeDB (emb, int8)"),
     "dense cold p50 rank of 9, int8 (prose: fourth)"),
    ("l3d.rank.warm.int8", 2.0, 0.0,
     lambda r: _dense_rank(D_WARM, "ArcadeDB (emb, int8)"),
     "dense warm p50 rank of 9, int8 (prose: second, behind Chroma)"),
    ("l3d.rank.warm.fp32", 3.0, 0.0,
     lambda r: _dense_rank(D_WARM, "ArcadeDB (emb, fp32)"),
     "dense warm p50 rank of 9, fp32 (prose: third)"),
    # The deployment prose quoted 0.81 (the #5412 close-out figure) while T5
    # and f8 both said 0.723. Three places, two numbers, same quantity.
    #
    # THE SAME THING HAPPENED AGAIN, one layer up, and this claim is where it
    # surfaces. The prose still reports the post-fix server re-measure as
    # "1.82 to 1.80 ms, 0.952 both times" with the build falling
    # "13,349 to 3,825 s". Those are the #109 BESPOKE A/B driver's numbers.
    # T5's published row comes from the multipass lane artifact and says
    # 2.01 ms [1.94--2.29], recall 0.950, build 3,785 s.
    #
    # Pinned to the PUBLISHED row, not the prose, because FAIRNESS.md's rule
    # is that bespoke drivers investigate and lane scripts publish. The prose
    # keeps the bespoke pair -- its "before" half exists nowhere else, and
    # splicing 2.01 into one side of an A/B whose other side came from a
    # different run would be a worse error than the mismatch it fixed -- but
    # it must SAY that is what it is.
    ("l3d.srv.p50", 2.01, 0.015,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv)", D_WARM),
     "dense server p50 warm (published multipass row, not the #109 A/B)"),
    # --- E2 atomicity, the thesis experiment -------------------------------
    # The tear is deterministic, not a race we caught once: all five trials
    # report the same pair. The prose said "a representative trial", which is
    # true and weaker than the evidence.
    ("e2.torn.distinct_evidence", 1.0, 0.0,
     lambda r: float(len({(e.get("neo4j_view_sum"), e.get("qdrant_bumped_points"))
                          for e in (x.get("torn_evidence") or {} for x in M.load_canonical())
                          if e})),
     "distinct torn-evidence pairs across trials (1 = deterministic)"),
    ("e2.torn.composed", 5, 0,
     lambda r: torn_count("composed_qdrant_neo4j"), "composed stack torn 5/5"),
    ("e2.torn.arcadedb", 0, 0,
     lambda r: torn_count("arcadedb_e2"), "ArcadeDB torn 0/5"),
    ("e2.torn.surrealdb", 0, 0,
     lambda r: torn_count("surrealdb_e2"), "SurrealDB torn 0/5"),

    # --- L4 time series ---------------------------------------------------
    ("l4.native.ingest", 1.92e6, 5e3,
     lambda r: ts_arm("ingest_pts_per_s"), "native ingest pts/s (prim arm)"),
    ("l4.native.q_global", 29.9, 0.1,
     lambda r: ts_arm("q_global_ms"), "12h aggregation on the native path"),
    ("l4.questdb.ingest", 431305, 500,
     lambda r: l4_median("ingest_pts_per_s", "questdb"), "QuestDB line protocol"),
    ("l4.duckdb.ingest", 1.94e6, 5e3,
     lambda r: l4_median("ingest_pts_per_s", "duckdb"), "DuckDB bulk ingest"),
    ("l4.doc.q_global", 1791.65, 1.0,
     lambda r: l4_median("q_global_ms", "arcadedb"), "12h aggregation, document path (1.8 s)"),
    ("l4.ratio.questdb", 4.4, 0.05,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "questdb"),
     "native vs QuestDB"),
    ("l4.ratio.docpath", 61.0, 0.5,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "arcadedb"),
     "native vs our own document path"),
    ("l4.tentag.ingest_cost", 2.0, 0.05,
     lambda r: _tentag("ingest_pts_per_s", 1) / _tentag("ingest_pts_per_s", 10),
     "ten-tag ingest cost, matched A/B (prose said 23x across experiments)"),
    ("l4.tentag.lastpoint_gain", 2.6, 0.05,
     lambda r: _tentag("q_last_ms", 1) / _tentag("q_last_ms", 10),
     "ten-tag last-point speedup, matched A/B"),
    ("l4.ratio.duckdb", 1.01, 0.01,
     lambda r: l4_median("ingest_pts_per_s", "duckdb") / ts_arm("ingest_pts_per_s"),
     "DuckDB's remaining lead"),
    # Last-point had the paper claiming a win it did not have. The prose read
    # "It wins the operational lookup: 0.52 ms beats both specialists" in a
    # paragraph whose subject was the NATIVE engine, but 0.52 is the document
    # path; native is 4.16 ms and loses to QuestDB (0.85) and DuckDB (1.40).
    # Two arms of our own system in one table, and the flattering row got
    # attributed to the arm being praised. Pin both arms separately so the
    # attribution cannot drift again.
    # The native arm now reports the UNBOUNDED last point: the one-hour
    # recency window was a workaround for a scan upstream has since fixed
    # (#5414/#5416), and on this line the unbounded form is FASTER than the
    # window it replaced (0.690 vs 0.940 ms), so carrying the window would
    # cost time and still need a footnote.
    ("l4.native.q_last", 0.690, 0.05,
     lambda r: ts_arm("q_last_unbounded_ms"),
     "last point, NATIVE arm, unbounded (now beats both specialists)"),
    ("l4.native.q_last_windowed", 0.940, 0.05,
     lambda r: ts_arm("q_last_ms"),
     "the retired recency window, kept as a claim so its loss stays visible"),
    ("l4.doc.q_last", 0.520, 0.01,
     lambda r: l4_median("q_last_ms", "arcadedb"),
     "last point, document path (the row that beats both)"),
    ("l4.rank.q_last_native", 1.0, 0.0,
     lambda r: 1.0 + sum(1 for b in ("questdb", "duckdb")
                         if (l4_median("q_last_ms", b) or float("inf"))
                         < (ts_arm("q_last_unbounded_ms") or 0)),
     "native last-point rank vs the two specialists (was 3 = last, now 1)"),

    # 2.52 -> 2.49 with the post-fix server p50 (1.80 vs 1.82). The ratio is
    # not stated literally in the prose; it is pinned so prose, T5 and f8
    # cannot drift apart on the same quantity.
    # Now 2.01/0.92 = 2.18 on the published warm column. Both halves moved to
    # D_WARM together: taking the ratio across the cold/warm boundary would
    # divide a page-cache fill by a warm search and call the quotient
    # transport.
    ("l3d.deployment_ratio", 2.18, 0.03,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv)", D_WARM)
               / cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_WARM),
     "dense transport ratio (prose, table and f8 must agree)"),
    ("e4.protocol_share_min", 85.6, 0.3,
     lambda r: e4_protocol_share("min"),
     "protocol's SMALLEST share of the deployment gap across sizes; the "
     "paper's '86--99.8%' lower bound"),
    ("e4.protocol_share_max", 99.8, 0.1,
     lambda r: e4_protocol_share("max"),
     "protocol's LARGEST share; the paper's upper bound"),
]


def figures_fresh():
    """Are the committed figures older than the committed tables?

    regen() proves the tables still generate from the data. Nothing said
    anything about figures, and that is exactly the gap that bit on
    2026-07-31: the time-series row moved to a new overlay, the tables were
    regenerated, and the figures were not. make_paper_figures reads some
    series straight from results/ rather than from the tables, so its bar kept
    plotting the superseded overlay while the table beside it printed the new
    one. The PDF shipped both.

    make_paper_figures does carry a guard (_check_f4_against_tables) and it
    does catch this, but only at the moment figures are regenerated. If nobody
    regenerates them, nobody runs the guard, and stale files sit there looking
    exactly like fresh ones.

    Mtimes are a blunt instrument and deliberately so: a figure older than the
    newest table is not proof of disagreement, but it IS proof that no guard
    has compared them since the table last changed. That is the condition
    worth failing on.
    """
    import glob as _glob
    import re as _re
    # Only figures the paper actually \includegraphics. The figures directory
    # also holds orphans (an older sparse sweep, and an f5 that is generated
    # but never included), and flagging those would make this check noise,
    # which is how checks come to be ignored.
    try:
        body = open(PAPER).read()
    except OSError:
        body = ""
    used = set(_re.findall(r"\\includegraphics\[[^\]]*\]\{figures/([^}]+)\}", body))
    figdir = os.path.join(TABLES, "..", "figures")
    figs = [os.path.join(figdir, n + ".pdf") for n in sorted(used)
            if os.path.exists(os.path.join(figdir, n + ".pdf"))]
    orphans = [os.path.basename(f) for f in _glob.glob(os.path.join(figdir, "*.pdf"))
               if os.path.basename(f)[:-4] not in used]
    tabs = _glob.glob(os.path.join(TABLES, "*.tex"))
    if not figs or not tabs:
        print("=== figure freshness ===\n  (figures or tables missing; skipped)\n")
        return 0
    newest_tab = max(os.path.getmtime(f) for f in tabs)
    stale = [f for f in figs if os.path.getmtime(f) < newest_tab]
    print("=== figure freshness ===")
    if not stale:
        print(f"  ok: all {len(figs)} figures used by the paper are newer "
              f"than the newest table")
        if orphans:
            print(f"  (not checked, not included by the paper: "
                  f"{', '.join(sorted(orphans))})")
        print()
        return 0
    import datetime as _dt
    print(f"  BAD {len(stale)} of {len(figs)} figure(s) predate the newest table")
    print(f"      newest table: {_dt.datetime.fromtimestamp(newest_tab):%Y-%m-%d %H:%M}")
    for f in sorted(stale)[:8]:
        ts = _dt.datetime.fromtimestamp(os.path.getmtime(f))
        print(f"        {os.path.basename(f):28} {ts:%Y-%m-%d %H:%M}")
    print("      Regenerate figures; their table-agreement guard only runs then.")
    print()
    return len(stale)


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
        return regen() + figures_fresh()

    stale_figs = figures_fresh() if not args.lane else 0

    rows = M.load_canonical()
    print(f"canonical rows: {len(rows)}  "
          f"(rc=0, PAPER_SCALES, latest ts_utc per lane/scale/workload/backend/rep)\n")

    bad = stale_figs
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
