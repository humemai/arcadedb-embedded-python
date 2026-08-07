#!/bin/bash
# The 11-day queue. Runs unattended; you check ~/STATUS.txt once a day.
#
#   ssh mini 'cat ~/STATUS.txt'
#
# WHAT THIS RUNS AND WHY. A full independent re-measure of every published tier
# on 26.8.1, through runner.py, at N=5. That is worth 11 days of an idle
# machine for three reasons at once:
#
#  1. REPRODUCIBILITY. Every headline number gets measured a second time in an
#     independent campaign. "Reproduced in a separate run weeks apart" is a
#     claim the paper cannot currently make and reviewers do ask for.
#  2. IT CLOSES F7. The dense driver now stamps degree_param/degree_family via
#     the same function the lane uses, so the cells become verifiable rather
#     than merely assumed matched.
#  3. IT CLOSES THE SERVER-CONDITIONS GAP. runner.py now reads each server
#     container's real cpuset, cap and -Xmx from the daemon into every served
#     row, so F3 can check a served cell instead of reconstructing it.
#
# ONLY KNOWN-GOOD INVOCATIONS. Every stage below is a runner.py lane or the
# native TS probe, both of which ran successfully within the last day. Two
# reconstructed invocations failed this week (a missing python module, a
# mis-specified data path), and with nobody at the laptop for 11 days a
# reconstruction that fails quietly wastes days rather than minutes. The dense
# DEEP-10M multipass driver is deliberately NOT here: its launch command
# survives in no script, so it would be a third reconstruction.
#
# FAILURE POLICY. A stage that fails does not stop the queue. Each is
# independent, each has its own timeout, and STATUS.txt records what happened
# so a bad stage costs its own budget and nothing else.
set -u
EXP=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qlong; mkdir -p "$OUT"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt
IMG=dbbench:arcadedb
export BENCH_DATA=$HOME/bench-data

log(){ echo "[$(date -Is)] $*" | tee -a "$LOG"; }

status(){
  {
    echo "ICDE long queue - written $(date -Is)"
    echo "host: load$(cut -d' ' -f1-3 /proc/loadavg | sed 's/^/ /'), $(free -g|awk '/^Mem:/{print $7}')G free, $(docker ps -q|wc -l) containers"
    echo
    echo "STAGES"
    # log() prefixes a timestamp, so anchoring on ^STAGE matches nothing and
    # this section stayed empty -- a status file whose progress list is always
    # blank is worse than no status file, because it reads as "no progress".
    grep -o 'STAGE .*' "$LOG" 2>/dev/null | tail -40 | sed 's/^/  /'
    echo
    echo "currently: ${1:-idle}"
    echo
    echo "published rows on 26.8.1 by lane/scale (this campaign):"
    python3 - <<'PY' 2>/dev/null || echo "  (count unavailable)"
import json, collections, os
CUT = open(os.path.expanduser("~/qlong/started_at")).read().strip()[:19]
R = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/runs.jsonl")
c = collections.Counter(); bad = collections.Counter()
for l in open(R):
    try: r = json.loads(l)
    except Exception: continue
    if str(r.get("ts_utc","")) >= CUT:
        k = (r.get("lane"), r.get("scale"))
        c[k] += 1
        if r.get("rc") != 0: bad[k] += 1
for k in sorted(c, key=str):
    print("  %-6s %-8s %3d rows%s" % (k[0], k[1], c[k],
          ("   %d FAILED" % bad[k]) if bad[k] else ""))
if not c: print("  (none yet)")
PY
    echo
    echo "if something looks wrong: tail -40 ~/qlong/queue.log"
  } > "$ST".tmp && mv "$ST".tmp "$ST"
}

stage(){  # name, timeout_s, command...
  local name=$1 tmo=$2; shift 2
  # WAIT FOR AN IDLE HOST, BUT NEVER FOREVER. This guard has blocked three
  # times on containers whose runner had already died -- orphans nobody would
  # ever clean up, so the wait could not end. It is the single most expensive
  # bug in this harness: it has cost hours of an idle machine each time, and
  # it looks identical to "still working" from outside.
  #
  # So the wait is bounded, and when it expires the guard assumes what has
  # been true every time: a container with no live runner behind it is
  # garbage. It says so, removes it, and continues, rather than protecting a
  # campaign that is not running.
  local waited=0
  while [ "$(docker ps -q | wc -l)" -gt 0 ]; do
    if [ "$waited" -ge 900 ]; then
      if pgrep -f "runner\.py" >/dev/null 2>&1 || pgrep -f "l4_native_probe" >/dev/null 2>&1; then
        waited=0            # something real is running; keep waiting
      else
        log "STAGE $name ORPHAN SWEEP: containers with no runner after 15min, removing"
        docker ps --format '{{.Names}}' | while read n; do docker rm -f "$n" >/dev/null 2>&1; done
        sleep 5
      fi
    fi
    sleep 30; waited=$((waited+30))
  done
  echo "$name" > "$OUT/current"
  log "STAGE $name START $(date -Is)"
  status "$name"
  local t0=$(date +%s)
  timeout "$tmo" "$@" >"$OUT/$name.log" 2>&1
  local rc=$?
  log "STAGE $name $( [ $rc -eq 0 ] && echo OK || echo "FAILED rc=$rc" ) after $(( ($(date +%s)-t0)/60 ))min"
  [ $rc -ne 0 ] && tail -15 "$OUT/$name.log" >>"$LOG"
  # A stage leaves nothing behind for the next one.
  docker ps --format '{{.Names}}' | grep -E '^(cli|srv)-' | while read n; do docker rm -f "$n" >/dev/null 2>&1; done
  echo "between stages" > "$OUT/current"
  status "between stages"
}

cd "$EXP" || { log "no experiments dir"; exit 1; }
date -Is > "$OUT/started_at"
echo starting > "$OUT/current"
log "qlong started, pid $$"

# STATUS.txt must never look frozen. status() alone fires only between stages,
# and a stage can run for hours, so a daily check mid-stage would see a
# timestamp from that morning and read it as stuck. This refreshes every ten
# minutes from whatever the current stage is, and dies with the queue.
( while kill -0 $$ 2>/dev/null; do sleep 600; status "$(cat "$OUT/current" 2>/dev/null)"; done ) &
REFRESHER=$!
trap 'kill $REFRESHER 2>/dev/null' EXIT
VER=$(docker run --rm "$IMG" python -m pip show arcadedb-embedded 2>/dev/null | awk '/^Version:/{print $2}')
case "${VER:-}" in "") log "ABORT no version"; exit 1;; *.dev*) log "ABORT F5: $VER"; exit 1;; esac
log "STAGE gate OK engine $VER"
status "starting"

# Cheap and fast first, so a daily check sees progress early.
stage l1_medium      21600 python3 -u runner.py --lanes l1    --scale medium  --reps 5 --tier paper
stage l2_sf1         14400 python3 -u runner.py --lanes l2    --scale sf1     --reps 5 --tier paper
stage l1tpc_tpch1    21600 python3 -u runner.py --lanes l1tpc --scale tpch1   --reps 5 --tier paper
stage e2             14400 python3 -u runner.py --lanes e2    --scale e2      --reps 5 --tier paper
stage l3s_tiny       14400 python3 -u runner.py --lanes l3s   --scale tiny    --reps 5 --tier paper
stage l2_sf10        43200 python3 -u runner.py --lanes l2    --scale sf10    --reps 5 --tier paper
stage l3s_small      28800 python3 -u runner.py --lanes l3s   --scale small   --reps 5 --tier paper
stage l3d_small      28800 python3 -u runner.py --lanes l3d   --scale small   --reps 5 --tier paper
stage l3s_medium     86400 python3 -u runner.py --lanes l3s   --scale medium  --reps 5 --tier paper

# TSBS at 10x the corpus the paper reports. New scale point, known-good probe.
mkdir -p "$EXP/results/ts10x"
for rep in 1 2 3 4 5; do
  stage ts10x_r$rep 7200 docker run --rm --name ts10x_r$rep \
    --cpuset-cpus 0-11 --memory 24g --memory-swap 24g \
    -v "$EXP:/work" -w /work -v "$HOME/bench-data:/data:ro" \
    -e TSBS_LP=/data/tsbs/cpu_influx_s1000.lp \
    -e TS_PRIMITIVE=1 -e TS_NUMPY=1 -e TS_SHARDS=4 -e TS_TAGS=1 \
    -e TS_SETTLE_S=0 -e TS_LAST_AB=1 \
    -e ARCADEDB_HEAP=12g -e BENCH_ROLE=engine \
    -e PROBE_OUT="/work/results/ts10x/nosettle_r$rep.json" \
    "$IMG" python -u l4_native_probe.py
done

log "STAGE ALL-DONE $(date -Is)"
status "finished - all stages attempted"
