# AGENTS.md: bindings/python

The Python bindings (`arcadedb-embedded` on PyPI) are our work in this fork. The Java engine under `engine/` and the per-language `e2e-*` suites belong to upstream: report a cause there instead of changing it here, and send engine fixes upstream as issues and pull requests (see `docs/development/upstream-pr.md`). Benchmarks have their own file: `benchmarks/AGENTS.md`.

## Build and test

```bash
cd bindings/python
./scripts/build.sh linux/amd64
uv run pytest
```

- Python tooling runs through `uv add`, `uv sync` and `uv run` only.
- `build.sh` packages the jars of the published `arcadedata/arcadedb` image unless you pass a jar directory as its third argument. To test an engine fix, build the jars from the commit that contains it and say which commit in the issue or PR (`docs/development/build-architecture.md`, `docs/development/sync-upstream.md`).
- Run the repository's own checks before pushing, and again after any later edit, even a message string. A pass covers only the bytes it ran against.

## One change, everything current

- When a change touches behaviour, update the source, tests, examples, docs and README in the same pull request, and remove the old text in that change. A stale line is worse than a missing one.
- When a perf hunt or audit finds the better way to do something, apply it across the package: `src/`, `tests/`, `examples/`, `docs/` (the guide and best-practice pages). Grep for the old pattern first, and list what you swept in the PR body.
- Numbers copied into docs, comments or issues are generated from the result files or checked by a script. Never type them by hand.
- A temporary file or doc says when it goes: put a `REMOVE WHEN:` line in it. Nothing piles up.

## Git and GitHub

- Open an issue, work on a branch, open a PR that references the issue. Merge only when every check is green, and delete the branch (remote and local) on merge. Sweep leftover branches when you find them.
- Stage files by explicit path. Never `git add -A`: agent worktrees and logs get committed that way.
- Always pass `-R owner/repo` to `gh`.
- Issue, PR and comment bodies: one paragraph is one line (no hard wraps), no em dashes, tables and code fences keep their own lines.
- This repository is public. Never write secrets, token locations or private notes into a file, a commit message, an issue or a comment.
