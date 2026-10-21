#!/usr/bin/env bash
# Phase 5: build the spike image(s) on GraalVM CE 25.4.4.1.1 (-O2, default -march = x86-64-v3) and the per-call probe images.
# usage: phase5-build.sh full MODE TAG [EXTRA native-image options]   (MODE 0 = C function pointers, 1 = FFM unbound build-time handle)
#        phase5-build.sh probe MODE TAG [EXTRA]
# Every build goes through quiet_build.sh on cores 12-15 (the timed A/B on 6-7 pauses while it runs).
set -u
WT=$HOME/build-scratch/wt-native-spike
G=${GRAALVM_HOME_P5:-$HOME/build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1}
QB=$HOME/repos/humemai/arcadedb-embedded-python/.notes/bench/tools/quiet_build.sh
OUT=$HOME/build-scratch/native-lib/p5; mkdir -p "$OUT"
export JAVA_HOME=$G PATH=$G/bin:$PATH
what=$1 mode=$2 tag=$3; shift 3
export NATIVE_IMAGE_OPTIONS="-J-Dfastops.mode=$mode -J-Xmx12g $*"
cd "$WT"
case $what in
  full)
    NEED_GB=14 $QB taskset -c 12-15 ./mvnw -B --no-transfer-progress -f native-spike/pom.xml -DskipTests -Dgraalvm.version=25.4.4.1.1 -Dnative.opt=-O2 package > "$OUT/build-$tag.log" 2>&1
    rc=$?; mkdir -p "$OUT/$tag"
    cp native-spike/target/libarcadedb.so "$OUT/$tag/" 2>/dev/null; cp "$HOME/build-scratch/native-lib/dir6/libjvector-x86_64.so" "$OUT/$tag/"
    echo "full $tag rc=$rc $(grep -a 'Finished generating' "$OUT/build-$tag.log")" ;;
  probe)
    CP=$(cat "$HOME/build-scratch/native-ffm-probe/cp.txt"); C=$WT/native-spike/target/classes; PC=$OUT/probe-classes; mkdir -p "$PC"
    javac --release 25 --add-modules jdk.incubator.vector -d "$PC" -cp "$C:$CP" "$WT/native-spike/scripts/Probe5.java" || exit 1
    NEED_GB=14 $QB taskset -c 12-15 native-image -O2 --no-fallback --add-modules=jdk.incubator.vector --enable-native-access=ALL-UNNAMED \
      --initialize-at-build-time=io.github.jbellis.jvector.vector.cnative.FastMode,io.github.jbellis.jvector.vector.cnative.FfmKernels \
      -cp "$PC:$C:$CP" Probe5 "$OUT/Probe5_$tag" > "$OUT/build-probe-$tag.log" 2>&1
    echo "probe $tag rc=$? $(grep -a 'Finished generating' "$OUT/build-probe-$tag.log")" ;;
esac
