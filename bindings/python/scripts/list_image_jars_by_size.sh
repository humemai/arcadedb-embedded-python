#!/usr/bin/env bash
set -euo pipefail

# List ArcadeDB JARs ordered by size, from an arcadedata/arcadedb image or from a
# lib directory (a source build's, such as
# package/target/arcadedb-<version>.dir/arcadedb-<version>/lib, or the
# arcadedb-lib artifact of build-engine-jars.yml).
# Usage:
#   ./scripts/list_image_jars_by_size.sh [IMAGE_TAG | LIB_DIR]
#   ./scripts/list_image_jars_by_size.sh latest
#   ./scripts/list_image_jars_by_size.sh ../../package/target/arcadedb-26.10.1-SNAPSHOT.dir/arcadedb-26.10.1-SNAPSHOT/lib
# With no argument, the image tagged with the pom.xml version.

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IMAGE_TAG="${1:-}"

print_by_size() {
    # Columns: size_bytes  size_human  jar_name
    find "$1" -maxdepth 1 -type f -name "*.jar" -printf "%s\t%p\n" |
        sort -nr |
        awk -F'\t' '{
      size=$1; path=$2; name=path; sub(/^.*\//,"",name);
      # human-readable size
      split("B KB MB GB TB", units, " ");
      s=size; u=1; while (s>=1024 && u<5) {s/=1024; u++;}
      printf "%12d\t%8.1f %s\t%s\n", size, s, units[u], name;
    }'
}

# A directory is listed as it is; anything else is an image tag.
if [[ -n "$IMAGE_TAG" && -d "$IMAGE_TAG" ]]; then
    if ! find "$IMAGE_TAG" -maxdepth 1 -name "*.jar" -print -quit | grep -q .; then
        echo "No JAR files in ${IMAGE_TAG}" >&2
        exit 1
    fi
    print_by_size "$IMAGE_TAG"
    exit 0
fi
if [[ "$IMAGE_TAG" == */* ]]; then
    echo "No such lib directory: ${IMAGE_TAG} (an image tag has no '/')" >&2
    exit 1
fi

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
print_by_size "$TMP_DIR/lib"
