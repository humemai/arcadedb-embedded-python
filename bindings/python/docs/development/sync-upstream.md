# Syncing Upstream

This fork tracks `ArcadeData/arcadedb` through the local `upstream-main` branch.

## Commands

```bash
./sync-upstream.sh --status
./sync-upstream.sh --dry-run
./sync-upstream.sh
```

## What it does

- Updates `upstream-main` to match `upstream/main`
- Merges `upstream-main` into `main`
- Preserves this fork's root `README.md`
- Keeps fork-excluded files (such as `CLAUDE.md`) out of the fork
- Keeps removed upstream workflows from being reintroduced:
  `.github/workflows/mvn-test.yml`, `.github/workflows/mvn-deploy.yml`,
  `.github/workflows/mvn-release.yml`, `.github/workflows/license-compliance.yml`, and
  `.github/workflows/meterian.yml`, and `.github/workflows/studio-security-audit.yml`

## After sync

```bash
cd bindings/python
./scripts/build.sh linux/amd64
pytest tests/ -v
git push origin main
```

This is step one of the contribution routine. The whole order, through to regenerating the pull-request branch, is in [Contributing Back to Upstream](upstream-pr.md).

## Verifying an upstream fix: laptop only, never the bench host

When an issue we filed is fixed upstream, the way to check it is to sync, build the wheel, and measure the thing the issue was about. **That happens on the laptop and only on the laptop**, for as long as a campaign is running.

The reason is the pin. Every row a campaign writes records the engine that produced it, and a campaign holds one engine from first cell to last. The October campaign is `26.10.1.dev0` built from upstream `417314c18`; mini carries exactly that wheel and no other. Dropping a freshly-synced wheel onto the bench host to see whether a fix landed would split the campaign's rows across two engines, and there is no version of that which is recoverable afterwards — the rows do not become comparable again just because the intent was good.

So the two hosts have different jobs, and they do not overlap:

| | laptop | mini |
|---|---|---|
| what it runs | upstream verification, repros, ablations, the placeholder skeleton | the campaign, at its pin |
| what engine | whatever answers the question — a synced `main`, a published release, several at once | one, fixed for the whole campaign |
| what its numbers are for | deciding whether a fix works, and what to say in an issue | the page |
| may its numbers reach a page? | no | yes |

The verification routine, then:

1. `./sync-upstream.sh` on the laptop, then `./scripts/build.sh linux/amd64` in `bindings/python`.
2. Re-run the issue's own repro against the new wheel — the Java ones under `.notes/bench/repros/` compile against an image's `lib/*` and need no wheel at all, which makes them the cheaper check where one exists.
3. Compare against the same repro on the build the issue was filed against. A fix is "verified" when the repro that reproduced stops reproducing, on the same host, not when the issue is closed.
   **Mind the JVM.** Upstream's published images run **Java 21**; the engine pair this project measures runs **Java 25** (the wheel bundles JRE 25, and the server image is built `FROM amazoncorretto:25`), and the embedded JVM always passes `-XX:+UseCompactObjectHeaders`, which Java 21 will not even start with. Verify on the image's own Java when replying upstream -- that is what the issue was filed on -- and, for any fix that reaches our numbers, run the same repro again with that build's jars on `amazoncorretto:25` and the same flag. A fix confirmed on a JVM we do not ship is not yet confirmed for us.
4. Record the verification in `.notes/bench/issues-trail.md` beside the filing, with the commit verified against.

**The bench host gets the new engine only at a re-pin**, which is a deliberate step with its own cost: re-measure every ArcadeDB arm, carry the comparators forward, and re-run one untouched comparator as a control that reproduces (DECISIONS #41). A re-pin replaces numbers on purpose; a wheel swapped in mid-campaign corrupts them by accident.
