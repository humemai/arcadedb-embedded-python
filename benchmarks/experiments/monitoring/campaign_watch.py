#!/usr/bin/env python3
"""Are the campaign's numbers genuinely fine? Read-only, run repeatedly.

Not a liveness check. Every rule here corresponds to a class of weird number
this project has actually shipped or nearly shipped:

  memory   a column that was 88% our own Python driver; a metric that captured
           26% of one engine's peak and 98% of another's; 20 rows on a heap
           nobody observed
  disk     SizeRw reading 20 KB while 1 GiB sat in a volume; a reading taken
           before writeback and compaction settled
  cold/warm a lane that timed one pass and never said which, hiding a 9.9x
           second-pass gain on the comparator we beat
  silent   30 OOM-killed cells that exited 0 with empty error strings
  drift    a cell whose reps disagree, averaged into a tidy median

Prints a compact table, then a SUSPECT section. The monitor forwards only the
SUSPECT section, so a check that fires must be worth waking someone for.
"""
import json, os, sys, statistics as st, collections

RES = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/"
                         "benchmarks/experiments/results")
rows = [json.loads(l) for l in open(os.path.join(RES, "runs.jsonl")) if l.strip()]

# THIS campaign only. Cut at the first row carrying the new envelope stamp;
# earlier rows legitimately differ and would fire every rule at once.
_inst = [r for r in rows if r.get("peak_owned_mib_sum") is not None]
# Cut at the LAST campaign start, read from STATUS.txt. Cutting on the first
# "full+client" row was wrong: the envelope landed one restart before the heap
# scoping did, so rows from the intermediate run passed the cut and fired the
# non-JVM-heap rule for a defect that was already fixed. A monitor that reports
# a fixed defect is a monitor people learn to ignore.
_cut = None
try:
    with open(os.path.expanduser("~/STATUS.txt"), errors="ignore") as fh:
        for line in fh:
            if "q87 smoke OK" in line and line.startswith("["):
                _cut = line[1:line.index("]")]
except Exception:
    pass
if _cut is None:
    _cut = next((r.get("ts_utc") for r in _inst if r.get("mem_split") == "full+client"), None)
new = [r for r in _inst if not _cut or (r.get("ts_utc") or "") >= _cut]
if not new:
    print("no rows from the instrumented campaign yet")
    sys.exit(0)

# Previous campaign, for "did this cell move" comparisons.
prev = {}
try:
    import csv
    with open(os.path.join(RES, "runs_paper.csv")) as fh:
        for r in csv.DictReader(fh):
            prev.setdefault((r["lane"], r["scale"], r["backend"], r["workload"]), []).append(r)
except Exception:
    pass

JVM = ("arcadedb", "neo4j", "elasticsearch", "questdb")
VOLUME_ENGINES = ("arcadedb_graph_server", "arcadedb_server", "arcadedb_sparse_server",
                  "arcadedb_dense_server", "neo4j", "postgres")
KEY = lambda r: (r.get("lane"), r.get("scale"), r.get("backend"), r.get("workload"))

def gib(v):
    return None if v is None else v / 1024.0

def num(v):
    return v if isinstance(v, (int, float)) else None


# ACKNOWLEDGED FINDINGS. Real, understood, already tracked, and NOT fixable in
# the rows this campaign is writing. They stay in the printed table so nobody
# forgets them; they are kept out of SUSPECT so the monitor does not re-alert
# every two minutes and drown a genuinely new finding.
#
# The rule for adding one: it must name the task that owns it, and it must be
# something this run cannot change. "Annoying" is not a reason.
ACK = [
    ("no observed server_heap",
     "known: observe_server matched -Xmx only, so Neo4j's "
     "NEO4J_server_memory_heap_max__size was invisible. Fixed in c61e8605 but "
     "deliberately NOT synced mid-campaign, since it adds a recorded field to "
     "a lane that is executing. These rows keep no witness by design and "
     "fairness_check will report them NO-WITNESS when the CSV regenerates."),
]

def _ack_reason(msg):
    for pat, why in ACK:
        if pat in msg:
            return why
    return None

fail = []
cells = collections.defaultdict(list)
for r in new:
    cells[KEY(r)].append(r)

print(f"{'lane':6} {'scale':8} {'backend':28} {'wl':6} {'n':>2} "
      f"{'owned GiB':>9} {'disk MiB':>9} {'set':>4}")
for k in sorted(cells, key=lambda x: tuple(str(i) for i in x)):
    rs = cells[k]
    lane, scale, be, wl = (str(x) for x in k)
    owned = [num(r.get("peak_owned_mib_sum")) for r in rs]
    disks = [num(r.get("disk_mb_sum")) or num(r.get("server_disk_mb"))
             or num(r.get("client_disk_mb")) for r in rs]
    ow = [x for x in owned if x is not None]
    dk = [x for x in disks if x is not None]
    print(f"{lane:6} {scale:8} {be:28} {wl:6} {len(rs):2d} "
          f"{(st.median(ow)/1024 if ow else 0):9.2f} {(st.median(dk) if dk else 0):9.1f} "
          f"{str(rs[-1].get('server_disk_settled'))[:4]:>4}")

    tag = f"{lane}/{scale}/{be}/{wl}"
    isjvm = any(t in be for t in JVM)

    for r in rs:
        # --- the cell ran at all -------------------------------------------
        if r.get("oom_killed"):
            fail.append(f"{tag}: OOM killed")
        if r.get("error"):
            fail.append(f"{tag}: error={r['error']}")
        metrics = {kk: v for kk, v in r.items()
                   if isinstance(v, (int, float))
                   and (kk.endswith("_ms") or kk in ("qps", "oltp_ops_per_s"))}
        if r.get("rc") == 0 and not metrics:
            fail.append(f"{tag}: rc=0 but the row carries no latency metric")

        # --- percentiles must be ordered ------------------------------------
        for base in {kk.rsplit("_p", 1)[0] for kk in r if "_p50_ms" in kk}:
            p50, p95, p99 = (num(r.get(f"{base}_p{p}_ms")) for p in (50, 95, 99))
            if p50 and p95 and p50 > p95 * 1.001:
                fail.append(f"{tag}: {base} p50 {p50} > p95 {p95}")
            if p95 and p99 and p95 > p99 * 1.001:
                fail.append(f"{tag}: {base} p95 {p95} > p99 {p99}")
        for kk, v in metrics.items():
            if v <= 0:
                fail.append(f"{tag}: {kk}={v}")

        # --- memory ----------------------------------------------------------
        ow1 = num(r.get("peak_owned_mib_sum"))
        cap = r.get("server_mem_cap_g") or r.get("mem_cap")
        capg = None
        if isinstance(cap, str) and cap.endswith("g"):
            capg = float(cap[:-1])
        elif isinstance(cap, (int, float)):
            capg = float(cap)
        if ow1 and capg and ow1 / 1024 > capg * 1.05:
            fail.append(f"{tag}: owned {ow1/1024:.1f} GiB exceeds its {capg} GiB cap")
        if ow1 is not None and ow1 < 32:
            fail.append(f"{tag}: owned memory {ow1} MiB, implausibly small for a loaded engine")
        # NO "owned should approach the committed heap" RULE. -Xms commits
        # address space; it does not pre-touch it, and cgroup anon counts only
        # RESIDENT pages. So an arm with -Xms4g legitimately shows 1.5 GiB
        # until the workload dirties more. This rule fired on ten healthy
        # ArcadeDB cells before the premise was checked. It would need
        # -XX:+AlwaysPreTouch to mean what it claimed, and that would change
        # what we measure. Recorded here so it is not re-added.
        # served cell dominated by our own driver
        cli, tot = num(r.get("client_peak_anon_mib")), num(r.get("peak_anon_mib_sum"))
        if num(r.get("server_peak_anon_mib")) is not None and cli and tot and cli / tot > 0.5:
            fail.append(f"{tag}: {100*cli/tot:.0f}% of the memory cell is the driver")

        # --- disk -------------------------------------------------------------
        d = num(r.get("disk_mb_sum")) or num(r.get("server_disk_mb")) or num(r.get("client_disk_mb"))
        if r.get("rc") == 0 and d is not None and d <= 0:
            fail.append(f"{tag}: disk measured {d}")
        if r.get("server_disk_settled") is False:
            fail.append(f"{tag}: disk never settled ({r.get('server_disk_note')})")
        if r.get("server_disk_note") and r.get("server_disk_settled") is not True:
            fail.append(f"{tag}: server disk note: {r.get('server_disk_note')}")
        if any(v in be for v in VOLUME_ENGINES):
            vol = num(r.get("server_disk_vol_mb"))
            if vol is not None and vol <= 0:
                fail.append(f"{tag}: declares a volume but server_disk_vol_mb={vol}; "
                            f"writable-layer-only measurement is back")

        # --- quality ----------------------------------------------------------
        rec = num(r.get("recall_at_10"))
        if rec is not None and not 0.5 <= rec <= 1.0:
            fail.append(f"{tag}: recall@10={rec}")

        # --- cold / warm ------------------------------------------------------
        for kk in [x for x in r if x.startswith("warm_") and x.endswith("_p50_ms")]:
            cold = num(r.get(kk[len("warm_"):]))
            warm = num(r.get(kk))
            if cold and warm:
                if warm > cold * 1.5:
                    fail.append(f"{tag}: {kk} SLOWER than its first pass "
                                f"({warm} vs {cold}); a repeat should not cost more")
                if warm and cold / warm > 25:
                    fail.append(f"{tag}: {kk} gain {cold/warm:.0f}x, implausibly large")

        # --- config actually applied -------------------------------------------
        if r.get("mem_split") not in (None, "full+client"):
            fail.append(f"{tag}: mem_split={r.get('mem_split')}, expected full+client")
        if r.get("heap") and not isjvm:
            fail.append(f"{tag}: non-JVM engine stamped with heap={r.get('heap')}")
        if isjvm and r.get("topology") == "client_server" and not r.get("server_heap"):
            fail.append(f"{tag}: served JVM arm with no observed server_heap")

    # --- reps of one cell must agree -------------------------------------------
    if len(rs) >= 3:
        for field in ("peak_owned_mib_sum", "point_p50_ms", "hop1_p50_ms",
                      "query_p50_ms", "read_p50_ms", "build_s"):
            v = [num(r.get(field)) for r in rs]
            v = [x for x in v if x]
            if len(v) >= 3 and min(v) > 0 and max(v) / min(v) > 3:
                fail.append(f"{tag}: {field} varies {min(v):.3g}..{max(v):.3g} "
                            f"across {len(v)} reps ({max(v)/min(v):.1f}x)")

    # --- did this cell move against the previous campaign? ---------------------
    old = prev.get(k)
    if old and len(rs) >= 3:
        for field in ("point_p50_ms", "hop1_p50_ms", "query_p50_ms", "read_p50_ms"):
            try:
                o = st.median([float(x[field]) for x in old if x.get(field)])
                n_ = st.median([num(r.get(field)) for r in rs if num(r.get(field))])
            except Exception:
                continue
            if o and n_ and (n_ / o > 2 or o / n_ > 2):
                fail.append(f"{tag}: {field} moved {o:.3g} -> {n_:.3g} "
                            f"({n_/o:.2f}x) against the previous campaign")

print()
live, acked = [], []
for f in sorted(set(fail)):
    (acked if _ack_reason(f) else live).append(f)

if acked:
    print("ACKNOWLEDGED (tracked, not re-alerted)")
    seen_why = set()
    for f in acked:
        why = _ack_reason(f)
        if why not in seen_why:
            print("  *", why)
            seen_why.add(why)
        print("    -", f)
    print()

if live:
    print("SUSPECT")
    for f in live:
        print("  -", f)
else:
    print("nothing suspect in these rows")
