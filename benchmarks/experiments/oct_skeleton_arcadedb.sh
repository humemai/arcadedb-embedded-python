#!/usr/bin/env bash
# Re-run every ArcadeDB arm of the laptop skeleton (CAMPAIGN.md 5a) on the
# OCTOBER pin: wheel arcadedb_embedded-26.10.1.dev0 and server image
# arcadedata/arcadedb:26.10.1-SNAPSHOT, both carrying upstream commit
# 417314c18da782620463bc7c09ac6bd34ac6fbda (verified: the engine jar's
# com/arcadedb/arcadedb.properties buildNumber is identical on both sides).
#
# The skeleton cells published as "arcadedb 26.8.1" while the October campaign
# pins 417314c18d, so the preview page named an engine the campaign does not
# run. This re-runs the 49 ArcadeDB rows of results/runs_skeleton_laptop.csv,
# at the same lanes, workloads, scales, durability classes and flags, and
# appends to results/runs_skeleton_laptop.jsonl.
#
# ARCADEDB_WHEEL + ARCADEDB_SERVER_IMAGE + ARCADEDB_ENGINE_COMMIT are the
# runner's own matched-pair path (runner.py "local engine" block): the first
# two must be set together (F5, one engine line per table), the third stamps
# engine_commit on every row, and _require_local_server_image() refuses a
# claimed local pin whose served arm is still on a stock image. The wheel has
# ALREADY been baked into dbbench:arcadedb by
#   BENCH_ALLOW_DEV=1 ARCADEDB_WHEEL=<whl> ./build_images.sh arcadedb
# because the embedded arms read the package from that image, not from a venv.
#
# BENCH_ARCADEDB_NO_COMPACT_HEADERS=1 is STILL required, re-verified by running
# on 2026-09-18: the published 26.10.1-SNAPSHOT image is Temurin 21.0.12, and
#   docker run --entrypoint java arcadedata/arcadedb:26.10.1-SNAPSHOT \
#     -XX:+UseCompactObjectHeaders -version
# answers "Unrecognized VM option 'UseCompactObjectHeaders'" and refuses to
# boot. The flag reaches the SERVER container's JAVA_OPTS only (runner.py:407
# and four siblings); the embedded JVM adds it unconditionally in jvm.py.
#
# STAGE ORDER. The stage labels are numbered by lane in the original order, but
# this script runs the LANES THAT HAVE NO OCTOBER ROWS YET first (10 l4, 11-13
# e2, 14 lifecycle) and the already-re-run lanes last (01-09). Two reasons: the
# missing lanes are the ones the re-run exists for, and 01-09 are being redone
# only to put every ArcadeDB row under the per-query budget regime of DECISIONS
# #106 (budget_lookup.budget_for, landed 18:30 on 2026-09-18, after those nine
# stages finished at 18:23). load_canonical dedupes on the payload key and
# keeps the newest ts_utc, so a later re-run supersedes cleanly.
#
# ONLY=<extended regex over stage labels> restricts the run. Default: all.
set -uo pipefail
cd "$(dirname "$0")"

WHEEL="${ARCADEDB_WHEEL:?export ARCADEDB_WHEEL=<path to the 26.10.1.dev0 wheel>}"
LOGDIR="${LOGDIR:?export LOGDIR=<where the per-stage logs go>}"
ONLY="${ONLY:-.}"
mkdir -p "$LOGDIR"

export BENCH_ALLOW_DEV=1
export BENCH_DATA="$HOME/bench-data"
export BENCH_HOST=laptop
export BENCH_CPUSET=0-11
export BENCH_ARCADEDB_NO_COMPACT_HEADERS=1
export BENCH_TPC_SF=0.01
export ARCADEDB_SERVER_IMAGE="arcadedata/arcadedb:26.10.1-SNAPSHOT@sha256:ccb0ad1f6e5298ee6b63e837b7da37b3c96da6e58b2179c2ad81644d3814cf44"
export ARCADEDB_ENGINE_COMMIT=417314c18da782620463bc7c09ac6bd34ac6fbda

RF=runs_skeleton_laptop.jsonl
COMMON=(--reps 1 --tier sweep --workers 1 --results-file "$RF")

say() { echo "[$(date -Is)] $*" | tee -a "$LOGDIR/STATUS.txt"; }

# stage <label> [VAR=val ...] -- <runner args...>
# Anything before the literal -- is exported for this stage only.
stage() {
  local label=$1; shift
  if ! [[ $label =~ $ONLY ]]; then say "SKIP  $label"; return 0; fi
  local -a envs=()
  while [[ $# -gt 0 && $1 != "--" ]]; do envs+=("$1"); shift; done
  [[ ${1:-} == "--" ]] && shift
  say "START $label${envs[*]+ (env: ${envs[*]})}"
  env "${envs[@]+${envs[@]}}" python3 -u runner.py "$@" "${COMMON[@]}" \
      >"$LOGDIR/$label.log" 2>&1
  local rc=$?
  say "END   $label rc=$rc"
  return 0
}

say "pin wheel=$(basename "$WHEEL") server=$ARCADEDB_SERVER_IMAGE commit=$ARCADEDB_ENGINE_COMMIT"
say "ONLY=$ONLY"

TPC=arcadedb_embedded,arcadedb_server
GRAPH=arcadedb_graph_embedded,arcadedb_graph_server
DENSE=arcadedb_dense_embedded,arcadedb_dense_embedded_int8,arcadedb_dense_server,arcadedb_dense_server_int8
SPARSE=arcadedb_sparse_embedded,arcadedb_sparse_embedded_fp32,arcadedb_sparse_embedded_nocompact,arcadedb_sparse_server,arcadedb_sparse_server_fp32
# TS_BACKENDS narrows stage 10 to the arms still missing. The l4 cells are the
# longest on the skeleton (the document arm runs ~45 min), so when a stage is
# interrupted part-way the recovery is to finish the missing arm rather than
# repeat the three that already wrote rows.
TS=${TS_BACKENDS:-arcadedb_ts_doc,arcadedb_ts_doc_server,arcadedb_ts_native,arcadedb_ts_native_server}
E2=arcadedb_e2,arcadedb_e2_server
LC=arcadedb_embedded,arcadedb_server

# ======================= lanes with no October rows yet =======================

# ---- l4 time series: document path and native TIMESERIES type, both arms.
# The lane the re-run exists for: #7610 is the served time-bucket serializer.
stage 10-l4-ts -- --lanes l4 --workloads ingest --scale ts100 --backends "$TS"

# ---- e2 cross-model: hybrid twice, atomicity once.
stage 11-e2-hybrid-relaxed -- --lanes e2 --workloads hybrid --scale e2 --backends "$E2"
stage 12-e2-hybrid-strict  -- --lanes e2 --workloads hybrid --scale e2 --backends "$E2" --durability strict
stage 13-e2-atomicity      -- --lanes e2 --workloads atomicity --scale e2 --backends "$E2"

# ---- lifecycle: all eight situations, embedded and served.
stage 14-lifecycle -- --lanes lifecycle --scale lc10k --backends "$LC"

# ================= lanes re-run for one budget regime (#106) ==================

# ---- l1tpc: TPC-H/TPC-C at SF0.01. Writes twice, reads once.
stage 01-l1tpc-oltp-relaxed -- --lanes l1tpc --workloads oltp --scale micro --backends "$TPC"
stage 02-l1tpc-oltp-strict  -- --lanes l1tpc --workloads oltp --scale micro --backends "$TPC" --durability strict
stage 03-l1tpc-olap         -- --lanes l1tpc --workloads olap --scale micro --backends "$TPC"

# ---- l2 graph: the synthetic micro network, writes twice.
stage 04-l2-oltp-relaxed -- --lanes l2 --workloads oltp --scale micro --backends "$GRAPH"
stage 05-l2-oltp-strict  -- --lanes l2 --workloads oltp --scale micro --backends "$GRAPH" --durability strict
stage 06-l2-olap-micro   -- --lanes l2 --workloads olap --scale micro --backends "$GRAPH"

# ---- l2 analytics: the LDBC SF1 slice, the same caps every other engine's
# analytics row used (DECISIONS #104; lsqb_probe.py header).
stage 07-l2-olap-sf1 \
  BENCH_GRAPH_SOURCE=ldbc BENCH_GRAPH_MSG_LIMIT=30000 BENCH_GRAPH_PERSON_LIMIT=2000 \
  -- --lanes l2 --workloads olap --scale sf1 --backends "$GRAPH"

# ---- l3d dense: both precisions, with the #82d mutate phase the skeleton forces on.
stage 08-l3d-dense BENCH_DENSE_MUTATE=1 \
  -- --lanes l3d --workloads search --scale micro --backends "$DENSE"

# ---- l3s sparse: the synthetic micro corpus, ground truth already staged at
# $BENCH_DATA/sparse/micro/gt.npy (without it recall_at_10 is null and
# load_canonical drops every row).
stage 09-l3s-sparse -- --lanes l3s --workloads search --scale micro --backends "$SPARSE"

say "ALL-DONE"
