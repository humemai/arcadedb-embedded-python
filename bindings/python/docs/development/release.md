# Release Workflow

Complete workflow for releasing ArcadeDB Python bindings to PyPI with versioned documentation.

## Prerequisites

- Push access to the repository
- PyPI environment configured in GitHub (`pypi`)
- Trusted publisher setup on PyPI (automatic authentication; see [CI/CD Setup](ci-setup.md#pypi-trusted-publisher-setup))

## Where the Version Comes From

This fork does not set its own version. The wheel version is derived from the root
`pom.xml`, and `pom.xml` belongs to upstream ArcadeDB: it arrives with each
`./sync-upstream.sh` run. Never edit it here; a local change would conflict with the
next sync.

- Between releases, upstream's `main` reads `X.Y.Z-SNAPSHOT`, and the wheel builds as `X.Y.Z.dev0`.
- Upstream cuts a release with a commit titled "Set release version to X.Y.Z", which
  sets `pom.xml` to `X.Y.Z`. A stable bindings release is built from a sync that stops
  at that commit.

## Which Engine a Release Ships

A release ships **upstream's official JARs**, the ones in `/home/arcadedb/lib` of
`arcadedata/arcadedb:<version>`: the artifacts Java users of that release get. Every other
CI run tests the engine built from this repository's source (see
[CI/CD Setup](ci-setup.md#where-the-engine-jars-come-from)); the release connects the two:

1. Both test workflows run with `jar-source: image` and the release's image, so the 20
   wheels that publish are built and tested on exactly the official JARs.
2. A gate, `verify-engine-jars.yml`, builds the release commit from source and compares it
   with the image: the same JAR names, every third-party JAR byte-identical, and every
   ArcadeDB JAR's entries byte-identical except the `buildNumber`, `timestamp`, and `branch`
   lines of `com/arcadedb/arcadedb.properties`. Publishing needs the gate to pass, so what
   CI tested on every push is the code that ships. The source build never enters a wheel
   or a test.

Shipping our own build of the same code was rejected: same classes, different bytes and
build stamps, and not upstream's artifact.

The gate holds for a real release. A CI build of the official 26.9.1 release commit
(`b6a92623554b`) matched `arcadedata/arcadedb:26.9.1` in all 86 JAR names, all 69
third-party JARs byte for byte, and all 75,699 ArcadeDB classes byte for byte; only
`arcadedb.properties` differed, in exactly those three lines (the official JARs record
`9cea8e848f`, the commit before the tag, as `buildNumber`).

!!! warning "Upstream uses the same version numbers"
    ArcadeDB's release tags carry the same numbers as ours (`26.9.1` is both their
    engine release and our wheel release). Always fetch `upstream` with `--no-tags`
    (`sync-upstream.sh` does). If their tag is ever fetched, `git tag -a X.Y.Z` fails
    with "already exists", but `git push origin X.Y.Z` still succeeds and publishes
    upstream's commit. Check what a tag points to before pushing it (step 4 below).

## Release Checklist (stable `X.Y.Z`)

### 1. Sync to Upstream's Release Commit

```bash
# Find upstream's release commit without fetching its tags
git fetch upstream --no-tags
git log upstream/main --oneline --grep "Set release version to X.Y.Z"

# Merge upstream up to that commit
./sync-upstream.sh --until <commit>
```

If the merge stops on conflicts, resolve them as described in
[Syncing Upstream](sync-upstream.md#when-the-merge-stops-on-conflicts), including the
fork-owned restore and the `.github` prune the script skips in that case. Afterwards
`pom.xml` reads `X.Y.Z`.

### 2. Build and Test

```bash
cd bindings/python

# Build with the official JARs this release will ship (pom.xml now reads X.Y.Z)
./scripts/build.sh

# Test distribution (build.sh refreshed the repo-root uv env with the new wheel)
uv run pytest
```

Upstream publishes `arcadedata/arcadedb:X.Y.Z` with the release, so this build already
embeds the JARs the release will ship. To build what CI tests on a push, the engine built
from this checkout, pass `--engine-from-source`.

- [ ] Full test suite passes
- [ ] Release notes prepared (for example in `notes.md`)
- [ ] Documentation updated if needed

### 3. Push and Let CI Pass

```bash
git push origin main
```

Wait for "Test Python Bindings" and "Test Python Examples" to finish, and check that
the examples actually ran rather than skipped. These push runs test the engine built from
the synced source. To see the official JARs pass before tagging, dispatch both workflows
with `jar-source=image` and `image-tag=X.Y.Z`, and run the gate on its own:
`gh workflow run verify-engine-jars.yml -f ref=main -f image-tag=X.Y.Z`.

### 4. Tag, Check, and Release

Tags are the source of truth. Pushing `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN` triggers
PyPI + docs.

```bash
git tag -a X.Y.Z -F notes.md

# The tag must point at the commit you just tested
test "$(git rev-parse 'X.Y.Z^{}')" = "$(git rev-parse HEAD)" && echo "tag OK"

git push origin X.Y.Z

# The remote tag must peel to the same commit
git ls-remote origin 'refs/tags/X.Y.Z^{}'

gh release create X.Y.Z --verify-tag \
  --title "Python release X.Y.Z" \
  --notes-file notes.md
```

`--verify-tag` stops `gh` from creating a tag of its own if the pushed one is missing.

### 5. Monitor GitHub Actions

- Check the Actions tab for "Build and Release Python Packages to PyPI" (`release-python-packages.yml`) and "Deploy MkDocs to GitHub Pages" (`deploy-python-docs.yml`).
- The release workflow first checks that the tag's base version equals the `pom.xml`
  base version, then runs the engine JAR gate and both test workflows (on the official
  JARs of `arcadedata/arcadedb:X.Y.Z`), then publishes the wheels. The gate's job summary
  lists the JAR names, the third-party JARs, and the classes it compared.
- The publish job has `continue-on-error: true`, so the run stays green even when the
  PyPI upload fails. Check PyPI for every wheel the release built.
- Every tag push deploys its docs as `latest`, dev tags included. To publish docs
  without moving `latest`, run the docs workflow by hand (`workflow_dispatch`) with
  `set_latest=false`.
- The docs workflow does not wait for the release, so a tag whose release fails still
  deploys its docs as `latest`. If the release failed, move `latest` back (see
  [Rolling Back a Release](#rolling-back-a-release)).

### 6. After the Release

Return `main` to upstream's development line with a normal sync. It brings the next
`-SNAPSHOT` version; there is no version bump to make here.

```bash
./sync-upstream.sh
```

**Announce Release:**

- Update project README if needed
- Notify users/community
- Update any integration guides

## Development Releases (`X.Y.Z.devN`)

A dev tag is released from `main` while `pom.xml` reads `X.Y.Z-SNAPSHOT`: the release
workflow compares only the base version (`X.Y.Z`). Tag and check it exactly as in
step 4. A dev tag publishes to the real PyPI index and becomes the `latest` docs.

There is no official image of an unreleased version, so a dev tag builds and tests on
upstream's moving `arcadedata/arcadedb:X.Y.Z-SNAPSHOT` image, and the engine JAR gate
compares that image with a build of the tagged commit. It passes only when the snapshot
was built from the same engine source as the last sync, which is rare once upstream has
moved on. Check before tagging with
`gh workflow run verify-engine-jars.yml -f ref=main -f image-tag=X.Y.Z-SNAPSHOT`.

## Python Versioning Strategy

### Overview

The Python bindings use an **automated versioning system** that extracts versions from ArcadeDB's `pom.xml` and converts them to PEP 440 compliant Python versions. In CI the release workflow passes the tag itself as the build version, so a wheel built from tag `X.Y.Z.devN` or `X.Y.Z.postN` carries that exact version.

### Key Principles

1. **Single Source of Truth**: The base version is only defined in `pom.xml` (upstream's), and everything else extracts it automatically
2. **PEP 440 Compliance**: All Python versions follow Python packaging standards
3. **Development/Release Distinction**: Different handling for `-SNAPSHOT` vs release versions
4. **Automated Conversion**: No manual version editing required in Python files

### Version Conversion Rules

| Maven Version (pom.xml) | Python Version | Use Case |
|-------------------------|----------------|----------|
| `26.10.1-SNAPSHOT` | `26.10.1.dev0` | Development builds |
| `26.9.1` | `26.9.1` | Release builds |
| `26.9.1` (tag `26.9.1.post1`) | `26.9.1.post1` | Python-only fix to a release |

### Development Mode vs Release Mode

**Development Mode** (SNAPSHOT versions):

- Triggered by: `-SNAPSHOT` suffix in `pom.xml`
- Conversion: `X.Y.Z-SNAPSHOT` → `X.Y.Z.devN`, where N comes from the untracked
  `scripts/.dev_version_tracker.json` and is 0 when that file has no entry for the version
  (no build step adds one)
- Purpose: Pre-release development builds
- Example: `26.10.1-SNAPSHOT` → `26.10.1.dev0`

**Release Mode** (clean versions):

- Triggered by: No `-SNAPSHOT` suffix in `pom.xml`
- Conversion: `X.Y.Z` → `X.Y.Z` (a `.postN` version comes from the tag; see below)
- Purpose: Official releases to PyPI
- Example: `26.9.1` → `26.9.1`

### Python-Specific Patches

A Python-only fix to a released version ships as `X.Y.Z.postN` (see
[Hotfix Release](#hotfix-release-xyzpostn)). The suffix comes from the tag, not from
`pom.xml`: the release workflow passes the tag to both test workflows as `build-version`,
they export it as `BUILD_VERSION`, and `build.sh` hands it to the Docker build or to
`build-native.sh`, which write it into `pyproject.toml` in place of the version derived
from `pom.xml`. To build such a wheel locally:

```bash
BUILD_VERSION=26.9.1.post1 ./scripts/build.sh
```

Without `BUILD_VERSION`, `extract_version.py` derives the version from `pom.xml` as
described above.

### Implementation Details

The conversion is handled by `bindings/python/scripts/extract_version.py` (see file for detailed implementation). Key features:

- **Automatic Detection**: Distinguishes development vs release mode automatically
- **Command Line Interface**: `--format=docker` prints the raw `pom.xml` version (the image
  tag). Its `--python-patch=N` option is not used by any build path; the `.postN` suffix
  comes from the tag
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

1. Upstream sets it in the root `pom.xml`: `<version>X.Y.Z-SNAPSHOT</version>` or `<version>X.Y.Z</version>`
2. `scripts/extract_version.py` converts based on mode:
    - Development: `X.Y.Z-SNAPSHOT` → `X.Y.Z.dev0`
    - Release: `X.Y.Z` → `X.Y.Z` (a `.postN` comes from the tag, through `BUILD_VERSION`)
3. Create annotated tag: `git tag -a X.Y.Z -F notes.md`
4. GitHub Release tag: `X.Y.Z`
5. Workflows use the tag version directly: `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN`
6. Used everywhere: PyPI (`X.Y.Z[.devN|.postN]`), docs (`/X.Y.Z/`)

**Note**: The base version is only in ONE place (`pom.xml`), and upstream owns it.

## Hotfix Release (`X.Y.Z.postN`)

A Python-only fix to a released version ships as `X.Y.Z.postN`. Do not make an
`X.Y.Z+1` of your own: that number is upstream's next release, and the tags would
collide.

```bash
# 1. Branch from the release tag (pom.xml there reads X.Y.Z)
git checkout -b release/X.Y.Z X.Y.Z

# 2. Make the fix, then build and test
cd bindings/python
./scripts/build.sh && uv run pytest
cd ../..

# 3. Commit and push the branch
git commit -am "Hotfix: description"
git push origin release/X.Y.Z

# 4. Tag, check, and push (as in step 4 above)
git tag -a X.Y.Z.post1 -m "Python hotfix release X.Y.Z.post1"
test "$(git rev-parse 'X.Y.Z.post1^{}')" = "$(git rev-parse HEAD)" && echo "tag OK"
git push origin X.Y.Z.post1

# 5. Create GitHub Release
gh release create X.Y.Z.post1 --verify-tag \
  --title "Python hotfix release X.Y.Z.post1" \
  --notes "Hotfix for critical bug in X.Y.Z"

# 6. Bring the fix back to main
git checkout main
git cherry-pick <fix commit>
git push origin main
```

## Rolling Back a Release

If you need to roll back a broken release:

**PyPI** (cannot delete, but can yank):

Yank the release in the PyPI web interface: open the project's **Manage** page, pick
the release, and choose **Options → Yank**. A yanked release stays downloadable for
pinned installs but is skipped by new unpinned installs. `twine` has no yank command.

**Documentation** (can delete version):

Docs live under `arcadedb/` on the `main` branch of `humemai/humemai-docs`, not on a `gh-pages`
branch. Run mike from a `humemai-docs/` checkout at the repo root, with the same flags as
`.github/workflows/deploy-python-docs.yml`:

```bash
# From the repo root (mike lives in the `docs` dependency group)
git clone -b main https://github.com/humemai/humemai-docs.git humemai-docs
cd humemai-docs

# Delete version from docs
uv run --project .. --group docs mike delete \
  --deploy-prefix arcadedb --branch main --push \
  --config-file ../bindings/python/mkdocs.yml \
  X.Y.Z

# Point the latest alias (the default version) at the previous release
uv run --project .. --group docs mike alias --update-aliases \
  --deploy-prefix arcadedb --branch main --push \
  --config-file ../bindings/python/mkdocs.yml \
  PREVIOUS_VERSION latest
```

**GitHub Release:**

1. Go to **Releases**
2. Edit the release
3. Check "Set as a pre-release"
4. Or delete the release entirely

## Troubleshooting

### PyPI upload fails

**Size limit exceeded:**

- Distribution might hit PyPI limits
- Request size increase: <https://pypi.org/help/#file-size-limit>
- Or distribute via GitHub releases only

**Authentication error:**

- Publishing uses PyPI trusted publishing, not API tokens
- Check that the `pypi` environment exists in the repository settings
- Verify the trusted publisher entry on PyPI (repository, `release-python-packages.yml`, environment `pypi`)

### Version check fails

- The release workflow stops if the tag's base version differs from the `pom.xml`
  base version (for example tag `26.9.1.dev0` while `pom.xml` reads `26.10.1-SNAPSHOT`)
- Check which commit the tag points to, and which `pom.xml` version that commit has

### Documentation deployment fails

**mike command error:**

- Ensure `git config` is set in workflow
- Check that the `HUMEMAI_DOCS_TOKEN` secret is set and can push to `humemai/humemai-docs`
- Verify the `main` branch of `humemai/humemai-docs` exists (docs deploy there under `arcadedb/`)
- The deploy installs the latest `mkdocs-material`, `mkdocs-git-revision-date-localized-plugin`,
  `mkdocs-macros-plugin`, and `mike` with `uv pip install --system`, not the locked `docs`
  group of the repo-root project, so a page that builds locally can still differ in the
  deployed build

**Version not appearing:**

- Check GitHub Actions logs
- Verify tag format: `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN`
- Manually run `mike list --deploy-prefix arcadedb --branch main --config-file ../bindings/python/mkdocs.yml` from a `humemai-docs/` checkout to see deployed versions

**Broken links:**

- Run `uv run mkdocs build --strict -f bindings/python/mkdocs.yml` locally first
- Check all internal links use correct paths
- Verify external URLs are accessible

### Build failures

**Docker build error:**

- Check Docker daemon is running
- Verify scripts/Dockerfile.build syntax
- Check that the `arcadedata/arcadedb:<version>` image exists for the `pom.xml` version: a
  release copies its JARs from it, and the Linux build's base stage pulls it

### Engine JAR gate fails

The `verify-engine-jars` job lists what differs between the image and the build of the
release commit, and the release does not publish:

- **JAR names differ**: the release commit is not the source of the image (check that the
  sync stopped at upstream's "Set release version to X.Y.Z" commit), or a dependency
  version moved.
- **A class or other entry differs**: the image holds different code from the release
  commit. Do not publish: find which commit the image was built from (the `buildNumber` in
  the summary) and what changed between them.
- **A dev tag fails**: expected when upstream's snapshot image has moved past the last
  sync; see [Development Releases](#development-releases-xyzdevn).

**Test failures:**

- Run specific test: `uv run pytest bindings/python/tests/test_core.py::test_name -v` (from the repository root)
- Check `log/` in the directory pytest ran from (`<repo root>/log/` for the command above;
  `bindings/python/log/` in CI)
- The tests use the wheel's bundled JRE, so no system Java is involved

## See Also

- [Documentation Development](documentation.md) - Working with MkDocs
- [Testing Guide](testing.md) - Running test suite
- [Contributing Guide](contributing.md) - Development workflow
- [Syncing Upstream](sync-upstream.md) - How upstream changes arrive
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [PyPI Publishing Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
