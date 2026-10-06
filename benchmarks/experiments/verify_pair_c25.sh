#!/bin/bash
# Verify the matched ArcadeDB pair: same jars, same JVM, on both arms.
#
# Replaces `build_engine_pair.sh --verify` for the upstream-jars pair. That
# script verifies a pair WE compiled; this one verifies a pair we assembled from
# upstream's published image, which is a different claim:
#
#   wheel jars buildNumber == image jars buildNumber == the SHA asked for
#   wheel JVM major        == image JVM major
#
# The second line is the one that did not exist before, and its absence is why
# the served arm ran Temurin 21 / musl / ZGC against the embedded arm's
# Corretto 25 / glibc / G1 for every server row ever published.
set -uo pipefail
SHA="${1:?usage: verify_pair_c25.sh <full-40-char-sha>}"
SHORT=${SHA:0:9}
# PAIR_IMAGE names the server image when it is not the c25 build of this commit
# (the 26.10.1 stages pass the release pair they were generated for).
IMG="${PAIR_IMAGE:-arcadedb-c25:${SHORT}}"
# THE CHECKOUT THIS SCRIPT LIVES IN, not a fixed path. It was $HOME/repos/humemai/arcadedb-embedded-python,
# the main checkout, so run from a worktree it built from, wrote into, and verified against main's
# bindings/python/dist and .venv: the pair it reported was another tree's. BENCH_PRINT_REPO=1 prints the
# tree and exits (test_pair_scripts.py holds this).
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
[ -z "${BENCH_PRINT_REPO:-}" ] || { echo "REPO=$REPO"; exit 0; }
EMBEDDED_IMAGE="${EMBEDDED_IMAGE:-dbbench:arcadedb}"   # the image the embedded arm runs (the runner names dbbench:arcadedb)
fail() { echo "PAIR UNVERIFIED: $*"; exit 1; }

command -v docker >/dev/null || fail "no docker"
docker image inspect "$IMG" >/dev/null 2>&1 || fail "no image $IMG"

W=$(ls -t "$REPO"/bindings/python/dist/*.whl 2>/dev/null | head -1)
[ -n "$W" ] || fail "no wheel in bindings/python/dist"

# 1. the image's jars
ISHA=$(docker run --rm --entrypoint sh "$IMG" -c 'cat /home/arcadedb/lib/arcadedb-engine-*.jar' \
  | python3 -c "
import sys, zipfile, io
z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))
p=z.read('com/arcadedb/arcadedb.properties').decode()
print(next(l.split('=',1)[1].strip() for l in p.splitlines() if l.strip().startswith('buildNumber')))" 2>/dev/null)
[ "$ISHA" = "$SHA" ] || fail "image jars are ${ISHA:0:9}, expected $SHORT"

# 2. the wheel's jars
WSHA=$(python3 -c "
import sys, zipfile, io
z=zipfile.ZipFile('$W')
n=next(x for x in z.namelist() if '/jars/arcadedb-engine-' in x and x.endswith('.jar'))
e=zipfile.ZipFile(io.BytesIO(z.read(n)))
p=e.read('com/arcadedb/arcadedb.properties').decode()
print(next(l.split('=',1)[1].strip() for l in p.splitlines() if l.strip().startswith('buildNumber')))" 2>/dev/null)
[ "$WSHA" = "$SHA" ] || fail "wheel jars are ${WSHA:0:9}, expected $SHORT"

# 3. THE JVMs. Same major on both sides or the deployment axis is not transport.
IJ=$(docker run --rm --entrypoint sh "$IMG" -c 'java -version 2>&1' | head -1 | grep -oE '"[0-9]+' | tr -d '"')
# The venv's JRE when this checkout has one (the bench host does); otherwise the JRE inside the
# embedded image, which is the JVM the embedded arm actually runs (a worktree has no .venv).
VENV_JAVA="$REPO/.venv/lib/python3.12/site-packages/arcadedb_embedded/jre/bin/java"
if [ -x "$VENV_JAVA" ]; then
  EJ=$("$VENV_JAVA" -version 2>&1 | head -1 | grep -oE '"[0-9]+' | tr -d '"')
else
  EJ=$(docker run --rm --entrypoint python3 "$EMBEDDED_IMAGE" -c "
import importlib.metadata as m, pathlib, subprocess
d = pathlib.Path(m.distribution('arcadedb-embedded').locate_file('arcadedb_embedded'))
print(subprocess.run([str(d / 'jre' / 'bin' / 'java'), '-version'], capture_output=True, text=True).stderr.splitlines()[0])" \
        2>/dev/null | grep -oE '"[0-9]+' | tr -d '"')
fi
[ -n "$IJ" ] && [ -n "$EJ" ] || fail "could not read a JVM version (image='$IJ' embedded='$EJ')"
[ "$IJ" = "$EJ" ] || fail "JVM major differs: image=$IJ embedded=$EJ"

# 4. THE WHEEL THE EMBEDDED ARM ACTUALLY RUNS, which is baked into
# dbbench:arcadedb at build time and is NOT the wheel file checked above.
# Checks 2 and 3 pass while the embedded arm runs a different engine: on
# 2026-09-19 dbbench:arcadedb carried arcadedb-embedded 26.8.1 from PyPI
# (build_images.sh's fallback when ARCADEDB_WHEEL is unset) while every
# served arm ran 26.9.1-SNAPSHOT, and the whole l4 table compared two
# ArcadeDB versions with this script reporting PAIR VERIFIED. A wheel FILE on
# disk is not the engine a cell ran; the image is.
if docker image inspect "$EMBEDDED_IMAGE" >/dev/null 2>&1; then
  BSHA=$(docker run --rm --entrypoint python3 "$EMBEDDED_IMAGE" -c "
import importlib.metadata as m, pathlib, zipfile, io, sys
d = pathlib.Path(m.distribution('arcadedb-embedded').locate_file('arcadedb_embedded'))
j = next(x for x in (d / 'jars').glob('arcadedb-engine-*.jar'))
z = zipfile.ZipFile(j)
p = z.read('com/arcadedb/arcadedb.properties').decode()
print(next(l.split('=',1)[1].strip() for l in p.splitlines() if l.strip().startswith('buildNumber')))" 2>/dev/null)
  [ "$BSHA" = "$SHA" ] || fail "$EMBEDDED_IMAGE bakes jars ${BSHA:0:9}, expected $SHORT (rebuild it with ARCADEDB_WHEEL set)"
else
  fail "no $EMBEDDED_IMAGE image; the embedded arm has nothing to run"
fi

echo "PAIR VERIFIED $SHORT  jars=image+wheel+embedded-image  jvm=$IJ  image=$IMG  embedded=$EMBEDDED_IMAGE  repo=$REPO  wheel=$W"
