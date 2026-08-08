#!/bin/bash
# Five INDEPENDENT builds per dense arm, so T5's build time and recall stop
# being one measurement wearing five rep labels.
#
# WHAT IS WRONG TODAY. dense_multipass_driver.py does ONE build then N query
# passes, and writes one record per pass. So a file looks like five reps, but
# build_s and recall_at_10 are identical down the column -- they are properties
# of the single build, copied. Anything computing median [min-max] over those
# prints a zero-width interval that reads as "five runs agreed exactly". That
# is a stronger claim than a missing number, and it is false.
#
# Only ArcadeDB fp32 escapes this, because mini_queue2.sh happened to run it
# three times (build2/build3 for issue #124). Those three say the build is
# nearly deterministic -- build_s 2678.68/2685.49/2701.95 (0.87% spread),
# recall 0.9499/0.9513/0.9533 (0.36%) -- which is exactly the kind of statement
# the other eight arms cannot make at all.
#
# UNIFORM PASSES, unlike the existing files. build1 ran the default 5 passes
# while builds 2 and 3 ran BENCH_MP_PASSES=3, so even fp32's three builds are
# not sampled alike. Every build here gets the same $PASSES.
#
# EVERY INVOCATION IS LIFTED FROM THE SCRIPT THAT PRODUCED THAT ARM'S CURRENT
# ARTIFACT, not reconstructed:
#   fp32,int8,chroma,duckvss  mini_queue2.sh run_mp()   36g, BENCH_ROLE=engine
#   lancedb                   icde_dense_fill.sh        36g, BENCH_ROLE=engine
#   sqlitevec                 icde_dense_last2.sh       36g, BENCH_ROLE=engine
#   qdrant                    icde_qdrant.sh            9g client + 27g server
#   milvus                    icde_dense_last2.sh       9g client + 27g server
#   arcsrv                    icde_srv.sh               9g client + 27g server
# Reconstructing these from memory is what the corpus bug and the QuestDB probe
# both were; a wrong cap here would produce a plausible build time, which is
# worse than a crash.
#
# BUILD-MAJOR ORDER. All arms get build 1, then all get build 2, and so on. If
# this dies at 60% every arm has three builds instead of six arms having five
# and three having none.
set -u
ICDE=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qfix5; mkdir -p "$OUT"
DEST=$ICDE/results/dense_mp5_2681; mkdir -p "$DEST"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt
BUILDS=5
PASSES=5

QDRANT_IMG="qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c"
MILVUS_IMG="milvusdb/milvus@sha256:0ea40276f8111f0183e72c8ee3144f3b9aafcd30571bd947de1ed0d22ee9dd56"
SRV_IMG="arcadedata/arcadedb:26.8.1@sha256:f54e8d85522f762767899e14cb9b6e39ef435de8216200f058843d41e5930bc9"
CLIENT_IMG=dbbench:client

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 1; }

log "qfix5 started, pid $$"

# ---- wait for qfix4 (behind qfix3, behind qfix2) ---------------------------
DEADLINE=$(( $(date +%s) + 60*3600 ))
while ! grep -q "QFIX4-COMPLETE" "$HOME/qfix4/queue.log" 2>/dev/null; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "qfix4 never completed in 60h"
  sleep 120
done
log "qfix4 complete"
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
[ -d "$HOME/bench-data/dense" ] || die "no dense corpus at ~/bench-data/dense"
for img in dbbench:arcadedb dbbench:dense "$CLIENT_IMG"; do
  docker image inspect "$img" >/dev/null 2>&1 || die "missing image $img"
done
log "gate: corpus and images present"
date -Is > "$OUT/started_at"

idle_wait() { while [ "$(docker ps -q | wc -l)" -gt 0 ]; do sleep 20; done; }

# ---- embedded arms: one container, 36g, BENCH_ROLE=engine ------------------
emb() {  # emb <arm> <backend> <image> <build> <timeout> [extra env...]
  local arm=$1 be=$2 img=$3 b=$4 tmo=$5; shift 5
  local outf="$DEST/mp_${arm}_b${b}.json"
  if [ -s "$outf" ]; then log "  SKIP $arm b$b (have it)"; return 0; fi
  idle_wait
  log "  START $arm build $b"
  local t0=$(date +%s)
  timeout "$tmo" docker run --rm --name "qfix5_${arm}_b${b}" --label dbbench=1 \
    --cpuset-cpus 0-11 --memory 36g --memory-swap 36g \
    -v "$ICDE:/work" -w /work -v "$HOME/bench-data:/data:ro" -v "$DEST:/out" \
    -e BENCH_DATA=/data -e BENCH_DENSE_DATA=/data/dense -e BENCH_DENSE_M=32 \
    -e BENCH_MP_BACKEND="$be" -e BENCH_MP_SCALE=deep10m \
    -e BENCH_MP_PASSES="$PASSES" -e BENCH_ROLE=engine \
    -e PROBE_OUT="/out/mp_${arm}_b${b}.json" \
    "$@" "$img" python -u dense_multipass_driver.py \
    > "$OUT/${arm}_b${b}.log" 2>&1
  log "  DONE $arm b$b rc=$? after $(( ($(date +%s)-t0)/60 ))min"
}

# ---- served arms: 27g server + 9g client sharing its netns -----------------
srv() {  # srv <arm> <backend> <build> <timeout> <server-up-fn>
  local arm=$1 be=$2 b=$3 tmo=$4 upfn=$5
  local outf="$DEST/mp_${arm}_b${b}.json"
  if [ -s "$outf" ]; then log "  SKIP $arm b$b (have it)"; return 0; fi
  idle_wait
  log "  START $arm build $b"
  if ! "$upfn"; then log "  $arm b$b SKIPPED (server never ready)"; return 1; fi
  local t0=$(date +%s)
  timeout "$tmo" docker run --rm --name "qfix5_${arm}_b${b}" \
    --network "container:qfix5srv" \
    --cpuset-cpus 0-11 --memory 9g --memory-swap 9g \
    -v "$ICDE:/work" -w /work -v "$HOME/bench-data:/data:ro" -v "$DEST:/out" \
    -e BENCH_DENSE_DATA=/data/dense -e BENCH_DENSE_M=32 \
    -e BENCH_SERVER_HOST=localhost -e BENCH_SERVER_PORT=2480 \
    -e BENCH_MP_BACKEND="$be" -e BENCH_MP_SCALE=deep10m \
    -e BENCH_MP_PASSES="$PASSES" -e BENCH_ROLE=client \
    -e PROBE_OUT="/out/mp_${arm}_b${b}.json" \
    "$CLIENT_IMG" python -u dense_multipass_driver.py \
    > "$OUT/${arm}_b${b}.log" 2>&1
  log "  DONE $arm b$b rc=$? after $(( ($(date +%s)-t0)/60 ))min"
  docker rm -f qfix5srv >/dev/null 2>&1
}

# Readiness greps read the SERVER'S OWN LOG, so they depend on nothing inside
# the vendor image. q10's QuestDB arm failed 5/5 shelling in for nc.
wait_log() {  # wait_log <pattern> <tries>
  local pat=$1 n=$2
  for i in $(seq 1 "$n"); do
    docker logs qfix5srv 2>&1 | grep -qE "$pat" && { log "    server up after $((i*5))s"; return 0; }
    docker ps -q -f name=qfix5srv | grep -q . || { log "    server DIED"; break; }
    sleep 5
  done
  docker logs qfix5srv 2>&1 | tail -10 | sed 's/^/      /' | tee -a "$LOG"
  docker rm -f qfix5srv >/dev/null 2>&1
  return 1
}

up_qdrant() {
  docker rm -f qfix5srv >/dev/null 2>&1
  docker run -d --name qfix5srv --cpuset-cpus 0-11 --memory 27g --memory-swap 27g \
    "$QDRANT_IMG" >/dev/null || return 1
  wait_log "Qdrant (HTTP|gRPC) listening|Actix runtime found" 60
}

up_milvus() {
  docker rm -f qfix5srv >/dev/null 2>&1
  docker run -d --name qfix5srv --cpuset-cpus 0-11 --memory 27g --memory-swap 27g \
    -e DEPLOY_MODE=STANDALONE -e ETCD_USE_EMBED=true \
    -e ETCD_DATA_DIR=/var/lib/milvus/etcd \
    -e ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml \
    -e COMMON_STORAGETYPE=local \
    -v "$ICDE/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml" \
    "$MILVUS_IMG" milvus run standalone >/dev/null || return 1
  wait_log "Proxy successfully started|successfully started" 120
}

up_arcsrv() {
  docker rm -f qfix5srv >/dev/null 2>&1
  docker run -d --name qfix5srv --cpuset-cpus 0-11 --memory 27g --memory-swap 27g \
    -e ARCADEDB_OPTS_MEMORY="-Xms24g -Xmx24g" \
    -e JAVA_OPTS="-Darcadedb.server.rootPassword=dbbenchpass -Darcadedb.server.defaultDatabases=bench[root] -Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000" \
    "$SRV_IMG" >/dev/null || return 1
  wait_log "HTTP Server started" 90
}

status() {
  { echo "ICDE dense N=5 builds - written $(date -Is)"
    echo "host: load $(awk '{print $1}' /proc/loadavg), $(free -g | awk '/^Mem:/{print $7}')G free, $(docker ps -q|wc -l) containers"
    echo; echo "builds completed per arm (target $BUILDS):"
    for a in fp32 int8 chroma duckvss lancedb sqlitevec qdrant milvus arcsrv; do
      printf "  %-10s %d\n" "$a" "$(ls "$DEST"/mp_${a}_b*.json 2>/dev/null | wc -l)"
    done
    echo; echo "tail: tail -30 $LOG"
  } > "$ST" 2>&1
}

for b in $(seq 1 "$BUILDS"); do
  log "===== BUILD ROUND $b of $BUILDS ====="
  status
  # fp32 asks for itself by LEAVING BENCH_DENSE_QUANT UNSET. Passing the
  # literal "fp32" is what killed q3_fp32_b1..b3; see mini_queue2.sh:236.
  emb fp32      arcadedb_dense_embedded dbbench:arcadedb "$b" 21600 -e ARCADEDB_HEAP=24g
  emb int8      arcadedb_dense_embedded dbbench:arcadedb "$b" 21600 -e ARCADEDB_HEAP=24g -e BENCH_DENSE_QUANT=INT8
  emb chroma    chroma_dense            dbbench:dense    "$b" 10800
  emb duckvss   duckdb_vss_dense        dbbench:dense    "$b" 10800
  emb lancedb   lancedb_dense           dbbench:dense    "$b" 10800
  emb sqlitevec sqlite_vec_dense        dbbench:dense    "$b" 21600
  srv qdrant    qdrant_dense            "$b" 21600 up_qdrant
  srv milvus    milvus_dense            "$b" 10800 up_milvus
  srv arcsrv    arcadedb_dense_server   "$b" 28800 up_arcsrv
done
status

log "=== acceptance ==="
python3 - <<'PY' | tee -a "$LOG"
import glob, json, os, statistics as st
DEST = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/dense_mp5_2681")
arms = ["fp32","int8","chroma","duckvss","lancedb","sqlitevec","qdrant","milvus","arcsrv"]
print("  %-10s %-7s %-24s %-22s" % ("arm","builds","build_s median [min-max]","recall median [min-max]"))
for a in arms:
    fs = sorted(glob.glob(os.path.join(DEST, "mp_%s_b*.json" % a)))
    bs, rc = [], []
    for f in fs:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        r = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)
        if not r: continue
        if isinstance(r.get("build_s"), (int, float)): bs.append(r["build_s"])
        if isinstance(r.get("recall_at_10"), (int, float)): rc.append(r["recall_at_10"])
    def fmt(v, p):
        return "-" if not v else "%.*f [%.*f-%.*f]" % (p, st.median(v), p, min(v), p, max(v))
    flag = "" if len(bs) >= 5 else ("   <-- only %d builds" % len(bs))
    print("  %-10s %-7d %-24s %-22s%s" % (a, len(fs), fmt(bs,1), fmt(rc,4), flag))
print()
print("  These are INDEPENDENT builds: each row is its own container, its own")
print("  index build, its own recall. Unlike dense_mp_2681, where five records")
print("  share one build_s because they are five query passes over one build.")
PY

log "QFIX5-COMPLETE"
status
