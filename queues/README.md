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

## The rule these encode

Stop a queue with `kill -- -PGID`, and then VERIFY by what the host shows:

    docker ps -q | wc -l      # -q has no header; `docker ps | wc -l` counts one
    pgrep -f runner.py        # pgrep does not match itself, unlike ps|grep over ssh

Killing the script alone leaves the runner alive and reparented, which has
blocked a following campaign three separate times. `icde_long.sh`'s idle guard
now bounds its wait and sweeps containers that have no live runner behind them,
because a guard that waits forever on garbage is indistinguishable from one
that is working.
