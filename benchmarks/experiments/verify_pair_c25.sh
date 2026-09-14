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
IMG="arcadedb-c25:${SHORT}"
REPO=$HOME/repos/humemai/arcadedb-embedded-python
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
EJ=$("$REPO"/.venv/lib/python3.12/site-packages/arcadedb_embedded/jre/bin/java -version 2>&1 \
      | head -1 | grep -oE '"[0-9]+' | tr -d '"')
[ -n "$IJ" ] && [ -n "$EJ" ] || fail "could not read a JVM version (image='$IJ' embedded='$EJ')"
[ "$IJ" = "$EJ" ] || fail "JVM major differs: image=$IJ embedded=$EJ"

echo "PAIR VERIFIED $SHORT  jars=both  jvm=$IJ  image=$IMG"
