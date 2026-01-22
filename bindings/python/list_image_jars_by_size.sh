#!/usr/bin/env bash
set -euo pipefail

# List JARs from the latest ArcadeDB Docker image (arcadedata/arcadedb) ordered by size.
# Usage:
#   ./list_image_jars_by_size.sh [IMAGE_TAG]
#   ./list_image_jars_by_size.sh latest

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IMAGE_TAG="${1:-}"

if [[ -z "$IMAGE_TAG" ]]; then
    if [[ -f "$SCRIPT_DIR/extract_version.py" ]]; then
        IMAGE_TAG=$(python3 "$SCRIPT_DIR/extract_version.py" --format=docker)
    else
        echo "extract_version.py not found; pass an explicit image tag." >&2
        exit 1
    fi
fi

IMAGE="arcadedata/arcadedb:${IMAGE_TAG}"

if ! command -v docker > /dev/null 2>&1; then
    echo "Docker is required to list jars from the image." >&2
    exit 1
fi

TMP_DIR=$(mktemp -d)
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

CONTAINER_ID=$(docker create "$IMAGE")
if [[ -z "$CONTAINER_ID" ]]; then
    echo "Failed to create container from ${IMAGE}" >&2
    exit 1
fi

# Copy JARs from the image
mkdir -p "$TMP_DIR/lib"
docker cp "${CONTAINER_ID}:/home/arcadedb/lib/." "$TMP_DIR/lib" > /dev/null
docker rm "$CONTAINER_ID" > /dev/null

# Print jars ordered by size (largest first)
# Columns: size_bytes  size_human  jar_name
find "$TMP_DIR/lib" -maxdepth 1 -type f -name "*.jar" -printf "%s\t%p\n" |
    sort -nr |
    awk -F'\t' '{
      size=$1; path=$2; name=path; sub(/^.*\//,"",name);
      # human-readable size
      split("B KB MB GB TB", units, " ");
      s=size; u=1; while (s>=1024 && u<5) {s/=1024; u++;}
      printf "%12d\t%8.1f %s\t%s\n", size, s, units[u], name;
    }'
