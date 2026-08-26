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
#
# MATCH THE VERSION, NOT THE PACKAGE STRING. The first version of this guard
# tested the whole of ARCADE_PKGS for *rc*, and "a-r-c-adedb" contains "rc", so
# it refused the correct 26.8.1 release build and blocked every rebuild. A
# guard that cannot tell 26.8.1 from 26.8.1.dev20 is worse than no guard: it
# gets disabled, and then nothing checks. So isolate the version token and
# test only that. Same for the wheel path, whose basename carries the version.
_pin=""
if [ -n "${ARCADEDB_WHEEL:-}" ]; then
  # arcadedb_embedded-26.8.1.dev20-py3-none-linux_x86_64.whl -> 26.8.1.dev20
  _pin=$(basename "$ARCADEDB_WHEEL" | cut -d- -f2)
else
  _pin=${ARCADE_PKGS#*arcadedb-embedded==}; _pin=${_pin%% *}
fi
case "$_pin" in
  *dev*|*rc[0-9]*|*a[0-9]*|*b[0-9]*|*SNAPSHOT*)
    if [ -z "${BENCH_ALLOW_DEV:-}" ]; then
      echo "REFUSING: ArcadeDB pin '$_pin' is a pre-release." >&2
      echo "A pre-release is publishable ONLY under commit pinning: load_canonical" >&2
      echo "admits a dev build if and only if the row carries engine_commit and it" >&2
      echo "matches the campaign's pinned commit (make_paper_tables._commit_matches)." >&2
      echo "Every LOCAL build reports 26.9.1.dev0 whichever commit produced it, so" >&2
      echo "a commit-pinned campaign necessarily trips this guard." >&2
      echo "" >&2
      echo "So: BENCH_ALLOW_DEV=1 is correct for a commit-pinned campaign whose rows" >&2
      echo "stamp engine_commit, and wrong for anything that does not. It is not a" >&2
      echo "debugging-only hatch any more, which is what this message used to say." >&2
      exit 1
    fi
    # NOT "cannot be published", which is what this line used to say and which
    # flatly contradicted the paragraph above it. DECISIONS #49: the page pins
    # by commit, so a pre-release IS publishable there once the rows stamp
    # engine_commit. The stale wording cost real time on 2026-08-26, when it was
    # read as a blocker on putting a completed, commit-pinned table on the page.
    echo "NOTE: PRE-RELEASE image ($_pin). Publishable on the COMMIT-PINNED page" >&2
    echo "      (DECISIONS #49) once every row stamps engine_commit; NOT publishable" >&2
    echo "      in the paper, which pins to stable releases (DECISIONS #42)." >&2 ;;
esac
echo "arcadedb pin: $_pin"

targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(arcadedb duckdb client dense)
for be in "${targets[@]}"; do
  echo "=== dbbench:$be (${PKGS[$be]})"
  docker build -q -t "dbbench:$be" --build-arg PIP_PACKAGES="${PKGS[$be]}" \
    -f Dockerfile.bench . >/dev/null && echo "  ok"
done
