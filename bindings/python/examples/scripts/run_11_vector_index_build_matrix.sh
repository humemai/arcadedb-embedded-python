#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/11_vector_index_build.py"
HELPERS_SH="$SCRIPT_DIR/_matrix_helpers.sh"

source "$HELPERS_SH"

# Dataset Tier  Batch   Memory  CPUs  Running   Note
# Tiny          1,000   2GB     2
# Small         2,500   4GB     4
# Medium        5,000   8GB     8
# Large         10,000  32GB    16
# X-Large       25,000  64GB    32

DATASET="stackoverflow-medium"
BATCH_SIZE=5000
MEM_LIMIT="8g"
THREADS=1
RUNS=1
SEED_START=0
SERVER_FRACTION="0.8"
MAX_CONNECTIONS=16
BEAM_WIDTH=100
QUANTIZATION="NONE"
STORE_VECTORS_IN_GRAPH=false
ADD_HIERARCHY=true
JVM_HEAP_FRACTION="0.80"
JVM_ARGS=""
DOCKER_IMAGE="python:3.12-slim"
PGVECTOR_IMAGE="pgvector/pgvector:pg18-trixie"
DB_ROOT="my_test_databases"

PG_HOST="127.0.0.1"
PG_PORT=6543
PG_USER="postgres"
PG_PASSWORD=""
PG_DATABASE="bench"
PG_SHARED_BUFFERS=""

QDRANT_HOST="127.0.0.1"
QDRANT_PORT=6333
QDRANT_IMAGE="qdrant/qdrant:v1.11.3"

MILVUS_HOST="127.0.0.1"
MILVUS_PORT=19530
MILVUS_COMPOSE_VERSION="v2.6.10"
MILVUS_COLLECTION="vectordata"

BACKENDS_RAW="arcadedb_sql,faiss,lancedb,pgvector,qdrant,milvus"
LABEL_PREFIX="sweep11"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Edit configuration values at the top of this file instead (for example DATASET)." >&2
    exit 1
fi

IFS=',' read -r -a BACKENDS <<< "$BACKENDS_RAW"
if [[ "${#BACKENDS[@]}" -eq 0 ]]; then
    echo "BACKENDS_RAW cannot be empty" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Benchmark script not found: $PY_SCRIPT" >&2
    exit 1
fi

matrix_prepare_local_arcadedb_wheel "$EXAMPLES_DIR"

case "$QUANTIZATION" in
    NONE | INT8 | BINARY | PRODUCT) ;;
    *)
        echo "QUANTIZATION must be one of: NONE, INT8, BINARY, PRODUCT" >&2
        exit 1
        ;;
esac

case "$ADD_HIERARCHY" in
    true | false) ;;
    *)
        echo "ADD_HIERARCHY must be true or false" >&2
        exit 1
        ;;
esac

case "$STORE_VECTORS_IN_GRAPH" in
    true | false) ;;
    *)
        echo "STORE_VECTORS_IN_GRAPH must be true or false" >&2
        exit 1
        ;;
esac

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS backends=${BACKENDS[*]} dataset=$DATASET seed_start=$SEED_START"
echo "Profile: threads=$THREADS mem-limit=$MEM_LIMIT batch-size=$BATCH_SIZE max-connections=$MAX_CONNECTIONS beam-width=$BEAM_WIDTH quantization=$QUANTIZATION"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for backend in "${BACKENDS[@]}"; do
        backend="$(echo "$backend" | xargs)"
        if [[ -z "$backend" ]]; then
            continue
        fi

        seed=$((SEED_START + execution_idx))
        run_label=$(printf "%s_r%02d_%s_s%05d" "$LABEL_PREFIX" "$run" "$backend" "$seed")
        run_docker_image="$DOCKER_IMAGE"
        if [[ "$backend" == "pgvector" ]]; then
            run_docker_image="$PGVECTOR_IMAGE"
        fi

        cmd=(
            python3 "$PY_SCRIPT"
            --backend "$backend"
            --dataset "$DATASET"
            --max-connections "$MAX_CONNECTIONS"
            --beam-width "$BEAM_WIDTH"
            --quantization "$QUANTIZATION"
            --batch-size "$BATCH_SIZE"
            --seed "$seed"
            --run-label "$run_label"
            --db-root "$DB_ROOT"
            --threads "$THREADS"
            --mem-limit "$MEM_LIMIT"
            --jvm-heap-fraction "$JVM_HEAP_FRACTION"
            --server-fraction "$SERVER_FRACTION"
            --docker-image "$run_docker_image"
            --add-hierarchy "$ADD_HIERARCHY"
            --pg-host "$PG_HOST"
            --pg-port "$PG_PORT"
            --pg-user "$PG_USER"
            --pg-database "$PG_DATABASE"
            --qdrant-port "$QDRANT_PORT"
            --qdrant-image "$QDRANT_IMAGE"
            --milvus-port "$MILVUS_PORT"
            --milvus-compose-version "$MILVUS_COMPOSE_VERSION"
            --milvus-collection "$MILVUS_COLLECTION"
        )

        if [[ "$STORE_VECTORS_IN_GRAPH" == true ]]; then
            cmd+=(--store-vectors-in-graph)
        fi

        if [[ -n "$JVM_ARGS" ]]; then
            cmd+=(--jvm-args "$JVM_ARGS")
        fi

        if [[ -n "$PG_SHARED_BUFFERS" ]]; then
            cmd+=(--pg-shared-buffers "$PG_SHARED_BUFFERS")
        fi

        if [[ -n "$PG_PASSWORD" ]]; then
            cmd+=(--pg-password "$PG_PASSWORD")
        fi

        if [[ -n "$QDRANT_HOST" && "$QDRANT_HOST" != "127.0.0.1" ]]; then
            cmd+=(--qdrant-host "$QDRANT_HOST")
        fi

        if [[ -n "$MILVUS_HOST" && "$MILVUS_HOST" != "127.0.0.1" ]]; then
            cmd+=(--milvus-host "$MILVUS_HOST")
        fi

        echo
        echo "[$((execution_idx + 1))/$((RUNS * ${#BACKENDS[@]}))] backend=$backend run=$run seed=$seed label=$run_label"
        echo "Command: ${cmd[*]}"
        set +e
        "${cmd[@]}"
        cmd_exit=$?
        set -e

        mapfile -t target_dirs < <(find "$DB_ROOT" -mindepth 1 -maxdepth 1 -type d -name "*run=${run_label}" | sort)

        if [[ "${#target_dirs[@]}" -eq 0 ]]; then
            echo "Warning: target directory not found for du capture (run_label=$run_label)"
        fi

        for target_dir in "${target_dirs[@]}"; do
            collected_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
            run_status="success"
            if ((cmd_exit != 0)); then
                run_status="failed"
            fi

            cat > "$target_dir/run_status.json" << EOF
{
  "status": "$run_status",
  "exit_code": $cmd_exit,
  "backend": "$backend",
  "dataset": "$DATASET",
  "threads": $THREADS,
  "batch_size": $BATCH_SIZE,
  "seed": $seed,
  "run_label": "$run_label",
  "collected_at_utc": "$collected_at"
}
EOF

            wheel_artifacts_for_dir="false"
            if [[ "$backend" == "arcadedb_sql" ]]; then
                wheel_artifacts_for_dir="true"
            fi
            matrix_write_wheel_metadata "$target_dir" "$collected_at" "$wheel_artifacts_for_dir"
            matrix_embed_wheel_metadata_in_results "$target_dir" "$collected_at"
            matrix_write_dependency_versions \
                "$target_dir" \
                "$collected_at" \
                "arcadedb_embedded" "auto" \
                "faiss_cpu" "auto" \
                "lancedb" "auto" \
                "pgvector_image" "$PGVECTOR_IMAGE" \
                "qdrant_image" "$QDRANT_IMAGE" \
                "milvus_compose_version" "$MILVUS_COMPOSE_VERSION"

            if ((cmd_exit != 0)); then
                echo "Skipped du capture because run failed: $target_dir"
                continue
            fi

            du_bytes="$(du -sB1 "$target_dir" | awk '{print $1}')"
            du_human="$(du -sh "$target_dir" | awk '{print $1}')"

            cat > "$target_dir/disk_usage_du.txt" << EOF
path: $target_dir
du_bytes: $du_bytes
du_human: $du_human
collected_at_utc: $collected_at
EOF

            cat > "$target_dir/disk_usage_du.json" << EOF
{
  "path": "$target_dir",
  "du_bytes": $du_bytes,
  "du_human": "$du_human",
  "collected_at_utc": "$collected_at"
}
EOF

            echo "Saved du size: $du_human ($du_bytes bytes) -> $target_dir/disk_usage_du.json"
        done

        if ((cmd_exit != 0)); then
            echo "Run failed (exit=$cmd_exit). Continuing to next run..." >&2
        fi

        execution_idx=$((execution_idx + 1))
    done
done

echo
echo "Completed all runs."
