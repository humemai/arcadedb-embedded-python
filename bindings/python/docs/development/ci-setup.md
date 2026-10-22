# CI/CD Multi-Platform Matrix Setup

## Overview

The CI/CD workflows build and release across **4 platforms** for a total of **16 wheel packages** per release (4 platforms × 4 Python versions), all under the single `arcadedb-embedded` package.

## Build Matrix

### Single-Package Strategy

- **arcadedb-embedded**: All platforms, JRE bundled, no external Java needed. The 26.11.1.dev0 linux/amd64 wheel measured on 2026-10-22 is about 68 MB compressed and 90 MB installed; other platforms and versions vary slightly.

### Platforms (All Native Runners)

- **linux/amd64**: Linux on x86_64 (ubuntu-24.04, Docker build)
- **linux/arm64**: Linux on ARM64 (ubuntu-24.04-arm, Docker build)
- **darwin/arm64**: macOS on Apple Silicon M1/M2/M3/M4 (macos-15, native build)
- **windows/amd64**: Windows on x86_64 (windows-2025, native build)

### Total Artifacts

**16 wheels per release**: 1 package × 4 platforms × 4 Python versions = 16 wheels

### Python 3.15 leg

Python 3.15 runs as one extra, informational leg in the bindings and the examples matrices, on `linux/amd64` only. It is an `include` entry with `experimental: true`, and the `test` job sets `continue-on-error: {% raw %}${{ matrix.experimental == true }}{% endraw %}`, so a failure in that leg is shown on the run but does not fail the job, the summary job or the pull request. It uploads no wheel artifact, so the release workflow never collects or publishes a 3.15 wheel. The package does not claim 3.15 yet: there is no 3.15 classifier, and the dependency floors audit (which reads the classifiers) does not resolve it. When the leg has been green for a release cycle, add the classifier, move the entry into the required matrix and raise the wheel count in the release workflow, `after_tag_verify.sh` and these docs.

## Workflows

### `test-python-bindings.yml`

- **Matrix**: `platform: [linux/amd64, linux/arm64, darwin/arm64, windows/amd64]` and `python-version: [3.11, 3.12, 3.13, 3.14]`, plus one informational Python 3.15 leg on `linux/amd64` (see [Python 3.15 leg](#python-315-leg))
- **Runners**: All native (no QEMU emulation)
    - ubuntu-24.04 (Linux x64)
    - ubuntu-24.04-arm (Linux ARM64)
    - macos-15 (macOS Apple Silicon)
    - windows-2025 (Windows x86_64)
- **Jobs**: `bandit`, `dependency-floors`, `download-jars`, `test` (16 required matrix jobs: 4 platforms × 4 Python versions, plus the informational 3.15 leg), and `test-summary`
- **Artifacts**:
    - `wheel-<os>-<arch>-py<version>` (for example `wheel-linux-amd64-py3.12`), kept 7 days; the
      release workflow collects these with the pattern `wheel-*-py*`
    - `wheel-<os>-<arch>-test`, a second copy of each platform's Python 3.12 wheel, kept 7 days
    - `arcadedb-jars`, the unfiltered JAR set for the native builds, kept 1 day
    - The `test-results-*` upload names `pytest-output.txt` and `.coverage`, which the pytest
      step does not write, so it uploads nothing
- **Triggers**: pushes to `main` and pull requests that touch `bindings/python/src/**`, `tests/**`, `examples/**`, `scripts/**`, `pyproject.toml`, `setup.py` or the workflow itself, manual dispatch, and `workflow_call` from the release workflow. A documentation-only change does not start the matrix (the `Docs Build` workflow covers it). A draft pull request skips every job (`bandit`, `dependency-floors`, `download-jars`, `test` and `test-summary`; the summary shows as skipped, not failed), and marking the pull request ready for review starts the run (`ready_for_review` is in the trigger types). Pushes to `main`, manual dispatch and the release workflow's call always run.
- **Timeouts**: job-level `timeout-minutes` (`bandit` and `dependency-floors` 15, `download-jars` 90 because the from-source engine build runs there, `test` 45, `test-summary` 5), so a job that never gets a runner or hangs does not hold the 360-minute default. Recent successful `test` jobs took 5 to 10 minutes.
- **Engine from source**: a manual dispatch or a `workflow_call` with `engine-from-source: true` builds the engine jars from this commit's source in `download-jars` instead of copying them out of upstream's snapshot image. Push and pull request runs never take this path.

### `test-python-examples.yml`

Builds the wheel on the same 4 × 4 matrix (and the same informational 3.15 leg) and runs the example scripts
(`0[1-9]_*.py 1[0-9]_*.py 2[0-9]_*.py` by default). Example 21 runs at reduced scale
(`--base-cities 1200 ...`, 15-minute limit).
Same path filter, triggers and draft rule as the bindings workflow (a draft pull request skips `download-jars`, `test-examples` and the summary). Job timeouts: `download-jars` 90, `test-examples` 120 (recent successful jobs took 29 to 38 minutes), summary 5. A clean exit is not the whole
check for example 10: its queries are run a second time on the pure-Python reference
backend (`--db python_memory`), and `examples/scripts/compare_query_hashes.py` fails the
job unless every query's row count and result hash agree (#12).

What else a run does:

- **An unreachable dataset host skips, it does not fail.** When `download_data.py` exits 75,
  the examples that need that dataset count as Skipped and the job stays green with a
  warning. Any other non-zero exit fails the job. Check the Skipped row of the job summary.
- **Each example has its own CI arguments and time limit.** An example that exceeds its
  limit (exit 124 from `timeout`) is reported as a timeout and counts as a failure.
- **Example 12 reads example 11's output.** It fails when example 11 did not build its
  database first.
- **The embedding model is cached.** `HF_HOME` points into the workspace and is cached, and a
  pre-warm step fetches the model with retries. That step has `continue-on-error`, so a
  failure there does not stop the job by itself.
- **A newer push to a pull request cancels the older run.** Runs on a push to `main` are left
  to finish.
- **Artifacts:** `example-logs-<os>-<arch>-py<version>` (kept 7 days), and, when the job
  fails, `example-databases-<os>-<arch>-py<version>` (kept 3 days).

### `lint-workflows.yml`

Runs on every push to `main` and every pull request:

- `sha-pinned-actions`: every action reference must be pinned to a full commit SHA
- `pre-commit`: the repository's pre-commit hooks (black, isort with the black profile, and the rest) on the files under `bindings/python`
- `ci-trigger-coverage` (`CI triggers cover every bindings/python entry`): every tracked entry directly under `bindings/python` must be in the trigger paths of both test workflows or listed there as needing no test run

A newer push to a pull request cancels the older run of this workflow; runs on `main` are left to finish. Draft pull requests still run it, because it is cheap.

### `docs-build.yml`

Named `Docs Build`. Runs `mkdocs build --strict` (Python 3.12, pinned `mkdocs`, `mkdocs-material` and plugin versions, run with `uvx`; `deploy-python-docs.yml` runs `mike` with the same versions) on pull requests and pushes to `main` that change `bindings/python/docs/**`, `bindings/python/mkdocs.yml` or the workflow, and on manual dispatch. It does not run the code blocks in the pages. See [Documentation](documentation.md#build-documentation).

### `build-engine-jars.yml`

Named `Build ArcadeDB engine jars`. A manual dispatch (inputs `repository`, default `ArcadeData/arcadedb`, `ref`, which is required, and `exclude-ha-raft-shaded`) or a `workflow_call` builds the full ArcadeDB distribution from source at any commit and uploads its `lib` directory as an artifact (`arcadedb-lib`, kept 7 days). Use it to check an upstream fix at its merge commit without building on your own machine; see [Upstream Issues](upstream-issues.md). The `engine-from-source` option of the two test workflows builds the jars itself and does not call this workflow.

### `release-python-packages.yml`

- **Trigger**: a pushed tag matching `[0-9]+.[0-9]+.[0-9]+*` (`X.Y.Z`, `X.Y.Z.devN`, `X.Y.Z.postN`)
- **validate-version**: the tag's base version must equal the `pom.xml` base version, or the release stops
- **test** and **test-examples**: call the two test workflows above with the tag version
- **publish**: needs all three, collects all 16 wheels, checks the count and the versions, and publishes to `arcadedb-embedded` on PyPI through the `pypi` environment (trusted publishing)
- The publish job has `continue-on-error: true`, so a failed upload or a failed check in it still leaves the run green. Check PyPI for every wheel the release built.

### Maintenance

Every `uses:` is pinned to a full commit SHA with a `# vX.Y.Z` comment (enforced by `lint-workflows.yml`), and every uv install is pinned to one version (`0.12.0`; raise it in all seven places together: `grep -c astral.sh/uv/ .github/workflows/*.yml`). `.github/dependabot.yml` opens one grouped pull request a week for the `github-actions` ecosystem with the commit prefix `ci`. It does not cover Python packages: tool versions in the workflows and `.pre-commit-config.yaml` are bumped by hand. The release and docs-deploy workflows only run on a tag, so a bump to them is not exercised by the pull request; the SHAs they share with the test workflows are, and the others (`gh-action-pypi-publish`) get their first run at the next release.

### Python tooling in the workflows

The workflows follow the project rule for Python tooling: no `pip install` and no `uv pip` anywhere. One-off tools run with `uvx` at an exact version (`bandit`, `pip-audit`, `mkdocs` with its plugins, `mike`). The inline `pyyaml` check in `lint-workflows.yml` runs with `uv run --no-project --with pyyaml==...`. The test jobs run `uv run --no-project --python <matrix version> --with <built wheel> --with-requirements <file> ...`, so the wheel and its test packages live in a throwaway environment and nothing is installed into the runner's interpreter. The example jobs do the same through a throwaway uv project (`uv run --project <dir> --python <matrix version> --with <built wheel> ...`) that the "Install example dependencies" step writes to `$RUNNER_TEMP`. The macOS and Windows wheel builds (`scripts/build-native.sh`) need a Python with the `build` module on `PATH`, so those steps run `bash ./scripts/build.sh` under `uv run --with build --with wheel --with setuptools`. That project declares the PyTorch CPU index with `explicit = true` and pins only `torch` to it through `[tool.uv.sources]`, so torch gets its CPU build from there and every other package comes from PyPI. The project is needed because `--no-project` reads no `[tool.uv.sources]` and a requirements file cannot mark an index explicit. Do not set `UV_INDEX` or `UV_INDEX_STRATEGY=unsafe-best-match` instead: uv then asks the PyTorch index about every package, and a PyTorch outage fails jobs that do not need torch (503 on `/whl/cpu/rich/` and `/whl/cpu/h11/`, #401). The examples job also sets `UV_HTTP_RETRIES=6` (uv's default is 3) to ride out a brief index outage. The Docker build of the Linux wheels (`scripts/Dockerfile.build`) installs nothing into the image's interpreter either: the `python-builder` stage runs `uv build --wheel`, which creates an isolated environment from the `[build-system] requires` in `pyproject.toml`, and the `tester` stage runs its smoke script with `uv run --no-project --with /tmp/*.whl --with pytest --with pytest-cov`.

### `deploy-python-docs.yml`

Deploys the docs with mike on a version tag or a manual dispatch. See
[Documentation](documentation.md#versioned-documentation). It runs on the same tag push as
the release but does not wait for it, so a tag whose release fails still deploys its docs
as `latest`.

## CI Gates

What must pass before a change is green, beyond the tests themselves:

- **Bandit** (`bandit` job): `src` and `tests` must be clean at low severity and low
  confidence; `examples` at medium severity and high confidence. A deliberate SQL
  string needs `# nosec B608` on the f-string line itself.
- **Dependency floors** (`dependency-floors` job): the dependencies declared in
  `bindings/python/pyproject.toml` (with the `test`, `vector`, `examples`, `arrow`,
  and `pandas` extras) are resolved to their lowest allowed versions for every
  Python version in the classifiers (`uv lock --script` and `uv export --script` on a generated PEP 723 header, because `uv lock` refuses the `managed = false` project), and `uvx pip-audit` checks the result.
- **No skips** (`test` job): a skipped test did not run, so the job fails on any skip in the
  JUnit XML (`scripts/check_test_skips.py`; its list of accepted skips is empty). A test file
  that cannot run on a platform is left out of collection in `tests/conftest.py`
  (`collect_ignore`: `test_sigint.py` and `test_python_function_interrupt.py` on Windows, `test_docs_examples.py` on the upstream pull
  request branch, which has no `docs/`), so it is not reported as skipped. A skip for a
  missing package (`could not import`, which is what `pytest.importorskip` gives, so call it
  without its own `reason=`) or for a feature the wheel always ships is therefore a failure,
  and a skip that is truly unavoidable (a Windows limitation, a case that needs an engine fix that is still upstream) is added to the list with the platform, the reason, and the upstream issue (for an engine bug a strict `xfail` is better: it fails the suite once the fix arrives). A new test dependency must be added both
  to the `test` extra in `bindings/python/pyproject.toml` and to the requirements list in the "Install wheel and
  test dependencies" step of `test-python-bindings.yml`. The repo-root `pyproject.toml`
  carries the same packages for local runs.
- **Timeouts**: the pytest step has a 30-minute limit, and `faulthandler_timeout = 600`
  in the pytest configuration dumps every Python thread's stack when a single test runs
  past 10 minutes. A minute earlier, `tests/conftest.py` writes every Java thread's
  name, state, and stack to the log, past pytest's output capture: a test hung inside
  a Java call shows only that call in the Python dump
  (`ARCADEDB_TEST_JAVA_DUMP_AFTER_S` moves the threshold; default 540 s).
- **Windows runs with `--capture=sys`**: with pytest's default fd capture, a Java log line
  could block forever on Windows, because swapping fds 1 and 2 around each test closes the
  handle the JVM cached for its console output and Windows can hand that value to another
  pipe (issue #10; the Java dump showed the main thread in `FileOutputStream.writeBytes`).
  The Windows job passes `--capture=sys`, so Java's log lines appear in that job's log.
- **SHA-pinned actions and pre-commit** (`lint-workflows.yml`, above).

Run the same checks locally before pushing (from the repository root):

```bash
uv run bandit -c bindings/python/pyproject.toml -r bindings/python/src bindings/python/tests \
  --severity-level low --confidence-level low
uv run bandit -c bindings/python/pyproject.toml -r bindings/python/examples \
  --severity-level medium --confidence-level high
uv run pytest -rs
uvx pre-commit run --files $(git ls-files 'bindings/python/**')
```

## PyPI Trusted Publisher Setup

The release workflow publishes through PyPI trusted publishing, which needs one
GitHub environment and one PyPI publisher entry. Both already exist for this
repository; this is how they are configured if they ever need to be recreated.

### Environment: `pypi`

- **PyPI Package**: `arcadedb-embedded`
- **Trusted Publisher**:
    - Repository: `humemai/arcadedb-embedded-python`
    - Workflow: `release-python-packages.yml`
    - Environment: `pypi`

### Steps

1. **Go to Repository Settings** → **Environments** → **New environment**
2. **Create `pypi`** environment
3. **Configure PyPI Trusted Publisher**:
    - Go to https://pypi.org/manage/account/publishing/
    - Add publisher for `arcadedb-embedded` (environment: `pypi`)

## Validation

### Expected Artifacts

After a successful release, you should see:

- **16 wheel files** on PyPI for `arcadedb-embedded` (4 platforms × 4 Python versions)

### Package Contents

Measured on the 26.11.1.dev0 linux/amd64 wheel on 2026-10-22:

| Wheel | JRE | JARs | Installed |
|-------|-----|------|-----------|
| about 68 MB | about 46 MB | about 44 MB | about 90 MB |

**All platforms include:**

- The same JAR set (includes the server, not Studio; the exclusions are in `scripts/jar_exclusions.txt`)
- A platform-specific JRE
- Native runners (no QEMU emulation anywhere)

## Cross-Platform Building

### Native Runners (No Emulation)

All platforms use native GitHub runners:

- **linux/amd64**: ubuntu-24.04 (Docker build)
- **linux/arm64**: ubuntu-24.04-arm (Docker build, native ARM64)
- **darwin/arm64**: macos-15 (native build)
- **windows/amd64**: windows-2025 (native build)

## Testing Locally

### Test specific platform build locally:

```bash
cd bindings/python

# Build for specific platform (requires Docker for Linux builds)
./scripts/build.sh linux/amd64
./scripts/build.sh darwin/arm64   # only on an Apple Silicon Mac

# Check the wheels
ls -lh dist/
```

### Test all platforms:

One machine cannot build all four wheels. `build.sh` builds the Linux targets in Docker,
but it exits with an error for a `darwin/*` or `windows/*` target unless it runs on a
host with that OS and architecture, because `jlink` only creates a JRE for the platform
it runs on. CI builds each wheel on its own native runner; to do the same by hand, run
`build.sh` on each host:

```bash
cd bindings/python

# Linux x86_64 host (Docker)
./scripts/build.sh linux/amd64

# Linux ARM64 host (Docker)
./scripts/build.sh linux/arm64

# Apple Silicon Mac (native)
./scripts/build.sh darwin/arm64

# Windows x86_64, from Git Bash (native)
./scripts/build.sh windows/amd64
```

The macOS and Windows builds need a JDK 25 or later with `jlink` and `JAVA_HOME` set, ignore
the Python version argument, and rewrite the tracked `pyproject.toml` in place. See
[Native Build Script](build-architecture.md#native-build-script).

## Troubleshooting

### "Value 'pypi' is not valid"

- This error appears in the workflow file when the `pypi` environment does not exist
- Create it as described in [PyPI Trusted Publisher Setup](#pypi-trusted-publisher-setup)

### Platform-specific JVM detection issues

The bindings load the bundled JRE's JVM library from a platform-specific path:

- macOS: `lib/server/libjvm.dylib`
- Linux: `lib/server/libjvm.so`
- Windows: `bin/server/jvm.dll`

### Wheel count mismatch

- The publish job validates that exactly 16 wheels exist
- If validation fails, check the build matrix jobs for failures
- Ensure all 4 platform builds succeeded

### Runner availability

All platforms use pinned runner versions:

- ubuntu-24.04 (guaranteed available)
- ubuntu-24.04-arm (GitHub-hosted ARM64)
- macos-15 (Apple Silicon, pinned version)
- windows-2025 (Windows x86_64, pinned version)
