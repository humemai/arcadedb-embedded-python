#!/usr/bin/env bash
# Stream campaign events from mini. Each echoed line becomes a notification.
#
# COVERAGE IS THE POINT. A monitor that only greps for progress markers is
# silent through a crash, and silence looks exactly like "still running". So
# this emits on: lane transitions, any failed cell, any row the sanity check
# distrusts, the queue going empty without ALL-DONE, and the host running out
# of disk or RAM. If the campaign died right now, this would say so.
export SSH_AUTH_SOCK=/run/user/1000/gcr/.ssh
S=~/STATUS.txt

seen_status=""      # last STATUS line already reported
seen_fail=""        # last failure line already reported
dead_reported=0
tick=0

while true; do
  tick=$((tick + 1))

  snap=$(ssh -o ConnectTimeout=20 -o BatchMode=yes mini '
    echo "###JOBS"
    pgrep -cf "q87_full_instrumented" 2>/dev/null || echo 0
    pgrep -cf "q88_sparse_medium" 2>/dev/null || echo 0
    echo "###STATUS"
    grep -aE "q8[678] " ~/STATUS.txt 2>/dev/null | tail -3
    echo "###FAIL"
    # ONLY THE CURRENT RUNNER INVOCATION. q87.log is appended across every
    # launch, so a bare grep resurfaces this morning\x27s aborted smoke forever
    # and the monitor cries wolf on its first poll. Same append-only-history
    # trap that made the q87 wait loop read a stale q86 ABORT. Cut at the last
    # "cell-runs (tier=" banner, which every runner invocation prints once.
    awk "/cell-runs \(tier=/{buf=\"\"} {buf=buf \$0 ORS} END{printf \"%s\", buf}" ~/q87.log 2>/dev/null \
      | grep -aE "FAILED|ABORT|OOM|Traceback|server_not_ready|client_failed" | tail -2
    echo "###LANE"
    awk "/cell-runs \(tier=/{n=0;h=\$0} /^  \[/{n++} END{print h \" :: done \" n}" ~/q87.log 2>/dev/null
    echo "###HOST"
    df -P / | awk "NR==2{print \$5}"
    free -g | awk "/^Mem:/{print \$3 \"/\" \$2}"
    echo "###WATCH"
    python3 ~/campaign_watch.py 40 2>/dev/null | sed -n "/SUSPECT/,\$p" | head -6
  ' 2>/dev/null)

  if [ -z "$snap" ]; then
    echo "MONITOR: cannot reach mini (ssh failed); will retry"
    sleep 180; continue
  fi

  sec() { printf '%s\n' "$snap" | sed -n "/^###$1\$/,/^###/p" | sed '1d;$d'; }

  q87=$(sec JOBS | sed -n 1p); q88=$(sec JOBS | sed -n 2p)
  status_last=$(sec STATUS | tail -1)
  fail_last=$(sec FAIL | tail -1)
  lane=$(sec LANE)
  suspect=$(sec WATCH)

  # 1. lane transitions and job markers, once each
  if [ -n "$status_last" ] && [ "$status_last" != "$seen_status" ]; then
    echo "CAMPAIGN: $status_last"
    seen_status="$status_last"
  fi

  # 2. any failed cell, once each
  if [ -n "$fail_last" ] && [ "$fail_last" != "$seen_fail" ]; then
    echo "CAMPAIGN FAILURE: $fail_last"
    seen_fail="$fail_last"
  fi

  # 3. rows the sanity check distrusts
  if [ -n "$suspect" ]; then
    echo "CAMPAIGN SUSPECT ROWS: $(printf '%s' "$suspect" | tr '\n' ' | ')"
  fi

  # 4. the queue went empty without finishing. THE failure mode a
  #    progress-only filter would sleep through.
  if [ "${q87:-0}" = "0" ] && [ "${q88:-0}" = "0" ] && [ "$dead_reported" = "0" ]; then
    case "$status_last" in
      *ALL-DONE*) echo "CAMPAIGN: queue empty and last marker is ALL-DONE, finished cleanly" ;;
      *)          echo "CAMPAIGN DIED: no q87/q88 process and last marker is: $status_last" ;;
    esac
    dead_reported=1
  fi
  [ "${q87:-0}" != "0" ] && dead_reported=0

  # 5. host limits that would kill a long run
  hostline=$(sec HOST)
  diskpct=$(printf '%s\n' "$hostline" | sed -n 1p | tr -d '%')
  if [ -n "$diskpct" ] && [ "$diskpct" -ge 90 ] 2>/dev/null; then
    echo "CAMPAIGN HOST: mini root filesystem ${diskpct}% full"
  fi

  # 6. a slow heartbeat so a long quiet lane is distinguishable from a
  #    wedged monitor. Every 30 polls at 120s is once an hour.
  if [ $((tick % 30)) -eq 0 ]; then
    echo "CAMPAIGN OK: $lane | q87=$q87 q88=$q88 | mem $(printf '%s\n' "$hostline" | sed -n 2p)"
  fi

  sleep 120
done
