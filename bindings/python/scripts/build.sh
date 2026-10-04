#!/bin/bash
# ArcadeDB Python Package Build Script
# Builds arcadedb-embedded with a bundled JRE (no Java install needed).
#
# Where the engine JARs come from, in order:
#   1) --engine-from-source: build the full distribution from this checkout's
#      engine source in a Maven container (maven:3.9-eclipse-temurin-21, the
#      JDK upstream's images are built with), then embed its lib directory.
#      This is what CI tests by default. ENGINE_BUILD_CPUSET pins the
#      container to a cpuset (none by default; the maintainer's laptop builds
#      on its low-power cores with ENGINE_BUILD_CPUSET=12-15).
#   2) A JAR directory (third argument, JAR_LIB_DIR): embed those JARs, for
#      example the full assembly's lib directory of an engine you built:
#        ./scripts/build.sh linux/amd64 3.12 ../../package/target/arcadedb-<version>.dir/arcadedb-<version>/lib
#   3) Neither: copy the JARs out of the arcadedata/arcadedb image, tagged with
#      the pom.xml version or ARCADEDB_IMAGE_TAG (the local default).

set -euo pipefail

# Stamped before anything is built, so the wheel check at the end can ask
# whether an artifact is newer than this run rather than merely present.
# A marker file rather than an epoch: `test -nt` is portable, while
# `find -newermt` is GNU-only and this script also runs on macOS hosts.
BUILD_START_MARKER=$(mktemp -t arcadedb-build-start.XXXXXX)
trap 'rm -f "$BUILD_START_MARKER"' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_BINDINGS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$PY_BINDINGS_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line arguments: options anywhere, then up to three positionals.
# Kept to bash 3.2, which macOS runs this under as /bin/bash.
PLATFORM=""
PYTHON_VERSION=""
JAR_LIB_DIR=""
ENGINE_FROM_SOURCE=0
SHOW_HELP=0
BAD_ARG=""
POSITIONAL_COUNT=0
for arg in "$@"; do
    case "$arg" in
        --engine-from-source) ENGINE_FROM_SOURCE=1 ;;
        -h | --help) SHOW_HELP=1 ;;
        -*) BAD_ARG="$arg" ;;
        *)
            POSITIONAL_COUNT=$((POSITIONAL_COUNT + 1))
            case "$POSITIONAL_COUNT" in
                1) PLATFORM="$arg" ;;
                2) PYTHON_VERSION="$arg" ;;
                3) JAR_LIB_DIR="$arg" ;;
                *) BAD_ARG="$arg" ;;
            esac
            ;;
    esac
done
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🎮 ArcadeDB Python Package - Build Script                 ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 [--engine-from-source] [PLATFORM] [PYTHON_VERSION] [JAR_LIB_DIR]"
    echo ""
    echo "Builds arcadedb-embedded package with bundled JRE"
    echo "No external Java installation required!"
    echo ""
    echo "PLATFORM:"
    echo "  Auto-detected if not specified"
    echo "  linux/amd64    Linux x86_64 (Docker build)"
    echo "  linux/arm64    Linux ARM64 (Docker build, native ARM64 runner)"
    echo "  darwin/arm64   macOS ARM64 Apple Silicon (native build on macOS)"
    echo "  windows/amd64  Windows x86_64 (native build on Windows)"
    echo ""
    echo "PYTHON_VERSION:"
    echo "  Python version for wheel (default: 3.12); used by Linux (Docker) builds only"
    echo "  Examples: 3.10, 3.11, 3.12, 3.13, 3.14"
    echo ""
    echo "JAR_LIB_DIR (optional):"
    echo "  Directory containing ArcadeDB JARs to embed"
    echo "  If omitted (and no --engine-from-source), JARs are copied from"
    echo "  arcadedata/arcadedb:<tag>, where <tag> is ARCADEDB_IMAGE_TAG or the pom.xml version"
    echo ""
    echo "--engine-from-source:"
    echo "  Build the full ArcadeDB distribution from this checkout's engine source"
    echo "  (./mvnw -DskipTests -pl package -am clean package in maven:3.9-eclipse-temurin-21,"
    echo "  needs Docker) and embed its lib directory. This is what CI tests by default."
    echo "  ENGINE_BUILD_CPUSET=<cpus>  pin the Maven container (default: no pin)"
    echo "  ENGINE_BUILD_IMAGE=<image>  Maven image (default: maven:3.9-eclipse-temurin-21)"
    echo "  ENGINE_BUILD_M2=<dir>       Maven repository to mount (default: ~/.m2)"
    echo ""
    echo "Build Methods:"
    echo "  Native: macOS/Windows build on matching native host architecture"
    echo "  Docker: Linux uses Docker for manylinux compliance"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Build for current platform with Python 3.12"
    echo "  $0 linux/amd64                        # Build for Linux x86_64 with Python 3.12 (Docker)"
    echo "  $0 linux/amd64 3.11                   # Build for Linux x86_64 with Python 3.11 (Docker)"
    echo "  $0 linux/amd64 3.12 /path/to/jars     # Build using JARs from /path/to/jars"
    echo "  $0 --engine-from-source linux/amd64   # Build the engine from source, then the wheel"
    echo "  ARCADEDB_IMAGE_TAG=26.9.1 $0          # Build with the official 26.9.1 image's JARs"
    echo "  $0 darwin/arm64                       # Build for macOS ARM64 (native; uses the first Python with a working build module)"
    echo ""
    echo "Package features:"
    echo "  ✅ Bundled platform-specific JRE (no Java required)"
    echo "  ✅ Optimized JAR selection (see scripts/jar_exclusions.txt)"
    echo "  ✅ Multi-platform support (4 platforms)"
    echo "  📦 Size varies by platform/version; see CI summaries for current numbers"
    echo ""
}

normalize_arch() {
    case "$1" in
        x86_64 | amd64)
            echo "amd64"
            ;;
        aarch64 | arm64)
            echo "arm64"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

# Check for help flag
if [[ "$SHOW_HELP" == 1 ]]; then
    print_header
    print_usage
    exit 0
fi
if [[ -n "$BAD_ARG" ]]; then
    echo -e "${RED}❌ Unexpected argument: ${BAD_ARG}${NC}"
    print_usage
    exit 1
fi
if [[ "$ENGINE_FROM_SOURCE" == 1 && -n "$JAR_LIB_DIR" ]]; then
    echo -e "${RED}❌ --engine-from-source and JAR_LIB_DIR both name the JARs; pass one${NC}"
    exit 1
fi

print_header

# Auto-detect platform if not specified
if [[ -z "$PLATFORM" ]]; then
    echo -e "${CYAN}🔍 Auto-detecting platform...${NC}"
    OS="$(uname -s)"
    ARCH="$(uname -m)"

    case "${OS}" in
        Linux*)
            PLATFORM_OS="linux"
            ;;
        Darwin*)
            PLATFORM_OS="darwin"
            ;;
        MINGW* | MSYS* | CYGWIN*)
            PLATFORM_OS="windows"
            ;;
        *)
            echo -e "${RED}❌ Unsupported OS: ${OS}${NC}"
            exit 1
            ;;
    esac

    case "${ARCH}" in
        x86_64 | amd64)
            PLATFORM_ARCH="amd64"
            ;;
        aarch64 | arm64)
            PLATFORM_ARCH="arm64"
            ;;
        *)
            echo -e "${RED}❌ Unsupported architecture: ${ARCH}${NC}"
            exit 1
            ;;
    esac

    PLATFORM="${PLATFORM_OS}/${PLATFORM_ARCH}"
    echo -e "${CYAN}✅ Detected platform: ${YELLOW}${PLATFORM}${NC}"
    echo ""
fi

# Auto-detect the version from pom.xml. POM_TAG names the version this source
# tree builds (and the wheel); DOCKER_TAG names the arcadedata/arcadedb image the
# build reads, which is the same unless ARCADEDB_IMAGE_TAG picks another (for
# example the official release image while pom.xml reads the next -SNAPSHOT).
echo -e "${CYAN}🔍 Detecting version from pom.xml...${NC}"
POM_TAG=$(python3 "$SCRIPT_DIR/extract_version.py" --format=docker)
DOCKER_TAG="${ARCADEDB_IMAGE_TAG:-$POM_TAG}"
echo -e "${CYAN}📌 pom.xml version: ${YELLOW}${POM_TAG}${NC}"
echo -e "${CYAN}📌 Docker tag: ${YELLOW}${DOCKER_TAG}${NC}"
echo ""

# --engine-from-source: build the full distribution from this checkout, then
# hand its lib directory to the JAR_LIB_DIR path below, exactly as a directory
# passed by hand. The same build CI runs (.github/workflows/build-engine-jars.yml):
# the package module and everything it needs, tests skipped, on JDK 21.
if [[ "$ENGINE_FROM_SOURCE" == 1 ]]; then
    REPO_ROOT="$(cd "$PY_BINDINGS_DIR/../.." && pwd)"
    if [[ ! -f "$REPO_ROOT/pom.xml" || ! -x "$REPO_ROOT/mvnw" ]]; then
        echo -e "${RED}❌ No pom.xml and mvnw at ${REPO_ROOT}; --engine-from-source needs the full repository${NC}"
        exit 1
    fi
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ --engine-from-source builds in a Maven container and needs Docker${NC}"
        exit 1
    fi
    ENGINE_BUILD_IMAGE="${ENGINE_BUILD_IMAGE:-maven:3.9-eclipse-temurin-21}"
    ENGINE_BUILD_M2="${ENGINE_BUILD_M2:-$HOME/.m2}"
    mkdir -p "$ENGINE_BUILD_M2"
    ENGINE_DOCKER_ARGS="--rm --user $(id -u):$(id -g) -e HOME=/tmp/h -e MAVEN_OPTS=-Duser.home=/tmp/h"
    if [[ -n "${ENGINE_BUILD_CPUSET:-}" ]]; then
        ENGINE_DOCKER_ARGS="$ENGINE_DOCKER_ARGS --cpuset-cpus ${ENGINE_BUILD_CPUSET}"
    fi
    # The engine stamps its build with the checked-out commit (buildNumber in
    # com/arcadedb/arcadedb.properties). In a git worktree the commit lives in
    # the main repository's .git, so that is mounted too.
    GIT_COMMON_DIR=$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir 2> /dev/null || true)
    GIT_MOUNT=()
    if [[ -n "$GIT_COMMON_DIR" && "$GIT_COMMON_DIR" != "$REPO_ROOT"/* ]]; then
        GIT_MOUNT=(-v "$GIT_COMMON_DIR:$GIT_COMMON_DIR")
    fi
    ENGINE_COMMIT=$(git -C "$REPO_ROOT" rev-parse --short=10 HEAD 2> /dev/null || echo "unknown commit")
    echo -e "${CYAN}🔨 Building the engine distribution from source (${ENGINE_COMMIT}) in ${YELLOW}${ENGINE_BUILD_IMAGE}${CYAN}${ENGINE_BUILD_CPUSET:+ on cpus ${ENGINE_BUILD_CPUSET}}...${NC}"
    # shellcheck disable=SC2086 # ENGINE_DOCKER_ARGS is a list of options
    docker run $ENGINE_DOCKER_ARGS \
        -v "$ENGINE_BUILD_M2:/tmp/h/.m2" \
        -v "$REPO_ROOT:$REPO_ROOT" \
        ${GIT_MOUNT[@]+"${GIT_MOUNT[@]}"} \
        -w "$REPO_ROOT" \
        "$ENGINE_BUILD_IMAGE" \
        ./mvnw -B -q -DskipTests -pl package -am clean package
    # The FULL distribution, for this pom.xml version. The base, headless, and
    # minimal variants sit beside it as arcadedb-<version>-<variant>.dir and
    # lack the plugins (no Gremlin, Bolt, wire protocols, GraphQL, metrics, or
    # tracing), so the lib is named exactly rather than globbed.
    ENGINE_LIB="$REPO_ROOT/package/target/arcadedb-${POM_TAG}.dir/arcadedb-${POM_TAG}/lib"
    if [[ ! -d "$ENGINE_LIB" ]]; then
        echo -e "${RED}❌ The build left no full-distribution lib at ${ENGINE_LIB}${NC}"
        exit 1
    fi
    if ! ls "$ENGINE_LIB"/arcadedb-gremlin-*.jar > /dev/null 2>&1; then
        echo -e "${RED}❌ ${ENGINE_LIB} has no Gremlin plugin jar, so it is not the full distribution${NC}"
        exit 1
    fi
    JAR_LIB_DIR="$ENGINE_LIB"
    echo -e "${GREEN}✅ Engine built: $(find "$ENGINE_LIB" -maxdepth 1 -name '*.jar' | wc -l | tr -d ' ') JARs in ${ENGINE_LIB}${NC}"
    echo ""
fi

# Select jar source: explicit directory when provided; otherwise pull from ArcadeDB image
LOCAL_JARS_DIR="$PY_BINDINGS_DIR/local-jars/lib"
USE_LOCAL_JARS_ARG=""
LOCAL_JARS_HASH_ARG=""
JAR_SOURCE_DESC="arcadedata/arcadedb:${DOCKER_TAG} image"
mkdir -p "$LOCAL_JARS_DIR"

if [[ -n "$JAR_LIB_DIR" ]]; then
    if [[ ! -d "$JAR_LIB_DIR" ]]; then
        echo -e "${RED}❌ JAR_LIB_DIR not found: ${JAR_LIB_DIR}${NC}"
        exit 1
    fi

    if ! find "$JAR_LIB_DIR" -maxdepth 1 -name "*.jar" -print -quit | grep -q .; then
        echo -e "${RED}❌ No JAR files found in: ${JAR_LIB_DIR}${NC}"
        exit 1
    fi

    JAR_LIB_DIR_REAL=$(realpath "$JAR_LIB_DIR")
    LOCAL_JARS_REAL=$(realpath "$LOCAL_JARS_DIR")

    if [[ "$JAR_LIB_DIR_REAL" == "$LOCAL_JARS_REAL" ]]; then
        echo -e "${CYAN}📦 Using pre-staged JARs in: ${YELLOW}${JAR_LIB_DIR}${NC}"
        JAR_SOURCE_DESC="${JAR_LIB_DIR} (pre-staged)"
    else
        echo -e "${CYAN}📦 Using provided JAR directory: ${YELLOW}${JAR_LIB_DIR}${NC}"
        rm -rf "$LOCAL_JARS_DIR"
        mkdir -p "$LOCAL_JARS_DIR"
        cp -a "$JAR_LIB_DIR"/*.jar "$LOCAL_JARS_DIR"/
        JAR_SOURCE_DESC="${JAR_LIB_DIR} (staged into local-jars)"
    fi
    if [[ "$ENGINE_FROM_SOURCE" == 1 ]]; then
        JAR_SOURCE_DESC="engine built from source at ${ENGINE_COMMIT} (${JAR_LIB_DIR})"
    fi

    USE_LOCAL_JARS_ARG="--build-arg USE_LOCAL_JARS=1"
    LOCAL_JARS_HASH=$(find "$LOCAL_JARS_DIR" -maxdepth 1 -name "*.jar" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
    LOCAL_JARS_HASH_ARG="--build-arg LOCAL_JARS_HASH=${LOCAL_JARS_HASH}"
else
    echo -e "${CYAN}📦 Using JARs from ArcadeDB image (no JAR_LIB_DIR provided)${NC}"
fi

# Determine build method: native or Docker
# Use native build if we're already on the target platform
CURRENT_OS="$(uname -s)"
CURRENT_ARCH="$(uname -m)"
CURRENT_ARCH_NORMALIZED="$(normalize_arch "$CURRENT_ARCH")"
TARGET_OS="${PLATFORM%%/*}"
TARGET_ARCH="${PLATFORM##*/}"

USE_NATIVE=false
if [[ "$TARGET_OS" == "darwin" ]]; then
    if [[ "$CURRENT_OS" != "Darwin" ]]; then
        echo -e "${RED}❌ ${PLATFORM} builds require a native macOS host${NC}"
        echo -e "${YELLOW}💡 jlink can only create a macOS JRE when run on macOS${NC}"
        exit 1
    fi
    if [[ "$CURRENT_ARCH_NORMALIZED" != "$TARGET_ARCH" ]]; then
        echo -e "${RED}❌ ${PLATFORM} builds require a matching native macOS architecture${NC}"
        echo -e "${YELLOW}💡 Host architecture: ${CURRENT_ARCH_NORMALIZED}; target architecture: ${TARGET_ARCH}${NC}"
        exit 1
    fi
    USE_NATIVE=true
elif [[ "$TARGET_OS" == "windows" ]]; then
    if [[ "$CURRENT_OS" != MINGW* && "$CURRENT_OS" != MSYS* && "$CURRENT_OS" != CYGWIN* ]]; then
        echo -e "${RED}❌ ${PLATFORM} builds require a native Windows host${NC}"
        echo -e "${YELLOW}💡 jlink can only create a Windows JRE when run on Windows${NC}"
        exit 1
    fi
    if [[ "$CURRENT_ARCH_NORMALIZED" != "$TARGET_ARCH" ]]; then
        echo -e "${RED}❌ ${PLATFORM} builds require a matching native Windows architecture${NC}"
        echo -e "${YELLOW}💡 Host architecture: ${CURRENT_ARCH_NORMALIZED}; target architecture: ${TARGET_ARCH}${NC}"
        exit 1
    fi
    USE_NATIVE=true
fi

BUILD_METHOD="Docker"
if [[ "$USE_NATIVE" == true ]]; then
    BUILD_METHOD="Native"
fi

# Check requirements based on build method
if [[ "$USE_NATIVE" == false ]]; then
    # Docker build
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
        echo -e "${YELLOW}💡 Please install Docker to build the Python bindings${NC}"
        exit 1
    fi
else
    # Native build - check for Java (needed to BUILD the bundled JRE)
    if ! command -v java &> /dev/null; then
        echo -e "${RED}❌ Java is not installed${NC}"
        echo -e "${YELLOW}💡 Please install Java 25+ JDK to BUILD the package (creates bundled JRE)${NC}"
        exit 1
    fi
    if ! command -v jlink &> /dev/null; then
        echo -e "${RED}❌ jlink not found${NC}"
        echo -e "${YELLOW}💡 Please install a full JDK 25+ (jlink creates the bundled JRE)${NC}"
        exit 1
    fi
fi

echo -e "${CYAN}📋 Build Configuration:${NC}"
echo -e "   Package: ${YELLOW}arcadedb-embedded${NC}"
echo -e "   Platform: ${YELLOW}${PLATFORM}${NC}"
echo -e "   Python Version: ${YELLOW}${PYTHON_VERSION}${NC}"
echo -e "   JAR Source: ${YELLOW}${JAR_SOURCE_DESC}${NC}"
echo -e "   JRE: ${YELLOW}Bundled (end users need no Java)${NC}"
echo -e "   Build Method: ${YELLOW}${BUILD_METHOD}${NC}"
echo ""

# Package configuration
PACKAGE_NAME="arcadedb-embedded"
DESCRIPTION="ArcadeDB embedded multi-model database with bundled JRE - no Java installation required"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Building: ${YELLOW}${PACKAGE_NAME}${NC}"
echo -e "${BLUE}Platform: ${YELLOW}${PLATFORM}${NC}"
echo -e "${BLUE}Method: ${YELLOW}${BUILD_METHOD}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$USE_NATIVE" == true ]]; then
    # Native build. build-native.sh packages whatever src/arcadedb_embedded/jars
    # holds (and fills it from the image only when it is empty), so a JAR
    # directory reaches a native build only by being staged there. CI downloads
    # its JAR artifact into that directory and passes the same path, which
    # needs no copy.
    if [[ -n "$JAR_LIB_DIR" ]]; then
        NATIVE_JARS_DIR="$PY_BINDINGS_DIR/src/arcadedb_embedded/jars"
        mkdir -p "$NATIVE_JARS_DIR"
        if [[ "$(realpath "$JAR_LIB_DIR")" != "$(realpath "$NATIVE_JARS_DIR")" ]]; then
            echo -e "${CYAN}📦 Staging ${JAR_LIB_DIR} into src/arcadedb_embedded/jars for the native build${NC}"
            find "$NATIVE_JARS_DIR" -maxdepth 1 -name '*.jar' -type f -exec rm -f {} +
            cp "$JAR_LIB_DIR"/*.jar "$NATIVE_JARS_DIR"/
        fi
    fi
    echo -e "${YELLOW} Building natively on ${PLATFORM}...${NC}"
    "$SCRIPT_DIR/build-native.sh" "$PLATFORM" "$PACKAGE_NAME" "$DESCRIPTION" "$DOCKER_TAG" "${BUILD_VERSION:-}"
else
    # Docker build
    echo -e "${YELLOW} 🐳 Building in Docker...${NC}"

    # Check if BUILD_VERSION is set (from CI/CD)
    BUILD_VERSION_ARG=""
    if [ -n "${BUILD_VERSION:-}" ]; then
        echo -e "${CYAN}📌 Using specified version: ${YELLOW}${BUILD_VERSION}${NC}"
        BUILD_VERSION_ARG="--build-arg BUILD_VERSION=$BUILD_VERSION"
    fi

    # Convert platform format: linux/amd64 -> linux-x64, linux/arm64 -> linux-arm64, etc.
    TARGET_PLATFORM=$(echo "$PLATFORM" | sed 's|/|-|' | sed 's/amd64/x64/')
    echo -e "${CYAN}🎯 Target platform: ${YELLOW}${PLATFORM}${NC}"
    echo -e "${CYAN}🎯 JRE platform: ${YELLOW}${TARGET_PLATFORM}${NC}"
    echo ""

    # Determine Docker build platform (always Linux for cross-compilation)
    # We build ON linux/amd64 or linux/arm64, but FOR any target platform
    DOCKER_PLATFORM="${PLATFORM}"

    if [[ -z "$DOCKER_TAG" ]]; then
        echo -e "${RED}❌ Missing ArcadeDB Docker tag${NC}"
        echo -e "${YELLOW}💡 Pass a version so Docker builds remain reproducible${NC}"
        exit 1
    fi

    # Build Docker image
    echo -e "${CYAN}📦 Building Docker image...${NC}"

    docker build \
        --pull \
        --platform "$DOCKER_PLATFORM" \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --build-arg PACKAGE_NAME="$PACKAGE_NAME" \
        --build-arg PACKAGE_DESCRIPTION="$DESCRIPTION" \
        --build-arg ARCADEDB_TAG="$DOCKER_TAG" \
        --build-arg TARGET_PLATFORM="$TARGET_PLATFORM" \
        $USE_LOCAL_JARS_ARG \
        $LOCAL_JARS_HASH_ARG \
        $BUILD_VERSION_ARG \
        --target export \
        -t arcadedb-python-package-export \
        -f "$SCRIPT_DIR/Dockerfile.build" \
        ../..

    # Run tests
    echo -e "${CYAN}🧪 Running tests in Docker...${NC}"
    docker build \
        --platform "$DOCKER_PLATFORM" \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --build-arg PACKAGE_NAME="$PACKAGE_NAME" \
        --build-arg PACKAGE_DESCRIPTION="$DESCRIPTION" \
        --build-arg ARCADEDB_TAG="$DOCKER_TAG" \
        --build-arg TARGET_PLATFORM="$TARGET_PLATFORM" \
        $USE_LOCAL_JARS_ARG \
        $LOCAL_JARS_HASH_ARG \
        $BUILD_VERSION_ARG \
        --target tester \
        -t arcadedb-python-package \
        -f "$SCRIPT_DIR/Dockerfile.build" \
        ../..

    # Create dist directory if it doesn't exist
    mkdir -p dist

    # Record what was in dist/ BEFORE extracting. The check below used to be
    # `ls dist/*.whl`, which asks "is there a wheel here?" when the question is
    # "did THIS build produce one?". Nothing cleans dist/, so a wheel left by
    # any earlier build satisfied that test: an export stage that yielded
    # nothing still printed the success banner and exited 0, handing back a
    # stale wheel that looks like a fresh one. build-native.sh already avoids
    # this by clearing the directory first; the Docker path had no equivalent.
    # Compare identities rather than clearing, so deliberately kept wheels for
    # other platforms survive a build.
    WHEELS_BEFORE=$(ls -1 dist/*.whl 2> /dev/null | sort || true)

    # Extract the wheel from the export container
    echo -e "${CYAN}📋 Extracting wheel file...${NC}"
    CONTAINER_ID=$(docker create arcadedb-python-package-export)
    docker cp ${CONTAINER_ID}:/build/dist/. ./dist/
    docker rm ${CONTAINER_ID}

    # Verify THIS build produced a wheel, not merely that dist/ contains one
    WHEELS_AFTER=$(ls -1 dist/*.whl 2> /dev/null | sort || true)
    NEW_WHEELS=$(comm -13 <(echo "$WHEELS_BEFORE") <(echo "$WHEELS_AFTER") || true)
    if [[ -n "$NEW_WHEELS" ]]; then
        echo -e "${GREEN}✅ Wheel file created successfully!${NC}"
    elif [[ -n "$WHEELS_AFTER" ]]; then
        # Same filename as before: only trust it if the export actually rewrote
        # it. A rebuild of the same version legitimately lands here.
        NEWEST=$(ls -t dist/*.whl | head -n1)
        if [[ "$NEWEST" -nt "$BUILD_START_MARKER" ]]; then
            echo -e "${GREEN}✅ Wheel file created successfully!${NC}"
        elif [[ -n "$JAR_LIB_DIR" ]]; then
            # MTIME IS A HEURISTIC; THE SHA256 BELOW IS THE FACT.
            #
            # `docker cp` preserves the timestamp from inside the container, so a
            # run whose layers all cache-hit copies out a wheel stamped when the
            # layer was first built. The wheel is correct and current, and the
            # -nt test calls it stale. That failed a pinned-pair build whose
            # wheel carried exactly the right engine commit.
            #
            # When JAR_LIB_DIR is set, the next step compares the SHA256 of the
            # integration jar INSIDE the wheel against the one on disk and exits
            # 1 on mismatch. That is a content check and strictly stronger, so
            # let it be the gate rather than failing here on a file date.
            echo -e "${YELLOW}⚠️  No wheel newer than this run; docker layers likely all cached.${NC}"
            echo -e "${YELLOW}   Deferring to the SHA256 jar verification below, which is authoritative.${NC}"
        else
            echo -e "${RED}❌ No wheel was produced by this build${NC}"
            echo -e "${YELLOW}💡 dist/ still holds only wheels older than this run:${NC}"
            ls -lh dist/*.whl
            exit 1
        fi
    else
        echo -e "${RED}❌ Failed to extract wheel file${NC}"
        exit 1
    fi

    if [[ -n "$JAR_LIB_DIR" ]]; then
        echo -e "${CYAN}🔎 Verifying embedded local integration JAR...${NC}"
        ARCADEDB_VERSION="$POM_TAG" python3 - << 'PY'
import hashlib
import os
import sys
import zipfile
from pathlib import Path

ARCADEDB_VERSION = os.environ["ARCADEDB_VERSION"]
# NOT sorted()[-1]: that is a LEXICOGRAPHIC sort over filenames, where
# "26.9.1" ranks above "26.10.1" because '9' > '1'. On 2026-09-19 that made
# this check open September's 26.9.1 wheel, look for October's
# arcadedb-integration-26.10.1-SNAPSHOT.jar inside it, and fail a wheel that
# was in fact correct and complete. Take the wheel this build just wrote --
# the newest by mtime -- and then assert its version is the one we asked for,
# so picking the wrong file fails loudly instead of validating a stale one.
wheels = sorted(Path("dist").glob("arcadedb_embedded-*.whl"),
                key=lambda p: p.stat().st_mtime)
if not wheels:
    print("❌ no wheel in dist/", file=sys.stderr)
    sys.exit(1)
wheel = wheels[-1]
_want = ARCADEDB_VERSION.replace("-SNAPSHOT", "").replace("-", ".")
if not wheel.name.startswith(f"arcadedb_embedded-{_want}"):
    print(f"❌ newest wheel is {wheel.name}, which is not the "
          f"{ARCADEDB_VERSION} build this run produced", file=sys.stderr)
    sys.exit(1)
# The staged JARs' own version, NOT pom.xml's: the JARs can come from another
# version than this source tree (an official release image's lib, for one).
local_jars = sorted(Path("local-jars/lib").glob("arcadedb-integration-*.jar"))
if len(local_jars) != 1:
    print(f"❌ expected one local integration JAR, found {[p.name for p in local_jars]}",
          file=sys.stderr)
    sys.exit(1)
local_jar = local_jars[0]
local_jar_name = local_jar.name

with zipfile.ZipFile(wheel) as zf:
    matches = [name for name in zf.namelist() if name.endswith(local_jar_name)]
    if not matches:
        print(f"❌ Embedded integration JAR ({local_jar_name}) not found in wheel", file=sys.stderr)
        sys.exit(1)
    wheel_bytes = zf.read(matches[0])

local_bytes = local_jar.read_bytes()
wheel_hash = hashlib.sha256(wheel_bytes).hexdigest()
local_hash = hashlib.sha256(local_bytes).hexdigest()

print(f"   wheel integration SHA256: {wheel_hash}")
print(f"   local integration SHA256: {local_hash}")

if wheel_bytes != local_bytes:
    print("❌ Wheel embedded integration JAR does not match local-jars/lib", file=sys.stderr)
    sys.exit(1)

print("✅ Embedded integration JAR matches local-jars/lib")
PY
    fi
fi

echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
# SUPERSEDED WHEELS ARE DELETED, NOT KEPT. A wheel left in dist/ from an
# earlier build was read as evidence of the engine inside a newer one
# (2026-09-15: a 26.10.1.dev0 label beside a 26.6.1 jar, from a build days
# apart), which is exactly the confusion a stale artifact produces. Only the
# wheel this build wrote survives for its python/platform tag; wheels for
# other tags are someone else's build and are left alone.
NEWEST_WHEEL=$(ls -t dist/*.whl | head -n1)
NEWEST_TAG=$(basename "$NEWEST_WHEEL" | sed -E 's/^[^-]+-[^-]+-//')
for old in dist/*.whl; do
    if [[ "$old" != "$NEWEST_WHEEL" && "$(basename "$old" | sed -E 's/^[^-]+-[^-]+-//')" == "$NEWEST_TAG" ]]; then
        rm -f "$old"
        echo -e "${YELLOW}🗑  Removed superseded wheel $(basename "$old")${NC}"
    fi
done

echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📦 Built package:${NC}"
if [ -d "dist" ]; then
    ls -lh dist/*.whl 2> /dev/null | awk '{print "   " $9 " (" $5 ")"}'
fi
# Read from the engine JAR inside the wheel, which is the evidence; the wheel's
# version string says nothing about the engine it carries. A function, not a
# heredoc inside $(...), which bash 3.2 parses badly.
read_engine_build_number() {
    python3 - "$1" << 'PY'
import io
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as wheel:
    engines = [n for n in wheel.namelist() if "/jars/arcadedb-engine-" in n]
    if len(engines) != 1:
        print(f"no single engine JAR in the wheel ({len(engines)} found)")
        sys.exit(0)
    with zipfile.ZipFile(io.BytesIO(wheel.read(engines[0]))) as jar:
        try:
            props = jar.read("com/arcadedb/arcadedb.properties").decode("latin-1")
        except KeyError:
            print("none recorded")
            sys.exit(0)
for line in props.splitlines():
    key, sep, value = line.partition("=")
    if sep and key.strip() == "buildNumber":
        print(value.strip())
        break
else:
    print("none recorded")
PY
}
ENGINE_BUILD_NUMBER=$(read_engine_build_number "$NEWEST_WHEEL" || echo "unreadable")
echo -e "${CYAN}🧩 JAR source: ${YELLOW}${JAR_SOURCE_DESC}${NC}"
echo -e "${CYAN}🧩 Engine buildNumber: ${YELLOW}${ENGINE_BUILD_NUMBER}${NC}"

echo ""

# Refresh the repo-root uv dev environment so `uv run pytest` immediately uses
# the wheel that was just built. Skipped in CI, which installs wheels itself.
if [ -z "${CI:-}" ] && command -v uv > /dev/null 2>&1; then
    REPO_ROOT=$(git rev-parse --show-toplevel 2> /dev/null || true)
    if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/pyproject.toml" ]; then
        echo -e "${CYAN}🔄 Refreshing uv dev environment at repo root...${NC}"
        (
            cd "$REPO_ROOT" &&
                uv lock --upgrade-package arcadedb-embedded &&
                uv sync --reinstall-package arcadedb-embedded
        )
    fi
fi

echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo -e "   🧪 Run tests (from the repository root or bindings/python):"
echo -e "      ${YELLOW}uv run pytest${NC}"
echo ""
echo -e "   📤 Releases publish through the release workflow (docs/development/release.md);"
echo -e "      do not upload wheels by hand"
echo ""
