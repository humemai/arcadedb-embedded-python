#!/usr/bin/env bash
# Build the native-preview image (the one the arcadedb-embedded-native wheel ships): GraalVM CE 25.4.4.1.1, -O2, FFM unbound Highway
# handle (fastops.mode 1), -H:-VectorAPISupport (CE crash oracle/graal#14751), engine jars of the pinned RELEASE (arcadedb.version, from
# Maven Central, never a local SNAPSHOT), local symbols deleted (the default: a smaller image than the phase 7/8 profiling builds).
# MARCH (default compatibility = baseline x86-64, what a manylinux wheel promises, PEP 600; x86-64-v3 is the GraalVM CE 25.4 default and the faster reference).
# usage: [MARCH=x86-64-v3] preview-build.sh [OUTDIR]     Run it DETACHED through tools/quiet_build.sh (NEED_GB=13 JOB_MEM_GB=14), never directly.
#   e.g. NEED_GB=13 JOB_MEM_GB=14 quiet_build.sh bash native-spike/scripts/preview-build.sh
set -eu
WT=$(cd "$(dirname "$0")/../.." && pwd)
G=${GRAALVM_HOME_P5:-$HOME/build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1}
OUT=${1:-$HOME/build-scratch/native-lib/preview}; mkdir -p "$OUT"
ENGINE=${ARCADEDB_ENGINE_VERSION:-26.10.2}
MARCH=${MARCH:-compatibility}
export JAVA_HOME=$G PATH=$G/bin:$PATH
export NATIVE_IMAGE_OPTIONS="-J-Dfastops.mode=1 -J-Xmx12g -H:-VectorAPISupport -march=$MARCH"
cd "$WT"
rm -f native-spike/target/libarcadedb.so "$OUT/libarcadedb.so"
./mvnw -B --no-transfer-progress -f native-spike/pom.xml -DskipTests -Darcadedb.version="$ENGINE" -Dgraalvm.version=25.4.4.1.1 -Dnative.opt=-O2 package > "$OUT/build.log" 2>&1
cp native-spike/target/libarcadedb.so "$OUT/"
# Highway (jvector's native provider), found next to libarcadedb.so by the image (ARCADEDB_NATIVE_LIBDIR)
J=$(unzip -l "$HOME/.m2/repository/io/github/jbellis/jvector/4.0.2/jvector-4.0.2.jar" | awk '/libjvector-x86_64.so/{print $4}' | head -1)
if [ -n "$J" ]; then unzip -p "$HOME/.m2/repository/io/github/jbellis/jvector/4.0.2/jvector-4.0.2.jar" "$J" > "$OUT/libjvector-x86_64.so"; else cp "$HOME/build-scratch/native-lib/dir6/libjvector-x86_64.so" "$OUT/"; fi
sha256sum "$OUT/libarcadedb.so" "$OUT/libjvector-x86_64.so" > "$OUT/sha256.txt"
echo "preview image done: engine $ENGINE; march $MARCH; $(grep -a 'Finished generating' "$OUT/build.log")" | tee "$OUT/build.done"
