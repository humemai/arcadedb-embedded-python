#!/bin/bash
# Emit ONE line of facts about the bench host. Logic lives in the caller.
#
# Fields: rows fail containers script complete load memfree
#   rows       published rows for the active scale since the cutoff
#   fail       how many of those have rc != 0
#   containers running containers (docker ps -q, no header to miscount)
#   script     1 if a queue script process is alive, else 0
#   complete   1 if the queue log carries its COMPLETE marker
#
# WHY THESE FIVE. Every wasted hour on this host so far was one of them
# disagreeing with another, and none was visible from any single number:
#   containers>0 with script=0   an orphaned runner nobody owns (q19)
#   script=1 with containers=0   a queue stuck in its host-idle guard (q21)
#   rows climbing with fail>0    cells failing fast (q21's path bug)
#   nothing moving at all        a genuinely hung cell
set -u
Q=${1:-q22}
SCALE=${2:-tpch10}
CUT=${3:-2026-08-06T10}
R=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results/runs.jsonl

read -r rows fail <<<"$(python3 -c "
import json,sys
n=f=0
try:
    for l in open('$R'):
        l=l.strip()
        if not l: continue
        try: r=json.loads(l)
        except Exception: continue
        if r.get('scale')=='$SCALE' and str(r.get('ts_utc',''))>='$CUT':
            n+=1
            if r.get('rc')!=0: f+=1
except Exception: pass
print(n,f)
" 2>/dev/null || echo "0 0")"

# docker ps -q has no header line, so this cannot be off by one the way
# 'docker ps | wc -l' was when it reported 1 for an empty host.
containers=$(docker ps -q 2>/dev/null | wc -l)

# pgrep does not match its own command line, unlike ps|grep over ssh, which
# is what made an earlier check unreadable.
script=0; pgrep -f "icde_${Q}\.sh" >/dev/null 2>&1 && script=1
complete=0; grep -q "COMPLETE" "$HOME/$Q/queue.log" 2>/dev/null && complete=1
load=$(awk '{printf "%.2f",$1}' /proc/loadavg)
memfree=$(free -g | awk '/^Mem:/{print $7}')

echo "$rows $fail $containers $script $complete $load $memfree"
