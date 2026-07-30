#!/usr/bin/env python3
"""Pilot for task #83: TSBS on ArcadeDB's NATIVE time-series engine, against
the document-path adapter the July campaign measured.

Native path: CREATE TIMESERIES TYPE (SQL DDL), columnar bulk ingest via
AsyncExecutor.append_samples (tags then fields, declaration order), queries
via ts.timeBucket / ts.last with WHERE ts BETWEEN range pruning.
Timestamps stored in ms (the TS engine's default precision).

Smoke on laptop with a subset (TSBS_LP + TSBS_LIMIT); paper-adjacent numbers
re-measured on mini per project convention.
"""
import json
import os
import statistics
import time

from l4_tsbs import parse_lp, HOST, T0, QITER

SHARDS = int(os.environ.get("TS_SHARDS", "4"))
# #5474: route each batch through the engine primitive TimeSeriesBatch
# instead of Object[] columns, so no numeric sample is boxed on the way in.
PRIMITIVE = os.environ.get("TS_PRIMITIVE", "0") == "1"
# Columns cross as ndarrays by default. Passing Python lists makes
# append_samples convert per element instead of taking the binding's bulk
# path, which understated this lane 2.9x through the whole July campaign;
# lists remain reachable (TS_NUMPY=0) only to reproduce that "before" number.
NUMPY_COLS = os.environ.get("TS_NUMPY", "1") == "1"
# Fixed post-ingest settle so every arm gets the same background-sealing
# window; see the note at the call site. Default 30 s comfortably exceeds the
# ~4.7 s spread between the fastest and slowest ingest arms.
SETTLE_S = float(os.environ.get("TS_SETTLE_S", "30"))
# TSBS cpu declares TEN tags; this lane declared one, which put our published
# number on the 290-byte stride arm rather than the 2,612-byte one real users
# are on, and therefore flattered ArcadeDB. Only became viable to fix with
# upstream #5574 (a TAG is now a 4-byte dictionary id, not a 258-byte inline
# slot). Kept configurable so the narrow arm stays reproducible for comparison
# against what is already published.
TAG_NAMES = ["hostname", "region", "datacenter", "rack", "os",
             "arch", "team", "service", "service_version", "service_environment"]
N_TAGS = int(os.environ.get("TS_TAGS", "1"))
# The narrow schema calls its single tag "host"; the wide one uses the real
# TSBS names, whose first is "hostname". The queries filter on this column, so
# hardcoding "host" would make the wide arm filter on a column that does not
# exist and report zero rows as though it were a fast query.
TAG0 = TAG_NAMES[0] if N_TAGS > 1 else "host"
CHUNK = 50_000


class ArcadeTSNative:
    name = "arcadedb_ts_native"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database(
            os.environ.get("TS_DB_PATH", "/tmp/l4n_arcade"),
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})

    def ingest(self, pts):
        db = self.db
        # N_TAGS>1 needs the real tag values, which parse_lp discards (it keeps
        # hostname only). ts_stride_probe.parse_full keeps all ten, so the wide
        # arm uses genuine TSBS cardinality rather than synthesised values;
        # synthetic tags would change dictionary cardinality and therefore
        # measure something other than the real schema.
        if N_TAGS > 1:
            from ts_stride_probe import parse_full, TAGS as _ALLTAGS
            rows = parse_full()
            if not rows:
                raise SystemExit("ABORT: parse_full returned no rows for the wide-tag arm")
            tagcols = ", ".join(f"{_ALLTAGS[i]} STRING" for i in range(N_TAGS))
        else:
            tagcols = "host STRING"
        db.command("sql",
                   "CREATE TIMESERIES TYPE Point TIMESTAMP ts "
                   f"TAGS ({tagcols}) "
                   "FIELDS (uu DOUBLE, us DOUBLE, ui DOUBLE) "
                   f"SHARDS {SHARDS}")
        if N_TAGS > 1:
            return self._ingest_wide(rows)
        ex = self.db.async_executor()
        for lo in range(0, len(pts), CHUNK):
            chunk = pts[lo:lo + CHUNK]
            ts_col = [p[1] * 1000 for p in chunk]   # ts in ms
            host_col = [p[0] for p in chunk]        # host (tag)
            uu_col = [p[2] for p in chunk]
            us_col = [p[3] for p in chunk]
            ui_col = [p[4] for p in chunk]
            if NUMPY_COLS:
                import numpy as _np
                ts_col = _np.asarray(ts_col, dtype=_np.int64)
                uu_col = _np.asarray(uu_col, dtype=_np.float64)
                us_col = _np.asarray(us_col, dtype=_np.float64)
                ui_col = _np.asarray(ui_col, dtype=_np.float64)
            # Released wheels have no primitive= keyword; only send it when asked.
            kw = {"primitive": True} if PRIMITIVE else {}
            ex.append_samples(
                "Point", ts_col, host_col, uu_col, us_col, ui_col, **kw)
        ex.wait_completion()

    def _ingest_wide(self, rows):
        """Real TSBS tag cardinality: N_TAGS tag columns from parse_full.

        Same chunking, same numpy/primitive switches and the same settle as the
        narrow path, so the only difference between arms is the tag count.
        """
        ex = self.db.async_executor()
        for lo in range(0, len(rows), CHUNK):
            chunk = rows[lo:lo + CHUNK]
            ts_col = [r[1] * 1000 for r in chunk]
            tag_cols = [[r[0][i] for r in chunk] for i in range(N_TAGS)]
            fld = [[r[2][j] for r in chunk] for j in range(3)]
            if NUMPY_COLS:
                import numpy as _np
                ts_col = _np.asarray(ts_col, dtype=_np.int64)
                fld = [_np.asarray(c, dtype=_np.float64) for c in fld]
            kw = {"primitive": True} if PRIMITIVE else {}
            ex.append_samples("Point", ts_col, *tag_cols, *fld, **kw)
        ex.wait_completion()

    def settle(self):
        """Fixed post-ingest wait, called by the driver AFTER the ingest timer
        has stopped.

        Why a settle exists at all: wait_completion() returns when the async
        ingest has been accepted, not when background sealing has caught up,
        and this lane had none while every other lane has one (ES forcemerge,
        Milvus flush, Qdrant green-wait, ArcadeDB COMPACT INDEX). Without it
        the arms are not comparable: the list arm spends ~6.2 s ingesting where
        the batch arm spends ~1.5 s, so the slow arm hands sealing ~4.7 s more
        wall clock before the first query, and the "faster ingest reads slower"
        effect could be entirely that. There is no user-facing flush or compact
        for TIMESERIES (only an internal flushHeader), so a wall-clock wait is
        the honest instrument rather than a chosen one.

        Why it is called from the driver rather than from ingest(): it used to
        sit at the end of each ingest path, inside the timed region. That made
        `ingest_s` 30 s high and dropped `ingest_pts_per_s` 5.8x (417k to 72k
        on the same corpus and the same arm), which reads exactly like a
        TimeSeries ingest regression and is not one. It nearly went into the
        paper as one. A settle equalises the window before queries; it is not
        ingest work and must not be timed as any.
        """
        if SETTLE_S > 0:
            time.sleep(SETTLE_S)

    def q_last(self):
        # Bounded window: unbounded ts.last scans the tag's whole series
        # (208 ms vs 2.5 ms measured); TSBS's last-point permits recency.
        a = self.tmax_ms - 3600_000
        return self.db.query("sql",
            f"SELECT ts, uu FROM Point WHERE {TAG0} = '{HOST}' "
            f"AND ts BETWEEN {a} AND {self.tmax_ms} "
            f"ORDER BY ts DESC LIMIT 1").to_list()

    def q_range(self):
        a, b = T0 * 1000, (T0 + 3600) * 1000
        return self.db.query("sql",
            f"SELECT ts.timeBucket('1m', ts) AS m, max(uu) AS v FROM Point "
            f"WHERE {TAG0} = '{HOST}' AND ts BETWEEN {a} AND {b - 1} "
            f"GROUP BY m ORDER BY m").to_list()

    def q_global(self):
        a, b = T0 * 1000, (T0 + 43200) * 1000
        return self.db.query("sql",
            f"SELECT ts.timeBucket('1h', ts) AS h, avg(uu) AS v FROM Point "
            f"WHERE ts BETWEEN {a} AND {b - 1} "
            f"GROUP BY h ORDER BY h").to_list()

    def close(self):
        self.db.close()


def main():
    pts = parse_lp()
    out = {"n_points": len(pts), "backend": ArcadeTSNative.name,
           "shards": SHARDS, "primitive": PRIMITIVE, "numpy_cols": NUMPY_COLS}
    b = ArcadeTSNative()
    b.tmax_ms = max(p[1] for p in pts) * 1000
    b.connect()
    t0 = time.perf_counter()
    b.ingest(pts)
    dt = time.perf_counter() - t0
    out["ingest_s"] = round(dt, 2)
    out["ingest_pts_per_s"] = round(len(pts) / dt, 1)
    # Settle AFTER the timer: every arm gets the same sealing window before
    # queries, and none of it is counted as ingest.
    out["settle_s"] = SETTLE_S
    b.settle()
    for qn in ("q_last", "q_range", "q_global"):
        times, ref = [], None
        for _ in range(QITER):
            t = time.perf_counter()
            ref = getattr(b, qn)()
            times.append((time.perf_counter() - t) * 1000)
        out[f"{qn}_ms"] = round(statistics.median(times), 2)
        rows = len(ref) if ref is not None else 0
        out[f"{qn}_rows"] = rows
        # A query that matches nothing is fast, and looks like a result. This
        # guard exists because the wide-tag arm renames the first tag column
        # (host -> hostname) and a stale filter would have returned zero rows
        # at high speed rather than failing.
        if rows == 0:
            raise SystemExit(
                f"ABORT: {qn} returned 0 rows (TS_TAGS={N_TAGS}, filter column "
                f"{TAG0!r}); a zero-row query is not a fast query")
    b.close()
    # Stamp the wheel actually installed in this container. The TS overlay was
    # the one results directory feeding a published table with no version
    # recorded anywhere, and a cell whose version is not in the row is a cell
    # nothing can check later: T5's server build cell was wrong for exactly a
    # year of that reason. Key name matches the sparse lane (`engine_version`)
    # so one audit can read every overlay.
    try:
        from importlib.metadata import version as _pkgver
        out["engine_version"] = _pkgver("arcadedb-embedded")
    except Exception as e:  # never lose a completed run over provenance
        out["engine_version"] = f"unknown ({e.__class__.__name__})"
    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        with open(outp, "w") as f:
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
