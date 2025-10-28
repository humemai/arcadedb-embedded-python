#!/bin/bash
# Build JRE Prototype using Docker
# This script builds a minimal JRE for ArcadeDB and extracts it for testing

set -e

echo "================================="
echo "JRE Bundling Prototype Build"
echo "================================="
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# Auto-detect Docker tag from pom.xml (same logic as build.sh)
echo "🔍 Detecting version from pom.xml..."
ARCADEDB_TAG=$(python3 "${SCRIPT_DIR}/../extract_version.py" --format=docker)
echo "📌 ArcadeDB version detected: ${ARCADEDB_TAG}"
echo ""

# Clean previous output
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

echo "Step 1: Building JRE prototype with Docker..."
echo ""

# Build the Docker image
docker build \
    --build-arg ARCADEDB_TAG="${ARCADEDB_TAG}" \
    -f "${SCRIPT_DIR}/Dockerfile.jre-prototype" \
    -t arcadedb-jre-prototype:latest \
    "${SCRIPT_DIR}"

echo ""
echo "Step 2: Extracting JRE and analysis results..."
echo ""

# Create a temporary container to extract files
CONTAINER_ID=$(docker create arcadedb-jre-prototype:latest)

# Extract analysis results
docker cp "${CONTAINER_ID}:/analysis" "${OUTPUT_DIR}/"

# Extract minimal JRE
docker cp "${CONTAINER_ID}:/minimal-jre" "${OUTPUT_DIR}/"

# Extract JARs for reference
docker cp "${CONTAINER_ID}:/jars" "${OUTPUT_DIR}/"

# Clean up container
docker rm "${CONTAINER_ID}"

echo ""
echo "Step 3: Analyzing results..."
echo ""

# Display module list
echo "Required Java modules:"
cat "${OUTPUT_DIR}/analysis/required-modules.txt"
echo ""

# Display JRE size
JRE_SIZE=$(du -sh "${OUTPUT_DIR}/minimal-jre" | cut -f1)
echo "Minimal JRE size: ${JRE_SIZE}"
echo ""

# Count JARs (excluding gRPC)
JAR_COUNT=$(ls "${OUTPUT_DIR}/jars"/*.jar 2> /dev/null | wc -l)
GRPC_COUNT=$(ls "${OUTPUT_DIR}/jars"/*grpcw*.jar 2> /dev/null | wc -l || echo 0)
FILTERED_COUNT=$((JAR_COUNT - GRPC_COUNT))
echo "Total JARs: ${JAR_COUNT}"
echo "gRPC JARs (excluded): ${GRPC_COUNT}"
echo "Filtered JARs: ${FILTERED_COUNT}"
echo ""

# Test the JRE
echo "Step 4: Testing minimal JRE..."
"${OUTPUT_DIR}/minimal-jre/bin/java" -version
echo ""

echo "================================="
echo "✅ Prototype build complete!"
echo "================================="
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo ""
echo "Next steps:"
echo "  1. Review required modules in: ${OUTPUT_DIR}/analysis/required-modules.txt"
echo "  2. Test JRE with Python/JPype"
echo "  3. Create prototype packages (base + JRE variants)"
echo ""
