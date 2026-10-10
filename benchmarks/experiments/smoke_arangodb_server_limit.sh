#!/bin/bash
# PENDING SMOKE TEST for DECISIONS #179: does the real ArangoDB 3.12.12 server kill a long analytics query at AQL maxRuntime,
# with error 1500, in about the time asked, and does the harness adapter turn that into graph_common.QueryKilled?
#
# Not run when written (the laptop was in a timed sweep). Run it on a quiet machine, never on mini:
#   bash smoke_arangodb_server_limit.sh            # a few minutes, one docker container on port 18529
# The container is pinned to SMOKE_CORES (default 14-15) with 4g of memory and the client runs under nice -n 19, so it can sit
# beside a timed sweep as long as the sweep does not use those cores.
#
# It checks (1) a fast query with a limit set is untouched; (2) with max_runtime=LIMIT the server answers error 1500 to a
# triangle count over a dense random graph, a call that would otherwise run far past the limit (if it finishes inside the
# limit the test says to enlarge the graph); (3) ArangoGraph.run_olap raises graph_common.QueryKilled for it, and the kill
# latency (seconds past the limit) is printed.
# Prints "SMOKE OK <kill latency>" or exits non-zero with the reason. The container is removed on exit.
set -u
cd "$(dirname "$0")" || exit 1
PORT=${SMOKE_PORT:-18529}
CORES=${SMOKE_CORES:-14-15}
MEM=${SMOKE_MEM:-4g}
LIMIT=${SMOKE_LIMIT_S:-5}
SLACK=${SMOKE_SLACK_S:-10}
IMG=$(python3 - <<'PY'
import re
print(re.search(r'"arangodb_graph": \{.*?"server_image": "([^"]+)"', open("runner.py").read(), re.S).group(1))
PY
)
NAME=smoke-arango-maxruntime-$$
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT
docker run -d --name "$NAME" --cpuset-cpus "$CORES" --memory "$MEM" -p "$PORT:8529" -e ARANGO_ROOT_PASSWORD=dbbenchpass "$IMG" arangod >/dev/null || { echo "SMOKE FAIL: docker run"; exit 1; }
for _ in $(seq 1 120); do docker logs "$NAME" 2>&1 | grep -q "is ready for business" && break; sleep 1; done
docker logs "$NAME" 2>&1 | grep -q "is ready for business" || { echo "SMOKE FAIL: server not ready"; exit 1; }
EXP=$PWD BENCH_SERVER_HOST=localhost BENCH_SERVER_PORT=$PORT LIMIT=$LIMIT SLACK=$SLACK \
  nice -n 19 taskset -c "$CORES" uv run --directory ../.. --with python-arango==8.3.5 python -I - <<'PY' || exit 1
import os, random, sys, time
sys.path.insert(0, os.environ["EXP"])
import graph_common as G
import l2_graph as L

LIMIT, SLACK = float(os.environ["LIMIT"]), float(os.environ["SLACK"])
ad = L.ArangoGraph()
ad.connect()
rnd = random.Random(1)
N, E = 6000, 600000
ad.person.import_bulk([{"_key": str(i), "id": i, "name": f"p{i}", "age": 30, "city": "c0"} for i in range(N)])
seen = set()
batch = []
while len(seen) < E:
    a, b = rnd.randrange(N), rnd.randrange(N)
    if a < b and (a, b) not in seen:
        seen.add((a, b)); batch.append({"_from": f"person/{a}", "_to": f"person/{b}"})
ad.knows.import_bulk(batch)
tri = ad.OLAP["triangles"]

# (1) a fast query with a limit is untouched
ad.olap_limit_s = LIMIT
t = time.perf_counter(); rows = ad.run_olap("top_degree"); print(f"fast query: {time.perf_counter() - t:.2f}s, {len(rows)} rows")
assert rows, "top_degree returned nothing"

# (2) the server kills the long query at the limit, error 1500
try:
    ad.db.aql.execute(tri, max_runtime=LIMIT)
except Exception as e:  # noqa: BLE001
    print(f"raw call raised {type(e).__name__} error_code={getattr(e, 'error_code', None)} http={getattr(e, 'http_code', None)}")
    assert getattr(e, "error_code", None) == 1500, "the server did not answer error 1500 for maxRuntime"
else:
    sys.exit("SMOKE FAIL: the triangle count finished inside the limit; raise N/E so it is long enough to be cut")

# (3) the adapter turns it into QueryKilled, in about LIMIT seconds
ad.olap_limit_s = LIMIT
t = time.perf_counter()
try:
    ad.run_olap("triangles")
except G.QueryKilled as e:
    dt = time.perf_counter() - t
    print(f"QueryKilled after {dt:.2f}s (limit {LIMIT:g}s): {e}")
    assert LIMIT * 0.8 <= dt <= LIMIT + SLACK, f"kill latency {dt:.2f}s outside [{LIMIT * 0.8:g}, {LIMIT + SLACK:g}]"
    print(f"SMOKE OK kill latency {dt - LIMIT:+.2f}s")
else:
    sys.exit("SMOKE FAIL: run_olap returned instead of raising QueryKilled")
PY
