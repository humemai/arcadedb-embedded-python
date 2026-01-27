# Multi-Platform JRE Bundling Architecture

This document describes the build architecture for creating platform-specific Python wheels with bundled JRE for ArcadeDB Embedded.

## Overview

**Goal:** Distribute a single `arcadedb-embedded` package that works on 3 platforms with **zero Java installation required**.

**Achievement:** 3 platform-specific wheels (~63–115MB compressed) with bundled platform-specific JRE, built and tested on GitHub Actions using native runners.

## Supported Platforms

| Platform | Wheel Size | JRE Size | Runner | Build Method | Notes |
|----------|-----------|----------|---------|--------------|-------|
| **linux/amd64** | 115.2M | 249.0M | `ubuntu-24.04` | Docker native | Most common Linux platform |
| **linux/arm64** | 114.1M | 249.6M | `ubuntu-24.04-arm` | Docker native | ARM64 servers, Raspberry Pi |
| **darwin/arm64** | 63.1M | 55.1M | `macos-15` | Native build | Apple Silicon Macs (2020+) |

**All supported platforms:**

- ✅ 252 tests passing
- ✅ 31.7M JARs (83 files, identical across platforms)
- ✅ All native runners (no QEMU emulation)
- ✅ Reproducible builds (pinned runner versions)

## Architecture

### Build Strategy

We use a **hybrid build approach** to create platform-specific wheels:

1. **Linux platforms:** Docker native builds
    - linux/amd64: Native Docker on `ubuntu-24.04`
    - linux/arm64: Native Docker on `ubuntu-24.04-arm` (GitHub ARM64 runner)
    - Builds platform-specific JRE via `jlink`

2. **macOS platform:** Native builds
    - Uses platform-specific GitHub Actions runner
    - Native `jlink` creates correct JRE for the platform
    - Pre-filtered JARs from artifact (eliminates glob issues)

**Critical:** All wheels are **platform-specific** (not `py3-none-any`). This is achieved by:

1. **setup.py with BinaryDistribution class**: Overrides default behavior
2. **Platform-specific JRE**: Each wheel contains native binaries
3. **Platform tags**: Automatically set by setuptools based on JRE contents

### Why Platform-Specific Wheels Matter

Initially, we were creating `py3-none-any` wheels because:

- `pyproject.toml` alone doesn't communicate platform-specificity to setuptools
- Without `setup.py`, setuptools assumes "pure Python" package
- Result: All platforms got same wheel name, uv pip couldn't select correct one

**The Solution - setup.py**:

```python
from setuptools import setup
from setuptools.dist import Distribution

class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name"""
    def has_ext_modules(self):
        return True  # Tells setuptools: "I have platform-specific content!"

setup(
    distclass=BinaryDistribution,
    # ... rest of setup
)
```

This simple class tells setuptools "this package has binary content" which:

- Triggers platform-specific wheel naming
- Makes uv pip download the correct wheel for each platform
- Enables platform tags like `macosx_11_0_arm64`, `manylinux_2_17_x86_64`, etc.

**Without setup.py**: All platforms → `arcadedb_embedded-X.Y.Z-py3-none-any.whl` (wrong!)

**With setup.py**: Each platform → `arcadedb_embedded-X.Y.Z-py3-none-<platform>.whl` (correct!)

See `bindings/python/setup.py` for the complete implementation.

### Why This Works

**Key Insight:** `jlink` can ONLY create JREs for the platform it's running on.

- Running `jlink` on macOS-amd64 → Creates macOS-amd64 JRE ✅
- Running `jlink` in Docker on linux-x64 → Creates linux-x64 JRE ✅
- Running `jlink` in Docker on linux-arm64 → Creates linux-arm64 JRE ✅
- Running `jlink` with `--platform linux/arm64` on x64 → **Still creates linux-x64 JRE** ❌

**Solution:** Run builds on native hardware for each platform.

## Build Pipeline

### Two-Job Strategy

```yaml
jobs:
  download-jars:
    runs-on: ubuntu-24.04
    # Downloads 84 ArcadeDB JARs, filters to 83, uploads artifact

  test:
    needs: download-jars
    strategy:
      matrix:
        platform: [linux/amd64, linux/arm64, darwin/arm64]
    # Builds platform-specific wheel, runs tests
```

### Job 1: download-jars (Ubuntu)

**Purpose:** Single point of JAR filtering to avoid cross-platform issues.

**Steps:**

1. Download 84 JARs from ArcadeDB Docker image
2. Read `jar_exclusions.txt` (single source of truth)
3. Filter out excluded JARs (currently: `arcadedb-grpcw-*.jar`)
4. Result: 83 JARs (167.4M)
5. Upload as artifact for native builds

**Why Ubuntu?** Bash filtering works reliably and avoids cross-platform glob differences.

### Job 2: test (Matrix)

**Platform-specific build and test:**

#### Linux Platforms (Docker)

1. Run Docker multi-stage build on native ARM64/AMD64 runner
2. Build platform-specific wheel:
    - `jre-builder`: Creates platform-specific JRE via `jlink`
    - `python-builder`: Builds wheel with bundled JRE
3. Skip artifact download (Docker gets JARs directly)
4. Tests run on same native platform

#### macOS Platform (Native)

1. Download pre-filtered JARs artifact
2. Run `build-native.sh`:
    - Uses system Java (GitHub runner provides Java 25)
    - Runs `jlink` natively → platform-specific JRE
    - Builds wheel with `python -m build`
3. Run tests on native platform

## JAR Exclusion System

### Single Source of Truth: `jar_exclusions.txt`

**Location:** `bindings/python/jar_exclusions.txt`

**Format:** One glob pattern per line
```
arcadedb-grpcw-*.jar
```

**Used by:**

1. `.github/workflows/test-python-bindings.yml` (download-jars job)
2. `bindings/python/Dockerfile.build` (Docker builds)
3. `bindings/python/setup_jars.py` (documentation/validation)

**Result:** ~40MB savings per wheel (gRPC is ~38MB)

### Implementation

**Before (Broken):** Each build step filtered independently

- `build-native.sh`: Filtered with bash on macOS
- `Dockerfile.build`: Filtered with bash on Linux
- `setup_jars.py`: Filtered with Python glob
- **Problem:** Glob patterns varied across shells, causing duplication and inconsistency

**After (Fixed):** Single upstream filter

- `download-jars` job: Filters once on Ubuntu (reliable bash)
- Native builds: Use pre-filtered JARs from artifact
- Docker builds: Filter independently (different source)
- **Result:** Consistent 83 JARs across all platforms

## Test Parsing

### JUnit XML for Reliable Results

**Challenge:** Parse test results across Linux (bash) and macOS (BSD tools)

**Solution:** Structured data via pytest's JUnit XML output

```bash
# Run tests with XML output
pytest tests/ --junitxml=test-results.xml

# Parse with POSIX-compatible grep (not GNU-only grep -P)
tests_run=$(grep -oE 'tests="[0-9]+"' test-results.xml | grep -oE '[0-9]+')
failures=$(grep -oE 'failures="[0-9]+"' test-results.xml | grep -oE '[0-9]+')
errors=$(grep -oE 'errors="[0-9]+"' test-results.xml | grep -oE '[0-9]+')
```

**Benefits:**

- ✅ Cross-platform compatible (POSIX grep, not GNU)
- ✅ Structured data (no fragile regex)
- ✅ Reliable counts (no sed greediness issues)

## Docker Multi-Stage Build

### Stages

```dockerfile
# Stage 1: java-builder (downloads JARs from ArcadeDB image)
FROM arcadedb/arcadedb:24.11.1 AS java-builder
# Downloads 84 JARs to /jars

# Stage 2: jre-builder (filters JARs, creates JRE)
FROM eclipse-temurin:21-jdk AS jre-builder
COPY --from=java-builder /jars/*.jar /jars/
# Reads jar_exclusions.txt
# Filters to 83 JARs (167.4M)
# Runs jlink → creates /jre (platform-specific!)

# Stage 3: python-builder (builds wheel)
FROM python:3.12-slim
COPY --from=jre-builder /jars/*.jar /jars/
COPY --from=jre-builder /jre /jre
# Builds wheel with bundled JRE
```

### Key Fix: Copy from jre-builder, not java-builder

**Bug:** Originally copied from `java-builder` → got 84 JARs (unfiltered)
**Fix:** Copy from `jre-builder` → gets 83 JARs (filtered)

## Native Build Script

### `build-native.sh` Workflow

```bash
# 1. Check for pre-filtered JARs (from artifact)
if [ -d "$JARS_DIR" ]; then
  echo "Using existing JARs from artifact"
else
  # Fallback: download from Docker (not used in CI)
  download_jars_from_docker
fi

# 2. Create platform-specific JRE via jlink
jlink --output jre \
  --add-modules "$MODULES" \
  --strip-debug \
  --no-man-pages \
  --no-header-files \
  --compress zip-6

# 3. Copy JARs and JRE to package
python setup_jars.py

# 4. Build wheel
python -m build --wheel
```

**Simplification:** Removed ~30 lines of JAR filtering logic (now uses pre-filtered artifact)

## GitHub ARM64 Runners (linux/arm64)

### Native ARM64 Support

As of late 2024, GitHub Actions provides **free native ARM64 runners** for public repositories:

```yaml
- platform: linux/arm64
  runs-on: ubuntu-24.04-arm  # Native ARM64 runner
```

### Benefits

- **Native performance:** No emulation overhead (3-4x faster than QEMU)
- **True platform builds:** `jlink` creates actual ARM64 JRE
- **Free for public repos:** Part of GitHub Actions free tier
- **Consistent with other platforms:** Same build process as linux/amd64

### Build Process

```bash
docker build \
  --platform linux/arm64 \
  --build-arg TARGETARCH=arm64 \
  -t arcadedb-python-builder:arm64 \
  .
```

Since the runner itself is ARM64, Docker builds run natively without emulation.

## File Structure

```
bindings/python/
├── jar_exclusions.txt          # Single source of truth for JAR filtering
├── build-native.sh             # Native builds (macOS)
├── Dockerfile.build            # Docker builds (Linux)
├── setup_jars.py               # Copies JARs/JRE to package
├── pyproject.toml              # Package metadata, dependencies
└── src/arcadedb/
    └── jre/                    # Bundled JRE (created during build)
        ├── bin/java            # Platform-specific Java binary
        ├── lib/                # JRE libraries
        └── ...
```

## Build Workflow File

**Location:** `.github/workflows/test-python-bindings.yml`

**Key sections:**

1. **download-jars job** (lines 18-89)
    - Downloads and filters JARs once
    - Uploads artifact for native builds

2. **test job matrix** (lines 91-364)
    - Builds 3 platforms
    - Platform-specific steps (native runners, artifact download, tests)

3. **Test parsing** (lines 200-237)
    - JUnit XML generation and parsing
    - Cross-platform compatible

## Common Issues & Solutions

### Issue 1: All Platforms Created Identical Linux Wheels

**Problem:** Original Docker-only approach built linux-x64 JRE for all platforms.

**Solution:** Native runners for macOS, Docker only for Linux.

### Issue 2: Test Count Parsing Failed

**Problem:** `grep -P` (Perl regex) not available on macOS.

**Solution:** Switch to JUnit XML + POSIX-compatible `grep -oE`.

### Issue 3: Docker Copied Unfiltered JARs

**Problem:** `python-builder` copied from `java-builder` (84 JARs) instead of `jre-builder` (83 JARs).

**Solution:** Change `COPY --from=java-builder` to `COPY --from=jre-builder`.

### Issue 4: Linux Builds Downloaded Unnecessary Artifact

**Problem:** Linux Docker builds downloaded pre-filtered artifact but didn't use it.

**Solution:** Skip artifact download for Linux platforms (Docker gets JARs directly).

### Issue 5: Bash Counter Increment Failed

**Problem:** `COUNTER=$((COUNTER+1))` failed with `set -e` in bash.

**Solution:** Use `((COUNTER++))` or `COUNTER=$((COUNTER + 1))` (spaces matter).

### Issue 6: Sed Pattern Too Greedy

**Problem:** Sed regex captured too much when parsing test output.

**Solution:** Switch to JUnit XML (structured data, no regex).

## Size Breakdown (current, as of 26-Jan-2026)

**linux/amd64**

- Wheel: 115.2M (compressed)
- JRE: 249.0M (uncompressed)
- JARs: 31.7M (uncompressed)
- Installed: ~281M (uncompressed)

**linux/arm64**

- Wheel: 114.1M (compressed)
- JRE: 249.6M (uncompressed)
- JARs: 31.7M (uncompressed)
- Installed: ~281M (uncompressed)

**darwin/arm64**

- Wheel: 63.1M (compressed)
- JRE: 55.1M (uncompressed)
- JARs: 31.7M (uncompressed)
- Installed: ~87M (uncompressed)

### Why Sizes Vary by Platform

- JRE binaries differ by platform (different native code and compression).
- Linux wheels include larger JRE footprints than macOS arm64.

## Development

### Local Build

```bash
# Build for current platform
cd bindings/python
./build-native.sh

# Or use Docker (Linux only)
docker build -f Dockerfile.build -t arcadedb-python-builder .
```

### Test Locally

```bash
# Install wheel
uv pip install dist/arcadedb_embedded-*.whl

# Run tests
pytest tests/
```

## References

- **jlink documentation:** [Oracle jlink man page](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jlink.html)
- **GitHub Actions runners:** [GitHub-hosted runners](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)
- **GitHub ARM64 runners:** [Supported runners and hardware resources](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#supported-runners-and-hardware-resources)
- **pytest JUnit XML:** [pytest JUnit XML output](https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files)
