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

!!! warning "Upstream uses the same version numbers"
    ArcadeDB's release tags carry the same numbers as ours (`26.9.1` is both their
    engine release and our wheel release). Always fetch `upstream` with `--no-tags`
    (`sync-upstream.sh` does). If their tag is ever fetched, `git tag -a X.Y.Z` fails
    with "already exists", but `git push origin X.Y.Z` still succeeds and publishes
    upstream's commit. Check what a tag points to before pushing it (step 4 below).
    `git config remote.upstream.tagopt --no-tags` makes `git fetch upstream` skip tags for good.

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

# Build distribution
./scripts/build.sh

# Test distribution (build.sh refreshed the repo-root uv env with the new wheel)
uv run pytest
```

- [ ] Full test suite passes
- [ ] Every wheel is under 100 MB (`build.sh` fails a wheel at or over it, and the release workflow
  checks it again before the upload; the policy holds even where the PyPI project's own limit is
  higher, because an embedded database should not ship a huge wheel)
- [ ] Release notes prepared in `notes.md` (see [What the release body contains](#what-the-release-body-contains))
- [ ] Documentation updated if needed

### 3. Push and Let CI Pass

```bash
git push origin main
```

Wait for "Test Python Bindings" and "Test Python Examples" to finish, and check that
the examples actually ran rather than skipped. The bindings summary of a green run reads
`N passed, K expected failures (xfail), 0 skipped, 0 failed`: the xfails are open upstream bugs
the suite tracks, and `scripts/check_test_skips.py` already fails any real skip.

The other 19 wheels are built by CI, so check their sizes before you tag. With the release
commit `pom.xml` reads `X.Y.Z`, so the run on the commit you will tag builds from the same
official image the release run will use:

```bash
gh run download <run-id> -R humemai/arcadedb-embedded-python -p 'wheel-*-py*' -D wheels
ls wheels/*/*.whl | wc -l                                           # 20
for w in wheels/*/*.whl; do [ "$(stat -c%s "$w")" -lt 100000000 ] || echo "TOO BIG: $w"; done
```

### 4. Tag, Check, and Release

Tags are the source of truth. Pushing `X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN` triggers
PyPI + docs.

```bash
# No tag of this name may exist yet, here or on origin (upstream's tags share our names)
test -z "$(git tag -l X.Y.Z)" && test -z "$(git ls-remote --tags origin X.Y.Z)" && echo "no tag yet"

git tag -a --cleanup=verbatim X.Y.Z -F notes.md

# The tag must point at the commit you just tested...
test "$(git rev-parse 'X.Y.Z^{}')" = "$(git rev-parse HEAD)" && echo "tag OK"
# ...and must not be upstream's release commit (ours has it as an ancestor, but is not it)
test "$(git rev-parse 'X.Y.Z^{}')" != "<upstream release commit, 40 characters>" && echo "not upstream's"

git push origin X.Y.Z

# The remote tag must peel to the same commit
git ls-remote origin 'refs/tags/X.Y.Z^{}'

gh release create X.Y.Z -R humemai/arcadedb-embedded-python --verify-tag \
  --title "X.Y.Z" \
  --notes-file notes.md
```

`--cleanup=verbatim` keeps the lines of the notes that start with `#`: `git tag -F` strips them
by default, so the `##` headings of the release body would be missing from the tag message.
`--verify-tag` stops `gh` from creating a tag of its own if the pushed one is missing.
Always pass `-R humemai/arcadedb-embedded-python`: in a checkout of this fork, `gh`
resolves its default repository to upstream, where a release would be a mistake. The
release is created at <https://github.com/humemai/arcadedb-embedded-python/releases>;
every release there is named by its tag (`26.9.1`, `26.5.1.post1`) and has no assets,
because the wheels go to PyPI.

#### What the release body contains

Read the previous release at that page and keep its shape:

- one line saying the wheel bundles the ArcadeDB engine of that version, synced to
  upstream's release commit, with a link to the commit by its full SHA;
- the `pip install` lines, including the optional extras;
- "Read this before upgrading": behaviour changes a working program may depend on,
  grouped under SQL, openCypher, and Through the bindings, each deliberate upstream and
  linked to its issue;
- a Security section for upstream advisories that matter to embedded use;
- what the bindings added, and a pointer to [Known Engine Issues](../guide/known-issues.md).

### 5. Monitor GitHub Actions

- Check the Actions tab for "Build and Release Python Packages to PyPI" (`release-python-packages.yml`) and "Deploy MkDocs to GitHub Pages" (`deploy-python-docs.yml`).
- The release workflow first checks that the tag's base version equals the `pom.xml`
  base version, then runs both test workflows, then publishes the wheels.
- The publish job has `continue-on-error: true`, so the run stays green even when the
  PyPI upload fails. Read the publish job's own conclusion, then check PyPI for every
  wheel the release built:

  ```bash
  curl -s https://pypi.org/pypi/arcadedb-embedded/X.Y.Z/json | python3 -c \
    "import json,sys; fs=json.load(sys.stdin)['urls']; print(len(fs)); [print(f['filename'], f['size']) for f in sorted(fs, key=lambda f: f['filename'])]"
  ```

  `scripts/after_tag_verify.sh <version> <previous-version> <release-run-id>` (optionally followed
  by the engine jar's sha256 and build number) does the whole check in one command and prints
  PASS or FAIL for each step: the run and the publish job's own conclusion, the file set against
  the previous release, every file's sha256 against the run's artifact, `pip download` for the
  four platforms, fresh installs on the oldest and newest Python, and the docs.

  Expect 20 files: Python 3.10 to 3.14, each as `macosx_11_0_arm64`,
  `manylinux_2_34_aarch64`, `manylinux_2_34_x86_64`, and `win_amd64`, about 66 to 72 MB
  each (PyPI refuses a file over 100 MB). Compare each file's sha256 with the artifact
  the run built, and install the release from PyPI into a fresh environment and run a
  query. The workflow does not set `skip-existing`, so re-running the publish job after
  a partial upload stops at the first file that already exists: upload the missing
  files from the run's artifacts with `twine upload --skip-existing`.
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

### 7. Open the Upstream Pull Request, Last

Only now regenerate the `python-bindings` branch and open the pull request to
ArcadeData/arcadedb: it is built on the `upstream-main` mirror that this sync just
brought up to date, and it carries everything since the previous one. See
[Contributing Back to Upstream](upstream-pr.md).

## Development Releases (`X.Y.Z.devN`)

A dev tag is released from `main` while `pom.xml` reads `X.Y.Z-SNAPSHOT`: the release
workflow compares only the base version (`X.Y.Z`). Tag and check it exactly as in
step 4. A dev tag publishes to the real PyPI index and becomes the `latest` docs.

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
gh release create X.Y.Z.post1 -R humemai/arcadedb-embedded-python --verify-tag \
  --title "X.Y.Z.post1" \
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

- PyPI refuses a file over 100 MB by default, and the policy here is to stay under that:
  `build.sh` and the release workflow's "Verify wheels" step fail a wheel at or over
  100 MB before anything uploads
- Find what grew instead of asking for a larger limit: `scripts/list_image_jars_by_size.sh`
  lists the engine JARs by size, and `scripts/jar_exclusions.txt` is where a JAR that the
  wheel does not need is dropped

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
- Check that the `arcadedata/arcadedb:<version>` image exists for the `pom.xml` version: the Linux build copies its JARs from it

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
