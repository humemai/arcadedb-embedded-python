#!/usr/bin/env python3
"""Are the campaign's numbers genuinely fine? Read-only, run repeatedly.

Not a liveness check. Every rule here corresponds to a class of weird number
this project has actually shipped or nearly shipped:

  memory    a column that was 88% our own Python driver; a metric that captured
            26% of one engine's peak and 98% of another's; 20 rows on a heap
            nobody observed
  disk      SizeRw reading 20 KB while 1 GiB sat in a volume; a reading taken
            before writeback and compaction settled
  cold/warm a lane that timed one pass and never said which, hiding a 9.4x
            second-pass gain on the comparator we beat
  lifecycle two lanes that never closed the database, so the disk figure was a
            crash state and deferred shutdown work was never paid (#155)
  silent    30 OOM-killed cells that exited 0 with empty error strings
  drift     a cell whose reps disagree, averaged into a tidy median
  provenance a comparator row stamped "unknown (PackageNotFoundError)", which
            cannot be re-measured by anyone including us

Usage:
    campaign_watch.py [--since ISO8601 | --since-marker TEXT] [--all]

Prints a compact table, then a SUSPECT section. The monitor forwards only the
SUSPECT section, so a check that fires must be worth waking someone for.
"""
import argparse
import collections
import csv
import json
import os
import re
import statistics as st
import sys

RES = os.path.expanduser("~/repos/humemai/arcadedb-embedded-python/"
                         "benchmarks/experiments/results")

# ANCHOR THE PRE-RELEASE TEST TO A VERSION, NEVER TO A SUBSTRING OF THE WHOLE
# STRING. A bare `"rc" in ver` matches "a-rc-adedb", and the identical mistake
# in build_images.sh refused every correct release build until it was found.
# Each alternative below must sit against a digit or a boundary.
_PRERELEASE = re.compile(r"(\.dev\d|[-_.]?rc\d|\d[ab]\d|-SNAPSHOT)", re.I)

JVM = ("arcadedb", "neo4j", "elasticsearch", "questdb")
VOLUME_ENGINES = ("arcadedb_graph_server", "arcadedb_server", "arcadedb_sparse_server",
                  "arcadedb_dense_server", "neo4j", "postgres")


def KEY(r):
    return (r.get("lane"), r.get("scale"), r.get("backend"), r.get("workload"))


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ACKNOWLEDGED FINDINGS. Real, understood, already tracked, and NOT fixable in
# the rows this campaign is writing. They stay in the printed table so nobody
# forgets them; they are kept out of SUSPECT so the monitor does not re-alert
# every two minutes and drown a genuinely new finding.
#
# The rule for adding one: it must name the task that owns it, and it must be
# something this run cannot change. "Annoying" is not a reason.
#
# EMPTIED 2026-08-15. The one entry here covered observe_server matching only
# -Xmx, which made Neo4j's NEO4J_server_memory_heap_max__size invisible. That
# fix is now on the bench host, so a row with no observed server heap is once
# again a real finding and must alert.
ACK = []


def _ack_reason(msg):
    for pat, why in ACK:
        if pat in msg:
            return why
    return None


def _cut_point(args, rows):
    """When did the run under observation start?

    A campaign is a set of rows, not a process, and runs.jsonl is append-only
    across months. Without a cut every rule fires on history: rows written
    before a fix legitimately violate it, and a monitor that reports
    already-fixed defects is one people learn to ignore.

    Order of preference, most explicit first:
      --since             an ISO timestamp, for reading an old window
      --since-marker      the last STATUS.txt line containing this text
      results/.campaign_start  written by whatever launched the campaign
      first row carrying the current instrument
    """
    if args.all:
        return None
    if args.since:
        return args.since
    if args.since_marker:
        try:
            with open(os.path.expanduser("~/STATUS.txt"), errors="ignore") as fh:
                stamps = [ln[1:ln.index("]")] for ln in fh
                          if args.since_marker in ln and ln.startswith("[")]
            if stamps:
                # THE LAST ONE. Cutting on the first match was wrong: a job
                # that was fixed and relaunched writes its marker twice, and
                # the earlier one admits rows from the aborted attempt.
                return stamps[-1]
        except OSError:
            pass
    try:
        with open(os.path.join(RES, ".campaign_start")) as fh:
            return fh.read().strip()
    except OSError:
        pass
    return next((r.get("ts_utc") for r in rows
                 if r.get("peak_owned_mib_sum") is not None), None)


def check_row(r, tag, isjvm, fail):
    """Every per-row rule. Appends human-readable findings to `fail`."""
    # --- the cell ran at all ------------------------------------------------
    if r.get("oom_killed"):
        fail.append(f"{tag}: OOM killed")
    if r.get("error"):
        fail.append(f"{tag}: error={r['error']}")
    metrics = {k: v for k, v in r.items()
               if num(v) is not None
               and (k.endswith("_ms") or k in ("qps", "oltp_ops_per_s"))}
    # NOT EVERY LANE MEASURES LATENCY. e2's atomicity workload counts torn
    # states across trials and emits no _ms at all; demanding one there fired
    # on six healthy cells. Ask instead whether the row carries ANY result,
    # which is the thing that actually distinguishes a working cell from a
    # green-but-empty one.
    outcomes = ("trials", "torn_count", "no_loss", "recovered", "rows",
                "ingest_pts_per_s", "recall_at_10")
    if r.get("rc") == 0 and not metrics and not any(k in r for k in outcomes):
        fail.append(f"{tag}: rc=0 but the row carries neither a latency metric "
                    f"nor any other result")

    # --- percentiles must be ordered ----------------------------------------
    for base in {k.rsplit("_p", 1)[0] for k in r if "_p50_ms" in k}:
        p50, p95, p99 = (num(r.get(f"{base}_p{p}_ms")) for p in (50, 95, 99))
        if p50 and p95 and p50 > p95 * 1.001:
            fail.append(f"{tag}: {base} p50 {p50} > p95 {p95}")
        if p95 and p99 and p95 > p99 * 1.001:
            fail.append(f"{tag}: {base} p95 {p95} > p99 {p99}")
    for k, v in metrics.items():
        if v <= 0:
            fail.append(f"{tag}: {k}={v}")

    # --- memory --------------------------------------------------------------
    owned = num(r.get("peak_owned_mib_sum"))
    cap = r.get("server_mem_cap_g") or r.get("mem_cap")
    capg = None
    if isinstance(cap, str) and cap.endswith("g"):
        capg = float(cap[:-1])
    elif num(cap) is not None:
        capg = float(cap)
    if owned and capg and owned / 1024 > capg * 1.05:
        fail.append(f"{tag}: owned {owned/1024:.1f} GiB exceeds its {capg} GiB cap")
    if owned is not None and owned < 32:
        fail.append(f"{tag}: owned memory {owned} MiB, implausibly small for a loaded engine")
    # NO "owned should approach the committed heap" RULE. -Xms commits address
    # space; it does not pre-touch it, and cgroup anon counts only RESIDENT
    # pages. So an arm with -Xms4g legitimately shows 1.5 GiB until the workload
    # dirties more. This rule fired on ten healthy ArcadeDB cells before the
    # premise was checked. Making it true would need -XX:+AlwaysPreTouch, which
    # would change what we measure. Recorded so it is not re-added.
    cli, tot = num(r.get("client_peak_anon_mib")), num(r.get("peak_anon_mib_sum"))
    if num(r.get("server_peak_anon_mib")) is not None and cli and tot and cli / tot > 0.5:
        fail.append(f"{tag}: {100*cli/tot:.0f}% of the memory cell is the driver")

    # --- disk ----------------------------------------------------------------
    d = (num(r.get("disk_mb_sum")) or num(r.get("server_disk_mb"))
         or num(r.get("client_disk_mb")))
    if r.get("rc") == 0 and d is not None and d <= 0:
        fail.append(f"{tag}: disk measured {d}")
    if r.get("server_disk_settled") is False:
        fail.append(f"{tag}: disk never settled ({r.get('server_disk_note')})")
    if r.get("server_disk_note") and r.get("server_disk_settled") is not True:
        fail.append(f"{tag}: server disk note: {r.get('server_disk_note')}")
    if any(v in str(r.get("backend")) for v in VOLUME_ENGINES):
        vol = num(r.get("server_disk_vol_mb"))
        if vol is not None and vol <= 0:
            fail.append(f"{tag}: declares a volume but server_disk_vol_mb={vol}; "
                        f"writable-layer-only measurement is back")

    # --- lifecycle (#154, #155) ----------------------------------------------
    # A disk figure taken before a clean close is a crash state. Measured on
    # 26.8.1: a close releases 30-87 MB, which is 84% of a toy database and
    # 2.0% of a 1.5 GB one, and LadybugDB releases nothing because it was
    # already settled. So the defect is real but bounded, and the thing to
    # watch is whether the close happened at all.
    close_s = num(r.get("close_s"))
    if r.get("topology") == "embedded" and r.get("rc") == 0:
        if close_s is None and r.get("close_note") is None:
            fail.append(f"{tag}: embedded cell recorded neither close_s nor a reason; "
                        f"its disk figure may be a crash state (#155)")
    if close_s is not None and close_s > 60:
        fail.append(f"{tag}: close took {close_s}s, which is deferred work "
                    f"nobody was charged for (#155)")
    reopen_s = num(r.get("reopen_s"))
    if reopen_s is not None and reopen_s > 30:
        fail.append(f"{tag}: reopen took {reopen_s}s; a phase split would charge "
                    f"this to every JVM arm and to no comparator (#154)")

    # --- phase accounting ----------------------------------------------------
    # Unaccounted time is where a settle step, a stall or a retry hides. The
    # sparse lane had ~105-145 min per cell that no phase timer claimed.
    acc, wall = num(r.get("phases_accounted_s")), num(r.get("cell_wall_s"))
    if acc and wall and wall > 60 and acc / wall < 0.7:
        fail.append(f"{tag}: phases account for {100*acc/wall:.0f}% of {wall:.0f}s "
                    f"wall; the rest is unexplained")

    # --- quality -------------------------------------------------------------
    rec = num(r.get("recall_at_10"))
    if rec is not None and not 0.5 <= rec <= 1.0:
        fail.append(f"{tag}: recall@10={rec}")

    # --- cold / warm ---------------------------------------------------------
    for k in [x for x in r if x.startswith("warm_") and x.endswith("_p50_ms")]:
        cold = num(r.get(k[len("warm_"):]))
        warm = num(r.get(k))
        if cold and warm:
            if warm > cold * 1.5:
                fail.append(f"{tag}: {k} SLOWER than its first pass "
                            f"({warm} vs {cold}); a repeat should not cost more")
            if cold / warm > 25:
                fail.append(f"{tag}: {k} gain {cold/warm:.0f}x, implausibly large")

    # --- provenance ----------------------------------------------------------
    # A row that cannot say what it ran is a row nobody can re-measure. Every
    # one of these has bitten: a comparator stamped "unknown", a server row
    # labelled "server:latest" while running a pinned digest, an overlay with
    # no conditions at all (#113, #141).
    ver = str(r.get("engine_version") or "")
    if not ver or "unknown" in ver or ver == "unrecorded":
        fail.append(f"{tag}: engine_version={ver!r}, so this row cannot be re-measured")
    elif not any(c.isdigit() for c in ver):
        # "arcadedb-embedded", "qdrant-local+neo4j", "server:latest": a NAME
        # where a version belongs. Nine rows do this (#156), and each one is a
        # cell nobody can reproduce.
        fail.append(f"{tag}: engine_version={ver!r} names the engine but gives "
                    f"no version (#156)")
    elif _PRERELEASE.search(ver):
        fail.append(f"{tag}: engine_version={ver!r} is a pre-release; "
                    f"the table loader will reject this row")
    if r.get("cpuset") not in (None, "0-11"):
        fail.append(f"{tag}: cpuset={r.get('cpuset')!r}, not the full paper cpuset")

    # --- config actually applied ---------------------------------------------
    if r.get("mem_split") not in (None, "full+client"):
        fail.append(f"{tag}: mem_split={r.get('mem_split')}, expected full+client")
    if r.get("heap") and not isjvm:
        fail.append(f"{tag}: non-JVM engine stamped with heap={r.get('heap')}")
    if isjvm and r.get("topology") == "client_server" and not r.get("server_heap"):
        fail.append(f"{tag}: served JVM arm with no observed server_heap")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO timestamp; ignore rows older than this")
    ap.add_argument("--since-marker",
                    help="cut at the LAST STATUS.txt line containing this text")
    ap.add_argument("--all", action="store_true",
                    help="every row ever written; expect history to fire rules")
    ap.add_argument("--expect-reps", type=int, default=5,
                    help="reps a complete cell should have (0 disables the check)")
    args = ap.parse_args()

    with open(os.path.join(RES, "runs.jsonl")) as fh:
        rows = [json.loads(ln) for ln in fh if ln.strip()]

    cut = _cut_point(args, rows)
    new = [r for r in rows if not cut or (r.get("ts_utc") or "") >= cut]
    if not new:
        print(f"no rows since {cut}")
        return 0
    print(f"{len(new)} rows since {cut or 'the beginning'}\n")

    # Previous campaign, for "did this cell move" comparisons.
    prev = collections.defaultdict(list)
    try:
        with open(os.path.join(RES, "runs_paper.csv")) as fh:
            for r in csv.DictReader(fh):
                prev[(r["lane"], r["scale"], r["backend"], r["workload"])].append(r)
    except OSError:
        pass

    fail = []
    cells = collections.defaultdict(list)
    for r in new:
        cells[KEY(r)].append(r)

    print(f"{'lane':6} {'scale':8} {'backend':28} {'wl':6} {'n':>2} "
          f"{'owned GiB':>9} {'disk MiB':>9} {'close_s':>7} {'set':>4}")
    for k in sorted(cells, key=lambda x: tuple(str(i) for i in x)):
        rs = cells[k]
        lane, scale, be, wl = (str(x) for x in k)
        tag = f"{lane}/{scale}/{be}/{wl}"
        isjvm = any(t in be for t in JVM)

        ow = [x for x in (num(r.get("peak_owned_mib_sum")) for r in rs) if x]
        dk = [x for x in ((num(r.get("disk_mb_sum")) or num(r.get("server_disk_mb"))
                           or num(r.get("client_disk_mb"))) for r in rs) if x]
        cl = [x for x in (num(r.get("close_s")) for r in rs) if x is not None]
        print(f"{lane:6} {scale:8} {be:28} {wl:6} {len(rs):2d} "
              f"{(st.median(ow)/1024 if ow else 0):9.2f} "
              f"{(st.median(dk) if dk else 0):9.1f} "
              f"{(st.median(cl) if cl else 0):7.3f} "
              f"{str(rs[-1].get('server_disk_settled'))[:4]:>4}")

        for r in rs:
            check_row(r, tag, isjvm, fail)

        # --- the cell is complete --------------------------------------------
        # A short cell is not visibly broken: it prints a median like any
        # other. Table IV's 8.84M row is stuck at N=3 for exactly this reason.
        if args.expect_reps and 0 < len(rs) < args.expect_reps:
            done = all(r.get("rc") == 0 for r in rs)
            if done:
                fail.append(f"{tag}: {len(rs)} reps, expected {args.expect_reps}")

        # --- reps of one cell must agree --------------------------------------
        if len(rs) >= 3:
            for field in ("peak_owned_mib_sum", "point_p50_ms", "hop1_p50_ms",
                          "query_p50_ms", "read_p50_ms", "build_s"):
                v = [x for x in (num(r.get(field)) for r in rs) if x]
                if len(v) >= 3 and min(v) > 0 and max(v) / min(v) > 3:
                    fail.append(f"{tag}: {field} varies {min(v):.3g}..{max(v):.3g} "
                                f"across {len(v)} reps ({max(v)/min(v):.1f}x)")

        # --- did this cell move against the previous campaign? ----------------
        old = prev.get(k)
        if old and len(rs) >= 3:
            for field in ("point_p50_ms", "hop1_p50_ms", "query_p50_ms", "read_p50_ms"):
                try:
                    o = st.median([float(x[field]) for x in old if x.get(field)])
                    n_ = st.median([x for x in (num(r.get(field)) for r in rs) if x])
                except (ValueError, st.StatisticsError):
                    continue
                if o and n_ and (n_ / o > 2 or o / n_ > 2):
                    fail.append(f"{tag}: {field} moved {o:.3g} -> {n_:.3g} "
                                f"({n_/o:.2f}x) against the previous campaign")

    # --- one protocol per comparison group -----------------------------------
    # PROTOCOL forbids printing a one-build-many-passes row beside a
    # per-rep-build row: the two price different work. Keyed on
    # (lane, scale, workload) and compared per backend, because keying without
    # the workload made this fire on every family at once.
    for gk, group in collections.defaultdict(list, {
            g: [r for r in new if (r.get("lane"), r.get("scale"), r.get("workload")) == g]
            for g in {(r.get("lane"), r.get("scale"), r.get("workload")) for r in new}
    }).items():
        shapes = collections.defaultdict(set)
        for r in group:
            shapes[r.get("backend")].add(r.get("protocol") or r.get("pass_shape"))
        distinct = {next(iter(v)) for v in shapes.values() if len(v) == 1}
        if len(distinct) > 1:
            fail.append(f"{'/'.join(str(x) for x in gk)}: backends ran different "
                        f"protocols {sorted(str(d) for d in distinct)} in one group")

    print()
    live, acked = [], []
    for f in sorted(set(fail)):
        (acked if _ack_reason(f) else live).append(f)

    if acked:
        print("ACKNOWLEDGED (tracked, not re-alerted)")
        seen = set()
        for f in acked:
            why = _ack_reason(f)
            if why not in seen:
                print("  *", why)
                seen.add(why)
            print("    -", f)
        print()

    if live:
        print("SUSPECT")
        for f in live:
            print("  -", f)
    else:
        print("nothing suspect in these rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
