# CI/CD Multi-Platform Matrix Setup

## Overview

The CI/CD workflows build and release across **4 platforms** for a total of **20 wheel packages** per release (4 platforms × 5 Python versions), all under the single `arcadedb-embedded` package.

## Build Matrix

### Single-Package Strategy

- **arcadedb-embedded**: All platforms, JRE bundled, no external Java needed. The 26.10.1.dev0 linux/amd64 wheel measured on 2026-09-29 is about 69 MB compressed and 96 MB installed; other platforms and versions vary slightly.

### Platforms (All Native Runners)

- **linux/amd64**: Linux on x86_64 (ubuntu-24.04, Docker build)
- **linux/arm64**: Linux on ARM64 (ubuntu-24.04-arm, Docker build)
- **darwin/arm64**: macOS on Apple Silicon M1/M2/M3/M4 (macos-15, native build)
- **windows/amd64**: Windows on x86_64 (windows-2025, native build)

### Total Artifacts

**20 wheels per release**: 1 package × 4 platforms × 5 Python versions = 20 wheels

## Workflows

### `test-python-bindings.yml`

- **Matrix**: `platform: [linux/amd64, linux/arm64, darwin/arm64, windows/amd64]` and `python-version: [3.10, 3.11, 3.12, 3.13, 3.14]`
- **Runners**: All native (no QEMU emulation)
    - ubuntu-24.04 (Linux x64)
    - ubuntu-24.04-arm (Linux ARM64)
    - macos-15 (macOS Apple Silicon)
    - windows-2025 (Windows x86_64)
- **Jobs**: `bandit`, `dependency-floors`, `download-jars`, `test` (20 matrix jobs: 4 platforms × 5 Python versions), and `test-summary`
- **Artifacts**:
    - `wheel-<os>-<arch>-py<version>` (for example `wheel-linux-amd64-py3.12`), kept 7 days; the
      release workflow collects these with the pattern `wheel-*-py*`
    - `wheel-<os>-<arch>-test`, a second copy of each platform's Python 3.12 wheel, kept 7 days
    - `arcadedb-jars`, the unfiltered JAR set for the native builds, kept 1 day
    - The `test-results-*` upload names `pytest-output.txt` and `.coverage`, which the pytest
      step does not write, so it uploads nothing
- **Triggers**: pushes to `main` and pull requests that touch `bindings/python/**` or the workflow itself, manual dispatch, and `workflow_call` from the release workflow

### `test-python-examples.yml`

Builds the wheel on the same 4 × 5 matrix and runs the example scripts
(`0[1-9]_*.py 1[0-9]_*.py 2[0-9]_*.py` by default). Example 21 runs at reduced scale
(`--base-cities 1200 ...`, 15-minute limit).
Same path filter and triggers as the bindings workflow. A clean exit is not the whole
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

### `release-python-packages.yml`

- **Trigger**: a pushed tag matching `[0-9]+.[0-9]+.[0-9]+*` (`X.Y.Z`, `X.Y.Z.devN`, `X.Y.Z.postN`)
- **validate-version**: the tag's base version must equal the `pom.xml` base version, or the release stops
- **test** and **test-examples**: call the two test workflows above with the tag version
- **publish**: needs all three, collects all 20 wheels, checks the count and the versions, and publishes to `arcadedb-embedded` on PyPI through the `pypi` environment (trusted publishing)
- The publish job has `continue-on-error: true`, so a failed upload or a failed check in it still leaves the run green. Check PyPI for every wheel the release built.

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
  Python version in the classifiers, and `pip-audit` checks the result.
- **No skips** (`test` job): a skipped test did not run, so the job fails on any skip in the
  JUnit XML (`scripts/check_test_skips.py`; its list of accepted skips is empty). A test file
  that cannot run on a platform is left out of collection in `tests/conftest.py`
  (`collect_ignore`: `test_sigint.py` on Windows, `test_docs_examples.py` on the upstream pull
  request branch, which has no `docs/`), so it is not reported as skipped. A skip for a
  missing package (`could not import`, which is what `pytest.importorskip` gives, so call it
  without its own `reason=`) or for a feature the wheel always ships is therefore a failure,
  and a skip that is truly unavoidable (a Windows limitation, a case that needs an engine fix that is still upstream) is added to the list with the platform, the reason, and the upstream issue (for an engine bug a strict `xfail` is better: it fails the suite once the fix arrives). A new test dependency must be added both
  to the `test` extra in `bindings/python/pyproject.toml` and to the "Install wheel and
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

- **20 wheel files** on PyPI for `arcadedb-embedded` (4 platforms × 5 Python versions)

### Package Contents

Measured on the 26.10.1.dev0 linux/amd64 wheel on 2026-09-29:

| Wheel | JRE | JARs | Installed |
|-------|-----|------|-----------|
| about 69 MB | about 63 MB | about 33 MB | about 96 MB |

**All platforms include:**

- The same JAR set (includes server/Studio; the exclusions are in `scripts/jar_exclusions.txt`)
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

- The publish job validates that exactly 20 wheels exist
- If validation fails, check the build matrix jobs for failures
- Ensure all 4 platform builds succeeded

### Runner availability

All platforms use pinned runner versions:

- ubuntu-24.04 (guaranteed available)
- ubuntu-24.04-arm (GitHub-hosted ARM64)
- macos-15 (Apple Silicon, pinned version)
- windows-2025 (Windows x86_64, pinned version)
