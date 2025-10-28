# CI/CD Multi-Platform Matrix Setup

## Overview

The CI/CD workflows now support building and releasing **2 variants** across **5 platforms** for a total of **10 wheel packages** per release.

## Build Matrix

### Variants
- **base**: Standard package (~123MB) - requires Java 21+ on host
- **jre**: Bundled JRE package (~162MB) - no external Java needed

### Platforms
- **linux-x64**: Linux on x86_64 (Intel/AMD 64-bit)
- **linux-arm64**: Linux on ARM64 (Apple Silicon, AWS Graviton, etc.)
- **darwin-x64**: macOS on Intel
- **darwin-arm64**: macOS on Apple Silicon (M1, M2, M3, M4, etc.)
- **windows-x64**: Windows on x86_64

### Total Artifacts
**10 wheels per release**: 2 variants × 5 platforms = 10 wheels

## Workflow Changes

### `test-python-bindings.yml`
- **Matrix**: `variant: [base, jre]` × `platform: [linux-x64, linux-arm64]`
- **QEMU**: Set up for ARM64 emulation when `platform == 'linux-arm64'`
- **Jobs**: 4 total (2 variants × 2 platforms for testing)
- **Artifacts**: `wheel-{variant}-{platform}-test` (4 artifacts)

### `release-python-packages.yml`
- **Matrix**: `variant: [base, jre]` × `platform: [linux-x64, linux-arm64, darwin-x64, darwin-arm64, windows-x64]`
- **QEMU**: Set up for ARM64 emulation when platform includes `arm64`
- **Jobs**: 10 build jobs + 2 publish jobs (12 total)
- **Artifacts**: `wheel-{variant}-{platform}` (10 artifacts)
- **Publish Jobs**:
  - `publish-base`: Collects all 5 base wheels and publishes to `arcadedb-embedded`
  - `publish-jre`: Collects all 5 jre wheels and publishes to `arcadedb-embedded-jre`

## GitHub Repository Setup Required

### 1. Create PyPI Trusted Publisher Environments

You need to create two environments in GitHub repository settings:

#### Environment: `pypi-base`
- **PyPI Package**: `arcadedb-embedded`
- **Trusted Publisher**:
  - Repository: `humemai/arcadedb-embedded-python`
  - Workflow: `release-python-packages.yml`
  - Environment: `pypi-base`

#### Environment: `pypi-jre`
- **PyPI Package**: `arcadedb-embedded-jre`
- **Trusted Publisher**:
  - Repository: `humemai/arcadedb-embedded-python`
  - Workflow: `release-python-packages.yml`
  - Environment: `pypi-jre`

### 2. Steps to Create Environments

1. **Go to Repository Settings** → **Environments** → **New environment**
2. **Create `pypi-base`** environment
3. **Create `pypi-jre`** environment
4. **Configure PyPI Trusted Publishers**:
   - Go to https://pypi.org/manage/account/publishing/
   - Add publisher for `arcadedb-embedded` (environment: `pypi-base`)
   - Add publisher for `arcadedb-embedded-jre` (environment: `pypi-jre`)

### 3. First Release Steps

1. **Register packages on PyPI** (if not already registered):
   ```bash
   # Build a wheel locally first
   cd bindings/python
   ./build.sh base
   ./build.sh jre

   # Upload manually to register the packages
   pip install twine
   twine upload dist/arcadedb_embedded-*.whl
   twine upload dist/arcadedb_embedded_jre-*.whl
   ```

2. **Set up trusted publishers** on PyPI (see step 2 above)

3. **Push a test tag**:
   ```bash
   git tag 25.10.1.dev0
   git push origin 25.10.1.dev0
   ```

4. **Monitor the workflow**:
   - Go to Actions tab
   - Watch `Build and Release Python Packages to PyPI`
   - Check that 10 wheels are built and 2 publish jobs succeed

## Validation

### Expected Artifacts
After a successful release, you should see:
- **10 wheel files** on PyPI split across 2 packages:
  - `arcadedb-embedded`: 5 wheels (one per platform)
  - `arcadedb-embedded-jre`: 5 wheels (one per platform)

### Wheel Naming Convention
- **Base variant**: `arcadedb_embedded-{version}-py3-none-any.whl`
- **JRE variant**: `arcadedb_embedded_jre-{version}-py3-none-any.whl`

Note: Platform-specific wheels use the same filename because Python wheels for pure-Python packages don't encode platform in the filename. The platform targeting is handled during the build process via the JRE bundling.

## Cross-Platform Building

### QEMU Emulation
- **linux-arm64**: Uses QEMU to emulate ARM64 on GitHub's x86_64 runners
- **darwin-arm64**: Uses QEMU + Docker Buildx multi-platform support
- **windows-x64**: Cross-compiled from Linux using Docker

### Build Time Expectations
- **x64 platforms**: ~5-10 minutes per variant
- **ARM64 platforms**: ~10-20 minutes per variant (QEMU overhead)
- **Total release time**: ~30-45 minutes (parallel builds)

## Testing Locally

### Test ARM64 build locally (requires Docker Desktop with QEMU):
```bash
cd bindings/python

# Build linux-arm64 variant
./build.sh base --platform linux-arm64
./build.sh jre --platform linux-arm64

# Check the wheels
ls -lh dist/
```

### Test all platforms:
```bash
cd bindings/python

for platform in linux-x64 linux-arm64 darwin-x64 darwin-arm64 windows-x64; do
  echo "Building base variant for $platform..."
  ./build.sh base --platform "$platform"

  echo "Building jre variant for $platform..."
  ./build.sh jre --platform "$platform"
done

# Should have 10 wheels
ls -1 dist/*.whl | wc -l  # Should output: 10
```

## Troubleshooting

### "Value 'pypi-base' is not valid"
- This error appears in the workflow file but is expected
- The environments don't exist yet in GitHub settings
- Create them as described in section 1 above

### QEMU builds are slow
- ARM64 emulation is ~10x slower than native builds
- This is expected and normal
- Consider using self-hosted ARM64 runners for production

### Wheel count mismatch
- The publish jobs validate that exactly 5 wheels exist per variant
- If validation fails, check the build matrix jobs for failures
- Ensure all 5 platform builds succeeded

## Next Steps

1. **Create GitHub environments** (`pypi-base`, `pypi-jre`)
2. **Set up PyPI trusted publishers** for both packages
3. **Test with a dev tag**: `git tag 25.10.1.dev0 && git push origin 25.10.1.dev0`
4. **Verify 10 wheels are published** to PyPI
5. **Update documentation** (task #12)
6. **Full validation testing** (task #13)
