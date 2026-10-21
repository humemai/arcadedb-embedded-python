#!/usr/bin/env python3
"""Emit the next instrument's queue scripts: the multi-model subset at N reps, one stage per lane piece.

A PROFILE OF make_2610_stages (which is a profile of make_october_stages), NOT A COPY. Every guard those two carry (the
cap table, shadowed definitions, budgets against the cap, the whole-cell cost, images present AND current, the comparator
digests frozen at generation, the JPype pin read back out of the image, the pinned wheel by sha256, the cap rule, the
ALL-DONE trap) reaches these stages by import. What this file adds is the selection and the instrument:

  * THE SUBSET (PLAN-26111): ArcadeDB (embedded and served), SurrealDB (embedded and served), ArangoDB, Memgraph, PostgreSQL
    with pgvector and AGE (and plain PostgreSQL where a lane uses it), MongoDB (with MongoDB Search), DuckDB (with VSS and
    DuckPGQ), SQLite (with sqlite-vec), and the composed Qdrant plus Neo4j stack. Core lanes: graph (interactive and
    analytics), cross-model, documents (TPC-C and TPC-H), dense. `--second-list` adds sparse, time series and lifecycle.
    The stage list is DERIVED from make_2610_stages.STAGES and runner.LANES, filtered by engine and lane, and `--check`
    proves the filtered list runs exactly the cells the unfiltered one would for those engines and lanes. Every registered
    arm is either in the subset or named in OUTSIDE, so a newly registered arm forces a decision here.
  * THE INSTRUMENT. Every stage exports BENCH_INSTRUMENT=2026-11 before its first python call and aborts if the tree
    does not select it. Rows go to `runs_page_<pin>_2611.jsonl` (and the overlay directories carry the same suffix), never to
    the file a 2026-10 pass wrote for the same pin, so one file never holds two instruments. This generator re-executes
    itself with the variable set; a different value in the environment is refused.
  * TWO MODES. Default: the subset's comparators, on the release pair already installed (ARCADEDB_WHEEL,
    ARCADEDB_SERVER_IMAGE, ARCADEDB_ENGINE_COMMIT, as for make_2610_stages). `--arcadedb-release X.Y.Z`: ArcadeDB alone on
    that release; it refuses unless the engine commit, the official image DIGEST, the wheel name, its sha256 and its URL are
    given on the command line, because the release may not exist when the drafts are made. That mode also writes `<prefix>00`,
    the pair install (official image by digest, wheel by sha256, build_matched_pair.sh, verify_pair_c25.sh), which the
    first lane stage waits for.
  * REPS. `--reps N` (default 3, at most 5) is baked in as `REPS=N`; a stage environment that declares fewer (the image
    defaults arm) keeps its own.
  * THE CHAIN. `--after <stage>` is the marker the first stage waits for (`grep -qx "<stage> ALL-DONE"`), or `none`. It is
    required: the previous chain's last stage is not a default anyone should inherit.
  * ORDER. `paper` (default, the table order), or `hours-asc` / `hours-desc` with `--project CELLS_TSV`, which prices each
    stage from October's measured cells (make_2610_stages.project) scaled to N/5 repetitions.

Usage:
  python3 make_2611_stages.py --check [--drafts DIR]       # selection, coverage and instrument proofs; lints DIR's scripts
  python3 make_2611_stages.py --project CELLS.tsv --check   # plus the projected hours per stage
  ARCADEDB_WHEEL=... ARCADEDB_SERVER_IMAGE=... ARCADEDB_ENGINE_COMMIT=<40 hex> \\
      python3 make_2611_stages.py --after qR15 --id-prefix qS --out DIR [--engines a,b] [--lanes graph,dense] [--second-list]
  python3 make_2611_stages.py --arcadedb-release 26.11.1 --engine-commit <40 hex> --image-digest sha256:<64 hex> \\
      --wheel-name arcadedb_embedded-26.11.1-<tags>.whl --wheel-sha256 <64 hex> --wheel-url <https url> \\
      --after <last comparator stage> --id-prefix qT --out DIR
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys

import bench_common
import make_2610_stages as M
import runner

HERE = os.path.dirname(os.path.abspath(__file__))

INSTRUMENT = "2026-11"
ROWS_SUFFIX = "_2611"
# cell_cost_check's prior for a tier this pass has not measured: the 2026-10 pass-1 rows, the comparators' measured cells
PRIOR_PIN = "d36b4ca3a"
DEFAULT_PREFIX = "qS"
MAX_REPS = 5

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
    """make_2610_stages.STAGES, unnumbered, restricted to the lanes and to the arms of these engines (minus `skip`). A stage
    left with no arm is dropped; the host-side, restart and decomposition stages are not in the subset's lists. Order
    "paper" is the table order; "biggest-last" is described at BIGGEST."""
    base = []
    for spec in M.STAGES:
        s = _spec10(spec)
        if s[2] not in lanes:
            continue
        bes = [b for b in M.stage_backends(spec) if engine_of(b) in engines and b not in skip]
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
    and the exactly-once proof: the cells the list schedules equal the cells make_2610_stages.STAGES schedules for these engines and
    lanes (nothing lost, nothing doubled, nothing extra)."""
    out = arm_problems()
    for st in stages:
        if st[2] not in lanes:
            out.append(f"{st[0]}: lane {st[2]} is not in the lanes asked for")
        for b in M.stage_backends(st):
            if engine_of(b) is None:
                out.append(f"{st[0]}: runs {b}, which is not in the subset")
            elif engine_of(b) not in engines or b in skip:
                out.append(f"{st[0]}: runs {b} ({engine_of(b)}), which is not among the engines asked for")
    want = collections.Counter()
    for spec in M.STAGES:
        if spec[2] not in lanes:
            continue
        s = _spec10(spec)
        s[8] = [b for b in M.stage_backends(spec) if engine_of(b) in engines and b not in skip]
        if not s[8]:   # an empty roster would mean "every arm of the lane" to stage_backends
            continue
        for c in M.stage_cells(tuple(s)):
            want[c] += 1
    have = collections.Counter(c for st in stages for c in M.stage_cells(st))
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
    m = _BACKENDS.search(text)
    if not m:
        out.append(f"{name}: no BACKENDS line")
    else:
        for b in m.group(1).split():
            eng = engine_of(b)
            if eng is None:
                out.append(f"{name}: runs {b}, which is not in the subset")
            elif engines is not None and eng not in engines:
                out.append(f"{name}: runs {b} ({eng}), which is not among the engines asked for")
    return out


def lint_drafts(directory, engines=None):
    """Lint every script in a folder, and check the chain: each stage waits for the one before it in id order."""
    files = sorted(glob.glob(os.path.join(directory, "*.sh")))
    out = []
    if not files:
        return [f"{directory}: no stage scripts"]
    prev = None
    for f in files:
        name = os.path.basename(f)
        text = open(f, encoding="utf-8").read()
        out += lint_draft(text, name, engines)
        waits = re.findall(r'^while ! grep -qx "(\S+) ALL-DONE"', text, re.M)
        if prev is not None and waits != [prev]:
            out.append(f"{name}: waits for {waits or 'nothing'}, expected {prev}")
        prev = name[:-3]
    return out


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
    """The comparator mode's pins: the release pair already installed, from the environment as make_2610_stages reads it."""
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


# --------------------------------------------------------------------------------------------------- the retarget
def _sub(text, old, new, count=1):
    if text.count(old) != count:
        raise SystemExit(f"make_2610_stages' template moved an anchor this profile replaces ({text.count(old)} matches, "
                         f"expected {count}): {old[:70]!r}")
    return text.replace(old, new)


_ROWS_NAME = re.compile(r"(runs_page|dense_mp5(?:_small)?|mp_rows(?:_small|_sparse)?|sparse_mp)_\$\{PIN\}")

INSTRUMENT_BLOCK = f'''export PATH=$HOME/.local/bin:$PATH
# THE NEXT INSTRUMENT (CAMPAIGN, ONE LINE OF DEVELOPMENT): this stage measures {INSTRUMENT} and nothing else. Mini pulls main at
# every stage start, so the selector must already be in the tree, and what it selects is read back before a cell runs.
export BENCH_INSTRUMENT={INSTRUMENT}
grep -q 'def instrument_at_least' bench_common.py || {{ say "$ID ABORT: no BENCH_INSTRUMENT selector in this tree"; exit 1; }}
python3 -c 'import sys, bench_common; sys.exit(0 if bench_common.INSTRUMENT == "{INSTRUMENT}" else 1)' || {{ say "$ID ABORT: the tree does not select instrument {INSTRUMENT}"; exit 1; }}'''


def retarget(body, reps):
    """The instrument half of the stage: BENCH_INSTRUMENT exported and read back, the 2611 rows file and overlay
    directories, REPS fixed, the header says what generated it. Each replacement is asserted."""
    body = _sub(body, "export PATH=$HOME/.local/bin:$PATH", INSTRUMENT_BLOCK)
    body = _sub(body, "REPS=${REPS:-5}", f"REPS={reps}   # fixed at generation (make_2611_stages --reps)")
    body, n = _ROWS_NAME.subn(lambda m: f"{m.group(1)}_${{PIN}}{ROWS_SUFFIX}", body)
    if n < 1:
        raise SystemExit("no rows-file name found to give the 2611 suffix")
    body = _sub(body, "# GENERATED by make_2610_stages.py (a profile of make_october_stages.py) -- edit",
                "# GENERATED by make_2611_stages.py (a profile of make_2610_stages.py and make_october_stages.py) -- edit")
    body = re.sub(r"26\.10\.1 stage (\d+) of", rf"{INSTRUMENT} instrument stage \1 of", body, count=1)
    if f"instrument {INSTRUMENT}\"" not in body:
        raise SystemExit("the START line does not name the instrument")
    return body


def emit(out, stages, pins, first_after, reps, allow_dev, mode, release=None):
    """M.emit_all for the lane stages, then the retarget over each written script (and the pair install in the arcadedb mode)."""
    saved = M.PRIOR_PIN
    M.PRIOR_PIN = PRIOR_PIN
    try:
        M.emit_all(out, pins, first_after, allow_dev=allow_dev, stages=stages)
    finally:
        M.PRIOR_PIN = saved
    for st in stages:
        p = os.path.join(out, f"{st[0]}.sh")
        text = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(retarget(text, reps))
        os.chmod(p, 0o755)


def write_pair(out, pair_id, a, after):
    p = os.path.join(out, f"{pair_id}.sh")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(PAIR.format(id=pair_id, release=a.arcadedb_release, sha=a.engine_commit, wait=M._wait(after),
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
        for c in M.stage_cells(st):
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
    return M._after_arg(text) if text is not None else False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the next instrument's multi-model subset stages")
    ap.add_argument("--out", help="directory for the generated scripts (a draft folder, not the repo)")
    ap.add_argument("--after", help="the stage the first one waits on (its ALL-DONE marker); `none` for no wait. Required to emit")
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

    jp = M.check_jpype_pin()
    for p in jp:
        print(f"  PROBLEM jpype pin: {p}")
    if jp:
        return 1
    print(f"jpype pin: {bench_common.JPYPE_PIN}; instrument {INSTRUMENT}; mode {mode}; reps {a.reps}")

    skip = (TIMESCALEDB,) if a.without_timescaledb else ()
    specs = subset_specs(engines, lanes, a.order, skip)
    pair_id = f"{a.id_prefix}00" if mode == "arcadedb" else None
    stages = number(specs, a.id_prefix)
    problems = stage_problems(stages, engines, lanes, skip)
    print(f"engines: {', '.join(engines)}\nlanes: {', '.join(lanes)}\n{len(stages)} stages, order {a.order}")
    for st in stages:
        bes = M.stage_backends(st)
        print(f"  {st[0]}  {st[2]:9} {','.join(st[4]) or '-':26} {len(bes):2} arms  {st[1]}")
    if a.check and a.drafts:
        problems += lint_drafts(a.drafts, set(engines))
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
    if pins is None:
        pins = installed_pins()
    os.makedirs(a.out, exist_ok=True)
    first_after = after
    if pair_id:
        write_pair(a.out, pair_id, a, after)
        first_after = pair_id
    emit(a.out, stages, pins, first_after, a.reps, allow_dev=False, mode=mode)
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
