#!/bin/bash
# SMOKE TEST for DECISIONS #179: does the real MongoDB (the digest the l2 graph lane pins) stop a long analytics aggregate at
# maxTimeMS with error 50 (MaxTimeMSExpired, pymongo ExecutionTimeout), in about the time asked, and does MongoGraph.run_olap turn it
# into graph_common.QueryKilled?
#
#   bash smoke_mongodb_server_limit.sh         # a minute or two, one docker container on port 18527
# The container is pinned to SMOKE_CORES (default 14-15) with SMOKE_MEM (default 4g) and the client runs under nice -n 19 and
# taskset, so it can sit beside a timed sweep as long as the sweep does not use those cores. Never run it on mini.
#
# It checks (1) a fast aggregate with a maxTimeMS set is untouched; (2) a raw unindexed self-join aggregate over a few thousand
# documents raises the class and code the helper expects; (3) MongoGraph.run_olap("lsqb_q5") on those collections raises QueryKilled
# in about LIMIT seconds. Prints "SMOKE OK <kill latency>" or exits non-zero with the reason. The container is removed on exit.
set -u
cd "$(dirname "$0")" || exit 1
PORT=${SMOKE_PORT:-18527}
CORES=${SMOKE_CORES:-14-15}
MEM=${SMOKE_MEM:-4g}
LIMIT=${SMOKE_LIMIT_S:-3}
SLACK=${SMOKE_SLACK_S:-10}
IMG=$(python3 - <<'PY'
import re
print(re.search(r'"mongodb_graph": \{.*?"server_image": "([^"]+)"', open("runner.py").read(), re.S).group(1))
PY
)
NAME=smoke-mongodb-server-limit-$$
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT
docker image inspect "$IMG" >/dev/null 2>&1 || docker pull -q "$IMG" >/dev/null || { echo "SMOKE FAIL: cannot pull $IMG"; exit 1; }
docker run -d --name "$NAME" --cpuset-cpus "$CORES" --memory "$MEM" -p "$PORT:27017" "$IMG" mongod --bind_ip_all >/dev/null || { echo "SMOKE FAIL: docker run"; exit 1; }
for _ in $(seq 1 60); do docker logs "$NAME" 2>&1 | grep -q "Waiting for connections" && break; sleep 1; done
docker logs "$NAME" 2>&1 | grep -q "Waiting for connections" || { echo "SMOKE FAIL: server not ready"; exit 1; }
EXP=$PWD PORT=$PORT LIMIT=$LIMIT SLACK=$SLACK \
  nice -n 19 taskset -c "$CORES" uv run --directory ../.. --with pymongo==4.18.1 python -I - <<'PY' || exit 1
import os, sys, time
sys.path.insert(0, os.environ["EXP"])
import pymongo
import graph_common as G
import l2_graph as L
import mongo_common

LIMIT, SLACK = float(os.environ["LIMIT"]), float(os.environ["SLACK"])
cl = pymongo.MongoClient(f"mongodb://localhost:{os.environ['PORT']}", serverSelectionTimeoutMS=30000)
cl.admin.command("ping")
print("server", cl.server_info()["version"], "pymongo", pymongo.version)
db = cl["smoke"]
n = 3000
db["e_replyof"].insert_many([{"s": i, "d": 1} for i in range(n)])          # every reply points at message 1 ...
db["e_hastag"].insert_many([{"s": 1, "d": i % 50} for i in range(n)] + [{"s": i, "d": i % 50} for i in range(2, n)])
# ... and message 1 carries n tags: the unindexed $lookup chain of lsqb_q5 produces n x n rows and scans for each
ad = L.MongoGraph()
ad.db = db

# (1) a fast aggregate with a limit is untouched
ad.olap_limit_s = LIMIT
t = time.perf_counter(); rows = list(db["e_hastag"].aggregate([{"$count": "n"}], maxTimeMS=int(LIMIT * 1000)))
print(f"fast aggregate: {time.perf_counter() - t:.2f}s {rows}")

# (2) the raw call: the real exception class and code
coll, pipeline = ad._LSQB["lsqb_q5"]
t = time.perf_counter()
try:
    list(db[coll].aggregate(pipeline, allowDiskUse=True, maxTimeMS=int(LIMIT * 1000)))
except Exception as e:  # noqa: BLE001
    print(f"raw call raised {type(e).__module__}.{type(e).__name__} code={getattr(e, 'code', None)} "
          f"after {time.perf_counter() - t:.2f}s: {str(e)[:160]}")
    assert mongo_common.is_query_killed(e), "the helper does not recognise the real exception"
    assert getattr(e, "code", None) == 50, "expected code 50 (MaxTimeMSExpired)"
else:
    sys.exit("SMOKE FAIL: the self-join finished inside the limit; raise n so it is long enough to be cut")

# (3) the adapter
ad.olap_limit_s = LIMIT
t = time.perf_counter()
try:
    ad.run_olap("lsqb_q5")
except G.QueryKilled as e:
    dt = time.perf_counter() - t
    print(f"QueryKilled after {dt:.2f}s (limit {LIMIT:g}s): {str(e)[:160]}")
    assert LIMIT * 0.8 <= dt <= LIMIT + SLACK, f"kill latency {dt:.2f}s outside [{LIMIT * 0.8:g}, {LIMIT + SLACK:g}]"
    print(f"SMOKE OK kill latency {dt - LIMIT:+.2f}s")
else:
    sys.exit("SMOKE FAIL: run_olap returned instead of raising QueryKilled")
PY
