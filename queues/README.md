# Bench-host queue scripts

The scripts that drive unattended campaigns on the bench host. They live here
because until now they lived ONLY on mini, in `~/*.sh`, which meant the exact
commands behind published numbers were unrecoverable if that host were lost --
the same provenance gap the artifacts themselves had. Two probes already have
no surviving launch command for precisely this reason.

`icde_long.sh` runs an independent re-measure of every published tier on one
released engine at N=5, then TSBS at 10x the paper's corpus. It writes
`~/STATUS.txt` every ten minutes, so a check from anywhere is one command:

    ssh mini 'cat ~/STATUS.txt'

`mini_probe.sh` emits one line of host facts (rows, failures, containers,
script alive, complete) for a monitor to compare. The five fields exist because
every wasted hour on this host has been two of them disagreeing: containers
running with no script is an orphan, a live script with no containers is a
stuck guard, rows climbing with failures is a fast-fail.

## The repair chain, 2026-08-08

`icde_long.sh` exported only `BENCH_DATA`. The campaign that produced good
data exported six variables, each asserted. The graph lane crashed outright
(80 cells, loudly); the sparse lane succeeded on the WRONG CORPUS (94 rows,
quietly). These four scripts repair that, each waiting on the previous one's
completion marker with a hard deadline:

- `icde_fix.sh` (qfix2) — re-runs l2 at both scales and l3s at all three, with
  the full environment, a **container-side preflight** that asks the container
  what it can see before anything runs, and a per-stage check of the corpus it
  actually measured rather than its exit code.
- `icde_fix3.sh` (qfix3) — re-measures the time-series comparators, the last
  feed whose rows recorded no cpuset, heap, cap or version. Its QuestDB probe
  connects from an image we ship instead of shelling into the vendor's for
  `nc`, which is why the previous attempt failed 5/5 as `NEVER-READY` while
  the campaign still logged a tidy DONE.
- `icde_fix4.sh` (qfix4) — re-runs Elasticsearch at every tier now that its
  heap scales with the tier instead of being hardcoded to 4g. It gates on the
  fix being present in `runner.py` on that host, and its acceptance separates
  "OOM under the equalised envelope" (a paper finding) from "the heap still
  mismatches" (the fix did not take).
- `icde_fix5.sh` (qfix5) — five INDEPENDENT builds per dense arm, because
  `dense_multipass_driver.py` does one build then N query passes, so five
  records share one `build_s` and one recall. Every arm's invocation is lifted
  verbatim from the script that produced its current artifact; the caps differ
  per arm (36g embedded, 9g client + 27g server) and reconstructing them from
  memory is how the corpus bug happened.

They run build-major and skip work already on disk, so an interruption resumes
instead of restarting, and a partial run leaves every arm equally sampled
rather than the first few complete and the rest empty.

## The rule these encode

Stop a queue with `kill -- -PGID`, and then VERIFY by what the host shows:

    docker ps -q | wc -l      # -q has no header; `docker ps | wc -l` counts one
    pgrep -f runner.py        # pgrep does not match itself, unlike ps|grep over ssh

Killing the script alone leaves the runner alive and reparented, which has
blocked a following campaign three separate times. `icde_long.sh`'s idle guard
now bounds its wait and sweeps containers that have no live runner behind them,
because a guard that waits forever on garbage is indistinguishable from one
that is working.
