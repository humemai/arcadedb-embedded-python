#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/09_stackoverflow_graph_oltp.py"

# mark 🚧 for ongoing and ✅ for done
# Ladybug uses a reduced transaction budget for OLTP matrix fairness/stability.
# multi-threading only works well with arcadedb for this OLTP

# Dataset Tier  Transactions  Batch   Memory  CPUs  Running   Note
# Tiny          10,000        1,000   1GB     1     ✅
# Tiny          10,000        1,000   1GB     8     ✅
# Small         50,000        2,500   2GB     1     ✅
# Small         50,000        2,500   2GB     8     ✅
# Medium        100,000       5,000   4GB     1     ✅
# Medium        100,000       5,000   4GB     8     😵        Only 1/3 passed.
# Large         250,000       10,000  8GB     1     🚧
# Large         250,000       10,000  8GB     8     😵        concurrency is tough
# X-Large       1,000,000     25,000  32GB    1
# X-Large       1,000,000     25,000  32GB    8

DATASET="stackoverflow-large"
ARCADEDB_TRANSACTIONS=250000
LADYBUG_TRANSACTIONS_FRACTION=0.1
BATCH_SIZE=10000
MEM_LIMIT="8g"
THREADS=8
RUNS=3
SEED_START=0
JVM_HEAP_FRACTION="0.80"
ARCADEDB_VERSION="26.2.1"
LADYBUG_VERSION="0.14.1"
DOCKER_IMAGE="python:3.12-slim"
DBS_RAW="arcadedb,ladybug"
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

if ((THREADS > 1)); then
    DBS_RAW="arcadedb"
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

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS dbs=${DBS[*]} dataset=$DATASET seed_start=$SEED_START"
echo "Profile: threads=$THREADS arcadedb-transactions=$ARCADEDB_TRANSACTIONS ladybug-transactions-fraction=$LADYBUG_TRANSACTIONS_FRACTION mem-limit=$MEM_LIMIT batch-size=$BATCH_SIZE"

dataset_slug="${DATASET//-/_}"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for db in "${DBS[@]}"; do
        db="$(echo "$db" | xargs)"
        if [[ -z "$db" ]]; then
            continue
        fi

        seed=$((SEED_START + execution_idx))
        run_label=$(printf "%s_t%02d_r%02d_%s_s%05d" "$LABEL_PREFIX" "$THREADS" "$run" "$db" "$seed")

        transactions_for_db=$ARCADEDB_TRANSACTIONS
        if [[ "$db" == "ladybug" ]]; then
            transactions_for_db=$(awk -v base="$ARCADEDB_TRANSACTIONS" -v frac="$LADYBUG_TRANSACTIONS_FRACTION" 'BEGIN { print int(base * frac) }')
            if ((transactions_for_db < 1)); then
                transactions_for_db=1
            fi
        fi

        cmd=(
            python3 "$PY_SCRIPT"
            --dataset "$DATASET"
            --db "$db"
            --threads "$THREADS"
            --transactions "$transactions_for_db"
            --batch-size "$BATCH_SIZE"
            --mem-limit "$MEM_LIMIT"
            --jvm-heap-fraction "$JVM_HEAP_FRACTION"
            --arcadedb-version "$ARCADEDB_VERSION"
            --ladybug-version "$LADYBUG_VERSION"
            --docker-image "$DOCKER_IMAGE"
            --seed "$seed"
            --run-label "$run_label"
        )

        echo
        echo "[$((execution_idx + 1))/$((RUNS * ${#DBS[@]}))] db=$db run=$run seed=$seed tx=$transactions_for_db label=$run_label"
        echo "Command: ${cmd[*]}"
        "${cmd[@]}"

        target_dir="my_test_databases/${dataset_slug}_graph_oltp_${db}_${run_label}"
        if [[ -d "$target_dir" ]]; then
            du_bytes="$(du -sB1 "$target_dir" | awk '{print $1}')"
            du_human="$(du -sh "$target_dir" | awk '{print $1}')"
            collected_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

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
            echo "Warning: target directory not found for du capture: $target_dir"
        fi

        execution_idx=$((execution_idx + 1))
    done
done

echo

echo "Completed all runs."
