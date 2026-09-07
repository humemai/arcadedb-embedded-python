#!/usr/bin/env bash
# One-command reproduction of the paper's hybrid workflow (vector -> SQL -> Cypher).
#
#   ./benchmarks/python-bindings/reproduce_hybrid.sh              # paper corpus (stats.stackexchange.com)
#   ./benchmarks/python-bindings/reproduce_hybrid.sh stackoverflow-tiny   # quick check, < 1 min
#
# Downloads the Stack Exchange dump and computes embeddings if they are missing, converts
# the XML to Parquet if that is missing, then runs hybrid_showcase.py over the whole corpus.
#
# Needs only uv. Every step runs in a throwaway uv environment (--no-project) with the
# package versions the paper used, pulled from PyPI, so nothing else from this repository's
# development setup is required. Override the ArcadeDB version with ARCADEDB_VERSION=.
set -euo pipefail
DATASET="${1:-stackoverflow-medium}"
ARCADEDB_VERSION="${ARCADEDB_VERSION:-26.8.1}"
UV="uv run --no-project --python 3.12"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DATA="bindings/python/examples/data/$DATASET"

if [ ! -f "$DATA/vectors/$DATASET-questions.meta.json" ]; then
  echo "== 1/3 download + embed ($DATASET); the embedding step is the slow part"
  $UV --with sentence-transformers --with numpy python bindings/python/examples/download_data.py "$DATASET"
else
  echo "== 1/3 download + embed: already present, skipping"
fi

if [ ! -f "$DATA/prepared/posts.parquet" ]; then
  echo "== 2/3 XML -> Parquet"
  $UV --with pandas --with pyarrow python benchmarks/python-bindings/datasets/prepare.py "$DATASET"
else
  echo "== 2/3 XML -> Parquet: already present, skipping"
fi

echo "== 3/3 hybrid workflow"
$UV --with "arcadedb-embedded==$ARCADEDB_VERSION" --with numpy --with pandas --with pyarrow \
  python benchmarks/python-bindings/hybrid_showcase.py \
  --data-dir "$DATA/prepared" --vectors-dir "$DATA/vectors" --name "$DATASET" --limit 1000000
