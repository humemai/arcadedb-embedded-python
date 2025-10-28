#!/bin/bash
# Native build script for ArcadeDB Python package
# Used on macOS and Windows where Docker is not needed
# This script runs natively on the target platform and uses jlink to create platform-specific JRE

set -euo pipefail

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parameters
PLATFORM="${1:-}"
PACKAGE_NAME="${2:-arcadedb-embedded}"
PACKAGE_DESCRIPTION="${3:-ArcadeDB embedded multi-model database with bundled JRE}"
ARCADEDB_TAG="${4:-}"
BUILD_VERSION="${5:-}"

if [[ -z "$PLATFORM" ]] || [[ -z "$ARCADEDB_TAG" ]]; then
    echo -e "${RED}Usage: $0 PLATFORM PACKAGE_NAME PACKAGE_DESCRIPTION ARCADEDB_TAG [BUILD_VERSION]${NC}"
    exit 1
fi

echo -e "${CYAN}🔨 Native build for platform: ${YELLOW}${PLATFORM}${NC}"
echo -e "${CYAN}📦 Package: ${YELLOW}${PACKAGE_NAME}${NC}"
echo -e "${CYAN}📌 ArcadeDB tag: ${YELLOW}${ARCADEDB_TAG}${NC}"

# Check for Java (needed for jlink and JPype build)
if ! command -v java &> /dev/null; then
    echo -e "${RED}❌ Java not found${NC}"
    echo -e "${YELLOW}💡 Please install Java 21 or later${NC}"
    exit 1
fi

JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2 | cut -d'.' -f1)
echo -e "${CYAN}☕ Java version: ${YELLOW}${JAVA_VERSION}${NC}"

if [[ "$JAVA_VERSION" -lt 21 ]]; then
    echo -e "${RED}❌ Java 21 or later is required (found: ${JAVA_VERSION})${NC}"
    exit 1
fi

# Check for jlink
if ! command -v jlink &> /dev/null; then
    echo -e "${RED}❌ jlink not found${NC}"
    echo -e "${YELLOW}💡 Please install a JDK (not just JRE)${NC}"
    exit 1
fi

echo ""

# Step 1: Download ArcadeDB JARs (if not already present)
JARS_DIR="$SCRIPT_DIR/src/arcadedb_embedded/jars"
if [[ -d "$JARS_DIR" ]] && [[ $(ls -1 "$JARS_DIR"/*.jar 2> /dev/null | wc -l) -gt 0 ]]; then
    echo -e "${GREEN}✅ Using existing JARs from: $JARS_DIR${NC}"
    JAR_COUNT=$(ls -1 "$JARS_DIR"/*.jar | wc -l)
    echo -e "${CYAN}📦 Found $JAR_COUNT JAR files${NC}"
else
    # Check for Docker (needed to download JARs from ArcadeDB image)
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found and JARs not present${NC}"
        echo -e "${YELLOW}💡 Either:${NC}"
        echo -e "${YELLOW}   1. Install Docker to download JARs: https://www.docker.com/get-started${NC}"
        echo -e "${YELLOW}   2. Or manually place JARs in: $JARS_DIR${NC}"
        exit 1
    fi

    echo -e "${CYAN}📥 Downloading ArcadeDB JARs from Docker image...${NC}"
    TEMP_JARS=$(mktemp -d)

    if ! docker run --rm arcadedata/arcadedb:${ARCADEDB_TAG} tar -cf - -C /home/arcadedb lib | tar -xf - -C "$TEMP_JARS"; then
        echo -e "${RED}❌ Failed to download JARs from Docker image${NC}"
        echo -e "${YELLOW}💡 Make sure Docker is running and you have internet access${NC}"
        rm -rf "$TEMP_JARS"
        exit 1
    fi

    mkdir -p "$JARS_DIR"
    cp "$TEMP_JARS/lib"/*.jar "$JARS_DIR/"
    rm -rf "$TEMP_JARS"
    echo -e "${GREEN}✅ JARs downloaded to: $JARS_DIR${NC}"
fi

# Step 2: Build minimal JRE with jlink
echo -e "${CYAN}🔨 Building minimal JRE with jlink...${NC}"
REQUIRED_MODULES="java.base,java.compiler,java.desktop,java.logging,java.management,java.naming,java.prefs,java.rmi,java.scripting,java.security.jgss,java.security.sasl,java.sql,java.transaction.xa,java.xml,jdk.incubator.vector,jdk.internal.vm.ci,jdk.jfr,jdk.management,jdk.sctp,jdk.unsupported,jdk.zipfs"

rm -rf "$SCRIPT_DIR/temp_jre"
jlink \
    --module-path "${JAVA_HOME}/jmods" \
    --add-modules "${REQUIRED_MODULES}" \
    --ignore-signing-information \
    --strip-debug \
    --no-man-pages \
    --no-header-files \
    --compress zip-9 \
    --output "$SCRIPT_DIR/temp_jre"

echo -e "${GREEN}✅ JRE built${NC}"
JRE_SIZE=$(du -sh "$SCRIPT_DIR/temp_jre" | cut -f1)
echo -e "${CYAN}📊 JRE size: ${YELLOW}${JRE_SIZE}${NC}"

# Step 3: Copy JRE to package (JARs already in place)
echo -e "${CYAN}📦 Preparing package...${NC}"

# Clean up: Remove gRPC wire protocol JAR if present (not needed)
if ls "$JARS_DIR"/arcadedb-grpcw-*.jar 1> /dev/null 2>&1; then
    rm -f "$JARS_DIR"/arcadedb-grpcw-*.jar
    echo -e "${YELLOW}🗑️  Removed gRPC wire protocol JAR (not needed)${NC}"
fi

# Build and copy JRE
rm -rf "$SCRIPT_DIR/src/arcadedb_embedded/jre"
mkdir -p "$SCRIPT_DIR/src/arcadedb_embedded/jre"
cp -R "$SCRIPT_DIR/temp_jre"/* "$SCRIPT_DIR/src/arcadedb_embedded/jre/"

JAR_COUNT=$(ls -1 "$JARS_DIR"/*.jar | wc -l)
echo -e "${GREEN}✅ Package prepared (${JAR_COUNT} JARs + JRE)${NC}"

# Step 4: Write version to pyproject.toml
echo -e "${CYAN}📝 Writing version...${NC}"
if [[ -n "${BUILD_VERSION}" ]]; then
    PYTHON_VERSION="${BUILD_VERSION}"
else
    PYTHON_VERSION=$(python3 "$SCRIPT_DIR/extract_version.py" --format=pep440)
fi
echo -e "${CYAN}📦 Python package version: ${YELLOW}${PYTHON_VERSION}${NC}"

# Update pyproject.toml (handle macOS BSD sed vs GNU sed)
if [[ "$(uname -s)" == "Darwin" ]]; then
    # macOS uses BSD sed
    sed -i '' "s|^version = .*|version = \"${PYTHON_VERSION}\"|" "$SCRIPT_DIR/pyproject.toml"
    sed -i '' "s|^name = .*|name = \"${PACKAGE_NAME}\"|" "$SCRIPT_DIR/pyproject.toml"
    sed -i '' "s|^description = .*|description = \"${PACKAGE_DESCRIPTION}\"|" "$SCRIPT_DIR/pyproject.toml"
else
    # Linux/Windows use GNU sed
    sed -i "s|^version = .*|version = \"${PYTHON_VERSION}\"|" "$SCRIPT_DIR/pyproject.toml"
    sed -i "s|^name = .*|name = \"${PACKAGE_NAME}\"|" "$SCRIPT_DIR/pyproject.toml"
    sed -i "s|^description = .*|description = \"${PACKAGE_DESCRIPTION}\"|" "$SCRIPT_DIR/pyproject.toml"
fi

# Step 5: Generate version file
echo -e "${CYAN}📝 Generating _version.py...${NC}"
python3 "$SCRIPT_DIR/write_version.py" "$SCRIPT_DIR/../../pom.xml"

# Step 6: Build wheel with proper platform tag
echo -e "${CYAN}🔨 Building wheel...${NC}"

# Determine platform tag for wheel
case "$PLATFORM" in
    linux/amd64)
        PLAT_NAME="manylinux_2_17_x86_64"
        ;;
    darwin/amd64)
        PLAT_NAME="macosx_10_9_x86_64"
        ;;
    darwin/arm64)
        PLAT_NAME="macosx_11_0_arm64"
        ;;
    windows/amd64)
        PLAT_NAME="win_amd64"
        ;;
    *)
        echo -e "${RED}❌ Unsupported platform: ${PLATFORM}${NC}"
        exit 1
        ;;
esac

echo -e "${CYAN}🏷️  Platform tag: ${YELLOW}${PLAT_NAME}${NC}"

# Build wheel
python3 -m build --wheel --outdir "$SCRIPT_DIR/dist"

# Rename wheel to have correct platform tag if needed
# (python -m build may not set it correctly for cross-platform builds)
WHEEL_FILE=$(ls "$SCRIPT_DIR/dist"/*.whl | head -n1)
if [[ -n "$WHEEL_FILE" ]]; then
    # Extract components from wheel filename
    WHEEL_NAME=$(basename "$WHEEL_FILE")
    # arcadedb_embedded-25.10.1-py3-none-any.whl -> arcadedb_embedded-25.10.1-py3-none-PLAT_NAME.whl
    NEW_WHEEL_NAME=$(echo "$WHEEL_NAME" | sed "s|-py3-none-any\.whl|-py3-none-${PLAT_NAME}.whl|")
    if [[ "$WHEEL_NAME" != "$NEW_WHEEL_NAME" ]]; then
        mv "$WHEEL_FILE" "$SCRIPT_DIR/dist/$NEW_WHEEL_NAME"
        echo -e "${CYAN}🏷️  Renamed wheel to: ${YELLOW}${NEW_WHEEL_NAME}${NC}"
    fi
fi

echo -e "${GREEN}✅ Wheel built${NC}"

# Step 7: Clean up temp files
echo -e "${CYAN}🧹 Cleaning up...${NC}"
rm -rf "$SCRIPT_DIR/temp_jre"

echo ""
echo -e "${GREEN}🎉 Native build completed successfully!${NC}"
echo -e "${CYAN}📦 Wheel file:${NC}"
ls -lh "$SCRIPT_DIR/dist"/*.whl
