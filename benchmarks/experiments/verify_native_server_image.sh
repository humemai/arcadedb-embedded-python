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
#
# RELEASE-PAIR EQUIVALENCE (26.11.1): upstream's native-image.yml builds the `-native` image at the release tag, one commit after the commit the
# JVM image, the jars and both wheels were built at ("Set release version to 26.11.1": version strings only). Env NATIVE_SERVER_EQUIV_SHAS (space
# or comma separated, 7 to 40 hex characters each; run.sh exports it from the pins) names the commits the server may report INSTEAD of the pin.
# It counts ONLY together with the pin (no sha argument: refused), it never replaces the pin check for another commit, and every use prints
#   NATIVE_SERVER_EQUIV=<got> accepted for pin <pin>: see ENGINE-COMMIT-EQUIV
# so STATUS shows it. The evidence is mini-ab-prep/fourarm-2611/ENGINE-COMMIT-EQUIV-<release>.md and engine_commit_equiv.json (engine_pin.py).
# Without the variable the behaviour is exactly as before.
set -uo pipefail
IMG="${1:?usage: verify_native_server_image.sh <image> [<sha>]}"
SHA="${2:-}"
PW=dbbenchpass
fail() { echo "NATIVE SERVER UNVERIFIED: $*"; exit 1; }
EQUIV="${NATIVE_SERVER_EQUIV_SHAS:-}"
EQUIV="${EQUIV//,/ }"
if [ -n "${EQUIV//[[:space:]]/}" ]; then
  [ -n "$SHA" ] || fail "NATIVE_SERVER_EQUIV_SHAS is set but no pin was given: an equivalent commit is accepted only together with the pin"
  for e in $EQUIV; do
    printf '%s' "$e" | grep -qE '^[0-9a-f]{7,40}$' || fail "NATIVE_SERVER_EQUIV_SHAS entry '$e' is not 7 to 40 lower-case hex characters"
  done
fi
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
  "http://127.0.0.1:$PORT/api/v1/query/bench" | uv run --no-project python -c 'import sys,json; print(json.load(sys.stdin)["result"][0]["v"])') || fail "SELECT version() failed"
GOT=$(printf '%s' "$V" | sed -n 's/.*(build \([0-9a-f]\{7,40\}\)\/.*/\1/p')
[ -n "$GOT" ] || fail "no build sha in '$V'"
echo "NATIVE_SERVER_VERSION=$V"
echo "NATIVE_SERVER_COMMIT=$GOT"
if [ -n "$SHA" ]; then
  case "$SHA" in "$GOT"*) ;; *) case "$GOT" in "${SHA:0:7}"*) ;; *)
    ok=0
    for e in $EQUIV; do
      case "$GOT" in "$e"*) ok=1 ;; *) case "$e" in "$GOT"*) ok=1 ;; esac ;; esac
    done
    [ "$ok" = 1 ] || fail "the native server runs ${GOT:0:9}, expected ${SHA:0:9}${EQUIV:+ (equivalents: $EQUIV)}"
    echo "NATIVE_SERVER_EQUIV=$GOT accepted for pin $SHA: see ENGINE-COMMIT-EQUIV" ;; esac ;; esac
fi
exit 0
