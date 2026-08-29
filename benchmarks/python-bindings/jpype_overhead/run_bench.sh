#!/usr/bin/env bash
# Orchestrates the Java-vs-Python JPype-overhead benchmark suite.
# Runs every phase sequentially, logging to results/<step>.log and collecting
# RESULT/PARITY/INFO/MICRO lines into results/all_results.csv. Steps that fail
# are recorded and skipped past, so an overnight run always completes.
set -u

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Was ../../../.. from bindings/python/benchmarks/jpype_overhead. The suite
# now lives at benchmarks/python-bindings/jpype_overhead, one level nearer
# the root, and this path is what locates the uv project and its venv.
REPO_ROOT="$(cd "$BENCH_DIR/../../.." && pwd)"
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

# The campaign pins every cell to 0-11; a host-side suite gets the whole machine
# unless it asks. An unpinned run is not comparable to the numbers it is meant
# to be compared against -- the same defect that made the e4 host-side run
# unusable. Override with BENCH_CPUSET= (empty) to deliberately run unpinned.
BENCH_CPUSET="${BENCH_CPUSET-0-11}"
if [ -n "$BENCH_CPUSET" ]; then
    PIN=(taskset -c "$BENCH_CPUSET")
else
    PIN=()
fi

FAILED_STEPS=""

# OverheadBench.class is gitignored, so a fresh checkout has the source and no
# class: every j-* arm died on ClassNotFoundException while run_bench.sh still
# exited 0, and the CSV kept only the p-* half of a Java-vs-Python comparison.
# The bundled JRE is runtime-only and neither bench host carries a JDK, so
# compile in the same Corretto the JRE is (docker image, no host install).
JAVAC_IMAGE="${JAVAC_IMAGE:-maven:3.9-amazoncorretto-25}"
compile_java() {
    if command -v javac >/dev/null 2>&1; then
        echo "=== compiling OverheadBench.java with host javac"
        javac -cp "$JARS" -d "$BENCH_DIR" "$BENCH_DIR/OverheadBench.java" || return 1
    elif command -v docker >/dev/null 2>&1; then
        echo "=== compiling OverheadBench.java in $JAVAC_IMAGE"
        # HOME=/tmp: the maven image tries to seed /root/.m2 and prints a
        # "Wrong volume permissions?" warning under -u; javac never needs it.
        docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp \
            -v "$BENCH_DIR:/bench" -v "$SITE/jars:/jars:ro" -w /bench \
            "$JAVAC_IMAGE" javac -cp '/jars/*' -d /bench OverheadBench.java || return 1
    else
        echo "no javac and no docker: cannot build the Java arm" >&2
        return 1
    fi
    [ -f "$BENCH_DIR/OverheadBench.class" ]
}
if ! compile_java; then
    echo "ABORT: OverheadBench did not compile; the Java half of the suite" >&2
    echo "       cannot run and a Python-only CSV proves nothing." >&2
    exit 1
fi

step() { # step <name> <cmd...>
    local name="$1"
    shift
    echo "=== [$(date +%H:%M:%S)] $name" | tee -a "$RESULTS/run.log"
    if "$@" > "$RESULTS/$name.log" 2>&1; then
        echo "OK  $name" >> "$RESULTS/run.log"
    else
        echo "FAIL $name (exit $?)" | tee -a "$RESULTS/run.log"
        FAILED_STEPS="$FAILED_STEPS $name"
    fi
    # -o extraction (not ^-anchored): the engine logger omits trailing newlines,
    # so protocol lines can start mid-line
    # PROVENANCE is collected with the rest. The phases now print a line naming
    # the engine, the commit and the timestamp they ran under, and a collector
    # that filtered it out would leave the CSV exactly as unprovenanced as the
    # one this change exists to replace.
    # NOT [^\r\n]* -- in a POSIX bracket expression \r and \n are the literal
    # characters backslash, r and n, so that class means "not backslash, r or n"
    # and every line was truncated at its first r/n. It silently reduced
    # PROVENANCE,{"cpuset": "0-19", "engine"...  to  PROVENANCE,{"cpuset": "0-19", "e
    # for the whole of 2026-08. grep is already line-oriented, so .* is the
    # correct "rest of line"; tr strips the CR the engine logger can leave.
    grep -ohE '(RESULT|PARITY|INFO|MICRO|PROVENANCE),.*' "$RESULTS/$name.log" \
        | tr -d '\r' >> "$RESULTS/all_results.csv" || true
}

jrun() { # jrun <phase> <dataDir> <dbDir>
    "${PIN[@]}" "$JAVA" "${JFLAGS[@]}" -cp "$JARS:$BENCH_DIR" OverheadBench "$@"
}

prun() { # prun <phase> <dataDir> <dbDir>
    (cd "$REPO_ROOT" && "${PIN[@]}" uv run python "$BENCH_DIR/bench_python.py" "$@")
}

: > "$RESULTS/all_results.csv"

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

# "Steps that fail are skipped past so an overnight run always completes" is a
# good property; reporting rc=0 for a run in which every Java arm died is not.
# The queue gates on this line.
if [ -n "$FAILED_STEPS" ]; then
    echo "FAILED STEPS:$FAILED_STEPS" | tee -a "$RESULTS/run.log"
    exit 1
fi
