#!/bin/bash
# #5577: why does the silent phase burn 2x the CPU for 1.00x the throughput?
#
# Known: one DEEP-10M build has a logged insertion phase that scales 1.92x on
# 2x threads, and a silent phase that scales 1.00x while CPU sampling shows a
# single tight cluster at 1200%. The two phases have identical -e cpu frame
# composition (squareDistance 45/46%, LongAdder 28/29%, heaps 7.6/6.5%).
#
# -e cpu cannot answer this. Saturated is not the same as productive: twelve
# threads each half-idle and six busy while six spin on a monitor both read as
# high CPU, and a spin burns cycles without progress. Two instruments can tell
# them apart and neither has been pointed at this phase:
#
#   -e lock  attributes contended monitor/park time to the object contended
#   -t       splits the profile per thread, so imbalance is visible
#
# Falsifiable either way. If lock time is negligible and the per-thread split
# is flat, contention is NOT the mechanism and the answer is elsewhere
# (memory bandwidth is the next candidate, and would need perf counters).
set -u
PROF=$HOME/profiling/async-profiler-4.0-linux-x64
OUT=$HOME/profiling/flame
exec >> "$HOME/profiling/queue55.log" 2>&1
say() { echo "[$(date -u +%H:%M:%S)] $*"; }
die() { say "ABORT: $*"; exit 1; }
guard() { while [ "$(docker ps -q | wc -l)" -gt 0 ]; do sleep 30; done; }

guard
cd ~/repos/humemai/arcadedb-icde/paper-icde/experiments || die "no experiments dir"
[ -d "$PROF" ] || die "async-profiler not staged at $PROF"

VER=$(docker run --rm icde-bench:arcadedb python -m pip show arcadedb-embedded 2>/dev/null | awk '/^Version:/{print $2}')
[ -n "${VER:-}" ] || die "no engine version"
say "engine $VER"

# Contract check before a 45-minute build: the driver must still exist and the
# profiler must accept BOTH events. queue48 lost an arm to an event name that
# does not exist ("-e wall"); check the spellings against this binary, not
# against memory.
[ -f l3d_dense.py ] || die "l3d_dense.py missing"
# --out is required=True; omitting it makes argparse kill the run instantly,
# which is how queue39 lost 10/10 cells to a flag that did not exist.
python3 - <<'PYC' || die "l3d_dense CLI contract changed"
import re
s = open("l3d_dense.py").read()
need = {"--backend", "--scale", "--out"}
have = set(re.findall(r'add_argument\("(--[a-z0-9_]+)"', s))
missing = need - have
raise SystemExit(f"missing {missing}" if missing else 0)
PYC
say "contract ok: --backend --scale --out present"
"$PROF/bin/asprof" -h 2>&1 | grep -qiE '\block\b' || say "WARN: 'lock' not in asprof help; will verify at arm time"

N=lock55
docker rm -f $N >/dev/null 2>&1
docker run -d --name $N --cpuset-cpus 0-11 --memory 36g --memory-swap 36g \
  -v "$PWD:/work" -w /work -v "$HOME/icde-data:/data:ro" \
  -v "$PROF:/prof:ro" -v "$OUT:/pout" \
  -e BENCH_DENSE_DATA=/data/dense -e BENCH_DENSE_M=32 -e ARCADEDB_HEAP=24g \
  icde-bench:arcadedb python -u l3d_dense.py --backend arcadedb_dense_embedded \
  --scale deep10m --out /pout/5577_build.json >/dev/null \
  || die "build container failed to start"
say "build started"

# Reach the silent phase by TIME, not by log output.
#
# l3d_dense prints exactly one line, the final RESULT, so there are no progress
# lines to watch. My first attempt watched for output to stop without ever
# requiring it to start, and duly announced "silent phase detected" 100 s in,
# with 2 lines printed, while the build was still mmapping 3.8 GB of
# descriptors. It then armed the profiler on the dataset load.
#
# The phase fractions are already measured for this exact build (issue #5577):
# insertion 38.6% of build, silent 53.1%. At the dev23 build time of ~2693 s
# that puts insertion at ~1040 s and the silent phase at ~1040-2470 s. Arming
# at 1200 s sits well inside it with margin at both ends.
ARM_AT=${ARM_AT:-1200}
say "waiting ${ARM_AT}s to land inside the silent phase (insertion ends ~1040s)"
found=0
for i in $(seq 1 $((ARM_AT / 10))); do
  docker ps --format '{{.Names}}' | grep -q "^${N}$" || { say "build exited after ~$((i*10))s, before the silent phase"; break; }
  sleep 10
done
if docker ps --format '{{.Names}}' | grep -q "^${N}$"; then
  cpu=$(docker stats --no-stream --format '{{.CPUPerc}}' $N 2>/dev/null | tr -d '%')
  say "at ${ARM_AT}s the build is alive at ${cpu:-?}% CPU; arming"
  # A silent phase that is not burning CPU would mean the build already finished
  # its work, so record the reading rather than assume it.
  found=1
fi

arm() {  # $1 event-args, $2 label, $3 seconds
  docker exec $N /prof/bin/asprof start $1 1 >/dev/null 2>&1 || { say "$2: asprof start rejected ($1)"; return 1; }
  say "$2: armed for $3s"
  sleep "$3"
  docker exec $N /prof/bin/asprof stop -o collapsed \
    -f "/pout/5577_${2}_${VER}.collapsed" 1 >/dev/null 2>&1 \
    && say "$2: written" || say "$2: stop FAILED"
}

arm "-e lock" lock 300
arm "-e cpu -t" cputhread 300

docker rm -f $N >/dev/null 2>&1

say "=== analysis ==="
python3 - <<'PY'
import glob, os, re
from collections import Counter

def load(p):
    tot = 0; rows = []
    for line in open(p):
        line = line.rstrip("\n")
        if " " not in line: continue
        st, _, n = line.rpartition(" ")
        try: n = int(n)
        except ValueError: continue
        tot += n; rows.append((st, n))
    return tot, rows

for f in sorted(glob.glob(os.path.expanduser("~/profiling/flame/5577_*.collapsed"))):
    tot, rows = load(f)
    name = os.path.basename(f)
    print(f"\n== {name}  total {tot:,}")
    if not tot:
        print("   EMPTY: the event produced nothing. That is itself an answer for -e lock.")
        continue
    if "lock" in name:
        c = Counter()
        for st, n in rows:
            fr = [x for x in st.split(";") if x]
            c[fr[-1].split("/")[-1] if fr else "?"] += n
        print("   contended sites (leaf):")
        for k, v in c.most_common(10):
            print(f"     {100.0*v/tot:6.2f}%  {k[:70]}")
    else:
        # -t prefixes each stack with the thread name
        th = Counter()
        for st, n in rows:
            th[st.split(";")[0][:44]] += n
        print(f"   {len(th)} threads; share of samples per thread:")
        for k, v in th.most_common(16):
            print(f"     {100.0*v/tot:6.2f}%  {k}")
        vals = sorted(th.values(), reverse=True)
        if len(vals) > 1:
            print(f"   top/median thread ratio: {vals[0]/vals[len(vals)//2]:.2f}x "
                  f"(1.0 = perfectly balanced)")
PY
say "QUEUE55-DONE"
