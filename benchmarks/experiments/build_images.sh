#!/usr/bin/env bash
# Build the per-backend bench images. ARCADEDB_WHEEL=<path> bakes a local wheel
# into dbbench:arcadedb instead of the PyPI pin.
set -eu
cd "$(dirname "$0")"

# RELEASE, NOT A DEV BUILD. This said 26.8.1.dev20, and mini's image only
# escaped it because it was built through the ARCADEDB_WHEEL override. Anyone
# rebuilding would get a pre-release, and load_canonical._DEV_RE would then
# reject every ArcadeDB row in the campaign: a green build producing rows no
# table can admit. The docker server pin has been 26.8.1 by digest all along,
# so this was also the one place the two deployments disagreed.
ARCADE_PKGS="arcadedb-embedded==26.8.1 numpy pandas pyarrow"
mkdir -p docker-wheels && rm -f docker-wheels/*.whl
if [ -n "${ARCADEDB_WHEEL:-}" ]; then
  cp "$ARCADEDB_WHEEL" docker-wheels/
  ARCADE_PKGS="numpy pandas pyarrow"
  echo "using local wheel: $(basename "$ARCADEDB_WHEEL")"
fi

declare -A PKGS=(
  # EVERY package pinned, and every pin at the current release as of
  # 2026-08-15. Two rules, both learned the hard way:
  #
  # NOTHING UNPINNED. duckdb was bare here while [dense] pinned 1.5.4, so the
  # two images resolved differently on different build days and the SAME PAPER
  # ended up comparing against duckdb 1.5.5 in l1 and 1.5.4 in l3d. An
  # unpinned dependency is a comparator that changes when nobody is looking.
  #
  # NOTHING STALE. Pinning ArcadeDB to a current release while comparators sit
  # months behind is unfair in our favour, and it is the first thing a reviewer
  # checks. qdrant-client, pymilvus, elasticsearch and ladybug were all behind.
  [arcadedb]="$ARCADE_PKGS"
  [duckdb]="duckdb==1.5.5 pandas pyarrow"
  [client]="requests psycopg[binary] pandas pyarrow numpy surrealdb==2.0.0 qdrant-client==1.19.0 pymilvus==3.0.1 elasticsearch==9.5.0 neo4j==6.2.0 ladybug==0.19.1"
  [dense]="chromadb==1.5.9 lancedb==0.37.1 sqlite-vec==0.1.9 duckdb==1.5.5 numpy pandas pyarrow"
)
# A GUARD, not a comment. The dev pin above survived because nothing checked
# it. BENCH_ALLOW_DEV=1 is the deliberate escape hatch for engine debugging.
case "$ARCADE_PKGS" in
  *dev*|*rc*|*SNAPSHOT*)
    if [ -z "${BENCH_ALLOW_DEV:-}" ]; then
      echo "REFUSING: ARCADE_PKGS names a pre-release ($ARCADE_PKGS)." >&2
      echo "Published rows must come from a stable release; the table loader" >&2
      echo "rejects dev builds, so this would produce rows no table admits." >&2
      echo "Set BENCH_ALLOW_DEV=1 if you are debugging rather than publishing." >&2
      exit 1
    fi
    echo "WARNING: building a PRE-RELEASE image; these rows cannot be published" >&2 ;;
esac

targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(arcadedb duckdb client dense)
for be in "${targets[@]}"; do
  echo "=== dbbench:$be (${PKGS[$be]})"
  docker build -q -t "dbbench:$be" --build-arg PIP_PACKAGES="${PKGS[$be]}" \
    -f Dockerfile.bench . >/dev/null && echo "  ok"
done
