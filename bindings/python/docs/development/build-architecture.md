# Multi-Platform JRE Bundling Architecture

This document describes the build architecture for creating platform-specific Python wheels with bundled JRE for ArcadeDB Embedded.

## Overview

**Goal:** Distribute a single `arcadedb-embedded` package that works on 4 platforms with **zero Java installation required**.

**Achievement:** 4 platform-specific wheels with a bundled platform-specific JRE, built and tested on GitHub Actions using native runners. The 26.10.1.dev0 linux/amd64 wheel measured on 2026-09-29 is about 69 MB compressed and 96 MB installed; other platforms and versions vary slightly.

## Supported Platforms

| Platform | Runner | Build Method | Notes |
|----------|---------|--------------|-------|
| **linux/amd64** | `ubuntu-24.04` | Docker native | Most common Linux platform |
| **linux/arm64** | `ubuntu-24.04-arm` | Docker native | ARM64 servers, Raspberry Pi |
| **darwin/arm64** | `macos-15` | Native build | Apple Silicon Macs (2020+) |
| **windows/amd64** | `windows-2025` | Native build | Windows x86_64 |

**All supported platforms:**

- ✅ Full bindings suite passes on every platform build
- ✅ About 33 MB of JARs (measured on the linux/amd64 wheel; the same JAR set on every platform; includes server/Studio)
- ✅ All native runners (no QEMU emulation)
- ✅ Pinned runner versions
- ✅ One engine per run: by default the JARs are built from the tested commit's engine
  source (cached by that source), so two runs of the same commit embed the same engine;
  a stable release embeds upstream's official JARs instead (see
  [Where the engine JARs come from](#where-the-engine-jars-come-from))

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
    - JARs from the run's JAR artifact, filtered by `scripts/build-native.sh`

3. **Windows platform:** Native builds
    - Uses platform-specific GitHub Actions runner
    - Native `jlink` creates correct JRE for the platform
    - JARs from the run's JAR artifact, filtered by `scripts/build-native.sh`

Every platform of a run embeds the same JAR artifact; the Linux builds receive it as
`build.sh`'s `JAR_LIB_DIR`.

### Where the engine JARs come from

| Build | Engine JARs |
|-------|-------------|
| CI push, pull request, or dispatch (default, `jar-source: source`) | the full distribution built from the tested commit's engine source by `.github/workflows/build-engine-jars.yml`, cached by a hash of that source |
| CI with `jar-source: image` | `/home/arcadedb/lib` of `arcadedata/arcadedb:<image-tag>` |
| Stable release `X.Y.Z` or `X.Y.Z.postN` (`release-python-packages.yml`) | `/home/arcadedb/lib` of `arcadedata/arcadedb:X.Y.Z`, upstream's official JARs; built and tested on those, and published only after `verify-engine-jars.yml` finds the same classes in a build of the release commit |
| Dev release `X.Y.Z.devN` | the full distribution built from the tagged commit's source, as on a push; no gate, since no official image exists |
| Local `build.sh` (default) | `arcadedata/arcadedb:<tag>`, where the tag is `ARCADEDB_IMAGE_TAG` or the `pom.xml` version |
| Local `build.sh --engine-from-source` | the full distribution built from the checkout in a Maven container |
| Local `build.sh <platform> <python> <dir>` | the JARs in `<dir>` |

The source build and the official image of a stable release hold the same code: for 26.9.1 the
two matched in all 86 JAR names, all 69 third-party JARs byte for byte, and all 75,699
ArcadeDB classes byte for byte, and differed only in the `buildNumber`, `timestamp`, and
`branch` lines of `com/arcadedb/arcadedb.properties` (and in zip timestamps). That is why
`jar_fingerprint()` hashes JAR contents rather than files: both give the same
`engine_sha256`, and `build_number` tells them apart.

**Critical:** All wheels are **platform-specific** (not `py3-none-any`). This is achieved by:

1. **setup.py with BinaryDistribution class**: Overrides default behavior
2. **Platform-specific JRE**: Each wheel contains native binaries
3. **Platform tags**: Set per build method. The Linux Docker build passes
   `--plat-name=manylinux_2_34_<arch>` and then checks that tag against the highest GLIBC
   version the bundled JRE needs (`scripts/verify_wheel_platform_tag.py`). The macOS build
   sets `_PYTHON_HOST_PLATFORM=macosx-11.0-arm64` (`scripts/build-native.sh`). The Windows
   build takes `win_amd64` from the interpreter.

### Why Platform-Specific Wheels Matter

`pyproject.toml` alone does not tell setuptools that the package is platform-specific.
Without `setup.py`, setuptools treats it as a pure Python package, every platform gets the
same `py3-none-any` wheel name, and installers cannot select the correct one.

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
- Makes pip download the correct wheel for each platform
- Enables platform tags like `macosx_11_0_arm64`, `manylinux_2_34_x86_64`, etc.

**Without setup.py**: All platforms → `arcadedb_embedded-X.Y.Z-py3-none-any.whl` (wrong!)

**With setup.py**: Each platform → `arcadedb_embedded-X.Y.Z-cp<pyver>-cp<pyver>-<platform>.whl` (correct!)

See `bindings/python/setup.py` for the complete implementation.

### Why This Works

**Key Insight:** `jlink` can ONLY create JREs for the platform it's running on.

- Running `jlink` on macOS-amd64 → Creates macOS-amd64 JRE ✅
- Running `jlink` in Docker on linux-x64 → Creates linux-x64 JRE ✅
- Running `jlink` in Docker on linux-arm64 → Creates linux-arm64 JRE ✅
- Running `jlink` with `--platform linux/arm64` on x64 → **Still creates linux-x64 JRE** ❌

**Solution:** Run builds on native hardware for each platform.

## Build Pipeline

### Jobs

`test-python-bindings.yml` runs these jobs. `jar-source`, `engine-jars` or `image-jars`,
and `test` build the wheels:

```yaml
jobs:
  jar-source:
    # Validates the jar-source input (default: source) and resolves the image tag

  engine-jars:
    if: needs.jar-source.outputs.source == 'source'
    uses: ./.github/workflows/build-engine-jars.yml
    # Builds the engine from this commit (or restores it from the cache), uploads artifact

  image-jars:
    if: needs.jar-source.outputs.source == 'image'
    # Copies the ArcadeDB JARs out of arcadedata/arcadedb:<image-tag>, uploads artifact

  test:
    needs: [jar-source, engine-jars, image-jars]
    strategy:
      matrix:
        platform: [linux/amd64, linux/arm64, darwin/arm64, windows/amd64]
        python-version: ['3.10', '3.11', '3.12', '3.13', '3.14']
    # Builds platform-specific wheel, runs tests
```

The others are `bandit` (security scan), `dependency-floors` (audit of the declared
dependency floors), and `test-summary`. See [CI/CD Setup](ci-setup.md#ci-gates).

### Job 1: engine-jars or image-jars (Ubuntu)

**Purpose:** Produce the one ArcadeDB JAR set every platform of the run embeds.

**Steps:**

1. `engine-jars` (`jar-source: source`): `build-engine-jars.yml` restores the JARs for this
   commit's engine source from the cache, or builds the package module and everything it
   needs (`./mvnw -B -q -DskipTests -pl package -am package`, JDK 21) and saves them
2. `image-jars` (`jar-source: image`): copy `/home/arcadedb/lib` out of
   `arcadedata/arcadedb:<image-tag>` with `docker create` and `docker cp`
3. Upload the unfiltered set as the `arcadedb-jars` artifact, with a `BUILD-INFO.txt` that
   names the commit or image and the engine's `buildNumber`

The JARs are filtered later, by the build that packages them (see
[JAR Exclusion System](#jar-exclusion-system)).

### Job 2: test (Matrix)

**Platform-specific build and test:**

#### Linux Platforms (Docker)

1. Run Docker multi-stage build on native ARM64/AMD64 runner
2. Build platform-specific wheel:
    - `jre-builder`: Filters the JARs, compiles `arcadedb-python-bridge.jar`, and creates the
      platform-specific JRE via `jdeps` and `jlink`
    - `python-builder`: Builds wheel with bundled JRE
    - `tester`: Installs the wheel in a clean image and runs a create, insert, and query
      smoke script (not pytest)
3. Download the JAR artifact and pass it to `build.sh` as `JAR_LIB_DIR`, which stages it
   into `local-jars/lib` for the Docker build (with `jar-source: image`,
   `ARCADEDB_IMAGE_TAG` also names the image of the base stage)
4. `build.sh` runs the `tester` smoke stage; the full suite then runs on the runner host
   against the built wheel

#### macOS Platform (Native)

1. Download the JAR artifact
2. Run `scripts/build-native.sh`:
    - Removes the JARs listed in `jar_exclusions.txt`
    - Uses the Corretto 25 JDK that the workflow installs with `actions/setup-java`
    - Runs `jlink` natively → platform-specific JRE
    - Builds wheel with `python -m build`
3. Run tests on native platform

#### Windows Platform (Native)

1. Download the JAR artifact
2. Run `scripts/build-native.sh`:
    - Removes the JARs listed in `jar_exclusions.txt`
    - Uses the Corretto 25 JDK that the workflow installs with `actions/setup-java`
    - Runs `jlink` natively → platform-specific JRE
    - Builds wheel with `python -m build`
3. Run tests on native platform

## JAR Exclusion System

### Single Source of Truth: `scripts/jar_exclusions.txt`

**Location:** `bindings/python/scripts/jar_exclusions.txt`

**Format:** One glob pattern per line

```text
arcadedb-grpcw-*.jar
arcadedb-ha-raft-*.jar
```

**Used by:**

1. `bindings/python/scripts/Dockerfile.build` (Docker builds)
2. `bindings/python/scripts/build-native.sh` (native builds)

**Result:** The wheel excludes optional Java components that are not part of the default Python distribution.

### Implementation

Filtering happens in the build that packages the JARs, so every wheel gets the same filter:

- `scripts/Dockerfile.build` (Linux): the `jre-builder` stage copies
  `jar_exclusions.txt` into the image and deletes each matching JAR with `find -name "$pattern" -delete`
- `scripts/build-native.sh` (macOS, Windows): `apply_jar_exclusions` deletes each matching JAR
  from `src/arcadedb_embedded/jars`, stripping a trailing CR from each pattern so a CRLF checkout
  on Windows still matches
- **Result:** Consistent filtered JAR contents across all platforms

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
# Stage 1: java-builder (the ArcadeDB image; ARCADEDB_TAG is a required build arg)
FROM arcadedata/arcadedb:${ARCADEDB_TAG} AS java-builder

# Stage 2: jre-builder (filters JARs, compiles the bridge JAR, creates JRE)
FROM amazoncorretto:25 AS jre-builder
COPY --from=java-builder /home/arcadedb/lib /build/upstream-jars/
COPY bindings/python/local-jars/lib/ /build/local-jars/
# Uses /build/local-jars instead of the image's JARs when USE_LOCAL_JARS=1
# Reads jar_exclusions.txt
# Filters out excluded JARs before packaging
# Compiles arcadedb-python-bridge.jar from bindings/python/src/java with javac
# Runs jdeps on the JARs and adds jdk.management, jdk.zipfs, jdk.unsupported,
# and jdk.incubator.vector to the detected modules
# Runs jlink → creates /build/jre (platform-specific!)

# Stage 3: python-builder (builds wheel)
FROM python:${PYTHON_VERSION}-slim AS python-builder
COPY --from=jre-builder /build/jars /build/jars/
COPY --from=jre-builder /build/jre /build/jre/
# Builds wheel with bundled JRE; on Linux, checks the manylinux tag against the JRE

# Stage 4: export (build.sh copies the wheel out of this stage)
FROM python-builder AS export

# Stage 5: tester (installs the wheel in a clean image, runs a smoke script)
FROM python:${PYTHON_VERSION}-slim AS tester
```

`python-builder` copies the JARs from `jre-builder`, not from `java-builder`, so it gets the
filtered JAR set.

## Native Build Script

### `scripts/build-native.sh` Workflow

```bash
# 0. Check for Java 25 or later and jlink; pick the first of python3.13, python3.12,
#    python3.11, python3, and python that has a working `build` module

# 1. Use JARs already in src/arcadedb_embedded/jars (the CI artifact)
if [ -d "$JARS_DIR" ]; then
  echo "Using existing JARs"
else
  # Fallback: copy from the ArcadeDB Docker image (not used in CI)
  download_jars_from_docker
fi

# 2. Apply jar_exclusions.txt (CRLF-safe on Windows)

# 3. Compile arcadedb-python-bridge.jar from src/java with javac

# 4. Create platform-specific JRE via jlink
jlink --output jre \
  --add-modules "$MODULES" \
  --strip-debug \
  --no-man-pages \
  --no-header-files \
  --compress zip-9

# 5. Remove Windows-only non-runtime artifacts when needed

# 6. Stage JRE into src/arcadedb_embedded/jre

# 7. Write version, name, and description into pyproject.toml; run write_version.py

# 8. Delete dist/*.whl, then build the wheel
python -m build --wheel
```

**Current behavior:** Native builds use the JAR artifact from CI when it is present, and apply
`jar_exclusions.txt` themselves, so the artifact, fallback Docker downloads, and Windows checkouts
all end up with the same JAR set.

When you run a native build by hand:

- An existing, non-empty `src/arcadedb_embedded/jars` is reused whatever engine version it
  holds. Docker is needed only to fill it when it is empty; delete it to pick up another engine.
- A JAR directory passed as `build.sh`'s third argument, or built by `--engine-from-source`,
  replaces the JARs in `src/arcadedb_embedded/jars` before `build-native.sh` runs. CI
  downloads its artifact into that directory and passes the same path.
- `JAVA_HOME` must be set: the script runs with `set -u` and reads `$JAVA_HOME/jmods`.
- The Python version argument of `build.sh` is not used. The interpreter is the first match
  of the fallback list in step 0.
- The script rewrites the tracked `bindings/python/pyproject.toml` in place (version, name,
  and description). Revert that file before you commit.

## GitHub ARM64 Runners (linux/arm64)

### Native ARM64 Support

GitHub provides native ARM64 runners (`ubuntu-24.04-arm`) for public repositories:

```yaml
- platform: linux/arm64
  runs-on: ubuntu-24.04-arm  # Native ARM64 runner
```

### Benefits

- **Native performance:** No emulation overhead
- **True platform builds:** `jlink` creates actual ARM64 JRE
- **Free for public repos:** Part of GitHub Actions free tier
- **Consistent with other platforms:** Same build process as linux/amd64

### Build Process

```bash
cd bindings/python
./scripts/build.sh linux/arm64
```

`build.sh` runs `docker build --platform linux/arm64` with `-f scripts/Dockerfile.build`,
the repository root as the build context, and the required `ARCADEDB_TAG`,
`PYTHON_VERSION`, and `TARGET_PLATFORM` build arguments. Since the runner itself is
ARM64, Docker builds run natively without emulation.

## File Structure

```text
bindings/python/
├── scripts/build.sh            # Main build entrypoint
├── scripts/build-native.sh     # Native builds (macOS, Windows)
├── scripts/jar_exclusions.txt  # Single source of truth for JAR filtering
├── scripts/Dockerfile.build    # Docker builds (Linux)
├── scripts/setup_jars.py       # Copies JARs/JRE to package
├── scripts/extract_version.py  # Reads the version from pom.xml
├── scripts/write_version.py    # Writes src/arcadedb_embedded/_version.py
├── scripts/verify_wheel_platform_tag.py  # Checks the manylinux tag against the JRE's GLIBC
├── scripts/compare_engine_jars.py  # Release gate: an image's lib against a source build's
├── setup.py                    # BinaryDistribution: forces a platform-specific wheel
├── pyproject.toml              # Package metadata, dependencies
├── local-jars/lib/             # JARs staged from build.sh's third argument (gitignored)
├── dist/                       # Built wheels
└── src/
    ├── java/                   # Bridge sources, compiled into arcadedb-python-bridge.jar
    └── arcadedb_embedded/
        └── jre/                # Bundled JRE (created during build)
            ├── bin/java        # Platform-specific Java binary
            ├── lib/            # JRE libraries
            └── ...
```

## Build Workflow File

**Location:** `.github/workflows/test-python-bindings.yml`

**Key sections:**

1. **jar-source, engine-jars, and image-jars jobs**
    - Choose the engine JARs: built from this commit (default, cached by its engine
      source) or copied out of `arcadedata/arcadedb:<image-tag>`
    - Upload them as the artifact every platform builds with

2. **test job matrix**
    - Builds 4 platforms × 5 Python versions
        - Platform-specific steps (native runners, artifact download, tests)
    - Every platform embeds the artifact of step 1

3. **Test parsing**
    - JUnit XML generation and parsing
    - Cross-platform compatible

4. **bandit, dependency-floors, and test-summary jobs**
    - See [CI/CD Setup](ci-setup.md#ci-gates)

## Size Breakdown (current ballpark)

Measured on the 26.10.1.dev0 linux/amd64 wheel on 2026-09-29; other platforms and
versions vary slightly:

- Wheel: about 69 MB (compressed)
- JRE: about 63 MB (uncompressed)
- JARs: about 33 MB (uncompressed)
- Installed package: about 96 MB

## Development

### Local Build

```bash
# Build for the current platform (Docker on Linux, native on macOS and Windows)
cd bindings/python
./scripts/build.sh

# Or pick the target platform and Python version
./scripts/build.sh linux/amd64 3.12

# Or build the engine from this checkout's source first, as CI does by default
./scripts/build.sh --engine-from-source linux/amd64

# Or embed JARs you built yourself (third argument, JAR_LIB_DIR)
./scripts/build.sh linux/amd64 3.12 ../../package/target/arcadedb-<version>.dir/arcadedb-<version>/lib

# Or embed another image's JARs, for example a release while pom.xml reads the next snapshot
ARCADEDB_IMAGE_TAG=26.9.1 ./scripts/build.sh linux/amd64
```

That directory is the full assembly's `lib`, the same JAR set the image ships.

Without `--engine-from-source` or `JAR_LIB_DIR`, the build copies its JARs from the
`arcadedata/arcadedb:<tag>` image, so engine changes in your local checkout are **not**
in the wheel. To test a local or freshly synced engine change, pass `--engine-from-source`:
`build.sh` runs `./mvnw -B -q -DskipTests -pl package -am clean package` in a
`maven:3.9-eclipse-temurin-21` container (Docker, no host Java), takes the full
distribution's `lib` for the `pom.xml` version, and feeds it through the `JAR_LIB_DIR`
path. The container runs as your user, mounts `~/.m2` (`ENGINE_BUILD_M2`), and mounts the
main repository's `.git` when you build in a worktree, so the engine records its commit as
`buildNumber`. `ENGINE_BUILD_CPUSET` pins the container to a cpuset (no pin by default;
`ENGINE_BUILD_CPUSET=12-15` keeps it on a laptop's low-power cores), and
`ENGINE_BUILD_IMAGE` replaces the Maven image. The build summary prints the JAR source
and the `buildNumber` of the engine JAR inside the wheel.

`build.sh` stages a JAR directory into `local-jars/lib` for the Docker build, and into
`src/arcadedb_embedded/jars` for a native build.

`build.sh` reads the ArcadeDB tag from `pom.xml` (or `ARCADEDB_IMAGE_TAG`) and passes it on. If you call the lower-level
scripts directly, `build-native.sh` needs `PLATFORM PACKAGE_NAME PACKAGE_DESCRIPTION ARCADEDB_TAG [BUILD_VERSION]`
(the tag comes from `python3 scripts/extract_version.py --format=docker`), and `Dockerfile.build`
needs `--build-arg ARCADEDB_TAG=<tag>`.

### Test Locally

```bash
# build.sh refreshed the repo-root uv env with the new wheel

# Run tests
uv run pytest
```

## References

- **jlink documentation:** [Oracle jlink man page](https://docs.oracle.com/en/java/javase/25/docs/specs/man/jlink.html)
- **GitHub Actions runners:** [GitHub-hosted runners](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)
- **GitHub ARM64 runners:** [Supported runners and hardware resources](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#supported-runners-and-hardware-resources)
- **pytest JUnit XML:** [pytest JUnit XML output](https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files)
