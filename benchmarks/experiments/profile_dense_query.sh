#!/bin/bash
# Dense DEEP-10M fp32 QUERY-phase CPU profile (owed on #5412/#5388).
# Chained: waits for the #5414 verification to finish first.
# Fixes the marker-wait fallthrough: attach ONLY after QUERY-PHASE-START.
set -u
OUT=$HOME/profiling/flame
until grep -qa "TS5414-DONE" ~/profiling/ts5414_outer.log 2>/dev/null; do sleep 60; done
cd ~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
docker rm -f prof_dense10m >/dev/null 2>&1
docker run -d --name prof_dense10m --cpuset-cpus 0-11 --memory 37g --memory-swap 37g \
  -v "$PWD:/work" -w /work -v "$HOME/bench-data:/data:ro" \
  -v "$HOME/profiling/async-profiler-4.0-linux-x64:/prof:ro" -v "$OUT:/pout" \
  -e MODE=dense -e PROFILE_SECS=300 -e BENCH_DENSE_DATA=/data/dense -e BENCH_DENSE_M=32 \
  -e ARCADEDB_HEAP=24g \
  dbbench:arcadedb python -u profile_query_driver.py >/dev/null
found=0
for i in $(seq 1 480); do  # up to 2h for the ~85min build
  docker logs prof_dense10m 2>&1 | grep -qa "QUERY-PHASE-START" && { found=1; break; }
  docker ps -q -f name=prof_dense10m | grep -q . || { echo "dense10m DIED"; docker logs prof_dense10m 2>&1 | tail -6; exit 1; }
  sleep 15
done
if [ "$found" -ne 1 ]; then
  echo "dense10m NEVER-REACHED-QUERY-PHASE after 2h; not attaching"
  docker logs prof_dense10m 2>&1 | tail -6
  docker rm -f prof_dense10m >/dev/null 2>&1
  exit 1
fi
sleep 10
docker exec prof_dense10m /prof/bin/asprof start -e cpu 1 && echo "dense10m query-phase profiling"
sleep 240
docker exec prof_dense10m /prof/bin/asprof stop -o collapsed -f /pout/dense10m_query_cpu.collapsed 1 && echo "dense10m collapsed written"
docker rm -f prof_dense10m >/dev/null 2>&1
echo DENSE-QUERY-PROFILE-DONE
