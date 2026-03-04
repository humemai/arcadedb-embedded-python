#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/12_vector_search.py"
HELPERS_SH="$SCRIPT_DIR/_matrix_helpers.sh"

source "$HELPERS_SH"

# Dataset Tier  Memory  CPUs  Running   Note
# Tiny          2GB     2
# Small         4GB     4
# Medium        8GB     8
# Large         16GB    16
# X-Large       32GB    32

DATASET="stackoverflow-medium"
MEM_LIMIT="8g"
THREADS=1
RUNS=1
SEED_START=0
SERVER_FRACTION="0.8"
K=50
QUERY_LIMIT=1000
QUERY_RUNS=1
QUERY_ORDER="shuffled"
OVERQUERY_FACTORS="4"

JVM_HEAP_FRACTION="0.80"
JVM_ARGS=""
ARCADEDB_VERSION="latest"
FAISS_VERSION="latest"
LANCEDB_VERSION="latest"
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

BACKENDS_RAW="bruteforce,milvus,faiss,lancedb,arcadedb,pgvector,qdrant"
BUILD_LABEL_PREFIX="sweep11"
SEARCH_LABEL_PREFIX="sweep12"

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

NORMALIZED_BACKENDS=()
for backend in "${BACKENDS[@]}"; do
    backend="$(echo "$backend" | xargs)"
    case "$backend" in
        brutceforce | bruteforce)
            backend="bruteforce"
            ;;
    esac
    if [[ -z "$backend" ]]; then
        continue
    fi
    duplicate=false
    for existing in "${NORMALIZED_BACKENDS[@]}"; do
        if [[ "$existing" == "$backend" ]]; then
            duplicate=true
            break
        fi
    done
    if [[ "$duplicate" == false ]]; then
        NORMALIZED_BACKENDS+=("$backend")
    fi
done
BACKENDS=("${NORMALIZED_BACKENDS[@]}")

if [[ "${#BACKENDS[@]}" -eq 0 ]]; then
    echo "BACKENDS_RAW resolved to empty backend list" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Benchmark script not found: $PY_SCRIPT" >&2
    exit 1
fi

FAISS_VERSION="$(matrix_resolve_version "$FAISS_VERSION" "faiss-cpu")"
LANCEDB_VERSION="$(matrix_resolve_version "$LANCEDB_VERSION" "lancedb")"

matrix_prepare_local_arcadedb_wheel "$EXAMPLES_DIR"
if [[ -n "${MATRIX_WHEEL_VERSION:-}" ]]; then
    ARCADEDB_VERSION="$MATRIX_WHEEL_VERSION"
fi

if [[ "$QUERY_ORDER" != "fixed" && "$QUERY_ORDER" != "shuffled" ]]; then
    echo "QUERY_ORDER must be either 'fixed' or 'shuffled'" >&2
    exit 1
fi

if [[ "$QUERY_RUNS" -lt 1 ]]; then
    echo "QUERY_RUNS must be >= 1" >&2
    exit 1
fi

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS backends=${BACKENDS[*]} dataset=$DATASET seed_start=$SEED_START"
echo "Profile: threads=$THREADS mem-limit=$MEM_LIMIT k=$K query-limit=$QUERY_LIMIT query-runs=$QUERY_RUNS query-order=$QUERY_ORDER overquery=$OVERQUERY_FACTORS"
echo "Build label prefix: $BUILD_LABEL_PREFIX"
echo "Search label prefix: $SEARCH_LABEL_PREFIX"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for backend in "${BACKENDS[@]}"; do
        if [[ "$backend" == "bruteforce" ]]; then
            seed=$((SEED_START + execution_idx))
            build_run_label=$(printf "%s_r%02d_%s_s%05d" "$BUILD_LABEL_PREFIX" "$run" "$backend" "$seed")
            db_path="$DB_ROOT/backend=${backend}_dataset=${DATASET}_run=${build_run_label}"
            mkdir -p "$db_path"
        else
            mapfile -t build_dirs < <(find "$DB_ROOT" -mindepth 1 -maxdepth 1 -type d -name "*backend=${backend}_dataset=${DATASET}_*run=${BUILD_LABEL_PREFIX}_r$(printf '%02d' "$run")_${backend}_s*" | sort)
            if [[ "${#build_dirs[@]}" -eq 0 ]]; then
                echo "Build DB directory not found for backend=$backend run=$run (prefix=${BUILD_LABEL_PREFIX}). Skipping..." >&2
                execution_idx=$((execution_idx + 1))
                continue
            fi

            db_path="${build_dirs[0]}"
            if [[ "${#build_dirs[@]}" -gt 1 ]]; then
                echo "Warning: multiple build DB dirs matched for backend=$backend run=$run; using first: $db_path"
            fi

            build_run_label="${db_path##*run=}"
            if [[ "$build_run_label" =~ _s([0-9]{5})$ ]]; then
                seed=$((10#${BASH_REMATCH[1]}))
            else
                seed=$((SEED_START + execution_idx))
            fi
        fi
        search_run_label=$(printf "%s_r%02d_%s_s%05d" "$SEARCH_LABEL_PREFIX" "$run" "$backend" "$seed")
        run_docker_image="$DOCKER_IMAGE"
        if [[ "$backend" == "pgvector" ]]; then
            run_docker_image="$PGVECTOR_IMAGE"
        fi

        cmd=(
            python3 "$PY_SCRIPT"
            --backend "$backend"
            --dataset "$DATASET"
            --db-path "$db_path"
            --overquery-factors "$OVERQUERY_FACTORS"
            --k "$K"
            --query-limit "$QUERY_LIMIT"
            --query-runs "$QUERY_RUNS"
            --query-order "$QUERY_ORDER"
            --seed "$seed"
            --run-label "$search_run_label"
            --threads "$THREADS"
            --mem-limit "$MEM_LIMIT"
            --jvm-heap-fraction "$JVM_HEAP_FRACTION"
            --server-fraction "$SERVER_FRACTION"
            --arcadedb-version "$ARCADEDB_VERSION"
            --faiss-version "$FAISS_VERSION"
            --lancedb-version "$LANCEDB_VERSION"
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

        if [[ -n "$JVM_ARGS" ]]; then
            cmd+=(--jvm-args "$JVM_ARGS")
        fi

        if [[ -n "$run_docker_image" ]]; then
            cmd+=(--docker-image "$run_docker_image")
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
        echo "[$((execution_idx + 1))/$((RUNS * ${#BACKENDS[@]}))] backend=$backend run=$run seed=$seed build_label=$build_run_label search_label=$search_run_label"
        echo "DB path: $db_path"
        echo "Command: ${cmd[*]}"
        set +e
        "${cmd[@]}"
        cmd_exit=$?
        set -e

        collected_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        run_status="success"
        if ((cmd_exit != 0)); then
            run_status="failed"
            echo "Run failed (exit=$cmd_exit). Continuing to next run..." >&2
        fi

        cat > "$db_path/search_run_status.json" << EOF
{
      "status": "$run_status",
      "exit_code": $cmd_exit,
      "backend": "$backend",
      "dataset": "$DATASET",
      "threads": $THREADS,
      "query_limit": $QUERY_LIMIT,
      "query_runs": $QUERY_RUNS,
      "seed": $seed,
      "build_run_label": "$build_run_label",
      "search_run_label": "$search_run_label",
      "collected_at_utc": "$collected_at"
}
EOF

        wheel_artifacts_for_dir="false"
        if [[ "$backend" == "arcadedb" ]]; then
            wheel_artifacts_for_dir="true"
        fi
        matrix_write_wheel_metadata "$db_path" "$collected_at" "$wheel_artifacts_for_dir"
        matrix_embed_wheel_metadata_in_results "$db_path" "$collected_at"
        matrix_write_dependency_versions \
            "$db_path" \
            "$collected_at" \
            "arcadedb_embedded" "$ARCADEDB_VERSION" \
            "faiss_cpu" "$FAISS_VERSION" \
            "lancedb" "$LANCEDB_VERSION" \
            "pgvector_image" "$PGVECTOR_IMAGE" \
            "qdrant_image" "$QDRANT_IMAGE" \
            "milvus_compose_version" "$MILVUS_COMPOSE_VERSION" \
            "bruteforce" "builtin"

        if ((cmd_exit == 0)) && [[ -d "$db_path" ]]; then
            du_bytes="$(du -sB1 "$db_path" | awk '{print $1}')"
            du_human="$(du -sh "$db_path" | awk '{print $1}')"

            cat > "$db_path/disk_usage_du_search.txt" << EOF
path: $db_path
du_bytes: $du_bytes
du_human: $du_human
collected_at_utc: $collected_at
search_run_label: $search_run_label
EOF

            cat > "$db_path/disk_usage_du_search.json" << EOF
{
  "path": "$db_path",
  "du_bytes": $du_bytes,
  "du_human": "$du_human",
  "collected_at_utc": "$collected_at",
  "search_run_label": "$search_run_label"
}
EOF

            echo "Saved search du size: $du_human ($du_bytes bytes) -> $db_path/disk_usage_du_search.json"
        else
            echo "Skipped search du capture because run failed or DB path missing: $db_path"
        fi

        execution_idx=$((execution_idx + 1))
    done
done

echo
echo "Completed all runs."
