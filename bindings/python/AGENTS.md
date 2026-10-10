# AGENTS.md: bindings/python

The Python bindings (`arcadedb-embedded` on PyPI) are our work in this fork. The Java engine under `engine/` and the per-language `e2e-*` suites belong to upstream: report a cause there instead of changing it here. Benchmarks have their own file: `benchmarks/AGENTS.md`.

Paths in this file are relative to the repository root (the directory that contains `.git`), whatever your working directory is.

## Read first, by task

| You are | Read |
|---|---|
| setting up, building, changing code, opening a PR | `bindings/python/docs/development/contributing.md` (including "Keep the change complete") |
| running or writing tests | `bindings/python/docs/development/testing.md` |
| changing docs | `bindings/python/docs/development/documentation.md` |
| touching CI or the wheel build | `bindings/python/docs/development/ci-setup.md`, `bindings/python/docs/development/build-architecture.md` |
| touching the Java bridge or the architecture | `bindings/python/docs/development/bridge.md`, `bindings/python/docs/development/architecture.md` |
| syncing upstream, or testing an engine fix | `bindings/python/docs/development/sync-upstream.md` |
| sending a change or an engine fix to ArcadeData/arcadedb | `bindings/python/docs/development/upstream-pr.md` |
| releasing | `bindings/python/docs/development/release.md` |
| debugging a build, JVM or test failure | `bindings/python/docs/development/troubleshooting.md` |
| making a performance claim, or working around an engine bug | `bindings/python/docs/guide/performance.md`, `bindings/python/docs/guide/known-issues.md`, `bindings/python/docs/benchmarks/protocol.md` |

## Where a behaviour is described

A change to behaviour updates every place that describes it. Grep these for the old text before opening the PR:

| Area | Source and tests | Docs |
|---|---|---|
| API (database, schema, transactions, results, records, async, exceptions, type conversion, JVM) | `bindings/python/src/arcadedb_embedded/`, `bindings/python/tests/` | `bindings/python/docs/api/` |
| Vectors | same | `bindings/python/docs/guide/vectors.md`, `bindings/python/docs/api/vector.md` |
| Graphs and bulk loading | same | `bindings/python/docs/guide/graphs.md`, `bindings/python/docs/api/graph_batch.md` |
| Import and export | same | `bindings/python/docs/guide/import.md`, `bindings/python/docs/api/importer.md`, `bindings/python/docs/api/exporter.md` |
| Server mode, operations | same | `bindings/python/docs/guide/server.md`, `bindings/python/docs/api/server.md`, `bindings/python/docs/guide/operations.md` |
| Which Java API is wrapped | same | `bindings/python/docs/java-api-coverage.md`, `bindings/python/docs/api-access-methods.md` |
| Examples | `bindings/python/examples/` | `bindings/python/docs/examples/`, `bindings/python/docs/getting-started/` |

## Rules for agents

- Python tooling runs through `uv add`, `uv sync` and `uv run` only.
- Run the repository's checks before pushing and again after any later edit, even a message string. A pass covers only the bytes it ran against.
- Open an issue, work on a branch, open a PR that references the issue, merge when every check is green, delete the branch on merge.
- Stage files by explicit path, never `git add -A`. Always pass `-R owner/repo` to `gh`.
- Issue, PR and comment bodies: one paragraph is one line (no hard wraps), no em dashes; tables and code fences keep their own lines.
- A security vulnerability is never reported in a public issue or PR; follow `SECURITY.md`.
- When you add, rename or remove a doc, update its row in this file in the same PR.
- This repository is public. Never write secrets, token locations or private notes into a file, a commit message, an issue or a comment.
