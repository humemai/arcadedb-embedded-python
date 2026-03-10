#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/08_stackoverflow_tables_olap.py"
HELPERS_SH="$SCRIPT_DIR/_matrix_helpers.sh"

source "$HELPERS_SH"

# mark 🚧 for ongoing and ✅ for done
# Dataset Tier  Batch   Memory  CPUs    Running   Note
# Tiny          1,000   1GB     2
# Small         2,500   2GB     4
# Medium        5,000   4GB     8
# Large         10,000  8GB     16
# X-Large       25,000  32GB    32

DATASET="stackoverflow-medium"
BATCH_SIZE=5000
MEM_LIMIT="4g"
THREADS=1
RUNS=1
SEED_START=0
JVM_HEAP_FRACTION="0.80"
DOCKER_IMAGE="python:3.12-slim"
POSTGRESQL_IMAGE="postgres:latest"
QUERY_RUNS=10
QUERY_ORDER="shuffled"
ARCADEDB_QUERY_MAX_HEAP_ELEMENTS=-1
DBS_RAW="arcadedb_sql,sqlite,duckdb,postgresql"
LABEL_PREFIX="sweep08"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Edit configuration values at the top of this file instead (for example DATASET)." >&2
    exit 1
fi

IFS=',' read -r -a DBS <<< "$DBS_RAW"
if [[ "${#DBS[@]}" -eq 0 ]]; then
    echo "DBS_RAW cannot be empty" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Benchmark script not found: $PY_SCRIPT" >&2
    exit 1
fi

matrix_prepare_local_arcadedb_wheel "$EXAMPLES_DIR"

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS dbs=${DBS[*]} dataset=$DATASET seed_start=$SEED_START"
echo "Profile: threads=$THREADS mem-limit=$MEM_LIMIT batch-size=$BATCH_SIZE query-runs=$QUERY_RUNS query-order=$QUERY_ORDER arcadedb-query-max-heap-elements=$ARCADEDB_QUERY_MAX_HEAP_ELEMENTS"

dataset_slug="${DATASET//-/_}"
mem_tag="mem$(printf '%s' "$MEM_LIMIT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for db in "${DBS[@]}"; do
        db="$(echo "$db" | xargs)"
        if [[ -z "$db" ]]; then
            continue
        fi

        seed=$((SEED_START + execution_idx))
        run_label=$(printf "%s_t%02d_r%02d_%s_s%05d" "$LABEL_PREFIX" "$THREADS" "$run" "$db" "$seed")
        run_docker_image="$DOCKER_IMAGE"
        if [[ "$db" == "postgresql" ]]; then
            run_docker_image="$POSTGRESQL_IMAGE"
        fi

        cmd=(
            python3 "$PY_SCRIPT"
            --dataset "$DATASET"
            --db "$db"
            --threads "$THREADS"
            --batch-size "$BATCH_SIZE"
            --mem-limit "$MEM_LIMIT"
            --jvm-heap-fraction "$JVM_HEAP_FRACTION"
            --docker-image "$run_docker_image"
            --query-runs "$QUERY_RUNS"
            --query-order "$QUERY_ORDER"
            --arcadedb-query-max-heap-elements "$ARCADEDB_QUERY_MAX_HEAP_ELEMENTS"
            --seed "$seed"
            --run-label "$run_label"
        )

        echo
        echo "[$((execution_idx + 1))/$((RUNS * ${#DBS[@]}))] db=$db run=$run seed=$seed label=$run_label"
        echo "Command: ${cmd[*]}"
        set +e
        "${cmd[@]}"
        cmd_exit=$?
        set -e

        target_dir="my_test_databases/${dataset_slug}_tables_olap_${db}_${mem_tag}_${run_label}"
        if [[ ! -d "$target_dir" ]]; then
            mkdir -p "$target_dir"
        fi

        collected_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        run_status="success"
        if ((cmd_exit != 0)); then
            run_status="failed"
            echo "Run failed (exit=$cmd_exit). Continuing to next run..." >&2
        fi

        cat > "$target_dir/run_status.json" << EOF
{
  "status": "$run_status",
  "exit_code": $cmd_exit,
  "db": "$db",
  "dataset": "$DATASET",
  "threads": $THREADS,
  "batch_size": $BATCH_SIZE,
    "docker_image": "$run_docker_image",
  "query_runs": $QUERY_RUNS,
  "query_order": "$QUERY_ORDER",
  "seed": $seed,
  "run_label": "$run_label",
  "collected_at_utc": "$collected_at"
}
EOF

        wheel_artifacts_for_dir="false"
        if [[ "$db" == "arcadedb_sql" || "$db" == "arcadedb_cypher" ]]; then
            wheel_artifacts_for_dir="true"
        fi
        matrix_write_wheel_metadata "$target_dir" "$collected_at" "$wheel_artifacts_for_dir"
        matrix_embed_wheel_metadata_in_results "$target_dir" "$collected_at"
        matrix_write_dependency_versions \
            "$target_dir" \
            "$collected_at" \
            "arcadedb_embedded" "auto" \
            "duckdb" "auto" \
            "postgresql_image" "$POSTGRESQL_IMAGE" \
            "sqlite" "builtin"

        if ((cmd_exit == 0)); then
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
        else
            echo "Skipped du capture because run failed: $target_dir"
        fi

        execution_idx=$((execution_idx + 1))
    done
done

echo
echo "Completed all runs."
