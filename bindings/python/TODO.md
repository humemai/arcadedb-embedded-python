# ArcadeDB Python Bindings - TODO

**Last Updated:** 2025-10-28
**Status:** Production Ready - Documentation Updates Remaining

---

## 🎉 What's Complete

**All core functionality is working and tested!**

- ✅ **6-Platform Support**: linux (x64/arm64), macOS (Intel/Apple Silicon), Windows (x64/arm64)
- ✅ **Platform-Specific Wheels**: Correct wheel tags (manylinux, macosx, win) - no more py3-none-any
- ✅ **Build System**: Native runners for all platforms, Docker for Linux (manylinux compliance)
- ✅ **Testing**: 43/43 tests passing on all 6 platforms
- ✅ **Tag-Driven Releases**: Manual git tags trigger full release workflow
- ✅ **GitHub Releases**: All 6 wheels attached automatically
- ✅ **GitHub Pages PyPI Index**: pip-compatible index at https://humemai.github.io/arcadedb-embedded-python/simple/
- ✅ **Distribution**: Users can install with `pip install arcadedb-embedded --index-url https://humemai.github.io/arcadedb-embedded-python/simple/`

**Installation works today!** Just pending PyPI size limit approval for direct PyPI distribution.

---

## 📋 Remaining Tasks

### High Priority: Documentation Updates

#### 1. Update Installation Documentation
**File**: `bindings/python/docs/getting-started/installation.md`

Current docs show old 3-variant system (headless/minimal/full). Need to update:

- [ ] Remove all references to old variants (headless/minimal/full)
- [ ] Update to single package: `arcadedb-embedded`
- [ ] Show GitHub Pages installation (current method):
  ```bash
  pip install arcadedb-embedded --index-url https://humemai.github.io/arcadedb-embedded-python/simple/
  ```
- [ ] Note PyPI size limit pending approval
- [ ] Update to "No Java required" (bundled JRE)
- [ ] Update platform support table (6 platforms)
- [ ] Update wheel sizes (~155-161MB)

#### 2. Update Build Architecture Documentation
**File**: `bindings/python/docs/development/build-architecture.md`

- [ ] Document setup.py requirement for platform-specific wheels
- [ ] Explain BinaryDistribution class and why it's needed
- [ ] Document actual wheel naming per platform (manylinux_2_17_x86_64 etc)
- [ ] Explain why py3-none-any was created before and how setup.py fixes it

#### 3. Update Examples Documentation
**File**: `bindings/python/examples/README.md`

- [ ] Update installation commands to use GitHub Pages index
- [ ] Remove any references to old variant system

#### 4. Update CONTRIBUTING.md
**File**: `CONTRIBUTING.md` (root)

- [ ] Update build instructions (no variant parameter)
- [ ] Update to single package workflow

### Medium Priority: Pending External Approvals

#### PyPI Size Limit Increase
**Status**: Request submitted to PyPI

- [ ] Wait for PyPI team response (requested 250MB limit)
- [ ] Once approved: Test direct PyPI publication
- [ ] Update docs to show standard `pip install arcadedb-embedded` as primary method
- [ ] Keep GitHub Pages as backup/mirror

### Low Priority: Optional Improvements

#### Architecture Documentation
- [ ] Optional: Create comprehensive architecture doc covering JRE bundling
- [ ] Document 21 Java modules included via jlink
- [ ] Size breakdown details

#### Workflow Optimizations
- [ ] Consider restoring full example testing (currently only testing example 01)
- [ ] Consider increasing HTTP benchmark operations back to 1000 (currently 100)

---

## 📚 Reference: Key Files

**Build System:**
- `bindings/python/build.sh` - Build orchestrator
- `bindings/python/setup.py` - Forces platform-specific wheels
- `bindings/python/Dockerfile.build` - Docker build for Linux
- `bindings/python/pyproject.toml` - Package configuration

**CI/CD:**
- `.github/workflows/test-python-bindings.yml` - Build & test on 6 platforms
- `.github/workflows/test-python-examples.yml` - Example validation
- `.github/workflows/release-python-packages.yml` - Release workflow (includes PyPI index update)
- `.github/workflows/deploy-python-docs.yml` - MkDocs deployment

**Documentation:**
- `README.md` (root) - ✅ Updated with GitHub Pages install
- `bindings/python/README.md` - ✅ Updated with GitHub Pages install
- `bindings/python/docs/getting-started/installation.md` - ❌ Needs update
- `bindings/python/docs/development/build-architecture.md` - ❌ Needs setup.py docs
