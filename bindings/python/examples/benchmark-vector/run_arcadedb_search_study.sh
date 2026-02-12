#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 6 ]]; then
    echo "Usage: $0 <db_path> <dataset_dir> [overquery_csv] [heaps_csv] [threads] [output_root]" >&2
    echo "  db_path: path under arcadedb_runs (built DB)" >&2
    echo "  dataset_dir: datasets/MSMARCO-*" >&2
    echo "  overquery_csv (optional): default 1,2,4,8,16" >&2
    echo "  heaps_csv (optional): comma list like 1g,2g,4g" >&2
    echo "  threads (optional): default 4" >&2
    echo "  output_root (optional): default arcadedb_runs_search" >&2
    exit 1
fi

DB_PATH="$1"
DATASET_DIR="$2"
OVERQUERY_CSV="${3:-1,2,4,8,16}"
HEAPS_CSV="${4:-}"
THREADS="${5:-4}"
OUTPUT_ROOT="${6:-arcadedb_runs_search}"

# as for M=16, efConstruction=100, k=50
# | Overquery | Equivalent efSearch |
# | --------- | ------------------- |
# | 1.0       | 50                  |
# | 2.0       | 100                 |
# | 3.0       | 150                 |
# | 4.0       | 200                 |
# | 6.0       | 300                 |
# | 8.0       | 400                 |

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY="${SCRIPT_DIR}/run_arcadedb_search_study.py"

if [[ ! -f "$PY" ]]; then
    echo "run_arcadedb_search_study.py not found at $PY" >&2
    exit 1
fi

# Derive heap from db_path if not provided
if [[ -z "$HEAPS_CSV" ]]; then
    if [[ "$DB_PATH" =~ heap=([^_]+) ]]; then
        HEAPS_CSV="${BASH_REMATCH[1]}"
    else
        HEAPS_CSV="default"
    fi
fi

IFS="," read -ra HEAPS <<< "$HEAPS_CSV"

export OMP_NUM_THREADS="${THREADS}"
export MKL_NUM_THREADS="${THREADS}"
export OPENBLAS_NUM_THREADS="${THREADS}"
export VECLIB_MAXIMUM_THREADS="${THREADS}"
export BLIS_NUM_THREADS="${THREADS}"
export NUMEXPR_NUM_THREADS="${THREADS}"
JVM_THREAD_FLAGS="-Djava.util.concurrent.ForkJoinPool.common.parallelism=${THREADS} -Djvector.physical_core_count=${THREADS} -XX:ActiveProcessorCount=${THREADS}"

for HEAP in "${HEAPS[@]}"; do
    if [[ "$HEAP" != "default" ]]; then
        if ! [[ "$HEAP" =~ ^[0-9]+g$ ]]; then
            echo "Skipping invalid heap size (use integer g, e.g. 4g): $HEAP" >&2
            continue
        fi
        JVM_ARGS="-Xmx${HEAP} -Xms${HEAP} ${JVM_THREAD_FLAGS}"
    else
        JVM_ARGS="${JVM_THREAD_FLAGS}"
    fi

    echo ">>> RUN: heap=${HEAP} threads=${THREADS} overquery=${OVERQUERY_CSV}" >&2
    HEAP_FLAG=()
    if [[ "$HEAP" != "default" ]]; then
        HEAP_FLAG=("--heap-size" "$HEAP")
    fi

    python "$PY" \
        --db-path "$DB_PATH" \
        --dataset-dir "$DATASET_DIR" \
        --overquery-factors "$OVERQUERY_CSV" \
        --output-root "$OUTPUT_ROOT" \
        --heap-tag "$HEAP" \
        --jvm-args "$JVM_ARGS" \
        "${HEAP_FLAG[@]}"
done
