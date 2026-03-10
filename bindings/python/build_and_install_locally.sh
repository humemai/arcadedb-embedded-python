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
    sh -c "if ! command -v git >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1; then \
        if command -v yum >/dev/null 2>&1; then \
            yum -y install git tar; \
        elif command -v apt-get >/dev/null 2>&1; then \
            apt-get update && apt-get install -y git tar; \
        else \
            echo '❌ git/tar not found and no supported package manager (yum/apt-get) available' >&2; \
            exit 1; \
        fi; \
    fi; \
    git config --global --add safe.directory /src && ./mvnw -DskipTests -pl package -am package"

# 2) Copy freshly built JARs into local-jars for the Python build
log "Staging JARs into bindings/python/local-jars/lib..."
mkdir -p "${LOCAL_JARS_DIR}"
HEADLESS_PARENT_DIR=$(ls -d "${REPO_ROOT}/package/target/arcadedb-"*-headless.dir 2> /dev/null | sort | tail -n 1)
if [[ -z "${HEADLESS_PARENT_DIR}" ]]; then
    echo "❌ Headless package directory not found under ${REPO_ROOT}/package/target" >&2
    exit 1
fi
HEADLESS_LIB_DIR=$(ls -d "${HEADLESS_PARENT_DIR}"/arcadedb-*/lib 2> /dev/null | sort | tail -n 1)
if [[ -z "${HEADLESS_LIB_DIR}" || ! -d "${HEADLESS_LIB_DIR}" ]]; then
    echo "❌ Headless package lib directory not found under ${HEADLESS_PARENT_DIR}" >&2
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
WHEEL_PATH=$(ls -1 dist/arcadedb_embedded-*.whl | sort | tail -n 1)
if [[ -z "${WHEEL_PATH}" ]]; then
    echo "❌ No wheel found in dist/. Did the build succeed?" >&2
    exit 1
fi
uv pip install --force-reinstall "${WHEEL_PATH}"
log "Installed ${WHEEL_PATH}"

log "All done."
