#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_SCRIPT="$EXAMPLES_DIR/10_stackoverflow_graph_olap.py"
HELPERS_SH="$SCRIPT_DIR/_matrix_helpers.sh"

source "$HELPERS_SH"

# mark 🚧 for ongoing and ✅ for done
# Dataset Tier  Batch       Memory  CPUs  Running   Note
# Tiny          1,000       1GB     2
# Small         2,500       2GB     4
# Medium        5,000       4GB     8
# Large         10,000      8GB     16
# X-Large       25,000      32GB    32

DATASET="stackoverflow-large"
BATCH_SIZE=10000
MEM_LIMIT="32g"
THREADS=4
RUNS=3
SEED_START=0
JVM_HEAP_FRACTION="0.80"
SQLITE_PROFILE="olap"
DOCKER_IMAGE="python:3.12-slim"
QUERY_RUNS=100
QUERY_ORDER="shuffled"
ONLY_QUERY=""
MANUAL_CHECKS=false
DBS_RAW="arcadedb_cypher,python_memory,ladybug,neo4j"
GAV_MODES_RAW="off,on"
LABEL_PREFIX="sweep10"

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

IFS=',' read -r -a GAV_MODES <<< "$GAV_MODES_RAW"
if [[ "${#GAV_MODES[@]}" -eq 0 ]]; then
    echo "GAV_MODES_RAW cannot be empty" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Benchmark script not found: $PY_SCRIPT" >&2
    exit 1
fi

matrix_prepare_local_arcadedb_wheel "$EXAMPLES_DIR"

if [[ "$QUERY_ORDER" != "fixed" && "$QUERY_ORDER" != "shuffled" ]]; then
    echo "QUERY_ORDER must be either 'fixed' or 'shuffled'" >&2
    exit 1
fi

if [[ "$QUERY_RUNS" -lt 1 ]]; then
    echo "QUERY_RUNS must be >= 1" >&2
    exit 1
fi

cd "$EXAMPLES_DIR"

echo "Running matrix: runs=$RUNS dbs=${DBS[*]} dataset=$DATASET seed_start=$SEED_START gav_modes=${GAV_MODES[*]}"
echo "Profile: threads=$THREADS mem-limit=$MEM_LIMIT batch-size=$BATCH_SIZE query-runs=$QUERY_RUNS query-order=$QUERY_ORDER sqlite-profile=$SQLITE_PROFILE"

dataset_slug="${DATASET//-/_}"
mem_tag="$(matrix_normalize_mem_tag "$MEM_LIMIT")"

execution_idx=0
for ((run = 1; run <= RUNS; run++)); do
    for db in "${DBS[@]}"; do
        db="$(echo "$db" | xargs)"
        if [[ -z "$db" ]]; then
            continue
        fi

        db_engine="$db"
        case "$db" in
            arcadedb_sql | arcadedb_cypher | neo4j | ladybug | ladybugdb | duckdb | sqlite | graphqlite | python_memory)
                db_engine="$db"
                ;;
            *)
                echo "Unsupported DB alias in DBS_RAW: $db" >&2
                echo "Supported values: arcadedb_sql, arcadedb_cypher, neo4j, ladybug, ladybugdb, duckdb, sqlite, graphqlite, python_memory" >&2
                exit 1
                ;;
        esac

        for gav_mode in "${GAV_MODES[@]}"; do
            gav_mode="$(echo "$gav_mode" | xargs | tr '[:upper:]' '[:lower:]')"
            case "$gav_mode" in
                on | off) ;;
                *)
                    echo "Unsupported GAV mode in GAV_MODES_RAW: $gav_mode" >&2
                    echo "Supported values: on, off" >&2
                    exit 1
                    ;;
            esac

            effective_gav_mode="$gav_mode"
            if [[ "$db_engine" != arcadedb_* ]]; then
                effective_gav_mode=""
                if ((${#GAV_MODES[@]} > 1)) && [[ "$gav_mode" != "${GAV_MODES[0]}" ]]; then
                    continue
                fi
            fi

            seed=$((SEED_START + execution_idx))
            if [[ -n "$effective_gav_mode" ]]; then
                internal_run_label=$(printf "%s_t%02d_r%02d_%s_gav%s_s%05d" "$LABEL_PREFIX" "$THREADS" "$run" "$db" "$effective_gav_mode" "$seed")
            else
                internal_run_label=$(printf "%s_t%02d_r%02d_%s_s%05d" "$LABEL_PREFIX" "$THREADS" "$run" "$db" "$seed")
            fi
            run_label="$(matrix_build_summary_run_label "$internal_run_label" "$MEM_LIMIT")"

            cmd=(
                python3 "$PY_SCRIPT"
                --dataset "$DATASET"
                --db "$db_engine"
                --threads "$THREADS"
                --batch-size "$BATCH_SIZE"
                --mem-limit "$MEM_LIMIT"
                --jvm-heap-fraction "$JVM_HEAP_FRACTION"
                --sqlite-profile "$SQLITE_PROFILE"
                --docker-image "$DOCKER_IMAGE"
                --query-runs "$QUERY_RUNS"
                --query-order "$QUERY_ORDER"
                --seed "$seed"
                --run-label "$run_label"
            )

            if [[ "$db_engine" == arcadedb_* && "$effective_gav_mode" == "on" ]]; then
                cmd+=(--use-gav)
            fi

            if [[ -n "$ONLY_QUERY" ]]; then
                cmd+=(--only-query "$ONLY_QUERY")
            fi

            if [[ "$MANUAL_CHECKS" == true ]]; then
                cmd+=(--manual-checks)
            fi

            echo
            echo "[$((execution_idx + 1))/$((RUNS * ${#DBS[@]} * ${#GAV_MODES[@]}))] db=$db gav=${effective_gav_mode:-} run=$run seed=$seed label=$run_label"
            echo "Command: ${cmd[*]}"
            "${cmd[@]}"

            target_dir="my_test_databases/${dataset_slug}_graph_olap_${db_engine}_${mem_tag}_${run_label}"
            if [[ -d "$target_dir" ]]; then
                collected_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
                matrix_rename_result_artifacts "$target_dir" "$internal_run_label" "$run_label"
                matrix_rewrite_json_run_label "$target_dir" "$internal_run_label" "$run_label"
                wheel_artifacts_for_dir="false"
                if [[ "$db_engine" == "arcadedb_sql" || "$db_engine" == "arcadedb_cypher" ]]; then
                    wheel_artifacts_for_dir="true"
                fi
                matrix_write_wheel_metadata "$target_dir" "$collected_at" "$wheel_artifacts_for_dir"
                matrix_embed_wheel_metadata_in_results "$target_dir" "$collected_at"
                matrix_write_dependency_versions \
                    "$target_dir" \
                    "$collected_at" \
                    "arcadedb_embedded" "auto" \
                    "real_ladybug" "auto" \
                    "neo4j" "auto" \
                    "graphqlite" "auto" \
                    "duckdb" "auto" \
                    "sqlite" "builtin" \
                    "python_memory" "builtin"

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
                echo "Warning: target directory not found for du capture: $target_dir"
            fi

            execution_idx=$((execution_idx + 1))
        done
    done
done

echo
echo "Completed all runs."
