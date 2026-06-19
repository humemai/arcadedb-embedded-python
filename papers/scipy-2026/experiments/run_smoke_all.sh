#!/usr/bin/env bash
# Build a per-backend Docker image and run its smoke test, one at a time.
# Versions are unpinned here (latest) just to verify each runs; we pin once
# the resolved versions are recorded.
set -u
cd "$(dirname "$0")"

# backend : pip packages : smoke script
BACKENDS=(
  "arcadedb:arcadedb-embedded==26.6.1 numpy:smoke_arcadedb.py"
  "sqlite::smoke_sqlite.py"
  "duckdb:duckdb:smoke_duckdb.py"
  "kuzu:kuzu:smoke_kuzu.py"
  "chroma:chromadb numpy:smoke_chroma.py"
  "faiss:faiss-cpu numpy:smoke_faiss.py"
)

pass=0; fail=0
for entry in "${BACKENDS[@]}"; do
  be="${entry%%:*}"; rest="${entry#*:}"; pkgs="${rest%%:*}"; script="${rest#*:}"
  echo "============================================================"
  echo "### $be   (pip: ${pkgs:-<stdlib>})"
  echo "============================================================"
  if ! docker build -q -t "scipy-bench:$be" --build-arg PIP_PACKAGES="$pkgs" -f docker/Dockerfile . >/dev/null; then
    echo "BUILD FAILED: $be"; fail=$((fail+1)); continue
  fi
  out="$(docker run --rm -v "$PWD":/work -w /work "scipy-bench:$be" python "$script" 2>&1)"; rc=$?
  # show only the meaningful lines (drop JVM/INFO noise)
  echo "$out" | grep -vE '^\s*$|INFO |WARNI |WARNING|incubator' | tail -10
  if [ $rc -eq 0 ] && echo "$out" | grep -q 'SMOKE OK'; then
    echo "[$be] PASS"; pass=$((pass+1))
  else
    echo "[$be] FAIL (rc=$rc)"; fail=$((fail+1))
  fi
done

echo "============================================================"
echo "SUMMARY: $pass passed, $fail failed"
