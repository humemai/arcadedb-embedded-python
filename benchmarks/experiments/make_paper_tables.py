#!/usr/bin/env python3
"""Generate the paper's LaTeX tables (T2-T5) from results/runs.jsonl +
results/l4_tsbs.jsonl.

Canonical-row rule (see CAMPAIGN_2026-07.md): latest row per
(lane, scale, workload, backend, rep), rc==0, paper scales only.
Cells are median [min-max] over N=5 reps. Raw rows are never edited;
rerun this script after the October freeze re-measure.

Outputs: ../latex/tables/t{2,3,4,5}_*.tex + tables_summary.md (prose crib).
"""
import collections
import json
import os
import re
import sys
import statistics as st
from decimal import Decimal, ROUND_HALF_UP

# A pre-release engine, in any of the spellings the harness has produced:
# "26.8.1.dev0", "26.8.1.dev24", "server:26.8.1-SNAPSHOT". Matched rather than
# equality-tested against a release list, because the failure to guard against
# is a version nobody thought to enumerate.
_DEV_RE = re.compile(r"dev\d|SNAPSHOT", re.I)

# The commit this campaign froze, as a short or full sha. When set, a
# pre-release engine becomes publishable IF AND ONLY IF the row identifies
# itself by commit and that commit is this one.
#
# WHY THIS EXISTS. The version test below is a STALENESS guard wearing a
# release-policy costume: what it actually caught was 20 canonical rows still
# carrying an old dev build after a re-measure. Under commit pinning
# (DECISIONS #49) every local build reports "26.9.1.dev0" whichever commit
# produced it, so the version test would reject the entire campaign while
# still not distinguishing this build from last week's.
#
# Matching on engine_commit is strictly stronger than matching on version: it
# rejects the stale dev rows the old test was written for AND the case the old
# test could never see, which is two different builds sharing one version
# string. Unset, behaviour is exactly as before: every pre-release row drops.
_PINNED_COMMIT = os.environ.get("BENCH_ENGINE_COMMIT", "").strip().lower()

# THE CORPUS EACH PUBLISHED TIER IS MEASURED ON, as (n_docs, dims).
#
# Two different corpora have shared one scale name. The sparse lane's synthetic
# generator (sparse_common: 30,000 dims, medium = 10,000,000 docs) was retired
# in favour of the real Big-ANN'23 corpus (bigann_sparse: 30,109 dims, medium =
# 8,841,823 docs), and rows from both survive in runs.jsonl under scale
# "medium". They do not collide on the canonical key, which already contains
# n_docs -- BOTH are admitted, and a consumer that groups without n_docs then
# pools them. export_web.py did exactly that, publishing a Qdrant p50 of 10.533
# ms that is the median across a ~5.2 cluster and a ~16.1 cluster and belongs
# to no run that happened, under a label reading "8.84M".
#
# The fingerprint is (n_docs, dims) and not n_docs alone, because at tiny and
# small BOTH corpora hold 100,000 and 1,000,000 docs. n_docs alone is vacuous
# at two tiers of three; dims is what separates them there.
#
# Literals, not imports from the lane modules: run_gates() launches the
# checkers with sys.executable, and `python3 -c "import bigann_sparse"` fails
# on numpy outside the venv. fairness_check F10b compares these against the
# modules so the duplication is checked rather than trusted.
PAPER_CORPUS = {
    ("l3s", "tiny"):   (100_000, 30_109),
    ("l3s", "small"):  (1_000_000, 30_109),
    ("l3s", "medium"): (8_841_823, 30_109),
}

# Reset per load_canonical() call, never cumulative: claims_check calls the
# loader eleven times in one process, and a counter that survives the call
# reports 110 exclusions where ten happened.
CORPUS_EXCLUDED = collections.Counter()


def _commit_matches(row_commit):
    """Does this row's engine_commit identify the pinned build?

    Compared on the first 9 hex characters, because the harness stamps a short
    sha while a jar's arcadedb.properties carries all 40, and a campaign that
    fails its own gate on sha length would be fixed by loosening the gate.
    """
    if not _PINNED_COMMIT:
        return False
    rc = str(row_commit or "").strip().lower()
    if len(rc) < 9:
        return False
    return rc[:9] == _PINNED_COMMIT[:9]

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
# The paper source is deliberately not in this repository. Point
# BENCH_PAPER_DIR at the directory holding paper.tex and its generated
# tables/ and figures/ subdirectories.
_PAPER_DIR = os.environ.get(
    "BENCH_PAPER_DIR", os.path.join(HERE, "..", "..", "paper"))
OUT = os.path.join(_PAPER_DIR, "tables")

# Every published cell is N=5. A row outside 1..5 is a probe, not a repetition;
# see the rep filter in load_canonical for the 34 rows that made this explicit.
MAX_REP = 5

# A LANE MISSING FROM THIS MAP IS SILENTLY DELETED, not flagged. load_canonical
# drops any row whose (lane, scale) is not listed, via PAPER_SCALES.get(lane, []),
# so an unlisted lane resolves to the empty list and every one of its rows goes.
#
# That is not hypothetical. `lifecycle` and `l4` were registered in runner.LANES,
# run to completion, and stamped correctly, and every row was discarded here
# before any table, figure or gate saw it: 117 lifecycle rows worth ~18 h of
# bench time and 20 l4 rows. The F11 close-cost gate then reported
# "NOT CHECKED: no lifecycle rows" and returned 0, i.e. PASS, because the rows it
# was written to check had already been filtered out upstream of it.
#
# Adding a lane here is therefore step 1 of 3. Step 2 is export_web.SCALE_LABELS,
# which SystemExits on a missing tier by design. Step 3 is fairness_check
# .LANE_SCRIPT, so F6b can tell a lane script from a bespoke driver.
PAPER_SCALES = {"l1": ["medium"], "l1tpc": ["tpch1"], "l2": ["sf1", "sf10"],
                "l3s": ["tiny", "small", "medium"], "l3d": ["small", "deep10m"],
                "e2": ["e2"],
                "l4": ["ts100"],
                "lifecycle": ["lc10k", "lc100k", "lc1m", "lc10m"]}

NAMES = {
    "arcadedb_embedded": "ArcadeDB (emb)", "arcadedb_server": "ArcadeDB (srv)",
    "duckdb": "DuckDB", "postgres": "PostgreSQL",
    # the buffer-pool ablation; named so a table cannot print a raw backend id
    "postgres_tuned": "PostgreSQL (tuned)",
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
    # the dense server overlay stamps quantization=fp32
    "arcadedb_dense_server": "ArcadeDB (srv, fp32)",
    # DENSE ROWS STATE WHAT THEY STORE, all of them. T5 labelled only our two
    # arms "(emb, fp32)" and "(emb, int8)", so quantization read as an ArcadeDB
    # peculiarity and every unlabelled row read as full precision. LanceDB is
    # not: it builds IVF_HNSW_SQ, int8 scalar-quantized, its only HNSW offering.
    # That makes its 0.932 recall the same kind of number as our int8 arm's
    # 0.943, where Chroma's 0.934 at fp32 is a different kind. Read from the
    # adapters in l3d_dense.py, never from the rows' `quantization` field, which
    # echoes BENCH_DENSE_QUANT and reports "fp32" for every comparator.
    "qdrant_dense": "Qdrant (fp32)", "milvus_dense": "Milvus (fp32)",
    # The int8 arms. Every dense row already states its precision, which is why
    # LanceDB reads "(int8)" -- so a quantized arm that printed a bare engine
    # name would be the one row in the table whose precision a reader had to
    # infer.
    "arcadedb_dense_embedded_int8": "ArcadeDB (emb, int8)",
    "qdrant_dense_int8": "Qdrant (int8)", "milvus_dense_int8": "Milvus (int8)",
    "chroma_dense": "Chroma (fp32)", "lancedb_dense": "LanceDB (int8)",
    "sqlite_vec_dense": "sqlite-vec (fp32)",
    "duckdb_vss_dense": "DuckDB-VSS (fp32)",
    "arcadedb_e2": "ArcadeDB (one txn)", "surrealdb_e2": "SurrealDB (one txn)",
    "composed_qdrant_neo4j": "Qdrant+Neo4j (composed)",
    "questdb": "QuestDB", "arcadedb": "ArcadeDB (emb)",
}


def load_canonical(apply_corpus=True):
    CORPUS_EXCLUDED.clear()
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
        # A published cell must come from the SERIAL tier. The sweep tier runs
        # N workers on disjoint cpuset shards, which shows up here as a
        # partial cpuset like "0-5". Sweeps did run (l2 sf1, l2 sf10, l3s
        # micro), and none of them currently reaches a table -- but only
        # because the serial re-runs happened to come later, and this dedupe
        # keys on latest timestamp and has no idea what a cpuset is. A sweep
        # run after a serial one would have walked straight into the tables.
        # Dropped BEFORE the dedupe, so a sharded row cannot shadow the good
        # serial row it would otherwise outrank on ts_utc. See FAIRNESS.md F2.
        cpuset = str(r.get("cpuset"))
        if cpuset not in ("0-11", "None"):
            continue
        # A PUBLISHED CELL HAS reps 1..N, AND NOTHING ELSE. `rep` is part of the
        # canonical key below, so an out-of-range rep does not supersede
        # anything -- it ADDS a repetition to a finished cell, silently, and the
        # median and the printed [min--max] both move.
        #
        # Not hypothetical: 34 rows carrying rep=9 sit in runs.jsonl from
        # overnight probe batches on 2026-08-15 (01:00-02:55 UTC), written at
        # tier=paper before --results-file existed to send scratch elsewhere.
        # Six batches of four l2/sf1 backends plus six l1/small PostgreSQL
        # rows. They would have turned four graph cells into N=6, and one of
        # them is decisive on its own: ladybug rep 9 ran 0.18.1 while reps 1-5
        # of the same cell ran 0.19.1, so a single cell would have mixed two
        # comparator releases -- exactly what this round's pinning work
        # existed to prevent.
        #
        # The rows are KEPT in runs.jsonl, which is append-only and is the
        # record of what was run. They are excluded from what gets published.
        if not isinstance(r.get("rep"), int) or not 1 <= r["rep"] <= MAX_REP:
            continue
        # NO PRE-RELEASE ENGINE REACHES A TABLE. DECISIONS #42: every ICDE
        # number comes from a monthly stable release. That was policy enforced
        # by remembering, and remembering failed: 20 canonical rows were still
        # on 26.8.1.dev0 and .dev3 after the whole re-measure campaign.
        #
        # They survived because the canonical key includes n_docs and they sit
        # at the RETIRED 10M synthetic sparse tier, so the 8.84M Big-ANN rows
        # that replaced them are a different key and never superseded them.
        # T4's explicit n_docs == 8_841_823 filter kept them off the page, but
        # that is one hard-coded line standing between a dev number and a
        # table, and it only covers the tier someone thought to hard-code.
        if _DEV_RE.search(str(r.get("engine_version", ""))) \
                and not _commit_matches(r.get("engine_commit")):
            continue
        # A sparse cell with no recall number cannot be published -- the paper
        # reports recall beside every latency -- and the reason one is missing
        # is not benign. l3_sparse.py:22 falls back to the SYNTHETIC generator
        # unless BENCH_SPARSE_SOURCE=bigann is exported, and the synthetic path
        # ships no ground truth, so its rows carry gt_missing and
        # recall_at_10=None. On 2026-08-07 a queue script that omitted that
        # export wrote 94 such rows. At medium they were distinguishable
        # (n_docs 10,000,000 against Big-ANN's 8,841,823, and n_docs is in the
        # key below); at tiny and small BOTH corpora hold 100k and 1M docs, so
        # the synthetic rows outranked the real ones on ts_utc and would have
        # walked into T4 carrying no recall at all. Exactly the sweep-tier
        # shape above: a later run under a different protocol shadowing a good
        # one. Dropped at the same point, before the dedupe, for the same
        # reason -- a row that cannot be published must not be able to shadow.
        if r["lane"] == "l3s" and r.get("recall_at_10") is None:
            continue
        # THE ROW MUST BE ON THE CORPUS ITS TIER PUBLISHES. See PAPER_CORPUS:
        # a retired synthetic corpus shares scale names with the real one, and
        # both survive the canonical key because that key contains n_docs and
        # so admits each as its own cell. The pooling happens downstream, in
        # any consumer that groups without n_docs, which is why the rule
        # belongs here rather than in one consumer.
        #
        # apply_corpus=False still COUNTS but does not drop, so fairness F10
        # can see the pooled population it exists to fail on instead of
        # inspecting a set the filter has already cleaned.
        want = PAPER_CORPUS.get((r["lane"], r["scale"]))
        if want is not None:
            got = (r.get("n_docs"), r.get("dims"))
            if got != want:
                CORPUS_EXCLUDED[(r["lane"], r["scale"], r["backend"],
                                 str(got))] += 1
                if apply_corpus:
                    continue
        # Elasticsearch must prove the heap it ran, not assert it. Until
        # 2026-08-08 runner.py hardcoded "ES_JAVA_OPTS=-Xms2g -Xmx4g" for this
        # backend alone, so ES ran 4g at tiny, small AND medium while its
        # comparators scaled 4g -> 8g -> 16g: a quarter of the memory at medium,
        # in the direction that flatters ArcadeDB, in this paper's centrepiece
        # table.
        #
        # Those rows are INDISTINGUISHABLE from correct ones by any other
        # field, because `heap` stamps what the cell REQUESTED -- they say
        # heap=16g. The only witness is server_heap, which observe_server()
        # reads out of the container's own Env, and which did not exist when
        # they were written. So absence of that witness is the signal.
        #
        # A missing cell in T4 is honest; a 4g cell wearing a 16g label is not.
        # If the re-measure fails at a tier, that tier shows a gap.
        #
        # Both keys must be PRESENT as well as equal: three rows carried
        # heap=None and server_heap=None, which an equality test alone passes
        # by matching nothing against nothing. Absent is not agreement.
        if r["backend"] == "elasticsearch_sparse":
            if not r.get("server_heap") or r.get("server_heap") != r.get("heap"):
                continue
            # And it must have retrieved without index-time pruning. ES 9.1
            # turned that on by default for every new sparse_vector field,
            # using thresholds Elastic tuned on ELSERv2; this corpus is
            # SPLADE-cocondenser, and the cost is measured in our own rows:
            #
            #     ES 9.0.0 (predates the default)  recall  0.991 - 0.9985
            #     ES 9.4.1 (pruning on)            recall  0.725 - 0.929
            #
            # Qdrant and Milvus retrieve exactly and score ~1.0 on the same
            # queries, so a pruned row prints 0.75 beside their 1.0 and reads
            # as "Elasticsearch is bad at sparse retrieval". It is not: it is
            # one model's thresholds applied to another model's vectors.
            #
            # es_prune is recorded by l3_sparse.py, so False is a POSITIVE
            # statement that pruning was off. Absent means the row predates
            # the field and cannot make that statement -- including the rows
            # from the heap re-run, which fixed the heap while still pruning.
            # Those are exactly the rows that would otherwise slip through the
            # check above, having finally got their heap right.
            if r.get("es_prune") is not False:
                continue
        # A SERVER row must be able to say which engine served it. The dev
        # guard above reads engine_version, and for served backends that field
        # is whatever the adapter managed to scrape: l2 and l3s query the
        # server and get "server:26.8.1 (build 727aa45...)", while l1 records
        # "server:latest", l1tpc records "server", and l3d records "unknown
        # (PackageNotFoundError)". None of those three is a version, so the
        # pre-release guard cannot see through them and a row from any engine
        # line passes.
        #
        # The witness that does exist is server_image_ref, the pinned
        # image@sha256 the runner actually started. Every server row from the
        # released campaign carries the same digest on arcadedata/arcadedb:
        # 26.8.1, which is proof independent of the label. Five rows carry
        # NEITHER: l3s medium from 2026-07-07, "server:latest" with no digest
        # at the retired 10M synthetic corpus, which is the same stale-tier
        # leak the dev guard was written for wearing a label that guard cannot
        # read. They hold recall 0.993 and would answer a recall selector.
        #
        # So: an uninformative label is tolerated when a digest backs it, and
        # refused when nothing does.
        if "server" in str(r.get("backend", "")):
            ver = str(r.get("engine_version") or "")
            named = bool(re.search(r"\d+\.\d+\.\d+", ver))
            if not named and "@sha256:" not in str(r.get("server_image_ref") or ""):
                continue
        # `gav` separates the graph lane's two OLAP arms. BENCH_GAV=0 runs the
        # analytical queries WITHOUT the Graph Analytical View, which is the
        # ablation the paper reports, and the runner stamps the same backend
        # for both. Without this term the ablation and the published cell share
        # a key and the newer one wins on ts_utc, so re-running the ablation
        # would overwrite T3 with numbers 2-7x worse and report them as the
        # engine's OLAP performance.
        #
        # `is not False` and not `get("gav", True)`: every OLAP run before the
        # stamp existed built the view, so a missing field means with-view and
        # must land in the SAME bucket as an explicit True. Defaulting the other
        # way would split one N=5 cell into two N=5 cells wearing one label.
        k = (r["lane"], r["scale"], r.get("n_docs"), r.get("workload"),
             r["backend"], r.get("gav") is not False, r["rep"])
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


def _require_paper_dir():
    """Refuse to write tables into a paper directory that does not exist.

    BENCH_PAPER_DIR defaults to <repo>/paper, a placeholder: the paper source
    is deliberately not in this repository. A generator run without the
    variable used to CREATE that placeholder and fill it with a second,
    divergent set of tables, which happened once and went unnoticed because
    nothing builds from there. The reverse is worse: claims_check resolves the
    same default, so once the placeholder exists it verifies the paper's prose
    against those stale copies and reports agreement. Neither failure is
    visible in any output, so refuse the write instead.
    """
    if not os.path.isdir(_PAPER_DIR):
        sys.exit(
            f"BENCH_PAPER_DIR unset or wrong: {os.path.normpath(_PAPER_DIR)} "
            "does not exist.\nSet it to the directory holding paper.tex.")


def write(name, body):
    _require_paper_dir()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    # Do not rewrite an unchanged table. claims_check's figure-freshness guard
    # compares figure mtimes against the newest table mtime, so a regeneration
    # that rewrote byte-identical content marked all five figures stale and
    # told us to redraw them for nothing. A guard that cries wolf on every
    # no-op run is a guard that gets ignored, which is the failure mode this
    # whole file has been finding all day.
    if os.path.exists(path):
        with open(path) as f:
            if f.read() == body:
                print("unchanged", name)
                return
    with open(path, "w") as f:
        f.write(body)
    print("wrote", name)


def tabular_table(rows):
    l1 = [r for r in rows if r["lane"] == "l1"]
    tpc = [r for r in rows if r["lane"] == "l1tpc"]
    order = ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres"]
    # Peak anon from the OLTP rows only. This lane runs OLTP and OLAP over one
    # corpus, and memory is recorded for BOTH, so pooling them would report a
    # median straddling two workloads: PostgreSQL reads 0.119 GiB on OLTP and
    # 0.152 on OLAP, and their midpoint describes neither run. The latency
    # columns are already per-workload by construction.
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"System & OLTP (ops/s) & Ins.\ p99 (ms) & "
             r"Q1 (ms) & Q6 (ms) & Peak anon (GiB) \\", r"\midrule"]
    for be in order:
        oltp = [r for r in l1 if r["backend"] == be and r["workload"] == "oltp"]
        tq = [r for r in tpc if r["backend"] == be and r["workload"] == "olap"]
        # MEDIAN ONLY for Q1/Q6, ranges kept for OLTP and insert p99.
        #
        # Not a space-saving dodge: it puts dispersion where dispersion is
        # informative. Measured spreads across the five reps are
        #   Q1  1.6-4.3%    Q6  2.3-6.5%
        #   OLTP 5.4-17.5%  insert p99 13.6-101.6%  (PostgreSQL's tail)
        # so the analytical columns were spending the width that forced this
        # table under a \resizebox -- rendering it visibly smaller than every
        # other table on its page -- to report that a scan takes about as long
        # as it took last time. The caption states the bound they now carry
        # implicitly, and the artifact has every repetition.
        lines.append(" & ".join([
            NAMES[be],
            mmm(oltp, "oltp_ops_per_s"), mmm(oltp, "insert_p99_ms"),
            fmt(st.median([r["q1_ms"] for r in tq
                           if isinstance(r.get("q1_ms"), (int, float))]))
            if any(isinstance(r.get("q1_ms"), (int, float)) for r in tq) else "--",
            fmt(st.median([r["q6_ms"] for r in tq
                           if isinstance(r.get("q6_ms"), (int, float))]))
            if any(isinstance(r.get("q6_ms"), (int, float)) for r in tq) else "--",
            mmm(oltp, "peak_anon_mib_sum", 1.0 / 1024),
        ]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t2_tabular.tex", "\n".join(lines) + "\n")


def graph_table(rows):
    l2 = [r for r in rows if r["lane"] == "l2"]
    order = ["arcadedb_graph_embedded", "arcadedb_graph_server",
             "neo4j_graph", "ladybug_graph"]
    # Peak anon is the LAST column deliberately: it is a resource axis, not a
    # latency, and putting it beside the p99s invites reading it as one. The
    # field is peak_anon_mib_sum, which for a served backend is server+client
    # and for an embedded one is the single process, so both deployments
    # report the whole engine's footprint rather than half of it.
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"System & Scale & 1-hop p50 (ms) & 1-hop p99 (ms) & "
             r"2-hop p99 (ms) & Peak anon (GiB) \\", r"\midrule"]
    for be in order:
        for sc in ("sf1", "sf10"):
            g = [r for r in l2 if r["backend"] == be and r["scale"] == sc
                 and r["workload"] == "oltp"]
            if not g:
                continue
            lines.append(" & ".join([
                NAMES[be], sc.upper(),
                mmm(g, "hop1_p50_ms"), mmm(g, "hop1_p99_ms"),
                mmm(g, "hop2_p99_ms"),
                mmm(g, "peak_anon_mib_sum", 1.0 / 1024)]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t3_graph.tex", "\n".join(lines) + "\n")


# THE DEV OVERLAY CASCADE LIVED HERE and is deleted, not deprecated.
# _sparse_full_rows, _released_sparse_rows, _sparse_rows_by_docs,
# _t4dev23_rows, _dev15_sparse_rows, _dev21_sparse_rows and
# _dev21_sparse_full_rows each preferred a newer pre-release line per tier
# and fell back to an older one when a directory was missing. That is how a
# table keeps printing pre-release numbers after the release is measured:
# nothing fails, an older branch of the cascade just wins quietly.
#
# Every tier is now measured on one released engine, so there is nothing to
# prefer and nothing to fall back to. Keeping the helpers 'just in case'
# would keep the failure mode alive, since the next missing directory would
# re-arm it. _sparse_2681_rows below refuses instead of falling back.

def _sparse_2681_rows(arm="arcadedb_sparse_embedded"):
    """T4's ArcadeDB rows, from ONE released engine.

    Replaces a six-deep cascade of dev overlays (verify5411=dev0, sparse_full=
    dev20, dev21_sparse, dev21_sparse_full, dev22_sparse, t4dev23) whose whole
    purpose was to prefer the newest dev line per tier and "fall back rather
    than mix". Every tier is now measured on the release at N=5, so there is
    nothing to prefer and nothing to fall back to. The cascade was also the
    mechanism by which T4 kept quoting dev-era numbers after the release was
    re-measured, which is the same defect the dense block had.

    Refuses to return anything unless all three tiers are complete and on one
    version, because a partial return here would silently reinstate exactly
    the mixed-version row this replaced.
    """
    import glob
    out = {}
    for fp in glob.glob(os.path.join(RESULTS, "sparse_2681", "*.json")):
        try:
            r = json.load(open(fp))
        except Exception:
            continue
        if r.get("backend") != arm:
            continue
        out.setdefault(r["scale"], []).append(r)
    tiers = ("tiny", "small", "medium")
    missing = [t for t in tiers if len(out.get(t, [])) < 5]
    if missing:
        raise SystemExit(
            "REFUSING to write t4: sparse_2681 has fewer than 5 reps at %s. "
            "The dev-overlay cascade this replaced is gone on purpose; "
            "falling back to it would reinstate mixed-version rows."
            % ", ".join(missing))
    versions = {str(r.get("engine_version")) for t in tiers for r in out[t]}
    if versions != {"26.8.1"}:
        raise SystemExit("REFUSING to write t4: sparse_2681 is not one "
                         "released version: %s" % sorted(versions))
    return out


def sparse_table(rows):
    l3s = [r for r in rows if r["lane"] == "l3s"]
    # ArcadeDB: one released engine, every tier, N=5. Comparators stay in
    # runs.jsonl and are untouched: they are not ArcadeDB runs, their own
    # versions did not change, and the F9 control re-runs one of them to
    # license keeping the other two.
    arc = _sparse_2681_rows()
    order = ["arcadedb_sparse_embedded", "qdrant_sparse", "milvus_sparse",
             "elasticsearch_sparse"]
    tiers = (("tiny", "100k"), ("small", "1M"), ("medium", "8.84M"))
    # TIERS AS ROWS, three per system, systems kept together.
    #
    # They were column groups, which put each system's scaling trend on one
    # line at a cost of nine data columns. That is 548pt at scriptsize: fine
    # across an IEEEtran table* at 7.16in, and 57pt past the measure of any
    # single-column layout, where the only escapes are shrinking the type below
    # scriptsize or letting it run off the page. Neither is worth one line.
    #
    # Grouping by SYSTEM rather than by tier keeps what the column layout was
    # for: ArcadeDB's 100k/1M/8.84M sit on consecutive rows, so the scaling
    # trend still reads down three rows instead of across one, and the prose's
    # claims about it (the Qdrant ratio widening from 3.9x to 5.2x) stay
    # legible. Cross-system comparison at a fixed tier costs a short jump,
    # which is the side of the trade the sparse narrative uses less.
    lines = [r"\begin{tabular}{llrrr}", r"\toprule",
             r"System & Tier & p50 (ms) & p99 (ms) & R@10 \\", r"\midrule"]
    for i, be in enumerate(order):
        if i:
            lines.append(r"\addlinespace")
        for j, (sc, lab) in enumerate(tiers):
            g = [r for r in l3s if r["backend"] == be and r["scale"] == sc]
            # medium holds two corpora: the retired synthetic 10M and
            # Big-ANN's 8.84M. Mixing them is the #5411 error in table form.
            # The n_docs == 8_841_823 filter that used to stand here is now
            # PAPER_CORPUS in load_canonical, which covers every tier and every
            # consumer instead of the one tier someone thought to hardcode.
            if be == "arcadedb_sparse_embedded":
                g = arc[sc]
            # The system name labels its block once; repeating it down three
            # rows is noise the eye has to subtract.
            head = NAMES[be] if j == 0 else ""
            if not g:
                lines.append(" & ".join([head, lab, "--", "--", "--"]) + r" \\")
                continue
            lines.append(" & ".join([
                head, lab, mmm(g, "query_p50_ms"), mmm(g, "query_p99_ms"),
                mmm_rec(g)]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t4_sparse.tex", "\n".join(lines) + "\n")


MP_ARMS = ("fp32", "int8", "arcsrv", "arcsrv_int8", "milvus", "milvus_int8",
           "qdrant", "qdrant_int8", "chroma", "duckvss", "lancedb",
           "sqlitevec", "sqlitevec_int8")
MP_BUILDS = 5


def dense_mp_dir():
    """results/dense_mp5_<pin> when qCJ has written EVERY arm's five builds,
    else results/dense_mp5_2681. One resolver for the table, the figures, the
    exporter and the checks, so they cannot disagree about which directory
    "the dense overlay" is. All-or-nothing for the same reason export_web's
    _pinned_dir is: a half-written pinned directory must not supersede a
    complete overlay file by file."""
    pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    if pin:
        cand = os.path.join(RESULTS, f"dense_mp5_{pin}")
        if os.path.isdir(cand):
            missing = [f"mp_{a}_b{b}.json" for a in MP_ARMS for b in range(1, MP_BUILDS + 1)
                       if not os.path.isfile(os.path.join(cand, f"mp_{a}_b{b}.json"))]
            if not missing:
                return cand
            sys.stderr.write(f"dense_mp5_{pin}: {len(missing)} of {len(MP_ARMS) * MP_BUILDS} "
                             f"files missing (e.g. {missing[0]}); using dense_mp5_2681\n")
    return os.path.join(RESULTS, "dense_mp5_2681")


def _dense_multipass():
    """T5's dense block, read from the one-build/five-pass artifacts.

    WHY THIS REPLACED THE runs.jsonl PATH. The dense block used to be built
    from per-rep rows in runs.jsonl, which cannot express the cold/warm split
    at all: each rep is one number. The 26.8.1 re-measurement is a MULTIPASS
    protocol (one build, then five passes over it), so pass 0 is the cold
    query and passes 1-4 are steady state. Those artifacts never entered
    runs.jsonl, so the generator kept emitting dev3-era rows while the paper
    carried a hand-built table. Re-running the generator would have silently
    reverted the paper's headline table to a superseded engine.

    Returns [(label, build_s, cold_p50, warm_cell, cold_p99, recall)].
    """
    import glob
    # FIVE INDEPENDENT BUILDS PER ARM, not one build read five times.
    #
    # dense_mp_2681 held ONE file per arm: one build followed by five query
    # passes. Every record in it repeated that build's build_s and recall, so a
    # median over the file was a median over one number, and only the warm
    # column carried a real range. The 2026-08-08 re-run (dense_mp5_2681, nine
    # arms x five builds, 45 files) replaces it, and the change is not cosmetic:
    # four of the nine single-build recalls fall OUTSIDE the five-build range,
    # and they lean one way -- both ArcadeDB arms read high, DuckDB-VSS and
    # LanceDB read low, so the old gap between us and them was overstated.
    #
    # Cold p50 gains the most. It was ONE sample per arm, which is why #124
    # could not decide whether an 85% cold-latency move between two engine
    # builds was a regression or noise. It is now five, one per build.
    stats = {}
    for fp in sorted(glob.glob(os.path.join(dense_mp_dir(), "mp_*_b*.json"))):
        try:
            passes = json.load(open(fp))
        except Exception:
            continue
        if not isinstance(passes, list) or len(passes) < 2:
            continue
        p0 = passes[0]
        be = p0.get("backend")
        label = NAMES.get(be, be)
        if be == "arcadedb_dense_embedded":
            q = str(p0.get("quantization", "")).lower()
            label = "ArcadeDB (emb, int8)" if "int8" in q else "ArcadeDB (emb, fp32)"
        elif be == "arcadedb_dense_server":
            # Reads its own stamp rather than hard-coding fp32, so a future
            # quantized server run relabels itself instead of publishing a
            # precision it did not run. The embedded arm above already does
            # this; the server arm was the one row still asserting.
            q = str(p0.get("quantization", "")).lower()
            label = "ArcadeDB (srv, int8)" if "int8" in q else "ArcadeDB (srv, fp32)"
        s = stats.setdefault(label, {"build": [], "cold": [], "warm": [],
                                     "cold99": [], "recall": []})
        # One value per BUILD for anything that is a property of the build.
        for k, key in (("build", "build_s"), ("cold", "p50"),
                       ("cold99", "p99"), ("recall", "recall_at_10")):
            v = p0.get(key)
            if isinstance(v, (int, float)):
                s[k].append(v)
        # Warm pools every warm pass of every build: pass 0 is the cold one, so
        # this is 5 builds x 4 warm passes = 20 samples, not 4.
        s["warm"] += [x["p50"] for x in passes[1:] if x.get("p50") is not None]

    def cell(v):
        return None if not v else (st.median(v), min(v), max(v), len(v))

    out = [(label, cell(s["build"]), cell(s["cold"]), cell(s["warm"]),
            cell(s["cold99"]), cell(s["recall"]))
           for label, s in stats.items()]
    # Ordered by cold p50 median: the lifecycle axis is what this block is for.
    return sorted(out, key=lambda r: (r[2] is None, r[2] and r[2][0]))


def _sig3(v):
    """Three significant figures, thousands-separated above 1000.

    The table is read by eye, not by a machine: 522.26 s of index build is
    false precision when the run-to-run spread is seconds. This is the
    formatting the hand-built table used, reproduced so the generator emits
    it rather than a wall of raw floats.
    """
    if v is None:
        return "--"
    if v >= 1000:
        return "{:,}".format(int(round(v))).replace(",", "{,}")
    places = 0 if v >= 100 else (1 if v >= 10 else 2)
    return str(Decimal(repr(v)).quantize(Decimal(1).scaleb(-places),
                                         rounding=ROUND_HALF_UP))


def dense_ts_table(rows):
    dense = _dense_multipass()
    if not dense:
        raise SystemExit(
            "REFUSING to write t5: no dense multipass artifacts under "
            "results/dense_mp_2681/. The old runs.jsonl path emitted dev3-era "
            "rows and would silently revert the paper's headline table.")
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"\multicolumn{6}{l}{\textit{Dense ANN, DEEP-10M "
             r"(10M$\times$96d), degree-matched; latencies in ms}} \\",
             r"System & Build (s) & Cold p50 & Warm p50 & Cold p99 & Recall \\",
             r"\midrule"]
    # WHICH COLUMNS SHOW THEIR RANGE. Every column now has one -- five builds
    # give five values for build, cold and recall, and twenty for warm. Showing
    # all five ranges is the most informative table and also the widest, and
    # this paper is over its page limit (#118). So the range is printed where
    # the spread is load-bearing and the caption carries the rest:
    #   cold p50  the column the run existed to put error bars on (#124)
    #   warm p50  unchanged from before, a range readers already expect
    # build_s, cold p99 and recall print the median; their spread goes in the
    # caption, which is honest because it IS small.
    #
    # Recall lost its interval on the measurement, not to save space. Across
    # the nine arms it spreads 0.00-1.03% build to build, against 23-30% for
    # the cold p50 beside it: the range was spending the widest column of the
    # widest table to say "recall reproduces", which one caption clause says
    # better. Same call as T2's Q1/Q6. The recall MEDIAN stays next to every
    # latency, because reporting quality beside speed is the commitment; only
    # the interval goes.
    RANGED = {"cold", "warm"}

    def fmt(c, kind, digits=None):
        if c is None:
            return "--"
        med, lo, hi, _n = c
        f = ((lambda v: str(Decimal(repr(v)).quantize(
                 Decimal("0.001"), rounding=ROUND_HALF_UP)))
             if digits else _sig3)
        return ("%s [%s--%s]" % (f(med), f(lo), f(hi))) if kind in RANGED else f(med)

    for label, build, cold50, warm, cold99, recall in dense:
        # sqlite-vec is exact brute force, so its recall of 1.000 is a property
        # of the method rather than a result. The dagger points at the caption.
        if label.startswith("sqlite-vec"):
            label = r"sqlite-vec (fp32)$^{\dagger}$"
        lines.append(" & ".join([
            label, fmt(build, "build"), fmt(cold50, "cold"), fmt(warm, "warm"),
            fmt(cold99, "cold99"), fmt(recall, "recall", digits=3)]) + r" \\")
    ts = [json.loads(l) for l in open(os.path.join(RESULTS, "l4_tsbs.jsonl"))
          if l.strip()]
    lines += [r"\midrule",
              r"\multicolumn{6}{l}{\textit{Time series, TSBS cpu-only "
              r"(2.59M points)}} \\",
              r"System & Ingest (pts/s) & Last point (ms) & 1h bucket (ms) & "
              r"12h global (ms) & \\", r"\midrule"]
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
    # ONE SOURCE, NO FALLBACK. This used to cascade ts59 -> dev21_ts -> batch1,
    # each with its own last-point key, so a missing directory silently changed
    # both the engine line and the quantity being reported. The cascade is
    # gone: the release artifacts or nothing.
    native = [json.load(open(fp)) for fp in
              glob.glob(os.path.join(RESULTS, "ts_2681", "nosettle_r*.json"))]
    last_key = "q_last_unbounded_ms"
    # ts_2681 REPLACED ts59, which was the last published cell measured on a
    # pre-release wheel (26.8.1.dev23). A version sweep found it; this row is
    # the re-measure. It also records cpuset/heap/mem_cap/producer/role/host,
    # which ts59 did not, so the cell is now traceable as well as correctly
    # versioned.
    #
    # The engine barely moved across that gap, which is the useful part: ingest
    # 1.92M -> 1.86M pts/s, last point 0.690 -> 0.72 ms, 1h bucket 4.31 -> 4.41,
    # and the 12h aggregation IMPROVED 29.86 -> 24.98 ms. Nothing here changes
    # a conclusion, so the re-measure buys provenance rather than a new result,
    # which is exactly what a version freeze is supposed to buy.
    _v = {str(r.get("engine_version") or "?") for r in native}
    _dev = sorted(v for v in _v if ".dev" in v)
    if _dev:
        print("  !! T5 time-series ArcadeDB row is NOT on the release: %s.\n"
              "     Re-run the native TS probe on 26.8.1 before submission; "
              "this row is not publishable as measured." % ", ".join(_dev),
              file=sys.stderr)
    elif len(native) < 5:
        print("  !! T5 time-series ArcadeDB row has %d reps, not 5." % len(native),
              file=sys.stderr)
    if native:
        lines.append(" & ".join([
            r"ArcadeDB (native TS)", mmm(native, "ingest_pts_per_s"),
            mmm(native, last_key), mmm(native, "q_range_ms"),
            mmm(native, "q_global_ms")]) + " & " + chr(92)*2)
    for be in ("arcadedb", "duckdb", "questdb"):
        g = [r for r in ts if r["backend"] == be]
        label = ("ArcadeDB (document path)" if be == "arcadedb"
                 else NAMES[be])
        lines.append(" & ".join([
            label, mmm(g, "ingest_pts_per_s"), mmm(g, "q_last_ms"),
            mmm(g, "q_range_ms"), mmm(g, "q_global_ms")]) + " & " + chr(92)*2)
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


def run_gates():
    """Run the audit scripts and record their verdict beside the tables.

    FAIRNESS.md line 8 says "Run python3 fairness_check.py before regenerating
    tables and at the freeze". Nothing enforced that: this file imported none
    of the three audit scripts, so every table could be regenerated with a live
    fairness violation and leave no trace that it had been. The instruction
    lived in prose, which is the same "act of memory" the producer stamp was
    added to eliminate one level down.

    Deliberately NOT a hard block. Two invariants fail today by known and
    documented causes (F3's dense envelope, F7's unpublished SIFT-1M degree),
    and a gate that refuses to run until they are fixed is a gate people learn
    to bypass. Instead: print the verdict, and write it next to the .tex so
    "these tables were generated while F3 was failing" is a fact on disk
    rather than something to remember. --strict makes it fatal, for the freeze.
    """
    import subprocess
    lines, failed = [], []
    for script in ("fairness_check.py", "provenance_check.py"):
        try:
            p = subprocess.run([sys.executable, os.path.join(HERE, script)],
                               capture_output=True, text=True, timeout=600)
            tail = [l for l in p.stdout.splitlines()
                    if "FAIL" in l or "BAD" in l or "failure(s)" in l
                    or "finding(s)" in l]
            lines.append(f"--- {script} (exit {p.returncode}) ---")
            lines.extend("    " + l.strip() for l in tail[:40])
            if p.returncode != 0:
                failed.append(script)
        except Exception as e:
            lines.append(f"--- {script}: COULD NOT RUN: "
                         f"{e.__class__.__name__}: {e} ---")
            failed.append(script)

    banner = ("GATES CLEAN" if not failed
              else "GATES REPORTED FAILURES: " + ", ".join(failed))
    print("\n" + "=" * 62)
    print(banner)
    for l in lines:
        print(l)
    print("=" * 62 + "\n")

    _require_paper_dir()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "GATE_STATUS.txt"), "w") as f:
        f.write(f"{banner}\n\nTables in this directory were generated with the\n"
                f"audit scripts in the state below. A failure here does not\n"
                f"mean a table is wrong; it means an invariant those tables\n"
                f"depend on was not holding when they were written.\n\n")
        f.write("\n".join(lines) + "\n")
    print("wrote GATE_STATUS.txt")
    return failed


def freeze_paper_rows(rows):
    """Write the canonical rows the tables were built from, as a tracked file.

    runs.jsonl is the live append log and stays gitignored: it is written
    during a campaign, and a `git checkout` once reverted it mid-run and lost
    rows. But it is also the input to load_canonical(), so with it ignored the
    tabular and graph tables had no public source while the sparse and dense
    overlays did.

    This is the frozen half of that split. It is written HERE, in the same
    call that writes the tables, so the published rows and the published
    tables cannot come from different states of the log. A reader can
    recompute every T2/T3 cell from this file alone.
    """
    import csv as _csv
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    path = os.path.join(RESULTS, "runs_paper.csv")
    with open(path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (str(x.get("lane")), str(x.get("scale")),
                                             str(x.get("backend")), x.get("rep") or 0)):
            w.writerow({k: r.get(k) for k in cols})
    print(f"froze {len(rows)} canonical rows -> {os.path.relpath(path, HERE)}")


def main(freeze=True):
    """Regenerate the tables. freeze=False writes NO tracked file.

    THE FREEZE IS A SIDE EFFECT, and a destructive one. claims_check --regen
    is documented as a read-only check ("generates into a temp directory and
    diffs; never writes the real tables") and it redirects OUT to a temp dir
    to keep that promise -- but freeze_paper_rows writes to RESULTS, which is
    not redirected, so running the read-only gate overwrote runs_paper.csv:
    the only committed record of the PREVIOUS campaign's canonical selection,
    381 rows replaced by 405. That file cannot be regenerated back, because
    load_canonical() always dedupes to the latest ts_utc.

    Worse than the loss: after such a run the repo holds a CSV frozen from one
    row set beside tables built from another, two tracked files that look
    consistent and are not.
    """
    strict = "--strict" in sys.argv
    failed = run_gates()
    if failed and strict:
        print("--strict: refusing to regenerate tables while gates fail")
        return 1

    rows = load_canonical()
    print(f"{len(rows)} canonical rows")
    if freeze:
        freeze_paper_rows(rows)
    tabular_table(rows)
    graph_table(rows)
    sparse_table(rows)
    dense_ts_table(rows)
    e2_summary(rows)
    return 0


if __name__ == "__main__":
    main()
