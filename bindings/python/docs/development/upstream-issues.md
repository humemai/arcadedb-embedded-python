# Upstream Issues and Fixes

How an engine bug found here reaches ArcadeData/arcadedb, and how we check the fix. The periodic update of `bindings/python` is a separate routine: [Sending the Bindings Upstream](upstream-bindings-pr.md).

## Reporting an engine bug

Upstream's `CONTRIBUTING.md` (repository root) sets the rules for reporters; ours add the reproduction.

- A security vulnerability is never reported in a public issue or pull request: follow `SECURITY.md`.
- A new feature or a change of behaviour starts in upstream's Discussions, not in an issue.
- Check the bug on the current upstream `main` and on the latest release before filing, and search the existing issues. If a tracking issue exists, comment there instead of opening another. To get the engine jars of any upstream commit without building on your machine, run the `Build ArcadeDB engine jars` workflow with the commit's full 40-character SHA (a short SHA fails) and download its `arcadedb-lib` artifact:

```bash
gh workflow run build-engine-jars.yml -R humemai/arcadedb-embedded-python -f ref=<full sha> -f exclude-ha-raft-shaded=true
gh run download <run id> -R humemai/arcadedb-embedded-python -n arcadedb-lib -D <dir>
```

  `exclude-ha-raft-shaded` leaves out the shaded HA jar, which bundles its own copy of the engine classes and would hide an engine swap.
- One problem per issue. The title names the symptom. The body gives what you expected and what happened, with numbers, the exact build (version and commit) and the JDK.
- The reproduction is Java against the engine API, never Python through the bindings, because the people reading it are Java developers. Keep it minimal and keep it with the issue: it is also how the fix is verified later.
- One line per paragraph in the body, since single newlines render as breaks.
- Record the issue where you track work. When the fix lands, follow "When upstream fixes one of our issues" below.

## Sending a low-hanging fix

Most issues stay issues. Send a pull request only when the fix is small and you are sure of it; otherwise leave it to the maintainers.

- Branch from upstream's `main` in the `tae898/arcadedb` fork (the `fork` remote; its Actions are disabled, so its pushes cost nothing) and open the pull request with `gh pr create -R ArcadeData/arcadedb --head tae898:<branch>`.
- The body references the issue (`Fixes #N`). Add a test that fails before the change and passes after it, put the SPDX header on new files, and run upstream's pre-commit configuration, as upstream's `CONTRIBUTING.md` asks.
- Keep it to the engine change. The periodic bindings update is a different pull request.

## When upstream fixes one of our issues

The same four steps of [Sending the Bindings Upstream](upstream-bindings-pr.md) run in a different order, with two additions, and the whole loop belongs to one sitting: a fix verified today against an engine that moves every day is a claim with an expiry date.

1. **Sync** (step 1) through the merge commit of the fix, and reconcile (step 2) whatever the sync touched.
2. **Verify with the reproduction that was filed**, never with the description of the fix. The reproduction is Java against the engine API, kept with the issue. Run it on the release the issue was filed against and on the synced engine, same JDK, and keep both outputs. Every number the reproduction prints must be exact afterwards; one that is merely better is a different bug. Re-run the reproductions of the fixes verified earlier on the same engine, since a later merge can undo an earlier one.
3. **Build, test, push, and read the workflows** (step 3), with the wheel's engine jar named by its file inside the wheel rather than by the wheel's version string. If the fix is not yet in a published upstream image, pass the engine's JAR directory as `build.sh`'s third argument (`./scripts/build.sh linux/amd64 3.12 <jar dir>`) so the wheel contains it; an environment variable named `JAR_LIB_DIR` is ignored. A sync that touches only Java does not trigger the two test workflows, which are path-filtered to the bindings; dispatch them by hand on the pushed commit (`gh workflow run "Test Python Bindings" --ref main`, and the same for the examples) and read those runs.
4. **Reply once on the issue** with the before-and-after table, the commit and JDK tested, and that the bindings suite is green on that engine. Read the thread first so the reply is not a duplicate. Nothing that was not run goes in it.
5. **Update the tracking the same day**: record the fix, its pull request, and the verification next to the issue, and mark the issue fixed with the numbers. Any workaround that exists because of the defect is marked for removal at the next deliberate engine upgrade of whatever depends on it, not removed now, because anything still running on the old engine still has the defect.

A fix that cannot be verified with the reproduction is not verified. Say so on the issue and in your own tracking, and keep it open.

## Before the merge: pre-verifying an open fix

A fix usually arrives as a pull request hours before it merges, and the reviews it gets are about the code, not about our reproductions. Pre-verifying it takes the steps above without the sync. Build the head's engine into a copy of the current jar set (the engine jar alone, unless the pull request touches the server or another module), run each issue's reproduction on the build it was filed on and on the head, on both JDKs, and comment once on the pull request with the same table. Repeat a race until the rate means something: a lost update seen in 4 of 4 runs on the filed build was clean in 12 of 12 on the head. Check that the head has not moved just before you comment, and test the sibling forms of each fixed behavior: the same operation through SQL and through openCypher, through the record API and through `GraphBatch`. PR #8989 fixed its three issues, but a Cypher `DELETE` that loses a race to a concurrent delete went from completing with no rows to failing without a retry, because the engine's Cypher wrapper rewraps the new retryable exception, and none of its reviews had said so. At the merge, verify again on the merge commit; the head you tested is not the commit that ships.

## When upstream groups our issues

Since 2026-10-03 a workflow opens a tracking issue for related reports and closes the later ones as duplicates ("Merged into #N, which now tracks this"). A close like that is not a fix. Read the tracker, reopen one of ours only if the grouping is wrong, and expect the fix to land against the tracker. At that point run the reproduction of every grouped issue, because they can differ in the commit that introduced them (#8999's `x < 2.7` line was bisected to the range change in 179cf8dcdc, while the type inference it was grouped with exists on older builds too), and reply on the tracker, since the issues are closed.
