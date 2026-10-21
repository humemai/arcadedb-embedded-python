#!/usr/bin/env bash
# Phase 6: build the standalone Vector API reproducers (no ArcadeDB) with native-image. usage: phase6-repro.sh CLASS [EXTRA native-image options]
# CLASS = DotMin | DotRepro (sources: .notes/bench/repros/native-spike-20261021/vapi-repro). Through quiet_build.sh on cores 12-15.
set -u
G=${GRAALVM_HOME_P5:-$HOME/build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1}
QB=$HOME/repos/humemai/arcadedb-embedded-python/.notes/bench/tools/quiet_build.sh
SRC=$HOME/repos/humemai/arcadedb-embedded-python/.notes/bench/repros/native-spike-20261021/vapi-repro
OUT=$HOME/build-scratch/native-lib/p6/vapi; mkdir -p "$OUT/classes"
export JAVA_HOME=$G PATH=$G/bin:$PATH
c=$1; shift
tag=$c$(printf '%s' "$*" | tr -c 'A-Za-z0-9' '_')
javac --release 25 --add-modules jdk.incubator.vector ${REPRO_CP:+-cp "$REPRO_CP"} -d "$OUT/classes" "$SRC/$c.java" || exit 1
set -x
NEED_GB=8 $QB taskset -c 12-15 native-image -O2 --no-fallback --add-modules=jdk.incubator.vector -J-Xmx12g "$@" -cp "$OUT/classes${REPRO_CP:+:$REPRO_CP}" "$c" "$OUT/$tag" > "$OUT/build-$tag.log" 2>&1
rc=$?
set +x
echo "$c $* rc=$rc"
[ $rc = 0 ] && "$OUT/$tag" | tee "$OUT/run-$tag.log"
