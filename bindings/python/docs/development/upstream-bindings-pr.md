# Sending the Bindings Upstream

Changes made here reach ArcadeData/arcadedb through one branch, `python-bindings`, regenerated from `main` rather than edited. The order below matters: each step exists because skipping it has cost something.

## 1. Sync upstream into main

```bash
./sync-upstream.sh
```

Never hand-merge. The script owns the allowlist of what crosses and maintains the `upstream-main` mirror the pull-request branch is built on. See [Syncing Upstream](sync-upstream.md).

## 2. Reconcile the bindings with what arrived

Upstream changes can move the Java surface the bindings wrap. Read what the sync brought and update the source, tests, examples, and documentation where it lands. A sync that compiles is not a sync that is correct: run the tests and the examples, not just the build.

```bash
cd bindings/python
./scripts/build.sh linux/amd64
uv run pytest
```

`build.sh` without a third argument packages the JARs of the published
`arcadedata/arcadedb:<version>` image, which can lag the sources you just synced.
To test the synced engine code, build its JARs and pass their directory as the third
argument, `JAR_LIB_DIR` (see [Build Architecture](build-architecture.md#local-build)).

## 3. Push and let CI prove it

```bash
git push origin main
```

Wait for the workflows to finish and read them. A run that reports success while a job skipped its real work is not a pass: the examples workflow skips a dataset-dependent example when its third-party host is unreachable. Check that the examples you care about actually ran.

## 4. Regenerate the pull-request branch

```bash
./make-upstream-pr-branch.sh            # regenerate and force push
./make-upstream-pr-branch.sh --no-push  # regenerate only
```

The branch is never edited directly. It is rebuilt from `main` on top of `upstream-main`, so `main` stays the single source of truth and the branch can always be thrown away.

What crosses is the bare minimum: upstream's existing `bindings/python` tree with our file contents, plus whatever the wheel build, the tests, and the examples strictly need. Fork-only tooling, the benchmark harness, the notes, and result archives never cross.

What the script does beyond that:

- Besides `bindings/python`, it ships `.github/workflows/test-python-bindings.yml` and `.github/workflows/test-python-examples.yml`, so an edit to either workflow must also work in upstream's repository.
- It leaves out `examples/benchmark_results`, `examples/scripts`, `scripts/profile-python`, `scripts/fix_markdown.py`, `scripts/list_image_jars_by_size.sh`, and `scripts/build_and_install_locally.sh`.
- It refuses to run while tracked files have uncommitted changes, and it warns when the branch has a top-level entry under `bindings/python` that upstream's tree lacks.
- It ships only the tree: set the pull request's title and body by hand. The earlier ones
  (ArcadeData/arcadedb#5807, #6889) open with "Periodic update of `bindings/python` from the
  downstream packaging fork (humemai/arcadedb-embedded-python), rebased on current `main`.
  No engine code.", say that the change has been shipping on PyPI as `arcadedb-embedded`,
  most recently as which version, then explain each file that crosses outside
  `bindings/python` and why, show the result of upstream's checks on the first push, and
  state the scope. In a release cycle the pull request comes last, after the release and
  the sync that follows it ([Release Workflow](release.md#7-open-the-upstream-pull-request-last)).

## What upstream expects

Their checks run on the pull request and some of them are stricter than ours, so run their pre-commit configuration locally before pushing the branch, over everything that crosses:

```bash
uvx pre-commit run --files $(git ls-files 'bindings/python/**' .github/workflows/test-python-bindings.yml .github/workflows/test-python-examples.yml)
```

Our own `pre-commit` job covers only `bindings/python`, and the two workflows cross too.

Reporting an engine bug, and checking a fix to one of our issues, are in [Upstream Issues and Fixes](upstream-issues.md).
