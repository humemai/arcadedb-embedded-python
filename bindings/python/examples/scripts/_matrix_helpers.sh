#!/usr/bin/env bash
set -euo pipefail

matrix_log() {
    echo "[matrix] $*"
}

matrix_normalize_mem_tag() {
    local raw="${1:-}"
    raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
    if [[ -z "$raw" ]]; then
        return 1
    fi

    if [[ "$raw" == mem* ]]; then
        printf '%s\n' "$raw"
        return 0
    fi

    if [[ "$raw" == m[0-9]* ]]; then
        printf 'mem%s\n' "${raw#m}"
        return 0
    fi

    printf 'mem%s\n' "$raw"
}

matrix_build_summary_run_label() {
    local internal_run_label="$1"
    local mem_limit="$2"
    local mem_tag
    mem_tag="$(matrix_normalize_mem_tag "$mem_limit")" || return 1

    local base_label="$internal_run_label"
    # Ensure idempotent normalization: if label already has trailing mem tokens
    # (possibly duplicated by previous runs), strip them before appending.
    while [[ "$base_label" =~ _((mem|m)[[:alnum:]]+|memory)$ ]]; do
        base_label="${base_label%_${BASH_REMATCH[1]}}"
    done

    printf '%s_%s\n' "$base_label" "$mem_tag"
}

matrix_rewrite_json_run_label() {
    local target_dir="$1"
    local old_label="$2"
    local new_label="$3"

    if [[ ! -d "$target_dir" || -z "$old_label" || -z "$new_label" || "$old_label" == "$new_label" ]]; then
        return 0
    fi

    python3 - "$target_dir" "$old_label" "$new_label" << 'PY'
import glob
import json
import pathlib
import sys

target_dir = pathlib.Path(sys.argv[1])
old_label = sys.argv[2]
new_label = sys.argv[3]
label_keys = {"run_label", "search_run_label"}


def rewrite_labels(value):
    changed = False

    if isinstance(value, dict):
        updated = {}
        for key, item in value.items():
            if key in label_keys and item == old_label:
                updated[key] = new_label
                changed = True
            else:
                updated_item, item_changed = rewrite_labels(item)
                updated[key] = updated_item
                changed = changed or item_changed
        return updated, changed

    if isinstance(value, list):
        updated = []
        for item in value:
            updated_item, item_changed = rewrite_labels(item)
            updated.append(updated_item)
            changed = changed or item_changed
        return updated, changed

    return value, False


for pattern in ("results_*.json", "search_results_*.json"):
    for path_str in sorted(glob.glob(str(target_dir / pattern))):
        path = pathlib.Path(path_str)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        payload, changed = rewrite_labels(payload)
        if not changed:
            continue

        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

matrix_rename_result_artifacts() {
    local target_dir="$1"
    local old_label="$2"
    local new_label="$3"

    if [[ ! -d "$target_dir" || -z "$old_label" || -z "$new_label" || "$old_label" == "$new_label" ]]; then
        return 0
    fi

    local old_results="$target_dir/results_${old_label}.json"
    local new_results="$target_dir/results_${new_label}.json"
    if [[ -f "$old_results" && ! -e "$new_results" ]]; then
        mv "$old_results" "$new_results"
    fi

    local old_search_results="$target_dir/search_results_${old_label}.json"
    local new_search_results="$target_dir/search_results_${new_label}.json"
    if [[ -f "$old_search_results" && ! -e "$new_search_results" ]]; then
        mv "$old_search_results" "$new_search_results"
    fi
}

matrix_move_dir_if_needed() {
    local old_dir="$1"
    local new_dir="$2"

    if [[ -z "$old_dir" || -z "$new_dir" || "$old_dir" == "$new_dir" || ! -d "$old_dir" ]]; then
        return 0
    fi

    if [[ -e "$new_dir" ]]; then
        echo "Refusing to rename '$old_dir' to existing path '$new_dir'" >&2
        return 1
    fi

    mv "$old_dir" "$new_dir"
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

matrix_http_json_value() {
    local url="$1"
    local python_expr="$2"

    python3 - "$url" "$python_expr" << 'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
python_expr = sys.argv[2]
req = urllib.request.Request(url, headers={"User-Agent": "arcadedb-bench"})
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.load(response)

namespace = {"payload": payload}
value = eval(python_expr, {"__builtins__": {}}, namespace)
if value in (None, ""):
    raise SystemExit(f"No value found for expression: {python_expr}")
print(value)
PY
}

matrix_resolve_latest_pgvector_image() {
    python3 - << 'PY'
import json
import re
import urllib.request

url = 'https://hub.docker.com/v2/repositories/pgvector/pgvector/tags?page_size=100'
req = urllib.request.Request(url, headers={'User-Agent': 'arcadedb-bench'})
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.load(response)

pattern = re.compile(r'^pg(\d+)-trixie$')
best = None
for item in payload.get('results', []):
    tag = str(item.get('name') or '')
    match = pattern.match(tag)
    if not match:
        continue
    major = int(match.group(1))
    candidate = (major, tag)
    if best is None or candidate > best:
        best = candidate

if best is None:
    raise SystemExit('Could not resolve latest pgvector pgN-trixie tag from Docker Hub')

print(f'pgvector/pgvector:{best[1]}')
PY
}

matrix_resolve_pgvector_image() {
    local requested="${1:-}"
    if [[ -z "$requested" || "$requested" == "latest" || "$requested" == "pgvector/pgvector:latest" ]]; then
        matrix_resolve_latest_pgvector_image
        return
    fi

    echo "$requested"
}

matrix_resolve_qdrant_image() {
    local requested="${1:-}"
    if [[ -z "$requested" || "$requested" == "latest" ]]; then
        echo "qdrant/qdrant:latest"
        return
    fi

    echo "$requested"
}

matrix_resolve_milvus_compose_version() {
    local requested="${1:-}"
    if [[ -z "$requested" || "$requested" == "latest" ]]; then
        matrix_http_json_value \
            "https://api.github.com/repos/milvus-io/milvus/releases/latest" \
            "payload.get('tag_name')"
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

    matrix_log "Keeping local wheel artifact for Docker-wrapped example runs: $wheel_name"

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

    export MATRIX_WHEEL_PATH="$wheel_path"
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

        if [[ "$value" == "auto" ]]; then
            continue
        fi

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
