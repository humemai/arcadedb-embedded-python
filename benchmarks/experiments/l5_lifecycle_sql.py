#!/usr/bin/env python3
"""Lifecycle on SQLite and DuckDB, embedded: comparator arms of l5_lifecycle.py (2026-10-02).

DECISIONS #131 item 5 (CAMPAIGN.md section 7 row 40, queued last by #133): each
embedded engine on the page runs the lifecycle workloads its model supports.
This module is the two in-process SQL engines the page already runs, through
their own Python packages: SQLite (stdlib sqlite3, WAL with synchronous=NORMAL
as on every SQLite arm, DECISIONS #70) and DuckDB 1.5.4 (the pinned
dbbench:duckdb image, its thread pool fitted to the cpuset, FAIRNESS F6).

WHAT IS THE SAME as l5_lifecycle_surreal.py, so a row reads against the
ArcadeDB row above it: the situations, sizes, and generators (the same 7919
fan-out, the same seeded vectors), the session timed as open + action +
close, the mode set including the stale-reopen cycles, the cold column after
a verified page-cache eviction, the cold start in a fresh subprocess, and
each read's answer digested under DECISIONS #88 (doc, doc_idx10, graph, and
ts answer what the ArcadeDB and SurrealDB reads answer). The build streams its
input in batches, never as one list (BUGS F161).

WHAT EACH ENGINE CAN EXPRESS:
  SQLite   empty, doc, doc_idx10, ts (a plain table). graph, graph_gav,
           vector, and sparse are DECLARED: SQLite has no graph query language
           (the graph tables require one, DECISIONS #128), and its core has no
           vector or sparse index (sqlite-vec is its own engine on the dense
           table, with its own arm).
  DuckDB   empty, doc, doc_idx10, ts (a plain table), vector (the VSS
           extension's HNSW, persisted, the dense table's DuckDB arm), graph
           (a DuckPGQ property graph over the vertex and edge tables, read
           with GRAPH_TABLE, as the graph table's DuckPGQ arm). graph_gav and
           sparse are DECLARED: no analytical graph view, no sparse index.
A declaration carries the engine's own error for the statement that would
have built it (DECISIONS #92), and the cell exits clean without session
numbers; the table prints the reason.
"""
import json
import os
import random
import statistics as st
import subprocess
import sys
import time

import bench_common
import pagecache

import l5_lifecycle as L

DIM = L.DIM
FANOUT = 4                  # edges per vertex in the graph situation, as in L.build
INGEST_BATCH = 5_000
HNSW_M, EF_CONSTRUCTION = 16, 100   # the dense lane's matched operating point
DUCKPGQ_DOC = "https://duckdb.org/docs/stable/core_extensions/duckpgq"

READS = {   # every engine's read of a situation returns the same answer
    "doc": "SELECT count(*) AS n FROM D",
    "doc_idx10": "SELECT " + ", ".join(f"p{i}" for i in range(10)) + " FROM D WHERE p0 = 5 LIMIT 10",
    "ts": "SELECT count(*) AS n FROM T",
}
# The graph read: one hop out of the first 100 // FANOUT vertices, which is the
# 100 records L.READS["graph"] and the SurrealDB arm count.
GRAPH_READ_DUCKPGQ = (f"SELECT count(*) AS n FROM GRAPH_TABLE (lcg MATCH (a:P)-[e:E]->(b:P) "
                      f"WHERE a.id < {100 // FANOUT} COLUMNS (b.id AS bid))")


class Unexpressible(Exception):
    pass


def _first_line(e):
    return str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__


class Engine:
    name = "?"
    db_path = "?"
    durability = None

    def connect(self):
        raise NotImplementedError

    def version(self):
        raise NotImplementedError

    def unexpressible(self):   # situation -> (statement tried, why[, setup statements])
        return {}


class SQLiteEngine(Engine):
    name = "sqlite"
    db_path = "/lcdb/lc_sqlite.db"
    durability = bench_common.DURABILITY_SQLITE

    def connect(self):
        import sqlite3
        cx = sqlite3.connect(self.db_path, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        return cx

    def version(self):
        import sqlite3
        return f"sqlite {sqlite3.sqlite_version}"

    def unexpressible(self):
        return {
            "graph": ("SELECT * FROM GRAPH_TABLE (g MATCH (a)-[e]->(b) COLUMNS (b.id))",
                      "no graph query language: the graph situations need one (DECISIONS #128), and SQLite's "
                      "SQL has no GRAPH_TABLE, MATCH, or property graph"),
            "graph_gav": ("SELECT * FROM GRAPH_TABLE (g MATCH (a)-[e]->(b) COLUMNS (b.id))",
                          "no graph query language and no analytical graph view (DECISIONS #128)"),
            "vector": ("CREATE VIRTUAL TABLE v USING vec0(emb float[64])",
                       "no vector index in SQLite's core: sqlite-vec is a separate engine with its own arm on "
                       "the dense table, not part of the SQLite this arm runs"),
            "sparse": ("CREATE VIRTUAL TABLE s USING vec0(emb float[30000])",
                       "no sparse-vector index in SQLite's core or in any extension this arm loads"),
        }


class DuckEngine(Engine):
    name = "duckdb"
    db_path = "/lcdb/lc_duck.db"
    durability = bench_common.DURABILITY_DUCKDB
    situation = None

    def connect(self):
        import duckdb
        cx = duckdb.connect(self.db_path)
        cx.execute(f"PRAGMA threads={len(os.sched_getaffinity(0))}")   # F6, as every DuckDB arm
        if self.situation == "vector":
            cx.execute("LOAD vss")
            cx.execute("SET hnsw_enable_experimental_persistence=true")
        elif self.situation == "graph":
            cx.execute("LOAD duckpgq")
        return cx

    def version(self):
        import duckdb
        return f"duckdb {duckdb.__version__}"

    def unexpressible(self):
        return {
            "graph_gav": ("CREATE GRAPH ANALYTICAL VIEW lcv ON P",
                          f"no analytical graph view: DuckPGQ's CREATE PROPERTY GRAPH defines a view over the "
                          f"vertex and edge tables, read by GRAPH_TABLE on each query, with no materialised "
                          f"adjacency layout ({DUCKPGQ_DOC})"),
            "sparse": ("CREATE INDEX s_idx ON S USING SPARSE (tokens, weights)",
                       "no sparse-vector index: VSS indexes fixed-size FLOAT arrays only",
                       ("CREATE TABLE S (tokens INTEGER[], weights FLOAT[])",)),
        }


ENGINES = {"sqlite_lifecycle": SQLiteEngine, "duckdb_lifecycle": DuckEngine}
_LAST_READ = {"rows": None, "situation": None}
_WRITE_SEQ = [0]


def _rm(path):
    for p in (path, path + ".wal", path + "-wal", path + "-shm"):
        if os.path.exists(p):
            os.remove(p)


def _batched(rows):
    buf = []
    for r in rows:
        buf.append(r)
        if len(buf) == INGEST_BATCH:
            yield buf
            buf = []
    if buf:
        yield buf


def _insert(eng, cx, table, ncols, rows, select=None):
    """Stream `rows` (tuples of `ncols` values) into `table`, one transaction per batch.

    Each engine's own batch path: SQLite's executemany, and for DuckDB an Arrow
    batch inserted with INSERT ... SELECT, as the time-series lane's DuckDB arm
    loads (executemany is row by row in DuckDB, hours at 10M). `select` casts
    the Arrow columns (c0, c1, ...) where the table needs it, e.g. FLOAT[64].
    """
    if eng.name == "duckdb":
        import pyarrow as pa
        expr = select or ", ".join(f"c{k}" for k in range(ncols))
        for batch in _batched(rows):
            cols = list(zip(*batch))
            cx.register("lc_batch", pa.table({f"c{k}": list(cols[k]) for k in range(ncols)}))
            cx.execute(f"INSERT INTO {table} SELECT {expr} FROM lc_batch")
            cx.unregister("lc_batch")
        return
    sql = f"INSERT INTO {table} VALUES (" + ", ".join("?" * ncols) + ")"
    for batch in _batched(rows):
        cx.execute("BEGIN")
        cx.executemany(sql, batch)
        cx.execute("COMMIT")


def _vectors(n):
    rnd = random.Random(17)              # L._vectors' seed and draw order
    for i in range(n):
        yield (i, [float("%.6f" % rnd.random()) for _ in range(DIM)])


def build(eng, situation, n):
    """Create the database for `situation` at `n` rows, then close it. Returns the build close ms."""
    _rm(eng.db_path)
    decl = eng.unexpressible().get(situation)
    if decl:
        stmt, why = decl[0], decl[1]
        cx = eng.connect()
        for setup in (decl[2] if len(decl) > 2 else ()):
            cx.execute(setup)      # the table the probe needs, so the error is about the feature
        try:
            cx.execute(stmt)
        except Exception as e:      # the engine's own words, carried on the row
            cx.close()
            raise Unexpressible(f"{why}; tried `{stmt}` and the engine answered: {_first_line(e)}")
        cx.close()
        raise SystemExit(f"{eng.name}: `{stmt}` succeeded, so the declaration for {situation!r} is wrong")
    if eng.name == "duckdb":
        eng.situation = situation
        if situation in ("vector", "graph"):
            import duckdb
            boot = duckdb.connect()
            boot.execute("INSTALL vss" if situation == "vector" else "INSTALL duckpgq FROM community")
            boot.close()
    cx = eng.connect()
    cx.execute("CREATE TABLE Scratch (n INTEGER)")
    if situation == "doc":
        cx.execute("CREATE TABLE D (id INTEGER)")
        _insert(eng, cx, "D", 1, ((i,) for i in range(n)))
    elif situation == "doc_idx10":
        cx.execute("CREATE TABLE D (" + ", ".join(f"p{i} INTEGER" for i in range(10)) + ")")
        for i in range(10):
            cx.execute(f"CREATE INDEX d_p{i} ON D (p{i})")
        _insert(eng, cx, "D", 10, ((i,) * 10 for i in range(n)))
    elif situation == "ts":
        cx.execute("CREATE TABLE T (ts BIGINT, sensor VARCHAR, value DOUBLE)")
        _insert(eng, cx, "T", 3, ((1_700_000_000_000 + i * 1000, "s0", 1.0) for i in range(n)))
    elif situation == "vector":
        cx.execute(f"CREATE TABLE V (id INTEGER, emb FLOAT[{DIM}])")
        _insert(eng, cx, "V", 2, _vectors(n), select=f"c0, c1::FLOAT[{DIM}]")
        cx.execute(f"CREATE INDEX v_emb ON V USING HNSW (emb) WITH (metric = 'cosine', M = {HNSW_M}, "
                   f"ef_construction = {EF_CONSTRUCTION})")
    elif situation == "graph":
        cx.execute("CREATE TABLE P (id INTEGER PRIMARY KEY)")
        cx.execute("CREATE TABLE E (src INTEGER, dst INTEGER)")
        _insert(eng, cx, "P", 1, ((i,) for i in range(n)))
        _insert(eng, cx, "E", 2, ((i, (i + f * 7919) % n) for i in range(n) for f in range(1, FANOUT + 1)))
        cx.execute("CREATE PROPERTY GRAPH lcg VERTEX TABLES (P) EDGE TABLES (E SOURCE KEY (src) REFERENCES P (id) "
                   "DESTINATION KEY (dst) REFERENCES P (id))")
    elif situation != "empty":
        raise SystemExit(f"unknown situation {situation}")
    t = time.perf_counter()
    cx.close()
    return (time.perf_counter() - t) * 1000


def _read(cx, situation):
    if situation == "empty":
        return
    if situation == "vector":
        v = ", ".join("0.5" for _ in range(DIM))
        cx.execute(f"SELECT id FROM V ORDER BY array_cosine_distance(emb, [{v}]::FLOAT[{DIM}]) LIMIT 10").fetchall()
        return
    text = GRAPH_READ_DUCKPGQ if situation == "graph" else READS.get(situation)
    if text:
        cur = cx.execute(text)
        cols = [d[0] for d in cur.description]
        _LAST_READ["rows"] = [dict(zip(cols, r)) for r in cur.fetchall()]
        _LAST_READ["situation"] = situation


def _write(cx, situation):
    """One row into Scratch, in every situation (L._write)."""
    _WRITE_SEQ[0] += 1
    cx.execute("BEGIN")
    cx.execute("INSERT INTO Scratch VALUES (?)", (_WRITE_SEQ[0],))
    cx.execute("COMMIT")


def _write_own(cx, situation):
    """Write into the situation's OWN structure (L._write_own)."""
    _WRITE_SEQ[0] += 1
    i = 10_000_000 + _WRITE_SEQ[0]
    cx.execute("BEGIN")
    if situation == "vector":
        cx.execute("INSERT INTO V VALUES (?, ?)", (i, [0.25] * DIM))
    elif situation == "graph":
        cx.execute("INSERT INTO P VALUES (?)", (i,))
    elif situation == "doc":
        cx.execute("INSERT INTO D VALUES (?)", (i,))
    elif situation == "doc_idx10":
        cx.execute("INSERT INTO D VALUES (" + ", ".join("?" * 10) + ")", tuple(i + k for k in range(10)))
    elif situation == "ts":
        cx.execute("INSERT INTO T VALUES (?, 's0', 1.0)", (1_800_000_000_000 + i,))
    else:
        cx.execute("INSERT INTO Scratch VALUES (?)", (i,))
    cx.execute("COMMIT")


def _drop(cx, situation):
    if situation == "vector":
        cx.execute("DROP INDEX v_emb")


def cycle(eng, situation, mode, cold=False):
    """One open/close cycle: (open_ms, close_ms, action_ms), as L.cycle."""
    if cold:
        pagecache.evict(eng.db_path)    # raises if pages survive: no fabricated cold column
    t0 = time.perf_counter()
    cx = eng.connect()
    t1 = time.perf_counter()
    if mode == "read":
        _read(cx, situation)
    elif mode == "write":
        _write(cx, situation)
    elif mode == "write_read":
        _write(cx, situation)
        _read(cx, situation)
    elif mode == "write_own":
        _write_own(cx, situation)
    elif mode == "write_own_read":
        _write_own(cx, situation)
        _read(cx, situation)
    elif mode == "drop":
        _drop(cx, situation)
    t2 = time.perf_counter()
    cx.close()
    t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000, (t2 - t1) * 1000


def measure(eng, situation, mode, cold=False):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        a, b, act = cycle(eng, situation, mode, cold=cold)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def measure_stale(eng, situation, mode):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        cycle(eng, situation, "write_own")
        a, b, act = cycle(eng, situation, mode)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def _cold_process(eng, situation):
    """Interpreter start, package import, first open, close, in a FRESH process (L.main's span)."""
    if eng.name == "sqlite":
        imp, opn = "import sqlite3", f"cx = sqlite3.connect({eng.db_path!r})"
    else:
        imp = "import duckdb"
        ext = {"vector": "; cx.execute('LOAD vss')", "graph": "; cx.execute('LOAD duckpgq')"}.get(situation, "")
        opn = f"cx = duckdb.connect({eng.db_path!r}){ext}"
    boot = subprocess.run(
        [sys.executable, "-c",
         f"import time; _t0 = time.perf_counter()\n{imp}\n_ti = time.perf_counter()\n{opn}\n"
         "_to = time.perf_counter()\ncx.close()\n"
         "print('%.3f %.3f %.3f' % ((_ti-_t0)*1000, (_to-_ti)*1000, (time.perf_counter()-_t0)*1000))"],
        capture_output=True, text=True, timeout=900)
    if boot.returncode == 0 and boot.stdout.strip():
        return tuple(float(x) for x in boot.stdout.strip().split()[-3:])
    sys.stderr.write("cold-start subprocess failed (rc=%s); cold columns will be null\n%s\n"
                     % (boot.returncode, (boot.stderr or "")[-2000:]))
    return None, None, None


def _base_row(args, eng, n, fs, build_s):
    out = bench_common.run_conditions(
        lane="lifecycle", backend=args.backend, workload=args.workload,
        scale=args.scale, n_rows=n, dims=DIM, fs_type=fs,
        lc_iters=L.ITERS, lc_warmup=L.WARMUP, build_s=build_s)
    out["engine_version"] = eng.version()      # the engine, not the ArcadeDB wheel (BUGS F39)
    out["deployment"] = "embedded"
    bench_common.stamp_durability(out, bench_common.at_class(eng.durability))
    out["instrument"] = bench_common.INSTRUMENT
    out["cold_warm_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    out["cold_first_query_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    return out


def main(args):
    fs = L._assert_fs()
    n = L.SCALE_ROWS[args.scale]
    eng = ENGINES[args.backend]()
    t0 = time.perf_counter()
    try:
        build_close_ms = build(eng, args.workload, n)
    except Unexpressible as e:
        # DECLARED, NOT SKIPPED (DECISIONS #88, #92)
        out = _base_row(args, eng, n, fs, round(time.perf_counter() - t0, 3))
        out["lifecycle_situation_unexpressible"] = str(e)
        bench_common.record_unexpressible(out, "lifecycle_read", str(e))
        _rm(eng.db_path)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(out, open(args.out, "w"), indent=1)
        print(f"RESULT {json.dumps(out)[:400]}")
        return
    build_s = round(time.perf_counter() - t0, 3)
    import_ms, first_open_ms, cold_proc_ms = _cold_process(eng, args.workload)

    out = _base_row(args, eng, n, fs, build_s)
    if args.workload == "vector":
        out["hnsw_M"], out["ef_construction"], out["k"] = HNSW_M, EF_CONSTRUCTION, 10
    if args.workload == "ts":
        out["ts_type"] = "plain table of timestamped rows: no time-series type"
    o, c, w = measure(eng, args.workload, "clean", cold=True)
    out["cold_open_ms"], out["cold_close_ms"] = round(o, 3), round(c, 3)
    out["build_close_ms"] = round(build_close_ms, 3)
    _r3 = lambda x: None if x is None else round(x, 3)   # noqa: E731
    out["import_ms"] = _r3(import_ms)
    out["jvm_start_ms"] = None
    out["runtime_start_na"] = (f"no JVM: {eng.name} is a compiled library the import loads, "
                               f"so import_ms is the runtime start")
    out["first_open_ms"] = _r3(first_open_ms)
    out["cold_process_ms"] = _r3(cold_proc_ms)
    out["cold_process_cache_state"] = "warm-page-cache"

    for mode in L.MODES:
        o, c, w = measure(eng, args.workload, mode)
        out[f"{mode}_open_ms"] = round(o, 3)
        out[f"{mode}_close_ms"] = round(c, 3)
        out[f"{mode}_action_ms"] = round(w, 3)
        out[f"{mode}_session_ms"] = round(o + w + c, 3)
    out["cold_start_penalty_ms"] = None if out["cold_process_ms"] is None else round(
        max(0.0, out["cold_process_ms"] - (out["clean_open_ms"] + out["clean_close_ms"])), 3)

    if "write_own" in L.MODES:
        o, c, w = measure_stale(eng, args.workload, "clean")
        out["stale_open_ms"], out["stale_close_ms"] = round(o, 3), round(c, 3)
        o, c, w = measure_stale(eng, args.workload, "read")
        out["stale_read_open_ms"], out["stale_read_close_ms"] = round(o, 3), round(c, 3)
        out["stale_read_action_ms"] = round(w, 3)
        out["stale_read_session_ms"] = round(o + w + c, 3)
        out["stale_redirties_every_cycle"] = True

    if args.workload == "vector" and "drop" not in os.environ.get("BENCH_LC_SKIP", ""):
        o, c, w = cycle(eng, args.workload, "drop")
        out["drop_open_ms"], out["drop_close_ms"] = round(o, 3), round(c, 3)
        out["drop_action_ms"] = round(w, 3)
        out["drop_is_single_cycle"] = True

    if args.workload == "vector":
        bench_common.record_unexpressible(
            out, "lifecycle_read",
            "the vector situation's read goes through an approximate index; "
            "it is checked by recall on the dense vector table, not by an exact digest")
    elif _LAST_READ["rows"] is not None:
        bench_common.record_result(out, "lifecycle_read", _LAST_READ["rows"])
        out["lifecycle_read_situation"] = _LAST_READ["situation"]
    else:
        bench_common.record_unexpressible(
            out, "lifecycle_read", f"situation {args.workload!r} issues no read in the modes this cell ran")
    out["close_over_budget"] = out["clean_close_ms"] > 100.0
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")
