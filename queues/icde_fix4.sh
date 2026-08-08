#!/bin/bash
# Re-measure Elasticsearch at every sparse tier, now that its heap scales.
#
# WHY. elasticsearch_sparse was the only served backend whose heap was not
# templated on {heap}: runner.py hardcoded "-Xms2g -Xmx4g", so ES ran a 4g heap
# at tiny, small AND medium while its comparators scaled 4g -> 8g -> 16g. At
# medium that is a quarter of the memory. The rows still recorded heap=8g and
# heap=16g, because a row stamps what was REQUESTED, so the artifact asserted a
# heap the engine never had.
#
# The direction matters: under-resourcing a comparator flatters ArcadeDB, in a
# paper ArcadeDB's own maintainers wrote, in its centerpiece table. This is not
# a rounding issue to disclose in a footnote.
#
# ALL THREE TIERS, INCLUDING TINY. Tiny's ES cells passed the guard because the
# observed 4g happened to equal the requested 4g, but they ran -Xms2g -Xmx4g:
# unpinned, while every other JVM in this lane commits its heap up front
# (l3_sparse.py:82). An arm that grows its heap under load is not running the
# same experiment, so tiny is re-measured too rather than kept on a coincidence.
#
# WHAT MAY GO WRONG, stated up front so a failure is read correctly. Elastic
# recommends a heap of at most half of container RAM, leaving the rest for
# Lucene's mmap'd file cache. At medium the matched heap is 16g inside a 24g
# server share, which is 67%. Matching the operating point is the F3 invariant
# and is what every other engine here gets, so that is what ES gets; but if it
# OOM-kills or degrades, that is a REAL consequence of an equalised envelope
# and belongs in the paper, not a harness bug to paper over. The acceptance
# block below distinguishes the two.
set -u
EXP=$HOME/repos/humemai/arcadedb-embedded-python/benchmarks/experiments
OUT=$HOME/qfix4; mkdir -p "$OUT"
LOG=$OUT/queue.log
ST=$HOME/STATUS.txt

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit 1; }

log "qfix4 started, pid $$"
cd "$EXP" || die "no experiments dir"

# ---- wait for qfix3 (which itself waits for qfix2), with a hard deadline ----
DEADLINE=$(( $(date +%s) + 48*3600 ))
while ! grep -q "QFIX3-COMPLETE" "$HOME/qfix3/queue.log" 2>/dev/null; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "qfix3 never completed in 48h"
  sleep 120
done
log "qfix3 complete"
while [ "$(docker ps -q | wc -l)" -gt 0 ]; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && die "containers still running at deadline"
  sleep 30
done
log "host idle"

# The fix must actually be in the file this host will run. A queue that assumes
# its own patch landed is how the corpus bug survived a whole campaign.
grep -q 'ES_JAVA_OPTS=-Xms{heap} -Xmx{heap}' runner.py \
  || die "runner.py on this host does not have the templated ES heap"
log "gate: runner.py has the templated ES heap"

export BENCH_DATA=$HOME/bench-data
export BENCH_SPARSE_SOURCE=bigann
export BENCH_SPARSE_DATA=/data/bigann
[ -d "$BENCH_DATA/bigann" ] || die "no bigann corpus"
log "gate: bigann corpus present, BENCH_SPARSE_SOURCE=bigann"

date -Is > "$OUT/started_at"

stage() {  # scale, timeout_s
  local scale=$1 tmo=$2
  while [ "$(docker ps -q | wc -l)" -gt 0 ]; do sleep 30; done
  log "STAGE es_$scale START"
  local t0=$(date +%s)
  timeout "$tmo" python3 -u runner.py --lanes l3s --scale "$scale" --tier paper \
    --backends elasticsearch_sparse --reps 5 >"$OUT/es_$scale.log" 2>&1
  local rc=$?
  log "STAGE es_$scale $( [ $rc -eq 0 ] && echo OK || echo "FAILED rc=$rc" ) after $(( ($(date +%s)-t0)/60 ))min"
  [ $rc -ne 0 ] && tail -12 "$OUT/es_$scale.log" >>"$LOG"
  docker ps --format '{{.Names}}' | grep -E '^(cli|srv)-' | while read n; do docker rm -f "$n" >/dev/null 2>&1; done
}

stage tiny   7200
stage small  21600
stage medium 86400

log "=== acceptance ==="
python3 - <<'PY' | tee -a "$LOG"
import json, os, collections
EXP = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments")
cut = open(os.path.expanduser("~/qfix4/started_at")).read().strip()
rows = []
for l in open(os.path.join(EXP, "results", "runs.jsonl")):
    l = l.strip()
    if not l:
        continue
    try:
        r = json.loads(l)
    except Exception:
        continue
    if (r.get("backend") == "elasticsearch_sparse"
            and str(r.get("ts_utc", "")) >= cut):
        rows.append(r)

want_heap = {"tiny": "4g", "small": "8g", "medium": "16g"}
by = collections.defaultdict(list)
for r in rows:
    by[r.get("scale")].append(r)

for sc in ("tiny", "small", "medium"):
    rs = by.get(sc, [])
    ok = [r for r in rs if r.get("rc") == 0]
    rec = [r for r in ok if r.get("recall_at_10") is not None]
    heaps = sorted({str(r.get("heap")) for r in ok})
    srv = sorted({str(v) for r in ok for k, v in r.items()
                  if k.startswith("server_") and "heap" in k})
    print("  es/%-7s %d run, %d ok, %d with recall; heap=%s observed=%s"
          % (sc, len(rs), len(ok), len(rec), heaps, srv or ["(not recorded)"]))
    if not ok:
        # Distinguish the two failure modes named in the header.
        errs = collections.Counter(str(r.get("error"))[:70] for r in rs)
        for e, n in errs.most_common(3):
            print("      x%d  %s" % (n, e))
        print("      -> ZERO usable cells at %s. If the error is OOM/137 this is"
              " the equalised-envelope consequence and belongs in the paper;" % sc)
        print("         if it is a heap mismatch again, the fix did not take.")
    elif len(rec) < 5:
        print("      -> only %d/5 usable; T4's ES cell at %s stays short" % (len(rec), sc))
    elif heaps != [want_heap[sc]]:
        print("      -> heap is %s, expected %s" % (heaps, want_heap[sc]))
    else:
        print("      -> matched at %s, 5/5 with recall" % want_heap[sc])
PY

log "QFIX4-COMPLETE"
{ echo "qfix4 (Elasticsearch heap parity) finished $(date -Is)"; echo; tail -30 "$LOG"; } > "$ST"
