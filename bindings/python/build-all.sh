#!/bin/bash
# ArcadeDB Python Package Build Script
# Builds arcadedb-embed variants (base and jre) from minimal distribution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line arguments
VARIANT="${1:-base}"

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🎮 ArcadeDB Python Package - Docker Build Script          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 [VARIANT]"
    echo ""
    echo "VARIANT:"
    echo "  base        Build base package (requires Java 21+) - default"
    echo "  jre         Build package with bundled JRE (coming soon)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Build base variant (default)"
    echo "  $0 base               # Build base variant explicitly"
    echo "  $0 jre                # Build JRE variant (future)"
    echo ""
    echo "Note: Both variants are based on ArcadeDB minimal distribution"
    echo "      (includes Studio UI, excludes Gremlin/GraphQL)"
    echo ""
}

# Check for help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    print_header
    print_usage
    exit 0
fi

print_header

# Validate variant argument
if [[ ! "$VARIANT" =~ ^(base|jre)$ ]]; then
    echo -e "${RED}❌ Invalid variant: $VARIANT${NC}"
    echo ""
    print_usage
    exit 1
fi

# For now, only base variant is supported
if [[ "$VARIANT" == "jre" ]]; then
    echo -e "${RED}❌ JRE variant not yet implemented${NC}"
    echo -e "${YELLOW}💡 Currently only 'base' variant is available${NC}"
    echo -e "${YELLOW}💡 JRE variant coming in future release${NC}"
    exit 1
fi

# Auto-detect Docker tag from pom.xml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${CYAN}🔍 Detecting version from pom.xml...${NC}"
DOCKER_TAG=$(python3 "$SCRIPT_DIR/extract_version.py" --format=docker)
echo -e "${CYAN}📌 Docker tag: ${YELLOW}${DOCKER_TAG}${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    echo -e "${YELLOW}💡 Please install Docker to build the Python bindings${NC}"
    exit 1
fi

echo -e "${CYAN}📋 Build Configuration:${NC}"
echo -e "   Variant: ${YELLOW}$VARIANT${NC}"
echo -e "   Base Distribution: ${YELLOW}minimal${NC}"
echo -e "   Build Method: ${YELLOW}Docker${NC}"
echo ""

# Function to build the package variant
build_variant() {
    local variant=$1
    local variant_name=""
    local package_name=""
    local description=""

    case $variant in
        base)
            variant_name="Base Package (requires Java 21+)"
            package_name="arcadedb-embed"
            description="ArcadeDB embedded Python package - requires Java 21+ (minimal distribution: Studio + core database)"
            ;;
        jre)
            variant_name="JRE Package (bundled JRE)"
            package_name="arcadedb-embed-jre"
            description="ArcadeDB embedded Python package with bundled JRE - no Java installation required (minimal distribution: Studio + core database)"
            ;;
        *)
            echo -e "${RED}❌ Unknown variant: $variant${NC}"
            exit 1
            ;;
    esac

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Building: ${YELLOW}$variant_name${NC}"
    echo -e "${BLUE}Package: ${YELLOW}$package_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    echo -e "${YELLOW}🐳 Building in Docker...${NC}"

    # Build Docker image for the variant
    echo -e "${CYAN}📦 Building Docker image for $variant variant...${NC}"
    docker build \
        --build-arg VARIANT=$variant \
        --build-arg PACKAGE_NAME=$package_name \
        --build-arg PACKAGE_DESCRIPTION="$description" \
        --build-arg ARCADEDB_TAG=$DOCKER_TAG \
        --target export \
        -t arcadedb-python-package-$variant-export \
        -f Dockerfile.build \
        ../..

    # Also build the tester stage (runs tests)
    echo -e "${CYAN}🧪 Running tests in Docker...${NC}"
    docker build \
        --build-arg VARIANT=$variant \
        --build-arg PACKAGE_NAME=$package_name \
        --build-arg PACKAGE_DESCRIPTION="$description" \
        --build-arg ARCADEDB_TAG=$DOCKER_TAG \
        --target tester \
        -t arcadedb-python-package-$variant \
        -f Dockerfile.build \
        ../..

    # Create dist directory if it doesn't exist
    mkdir -p dist

    # Extract the wheel from the export container
    echo -e "${CYAN}📋 Extracting wheel file...${NC}"
    CONTAINER_ID=$(docker create arcadedb-python-package-$variant-export)
    docker cp ${CONTAINER_ID}:/build/dist/. ./dist/
    docker rm ${CONTAINER_ID}

    # Verify wheel was extracted
    if ls dist/*.whl 1> /dev/null 2>&1; then
        echo -e "${GREEN}✅ Wheel file created successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to extract wheel file${NC}"
        exit 1
    fi

    echo ""
}

# Main build logic - simplified for single variant
echo -e "${CYAN}📦 Building $VARIANT variant...${NC}"
echo ""

build_variant "$VARIANT"

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
echo -e "      ${YELLOW}pip install dist/arcadedb_embed-*.whl${NC}"
echo ""
echo -e "   🧪 Run tests:"
echo -e "      ${YELLOW}pytest tests/${NC}"
echo ""
echo -e "   📤 Publish to PyPI:"
echo -e "      ${YELLOW}twine upload dist/*.whl${NC}"
echo ""
