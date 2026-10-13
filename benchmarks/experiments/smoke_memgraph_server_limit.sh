#!/bin/bash
# SMOKE TEST for DECISIONS #179: does the pinned Memgraph image (the digest the l2 graph lane pins, started with the lane's flags,
# --query-execution-timeout-sec=0 included) abort a long analytics query at a Bolt transaction timeout, with which error, in about
# the time asked, and does MemgraphGraph.run_olap turn it into graph_common.QueryKilled?
#
#   bash smoke_memgraph_server_limit.sh        # about a minute, one docker container on port 18687
# The container is pinned to SMOKE_CORES (default 14-15) with SMOKE_MEM (default 4g) and the client runs under nice -n 19 and
# taskset, so it can sit beside a timed sweep as long as the sweep does not use those cores. Never run it on mini.
#
# It prints, for the record, both mechanisms on a cartesian count over 1000 nodes: (i) the runtime setting
# SET DATABASE SETTING 'query.timeout' (global state, reset afterwards) and (ii) the per-query Bolt tx_timeout the adapter uses.
# Then (iii) a fast query with a limit is untouched and (iv) MemgraphGraph.run_olap raises QueryKilled in about LIMIT seconds.
# Prints "SMOKE OK <kill latency>" or exits non-zero with the reason. The container is removed on exit.
set -u
cd "$(dirname "$0")" || exit 1
PORT=${SMOKE_PORT:-18687}
CORES=${SMOKE_CORES:-14-15}
MEM=${SMOKE_MEM:-4g}
LIMIT=${SMOKE_LIMIT_S:-3}
SLACK=${SMOKE_SLACK_S:-10}
IMG=$(python3 - <<'PY'
import re
print(re.search(r'"memgraph_graph": \{.*?"server_image": "([^"]+)"', open("runner.py").read(), re.S).group(1))
PY
)
NAME=smoke-memgraph-server-limit-$$
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT
docker image inspect "$IMG" >/dev/null 2>&1 || docker pull -q "$IMG" >/dev/null || { echo "SMOKE FAIL: cannot pull $IMG"; exit 1; }
# the lane's server flags (runner.py), sized for the smoke container: 2 workers, 90% of 4g
docker run -d --name "$NAME" --cpuset-cpus "$CORES" --memory "$MEM" -p "$PORT:7687" "$IMG" --log-level=INFO --also-log-to-stderr=true \
  --bolt-num-workers=2 --storage-snapshot-thread-count=2 --memory-limit=3600 --query-execution-timeout-sec=0 --telemetry-enabled=false \
  >/dev/null || { echo "SMOKE FAIL: docker run"; exit 1; }
for _ in $(seq 1 90); do docker logs "$NAME" 2>&1 | grep -q "Bolt server is fully armed and operational" && break; sleep 1; done
docker logs "$NAME" 2>&1 | grep -q "Bolt server is fully armed and operational" || { echo "SMOKE FAIL: server not ready"; exit 1; }
EXP=$PWD BENCH_SERVER_HOST=localhost BENCH_SERVER_PORT=$PORT LIMIT=$LIMIT SLACK=$SLACK \
  nice -n 19 taskset -c "$CORES" uv run --directory ../.. --with neo4j==6.3.1 python -I - <<'PY' || exit 1
import os, sys, time
sys.path.insert(0, os.environ["EXP"])
import neo4j
import graph_common as G
import l2_graph as L

LIMIT, SLACK = float(os.environ["LIMIT"]), float(os.environ["SLACK"])
ad = L.MemgraphGraph()
ad.connect()
print("server", ad.version, "driver", neo4j.__version__)
with ad.driver.session() as s:
    s.run("UNWIND range(1, 1000) AS i CREATE (:P {id: i})").consume()
SLOW = "MATCH (a:P),(b:P),(c:P) RETURN count(*) AS n"


def describe(label, fn):
    t = time.perf_counter()
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"{label}: {type(e).__module__}.{type(e).__name__} code={getattr(e, 'code', None)!r} "
              f"after {time.perf_counter() - t:.2f}s: {str(e)[:140]!r}")
        return e
    sys.exit(f"SMOKE FAIL: {label} finished inside the limit; raise the node count")


# (i) the runtime setting, for the record (global state: set, try, reset)
with ad.driver.session() as s:
    s.run(f"SET DATABASE SETTING 'query.timeout' TO '{LIMIT:g}'").consume()
try:
    describe("(i) query.timeout", lambda: list(ad.driver.session().run(SLOW)))
finally:
    with ad.driver.session() as s:
        s.run("SET DATABASE SETTING 'query.timeout' TO '0'").consume()

# (ii) the per-query Bolt transaction timeout, the adapter's mechanism: the helper must recognise the real error
e = describe("(ii) tx_timeout", lambda: list(ad.driver.session().run(neo4j.Query(SLOW, timeout=LIMIT))))
assert G.is_bolt_tx_timeout(e), "graph_common.is_bolt_tx_timeout does not recognise the real exception"

# (iii) a fast query with a limit is untouched
ad.olap_limit_s = LIMIT
rows = ad.run_olap("top_degree")
print(f"fast query with a limit: {rows}")

# (iv) the adapter
ad.LSQB = {"slow": SLOW}
t = time.perf_counter()
try:
    ad.run_olap("slow")
except G.QueryKilled as e:
    dt = time.perf_counter() - t
    print(f"QueryKilled after {dt:.2f}s (limit {LIMIT:g}s): {str(e)[:160]}")
    assert LIMIT * 0.8 <= dt <= LIMIT + SLACK, f"kill latency {dt:.2f}s outside [{LIMIT * 0.8:g}, {LIMIT + SLACK:g}]"
    with ad.driver.session() as s:                                   # the connection and the data survive a kill
        assert s.run("MATCH (a:P) RETURN count(a) AS n").single()["n"] == 1000
    print(f"SMOKE OK kill latency {dt - LIMIT:+.2f}s")
else:
    sys.exit("SMOKE FAIL: run_olap returned instead of raising QueryKilled")
PY
