# Contributing Back to Upstream

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
pytest tests/ -v
```

## 3. Push and let CI prove it

```bash
git push origin main
```

Wait for the workflows to finish and read them. A run that reports success while a job skipped its real work is not a pass: the examples workflow skips a dataset-dependent example when its third-party host is unreachable, which hid a failing example for over two weeks in September 2026. Check that the examples you care about actually ran.

## 4. Regenerate the pull-request branch

```bash
./make-upstream-pr-branch.sh            # regenerate and force push
./make-upstream-pr-branch.sh --no-push  # regenerate only
```

The branch is never edited directly. It is rebuilt from `main` on top of `upstream-main`, so `main` stays the single source of truth and the branch can always be thrown away.

What crosses is the bare minimum: upstream's existing `bindings/python` tree with our file contents, plus whatever the wheel build, the tests, and the examples strictly need. Fork-only tooling, the benchmark harness, the notes, and result archives never cross. The rule was set by the first accepted pull request and has not changed since.

## What upstream expects

Their checks run on the pull request and some of them are stricter than ours, so run their pre-commit configuration locally before pushing the branch. A reproduction filed with an issue is Java against the engine API, never Python through the bindings, because the people reading it are Java developers. An issue body gets one line per paragraph, since single newlines render as breaks.
