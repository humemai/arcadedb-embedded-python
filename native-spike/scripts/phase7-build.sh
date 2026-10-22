#!/usr/bin/env bash
# Phase 7: build the image from the native-perf worktree on GraalVM CE 25.4.4.1.1 (-O2, FFM unbound handle = fastops.mode 1), with local symbols kept
# (-H:-DeleteLocalSymbols) so a gdb stack sampler can name the hot methods. usage: phase7-build.sh TAG [EXTRA native-image options]
set -u
WT=$HOME/build-scratch/wt-native-perf
G=${GRAALVM_HOME_P5:-$HOME/build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1}
QB=$HOME/repos/humemai/arcadedb-embedded-python/.notes/bench/tools/quiet_build.sh
OUT=$HOME/build-scratch/native-lib/p7perf; mkdir -p "$OUT"
export JAVA_HOME=$G PATH=$G/bin:$PATH
tag=$1; shift
export NATIVE_IMAGE_OPTIONS="-J-Dfastops.mode=1 -J-Xmx12g -H:-DeleteLocalSymbols -H:-VectorAPISupport $*"
cd "$WT"
NEED_GB=14 $QB taskset -c 12-15 ./mvnw -B --no-transfer-progress -f native-spike/pom.xml -DskipTests -Dgraalvm.version=25.4.4.1.1 -Dnative.opt=-O2 package > "$OUT/build-$tag.log" 2>&1
rc=$?; mkdir -p "$OUT/$tag"
cp native-spike/target/libarcadedb.so "$OUT/$tag/" 2>/dev/null; cp "$HOME/build-scratch/native-lib/dir6/libjvector-x86_64.so" "$OUT/$tag/"
echo "full $tag rc=$rc $(grep -a 'Finished generating' "$OUT/build-$tag.log")" > "$OUT/build-$tag.done"
cat "$OUT/build-$tag.done"
