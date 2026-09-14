#!/bin/bash
# Build a MATCHED ArcadeDB pair from upstream's published snapshot.
#
# WHY THIS EXISTS. The served and embedded arms were never the same engine:
#
#     served    Temurin 21.0.11 / Alpine musl / ZGC   (upstream's image)
#     embedded  Corretto 25.0.4 / glibc / G1          (our wheel's bundled JRE)
#
# The deployment axis claims to isolate TRANSPORT. It was also switching JVM
# major, libc and garbage collector. The dense build is ~46% SIMD distance work
# (PanamaVectorUtilSupport.squareDistancePreferred, from the #5577 profile) on
# an INCUBATING Vector API, which is exactly the kind of code whose performance
# moves between JVM majors.
#
# WHAT THIS BUILDS. Both halves from ONE set of jars -- upstream's own published
# snapshot build, taken by digest, never recompiled by us -- run on ONE JVM:
#
#     jars    arcadedata/arcadedb@<digest>  ->  /home/arcadedb/lib  (86 jars)
#     server  FROM amazoncorretto:25        +  those jars
#     wheel   build.sh <plat> <py> <that jar dir>
#
# So server and embedded differ in transport and nothing else.
set -euo pipefail

DIGEST="${1:?usage: build_matched_pair.sh <image-digest> [tag-suffix]}"
SRC="arcadedata/arcadedb@${DIGEST}"
REPO=$HOME/repos/humemai/arcadedb-embedded-python
WORK=$HOME/engine-builds/c25
say() { echo "[$(date -Is)] pair: $*"; }

say "source image $SRC"
docker pull -q "$SRC" >/dev/null

# 1. the commit these jars actually are. Never trust the tag.
TMP=$(mktemp)
docker run --rm --entrypoint sh "$SRC" -c 'cat /home/arcadedb/lib/arcadedb-engine-*.jar' > "$TMP"
SHA=$(python3 - "$TMP" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
props = z.read("com/arcadedb/arcadedb.properties").decode()
print(next(l.split("=",1)[1].strip() for l in props.splitlines()
           if l.strip().startswith("buildNumber")))
PY
)
rm -f "$TMP"
[ ${#SHA} -eq 40 ] || { say "ABORT: could not read buildNumber (got '$SHA')"; exit 1; }
SHORT=${SHA:0:9}
say "jars are upstream commit $SHORT"

# 2. extract the whole assembly, not just lib: bin/server.sh and config are
#    upstream's too, and rebuilding them here would be inventing a deployment.
rm -rf "$WORK"; mkdir -p "$WORK/ctx"
CID=$(docker create "$SRC")
docker cp "$CID:/home/arcadedb" "$WORK/ctx/arcadedb-assembly" >/dev/null
docker rm -f "$CID" >/dev/null
JARS=$(ls "$WORK/ctx/arcadedb-assembly/lib"/*.jar | wc -l)
say "assembly extracted, $JARS jars"
[ "$JARS" -gt 50 ] || { say "ABORT: only $JARS jars"; exit 1; }

# 3. the server image, on the SAME JVM the wheel bundles.
#    Upstream's ENV is kept verbatim, including ARCADEDB_OPTS_GC: runner.py
#    clears it at run time so the arms match, and keeping it here means the
#    image is still a faithful copy of what upstream ships, with the JVM as the
#    single deliberate difference.
cat > "$WORK/ctx/Dockerfile" <<'DOCKER'
FROM amazoncorretto:25
LABEL maintainer="Arcade Data LTD (info@arcadedb.com)"
LABEL org.humemai.note="upstream jars, unmodified, on Corretto 25 for JVM parity with the embedded wheel"
ENV ARCADEDB_OPTS_GC="-XX:+UseZGC -XX:+ZGenerational"
ENV ARCADEDB_OPTS_MEMORY="-XX:MaxRAMPercentage=75"
ENV ARCADEDB_JMX="-Dcom.sun.management.jmxremote=true \
    -Dcom.sun.management.jmxremote.local.only=false \
    -Dcom.sun.management.jmxremote.authenticate=false \
    -Dcom.sun.management.jmxremote.ssl=false \
    -Dcom.sun.management.jmxremote.port=9999 \
    -Dcom.sun.management.jmxremote.rmi.port=9998"
RUN yum -y update && yum -y install shadow-utils && yum clean all && rm -rf /var/cache/yum
RUN useradd -m -d /home/arcadedb -s /bin/sh arcadedb
WORKDIR /home/arcadedb
COPY --chown=arcadedb:arcadedb ./arcadedb-assembly/ ./
RUN chmod +x ./bin/*.sh
USER arcadedb
EXPOSE 2480 2434 8182 5432 6379 27017 50051 9999 9998
CMD ["./bin/server.sh"]
DOCKER

IMG="arcadedb-c25:${SHORT}"
say "docker build $IMG"
docker build -q -t "$IMG" \
  --label "org.opencontainers.image.revision=$SHA" \
  --label "org.humemai.source-image=$SRC" \
  "$WORK/ctx" >/dev/null
say "built $IMG"

# 4. prove the image runs the JVM we asked for, and the jars we gave it.
docker run --rm --entrypoint sh "$IMG" -c 'java -version' 2>&1 | head -2 | sed 's/^/    /'
IMGSHA=$(docker run --rm --entrypoint sh "$IMG" -c 'cat /home/arcadedb/lib/arcadedb-engine-*.jar' \
  | python3 -c "
import sys, zipfile, io
z = zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))
p = z.read('com/arcadedb/arcadedb.properties').decode()
print(next(l.split('=',1)[1].strip() for l in p.splitlines() if l.strip().startswith('buildNumber')))")
[ "$IMGSHA" = "$SHA" ] || { say "ABORT: image jars are $IMGSHA, expected $SHA"; exit 1; }
say "image jars verified at $SHORT"
echo "PAIR_IMAGE=$IMG"
echo "PAIR_SHA=$SHA"
echo "PAIR_JARDIR=$WORK/ctx/arcadedb-assembly/lib"
