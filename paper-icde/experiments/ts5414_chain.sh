#!/bin/bash
# Waits for the INT8 rep run, then verifies #5414 on dev14 with sealed data.
set -u
OUT=$HOME/profiling/verify5414
mkdir -p "$OUT"
until grep -qa "INT8-REPS-DONE" ~/profiling/int8_reps_outer.log 2>/dev/null; do sleep 60; done
cd ~/repos/humemai/arcadedb-icde/paper-icde/experiments
docker run --rm --cpuset-cpus 0-11 --memory 12g --memory-swap 12g \
  -v "$PWD:/work" -w /work -v "$HOME/icde-data:/data:ro" -v "$OUT:/pout" \
  -v "$HOME/profiling/ts5414_driver.py:/work/ts5414_driver.py" \
  -e TS_DB_PATH=/tmp/l4n_arcade -e ARCADEDB_HEAP=6g \
  icde-bench:arcadedb bash -c \
  "python -m pip install -q arcadedb-embedded==26.8.1.dev14 && python -u ts5414_driver.py" \
  > "$OUT/ts5414.log" 2>&1
echo "TS5414 rc=$?"
echo TS5414-DONE
