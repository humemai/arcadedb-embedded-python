#!/bin/bash
# ArcadeDB Python Package Build Script
# Builds arcadedb-embedded package with bundled JRE (no Java installation required)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line arguments
PLATFORM="${1:-}"
PYTHON_VERSION="${2:-3.12}"

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🎮 ArcadeDB Python Package - Docker Build Script          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 [PLATFORM] [PYTHON_VERSION]"
    echo ""
    echo "Builds arcadedb-embedded package with bundled JRE"
    echo "No external Java installation required!"
    echo ""
    echo "PLATFORM:"
    echo "  Auto-detected if not specified"
    echo "  linux/amd64    Linux x86_64 (Docker build)"
    echo "  linux/arm64    Linux ARM64 (Docker build, native ARM64 runner)"
    echo "  darwin/amd64   macOS x86_64 (native build on macOS)"
    echo "  darwin/arm64   macOS ARM64 Apple Silicon (native build on macOS)"
    echo "  windows/amd64  Windows x86_64 (native build on Windows)"
    echo "  windows/arm64  Windows ARM64 (native build on Windows)"
    echo ""
    echo "PYTHON_VERSION:"
    echo "  Python version for wheel (default: 3.12)"
    echo "  Examples: 3.10, 3.11, 3.12, 3.13, 3.14"
    echo ""
    echo "Build Methods:"
    echo "  Native: macOS and Windows build natively on their platforms"
    echo "  Docker: Linux uses Docker for manylinux compliance"
    echo ""
    echo "Examples:"
    echo "  $0                    # Build for current platform with Python 3.12"
    echo "  $0 linux/amd64        # Build for Linux x86_64 with Python 3.12 (via Docker)"
    echo "  $0 linux/amd64 3.11   # Build for Linux x86_64 with Python 3.11 (via Docker)"
    echo "  $0 darwin/arm64 3.12  # Build for macOS ARM64 with Python 3.12 (native)"
    echo ""
    echo "Package features:"
    echo "  ✅ Bundled platform-specific JRE (no Java required)"
    echo "  ✅ Optimized JAR selection (see jar_exclusions.txt)"
    echo "  ✅ Multi-platform support (6 platforms)"
    echo "  📦 Size: ~215MB (compressed), ~289MB (installed)"
    echo ""
}

# Check for help flag
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    print_header
    print_usage
    exit 0
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

# Auto-detect Docker tag from pom.xml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${CYAN}🔍 Detecting version from pom.xml...${NC}"
DOCKER_TAG=$(python3 "$SCRIPT_DIR/extract_version.py" --format=docker)
echo -e "${CYAN}📌 Docker tag: ${YELLOW}${DOCKER_TAG}${NC}"
echo ""

# Determine build method: native or Docker
# Use native build if we're already on the target platform
CURRENT_OS="$(uname -s)"
CURRENT_ARCH="$(uname -m)"

USE_NATIVE=false
if [[ "$PLATFORM" == "darwin/"* ]] && [[ "$CURRENT_OS" == "Darwin" ]]; then
    USE_NATIVE=true
elif [[ "$PLATFORM" == "windows/"* ]] && [[ "$CURRENT_OS" == MINGW* || "$CURRENT_OS" == MSYS* || "$CURRENT_OS" == CYGWIN* ]]; then
    USE_NATIVE=true
elif [[ "$PLATFORM" == "linux/amd64" ]] && [[ "$CURRENT_OS" == "Linux" ]] && [[ "$CURRENT_ARCH" == "x86_64" ]]; then
    # For Linux, still use Docker for reproducibility (manylinux compliance)
    USE_NATIVE=false
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
        echo -e "${YELLOW}💡 Please install Java 21+ JDK to BUILD the package (creates bundled JRE)${NC}"
        exit 1
    fi
    if ! command -v jlink &> /dev/null; then
        echo -e "${RED}❌ jlink not found${NC}"
        echo -e "${YELLOW}💡 Please install a full JDK (jlink creates the bundled JRE)${NC}"
        exit 1
    fi
fi

echo -e "${CYAN}📋 Build Configuration:${NC}"
echo -e "   Package: ${YELLOW}arcadedb-embedded${NC}"
echo -e "   Platform: ${YELLOW}${PLATFORM}${NC}"
echo -e "   Python Version: ${YELLOW}${PYTHON_VERSION}${NC}"
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
    # Native build
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
    if [[ "$PLATFORM" == darwin/* ]] || [[ "$PLATFORM" == windows/* ]]; then
        # Cross-compiling for macOS/Windows - build on Linux
        DOCKER_PLATFORM="linux/amd64"
        echo -e "${CYAN}🔧 Cross-compiling: Building on linux/amd64 for ${YELLOW}${PLATFORM}${NC}"
        echo ""
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
        $BUILD_VERSION_ARG \
        --target export \
        -t arcadedb-python-package-export \
        -f Dockerfile.build \
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
        $BUILD_VERSION_ARG \
        --target tester \
        -t arcadedb-python-package \
        -f Dockerfile.build \
        ../..

    # Create dist directory if it doesn't exist
    mkdir -p dist

    # Extract the wheel from the export container
    echo -e "${CYAN}📋 Extracting wheel file...${NC}"
    CONTAINER_ID=$(docker create arcadedb-python-package-export)
    docker cp ${CONTAINER_ID}:/build/dist/. ./dist/
    docker rm ${CONTAINER_ID}

    # Verify wheel was extracted
    if ls dist/*.whl 1> /dev/null 2>&1; then
        echo -e "${GREEN}✅ Wheel file created successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to extract wheel file${NC}"
        exit 1
    fi
fi

echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📦 Built package:${NC}"
if [ -d "dist" ]; then
    ls -lh dist/*.whl 2> /dev/null | awk '{print "   " $9 " (" $5 ")"}'
fi

echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo -e "   📦 Install the package:"
echo -e "      ${YELLOW}pip install dist/arcadedb_embedded-*.whl${NC}"
echo ""
echo -e "   🧪 Run tests:"
echo -e "      ${YELLOW}pytest tests/${NC}"
echo ""
echo -e "   📤 Publish to PyPI:"
echo -e "      ${YELLOW}twine upload dist/*.whl${NC}"
echo ""
