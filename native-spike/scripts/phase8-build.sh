#!/usr/bin/env bash
# Phase 8 (same recipe as phase7-build.sh, worktree wt-native-perf8, output p8perf): build the image from the native-perf worktree on GraalVM CE 25.4.4.1.1 (-O2, FFM unbound handle = fastops.mode 1), with local symbols kept
# (-H:-DeleteLocalSymbols) so a gdb stack sampler can name the hot methods. usage: phase7-build.sh TAG [EXTRA native-image options]
set -u
WT=$HOME/build-scratch/wt-native-perf8
G=${GRAALVM_HOME_P5:-$HOME/build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1}
QB=$HOME/repos/humemai/arcadedb-embedded-python/.notes/bench/tools/quiet_build.sh
OUT=$HOME/build-scratch/native-lib/p8perf; mkdir -p "$OUT"
export JAVA_HOME=$G PATH=$G/bin:$PATH
tag=$1; shift
export NATIVE_IMAGE_OPTIONS="-J-Dfastops.mode=1 -J-Xmx12g -H:-DeleteLocalSymbols -H:-VectorAPISupport $*"
cd "$WT"
rm -f native-spike/target/libarcadedb.so   # a failed build must not leave the previous image behind for the copy below (2026-10-22: img2 failed and shipped img1 bytes)
QBX=$QB; [ -n "${NO_QB:-}" ] && QBX=""   # NO_QB=1: the caller already holds a quiet_build slot (no nested waits)
NEED_GB=13 JOB_MEM_GB=14 $QBX taskset -c 12-15 ./mvnw -B --no-transfer-progress -f native-spike/pom.xml -DskipTests -Dgraalvm.version=25.4.4.1.1 -Dnative.opt=-O2 package > "$OUT/build-$tag.log" 2>&1
rc=$?; mkdir -p "$OUT/$tag"; rm -f "$OUT/$tag/libarcadedb.so"
[ $rc = 0 ] && cp native-spike/target/libarcadedb.so "$OUT/$tag/"; cp "$HOME/build-scratch/native-lib/dir6/libjvector-x86_64.so" "$OUT/$tag/"
echo "full $tag rc=$rc $(grep -a 'Finished generating' "$OUT/build-$tag.log")" > "$OUT/build-$tag.done"
cat "$OUT/build-$tag.done"
