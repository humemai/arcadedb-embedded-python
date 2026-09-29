# Syncing Upstream

This fork tracks `ArcadeData/arcadedb` through the local `upstream-main` branch.

## Commands

```bash
./sync-upstream.sh --status              # how far main and upstream-main are behind
./sync-upstream.sh --dry-run             # list what would be merged, change nothing
./sync-upstream.sh                       # sync to upstream/main
./sync-upstream.sh --until <commit>      # sync only up to a given upstream commit
```

`--until` also works with `--status` and `--dry-run`. It is how a release is cut: sync
up to upstream's "Set release version to X.Y.Z" commit (see
[Release Workflow](release.md)).

## What it does

In order:

1. Fetches `upstream` with `--no-tags` (upstream's release tags use the same numbers as ours) and shows the commits it would merge. `--status` and `--dry-run` stop here.
2. Refuses to continue if tracked files have uncommitted changes.
3. Asks `Continue with merge? [y/N]` and waits. There is no flag to skip it; from a non-interactive shell, pipe the answer (`printf y | ./sync-upstream.sh`), or the script exits silently at the prompt without merging.
4. Resets `upstream-main` to the sync target (`upstream/main`, or the `--until` commit).
5. Merges `upstream-main` into `main`.
6. Keeps this fork's own copies of the paths listed in `FORK_OWNED_PATHS` in the script (the root `README.md`, `pyproject.toml`, `uv.lock`, and a few others), and keeps the paths in `FORK_EXCLUDED_PATHS` (such as `CLAUDE.md`) out of the fork.
7. Treats `.github/` as an **allowlist**: after the merge it deletes every tracked file under `.github/` that is not named in `FORK_GITHUB_ALLOWLIST`, so no upstream workflow arrives. A list of files to delete could only name the ones that existed when it was written; the allowlist also stops the ones upstream adds later. Adding a workflow of our own therefore means adding it to that list in the same commit, or the next sync deletes it.

The lists live in `sync-upstream.sh` and nowhere else on purpose: this page used to repeat the workflows by name and had gone stale.

## When the merge stops on conflicts

The script resolves conflicts on its own only for the paths in `FORK_OWNED_PATHS` and
`FORK_EXCLUDED_PATHS`. Any other conflict makes it print the conflict steps and exit
**before** steps 6 and 7, so the fork-owned restore and the `.github` prune do not run.
The usual case is a modify/delete conflict on a `.github/` file that an earlier sync
pruned and upstream has since changed. Finish by hand:

```bash
# 1. See what conflicts
git diff --name-only --diff-filter=U

# 2. A pruned .github file: resolve it as a deletion
git rm --cached <path> && rm -f <path>

# 3. Resolve anything else normally, then finish the merge
GIT_EDITOR=true git merge --continue
```

Then do what the script skipped:

- Delete every tracked file under `.github/` that is not in `FORK_GITHUB_ALLOWLIST`.
- Check that the `FORK_OWNED_PATHS` files are unchanged against the pre-merge commit
  (`git diff <pre-merge commit> -- README.md pyproject.toml uv.lock ...`), and restore
  any that changed.
- Check that the `FORK_EXCLUDED_PATHS` files (such as `CLAUDE.md`) are absent.
- Commit, and run `./sync-upstream.sh --status`.

## After sync

```bash
cd bindings/python
./scripts/build.sh linux/amd64
uv run pytest
git push origin main
```

The build takes its engine JARs from the `arcadedata/arcadedb:<version>` image, not
from the Java sources you just synced. To test the synced engine code itself, build the
engine JARs and pass their directory as `build.sh`'s third argument (`JAR_LIB_DIR`); see
[Build Architecture](build-architecture.md#local-build).

This is step one of the contribution routine. The whole order, through to regenerating the pull-request branch, is in [Contributing Back to Upstream](upstream-pr.md).

## Verifying an upstream fix

When an issue we filed is fixed upstream, the way to check it is to sync, build the
wheel, and measure the thing the issue was about. Do this on a development machine,
never on a machine that is in the middle of a benchmark run: a long measurement run
should use one engine build from start to finish, and swapping in a freshly synced
wheel partway through would split its results across two engines in a way that cannot
be undone afterwards.

The verification routine:

1. `./sync-upstream.sh`, then `./scripts/build.sh linux/amd64` in `bindings/python`. Pass `JAR_LIB_DIR` if the fix has not reached a published upstream image yet; otherwise the wheel does not contain it.
2. Re-run the issue's own reproduction against the new build. A Java reproduction compiles against an image's `lib/*` and needs no wheel at all, which makes it the cheaper check where one exists.
3. Compare against the same reproduction on the build the issue was filed against. A fix is "verified" when the repro that reproduced stops reproducing, on the same host, not when the issue is closed.
   **Mind the JVM.** Upstream's published images run **Java 21**; the wheel bundles a **Java 25** JRE, and the embedded JVM always passes `-XX:+UseCompactObjectHeaders`, which Java 21 will not even start with. Verify on the image's own Java when replying upstream (that is what the issue was filed on), and, for any fix that affects the bindings, run the same repro again with that build's jars on Java 25 and the same flag. A fix confirmed on a JVM we do not ship is not yet confirmed for us.
4. Record the verification next to the issue, with the commit it was verified against.

A benchmark host moves to a new engine only between runs, as a deliberate step: re-measure what the engine affects, and re-run an untouched comparison as a control.
