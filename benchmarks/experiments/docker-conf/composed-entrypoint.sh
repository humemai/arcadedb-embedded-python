#!/bin/bash
# The composed cross-model stack's server: Qdrant (the pinned server's own
# binary, as the dense lane runs it) beside Neo4j, in ONE container, so the
# runner's single server cgroup caps, pins and measures both halves the way it
# does every other engine (BUGS F133, DECISIONS #117; the same arrangement as
# Dockerfile.mongosearch). Qdrant starts first and must answer its readiness
# probe before Neo4j starts, so the runner's Neo4j readiness line ("Started.")
# cannot appear while the vector half is still coming up.
set -u
cd /qdrant
./qdrant &
QDRANT_PID=$!
for _ in $(seq 1 240); do
  if wget -qO- http://127.0.0.1:6333/readyz >/dev/null 2>&1; then
    echo "DBBENCH qdrant ready (pid $QDRANT_PID)"
    break
  fi
  if ! kill -0 "$QDRANT_PID" 2>/dev/null; then
    echo "DBBENCH qdrant exited before it was ready" >&2
    exit 1
  fi
  sleep 0.5
done
wget -qO- http://127.0.0.1:6333/readyz >/dev/null 2>&1 || { echo "DBBENCH qdrant not ready after 120 s" >&2; exit 1; }
# Neo4j's own entrypoint, exactly as its image runs it (tini -g, docker-entrypoint.sh neo4j).
exec tini -g -- /startup/docker-entrypoint.sh "$@"
