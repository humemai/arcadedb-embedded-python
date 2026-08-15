#!/usr/bin/env python3
r"""Does each monitor rule actually fire? Run after touching check_row.

A rule that has silently stopped firing looks exactly like a clean campaign,
which is the failure mode a monitor cannot afford. So every rule gets a
control row that must stay quiet and a mutated row that must go red, and the
release-version cases are checked explicitly because substring tests keep
matching things that are not versions: "rc" matches "a-rc-adedb", and a
\d[ab]\d alpha/beta pattern matches the "2b0" inside a git build hash. Three
instances of that one class of bug in a single day, which is why the fix is a
test rather than another patch.

    python3 monitoring/test_checks.py     # exits non-zero if any rule misbehaves
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_watch as W  # noqa: E402

HEALTHY = dict(
    lane="l2", scale="sf10", backend="arcadedb_graph_embedded", workload="oltp",
    rc=0, topology="embedded", engine_version="26.8.1", cpuset="0-11",
    mem_cap="24g", peak_owned_mib_sum=4000, heap="12g",
    hop1_p50_ms=0.4, hop1_p95_ms=0.8, hop1_p99_ms=1.2,
    close_s=0.055, reopen_s=0.011,
)

DEFECTS = [
    ("close never recorded",     lambda r: r.pop("close_s")),
    ("close took forever",       lambda r: r.update(close_s=120.0)),
    ("reopen took forever",      lambda r: r.update(reopen_s=45.0)),
    ("version is a name",        lambda r: r.update(engine_version="arcadedb-embedded")),
    ("version is a dev build",   lambda r: r.update(engine_version="26.8.1.dev20")),
    ("version is an rc",         lambda r: r.update(engine_version="26.9.0rc1")),
    ("version is a SNAPSHOT",    lambda r: r.update(engine_version="26.8.1-SNAPSHOT")),
    ("version missing",          lambda r: r.update(engine_version=None)),
    ("sharded cpuset",           lambda r: r.update(cpuset="0-5")),
    ("percentiles out of order", lambda r: r.update(hop1_p50_ms=9.0)),
    ("phases unaccounted",       lambda r: r.update(phases_accounted_s=100, cell_wall_s=1000)),
    ("recall out of range",      lambda r: r.update(recall_at_10=0.2)),
    ("owned exceeds its cap",    lambda r: r.update(peak_owned_mib_sum=40000)),
    ("owned implausibly small",  lambda r: r.update(peak_owned_mib_sum=4)),
    ("warm slower than cold",    lambda r: r.update(read_p50_ms=1.0, warm_read_p50_ms=5.0)),
    ("cold/warm gain absurd",    lambda r: r.update(read_p50_ms=500.0, warm_read_p50_ms=1.0)),
    ("OOM killed",               lambda r: r.update(oom_killed=True)),
    ("driver dominates memory",  lambda r: r.update(server_peak_anon_mib=100,
                                                    client_peak_anon_mib=900,
                                                    peak_anon_mib_sum=1000)),
    ("non-JVM stamped a heap",   lambda r: r.update(backend="qdrant_sparse")),
    ("green but empty",          lambda r: [r.pop(k) for k in list(r)
                                            if k.endswith("_ms")]),
]

# Releases, and strings that merely CONTAIN a pre-release-looking substring.
# Every one of these must stay quiet.
RELEASES = ["26.8.1", "27.0.0", "1.5.5", "ladybug:0.19.1", "arcadedb:26.8.1",
            "qdrant:1.19.0", "server:26.8.1",
            # The real string an ArcadeDB server reports. Its git hash ends
            # "...6299b2b0c", and a \d[ab]\d pattern applied to the whole
            # string matches the "2b0" inside it, so a healthy released server
            # was reported as a pre-release the table loader would reject.
            # Third time this class of bug shipped in one day; it stays here.
            "server:26.8.1 (build 727aa4568cdface314ee15cd242f71d6299b2b0c/1785790932717/main)"]


# Rep sequences measured on mini at l1/small, 2026-08-15. The postgres one is
# the defect the drift check was written for; the rest are healthy cells from
# the same run and must stay quiet, which is what stops the rule from being a
# blanket "reps disagree" alarm.
DRIFT_CASES = [
    ("postgres OLTP, the real drift", [0.356, 0.398, 0.400, 0.613, 0.601], True),
    ("postgres_tuned, healthy",       [0.569, 0.579, 0.489, 0.576, 0.619], False),
    ("arcadedb_server, healthy",      [0.662, 0.734, 0.657, 0.727, 0.655], False),
    ("duckdb, healthy",               [1.005, 0.988, 0.960, 0.987, 0.992], False),
    ("noisy but no trend",            [1.0, 2.0, 1.0, 2.0, 1.0],           False),
]


def drift_ratio(vals, field="read_p50_ms"):
    import statistics as st
    ordered = [{"rep": i + 1, field: v} for i, v in enumerate(vals)]
    half = len(ordered) // 2
    a = [x for x in (W.num(r.get(field)) for r in ordered[:half]) if x]
    b = [x for x in (W.num(r.get(field)) for r in ordered[-half:]) if x]
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = st.median(a), st.median(b)
    return mb / ma if ma and mb else None


def findings(row, isjvm=True):
    out = []
    W.check_row(row, "TAG", isjvm, out)
    return out


def main():
    control = findings(dict(HEALTHY))
    bad = 0
    if control:
        bad += 1
        print(f"CONTROL row is not clean: {control}")
    else:
        print("control: clean")

    for name, mutate in DEFECTS:
        row = dict(HEALTHY)
        mutate(row)
        isjvm = any(t in str(row.get("backend")) for t in W.JVM)
        got = [f for f in findings(row, isjvm) if f not in control]
        if got:
            print(f"  RED  {name:26} {got[0][5:]}")
        else:
            bad += 1
            print(f"  MISS {name:26} NOTHING FIRED")

    for ver in RELEASES:
        row = dict(HEALTHY)
        row["engine_version"] = ver
        got = [f for f in findings(row) if f not in control]
        if got:
            bad += 1
            print(f"  FALSE POSITIVE on release {ver!r}: {got}")
    print(f"releases stayed quiet: {len(RELEASES)} checked")

    for name, vals, should_fire in DRIFT_CASES:
        r = drift_ratio(vals)
        fired = r is not None and (r > 1.25 or r < 1 / 1.25)
        if fired != should_fire:
            bad += 1
            print(f"  DRIFT WRONG {name}: ratio={r}, fired={fired}, expected={should_fire}")
    print(f"drift cases behaved: {len(DRIFT_CASES)} checked")

    print("\nALL CHECKS BEHAVE" if not bad else f"\n{bad} PROBLEMS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
