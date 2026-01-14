#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 <dataset_dir> <parallel_jobs> [threads_per_task]" >&2
    echo "  dataset_dir: datasets/MSMARCO-1M | datasets/MSMARCO-10M | datasets/MSMARCO-100M" >&2
    echo "  parallel_jobs: number of concurrent runs" >&2
    echo "  threads_per_task (optional): sets OMP/MKL/OPENBLAS/VECLIB/BLIS/NUMEXPR" >&2
    exit 1
fi

DATASET_DIR="$1"
PARALLEL_JOBS="$2"
THREADS_PER_TASK="${3:-}"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BENCH_PY="$SCRIPT_DIR/benchmark_faiss_msmarco.py"

if [[ ! -f "$BENCH_PY" ]]; then
    echo "benchmark_faiss_msmarco.py not found at $BENCH_PY" >&2
    exit 1
fi

THREAD_ENV=""
if [[ -n "$THREADS_PER_TASK" ]]; then
    THREAD_ENV="OMP_NUM_THREADS=${THREADS_PER_TASK} MKL_NUM_THREADS=${THREADS_PER_TASK} OPENBLAS_NUM_THREADS=${THREADS_PER_TASK} VECLIB_MAXIMUM_THREADS=${THREADS_PER_TASK} BLIS_NUM_THREADS=${THREADS_PER_TASK} NUMEXPR_NUM_THREADS=${THREADS_PER_TASK}"
fi

BASE="${THREAD_ENV} python \"${BENCH_PY}\" --dataset-dir \"${DATASET_DIR}\""
cmds=()

# Flat baseline (IP only)
cmds+=("${BASE} --index flat")

# HNSW grid (IP) - representative
for M in 16 32; do
    for EFC in 100 200; do
        for EFS in 64 128; do
            cmds+=("${BASE} --index hnsw --hnsw-m ${M} --hnsw-efc ${EFC} --hnsw-efs ${EFS}")
        done
    done
done

# IVF-Flat grid (IP) (representative)
for NLIST in 512 1024; do
    for NPROBE in 16 32 64; do
        cmds+=("${BASE} --index ivf_flat --nlist ${NLIST} --nprobe ${NPROBE}")
    done
done

# IVF-PQ grid (IP) -- representative; pq_m divides dim (MSMARCO dim=1024)
for NLIST in 512 1024; do
    for NPROBE in 16 32 64; do
        for M in 16 32; do
            cmds+=("${BASE} --index ivf_pq --nlist ${NLIST} --nprobe ${NPROBE} --pq-m ${M} --pq-nbits 8")
        done
    done
done

# HNSW-PQ grid (IP) - representative
for M in 16 32; do
    for EFC in 100 200; do
        for EFS in 64 128; do
            for PQM in 16; do
                cmds+=("${BASE} --index hnsw_pq --hnsw-m ${M} --hnsw-efc ${EFC} --hnsw-efs ${EFS} --pq-m ${PQM} --pq-nbits 8")
            done
        done
    done
done

echo "Planned runs: ${#cmds[@]}" >&2

# Shuffle to spread load/memory footprint across types
if command -v shuf > /dev/null 2>&1; then
    cmd_stream=$(printf '%s\n' "${cmds[@]}" | shuf)
else
    # fallback without shuf
    cmd_stream=$(printf '%s\n' "${cmds[@]}")
fi

printf '%s\n' "${cmd_stream}" | xargs -I{} -P "${PARALLEL_JOBS}" bash -lc '
  echo ">>> RUN: $1" >&2
  eval "$1"
' _ {}
