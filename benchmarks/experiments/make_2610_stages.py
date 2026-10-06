#!/usr/bin/env python3
"""Emit the 26.10.1 measurement's queue scripts (DECISIONS #133), one per stage.

A PROFILE OF make_october_stages, NOT A COPY. October's template carries every
guard the campaign learned (the cap table, shadowed definitions, budgets against
the cap, the whole-cell cost, images present AND current, the pinned pair, the
ALL-DONE trap, F162's rep-1-first overlay). Copying it would start two templates
drifting on the first fix; importing it means a guard added there reaches these
stages too. What differs is replaced by exact-string substitution, each one
asserted, so a change to October's template that moves an anchor fails here
loudly instead of emitting a script with the old text:

  * THE PIN IS A RELEASE, NAMED, NOT FOUND (DECISIONS #42: the paper cites stable
    releases). October took the newest wheel in dist/ (`ls -t`) and the server
    image `arcadedb-c25:<sha>`. These stages are generated FOR one wheel, by file
    name and sha256, one server image, and one engine commit, read from the
    environment at generation (ARCADEDB_WHEEL, ARCADEDB_SERVER_IMAGE,
    ARCADEDB_ENGINE_COMMIT); the generator refuses to emit without all three, and
    refuses a pre-release wheel unless --allow-prerelease. Each stage refuses to
    start if dist/ holds anything else.
  * THE COMPARATOR PINS ARE FROZEN AT GENERATION. Every stage `git pull`s main, so
    a comparator digest edited in runner.py mid-chain would split one table across
    two versions with every gate green until the landing (memories: land changes
    before the campaign; one line of development). Each stage carries the digests
    its arms had when the chain was generated and refuses to start if runner.py
    now says otherwise.
  * cell_cost_check reads October's rows as well as this pin's, so a tier this pin
    has not measured yet is still scored from the nearest measured engine
    (rc=2 stays non-blocking, as October's rule says).

The stage list is #133's order: the paper's tables first (graph interactive, graph
analytics, cross-model, documents, dense), then sparse, time series, the e4
decomposition (export_web refuses a page without e4decomp_<pin>; the 2026-10-02
rehearsal reported e4 LOST without it), lifecycle for ArcadeDB and SurrealDB, the
Python-cost table (a host-side stage: run_bench.sh's six steps, five runs), and
LAST the lifecycle expansion (CAMPAIGN row 40). Backends come from runner.LANES;
check_coverage() proves every registered arm of every page lane is in exactly one
stage per workload, from runner.LANES and export_web._TABLE_LANE, not from a list.

Usage:
  python3 make_2610_stages.py --check                 # coverage only, no pins needed
  python3 make_2610_stages.py --project CELLS.tsv     # per-stage hours from measured cells
  ARCADEDB_WHEEL=... ARCADEDB_SERVER_IMAGE=... ARCADEDB_ENGINE_COMMIT=<40 hex> \\
      python3 make_2610_stages.py --out DIR [--after qOA5]
"""
from __future__ import annotations

import argparse
import ast
import collections
import csv
import hashlib
import json
import os
import re
import statistics
import sys

import make_october_stages as O
import runner
import bench_common

HERE = os.path.dirname(os.path.abspath(__file__))

# October's rows, the prior cell_cost_check scores a tier from until this pin has
# measured it. The last October stage, the one the first 26.10.1 stage waits on.
PRIOR_PIN = "417314c18"
OCTOBER_LAST_STAGE = "qOA5"

# ArcadeDB's and SurrealDB's lifecycle arms, the table as it stands; every other
# lifecycle arm is the expansion (#131 item 5, CAMPAIGN row 40), queued last (#133).
LIFECYCLE_PAPER = ("arcadedb_embedded", "arcadedb_server", "surrealdb_lifecycle")

# The six run_bench.sh steps the page's Python-cost table reads (export_web
# _overhead_medians: RESULT rows of the vector and query workloads), five runs, as
# the September re-measure at 8d6af9475 has them.
PYCOST_STEPS = ("j-vector-build-100k j-vector-bench-100k p-vector-bench-100k "
                "j-seed-docs j-bench-query p-bench-query")
PYCOST_RUNS = 5


def _october(sid):
    """October's spec for a stage, so a guard or an environment is shared, not retyped."""
    for spec in O.STAGES:
        if spec[0] == sid:
            return spec
    raise SystemExit(f"make_october_stages has no stage {sid}; the 26.10.1 table borrows from it")


_LC = _october("qOG")

# The restart lane's arms by model, from the lane's own map, so a model gaining
# an engine there gains it here; and its protocol, stated rather than defaulted.
import l6_restart as _RS  # noqa: E402
RESTART_BY_MODEL = {m: tuple(b for b in runner.LANES["restart"][1] if _RS.MODEL[b] == m)
                    for m in ("docs", "graph", "dense", "ts")}
RESTART_ENV = ("BENCH_RS_ITERS=5", "BENCH_RS_WARMUP=1", "BENCH_RS_WRITE_N=1000")
# THE SENSITIVITY ARM (CAMPAIGN 7 row 69): the arms runner.ARM_WORKLOADS restricts to one
# workload. The main documents stage leaves them out, and a stage of their own runs them
# where the row says: documents OLTP, served, the 2M-part cell (tpch10), three repetitions,
# the relaxed class only (the page prints the arm beside the main arm on the relaxed table).
SENSITIVITY_ARMS = tuple(sorted(runner.ARM_WORKLOADS))
DOCS_MAIN_ARMS = [b for b in runner.LANES["l1tpc"][1] if b not in SENSITIVITY_ARMS]
# id, title, lane, workloads, scales, guards, extra, stage_env, only, dur_mode, after
STAGES = [
    ("qRA", "graph INTERACTIVE at both sizes, both durability classes", "l2", ["oltp"], ["sf1", "sf10"],
     _october("qOA")[5], {}, []),
    ("qRB", "graph ANALYTICS on the full SF1 network", "l2", ["olap"], ["sf1full"],
     _october("qOB2")[5], _october("qOB2")[6], []),
    ("qRC", "cross-model at both sizes, both durability classes", "e2", ["hybrid", "atomicity"],
     ["e2", "e2_500k"], _october("qOD")[5], {}, []),
    ("qRD", "documents, both tables, at both sizes", "l1tpc", ["oltp", "olap"], ["tpch1", "tpch10"],
     _october("qOE")[5], {}, [], DOCS_MAIN_ARMS),
    ("qRE", "dense vector at both sizes, with the multipass overlay", "l3d", ["search"],
     ["small", "deep10m"], [], {}, []),
    ("qRF", "sparse vector at three sizes, with the second pass", "l3s", ["search"],
     ["tiny", "small", "medium"], [], {}, _october("qOF")[7]),
    ("qRG", "time series at both sizes", "l4", ["ingest"], ["ts100", "ts1000"],
     _october("qOJ")[5], {}, _october("qOJ")[7]),
    ("qRH", "deployment decomposition, the E4 table's producer", "e4", ["decomp"], ["e2"],
     _october("qOK")[5], {}, []),
    ("qRI", "lifecycle at four sizes, ArcadeDB and SurrealDB", "lifecycle", _LC[3], _LC[4], [], {},
     _LC[7], list(LIFECYCLE_PAPER)),
    ("qRJ", "the Python-cost table (host-side, run_bench.sh)", "pycost", [], [], [], {}, []),
    # THE SERVER RESTART (DECISIONS #139 item 2, l6_restart.py), one stage per
    # model: a stage's scales apply to every arm in it, and each model has its
    # own tiers (the scale names the model, and the lane refuses another's).
    ("qRK", "server restart on documents, both sizes", "restart", ["restart"], ["tpch1", "tpch10"],
     _october("qOE")[5], {}, list(RESTART_ENV), list(RESTART_BY_MODEL["docs"])),
    ("qRL", "server restart on the graph, both sizes", "restart", ["restart"], ["sf1", "sf10"],
     _october("qOA")[5], {}, list(RESTART_ENV), list(RESTART_BY_MODEL["graph"])),
    # 1M and 10M (DECISIONS #139 item 2, 2026-10-02): a vector index's restart cost is
    # the index coming back, and it shows at 10M; about 25-40 h more, mostly loads.
    ("qRM", "server restart on dense vectors, both sizes", "restart", ["restart"], ["small", "deep10m"],
     [], {}, list(RESTART_ENV), list(RESTART_BY_MODEL["dense"])),
    ("qRN", "server restart on time series, both sizes", "restart", ["restart"], ["ts100", "ts1000"],
     [_october("qOJ")[5][0]], {}, list(RESTART_ENV), list(RESTART_BY_MODEL["ts"])),
    # The lifecycle expansion stage (the single-model embedded engines) was
    # dropped (DECISIONS #139); the lane's roster is ArcadeDB and SurrealDB.
    # LAST, because it is a sensitivity arm that no table waits for: ONE served
    # ArcadeDB arm at the image's own JVM settings, on the documents transaction
    # workload at the 2M-part tier, three repetitions (REPS=3, set after the
    # template's default of five), the relaxed class only (CAMPAIGN 7 row 69).
    ("qRO", "documents OLTP, served ArcadeDB at the image's own JVM defaults, the 2M-part cell", "l1tpc",
     ["oltp"], ["tpch10"], _october("qOE")[5], {}, ["REPS=3"], list(SENSITIVITY_ARMS), "relaxed"),
]


# --------------------------------------------------------------------- coverage
def _page_lanes():
    """(lane -> set of workloads, or None for any) the published tables read, from
    export_web._TABLE_LANE by ast (export_web refuses to import without results)."""
    tree = ast.parse(open(os.path.join(HERE, "export_web.py")).read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_TABLE_LANE":
            tl = ast.literal_eval(n.value)
            out = collections.defaultdict(set)
            for lane, wl in tl.values():
                out[lane].add(wl)
            # e4 is a page table read from its artifact directory, not through _TABLE_LANE
            out["e4"].add("decomp")
            return {k: (None if None in v else v) for k, v in out.items()}
    raise SystemExit("export_web._TABLE_LANE not found")


def stage_backends(spec):
    only = spec[8] if len(spec) > 8 and spec[8] else None
    if spec[2] == "pycost":
        return []
    return list(only) if only else list(runner.LANES[spec[2]][1])


def check_coverage(stages=STAGES):
    """Every registered arm of every page lane in exactly one stage per workload.

    Returns (problems, excluded lanes with reasons, per-lane counts)."""
    page = _page_lanes()
    seen = collections.Counter()
    stage_wls = collections.defaultdict(set)
    problems = []
    for spec in stages:
        lane = spec[2]
        if lane == "pycost":
            continue
        for wl in spec[3]:
            stage_wls[lane].add(wl)
            for be in stage_backends(spec):
                seen[(lane, wl, be)] += 1
                if not runner.arm_runs(lane, wl, be):
                    problems.append(f"{lane}/{wl}/{be}: staged, but runner.ARM_WORKLOADS keeps it off this workload")
    excluded, counts = [], {}
    for lane, spec_l in runner.LANES.items():
        backends = spec_l[1]
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


# ------------------------------------------------------------------- the template
def _sub(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"make_october_stages.HEAD moved an anchor this profile replaces "
                         f"({text.count(old)} matches): {old[:70]!r}")
    return text.replace(old, new)


def _head():
    h = O.HEAD
    h = _sub(h, "# {id}. October stage {n} of {total}: {title}.",
             "# {id}. 26.10.1 stage {n} of {total}: {title}.")
    h = _sub(h, "# GENERATED by make_october_stages.py -- edit that file, not this one, and",
             "# GENERATED by make_2610_stages.py (a profile of make_october_stages.py) -- edit\n"
             "# those files, not this one, and")
    h = _sub(h, '''RF="runs_page_${{PIN}}.jsonl"''',
             '''PRIOR_RF="runs_page_{prior}.jsonl"   # October's rows: cell_cost_check's prior
RF="runs_page_${{PIN}}.jsonl"''')
    # October's rule stands for this pin's own rows: a scored projection over the cap
    # aborts. A tier this pin has not measured yet (rc=2) is scored from October's
    # rows instead, and THAT verdict only warns: it is another engine version's
    # worst case (every query spending its whole budget), and at tpch10 it puts
    # MongoDB at 103% and SurrealDB served at 106% of a cap October's cells met.
    h = _sub(h, '''  elif [ $_cc -eq 2 ]; then
    say "$ID: cell cost not scored at $_tier, no first-touch rows for this roster yet"
  fi''',
             '''  elif [ $_cc -eq 2 ]; then
    if [ -f "results/$PRIOR_RF" ]; then
      python3 cell_cost_check.py --lane {lane} --tier "$_tier" --rows "results/$PRIOR_RF" >> "$S" 2>&1
      case $? in
        1) say "$ID WARNING: $_tier projected over the cap from October's rows ($PRIOR_RF); this pin has none yet, so it runs and its censored cells are what the projection said" ;;
        0) say "$ID: $_tier scored from October's rows ($PRIOR_RF): fits" ;;
        *) say "$ID: cell cost not scored at $_tier, no first-touch rows for this roster at either pin" ;;
      esac
    else
      say "$ID: cell cost not scored at $_tier, no first-touch rows for this roster yet"
    fi
  fi''')
    h = _sub(h, '''W=$(ls -t "$REPO"/bindings/python/dist/*.whl | head -1)
[ -n "$W" ] || {{ say "$ID ABORT: no wheel in dist/"; exit 1; }}''',
             '''# THE RELEASE PAIR THIS CHAIN WAS GENERATED FOR, named rather than found
# (DECISIONS #42). A different file in dist/ is a different engine under test.
W="$REPO/bindings/python/dist/{wheel_name}"
[ -f "$W" ] || {{ say "$ID ABORT: the pinned wheel {wheel_name} is not in dist/"; exit 1; }}''')
    h = _sub(h, "export ARCADEDB_WHEEL=\"$W\" ARCADEDB_SERVER_IMAGE=arcadedb-c25:$PIN",
             '''[ "$(sha256sum "$W" | cut -d' ' -f1)" = "{wheel_sha256}" ] || {{ say "$ID ABORT: dist/{wheel_name} is not the wheel this chain was generated for (sha256)"; exit 1; }}
export ARCADEDB_WHEEL="$W" ARCADEDB_SERVER_IMAGE="{server_image}"
docker image inspect "$ARCADEDB_SERVER_IMAGE" >/dev/null 2>&1 || {{ say "$ID ABORT: no server image $ARCADEDB_SERVER_IMAGE"; exit 1; }}''')
    h = _sub(h, "BENCH_ALLOW_DEV=1 ./build_images.sh {images}", "BENCH_ALLOW_DEV={allow_dev} ./build_images.sh {images}")
    h = _sub(h, '''./verify_pair_c25.sh "$SHA" >> "$S" 2>&1 || {{ say "$ID ABORT: pair unverified at the October pin"; exit 1; }}''',
             '''PAIR_IMAGE="$ARCADEDB_SERVER_IMAGE" ./verify_pair_c25.sh "$SHA" >> "$S" 2>&1 || {{ say "$ID ABORT: pair unverified at the pin"; exit 1; }}''')
    h = _sub(h, "pin $PIN, instrument 2026-10\"", "pin $PIN, instrument {instrument}\"")
    return h


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


HOST = '''#!/bin/bash
# {id}. 26.10.1 stage {n} of {total}: {title}.
#
# GENERATED by make_2610_stages.py. A HOST-SIDE stage, not runner cells (memory:
# host-side probes are not cells): run_bench.sh pins itself to BENCH_CPUSET (0-11)
# and runs the repo venv's arcadedb-embedded, so that venv must hold the pinned
# release. Output goes OUTSIDE the tree ($HOME/pycost), because a file the laptop
# later commits must not sit untracked on mini (BUGS F19); the landing copies it to
# benchmarks/python-bindings/jpype_overhead/results/mini_results_<pin>.csv, which
# export_web prefers over the tracked file.
set -u
ID={id}
S=$HOME/STATUS.txt
REPO=$HOME/repos/humemai/arcadedb-embedded-python
SHA={sha}
PIN=${{SHA:0:9}}
say() {{ echo "[$(date -Is)] $*" >> "$S"; }}
{wait}
cd "$REPO" && git pull -q --ff-only || {{ say "$ID ABORT: pull"; exit 1; }}
export PATH=$HOME/.local/bin:$PATH
D=$REPO/benchmarks/python-bindings/jpype_overhead
[ -d "$D/data_100k" ] || {{ say "$ID ABORT: $D/data_100k missing (gen_dataset.py data_100k 100000 384)"; exit 1; }}
grep -q 'ONLY_STEPS' "$D/run_bench.sh" || {{ say "$ID ABORT: run_bench.sh has no ONLY_STEPS (pre-2026-10-02 tree)"; exit 1; }}
WANT=$(basename "{wheel_name}" | cut -d- -f2)
HAVE=$("$REPO"/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("arcadedb-embedded"))' 2>/dev/null)
[ "$HAVE" = "$WANT" ] || {{ say "$ID ABORT: the repo venv runs arcadedb-embedded '$HAVE', the pin is $WANT; install it first: uv pip install --python $REPO/.venv $REPO/bindings/python/dist/{wheel_name}"; exit 1; }}
OUT=$HOME/pycost/mini_results_${{PIN}}.csv
mkdir -p "$HOME/pycost"
trap 'echo "$ID ALL-DONE" >> "$S"' EXIT
say "$ID START: {title}, {runs} runs of: {steps}, pin $PIN"
: > "$OUT"
for i in $(seq 1 {runs}); do
  R=$HOME/pycost/run$i
  rm -rf "$R" && mkdir -p "$R/results" "$R/dbs"
  ONLY_STEPS="{steps}" UV_RUN_ARGS=--no-sync PYCOST_RESULTS="$R/results" PYCOST_DBS="$R/dbs" \\
    "$D/run_bench.sh" > "$R/run_bench.out" 2>&1 || say "$ID: run $i exited non-zero (see $R/run_bench.out)"
  sed "s/^/MINI,RUN$i,/" "$R/results/all_results.csv" >> "$OUT"
  rm -rf "$R/dbs"
done
N=$(grep -c ',RESULT,' "$OUT")
say "$ID: $OUT holds $N RESULT lines over {runs} runs"
[ "$N" -gt 0 ] || say "$ID WARNING: no RESULT lines; the Python-cost table would publish nothing"
say "$ID finished"   # the EXIT trap writes the ALL-DONE marker
'''


def _wait(after):
    return ("" if after is None else
            f'\nwhile ! grep -q "{after} ALL-DONE" "$S" 2>/dev/null; do sleep 300; done\n'
            f'say "$ID: {after} finished, taking the machine"\n')


def emit_all(out, pins, first_after, allow_dev):
    """Write every stage. October's emit() is reused for the runner stages, with its
    template and SHA swapped for the duration of the call."""
    head = _head()
    sha, wheel, server = pins["ARCADEDB_ENGINE_COMMIT"], pins["ARCADEDB_WHEEL"], pins["ARCADEDB_SERVER_IMAGE"]
    wheel_name = os.path.basename(wheel)
    wheel_sha = hashlib.sha256(open(wheel, "rb").read()).hexdigest()
    saved = (O.HEAD, O.SHA, O.STAGES)
    try:
        O.SHA = sha
        O.STAGES = STAGES
        for i, spec in enumerate(STAGES):
            after = first_after if i == 0 else STAGES[i - 1][0]
            if spec[2] == "pycost":
                body = HOST.format(id=spec[0], n=i + 1, total=len(STAGES), title=spec[1], sha=sha,
                                   wait=_wait(after), wheel_name=wheel_name, runs=PYCOST_RUNS,
                                   steps=PYCOST_STEPS)
            else:
                guards = list(spec[5]) + _pin_guard(stage_backends(spec))
                full = (spec[0], spec[1], spec[2], spec[3], spec[4], guards, spec[6], spec[7],
                        spec[8] if len(spec) > 8 else None, spec[9] if len(spec) > 9 else None, after)
                O.HEAD = head.replace("{prior}", PRIOR_PIN).replace("{wheel_name}", wheel_name) \
                    .replace("{wheel_sha256}", wheel_sha).replace("{server_image}", server) \
                    .replace("{allow_dev}", "1" if allow_dev else "0") \
                    .replace("{instrument}", bench_common.INSTRUMENT)
                body = O.emit(i, full)
            p = os.path.join(out, f"{spec[0]}.sh")
            with open(p, "w") as fh:
                fh.write(body)
            os.chmod(p, 0o755)
            print(f"  {spec[0]}.sh  lane={spec[2]:9} backends={len(stage_backends(spec)):2}  "
                  f"scales={','.join(spec[4]) or '-'}  after={after}")
    finally:
        O.HEAD, O.SHA, O.STAGES = saved


# ------------------------------------------------------------------- projection
def project(cells_tsv):
    """Per-stage hours from October's measured cells (.notes projection-2026-10-02/
    cells_by_arm.tsv: lane, workload, scale, backend, class, rows, hours, ...). A cell
    with no October measurement (a new arm) is estimated as the median of the measured
    arms of the same lane, workload, scale, and class, and counted apart."""
    meas = {}
    with open(cells_tsv) as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) < 7 or not row[6].endswith("h"):
                continue
            meas[(row[0], row[1], row[2], row[3], row[4])] = float(row[6][:-1])
    by_group = collections.defaultdict(list)
    for (lane, wl, sc, _be, cls), h in meas.items():
        by_group[(lane, wl, sc, cls)].append(h)
    rows, total_m, total_e = [], 0.0, 0.0
    for spec in STAGES:
        lane = spec[2]
        if lane == "pycost":
            rows.append((spec[0], spec[1], 0.0, 0.0, [], "1-3 h (September's re-measure: six steps, five runs)"))
            continue
        m = e = 0.0
        new = []
        for sc in spec[4]:
            for wl in spec[3]:
                classes = ["relaxed"] + (["strict"] if (lane, wl) in O.STRICT_WORKLOADS else [])
                for cls in classes:
                    for be in stage_backends(spec):
                        k = (lane, wl, sc, be, cls)
                        if k in meas:
                            m += meas[k]
                        else:
                            grp = by_group.get((lane, wl, sc, cls))
                            if grp:
                                e += statistics.median(grp)
                                # A median of one or two arms is not an estimate: October's
                                # qOB2 (sf1full) and the rest of qOH (dense) ran after the
                                # projection's cells were taken, so those groups are thin.
                                thin = f" (thin: {len(grp)} measured)" if len(grp) < 3 else ""
                                new.append(f"{be}@{sc}{'/' + cls if cls != 'relaxed' else ''}{thin}")
                            else:
                                new.append(f"{be}@{sc} (no measured peer)")
        rows.append((spec[0], spec[1], m, e, new, ""))
        total_m += m
        total_e += e
    return rows, total_m, total_e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="directory for the generated scripts (not the repo)")
    ap.add_argument("--after", default=OCTOBER_LAST_STAGE, help="the stage the first one waits on")
    ap.add_argument("--allow-prerelease", action="store_true",
                    help="emit for a dev/rc wheel (a page measurement; the paper cites releases, #42)")
    ap.add_argument("--check", action="store_true", help="coverage only")
    ap.add_argument("--project", metavar="CELLS_TSV", help="per-stage hours from October's measured cells")
    a = ap.parse_args()

    problems, excluded, counts = check_coverage()
    print("coverage: every registered arm of every page lane in exactly one stage per workload")
    for lane, n in sorted(counts.items()):
        print(f"  {lane:10} {n:2} arms")
    for lane, why in excluded:
        print(f"  excluded lane {lane}: {why}")
    for p in problems:
        print(f"  PROBLEM {p}")
    if problems:
        return 1
    if a.project:
        rows, tm, te = project(a.project)
        print("\nprojection from October's measured cells (h):")
        for sid, title, m, e, new, note in rows:
            print(f"  {sid}  measured {m:6.1f}  + new-arm estimate {e:6.1f}  {title}"
                  + (f"  [{note}]" if note else ""))
            if new:
                print(f"         estimated: {', '.join(new[:14])}{' ...' if len(new) > 14 else ''}")
        print(f"  total measured {tm:.0f} h + estimated {te:.0f} h = {tm + te:.0f} h "
              f"(a stage whose estimates say 'thin' needs projection-2026-10-02/SUMMARY.md's range instead)")
    if a.check or a.project:
        return 0

    if not a.out:
        raise SystemExit("--out DIR is required to emit (a scratch directory, not the repo)")
    pins = {k: os.environ.get(k, "").strip() for k in ("ARCADEDB_WHEEL", "ARCADEDB_SERVER_IMAGE",
                                                        "ARCADEDB_ENGINE_COMMIT")}
    missing = [k for k, v in pins.items() if not v]
    if missing:
        raise SystemExit(f"REFUSING to emit: {', '.join(missing)} unset. The 26.10.1 stages are generated "
                         f"for one release pair (F5): the wheel file, the server image, and the engine commit.")
    if not re.fullmatch(r"[0-9a-f]{40}", pins["ARCADEDB_ENGINE_COMMIT"]):
        raise SystemExit("ARCADEDB_ENGINE_COMMIT must be the full 40-character commit")
    if not os.path.isfile(pins["ARCADEDB_WHEEL"]):
        raise SystemExit(f"ARCADEDB_WHEEL is not a file: {pins['ARCADEDB_WHEEL']}")
    ver = os.path.basename(pins["ARCADEDB_WHEEL"]).split("-")[1]
    pre = bool(re.search(r"(dev|rc|a|b)\d*$|SNAPSHOT", ver))
    if pre and not a.allow_prerelease:
        raise SystemExit(f"REFUSING to emit: wheel {ver} is a pre-release; the paper cites stable releases "
                         f"(DECISIONS #42). --allow-prerelease emits for a page-only measurement.")
    os.makedirs(a.out, exist_ok=True)
    emit_all(a.out, pins, a.after, allow_dev=pre)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
