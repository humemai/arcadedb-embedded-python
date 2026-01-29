#!/usr/bin/env bash
# End-to-end helper to rebuild ArcadeDB JARs (via Docker Maven),
# stage them for the Python wheel, build the wheel, and install it with uv.
# Usage: run from any directory: ./bindings/python/build_and_install.sh

set -euo pipefail

log() {
    echo "[build] $*" >&2
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PY_BINDINGS_DIR="${REPO_ROOT}/bindings/python"
LOCAL_JARS_DIR="${PY_BINDINGS_DIR}/local-jars/lib"

log "Repo root: ${REPO_ROOT}"

# 1) Build ArcadeDB JARs in Docker (Java 25)
log "Building ArcadeDB JARs via Docker Maven..."
docker run --rm \
    -v "${REPO_ROOT}":/src \
    -w /src \
    maven:3.9-amazoncorretto-25 \
    sh -c "git config --global --add safe.directory /src && ./mvnw -DskipTests -pl package -am package"

# 2) Copy freshly built JARs into local-jars for the Python build
log "Staging JARs into bindings/python/local-jars/lib..."
mkdir -p "${LOCAL_JARS_DIR}"
HEADLESS_LIB_DIR="${REPO_ROOT}/package/target/arcadedb-26.1.1-SNAPSHOT-headless.dir/arcadedb-26.1.1-SNAPSHOT/lib"
if [[ ! -d "${HEADLESS_LIB_DIR}" ]]; then
    echo "❌ Headless package lib directory not found at ${HEADLESS_LIB_DIR}" >&2
    exit 1
fi
cp "${HEADLESS_LIB_DIR}"/*.jar "${LOCAL_JARS_DIR}/"
log "Copied $(ls -1 "${LOCAL_JARS_DIR}" | wc -l) JARs into local stash"

# 3) Build the Python wheel (defaults to linux/amd64 + Python 3.12) using staged JARs
#    For Windows or macOS, run this script on that OS and update the platform accordingly.
log "Building Python wheel with local JARs..."
cd "${PY_BINDINGS_DIR}"
./build.sh linux/amd64 3.12 "${LOCAL_JARS_DIR}"

# 4) Install the wheel with uv (force reinstall)
log "Installing wheel via uv pip..."
WHEEL_PATH=$(ls -1 dist/arcadedb_embedded-*-linux_x86_64.whl | sort | tail -n 1)
if [[ -z "${WHEEL_PATH}" ]]; then
    echo "❌ No wheel found in dist/. Did the build succeed?" >&2
    exit 1
fi
uv pip install --force-reinstall "${WHEEL_PATH}"
log "Installed ${WHEEL_PATH}"

log "All done."
