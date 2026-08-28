#!/usr/bin/env bash
# Build per-backend Docker images with PINNED versions + the deps each lane needs.
# Usage: ./build_images.sh [backend ...]   (default: all)
set -eu
cd "$(dirname "$0")"

# ARCADEDB_WHEEL=/path/to/arcadedb_embedded-*.whl uses that local wheel for the
# arcadedb image instead of the PyPI release (pin exact PyPI version otherwise).
declare -A PKGS=(
  [arcadedb]="arcadedb-embedded==26.8.1 numpy pandas pyarrow"
  [sqlite]="pandas pyarrow"
  [duckdb]="duckdb==1.5.4 pandas pyarrow"
  [ladybug]="ladybug==0.18.1 pandas pyarrow"
  [chroma]="chromadb==1.5.9 numpy"
)

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(arcadedb sqlite duckdb ladybug chroma)

rm -f docker/wheels/*.whl
if [ -n "${ARCADEDB_WHEEL:-}" ]; then
  cp "$ARCADEDB_WHEEL" docker/wheels/
  PKGS[arcadedb]="numpy pandas pyarrow"
  echo "using local wheel: $(basename "$ARCADEDB_WHEEL")"
fi

for be in "${targets[@]}"; do
  echo "=== building scipy-bench:$be  (${PKGS[$be]}) ==="
  docker build -q -t "scipy-bench:$be" --build-arg PIP_PACKAGES="${PKGS[$be]}" -f docker/Dockerfile . >/dev/null \
    && echo "  ok" || { echo "  FAILED"; exit 1; }
done
echo "done."
