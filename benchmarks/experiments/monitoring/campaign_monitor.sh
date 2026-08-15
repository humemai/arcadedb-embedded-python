#!/usr/bin/env bash
# Stream campaign events from the bench host. Each echoed line is a notification.
#
# Usage:  campaign_monitor.sh <job-pattern> [start-marker]
#   job-pattern   pgrep -f pattern matching the queue scripts, e.g. 'q9[0-9]_'
#   start-marker  STATUS.txt text identifying the line where this campaign
#                 STARTED, e.g. 'q92 lifecycle scale-up START'. Everything is
#                 scoped to the last line matching it.
#
# THE MARKER MUST NAME THE START LINE, not the job. Passing a job prefix like
# 'q92 ' matches every line the job ever wrote, so the last match is its
# ALL-DONE and the window collapses to nothing: the campaign's own log falls
# outside its own scope and failures inside it go unreported.
#
# COVERAGE IS THE POINT. A monitor that only greps for progress markers is
# silent through a crash, and silence looks exactly like "still running". So
# this emits on: lane transitions, any failed cell, any row the sanity check
# distrusts, the queue going empty without ALL-DONE, and the host running out
# of disk, RAM or patience with swap. If the campaign died right now, this
# would say so.
#
# JOB NAMES ARE AN ARGUMENT, NOT A CONSTANT. The previous version hardcoded
# q87/q88/q89 and went quietly blind the moment the campaign was renumbered:
# it reported "queue empty, finished cleanly" for jobs it could no longer see.
set -u
export SSH_AUTH_SOCK=${SSH_AUTH_SOCK:-/run/user/1000/gcr/.ssh}
HOST=${BENCH_HOST_SSH:-mini}
PAT=${1:?usage: campaign_monitor.sh <job-pattern> [marker]}
MARKER=${2:-$PAT}
INTERVAL=${MONITOR_INTERVAL:-120}
# WHERE THE CHECKER LIVES ON THE BENCH HOST. Normally the repo copy. The
# override exists because the checker must be improvable DURING a campaign
# while the lane scripts must not: syncing the repo mid-run is what split one
# lane's rows across two schemas. Point this at a scp'd copy under /tmp to fix
# a noisy or broken rule without touching the checkout the campaign is running.
WATCH=${MONITOR_WATCH_PATH:-~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/monitoring/campaign_watch.py}

# RUN ON THE BENCH HOST ITSELF, OR POLL IT OVER SSH.
#
# BENCH_HOST_SSH=local runs the snapshot with a plain shell instead of ssh, so
# the monitor can live on the bench host under setsid/nohup and outlive any
# workstation session. That is the difference between "monitoring" and
# "monitoring until my laptop hiccups": four separate laptop-side monitors died
# mid-campaign -- two to a kill pattern that matched their own launcher, one to
# a deliberate restart, one to a session reap -- and each time a live campaign
# ran unwatched until somebody noticed.
#
# Over ssh it still works unchanged, which is right for watching from a
# workstation while you are there.
if [ "$HOST" = "local" ]; then
  RUNNER="bash -c"
else
  RUNNER="ssh -o ConnectTimeout=20 -o BatchMode=yes $HOST"
fi

seen_status=""
seen_fail=""
seen_suspect=""
dead_reported=0
tick=0

while true; do
  tick=$((tick + 1))

  snap=$($RUNNER "
    echo '###JOBS'
    # NO '|| echo 0'. pgrep -c already prints 0 when nothing matches, and it
    # exits 1 while doing so, so the fallback appended a SECOND zero and every
    # field below it read one line off: the container count was silently the
    # spurious zero, and the orphan check could never fire.
    pgrep -cf '$PAT' 2>/dev/null
    docker ps -q --filter label=dbbench=1 | wc -l
    echo '###STATUS'
    grep -aE '$MARKER' ~/STATUS.txt 2>/dev/null | tail -3
    echo '###FAIL'
    # TWO SCOPES, BOTH NECESSARY, BOTH LEARNED FROM A FALSE ALARM.
    #
    # Across FILES: only logs written since this campaign's marker. The first
    # version globbed every q9*.log and reported a TypeError from q90 -- a
    # different job, already diagnosed and fixed hours earlier -- as though it
    # were happening now.
    #
    # Within a FILE: only the current runner invocation. Job logs are appended
    # across launches, so a bare grep resurfaces this morning's aborted smoke
    # forever. Cut at the last 'cell-runs (tier=' banner, which every runner
    # invocation prints once. (Bespoke probes print no banner, which is why
    # the file-level scope has to carry them.)
    since=\$(grep -aE '$MARKER' ~/STATUS.txt 2>/dev/null | tail -1 | sed -n 's/^\[\([^]]*\)\].*/\1/p')
    for f in \$(find ~ -maxdepth 1 -name 'q*.log' \${since:+-newermt \"\$since\"} 2>/dev/null); do
      awk '/cell-runs \(tier=/{buf=\"\"} {buf=buf \$0 ORS} END{printf \"%s\", buf}' \"\$f\" \
        | grep -aE 'FAILED|ABORT|OOM|Traceback|server_not_ready|client_failed' | tail -2
    done
    echo '###HOST'
    df -P / | awk 'NR==2{print \$5}'
    free -g | awk '/^Mem:/{print \$3 \"/\" \$2}'
    awk '/^pswpin|^pswpout/{printf \"%s \", \$2}' /proc/vmstat
    echo
    echo '###WATCH'
    python3 $WATCH \
      --since-marker '$MARKER' 2>&1 | sed -n '/SUSPECT/,\$p' | head -8
  " 2>/dev/null)

  if [ -z "$snap" ]; then
    echo "MONITOR: cannot reach $HOST (ssh failed); will retry"
    sleep 180; continue
  fi

  sec() { printf '%s\n' "$snap" | sed -n "/^###$1\$/,/^###/p" | sed '1d;$d'; }

  jobs=$(sec JOBS | sed -n 1p)
  containers=$(sec JOBS | sed -n 2p)
  # THE LAST MARKER, not any of them. STATUS.txt is append-only, so a job that
  # was fixed and relaunched has written its marker twice and the earlier one
  # is stale. Reading any-match once made a wait loop act on a three-hour-old
  # ABORT from a run that had since been fixed.
  status_last=$(sec STATUS | tail -1)
  fail_last=$(sec FAIL | tail -1)
  suspect=$(sec WATCH)
  hostline=$(sec HOST)

  if [ -n "$status_last" ] && [ "$status_last" != "$seen_status" ]; then
    echo "CAMPAIGN: $status_last"
    seen_status="$status_last"
  fi

  if [ -n "$fail_last" ] && [ "$fail_last" != "$seen_fail" ]; then
    echo "CAMPAIGN FAILURE: $fail_last"
    seen_fail="$fail_last"
  fi

  # ONLY WHEN THE SET CHANGES. A finding that is real but not yet actionable --
  # Milvus never settling its disk, say -- is still true on every poll, and
  # re-emitting it every two minutes buries the next genuinely new one. That is
  # the same reasoning as the ACK list in the watcher, applied to the stream:
  # 45 KB of one repeated line is how this first showed up.
  if [ -n "$suspect" ] && [ "$suspect" != "$seen_suspect" ]; then
    echo "CAMPAIGN SUSPECT ROWS: $(printf '%s' "$suspect" | tr '\n' ' | ')"
    seen_suspect="$suspect"
  fi

  # The queue went empty without finishing. THE failure mode a progress-only
  # filter would sleep through.
  if [ "${jobs:-0}" = "0" ] && [ "$dead_reported" = "0" ]; then
    case "$status_last" in
      *ALL-DONE*) echo "CAMPAIGN: queue empty and last marker is ALL-DONE, finished cleanly" ;;
      *)          echo "CAMPAIGN DIED: no '$PAT' process and last marker is: $status_last" ;;
    esac
    dead_reported=1
  fi
  [ "${jobs:-0}" != "0" ] && dead_reported=0

  # A container with no job behind it is an orphan holding a cpuset and a
  # memory cap against whatever runs next.
  if [ "${jobs:-0}" = "0" ] && [ "${containers:-0}" != "0" ]; then
    echo "CAMPAIGN ORPHAN: $containers dbbench container(s) with no queue process"
  fi

  diskpct=$(printf '%s\n' "$hostline" | sed -n 1p | tr -d '%')
  if [ -n "$diskpct" ] && [ "$diskpct" -ge 90 ] 2>/dev/null; then
    echo "CAMPAIGN HOST: $HOST root filesystem ${diskpct}% full"
  fi

  # SWAP-IN IS NOT A HOST CURIOSITY, IT INVALIDATES THE CELL. Under reclaim a
  # peak-anon column stops being a demand and becomes a record of who got
  # squeezed, and the latency beside it is a different measurement.
  swap=$(printf '%s\n' "$hostline" | sed -n 3p)
  pswpin=${swap%% *}
  if [ -n "${pswpin:-}" ] && [ "${last_pswpin:-}" != "" ] && [ "$pswpin" -gt "$last_pswpin" ] 2>/dev/null; then
    echo "CAMPAIGN SWAP: host swapped IN $((pswpin - last_pswpin)) pages since last poll; memory numbers in this window are suspect"
  fi
  last_pswpin=${pswpin:-}

  # A slow heartbeat, so a long quiet lane is distinguishable from a wedged
  # monitor. Every 30 polls at 120s is once an hour.
  if [ $((tick % 30)) -eq 0 ]; then
    echo "CAMPAIGN OK: jobs=$jobs containers=$containers | mem $(printf '%s\n' "$hostline" | sed -n 2p) | $status_last"
  fi

  sleep "$INTERVAL"
done
