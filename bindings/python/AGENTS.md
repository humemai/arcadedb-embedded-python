# AGENTS.md: bindings/python

The Python bindings (`arcadedb-embedded` on PyPI) are our work in this fork. The Java engine under `engine/` and the per-language `e2e-*` suites belong to upstream: report a cause there instead of changing it here. Benchmarks have their own file: `benchmarks/AGENTS.md`.

## Read first, by task

All paths are under `bindings/python/docs/`.

| You are | Read |
|---|---|
| setting up, building, changing code, opening a PR | `development/contributing.md` (including "Keep the change complete") |
| running or writing tests | `development/testing.md` |
| changing docs | `development/documentation.md` |
| touching CI or the wheel build | `development/ci-setup.md`, `development/build-architecture.md` |
| touching the Java bridge or the architecture | `development/bridge.md`, `development/architecture.md` |
| syncing upstream, or testing an engine fix | `development/sync-upstream.md` |
| sending a change or an engine fix to ArcadeData/arcadedb | `development/upstream-pr.md` |
| releasing | `development/release.md` |
| debugging a build, JVM or test failure | `development/troubleshooting.md` |
| making a performance claim, or using an engine bug workaround | `guide/performance.md`, `guide/known-issues.md`, `benchmarks/protocol.md` |

## Rules for agents

- Python tooling runs through `uv add`, `uv sync` and `uv run` only.
- Run the repository's checks before pushing and again after any later edit, even a message string. A pass covers only the bytes it ran against.
- Open an issue, work on a branch, open a PR that references the issue, merge when every check is green, delete the branch on merge.
- Stage files by explicit path, never `git add -A`. Always pass `-R owner/repo` to `gh`.
- Issue, PR and comment bodies: one paragraph is one line (no hard wraps), no em dashes; tables and code fences keep their own lines.
- This repository is public. Never write secrets, token locations or private notes into a file, a commit message, an issue or a comment.
