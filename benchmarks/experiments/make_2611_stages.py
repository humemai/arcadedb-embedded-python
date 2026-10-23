#!/usr/bin/env python3
"""Emit the 2026-11 instrument's queue scripts: the multi-model subset at N reps, one stage per lane piece.

One generator, one template. The stage table below (STAGES) lists the lane pieces; the template (HEAD) is the stage
script, and it takes the instrument, REPS and the banner as parameters (stage_params), so nothing is rewritten after the
fact. Every guard the campaign learned is in the template: the cap table, shadowed definitions, budgets against the cap,
the whole-cell cost, images present AND current, the comparator digests frozen at generation, the JPype pin read back out
of the image, the pinned wheel by sha256, the cap rule, the ALL-DONE trap. What the selection adds:

  * THE SUBSET (PLAN-26111): ArcadeDB (embedded and served), SurrealDB (embedded and served), ArangoDB, Memgraph, PostgreSQL
    with pgvector and AGE (and plain PostgreSQL where a lane uses it), MongoDB (with MongoDB Search), DuckDB (with VSS and
    DuckPGQ), SQLite (with sqlite-vec), and the composed Qdrant plus Neo4j stack. Core lanes: graph (interactive and
    analytics), cross-model, documents (TPC-C and TPC-H), dense. `--second-list` adds sparse, time series and lifecycle.
    The stage list is DERIVED from STAGES and runner.LANES, filtered by engine and lane, and `--check` proves the filtered
    list runs exactly the cells the unfiltered one would for those engines and lanes. Every registered arm is either in the
    subset or named in OUTSIDE, so a newly registered arm forces a decision here.
  * THE INSTRUMENT. Every stage exports BENCH_INSTRUMENT=2026-11 before its first python call and aborts if the tree
    does not select it. Rows go to `runs_page_<pin>_2611.jsonl` (and the overlay directories carry the same suffix), so one
    file never holds two instruments. This generator re-executes itself with the variable set; a different value in the
    environment is refused.
  * TWO MODES. Default: the subset's comparators, on the release pair already installed (ARCADEDB_WHEEL,
    ARCADEDB_SERVER_IMAGE, ARCADEDB_ENGINE_COMMIT). `--arcadedb-release X.Y.Z`: ArcadeDB alone on that release, the pass a
    new release gets; it refuses unless the engine commit, the official image DIGEST, the wheel name, its sha256 and its URL
    are given on the command line, because the release may not exist when the drafts are made. That mode also writes
    `<prefix>00`, the pair install (official image by digest, wheel by sha256, build_matched_pair.sh, verify_pair_c25.sh),
    which the first lane stage waits for.
  * REPS. `--reps N` (default 3, at most 5) is baked in as `REPS=N`; a stage environment that declares fewer (the image
    defaults arm) keeps its own.
  * THE CHAIN. `--after <stage>` is the marker the first stage waits for (`grep -qx "<stage> ALL-DONE"`), or `none`. It is
    required: the previous chain's last stage is not a default anyone should inherit. It must be the LAST item of the
    queue already on the machine (2026-10-23: `qMA06 ALL-DONE` was already in mini's STATUS.txt because the study was
    skipped, so drafts waiting on it would have started beside the running A/Bs). `--status-file PATH` is required with a
    marker: the generator reads that copy of the machine's STATUS.txt and REFUSES a marker already in it, because a wait
    that is true at once is no wait. `--status-file none` says on purpose that there is no queue (the chain starts
    when launched, or the file is a fresh machine's).
  * ORDER. `biggest-last` (default) or `paper` (the table order); `--project CELLS_TSV` prices each stage from a per-cell
    hours table, scaled to N repetitions.

Usage:
  python3 make_2611_stages.py --check [--drafts DIR]       # selection, coverage and instrument proofs; lints DIR's scripts
  python3 make_2611_stages.py --project CELLS.tsv --check   # plus the projected hours per stage
  ARCADEDB_WHEEL=... ARCADEDB_SERVER_IMAGE=... ARCADEDB_ENGINE_COMMIT=<40 hex> \\
      python3 make_2611_stages.py --after qR15 --status-file STATUS.txt --id-prefix qS --out DIR [--engines a,b] [--lanes graph,dense] [--second-list]
  python3 make_2611_stages.py --arcadedb-release 26.11.1 --engine-commit <40 hex> --image-digest sha256:<64 hex> \\
      --wheel-name arcadedb_embedded-26.11.1-<tags>.whl --wheel-sha256 <64 hex> --wheel-url <https url> \\
      --after <last comparator stage> --status-file STATUS.txt --id-prefix qT --out DIR
  python3 make_2611_stages.py --check --drafts DIR [--status-file STATUS.txt]   # also: the drafts' first wait is not already in STATUS.txt
"""
from __future__ import annotations

import argparse
import ast
import collections
import glob
import hashlib
import json
import os
import re
import sys

import bench_common
import cap_rule
import runner
import engine_pin

HERE = os.path.dirname(os.path.abspath(__file__))

INSTRUMENT = "2026-11"
ROWS_SUFFIX = "_2611"
# cell_cost_check's prior for a tier this pass has not measured: the 2026-10 pass-1 rows, the comparators' measured cells
PRIOR_PIN = "d36b4ca3a"
DEFAULT_PREFIX = "qS"
MAX_REPS = 5
# the first line of every stage's banner (the next line, in the template, finishes the sentence)
BANNER = "# GENERATED by make_2611_stages.py -- edit"


# ------------------------------------------------------------------------------------------------ the stage table
# PER-SIZE environment. These are corpus selectors that are NOT derived from --scale, so a stage that omits one measures the
# wrong data under the right label (BUGS F6): tpch1/tpch10 carry SF 1 and 10, l3d small/deep10m carry n_docs 1,000,000 and
# 9,990,000.
SCALE_ENV = {
    ("l1tpc", "tpch1"): ["BENCH_TPC_SF=1"],
    ("l1tpc", "tpch10"): ["BENCH_TPC_SF=10"],
    ("l3d", "small"): ["BENCH_DENSE_DATA=/data/dense"],
    ("l3d", "deep10m"): ["BENCH_DENSE_DATA=/data/deep10m"],
}

# The sparse overlay names its files per scale; the dense one uses the runner's default mp_{label}_b{rep}.json, which is what
# the dense resolver looks for.
OVERLAY_ENV = {"l3s": 'BENCH_DRIVER_OUT_FMT=sp_{label}_{scale}.json'}

# THE OVERLAY LANES. The dense and sparse TABLES do not read the lane's own search rows: they read a multipass overlay
# produced by a bespoke driver run through `runner.py --driver`, which builds once and then times five passes, so cold and
# warm exist for every engine under one protocol. The lane row is still needed (it carries ingest, build, memory and disk),
# so BOTH run, into different results files. The names carry ${PIN}; rows_name() adds the instrument's suffix.
OVERLAY = {
    "l3d": ("dense_multipass_driver.py", "$REPS", {
        "small":   ("dense_mp5_small_${PIN}", "mp_rows_small_${PIN}.jsonl"),
        "deep10m": ("dense_mp5_${PIN}",       "mp_rows_${PIN}.jsonl"),
    }),
    # the sparse overlay takes its repetitions INSIDE the driver, so the runner runs it once per arm
    "l3s": ("sparse_multipass_driver.py", "1", {
        "tiny":   ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
        "small":  ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
        "medium": ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
    }),
}


def rows_name(name):
    """A rows file or overlay directory name with the instrument's suffix after the pin."""
    return name.replace("${PIN}", "${PIN}" + ROWS_SUFFIX)


# THE TIMED WRITES RUN TWICE, ONCE AT EACH DURABILITY CLASS (DECISIONS #90, FAIRNESS F10b). Reads are untouched and bulk
# ingest stays at one setting (#90a): only the (lane, workload) pairs fairness_check enforces both classes on get the second
# pass. DERIVED, NOT TYPED: read by ast rather than imported, because fairness_check pulls in the whole table stack and a
# stage generator runs on the bench host where that must not happen.
def _strict_workloads():
    tree = ast.parse(open(os.path.join(HERE, "fairness_check.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "WRITE_CELLS":
            return {tuple(p) for p in ast.literal_eval(node.value)}
    raise SystemExit("fairness_check.WRITE_CELLS not found: the stage generator "
                     "cannot tell which cells need both durability classes")


STRICT_WORKLOADS = _strict_workloads()

# Guards a lane's stage adds to the template's own (shell, run before the first cell).
_LDBC = ['[ -d "$HOME/bench-data/ldbc/sf1" ] && [ -d "$HOME/bench-data/ldbc/sf10" ]'
         ' || { say \'$ID ABORT: ldbc sf1/sf10 missing\'; exit 1; }']
_LDBC_FULL = ['grep -q "sf1full" ldbc_snb.py || { say "$ID ABORT: no sf1full tier"; exit 1; }',
              'python3 -c "import graph_common as G, sys; sys.exit(0 if G.tier_excluded(\'sf1full\',\'lsqb_q6\') else 1)"'
              ' || { say "$ID ABORT: #109 exclusions are not in this tree"; exit 1; }']
# READ the constant, do not IMPORT the lane: e2_hybrid imports numpy and the host python3 has none, so an importing guard
# aborts a healthy stage for a reason that has nothing to do with the stage.
_E2 = ['python3 -c "import ast,sys;'
       ' t=ast.parse(open(\'e2_hybrid.py\').read());'
       ' d=[n for n in t.body if isinstance(n,ast.Assign) and getattr(n.targets[0],\'id\',None)==\'SCALE_PRODUCTS\'];'
       ' v=dict(zip([k.value for k in d[0].value.keys],[ast.literal_eval(x) for x in d[0].value.values]));'
       ' sys.exit(0 if v.get(\'e2_500k\')==500000 else 1)"'
       ' || { say "$ID ABORT: e2_500k is not 500k products"; exit 1; }']
_TPCH = ['ls "$HOME"/bench-data/tpch/sf10_lineitem.parquet >/dev/null 2>&1'
         ' || { say \'$ID ABORT: tpch sf10 parquet missing\'; exit 1; }']
# BENCH_TS_SETTLE_S: the served ArcadeDB time-series aggregate only sees SEALED data, so for ~58 s after an ingest returns it
# answers with whole hours missing (BUGS F68). The settle is applied outside the ingest timer to EVERY backend and recorded
# on the row.
_TS = ['[ -f "$HOME/bench-data/tsbs/cpu_influx.lp" ] && [ -f "$HOME/bench-data/tsbs/cpu_influx_s1000.lp" ]'
       ' || { say \'$ID ABORT: tsbs corpora missing\'; exit 1; }',
       'grep -q "CREATE INDEX p_host_ts ON p (host, ts)" l4_tsbs.py'
       ' || { say "$ID ABORT: the DuckDB index this re-run exists for is not in this tree"; exit 1; }']
# BENCH_SPARSE_SOURCE defaults to a SYNTHETIC corpus; omitting it runs synthetic data under a paper label (BUGS F6).
_SPARSE_ENV = ["BENCH_SPARSE_SOURCE=bigann", "BENCH_SPARSE_DATA=/data/bigann"]
# BENCH_LC_ITERS/WARMUP are set EXPLICITLY: the lane's in-script defaults are ITERS=3 and WARMUP=1, the campaign's protocol
# is 5 and 2. Every other lane's in-script default is what the frozen rows recorded.
_LC_WORKLOADS = ["empty", "doc", "doc_idx10", "graph", "graph_gav", "vector", "sparse", "ts"]
_LC_SCALES = ["lc10k", "lc100k", "lc1m", "lc10m"]
_LC_ENV = ["BENCH_LC_ITERS=5", "BENCH_LC_WARMUP=2"]
# the full SF1 network's analytics: ArcadeDB also runs its no-GAV arm
_GAV_OFF = {"arcadedb_graph_embedded": ["BENCH_GAV=0"], "arcadedb_graph_server": ["BENCH_GAV=0"]}

# id, title, lane, workloads, scales, guards, extra arms {backend: [env]}, stage environment, [only these arms]
STATIC_STAGES = [
    ("qRA", "graph INTERACTIVE at both sizes, both durability classes", "l2", ["oltp"], ["sf1", "sf10"], _LDBC, {}, []),
    ("qRB", "graph ANALYTICS on the full SF1 network", "l2", ["olap"], ["sf1full"], _LDBC_FULL, _GAV_OFF, []),
    ("qRC", "cross-model at both sizes, both durability classes", "e2", ["hybrid", "atomicity"],
     ["e2", "e2_500k"], _E2, {}, []),
    ("qRD", "documents, both tables, at both sizes", "l1tpc", ["oltp", "olap"], ["tpch1", "tpch10"], _TPCH, {}, []),
    ("qRE", "dense vector at both sizes, with the multipass overlay", "l3d", ["search"], ["small", "deep10m"], [], {}, []),
    ("qRF", "sparse vector at three sizes, with the second pass", "l3s", ["search"], ["tiny", "small", "medium"], [], {},
     _SPARSE_ENV),
    ("qRG", "time series at both sizes", "l4", ["ingest"], ["ts100", "ts1000"], _TS, {}, ["BENCH_TS_SETTLE_S=90"]),
    ("qRH", "lifecycle at four sizes, ArcadeDB and SurrealDB", "lifecycle", _LC_WORKLOADS, _LC_SCALES, [], {}, _LC_ENV,
     ["arcadedb_embedded", "arcadedb_server", "surrealdb_lifecycle"]),
]


def _next_id(stage_id):
    """qRH -> qRI: the letter after the last static stage's."""
    return stage_id[:-1] + chr(ord(stage_id[-1]) + 1)


def _derived_stages(static):
    """One stage per arm that runs only part of its lane (runner.ARM_RUNS), after the static ones (nothing waits for a
    sensitivity arm, so it runs last): the arm alone, on the workloads, sizes, repetitions and durability class its declaration
    names, under the guards of its lane's main stage. Nothing here names an arm. A lane this table has no stage for is not
    this generator's."""
    out, last = [], static[-1][0]
    lanes = {s[2] for s in static}
    for lane in runner.LANES:
        if lane not in lanes:
            continue
        for arm, cfg in sorted(runner.restricted_arms(lane).items()):
            main = next(s for s in static if s[2] == lane)
            last = _next_id(last)
            out.append((last, cfg["title"], lane, list(cfg["workloads"]), list(cfg["scales"]), list(main[5]), {},
                        [f"REPS={cfg['reps']}"] if cfg.get("reps") else [], [arm], cfg.get("durability")))
    return out


STAGES = STATIC_STAGES + _derived_stages(STATIC_STAGES)


# --------------------------------------------------------------------------------------------------------- coverage
def _page_lanes():
    """(lane -> set of workloads, or None for any) the published tables read, from export_web._TABLE_LANE by ast
    (export_web refuses to import without results)."""
    tree = ast.parse(open(os.path.join(HERE, "export_web.py")).read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_TABLE_LANE":
            tl = ast.literal_eval(n.value)
            out = collections.defaultdict(set)
            for lane, wl in tl.values():
                out[lane].add(wl)
            return {k: (None if None in v else v) for k, v in out.items()}
    raise SystemExit("export_web._TABLE_LANE not found")


def stage_backends(spec):
    only = spec[8] if len(spec) > 8 and spec[8] else None
    # a lane's main stage leaves out the arms that run only part of it: they have stages of their own
    bes = list(only) if only else [b for b in runner.LANES[spec[2]][1] if b not in runner.restricted_arms(spec[2])]
    return sorted(bes, key=engine_rank)   # stable: arms of one engine keep the lane's order


def check_coverage(stages=None):
    """Every registered arm of every page lane this table stages in exactly one stage per workload, and no stage that
    contradicts runner.ARM_RUNS (a workload, size, repetitions or durability class the arm's declaration does not name).
    Returns (problems, excluded lanes with reasons, per-lane arm counts)."""
    stages = STAGES if stages is None else stages
    page = _page_lanes()
    ours = {s[2] for s in STATIC_STAGES}
    seen = collections.Counter()
    stage_wls = collections.defaultdict(set)
    problems = []
    for spec in stages:
        lane = spec[2]
        for wl in spec[3]:
            stage_wls[lane].add(wl)
            for be in stage_backends(spec):
                seen[(lane, wl, be)] += 1
                if not runner.arm_runs(lane, wl, be):
                    problems.append(f"{lane}/{wl}/{be}: staged, but runner.ARM_RUNS keeps it off this workload")
                cfg = runner.ARM_RUNS.get(be, {}).get(lane)
                for sc in (spec[4] if cfg else []):
                    if sc not in cfg["scales"]:
                        problems.append(f"{lane}/{wl}/{be}: staged at {sc}, outside runner.ARM_RUNS' sizes {cfg['scales']}")
                if cfg and cfg.get("reps") and f"REPS={cfg['reps']}" not in (spec[7] if len(spec) > 7 else []):
                    problems.append(f"{lane}/{wl}/{be}: staged without REPS={cfg['reps']}, the repetitions runner.ARM_RUNS declares")
                if cfg and cfg.get("durability") and (spec[9] if len(spec) > 9 else None) != cfg["durability"]:
                    problems.append(f"{lane}/{wl}/{be}: staged for both durability classes, runner.ARM_RUNS declares {cfg['durability']} only")
    excluded, counts = [], {}
    for lane, spec_l in runner.LANES.items():
        backends = spec_l[1]
        if lane not in ours:
            excluded.append((lane, "not a lane of this generator's table"))
            continue
        if lane not in page:
            excluded.append((lane, "feeds no page table (export_web._TABLE_LANE), so no stage runs it"))
            continue
        wls = page[lane] if page[lane] is not None else stage_wls.get(lane, set())
        if not wls:
            problems.append(f"{lane}: a page lane with no stage")
        for wl in sorted(wls):
            if wl not in stage_wls.get(lane, set()):
                problems.append(f"{lane}/{wl}: on the page, in no stage")
                continue
            for be in backends:
                if not runner.arm_runs(lane, wl, be):
                    continue
                c = seen[(lane, wl, be)]
                if c != 1:
                    problems.append(f"{lane}/{wl}/{be}: in {c} stages, expected exactly 1")
        counts[lane] = len(backends)
    for (lane, wl, be), c in seen.items():
        if be not in runner.LANES.get(lane, ("", []))[1]:
            problems.append(f"{lane}/{wl}/{be}: staged but not registered in runner.LANES")
    return problems, excluded, counts


# the extra arms a lane stage runs (the full SF1 analytics: BENCH_GAV=0) and the marker their rows carry as `backend_arm`
ARM_OF_ENV = {"BENCH_GAV=0": "nogav"}

Cell = collections.namedtuple("Cell", "label lane scale workload backend cls arm kind")


def stage_cells(spec):
    """Every run_cell and run_overlay call a stage makes, as (label, lane, scale, workload, backend, class, arm, kind), in
    the order render_stage writes them. The label is the string the script passes; a test reads the emitted scripts back and
    compares."""
    lane, wls, scales = spec[2], spec[3], spec[4]
    extra = spec[6] if len(spec) > 6 and spec[6] else {}
    dur_mode = spec[9] if len(spec) > 9 else None
    out = []
    for sc in scales:
        for be in stage_backends(spec):
            for wl in wls:
                if not runner.arm_runs(lane, wl, be):
                    continue
                base = f"{lane}/{sc}/{be}/{wl}"
                if dur_mode != "strict":
                    out.append(Cell(base, lane, sc, wl, be, "relaxed", "", "lane"))
                if (lane, wl) in STRICT_WORKLOADS and dur_mode != "relaxed":
                    out.append(Cell(f"{base} strict", lane, sc, wl, be, "strict", "", "lane"))
                for e in extra.get(be, []):
                    if e not in ARM_OF_ENV:
                        raise SystemExit(f"{lane}/{be}: the extra arm's environment {e!r} has no row marker in "
                                         f"ARM_OF_ENV, so the roster cannot say whether it finished")
                    out.append(Cell(f"{base} {e}", lane, sc, wl, be, "relaxed", ARM_OF_ENV[e], "lane"))
                if lane in OVERLAY:
                    out.append(Cell(f"{base} multipass", lane, sc, wl, be, "relaxed", "", "overlay"))
    return out


# ------------------------------------------------------------------------------------------------------ the JPype pin
JPYPE_DOCKERFILE = os.path.join(HERE, "Dockerfile.bench")
_JPYPE_ARG = re.compile(r"^ARG JPYPE_VERSION=(\S*)[ \t]*$", re.M)


def check_jpype_pin(dockerfile_text=None, pin=None):
    """Problems with the JPype pin, [] when the image recipe and the stage checks agree on one hard version.

    JPYPE IS PINNED, NOT RESOLVED (CAMPAIGN 7 row 73). The wheel declares jpype1>=1.5.0 with no upper bound, so an image or a
    venv built on the day of a new JPype release would change what every embedded ArcadeDB call costs mid-run. The stages
    compare the image's JPype to `pin`, which is baked into each script at generation; the image holds whatever
    Dockerfile.bench's ARG default says. Two copies of one number, so they are compared here, and every install line must be a
    hard `==` on the ARG, because a `>=` or a bare `jpype1` is how a release made on some other day reaches the image."""
    pin = bench_common.JPYPE_PIN if pin is None else pin
    if dockerfile_text is None:
        with open(JPYPE_DOCKERFILE, encoding="utf-8") as fh:
            dockerfile_text = fh.read()
    problems = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", pin or ""):
        problems.append(f"bench_common.JPYPE_PIN is {pin!r}, not one release (x.y.z)")
    defaults = _JPYPE_ARG.findall(dockerfile_text)
    if len(defaults) != 1:
        problems.append(f"Dockerfile.bench has {len(defaults)} `ARG JPYPE_VERSION=` lines, expected exactly 1")
    elif defaults[0] != pin:
        problems.append(f"Dockerfile.bench builds JPype {defaults[0]} and bench_common.JPYPE_PIN is {pin}: the image "
                        f"would hold one version and every stage would demand the other")
    code = "\n".join(l for l in dockerfile_text.splitlines() if not l.lstrip().startswith("#"))
    if "jpype1==${JPYPE_VERSION}" not in code:
        problems.append("Dockerfile.bench never installs `jpype1==${JPYPE_VERSION}`")
    for m in re.finditer(r"jpype1(?!==\$\{JPYPE_VERSION\})\S*", code):
        problems.append(f"Dockerfile.bench installs `{m.group(0)}`, which is not a hard `jpype1==${{JPYPE_VERSION}}`")
    return problems


# engine -> (what it covers, backend-name prefixes). The subset of PLAN-26111, by arm prefix of runner.LANES.
ENGINES = collections.OrderedDict([
    ("arcadedb", ("ArcadeDB, embedded and served", ("arcadedb",))),
    ("surrealdb", ("SurrealDB, embedded and served", ("surrealdb",))),
    ("arangodb", ("ArangoDB", ("arangodb",))),
    ("memgraph", ("Memgraph", ("memgraph",))),
    ("postgresql", ("PostgreSQL with pgvector, AGE and TimescaleDB, and plain PostgreSQL",
                    ("postgres", "pgvector", "pgage", "pg_age", "timescaledb"))),
    ("mongodb", ("MongoDB with MongoDB Search", ("mongodb",))),
    ("duckdb", ("DuckDB with VSS and DuckPGQ", ("duckdb", "duckpgq"))),
    ("sqlite", ("SQLite with sqlite-vec", ("sqlite",))),
    ("qdrant-neo4j", ("the composed Qdrant plus Neo4j stack", ("composed_qdrant_neo4j",))),
    ("neo4j", ("Neo4j on its own: graph and dense", ("neo4j_graph", "neo4j_dense"))),
    ("qdrant", ("Qdrant on its own: dense, and sparse on the second list", ("qdrant_dense", "qdrant_sparse"))),
    ("redis", ("Redis 8 (Query Engine): dense", ("redis_",))),
    ("ladybug", ("LadybugDB, embedded graph and vector, on every lane it supports", ("ladybug",))),
])
# TimescaleDB completes the PostgreSQL arm (pgvector, AGE, TimescaleDB) and runs whenever the time-series lane does
TIMESCALEDB = "timescaledb"
# registered arms that are NOT in the subset (prefixes). Neo4j's cross-model arm is the composed stack's part.
OUTSIDE = ("neo4j_e2", "falkordb", "milvus", "elasticsearch", "chroma", "lancedb", "questdb")

CORE_LANES = ("l2", "e2", "l1tpc", "l3d")
SECOND_LANES = ("l3s", "l4", "lifecycle")
LANE_ALIASES = {"graph": "l2", "cross-model": "e2", "documents": "l1tpc", "dense": "l3d", "sparse": "l3s",
                "timeseries": "l4", "time-series": "l4", "lifecycle": "lifecycle"}
MODES = ("comparators", "arcadedb")
# ORDER (the default, "biggest-last"): the core block first, the second list after it (lifecycle, sparse, time series).
# Inside the core block the large tiers (LARGE_SCALES) run after every small tier, and the cells that dominate the hours
# (BIGGEST: Memgraph's deep10m dense cells, SurrealDB's documents at tpch1, the full SF1 network's analytics) run last of
# all, in stages of their own, where they are easiest to drop if time runs short. Splitting changes the stage boundaries
# only: stage_problems proves the cells are the same.
LARGE_SCALES = ("deep10m", "tpch10", "sf1full")
BIGGEST = (("l3d", ("memgraph_dense",), ("deep10m",)),
           ("l1tpc", ("surrealdb_tpc",), ("tpch1",)),
           ("l2", None, ("sf1full",)))
SECOND_ORDER = ("lifecycle", "l3s", "l4")


# THE ORDER INSIDE A LANE (the user, 2026-10-23: "order the comparators in priority"), highest first: when a pass is cut short the
# engines that matter most have their rep. ArcadeDB's four 26.11.1 arms (JVM/native x embedded/server) go on top when 26.11.1
# ships. Redis 8 and CrateDB are named here before their adapters are merged: an engine that is not in ENGINES is skipped cleanly.
ENGINE_PRIORITY = ("arcadedb", "surrealdb", "arangodb", "postgresql", "mongodb", "redis", "qdrant-neo4j", "neo4j", "qdrant",
                   "duckdb", "sqlite", "memgraph", "ladybug", "cratedb")


def engine_rank(backend):
    """Sort key of an arm: its engine's place in ENGINE_PRIORITY (an engine outside the list sorts last)."""
    eng = engine_of(backend)
    return ENGINE_PRIORITY.index(eng) if eng in ENGINE_PRIORITY else len(ENGINE_PRIORITY)


def engine_of(backend):
    """The subset engine an arm belongs to, or None."""
    for eng, (_what, prefixes) in ENGINES.items():
        if backend.startswith(prefixes):
            return eng
    return None


def is_outside(backend):
    return backend.startswith(OUTSIDE)


def registered_arms():
    return sorted({b for spec in runner.LANES.values() for b in spec[1]})


def arm_problems(arms=None):
    """Every registered arm is in exactly one subset engine or declared outside it."""
    out = []
    for b in registered_arms() if arms is None else arms:
        eng, outside = engine_of(b), is_outside(b)
        if eng and outside:
            out.append(f"arm {b} is both in the subset ({eng}) and in OUTSIDE")
        elif not eng and not outside:
            out.append(f"arm {b} is neither in the subset nor in OUTSIDE: decide which")
    return out


# ------------------------------------------------------------------------------------------------------ selection
def parse_engines(text, mode):
    names = [x.strip() for x in text.split(",") if x.strip()] if text else []
    bad = [n for n in names if n not in ENGINES]
    if bad:
        raise SystemExit(f"REFUSING: {', '.join(bad)} is not in the subset; the subset is {', '.join(ENGINES)}")
    allowed = [e for e in ENGINES if (e == "arcadedb") == (mode == "arcadedb")]
    if not names:
        return allowed
    wrong = [n for n in names if n not in allowed]
    if wrong:
        raise SystemExit(f"REFUSING: {', '.join(wrong)} does not run in the {mode} mode ("
                         + ("ArcadeDB runs only with --arcadedb-release" if mode == "comparators"
                            else "--arcadedb-release runs ArcadeDB alone") + ")")
    return names


def parse_lanes(text, second_list):
    if not text:
        return list(CORE_LANES + (SECOND_LANES if second_list else ()))
    out = []
    for x in (t.strip() for t in text.split(",") if t.strip()):
        lane = LANE_ALIASES.get(x, x)
        if lane not in CORE_LANES + SECOND_LANES:
            raise SystemExit(f"REFUSING: lane {x} is not in the subset's lists (core: graph, cross-model, documents, dense; "
                             f"second list: sparse, timeseries, lifecycle)")
        if lane in SECOND_LANES and not second_list:
            raise SystemExit(f"REFUSING: lane {x} is on the second list; add --second-list")
        out.append(lane)
    return out


def _spec10(spec):
    return list(spec) + [None] * (10 - len(spec))


def _piece(s, title, backends, scales):
    p = list(s)
    p[1], p[4], p[8] = title, list(scales), list(backends)
    p[6] = {b: v for b, v in (s[6] or {}).items() if b in backends}
    return p


def subset_specs(engines, lanes, order="biggest-last", skip=()):
    """STAGES, unnumbered, restricted to the lanes and to the arms of these engines (minus `skip`). A stage
    left with no arm is dropped; the host-side, restart and decomposition stages are not in the subset's lists. Order
    "paper" is the table order; "biggest-last" is described at BIGGEST."""
    base = []
    for spec in STAGES:
        s = _spec10(spec)
        if s[2] not in lanes:
            continue
        bes = [b for b in stage_backends(spec) if engine_of(b) in engines and b not in skip]
        if bes:
            base.append(_piece(s, s[1], bes, s[4]))
    if order == "paper":
        return base
    pieces = []   # (block, tier, index, spec)
    for i, s in enumerate(base):
        block = 0 if s[2] in CORE_LANES else 1 + SECOND_ORDER.index(s[2])
        small = [x for x in s[4] if x not in LARGE_SCALES]
        large = [x for x in s[4] if x in LARGE_SCALES]
        parts = [(0, small, " (small tier)" if large and small else ""), (1, large, " (large tier)" if small else "")]
        for tier, scales, suffix in parts:
            if not scales:
                continue
            rest, normal, last = list(s[8]), [], []
            for lane, arms, rscales in BIGGEST:
                hit = [b for b in rest if arms is None or b.startswith(arms)] if lane == s[2] else []
                names = [x for x in scales if x in rscales]
                if hit and names:
                    last.append((hit, names))      # these arms at these scales: the biggest cells
                    if len(names) < len(scales):   # the same arms at the piece's other scales stay in place
                        normal.append((hit, [x for x in scales if x not in rscales]))
                    rest = [b for b in rest if b not in hit]
            if rest:
                normal.append((rest, scales))
            for bes, sc in normal:
                pieces.append((block, tier, i, _piece(s, s[1] + suffix, bes, sc)))
            for bes, sc in last:
                pieces.append((block, 2, i, _piece(s, s[1] + " (biggest cells, last)", bes, sc)))
    pieces.sort(key=lambda t: (t[0] != 0, t[1] if t[0] == 0 else 0, t[0], t[2]))
    return [t[3] for t in pieces]


def number(specs, prefix, start=1):
    return [tuple([f"{prefix}{i + start:02d}"] + s[1:]) for i, s in enumerate(specs)]


# --------------------------------------------------------------------------------------------------------- proofs
def stage_problems(stages, engines, lanes, skip=()):
    """What is wrong with a stage list: an arm outside the engines asked for or outside the subset, a lane outside the lanes,
    and the exactly-once proof: the cells the list schedules equal the cells STAGES schedules for these engines and
    lanes (nothing lost, nothing doubled, nothing extra)."""
    out = arm_problems()
    for st in stages:
        if st[2] not in lanes:
            out.append(f"{st[0]}: lane {st[2]} is not in the lanes asked for")
        for b in stage_backends(st):
            if engine_of(b) is None:
                out.append(f"{st[0]}: runs {b}, which is not in the subset")
            elif engine_of(b) not in engines or b in skip:
                out.append(f"{st[0]}: runs {b} ({engine_of(b)}), which is not among the engines asked for")
    want = collections.Counter()
    for spec in STAGES:
        if spec[2] not in lanes:
            continue
        s = _spec10(spec)
        s[8] = [b for b in stage_backends(spec) if engine_of(b) in engines and b not in skip]
        if not s[8]:   # an empty roster would mean "every arm of the lane" to stage_backends
            continue
        for c in stage_cells(tuple(s)):
            want[c] += 1
    have = collections.Counter(c for st in stages for c in stage_cells(st))
    for c, n in sorted((have - want).items()):
        out.append(f"cell {c.label} is scheduled {have[c]} times, expected {want[c]}")
    for c in sorted(want - have):
        out.append(f"cell {c.label} is in no stage")
    return out


def instrument_problems(env=None):
    """Anything that would let this generator, or the stages it writes, measure another instrument."""
    env = os.environ if env is None else env
    out = []
    v = env.get("BENCH_INSTRUMENT")
    if v not in (None, INSTRUMENT):
        out.append(f"BENCH_INSTRUMENT={v} in the environment: these stages are the {INSTRUMENT} instrument's, and a "
                   f"generator on another instrument would mix the two")
    if bench_common.INSTRUMENT != INSTRUMENT:
        out.append(f"bench_common.INSTRUMENT is {bench_common.INSTRUMENT}, not {INSTRUMENT} (run through this file's own "
                   f"entry point, which sets BENCH_INSTRUMENT={INSTRUMENT})")
    return out


_BACKENDS = re.compile(r'^BACKENDS="([^"]*)"', re.M)


def lint_draft(text, name, engines=None):
    """Problems in one emitted stage script: it must export the instrument, name no other, write the 2611 rows file and
    run only subset arms (of `engines` when given). The pair-install script has no runner cells and is only checked for
    the instrument not being named wrongly."""
    out = []
    pair = "build_matched_pair.sh" in text
    if re.search(r"instrument 2026-10\b|BENCH_INSTRUMENT=2026-10\b", text):
        out.append(f"{name}: names the 2026-10 instrument")
    if pair:
        return out
    if not re.search(rf"^export BENCH_INSTRUMENT={INSTRUMENT}$", text, re.M):
        out.append(f"{name}: does not export BENCH_INSTRUMENT={INSTRUMENT}")
    if re.search(r"runs_page_\$\{PIN\}\.jsonl", text) or f"runs_page_${{PIN}}{ROWS_SUFFIX}.jsonl" not in text:
        out.append(f"{name}: writes a rows file that is not runs_page_<pin>{ROWS_SUFFIX}.jsonl")
    first_abort = text.find('$ID ABORT')
    if first_abort >= 0 and not 0 <= text.find("ALL-DONE\" >> \"$S\"' EXIT") < first_abort:
        out.append(f"{name}: a guard can ABORT before the ALL-DONE trap is set, which strands every stage waiting on this one")
    m = _BACKENDS.search(text)
    if not m:
        out.append(f"{name}: no BACKENDS line")
    else:
        arcade = has_arcadedb_arm(m.group(1).split())
        # every stage builds images with the pinned wheel baked in, so every stage guards the wheel's sha256
        if "is not the wheel this chain was generated for" not in text:
            out.append(f"{name}: no guard for the pinned wheel's sha256, which the image build bakes into every image")
        for needle, what in (("wheels in dist/", "one wheel in dist/"), ("ABORT: no server image", "the server image"),
                             ("ABORT: dbbench:arcadedb carries wheel", "the dbbench:arcadedb wheel check"),
                             ("ABORT: pair unverified at the pin", "verify_pair_c25.sh")):
            if arcade and needle not in text:
                out.append(f"{name}: runs an ArcadeDB arm but has no guard for {what}")
            if not arcade and needle in text:
                out.append(f"{name}: runs no ArcadeDB arm but guards {what}, so a host still on the previous release aborts it")
        for b in m.group(1).split():
            eng = engine_of(b)
            if eng is None:
                out.append(f"{name}: runs {b}, which is not in the subset")
            elif engines is not None and eng not in engines:
                out.append(f"{name}: runs {b} ({eng}), which is not among the engines asked for")
    return out


def marker_in_status(marker, status_file):
    """True when `marker ALL-DONE` is already a whole line of the STATUS file (the test every wait makes: `grep -qx`)."""
    want = f"{marker} ALL-DONE"
    with open(status_file, encoding="utf-8", errors="replace") as fh:
        return any(line.rstrip("\n") == want for line in fh)


def status_problems(marker, status_file):
    """A wait on a marker the machine already holds is no wait: the stage starts at once, beside whatever still runs.
    2026-10-23: `qMA06 ALL-DONE` was in mini's STATUS.txt (the study was skipped) while four A/B jobs still ran."""
    if marker is None or status_file is None:
        return []
    if not os.path.isfile(status_file):
        return [f"--status-file {status_file}: no such file"]
    if marker_in_status(marker, status_file):
        return [f"the start marker `{marker} ALL-DONE` is already a line of {status_file}: a stage waiting on it starts at "
                f"once. Pick the LAST item of the queue that is still to run (it writes its marker whether it runs or skips)"]
    return []


def lint_drafts(directory, engines=None, status_file=None):
    """Lint every script in a folder, and check the chain: each stage waits for the one before it in id order.
    With a STATUS file, the first stage's wait must not already be true there."""
    files = sorted(glob.glob(os.path.join(directory, "*.sh")))
    out = []
    if not files:
        return [f"{directory}: no stage scripts"]
    prev = None
    first = True
    for f in files:
        name = os.path.basename(f)
        text = open(f, encoding="utf-8").read()
        out += lint_draft(text, name, engines)
        waits = re.findall(r'^while ! grep -qx "([^"]+?) ALL-DONE"', text, re.M)
        if prev is not None and waits != [prev]:
            out.append(f"{name}: waits for {waits or 'nothing'}, expected {prev}")
        prev = name[:-3]
        if status_file is not None and first:
            out += [f"{name}: {p}" for p in status_problems(waits[0] if len(waits) == 1 else None, status_file)]
        first = False
    return out




# ------------------------------------------------------------------------------------------------------ the template
# THE COMPARATOR PINS ARE FROZEN AT GENERATION. Every stage `git pull`s main, so a comparator digest edited in runner.py
# mid-chain would split one table across two versions with every gate green until the landing. Each stage carries the digests
# its arms had when the chain was generated and refuses to start if runner.py now says otherwise.
def _comparator_pins(backends):
    """{backend: {key: digest}} for every pulled comparator image these arms name."""
    out = {}
    for be in backends:
        d = runner.BACKENDS.get(be, {})
        pins = {k: d[k] for k in ("image", "server_image")
                if isinstance(d.get(k), str) and "@sha256:" in d[k] and not d[k].startswith("dbbench:")
                and not be.startswith("arcadedb")}
        if pins:
            out[be] = pins
    return out


def _pin_guard(backends):
    pins = _comparator_pins(backends)
    if not pins:
        return []
    js = json.dumps(pins, sort_keys=True)
    return [
        "# THE COMPARATOR PINS THIS CHAIN WAS GENERATED WITH. Every stage pulls main, so a",
        "# digest edited in runner.py mid-chain would split a table across two versions.",
        "python3 - <<'PY' || { say \"$ID ABORT: a comparator pin moved since the chain was generated\"; exit 1; }",
        "import json, sys",
        "import runner",
        f"want = json.loads({js!r})",
        "bad = [f'{b}.{k}: runner {runner.BACKENDS.get(b, {}).get(k)!r} != generated {v!r}'",
        "       for b, d in want.items() for k, v in d.items() if runner.BACKENDS.get(b, {}).get(k) != v]",
        "for x in bad:",
        "    print('  pin moved:', x)",
        "sys.exit(1 if bad else 0)",
        "PY",
    ]


def _images_for(backends):
    """The dbbench:* images these backends actually name, as build targets.

    TYPED IMAGE LISTS GO STALE SILENTLY. Every stage built `arcadedb duckdb
    client` because that was true when the first stage was written; the
    cross-model lane then gained MongoDB (#98), whose arm runs the purpose-
    built dbbench:mongo-search, and nothing built it. The cell did not say
    "missing image" -- it waited for a readiness line from a container that
    could not start and recorded `server_not_ready`, which reads like a slow
    engine. Deriving the list from runner.BACKENDS means a new arm brings its
    image with it.
    """
    out = set()
    for be in backends:
        d = runner.BACKENDS.get(be, {})
        for key in ("image", "server_image"):
            img = d.get(key, "")
            if img.startswith("dbbench:"):
                out.add(engine_pin.build_target(img))  # dbbench:arcadedb-<version> is built as the `arcadedb` target
    return sorted(out)


def _pulled_images_for(backends):
    """The PINNED images these backends pull rather than build.

    The stages verify every image they BUILD -- `build_images.sh`, then a
    `docker image inspect` per dbbench target -- and nothing at all for the
    ones they pull. A digest-pinned comparator is fetched lazily by the first
    `docker run` that names it, so a registry that is slow or a digest that has
    been collected upstream surfaces as a FAILED CELL partway into a stage
    rather than an abort in its first minute.

    That is not hypothetical for the stages queued on 2026-09-22: five pinned
    images are absent from mini -- elasticsearch, milvus (3.7 GB), pgvector,
    postgres, qdrant -- because the lanes that use them have not run since the
    October re-pin. qOE, qOF and qOH need them. All five still resolve
    upstream, so the queued stages will be fine; the point is that nothing
    checked, and the run that finds out is the expensive one.

    Pulled up front, by digest, so the failure is loud and early.
    """
    out = set()
    for be in backends:
        d = runner.BACKENDS.get(be, {})
        for key in ("image", "server_image"):
            img = d.get(key, "")
            if img and not img.startswith("dbbench:") and "@sha256:" in img:
                out.add(img)
    return sorted(out)


# THE CAP RULE (DECISIONS #188, cap_rule.py). The bash is what was patched into the live pass-1 stages on 2026-10-18; the
# generator emits the same text so later stages match them.
CAP_RULE_HELPERS = """
# THE CAP RULE (DECISIONS #188, 2026-10-18). Each run_cell cap above is min(the tier cap, max(1800 s, 10 x the slower of
# ArcadeDB's and the median engine's pass-1 median for that cell)), so no ArcadeDB arm is ever censored by it. And an arm
# censored at a smaller size is censored at every larger one of the same lane, workload and class: it is not run there,
# and its overlay at a size where its lane cell was censored is not run either.
declare -A CENSORED_AT
cap_rule_skip() {  # <label> <key>: true (and says so) when the arm was already censored in this stage
  local at=${CENSORED_AT[$2]:-}
  [ -n "$at" ] || return 1
  say "$ID: $1 not run: censored at $at, so censored here too (cap rule, DECISIONS #188)"
  return 0
}
cap_rule_note() {  # <key> <scale>: after a failed rep 1, remember a TIMEOUT (not another failure) for the larger sizes
  grep -E '^\\s+\\[[0-9]+/[0-9]+\\] ' "$S" | tail -1 | grep -q -- '-> timeout_after_' && CENSORED_AT[$1]=${CENSORED_AT[$1]:-$2}
  return 0
}
"""


_RUN_CELL_CAP = re.compile(r'run_cell "([a-z0-9]+)/([a-z0-9_]+)/\$BE/([a-z_0-9]+)( strict)?" ([a-z0-9_]+) (\d+)')


def apply_cap_rule(body, lane, backends, workloads, data=None):
    """The run-time half of the rule, on one emitted stage: each run_cell cap becomes min(its cap, the rule cap of its cell)
    when cap_rule_2610.json has the cell, and before each scale's backend loop CENSORED_AT is seeded for the stage's arms that
    pass 1 censored at a smaller scale of the lane (over the rule, or a TIMEOUT of rep 1), so a stage run later (the deferred
    lifecycle stage, the top-up pass) does not run them again. Without the file the stage is unchanged."""
    data = data if data is not None else cap_rule.load()
    if not data:
        return body

    def sub_cap(m):
        lane_, scale, wl, strict, _, cap = m.groups()
        r = cap_rule.rule_cap(lane_, scale, wl, "strict" if strict else "", data)
        if r is None or r >= int(cap):
            return m.group(0)
        return m.group(0)[: m.start(6) - m.start(0)] + str(r)
    body = _RUN_CELL_CAP.sub(sub_cap, body)

    def seed(m):
        scale = re.search(r'run_cell "[a-z0-9]+/([a-z0-9_]+)/\$BE/', body[m.end():]).group(1)
        lines = []
        for (l, be, wl, cls), _ in sorted(cap_rule.censored_scales(data).items()):
            if l != lane or be not in backends or wl not in workloads:
                continue
            at = cap_rule.censored_before(l, scale, be, wl, cls, data)
            if at:
                dur = "--durability strict" if cls == "strict" else ""
                lines.append(f'CENSORED_AT["{be}|{wl}|{dur}"]="{at}"')
        head = ("# CAP RULE, seeded from pass 1 (cap_rule_2610.json): arms already censored at a smaller scale of this lane\n"
                + "\n".join(lines) + "\n") if lines else ""
        return "\n" + head + m.group(0)[1:]
    return re.sub(r"\nfor BE in \$BACKENDS; do\n", seed, body)


# THE ARCADEDB PAIR'S GUARDS. A stage that runs an ArcadeDB arm (the --arcadedb-release pass) gets all of them. A comparator-only
# stage gets the ones its IMAGE BUILD needs and no others: the build bakes ARCADEDB_WHEEL into every generic image (client,
# duckdb, dense; Dockerfile.bench installs every wheel in docker-wheels/), so the wheel is exported before build_images.sh,
# exactly as in the ArcadeDB stages, and must exist at the pinned path with the pinned sha256 (build_images.sh copies it from
# there; nothing in it or in the Dockerfiles reads dist/ itself). What it does not need, because none of its arms is ArcadeDB:
# the "one wheel in dist/" rule (it protects verify_pair_c25.sh, which takes the newest wheel there), the server image, the wheel
# and JPype read back out of dbbench:arcadedb, and verify_pair_c25.sh. Guarding those anyway aborted a healthy comparator stage
# on a host whose dist/ and dbbench:arcadedb were still the previous release's.
ARCADE_WHEEL_HEAD = '''# THE WHEEL IS BAKED AT IMAGE BUILD TIME, so it has to be exported BEFORE
# build_images.sh, and the arcadedb image has to be rebuilt. Without both,
# the embedded arms would run another wheel than the served ones run
# (build_images.sh used to fall back to `arcadedb-embedded==26.8.1` from PyPI;
# it now refuses without ARCADEDB_WHEEL): two ArcadeDB versions on one table.
# That is exactly what last night's calibration did -- its embedded arms ran 26.8.1 against served
# 26.9.1-SNAPSHOT -- and verify_pair_c25.sh does not catch it, because it
# compares the newest wheel FILE in dist/ against the server image and never
# looks inside dbbench:arcadedb.
# THE RELEASE PAIR THIS CHAIN WAS GENERATED FOR, named rather than found
# (DECISIONS #42). A different file in dist/ is a different engine under test.
W="$REPO/bindings/python/dist/{wheel_name}"
[ -f "$W" ] || {{ say "$ID ABORT: the pinned wheel {wheel_name} is not in dist/"; exit 1; }}
'''

ARCADE_WHEEL_COUNT = '''# ONE WHEEL, OR SAY WHICH. `ls -t | head -1` takes the newest by mtime and
# says nothing about the ones it passed over, so a second wheel in dist/ --
# a rebuild at a different pin, a copy kept "just in case" -- silently
# decides what every cell of this stage measures. dist/ holds exactly one
# today; the guard is here because the day it holds two is the day nobody
# notices. Refusing rather than warning: this picks the ENGINE UNDER TEST.
_NW=$(ls "$REPO"/bindings/python/dist/*.whl 2>/dev/null | wc -l)
[ "$_NW" -eq 1 ] || {{ say "$ID ABORT: $_NW wheels in dist/, and ls -t would pick one by date: $(ls "$REPO"/bindings/python/dist/*.whl | tr '
' ' ')"; exit 1; }}
'''

ARCADE_WHEEL_SHA_EXPORT = '''[ "$(sha256sum "$W" | cut -d' ' -f1)" = "{wheel_sha256}" ] || {{ say "$ID ABORT: dist/{wheel_name} is not the wheel this chain was generated for (sha256)"; exit 1; }}
export ARCADEDB_WHEEL="$W" ARCADEDB_SERVER_IMAGE="{server_image}"
'''

ARCADE_PRE_TAIL = '''docker image inspect "$ARCADEDB_SERVER_IMAGE" >/dev/null 2>&1 || {{ say "$ID ABORT: no server image $ARCADEDB_SERVER_IMAGE"; exit 1; }}
WV=$(basename "$W" | cut -d- -f2)
'''

ARCADE_PRE_BUILD = ARCADE_WHEEL_HEAD + ARCADE_WHEEL_COUNT + ARCADE_WHEEL_SHA_EXPORT + ARCADE_PRE_TAIL
COMPARATOR_PRE_BUILD = ARCADE_WHEEL_HEAD + ARCADE_WHEEL_SHA_EXPORT.rstrip("\n")

ARCADE_POST_CHECKS = '''# VERIFY THE ARM, NOT THE FILE: read the version out of the built image.
# The pair check below is the REPO copy, not ~/verify_pair_c25.sh: that
# one is a stale copy from 2026-08-30 and would miss its own fourth
# check. A script pulled with the tree cannot drift from it.
IV=$(docker run --rm --entrypoint python3 "dbbench:arcadedb-$WV" -c      'import importlib.metadata as m; print(m.version("arcadedb-embedded"))' 2>/dev/null | tr -dc "0-9a-zA-Z.-")
[ "$IV" = "$WV" ] || {{ say "$ID ABORT: dbbench:arcadedb carries wheel $IV, dist has $WV"; exit 1; }}
say "$ID: dbbench:arcadedb carries wheel $IV, matching dist"
IJ=$(docker run --rm --entrypoint python3 "dbbench:arcadedb-$WV" -c 'import jpype; print(jpype.__version__)' 2>/dev/null | tr -dc "0-9a-zA-Z.-")
[ "$IJ" = "{jpype_version}" ] || {{ say "$ID ABORT: dbbench:arcadedb runs JPype '$IJ', the pin is {jpype_version} (Dockerfile.bench, ARG JPYPE_VERSION); rebuild dbbench:arcadedb, which installs the pin"; exit 1; }}
say "$ID: dbbench:arcadedb runs JPype $IJ, the pin"
PAIR_IMAGE="$ARCADEDB_SERVER_IMAGE" ./verify_pair_c25.sh "$SHA" >> "$S" 2>&1 || {{ say "$ID ABORT: pair unverified at the pin"; exit 1; }}
'''

COMPARATOR_POST_CHECKS = "# (no ArcadeDB arm in this stage: dbbench:arcadedb and the pair are not checked, see ARCADE_PRE_BUILD)"


def has_arcadedb_arm(backends):
    """True when the stage runs an ArcadeDB arm (embedded or served), which is when the pair's guards apply."""
    return any(engine_of(b) == "arcadedb" for b in backends)


# The stage script. Braces are doubled where bash needs one. The parameters that change with the instrument are the instrument
# itself ({instrument}), the repetitions ({reps}), the rows file suffix ({rows_suffix}) and the banner ({banner}); the rest is
# per stage (stage_script) or per release pair.
HEAD = '''#!/bin/bash
# {id}. {instrument} instrument stage {n} of {total}: {title}.
#
{banner}
# that file, not this one, and
# never edit this file while it is running: bash reads a script by byte
# offset, so a mid-run edit resumes mid-token.
#
# Backends come from runner.LANES[{lane!r}] ({nbe} of them) and the cap from
# runner.TIMEOUT_BY_SCALE, so neither can disagree with the harness.
set -u
ID={id}
S=$HOME/STATUS.txt
REPO=$HOME/repos/humemai/arcadedb-embedded-python
R=$REPO/benchmarks/experiments
SHA={sha}
PIN=${{SHA:0:9}}
PRIOR_RF="runs_page_{prior}.jsonl"   # October's rows: cell_cost_check's prior
RF="runs_page_${{PIN}}{rows_suffix}.jsonl"   # land_stage.py pulls this exact name; the
                              # PIN separates October from September, so
                              # a second convention would only mean
                              # land_stage silently pulls nothing.
REPS={reps}   # fixed at generation (make_2611_stages --reps)
PASS={pass_no}   # the ONE repetition this stage runs (rep-major: the chain runs pass 1 of every stage, then pass 2, ...)
say() {{ echo "[$(date -Is)] $*" >> "$S"; }}
{wait}
# AN ABORT MUST NOT STRAND THE CHAIN. Every ABORT hands on (the convention of the qMA stages: "an EXIT trap set after the wait
# writes its own marker, so ABORT/SKIP still hand on"). This trap used to be set after the guards, so a guard that failed
# before the START line exited without a marker and the stages waiting on this one waited forever -- which is what happened
# on 2026-09-20 when a guard of mine aborted a healthy stage and left the host idle. Set from here on, the marker is written
# whatever happens: the ABORT is already in STATUS.txt and loud (mini_watch.sh greps it), and the rest of the campaign is worth
# more than making a human notice sooner. It is set after the wait, so a waiter that is killed does not hand on.
trap 'echo "$ID ALL-DONE" >> "$S"' EXIT
cd "$REPO" && git pull -q --ff-only || {{ say "$ID ABORT: pull"; exit 1; }}
cd "$R" || exit 1
export PATH=$HOME/.local/bin:$PATH
# THE NEXT INSTRUMENT (CAMPAIGN, ONE LINE OF DEVELOPMENT): this stage measures {instrument} and nothing else. Mini pulls main at
# every stage start, so the selector must already be in the tree, and what it selects is read back before a cell runs.
export BENCH_INSTRUMENT={instrument}
python3 -c 'import sys, bench_common; sys.exit(0 if bench_common.INSTRUMENT == "{instrument}" else 1)' || {{ say "$ID ABORT: the tree does not select instrument {instrument}"; exit 1; }}

# --- the instrument must be the MERGED October one ------------------------
grep -q 'import budget_lookup' l2_graph.py || {{ say "$ID ABORT: no budget lookup (pre-merge tree)"; exit 1; }}
[ -f equivalence_check.py ] || {{ say "$ID ABORT: no equivalence_check.py (pre-merge tree)"; exit 1; }}
[ -f budgets.py ] || {{ say "$ID ABORT: no budgets.py"; exit 1; }}
python3 - <<'PY' || {{ say "$ID ABORT: cap table failed its check"; exit 1; }}
import ast, collections, sys
tree = ast.parse(open("runner.py").read())
for n in ast.walk(tree):
    if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "TIMEOUT_BY_SCALE" for t in n.targets):
        keys = [k.value for k in n.value.keys]
        dup = [k for k, c in collections.Counter(keys).items() if c > 1]
        if dup:
            sys.exit(f"TIMEOUT_BY_SCALE has duplicate keys {{dup}} (BUGS F62 is back)")
        d = eval(compile(ast.Expression(n.value), "<d>", "eval"))
        for tier, want in {caps!r}:
            if d.get(tier) != want:
                sys.exit(f"cap for {{tier}} is {{d.get(tier)}}, expected {{want}}")
        break
else:
    sys.exit("no TIMEOUT_BY_SCALE")
PY
# NO SHADOWED DEFINITION ANYWHERE IN THE LANE MODULES. A merge that keeps
# both sides of a class, function or module-level name leaves the LAST one
# winning, and nothing notices: it compiles, it imports, every gate passes,
# and the defect surfaces only when a real cell exercises that code. The
# October merge did this three times -- two duplicate dict keys, a duplicate
# NOT_PRINTED binding, and two DuckpgqGraph classes where the stale one
# returned row COUNTS instead of rows, which crashed every DuckPGQ cell in
# the first stage. Checking the effective value cannot see any of them.
python3 - <<'PY' || {{ say "$ID ABORT: a shadowed definition is back"; exit 1; }}
import ast, collections, glob, sys
bad = []
for f in sorted(glob.glob("*.py")):
    try:
        tree = ast.parse(open(f, errors="replace").read())
    except SyntaxError as exc:
        sys.exit(f"{{f}} does not parse: {{exc}}")
    names = collections.defaultdict(list)
    for n in tree.body:
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names[n.name].append(n.lineno)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names[t.id].append(n.lineno)
    for k, v in names.items():
        if len(v) > 1:
            bad.append(f"{{f}}:{{k}} at lines {{v}}")
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            ks = [k.value for k in n.keys if isinstance(k, ast.Constant)]
            dup = [k for k, c in collections.Counter(ks).items() if c > 1]
            if dup:
                bad.append(f"{{f}}:{{n.lineno}} dict literal repeats {{dup}}")
if bad:
    for _b in bad:
        print("  shadowed:", _b)
    sys.exit(1)
PY
# THE BUDGETS MUST FIT THE CAP. Each lane's flat fallback was chosen for ONE
# query and never multiplied by the number of queries in the lane: on
# 2026-09-20 the documents lane's five queries at 1,800 s each came to 9,000 s
# against a 7,200 s cap -- 125%, so every engine that used its budgets was
# censored by arithmetic before anything ran slowly. Fallbacks are clamped to
# a share of the cap now; this refuses anyway, because a MEASURED budget is
# deliberately not clamped and a tier whose measured budgets exceed its cap is
# telling you the cap is wrong.
python3 - <<'PY' || {{ say "$ID ABORT: this tier's budgets do not fit its cap"; exit 1; }}
import sys
import runner, budget_lookup as B
LANE = {lane!r}
for tier in {scales!r}:
    cap = float(runner.TIMEOUT_BY_SCALE[tier])
    if LANE == "l2":
        import graph_common as G
        qs = [q for q in G.OLAP_QUERIES if not G.tier_excluded(tier, q)]
        dflt = G.OLAP_BUDGET_S
    elif LANE == "l1tpc":
        import l1_tpc
        qs, dflt = list(l1_tpc.OLAP_QUERIES), l1_tpc.OLAP_BUDGET_S
    elif LANE == "l4":
        import l4_tsbs
        qs, dflt = list(l4_tsbs.QUERIES), l4_tsbs.QUERY_BUDGET_S
    else:
        continue
    tot = sum(B.budget_for(LANE, tier, q, dflt, None, n_queries=len(qs))[0] for q in qs)
    pct = tot / cap * 100
    print(f"  budgets {{LANE}}/{{tier}}: {{tot:.0f}}s = {{pct:.0f}}% of the {{cap:.0f}}s cap")
    if tot >= cap:
        sys.exit(f"{{LANE}}/{{tier}}: budgets alone are {{pct:.0f}}% of the cap")
PY

# --- will the WHOLE CELL fit, first touches included? ----------------------
# The budget check above bounds what ITERATIONS may cost. It cannot see the
# FIRST TOUCH, which #82b makes always complete, and that is the gap that
# actually bit: October's first analytics cell was censored at its 7,200 s
# cap while its budgets summed to 3,480 s -- 48 percent -- because one
# query (lsqb_q6) spent 1,384 s on its first touch alone (#109, BUGS F74).
# cell_cost_check adds ingest + measured first touches + the budget ceiling
# and compares the total against the cap.
#
# THREE OUTCOMES, AND ONLY ONE STOPS A STAGE. rc=1 is a scored projection
# over the cap: a stage that would burn hours to publish censored cells.
# rc=2 is the tool REFUSING to score because the rows do not cover this
# tier query roster yet, which is the normal state for a tier nobody has
# measured and must never block it -- that refusal exists because the tool
# once scored 5 of 14 queries and reported ok.
for _tier in {scale_list}; do
  python3 cell_cost_check.py --lane {lane} --tier "$_tier" --backends "{backends}" --rows "results/$RF" >> "$S" 2>&1
  _cc=$?
  if [ $_cc -eq 1 ]; then
    say "$ID ABORT: projected cell cost exceeds the cap at $_tier (cell_cost_check)"
    exit 1
  elif [ $_cc -eq 2 ]; then
    if [ -f "results/$PRIOR_RF" ]; then
      python3 cell_cost_check.py --lane {lane} --tier "$_tier" --backends "{backends}" --rows "results/$PRIOR_RF" >> "$S" 2>&1
      case $? in
        1) say "$ID WARNING: $_tier projected over the cap from October's rows ($PRIOR_RF); this pin has none yet, so it runs and its censored cells are what the projection said" ;;
        0) say "$ID: $_tier scored from October's rows ($PRIOR_RF): fits" ;;
        *) say "$ID: cell cost not scored at $_tier, no first-touch rows for this roster at either pin" ;;
      esac
    else
      say "$ID: cell cost not scored at $_tier, no first-touch rows for this roster yet"
    fi
  fi
done
{guards}
# --- images and the pinned pair -------------------------------------------
{pre_build}
BENCH_ALLOW_DEV=0 ./build_images.sh {images} >> "$S" 2>&1 || {{ say "$ID ABORT: image build"; exit 1; }}
# ARTIFACT EXISTS IS NOT ARTIFACT BUILT: a target that silently did
# nothing leaves no image, and the first cell to want it reports
# server_not_ready. Check here, where the message can name the cause.
for _img in {images}; do
  # the arcadedb image is tagged with the pinned version, never floating (engine_pin.py)
  _tag="dbbench:$_img"; [ "$_img" = "arcadedb" ] && _tag="dbbench:arcadedb-$(basename "$ARCADEDB_WHEEL" | cut -d- -f2)"
  docker image inspect "$_tag" >/dev/null 2>&1 || {{ say "$ID ABORT: $_tag missing after build"; exit 1; }}
done
say "$ID: images present: {images}"
# AND THE ONES WE PULL RATHER THAN BUILD. Everything above checks images this
# stage BUILDS; a digest-pinned comparator is fetched lazily by the first
# `docker run` that names it, so a slow registry or a digest collected
# upstream shows up as a failed cell deep into the stage instead of an abort
# in its first minute. On 2026-09-22 five pinned images were absent from this
# host -- elasticsearch, milvus at 3.7 GB, pgvector, postgres, qdrant -- with
# three queued stages needing them and nothing checking. Pulled by digest, so
# the pull IS the verification: a digest that no longer resolves cannot be
# satisfied by a tag that moved.
for _pin in {pulled}; do
  [ -n "$_pin" ] || continue   # the empty element a lane with no pinned image renders
  docker image inspect "$_pin" >/dev/null 2>&1 && continue
  say "$ID: pulling $_pin"
  docker pull -q "$_pin" >> "$S" 2>&1 || {{ say "$ID ABORT: cannot pull $_pin"; exit 1; }}
done
# IMAGES PRESENT IS NOT IMAGES CURRENT, and the difference cost two hours a
# cell. dbbench:pg-age sat on PostgreSQL 17 for nine days after the pin moved
# to 18 while this very check reported "present"; AGE 1.7.0 builds edges 65x
# slower than 1.8.0, so the cross-model cell at e2_500k burned the whole cap
# and read as an engine limit (BUGS F90, F76). The ArcadeDB arm has been
# verified by content since August -- the pair check below reads the jar's own
# build number -- and this gives every comparator the same treatment, by
# reading each image's versions back out of the image before any cell runs.
python3 version_pin_check.py --runtime >> "$S" 2>&1 || {{ say "$ID ABORT: an image does not carry the version it is pinned to"; exit 1; }}
say "$ID: images carry their pins"
{post_checks}
export ARCADEDB_ENGINE_COMMIT=$PIN BENCH_DATA=$HOME/bench-data BENCH_HOST=mini
export BENCH_CPUSET=0-11 BENCH_GRAPH_SOURCE=ldbc
{stage_env}

BACKENDS="{backends}"
say "$ID START: {title}, {nbe} engines, rep pass $PASS of $REPS, pin $PIN, instrument {instrument}"

{cap_rule_helpers}
{rep_helpers}
run_overlay() {{  # <label> <scale> <cap> <be> <wl> <driver> <outdir> <rf> <reps> <env>
  local label=$1 scale=$2 cap=$3 be=$4 wl=$5 drv=$6 outdir=$7 orf=$8 oreps=$9 oenv=${{10}}
  # ONE RECORDED FAILURE PER ARM (BUGS F162, DECISIONS #127). Rep 1 first; the later passes run only when rep 1 left a clean row
  # (rep_gate). The sparse driver repeats inside itself (oreps 1): it runs in pass 1 only, as one invocation.
  cap_rule_skip "$label" "$be|$wl|" && return 0
  [ "$PASS" -le "$oreps" ] || return 0
  rep_gate "$label" || return 0
  local onlyreps=
  [ "$oreps" -lt 2 ] || onlyreps="--only-reps $PASS"
  if env $oenv python3 runner.py --lanes {lane} --scale "$scale" --backends "$be" \\
    --workloads "$wl" --tier paper --workers 1 --timeout "$cap" $onlyreps --reps "$oreps" --driver "$drv" \\
    --driver-out-dir "$outdir" --results-file "$orf" >> "$S" 2>&1; then
    rep_note "$label" "$PASS" ok
  else
    rep_note "$label" "$PASS" fail
    say "$ID: $label OVERLAY rep $PASS failed (the table reads this, not the lane row)"
  fi
  return 0
}}

run_cell() {{   # run_cell <label> <scale> <cap> <backend> <workload> <env-or-empty> [durability-flag]
  local label=$1 scale=$2 cap=$3 be=$4 wl=$5 envset=$6
  # THE CLASS IS A CLI FLAG, NOT AN ENVIRONMENT VARIABLE. runner.py assigns
  # os.environ["BENCH_DURABILITY"] from --durability, whose default is
  # "relaxed", so exporting BENCH_DURABILITY=strict into the environment is
  # overwritten before any lane reads it and the cell runs relaxed while
  # claiming nothing. Unquoted on purpose: "--durability strict" must reach
  # the runner as two words, which is what bash does here.
  local dur=${{7:-}}
  cap_rule_skip "$label" "$be|$wl|$dur" && return 0
  rep_gate "$label" || return 0
  env $envset python3 runner.py --lanes {lane} --scale "$scale" --backends "$be" \\
    --workloads "$wl" --tier paper --workers 1 --timeout "$cap" $dur \\
    --only-reps "$PASS" --reps "$REPS" --results-file "$RF" >> "$S" 2>&1
  if [ $? -ne 0 ]; then
    rep_note "$label" "$PASS" fail
    # only a TIMEOUT of rep 1 censors the larger sizes; a later pass fails on its own
    if [ "$PASS" -eq 1 ]; then cap_rule_note "$be|$wl|$dur" "$scale"; say "$ID: $label rep 1 failed, not repeating it"
    else say "$ID: $label rep $PASS failed"; fi
    return 0
  fi
  rep_note "$label" "$PASS" ok
}}
'''


REP_HELPERS = r"""
# REP-MAJOR (the user, 2026-10-23: "do n=1 for all dbs and then do the n=2, etc."). This stage runs ONE repetition, $PASS, of every
# cell it owns. The chain runs pass 1 of every stage (core lanes, then the second list), then pass 2 of every stage, then pass 3,
# so when time runs out every engine has the same n, and reps days apart show drift. WHICH REPS EXIST is written to REPSTATE, one
# line per finished repetition (<label> TAB <rep> TAB ok|fail); the runner's own rows (rep numbered in the row, appended to $RF) are
# the data, this file only drives the order. Stopping after any pass leaves a valid n; a later pass picks up from it with no
# regeneration, and a restarted stage skips what is already clean. Delete REPSTATE to start the chain over.
REPSTATE=$HOME/rep-state-@INSTRUMENT@-$PIN.tsv
rep_done() {  # <label> <rep>: true when that repetition of the cell finished CLEAN (a fail is retried by a restart)
  grep -qxF -- "$1"$'\t'"$2"$'\t'ok "$REPSTATE" 2>/dev/null
}
rep_note() {  # <label> <rep> <ok|fail>
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$REPSTATE"
}
rep_gate() {  # <label>: true when this pass may run the cell; says why when it may not
  [ "$PASS" -le "$REPS" ] || return 1   # a cell whose stage environment declares fewer reps (REPS=k) is done after k passes
  if rep_done "$1" "$PASS"; then say "$ID: $1 rep $PASS is already clean, not rerun"; return 1; fi
  if [ "$PASS" -gt 1 ] && ! rep_done "$1" 1; then say "$ID: $1 has no clean rep 1, rep $PASS not run (rep 1 first)"; return 1; fi
  return 0
}
""".replace("@INSTRUMENT@", INSTRUMENT)


def stage_params(reps):
    """What the template takes besides the stage and the pins: the instrument, REPS and the banner, the suffix of the rows
    files they write, the pin whose rows cell_cost_check scores a tier from until this pass has measured it, the JPype pin and
    the cap rule's bash."""
    return {"instrument": INSTRUMENT, "reps": reps, "banner": BANNER, "rows_suffix": ROWS_SUFFIX, "prior": PRIOR_PIN,
            "jpype_version": bench_common.JPYPE_PIN, "cap_rule_helpers": CAP_RULE_HELPERS.lstrip("\n"),
            "rep_helpers": REP_HELPERS.lstrip("\n"), "pass_no": 1}


def _pair_part(text, pins, params):
    return text.format(wheel_name=pins["wheel_name"], wheel_sha256=pins["wheel_sha256"],
                       server_image=pins["ARCADEDB_SERVER_IMAGE"], jpype_version=params["jpype_version"])


def stage_script(idx, total, spec, after, pins, params):
    """One stage's script. THE ROSTER IS stage_backends(spec), never the lane's whole arm list: that would put an arm that
    runs only part of its lane into the lane's main stage as well."""
    sid, title, lane, workloads, scales, guards, extra, stage_env = spec[:8]
    # spec[9]: None runs both classes where F10b applies, "strict" runs only the strict pass, "relaxed" only the relaxed one
    dur_mode = spec[9] if len(spec) > 9 else None
    backends = stage_backends(spec)
    guards = list(guards) + _pin_guard(backends)
    arcade = has_arcadedb_arm(backends)
    caps = [(s, runner.TIMEOUT_BY_SCALE[s]) for s in scales]
    body = HEAD.format(
        id=sid, n=idx + 1, total=total, title=title, lane=lane, nbe=len(backends), sha=pins["ARCADEDB_ENGINE_COMMIT"],
        wait=_wait(after), caps=caps, scales=list(scales), scale_list=" ".join(scales),
        guards="\n".join(guards) + ("\n" if guards else ""),
        stage_env=("export " + " ".join(stage_env) if stage_env else "# (this lane's in-script defaults are what the frozen rows ran)"),
        backends=" ".join(backends), images=" ".join(_images_for(backends)),
        # ONE SHAPE FOR BOTH CASES: an empty string is a valid word the loop skips, a comment is a bash syntax error
        pulled=(" ".join(f'"{i}"' for i in _pulled_images_for(backends)) or '""'),
        wheel_name=pins["wheel_name"], wheel_sha256=pins["wheel_sha256"], server_image=pins["ARCADEDB_SERVER_IMAGE"],
        pre_build=_pair_part(ARCADE_PRE_BUILD if arcade else COMPARATOR_PRE_BUILD, pins, params),
        post_checks=_pair_part(ARCADE_POST_CHECKS if arcade else COMPARATOR_POST_CHECKS, pins, params),
        **params)
    for scale, cap in caps:
        senv = " ".join(SCALE_ENV.get((lane, scale), []))
        body += f'\nfor BE in $BACKENDS; do\n'
        for wl in workloads:
            if dur_mode != "strict":
                body += (f'  run_cell "{lane}/{scale}/$BE/{wl}" {scale} {cap} '
                         f'"$BE" {wl} "{senv}"\n')
            if (lane, wl) in STRICT_WORKLOADS and dur_mode != "relaxed":
                body += (f'  run_cell "{lane}/{scale}/$BE/{wl} strict" {scale} {cap} '
                         f'"$BE" {wl} "{senv}" "--durability strict"\n')
            for be, envs in sorted(extra.items()):
                for e in envs:
                    body += (f'  [ "$BE" = "{be}" ] && run_cell '
                             f'"{lane}/{scale}/$BE/{wl} {e}" {scale} {cap} "$BE" {wl} "{e}"\n')
            if lane in OVERLAY:
                drv, oreps, dirs = OVERLAY[lane]
                outdir, orf = (rows_name(x) for x in dirs[scale])
                oenv = " ".join(x for x in [senv, OVERLAY_ENV.get(lane, "")] if x)
                body += (f'  run_overlay "{lane}/{scale}/$BE/{wl} multipass" {scale} {cap} '
                         f'"$BE" {wl} {drv} "{outdir}" "{orf}" {oreps} "{oenv}"\n')
        body += 'done\n'
        if lane in OVERLAY:
            outdir = rows_name(OVERLAY[lane][2][scale][0])
            body += (f'N=$(ls results/{outdir}/ 2>/dev/null | wc -l)\n'
                     f'say "$ID: {scale} overlay dir holds $N file(s)"\n'
                     f'[ "$N" -gt 0 ] || say "$ID WARNING: {scale} overlay produced NO files; '
                     f'the table reads this directory and would publish nothing"\n')
        body += f'say "$ID: {scale} done"\n'
    body += 'say "$ID finished"   # the EXIT trap writes the ALL-DONE marker\n'
    return apply_cap_rule(body, lane, set(backends), set(workloads))


def emit_all(out, stages, pins, first_after, reps):
    """Write every stage script. `pins` holds ARCADEDB_WHEEL, ARCADEDB_SERVER_IMAGE and ARCADEDB_ENGINE_COMMIT, and may hold
    ARCADEDB_WHEEL_SHA256 for a release that is not on disk at generation (--arcadedb-release); otherwise the file's own
    sha256 is what the stages demand."""
    wheel = pins["ARCADEDB_WHEEL"]
    wheel_sha = pins.get("ARCADEDB_WHEEL_SHA256") or hashlib.sha256(open(wheel, "rb").read()).hexdigest()
    pins = dict(pins, wheel_name=os.path.basename(wheel), wheel_sha256=wheel_sha)
    plan = pass_plan(stages, reps)
    for i, (spec, pass_no) in enumerate(plan):
        after = first_after if i == 0 else plan[i - 1][0][0]
        params = dict(stage_params(reps), pass_no=pass_no)
        p = os.path.join(out, f"{spec[0]}.sh")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(stage_script(i, len(plan), spec, after, pins, params))
        os.chmod(p, 0o755)
        print(f"  {spec[0]}.sh  pass {pass_no}/{reps} lane={spec[2]:9} backends={len(stage_backends(spec)):2}  "
              f"scales={','.join(spec[4]) or '-'}  after={after}")


def stage_reps(spec, reps):
    """The repetitions a stage runs: the chain's, or fewer when its environment declares REPS=k (the image defaults arm)."""
    for e in (spec[7] if len(spec) > 7 and spec[7] else []):
        if isinstance(e, str) and e.startswith("REPS="):
            return min(reps, int(e[5:]))
    return reps


def pass_plan(stages, reps):
    """REP-MAJOR. [(stage spec, pass)] in run order: pass 1 of every stage in `stages` (their own order), then pass 2 of the stages
    that run a second repetition, and so on up to `reps`. Ids are renumbered over the whole run, keeping the prefix of the first
    stage's, so each stage still waits on the one before it in id order. A single pass keeps `stages` as numbered."""
    if reps == 1 or not stages:
        return [(s, 1) for s in stages]
    prefix = re.match(r"^(\D+)", stages[0][0]).group(1)
    runs = [(s, p) for p in range(1, reps + 1) for s in stages if stage_reps(s, reps) >= p]
    out = []
    for k, (s, p) in enumerate(runs):
        title = f"{s[1]} [rep pass {p} of {reps}]"
        out.append((tuple([f"{prefix}{k + 1:02d}", title] + list(s[2:])), p))
    return out


def _after_arg(text):
    """`--after none` (or an empty string) is no wait. An empty id must never reach _wait: it would write
    `grep -q " ALL-DONE"`, which matches the first marker line in STATUS.txt and starts the stage at once
    while looking like a wait."""
    t = text.strip()
    return None if t.lower() in ("", "none") else t


def _wait(after):
    return ("" if after is None else
            f'\nwhile ! grep -qx "{after} ALL-DONE" "$S" 2>/dev/null; do sleep 300; done\n'
            f'say "$ID: {after} finished, taking the machine"\n')


# ------------------------------------------------------------------------------------------------------ the pair
PAIR = '''#!/bin/bash
# {id}. The ArcadeDB {release} matched pair (official image by digest, PyPI wheel by sha256, pin {sha}).
#
# GENERATED by make_2611_stages.py --arcadedb-release. Copy of the 26.10.2 pair install's steps; nothing here is found,
# everything is named: the image digest, the wheel file name, its sha256 and its URL were given at generation.
ID={id}; S=$HOME/STATUS.txt; REPO=$HOME/repos/humemai/arcadedb-embedded-python; R=$REPO/benchmarks/experiments
say() {{ echo "[$(date -Is)] $*" >> "$S"; }}
{wait}
trap 'echo "$ID ALL-DONE" >> "$S"' EXIT
SHA={sha}; IMG=arcadedb-c25:${{SHA:0:9}}
DIG={digest}
WN={wheel_name}; WSHA={wheel_sha256}
WURL={wheel_url}
say "$ID START: the {release} matched pair (official image by digest, PyPI wheel by sha256, pin $SHA)"
cd "$REPO" && git pull -q --ff-only || {{ say "$ID ABORT: pull"; exit 1; }}
docker pull -q "arcadedata/arcadedb@$DIG" >> "$S" 2>&1 || {{ say "$ID ABORT: docker pull of the {release} image"; exit 1; }}
cd "$R" && bash build_matched_pair.sh "$DIG" >> "$S" 2>&1 || {{ say "$ID ABORT: build_matched_pair.sh"; exit 1; }}
docker image inspect "$IMG" > /dev/null 2>&1 || {{ say "$ID ABORT: no $IMG after the pair build"; exit 1; }}
T=$(mktemp -d); curl -sf -o "$T/$WN" "$WURL" && [ "$(sha256sum "$T/$WN" | cut -c1-64)" = "$WSHA" ] || {{ say "$ID ABORT: PyPI wheel download or sha256"; exit 1; }}
mkdir -p "$HOME/dist-archive" && mv "$REPO"/bindings/python/dist/*.whl "$HOME/dist-archive/" && mv "$T/$WN" "$REPO/bindings/python/dist/" || {{ say "$ID ABORT: dist swap"; exit 1; }}
say "$ID: dist/ holds $WN only (the previous wheel moved to ~/dist-archive)"
ARCADEDB_WHEEL="$REPO/bindings/python/dist/$WN" ARCADEDB_SERVER_IMAGE="$IMG" BENCH_ALLOW_DEV=0 bash build_images.sh arcadedb >> "$S" 2>&1 || {{ say "$ID ABORT: build_images.sh arcadedb"; exit 1; }}
PAIR_IMAGE="$IMG" bash verify_pair_c25.sh "$SHA" >> "$S" 2>&1 || {{ say "$ID ABORT: pair unverified"; exit 1; }}
say "$ID finished: pair verified at ${{SHA:0:9}}; the lane stages start"
'''

RELEASE_RE = re.compile(r"\d+\.\d+\.\d+")


def release_pins(a):
    """The ArcadeDB release mode's pins, all from explicit arguments. Refuses anything missing or malformed: the release may
    not exist yet, and a digest or checksum guessed at generation would pin an engine nobody chose."""
    need = [("--engine-commit", a.engine_commit), ("--image-digest", a.image_digest), ("--wheel-name", a.wheel_name),
            ("--wheel-sha256", a.wheel_sha256), ("--wheel-url", a.wheel_url)]
    missing = [n for n, v in need if not v]
    if missing:
        raise SystemExit(f"REFUSING --arcadedb-release {a.arcadedb_release}: {', '.join(missing)} not given. The release's "
                         f"image digest and wheel sha256 are written down after it is published, never guessed.")
    if not RELEASE_RE.fullmatch(a.arcadedb_release):
        raise SystemExit(f"REFUSING: --arcadedb-release {a.arcadedb_release} is not one stable x.y.z (the paper cites releases)")
    if not re.fullmatch(r"[0-9a-f]{40}", a.engine_commit):
        raise SystemExit("REFUSING: --engine-commit must be the full 40-character commit")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", a.image_digest):
        raise SystemExit("REFUSING: --image-digest must be sha256:<64 hex>, the official image by digest")
    if not re.fullmatch(r"[0-9a-f]{64}", a.wheel_sha256):
        raise SystemExit("REFUSING: --wheel-sha256 must be 64 hex characters")
    if not re.fullmatch(rf"arcadedb_embedded-{re.escape(a.arcadedb_release)}-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+\.whl",
                        a.wheel_name):
        raise SystemExit(f"REFUSING: --wheel-name {a.wheel_name} is not a {a.arcadedb_release} arcadedb_embedded wheel")
    if not a.wheel_url.startswith("https://") or not a.wheel_url.endswith(a.wheel_name):
        raise SystemExit("REFUSING: --wheel-url must be an https URL ending in the wheel's file name")
    return {"ARCADEDB_WHEEL": os.path.join("bindings", "python", "dist", a.wheel_name),
            "ARCADEDB_WHEEL_SHA256": a.wheel_sha256,
            "ARCADEDB_SERVER_IMAGE": f"arcadedb-c25:{a.engine_commit[:9]}",
            "ARCADEDB_ENGINE_COMMIT": a.engine_commit}


def installed_pins():
    """The comparator mode's pins: the release pair already installed, from the environment."""
    pins = {k: os.environ.get(k, "").strip() for k in ("ARCADEDB_WHEEL", "ARCADEDB_SERVER_IMAGE", "ARCADEDB_ENGINE_COMMIT")}
    missing = [k for k, v in pins.items() if not v]
    if missing:
        raise SystemExit(f"REFUSING to emit: {', '.join(missing)} unset. The stages are generated for one release pair: "
                         f"the wheel file, the server image, and the engine commit.")
    if not re.fullmatch(r"[0-9a-f]{40}", pins["ARCADEDB_ENGINE_COMMIT"]):
        raise SystemExit("ARCADEDB_ENGINE_COMMIT must be the full 40-character commit")
    if not os.path.isfile(pins["ARCADEDB_WHEEL"]):
        raise SystemExit(f"ARCADEDB_WHEEL is not a file: {pins['ARCADEDB_WHEEL']}")
    ver = os.path.basename(pins["ARCADEDB_WHEEL"]).split("-")[1]
    if re.search(r"(dev|rc|a|b)\d*$|SNAPSHOT", ver):
        raise SystemExit(f"REFUSING to emit: wheel {ver} is a pre-release; the paper cites stable releases")
    return pins


def write_pair(out, pair_id, a, after):
    p = os.path.join(out, f"{pair_id}.sh")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(PAIR.format(id=pair_id, release=a.arcadedb_release, sha=a.engine_commit, wait=_wait(after),
                             digest=a.image_digest, wheel_name=a.wheel_name, wheel_sha256=a.wheel_sha256,
                             wheel_url=a.wheel_url))
    os.chmod(p, 0o755)
    print(f"  {pair_id}.sh  the {a.arcadedb_release} matched pair  after={after}")


def load_hours(path, reps):
    """{(lane, workload, scale, backend, class): hours at `reps` repetitions} from a per-cell hours table: tab separated, a
    header line naming lane workload scale backend class h3 h5, one row per cell (a cell with no clean rep carries its one
    failed attempt in both columns)."""
    if reps not in (3, 5):
        raise SystemExit("--project prices 3 or 5 repetitions (the table's two columns)")
    with open(path, encoding="utf-8") as fh:
        rows = [ln.rstrip("\n").split("\t") for ln in fh if ln.strip() and not ln.startswith("#")]
    head = rows[0]
    if head[:7] != ["lane", "workload", "scale", "backend", "class", "h3", "h5"]:
        raise SystemExit(f"{path}: not a per-cell hours table (header {head[:7]})")
    col = 5 if reps == 3 else 6
    return {tuple(r[:5]): float(r[col]) for r in rows[1:] if len(r) > col}


def project_hours(stages, hours):
    """[(stage id, hours, cells priced, cells with no row)] from the lane cells of each stage (an overlay or second pass runs
    inside its lane cell's time)."""
    out = []
    for st in stages:
        h, n, miss = 0.0, 0, 0
        for c in stage_cells(st):
            if c.kind != "lane" or c.arm:
                continue
            v = hours.get((c.lane, c.workload, c.scale, c.backend, c.cls))
            if v is None:
                miss += 1
            else:
                h, n = h + v, n + 1
        out.append((st[0], h, n, miss))
    return out


def print_projection(stages, cells_tsv, reps):
    cum = 0.0
    print(f"\nPROJECTION, not measured at this instrument: the per-cell table's time for {reps} repetitions, per drafted stage")
    for (sid, h, n, miss), st in zip(project_hours(stages, load_hours(cells_tsv, reps)), stages):
        cum += h
        print(f"  {sid}  {h:6.1f} h  cum {cum:6.1f}  ({n} cells priced" + (f", {miss} with no row" if miss else "") + f")  {st[1]}")
    print(f"  total {cum:.0f} h over {len(stages)} stages (the new instrument's longer query sets are not priced)")


# ------------------------------------------------------------------------------------------------------------ main
def _after(text):
    return _after_arg(text) if text is not None else False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the next instrument's multi-model subset stages")
    ap.add_argument("--out", help="directory for the generated scripts (a draft folder, not the repo)")
    ap.add_argument("--after", help="the marker the first stage waits on (`<name> ALL-DONE`): the LAST item of the queue already on the "
                                    "machine, e.g. `mini-ab FINAL` on mini; `none` for no wait. Required to emit, no default")
    ap.add_argument("--status-file", metavar="PATH|none",
                    help="a copy of the machine's STATUS.txt: the generator refuses an --after marker already in it (the first stage "
                         "would start at once). Required to emit with a marker; `none` says there is no queue to wait for. "
                         "With --check --drafts DIR: also refuses drafts whose first wait is already true there")
    ap.add_argument("--id-prefix", default=DEFAULT_PREFIX, help=f"stage id prefix (default {DEFAULT_PREFIX})")
    ap.add_argument("--engines", help=f"comma list of subset engines ({', '.join(ENGINES)}); default every engine of the mode")
    ap.add_argument("--lanes", help="comma list: graph, cross-model, documents, dense (core); sparse, timeseries, lifecycle "
                                    "(second list, needs --second-list); runner lane ids work too")
    ap.add_argument("--second-list", action="store_true", help="add the second list: sparse, time series, lifecycle")
    ap.add_argument("--reps", type=int, default=3, help="repetitions per cell, 1 to 5 (default 3)")
    ap.add_argument("--order", choices=("biggest-last", "paper"), default="biggest-last",
                    help="biggest-last (default): core block first, then lifecycle, sparse, time series; inside the core block "
                         "large tiers after small ones and the biggest cells last; paper: the table order, no splits")
    ap.add_argument("--without-timescaledb", action="store_true",
                    help="leave TimescaleDB out of the time-series lane (it is in by default: it completes the PostgreSQL "
                         "arm with pgvector and AGE)")
    ap.add_argument("--project", metavar="CELLS_TSV", help="print the projected hours per stage from a per-cell hours table (header: lane workload scale backend class h3 h5; reps 3 or 5)")
    ap.add_argument("--check", action="store_true", help="selection, coverage and instrument proofs only; no pins needed")
    ap.add_argument("--drafts", metavar="DIR", help="with --check: also lint the scripts in DIR")
    ap.add_argument("--arcadedb-release", metavar="X.Y.Z", help="ArcadeDB alone on this release (needs the five pin arguments)")
    ap.add_argument("--engine-commit")
    ap.add_argument("--image-digest")
    ap.add_argument("--wheel-name")
    ap.add_argument("--wheel-sha256")
    ap.add_argument("--wheel-url")
    a = ap.parse_args(argv)
    status_file = None if a.status_file is None or a.status_file.strip().lower() == "none" else a.status_file

    problems = instrument_problems()
    if problems:
        for p in problems:
            print(f"  PROBLEM {p}")
        return 1
    if not 1 <= a.reps <= MAX_REPS:
        raise SystemExit(f"--reps must be 1 to {MAX_REPS}")
    mode = "arcadedb" if a.arcadedb_release else "comparators"
    pins = release_pins(a) if a.arcadedb_release else None
    engines = parse_engines(a.engines, mode)
    lanes = parse_lanes(a.lanes, a.second_list)

    jp = check_jpype_pin()
    for p in jp:
        print(f"  PROBLEM jpype pin: {p}")
    if jp:
        return 1
    print(f"jpype pin: {bench_common.JPYPE_PIN}; instrument {INSTRUMENT}; mode {mode}; reps {a.reps}")

    skip = (TIMESCALEDB,) if a.without_timescaledb else ()
    specs = subset_specs(engines, lanes, a.order, skip)
    pair_id = f"{a.id_prefix}00" if mode == "arcadedb" else None
    stages = number(specs, a.id_prefix)
    problems = stage_problems(stages, engines, lanes, skip) + check_coverage()[0]
    print(f"engines: {', '.join(engines)}\nlanes: {', '.join(lanes)}\n{len(stages)} stages, order {a.order}")
    for st in stages:
        bes = stage_backends(st)
        print(f"  {st[0]}  {st[2]:9} {','.join(st[4]) or '-':26} {len(bes):2} arms  {st[1]}")
    if a.check and a.drafts:
        problems += lint_drafts(a.drafts, set(engines), status_file)
    for p in problems:
        print(f"  PROBLEM {p}")
    if problems:
        return 1
    if not stages:
        print("  PROBLEM no stage: the engines and lanes asked for share no cell")
        return 1
    if a.project:
        print_projection(stages, a.project, a.reps)
    print("check: every subset arm of the lanes asked for is in exactly one stage per workload, none outside the subset")
    if a.check:
        return 0

    if not a.out:
        raise SystemExit("--out DIR is required to emit (a draft folder, not the repo)")
    after = _after(a.after)
    if after is False:
        raise SystemExit("--after is required to emit: the stage whose ALL-DONE the first stage waits for, or `none`")
    if after is not None and a.status_file is None:
        raise SystemExit("--status-file is required with an --after marker: a copy of the machine's STATUS.txt, which must not "
                         "hold `<marker> ALL-DONE` yet (or `--status-file none` when there is no queue)")
    bad = status_problems(after, status_file)
    if bad:
        for p in bad:
            print(f"  PROBLEM {p}")
        return 1
    if pins is None:
        pins = installed_pins()
    os.makedirs(a.out, exist_ok=True)
    first_after = after
    if pair_id:
        write_pair(a.out, pair_id, a, after)
        first_after = pair_id
    emit_all(a.out, stages, pins, first_after, a.reps)
    drafts = lint_drafts(a.out, set(engines))
    for p in drafts:
        print(f"  PROBLEM {p}")
    return 1 if drafts else 0


def _entry():
    v = os.environ.get("BENCH_INSTRUMENT")
    if v is None:
        # the arm tables and the START line follow bench_common.INSTRUMENT, read at import: set it, then start over
        env = dict(os.environ, BENCH_INSTRUMENT=INSTRUMENT)
        os.execve(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:], env)
    return main()


if __name__ == "__main__":
    raise SystemExit(_entry())
