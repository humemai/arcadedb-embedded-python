# CI/CD Multi-Platform Matrix Setup

## Overview

The CI/CD workflows now support building and releasing across **4 platforms** for a total of **20 wheel packages** per release (4 platforms × 5 Python versions), all under the single `arcadedb-embedded` package.

## Build Matrix

### Single-Package Strategy

- **arcadedb-embedded**: All platforms (~63–115MB compressed) - JRE bundled, no external Java needed

### Platforms (All Native Runners)

- **linux/amd64**: Linux on x86_64 (ubuntu-24.04, Docker build)
- **linux/arm64**: Linux on ARM64 (ubuntu-24.04-arm, Docker build)
- **darwin/arm64**: macOS on Apple Silicon M1/M2/M3/M4 (macos-15, native build)
- **windows/amd64**: Windows on x86_64 (windows-2025, native build)

### Total Artifacts

**20 wheels per release**: 1 package × 4 platforms × 5 Python versions = 20 wheels

## Workflow Changes

### `test-python-bindings.yml`

- **Matrix**: `platform: [linux/amd64, linux/arm64, darwin/arm64, windows/amd64]` and `python-version: [3.10, 3.11, 3.12, 3.13, 3.14]`
- **Runners**: All native (no QEMU emulation)
    - ubuntu-24.04 (Linux x64)
    - ubuntu-24.04-arm (Linux ARM64)
    - macos-15 (macOS Apple Silicon)
    - windows-2025 (Windows x86_64)
- **Jobs**: 20 total (4 platforms × 5 Python versions)
- **Artifacts**: `wheel-{platform}-py{version}` (20 artifacts)

### `release-python-packages.yml`

- **Artifacts**: `wheel-{platform}-py{version}` (20 artifacts)
- **Publish Job**:
    - `publish-pypi`: Collects all 20 wheels and publishes to `arcadedb-embedded`

## GitHub Repository Setup Required

### 1. Create PyPI Trusted Publisher Environment

You need to create one environment in GitHub repository settings:

#### Environment: `pypi`

- **PyPI Package**: `arcadedb-embedded`
- **Trusted Publisher**:
    - Repository: `humemai/arcadedb-embedded-python`
    - Workflow: `release-python-packages.yml`
    - Environment: `pypi`

### 2. Steps to Create Environment

1. **Go to Repository Settings** → **Environments** → **New environment**
2. **Create `pypi`** environment
3. **Configure PyPI Trusted Publisher**:
    - Go to https://pypi.org/manage/account/publishing/
    - Add publisher for `arcadedb-embedded` (environment: `pypi`)

### 3. First Release Steps

1. **Register package on PyPI** (if not already registered):
    ```bash
    # Build a wheel locally first
    cd bindings/python
    ./build.sh

    # Upload manually to register the package
    uv pip install twine
    twine upload dist/arcadedb_embedded-*.whl
    ```

2. **Set up trusted publisher** on PyPI (see step 2 above)

3. **Push a test tag**:
    ```bash
    git tag 25.10.1.dev0
    git push origin 25.10.1.dev0
    ```

4. **Monitor the workflow**:
    - Go to Actions tab
    - Watch `Build and Release Python Packages to PyPI`
    - Check that 20 wheels are built and publish job succeeds

## Validation

### Expected Artifacts

After a successful release, you should see:

- **20 wheel files** on PyPI for `arcadedb-embedded` (4 platforms × 5 Python versions)

### Test Results (CI run #96)

All 4 platforms passing 258 tests and example scripts:

| Platform | Wheel Size | JRE Size | Tests |
|----------|-----------|----------|-------|
| linux/amd64 | 115.2M | 249.0M | 258 passed ✅ |
| linux/arm64 | 114.1M | 249.6M | 258 passed ✅ |
| darwin/arm64 | 63.1M | 55.1M | 258 passed ✅ |
| windows/amd64 | ~115M | ~249M | 258 passed ✅ |

**All platforms include:**

- 31.7M JARs (83 files, identical across platforms, gRPC excluded)
- Platform-specific JRE (55.1–249.6M uncompressed, depending on platform)
- Native runners (no QEMU emulation anywhere)

## Cross-Platform Building

### Native Runners (No Emulation)

All platforms use native GitHub runners:

- **linux/amd64**: ubuntu-24.04 (Docker build)
- **linux/arm64**: ubuntu-24.04-arm (Docker build, native ARM64)
- **darwin/arm64**: macos-15 (native build)
- **windows/amd64**: windows-2025 (native build)

### Build Time Expectations

- **All platforms**: ~5-10 minutes per build (all native, no QEMU overhead)
- **Total release time**: ~15-25 minutes (parallel builds)

### Performance Improvements

Previously used QEMU for linux/arm64:

- QEMU: ~15-20 minutes per build
- Native ARM64: ~5-7 minutes per build
- **3-4x performance improvement** by switching to native runners

## Testing Locally

### Test specific platform build locally:

```bash
cd bindings/python

# Build for specific platform (requires Docker for Linux builds)
./build.sh --platform linux/amd64
./build.sh --platform darwin/arm64

# Check the wheels
ls -lh dist/
```

### Test all platforms (requires Docker):

```bash
cd bindings/python

for platform in linux/amd64 linux/arm64 darwin/arm64 windows/amd64; do
  echo "Building $platform..."
  ./build.sh --platform "$platform"
done

# Should have 4 wheels
ls -1 dist/*.whl | wc -l  # Should output: 4
```

## Troubleshooting

### "Value 'pypi' is not valid"

- This error appears in the workflow file but is expected
- The environment doesn't exist yet in GitHub settings
- Create it as described in section 1 above

### Platform-specific JVM detection issues

All platforms now use platform-specific JVM library paths:

- macOS: `lib/server/libjvm.dylib`
- Linux: `lib/server/libjvm.so`

### Wheel count mismatch

- The publish job validates that exactly 20 wheels exist
- If validation fails, check the build matrix jobs for failures
- Ensure all 4 platform builds succeeded

### Runner availability

All platforms use pinned runner versions for reproducibility:

- ubuntu-24.04 (guaranteed available)
- ubuntu-24.04-arm (GitHub-hosted ARM64)
- macos-15 (Apple Silicon, pinned version)
- windows-2025 (Windows x86_64, pinned version)

## Next Steps

1. **Create GitHub environment** (`pypi`)
2. **Set up PyPI trusted publisher** for `arcadedb-embedded`
3. **Test with a dev tag**: `git tag 25.10.1.dev0 && git push origin 25.10.1.dev0`
4. **Verify 20 wheels are published** to PyPI (4 platforms × 5 Python versions)
5. **Test installation** on the supported platforms
6. **Verify no Java required** on end-user systems (JRE bundled)
