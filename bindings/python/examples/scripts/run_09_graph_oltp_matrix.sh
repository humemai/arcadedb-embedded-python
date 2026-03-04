#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/09_stackoverflow_graph_oltp.py"
HELPERS_SH="$SCRIPT_DIR/_matrix_helpers.sh"

source "$HELPERS_SH"

# mark 🚧 for ongoing and ✅ for done
# Ladybug uses a reduced transaction budget for OLTP matrix fairness/stability.
# multi-threading only works well with arcadedb for this OLTP

# Dataset Tier  Transactions  Batch   Memory  CPUs  Running     Note
# Tiny          10,000        1,000   1GB     1
# Tiny          10,000        1,000   1GB     8
# Small         50,000        2,500   2GB     1
# Small         50,000        2,500   2GB     8
# Medium        100,000       5,000   4GB     1
# Medium        100,000       5,000   4GB     8
# Large         250,000       10,000  8GB     1
# Large         250,000       10,000  8GB     8
# X-Large       1,000,000     25,000  32GB    1
# X-Large       1,000,000     25,000  32GB    8

DATASET="stackoverflow-medium"
ARCADEDB_TRANSACTIONS=100000
LADYBUG_TRANSACTIONS_FRACTION=0.1
GRAPHQLITE_TRANSACTIONS_FRACTION=0.1
BATCH_SIZE=5000
MEM_LIMIT="4g"
THREADS=1
RUNS=1
SEED_START=0
JVM_HEAP_FRACTION="0.80"
ARCADEDB_VERSION="latest"
LADYBUG_VERSION="latest"
GRAPHQLITE_VERSION="latest"
DOCKER_IMAGE="python:3.12-slim"
# DBS_RAW="python_memory"
DBS_RAW="arcadedb_sql,arcadedb_cypher,ladybug,sqlite_native,python_memory"
LABEL_PREFIX="sweep09"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Edit configuration values at the top of this file instead (for example DATASET)." >&2
    exit 1
fi

if [[ -z "${THREADS:-}" ]]; then
    echo "THREADS must be set to a positive integer" >&2
    exit 1
fi

if ! [[ "$THREADS" =~ ^[0-9]+$ ]] || ((THREADS < 1)); then
    echo "THREADS must be a positive integer (current: $THREADS)" >&2
    exit 1
fi

# if ((THREADS > 1)); then
#     DBS_RAW="arcadedb"
# fi

IFS=',' read -r -a DBS <<< "$DBS_RAW"
if [[ "${#DBS[@]}" -eq 0 ]]; then
    echo "DBS_RAW cannot be empty" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Benchmark script not found: $PY_SCRIPT" >&2
    exit 1
fi

LADYBUG_VERSION="$(matrix_resolve_version "$LADYBUG_VERSION" "real_ladybug")"
GRAPHQLITE_VERSION="$(matrix_resolve_version "$GRAPHQLITE_VERSION" "graphqlite")"

matrix_prepare_local_arcadedb_wheel "$EXAMPLES_DIR"
if [[ -n "${MATRIX_WHEEL_VERSION:-}" ]]; then
    ARCADEDB_VERSION="$MATRIX_WHEEL_VERSION"
fi

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS dbs=${DBS[*]} dataset=$DATASET seed_start=$SEED_START"
echo "Profile: threads=$THREADS arcadedb-transactions=$ARCADEDB_TRANSACTIONS ladybug-transactions-fraction=$LADYBUG_TRANSACTIONS_FRACTION graphqlite-transactions-fraction=$GRAPHQLITE_TRANSACTIONS_FRACTION mem-limit=$MEM_LIMIT batch-size=$BATCH_SIZE graphqlite-version=$GRAPHQLITE_VERSION"

dataset_slug="${DATASET//-/_}"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for db in "${DBS[@]}"; do
        db="$(echo "$db" | xargs)"
        if [[ -z "$db" ]]; then
            continue
        fi

        db_engine="$db"
        arcadedb_oltp_language=""
        case "$db" in
            arcadedb_sql)
                db_engine="arcadedb"
                arcadedb_oltp_language="sql"
                ;;
            arcadedb_cypher)
                db_engine="arcadedb"
                arcadedb_oltp_language="cypher"
                ;;
            ladybug | ladybugdb)
                db_engine="$db"
                ;;
            graphqlite)
                db_engine="$db"
                ;;
            sqlite_native)
                db_engine="$db"
                ;;
            python_memory)
                db_engine="$db"
                ;;
            *)
                echo "Unsupported DB alias in DBS_RAW: $db" >&2
                echo "Supported values: arcadedb_cypher, arcadedb_sql, ladybug, ladybugdb, graphqlite, sqlite_native, python_memory" >&2
                exit 1
                ;;
        esac

        seed=$((SEED_START + execution_idx))
        run_label=$(printf "%s_t%02d_r%02d_%s_s%05d" "$LABEL_PREFIX" "$THREADS" "$run" "$db" "$seed")

        transactions_for_db=$ARCADEDB_TRANSACTIONS
        if [[ "$db_engine" == "ladybug" || "$db_engine" == "ladybugdb" ]]; then
            transactions_for_db=$(awk -v base="$ARCADEDB_TRANSACTIONS" -v frac="$LADYBUG_TRANSACTIONS_FRACTION" 'BEGIN { print int(base * frac) }')
            if ((transactions_for_db < 1)); then
                transactions_for_db=1
            fi
        elif [[ "$db_engine" == "graphqlite" ]]; then
            transactions_for_db=$(awk -v base="$ARCADEDB_TRANSACTIONS" -v frac="$GRAPHQLITE_TRANSACTIONS_FRACTION" 'BEGIN { print int(base * frac) }')
            if ((transactions_for_db < 1)); then
                transactions_for_db=1
            fi
        fi

        cmd=(
            python3 "$PY_SCRIPT"
            --dataset "$DATASET"
            --db "$db_engine"
            --threads "$THREADS"
            --transactions "$transactions_for_db"
            --batch-size "$BATCH_SIZE"
            --mem-limit "$MEM_LIMIT"
            --jvm-heap-fraction "$JVM_HEAP_FRACTION"
            --arcadedb-version "$ARCADEDB_VERSION"
            --ladybug-version "$LADYBUG_VERSION"
            --graphqlite-version "$GRAPHQLITE_VERSION"
            --docker-image "$DOCKER_IMAGE"
            --seed "$seed"
            --run-label "$run_label"
        )
        if ((THREADS == 1)); then
            cmd+=(--verify-single-thread-series)
        fi
        if [[ "$db_engine" == "arcadedb" ]]; then
            cmd+=(--arcadedb-oltp-language "$arcadedb_oltp_language")
        fi

        echo
        echo "[$((execution_idx + 1))/$((RUNS * ${#DBS[@]}))] db=$db run=$run seed=$seed tx=$transactions_for_db label=$run_label"
        echo "Command: ${cmd[*]}"
        set +e
        "${cmd[@]}"
        cmd_exit=$?
        set -e

        target_dir="my_test_databases/${dataset_slug}_graph_oltp_${db_engine}_${run_label}"
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
    "db_engine": "$db_engine",
    "arcadedb_oltp_language": "$arcadedb_oltp_language",
  "dataset": "$DATASET",
  "threads": $THREADS,
  "transactions": $transactions_for_db,
  "batch_size": $BATCH_SIZE,
  "seed": $seed,
  "run_label": "$run_label",
  "collected_at_utc": "$collected_at"
}
EOF

        wheel_artifacts_for_dir="false"
        if [[ "$db_engine" == "arcadedb" ]]; then
            wheel_artifacts_for_dir="true"
        fi
        matrix_write_wheel_metadata "$target_dir" "$collected_at" "$wheel_artifacts_for_dir"
        matrix_embed_wheel_metadata_in_results "$target_dir" "$collected_at"
        matrix_write_dependency_versions \
            "$target_dir" \
            "$collected_at" \
            "arcadedb_embedded" "$ARCADEDB_VERSION" \
            "real_ladybug" "$LADYBUG_VERSION" \
            "graphqlite" "$GRAPHQLITE_VERSION" \
            "sqlite_native" "builtin" \
            "python_memory" "builtin"

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
