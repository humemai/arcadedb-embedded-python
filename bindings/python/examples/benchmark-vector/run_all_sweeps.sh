#!/bin/bash
# Comprehensive parameter sweep for ArcadeDB vector index benchmarking

DATASET="glove-100-angular"

# Create timestamped output directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="sweep_results_${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

# Create symlink to datasets folder to avoid re-downloading
if [ -d "datasets" ]; then
    ln -s "$(pwd)/datasets" "${OUTPUT_DIR}/datasets"
fi

echo "========================================================================"
echo "ArcadeDB Vector Index Parameter Sweep"
echo "========================================================================"
echo "Output directory: ${OUTPUT_DIR}"
echo ""

# Define all sweep configurations: HEAP|LOCATION_CACHE|GRAPH_BUILD_CACHE|DATASET_SIZE
CONFIGS=()

# # ---------------------------------------------------------------------
# # 1. Tiny (1,000 vectors)
# # ---------------------------------------------------------------------
# # Heap: 2g
# # Location cache: underfit (~10%), fit (100%), unlimited
# # Graph build cache: small / medium / full (tiny is cheap anyway)
# DS="tiny"
# H="2g"
# LOCS=("100" "1000" "-1")
# GRAPHS=("200" "500" "1000")
# for L in "${LOCS[@]}"; do for G in "${GRAPHS[@]}"; do CONFIGS+=("$H|$L|$G|$DS"); done; done

# # ---------------------------------------------------------------------
# # 2. Small (10,000 vectors)
# # ---------------------------------------------------------------------
# # Heap: 4g
# # Location cache: underfit (~20%), fit (100%), unlimited
# # Graph build cache: small (~10%), medium (~30%), large (~80%)
# DS="small"
# H="4g"
# LOCS=("2000" "10000" "-1")
# GRAPHS=("1000" "3000" "8000")
# for L in "${LOCS[@]}"; do for G in "${GRAPHS[@]}"; do CONFIGS+=("$H|$L|$G|$DS"); done; done

# # ---------------------------------------------------------------------
# # 3. Medium (100,000 vectors)
# # ---------------------------------------------------------------------
# # Heap: 8g
# # Location cache: underfit (~20%), fit (100%), unlimited
# # Graph build cache: small (~2%), medium (~10%), large (~50%)
# DS="medium"
# H="8g"
# LOCS=("20000" "100000" "-1")
# GRAPHS=("2000" "10000" "50000")
# for L in "${LOCS[@]}"; do for G in "${GRAPHS[@]}"; do CONFIGS+=("$H|$L|$G|$DS"); done; done

# ---------------------------------------------------------------------
# 4. Full (1,000,000 vectors)
# ---------------------------------------------------------------------
# Heap: 16g
# Location cache: underfit (~20%), high-cap (~50%), unlimited
# Graph build cache: small (~0.5%), medium (~5%), large (~20%)
DS="full"
H="4g"
LOCS=("200000" "500000" "-1")
GRAPHS=("5000" "50000" "200000")
for L in "${LOCS[@]}"; do for G in "${GRAPHS[@]}"; do CONFIGS+=("$H|$L|$G|$DS"); done; done

TOTAL=${#CONFIGS[@]}
CURRENT=0
MAX_WORKERS=3

# Optional: Set KEEP_DB=1 to retain DB directories after runs
KEEP_DB_FLAG="--keep-db"

# Function to run a single benchmark
run_benchmark() {
    local CONFIG=$1
    local CURRENT=$2
    local TOTAL=$3

    IFS='|' read -r HEAP LOCATION_CACHE GRAPH_BUILD_CACHE DATASET_SIZE <<< "$CONFIG"

    # Construct comprehensive run name
    RUN_NAME="heap${HEAP}_loc${LOCATION_CACHE}_graph${GRAPH_BUILD_CACHE}_${DATASET_SIZE}"

    echo ""
    echo "========================================================================"
    echo "Starting Run $CURRENT/$TOTAL: $RUN_NAME"
    echo "========================================================================"
    echo "  Heap: $HEAP | Location Cache: $LOCATION_CACHE | Graph Cache: $GRAPH_BUILD_CACHE | Dataset: $DATASET_SIZE"
    echo ""

    # Run benchmark
    cd "${OUTPUT_DIR}"

    START_TIME=$(date +%s)

    ../run_with_memory_monitor.sh "jvector-$RUN_NAME" \
        "python -u ../benchmark_vector_params.py \
    --dataset ${DATASET} \
    --dataset-size ${DATASET_SIZE} \
    --xmx ${HEAP} \
    --xms ${HEAP} \
    --max-direct-memory ${HEAP} \
    --location-cache-size ${LOCATION_CACHE} \
    --graph-build-cache-size ${GRAPH_BUILD_CACHE} \
    ${KEEP_DB_FLAG}"

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    mkdir -p benchmark_logs
    echo "$DURATION" > "benchmark_logs/jvector-${RUN_NAME}_duration.txt"

    cd ..

    echo "Completed Run $CURRENT/$TOTAL: $RUN_NAME (${DURATION}s)"
}

export -f run_benchmark
export OUTPUT_DIR DATASET

# Run benchmarks in parallel with limited workers
for CONFIG in "${CONFIGS[@]}"; do
    CURRENT=$((CURRENT + 1))

    # Wait if we've reached max workers
    while [ $(jobs -r | wc -l) -ge $MAX_WORKERS ]; do
        sleep 1
    done

    # Launch benchmark in background
    run_benchmark "$CONFIG" "$CURRENT" "$TOTAL" &
done

# Wait for all remaining jobs to complete
wait

echo ""

echo ""
echo "========================================================================"
echo "ALL SWEEPS COMPLETE!"
echo "========================================================================"
echo ""
echo "Total runs: $TOTAL"
echo "All results saved in: ${OUTPUT_DIR}/"
echo "  - benchmark_jvector_*.md (Markdown reports)"
echo "  - benchmark_logs/*.log (Execution logs with memory stats)"
echo "  - jvector_* (Database directories)"
echo ""
