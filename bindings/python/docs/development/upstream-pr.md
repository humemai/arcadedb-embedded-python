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

`build.sh` without a JAR argument packages the JARs of the published
`arcadedata/arcadedb:<version>` image, which can lag the sources you just synced.
To test the synced engine code, build with `./scripts/build.sh --engine-from-source linux/amd64`
(see [Build Architecture](build-architecture.md#local-build)). CI does the same by default:
its test workflows build the engine from the pushed commit.

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

- Besides `bindings/python`, it ships `.github/workflows/test-python-bindings.yml`, `.github/workflows/test-python-examples.yml`, and `.github/workflows/build-engine-jars.yml`, which the two test workflows call for their default JARs (the engine built from the tested commit). An edit to any of the three must also work in upstream's repository.
- It leaves out `examples/benchmark_results`, `examples/scripts`, `scripts/profile-python`, `scripts/fix_markdown.py`, `scripts/list_image_jars_by_size.sh`, `scripts/build_and_install_locally.sh`, and `scripts/compare_engine_jars.py` (the fork's release gate).
- It refuses to run while tracked files have uncommitted changes, and it warns when the branch has a top-level entry under `bindings/python` that upstream's tree lacks.
- It ships only the tree: set the pull request's title and body by hand.

## What upstream expects

Their checks run on the pull request and some of them are stricter than ours, so run their pre-commit configuration locally before pushing the branch, over everything that crosses:

```bash
uvx pre-commit run --files $(git ls-files 'bindings/python/**' .github/workflows/test-python-bindings.yml .github/workflows/test-python-examples.yml .github/workflows/build-engine-jars.yml)
```

Our own `pre-commit` job covers only `bindings/python`, and the three workflows cross too. A reproduction filed with an issue is Java against the engine API, never Python through the bindings, because the people reading it are Java developers. An issue body gets one line per paragraph, since single newlines render as breaks.

## When upstream fixes one of our issues

The same four steps run in a different order, with two additions, and the whole loop belongs to one sitting: a fix verified today against an engine that moves every day is a claim with an expiry date.

1. **Sync** (step 1) through the merge commit of the fix, and reconcile (step 2) whatever the sync touched.
2. **Verify with the reproduction that was filed**, never with the description of the fix. The reproduction is Java against the engine API, kept with the issue. Run it on the release the issue was filed against and on the synced engine, same JDK, and keep both outputs. Every number the reproduction prints must be exact afterwards; one that is merely better is a different bug. Re-run the reproductions of the fixes verified earlier on the same engine, since a later merge can undo an earlier one.
3. **Build, test, push, and read the workflows** (step 3), with the wheel's engine jar named by its file inside the wheel rather than by the wheel's version string. Build locally with `./scripts/build.sh --engine-from-source linux/amd64` so the wheel contains the synced fix whether or not upstream has published an image with it; the build summary prints the engine's `buildNumber`. CI's test workflows build the engine from the pushed commit by default. A sync that touches only Java does not trigger them, since they are path-filtered to the bindings; dispatch them by hand on the pushed commit (`gh workflow run "Test Python Bindings" --ref main`, and the same for the examples) and read those runs.
4. **Reply once on the issue** with the before-and-after table, the commit and JDK tested, and that the bindings suite is green on that engine. Read the thread first so the reply is not a duplicate. Nothing that was not run goes in it.
5. **Update the tracking the same day**: record the fix, its pull request, and the verification next to the issue, and mark the issue fixed with the numbers. Any workaround that exists because of the defect is marked for removal at the next deliberate engine upgrade of whatever depends on it, not removed now, because anything still running on the old engine still has the defect.

A fix that cannot be verified with the reproduction is not verified. Say so on the issue and in your own tracking, and keep it open.

## Before the merge: pre-verifying an open fix

A fix usually arrives as a pull request hours before it merges, and the reviews it gets are about the code, not about our reproductions. Pre-verifying it takes the steps above without the sync. Build the head's engine into a copy of the current jar set (the engine jar alone, unless the pull request touches the server or another module), run each issue's reproduction on the build it was filed on and on the head, on both JDKs, and comment once on the pull request with the same table. Repeat a race until the rate means something: a lost update seen in 4 of 4 runs on the filed build was clean in 12 of 12 on the head. Check that the head has not moved just before you comment, and test the sibling forms of each fixed behavior: the same operation through SQL and through openCypher, through the record API and through `GraphBatch`. PR #8989 fixed its three issues, but a Cypher `DELETE` that loses a race to a concurrent delete went from completing with no rows to failing without a retry, because the engine's Cypher wrapper rewraps the new retryable exception, and none of its reviews had said so. At the merge, verify again on the merge commit; the head you tested is not the commit that ships.

## When upstream groups our issues

Since 2026-10-03 a workflow opens a tracking issue for related reports and closes the later ones as duplicates ("Merged into #N, which now tracks this"). A close like that is not a fix. Read the tracker, reopen one of ours only if the grouping is wrong, and expect the fix to land against the tracker. At that point run the reproduction of every grouped issue, because they can differ in the commit that introduced them (#8999's `x < 2.7` line was bisected to the range change in 179cf8dcdc, while the type inference it was grouped with exists on older builds too), and reply on the tracker, since the issues are closed.
