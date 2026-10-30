#!/bin/bash
# Verify upstream's native-image ArcadeDB server: its engine commit (SELECT version()) is the pin (#222).
#
# usage: verify_native_server_image.sh <image> [<full-40-char-sha>]
#
# The native server image (arcadedata/arcadedb:<version>-native, built by upstream's native-image.yml from native/pom.xml) is a scratch image:
# no shell, no jars, nothing to `docker exec`. Its commit is therefore read the only way it can be: start it as a server on a loopback port with
# the same settings the benchmark gives it, ask `SELECT version()` over HTTP, stop it. Prints one line, `NATIVE_SERVER_COMMIT=<sha>`, and
# exits non-zero when the sha is given and differs, or when the server does not answer. With no sha it only reports (the smoke uses this:
# it checks plumbing, not the pair).
#
# FOR A DEV-COMMIT PAIR the image must be built at the pair's commit: dispatch upstream's native-image.yml with `ref=<sha>` (and
# `publish_nightly` is NOT needed: build it locally with native/scripts/build-native-docker.sh at that checkout), tag the result
# `arcadedb-native-c25:<first 9 of sha>`, and pass that tag as ARCADEDB_NATIVE_SERVER_IMAGE. For a RELEASE pass it is the published
# `arcadedata/arcadedb:<release>-native` tag, pulled by the pair stage. Nothing here builds an image.
set -uo pipefail
IMG="${1:?usage: verify_native_server_image.sh <image> [<sha>]}"
SHA="${2:-}"
PW=dbbenchpass
fail() { echo "NATIVE SERVER UNVERIFIED: $*"; exit 1; }
command -v docker >/dev/null || fail "no docker"
command -v curl >/dev/null || fail "no curl"
docker image inspect "$IMG" >/dev/null 2>&1 || fail "no image $IMG"
NAME="nsv-$$"
CID=$(docker run -d --rm --name "$NAME" -p 127.0.0.1::2480 "$IMG" -Xmx2g -Darcadedb.server.rootPassword=$PW \
  -Darcadedb.server.defaultDatabases='bench[root]' -Darcadedb.server.mode=development -Darcadedb.server.httpIncomingHost=0.0.0.0 \
  -Darcadedb.server.httpIncomingPort=2480) || fail "docker run"
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT
PORT=$(docker port "$NAME" 2480/tcp | head -1 | sed 's/.*://')
[ -n "$PORT" ] || fail "no mapped port"
up=0
for _ in $(seq 1 90); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/api/v1/ready" && { up=1; break; }
  sleep 1
done
[ "$up" = 1 ] || fail "the server did not answer /api/v1/ready in 90 s"
V=$(curl -sf -u "root:$PW" -H 'Content-Type: application/json' -d '{"language":"sql","command":"SELECT version() AS v"}' \
  "http://127.0.0.1:$PORT/api/v1/query/bench" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"][0]["v"])') || fail "SELECT version() failed"
GOT=$(printf '%s' "$V" | sed -n 's/.*(build \([0-9a-f]\{7,40\}\)\/.*/\1/p')
[ -n "$GOT" ] || fail "no build sha in '$V'"
echo "NATIVE_SERVER_VERSION=$V"
echo "NATIVE_SERVER_COMMIT=$GOT"
if [ -n "$SHA" ]; then
  case "$SHA" in "$GOT"*) ;; *) case "$GOT" in "${SHA:0:7}"*) ;; *) fail "the native server runs ${GOT:0:9}, expected ${SHA:0:9}" ;; esac ;; esac
fi
exit 0
