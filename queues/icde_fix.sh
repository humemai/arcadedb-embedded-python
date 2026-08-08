#!/bin/bash
# Re-run the lanes icde_long.sh got wrong, with the environment it was missing.
#
# WHAT WENT WRONG. icde_long.sh exported exactly one variable, BENCH_DATA. The
# campaign that produced good data, icde_q10.sh, exported six, each asserted,
# and its own header warned that l2_graph.py silently defaults to "synthetic".
# The consequences split two ways:
#   l2 sf1/sf10  CRASHED. Without BENCH_GRAPH_SOURCE=ldbc, SCALE_PERSONS is the
#                synthetic dict and argparse rejects --scale sf1. Loud, no data.
#   l3s          SUCCEEDED ON THE WRONG CORPUS. Without BENCH_SPARSE_SOURCE the
#                lane generated synthetic documents with no ground truth, so 94
#                rows landed carrying gt_missing and recall_at_10=None, and at
#                tiny/small they were indistinguishable from the real Big-ANN
#                rows by doc count alone.
# The second is the dangerous one, and it is why this script does not trust an
# exit code as evidence that a cell measured what it was told to measure.
#
# THREE THINGS THIS DOES THAT icde_long.sh DID NOT.
#  1. Exports the full environment, and asserts each dataset exists ON THE HOST.
#  2. Asserts the environment and the data are visible INSIDE THE CONTAINER,
#     which is where the lane actually reads them. q21 lost 20 cells to a path
#     that existed on the host and not in the container; checking the host side
#     is not the same check.
#  3. Verifies the CORPUS after each sparse stage, not just rc. A stage that
#     exits 0 having measured the wrong data is the exact failure being fixed,
#     so an rc-only gate would let it through again.
set -u
EXP=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qfix2; mkdir -p "$OUT"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt
IMG=dbbench:arcadedb

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; echo "ABORTED: $*" > "$ST"; exit 1; }

status() {
  { echo "ICDE corpus-fix queue - written $(date -Is)"
    echo "host: load $(awk '{print $1, $2, $3}' /proc/loadavg), $(free -g | awk '/^Mem:/{print $7}')G free, $(docker ps -q | wc -l) containers"
    echo
    echo "STAGES"; grep "^\[" "$LOG" | grep "STAGE" | sed 's/^/  /'
    echo
    echo "currently: ${1:-?}"
    echo
    echo "rows by lane/scale since this queue started:"
    python3 - <<PY
import json, collections
cut = open("$OUT/started_at").read().strip()
R = "$EXP/results/runs.jsonl"
c = collections.Counter(); f = collections.Counter(); rec = collections.Counter()
for l in open(R):
    l = l.strip()
    if not l: continue
    try: r = json.loads(l)
    except Exception: continue
    if str(r.get("ts_utc","")) < cut: continue
    k = (r.get("lane"), r.get("scale"))
    c[k] += 1
    if r.get("rc") != 0: f[k] += 1
    # the check that matters for sparse: did it measure a corpus with truth?
    if r.get("lane") == "l3s" and r.get("recall_at_10") is None: rec[k] += 1
for k in sorted(c, key=str):
    extra = ""
    if f[k]: extra += "   %d FAILED" % f[k]
    if rec[k]: extra += "   %d NO-RECALL (wrong corpus!)" % rec[k]
    print("  %-6s %-8s %3d rows%s" % (k[0], k[1], c[k], extra))
PY
    echo
    echo "if something looks wrong: tail -40 $LOG"
  } > "$ST" 2>&1
}

stage() {  # name, timeout_s, command...
  local name=$1 tmo=$2; shift 2
  local waited=0
  while [ "$(docker ps -q | wc -l)" -gt 0 ]; do
    if [ "$waited" -ge 900 ]; then
      if pgrep -f "runner[.]py" >/dev/null 2>&1; then
        waited=0
      else
        log "STAGE $name ORPHAN SWEEP: containers with no runner after 15min, removing"
        docker ps --format '{{.Names}}' | while read n; do docker rm -f "$n" >/dev/null 2>&1; done
        sleep 5
      fi
    fi
    sleep 30; waited=$((waited+30))
  done
  echo "$name" > "$OUT/current"
  log "STAGE $name START"
  status "$name"
  local t0=$(date +%s)
  timeout "$tmo" "$@" >"$OUT/$name.log" 2>&1
  local rc=$?
  log "STAGE $name $( [ $rc -eq 0 ] && echo OK || echo "FAILED rc=$rc" ) after $(( ($(date +%s)-t0)/60 ))min"
  [ $rc -ne 0 ] && tail -15 "$OUT/$name.log" >>"$LOG"
  docker ps --format '{{.Names}}' | grep -E '^(cli|srv)-' | while read n; do docker rm -f "$n" >/dev/null 2>&1; done
  echo "between stages" > "$OUT/current"
  status "between stages"
}

# A sparse stage that exits 0 having measured the wrong corpus is the bug this
# script exists to fix, so every one is checked against the DATA it produced.
verify_sparse() {  # scale, expected_min_rows
  local scale=$1 want=$2
  python3 - "$scale" "$want" <<'PY'
import json, sys, collections
scale, want = sys.argv[1], int(sys.argv[2])
cut = open("/home/tk/qfix2/started_at").read().strip()
R = "/home/tk/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/runs.jsonl"
rows = []
for l in open(R):
    l = l.strip()
    if not l: continue
    try: r = json.loads(l)
    except Exception: continue
    if (r.get("lane") == "l3s" and r.get("scale") == scale
            and str(r.get("ts_utc","")) >= cut and r.get("rc") == 0):
        rows.append(r)
norec = [r for r in rows if r.get("recall_at_10") is None]
docs = collections.Counter(r.get("n_docs") for r in rows)
print("  VERIFY l3s/%s: %d ok rows, n_docs=%s" % (scale, len(rows), dict(docs)))
bad = False
if len(rows) < want:
    print("    only %d/%d rows" % (len(rows), want)); bad = True
if norec:
    print("    %d rows have NO RECALL -> wrong corpus, this stage is UNUSABLE" % len(norec)); bad = True
if scale == "medium" and 8841823 not in docs:
    print("    medium n_docs is not Big-ANN's 8,841,823 -> wrong corpus"); bad = True
print("    %s" % ("REJECTED" if bad else "corpus verified"))
PY
}

date -Is > "$OUT/started_at"
log "qfix2 started, pid $$"
cd "$EXP" || die "no experiments dir"

# ---- the environment icde_long.sh did not set, each one asserted ------------
export BENCH_DATA=$HOME/bench-data
export BENCH_GRAPH_SOURCE=ldbc          # l2_graph.py:25 defaults to "synthetic"
export BENCH_GRAPH_DATA=/data/ldbc      # ldbc_snb.py:42 reads this
export BENCH_SPARSE_SOURCE=bigann       # l3_sparse.py:22 defaults to synthetic
export BENCH_SPARSE_DATA=/data/bigann
export BENCH_TPC_DATA=/data/tpch
export BENCH_TPC_SF=1

[ -d "$BENCH_DATA/ldbc/sf1" ]  || die "no ldbc/sf1 under $BENCH_DATA"
[ -d "$BENCH_DATA/ldbc/sf10" ] || die "no ldbc/sf10 under $BENCH_DATA"
[ -d "$BENCH_DATA/bigann" ]    || die "no bigann under $BENCH_DATA"
log "host data: ldbc/sf1 ldbc/sf10 bigann all present"

VER=$(docker run --rm "$IMG" python -m pip show arcadedb-embedded 2>/dev/null | awk '/^Version:/{print $2}')
case "${VER:-}" in
  "")     die "no engine version from $IMG" ;;
  *.dev*) die "F5: $IMG is $VER, a pre-release" ;;
esac
log "gate: engine $VER"

# ---- container-side preflight ----------------------------------------------
# The lane reads the environment and the corpus from INSIDE the container. That
# is the only place worth checking, and it is the check icde_long.sh never had.
log "preflight: asking the container what it can actually see"
docker run --rm --name qfix2_preflight \
  -e BENCH_GRAPH_SOURCE -e BENCH_GRAPH_DATA \
  -e BENCH_SPARSE_SOURCE -e BENCH_SPARSE_DATA \
  -v "$EXP:/work" -w /work -v "$BENCH_DATA:/data:ro" \
  "$IMG" python -u -c '
import os, sys
ok = True
print("  BENCH_GRAPH_SOURCE  =", os.environ.get("BENCH_GRAPH_SOURCE"))
print("  BENCH_SPARSE_SOURCE =", os.environ.get("BENCH_SPARSE_SOURCE"))
for p in ("/data/ldbc/sf1", "/data/ldbc/sf10", "/data/bigann"):
    e = os.path.isdir(p)
    print("  %-18s %s" % (p, "visible" if e else "MISSING"))
    ok &= e
# The decisive one: does the graph lane now accept the scales we will pass it?
import l2_graph
scales = sorted(l2_graph.SCALE_PERSONS)
print("  l2_graph accepts scales:", scales)
if "sf1" not in scales or "sf10" not in scales:
    print("  FAIL: still on the synthetic scale table"); ok = False
if os.environ.get("BENCH_SPARSE_SOURCE") != "bigann":
    print("  FAIL: sparse source is not bigann"); ok = False
sys.exit(0 if ok else 1)
' 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" -eq 0 ] || die "container preflight failed - fix before running anything"
log "preflight OK"

status "starting"

# ---- the one cell l1_medium's timeout cut off ------------------------------
stage l1_medium_gap 5400 python3 -u runner.py --lanes l1 --scale medium \
  --tier paper --backends arcadedb_embedded --workloads olap --reps 5 --only-reps 3

# ---- l2: had ZERO usable rows, cheapest to recover -------------------------
stage l2_sf1  7200  python3 -u runner.py --lanes l2 --scale sf1  --reps 5 --tier paper
stage l2_sf10 14400 python3 -u runner.py --lanes l2 --scale sf10 --reps 5 --tier paper

# ---- l3s: measured, but on the wrong corpus --------------------------------
stage l3s_tiny 7200 python3 -u runner.py --lanes l3s --scale tiny --reps 5 --tier paper
verify_sparse tiny 30 | tee -a "$LOG"

stage l3s_small 28800 python3 -u runner.py --lanes l3s --scale small --reps 5 --tier paper
verify_sparse small 30 | tee -a "$LOG"

stage l3s_medium 108000 python3 -u runner.py --lanes l3s --scale medium --reps 5 --tier paper
verify_sparse medium 15 | tee -a "$LOG"

log "STAGE ALL-DONE $(date -Is)"
status "finished"
