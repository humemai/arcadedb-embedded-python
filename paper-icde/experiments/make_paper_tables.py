#!/usr/bin/env python3
"""Generate the paper's LaTeX tables (T2-T5) from results/runs.jsonl +
results/l4_tsbs.jsonl.

Canonical-row rule (see CAMPAIGN_2026-07.md): latest row per
(lane, scale, workload, backend, rep), rc==0, paper scales only.
Cells are median [min-max] over N=5 reps. Raw rows are never edited;
rerun this script after the October freeze re-measure.

Outputs: ../latex/tables/t{2,3,4,5}_*.tex + tables_summary.md (prose crib).
"""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "..", "..", ".notes", "papers", "icde-2027", "latex", "tables")

PAPER_SCALES = {"l1": ["medium"], "l1tpc": ["tpch1"], "l2": ["sf1", "sf10"],
                "l3s": ["tiny", "small", "medium"], "l3d": ["small", "deep10m"],
                "e2": ["e2"]}

NAMES = {
    "arcadedb_embedded": "ArcadeDB (emb)", "arcadedb_server": "ArcadeDB (srv)",
    "duckdb": "DuckDB", "postgres": "PostgreSQL",
    "arcadedb_graph_embedded": "ArcadeDB (emb)",
    "arcadedb_graph_server": "ArcadeDB (srv)",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "arcadedb_sparse_embedded": "ArcadeDB (emb, int8)",
    "arcadedb_sparse_embedded_fp32": "ArcadeDB (emb, fp32)",
    "arcadedb_sparse_embedded_nocompact": "ArcadeDB (emb, no settle)",
    "arcadedb_sparse_server": "ArcadeDB (srv)",
    "qdrant_sparse": "Qdrant", "milvus_sparse": "Milvus",
    "elasticsearch_sparse": "Elasticsearch",
    "arcadedb_dense_embedded": "ArcadeDB (emb)",
    "arcadedb_dense_server": "ArcadeDB (srv)",
    "qdrant_dense": "Qdrant", "milvus_dense": "Milvus",
    "chroma_dense": "Chroma", "lancedb_dense": "LanceDB",
    "sqlite_vec_dense": "sqlite-vec", "duckdb_vss_dense": "DuckDB-VSS",
    "arcadedb_e2": "ArcadeDB (one txn)", "surrealdb_e2": "SurrealDB (one txn)",
    "composed_qdrant_neo4j": "Qdrant+Neo4j (composed)",
    "questdb": "QuestDB", "arcadedb": "ArcadeDB (emb)",
}


def load_canonical():
    # Dedupe on PAYLOAD fields, never run_id: pre-2026-07-21 run_ids were not
    # scale-qualified, so different scales collided under one id (the 100k
    # sparse tier was invisible under run_id-keyed dedupe).
    rows = [json.loads(l) for l in open(os.path.join(RESULTS, "runs.jsonl"))
            if l.strip()]
    best = {}
    for r in rows:
        if r.get("rc") != 0:
            continue
        if r["scale"] not in PAPER_SCALES.get(r["lane"], []):
            continue
        k = (r["lane"], r["scale"], r.get("n_docs"), r.get("workload"),
             r["backend"], r["rep"])
        if k not in best or r["ts_utc"] > best[k]["ts_utc"]:
            best[k] = r
    return list(best.values())


def cells(rows, key):
    g = {}
    for r in rows:
        g.setdefault(key(r), []).append(r)
    return g


def fmt(v, unit=""):
    """Compact number: unit-scale k/M above 10^4/10^6 to keep table cells
    inside the column width."""
    if v is None:
        return "--"
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.2f}M{unit}"
    if a >= 1000:
        return f"{v / 1e3:.1f}k{unit}"
    if a >= 100:
        return f"{v:.0f}{unit}"
    if a >= 1:
        return f"{v:.2f}{unit}"
    return f"{v:.3f}{unit}"


def fmtb(v):
    """Bracket endpoints: one step coarser than fmt to save width."""
    a = abs(v)
    if a >= 1000:
        return f"{v / 1e3:.1f}k" if a < 1e6 else f"{v / 1e6:.2f}M"
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}k"
    if a >= 100:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.1f}"
    return f"{v:.2f}"


def mmm_rec(rs, field="recall_at_10"):
    """Recall needs one fixed precision: fmt/fmtb switch format at the 1.0
    boundary, so 0.9999 and 1.0 rendered as '1.00' and '1.0' and a
    degenerate range printed as '1.000 [1.00--1.0]'."""
    v = [r[field] for r in rs if isinstance(r.get(field), (int, float))]
    if not v:
        return "--"
    med, lo, hi = st.median(v), min(v), max(v)
    if f"{lo:.3f}" == f"{hi:.3f}":
        return f"{med:.3f}"
    return f"{med:.3f} [{lo:.3f}--{hi:.3f}]"


def _unfmt(s):
    """Parse a rendered cell back to a number, for self-checks only."""
    s = s.strip()
    mult = 1.0
    if s.endswith("M"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("k"):
        mult, s = 1e3, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def mmm(rs, field, scale=1.0):
    v = [r[field] * scale for r in rs if isinstance(r.get(field), (int, float))]
    if not v:
        return "--"
    mv, lov, hiv = st.median(v), min(v), max(v)
    med, lo, hi = fmt(mv), fmtb(lov), fmtb(hiv)
    # fmtb is deliberately one step coarser than fmt to save column width, and
    # that can round an endpoint PAST the median: reps [3.98, 3.95, 4.20, 4.04,
    # 3.98] render as "3.98 [4.0--4.2]", a median outside its own range. Every
    # number there is individually correct and the pair still reads as an
    # error, which is the worst kind of table defect. Fall back to the median's
    # precision for the endpoints whenever the coarse rendering would not
    # contain it. Same failure mmm_rec documents for recall, one band down.
    lo_v, hi_v = _unfmt(lo), _unfmt(hi)
    if (lo_v is not None and lo_v > mv) or (hi_v is not None and hi_v < mv):
        lo, hi = fmt(lov), fmt(hiv)
    if lo == hi:  # degenerate range at rendered precision
        return med
    return f"{med} [{lo}--{hi}]"


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(body)
    print("wrote", name)


def tabular_table(rows):
    l1 = [r for r in rows if r["lane"] == "l1"]
    tpc = [r for r in rows if r["lane"] == "l1tpc"]
    order = ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres"]
    lines = [r"\begin{tabular}{lrrrr}", r"\toprule",
             r"System & OLTP (ops/s) & Ins.\ p99 (ms) & "
             r"Q1 (ms) & Q6 (ms) \\", r"\midrule"]
    for be in order:
        oltp = [r for r in l1 if r["backend"] == be and r["workload"] == "oltp"]
        tq = [r for r in tpc if r["backend"] == be and r["workload"] == "olap"]
        lines.append(" & ".join([
            NAMES[be],
            mmm(oltp, "oltp_ops_per_s"), mmm(oltp, "insert_p99_ms"),
            mmm(tq, "q1_ms"), mmm(tq, "q6_ms")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t2_tabular.tex", "\n".join(lines) + "\n")


def graph_table(rows):
    l2 = [r for r in rows if r["lane"] == "l2"]
    order = ["arcadedb_graph_embedded", "arcadedb_graph_server",
             "neo4j_graph", "ladybug_graph"]
    lines = [r"\begin{tabular}{llrrr}", r"\toprule",
             r"System & Scale & 1-hop p50 (ms) & 1-hop p99 (ms) & "
             r"2-hop p99 (ms) \\", r"\midrule"]
    for be in order:
        for sc in ("sf1", "sf10"):
            g = [r for r in l2 if r["backend"] == be and r["scale"] == sc
                 and r["workload"] == "oltp"]
            if not g:
                continue
            lines.append(" & ".join([
                NAMES[be], sc.upper(),
                mmm(g, "hop1_p50_ms"), mmm(g, "hop1_p99_ms"),
                mmm(g, "hop2_p99_ms")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t3_graph.tex", "\n".join(lines) + "\n")


def _sparse_full_rows():
    """8.84M Big-ANN tier for the embedded arcade row (N=5, dev20 line).
    Comparators at this tier come from the canonical runner rows."""
    import glob
    out = []
    for fp in glob.glob(os.path.join(RESULTS, "sparse_full", "l3s_full_r*.json")):
        out.append(json.load(open(fp)))
    return out


def _dev15_sparse_rows():
    """Rolling-update overlay: N=5 dev15 cells for the embedded int8 config
    (verify5411 re-runs after the append-only txn-lane fix; supersedes the
    dev6/verify6 overlay). Same harness, same data."""
    import glob
    out = {"tiny": [], "small": []}
    for sc in out:
        for fp in glob.glob(os.path.join(RESULTS, "verify5411",
                                         f"l3s_dev15_bigann_{sc}_r*.json")):
            out[sc].append(json.load(open(fp)))
    return out


# n_docs -> tier, so a released overlay can be read without parsing filenames.
_SPARSE_TIER_BY_DOCS = {100_000: "tiny", 1_000_000: "small", 8_841_823: "medium"}


def _released_sparse_rows(subdir, tag):
    """Overlay for a released wheel whose run wrote every tier into ONE
    directory (queue30 onward), returning {tier: [rows]} for all three.

    The tier is taken from ``n_docs`` in the JSON rather than from the
    filename. This file had grown one bespoke reader per release, each
    encoding that release's naming, which makes the next release's layout a
    guess; ``n_docs`` is written by the lane itself and cannot drift from the
    data it describes. A file whose n_docs matches no known tier is skipped
    rather than mislabelled, because a silently misfiled row would land in the
    wrong table column.
    """
    return _sparse_rows_by_docs(subdir, f"l3s_{tag}_*_r*.json")


def _sparse_rows_by_docs(subdir, pattern):
    """{tier: [rows]} for any sparse overlay, keyed by n_docs not by filename.

    Split out of _released_sparse_rows because a second layout arrived
    (queue60 writes ``<arm>_<scale>_r<rep>.json``) and the alternative was the
    bespoke-reader-per-release habit the docstring above already objects to.
    Only the glob differs; the tier still comes from the lane's own n_docs.
    """
    import glob
    out = {}
    for fp in glob.glob(os.path.join(RESULTS, subdir, pattern)):
        d = json.load(open(fp))
        tier = _SPARSE_TIER_BY_DOCS.get(d.get("n_docs"))
        if tier is None:
            continue
        out.setdefault(tier, []).append(d)
    return out


def _t4dev23_rows(arm="int8"):
    """queue60's dev23 re-measure, but only once ALL THREE tiers are present.

    The point of that run is to put T4's ArcadeDB row on one line at N=5 with
    conditions recorded. Taking it tier by tier as the cells arrive would do
    the opposite: dev23 tiny and small beside a dev22 medium is a version mix
    inside one row, which is the defect this file falls back rather than
    commits everywhere else. All or nothing.
    """
    got = _sparse_rows_by_docs("t4dev23", f"{arm}_*_r*.json")
    if all(len(got.get(t, [])) >= 5 for t in ("tiny", "small", "medium")):
        return got
    return {}


def _dev21_sparse_rows():
    """Released-wheel overlay for the embedded int8 config on 26.8.1.dev21,
    which carries all three merged sparse rounds (#5388 copy bound,
    #5467 r1 primitive cursors, #5467 r2 memoised block bounds) plus #5473's
    parallel-array top-K heap.

    This supersedes the dev15 overlay wherever it is present. It exists so the
    table can report the current engine from a RELEASED artifact: the same
    numbers were first measured on a locally compiled wheel for the upstream
    verification, and those belong in prose, not here.
    Empty until the dev21 re-run lands, in which case the dev15 overlay stands.
    """
    import glob
    out = {"tiny": [], "small": []}
    for sc in out:
        for fp in glob.glob(os.path.join(RESULTS, "dev21_sparse",
                                         f"l3s_dev21_{sc}_r*.json")):
            out[sc].append(json.load(open(fp)))
    return {sc: v for sc, v in out.items() if v}


def _dev21_sparse_full_rows():
    """8.84M Big-ANN tier on dev21. Supersedes _sparse_full_rows (dev20)."""
    import glob
    return [json.load(open(fp)) for fp in
            glob.glob(os.path.join(RESULTS, "dev21_sparse_full",
                                   "l3s_dev21_full_r*.json"))]


def sparse_table(rows):
    l3s = [r for r in rows if r["lane"] == "l3s"]
    # Prefer the newest released line per tier; fall back rather than mix.
    # Newest released line wins per tier, falling back rather than mixing.
    # dev22 is the first RELEASED artifact carrying #5518 (sparse parallel
    # top-K), so wherever it is present it supersedes dev21.
    dev22 = _released_sparse_rows("dev22_sparse", "26.8.1.dev22")
    dev15 = _dev15_sparse_rows()
    dev15.update(_dev21_sparse_rows())
    dev15.update({t: v for t, v in dev22.items() if t in ("tiny", "small") and v})
    full = dev22.get("medium") or _dev21_sparse_full_rows() or _sparse_full_rows()
    # queue60's dev23 re-measure supersedes all of the above when it is
    # complete: one line for every tier, N=5 including the 8.84M cell that
    # T4's caption has to except today, and cpuset/heap/mem_cap recorded.
    # Returns {} until all three tiers have five reps, so a partial run cannot
    # put dev23 tiny beside dev22 medium inside a single row.
    dev23 = _t4dev23_rows("int8")
    if dev23:
        dev15.update({t: dev23[t] for t in ("tiny", "small")})
        full = dev23["medium"]
    order = ["arcadedb_sparse_embedded", "qdrant_sparse", "milvus_sparse",
             "elasticsearch_sparse"]
    tiers = (("tiny", "100k"), ("small", "1M"), ("medium", "8.84M"))
    # Tiers as column groups: one row per system keeps the table to four
    # data rows instead of twelve and puts the scaling trend on one line.
    lines = [r"\begin{tabular}{l" + "rrr" * len(tiers) + "}", r"\toprule",
             "System & " + " & ".join(
                 r"\multicolumn{3}{c}{%s}" % lab for _, lab in tiers) + r" \\"]
    cols = "".join(r"\cmidrule(lr){%d-%d}" % (2 + 3 * i, 4 + 3 * i)
                   for i in range(len(tiers)))
    lines.append(cols)
    lines.append(" & " + " & ".join(["p50 & p99 & R@10"] * len(tiers)) + r" \\")
    lines.append(r"\midrule")
    for be in order:
        cells = [NAMES[be]]
        for sc, _lab in tiers:
            g = [r for r in l3s if r["backend"] == be and r["scale"] == sc]
            if sc == "medium":
                # medium holds two corpora: the retired synthetic 10M and
                # Big-ANN's 8.84M. Mixing them is the #5411 error in table form.
                g = [r for r in g if r.get("n_docs") == 8_841_823]
            if be == "arcadedb_sparse_embedded" and sc in ("tiny", "small") and dev15.get(sc):
                g = dev15[sc]
            elif be == "arcadedb_sparse_embedded" and sc == "medium":
                g = full
            if not g:
                cells += ["--", "--", "--"]
                continue
            cells += [mmm(g, "query_p50_ms"), mmm(g, "query_p99_ms"), mmm_rec(g)]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t4_sparse.tex", "\n".join(lines) + "\n")


def _dev16_dense_rows(prefix="fp32_dev20", subdir="verify5412b"):
    """Rolling-update overlay for the dense rows: N=4 warm-cache query
    passes over one current-line build each. Current line is 26.8.1.dev20
    (verify5412b), which carries both #5412 fixes: the shared warm search
    cache and the auto-sized graph-build cache. The server row still comes
    from the matched re-run in verify5413. Pass 1 (cold, cache filling) is
    disclosed in prose, not averaged in. INT8 row is the 16 GiB-heap cell,
    its operating point; the matched-24 GiB ablation is prose only.
    Field names mapped to the campaign schema."""
    import glob
    out = []
    for fp in glob.glob(os.path.join(RESULTS, subdir,
                                     f"{prefix}_rep*.json")):
        r = json.load(open(fp))
        if r.get("rep", 0) < 2:
            continue
        out.append({"build_s": r["build_s"], "query_p50_ms": r["p50"],
                    "query_p99_ms": r["p99"],
                    "recall_at_10": r["recall_at_10"]})
    return out


def dense_ts_table(rows):
    l3d = [r for r in rows if r["lane"] == "l3d" and r["scale"] == "deep10m"]
    dev16 = _dev16_dense_rows()
    order = ["arcadedb_dense_embedded", "arcadedb_dense_server", "qdrant_dense",
             "milvus_dense", "chroma_dense", "lancedb_dense",
             "sqlite_vec_dense", "duckdb_vss_dense"]
    lines = [r"\begin{tabular}{lrrrr}", r"\toprule",
             r"\multicolumn{5}{l}{\textit{Dense ANN, DEEP-10M "
             r"(10M$\times$96d), degree-matched}} \\",
             r"System & Build (s) & p50 (ms) & p99 (ms) & Recall@10 \\",
             r"\midrule"]
    int8 = _dev16_dense_rows("int8_dev20")
    # Post-fix server re-measure (#109). verify5413's image (build 8bd63ccc8,
    # 2026-07-25 19:58) sat between the commit that bounded the HNSW build
    # cache and the one that auto-sized it, so its 13,349 s build was a
    # version artifact reported as a deployment cost. srv109 is the same cell
    # on build bd0ba0d233 (2026-07-31), past the fix: 3,825 s, with p50 and
    # recall unchanged, which is what a BUILD-cache regression predicts.
    # Falls back rather than mixing if the new overlay is absent.
    srv = _dev16_dense_rows("srv109", "srv109") or \
        _dev16_dense_rows("srv5413", "verify5413")
    for be in order:
        g = [r for r in l3d if r["backend"] == be]
        if be == "arcadedb_dense_embedded" and dev16:
            g = dev16  # dev16 overlay (shared warm cache), caption discloses
        if be == "arcadedb_dense_server" and srv:
            g = srv  # matched-config re-run (#5413), caption discloses
        if not g:
            continue
        lines.append(" & ".join([
            NAMES[be], mmm(g, "build_s"), mmm(g, "query_p50_ms"),
            mmm(g, "query_p99_ms"), mmm(g, "recall_at_10")]) + r" \\")
        if be == "arcadedb_dense_embedded" and int8:
            # INT8 sibling row: same line, 16 GiB heap (vs 24), see prose
            lines.append(" & ".join([
                r"ArcadeDB (emb, int8, 16\,GiB)", mmm(int8, "build_s"),
                mmm(int8, "query_p50_ms"), mmm(int8, "query_p99_ms"),
                mmm(int8, "recall_at_10")]) + r" \\")
    ts = [json.loads(l) for l in open(os.path.join(RESULTS, "l4_tsbs.jsonl"))
          if l.strip()]
    lines += [r"\midrule",
              r"\multicolumn{5}{l}{\textit{Time series, TSBS cpu-only "
              r"(2.59M points)}} \\",
              r"System & Ingest (pts/s) & Last point (ms) & 1h bucket (ms) & "
              r"12h global (ms) \\", r"\midrule"]
    import glob
    # Native TimeSeries on released dev21 via the IDIOMATIC ingest path, which
    # supersedes the batch1 rows. Those were measured through the adapter's
    # per-element conversion (Python lists into an Object[] column), which was
    # our defect and not the engine's: numpy arrays reach the binding's bulk
    # path, and routing each batch through the engine's primitive
    # TimeSeriesBatch (#5474) reaches it fully. Reporting the list arm prices
    # our own adapter rather than the engine, and contradicts the prose, which
    # already cites 1.73M pts/s and a 1.12x DuckDB lead.
    # The full decomposition stays in the text: lists 417k, arrays 1.29M,
    # arrays + TimeSeriesBatch 1.73M.
    # dev23 re-measure, N=5, conditions stamped, NO settle. The settle choice
    # is the load-bearing one: nothing else in this block settles (l4_tsbs.py
    # has no forcemerge, flush or checkpoint for DuckDB, QuestDB or ArcadeDB's
    # document path), and the superseded dev21 files carry no settle_s key at
    # all, so they were the unsettled treatment too. A settled ArcadeDB row
    # beside unsettled comparators would take a one-sided advantage, and here
    # that advantage is large and two-directional: settling buys 2.23x on the
    # 12-hour aggregation and COSTS 2.5x on last-point (8.2x unbounded),
    # measured as an interleaved A/B on one engine (results/ts59).
    #
    # The unsettled q_global lands within 1% of the dev21 row it replaces
    # (29.86 vs 29.56 ms), which is the control: the two setups are otherwise
    # matched, so the last-point and bucket gains below are engine changes
    # (#5414/#5416) and not harness drift.
    #
    # Last point reports the UNBOUNDED form. T5 used to print a one-hour
    # recency window as a workaround for an unbounded query that scanned the
    # tag's whole series; on this line the unbounded form is not merely
    # affordable but FASTER than the window it replaced (0.69 vs 0.94 ms),
    # so the workaround is retired rather than carried with a footnote.
    native = [json.load(open(fp)) for fp in
              glob.glob(os.path.join(RESULTS, "ts59", "nosettle_r*.json"))]
    last_key = "q_last_unbounded_ms"
    if not native:  # fall back rather than mix lines
        native = [json.load(open(fp)) for fp in
                  glob.glob(os.path.join(RESULTS, "dev21_ts",
                                         "ts_dev21_prim_r*.json"))]
        last_key = "q_last_ms"
    if not native:
        native = [json.load(open(fp)) for fp in
                  glob.glob(os.path.join(RESULTS, "batch1", "l4n_r*.json"))]
        last_key = "q_last_ms"
    if native:
        lines.append(" & ".join([
            r"ArcadeDB (native TS)", mmm(native, "ingest_pts_per_s"),
            mmm(native, last_key), mmm(native, "q_range_ms"),
            mmm(native, "q_global_ms")]) + " " + chr(92)*2)
    for be in ("arcadedb", "duckdb", "questdb"):
        g = [r for r in ts if r["backend"] == be]
        label = ("ArcadeDB (document path)" if be == "arcadedb"
                 else NAMES[be])
        lines.append(" & ".join([
            label, mmm(g, "ingest_pts_per_s"), mmm(g, "q_last_ms"),
            mmm(g, "q_range_ms"), mmm(g, "q_global_ms")]) + " " + chr(92)*2)
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t5_dense_ts.tex", "\n".join(lines) + "\n")


def e2_summary(rows):
    e2 = [r for r in rows if r["lane"] == "e2"]
    out = ["# E2 + prose numbers crib (not a table; quoted in text)\n"]
    for be in ("arcadedb_e2", "surrealdb_e2", "composed_qdrant_neo4j"):
        h = [r for r in e2 if r["backend"] == be and r["workload"] == "hybrid"]
        a = [r for r in e2 if r["backend"] == be and r["workload"] == "atomicity"]
        torn = [r.get("torn_state") for r in a]
        out.append(f"- {NAMES[be]}: hybrid p50 {mmm(h, 'hybrid_p50_ms')} ms, "
                   f"p99 {mmm(h, 'hybrid_p99_ms')} ms; torn state "
                   f"{sum(bool(t) for t in torn)}/{len(torn)} trials")
    write("tables_summary.md", "\n".join(out) + "\n")


def main():
    rows = load_canonical()
    print(f"{len(rows)} canonical rows")
    tabular_table(rows)
    graph_table(rows)
    sparse_table(rows)
    dense_ts_table(rows)
    e2_summary(rows)


if __name__ == "__main__":
    main()
