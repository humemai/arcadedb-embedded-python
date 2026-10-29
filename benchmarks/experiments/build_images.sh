#!/usr/bin/env bash
# Build the per-backend bench images. ARCADEDB_WHEEL=<path> bakes a wheel into the arcadedb image, which is tagged with
# the wheel's version, dbbench:arcadedb-<version>, and never with a floating dbbench:arcadedb (engine_pin.py, 2026-10-22).
set -eu
cd "$(dirname "$0")"

# RELEASE, NOT A DEV BUILD. This said 26.8.1.dev20, and mini's image only
# escaped it because it was built through the ARCADEDB_WHEEL override. Anyone
# rebuilding would get a pre-release, and load_canonical._DEV_RE would then
# reject every ArcadeDB row in the campaign: a green build producing rows no
# table can admit. The docker server pin has been 26.8.1 by digest all along,
# so this was also the one place the two deployments disagreed.
# THE HARNESS'S OWN LIBRARIES, PINNED TOO (2026-10-02). numpy, pandas, pyarrow,
# requests, and psycopg were bare in every line below, so an image rebuilt on a
# different day resolved them differently: dbbench:duckdb carried pandas 3.0.5
# while the other three carried 3.0.6. They convert every vector and every
# result set, so they are part of the instrument. Pinned at what the October
# images on mini and the laptop resolved (2026-09-19); move them deliberately.
HARNESS_PKGS="numpy==2.5.3 pandas==3.0.6 pyarrow==25.0.1"
# NO SILENT PYPI FALLBACK (2026-10-22). The engine under test is always a named wheel: the `arcadedb` image takes it from
# ARCADEDB_WHEEL and nothing else, because the old default here (`arcadedb-embedded==26.8.1` from PyPI) was a stale pin that
# a build with the variable forgotten would have baked in without a word, two ArcadeDB versions on one table (F5). The
# generic images (client, duckdb, dense) take no ArcadeDB package of their own: with the variable set they carry the wheel
# (Dockerfile.bench installs every wheel in docker-wheels/), and without it they carry none, so building only those needs no wheel.
ARCADE_PKGS="$HARNESS_PKGS"
mkdir -p docker-wheels && rm -f docker-wheels/*.whl
if [ -n "${ARCADEDB_WHEEL:-}" ]; then
  [ -f "$ARCADEDB_WHEEL" ] || { echo "REFUSING: ARCADEDB_WHEEL=$ARCADEDB_WHEEL is not a file" >&2; exit 1; }
  # A whole-input insert_many (pre-26.10.2) killed l4/ts1000/arcadedb_ts_doc; no image may carry such a wheel (wheel_guard.py).
  python3 wheel_guard.py "$ARCADEDB_WHEEL" || exit 1
  cp "$ARCADEDB_WHEEL" docker-wheels/
  echo "using local wheel: $(basename "$ARCADEDB_WHEEL")"
fi
_want_arcadedb=1
if [ $# -gt 0 ]; then _want_arcadedb=0; for _t in "$@"; do [ "$_t" = "arcadedb" ] && _want_arcadedb=1; done; fi
if [ "$_want_arcadedb" = 1 ] && [ -z "${ARCADEDB_WHEEL:-}" ]; then
  echo "REFUSING: the arcadedb image needs ARCADEDB_WHEEL=<path to the pinned arcadedb (native) or arcadedb-jvm wheel>; there is no PyPI fallback." >&2
  echo "          Name the targets (e.g. './build_images.sh duckdb client dense') to build the images that take no wheel." >&2
  exit 1
fi

declare -A PKGS=(
  # EVERY package pinned, and every pin at the current release as of
  # 2026-09-19 (the October re-pin survey, DECISIONS #87/#103d). Two rules,
  # both learned the hard way:
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
  # 1.5.6, NOT 2.0.0 (2026-10-23, the bump from 1.5.4): DuckDB 2.0.0 is out and
  # its `vss` build and the `duckpgq` community build both exist for it, but
  # DuckPGQ LOADs on 2.0.0 (build 29ca668a22) without registering any of its
  # syntax: CREATE PROPERTY GRAPH and GRAPH_TABLE ... MATCH both answer
  # "Parser Error: syntax error", with or without `SET enable_legacy_parser`
  # and `allow_parser_override_extension` (laptop, duckdb 2.0.0 from PyPI), so
  # the graph arm cannot be measured on it. 1.5.6 is the newest DuckDB at
  # which every arm can be measured (DECISIONS #103d: latest MEASURABLE, not
  # highest): VSS HNSW and DuckPGQ (build 61f5d082) both work on it. Drop this
  # hold when a DuckPGQ build for 2.x parses; check with
  # `INSTALL duckpgq FROM community; LOAD duckpgq; CREATE PROPERTY GRAPH g
  # VERTEX TABLES (t)` on the new duckdb. One DuckDB version wears the page
  # (#103c's sibling rule, the two-version trap this file guards against
  # below), so documents, time series, dense VSS and the DuckPGQ graph arm
  # all pin here. The client and dense lines carry the OCTOBER RE-PIN of
  # 2026-09-19 (COMPARATORS.md, "The October re-pin").
  [duckdb]="duckdb==1.5.6 $HARNESS_PKGS"
  # ladybug 0.22.0 (2026-10-25), from 0.21.2 (2026-10-02, #129, which had moved off 0.20.4). 0.20.4 crashes the dense
  # arm's mutation phase after a deleted vector key is re-inserted (the process dies at `mutate-insert-start`; re-run
  # untimed on the laptop 2026-10-25, micro, BENCH_DENSE_MUTATE=1: 0.20.4 dies there, 0.22.0 completes it, recall
  # 0.9981 after the deletes and 0.9997 after the re-inserts, 0 deleted hits). 0.21.2 stopped working on 2026-10-25 04:28 UTC:
  # the vendor overwrote the v0.21.0 `vector` extension, the path every 0.21.x client downloads from, with a build
  # of the 0.22 sources, and `LOAD vector` fails with an undefined symbol (LadybugDB/ladybug#1390). The 0.21.x line has
  # no way back to a working extension but the vendor restoring the file; 0.22.0 is the newest stable and its
  # extension loads. The extension is baked into the client image below, pinned by sha256 (LADYBUG_EXTENSIONS).
  [client]="requests==2.34.2 psycopg[binary]==3.3.6 $HARNESS_PKGS surrealdb==2.0.0 qdrant-client==1.20.0 pymilvus[bulk_writer]==3.0.2 minio==7.2.20 azure-storage-blob==12.31.0 ml-dtypes==0.6.0 elasticsearch==9.5.1 neo4j==6.4.1 ladybug==0.22.0 pymongo==4.18.1 python-arango==8.3.6 falkordb==1.7.1 redis==8.1.0 neo4j-rust-ext==6.4.1.0 pgvector==0.5.1 arcadedb-driver==0.2.0"
  # ladybug==0.22.0 is the SAME pin as the client line above, here for the composed embedded cross-model arm
  # (composed_embedded_sqlite_lance_ladybug, 2026-10-25): SQLite + LanceDB + LadybugDB must import in ONE process, and
  # lancedb lives in this image. No new version: the dense lane's arms import none of it.
  [dense]="chromadb==1.5.9 lancedb==0.39.0 sqlite-vec==0.1.9 duckdb==1.5.6 ladybug==0.22.0 $HARNESS_PKGS"
)
# RUNTIME EXTENSIONS ARE PINNED BY SHA256 AND INSTALLED AT IMAGE BUILD TIME (2026-10-25). The client image's LadybugDB arms
# (ladybug_e2, ladybug_dense, ladybug_lifecycle) used to run `INSTALL vector` in every cell, which downloads the binary from
# extension.ladybugdb.com at run time. On 2026-10-25 04:28 UTC the vendor overwrote the file that every 0.21.x client reads and a
# pinned engine stopped loading (LadybugDB/ladybug#1390). `INSTALL` is a no-op when the file is already in ~/.lbdb (measured:
# same sha256 and mtime after a second INSTALL, also with --network none), so baking the binary here pins it for every cell with no
# change to any lane. The build FAILS when the downloaded file's sha256 is not the one below or when `LOAD` rejects it, so a vendor
# overwrite stops the build instead of changing the engine under a pinned pass. Format: `name=sha256` for linux_amd64 (the images
# are amd64-only); bake_ladybug_extensions.py does the work. Moving the ladybug pin means re-reading this sha:
#   docker run --rm dbbench:client python -c "import ladybug,glob,hashlib; c=ladybug.Connection(ladybug.Database(':memory:')); c.execute('INSTALL vector'); print(hashlib.sha256(open(glob.glob('/root/.lbdb/extension/*/linux_amd64/vector/libvector.lbug_extension')[0],'rb').read()).hexdigest())"
# v0.22.0/linux_amd64/vector/libvector.lbug_extension, Last-Modified Sun, 25 Oct 2026 04:29:24 GMT, 1164248 bytes.
LADYBUG_EXTENSIONS="vector=23da57e805fed208f1eacb4b011cb0c2e917ae098fa6853763e44221211e71b0"
# DuckDB's `INSTALL vss` and `INSTALL duckpgq FROM community` still run in the cell (it records the extension version on the
# row); baking them the same way is the open follow-up in COMPARATORS.md, "Runtime extensions".
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
  # arcadedb-26.11.1.dev0-py3-none-manylinux_2_28_x86_64.whl, arcadedb_jvm-26.11.1.dev0-... and the older
  # arcadedb_embedded-26.8.1.dev20-py3-none-linux_x86_64.whl all carry the version in the second field -> 26.8.1.dev20
  _pin=$(basename "$ARCADEDB_WHEEL" | cut -d- -f2)
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
# NO FLOATING ENGINE TAG (2026-10-22, engine_pin.py). dbbench:arcadedb pointed at whichever wheel was built last, and on the laptop it still
# pointed at 26.10.1 after October was retired. The image that carries ArcadeDB is named for the version it carries, and runner.py refuses
# any other tag for it.
ARCADEDB_TAG=""
if [ -n "$_pin" ]; then
  case "$_pin" in
    [0-9]*.[0-9]*.[0-9]*) ARCADEDB_TAG="dbbench:arcadedb-$_pin" ;;
    *) echo "REFUSING: the wheel name '$(basename "$ARCADEDB_WHEEL")' carries no x.y.z version, so the arcadedb image cannot be tagged" >&2; exit 1 ;;
  esac
fi

# JPYPE IS PART OF THE INSTRUMENT, SO IT IS PINNED TOO (CAMPAIGN 7 row 73). The
# wheel declares jpype1>=1.5.0 with no upper bound, and an image built on the day
# of a new JPype release would resolve the new one and change every embedded
# ArcadeDB call's cost in the middle of a run. The version is read from
# Dockerfile.bench's ARG default (bench_common.JPYPE_PIN is checked against it by
# make_2611_stages.py --check) and passed down explicitly, so a JPYPE_VERSION left
# in the caller's environment cannot move it.
JPYPE_VERSION=$(sed -n 's/^ARG JPYPE_VERSION=//p' Dockerfile.bench)
case "$JPYPE_VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "REFUSING: Dockerfile.bench has no usable 'ARG JPYPE_VERSION=<x.y.z>' default (read '$JPYPE_VERSION')" >&2; exit 1 ;;
esac
echo "jpype pin: $JPYPE_VERSION"

targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(arcadedb duckdb client dense pg-age mongo-search composed)
for be in "${targets[@]}"; do
  if [ "$be" = "composed" ]; then
    # Neo4j + Qdrant in one container (Dockerfile.composed), the composed
    # cross-model stack's server (BUGS F133, DECISIONS #117). Both halves
    # pinned by digest inside the Dockerfile.
    echo "=== dbbench:composed (Dockerfile.composed)"
    docker build -q -t dbbench:composed -f Dockerfile.composed . >/dev/null && echo "  ok"
    continue
  fi
  if [ "$be" = "mongo-search" ]; then
    # MongoDB Community 9.0.4 + mongot (MongoDB Search Community) 1.70.5 in
    # one container (Dockerfile.mongosearch), the dense and cross-model arms'
    # server. Both halves pinned by digest inside the Dockerfile, so a local
    # build has the same provenance a pulled image would.
    echo "=== dbbench:mongo-search (Dockerfile.mongosearch)"
    docker build -q -t dbbench:mongo-search -f Dockerfile.mongosearch . >/dev/null && echo "  ok"
    continue
  fi
  if [ "$be" = "pg-age" ]; then
    # PostgreSQL 17 + pgvector + Apache AGE, a server image (Dockerfile.pgage),
    # the cross-model lane's "one engine" rival (2026-09-11).
    echo "=== dbbench:pg-age (Dockerfile.pgage)"
    docker build -q -t dbbench:pg-age -f Dockerfile.pgage . >/dev/null && echo "  ok"
    continue
  fi
  # AN UNKNOWN TARGET IS AN ABORT, NOT AN EMPTY IMAGE. ${PKGS[$be]} expands
  # to nothing for a name that is not a key here, so the build below used to
  # succeed, tag dbbench:<typo> with no packages in it, and print "ok". A
  # caller deriving target names from runner.BACKENDS deserves to be told
  # when a name does not exist rather than handed a hollow image.
  [ -n "${PKGS[$be]+set}" ] || { echo "  unknown target '$be' (not a PKGS key and not a special case)" >&2; exit 1; }
  _tag="dbbench:$be"
  [ "$be" = "arcadedb" ] && _tag="$ARCADEDB_TAG"
  echo "=== $_tag (${PKGS[$be]})"
  _ext=""; [ "$be" = "client" ] && _ext="$LADYBUG_EXTENSIONS"
  docker build -q -t "$_tag" --build-arg PIP_PACKAGES="${PKGS[$be]}" \
    --build-arg JPYPE_VERSION="$JPYPE_VERSION" \
    --build-arg LADYBUG_EXTENSIONS="$_ext" \
    -f Dockerfile.bench . >/dev/null && echo "  ok"
done
