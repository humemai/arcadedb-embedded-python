# ArcadeDB Python Bindings - TODO

**Last Updated:** 2025-10-28
**Status:** Implementation Phase

---

## 📋 Overview

This document tracks all pending work for the ArcadeDB Python bindings project, organized by priority.

### Current State

- ✅ **Tag-driven release strategy** - implemented and ready
- ✅ **JRE bundling** - validated and integrated into build system
- ✅ **Single-package strategy** - JRE bundled by default in `arcadedb-embedded`
- ✅ **Multi-platform CI/CD** - **COMPLETED with native runners for all 6 platforms**
  - **Solution Implemented**: Native GitHub runners for all platforms
  - **Platforms Supported**: **6 platforms total** ✅
    - linux/amd64 (Docker - manylinux compliance on ubuntu-24.04)
    - linux/arm64 (Docker - native ARM64 on ubuntu-24.04-arm)
    - darwin/amd64 (Native - macOS Intel on macos-15-intel)
    - darwin/arm64 (Native - macOS Apple Silicon on macos-15)
    - windows/amd64 (Native - Windows x64 on windows-2025)
    - windows/arm64 (Native - Windows ARM64 on windows-11-arm)
  - **Philosophy**: Maximum platform support with native performance and reproducibility
- ✅ **Testing & Validation** - All 6 platforms passing 43/43 tests!
- ✅ **Pinned Runners** - All runner versions pinned for reproducible builds

### Key Decisions Made
- ✅ **Release strategy:** Tag-driven versioning (manual git tags like `25.10.1.dev0`, `25.10.1`, `25.10.1.post0`)
- ✅ **Package strategy:** Single package `arcadedb-embedded` with JRE bundled by default (~160MB)
  - JRE adds only ~40MB compressed but eliminates external Java dependency
  - Simpler user experience: one package, zero configuration
  - Cross-platform JRE sizes are consistent (60-70MB decompressed)
- ✅ **macOS builds:** Native (no Docker, use `actions/setup-java`)
- ✅ **Windows builds:** Native (no Docker, use `actions/setup-java`)
- ✅ **Examples testing:** Optimized triggers (PR to main + workflow_call + manual)
- ✅ **Documentation:** Deploy only for stable versions (skip `.devN` versions)

---

## ✅ Multi-Platform Build System - COMPLETE!

**Status:** ✅ COMPLETE - All 6 platforms working with native runners!

### Final Solution: Native GitHub Runners for All Platforms

**Supported Platforms (6):**

- ✅ **linux/amd64** - `ubuntu-24.04` (Docker native build)
- ✅ **linux/arm64** - `ubuntu-24.04-arm` (Docker native, ARM64 runner)
- ✅ **darwin/amd64** - `macos-15-intel` (native build, Intel Mac)
- ✅ **darwin/arm64** - `macos-15` (native build, Apple Silicon)
- ✅ **windows/amd64** - `windows-2025` (native build, x64)
- ✅ **windows/arm64** - `windows-11-arm` (native build, ARM64)

### Accomplishments (CI run #96 - 2025-10-28)

**Final Wheel Sizes:**

- linux/amd64: 160.9M (JRE: 62.7M) - 43/43 tests ✅
- linux/arm64: 159.9M (JRE: 61.8M) - 43/43 tests ✅
- darwin/amd64: 157.8M (JRE: 55.3M) - 43/43 tests ✅
- darwin/arm64: 156.7M (JRE: 53.9M) - 43/43 tests ✅
- windows/amd64: 157.4M (JRE: 51.5M) - 43/43 tests ✅
- windows/arm64: 155.1M (JRE: 47.3M) - 43/43 tests ✅

**All Platforms:**

- ✅ 43/43 tests passing on all platforms
- ✅ 167.4M JARs (83 files, identical across platforms, gRPC excluded)
- ✅ ~40MB savings per wheel (was 195.9M, now ~155-161M)
- ✅ All native runners (no QEMU emulation)
- ✅ Pinned runner versions for reproducibility

**Architecture Improvements:**

1. **Single JAR filtering point**: download-jars job filters once (Ubuntu bash), uploads artifact
2. **Artifact strategy**: Pre-filtered JARs for native builds, skip artifact for Docker
3. **Structured test data**: pytest --junitxml for reliable cross-platform parsing
4. **Code reduction**: Removed ~90 lines of duplicate filtering logic
5. **Native ARM64 runners**: Switched from QEMU to GitHub ARM64 runners (3-4x faster)
6. **Platform-specific JVM detection**: Added Windows/macOS/Linux JVM library paths
7. **Pinned runner versions**: All platforms use specific runner versions for reproducibility

### Issues Resolved

1. ✅ Docker python-builder copying wrong JARs → Fixed: copy from jre-builder not java-builder
2. ✅ Linux artifact conflict → Fixed: skip artifact download for Docker builds
3. ✅ linux/arm64 host testing → Fixed: enabled with native ARM64 runner
4. ✅ Windows glob pattern failure → Fixed: moved JAR filtering upstream to Ubuntu
5. ✅ JAR filtering duplication → Fixed: single upstream filter in download-jars job
6. ✅ Test count parsing failure → Fixed: grep -P (GNU-only) → JUnit XML (POSIX)
7. ✅ Bash counter increment → Fixed: set -e compatibility
8. ✅ QEMU performance overhead → Fixed: switched to native ARM64 runners (15-20min → 5-7min)
9. ✅ Windows ARM64 JVM detection → Fixed: platform-specific JVM library paths (jvm.dll vs libjvm.so)
10. ✅ Runner version reproducibility → Fixed: pinned all runner versions (ubuntu-24.04, macos-15, etc.)

### Why This Approach Works

1. GitHub Actions provides native runners for all major platforms (including ARM64!)
2. Docker provides consistent Linux builds with multi-platform support
3. Each platform builds with platform-specific JRE via native `jlink`
4. True platform-specific wheels served by PyPI based on user's platform
5. Single upstream JAR filtering eliminates duplication and cross-platform issues
6. Native ARM64 runners eliminate QEMU overhead (3-4x faster builds)
7. Pinned runner versions ensure reproducible builds over time
8. Platform-specific JVM detection enables all 6 platforms to work correctly

### Implementation Tasks

#### Phase 3.6: Multi-Platform Optimization and Refinement - ✅ COMPLETE

**NOTE:** Phase 3.6 evolved significantly beyond original plan:

**Original Plan:** Refactor to native runners for 4 platforms
**Final Achievement:** 6 platforms with native runners and optimized builds

**Accomplishments:**

- ✅ Added linux/arm64 support (initially via QEMU, then native runner)
- ✅ Added windows/arm64 support (6th platform with windows-11-arm runner)
- ✅ Implemented single upstream JAR filtering (jar_exclusions.txt)
- ✅ Switched to JUnit XML for reliable cross-platform test parsing
- ✅ Achieved ~40MB savings per wheel via gRPC exclusion
- ✅ Switched from QEMU to native GitHub ARM64 runners (3-4x performance improvement)
- ✅ Fixed Windows ARM64 JVM detection (platform-specific library paths)
- ✅ Pinned all runner versions for reproducible builds
- ✅ Simplified JVM initialization (always uses bundled JRE)
- ✅ 43/43 tests passing on all 6 platforms

**All original tasks superseded by superior 6-platform implementation.**

**Original Plan (Obsolete):**

**Build System Changes:**

- [ ] **Update `build.sh`**
  - Remove Docker-based build for darwin/windows
  - Add native build mode (use system Java + jlink directly)
  - Keep Docker build only for linux platforms
  - Auto-detect: if running on macOS → native build, if Linux → Docker

- [ ] **Create platform-specific wheel tags**
  - linux/amd64: `manylinux_2_17_x86_64`
  - darwin/amd64: `macosx_10_9_x86_64`
  - darwin/arm64: `macosx_11_0_arm64`
  - windows/amd64: `win_amd64`
  - Use `--plat-name` flag in `python -m build --wheel`

- [ ] **Update `Dockerfile.build`**
  - Keep only for linux builds
  - Remove TARGET_PLATFORM logic (not needed with native runners)
  - Simplify to single linux-x64 build

**CI/CD Changes:**

- [ ] **Update `.github/workflows/test-python-bindings.yml`**
  ```yaml
  strategy:
    matrix:
      include:
        - platform: linux/amd64
          runs-on: ubuntu-latest
        - platform: darwin/amd64
          runs-on: macos-13
        - platform: darwin/arm64
          runs-on: macos-latest
        - platform: windows/amd64
          runs-on: windows-latest
  ```

- [ ] **Update `.github/workflows/release-python-packages.yml`**
  - Same matrix changes as test workflow
  - Update wheel count validation: expect 4 wheels (not 5)
  - Remove QEMU setup (not needed)
  - Remove Docker Buildx setup for darwin/windows builds

- [ ] **Update `.github/workflows/test-python-examples.yml`**
  - Same matrix changes
  - Each platform tests on its native runner

**Documentation Changes:**

- [x] **Update `README.md` (root and bindings/python/)** ✅
  - Updated to 6 platforms (added windows/arm64)
  - Added platform badges and comparison tables
  - Updated all build instructions for native builds
  - Removed all QEMU references

- [x] **Update `TODO.md`** ✅
  - Marked Phase 3.6 complete
  - Updated platform count throughout (6 platforms)
  - Updated accomplishments with CI run #96 results

- [ ] **Update `bindings/python/docs/getting-started/distributions.md`**
  - Platform support table: 4 platforms
  - Expected wheel sizes (will vary by platform now!)

### Testing Plan

1. [ ] Create test branch: `fix/native-platform-builds`
2. [ ] Implement changes incrementally
3. [ ] Test locally on available platforms
4. [ ] Create test tag: `25.10.1.dev99`
5. [ ] Verify GitHub Actions creates 4 different wheels
6. [ ] Download and inspect wheels (different SHA256, different JRE binaries)
7. [ ] Test one wheel per platform if possible
8. [ ] Merge to `prototype-jre-bundling`
9. [ ] Delete test tag

### Expected Outcomes

**Before (Broken):**
- 5 wheels with identical linux-x64 JRE
- SHA256: slightly different (timestamps)
- Size: 160.8M all platforms (identical)
- Tests: all pass (same binary)

**After (Fixed):**
- 4 wheels with platform-specific JREs
- SHA256: completely different (different binaries)
- Size: varies by platform (darwin JRE slightly larger, windows slightly smaller)
- Tests: all pass on native platforms
- PyPI: serves correct wheel based on user's platform

---

## ✅ Single-Package Release Strategy - COMPLETE!

**Goal:** Simplify to single package `arcadedb-embedded` with JRE bundled by default

**Status:** Phase 3.1-3.4 complete! Ready for Phase 3.5 (Testing & Validation)

### Rationale

- JRE adds only ~40MB compressed (160MB vs 120MB wheel)
- Eliminates external Java dependency entirely
- Simpler user experience: one package name, zero configuration
- Cross-platform JRE sizes are consistent (60-70MB decompressed)
- No confusion about which variant to install

### Impact Assessment: Files to Change

**⚠️ IMPORTANT:** This is a significant architectural change affecting multiple layers.

#### Build System (5 files)

- `bindings/python/build.sh` - Remove variant parameter
- `bindings/python/Dockerfile.build` - Remove VARIANT arg, always build JRE
- `bindings/python/setup_jars.py` - Remove variant logic, always copy JRE
- `bindings/python/pyproject.toml` - Package name (no -jre suffix)
- `bindings/python/build-jre.sh` - No changes needed

#### CI/CD Workflows (4 files)

- `.github/workflows/test-python-bindings.yml` - Remove variant matrix
- `.github/workflows/release-python-packages.yml` - Remove variant matrix, single publish job
- `.github/workflows/test-python-examples.yml` - Verify compatibility (likely no changes)
- `.github/workflows/deploy-python-docs.yml` - Verify package name references

#### Documentation (8+ files)

- `README.md` (root) - Remove dual badges, variant table, update installation
- `bindings/python/README.md` - Same as root
- `bindings/python/docs/ARCHITECTURE.md` - NEW: document JRE bundling
- `bindings/python/docs/getting-started/*` - Update installation instructions
- `bindings/python/docs/development/build-architecture.md` - ✅ Moved from BUILD.md
- `bindings/python/docs/development/ci-setup.md` - ✅ Moved from CI_SETUP.md
- `CONTRIBUTING.md` - Update build instructions
- Any other docs mentioning base/jre variants

#### Cleanup (multiple files/dirs)

- Search all files for "base variant", "jre variant", "arcadedb-embedded-jre"
- Remove prototype directory or archive to docs/historical/
- Clean up temporary/generated files

**Total Impact: ~20+ files across repository**

### Phase 3.1: Simplify Build System

#### 3.1.1 Update `build.sh`

- [x] Remove variant parameter (1st arg) - ✅ COMPLETE
- [x] Platform is now 1st (and only) optional arg - ✅ COMPLETE
- [x] Update help text: emphasize bundled JRE - ✅ COMPLETE
- [x] Default to current platform if no `--platform` specified - ✅ COMPLETE
- [x] Remove references to `base` variant throughout - ✅ COMPLETE

**Expected behavior:**
```bash
./build.sh                        # Current platform with JRE
./build.sh linux/amd64            # Specific platform
./build.sh linux/arm64            # Linux ARM64 (native)
```

#### 3.1.2 Update `pyproject.toml`

- [x] Package name: `arcadedb-embedded` (no `-jre` suffix)
- [x] Update description: "ArcadeDB embedded database with bundled JRE"
- [x] Verify JRE files included in package-data
- [x] Update classifiers if needed
- [x] Update URLs (PyPI badge will point to single package)

#### 3.1.3 Update `Dockerfile.build`
- [x] Remove `VARIANT` build arg (always build JRE) - ✅ COMPLETE
- [x] Simplify: always run jre-builder stage - ✅ COMPLETE
- [x] Remove `ARCADEDB_VARIANT` environment variable - ✅ COMPLETE
- [x] Remove `INCLUDE_JRE` environment variable (redundant) - ✅ COMPLETE
- [x] Remove conditional logic for JRE copying - ✅ COMPLETE

#### 3.1.4 Update `setup_jars.py`
- [x] Remove `ARCADEDB_VARIANT` environment variable checks - ✅ COMPLETE
- [x] Always copy JRE (renamed `copy_jre_if_needed()` to `copy_jre()`) - ✅ COMPLETE
- [x] Simplify to single code path - ✅ COMPLETE

#### 3.1.5 Update other build scripts

- [x] `build-jre.sh`: **REMOVED** - inlined into Dockerfile.build ✅ COMPLETE
- [x] `extract_version.py`: No changes needed - ✅ VERIFIED
- [x] `write_version.py`: No changes needed - ✅ VERIFIED

### Phase 3.2: Simplify CI/CD Workflows

#### 3.2.1 Update `test-python-bindings.yml`

- [x] Remove variant matrix (only test single package) - ✅ COMPLETE
- [x] Remove variant input from `workflow_dispatch` - ✅ COMPLETE
- [x] Update platform matrix to all 5 platforms: `[linux/amd64, linux/arm64, darwin/amd64, darwin/arm64, windows/amd64]` - ✅ COMPLETE
- [x] Update job name: "Test arcadedb-embedded (${{ matrix.platform }})" - ✅ COMPLETE
- [x] Update artifact names: `wheel-${{ matrix.platform }}-test` - ✅ COMPLETE
- [x] Update build command: `./build.sh ${{ matrix.platform }}` - ✅ COMPLETE
- [x] Remove Java installation step (JRE bundled!) - ✅ COMPLETE

#### 3.2.2 Update `release-python-packages.yml`

- [x] Remove variant matrix (only build single package) - ✅ COMPLETE
- [x] Keep platform matrix: updated to `[linux/amd64, linux/arm64, darwin/amd64, darwin/arm64, windows/amd64]` - ✅ COMPLETE
- [x] Remove `publish-jre` job entirely - ✅ COMPLETE
- [x] Rename `publish-base` → `publish` - ✅ COMPLETE
- [x] Update wheel download pattern: `wheel-*` (no variant in name) - ✅ COMPLETE
- [x] Update wheel count validation: expect 5 wheels (one per platform) - ✅ COMPLETE
- [x] Update environment: use `pypi` (not `pypi-base` or `pypi-jre`) - ✅ COMPLETE
- [x] Update PyPI package name verification: check for `arcadedb-embedded` only - ✅ COMPLETE
- [x] Update build command: `./build.sh ${{ matrix.platform }}` - ✅ COMPLETE
- [x] Remove `VARIANT` environment variable - ✅ COMPLETE
- [x] Update job matrix to remove variant column - ✅ COMPLETE

#### 3.2.3 Update `test-python-examples.yml`

- [x] Add platform matrix: `[linux/amd64, linux/arm64, darwin/amd64, darwin/arm64, windows/amd64]` - ✅ COMPLETE
- [x] Update build command: `./build.sh ${{ matrix.platform }}` - ✅ COMPLETE
- [x] Add native ARM64 runners for all platforms - ✅ COMPLETE
- [x] Update artifact names to include platform - ✅ COMPLETE
- [x] Add summary job for all platforms - ✅ COMPLETE
- [x] Remove Java installation step (JRE bundled!) - ✅ COMPLETE (was already removed)
- [x] Verify workflow_call compatibility - ✅ VERIFIED

#### 3.2.4 Update `deploy-python-docs.yml`

- [x] Verify package name references (should be `arcadedb-embedded`) - ✅ VERIFIED
- [x] No changes needed (no variant references) - ✅ VERIFIED

#### 3.2.5 GitHub Environment Setup

- [ ] Create single `pypi` environment in GitHub repo settings
- [ ] Configure Trusted Publisher for `arcadedb-embedded` (not -jre)
- [ ] Request PyPI size limit increase (162MB > 100MB default)
- [ ] Remove any references to `pypi-base` or `pypi-jre` environments

**Note**: This task requires GitHub repo admin access and will be done during release

### Phase 3.3: Update Documentation

#### 3.3.1 Update `README.md` (repository root)
- [x] Remove dual PyPI badges (keep only `arcadedb-embedded`) ✅
- [x] Update installation section: single command `pip install arcadedb-embedded` ✅
- [x] Remove "Package Variants" comparison table ✅
- [x] Update requirements: "Python 3.8+ only (JRE bundled)" - no Java needed ✅
- [x] Remove references to separate `-jre` package ✅
- [x] Update package size: ~160MB (was 123MB for base) ✅
- [x] Emphasize "No Java installation required" prominently ✅
- [x] Update all code examples (no changes, but verify context) ✅

#### 3.3.2 Update `bindings/python/README.md`
- [x] Same changes as root README.md ✅
- [x] Emphasize bundled JRE in title/intro ✅
- [x] Remove variant comparison sections ✅
- [x] Update installation examples ✅
- [x] Add platform support table (5 platforms) ✅
- [x] Document wheel size: ~160MB ✅

#### 3.3.3 Create `bindings/python/docs/ARCHITECTURE.md`
- [ ] Optional: New file documenting JRE bundling architecture
- [ ] List 21 Java modules included via jlink
- [ ] Size breakdown (63MB JRE + 13MB JARs + 84MB Python/native)
- [x] Platform support details (6 platforms) ✅
- [ ] Build process overview (Docker + jlink)
- [x] Cross-platform building approach (native runners for all platforms) ✅

#### 3.3.4 Update `bindings/python/docs/` content
- [x] `getting-started/distributions.md`: Updated to single package ✅
- [x] Verified other docs: no variant references found ✅
- [ ] Optional: Review other docs for consistency

#### 3.3.5 Update Other Documentation Files
- [ ] `CONTRIBUTING.md`: Update build instructions (no variant parameter)
- [ ] `bindings/python/TODO.md`: Already updated ✅
- [x] Move `bindings/python/BUILD.md` → `docs/development/build-architecture.md` ✅
- [x] Move `bindings/python/CI_SETUP.md` → `docs/development/ci-setup.md` ✅
- [ ] Update prototype documentation references
- [ ] Check for any other files referencing base/jre variants

### Phase 3.4: Cleanup Obsolete Code

**Note**: Most cleanup already done in Phase 3.1-3.3. Remaining tasks below.

#### 3.4.1 Remove Variant Logic from Python Code
- [x] `build.sh`: Removed variant parameter ✅ (Phase 3.1.1)
- [x] `setup_jars.py`: Removed ARCADEDB_VARIANT checks ✅ (Phase 3.1.4)
- [x] `Dockerfile.build`: Removed VARIANT build arg ✅ (Phase 3.1.3)
- [x] `build-jre.sh`: Deleted and inlined ✅ (Phase 3.1.5)

#### 3.4.2 Remove Variant Logic from Workflows
- [x] `test-python-bindings.yml`: Removed variant matrix ✅ (Phase 3.2.1)
- [x] `release-python-packages.yml`: Removed variant matrix, publish-jre job ✅ (Phase 3.2.2)
- [x] `test-python-examples.yml`: Removed variant references ✅ (Phase 3.2.3)

#### 3.4.3 Remove Variant Logic from Documentation
- [x] Root `README.md`: Removed variant badges, comparison tables ✅ (Phase 3.3.1)
- [x] `bindings/python/README.md`: Removed variant sections ✅ (Phase 3.3.2)
- [x] `bindings/python/docs/getting-started/distributions.md`: Updated to single package ✅ (Phase 3.3.4)
- [x] Verified no variant references in other docs ✅ (Phase 3.3.4)

#### 3.4.4 Optional Cleanup Tasks
- [ ] Archive prototype files to `bindings/python/docs/historical/` if desired
- [x] BUILD.md and CI_SETUP.md moved to docs/development/ ✅
- [ ] Clean up `dist/` test wheels if desired

### Phase 3.5: Testing & Validation ⬅️ **NEXT PHASE**

#### Testing Matrix

| Platform | System Java | Expected | Status |
|----------|-------------|----------|--------|
| Linux x64 | No Java | ✅ Works | ✅ Tested locally (162MB) |
| Linux ARM64 | No Java | ✅ Works | ⏸️ Ready to test |
| macOS x64 | No Java | ✅ Works | ⏸️ Ready to test |
| macOS ARM64 | No Java | ✅ Works | ⏸️ Ready to test |
| Windows x64 | No Java | ✅ Works | ⏸️ Ready to test |

#### Recommended Testing Approach

**Option A: Quick Validation (Recommended First)**
1. [ ] Create test tag on this branch: `git tag 25.10.1.dev99 && git push origin 25.10.1.dev99`
2. [ ] Watch GitHub Actions run all workflows:
   - Unit tests on all 5 platforms (automated)
   - Example tests on all 5 platforms (automated)
   - Build wheels for all 5 platforms (automated)
   - Verify 5 wheels created with correct size (~162MB each)
3. [ ] Download artifacts from GitHub Actions
4. [ ] Test one wheel locally (install + quick test)
5. [ ] Delete test tag: `git tag -d 25.10.1.dev99 && git push origin :refs/tags/25.10.1.dev99`

**Option B: Full Local Testing (Time-consuming)**
- [ ] Build locally for all 6 platforms (requires Docker for Linux builds)
- [ ] Verify wheel sizes ~155-161MB for all platforms
- [ ] Install each wheel in fresh environment
- [ ] Run full test suite (43 tests) on each platform
- [ ] Performance benchmarks (optional)

**Option C: Merge and Let CI Do the Work**
1. [ ] Review all changes one final time
2. [ ] Merge `prototype-jre-bundling` → `main`
3. [ ] Create real dev tag: `git tag 25.10.1.dev0 && git push origin 25.10.1.dev0`
4. [ ] Monitor release workflow (tests + builds + publishes to PyPI)
5. [ ] Test installed package from PyPI

#### Current Status
- ✅ Build system complete (all 5 files updated)
- ✅ CI/CD workflows complete (all 4 workflows updated)
- ✅ Documentation complete (README.md, docs, etc.)
- ✅ All variant logic removed
- ✅ Single `pypi` environment configured
- ⏸️ Ready for end-to-end testing!

---

## 🎯 High Priority: Implement Tag-Driven Releases ✅

### 1. Update `extract_version.py`
- [x] Add `--tag-version` flag to accept explicit version string
  ```python
  parser.add_argument('--tag-version', help='Use explicit version from git tag')
  if args.tag_version:
      return args.tag_version
  ```
- [x] Test locally: `python3 extract_version.py --tag-version 25.10.1.dev0`
- [x] Verify it returns the exact version passed

### 2. Update `release-python-packages.yml`

- [x] Add version sanity check:
  - Extract version from `pom.xml` (e.g., `25.10.1-SNAPSHOT` → `25.10.1`)
  - Extract version from `${{ github.ref_name }}` tag (e.g., `25.10.1.dev0` → `25.10.1`)
  - Verify they match (fail build if mismatch)
  - This prevents accidentally releasing wrong version (e.g., tagging `25.9.1.dev0` when pom.xml says `25.10.1-SNAPSHOT`)
- [x] Extract version from `${{ github.ref_name }}` (the git tag)
- [x] Call `test-python-examples.yml` via `workflow_call` before building
- [x] Pass version to build via `BUILD_VERSION` environment variable
- [x] Update `Dockerfile.build` to accept `BUILD_VERSION` arg
- [x] Update `build.sh` to pass `BUILD_VERSION` to Docker
- [ ] Test with a test tag (next step after updating test-python-examples.yml)

### 3. Update `test-python-examples.yml`
- [x] Change triggers to:
  ```yaml
  on:
    pull_request:
      branches: [main]
    workflow_call:  # Called by release workflow
    workflow_dispatch:  # Manual testing
  ```
- [x] Remove `push:` trigger (examples take 30-60 min, too slow for every commit)

### 4. Update `deploy-python-docs.yml`
- [x] Add logic to skip `.devN` versions
- [x] Only deploy for stable versions (`25.10.1`, `25.10.1.post0`, etc.)
- [ ] Test with `workflow_dispatch`

### 5. Cleanup
- [x] Delete `.github/workflows/release-python-dev-packages.yml`
- [x] Delete `bindings/python/.dev_version_tracker.json`
- [ ] Commit changes

### Testing
- [ ] Create test tag: `git tag 25.10.1.dev0 && git push origin 25.10.1.dev0`
- [ ] Verify workflow triggers correctly
- [ ] Verify version extracted matches tag
- [ ] Delete test tag after validation: `git tag -d 25.10.1.dev0 && git push origin :refs/tags/25.10.1.dev0`

---

## 🚀 Low Priority: JRE Bundling Implementation (Historical) ✅

**Status:** Phase 1 & 2 complete. JRE bundling successfully implemented and tested.
**Next:** Phase 3 (single-package strategy) - see above.

<details>
<summary>Click to expand Phase 1 & 2 completed tasks</summary>

### Phase 1: Local Build System ✅

- [x] Update `build.sh` - JRE variant enabled, platform detection added
- [x] Create `build-jre.sh` - Standalone JRE builder with 21 modules
- [x] Update `Dockerfile.build` - Added jre-builder stage
- [x] Update `setup_jars.py` - Added copy_jre_if_needed() function
- [x] Update `pyproject.toml` - Added jre/**/* to package-data
- [x] Validation - All tests pass, database operations work with bundled JRE

### Phase 2: Multi-Platform Support (Superseded by Phase 3)

- Phase 2 tasks for dual-package approach are no longer needed
- Moving to single-package strategy with JRE bundled by default

</details>

---

## 📝 Low Priority: Code Quality & Cleanup

### Documentation
- [x] Review all `.md` files in `bindings/python/` ✅
- [x] Move detailed plans to `docs/` subdirectory ✅
- [x] Keep only essential files in root (README.md, TODO.md) ✅

### Code Quality
- [ ] Fix lint errors in `extract_version.py`
- [ ] Add type hints to Python scripts
- [ ] Add docstrings to all functions
- [ ] Review error messages

---

## 📚 Reference Files

- `bindings/python/build.sh` - Build orchestrator
- `bindings/python/extract_version.py` - Version management
- `bindings/python/setup_jars.py` - Package preparation
- `bindings/python/Dockerfile.build` - Docker build
- `bindings/python/prototype/` - Working JRE bundling example
- `.github/workflows/release-python-packages.yml` - Release automation
- `.github/workflows/test-python-bindings.yml` - CI testing
- `.github/workflows/test-python-examples.yml` - Example validation
- `.github/workflows/deploy-python-docs.yml` - Documentation deployment
