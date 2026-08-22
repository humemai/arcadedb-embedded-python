#!/usr/bin/env python3
"""L4: timeseries lane on TSBS cpu-only data (fixed seed, influx line protocol).

Backends: arcadedb (embedded; Point documents with a composite (host, ts)
index -- its idiomatic timeseries shape), duckdb (table + ART index),
questdb (server; ILP ingest on 9009, SQL over pg-wire). InfluxDB3 omitted
(no stable embedded/pinnable OSS artifact at eval time; disclosed).

Queries (TSBS-flavored):
  q_last   last point for one host
  q_range  1h of one host, per-minute max(usage_user)
  q_global 12h across all hosts, hourly avg(usage_user)

Metrics per rep: ingest points/s, per-query median ms over 10 iterations.
"""
import argparse
import json
import os
import statistics
import time

# THE CORPUS. BENCH_-prefixed because runner.py's env allowlist is a CLOSED
# tuple: a variable not in it is dropped at the container boundary and the
# in-script default silently runs instead. The old TSBS_ names are still read as
# a fallback so ts5414_driver.py, qlast_ab.py and ts_stride_probe.py keep working.
LP = os.environ.get("BENCH_TSBS_LP") or os.environ.get(
    "TSBS_LP", "/data/tsbs/cpu_influx.lp")
LIMIT = int(os.environ.get("BENCH_TS_LIMIT") or os.environ.get("TSBS_LIMIT", "0"))

# THE TIER. One today. It exists so the lane has a scale axis at all: every
# registered lane has one, PAPER_SCALES keys on it, and load_canonical drops a
# row whose scale is not listed for its lane.
SCALE_POINTS = {"ts100": 2_592_000}
QITER = 10
HOST = "host_42"
T0 = 1767225600  # 2026-01-01T00:00:00Z epoch seconds


def parse_lp():
    pts = []  # (host, ts_epoch_s, usage_user, usage_system, usage_idle)
    with open(LP) as f:
        for i, line in enumerate(f):
            if LIMIT and i >= LIMIT:
                break
            try:
                head, fields, ts = line.rsplit(" ", 2)
                host = head.split("hostname=", 1)[1].split(",", 1)[0]
                fd = dict(kv.split("=") for kv in fields.split(","))
                pts.append((host, int(ts) // 1_000_000_000,
                            float(fd["usage_user"].rstrip("i")),
                            float(fd["usage_system"].rstrip("i")),
                            float(fd["usage_idle"].rstrip("i"))))
            except Exception:
                continue
    return pts


class ArcadeTS:
    name = "arcadedb_ts_doc"

    def connect(self):
        import arcadedb_embedded as arcadedb
        self._arcadedb = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "6g")
        self.db = arcadedb.create_database("/tmp/l4_arcade",
                                           # -Xms pinned to -Xmx, matching every server arm and the other lanes.
                                           # heap_size sets -Xmx ONLY (bindings jvm.py), so without this the JVM
                                           # starts at its default initial heap, 1/64 of the cgroup, and grows
                                           # under load. The paper states -Xms=-Xmx as a protocol invariant for
                                           # everyone. It was true of l1, l2, l3s, l3d and every server arm, and
                                           # false here.
                                           jvm_kwargs={"heap_size": heap,
                                                       "jvm_args": f"-Xms{heap}"})

    def version(self):
        return f"arcadedb {self._arcadedb.__version__}"

    def ingest(self, pts):
        db = self.db
        db.command("sql", "CREATE DOCUMENT TYPE Point")
        for c, t in (("host", "STRING"), ("ts", "LONG"), ("uu", "DOUBLE"),
                     ("us", "DOUBLE"), ("ui", "DOUBLE")):
            db.command("sql", f"CREATE PROPERTY Point.{c} {t}")
        db.command("sql", "CREATE INDEX ON Point (host, ts) UNIQUE")
        db.begin()
        for n, (h, ts, uu, us, ui) in enumerate(pts):
            db.command("sql", "INSERT INTO Point SET host=:h, ts=:t, uu=:a, us=:b, ui=:c",
                       {"h": h, "t": ts, "a": uu, "b": us, "c": ui})
            if (n + 1) % 10_000 == 0:
                db.commit()
                db.begin()
        db.commit()

    def q_last(self):
        return self.db.query("sql",
            f"SELECT ts, uu FROM Point WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1").to_list()

    def q_range(self):
        return self.db.query("sql",
            f"SELECT (ts - ts % 60) AS m, max(uu) AS v FROM Point WHERE host='{HOST}' "
            f"AND ts >= {T0} AND ts < {T0+3600} GROUP BY m ORDER BY m").to_list()

    def q_global(self):
        return self.db.query("sql",
            f"SELECT (ts - ts % 3600) AS h, avg(uu) AS v FROM Point "
            f"WHERE ts >= {T0} AND ts < {T0+43200} GROUP BY h ORDER BY h").to_list()

    def close(self):
        self.db.close()


class DuckTS:
    name = "duckdb"

    def connect(self):
        import duckdb
        self._duckdb = duckdb
        self.cx = duckdb.connect("/tmp/l4_duck.db")

    def version(self):
        return f"duckdb {self._duckdb.__version__}"

    def ingest(self, pts):
        self.cx.execute("CREATE TABLE p (host VARCHAR, ts BIGINT, uu DOUBLE, "
                        "us DOUBLE, ui DOUBLE)")
        self.cx.executemany("INSERT INTO p VALUES (?,?,?,?,?)", pts) if len(pts) < 100_000 else None
        if len(pts) >= 100_000:
            import pyarrow as pa
            t = pa.table({"host": [p[0] for p in pts], "ts": [p[1] for p in pts],
                          "uu": [p[2] for p in pts], "us": [p[3] for p in pts],
                          "ui": [p[4] for p in pts]})
            self.cx.register("src", t)
            self.cx.execute("INSERT INTO p SELECT * FROM src")

    def q_last(self):
        return self.cx.execute(
            f"SELECT ts, uu FROM p WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1").fetchall()

    def q_range(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 60) AS m, max(uu) FROM p WHERE host='{HOST}' "
            f"AND ts >= {T0} AND ts < {T0+3600} GROUP BY m ORDER BY m").fetchall()

    def q_global(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 3600) AS h, avg(uu) FROM p WHERE ts >= {T0} "
            f"AND ts < {T0+43200} GROUP BY h ORDER BY h").fetchall()

    def close(self):
        self.cx.close()


class QuestTS:
    name = "questdb"

    def connect(self):
        import socket
        import psycopg
        # BENCH_SERVER_HOST is what runner.py sets for a client_server cell.
        # Refuse rather than fall back to localhost: a silent fallback would
        # connect to nothing, or worse to a leftover container, and report the
        # result as a measurement.
        host = os.environ.get("BENCH_SERVER_HOST") or os.environ.get("QUEST_HOST")
        if not host:
            raise SystemExit(
                "l4/questdb: neither BENCH_SERVER_HOST nor QUEST_HOST is set. "
                "This arm needs a server container; it cannot measure anything "
                "by defaulting to localhost.")
        self._ilp_host = host
        self.cx = psycopg.connect(
            f"host={host} port=8812 dbname=qdb user=admin password=quest",
            autocommit=True)

    def version(self):
        # The engine under test is in another container, so ASK it rather than
        # reporting anything about this process.
        with self.cx.cursor() as c:
            c.execute("SELECT build()")
            return f"questdb {c.fetchone()[0]}"

    def ingest(self, pts):
        import socket
        s = socket.create_connection((self._ilp_host, 9009))
        buf = []
        for h, ts, uu, us, ui in pts:
            buf.append(f"p,host={h} uu={uu},us={us},ui={ui} {ts*1_000_000_000}")
            if len(buf) >= 20_000:
                s.sendall(("\n".join(buf) + "\n").encode())
                buf = []
        if buf:
            s.sendall(("\n".join(buf) + "\n").encode())
        s.close()

    def settle(self):
        """Wait for WAL apply. Called by the driver AFTER the ingest timer stops.

        THIS USED TO RUN INSIDE ingest(), AND THEREFORE INSIDE THE TIMER. The
        loop cannot exit in under 3 s (it needs three consecutive equal counts a
        second apart), so roughly half of QuestDB's measured 5.99 s ingest was
        this poll, and the published pts/s was deflated by it. PROTOCOL section
        7 recorded the defect and its size: the headline ratio "would fall near
        2x" from 4.3x once this moves out.

        The rule it now follows, which is the one the lane needs to be
        internally consistent: EVERY arm's ingest timer stops when the engine
        has ACCEPTED the data, and any background catch-up is settled outside
        the timer. For the synchronous arms (ArcadeDB document path, DuckDB)
        accepted and queryable are the same instant, so nothing moves. For the
        async ones there is a gap, and both must treat it the same way:
        l4_native_probe stops at wait_completion() and settles afterwards, and
        this now matches it. Timing one async engine to "accepted" and another
        to "queryable" prices two different operations under one column name.
        """
        last, stable = -1, 0
        for _ in range(120):
            try:
                n = self.cx.execute("SELECT count() FROM p").fetchone()[0]
            except Exception:
                time.sleep(1)
                continue
            if n == last and n > 0:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = n
            time.sleep(1)

    def q_last(self):
        return self.cx.execute(
            f"SELECT timestamp, uu FROM p WHERE host='{HOST}' "
            f"ORDER BY timestamp DESC LIMIT 1").fetchall()

    def q_range(self):
        # QuestDB idiom: SAMPLE BY (its native time-bucketing)
        return self.cx.execute(
            f"SELECT timestamp, max(uu) FROM p WHERE host='{HOST}' "
            f"AND timestamp >= '2026-01-01T00:00:00Z' "
            f"AND timestamp < '2026-01-01T01:00:00Z' SAMPLE BY 1m").fetchall()

    def q_global(self):
        return self.cx.execute(
            f"SELECT timestamp, avg(uu) FROM p "
            f"WHERE timestamp >= '2026-01-01T00:00:00Z' "
            f"AND timestamp < '2026-01-01T12:00:00Z' SAMPLE BY 1h").fetchall()

    def close(self):
        self.cx.close()


# Backends whose cell runs a SEPARATE server container, so run_conditions reads
# the driver's cgroup and not the engine's. Kept as data beside the adapters so
# adding a served arm cannot forget to update the role test.
_CLIENT_SERVER = {"questdb"}

BACKENDS = {c.name: c for c in (ArcadeTS, DuckTS, QuestTS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    # The runner passes both on every cell. --workload is accepted and does not
    # branch: this lane measures ingest AND queries in one pass over one built
    # database, so splitting it into two cells would either build twice or carry
    # state between cells, and both are worse than one cell reporting both.
    # It rides the axis because runner.build_jobs crosses backends x workloads
    # and a lane with no workload produces no jobs.
    ap.add_argument("--workload", default="ingest")
    ap.add_argument("--scale", default="ts100", choices=list(SCALE_POINTS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pts = parse_lp()
    # n_docs, not just n_points: BOTH canonical keys include n_docs
    # (make_paper_tables and merge_campaign), and PAPER_CORPUS fingerprints a
    # tier on it. Without it two TSBS corpora of different sizes would collide
    # on one key, which is the defect that pooled two sparse campaigns.
    out = {"n_points": len(pts), "n_docs": len(pts), "backend": args.backend,
           "scale": args.scale, "workload": args.workload}
    want = SCALE_POINTS[args.scale]
    if LIMIT == 0 and len(pts) != want:
        raise SystemExit(
            f"l4: {args.scale} expects {want:,} points and the corpus at {LP} "
            f"holds {len(pts):,}. A tier that silently measures a different "
            f"corpus than its name claims is the sparse-pooling defect again.")
    b = BACKENDS[args.backend]()
    b.connect()
    t0 = time.perf_counter()
    b.ingest(pts)
    dt = time.perf_counter() - t0
    out["ingest_s"] = round(dt, 2)
    out["ingest_pts_per_s"] = round(len(pts) / dt, 1)

    # The engine's own catch-up, priced but not charged to the ingest rate.
    # An arm with no catch-up records 0.0 rather than nothing, so a row can
    # never be read as "settled" merely because the field is absent.
    _t = time.perf_counter()
    if hasattr(b, "settle"):
        b.settle()
    out["engine_settle_s"] = round(time.perf_counter() - _t, 3)

    # Optional settle between ingest and query, OUTSIDE the ingest timer.
    # Default 0 keeps every arm exactly as it was, because a settle given to
    # one engine and not the others is the asymmetry this lane already has to
    # answer for elsewhere. It exists because the provenanced questdb re-run
    # came out roughly 3x slower on every query than the unprovenanced row it
    # replaced, while duckdb reproduced within 4%, and the obvious suspect is
    # that a fresh container queried the instant pg-wire accepts has not
    # finished absorbing 2.6M rows. Setting this lets that be tested rather
    # than argued, and the value lands in the artifact so a settled row can
    # never be mistaken for an unsettled one.
    settle = float(os.environ.get("TSBS_SETTLE_S", "0"))
    out["settle_s"] = settle
    if settle > 0:
        time.sleep(settle)

    for qn in ("q_last", "q_range", "q_global"):
        times = []
        ref = None
        for _ in range(QITER):
            t = time.perf_counter()
            ref = getattr(b, qn)()
            times.append((time.perf_counter() - t) * 1000)
        out[f"{qn}_ms"] = round(statistics.median(times), 2)
        out[f"{qn}_rows"] = len(ref) if ref is not None else 0
    # Ask each backend for ITS OWN version, before closing it. run_conditions
    # stamps engine_version from the arcadedb-embedded wheel, which is the
    # right answer for the ArcadeDB row and the wrong one for duckdb and
    # questdb: the wheel is present in the image but is not the engine those
    # rows measured. Recording it unqualified would make the provenance audit
    # report a version and pass, which is worse than reporting none.
    try:
        out["backend_version"] = b.version()
    except Exception as e:
        out["backend_version"] = f"unknown ({e.__class__.__name__})"
    # TIME THE CLOSE, do not merely perform it (#155). A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. An unrecorded close is an unpriced one, and
    # the row cannot be told apart from a lane that never settles.
    _t = time.perf_counter()
    b.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)

    # Stamp what this actually ran under. Until now every row this lane wrote
    # carried only the backend name and the metrics, so T5's time-series block
    # printed three unprovenanced rows (duckdb, questdb, and ArcadeDB's
    # document path) beside one fully stamped row from l4_native_probe.py.
    # This lane is also the one never wired into runner.py, so no manifest was
    # covering for it either -- runs.jsonl has lanes l1, l1tpc, l2, l3d, l3s,
    # e2, and no l4.
    #
    # Read from the cgroup, not asserted: see bench_common.run_conditions.
    # questdb is a client/server backend, so for that row the conditions
    # describe THIS driver process and not the questdb container. Recorded
    # under a role that says so rather than silently implying otherwise.
    try:
        import bench_common
        # ROLE IS DERIVED FROM TOPOLOGY, not from a backend literal. The old
        # `== "questdb"` test broke the moment backends were renamed, and a
        # wrong role is invisible: it just mislabels whose cgroup was read.
        role = "driver" if args.backend in _CLIENT_SERVER else "engine"
        out.update(bench_common.run_conditions(lane="l4", backend=args.backend,
                                               role=role))
        # Same reasoning as backend_version above, from the other side: on a
        # comparator row engine_version names the wheel this harness imported,
        # not the engine measured. Move it to a name that says so, so the only
        # version field a reader can mistake for the engine under test is the
        # one that IS the engine under test.
        # startswith, NOT an equality test against one literal. With the arms
        # renamed to arcadedb_ts_doc / arcadedb_ts_native / _plain, `!=
        # "arcadedb"` is true for ALL of them, so every ArcadeDB row would lose
        # engine_version -- the field load_canonical's dev guard reads, the one
        # export_web falls back to, and the one the page prints as version_name.
        if not args.backend.startswith("arcadedb"):
            out["harness_arcadedb_version"] = out.pop("engine_version", None)
    except Exception as e:                     # never lose a measured result
        out["conditions_error"] = f"{e.__class__.__name__}: {e}"

    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
