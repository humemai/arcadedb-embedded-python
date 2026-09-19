#!/usr/bin/env bash
# Smoke every comparator whose pin MOVED in the October re-pin (2026-09-19),
# at the skeleton tier, through the runner, against the newly pinned images.
#
# This is the #87/#103d re-pin's proof of work: a version is not pinned because
# a registry has it, it is pinned because the lane it belongs on still runs and
# still agrees. Rows land in results/runs_skeleton_laptop.jsonl beside the
# ArcadeDB October rows, and equivalence_check.py reads the file afterwards --
# a version change that changes an answer is a finding, not a pin.
#
# ARCADEDB ARMS ARE DELIBERATELY ABSENT. ArcadeDB is not a comparator: it is
# pinned to our own wheel and the matched 26.10.1-SNAPSHOT image at commit
# 417314c18d, already re-run by oct_skeleton_arcadedb.sh. Nothing here touches
# it, and no stage names an arcadedb backend.
#
# ONLY=<extended regex over stage labels> restricts the run. Default: all.
set -uo pipefail
cd "$(dirname "$0")"

LOGDIR="${LOGDIR:?export LOGDIR=<where the per-stage logs go>}"
ONLY="${ONLY:-.}"
PY="${PY:-/home/tk/repos/humemai/arcadedb-embedded-python/.venv/bin/python}"
mkdir -p "$LOGDIR"

export BENCH_ALLOW_DEV=1
export BENCH_DATA="$HOME/bench-data"
export BENCH_HOST=laptop
export BENCH_CPUSET=0-11
export BENCH_ARCADEDB_NO_COMPACT_HEADERS=1
export BENCH_TPC_SF=0.01

RF=runs_skeleton_laptop.jsonl
COMMON=(--reps 1 --tier sweep --workers 1 --results-file "$RF")

say() { echo "[$(date -Is)] $*" | tee -a "$LOGDIR/STATUS.txt"; }

stage() {
  local label=$1; shift
  if ! [[ $label =~ $ONLY ]]; then say "SKIP  $label"; return 0; fi
  local -a envs=()
  while [[ $# -gt 0 && $1 != "--" ]]; do envs+=("$1"); shift; done
  [[ ${1:-} == "--" ]] && shift
  say "START $label${envs[*]+ (env: ${envs[*]})}"
  env "${envs[@]+${envs[@]}}" "$PY" -u runner.py "$@" "${COMMON[@]}" \
      >"$LOGDIR/$label.log" 2>&1
  local rc=$?
  say "END   $label rc=$rc"
  return 0
}

# Backends grouped by the pin that moved under them.
#   postgres 17.10->18.6            postgres, postgres_tuned
#   mongodb  8.2.12->8.3.11         mongodb, mongodb_graph, mongodb_dense, mongodb_e2
#   neo4j    2026.07.1->2026.08.1   neo4j_graph, neo4j_dense, neo4j_e2, composed_qdrant_neo4j
#   qdrant   v1.18.2->v1.19.1       qdrant_dense, qdrant_dense_int8, qdrant_sparse
#   milvus   v2.6.13->v3.0.1        milvus_dense, milvus_dense_int8, milvus_sparse
#   pgvector pg17->pg18             pgvector_dense, pgvector_sparse
#   pg-age   PG17/AGE1.7->PG18/1.8  pg_age_e2
#   timescale 2.28.3->2.30.1-pg18   timescaledb
#   questdb  9.1.1->10.0.1          questdb
#   elastic  9.4.1->9.5.4           elasticsearch_sparse
#   ladybug  0.19.1->0.20.4         ladybug_graph
#   lancedb  0.37.1->0.39.0         lancedb_dense
#   neo4j driver 6.2.0->6.3.1       ALSO memgraph_graph (engine unmoved, client moved)
TPC=postgres,postgres_tuned,mongodb
GRAPH=neo4j_graph,ladybug_graph,mongodb_graph,memgraph_graph
DENSE=pgvector_dense,qdrant_dense,qdrant_dense_int8,milvus_dense,milvus_dense_int8,neo4j_dense,mongodb_dense,lancedb_dense
SPARSE=pgvector_sparse,qdrant_sparse,milvus_sparse,elasticsearch_sparse
TS=questdb,timescaledb,mongodb
E2=pg_age_e2,mongodb_e2,neo4j_e2,composed_qdrant_neo4j

say "smoke of the October re-pin; results -> results/$RF"
say "ONLY=$ONLY"

# ---- l1tpc: TPC-H/TPC-C at SF0.01, writes twice (relaxed + strict), reads once.
stage 21-l1tpc-oltp-relaxed -- --lanes l1tpc --workloads oltp --scale micro --backends "$TPC"
stage 22-l1tpc-oltp-strict  -- --lanes l1tpc --workloads oltp --scale micro --backends "$TPC" --durability strict
stage 23-l1tpc-olap         -- --lanes l1tpc --workloads olap --scale micro --backends "$TPC"

# ---- l2 graph: the synthetic micro network.
stage 24-l2-oltp-relaxed -- --lanes l2 --workloads oltp --scale micro --backends "$GRAPH"
stage 25-l2-oltp-strict  -- --lanes l2 --workloads oltp --scale micro --backends "$GRAPH" --durability strict
stage 26-l2-olap-micro   -- --lanes l2 --workloads olap --scale micro --backends "$GRAPH"

# ---- l2 analytics: the LDBC SF1 slice. LadybugDB's projection and COPY paths
# are the flagged risk of this re-pin, and LSQB is where they are exercised.
stage 27-l2-olap-sf1 \
  BENCH_GRAPH_SOURCE=ldbc BENCH_GRAPH_MSG_LIMIT=30000 BENCH_GRAPH_PERSON_LIMIT=2000 \
  -- --lanes l2 --workloads olap --scale sf1 --backends "$GRAPH"

# ---- l3d dense, with the #82d mutate phase the skeleton forces on.
stage 28-l3d-dense BENCH_DENSE_MUTATE=1 \
  -- --lanes l3d --workloads search --scale micro --backends "$DENSE"

# ---- l3s sparse.
stage 29-l3s-sparse -- --lanes l3s --workloads search --scale micro --backends "$SPARSE"

# ---- l4 time series: QuestDB 10's ILP path and TimescaleDB on PG18.
stage 30-l4-ts -- --lanes l4 --workloads ingest --scale ts100 --backends "$TS"

# ---- e2 cross-model.
stage 31-e2-hybrid-relaxed -- --lanes e2 --workloads hybrid --scale e2 --backends "$E2"
stage 32-e2-hybrid-strict  -- --lanes e2 --workloads hybrid --scale e2 --backends "$E2" --durability strict
stage 33-e2-atomicity      -- --lanes e2 --workloads atomicity --scale e2 --backends pg_age_e2,mongodb_e2,neo4j_e2

say "ALL-DONE"
