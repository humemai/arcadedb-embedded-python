# Campaign monitoring

Two pieces, both read-only.

`campaign_watch.py` answers "are the numbers genuinely fine", not "is it still
running". Run it on the bench host at any time. It prints a per-cell table,
then two sections: ACKNOWLEDGED for findings already understood and tracked,
and SUSPECT for anything else.

`campaign_monitor.sh` polls the bench host every two minutes and emits one
line per event: lane transitions, failed cells, SUSPECT rows, the queue going
empty without ALL-DONE, and host disk pressure. Silence means healthy, which
is only true because the queue-death and failure cases are covered explicitly.

## Why each check exists

Every rule is a defect this project shipped or nearly shipped, so none of them
is hypothetical:

- a memory column that was 88% the benchmark's own Python driver
- a memory metric capturing 26% of one engine's peak and 98% of another's
- `SizeRw` reading 20 KB while 1017 MiB sat in a declared volume
- a disk reading taken before writeback and compaction settled
- a lane that timed one pass and never said whether it was cold or warm,
  hiding a 9.9x second-pass gain on the comparator we beat
- 30 OOM-killed cells that exited 0 with empty error strings
- a served JVM comparator whose heap nobody ever observed

## Two rules learned building it

**Scope every check to the current run.** The first version grepped the whole
of `q87.log`, which is appended across launches, and reported a failure from
an aborted smoke hours earlier on its very first poll. Same trap as reading an
append-only STATUS file as current state.

**Check the premise before trusting the rule.** A rule asserting that a JVM
arm's resident memory should approach its committed heap fired on ten healthy
cells. `-Xms` commits address space; it does not pre-touch it, and cgroup
`anon` counts only resident pages. The rule was wrong, not the data.

## Acknowledged findings

`ACK` in the watcher suppresses a finding from SUSPECT while keeping it in the
printed output. To add one it must name the task that owns it and be something
the current run cannot change. "Annoying" is not a reason: a monitor that
reports a known, unfixable finding every two minutes is one people stop
reading, and the next real finding arrives into that silence.
