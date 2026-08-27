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
    """Rows matching the given axes, EXCLUDING the analytical-view ablation.

    Separating the two OLAP arms onto different canonical keys stopped the
    ablation from SHADOWING the published cell, but it left them both in the
    row set under one backend name, so an unfiltered median pooled them: the
    with-view friend-age claim read 841.6 ms, which is the midpoint of 492.9
    (with view) and 1213.3 (without) and describes neither arm.

    Every claim written against this helper means the published, with-view
    configuration, so that is the default. The ablation has its own reader
    (gav_ablation) that asks for `gav is False` explicitly. A row predating
    the stamp carries no `gav` and is with-view by construction.
    """
    out = []
    for r in rows:
        if r.get("gav") is False:
            continue
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
    # ONE SOURCE. ts_2681 is the released re-measure; ts59 (dev23) and
    # dev21_ts were the pre-release rungs of a cascade whose only function was
    # to keep printing whichever dev line existed. Both are gone: a fallback
    # here silently changes the engine AND, because the arms use different
    # last-point keys, the quantity being reported.
    for sub, pat in (("ts_2681", "nosettle_r*.json"),):
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
DENSE_ROWS = ["ArcadeDB (emb, fp32)", "ArcadeDB (emb, int8)",
              "ArcadeDB (srv, fp32)",
              "Qdrant", "Milvus", "Chroma", "LanceDB", "sqlite-vec",
              "DuckDB-VSS"]

# 0-based column offsets into T5's dense half, after the label.
# System & Build (s) & Cold p50 & Warm p50 & Cold p99 & Recall
D_BUILD, D_COLD, D_WARM, D_COLDP99, D_RECALL = 0, 1, 2, 3, 4


def sparse_cell(system, tier, metric):
    """One cell of T4, addressed by what it MEANS rather than where it sits.

    T4 used to be one row per system with the three tiers as column groups, so
    a claim could say "column 3 is 1M p50". Making it three rows per system
    invalidated every one of those indices at once, and silently: two claims
    started reading a recall out of the p50 slot and still parsed as numbers.
    Column-index addressing is only correct until the table is edited, and a
    table that can never be edited is not one anyone will keep honest.

    So address by (system, tier, metric). Continuation rows carry an empty
    first cell, which is right for a reader and unusable for a lookup, so
    carry the system name down as the file is walked.
    """
    path = os.path.join(TABLES, "t4_sparse.tex")
    col = {"p50": 2, "p99": 3, "recall": 4}[metric]
    cur = None
    for line in open(path):
        line = line.strip()
        if not line.endswith(r"\\") or line.startswith(r"\multicolumn"):
            continue
        cells = [c.strip() for c in line.rstrip("\\").split("&")]
        if len(cells) <= col:
            continue
        if cells[0]:
            cur = cells[0]
        if cur != system or cells[1] != tier:
            continue
        m = re.match(r"([0-9]*\.?[0-9]+)\s*([kM])?", cells[col])
        if not m:
            return None
        return float(m.group(1)) * {"k": 1e3, "M": 1e6}.get(m.group(2) or "", 1)
    return None


def sparse_multipass(tier, stat):
    """Cold/warm gain from the queue82 sparse multi-pass overlay.

    stat is "max_gain" (the largest gain any engine makes at this tier),
    "min_gain", "arcade_gain" or "elastic_gain". The paper quotes a RANGE
    across engines rather than one engine's number, so the claim has to be
    computed over the whole set: quoting only ours would be the flattering
    half of a comparison whose point is that nobody gains much.
    """
    import glob as _glob
    import json as _json
    root = os.path.join(M.RESULTS, "sparse_mp")
    gains = {}
    for fp in sorted(_glob.glob(os.path.join(root, f"sp_*_{tier}.json"))):
        try:
            with open(fp, encoding="utf-8") as fh:
                reps = _json.load(fh)
        except Exception:
            continue
        cold = [r["query_p50_ms"] for r in reps if r.get("rep") == 0]
        warm = [r["query_p50_ms"] for r in reps if r.get("rep", 0) >= 1]
        if not cold or not warm:
            continue
        name = os.path.basename(fp)[len("sp_"):-len(f"_{tier}.json")]
        gains[name] = cold[0] / st.median(warm)
    if not gains:
        return None
    if stat == "max_gain":
        return max(gains.values())
    if stat == "min_gain":
        return min(gains.values())
    if stat == "arcade_gain":
        return max(v for k, v in gains.items() if k.startswith("arc"))
    if stat == "elastic_gain":
        return gains.get("elastic")
    return None


def gav_ablation(field):
    """Median of one OLAP query with the Graph Analytical View DISABLED.

    Until 2026-08-10 the ablation the paper reports ("gives 1257, 1272 and
    381 ms") had no artifact anywhere under results/. It was measured on some
    dev line and transcribed, which is the same defect the E4 decomposition
    had and the same one this file exists to prevent.

    Three harness bugs had to be fixed before it could be re-measured
    honestly: runner.py dropped BENCH_GAV at the container boundary, so the
    ablation would have built the view anyway; l2_graph.py stamped nothing, so
    the ablation shared a canonical key with the published cell and would have
    REPLACED it; and neither failure was visible in an exit code.

    Reads the gav=False rows, which exist only because the lane now stamps the
    condition it ran under.
    """
    rows = [r for r in M.load_canonical()
            if r.get("lane") == "l2" and r.get("scale") == "sf10"
            and r.get("workload") == "olap" and r.get("gav") is False
            and isinstance(r.get(field), (int, float))]
    return st.median([r[field] for r in rows]) if rows else None


def gav_speedup(rows, field):
    """How much the view is worth on one query: ablated / with-view.

    The page prints neither absolute. It prints the RATIO ("worth 6.5x on top
    degree"), and a ratio pinned only by its numerator is not pinned.

    The with-view side goes through median_of/_sel, the SAME helper every other
    with-view claim uses, rather than a filter of its own. My first version
    selected `gav is True` and got NODATA on all 25 rows: nothing stamps True.
    The ablation records `gav=False` and the default arm records nothing, so
    with-view is expressed by ABSENCE, which _sel already knows and a fresh
    filter does not. Writing a second way to select the same arm is exactly what
    this file's docstring warns against.
    """
    off = gav_ablation(field)
    on = median_of(rows, field, lane="l2", scale="sf10", workload="olap",
                   backend="arcadedb_graph_embedded")
    if off is None or on in (None, 0):
        return None
    return off / on


def ingest_ab(arm):
    """Median rows/s of one arm of the 500k-row bulk-vs-per-row A/B.

    async_ingest_probe.py printed this to stdout and wrote no file, so the
    paper's "177.1k rows/s against 67.3k for per-row SQL" lived only in a
    queue log. Now written under results/ingest_ab/ with the run conditions,
    so it is checkable and re-derivable like every other cell.
    """
    import glob as _glob
    import json as _json
    out = []
    for fp in _glob.glob(os.path.join(M.RESULTS, "ingest_ab", "ab_r*.json")):
        d = _json.load(open(fp))
        if M._DEV_RE.search(str(d.get("engine_version", ""))):
            continue
        if arm in d and isinstance(d[arm].get("rows_per_s"), (int, float)):
            # A throughput from a run that wrote the wrong number of rows is
            # not a throughput. The probe checks its own count; honour it.
            if d[arm].get("count_ok"):
                out.append(d[arm]["rows_per_s"])
    return st.median(out) if out else None


def _sparse_reps(n_docs, subdir="sparse_2681", arm="arcadedb_sparse_embedded"):
    """How many reps actually stand behind a published sparse cell.

    T4's caption said N=5 for every cell while its 8.84M ArcadeDB row had
    three reps, the comparators in the same column having five. A rep count
    is a claim the caption makes, and nothing was checking it.

    It was pinned at 3 while that shortfall stood, so that completing it would
    fail this check and force the caption's exception to be retired rather than
    left as a stale disclosure. The released re-measure supplies all five, so
    the pin is 5 and the exception goes.

    COUNTS ONE ARM. The released directory holds int8 AND fp32 for every tier,
    so an unfiltered count returns 10 and reads as "twice the reps we claim"
    rather than "two arms of five". T4's ArcadeDB row is the int8 arm; fp32 is
    a separate labelled row with its own rep count.
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
           and d.get("backend") == arm \
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
    # EVERY ROW MUST RESOLVE. `or float("inf")` used to swallow a name that no
    # longer matched T5, ranking silently over the survivors: relabelling the
    # server arm "ArcadeDB (srv, fp32)" on 2026-08-13 left this list pointing
    # at "ArcadeDB (srv)", so four rank claims computed over eight engines
    # while their own descriptions said "of 9". They stayed green by luck,
    # because the missing engine is slower than ours on both columns, so no
    # rank moved. A denominator that can quietly shrink is worse than a wrong
    # number: nothing looks different when it happens.
    missing = [s for s in DENSE_ROWS
               if cell("t5_dense_ts.tex", s, col) is None]
    if missing:
        raise SystemExit(
            f"dense_rank: {missing} not found in T5 column {col}.\n"
            "  DENSE_ROWS must name the table's rows exactly. A row that does "
            "not resolve is dropped from the ranking, and the rank keeps "
            "reporting a total it no longer has.")
    return 1.0 + sum(1 for s in DENSE_ROWS
                     if s != row
                     and cell("t5_dense_ts.tex", s, col) < mine)



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
               "surrealdb_e2": "surrealdb",
               # THE BUFFER-POOL ABLATION IS NOT A TWELFTH ENGINE. It is
               # PostgreSQL with shared_buffers turned up, same image digest,
               # and without this alias it counted as its own engine and the
               # gate reported 12 against the paper's correct "eleven". The
               # hazard is not the gate going red, it is somebody trusting
               # data=12 and editing the prose to match.
               "postgres_tuned": "postgres"}
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


def _e4_decomp():
    """Decompose the embedded->containerised-server gap, per result size.

    Three arms per run: embedded, an in-process server over loopback HTTP, and
    a server in a separate container. protocol = inproc - embedded (the wire
    format), boundary = docker - inproc (containerisation and loopback).

    Aggregates the FOUR matched runs on the released 26.8.1 rather than the
    single dev24 run this used to read. That matters: the dev24 run gave a
    tidy-looking 85.6--99.8% protocol share, and repeating it shows the share
    is not a measurable quantity. The protocol term reproduces to ~1%, but the
    boundary term is smaller than the docker arm's own run-to-run spread, so
    the ratio between them is noise. A prose figure with no artifact is what
    the UNSOURCED L1 ingest claim still fails on; a prose figure backed by one
    sample of an unstable quantity is the same failure with a file attached.

    Only decomp3m_* qualifies: decomp3_2681 ran a 2g heap (different envelope)
    and decomp_2681 has no docker arm.

    Returns {size: {"total": [...], "protocol": [...], "boundary": [...]}}
    with one entry per run, or None if the artifacts are missing.
    """
    import glob
    import json as _json
    fps = sorted(glob.glob(os.path.join(M.RESULTS, "e4decomp_2681",
                                        "decomp3m_2681*.json")))
    if not fps:
        return None
    out = {}
    for fp in fps:
        d = _json.load(open(fp))
        if M._DEV_RE.search(str(d["meta"].get("engine_version", ""))):
            continue
        r = d["results"]
        for size in (str(x) for x in d["meta"]["sizes"]):
            try:
                e = r["embedded"][size]["p50_ms"]
                i = r["inproc_http"][size]["p50_ms"]
                k = r["docker_http"][size]["p50_ms"]
            except KeyError:
                continue
            s = out.setdefault(size, {"total": [], "protocol": [], "boundary": []})
            s["total"].append(k - e)
            s["protocol"].append(i - e)
            s["boundary"].append(k - i)
    return out or None


def e4_term_ms(term, size):
    """Median of one decomposition term at one result size, in ms."""
    d = _e4_decomp()
    if not d or str(size) not in d:
        return None
    return st.median(d[str(size)][term])


def e4_boundary_negative_sizes():
    """How many result sizes have a median container/loopback term below zero.

    A negative boundary says the containerised arm measured FASTER than the
    in-process one, which is impossible as a decomposition and is the cleanest
    statement that this term is below the design's resolution. Pinned as a
    claim so that if a future re-run ever resolves it, the paper's hedge is
    forced to be revisited rather than quietly left in place.
    """
    d = _e4_decomp()
    if not d:
        return None
    return float(sum(1 for s in d if st.median(d[s]["boundary"]) < 0))


# (id, prose value, tolerance, how to compute it, note)
# Tolerance is what the prose's own rounding allows, not a fudge factor: a
# claim printed as "525 ops/s" is satisfied by anything rounding to 525.
def _sparse_arm(arm, scale, field):
    """One field from T4's own released-engine source, for an arm T4 does not
    print.

    The fp32 ablation is discussed only in prose (T4 publishes the int8
    default), so no cell existed for anything to compare it against, and it
    drifted: the prose read 0.9999 recall for 2.9% on p50 against a measured
    0.9998 for 2.2%. A number that appears in no table needs its own claim or
    it has no auditor at all.
    """
    import glob
    import json
    vals = []
    for fp in glob.glob(os.path.join(M.RESULTS, "sparse_2681", "*.json")):
        try:
            r = json.load(open(fp))
        except Exception:
            continue
        if r.get("backend") == arm and r.get("scale") == scale:
            if isinstance(r.get(field), (int, float)):
                vals.append(r[field])
    return st.median(vals) if vals else None


def _sparse_build(rows, backend, n_docs=8841823):
    """Median build seconds at the 8.84M tier.

    Filtering on n_docs is the point: scale 'medium' holds BOTH the 8.84M
    Big-ANN corpus and a 10M synthetic one, so a selector keyed on scale alone
    pools two corpora and returns a median belonging to neither. The prose
    quoted four build numbers and three were wrong, one of them by that
    pooling and one by quoting a min as a median.
    """
    g = [r for r in rows if r.get("lane") == "l3s"
         and r.get("n_docs") == n_docs and r.get("backend") == backend
         and isinstance(r.get("build_s"), (int, float))]
    return st.median([r["build_s"] for r in g]) if g else None



# ---------------------------------------------------------------------------
# Python-binding suite. A separate experiment from the lanes above, pinned here
# because the project page publishes it and nothing else was checking it.
#
# These exist because of a specific, repeated failure: the numbers are ratios
# between two ARMS, and picking the wrong arm yields a real median of real rows
# that answers a different question. Swapping P-raw-call for P-SQL moves the
# published vector ratio from 1.28 to 1.71 while every gate stays green. That
# is the mistake these claims are here to fail on.
_PYB = os.path.join(os.path.dirname(M.RESULTS), "..", "python-bindings")


def _overhead_median(workload, arm):
    """Median microseconds for one arm of the JPype overhead re-measure."""
    import csv as _csv
    import statistics as _stat
    path = os.path.join(_PYB, "jpype_overhead", "results", "mini_results.csv")
    vals = []
    with open(path) as fh:
        for row in _csv.reader(fh):
            if len(row) >= 8 and row[3] == workload and row[4] == arm:
                try:
                    vals.append(float(row[6]))
                except ValueError:
                    pass
    return _stat.median(vals) if vals else None


def e2_atomicity(backend, field):
    """Totals over the E2 atomicity cells, summed across repetitions.

    Pinned because this experiment shipped a result for months that no gate
    covered, and the result was wrong: torn_state was decided by the PYTHON
    TYPE of the state object rather than by any comparison, so every
    single-engine backend was stamped atomic by construction while SurrealDB's
    writes were silently not landing at all. A gate on the outcome would not
    have caught that by itself, but a gate on the TRIAL COUNT would have: the
    published claim was "5 of 5", and five trials cannot support an atomicity
    claim (rule of three: the 95% upper bound on the failure rate is ~45%).
    So both the count and the outcome are pinned here.
    """
    # THROUGH load_canonical, NOT THE RAW LOG. Reading runs.jsonl directly
    # bypassed dedupe, the rc filter, PAPER_SCALES, the cpuset guard and the
    # pre-release guard, so every superseded repetition was summed again:
    # 30 rows where 15 are canonical, returning 400 against a pinned 200, and
    # it would have returned 600 after the next campaign.
    #
    # The direction matters. The paper reads "0 of 200", and 0-of-400 is a
    # materially stronger rule-of-three bound than 0-of-200 -- so the defect
    # inflated OUR OWN safety claim. Three sibling gates stayed green only
    # because zero times any row count is still zero.
    #
    # `trials` remains the discriminator: it exists only on rows written by
    # the FIXED harness, so pre-fix rows cannot satisfy this claim.
    total = 0
    seen = 0
    for r in M.load_canonical():
        if (r.get("lane") == "e2" and r.get("workload") == "atomicity"
                and r.get("backend") == backend
                and r.get("trials") is not None):
            seen += 1
            total += int(r.get(field) or 0)
    return float(total) if seen else None


def e2_clean_baseline_disagreements():
    """Disagreeing records before the first injection, over composed cells.

    The harness records evidence for the first few torn trials, each carrying
    the pre- and post-injection state. Trial 0's PRE is the clean baseline:
    fifty completed operations have written both stores and nothing has been
    interrupted yet, so the two must agree exactly.
    """
    # Through load_canonical for the same reason as e2_atomicity above: the
    # raw log double-counts superseded repetitions. Green today only because
    # the value is zero, and zero times any row count is zero -- which is
    # exactly the kind of accident that hides a defect until the number moves.
    total = 0.0
    seen = 0
    if True:
        for r in M.load_canonical():
            if (r.get("lane") == "e2" and r.get("workload") == "atomicity"
                    and r.get("backend") == "composed_qdrant_neo4j"
                    and r.get("trials") is not None):
                ev = r.get("torn_evidence") or []
                first = next((e for e in ev if e.get("trial") == 0), None)
                if first:
                    seen += 1
                    total += float((first.get("pre") or {}).get(
                        "disagreeing_products", 0))
    return total if seen else None


def e3(kind, field, stat="median"):
    """E3 durability and failover, from results/e3_q17/.

    These artifacts lived only on mini's home directory until 2026-08-14, so
    every number in the paper's durability subsection was correct and yet
    unverifiable from the repository -- an auditor reading results/ concluded
    the section had no evidence at all. Copied in and pinned here.

    e3a_default_* is the default asynchronous WAL contract, e3a_2_* is
    per-commit flush; the paper reports ten trials pooled across both.
    """
    import glob as _glob
    import json as _json
    import statistics as _stat
    pat = {"recovery": "e3a_*trial*.json", "failover": "e3b_*.json"}[kind]
    vals = []
    for f in sorted(_glob.glob(os.path.join(M.RESULTS, "e3_q17", pat))):
        try:
            d = _json.load(open(f))
        except Exception:
            continue
        if isinstance(d.get(field), (int, float)):
            vals.append(float(d[field]))
    if not vals:
        return None
    return {"median": _stat.median, "min": min, "max": max}[stat](vals)


def l2_peak_anon_gib(backend, scale="sf10", workload="oltp"):
    """Peak anonymous working set for one graph cell, in GiB.

    Pinned because memory was measured in every lane from the start and
    reported in almost none of them: T3 grew its column on 2026-08-14, and
    before that the only memory numbers in the paper were three prose
    sentences. A number that appears once in prose and nowhere in a table is
    exactly the kind that drifts, since nothing regenerates it.
    """
    import statistics as _stat
    rs = [r for r in M.load_canonical()
          if r.get("lane") == "l2" and r.get("backend") == backend
          and r.get("scale") == scale and r.get("workload") == workload
          and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
    return _stat.median([r["peak_anon_mib_sum"] for r in rs]) / 1024 if rs else None


def mem_ratio(lane_a, be_a, lane_b, be_b, scale_a, scale_b, wl=None):
    """Peak-anon ratio between two engines in one lane, as the prose states it.

    The cross-lane memory section quotes five ratios spanning two orders of
    magnitude. A ratio is the most fragile thing to leave unpinned: both
    operands can be individually correct and the quotient still stale, which
    is how "2.4x" survived into a draft of that paragraph when the artifact
    said 3.7 (I had copied it from a summary using a different scale).

    THE SCALES ARE REQUIRED, and that is the whole point. They used to default
    to None, which med() reads as "no filter", so a caller who forgot them got
    a quotient pooled across every scale -- a number corresponding to no
    measurement anyone made. mem.ratio.qdrant_dense did exactly that: the
    numerator was ArcadeDB at 1M (n=5) and the denominator a pooled 1M+10M
    median (n=10), giving 2.54, which its gate then reported green while the
    same-scale figure is 12.27. The ratio is ours-over-theirs, so the silent
    default understated OUR memory by 4.8x. A missing scale is now a
    TypeError at import, not a plausible number.
    """
    import statistics as _stat
    def med(lane, be, sc):
        v = [r["peak_anon_mib_sum"] for r in M.load_canonical()
             if r.get("lane") == lane and r.get("backend") == be
             and (sc is None or r.get("scale") == sc)
             and (wl is None or r.get("workload") == wl)
             and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
        return _stat.median(v) if v else None
    a, b = med(lane_a, be_a, scale_a), med(lane_b, be_b, scale_b)
    return a / b if a and b else None


def _med_field(backend, lane, scale, workload, field):
    """Median of any numeric field for one cell. Used where a claim needs a
    raw per-container column rather than the summed one."""
    import statistics as _stat
    v = [r[field] for r in M.load_canonical()
         if r.get("lane") == lane and r.get("backend") == backend
         and r.get("scale") == scale and r.get("workload") == workload
         and isinstance(r.get(field), (int, float))]
    return _stat.median(v) if v else None


def anon_client_share(backend, lane, scale, workload):
    """Of a cell's summed anonymous set, how much is the benchmark DRIVER.

    runner.py sums client and server containers into peak_anon_mib_sum, which
    is the right thing to do for an engine that holds its memory in its own
    address space. For PostgreSQL it inverts the meaning of the column: the
    server contributes 0.014 GiB and our Python client 0.105, so the cell that
    a reader compares against ArcadeDB's 12.7 is 88% our own harness.

    Pinned per cell rather than pooled because it is a property of the workload
    shape. The same PostgreSQL server under TPC-H reads 1.571 client against
    0.006 server, since the driver materialises result sets there.
    """
    import statistics as _stat
    rs = [r for r in M.load_canonical()
          if r.get("lane") == lane and r.get("backend") == backend
          and r.get("scale") == scale and r.get("workload") == workload
          and isinstance(r.get("client_peak_anon_mib"), (int, float))
          and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
    if not rs:
        return None
    c = _stat.median([r["client_peak_anon_mib"] for r in rs])
    t = _stat.median([r["peak_anon_mib_sum"] for r in rs])
    return c / t if t else None


def anon_share(backend):
    """What fraction of an engine's peak memory anonymous accounting captures.

    Added after the T2 column made a 107x "memory loss" against PostgreSQL.
    My first explanation was that 0.12 GiB is the image's default 128 MB
    shared_buffers, which was wrong twice over, and the correction is what
    anon_client_share below pins: the number is mostly our Python driver, and
    PostgreSQL's buffer pool is POSIX shared memory that cgroup v2 files under
    shmem, so it never appears in anon at any size. Probed directly:
    shared_buffers=2GB over a 3M-row scan gives 5 MiB anon, 78 MiB shmem,
    1.6 GiB file. These two numbers make the asymmetry a checkable quantity
    rather than a thing someone has to remember.
    """
    import statistics as _stat
    a = [r["peak_anon_mib_sum"] for r in M.load_canonical()
         if r.get("backend") == backend
         and isinstance(r.get("peak_anon_mib_sum"), (int, float))]
    t = [r["peak_mib_sum"] for r in M.load_canonical()
         if r.get("backend") == backend
         and isinstance(r.get("peak_mib_sum"), (int, float))]
    return _stat.median(a) / _stat.median(t) if a and t else None


def pyb_ratio(workload, numerator_arm, denominator_arm):
    """The published ratio, stated as the exact pair of arms it compares."""
    a = _overhead_median(workload, numerator_arm)
    b = _overhead_median(workload, denominator_arm)
    return None if a is None or b is None else a / b


def pyb_cell(lane, backend, field, dataset="medium"):
    """Median of one cell in the binding suite's frozen rows."""
    import csv as _csv
    import statistics as _stat
    path = os.path.join(_PYB, "results", "runs_paper.csv")
    vals = []
    with open(path) as fh:
        for r in _csv.DictReader(fh):
            if r.get("lane") == lane and r.get("backend") == backend \
               and r.get("dataset") == dataset:
                try:
                    vals.append(float(r[field]))
                except (KeyError, ValueError, TypeError):
                    pass
    return _stat.median(vals) if vals else None


CLAIMS = [
    # --- Python binding suite (published on the project page) --------------
    ("pyb.vector.ratio", 1.28, 0.02,
     lambda r: pyb_ratio("vector", "P-raw-call", "J-direct"),
     "Python vector search against the in-process Java baseline; the paper's "
     "~1.3x. P-SQL/J-SQL is 1.12x and answers a different question"),
    ("pyb.scan.ratio", 1.63, 0.02,
     lambda r: pyb_ratio("query", "P-columns-100000", "J-allcols-100000"),
     "Python 100k-row columnar scan against Java reading the same columns; "
     "the paper's ~1.6x"),
    ("pyb.transport.spread", 13.81, 0.15,
     lambda r: pyb_ratio("query", "P-tolist-100000", "P-columns-100000"),
     "row objects against columns inside Python: the choice of call costs "
     "more than the language boundary does"),
    ("pyb.tabular.arcadedb.oltp", 6416, 1,
     lambda r: pyb_cell("tabular", "arcadedb", "oltp_ops_per_s"),
     "embedded tabular OLTP ops/s"),
    ("pyb.tabular.duckdb.olap", 9.35, 0.05,
     lambda r: pyb_cell("tabular", "duckdb", "olap_total_ms"),
     "DuckDB analytical suite; it wins this column and the page says so"),
    ("pyb.graph.arcadedb.oltp", 3211.9, 1,
     lambda r: pyb_cell("graph", "arcadedb", "oltp_ops_per_s"),
     "embedded graph OLTP ops/s against LadybugDB"),
    ("pyb.vector.arcadedb.recall", 0.9796, 0.001,
     lambda r: pyb_cell("vector", "arcadedb", "recall@10"),
     "recall at the matched graph degree, printed beside the latency"),
    # --- L1 tabular -------------------------------------------------------
    ("abstract.n_specialists", 11.0, 0.0, lambda r: _comparator_engines(),
     "specialist engines the abstract claims (was 8, data says 11)"),
    ("paper.n_specialists_stated", 11.0, 0.0,
     lambda r: _paper_specialist_count(),
     "every 'N specialist' in paper.tex agrees, and agrees with the data "
     "(-1 means the sites disagree; abstract vs Section I did until 08-01)"),
    ("l1.arcadedb.oltp", 8362, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "OLTP ops/s embedded"),
    ("l1.server.oltp", 1466, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_server"),
     "OLTP ops/s server (deployment axis)"),
    ("l1.postgres.oltp", 523, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="postgres"), "PostgreSQL ops/s"),
    ("l1.duckdb.oltp", 275, 1,
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
    ("l1.ingest.perrow", 29860, 400,
     lambda r: median_of(r, "ingest_rows_per_s", lane="l1", scale="medium",
                         backend="arcadedb_embedded", workload="oltp"),
     "per-row SQL ingest over the 20M-row corpus, the number the lane measures"),
    ("l1.ingest.server", 27090, 300,
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
    ("l1.arcadedb.insert_p99", 0.32, 0.01,
     lambda r: median_of(r, "insert_p99_ms", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "insert p99 ms"),

    # --- L2 graph ---------------------------------------------------------
    ("l2.arcadedb.hop2_p50", 1.63, 0.01,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "2-hop median SF10"),
    ("l2.neo4j.hop2_p50", 4.90, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="neo4j_graph"), "Neo4j 2-hop"),
    ("l2.ladybug.hop2_p50", 5.61, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="ladybug_graph"), "LadybugDB 2-hop"),
    ("l2.arcadedb.olap_friendage", 493, 1,
     lambda r: median_of(r, "friend_age_by_city_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP friend-age (WITH GAV)"),
    ("l2.arcadedb.olap_topdeg", 57, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP top-degree (WITH GAV)"),
    ("l2.neo4j.olap_topdeg", 320, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="neo4j_graph"), "Neo4j top-degree"),
    # The two summary figures in the same sentence, both of which were wrong
    # while every cell they summarise was right. "within 15%" was 8% on one
    # pair and 22% on the other; "wins all three by roughly 10x" ran 8.2x to
    # 20.9x. A spread stated as a single number hides its own worst case, so
    # pin the endpoints.
    ("l2.gap.samecity_pct", 23.1, 0.6,
     lambda r: 100.0 * (median_of(r, "same_city_edges_mean_ms", lane="l2",
                                  scale="sf10", workload="olap",
                                  backend="neo4j_graph")
                        / median_of(r, "same_city_edges_mean_ms", lane="l2",
                                    scale="sf10", workload="olap",
                                    backend="arcadedb_graph_embedded") - 1.0),
     "how far Neo4j trails us on same-city (prose: 22%)"),
    ("l2.ratio.ladybug_topdeg", 20.6, 0.3,
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
    ("e2.arcadedb.p50", 1.819, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="arcadedb_e2"), "hybrid p50"),
    ("e2.arcadedb.max", 2.0910, 0.01,
     lambda r: max_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range max"),
    ("e2.arcadedb.min", 1.796, 0.01,
     lambda r: min_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range min"),
    ("e2.surrealdb.p50", 7.678, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="surrealdb_e2"), "SurrealDB hybrid"),
    ("e2.composed.p50", 19.674, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="composed_qdrant_neo4j"), "composed stack hybrid"),
    # The two RATIOS the intro now leads with. The three medians above were
    # already pinned and the ratios were not, which is how the intro came to
    # claim 10x against the composed stack while f4 plotted 3.8x against
    # SurrealDB: both were arithmetically right about different comparators,
    # and nothing compared them to each other.
    #
    # 3.8x is the one that carries weight. Beating a stack with no transaction
    # spanning its engines is the easy comparison; beating the rival that DOES
    # commit across models in one transaction is the claim a reviewer will test,
    # and it is the number f4's cross-model bar plots.
    ("e2.ratio.surrealdb", 4.221, 0.02,
     lambda r: (median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                          backend="surrealdb_e2")
                / median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                            backend="arcadedb_e2")),
     "cross-model vs SurrealDB; the intro's 3.8x and f4's bar"),
    ("e2.ratio.composed", 10.82, 0.02,
     lambda r: (median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                          backend="composed_qdrant_neo4j")
                / median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                            backend="arcadedb_e2")),
     "cross-model vs the composed stack; the intro's 10x"),

    # --- L3d dense memory -------------------------------------------------
    # ArcadeDB ran this lane at two pinned heaps and the comparators at one, so
    # the backend alone does not identify an operating point. The figure used to
    # median across both and landed on neither.
    ("l3d.qdrant.mem_gib", 5.97, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l3d", scale="deep10m",
                   backend="qdrant_dense"), "Qdrant dense peak anon GiB"),

    # --- L3s sparse, the paper's centrepiece ------------------------------
    # Pinned to T4's cells: prose -> table -> data. Column layout is
    # Addressed by (system, tier, metric): T4 is three rows per system now,
    # and column indices did not survive that change.
    ("l3s.arcadedb.1m_p50", 11.3, 0.05,
     lambda r: sparse_cell("ArcadeDB (emb, int8)", "1M", "p50"), "1M p50"),
    ("l3s.arcadedb.full_p50", 83.7, 0.05,
     lambda r: sparse_cell("ArcadeDB (emb, int8)", "8.84M", "p50"), "8.84M p50"),
    ("l3s.qdrant.full_p50", 16.1, 0.05,
     lambda r: sparse_cell("Qdrant", "8.84M", "p50"), "Qdrant 8.84M p50"),
    ("l3s.milvus.full_p50", 39.0, 0.05,
     lambda r: sparse_cell("Milvus", "8.84M", "p50"), "Milvus 8.84M p50"),
    # Elasticsearch had NO claim at all, and its prose went stale the day
    # 0ff787925c disabled index-time pruning: the paragraph kept quoting the
    # pruned 10.8 ms / 0.781 recall after T4 refilled with unpruned rows. That
    # published a comparator at an operating point we had ourselves rejected as
    # unfair, in our favor, which is the exact failure the commit prevented in
    # the table and nothing prevented in the sentence.
    ("l3s.es.full_p50", 55.8, 0.05,
     lambda r: sparse_cell("Elasticsearch", "8.84M", "p50"),
     "Elasticsearch 8.84M p50, pruning disabled"),
    ("l3s.es.full_recall", 0.997, 0.01,
     lambda r: sparse_cell("Elasticsearch", "8.84M", "recall"),
     "Elasticsearch 8.84M recall@10, pruning disabled (was 0.781 pruned)"),
    # The fp32 ablation, which lives only in prose.
    ("l3s.fp32.full_recall", 0.9998, 0.001,
     lambda r: _sparse_arm("arcadedb_sparse_embedded_fp32", "medium",
                           "recall_at_10"),
     "fp32 8.84M recall@10 (prose said 0.9999)"),
    ("l3s.fp32.p50_penalty_pct", 2.2, 0.15,
     lambda r: 100.0 * (_sparse_arm("arcadedb_sparse_embedded_fp32", "medium",
                                    "query_p50_ms")
                        / _sparse_arm("arcadedb_sparse_embedded", "medium",
                                      "query_p50_ms") - 1.0),
     "what exactness costs on p50 at 8.84M (prose said 2.9%)"),
    # The four build seconds the 8.84M paragraph quotes. Three were wrong.
    ("l3s.build.arcadedb", 906.0, 1.0,
     lambda r: _sparse_arm("arcadedb_sparse_embedded", "medium", "build_s"),
     "ArcadeDB 8.84M build s (prose said 951)"),
    ("l3s.build.milvus", 1003.0, 1.0,
     lambda r: _sparse_build(r, "milvus_sparse"), "Milvus 8.84M build s"),
    ("l3s.build.qdrant", 1760.0, 1.0,
     lambda r: _sparse_build(r, "qdrant_sparse"),
     "Qdrant 8.84M build s (prose said 1,741, which is the min)"),
    ("l3s.build.es", 3111.0, 1.0,
     lambda r: _sparse_build(r, "elasticsearch_sparse"),
     "Elasticsearch 8.84M build s (prose said 3,077)"),
    # The two ratios the sparse argument turns on, recomputed rather than
    # restated: a ratio that drifts from its operands is the classic stale claim.
    ("l3s.ratio.qdrant_1m", 3.9, 0.05,
     lambda r: sparse_cell("ArcadeDB (emb, int8)", "1M", "p50")
               / sparse_cell("Qdrant", "1M", "p50"), "Qdrant ratio at 1M"),
    ("l3s.ratio.qdrant_full", 5.2, 0.05,
     lambda r: sparse_cell("ArcadeDB (emb, int8)", "8.84M", "p50")
               / sparse_cell("Qdrant", "8.84M", "p50"), "Qdrant ratio at 8.84M"),
    # l3s.improvement and l3s.ratio.qdrant_1m_orig were removed with the prose
    # they pinned. Both hardcoded 165.0, a pre-release measurement, as the
    # numerator of a "how far we have come" ratio. The paper reports one
    # released version and no trajectory, so a claim whose constant cannot be
    # reproduced from any published row has nothing left to check.
    # Rep counts are caption claims too. The 8.84M cell was stuck at N=3 for
    # weeks because the two missing reps could not be matched to the first
    # three, nothing having recorded what those ran under; the released
    # re-measure supplies all five under recorded conditions, so the pin moves
    # to 5 and the caption's N=3 exception is retired rather than carried.
    ("l3s.reps.8m84", 5.0, 0.0, lambda r: _sparse_reps(8841823),
     "reps behind the 8.84M cell (caption says N=5)"),
    ("l3s.reps.1m", 5.0, 0.0, lambda r: _sparse_reps(1000000),
     "reps behind the 1M cell (caption says N=5)"),

    # --- T5 dense ---------------------------------------------------------
    # Cold and warm are both claims now, so both are pinned. Pinning only the
    # warm one is how the withdrawn "second of eight" survived as long as it
    # did: it was true of the column being checked.
    ("l3d.arcadedb.p50", 0.96, 0.01,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_WARM),
     "dense fp32 p50 warm"),
    ("l3d.arcadedb.cold", 8.87, 0.02,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_COLD),
     "dense fp32 p50 cold (first pass after build)"),
    # THE PAGE'S TWO RECALL FIGURES, pinned against CANONICAL ROWS rather than
    # the paper's generated t5_dense_ts.tex. The page renders from
    # web_benchmarks.json, which comes from runs_paper.csv, so pinning it to the
    # paper's tables would check the page against a file it does not read -- and
    # BENCH_PAPER_DIR is deliberately absent from this repo, so those claims are
    # NODATA here anyway.
    #
    # arcadedb at deep10m has NO canonical rows yet: the dense campaign running
    # on mini is what produces them. Until it lands this claim is NODATA, which
    # is the correct reading of "the page states a number our data cannot yet
    # produce" -- it came from the paper's tables, and the campaign will replace
    # it. Do not delete the claim to make the check green.
    ("l3d.page.recall.arcadedb_deep10m", 0.951, 0.002,
     lambda r: median_of(r, "recall_at_10", lane="l3d", scale="deep10m",
                         backend="arcadedb_dense_embedded"),
     "the page's \"ArcadeDB returns 95.1%\" at 10M"),
    ("l3d.page.recall.chroma_deep10m", 0.9337, 0.002,
     lambda r: median_of(r, "recall_at_10", lane="l3d", scale="deep10m",
                         backend="chroma_dense"),
     "the page's \"Chroma returns 93.4% of the true neighbours\""),
    ("l3d.arcadedb.recall", 0.951, 0.001,
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
    ("l3d.srv.p50", 2.10, 0.015,
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv, fp32)", D_WARM),
     "dense server p50 warm (published multipass row, not the #109 A/B)"),
    # --- E3 durability and failover ---------------------------------------
    # Pinned late: these artifacts were on mini only, so this subsection was the
    # one part of the evaluation no gate could reach.
    ("e3.recovery.median", 0.361, 0.0005,
     lambda r: e3("recovery", "recovery_s", "median"),
     "SIGKILL-during-ingest recovery, median of ten trials"),
    ("e3.recovery.min", 0.354, 0.0005,
     lambda r: e3("recovery", "recovery_s", "min"), "fastest of the ten"),
    ("e3.recovery.max", 0.375, 0.0005,
     lambda r: e3("recovery", "recovery_s", "max"), "slowest of the ten"),
    ("e3.recovery.trials", 10.0, 0.0,
     lambda r: float(len([1 for _ in __import__("glob").glob(
         os.path.join(M.RESULTS, "e3_q17", "e3a_*trial*.json"))])),
     "recovery trials, five under the default async WAL contract and five "
     "under per-commit flush; the paper states both halves"),
    ("e3.failover.election", 9.60, 0.01,
     lambda r: e3("failover", "election_s", "median"),
     "Raft election, median of five"),
    ("e3.failover.overhead", 0.21, 0.01,
     lambda r: e3("failover", "client_overhead_s", "median"),
     "delay from a new leader to the first acknowledged write"),
    ("e3.failover.total", 9.81, 0.01,
     lambda r: e3("failover", "failover_s", "median"),
     "client-observed failover; the paper reports election and overhead "
     "separately because 'failover time' means different things to the "
     "cluster and to the client"),
    ("e3.integrity.no_acked_loss", 5.0, 0.0,
     lambda r: e3("failover", "no_acked_loss", "median") and float(len([1 for _ in
         __import__("glob").glob(os.path.join(M.RESULTS, "e3_q17", "e3b_*.json"))])),
     "failover trials in which no acknowledged write was lost; this is the "
     "correctness claim, the timing is secondary to it"),
    # --- the cross-lane memory section's five ratios ----------------------
    # The PostgreSQL memory ratio is NOT pinned as a result, because it is not
    # one. Its anon is 0.119 GiB, which is the image's default 128 MB
    # shared_buffers and nothing else: PostgreSQL keeps its working set in the
    # kernel page cache, which anon does not count. We set ArcadeDB's heap per
    # scale tier and left that default alone, so the ratio priced our own
    # configuration. What IS pinned is the confound itself, so that a future
    # reader who recomputes the ratio finds this note instead of a claim.
    ("mem.postgres.client_share", 0.884, 0.02,
     lambda r: anon_client_share("postgres", "l1", "medium", "oltp"),
     "of the PostgreSQL tabular cell's anon, this fraction is our Python "
     "driver, not the server (0.105 GiB client vs 0.014 server)"),
    ("mem.postgres.server_anon_gib", 0.014, 0.004,
     lambda r: (lambda v: v / 1024 if v is not None else None)(
         _med_field("postgres", "l1", "medium", "oltp", "server_peak_anon_mib")),
     "the PostgreSQL server's own anonymous set on the cell T2 prints; its "
     "buffer pool is shmem and its working set page cache, so anon sees "
     "neither at any shared_buffers setting"),
    ("mem.anon_share.postgres", 0.262, 0.02,
     lambda r: anon_share("postgres"),
     "fraction of PostgreSQL's peak that anon accounting captures. Low because "
     "its working set is page cache; the number exists so the asymmetry is "
     "checkable rather than remembered"),
    ("mem.anon_share.arcadedb_graph", 0.975, 0.02,
     lambda r: anon_share("arcadedb_graph_embedded"),
     "same fraction for a JVM engine, where the heap IS anonymous. The gap "
     "between this and the row above is why an anon ratio across these two "
     "architectures is not a comparison"),
    ("mem.ratio.ladybug", 22.1, 0.3,
     lambda r: mem_ratio("l2", "arcadedb_graph_embedded", "l2", "ladybug_graph",
                         "sf10", "sf10", "oltp"),
     "graph SF10 OLTP against the non-JVM columnar engine"),
    # DELIBERATELY LEFT TO FAIL, and the failure is the honest state.
    # This claim says DEEP-10M, so it now asks for DEEP-10M -- and ArcadeDB has
    # no canonical row there, because every one carries 26.8.1.dev3 or
    # -SNAPSHOT and the pre-release guard drops it. So the ratio cannot be
    # computed at the scale the paper names, and the check reports missing data
    # instead of a cross-scale quotient that flattered us by 4.8x.
    # Resolve by re-measuring ArcadeDB dense at DEEP-10M on a released engine,
    # or by withdrawing the dense memory comparison the way the PostgreSQL one
    # was withdrawn (#150). Do not "fix" this by re-pinning to 12.27: at
    # l3d/small ArcadeDB's peak IS its 8 GiB heap, the same caveat the sparse
    # paragraph already carries.
    ("mem.ratio.qdrant_dense", 2.54, 0.05,
     lambda r: mem_ratio("l3d", "arcadedb_dense_embedded", "l3d", "qdrant_dense",
                         "deep10m", "deep10m"),
     "dense DEEP-10M"),
    ("mem.ratio.qdrant_sparse", 3.67, 0.06,
     lambda r: mem_ratio("l3s", "arcadedb_sparse_embedded", "l3s", "qdrant_sparse",
                         "small", "small"),
     "sparse 1M. Pinned at 3.7 because a draft said 2.4, copied from a summary "
     "over a different scale selection: both operands right, quotient wrong"),
    ("mem.ratio.neo4j", 0.62, 0.02,
     lambda r: mem_ratio("l2", "arcadedb_graph_embedded", "l2", "neo4j_graph",
                         "sf10", "sf10", "oltp"),
     "the one comparison that favours us, stated as ours-over-theirs so a "
     "regression moves it the same direction as the losses above"),
    # --- graph memory, the column T3 grew on 2026-08-14 -------------------
    ("l2.mem.arcade_sf10", 8.06, 0.02,
     lambda r: l2_peak_anon_gib("arcadedb_graph_embedded"),
     "peak anon GiB, SF10 OLTP; the paper rounds it to 8.1"),
    ("l2.mem.neo4j_sf10", 12.93, 0.02,
     lambda r: l2_peak_anon_gib("neo4j_graph"),
     "Neo4j at the same cell; the 37% claim is this over ours"),
    ("l2.mem.ladybug_sf10", 0.365, 0.01,
     lambda r: l2_peak_anon_gib("ladybug_graph"),
     "LadybugDB at the same cell. This is OUR LOSS and the largest margin in "
     "the row: 22x less than ArcadeDB. Pinned so the prose that now states it "
     "cannot quietly revert to naming only the comparator we beat"),
    # --- E2 atomicity, the thesis experiment -------------------------------
    # THE CONTROL, and it is the claim the old version of this experiment could
    # not make. It used to pin "1 distinct torn-evidence pair", derived from
    # neo4j_view_sum vs qdrant_bumped_points -- a SUM against a COUNT of a
    # boolean flag, two quantities that drift apart with no crash and no
    # tearing at all, so the pair it called deterministic was measuring the
    # workload rather than the failure. Both stores now hold the same counter,
    # and what gets pinned is that they AGREE while nothing is injected. A
    # disagreement metric that never reads zero proves nothing; this is what
    # makes a non-zero reading afterwards evidence.
    ("e2.torn.clean_baseline", 0.0, 0.0,
     lambda r: e2_clean_baseline_disagreements(),
     "records the two stores disagree about BEFORE the first injection, "
     "summed over every composed-stack repetition; must be zero, otherwise "
     "the tear counted afterwards cannot be attributed to the injection"),
    ("e2.torn.composed", 5, 0,
     lambda r: torn_count("composed_qdrant_neo4j"), "composed stack torn 5/5"),
    ("e2.torn.arcadedb", 0, 0,
     lambda r: torn_count("arcadedb_e2"), "ArcadeDB torn 0/5"),
    ("e2.torn.surrealdb", 0, 0,
     lambda r: torn_count("surrealdb_e2"), "SurrealDB torn 0/5"),

    # --- L4 time series ---------------------------------------------------
    ("l4.native.ingest", 1.861e6, 5e3,
     lambda r: ts_arm("ingest_pts_per_s"), "native ingest pts/s (prim arm)"),
    ("l4.native.q_global", 25.0, 0.1,
     lambda r: ts_arm("q_global_ms"), "12h aggregation on the native path"),
    ("l4.questdb.ingest", 432400, 500,
     lambda r: l4_median("ingest_pts_per_s", "questdb"), "QuestDB line protocol"),
    ("l4.duckdb.ingest", 1862000, 5e3,
     lambda r: l4_median("ingest_pts_per_s", "duckdb"), "DuckDB bulk ingest"),
    ("l4.doc.q_global", 1696, 1.0,
     lambda r: l4_median("q_global_ms", "arcadedb"), "12h aggregation, document path (1.8 s)"),
    ("l4.ratio.questdb", 4.32, 0.05,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "questdb"),
     "native vs QuestDB"),
    ("l4.ratio.docpath", 46.4, 0.5,
     lambda r: ts_arm("ingest_pts_per_s") / l4_median("ingest_pts_per_s", "arcadedb"),
     "native vs our own document path"),
    ("l4.tentag.ingest_cost", 2.0, 0.05,
     lambda r: _tentag("ingest_pts_per_s", 1) / _tentag("ingest_pts_per_s", 10),
     "ten-tag ingest cost, matched A/B (prose said 23x across experiments)"),
    ("l4.tentag.lastpoint_gain", 2.6, 0.05,
     lambda r: _tentag("q_last_ms", 1) / _tentag("q_last_ms", 10),
     "ten-tag last-point speedup, matched A/B"),
    ("l4.ratio.duckdb", 1.00, 0.01,
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
    ("l4.native.q_last_windowed", 0.860, 0.05,
     lambda r: ts_arm("q_last_ms"),
     "the retired recency window, kept as a claim so its loss stays visible"),
    ("l4.doc.q_last", 0.43, 0.01,
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
     lambda r: cell("t5_dense_ts.tex", "ArcadeDB (srv, fp32)", D_WARM)
               / cell("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", D_WARM),
     "dense transport ratio (prose, table and f8 must agree)"),
    # The deployment decomposition, N=4 matched runs on the released engine.
    # These three replace a "85.6--99.8% protocol" pair that was computed from
    # ONE dev24 run. Repeating that run showed the share is not a measurable
    # quantity here: the protocol term reproduces to 1% but the boundary term
    # is smaller than the docker arm's own spread, so their ratio ranged
    # 46--326%. Shares above 100% mean the containerised arm measured FASTER
    # than the in-process one. The two terms are pinned separately instead,
    # because each is defensible on its own and the quotient is not.
    ("e4.protocol_ms_100k", 70.2, 0.05,
     lambda r: e4_term_ms("protocol", 100000),
     "wire-format cost at 100k rows, ms; reproduces to 1% across 4 runs"),
    ("e4.total_ms_100k", 78.2, 0.05,
     lambda r: e4_term_ms("total", 100000),
     "full embedded->containerised gap at 100k rows, ms"),
    # --- the two prose numbers that had no artifact until 2026-08-10 -------
    # The sparse multi-pass paragraph. A range across ENGINES, so each bound is
    # gated separately; quoting only ArcadeDB's would hide that the point is
    # that nobody gains much.
    ("l3s.multipass.small.max", 1.18, 0.02,
     lambda r: sparse_multipass("small", "max_gain"),
     "largest cold/warm gain by any engine at 1M"),
    ("l3s.multipass.medium.max", 1.13, 0.02,
     lambda r: sparse_multipass("medium", "max_gain"),
     "largest cold/warm gain by any engine at 8.84M"),
    ("l3s.multipass.medium.arcade", 1.04, 0.02,
     lambda r: sparse_multipass("medium", "arcade_gain"),
     "ArcadeDB's own gain at 8.84M, the smallest of the six"),
    ("l3s.multipass.medium.elastic", 1.13, 0.02,
     lambda r: sparse_multipass("medium", "elastic_gain"),
     "Elasticsearch's gain at 8.84M, the largest of the six"),
    ("l2.gav_ablated.friendage", 1213, 1,
     lambda r: gav_ablation("friend_age_by_city_mean_ms"),
     "friend-age WITHOUT the analytical view"),
    ("l2.gav_ablated.samecity", 1196, 1,
     lambda r: gav_ablation("same_city_edges_mean_ms"),
     "same-city WITHOUT the analytical view"),
    ("l2.gav_ablated.topdeg", 368, 1,
     lambda r: gav_ablation("top_degree_mean_ms"),
     "top-degree WITHOUT the analytical view; the 6.5x arm"),
    # THE RATIOS THE PROJECT PAGE PRINTS. Named l2.page.* rather than page.*
    # because --lane filters on the id PREFIX: a page claim about l2 data that
    # does not start with the lane silently never runs under --lane l2, which is
    # how the campaign checks each lane as it lands. The absolutes above were pinned and
    # the ratios derived from them were not, so the page could publish "6.5x"
    # against data that had moved and nothing would disagree. Found by
    # page_prose_check.py, which walks the page's prose and asks this list.
    ("l2.page.gav.speedup.topdeg", 6.5, 0.15,
     lambda r: gav_speedup(r, "top_degree_mean_ms"),
     "the page's \"worth 6.5x on top degree\""),
    ("l2.page.gav.speedup.samecity", 2.4, 0.15,
     lambda r: gav_speedup(r, "same_city_edges_mean_ms"),
     "the page's \"about 2.4x on the other two\"; same-city arm"),
    ("l1.ingest.perrow_500k", 67147, 1,
     lambda r: ingest_ab("serial_sql"),
     "per-row SQL at the matched 500k scale; reproduced the pre-release 67.3k"),
    ("l1.ingest.bulk_500k", 201647, 1,
     lambda r: ingest_ab("insert_many"),
     "bindings' bulk insert API at 500k; was 177.1k before the re-measure"),
    # E2 atomicity. The trial COUNT is pinned alongside the outcome: the claim
    # this experiment used to publish was "5 of 5", and five trials cannot
    # carry it. If a future run quietly drops back to one trial per rep, the
    # count claim fails even though the outcome would still look perfect.
    ("e2.atomicity.trials.arcade", 200.0, 0.0,
     lambda r: e2_atomicity("arcadedb_e2", "trials"),
     "injections against ArcadeDB, summed over the five repetitions"),
    ("e2.atomicity.trials.composed", 200.0, 0.0,
     lambda r: e2_atomicity("composed_qdrant_neo4j", "trials"),
     "injections against the composed stack, summed over the five repetitions"),
    ("e2.atomicity.torn.arcade", 0.0, 0.0,
     lambda r: e2_atomicity("arcadedb_e2", "torn_count"),
     "ArcadeDB operations left half-updated; the transaction must undo the "
     "interrupted operation every time, so anything above zero is a defect"),
    ("e2.atomicity.torn.surreal", 0.0, 0.0,
     lambda r: e2_atomicity("surrealdb_e2", "torn_count"),
     "SurrealDB operations left half-updated. Zero is the CLAIM, not the "
     "default: the old harness reported zero for this arm while its writes "
     "were never landing, so this is pinned against the fixed harness only"),
    ("e2.atomicity.torn.composed", 200.0, 0.0,
     lambda r: e2_atomicity("composed_qdrant_neo4j", "torn_count"),
     "composed-stack operations left half-updated, measured by counting the "
     "records the two stores disagree about; the count is zero while "
     "operations complete normally, which is what makes this reading mean "
     "something"),
    ("e4.boundary_negative_sizes", 4.0, 0.0,
     lambda r: e4_boundary_negative_sizes(),
     "result sizes whose median container/loopback term is BELOW ZERO, which "
     "is the evidence that this term is under the design's resolution; if a "
     "re-run ever resolves it this claim fails and forces the hedge to be "
     "revisited rather than left standing out of habit"),
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
        # freeze=False: OUT is redirected but RESULTS is not, and main() would
        # otherwise write runs_paper.csv -- the committed record of the
        # PREVIOUS campaign's canonical selection -- from the CURRENT rows.
        # That made the documented read-only check destructive, and
        # irreversibly so, since load_canonical always dedupes to latest.
        M.main(freeze=False)
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

    # Second pass: UNIT-BEARING MEASUREMENTS, not ratios.
    #
    # Ratios were swept because they are the summary-shaped numbers. That was
    # the wrong half. Every number that went stale in the 08-10 audit was a
    # plain measurement restating a table cell: warm p50 "0.96 [0.95--0.96]"
    # against a table saying [0.90--1.24], int8 warm 0.80 against 0.82, builds
    # 5{,}639/2{,}685 against 5{,}585/2{,}673, and Elasticsearch's 10.8 ms at
    # 0.781 recall months after the row was re-measured at 55.8 and 0.997.
    # A ratio sweep cannot see any of those: none of them carries $\times$.
    #
    # This matters more every month than it did once, because the paper
    # re-pins to each stable release (DECISIONS #42): the operands move on a
    # schedule, and a sentence quoting one does not.
    seen2, out2 = set(), []
    unit = r"(?:\\,)?(?:ms|s|GiB|MiB|\\%|%)"
    for m in re.finditer(rf"({num})\s*{unit}\b", body):
        v = float(m.group(1).replace("{,}", ""))
        if v == 0:
            continue
        ctx = " ".join(body[max(0, m.start() - 95):m.end() + 8].split())
        key = (v, ctx[-55:])
        if key in seen2:
            continue
        seen2.add(key)
        if not covered(v):
            out2.append((v, ctx))
    print(f"\n=== unit-bearing measurements with no CLAIM pinning them "
          f"({len(out2)}) ===")
    print("(same standard: not errors, but the set a re-pin must re-read)\n")
    for v, ctx in out2:
        print(f"  {v:<10} ...{ctx[-104:]}")
    print(f"\n{len(seen2)} measurement mentions scanned, "
          f"{len(seen2) - len(out2)} covered")
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
