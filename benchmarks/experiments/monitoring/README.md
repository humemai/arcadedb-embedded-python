# Campaign monitoring

Two pieces, both read-only.

`campaign_watch.py` answers "are the numbers genuinely fine", not "is it still
running". Run it on the bench host at any time. It prints a per-cell table,
then two sections: ACKNOWLEDGED for findings already understood and tracked,
and SUSPECT for anything else.

```sh
campaign_watch.py --since-marker 'q92 lifecycle scale-up START'
campaign_watch.py --since 2026-08-15T00:00:00
campaign_watch.py --all          # expect history to fire rules
```

`campaign_monitor.sh <job-pattern> <start-marker>` polls the bench host every
two minutes and emits one line per event: lane transitions, failed cells,
SUSPECT rows, the queue going empty without ALL-DONE, orphaned containers,
host swap-in, and disk pressure. Silence means healthy, which is only true
because the queue-death and failure cases are covered explicitly.

```sh
campaign_monitor.sh 'q9[0-9]_' 'q92 lifecycle scale-up START'
```

## Why each check exists

Every rule is a defect this project shipped or nearly shipped, so none of them
is hypothetical:

- a memory column that was 88% the benchmark's own Python driver
- a memory metric capturing 26% of one engine's peak and 98% of another's
- `SizeRw` reading 20 KB while 1017 MiB sat in a declared volume
- a disk reading taken before writeback and compaction settled
- a lane that timed one pass and never said whether it was cold or warm,
  hiding a 9.4x second-pass gain on the comparator we beat
- two lanes that never closed the database, so the disk figure was a crash
  state and deferred shutdown work was never paid (#155)
- 30 OOM-killed cells that exited 0 with empty error strings
- a served JVM comparator whose heap nobody ever observed
- comparator rows stamped `"unknown (PackageNotFoundError)"` or with a package
  name where a version belongs, which nobody can re-measure (#156)
- a cell that quietly finished at N=3 and printed a median like any other

## Six rules learned building it

**Scope every check to the current run, across files as well as within them.**
The first version grepped the whole of one appended log and reported an
aborted smoke from hours earlier on its very first poll. The rewrite still
reported a `TypeError` from a *different, already-fixed job*, because it
globbed every job log in the home directory. Both scopes are needed: files
newer than the start marker, and within each file the last runner invocation.

**The marker names the START line.** Match on a job prefix instead and the
last match is that job's own ALL-DONE, so the window collapses and the
campaign's log falls outside its own scope.

**Never kill by a pattern your own shell matches.** Restarting the monitor
with `pkill -f campaign_monitor.sh` in the same command killed the shell that
was launching the replacement, so both the old and new monitors died and a
live campaign ran unwatched. Same shape as an ssh kill pattern that matched
its own ssh. Launch the replacement in a separate invocation, or match on
pids from `pgrep` rather than on a string the launcher also contains.

**Completeness is an end-of-run check.** Mid-run every cell is legitimately
short, so a "N reps, expected 5" rule fires on every in-flight cell and
buries everything else. It lives behind `--final`, which the live monitor
never passes and the queue script runs once after ALL-DONE.

**Check the premise before trusting the rule.** A rule asserting that a JVM
arm's resident memory should approach its committed heap fired on ten healthy
cells. `-Xms` commits address space; it does not pre-touch it, and cgroup
`anon` counts only resident pages. The rule was wrong, not the data.

**Anchor substring tests to what they mean.** A pre-release check written as
`"rc" in version` matches `a-rc-adedb`. The identical bug in `build_images.sh`
refused every correct release build. Both now test a version token against an
anchored pattern, and both directions are covered by the injection test below.

## Verifying the checks still work

Rules rot silently: a check that stops firing looks exactly like a clean
campaign. Each rule has a control row and an injected-defect row, and every
one must go red on the defect and stay quiet on the control. Run the injection
harness after touching `check_row`; it currently covers close/reopen limits,
version provenance, cpuset, percentile ordering, phase accounting, recall
range, the memory cap, and cold/warm inversion.

## Acknowledged findings

`ACK` in the watcher suppresses a finding from SUSPECT while keeping it in the
printed output. To add one it must name the task that owns it and be something
the current run cannot change. "Annoying" is not a reason: a monitor that
reports a known, unfixable finding every two minutes is one people stop
reading, and the next real finding arrives into that silence.

`ACK` is currently **empty**. Its one entry covered `observe_server` matching
only `-Xmx`, which is fixed and on the bench host, so a row with no observed
server heap is once again a real finding.
