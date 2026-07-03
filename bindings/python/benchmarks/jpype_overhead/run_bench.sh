#!/usr/bin/env bash
# Orchestrates the Java-vs-Python JPype-overhead benchmark suite.
# Runs every phase sequentially, logging to results/<step>.log and collecting
# RESULT/PARITY/INFO/MICRO lines into results/all_results.csv. Steps that fail
# are recorded and skipped past, so an overnight run always completes.
set -u

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BENCH_DIR/../../../.." && pwd)"
SITE="$REPO_ROOT/.venv/lib/python3.12/site-packages/arcadedb_embedded"
JAVA="$SITE/jre/bin/java"
JARS="$SITE/jars/*"
RESULTS="$BENCH_DIR/results"
DBS="$BENCH_DIR/dbs"
mkdir -p "$RESULTS" "$DBS"

JFLAGS=(
  --add-modules=jdk.incubator.vector
  -Djava.awt.headless=true
  --enable-native-access=ALL-UNNAMED
  -Dfile.encoding=UTF8
  --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED
  --add-opens=java.base/java.nio.channels.spi=ALL-UNNAMED
  --add-opens=java.base/java.lang=ALL-UNNAMED
  -Dpolyglot.engine.WarnInterpreterOnly=false
  -XX:+UseCompactObjectHeaders
  -Xmx4g
)

step() { # step <name> <cmd...>
  local name="$1"; shift
  echo "=== [$(date +%H:%M:%S)] $name" | tee -a "$RESULTS/run.log"
  if "$@" >"$RESULTS/$name.log" 2>&1; then
    echo "OK  $name" >>"$RESULTS/run.log"
  else
    echo "FAIL $name (exit $?)" | tee -a "$RESULTS/run.log"
  fi
  # -o extraction (not ^-anchored): the engine logger omits trailing newlines,
  # so protocol lines can start mid-line
  grep -ohE '(RESULT|PARITY|INFO|MICRO),[^\r\n]*' "$RESULTS/$name.log" >>"$RESULTS/all_results.csv" || true
}

jrun() { # jrun <phase> <dataDir> <dbDir>
  "$JAVA" "${JFLAGS[@]}" -cp "$JARS:$BENCH_DIR" OverheadBench "$@"
}

prun() { # prun <phase> <dataDir> <dbDir>
  (cd "$REPO_ROOT" && uv run python "$BENCH_DIR/bench_python.py" "$@")
}

: >"$RESULTS/all_results.csv"

# ---------- lifecycle first (fast sanity for both harnesses) ----------
rm -rf "$DBS/lc_java" "$DBS/lc_py" && mkdir -p "$DBS/lc_java" "$DBS/lc_py"
step j-lifecycle jrun bench-lifecycle - "$DBS/lc_java"
step p-lifecycle prun bench-lifecycle - "$DBS/lc_py"

# ---------- phase A: vector 100k ----------
step j-vector-build-100k jrun vector-build "$BENCH_DIR/data_100k" "$DBS/vector_100k"
step j-vector-bench-100k jrun vector-bench "$BENCH_DIR/data_100k" "$DBS/vector_100k"
step p-vector-bench-100k prun vector-bench "$BENCH_DIR/data_100k" "$DBS/vector_100k"

# ---------- phase B: docs / result materialization ----------
step j-seed-docs jrun seed-docs - "$DBS/docs"
step j-bench-query jrun bench-query - "$DBS/docs"
step p-bench-query prun bench-query - "$DBS/docs"

# ---------- phase F: micro (uses docs db) ----------
step p-micro prun micro - "$DBS/docs"

# ---------- phase C: write ----------
rm -rf "$DBS/write_java" "$DBS/write_py"
step j-bench-write jrun bench-write - "$DBS/write_java"
step p-bench-write prun bench-write - "$DBS/write_py"

# ---------- phase D: cypher ----------
step j-seed-graph jrun seed-graph - "$DBS/graph"
step j-bench-cypher jrun bench-cypher - "$DBS/graph"
step p-bench-cypher prun bench-cypher - "$DBS/graph"

# ---------- phase E: fulltext ----------
step j-seed-text jrun seed-text - "$DBS/text"
step j-bench-fulltext jrun bench-fulltext - "$DBS/text"
step p-bench-fulltext prun bench-fulltext - "$DBS/text"

# ---------- stability re-run: vector 100k, second pass ----------
step j-vector-bench-100k-run2 jrun vector-bench "$BENCH_DIR/data_100k" "$DBS/vector_100k"
step p-vector-bench-100k-run2 prun vector-bench "$BENCH_DIR/data_100k" "$DBS/vector_100k"

# ---------- phase G: headline 500k ----------
if [ "${SKIP_500K:-0}" != "1" ]; then
  step gen-dataset-500k bash -c "cd '$REPO_ROOT' && uv run python '$BENCH_DIR/gen_dataset.py' '$BENCH_DIR/data_500k' 500000 384"
  step j-vector-build-500k jrun vector-build "$BENCH_DIR/data_500k" "$DBS/vector_500k"
  step j-vector-bench-500k jrun vector-bench "$BENCH_DIR/data_500k" "$DBS/vector_500k"
  step p-vector-bench-500k prun vector-bench "$BENCH_DIR/data_500k" "$DBS/vector_500k"
fi

echo "=== [$(date +%H:%M:%S)] ALL DONE" | tee -a "$RESULTS/run.log"
