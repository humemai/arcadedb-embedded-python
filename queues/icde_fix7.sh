#!/bin/bash
# Measure the last two paper numbers that have NO ARTIFACT anywhere.
#
# Both were real measurements. Neither left a file. The E4 decomposition had
# the same problem and was caught because a checker read its artifact; these
# two were never wired to a checker at all, so nothing noticed:
#
#   GAV ablation   "Ablating it (N=5, identical ten-row answers) gives 1257,
#                  1272 and 381 ms". Grep finds no such numbers in results/.
#                  Measured on some dev line, transcribed into prose.
#   500k bulk A/B  "the bindings' bulk insert API sustains 177.1k rows/s
#                  against 67.3k for per-row SQL (N=5), 2.6x".
#                  async_ingest_probe.py printed it to stdout and wrote
#                  nothing. The only copy was a queue log.
#
# THREE TRAPS FIXED BEFORE THIS SCRIPT COULD BE CORRECT. Each would have
# produced rc=0 and wrong numbers:
#
#  1. runner.py forwards an ALLOWLIST of BENCH_* into the container and
#     BENCH_GAV was not on it. The ablation would have built the view anyway
#     and written rows labelled "ablation". Fixed at runner.py:538.
#  2. l2_graph.py stamped nothing when BENCH_GAV=0, so the ablation shared a
#     canonical key with the published cell and, being newer, would have
#     REPLACED T3's OLAP numbers with figures 2-7x worse. Now stamps gav, and
#     load_canonical keys on it.
#  3. async_ingest_probe.py had no way to write a file. Now honours PROBE_OUT.
#
# So this script verifies the ABLATION ACTUALLY ABLATED rather than trusting
# the exit code, which is the standing rule here: an exit code is not evidence.
set -u
EXP=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qfix7; mkdir -p "$OUT"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt
IMG=dbbench:arcadedb
RES=$EXP/results

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; echo "ABORTED: $*" > "$ST"; exit 1; }

status() {
  { echo "ICDE unsourced-number queue - written $(date -Is)"
    echo "host: load $(awk '{print $1, $2, $3}' /proc/loadavg), $(free -g | awk '/^Mem:/{print $7}')G free, $(docker ps -q | wc -l) containers"
    echo
    echo "STAGES"; grep "STAGE" "$LOG" 2>/dev/null | sed 's/^/  /'
    echo
    echo "currently: ${1:-?}"
  } > "$ST"
}

stage() {
  local name=$1 tmo=$2; shift 2
  log "STAGE $name start"
  status "$name"
  ( cd "$EXP" && timeout "$tmo" "$@" ) >>"$LOG" 2>&1
  local rc=$?
  log "STAGE $name rc=$rc"
  return $rc
}

cd "$EXP" || die "no $EXP"

# ---- wait for an idle host, with a hard deadline --------------------------
DEADLINE=$(( $(date +%s) + 7200 ))
while [ "$(docker ps -q | wc -l)" -gt 0 ]; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "host still busy after 2h"
  sleep 60
done
log "host idle"

# ---- F5: released engine only ---------------------------------------------
VER=$(docker run --rm "$IMG" python -m pip show arcadedb-embedded 2>/dev/null | awk '/^Version:/{print $2}')
case "${VER:-}" in
  "")     die "no engine version from $IMG" ;;
  *.dev*) die "F5: $IMG is $VER, a pre-release" ;;
esac
log "gate: engine $VER"

export BENCH_DATA=$HOME/bench-data
export BENCH_CPUSET=0-11
export BENCH_GRAPH_SOURCE=ldbc
export BENCH_GRAPH_DATA=/data/ldbc
[ -d "$BENCH_DATA/ldbc/sf10" ] || die "no ldbc/sf10 under $BENCH_DATA"
log "host data: ldbc/sf10 present"

# ---- preflight: the env must reach the LANE, not just the host ------------
# Trap 1 was invisible from the host: BENCH_GAV was exported and dropped at the
# container boundary. Assert inside the container that the lane sees it.
docker run --rm -e BENCH_GAV=0 -e BENCH_GRAPH_SOURCE=ldbc \
  -v "$EXP":/exp -w /exp "$IMG" python3 -c '
import os, sys
ok = True
if os.environ.get("BENCH_GAV") != "0":
    print("  FAIL: BENCH_GAV did not reach the container"); ok = False
import l2_graph
if "sf10" not in l2_graph.SCALE_PERSONS:
    print("  FAIL: l2_graph is on the synthetic scale table"); ok = False
print("  BENCH_GAV visible to the lane:", os.environ.get("BENCH_GAV"))
sys.exit(0 if ok else 1)
' 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" -eq 0 ] || die "container preflight failed"
log "preflight OK"

status "starting"

# ---- 1. GAV ablation: SF10 OLAP without the view, N=5 ---------------------
BEFORE=$(grep -c '"lane": *"l2"' "$RES/runs.jsonl" 2>/dev/null || echo 0)
export BENCH_GAV=0
stage gav_ablation_sf10 21600 python3 -u runner.py --lanes l2 --scale sf10 \
  --reps 5 --tier paper --backends arcadedb_graph_embedded --workloads olap
GAV_RC=$?
unset BENCH_GAV

# VERIFY IT ABLATED. rc=0 proves the process exited, not that the view was
# skipped. A row that ran WITH the view is the failure this checks for, and it
# is invisible in the exit code and in the latency alone.
python3 - <<'PY' 2>&1 | tee -a "$LOG"
import json, os, statistics as st
res = os.path.join(os.path.expanduser("~"),
                   "repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/runs.jsonl")
rows = [json.loads(l) for l in open(res) if l.strip()]
abl = [r for r in rows if r.get("lane") == "l2" and r.get("scale") == "sf10"
       and r.get("workload") == "olap" and r.get("gav") is False]
wit = [r for r in rows if r.get("lane") == "l2" and r.get("scale") == "sf10"
       and r.get("workload") == "olap" and r.get("gav") is not False
       and r.get("backend") == "arcadedb_graph_embedded"]
print("  ablation rows stamped gav=False: %d (want 5)" % len(abl))
if len(abl) != 5:
    print("  FAIL: the ablation did not stamp itself; do NOT use these rows")
    raise SystemExit(1)
F = "friend_age_by_city_mean_ms"
a = st.median([r[F] for r in abl if isinstance(r.get(F), (int, float))])
w = st.median([r[F] for r in wit if isinstance(r.get(F), (int, float))])
print("  friend_age  with-view %.1f ms   ablated %.1f ms   ratio %.2fx" % (w, a, a / w))
# The whole point of the ablation is that the view does something. If the two
# arms agree, the view was built in both and the run is void.
if a / w < 1.5:
    print("  FAIL: ablated arm is within 50%% of the with-view arm.")
    print("        The view was probably built anyway. These rows are void.")
    raise SystemExit(1)
print("  OK: the two arms differ, the ablation is real")
PY
[ "${PIPESTATUS[0]}" -eq 0 ] || die "GAV ablation did not ablate"

# ---- 2. 500k bulk-insert A/B, now writing an artifact --------------------
mkdir -p "$RES/ingest_ab"
for rep in 1 2 3 4 5; do
  stage ingest_ab_r$rep 5400 docker run --rm --cpuset-cpus="$BENCH_CPUSET" \
    --memory=8g --memory-swap=8g \
    -e PROBE_ROWS=500000 -e ARCADEDB_HEAP=3g \
    -e "PROBE_OUT=/exp/results/ingest_ab/ab_r$rep.json" \
    -e BENCH_CPUSET="$BENCH_CPUSET" -e BENCH_MEM_CAP=8g -e BENCH_HOST=mini \
    -e PROBE_DB_BASE=/tmp/async_probe \
    -v "$EXP":/exp -w /exp "$IMG" python3 -u async_ingest_probe.py
done

python3 - <<'PY' 2>&1 | tee -a "$LOG"
import glob, json, os, statistics as st
d = os.path.join(os.path.expanduser("~"),
                 "repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/ingest_ab")
fs = sorted(glob.glob(os.path.join(d, "ab_r*.json")))
print("  ingest A/B files: %d (want 5)" % len(fs))
if not fs:
    raise SystemExit(1)
ds = [json.load(open(f)) for f in fs]
for arm in ("serial_sql", "insert_many", "insert_many_parallel", "async_parallel"):
    v = [x[arm]["rows_per_s"] for x in ds if arm in x]
    okc = all(x[arm]["count_ok"] for x in ds if arm in x)
    if v:
        print("  %-22s %9.1f rows/s [%.1f-%.1f]  counts_ok=%s"
              % (arm, st.median(v), min(v), max(v), okc))
PY

log "STAGE ALL-DONE $(date -Is)"
echo "QFIX7-COMPLETE" >> "$LOG"
status "finished"
