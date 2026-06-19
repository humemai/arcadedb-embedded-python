#!/usr/bin/env bash
# Build per-backend Docker images with PINNED versions + the deps each lane needs.
# Usage: ./build_images.sh [backend ...]   (default: all)
set -eu
cd "$(dirname "$0")"

declare -A PKGS=(
  [arcadedb]="arcadedb-embedded==26.6.1 numpy pandas pyarrow"
  [sqlite]="pandas pyarrow"
  [duckdb]="duckdb==1.5.4 pandas pyarrow"
  [kuzu]="kuzu==0.11.3 pandas pyarrow"
  [chroma]="chromadb==1.5.9 numpy"
)

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(arcadedb sqlite duckdb kuzu chroma)

for be in "${targets[@]}"; do
  echo "=== building scipy-bench:$be  (${PKGS[$be]}) ==="
  docker build -q -t "scipy-bench:$be" --build-arg PIP_PACKAGES="${PKGS[$be]}" -f docker/Dockerfile . >/dev/null \
    && echo "  ok" || { echo "  FAILED"; exit 1; }
done
echo "done."
