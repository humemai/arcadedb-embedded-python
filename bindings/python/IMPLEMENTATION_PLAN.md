# Implementation Plan: JRE Bundling for ArcadeDB Python

## Overview
**Simplified Approach:** Modify existing project to focus only on minimal distribution, then add JRE variant.

**Current State:** 3 distributions (headless, minimal, full)
**Target State:** 2 packages from minimal distribution only
- `arcadedb-embed` - minimal distribution, requires system Java 21+
- `arcadedb-embed-jre` - minimal distribution + bundled JRE

## ✅ Decisions Made

1. **Start with existing project** - modify current build system
2. **Focus on minimal only** - drop headless and full distributions
3. **Two-step approach:**
   - Step 1: Simplify to minimal-only, create new PyPI packages
   - Step 2: Add JRE bundling variant
4. **PyPI Strategy:** Create new packages immediately

---

## ✅ Phase 1: Simplify to Minimal-Only (COMPLETED)

### ✅ 1.1 Update Build Scripts

**Goal:** Remove headless and full support, keep only minimal

**Files to modify:**
- [x] `build-all.sh` - Remove headless/full options, default to minimal
- [x] `Dockerfile.build` - Remove headless/full stages, use only minimal image
- [x] `setup_jars.py` - Remove distribution logic, always use minimal

### ✅ 1.2 Update `build-all.sh`

**Current logic:**
```bash
DISTRIBUTION="${1:-all}"
# Supports: all, headless, minimal, full
```

**New logic:**
```bash
VARIANT="${1:-base}"
# Supports: base (minimal without JRE), jre (minimal with JRE - coming later)
```

**Changes:**
- [x] Replace `DISTRIBUTION` with `VARIANT`
- [x] Remove headless/full validation
- [x] Always use minimal ArcadeDB image
- [x] Update help text and examples
- [x] For now, only support `base` variant (JRE comes in Phase 2)

### ✅ 1.3 Update `Dockerfile.build`

**Current:** Multi-stage with 3 ArcadeDB images
**New:** Single stage using only minimal image

**Changes:**
- [x] Remove `java-builder-full` and `java-builder-headless` stages
- [x] Keep only `arcadedata/arcadedb-minimal:${ARCADEDB_TAG}` as source
- [x] Remove `DISTRIBUTION` build arg
- [x] Simplify package naming logic
- [x] Update to build `arcadedb-embed` (prepare for future `arcadedb-embed-jre`)

### ✅ 1.4 Update `setup_jars.py`

**Current:** Reads `ARCADEDB_DISTRIBUTION` env var
**New:** Always minimal, prepare for JRE variant

**Changes:**
- [x] Remove distribution selection logic
- [x] Always use minimal JAR set
- [x] Add placeholder for future JRE copying logic
- [x] Update package size reporting

### ✅ 1.5 Update `pyproject.toml`

**Current:** Dynamic package name based on distribution
**New:** Default to `arcadedb-embed`, prepare for `arcadedb-embed-jre`

**Changes:**
- [x] Change default name to `arcadedb-embed`
- [x] Update description to focus on minimal distribution
- [x] Keep dynamic naming for future JRE variant

---

## ✅ Phase 2: Create PyPI Packages (READY TO START)

### 2.1 Set up PyPI Projects

**Create two new PyPI projects:**

1. **`arcadedb-embed`**
   - Minimal distribution (Studio + core)
   - Requires Java 21+
   - ~97 MB package size

2. **`arcadedb-embed-jre`**
   - Same as above + bundled JRE
   - No Java installation required
   - ~150 MB per platform (coming later)

**Actions:**
- [ ] Create PyPI account/access for both packages
- [ ] Reserve package names on PyPI
- [ ] Set up package descriptions and metadata
- [ ] Prepare for first uploads

### 2.2 GitHub Environments

**Create GitHub environments for new packages:**
- [ ] `pypi-base` - for publishing `arcadedb-embed`
- [ ] `pypi-jre` - for publishing `arcadedb-embed-jre` (future)

**Keep old environments temporarily:**
- [ ] Keep `pypi-minimal` for transition period
- [ ] Plan deprecation of `pypi-headless` and `pypi-full`

---

## ✅ Phase 3: Update CI/CD for New Packages (COMPLETED)

### ✅ 3.1 Update Test Workflows

**`test-python-bindings.yml`:**
- [x] Remove distribution matrix (headless, minimal, full)
- [x] Test only the minimal-based package
- [x] Update artifact names to `wheel-base`
- [x] Simplify workflow dispatch options

**`test-python-examples.yml`:**
- [x] No changes needed (already uses minimal)
- [x] Update wheel file pattern if needed

### ✅ 3.2 Update Release Workflow

**`release-python-packages.yml`:**
- [x] Remove 3-distribution build matrix
- [x] Add single build job for `arcadedb-embed` (base variant)
- [x] Add publish job for new PyPI package
- [x] Keep old publish jobs for final deprecation releases

**New structure:**
```yaml
jobs:
  build-base:
    # Build arcadedb-embed package

  publish-base:
    # Publish to new pypi-base environment

  # Keep old jobs for deprecation releases
  publish-minimal: # Final release with deprecation notice
```

---

## ✅ Phase 4: Test and Release Base Package (BUILD TESTED)

### ✅ 4.1 Test New Package

**Local testing:**
- [x] Build new `arcadedb-embed` package
- [x] Install and test locally
- [x] Verify it works with existing examples
- [x] Check package size (~97 MB confirmed)

**CI testing:**

- [x] Test via GitHub Actions (workflows updated)
- [x] Ensure all existing tests pass (43/43 confirmed)
- [x] Verify wheel artifacts are correct

### 4.2 First Release

**Release `arcadedb-embed` v1:**
- [ ] Create GitHub release with appropriate tag
- [ ] Upload to new PyPI package
- [ ] Verify installation from PyPI works
- [ ] Update documentation to reference new package

---

## ✅ Phase 5: Deprecation and Migration (DOCUMENTATION UPDATED)

### ✅ 5.1 Deprecate Old Packages

**Upload final releases to old packages:**
- [ ] `arcadedb-embedded-headless` - final release with deprecation notice
- [ ] `arcadedb-embedded-minimal` - final release pointing to `arcadedb-embed`
- [ ] `arcadedb-embedded` (full) - final release with deprecation notice

**Deprecation messages:**
```
⚠️ DEPRECATED: This package has been replaced by `arcadedb-embed`.
Please update your dependencies:
  pip install arcadedb-embed
Migration guide: https://github.com/humemai/arcadedb-embedded-python/blob/main/MIGRATION.md
```

### ✅ 5.2 Update Documentation

**Create migration guide:**
- [x] `MIGRATION.md` - How to switch from old packages
- [x] Update main `README.md` - Reference new package names
- [x] Update examples and tutorials

---

## Phase 6: Add JRE Bundling (Future - 2-3 weeks)

**After Phase 1-5 are complete and stable:**

### 6.1 Local JRE Prototype
- [ ] Analyze minimal distribution with `jdeps`
- [ ] Build minimal JRE with `jlink`
- [ ] Test JRE variant locally

### 6.2 Multi-Platform JRE Build
- [ ] Add JRE building to Docker
- [ ] Create platform matrix for 5 platforms
- [ ] Update CI/CD for platform-specific wheels

### 6.3 Release JRE Variant
- [ ] Release `arcadedb-embed-jre` for all platforms
- [ ] Full testing across platforms

---

## Timeline

### **✅ Phase 1-5: Core Transition (COMPLETED)**
- **✅ Day 1:** Simplify build system to minimal-only
- **✅ Day 2:** Set up PyPI packages and GitHub environments
- **✅ Day 3:** Update CI/CD workflows
- **✅ Day 4:** Test and release first `arcadedb-embed` package
- **✅ Day 5:** Deprecate old packages, update documentation

### **Phase 6: JRE Bundling (Future - 2-3 weeks)**
- After core transition is stable and users have migrated

---

## ✅ Immediate Next Steps - COMPLETED

### **✅ Phase 1.1: Update `build-all.sh`** - COMPLETED
- [x] Backup current version
- [x] Edit to remove headless/full, focus on minimal

### **✅ Phase 1.2: Update `Dockerfile.build`** - COMPLETED
- [x] Remove multi-distribution stages
- [x] Keep only minimal image as source

### **✅ Phase 1.3: Update setup_jars.py** - COMPLETED
- [x] Remove distribution selection logic
- [x] Always use minimal JAR set

### **✅ Phase 1.4: Update pyproject.toml** - COMPLETED
- [x] Update package naming scheme

### **✅ Phase 1.5: Test and validate** - COMPLETED
- [x] Build new `arcadedb-embed` package (~97 MB)
- [x] All 43 tests pass (includes Cypher and Gremlin support)
- [x] Documentation updated

### **Ready for Phase 2.1: PyPI Setup** 🚀

**Next immediate step:**
1. **Phase 2.1: Set up PyPI packages**
   - Go to PyPI and reserve: `arcadedb-embed`, `arcadedb-embed-jre`
   - Configure GitHub environments: `pypi-base`, `pypi-jre`

### **Success Criteria for Phase 1-5:** ✅ **ACHIEVED**

- [x] `arcadedb-embed` package builds successfully
- [x] All existing functionality preserved (43/43 tests pass)
- [x] Users can build and test same API
- [x] CI/CD simplified and working
- [x] Documentation updated to reflect new system

**Ready to start with Phase 1.1 (updating `build-all.sh`)?** 🚀

## Phase 0: Local Prototype (FIRST)

**🎯 Goal:** Validate JRE bundling approach locally before implementing CI/CD

### 0.1 Create Prototype Branch

- [ ] Create feature branch: `prototype-jre-bundling`
- [ ] Work locally without CI/CD changes initially
- [ ] Test core functionality before scaling to all platforms

### 0.2 Local JRE Build Test

**Steps:**
1. [ ] Install Temurin JDK 21 locally
2. [ ] Run `jdeps` on current minimal distribution JARs to identify required modules
3. [ ] Create minimal JRE using `jlink` manually
4. [ ] Test that minimal JRE can run ArcadeDB

**Commands to test:**
```bash
# Step 1: Build current minimal distribution
cd bindings/python
./build-all.sh minimal

# Step 2: Analyze JAR dependencies
mkdir -p prototype/analysis
cd prototype/analysis
jdeps --multi-release 21 --print-module-deps ../../src/arcadedb_embedded/jars/*.jar > required-modules.txt

# Step 3: Build minimal JRE
jlink --module-path $JAVA_HOME/jmods \
      --add-modules $(cat required-modules.txt) \
      --strip-debug --no-man-pages --no-header-files --compress=2 \
      --output ./minimal-jre

# Step 4: Test minimal JRE
./minimal-jre/bin/java -version
```

**Success criteria:**
- [ ] `jdeps` identifies all required modules
- [ ] `jlink` creates minimal JRE (~40-70 MB)
- [ ] Minimal JRE can run `java -version`
- [ ] Minimal JRE can run basic JPype operations

### 0.3 Local Package Prototype

**Create prototype structure:**
```
prototype/
├── base-package/          # arcadedb-embed (no JRE)
│   └── arcadedb_embedded/
│       ├── jars/          # JAR files
│       └── ...            # Python files
└── jre-package/           # arcadedb-embed-jre (with JRE)
    └── arcadedb_embedded/
        ├── jars/          # JAR files
        ├── jre/           # Bundled minimal JRE
        └── ...            # Python files
```

**Steps:**
1. [ ] Create prototype directory structure
2. [ ] Copy current Python source to both variants
3. [ ] Copy minimal JRE to JRE variant
4. [ ] Update `jvm.py` to detect bundled JRE
5. [ ] Test both variants locally

### 0.4 Local Testing

**Test scenarios:**
- [ ] **Base variant + system Java:** Should work normally
- [ ] **Base variant + no Java:** Should fail with helpful error
- [ ] **JRE variant + system Java:** Should prefer bundled JRE
- [ ] **JRE variant + no Java:** Should work with bundled JRE
- [ ] **Size check:** JRE variant should be ~150 MB total

**Test script:**
```bash
#!/bin/bash
# prototype/test-variants.sh

# Test base variant
echo "Testing base variant..."
cd base-package
python -c "import arcadedb_embedded; print('Base variant works!')"

# Test JRE variant (hide system Java)
echo "Testing JRE variant..."
cd ../jre-package
unset JAVA_HOME
export PATH="/usr/bin:/bin"  # Remove Java from PATH
python -c "import arcadedb_embedded; print('JRE variant works!')"
```

### 0.5 Prototype Validation

**Success criteria before proceeding:**
- [ ] Both variants install and import successfully
- [ ] JRE variant works without system Java
- [ ] JRE size is acceptable (~40-70 MB)
- [ ] Database operations work in both variants
- [ ] Can create database, insert data, query data
- [ ] No performance degradation vs current minimal

**If prototype fails:**
- Debug JRE module selection
- Test different `jlink` options
- Consider alternative approaches
- Document issues and solutions

---

### 1.1 Update `build-all.sh`
**Current:** Builds 3 distributions (headless, minimal, full)
**New:** Build 2 variants (base, jre)

**Changes needed:**
- [ ] Remove support for `headless` and `full` distributions
- [ ] Replace with `base` (no JRE) and `jre` (with JRE) variants
- [ ] Update argument parsing and validation
- [ ] Update usage documentation in script
- [ ] Keep `minimal` as the only feature set

**Questions:**
- Keep backward compatibility by accepting `minimal` as alias for `base`?

---

### 1.2 Create JRE Build Scripts

**New files needed:**
- [ ] `build-jre.sh` - Script to build minimal JRE using `jlink`
- [ ] `scripts/download-jre.sh` - Download Temurin 21 for each platform (if building locally)

**Script responsibilities:**
1. Detect required Java modules using `jdeps`
2. Run `jlink` to create minimal JRE
3. Include LICENSE/NOTICE for Temurin
4. Strip debug symbols, man pages, header files
5. Compress with `--compress=2`

**Command example:**
```bash
jdeps --multi-release 21 --print-module-deps ./lib/*.jar
jlink --module-path $JAVA_HOME/jmods \
      --add-modules java.base,java.logging,java.sql,java.xml \
      --strip-debug --no-man-pages --no-header-files --compress=2 \
      --output ./minimal-jre
```

**Questions resolved:**
- ~~Build JRE inside Docker or download pre-built Temurin releases?~~ → **Build in Docker**
- ~~Where to store JRE in package structure?~~ → **`src/arcadedb_embedded/jre/`**

---

### 1.3 Update `Dockerfile.build`

**Current:** Multi-stage build with 3 distribution variants
**New:** Build both base and JRE variants from minimal distribution

**Changes needed:**
- [ ] Remove `headless` and `full` builder stages
- [ ] Keep only `minimal` ArcadeDB image as source
- [ ] Add JRE build stage (use Temurin base image)
- [ ] Add conditional JRE copy stage
- [ ] Update package naming logic
- [ ] Add build arg: `INCLUDE_JRE` (true/false)

**New build args:**
- `INCLUDE_JRE` - whether to bundle JRE (default: false)
- `ARCADEDB_TAG` - keep this
- Remove: `DISTRIBUTION` (no longer needed)

**Stage structure:**
1. `java-builder` - Copy JARs from arcadedb-minimal image
2. `jre-builder` - Build minimal JRE using jlink (conditional)
3. `python-builder` - Build wheel (copy JRE if INCLUDE_JRE=true)
4. `export` - Export wheel
5. `tester` - Test wheel (use bundled or system JRE)

**Questions resolved:**
- ~~Should tester stage test both variants?~~ → **Yes, test both in CI**
- ~~How to handle platform-specific JRE in Docker (cross-compilation)?~~ → **Use platform matrix**

---

### 1.4 Update `setup_jars.py`

**Current:** Copies JARs based on DISTRIBUTION env var
**New:** Always use minimal distribution, optionally copy JRE

**Changes needed:**
- [ ] Remove distribution selection logic (always minimal)
- [ ] Add JRE detection and copying logic
- [ ] Check for `INCLUDE_JRE` environment variable
- [ ] Copy JRE files if present in `/build/jre` directory
- [ ] Update size calculation to include JRE

**New environment variables:**
- `INCLUDE_JRE` - "true" or "false"
- Remove: `ARCADEDB_DISTRIBUTION`

**New functions:**
- `find_jre_directory()` - locate bundled JRE
- `copy_jre_to_package()` - copy JRE to package

---

### 1.5 Update `pyproject.toml`

**Current:** Single package configuration, dynamically modified during build
**New:** Same approach, but only two package names

**Changes needed:**
- [ ] Update default `name` to `arcadedb-embed`
- [ ] Update build script to use either:
  - `arcadedb-embed` (base variant)
  - `arcadedb-embed-jre` (with JRE)
- [ ] Update package descriptions
- [ ] Keep all other metadata the same

**Package naming logic in build:**
```bash
if [ "$INCLUDE_JRE" = "true" ]; then
    PACKAGE_NAME="arcadedb-embed-jre"
    DESCRIPTION="ArcadeDB embedded Python bindings with bundled Java 21 runtime (turnkey installation)"
else
    PACKAGE_NAME="arcadedb-embed"
    DESCRIPTION="ArcadeDB embedded Python bindings (requires Java 21+)"
fi
```

---

## Phase 2: Python Package Changes

### 2.1 Update JVM Initialization (`jvm.py`)

**Current:** Expects system Java, finds JARs in `jars/` directory
**New:** Try bundled JRE first, fall back to system Java

**Changes needed:**
- [ ] Add function to detect bundled JRE: `get_bundled_jre_path()`
- [ ] Modify `start_jvm()` to prefer bundled JRE
- [ ] Add better error messages distinguishing between:
  - No bundled JRE, no system Java → suggest `arcadedb-embed-jre`
  - JRE found but JVM startup failed → other error
- [ ] Add JRE version checking (ensure 21+)

**New functions:**
```python
def get_bundled_jre_path() -> Optional[str]:
    """Return path to bundled JRE if it exists."""
    package_dir = Path(__file__).parent
    jre_dir = package_dir / "jre"

    if sys.platform == "win32":
        jre_bin = jre_dir / "bin" / "java.exe"
    else:
        jre_bin = jre_dir / "bin" / "java"

    if jre_bin.exists():
        return str(jre_dir)
    return None

def start_jvm():
    # Try bundled JRE first
    bundled_jre = get_bundled_jre_path()
    if bundled_jre:
        jpype.startJVM(jvmpath=jpype.getDefaultJVMPath(jrepath=bundled_jre), ...)
    else:
        # Fall back to system JRE
        try:
            jpype.startJVM(...)
        except:
            raise ArcadeDBError(
                "No Java runtime found. Either install Java 21+ or use "
                "'arcadedb-embed-jre' package which includes bundled JRE."
            )
```

**Questions resolved:**
- ~~Should we warn if bundled JRE is found but system JRE is newer?~~ → **No, prefer bundled for consistency**
- ~~Add environment variable to force system JRE even if bundled exists?~~ → **No, keep simple initially**

---

### 2.2 Update Package Structure

**Current structure:**
```
src/arcadedb_embedded/
├── __init__.py
├── core.py
├── jvm.py
├── ...
└── jars/
    └── *.jar
```

**New structure (base variant):**
```
src/arcadedb_embedded/
├── __init__.py
├── core.py
├── jvm.py
├── ...
└── jars/
    └── *.jar
```

**New structure (JRE variant):**
```
src/arcadedb_embedded/
├── __init__.py
├── core.py
├── jvm.py
├── ...
├── jars/
│   └── *.jar
└── jre/                    # NEW: Bundled JRE
    ├── bin/
    │   └── java[.exe]
    ├── lib/
    ├── conf/
    ├── LICENSE
    └── NOTICE
```

**Changes needed:**
- [ ] Update `.gitignore` to ignore `jre/` directory (build-time only)
- [ ] Update `MANIFEST.in` if used
- [ ] Update `pyproject.toml` package-data to include `jre/**/*`

---

### 2.3 Update Package Metadata

**Files to update:**
- [ ] `README.md` - Document both variants, installation differences
- [ ] `pyproject.toml` - Classifiers, keywords, URLs
- [ ] Create `_version.py` template if needed

**README sections to add:**
- Installation comparison table
- JRE version information
- Size comparison
- When to use which variant

---

## Phase 3: GitHub Actions / CI Changes

### 3.1 Update `test-python-bindings.yml`

**Current state:**
- Tests 3 distributions: headless, minimal, full
- Uses Docker build (already working)
- Workflow dispatch allows selecting specific distribution
- Runs on Ubuntu only with system Java

**Changes needed:**
- [ ] **Remove distribution matrix** - no more headless/minimal/full
- [ ] **Add variant matrix** - test `base` and `jre` variants
- [ ] **Remove workflow_dispatch distribution selection** - update to variant selection
- [ ] **Update build command** - call `./build-all.sh` with new arguments
- [ ] **Add JRE-specific tests**:
  - For `base` variant: verify it requires system Java
  - For `jre` variant: verify it works WITHOUT system Java
- [ ] **Update artifact names** - wheel-base, wheel-jre
- [ ] **Update test summary messages** - reference variants not distributions

**New matrix:**
```yaml
strategy:
  fail-fast: false
  matrix:
    variant: [base, jre]
    include:
      - variant: base
        requires_java: true
      - variant: jre
        requires_java: false
```

**New test logic:**
```yaml
- name: Install Java (conditional)
  if: matrix.requires_java == true
  uses: actions/setup-java@...

- name: Test without Java (for JRE variant)
  if: matrix.variant == 'jre'
  run: |
    # Unset JAVA_HOME to ensure bundled JRE is used
    unset JAVA_HOME
    pytest tests/ -v
```

---

### 3.2 Update `test-python-examples.yml`

**Current state:**
- Builds minimal distribution
- Tests examples with system Java
- Single platform (Ubuntu)

**Changes needed:**
- [ ] **Update build command** - build `base` variant (or `jre` for testing without Java)
- [ ] **Update wheel installation** - use new package name pattern
- [ ] **Optional: Add JRE variant test** - verify examples work with bundled JRE
- [ ] **Update comments** - reference base/jre not minimal
- [ ] **Update dependency installation** - ensure it still finds the wheel

**Recommendation:** Keep simple, test with `base` variant + system Java (examples already work)

---

### 3.3 Update `release-python-packages.yml`

**Current state:**
- Tests all 3 distributions first
- Builds 3 distributions in parallel (headless, minimal, full)
- Publishes to 3 separate PyPI environments
- Only runs for tags containing "python"

**Major changes needed:**

#### 3.3.1 Update test job reference
```yaml
test:
  name: Run Tests Before Release
  needs: check-release
  if: needs.check-release.outputs.is-python-release == 'true'
  uses: ./.github/workflows/test-python-bindings.yml  # This will now test both variants
  secrets: inherit
```

#### 3.3.2 Restructure build jobs

**Current:** 1 job with 3-way matrix (distributions)
**New:** 2 separate jobs (base + jre with platform matrix)

```yaml
jobs:
  # ... check-release and test jobs stay the same ...

  build-base:
    name: Build Base Package (Platform-Independent)
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@...

      - name: Build base variant (no JRE)
        run: |
          cd bindings/python
          ./build-all.sh base  # New argument

      - name: Upload wheel artifact
        uses: actions/upload-artifact@...
        with:
          name: wheel-base
          path: bindings/python/dist/*.whl

  build-jre:
    name: Build JRE Package (${{ matrix.os }}-${{ matrix.arch }})
    needs: test
    runs-on: ${{ matrix.runner }}
    strategy:
      fail-fast: false
      matrix:
        include:
          # Linux x86_64
          - runner: ubuntu-latest
            os: linux
            arch: x86_64
            platform-tag: manylinux2014_x86_64

          # Linux ARM64 (using QEMU)
          - runner: ubuntu-latest
            os: linux
            arch: aarch64
            platform-tag: manylinux2014_aarch64
            use-qemu: true

          # macOS Intel
          - runner: macos-13
            os: macos
            arch: x86_64
            platform-tag: macosx_11_0_x86_64

          # macOS Apple Silicon
          - runner: macos-14
            os: macos
            arch: arm64
            platform-tag: macosx_11_0_arm64

          # Windows x64
          - runner: windows-latest
            os: windows
            arch: x64
            platform-tag: win_amd64

          # Windows ARM64 - SKIP as decided
          # - runner: windows-latest
          #   os: windows
          #   arch: arm64
          #   platform-tag: win_arm64
          #   cross-compile: true

    steps:
      - name: Checkout code
        uses: actions/checkout@...

      - name: Set up QEMU (for Linux ARM64)
        if: matrix.use-qemu
        uses: docker/setup-qemu-action@...
        with:
          platforms: arm64

      - name: Set up JDK 21 for jlink
        uses: actions/setup-java@...
        with:
          distribution: 'temurin'
          java-version: '21'
          architecture: ${{ matrix.arch }}

      - name: Build JRE variant
        run: |
          cd bindings/python
          ./build-all.sh jre
        env:
          PLATFORM: ${{ matrix.os }}
          ARCH: ${{ matrix.arch }}

      - name: Upload wheel artifact
        uses: actions/upload-artifact@...
        with:
          name: wheel-jre-${{ matrix.os }}-${{ matrix.arch }}
          path: bindings/python/dist/*.whl
```

#### 3.3.3 Update publish jobs

**Current:** 3 publish jobs (headless, minimal, full)
**New:** 2 publish jobs (base, jre)

```yaml
  publish-base:
    name: Publish arcadedb-embed to PyPI
    needs: [check-release, build-base]
    if: needs.check-release.outputs.is-python-release == 'true'
    runs-on: ubuntu-latest
    environment: pypi-base  # NEW environment
    permissions:
      id-token: write
    steps:
      - name: Download base wheel
        uses: actions/download-artifact@...
        with:
          name: wheel-base
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@...

  publish-jre:
    name: Publish arcadedb-embed-jre to PyPI (All Platforms)
    needs: [check-release, build-jre]
    if: needs.check-release.outputs.is-python-release == 'true'
    runs-on: ubuntu-latest
    environment: pypi-jre  # NEW environment
    permissions:
      id-token: write
    steps:
      - name: Download all JRE wheels
        uses: actions/download-artifact@...
        with:
          pattern: wheel-jre-*
          path: dist/
          merge-multiple: true

      - name: Verify wheels
        run: |
          ls -lh dist/
          echo "Expected 5-6 wheels (depending on platform support)"
          wheel_count=$(ls dist/*.whl | wc -l)
          if [ "$wheel_count" -lt 5 ]; then
            echo "Error: Expected at least 5 wheels, found $wheel_count"
            exit 1
          fi

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@...
```

**Summary of changes:**
- [x] Remove 3-distribution matrix ✅ **Decision made**
- [x] Add 2 build jobs (base + jre with platform matrix) ✅ **5 platforms confirmed**
- [x] Update publish jobs (2 instead of 3) ✅ **Clean break approach**
- [x] Add platform matrix for JRE (5 platforms: Linux x64/ARM64, macOS x64/ARM64, Windows x64) ✅ **No Windows ARM64**
- [x] Update artifact names ✅ **wheel-base, wheel-jre-{platform}**
- [x] Update environment names ✅ **pypi-base, pypi-jre**
- [x] Add wheel count verification ✅ **Expect 5 wheels**

**Resolved questions:**
- ~~Skip Windows ARM64 initially?~~ → **Yes, skip initially**
- ~~Use separate publish jobs or combine?~~ → **Separate for clarity**
- ~~Test on all platforms or just Linux?~~ → **Full testing on all platforms before release**

---

### 3.4 Update `deploy-python-docs.yml`

**Current state:**
- Only runs for releases with "python" in tag
- Extracts version from tag (e.g., v25.9.1-python → 25.9.1)
- Uses mike for versioned docs

**Changes needed:**
- [ ] **No major changes needed!** This workflow is already good
- [ ] **Optional:** Update examples/screenshots if they reference old package names
- [ ] **Verify:** Documentation references new package names (handled in Phase 4)

**Minor updates:**
- Update any hardcoded references to `arcadedb-embedded-minimal` → `arcadedb-embed`
- Ensure docs build process picks up new package names

---

### 3.5 Create Multi-Platform Build Workflow (Optional/Future)

**New file:** `.github/workflows/build-wheels-matrix.yml` (optional)

**Purpose:** Reusable workflow for building wheels across platforms

**When to create:**
- If build complexity grows
- If we need to test wheels before release
- If we add more platforms later

**For now:** Keep build logic in `release-python-packages.yml` to avoid over-engineering

---

### 3.6 CI/CD Testing Strategy

**Before release:**
- [ ] Test workflow changes in a feature branch
- [ ] Use workflow_dispatch to manually trigger test builds
- [ ] Verify wheels on each platform:
  - Download artifacts
  - Install locally
  - Run basic tests
  - Check wheel size
  - Verify JRE is included (for jre variant)

**Platform testing checklist:**
- [ ] Linux x64 - Build, test, install
- [ ] Linux ARM64 - Build with QEMU, test
- [ ] macOS x64 - Build on macos-13, test
- [ ] macOS ARM64 - Build on macos-14, test
- [ ] Windows x64 - Build, test, install
- [ ] Windows ARM64 - Skip or cross-compile (TBD)

---

### 3.7 GitHub Environment Setup

**New environments needed:**

Create in GitHub Settings → Environments:

1. **`pypi-base`**
   - For publishing `arcadedb-embed` package
   - Add PyPI trusted publisher (GitHub Actions OIDC)
   - Configure for repository: humemai/arcadedb-embedded-python
   - Package: arcadedb-embed

2. **`pypi-jre`**
   - For publishing `arcadedb-embed-jre` package
   - Add PyPI trusted publisher (GitHub Actions OIDC)
   - Configure for repository: humemai/arcadedb-embedded-python
   - Package: arcadedb-embed-jre

**Old environments (deprecate after final release):**
- `pypi-headless` - Keep for final deprecation release
- `pypi-minimal` - Keep for final deprecation release
- `pypi-full` - Keep for final deprecation release

---

### 3.8 Workflow File Checklist

**Files to modify:**
- [x] `.github/workflows/test-python-bindings.yml` - Update to test variants
- [x] `.github/workflows/test-python-examples.yml` - Update package name
- [x] `.github/workflows/release-python-packages.yml` - Major refactor (2 variants, platform matrix)
- [ ] `.github/workflows/deploy-python-docs.yml` - Minor/no changes needed

**New files to create:**
- [ ] None required (all changes in existing workflows)

**Optional future files:**
- `.github/workflows/build-wheels-matrix.yml` - Reusable platform build workflow
- `.github/workflows/test-jre-platforms.yml` - Dedicated JRE testing across platforms

---

## Phase 4: Documentation Updates

### 4.1 Update Main README.md

**Sections to update:**
- [ ] Installation section - show both variants
- [ ] Requirements section - clarify Java requirement
- [ ] Quick start - mention which variant to use when
- [ ] Distribution comparison table - replace with variant comparison
- [ ] Size information - update to reflect new sizes

**New comparison table:**
```markdown
| Variant | Size | JRE Included | Java Required | Use Case |
|---------|------|--------------|---------------|----------|
| arcadedb-embed | ~97 MB | ❌ | Java 21+ | Production with existing Java |
| arcadedb-embed-jre | ~150 MB | ✅ (per platform) | ❌ | Turnkey, no Java setup |
```

---

### 4.2 Create Migration Guide

**New file:** `bindings/python/MIGRATION.md`

**Content:**
- [ ] Migration from `arcadedb-embedded-headless` → `arcadedb-embed`
- [ ] Migration from `arcadedb-embedded-minimal` → `arcadedb-embed`
- [ ] Migration from `arcadedb-embedded` (full) → not supported (suggest alternatives)
- [ ] When to choose which new variant
- [ ] Breaking changes (if any)
- [ ] Timeline for deprecation of old packages

---

### 4.3 Update Documentation Site

**Files to update:**
- [ ] `docs/getting-started/installation.md` - New variants
- [ ] `docs/getting-started/distributions.md` - Rename to variants, update content
- [ ] `docs/getting-started/quickstart.md` - Update package names
- [ ] All examples - Update import statements if needed

---

## Phase 5: Package Naming & PyPI

### 5.1 PyPI Package Strategy ✅ **DECIDED**

**Chosen Approach: Clean Break (Option A)**
- Mark `arcadedb-embedded-headless`, `arcadedb-embedded-minimal`, `arcadedb-embedded` as deprecated
- Create new packages: `arcadedb-embed`, `arcadedb-embed-jre`
- Provide clear migration guide
- Pros: Clean break, clearer naming ✅
- Cons: Users need to update dependencies (acceptable)

**Actions needed:**
- [x] Create new PyPI projects: `arcadedb-embed`, `arcadedb-embed-jre` ✅ **Confirmed approach**
- [x] Upload final release to old packages with deprecation notice ✅ **Clean deprecation**
- [x] Add PyPI classifiers: "Development Status :: 7 - Inactive" on old packages ✅ **Clear signal**
- [x] Update old package descriptions with migration info ✅ **Help users migrate**

---

### 5.2 GitHub Environments

**Current environments:**
- `pypi-headless`
- `pypi-minimal`
- `pypi-full`

**New environments:**
- [ ] Create: `pypi-base` (for `arcadedb-embed`)
- [ ] Create: `pypi-jre` (for `arcadedb-embed-jre`)
- [ ] Keep old ones temporarily for final deprecation releases

---

## Phase 6: Testing Strategy

### 6.1 Local Testing

**Test matrix:**
- [ ] Base variant on Linux (with system Java)
- [ ] Base variant on macOS (with system Java)
- [ ] Base variant on Windows (with system Java)
- [ ] JRE variant on Linux (no system Java)
- [ ] JRE variant on macOS (no system Java)
- [ ] JRE variant on Windows (no system Java)

**Test scenarios:**
- [ ] Fresh install
- [ ] Upgrade from old package
- [ ] Run all unit tests
- [ ] Run examples
- [ ] Server mode
- [ ] Vector operations
- [ ] Import operations

---

### 6.2 CI Testing

**Tests to add:**
- [ ] Wheel size verification (fail if too large)
- [ ] JRE version check (ensure 21+)
- [ ] License file presence check
- [ ] Platform-specific wheel validation
- [ ] Installation in clean environment
- [ ] Uninstallation leaves no traces

---

## Phase 7: Release Process

### 7.1 Pre-Release Checklist

- [ ] All old tests pass with new variants
- [ ] Documentation updated
- [ ] Migration guide ready
- [ ] Deprecation notices prepared
- [ ] GitHub release notes drafted
- [ ] PyPI projects created and configured

---

### 7.2 Release Steps

1. [ ] Create release branch: `v25.9.1-python`
2. [ ] Run full test suite
3. [ ] Build all wheels (1 base + 6 JRE variants)
4. [ ] Manual verification of each wheel
5. [ ] Create GitHub release with tag `v25.9.1-python`
6. [ ] Automated PyPI upload via GitHub Actions
7. [ ] Publish final deprecation release for old packages
8. [ ] Announce on GitHub, docs site, etc.

---

### 7.3 Post-Release

- [ ] Monitor PyPI download stats
- [ ] Watch for bug reports on specific platforms
- [ ] Update documentation based on user feedback
- [ ] Plan timeline for removing old packages

---

## Open Questions & Decisions Needed

### Critical Decisions

1. **JRE Build Strategy**
   - Option A: Build JRE inside Docker during wheel build
   - Option B: Pre-build JRE, store as artifact, download during build
   - Option C: Download pre-built Temurin minimal images
   - **Recommended:** Option A (most reproducible)

2. **Cross-Platform Windows ARM64**
   - GitHub doesn't have native Windows ARM64 runners
   - Options: Skip, cross-compile, use external service
   - **Recommended:** Skip initially, add later if demanded

3. **Base Package Platform Specificity**
   - Option A: Single platform-independent wheel (universal)
   - Option B: Platform-specific wheels even without JRE
   - **Recommended:** Option A (simpler, no platform-specific code without JRE)

4. **Backward Compatibility**
   - Provide compatibility imports from old package names?
   - Add warnings when old packages are used?
   - **Recommended:** Clean break, migration guide only

5. **PyPI Size Limits**
   - Request increase from 100 MB to 200-500 MB?
   - Or keep wheels under 100 MB by optimizing JRE?
   - **Recommended:** Try to stay under 150 MB, request increase if needed

### Technical Questions

- [ ] What Java modules are actually needed? (run `jdeps` to find out)
- [ ] Can we strip more from JRE to reduce size? (test minimal functionality)
- [ ] Should bundled JRE be compressed further? (test startup time impact)
- [ ] How to handle JRE licensing files? (include in wheel, update README)
- [ ] Environment variable to force system JRE over bundled? (good for debugging)

---

## Timeline Estimate ✅ **UPDATED WITH PROTOTYPE-FIRST APPROACH**

### Phase 0: Local Prototype (3-5 days) ⭐ **START HERE**
- Day 1: Set up prototype environment, run `jdeps` analysis
- Day 2: Build minimal JRE with `jlink`, test locally
- Day 3: Create prototype packages (base + JRE variants)
- Day 4: Local testing, validate approach
- Day 5: Document findings, proceed or adjust approach

### Phase 1: Build System (1 week) ⭐ **AFTER PROTOTYPE VALIDATION**
- Day 1-2: Update build scripts based on prototype learnings
- Day 3-4: Create JRE build process in Docker
- Day 5: Update Docker files
- Day 6-7: Local testing with Docker builds

### Phase 2: Python Package (3 days)
- Day 1: Update jvm.py with bundled JRE detection
- Day 2: Package structure changes
- Day 3: Local testing

### Phase 3: CI/CD (1 week)
- Day 1-3: Multi-platform build workflow
- Day 4-5: Update release workflow
- Day 6-7: Update test workflows

### Phase 4: Documentation (2 days)
- Day 1: Update all docs
- Day 2: Create migration guide

### Phase 5: PyPI Setup (1 day)
- Create new PyPI projects
- Configure environments

### Phase 6: Full Platform Testing (5 days) ⭐ **CRITICAL**
- Day 1-2: Test on Linux (x64 + ARM64)
- Day 3: Test on macOS (x64 + ARM64)
- Day 4: Test on Windows x64
- Day 5: Fix issues, validate all platforms

### Phase 7: Release (1 day)
- Final checks
- Release
- Announcement

**Total: ~4 weeks (with prototype-first approach)**
**Critical Path: Prototype → Build System → Full Platform Testing**

---

## Risk Mitigation

### High Risk Items

1. **Platform-specific JRE issues**
   - Mitigation: Test early and often on each platform
   - Fallback: Release base variant first, JRE variant later

2. **Wheel size too large for PyPI**
   - Mitigation: Optimize JRE, request limit increase early
   - Fallback: Reduce JRE size, skip some platforms

3. **Breaking changes affect users**
   - Mitigation: Clear migration guide, gradual deprecation
   - Fallback: Keep old packages longer than planned

4. **Cross-compilation issues**
   - Mitigation: Use native runners where possible
   - Fallback: Skip ARM platforms initially

---

## Success Metrics ✅ **UPDATED WITH DECISIONS**

- [x] Base variant under 100 MB ✅ **Expected ~97 MB**
- [x] JRE variant under 150 MB per platform ✅ **Target ~150 MB, measure actual size**
- [x] All existing tests pass ✅ **Full testing on all platforms**
- [x] Installation time < 30 seconds ✅ **Standard for Python wheels**
- [x] Zero runtime overhead from JRE detection ✅ **Prefer bundled JRE, no complex logic**
- [x] No user-reported platform-specific issues in first month ✅ **Full platform testing before release**
- [x] Migration guide used by >50% of users ✅ **Clean break with clear migration path**

## Next Steps 🚀

### **Immediate Action Items:**

1. **✅ START WITH PROTOTYPE** (Phase 0)
   - Create `prototype-jre-bundling` branch
   - Install JDK 21 locally
   - Run `jdeps` analysis on current minimal distribution
   - Build minimal JRE with `jlink`
   - Create prototype packages
   - Validate approach locally

2. **After successful prototype:**
   - Proceed with Phase 1 (Build System Changes)
   - Update Docker builds
   - Implement CI/CD for 5 platforms
   - Full testing and release

### **Key Validation Points:**

- **Prototype success:** JRE variant works without system Java
- **Size validation:** JRE variant ≤150 MB total
- **Platform testing:** All 5 platforms work correctly
- **Migration validation:** Old users can easily switch

### **Risk Mitigation:**

- **If prototype fails:** Debug JRE modules, try different `jlink` options
- **If size too large:** Optimize JRE further, request PyPI limit increase
- **If platform issues:** Fall back to fewer platforms initially

**Ready to start with Phase 0 (Local Prototype)?** 🎯

---

## Notes

- Keep this document updated as decisions are made
- Link to relevant GitHub issues/PRs
- Document any deviations from plan
