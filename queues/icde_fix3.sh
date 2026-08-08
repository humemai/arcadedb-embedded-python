#!/bin/bash
# Re-measure the time-series comparator rows so T5 stops resting on artifacts
# that cannot say what produced them.
#
# WHY. provenance_check reports l4_tsbs.jsonl as the last BAD feed in the
# paper: 15 rows behind T5's time-series block that record NONE of cpuset,
# heap, mem_cap, mem_split or manifest, and no version under any key. l4_tsbs.py
# has stamped bench_common.run_conditions() since then, so this is a re-run
# rather than a code fix -- the rows simply predate the stamping.
#
# WHY NOT JUST COPY q10's BLOCK. Because q10's QuestDB arm FAILED 5/5, every
# rep "NEVER-READY", and its readiness probe says why:
#
#     docker exec q10quest sh -c 'nc -z 127.0.0.1 8812'
#
# That assumes nc exists inside questdb/questdb:9.1.1. When it does not, the
# probe can never pass, the arm is skipped, and the campaign still reports a
# tidy DONE. So the paper's QuestDB ingest figure is not q10's -- it is an
# older run nothing audits, which is exactly the hole this script closes.
#
# The probe now runs from OUR image over the shared docker network, so it
# depends on a python we ship rather than a binary we hope the vendor shipped.
# When it still fails, the questdb container's own logs go into the log, so the
# next person reads a reason instead of "NEVER-READY".
set -u
ICDE=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qfix3; mkdir -p "$OUT"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 1; }

log "qfix3 started, pid $$"

# ---- wait for qfix2, with a hard deadline ----------------------------------
DEADLINE=$(( $(date +%s) + 40*3600 ))
while ! grep -q "ALL-DONE" "$HOME/qfix2/queue.log" 2>/dev/null; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "qfix2 never completed in 40h"
  sleep 120
done
log "qfix2 complete"
while [ "$(docker ps -q | wc -l)" -gt 0 ]; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "containers still running at deadline"
  sleep 30
done
log "host idle"

VER=$(docker run --rm dbbench:arcadedb python -m pip show arcadedb-embedded 2>/dev/null | awk '/^Version:/{print $2}')
case "${VER:-}" in
  "")     die "no engine version" ;;
  *.dev*) die "F5: $VER is a pre-release" ;;
esac
log "gate: engine $VER"

[ -f "$HOME/bench-data/tsbs/cpu_influx.lp" ] || die "no TSBS corpus"

CPUS=0-11
MEM=20g
NET=qfix3net
docker network rm $NET >/dev/null 2>&1
docker network create $NET >/dev/null 2>&1 || die "no network"

# BENCH_HOST is passed EXPLICITLY: run_conditions() reports the real hostname,
# which inside a container is a random ID. Only the launcher knows this is mini.
COMMON="--cpuset-cpus $CPUS --memory $MEM --memory-swap $MEM
        -v $ICDE:/work -w /work -v $HOME/bench-data:/data:ro -v $OUT:/out
        -e TSBS_LP=/data/tsbs/cpu_influx.lp -e BENCH_HOST=mini"

# TS_SETTLE_S=0 on every arm, carried from q10 with its reasoning: queue71 ran
# the settle A/B and a settle changed nothing (435,134 vs 431,280 vs the old
# 431,306), so nobody gets one and F4 stays clean.

quest_up() {
  docker rm -f qfix3quest >/dev/null 2>&1
  docker run -d --name qfix3quest --network $NET \
    --cpuset-cpus $CPUS --memory $MEM --memory-swap $MEM \
    questdb/questdb:9.1.1 >/dev/null 2>&1
  # Probe from an image WE control. q10 shelled into the vendor image for nc
  # and got NEVER-READY 5/5; a probe may not assume the tools it needs exist
  # on the far side.
  for _ in $(seq 1 60); do
    if docker run --rm --network $NET dbbench:client python -c "
import socket, sys
try:
    socket.create_connection(('qfix3quest', 8812), 2).close()
except Exception:
    sys.exit(1)
" >/dev/null 2>&1; then
      return 0
    fi
    docker ps -q -f name=qfix3quest | grep -q . || break
    sleep 2
  done
  log "    questdb NEVER-READY -- its own logs follow, so this is diagnosable:"
  docker logs --tail 25 qfix3quest 2>&1 | sed 's/^/      /' | tee -a "$LOG"
  docker rm -f qfix3quest >/dev/null 2>&1
  return 1
}

run_doc() {  # backend rep
  local be=$1 rep=$2 img extra=""
  case "$be" in
    arcadedb) img=dbbench:arcadedb; extra="-e ARCADEDB_HEAP=8g -e BENCH_ROLE=engine" ;;
    duckdb)   img=dbbench:duckdb;   extra="-e BENCH_ROLE=engine" ;;
    questdb)  img=dbbench:client;   extra="-e BENCH_ROLE=driver -e QUEST_HOST=qfix3quest" ;;
  esac
  if [ "$be" = questdb ]; then
    quest_up || { log "    questdb rep$rep SKIPPED (never ready)"; return 1; }
  fi
  timeout 3600 docker run --rm --name qfix3_${be}_r${rep} --network $NET \
    $COMMON $extra $img \
    python -u l4_tsbs.py --backend "$be" --out "/out/${be}_r${rep}.json" \
    >>"$OUT/l4_${be}_r${rep}.log" 2>&1
  local rc=$?
  [ "$be" = questdb ] && docker rm -f qfix3quest >/dev/null 2>&1
  return $rc
}

ARMS=(arcadedb duckdb questdb)
for rep in 1 2 3 4 5; do
  # Rotate the starting arm. Running arm-by-arm to completion is how the dense
  # transport probe produced a 44% claim that reordering cut to 7%: whoever
  # goes first pays the page-cache and JIT warming for everyone after.
  off=$(( (rep - 1) % 3 ))
  order=()
  for k in 0 1 2; do order+=("${ARMS[$(( (off + k) % 3 ))]}"); done
  log "  rep$rep order: ${order[*]}"
  for be in "${order[@]}"; do
    run_doc "$be" "$rep" && log "    $be rep$rep ok" || log "    $be rep$rep FAILED"
  done
done
docker network rm $NET >/dev/null 2>&1

# ---- assemble and verify ----------------------------------------------------
# The old l4_tsbs.jsonl is NOT overwritten until the new rows pass. A feed with
# no provenance still beats a feed that is provenanced and wrong.
log "=== assemble + verify ==="
python3 - <<'PY' | tee -a "$LOG"
import glob, json, os, shutil
OUT = os.path.expanduser("~/qfix3")
EXP = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments")
DEST = os.path.join(EXP, "results", "l4_tsbs.jsonl")
# ASK EACH ROW FOR WHAT IT CAN HONESTLY SUPPLY. The first version of this
# check demanded cpuset+heap+mem_cap from every arm and rejected a run that had
# succeeded completely: DuckDB is a C++ engine with no JVM heap at all, and
# QuestDB's row is the CLIENT (role=driver) whose heap is not the engine's --
# exactly the caveat bench_common.run_conditions documents. It also read the
# version from engine_version, which l4_tsbs.py DELIBERATELY renames to
# harness_arcadedb_version for non-ArcadeDB arms so the only version a reader
# can mistake for the engine under test is the one that IS it. The engine's own
# version is backend_version.
#
# The guard's purpose was never a specific key. It was to refuse rows that
# cannot say what produced them. The rows this replaces could not; these can.
UNIVERSAL = ("cpuset", "mem_cap", "host", "role", "backend_version")
NEEDS_HEAP = {"arcadedb"}          # the only JVM engine measured in-process here

rows = []
for fp in sorted(glob.glob(os.path.join(OUT, "*_r*.json"))):
    try:
        rows.append(json.load(open(fp)))
    except Exception as e:
        print("  unreadable %s: %s" % (os.path.basename(fp), e))

by_be = {}
for r in rows:
    by_be.setdefault(r.get("backend"), []).append(r)
print("  produced %d rows: %s" % (len(rows), {k: len(v) for k, v in sorted(by_be.items())}))

bad = False
for be, rs in sorted(by_be.items()):
    miss = sorted({f for r in rs for f in UNIVERSAL if not r.get(f)})
    if be in NEEDS_HEAP and any(not r.get("heap") for r in rs):
        miss.append("heap")
    ver = sorted({str(r.get("backend_version")) for r in rs})
    role = sorted({str(r.get("role")) for r in rs})
    print("    %-10s n=%d  role=%s  %s  %s"
          % (be, len(rs), ",".join(role), ver[0][:40],
             ("MISSING " + ",".join(miss)) if miss else "conditions complete"))
    if miss:
        bad = True
    if len(rs) < 5:
        print("      only %d/5 reps" % len(rs)); bad = True
for be in ("arcadedb", "duckdb", "questdb"):
    if be not in by_be:
        print("    %-10s NO ROWS AT ALL" % be); bad = True

if bad:
    print("  NOT ACCEPTED -- leaving the existing l4_tsbs.jsonl in place.")
    print("  The old rows have no provenance, but replacing them with a short")
    print("  or unstamped set would trade one problem for a worse one.")
else:
    shutil.copy(DEST, DEST + ".pre-qfix3")
    with open(DEST, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print("  ACCEPTED -- wrote %d rows to l4_tsbs.jsonl (old kept as .pre-qfix3)" % len(rows))
PY

log "QFIX3-COMPLETE"
{ echo "qfix3 (time-series re-measure) finished $(date -Is)"; echo; tail -25 "$LOG"; } > "$ST"
