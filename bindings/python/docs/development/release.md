# Release Workflow

Complete workflow for releasing ArcadeDB Python bindings to PyPI with versioned documentation.

## Prerequisites

- Push access to the repository
- PyPI environment configured in GitHub (`pypi`)
- Trusted publisher setup on PyPI (automatic authentication)

## Release Checklist

### 1. Prepare Release

On `python-embedded` branch:

- [ ] Version is already set in `pom.xml` (e.g., `X.Y.Z-SNAPSHOT`)
- [ ] Run full test suite
- [ ] Update `CHANGELOG.md` or prepare release notes
- [ ] Update documentation if needed
- [ ] Commit all changes

```bash
cd bindings/python

# Build distribution
./build.sh

# Test distribution
pip install dist/arcadedb_embedded-*.whl
pytest
```

**Note**: Version is automatically extracted from `pom.xml` by `extract_version.py` during build. The `-SNAPSHOT` suffix is converted to `.dev0` for PEP 440 compliance.

### 2. Create GitHub Release

Instead of pushing tags manually, create a GitHub Release which automatically creates the tag and triggers deployments.

**Option A: Using GitHub Web UI** (Recommended)

1. Go to [Releases](https://github.com/humemai/arcadedb-embedded-python/releases)
2. Click **Draft a new release**
3. Click **Choose a tag** dropdown

2. Click **Choose a tag** → Type `vX.Y.Z-python` → **Create new tag**
3. Target: `python-embedded`
4. Release title: `Python release vX.Y.Z`
5. Description/Release notes:

   ```markdown
   ## What's New

   - Feature: Description
   - Fix: Description
   - Docs: Description

   ## Installation

   pip install arcadedb-embedded

   ## Documentation

   https://humemai.github.io/arcadedb-embedded-python/

   ## Test Results

   - All tests passed: 222 passed
   ```

6. Click **Publish release** (or **Save as draft** to test first)

**Option B: Using GitHub CLI**

```bash
# Commit final changes
git add .
git commit -m "Release Python bindings vX.Y.Z"
git push origin python-embedded

# Create annotated tag
git tag -a vX.Y.Z-python -m "Python release vX.Y.Z"
git push origin vX.Y.Z-python

# Create release from tag
gh release create vX.Y.Z-python \
  --target python-embedded \
  --title "Python release vX.Y.Z" \
  --notes "## What's New

- Feature: Description
- Fix: Description
```

## Installation

```bash
pip install arcadedb-embedded
```

## Documentation

https://humemai.github.io/arcadedb-embedded-python/

## Test Results

- 222 passed

**What happens automatically:**

- ✅ Git tag `vX.Y.Z-python` is created (annotated tag)
- ✅ PyPI workflow builds and uploads the distribution
- ✅ Docs workflow deploys versioned documentation

### 3. Monitor GitHub Actions

Two workflows trigger automatically when you publish the release:

**PyPI Deployment** (`.github/workflows/release-python-packages.yml`):

1. Builds the distribution (using Docker)
2. Publishes to PyPI:
   - `arcadedb-embedded`

**Documentation Deployment** (`.github/workflows/deploy-python-docs.yml`):

1. Extracts version from release tag (e.g., `vX.Y.Z-python` → `X.Y.Z`)
2. Builds documentation with MkDocs + mike
3. Deploys to GitHub Pages with version number
4. Sets as `latest` version
5. Updates version selector dropdown

**Check progress:**

- Go to **GitHub** → **Actions** tab
- Monitor both workflows
- Check for any failures
- Typical duration: 10-15 minutes total

### 4. Verify Deployment

**PyPI Packages:**

```bash
# Check packages are live (replace VERSION with your version)
pip index versions arcadedb-embedded

# Test installation
pip install arcadedb-embedded
python -c "import arcadedb_embedded as arcadedb; print(arcadedb.__version__)"
```

**Documentation:**

Visit:
- **Latest**: <https://humemai.github.io/arcadedb-embedded-python/>
- **Versioned**: <https://humemai.github.io/arcadedb-embedded-python/VERSION/> (replace VERSION)

Check:
- [ ] Version selector shows your version as `(latest)`
- [ ] All pages load correctly
- [ ] Search works
- [ ] Code examples render properly
- [ ] Links work (internal and external)

### 5. Post-Release

**Update Development Version:**

```bash
# Bump version in pom.xml for next development cycle
# e.g., X.Y.Z-SNAPSHOT → X.Y.Z+1-SNAPSHOT (or whatever next version is)

# Edit pom.xml, change <version> in parent POM
vim pom.xml

git add pom.xml
git commit -m "Bump version to next development version"
git push origin python-embedded
```

**Announce Release:**

- Update project README if needed
- Notify users/community
- Update any integration guides
- Optionally add release to CHANGELOG.md

## Python Versioning Strategy

### Overview

The Python bindings use an **automated versioning system** that extracts versions from ArcadeDB's `pom.xml` and converts them to PEP 440 compliant Python versions. This ensures version consistency across the entire project while supporting both development and release workflows.

### Key Principles

1. **Single Source of Truth**: Version is only defined in `pom.xml` - everything else extracts it automatically
2. **PEP 440 Compliance**: All Python versions follow Python packaging standards
3. **Development/Release Distinction**: Different handling for `-SNAPSHOT` vs release versions
4. **Automated Conversion**: No manual version editing required in Python files

### Version Conversion Rules

| Maven Version (pom.xml) | Python Version | Use Case |
|-------------------------|----------------|----------|
| `25.10.1-SNAPSHOT` | `25.10.1.dev0` | Development builds |
| `25.9.1` | `25.9.1` | Release builds |
| `25.9.1` (with --python-patch 1) | `25.9.1.post1` | Python-specific patches |
| `25.9.1` (with --python-patch 2) | `25.9.1.post2` | Additional Python patches |

### Development Mode vs Release Mode

**Development Mode** (SNAPSHOT versions):

- Triggered by: `-SNAPSHOT` suffix in `pom.xml`
- Conversion: `X.Y.Z-SNAPSHOT` → `X.Y.Z.dev0`
- Purpose: Pre-release development builds
- Example: `25.10.1-SNAPSHOT` → `25.10.1.dev0`

**Release Mode** (clean versions):

- Triggered by: No `-SNAPSHOT` suffix in `pom.xml`
- Conversion: `X.Y.Z` → `X.Y.Z` (or `X.Y.Z.postN` for Python patches)
- Purpose: Official releases to PyPI
- Example: `25.9.1` → `25.9.1` or `25.9.1.post1`

### Python-Specific Patches

For Python-only bug fixes that don't require a new ArcadeDB version:

```bash
# Build with Python patch number
./build.sh base --python-patch 1

# Results in version: 25.9.1.post1 (if base ArcadeDB version is 25.9.1)
```

### Implementation Details

The conversion is handled by `bindings/python/extract_version.py` (see file for detailed implementation). Key features:

- **Automatic Detection**: Distinguishes development vs release mode automatically
- **Command Line Interface**: Supports `--python-patch` parameter for .postN versions
- **Error Handling**: Validates input and provides clear error messages
- **Flexible Usage**: Can be called from build scripts, Docker, or manually

## Version Numbering

Python bindings follow the ArcadeDB main project version from `pom.xml`:

- **Format**: `MAJOR.MINOR.PATCH[.devN|.postN]`
- **POM version**: `X.Y.Z-SNAPSHOT` (development) or `X.Y.Z` (release)
- **Git tag**: `vX.Y.Z-python` (follows git best practices with `v` prefix)
- **Release tag**: `vX.Y.Z-python` (GitHub Release)
- **PyPI version**: `X.Y.Z[.devN|.postN]` (extracted automatically, no `v` prefix)
- **Docs version**: `X.Y.Z` (extracted from tag, no `v` prefix)

**How version is determined:**

1. Set in `pom.xml` root: `<version>X.Y.Z-SNAPSHOT</version>` or `<version>X.Y.Z</version>`
2. `extract_version.py` converts based on mode:
   - Development: `X.Y.Z-SNAPSHOT` → `X.Y.Z.dev0`
   - Release: `X.Y.Z` → `X.Y.Z` (or `X.Y.Z.postN` with --python-patch)
3. Create annotated tag: `git tag -a vX.Y.Z-python -m "Python release vX.Y.Z"`
4. GitHub Release tag: `vX.Y.Z-python` (with `v` prefix)
5. Workflows extract: `vX.Y.Z-python` → `X.Y.Z` (strip prefix/suffix)
6. Used everywhere: PyPI (`X.Y.Z[.devN|.postN]`), docs (`/X.Y.Z/`)

**When to bump:**

- **MAJOR**: Breaking API changes
- **MINOR**: New features, non-breaking
- **PATCH**: Bug fixes only
- **Python Patch**: Python-only fixes using `.postN` suffix

**Note**: Version is only in ONE place (`pom.xml`) - everything else extracts it automatically!

## Hotfix Release

For urgent bug fixes on a released version:

```bash
# 1. Create hotfix branch from tag
git checkout -b hotfix/X.Y.Z+1 vX.Y.Z-python

# 2. Make fixes, update version in pom.xml
vim pom.xml  # Change to X.Y.Z+1-SNAPSHOT

# 3. Test thoroughly
cd bindings/python
./build.sh full && pytest

# 4. Commit and create hotfix release
git commit -am "Hotfix: description"
git push origin hotfix/X.Y.Z+1

# 5. Create annotated tag
git tag -a vX.Y.Z+1-python -m "Python hotfix release vX.Y.Z+1"
git push origin vX.Y.Z+1-python

# 6. Create GitHub Release
gh release create vX.Y.Z+1-python \
  --target hotfix/X.Y.Z+1 \
  --title "Python hotfix release vX.Y.Z+1" \
  --notes "Hotfix for critical bug in X.Y.Z"

# 7. Merge back to python-embedded
git checkout python-embedded
git merge hotfix/X.Y.Z+1
git push origin python-embedded
```

## Rolling Back a Release

If you need to roll back a broken release:

**PyPI** (cannot delete, but can yank):

```bash
# Install twine
pip install twine

# Yank the release (makes it unavailable for new installs)
twine yank arcadedb-embedded 25.9.1
```

**Documentation** (can delete version):

```bash
cd bindings/python

# Install mike
pip install mike

# Delete version from docs
mike delete 25.9.1 --push

# Set previous version as latest
mike set-default 25.9.0 --push
```

**GitHub Release:**

1. Go to **Releases**
2. Edit the release
3. Check "Set as a pre-release"
4. Or delete the release entirely

## Troubleshooting

### PyPI upload fails

**Size limit exceeded:**

- Distribution might hit PyPI limits (~215 MB)
- Request size increase: <https://pypi.org/help/#file-size-limit>
- Or distribute via GitHub releases only

**Authentication error:**

- Check GitHub environment secrets
- Verify trusted publisher configuration
- Check PyPI API tokens

### Documentation deployment fails

**mike command error:**

- Ensure `git config` is set in workflow
- Check branch permissions
- Verify `gh-pages` branch exists

**Version not appearing:**

- Check GitHub Actions logs
- Verify tag format: `python-*`
- Manually run: `mike list` to see deployed versions

**Broken links:**

- Run `mkdocs build --strict` locally first
- Check all internal links use correct paths
- Verify external URLs are accessible

### Build failures

**Docker build error:**

- Check Docker daemon is running
- Verify Dockerfile.build syntax
- Check Maven dependencies are available

**Test failures:**

- Run specific test: `pytest tests/test_core.py::test_name -v`
- Check logs in `bindings/python/log/`
- Verify Java JDK 21+ is available

## See Also

- [Documentation Development](documentation.md) - Working with MkDocs
- [Testing Guide](testing.md) - Running test suite
- [Contributing Guide](contributing.md) - Development workflow
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [PyPI Publishing Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
