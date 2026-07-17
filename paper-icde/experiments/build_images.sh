#!/usr/bin/env bash
# Build the per-backend bench images. ARCADEDB_WHEEL=<path> bakes a local wheel
# into icde-bench:arcadedb instead of the PyPI pin.
set -eu
cd "$(dirname "$0")"

ARCADE_PKGS="arcadedb-embedded==26.8.1.dev2 numpy pandas pyarrow"
mkdir -p docker-wheels && rm -f docker-wheels/*.whl
if [ -n "${ARCADEDB_WHEEL:-}" ]; then
  cp "$ARCADEDB_WHEEL" docker-wheels/
  ARCADE_PKGS="numpy pandas pyarrow"
  echo "using local wheel: $(basename "$ARCADEDB_WHEEL")"
fi

declare -A PKGS=(
  [arcadedb]="$ARCADE_PKGS"
  [duckdb]="duckdb pandas pyarrow"
  [client]="requests psycopg[binary] pandas pyarrow numpy qdrant-client==1.18.0 pymilvus==3.0.0 elasticsearch==9.4.1 neo4j==6.2.0 ladybug==0.18.1"
  [dense]="chromadb==1.5.9 lancedb==0.34.0 sqlite-vec==0.1.9 duckdb==1.5.4 numpy pandas pyarrow"
)
targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(arcadedb duckdb client dense)
for be in "${targets[@]}"; do
  echo "=== icde-bench:$be (${PKGS[$be]})"
  docker build -q -t "icde-bench:$be" --build-arg PIP_PACKAGES="${PKGS[$be]}" \
    -f Dockerfile.bench . >/dev/null && echo "  ok"
done
