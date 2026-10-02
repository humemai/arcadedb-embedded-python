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
- It ships only the tree: set the pull request's title and body by hand.

## What upstream expects

Their checks run on the pull request and some of them are stricter than ours, so run their pre-commit configuration locally before pushing the branch, over everything that crosses:

```bash
uvx pre-commit run --files $(git ls-files 'bindings/python/**' .github/workflows/test-python-bindings.yml .github/workflows/test-python-examples.yml)
```

Our own `pre-commit` job covers only `bindings/python`, and the two workflows cross too. A reproduction filed with an issue is Java against the engine API, never Python through the bindings, because the people reading it are Java developers. An issue body gets one line per paragraph, since single newlines render as breaks.

## When upstream fixes one of our issues

The same four steps run in a different order, with two additions, and the whole loop belongs to one sitting: a fix verified today against an engine that moves every day is a claim with an expiry date.

1. **Sync** (step 1) through the merge commit of the fix, and reconcile (step 2) whatever the sync touched.
2. **Verify with the reproduction that was filed**, never with the description of the fix. The reproduction is Java against the engine API, kept with the issue. Run it on the release the issue was filed against and on the synced engine, same JDK, and keep both outputs. Every number the reproduction prints must be exact afterwards; one that is merely better is a different bug. Re-run the reproductions of the fixes verified earlier on the same engine, since a later merge can undo an earlier one.
3. **Build, test, push, and read the workflows** (step 3), with the wheel's engine jar named by its file inside the wheel rather than by the wheel's version string. If the fix is not yet in a published upstream image, pass the engine's JAR directory as `build.sh`'s third argument (`./scripts/build.sh linux/amd64 3.12 <jar dir>`) so the wheel contains it; an environment variable named `JAR_LIB_DIR` is ignored. A sync that touches only Java does not trigger the two test workflows, which are path-filtered to the bindings; dispatch them by hand on the pushed commit (`gh workflow run "Test Python Bindings" --ref main`, and the same for the examples) and read those runs.
4. **Reply once on the issue** with the before-and-after table, the commit and JDK tested, and that the bindings suite is green on that engine. Read the thread first so the reply is not a duplicate. Nothing that was not run goes in it.
5. **Update the tracking the same day**: record the fix, its pull request, and the verification next to the issue, and mark the issue fixed with the numbers. Any workaround that exists because of the defect is marked for removal at the next deliberate engine upgrade of whatever depends on it, not removed now, because anything still running on the old engine still has the defect.

A fix that cannot be verified with the reproduction is not verified. Say so on the issue and in your own tracking, and keep it open.
