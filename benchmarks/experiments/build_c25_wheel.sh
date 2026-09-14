#!/bin/bash
# Build the wheel from the SAME upstream jars the c25 server image holds, so
# the embedded and served arms differ in transport and nothing else.
set -euo pipefail
REPO=$HOME/repos/humemai/arcadedb-embedded-python
LIB=$HOME/engine-builds/c25/ctx/arcadedb-assembly/lib
DEST=$HOME/engine-builds/c25
SHA=${1:-8d6af94753ea8446bd13ac1aed2bb79eaf78dc90}  # first positional: the upstream commit the jars must carry (qCZ passes PAIR_SHA)
say() { echo "[$(date -Is)] wheel: $*"; }

[ -d "$LIB" ] || { say "ABORT: no jar dir at $LIB"; exit 1; }
say "building from $(ls "$LIB"/*.jar | wc -l) upstream jars"

# THIRD POSITIONAL, ABSOLUTE. As an env var it is silently ignored and the build
# falls through to jars from a moving upstream tag while still reporting success.
bash "$REPO/bindings/python/scripts/build.sh" "" "3.12" "$LIB" > "$DEST/wheel.log" 2>&1 \
  || { tail -25 "$DEST/wheel.log"; say "ABORT: wheel build failed"; exit 1; }
grep -q "Using provided JAR directory\|pre-staged" "$DEST/wheel.log" \
  || { say "ABORT: build.sh did not take the local jars"; grep -m1 "JARs from" "$DEST/wheel.log"; exit 1; }

W=$(ls -t "$REPO"/bindings/python/dist/*.whl | head -1)
say "wheel $W"

# V0: the wheel must carry the SAME commit as the image, or the pair is not a pair.
python3 - "$W" "$SHA" <<'PY'
import sys, zipfile, io
w, want = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(w)
jar = next(n for n in z.namelist() if "/jars/arcadedb-engine-" in n and n.endswith(".jar"))
ez = zipfile.ZipFile(io.BytesIO(z.read(jar)))
props = ez.read("com/arcadedb/arcadedb.properties").decode()
got = next(l.split("=",1)[1].strip() for l in props.splitlines()
           if l.strip().startswith("buildNumber"))
print(f"    wheel jars buildNumber = {got[:9]}")
if got != want:
    print(f"    MISMATCH: wanted {want[:9]}"); sys.exit(1)
PY
say "wheel verified at ${SHA:0:9}"
echo "PAIR_WHEEL=$W"
