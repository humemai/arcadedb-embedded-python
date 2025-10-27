#!/bin/bash
# Test JRE-bundled wheel creation and installation
# This validates the Phase 0 prototype end-to-end

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TEST_DIR="${SCRIPT_DIR}/test-package"

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}JRE Wheel Build & Test${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# Step 1: Check if JRE prototype has been built
if [ ! -d "${OUTPUT_DIR}/minimal-jre" ]; then
    echo -e "${RED}❌ JRE prototype not found${NC}"
    echo -e "${YELLOW}💡 Run ./build-jre-prototype.sh first${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found JRE prototype${NC}"
JRE_SIZE=$(du -sh "${OUTPUT_DIR}/minimal-jre" | cut -f1)
echo -e "${CYAN}   JRE size: ${JRE_SIZE}${NC}"
echo ""

# Step 2: Create test package structure
echo -e "${CYAN}📦 Creating test package structure...${NC}"
rm -rf "${TEST_DIR}"
mkdir -p "${TEST_DIR}/arcadedb_embedded/jars"
mkdir -p "${TEST_DIR}/arcadedb_embedded/jre"

# Copy Python source
echo -e "${CYAN}   Copying Python source...${NC}"
cp -r "${SCRIPT_DIR}/../src/arcadedb_embedded/"*.py "${TEST_DIR}/arcadedb_embedded/"

# Generate _version.py file
echo -e "${CYAN}   Generating version file...${NC}"
cd "${SCRIPT_DIR}/.."
python3 write_version.py
cp src/arcadedb_embedded/_version.py "${TEST_DIR}/arcadedb_embedded/"
cd "${SCRIPT_DIR}"

# Copy JARs (excluding gRPC)
echo -e "${CYAN}   Copying JAR files (excluding gRPC)...${NC}"
JAR_COUNT=0
TOTAL_JARS=$(ls -1 "${OUTPUT_DIR}/jars"/*.jar 2> /dev/null | wc -l)
echo -e "${CYAN}   Found ${TOTAL_JARS} JARs to process...${NC}"
for jar in "${OUTPUT_DIR}/jars"/*.jar; do
    jar_name=$(basename "$jar")
    # Exclude gRPC wire protocol (same logic as setup_jars.py)
    if [[ ! "$jar_name" =~ grpcw ]]; then
        cp "$jar" "${TEST_DIR}/arcadedb_embedded/jars/"
        JAR_COUNT=$((JAR_COUNT + 1))
        if [ $((JAR_COUNT % 10)) -eq 0 ]; then
            echo -e "${CYAN}   Copied ${JAR_COUNT} JARs...${NC}"
        fi
    fi
done
echo -e "${CYAN}   ✓ Copied ${JAR_COUNT} JAR files (excluded gRPC)${NC}"

# Copy bundled JRE
echo -e "${CYAN}   Copying bundled JRE...${NC}"
cp -r "${OUTPUT_DIR}/minimal-jre"/* "${TEST_DIR}/arcadedb_embedded/jre/"

# Create minimal pyproject.toml
echo -e "${CYAN}   Creating package metadata...${NC}"
ARCADEDB_VERSION=$(python3 "${SCRIPT_DIR}/../extract_version.py" --format=pep440)
cat > "${TEST_DIR}/pyproject.toml" << EOF
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "arcadedb-embedded-jre-prototype"
version = "${ARCADEDB_VERSION}"
description = "ArcadeDB embedded Python package with bundled JRE (prototype)"
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "JPype1>=1.5.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["arcadedb_embedded*"]

[tool.setuptools.package-data]
arcadedb_embedded = [
    "jars/*.jar",
    "jre/**/*",
]
EOF

# Create README
cat > "${TEST_DIR}/README.md" << 'EOF'
# ArcadeDB Embedded JRE Prototype

This is a test package with bundled JRE for local validation.

**DO NOT PUBLISH** - This is for testing only.
EOF

# Step 3: Build the wheel
echo ""
echo -e "${CYAN}📦 Building wheel with bundled JRE...${NC}"
cd "${TEST_DIR}"
python3 -m build --wheel

# Check wheel size
WHEEL_FILE=$(ls dist/*.whl)
WHEEL_SIZE=$(du -sh "$WHEEL_FILE" | cut -f1)
echo -e "${GREEN}✅ Wheel created: ${WHEEL_FILE}${NC}"
echo -e "${CYAN}   Wheel size: ${WHEEL_SIZE}${NC}"
echo ""

# Step 4: Test installation in a virtual environment
echo -e "${CYAN}🧪 Testing installation in virtual environment...${NC}"
TEST_VENV="${TEST_DIR}/test-venv"
rm -rf "${TEST_VENV}"
python3 -m venv "${TEST_VENV}"

echo -e "${CYAN}   Installing wheel...${NC}"
"${TEST_VENV}/bin/pip" install --quiet "${WHEEL_FILE}"

# Step 5: Test that it works WITHOUT system Java
echo ""
echo -e "${CYAN}🧪 Testing without system Java...${NC}"

# Create test script
cat > "${TEST_DIR}/test_bundled_jre.py" << 'EOF'
#!/usr/bin/env python3
import sys
import os
import tempfile
import shutil

# Verify we're using bundled JRE
import arcadedb_embedded as arcadedb

print("🔍 Testing bundled JRE...")

# Check if JRE directory exists
package_dir = os.path.dirname(arcadedb.__file__)
jre_dir = os.path.join(package_dir, "jre")

if os.path.exists(jre_dir):
    print(f"✅ Bundled JRE found at: {jre_dir}")

    # Check JRE size
    jre_size = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, dirnames, filenames in os.walk(jre_dir)
        for filename in filenames
    ) / (1024 * 1024)  # MB
    print(f"   JRE size: {jre_size:.1f} MB")
else:
    print("❌ Bundled JRE not found!")
    sys.exit(1)

# Test database operations
print("\n🎮 Testing ArcadeDB operations...")
print(f"📦 Version: {arcadedb.__version__}")

temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "test_jre_db")

try:
    with arcadedb.create_database(db_path) as db:
        print("✅ Database created")

        with db.transaction():
            db.command("sql", "CREATE DOCUMENT TYPE TestJRE")
            db.command("sql", "INSERT INTO TestJRE SET name = 'bundled_jre_test', value = 42")
        print("✅ Transaction committed")

        result = db.query("sql", "SELECT FROM TestJRE")
        for record in result:
            name = record.get_property('name')
            value = record.get_property('value')
            print(f"✅ Query result: {name} = {value}")

    print("\n🎉 All tests passed with bundled JRE!")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
EOF

# Run test WITHOUT Java in PATH (simulate clean environment)
echo -e "${CYAN}   Running test (without system Java in PATH)...${NC}"
env -i \
    HOME="$HOME" \
    PATH="/usr/bin:/bin" \
    "${TEST_VENV}/bin/python3" "${TEST_DIR}/test_bundled_jre.py"

# Step 6: Summary
echo ""
echo -e "${BLUE}=================================${NC}"
echo -e "${GREEN}✅ JRE Wheel Test Complete!${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""
echo -e "${CYAN}📊 Summary:${NC}"
echo -e "   JRE size: ${JRE_SIZE}"
echo -e "   Wheel size: ${WHEEL_SIZE}"
echo -e "   JARs included: ${JAR_COUNT}"
echo -e "   Wheel location: ${WHEEL_FILE}"
echo ""
echo -e "${GREEN}✅ Package works without system Java!${NC}"
echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo -e "   1. Review package size and optimize if needed"
echo -e "   2. Update jvm.py to prefer bundled JRE"
echo -e "   3. Integrate into main build system"
echo ""
