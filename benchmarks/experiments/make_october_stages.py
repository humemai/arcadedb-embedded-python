#!/usr/bin/env python3
"""Emit October's queue scripts, one per stage, from one table.

Why generated rather than eight hand-written scripts: they differ in four
fields and agree in everything else, and the parts they agree on are the parts
that go wrong. Two hand-written stages had already drifted before this file
existed -- both listed ten graph backends while `runner.LANES` registers
eleven, so `mongodb_graph` would have been silently absent from a published
table and coverage rule A3 would have refused the publish.

So nothing here is typed that the harness already knows:

  * BACKENDS come from `runner.LANES[lane]`, never a literal. A backend added
    to a lane reaches the next generated stage automatically.
  * The --timeout comes from `runner.TIMEOUT_BY_SCALE`, so a stage cannot
    disagree with the cap table. Passing it explicitly is deliberate: the
    stage states what it ran with, and this generator guarantees the statement
    is true. BUGS F62 is what happens when the two drift.
  * Each stage waits on the previous stage's ALL-DONE MARKER, not on `pgrep`,
    which can match the waiting shell itself and loop forever (BUGS F59).

Usage:  python3 make_october_stages.py [--out DIR]   (default: ./october_stages)
"""
from __future__ import annotations

import argparse
import os

import runner

SHA = "417314c18da782620463bc7c09ac6bd34ac6fbda"

# PER-SIZE environment. These are corpus selectors that are NOT derived from
# --scale, so a stage that omits one measures the wrong data under the right
# label -- the exact shape of BUGS F6. Verified against the frozen rows:
# tpch1/tpch10 carry SF 1 and 10, l3d small/deep10m carry n_docs 1,000,000 and
# 9,990,000, l3s tiny/small/medium carry 100,000 / 1,000,000 / 8,841,823.
SCALE_ENV = {
    ("l1tpc", "tpch1"): ["BENCH_TPC_SF=1"],
    ("l1tpc", "tpch10"): ["BENCH_TPC_SF=10"],
    ("l3d", "small"): ["BENCH_DENSE_DATA=/data/dense"],
    ("l3d", "deep10m"): ["BENCH_DENSE_DATA=/data/deep10m"],
}

# The sparse overlay names its files per scale; the dense one uses the
# runner's default mp_{label}_b{rep}.json, which is what the dense resolver
# looks for.
OVERLAY_ENV = {"l3s": 'BENCH_DRIVER_OUT_FMT=sp_{label}_{scale}.json'}

# THE OVERLAY LANES. The dense and sparse TABLES do not read the lane's own
# search rows: they read a multipass overlay produced by a bespoke driver run
# through `runner.py --driver`, which builds once and then times five passes,
# so cold and warm exist for every engine under one protocol. The lane row is
# still needed (it carries ingest, build, memory and disk), so BOTH run, into
# different results files. A stage that ran only the lane would spend its
# whole budget producing rows no page table reads: 122 h for dense and 31 h
# for sparse, 44% of the campaign. Forms copied from the September stages
# that produced today's overlays (qDV dense, qDP sparse), not reconstructed.
OVERLAY = {
    "l3d": ("dense_multipass_driver.py", "$REPS", {
        "small":   ("dense_mp5_small_${PIN}", "mp_rows_small_${PIN}.jsonl"),
        "deep10m": ("dense_mp5_${PIN}",       "mp_rows_${PIN}.jsonl"),
    }),
    # the sparse overlay takes its repetitions INSIDE the driver, so the runner
    # runs it once per arm; qDP used --reps 1 and its arms land as
    # sp_<arm>_<scale>.json under one directory for all three sizes.
    "l3s": ("sparse_multipass_driver.py", "1", {
        "tiny":   ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
        "small":  ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
        "medium": ("sparse_mp_${PIN}", "mp_rows_sparse_${PIN}.jsonl"),
    }),
}

# id, title, lane, workloads, scales, extra guards, extra arms {backend: [env]}
STAGES = [
    ("qOA", "graph INTERACTIVE at both sizes", "l2", ["oltp"], ["sf1", "sf10"],
     ['[ -d "$HOME/bench-data/ldbc/sf1" ] && [ -d "$HOME/bench-data/ldbc/sf10" ]'
      ' || { say \'$ID ABORT: ldbc sf1/sf10 missing\'; exit 1; }'], {}, []),
    # DuckPGQ ALONE, because qOA loses it: the merge left two DuckpgqGraph
    # classes and the stale one crashed every cell, so qOA's probe rule
    # correctly declined to repeat a failed rep and that engine has no rows.
    # Fixed in the tree qOA2 pulls; the other ten arms are already measured
    # and are not re-run. A stage between qOA and qOB rather than at the end,
    # so the interactive table is complete before anything lands.
    ("qOA2", "DuckPGQ alone on the interactive table (qOA patch)", "l2", ["oltp"],
     ["sf1", "sf10"],
     ['grep -q "class DuckpgqGraph" l2_graph.py || { say "$ID ABORT: no DuckPGQ arm"; exit 1; }'],
     {}, [], ["duckpgq_graph"]),
    ("qOB", "graph ANALYTICS on the full SF1 network", "l2", ["olap"], ["sf1full"],
     ['grep -q "sf1full" ldbc_snb.py || { say \'$ID ABORT: ldbc_snb.py lacks the sf1full tier\'; exit 1; }',
      '[ -f "$HOME/bench-data/ldbc/sf1/social_network-sf1-CsvCompositeMergeForeign-LongDateFormatter/dynamic/comment_0_0.csv" ]'
      ' || { say \'$ID ABORT: no full SF1 network (the message half)\'; exit 1; }'],
     {"arcadedb_graph_embedded": ["BENCH_GAV=0"], "arcadedb_graph_server": ["BENCH_GAV=0"]}, []),
    # BENCH_TS_SETTLE_S: the served ArcadeDB time-series aggregate only sees
    # SEALED data, so for ~58 s after an ingest returns it answers with whole
    # hours missing while count(*) over the same predicate is complete
    # (BUGS F68, reproduced 9 times and in a pure-Java server repro). The
    # lane's default settle is 0, applied outside the ingest timer to EVERY
    # backend, so raising it is symmetric and recorded on the row. Without it
    # every served ArcadeDB TS latency was measured against a partly sealed
    # store, ts100 included, where the shapes happened to match.
    ("qOC", "time series at both sizes", "l4", ["ingest"], ["ts100", "ts1000"],
     ['[ -f "$HOME/bench-data/tsbs/cpu_influx.lp" ] && [ -f "$HOME/bench-data/tsbs/cpu_influx_s1000.lp" ]'
      ' || { say \'$ID ABORT: tsbs corpora missing\'; exit 1; }'], {},
     ["BENCH_TS_SETTLE_S=90"]),
    ("qOD", "cross-model at both sizes", "e2", ["hybrid", "atomicity"], ["e2", "e2_500k"],
     # READ the constant, do not IMPORT the lane: e2_hybrid imports numpy and
      # the host python3 has none, so an importing guard aborts a healthy stage
      # for a reason that has nothing to do with the stage (2026-09-20).
      ['python3 -c "import ast,sys;'
      ' t=ast.parse(open(\'e2_hybrid.py\').read());'
      ' d=[n for n in t.body if isinstance(n,ast.Assign) and getattr(n.targets[0],\'id\',None)==\'SCALE_PRODUCTS\'];'
      ' v=dict(zip([k.value for k in d[0].value.keys],[ast.literal_eval(x) for x in d[0].value.values]));'
      ' sys.exit(0 if v.get(\'e2_500k\')==500000 else 1)"'
      ' || { say "$ID ABORT: e2_500k is not 500k products"; exit 1; }'], {}, []),
    # qOD ran two of its nine arms against images nobody was rebuilding, both
    # for the same reason: the stage built a typed list of three images, so an
    # image outside that list was whatever happened to be on the host.
    # dbbench:mongo-search did not exist at all, and its cells recorded
    # `server_not_ready` -- a readiness timeout against a container that could
    # not start, which reads like a slow engine. dbbench:pg-age was built
    # 2026-09-12, before the re-pin, and its rows say
    # `PostgreSQL 17.11 + pgvector:0.8.6 + age:1.7.0` against a declared
    # PG 18 + AGE 1.8.0.
    #
    # A REPAIR, NOT A DELETION. The canonical key is (lane, scale, n_docs,
    # workload, backend, gav, rep, durability_class) and the newest ts_utc
    # wins, so re-running the same cells supersedes the bad rows where they
    # stand. Both arms are client_server, so this stage derives exactly
    # client + pg-age + mongo-search and rebuilds all three.
    ("qOD2", "cross-model: the two arms qOD ran on unbuilt images (#110)", "e2",
     ["hybrid", "atomicity"], ["e2", "e2_500k"],
     ['docker image inspect dbbench:mongo-search >/dev/null 2>&1 && '
      '{ say "$ID: dbbench:mongo-search already present, will be rebuilt"; } || true'],
     {}, [], ["pg_age_e2", "mongodb_e2"]),
    # THE STRICT HALF OF #90 FOR THE TWO STAGES THAT ALREADY RAN WITHOUT IT.
    # qOA and qOD measured their timed writes at the relaxed class only,
    # because no stage has ever passed --durability strict. Their relaxed rows
    # are correct and stay; these add the missing second pass at the same pin
    # and instrument, which is an extension of the campaign rather than a
    # re-measure (#103a). Stages from qOE on carry both passes themselves.
    #
    # Reads are re-run as a side effect -- the class is a property of the
    # CELL, not of an operation (F10b), so there is no way to ask for the
    # writes alone. That is the cost #90 accepted when it chose a second cell
    # over a second measurement inside one.
    ("qOA3", "graph transactional, the strict durability pass (#90, F10b)", "l2",
     ["oltp"], ["sf1", "sf10"], [], {}, [], None, "strict"),
    ("qOD3", "cross-model, the strict durability pass (#90, F10b)", "e2",
     ["hybrid", "atomicity"], ["e2", "e2_500k"], [], {}, [], None, "strict"),
    # BENCH_TPC_SF is NOT derived from --scale: `SF = os.environ.get("BENCH_TPC_SF", "1")`
    # is a module constant, so --scale tpch10 without it loads SF1 and records
    # it as tpch10. September's stages set it per scale; so does this one.
    ("qOE", "documents, both tables, at both sizes", "l1tpc", ["oltp", "olap"], ["tpch1", "tpch10"],
     ['ls "$HOME"/bench-data/tpch/sf10_lineitem.parquet >/dev/null 2>&1'
      ' || { say \'$ID ABORT: tpch sf10 parquet missing\'; exit 1; }'], {}, []),
    # BENCH_SPARSE_SOURCE defaults to a SYNTHETIC corpus. Omitting it is BUGS
    # F6 -- the sparse lane running synthetic data under a paper label -- and
    # the omission of this exact knob already cost this campaign 94 rows.
    ("qOF", "sparse vector at three sizes", "l3s", ["search"], ["tiny", "small", "medium"], [], {},
     ["BENCH_SPARSE_SOURCE=bigann", "BENCH_SPARSE_DATA=/data/bigann"]),
    # BENCH_LC_ITERS/WARMUP are set EXPLICITLY, and this is the only stage that
    # needs it. The lane's in-script defaults are ITERS=3 and WARMUP=1; the
    # frozen September rows are 105 at (5, 2) against 12 at (3, 1), so the
    # campaign's protocol is 5 and 2 and the lane's default is not it. Left
    # unset, October's lifecycle rows would carry a different protocol from
    # September's on the same table. Checked the same way for every other
    # lane -- graph 100 iterations, documents 100, time series 100,
    # cross-model 300 operations -- and in each of those the in-script default
    # is exactly what the frozen rows recorded, so no other stage sets one.
    ("qOG", "lifecycle at four sizes", "lifecycle",
     ["empty", "doc", "doc_idx10", "graph", "graph_gav", "vector", "sparse", "ts"],
     ["lc10k", "lc100k", "lc1m", "lc10m"], [], {},
     ["BENCH_LC_ITERS=5", "BENCH_LC_WARMUP=2"]),
    # BENCH_DENSE_DATA is per SIZE: /data/dense is the 1M fixture and
    # /data/deep10m the 9.99M one. The lane's default is /data/dense, so
    # deep10m without this runs the 1M corpus and labels it deep10m. I made
    # exactly this mistake on a probe earlier in the campaign.
    ("qOH", "dense vector at both sizes", "l3d", ["search"], ["small", "deep10m"], [], {}, []),
    # qOB RE-RUN, at the end. Its first attempt was censored on our own engine
    # and it was stopped (BUGS F74); DECISIONS #109 excludes lsqb_q6 and
    # lsqb_q9 at this tier, which cell_cost_check puts at 9-11% of the cap for
    # both ArcadeDB arms. It goes LAST rather than back into its old slot
    # because the five stages behind it are already running and inserting into
    # a live chain costs a kill-and-relaunch of each.
    ("qOB2", "graph ANALYTICS on the full SF1 network (qOB re-run, #109)", "l2",
     ["olap"], ["sf1full"],
     ['grep -q "sf1full" ldbc_snb.py || { say "$ID ABORT: no sf1full tier"; exit 1; }',
      'python3 -c "import graph_common as G, sys; sys.exit(0 if G.tier_excluded(\'sf1full\',\'lsqb_q6\') else 1)"'
      ' || { say "$ID ABORT: #109 exclusions are not in this tree"; exit 1; }'],
     {"arcadedb_graph_embedded": ["BENCH_GAV=0"], "arcadedb_graph_server": ["BENCH_GAV=0"]}, []),
]

HEAD = '''#!/bin/bash
# {id}. October stage {n} of {total}: {title}.
#
# GENERATED by make_october_stages.py -- edit that file, not this one, and
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
RF="runs_page_${{PIN}}.jsonl"   # land_stage.py pulls this exact name; the
                              # PIN separates October from September, so
                              # a second convention would only mean
                              # land_stage silently pulls nothing.
REPS=${{REPS:-5}}
say() {{ echo "[$(date -Is)] $*" >> "$S"; }}
{wait}
cd "$REPO" && git pull -q --ff-only || {{ say "$ID ABORT: pull"; exit 1; }}
cd "$R" || exit 1
export PATH=$HOME/.local/bin:$PATH

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
{guards}
# --- images and the pinned pair -------------------------------------------
# THE WHEEL IS BAKED AT IMAGE BUILD TIME, so it has to be exported BEFORE
# build_images.sh, and the arcadedb image has to be rebuilt. Without both,
# build_images.sh falls back to `arcadedb-embedded==26.8.1` from PyPI and
# every EMBEDDED arm runs that while every SERVED arm runs the pinned image:
# two ArcadeDB versions on one table. That is exactly what last night's
# calibration did -- its embedded arms ran 26.8.1 against served
# 26.9.1-SNAPSHOT -- and verify_pair_c25.sh does not catch it, because it
# compares the newest wheel FILE in dist/ against the server image and never
# looks inside dbbench:arcadedb.
W=$(ls -t "$REPO"/bindings/python/dist/*.whl | head -1)
[ -n "$W" ] || {{ say "$ID ABORT: no wheel in dist/"; exit 1; }}
export ARCADEDB_WHEEL="$W" ARCADEDB_SERVER_IMAGE=arcadedb-c25:$PIN
WV=$(basename "$W" | cut -d- -f2)
BENCH_ALLOW_DEV=1 ./build_images.sh {images} >> "$S" 2>&1 || {{ say "$ID ABORT: image build"; exit 1; }}
# ARTIFACT EXISTS IS NOT ARTIFACT BUILT: a target that silently did
# nothing leaves no image, and the first cell to want it reports
# server_not_ready. Check here, where the message can name the cause.
for _img in {images}; do
  docker image inspect "dbbench:$_img" >/dev/null 2>&1 || {{ say "$ID ABORT: dbbench:$_img missing after build"; exit 1; }}
done
say "$ID: images present: {images}"
# VERIFY THE ARM, NOT THE FILE: read the version out of the built image.
# The pair check below is the REPO copy, not ~/verify_pair_c25.sh: that
# one is a stale copy from 2026-08-30 and would miss its own fourth
# check. A script pulled with the tree cannot drift from it.
IV=$(docker run --rm --entrypoint python3 dbbench:arcadedb -c \
     'import importlib.metadata as m; print(m.version("arcadedb-embedded"))' 2>/dev/null | tr -dc "0-9a-zA-Z.-")
[ "$IV" = "$WV" ] || {{ say "$ID ABORT: dbbench:arcadedb carries wheel $IV, dist has $WV"; exit 1; }}
say "$ID: dbbench:arcadedb carries wheel $IV, matching dist"
./verify_pair_c25.sh "$SHA" >> "$S" 2>&1 || {{ say "$ID ABORT: pair unverified at the October pin"; exit 1; }}
export ARCADEDB_ENGINE_COMMIT=$PIN BENCH_DATA=$HOME/bench-data BENCH_HOST=mini
export BENCH_CPUSET=0-11 BENCH_GRAPH_SOURCE=ldbc
{stage_env}

BACKENDS="{backends}"
# AN ABORT MUST NOT STRAND THE CHAIN. Every guard above exits 1 without a
# marker, so the stages waiting on this one wait forever -- which is what
# happened on 2026-09-20 when a guard of mine aborted a healthy stage and left
# the host idle. From the START line on, the marker is written by a trap
# whatever happens: the ABORT is already in STATUS.txt and loud, and the rest
# of the campaign is worth more than making a human notice sooner.
trap 'echo "$ID ALL-DONE" >> "$S"' EXIT
say "$ID START: {title}, {nbe} engines, REPS=$REPS, pin $PIN, instrument 2026-10"

run_overlay() {{  # <label> <scale> <cap> <be> <wl> <driver> <outdir> <rf> <reps> <env>
  local label=$1 scale=$2 cap=$3 be=$4 wl=$5 drv=$6 outdir=$7 orf=$8 oreps=$9 oenv=${{10}}
  env $oenv python3 runner.py --lanes {lane} --scale "$scale" --backends "$be" \
    --workloads "$wl" --tier paper --workers 1 --timeout "$cap" \
    --reps "$oreps" --driver "$drv" --driver-out-dir "$outdir" \
    --results-file "$orf" >> "$S" 2>&1 \
    || say "$ID: $label OVERLAY failed (the table reads this, not the lane row)"
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
  env $envset python3 runner.py --lanes {lane} --scale "$scale" --backends "$be" \\
    --workloads "$wl" --tier paper --workers 1 --timeout "$cap" $dur \\
    --only-reps 1 --reps "$REPS" --results-file "$RF" >> "$S" 2>&1
  if [ $? -ne 0 ]; then
    say "$ID: $label rep 1 failed, not repeating it"
    return 0
  fi
  [ "$REPS" -lt 2 ] || env $envset python3 runner.py --lanes {lane} --scale "$scale" \\
    --backends "$be" --workloads "$wl" --tier paper --workers 1 --timeout "$cap" $dur \\
    --only-reps "$(seq -s, 2 "$REPS")" --reps "$REPS" --results-file "$RF" >> "$S" 2>&1
}}
'''


# THE TIMED WRITES RUN TWICE, ONCE AT EACH DURABILITY CLASS (DECISIONS #90,
# FAIRNESS F10b). Every stage ran the relaxed pass only, so no row in any
# campaign -- September's chain, October's, or the archive -- carries
# `durability_class: strict`, the durability table publishes with every cell
# empty, and fairness_check F10 fails for every timed write cell it sees. The
# gate blocks a landing, so October could have finished and still been
# unpublishable. Reads are untouched and bulk ingest stays at one setting
# (#90a): only these four (lane, workload) pairs get the second pass.
STRICT_WORKLOADS = {("l1tpc", "oltp"), ("l2", "oltp"),
                    ("e2", "hybrid"), ("e2", "atomicity")}


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
                out.add(img.split(":", 1)[1])
    return sorted(out)


def emit(idx: int, spec) -> str:
    sid, title, lane, workloads, scales, guards, extra, stage_env = spec[:8]
    only = spec[8] if len(spec) > 8 else None
    # spec[9]: None runs both classes where F10b applies, "strict" runs only
    # the strict pass (a repair for a stage that already ran relaxed-only),
    # "relaxed" only the relaxed one.
    dur_mode = spec[9] if len(spec) > 9 else None
    backends = list(only) if only else list(runner.LANES[lane][1])
    caps = [(s, runner.TIMEOUT_BY_SCALE[s]) for s in scales]
    wait = ("" if idx == 0 else
            f'\nwhile ! grep -q "{STAGES[idx - 1][0]} ALL-DONE" "$S" 2>/dev/null; do sleep 300; done\n'
            f'say "$ID: {STAGES[idx - 1][0]} finished, taking the machine"\n')
    body = HEAD.format(id=sid, n=idx + 1, total=len(STAGES), title=title, lane=lane,
                       nbe=len(backends), sha=SHA, wait=wait,
                       caps=caps, scales=list(scales), guards="\n".join(guards) + ("\n" if guards else ""),
                       stage_env=("export " + " ".join(stage_env) if stage_env else "# (this lane's in-script defaults are what the frozen rows ran)"),
                       backends=" ".join(backends),
                       images=" ".join(_images_for(backends)))
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
                outdir, orf = dirs[scale]
                oenv = " ".join(x for x in [senv, OVERLAY_ENV.get(lane, "")] if x)
                body += (f'  run_overlay "{lane}/{scale}/$BE/{wl} multipass" {scale} {cap} '
                         f'"$BE" {wl} {drv} "{outdir}" "{orf}" {oreps} "{oenv}"\n')
        body += 'done\n'
        if lane in OVERLAY:
            _, _, dirs = OVERLAY[lane]
            outdir, _ = dirs[scale]
            body += (f'N=$(ls results/{outdir}/ 2>/dev/null | wc -l)\n'
                     f'say "$ID: {scale} overlay dir holds $N file(s)"\n'
                     f'[ "$N" -gt 0 ] || say "$ID WARNING: {scale} overlay produced NO files; '
                     f'the table reads this directory and would publish nothing"\n')
        body += f'say "$ID: {scale} done"\n'
    body += 'say "$ID finished"   # the EXIT trap writes the ALL-DONE marker\n'
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="october_stages")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for i, spec in enumerate(STAGES):
        p = os.path.join(a.out, f"{spec[0]}.sh")
        with open(p, "w") as fh:
            fh.write(emit(i, spec))
        os.chmod(p, 0o755)
        print(f"  {spec[0]}.sh  lane={spec[2]:9} "
              f"backends={len(spec[8]) if len(spec) > 8 and spec[8] else len(runner.LANES[spec[2]][1]):2}"
              f"  scales={','.join(spec[4])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
