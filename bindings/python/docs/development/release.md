# Release Workflow

Complete workflow for releasing ArcadeDB Python bindings to PyPI with versioned documentation.

## Prerequisites

- Push access to the repository
- PyPI environment configured in GitHub (`pypi`)
- Trusted publisher setup on PyPI (automatic authentication)

## Release Checklist

### 1. Prepare Release

On `main` (or a `release/X.Y.Z` branch if you want main to keep moving):

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
uv pip install dist/arcadedb_embedded-*.whl
pytest
```

### 2. Tag and Release (CLI)

Tags are the source of truth. Pushing `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN` triggers PyPI + docs.
If `main` keeps moving, create all `X.Y.Z.devN`, `X.Y.Z`, and `X.Y.Z.postN` tags from `release/X.Y.Z`.

```bash
git add .
git commit -m "Release Python bindings X.Y.Z"
git push origin main

git tag -a X.Y.Z -m "Python release X.Y.Z"
git push origin X.Y.Z

gh release create X.Y.Z \
  --target main \
  --title "Python release X.Y.Z" \
  --notes "Release X.Y.Z"
```

### 3. Monitor GitHub Actions

- Check the Actions tab for `release-python-packages` and `deploy-python-docs`.
- Docs deploy uses the tag version; dev tags become `latest` unless you run the docs workflow with `set_latest=false`.

### 4. Post-Release

```bash
# Bump version in pom.xml for next development cycle
vim pom.xml

git add pom.xml
git commit -m "Bump version to next development version"
git push origin main
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
- **Git tag**: `X.Y.Z` (or `X.Y.Z.devN` / `X.Y.Z.postN`)
- **Release tag**: `X.Y.Z` (GitHub Release)
- **PyPI version**: `X.Y.Z[.devN|.postN]` (extracted automatically, no `v` prefix)
- **Docs version**: `X.Y.Z` (extracted from tag, no `v` prefix)

**How version is determined:**

1. Set in `pom.xml` root: `<version>X.Y.Z-SNAPSHOT</version>` or `<version>X.Y.Z</version>`
2. `extract_version.py` converts based on mode:
   - Development: `X.Y.Z-SNAPSHOT` → `X.Y.Z.dev0`
   - Release: `X.Y.Z` → `X.Y.Z` (or `X.Y.Z.postN` with --python-patch)
3. Create annotated tag: `git tag -a X.Y.Z -m "Python release X.Y.Z"`
4. GitHub Release tag: `X.Y.Z`
5. Workflows use the tag version directly: `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN`
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
git checkout -b hotfix/X.Y.Z+1 X.Y.Z

# 2. Make fixes, update version in pom.xml
vim pom.xml  # Change to X.Y.Z+1-SNAPSHOT

# 3. Test thoroughly
cd bindings/python
./build.sh full && pytest

# 4. Commit and create hotfix release
git commit -am "Hotfix: description"
git push origin hotfix/X.Y.Z+1

# 5. Create annotated tag
git tag -a X.Y.Z+1 -m "Python hotfix release X.Y.Z+1"
git push origin X.Y.Z+1

# 6. Create GitHub Release
gh release create X.Y.Z+1 \
  --target hotfix/X.Y.Z+1 \
   --title "Python hotfix release X.Y.Z+1" \
  --notes "Hotfix for critical bug in X.Y.Z"

# 7. Merge back to main
git checkout main
git merge hotfix/X.Y.Z+1
git push origin main
```

## Rolling Back a Release

If you need to roll back a broken release:

**PyPI** (cannot delete, but can yank):

```bash
# Install twine
uv pip install twine

# Yank the release (makes it unavailable for new installs)
twine yank arcadedb-embedded 25.9.1
```

**Documentation** (can delete version):

```bash
cd bindings/python

# Install mike
uv pip install mike

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
- Verify tag format: `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN`
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
- Verify Java JDK 25+ is available

## See Also

- [Documentation Development](documentation.md) - Working with MkDocs
- [Testing Guide](testing.md) - Running test suite
- [Contributing Guide](contributing.md) - Development workflow
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [PyPI Publishing Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
