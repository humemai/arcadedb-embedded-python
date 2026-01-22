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

# Heap selection: use ARCADEDB_JVM_ARGS if set, otherwise sweep HEAP_SIZES
PRESET_JVM_ARGS="${ARCADEDB_JVM_ARGS:-}"
HEAP_SIZES_CSV="${HEAP_SIZES:-}"
HEAP_SIZES=()

# I swept the below heap sizes and got these results (1024 dimensional vectors)
# 1M: at least 4G
# 2M: 4G impossible, 6G very slow, 8G ok
# 4M: 16G works
# 8M

if [[ -z "$PRESET_JVM_ARGS" ]]; then
    # Default heap sweep per dataset (override by setting HEAP_SIZES="8g,12g,16g")
    case "$(basename "$DATASET_DIR")" in
        # *MSMARCO-100K*) HEAP_SIZES=("1g" "2g") ;;  # 1g works fine. ran with 4 threads
        # *MSMARCO-1M*) HEAP_SIZES=("4g") ;;   # below 4g heap is already really slow. ran with 4 threads
        # *MSMARCO-2M*) HEAP_SIZES=("8g" "16g") ;;   # 4 threads
        # *MSMARCO-4M*) HEAP_SIZES=("16g" "32g") ;;  # 4 threads
        *MSMARCO-8M*) HEAP_SIZES=("32g") ;; # 4 threads
        # *MSMARCO-16M*) HEAP_SIZES=("64g") ;;  # 4 threads
        *) HEAP_SIZES=("default") ;;
    esac

    if [[ -n "$HEAP_SIZES_CSV" ]]; then
        IFS="," read -ra HEAP_SIZES <<< "$HEAP_SIZES_CSV"
    fi
else
    echo "Using pre-set ARCADEDB_JVM_ARGS='${PRESET_JVM_ARGS}'" >&2
    HEAP_SIZES=("preset")
fi

THREAD_ENV=""
if [[ -n "$THREADS_PER_TASK" ]]; then
    THREAD_ENV="OMP_NUM_THREADS=${THREADS_PER_TASK} MKL_NUM_THREADS=${THREADS_PER_TASK} OPENBLAS_NUM_THREADS=${THREADS_PER_TASK} VECLIB_MAXIMUM_THREADS=${THREADS_PER_TASK} BLIS_NUM_THREADS=${THREADS_PER_TASK} NUMEXPR_NUM_THREADS=${THREADS_PER_TASK}"
    # Restrict JVM pools for JVector: common pool, physical core count, and reported processors
    JVM_THREAD_FLAGS="-Djava.util.concurrent.ForkJoinPool.common.parallelism=${THREADS_PER_TASK} -Djvector.physical_core_count=${THREADS_PER_TASK} -XX:ActiveProcessorCount=${THREADS_PER_TASK}"
fi

cmds=()

# Parameter sweeps (cosine only):
# max_connections x beam_width x overquery_factor x quantization x store_vectors_in_graph x add_hierarchy
# Expanded for real runs; still bounded to avoid explosion
MAX_CONNECTIONS=(16) # default is 16
BEAM_WIDTHS=(100)    # default is 100
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

for HEAP in "${HEAP_SIZES[@]}"; do
    if [[ "$HEAP" != "default" && "$HEAP" != "preset" ]]; then
        if ! [[ "$HEAP" =~ ^[0-9]+g$ ]]; then
            echo "Skipping invalid heap size (use integer g, e.g. 4g): $HEAP" >&2
            continue
        fi
    fi
    JVM_ARGS=""
    if [[ -n "$PRESET_JVM_ARGS" ]]; then
        JVM_ARGS="$PRESET_JVM_ARGS"
    elif [[ "$HEAP" != "default" ]]; then
        JVM_ARGS="-Xmx${HEAP} -Xms${HEAP}"
    fi
    if [[ -n "${JVM_THREAD_FLAGS:-}" ]]; then
        JVM_ARGS="${JVM_ARGS} ${JVM_THREAD_FLAGS}"
    fi

    BASE_ENV="${THREAD_ENV}"
    if [[ -n "$JVM_ARGS" ]]; then
        BASE_ENV="ARCADEDB_JVM_ARGS=\"${JVM_ARGS}\" ${BASE_ENV}"
    fi

    BASE="${BASE_ENV} python \"${BENCH_PY}\" --dataset-dir \"${DATASET_DIR}\" --db-root \"${DB_ROOT}\""

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
