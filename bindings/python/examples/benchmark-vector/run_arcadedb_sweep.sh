#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 4 ]]; then
    echo "Usage: $0 <dataset_dir> <parallel_jobs> [threads_per_task] [db_root]" >&2
    echo "  dataset_dir: datasets/MSMARCO-1M | datasets/MSMARCO-10M | datasets/MSMARCO-100M" >&2
    echo "  parallel_jobs: number of concurrent runs" >&2
    echo "  threads_per_task (optional): sets OMP/MKL/OPENBLAS/VECLIB/BLIS/NUMEXPR (for ingestion)" >&2
    echo "  db_root (optional): where to store DBs/results (default: arcadedb_runs)" >&2
    exit 1
fi

DATASET_DIR="$1"
PARALLEL_JOBS="$2"
THREADS_PER_TASK="${3:-}"
DB_ROOT="${4:-arcadedb_runs}"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BENCH_PY="$SCRIPT_DIR/benchmark_arcadedb_msmarco.py"

if [[ ! -f "$BENCH_PY" ]]; then
    echo "benchmark_arcadedb_msmarco.py not found at $BENCH_PY" >&2
    exit 1
fi

# Choose heap based on dataset size if ARCADEDB_JVM_ARGS not already set
if [[ -z "${ARCADEDB_JVM_ARGS:-}" ]]; then
    case "$(basename "$DATASET_DIR")" in
        *MSMARCO-1M*) XMX="4g" ;;    # 4G works for 1M
        *MSMARCO-10M*) XMX="16g" ;;  # 16G testing ...
        *MSMARCO-20M*) XMX="32g" ;;  # 32G testing ...
        *MSMARCO-100M*) XMX="64g" ;; # Not sure if I'll ever test this. It's humongous.
    esac
    if [[ -n "${XMX:-}" ]]; then
        JVM_ARGS="-Xmx${XMX} -Xms${XMX}"
        echo "Using ARCADEDB_JVM_ARGS='${JVM_ARGS}'" >&2
        export ARCADEDB_JVM_ARGS="${JVM_ARGS}"
    else
        echo "ARCADEDB_JVM_ARGS not set; using embedded defaults" >&2
    fi
else
    echo "Using pre-set ARCADEDB_JVM_ARGS='${ARCADEDB_JVM_ARGS}'" >&2
fi

THREAD_ENV=""
if [[ -n "$THREADS_PER_TASK" ]]; then
    THREAD_ENV="OMP_NUM_THREADS=${THREADS_PER_TASK} MKL_NUM_THREADS=${THREADS_PER_TASK} OPENBLAS_NUM_THREADS=${THREADS_PER_TASK} VECLIB_MAXIMUM_THREADS=${THREADS_PER_TASK} BLIS_NUM_THREADS=${THREADS_PER_TASK} NUMEXPR_NUM_THREADS=${THREADS_PER_TASK}"
    # Restrict JVM ForkJoinPool for JVector parallelism
    export ARCADEDB_JVM_ARGS="${ARCADEDB_JVM_ARGS:-} -Djava.util.concurrent.ForkJoinPool.common.parallelism=${THREADS_PER_TASK}"
fi

BASE="${THREAD_ENV} python \"${BENCH_PY}\" --dataset-dir \"${DATASET_DIR}\" --db-root \"${DB_ROOT}\""
cmds=()

# Parameter sweeps (cosine only):
# max_connections x beam_width x overquery_factor x quantization x store_vectors_in_graph x add_hierarchy
# Expanded for real runs; still bounded to avoid explosion
MAX_CONNECTIONS=(16)
BEAM_WIDTHS=(100)
OVERQUERY_FACTORS=(1)
QUANTIZATIONS=(INT8)
STORE_GRAPH_FLAGS=(false)
ADD_HIERARCHY_FLAGS=(true)
BATCH_SIZES=(10000)

# MAX_CONNECTIONS=(12 16 24)
# BEAM_WIDTHS=(64 100 150)
# OVERQUERY_FACTORS=(4 8 16)
# QUANTIZATIONS=(NONE INT8)
# STORE_GRAPH_FLAGS=(true false)
# ADD_HIERARCHY_FLAGS=(true false)

for MC in "${MAX_CONNECTIONS[@]}"; do
    for BW in "${BEAM_WIDTHS[@]}"; do
        for OQ in "${OVERQUERY_FACTORS[@]}"; do
            for Q in "${QUANTIZATIONS[@]}"; do
                for STORE in "${STORE_GRAPH_FLAGS[@]}"; do
                    for HIER in "${ADD_HIERARCHY_FLAGS[@]}"; do
                        FLAGS=()
                        if [[ "$STORE" == "true" ]]; then
                            FLAGS+=("--store-vectors-in-graph")
                        fi
                        if [[ "$HIER" == "true" ]]; then
                            FLAGS+=("--add-hierarchy")
                        fi
                        for BATCH in "${BATCH_SIZES[@]}"; do
                            cmds+=("${BASE} --max-connections ${MC} --beam-width ${BW} --overquery-factor ${OQ} --quantization ${Q} --batch-size ${BATCH} ${FLAGS[*]}")
                        done
                    done
                done
            done
        done
    done
done

echo "Planned runs: ${#cmds[@]}" >&2

# Shuffle to spread load/memory footprint across types
cmd_source() {
    if command -v shuf > /dev/null 2>&1; then
        printf '%s\n' "${cmds[@]}" | shuf
    else
        printf '%s\n' "${cmds[@]}"
    fi
}

# Null-delimit to preserve each command as a single arg (avoids quote breakage)
cmd_source | tr '\n' '\0' | xargs -0 -I{} -P "${PARALLEL_JOBS}" bash -lc '
  echo ">>> RUN: $1" >&2
  eval "$1"
' _ "{}"
