# Syncing Upstream (retired)

!!! danger "Retired on 2026-10-25. Do not run `sync-upstream.sh`."
    ArcadeData/arcadedb deleted `bindings/python` in [#10615](https://github.com/ArcadeData/arcadedb/pull/10615) (commit `1e0507a522`, 2026-10-23, 143 files). A sync would merge that deletion into this fork. The decision was "Stop syncing" (2026-10-25). The script now exits with an error and a message that names the decision; only `./sync-upstream.sh --help` still prints (the old help, for the record).

Nothing needs the engine tree synced any more:

- The wheels take their engine JARs from the `arcadedata/arcadedb:<version>` release image, not from the Java sources in this tree.
- Pull requests to ArcadeData/arcadedb branch from upstream's `main` in the `tae898/arcadedb` fork, never from this repository ([Upstream Issues and Fixes](upstream-issues.md)).
- The Python bindings continue in [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python).

The engine tree in this repository is therefore frozen at the last sync. Do not rely on it being current, and do not edit it ([AGENTS.md](https://github.com/humemai/arcadedb-embedded-python/blob/main/AGENTS.md)).

## What replaces each use

| You wanted to | Do this instead |
|---|---|
| Get upstream's newer engine into the wheel | Nothing is synced: build the wheel against the release image's JARs (`build.sh` does this by default), or against JARs you built from any upstream commit (below). |
| Test an upstream engine fix | Build the engine JARs of the upstream commit and pass their directory to `build.sh` (below). |
| Send the bindings to ArcadeData/arcadedb | Retired too: [Sending the Bindings Upstream](upstream-bindings-pr.md). |
| Cut a release | [Release Workflow](release.md) (read its note on the version source first). |

## Testing an engine fix without a sync

Get the JARs of an upstream commit without building on your machine: run the `Build ArcadeDB engine jars` workflow on the commit's full 40-character SHA and download its `arcadedb-lib` artifact ([Upstream Issues and Fixes](upstream-issues.md#reporting-an-engine-bug) has the commands). Then:

```bash
cd bindings/python
./scripts/build.sh linux/amd64 3.12 <jar dir>
uv run pytest
```

The third argument is the JAR directory; an environment variable named `JAR_LIB_DIR` is ignored. See [Build Architecture](build-architecture.md#local-build).

## Verifying an upstream fix

When an issue we filed is fixed upstream, the way to check it is to build the wheel on the fix's engine and measure the thing the issue was about. Do this on a development machine, never on a machine that is in the middle of a benchmark run: a long measurement run should use one engine build from start to finish, and swapping in a freshly built wheel partway through would split its results across two engines in a way that cannot be undone afterwards.

The verification routine:

1. Build the engine JARs of the fix's merge commit (above), then `./scripts/build.sh linux/amd64 3.12 <jar dir>` in `bindings/python`. If the fix is already in a published upstream image, `build.sh` without the third argument is enough; otherwise the wheel does not contain the fix.
2. Re-run the issue's own reproduction against the new build. A Java reproduction compiles against an image's `lib/*` and needs no wheel at all, which makes it the cheaper check where one exists.
3. Compare against the same reproduction on the build the issue was filed against. A fix is "verified" when the repro that reproduced stops reproducing, on the same host, not when the issue is closed.
   **Mind the JVM.** Upstream's published images run **Java 21**; the wheel bundles a **Java 25** JRE, and the embedded JVM adds `-XX:+UseCompactObjectHeaders` unless the JVM arguments already set it, a flag Java 21 will not even start with. Verify on the image's own Java when replying upstream (that is what the issue was filed on), and, for any fix that affects the bindings, run the same repro again with that build's jars on Java 25 and the same flag. A fix confirmed on a JVM we do not ship is not yet confirmed for us.
4. Record the verification next to the issue, with the commit it was verified against.
5. Apply what the answer changes in practice across the package, the same day: `src/`, `tests/`, `examples/`, and `docs/`, not only the code that found the issue. A maintainer's answer often carries a recommendation (a setting, a statement, a pattern to avoid) beyond the fix itself. Install the rebuilt wheel first, so the new behavior can be tested locally; a test for a new feature should fail on the last release (`uv run --no-project --with arcadedb-embedded==<last release> python -m pytest ...`) and must not pass vacuously on the new one. The routine is not finished at the reply.

A benchmark host moves to a new engine only between runs, as a deliberate step: re-measure what the engine affects, and re-run an untouched comparison as a control.

## What the sync did (record)

For the record, the script kept a local `upstream-main` mirror of `upstream/main`, merged it into `main`, restored the fork-owned paths (`README.md`, `pyproject.toml`, `uv.lock`, and a few others) and kept `CLAUDE.md` out, then deleted every tracked file under `.github/` that was not on an allowlist, so no upstream workflow arrived. The lists, and the reasons behind them, are in the script's comments and in its git history. The local `upstream-main` branch is no longer maintained.
