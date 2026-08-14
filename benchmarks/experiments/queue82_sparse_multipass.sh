#!/bin/bash
# #145: give the SPARSE lane the multi-pass protocol, for every engine.
#
# l3_sparse.py times ONE pass per cell, for all seven backends. That is
# internally fair. It is also blind to the state the dense lane turned out to
# have: queue61 gave the dense comparators our multi-pass protocol and found
# the gain is ours alone.
#
#   engine     cold    warm    gain
#   Qdrant     1.342   1.312   1.02x
#   Chroma     0.700   0.708   0.99x
#   LanceDB    3.199   3.154   1.01x
#   ArcadeDB   8.869   0.956   9.27x
#
# Nobody has ever run the sparse lane twice over one index, so we do not know
# whether LSM_SPARSE_VECTOR behaves the same way. It matters here far more than
# it did for dense, because the sparse field is TIGHT. At 1M (T4, N=5):
#
#   qdrant       2.867 ms   recall 1.0000
#   milvus       9.041      1.0000
#   elastic      9.829      0.9972
#   arcade int8 11.339      0.9935
#   arcade fp32 11.521      1.0000
#   arcade srv  13.608      0.9935
#
# ArcadeDB is 4.0x behind Qdrant but only 1.25x behind Milvus and Elasticsearch.
# A warm effect of 1.3x reorders us above both. A dense-sized 9x puts us in
# front of Qdrant. So the CURRENT RANKING IS NOT KNOWN TO BE STABLE under the
# operating point a running service actually sees, and neither the published
# order nor its inverse can be defended until this runs.
#
# WARM QUERIES ARE DISJOINT FROM COLD ONES here, and that is the one place the
# driver deliberately does not copy dense_multipass_driver.py. The dense driver
# replays the same 1000 queries every pass, so its warm number cannot separate
# "the index is now resident" (real, and what a service gets) from "these exact
# queries were seen before" (memoisation, which a service does not get). The
# split gives the warm pass questions the engine has never been asked against
# an index it has already paged in. Cost: the two halves are not paired
# per-query, which is fine for a median over 500.
#
# IMAGES ARE NOT INTERCHANGEABLE, the mistake queue61 caught in draft:
#   dbbench:arcadedb   arcadedb-embedded wheel        (embedded arms)
#   dbbench:client     qdrant/pymilvus/elasticsearch  (every served arm)
# Contract-checked below before a single build starts, because an ImportError
# discovered after a 3.5 h medium build is 3.5 h lost.
#
# ENVELOPE. Same as runner.py gives an l3s cell: cpuset 0-11, 16g at small and
# 32g at medium, ArcadeDB heap 8g/16g. Served arms SPLIT that envelope
# 0.75/0.25 between server and client rather than doubling it, so a served pair
# sums to exactly what an embedded arm gets alone. Elasticsearch, Milvus and
# the ArcadeDB server each get the heap their runner entry templates, so this
# run inherits the F3 fix rather than reintroducing the 4g-at-every-tier bug.
#
# SCOPE, stated because a silent cap reads as coverage:
#   run    arcadedb int8, arcadedb fp32, arcadedb server, qdrant, milvus,
#          elasticsearch -- every row T4 prints, at BOTH published tiers
#   SKIP   arcadedb_sparse_embedded_nocompact. It is the settle-step ablation,
#          it is not published on the project page, and its question (what
#          COMPACT buys) is orthogonal to what a second pass buys.
# small runs first because it is ~20 min and answers the f4 question on its
# own; medium chains behind it and takes ~3.5 h, dominated by builds.
set -u
mkdir -p "$HOME/profiling"
exec >> "$HOME/profiling/queue82.log" 2>&1
say() { echo "[$(date -u +%FT%TZ)] $*"; }
die() { say "ABORT: $*"; exit 1; }
guard() { while [ "$(docker ps -q | wc -l)" -gt 0 ]; do sleep 30; done; }

guard
cd "$HOME/q82/exp" || die "no staged harness at ~/q82/exp"
OUT=results/sparse_mp
mkdir -p "$OUT"

ARC_IMG=dbbench:arcadedb
CLI_IMG=dbbench:client
QDRANT_IMG="qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c"
MILVUS_IMG="milvusdb/milvus@sha256:0ea40276f8111f0183e72c8ee3144f3b9aafcd30571bd947de1ed0d22ee9dd56"
ES_IMG="docker.elastic.co/elasticsearch/elasticsearch@sha256:268f65f1b32ea367e49c9be2acab144011b8c66c462c890f6190707743199050"
ARCSRV_IMG="arcadedata/arcadedb:26.8.1@sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a"

DATA="$HOME/bench-data"
[ -f "$DATA/bigann/base_1M.csr" ] || die "no bigann corpus at $DATA/bigann"

# ---- contract check per image, before any build ----
docker run --rm -v "$PWD:/work" -w /work \
  -e BENCH_SPARSE_SOURCE=bigann -v "$DATA:/data:ro" "$ARC_IMG" python -c "
import l3_sparse as L
for k in ('arcadedb_sparse_embedded','arcadedb_sparse_embedded_fp32'):
    assert k in L.BACKENDS, k
import sparse_multipass_driver as D
assert D.PASSES == 5, D.PASSES
print('arcadedb image ok')
" || die "$ARC_IMG cannot run the sparse multipass driver"

docker run --rm -v "$PWD:/work" -w /work \
  -e BENCH_SPARSE_SOURCE=bigann -v "$DATA:/data:ro" "$CLI_IMG" python -c "
import qdrant_client, pymilvus, elasticsearch
import l3_sparse as L
for k in ('qdrant_sparse','milvus_sparse','elasticsearch_sparse',
          'arcadedb_sparse_server'):
    assert k in L.BACKENDS, k
import sparse_multipass_driver
print('client image ok')
" || die "$CLI_IMG cannot run the sparse multipass driver"

say "both images pass the contract check"

# ---- envelope, matching runner.py's MEM_BY_SCALE / HEAP_BY_SCALE ----
mem_for()  { case "$1" in small) echo 16 ;; medium) echo 32 ;; esac; }
heap_for() { case "$1" in small) echo 8g ;; medium) echo 16g ;; esac; }

run_embedded() {  # $1 backend  $2 label  $3 scale
  local be=$1 label=$2 scale=$3
  local out="$OUT/sp_${label}_${scale}.json"
  [ -s "$out" ] && { say "$label/$scale present, skipping"; return; }
  guard
  local mem heap; mem=$(mem_for "$scale"); heap=$(heap_for "$scale")
  say "starting $label/$scale (one build, 1 cold + 5 warm passes)"
  timeout 21600 docker run --rm --name q82_${label}_${scale} \
    --cpuset-cpus 0-11 --memory ${mem}g --memory-swap ${mem}g \
    -v "$PWD:/work" -w /work -v "$DATA:/data:ro" \
    -e BENCH_SPARSE_SOURCE=bigann -e BENCH_SPARSE_DATA=/data/bigann \
    -e ARCADEDB_HEAP="$heap" -e BENCH_ROLE=engine \
    -e BENCH_MP_BACKEND="$be" -e BENCH_MP_SCALE="$scale" \
    -e PROBE_OUT="/work/$out" \
    "$ARC_IMG" python -u sparse_multipass_driver.py \
    && say "$label/$scale ok" || say "$label/$scale FAILED"
}

# Served arms. The pair SPLITS the envelope 0.75 server / 0.25 client, so a
# served cell consumes exactly what an embedded cell does.
run_served() {  # $1 backend  $2 label  $3 scale  $4 srv_image  $5 ready_regex
                # remaining args: extra docker args for the SERVER container
  local be=$1 label=$2 scale=$3 img=$4 rx=$5; shift 5
  local out="$OUT/sp_${label}_${scale}.json"
  [ -s "$out" ] && { say "$label/$scale present, skipping"; return; }
  guard
  local mem heap smem cmem
  mem=$(mem_for "$scale"); heap=$(heap_for "$scale")
  smem=$(( mem * 3 / 4 )); cmem=$(( mem - smem ))
  local srv=q82srv_${label}_${scale}
  docker rm -f "$srv" >/dev/null 2>&1
  say "starting $label server (${smem}g, pinned digest)"
  # SRV_CMD is the command AFTER the image, which runner.py calls server_cmd.
  # Only Milvus needs one, and leaving it out is not a slow failure: the image
  # entrypoint is /tini --, which without a command prints its own usage and
  # exits 1, so the cell then sat in the readiness loop for ten minutes waiting
  # on a container that had already died. Set per call, cleared after.
  docker run -d --name "$srv" --cpuset-cpus 0-11 \
    --memory ${smem}g --memory-swap ${smem}g "$@" "$img" \
    ${SRV_CMD[@]+"${SRV_CMD[@]}"} >/dev/null \
    || { say "$label server FAILED to start"; return; }
  # Fail fast instead of polling a corpse: if the container is already gone,
  # the readiness regex will never match and the wait is pure dead time.
  sleep 5
  if [ -z "$(docker ps -q --filter name="^${srv}$")" ]; then
    docker logs "$srv" 2>&1 | tail -8
    docker rm -f "$srv" >/dev/null 2>&1
    say "$label server exited immediately"; return
  fi
  local up=0 i
  for i in $(seq 1 120); do
    if docker logs "$srv" 2>&1 | grep -qE "$rx"; then up=1; break; fi
    sleep 5
  done
  if [ "$up" -ne 1 ]; then
    docker logs "$srv" 2>&1 | tail -8
    docker rm -f "$srv" >/dev/null 2>&1
    say "$label server never became ready"; return
  fi
  say "$label server up; starting $label/$scale (one build, 1 cold + 5 warm)"
  timeout 21600 docker run --rm --name q82_${label}_${scale} \
    --network container:"$srv" \
    --cpuset-cpus 0-11 --memory ${cmem}g --memory-swap ${cmem}g \
    -v "$PWD:/work" -w /work -v "$DATA:/data:ro" \
    -e BENCH_SPARSE_SOURCE=bigann -e BENCH_SPARSE_DATA=/data/bigann \
    -e BENCH_SERVER_HOST=localhost -e ARCADEDB_HEAP="$heap" \
    -e BENCH_ROLE=client \
    -e BENCH_MP_BACKEND="$be" -e BENCH_MP_SCALE="$scale" \
    -e PROBE_OUT="/work/$out" \
    "$CLI_IMG" python -u sparse_multipass_driver.py \
    && say "$label/$scale ok" || say "$label/$scale FAILED"
  docker rm -f "$srv" >/dev/null 2>&1
}

SRV_CMD=()

run_tier() {
  local scale=$1 heap; heap=$(heap_for "$scale")
  say "===== tier $scale ====="
  run_embedded arcadedb_sparse_embedded      arc_int8 "$scale"
  run_embedded arcadedb_sparse_embedded_fp32 arc_fp32 "$scale"
  run_served qdrant_sparse qdrant "$scale" "$QDRANT_IMG" \
    "Qdrant (HTTP|gRPC) listening|Actix runtime found"
  SRV_CMD=(milvus run standalone)
  run_served milvus_sparse milvus "$scale" "$MILVUS_IMG" \
    "Proxy successfully started|successfully started" \
    -e DEPLOY_MODE=STANDALONE -e ETCD_USE_EMBED=true \
    -e ETCD_DATA_DIR=/var/lib/milvus/etcd \
    -e ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml \
    -e COMMON_STORAGETYPE=local \
    -v "$PWD/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml"
  SRV_CMD=()
  run_served elasticsearch_sparse elastic "$scale" "$ES_IMG" \
    '"message":"started|current.health="GREEN"' \
    -e discovery.type=single-node -e xpack.security.enabled=false \
    -e ES_JAVA_OPTS="-Xms$heap -Xmx$heap"
  run_served arcadedb_sparse_server arc_srv "$scale" "$ARCSRV_IMG" \
    "HTTP Server started" \
    -e ARCADEDB_OPTS_MEMORY="-Xms$heap -Xmx$heap" \
    -e JAVA_OPTS="-Darcadedb.server.rootPassword=dbbenchpass -Darcadedb.server.defaultDatabases=bench[root] -Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000"
}

run_tier small
say "small tier complete; summarising before medium"
python3 summarise_sparse_mp.py small || true

run_tier medium

say "=== result ==="
python3 summarise_sparse_mp.py || true
say "QUEUE82-DONE"
