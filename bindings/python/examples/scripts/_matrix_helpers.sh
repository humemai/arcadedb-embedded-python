#!/usr/bin/env bash
set -euo pipefail

matrix_log() {
    echo "[matrix] $*"
}

matrix_resolve_latest_pypi_version() {
    local package_name="$1"
    python3 - "$package_name" << 'PY'
import json
import sys
import urllib.request

package = sys.argv[1]
url = f"https://pypi.org/pypi/{package}/json"
with urllib.request.urlopen(url, timeout=30) as response:
    payload = json.load(response)
version = payload.get("info", {}).get("version")
if not version:
    raise SystemExit(f"No version found on PyPI for package: {package}")
print(version)
PY
}

matrix_resolve_version() {
    local requested="$1"
    local package_name="$2"

    if [[ -z "$requested" || "$requested" == "latest" ]]; then
        matrix_resolve_latest_pypi_version "$package_name"
        return
    fi

    echo "$requested"
}

matrix_prepare_local_arcadedb_wheel() {
    local examples_dir="$1"
    local platform="${2:-linux/amd64}"

    if ! command -v docker > /dev/null 2>&1; then
        echo "docker is required to build local arcadedb wheel" >&2
        return 1
    fi

    if ! command -v uv > /dev/null 2>&1; then
        echo "uv is required to install local arcadedb wheel" >&2
        return 1
    fi

    local py_bindings_dir
    py_bindings_dir="$(cd "$examples_dir/.." && pwd)"

    local python_version
    python_version="$(
        python3 - << 'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
    )"

    matrix_log "Building local arcadedb wheel from source (platform=$platform, python=$python_version)"
    (
        cd "$py_bindings_dir"
        ./build.sh "$platform" "$python_version"
    )

    local wheel_path
    wheel_path="$(ls -1t "$py_bindings_dir"/dist/*.whl | head -n 1)"
    if [[ -z "$wheel_path" || ! -f "$wheel_path" ]]; then
        echo "No wheel produced under $py_bindings_dir/dist" >&2
        return 1
    fi

    local wheel_name
    wheel_name="$(basename "$wheel_path")"

    matrix_log "Installing local wheel with uv: $wheel_name"
    if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
        uv pip install --python "${VIRTUAL_ENV}/bin/python" --force-reinstall "$wheel_path"
    else
        uv pip install --python "$(command -v python3)" --user --force-reinstall "$wheel_path"
    fi

    matrix_log "Removing local wheel artifact after install: $wheel_name"
    rm -f "$wheel_path"

    local arcadedb_tag
    arcadedb_tag="$(python3 "$py_bindings_dir/extract_version.py" --format=docker)"

    matrix_log "Resolving ArcadeDB image digest for arcadedata/arcadedb:$arcadedb_tag"
    docker pull "arcadedata/arcadedb:$arcadedb_tag" > /dev/null

    local image_digest
    image_digest="$(docker inspect --format='{{index .RepoDigests 0}}' "arcadedata/arcadedb:$arcadedb_tag" 2> /dev/null || true)"

    local wheel_version
    wheel_version="$(
        python3 - << 'PY'
import arcadedb_embedded
print(getattr(arcadedb_embedded, '__version__', 'unknown'))
PY
    )"

    export MATRIX_WHEEL_PATH=""
    export MATRIX_WHEEL_FILE="$wheel_name"
    export MATRIX_WHEEL_VERSION="$wheel_version"
    export MATRIX_ARCADEDB_DOCKER_TAG="$arcadedb_tag"
    export MATRIX_ARCADEDB_IMAGE_DIGEST="$image_digest"

    matrix_log "Local wheel ready: version=$MATRIX_WHEEL_VERSION tag=$MATRIX_ARCADEDB_DOCKER_TAG digest=${MATRIX_ARCADEDB_IMAGE_DIGEST:-unknown}"
}

matrix_write_wheel_metadata() {
    local target_dir="$1"
    local collected_at="$2"
    local copy_artifacts="${3:-true}"

    if [[ -z "${MATRIX_WHEEL_FILE:-}" ]]; then
        return 0
    fi

    local wheel_name
    wheel_name="$MATRIX_WHEEL_FILE"

    if [[ "$copy_artifacts" == "true" ]]; then
        cat > "$target_dir/arcadedb_wheel_build.json" << EOF
{
  "wheel_file": "$wheel_name",
  "wheel_version": "${MATRIX_WHEEL_VERSION:-unknown}",
  "wheel_source": "local_bindings_source",
  "arcadedb_docker_tag": "${MATRIX_ARCADEDB_DOCKER_TAG:-unknown}",
  "arcadedb_docker_digest": "${MATRIX_ARCADEDB_IMAGE_DIGEST:-unknown}",
  "collected_at_utc": "$collected_at"
}
EOF
    fi
}

matrix_embed_wheel_metadata_in_results() {
    local target_dir="$1"
    local collected_at="$2"

    if [[ ! -d "$target_dir" ]]; then
        return 0
    fi

    python3 - "$target_dir" "$collected_at" << 'PY'
import glob
import json
import os
import pathlib
import sys

target_dir = pathlib.Path(sys.argv[1])
collected_at = sys.argv[2]

wheel_path = os.environ.get("MATRIX_WHEEL_PATH", "")
wheel_file = os.environ.get("MATRIX_WHEEL_FILE")
if not wheel_file and wheel_path:
    wheel_file = pathlib.Path(wheel_path).name

metadata = {
    "wheel_file": wheel_file,
    "wheel_version": os.environ.get("MATRIX_WHEEL_VERSION", "unknown"),
    "wheel_source": "local_bindings_source",
    "arcadedb_docker_tag": os.environ.get("MATRIX_ARCADEDB_DOCKER_TAG", "unknown"),
    "arcadedb_docker_digest": os.environ.get("MATRIX_ARCADEDB_IMAGE_DIGEST", "unknown"),
    "collected_at_utc": collected_at,
}

for result_path in sorted(glob.glob(str(target_dir / "results_*.json"))):
    p = pathlib.Path(result_path)
    try:
        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        print(f"[matrix] warning: cannot parse {p}: {exc}", file=sys.stderr)
        continue

    payload["arcadedb_wheel_metadata"] = metadata
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
PY
}

matrix_write_dependency_versions() {
    local target_dir="$1"
    local collected_at="$2"
    shift 2

    cat > "$target_dir/dependency_versions.json" << EOF
{
  "collected_at_utc": "$collected_at",
EOF

    local first=true
    while [[ $# -gt 0 ]]; do
        local key="$1"
        local value="$2"
        shift 2

        if [[ "$first" == true ]]; then
            first=false
        else
            echo "," >> "$target_dir/dependency_versions.json"
        fi

        printf '  "%s": "%s"' "$key" "$value" >> "$target_dir/dependency_versions.json"
    done

    echo "" >> "$target_dir/dependency_versions.json"
    echo "}" >> "$target_dir/dependency_versions.json"
}
