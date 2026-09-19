#!/usr/bin/env python3
"""Lifecycle on SurrealDB embedded: the comparator arm of l5_lifecycle.py (2026-09-16).

DECISIONS #95a left the lifecycle table with one engine and said why: the lane
times a PROCESS opening and closing an embedded database, which only ArcadeDB
and SurrealDB on this page can do at all. This is the SurrealDB arm, through
the same Python SDK and the same SurrealKV disk store the other SurrealDB
embedded arms use (surreal_common; SDK 2.0.0 carrying core 2.3.10), and the
same durability string those arms record (DECISIONS #90).

WHAT IS THE SAME, so a row here reads against an ArcadeDB row above it:
  the situations, their sizes and generators (the same 7919 fan-out, the same
  seeded vectors), the session (open + action + close, timed as three spans),
  the mode set INCLUDING the stale-reopen cycles of the embedded lane (this is
  an embedded arm, so a previous session's commit is a real thing to arrive
  at), the cold column after a verified page-cache eviction, and the cold
  start measured in a fresh subprocess. The read of each situation returns the
  same answer as the ArcadeDB read and is digested under DECISIONS #88; the
  doc, doc_idx10, graph, and ts reads agree with the ArcadeDB embedded arm to
  the digest, which is how "the same session" is proven rather than asserted.

WHAT IS NOT, stated here rather than hidden in a column name:
  jvm_start_ms is None. There is no JVM; the SurrealDB core is a compiled
  extension the `import surrealdb` loads, so import_ms is the analogue and
  first_open_ms is the first open with the SDK already imported.
  ts is a plain table of timestamped records, the footing l4_tsbs.SurrealTS
  already runs on: SurrealDB has no time-series type (DEFINE TABLE ... TYPE
  accepts NORMAL, RELATION, or ANY, and the parser says so).
  graph_gav and sparse are DECLARED, not built: SurrealDB has no graph
  analytical view and no sparse-vector index type, by its documentation and
  by the parser's own error, which the row carries verbatim (DECISIONS #92).
  The cell exits clean with the declaration and no session numbers; the
  table prints the reason.

Every SurrealQL statement this arm issues is in this file, by situation, so
the COMPARATOR-DIALECTS.md section can be written from it.
"""
import json
import os
import statistics as st
import subprocess
import sys
import time
import types

import bench_common
import pagecache
import surreal_common

import l5_lifecycle as L

# Beside the ArcadeDB database, on the same bind mount (see L._assert_fs and
# runner.LC_HOST_DIR): a cold open needs a real filesystem to be evicted from.
DB = "/lcdb/lc_surreal"
URL = f"surrealkv://{DB}"
NS = DBNAME = "bench"
DIM = L.DIM
# The dense lane's matched HNSW operating point (l3d_dense.EF_CONSTRUCTION,
# COMPARATOR_M, EF_SEARCH), typed here rather than imported: importing the
# dense lane pulls in numpy and three comparator drivers for three integers.
EF_CONSTRUCTION, HNSW_M, EF_SEARCH = 100, 16, 100
FANOUT = 4          # edges per vertex in the graph situations, as in L.build
INGEST_BATCH = 5_000

# The documentation each declaration cites (DECISIONS #92).
DOC_DEFINE_INDEX = "https://surrealdb.com/docs/surrealql/statements/define/indexes"
DOC_DEFINE = "https://surrealdb.com/docs/surrealql/statements/define"
DOC_DEFINE_TABLE = "https://surrealdb.com/docs/surrealql/statements/define/table"
DOC_KNN = "https://surrealdb.com/docs/surrealql/operators"

# THE STATEMENTS TRIED for the situations this engine cannot build. Each is
# issued against the open store so the row carries the parser's exact error
# rather than an opinion that it would fail.
UNEXPRESSIBLE_PROBES = {
    "sparse": (
        "DEFINE INDEX s_tw ON S FIELDS tokens, weights SPARSE_VECTOR DIMENSION 30000",
        f"no sparse-vector index type: DEFINE INDEX offers standard, unique, "
        f"composite, count, full-text, HNSW, and DISKANN (this core also accepts "
        f"MTREE), and every vector form indexes one field holding a dense array "
        f"of numbers of a fixed DIMENSION ({DOC_DEFINE_INDEX}); the knn operator "
        f"takes one dense array ({DOC_KNN})"),
    "graph_gav": (
        "DEFINE ANALYTICAL VIEW lcv ON P",
        f"no graph analytical view: DEFINE has no statement that materialises a "
        f"graph for traversal ({DOC_DEFINE}); a table view (DEFINE TABLE ... AS "
        f"SELECT) pre-computes one query's result table, not an adjacency layout "
        f"({DOC_DEFINE_TABLE})"),
}
TS_NOTE = ("plain table of timestamped records: SurrealDB has no time-series "
           "type (DEFINE TABLE ... TYPE accepts NORMAL, RELATION, or ANY), the "
           "footing l4_tsbs.SurrealTS runs on")


def _rows(res):
    """The SDK returns a list for SELECT, a scalar for RETURN, and a list of
    {result} blocks for a multi-statement script; one shape out."""
    if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
        res = res[-1]["result"]
    return res if isinstance(res, list) else ([res] if res is not None else [])


def _rm(p):
    import shutil
    if os.path.isdir(p):
        shutil.rmtree(p)


def _open():
    from surrealdb import Surreal
    db = Surreal(URL)
    db.use(NS, DBNAME)
    return db


def _insert(db, table, docs):
    for i in range(0, len(docs), INGEST_BATCH):
        db.insert(table, docs[i:i + INGEST_BATCH])


def _rid(table, i):
    from surrealdb import RecordID   # a string id would become a string key
    return RecordID(table, i)


def _vector_docs(n):
    import random
    rnd = random.Random(17)              # L._vectors' seed and draw order
    return [{"id": _rid("V", i), "vid": i,
             "emb": [round(rnd.random(), 6) for _ in range(DIM)]} for i in range(n)]


def build(situation, n):
    """Create the database for `situation` at `n` rows, then close it.

    Returns (build session close ms, engine stamp). Raises Unexpressible for
    the situations this engine cannot build, carrying the parser's error.
    """
    _rm(DB)
    db = _open()
    stamp = surreal_common.engine_stamp(db)
    q = db.query
    # The scratch table, defined up front in every situation: an undefined
    # table is created implicitly by its first CREATE, which would put a
    # schema change inside the timed write.
    q("DEFINE TABLE scratch SCHEMALESS")
    if situation == "empty":
        pass
    elif situation == "doc":
        q("DEFINE TABLE D SCHEMALESS")
        _insert(db, "D", [{"id": _rid("D", i), "did": i} for i in range(n)])
    elif situation == "doc_idx10":
        q("DEFINE TABLE D SCHEMALESS")
        # Index BEFORE the load, as the TPC arm does (2026-09-13): on SurrealKV a
        # DEFINE INDEX over loaded rows is one transaction record.
        for i in range(10):
            q(f"DEFINE INDEX D_p{i} ON D FIELDS p{i}")
        _insert(db, "D", [dict({"id": _rid("D", i)}, **{f"p{k}": i for k in range(10)})
                          for i in range(n)])
    elif situation == "graph":
        q("DEFINE TABLE P SCHEMALESS; DEFINE TABLE E TYPE RELATION IN P OUT P SCHEMALESS")
        _insert(db, "P", [{"id": _rid("P", i), "pid": i} for i in range(n)])
        # insert_relation, not RELATE statements (l2_graph.SurrealGraph): the
        # same fan-out and targets as L.build's CREATE EDGE loop.
        edges = [{"in": _rid("P", i), "out": _rid("P", (i + f * 7919) % n)}
                 for i in range(n) for f in range(1, FANOUT + 1)]
        for i in range(0, len(edges), INGEST_BATCH):
            db.insert_relation("E", edges[i:i + INGEST_BATCH])
    elif situation == "vector":
        # Index BEFORE the load, as the dense arm does; the matched HNSW
        # operating point, COSINE like the ArcadeDB situation's LSM_VECTOR.
        q(f"DEFINE INDEX v_emb ON V FIELDS emb HNSW DIMENSION {DIM} DIST COSINE "
          f"TYPE F32 EFC {EF_CONSTRUCTION} M {HNSW_M}")
        _insert(db, "V", _vector_docs(n))
    elif situation == "ts":
        q("DEFINE TABLE T SCHEMALESS")
        _insert(db, "T", [{"ts": 1_700_000_000_000 + i * 1000, "sensor": "s0", "value": 1.0}
                          for i in range(n)])
    elif situation in UNEXPRESSIBLE_PROBES:
        stmt, why = UNEXPRESSIBLE_PROBES[situation]
        try:
            q(stmt)
        except Exception as e:  # noqa: BLE001 - the error IS the evidence
            db.close()
            raise Unexpressible(f"{why}; tried `{stmt}` and the engine answered: "
                                f"{_first_line(e)}") from None
        db.close()
        raise SystemExit(f"{situation}: {stmt!r} was accepted; the declaration "
                         f"in UNEXPRESSIBLE_PROBES is wrong and must be re-read")
    else:
        raise SystemExit(f"unknown situation {situation}")
    _bt = time.perf_counter()
    db.close()
    return (time.perf_counter() - _bt) * 1000, stamp


class Unexpressible(Exception):
    pass


def _first_line(e):
    """The parser's message with its position, without the caret drawing."""
    text = str(e).replace("There was a problem with the database: ", "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = lines[0] if lines else text
    pos = next((ln for ln in lines[1:] if ln.startswith("-->")), "")
    return f"{type(e).__name__}: {head}" + (f" {pos}" if pos else "")


# THE READS, one per situation, each returning the same answer as L.READS'
# ArcadeDB statement so the #88 digest can compare them (a dict row is
# digested by its values in key order, so the column name is free).
#
#   doc / ts    a count of the table: [{"n": N}] against [{"count(*)": N}]
#   doc_idx10   the ten indexed fields of the row where p0 = 5
#   graph       the ArcadeDB read expands out('E') from P and stops at 100
#               expanded rows, which at FANOUT 4 is 25 source vertices: the
#               same 25 vertices, 100 edges walked, 100 neighbour records
#               fetched, counted
#   vector      the knn operator over the HNSW index, k=10 at EF_SEARCH; not
#               digested (approximate), like the ArcadeDB vector read
READS = {
    "doc":       "SELECT count() AS n FROM D GROUP ALL",
    "doc_idx10": "SELECT " + ", ".join(f"p{i}" for i in range(10)) + " FROM D WHERE p0 = 5 LIMIT 10",
    "graph":     (f"SELECT count() AS n FROM array::flatten((SELECT VALUE ->E->P FROM P "
                  f"LIMIT {100 // FANOUT})) GROUP ALL"),
    "ts":        "SELECT count() AS n FROM T GROUP ALL",
}
_LAST_READ = {"rows": None, "situation": None}
_WRITE_SEQ = [0]


def _read(db, situation):
    if situation == "empty":
        return
    if situation == "vector":
        v = ", ".join("0.5" for _ in range(DIM))
        _rows(db.query(f"SELECT vid FROM V WHERE emb <|10,{EF_SEARCH}|> [{v}]"))
        return
    text = READS.get(situation)
    if text:
        _LAST_READ["rows"] = _rows(db.query(text))   # plain dicts already
        _LAST_READ["situation"] = situation


def _write(db, situation):
    """One record into scratch, in every situation (L._write)."""
    _WRITE_SEQ[0] += 1
    db.query(f"CREATE scratch SET n = {_WRITE_SEQ[0]}")


def _write_own(db, situation):
    """Write into the situation's OWN structure (L._write_own)."""
    _WRITE_SEQ[0] += 1
    i = 10_000_000 + _WRITE_SEQ[0]
    if situation == "vector":
        v = ", ".join("0.25" for _ in range(DIM))
        db.query(f"CREATE V:{i} SET vid = {i}, emb = [{v}]")
    elif situation == "graph":
        db.query(f"CREATE P:{i} SET pid = {i}")
    elif situation == "doc":
        db.query(f"CREATE D:{i} SET did = {i}")
    elif situation == "doc_idx10":
        cols = ", ".join(f"p{k} = {i + k}" for k in range(10))
        db.query(f"CREATE D:{i} SET {cols}")
    elif situation == "ts":
        db.query(f"CREATE T SET ts = {1_800_000_000_000 + i}, sensor = 's0', value = 1.0")
    else:
        db.query(f"CREATE scratch SET n = {i}")


def _drop(db, situation):
    if situation == "vector":
        db.query("REMOVE INDEX v_emb ON TABLE V")


def cycle(situation, mode, cold=False):
    """One open/close cycle: (open_ms, close_ms, action_ms), as L.cycle."""
    if cold:
        pagecache.evict(DB)      # raises if pages survive: no fabricated cold column
    t0 = time.perf_counter()
    db = _open()
    t1 = time.perf_counter()
    if mode == "read":
        _read(db, situation)
    elif mode == "write":
        _write(db, situation)
    elif mode == "write_read":
        _write(db, situation)
        _read(db, situation)
    elif mode == "write_own":
        _write_own(db, situation)
    elif mode == "write_own_read":
        _write_own(db, situation)
        _read(db, situation)
    elif mode == "drop":
        _drop(db, situation)
    t2 = time.perf_counter()
    db.close()
    t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000, (t2 - t1) * 1000


def measure(situation, mode, cold=False):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        a, b, act = cycle(situation, mode, cold=cold)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def measure_stale(situation, mode):
    """Re-dirty before every cycle, as L.measure_stale (2026-08-25)."""
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        cycle(situation, "write_own")
        a, b, act = cycle(situation, mode)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def _cold_process():
    """Interpreter start, SDK import, first open, close, in a FRESH process.

    The same span L.main times for ArcadeDB. There is no runtime to start
    apart from the import: the compiled core comes up with the module.
    """
    _boot = subprocess.run(
        [sys.executable, "-c",
         "import time; _t0 = time.perf_counter()\n"
         "from surrealdb import Surreal\n"
         "_ti = time.perf_counter()\n"
         "db = Surreal(%r); db.use(%r, %r)\n"
         "_to = time.perf_counter()\n"
         "db.close()\n"
         "print('%%.3f %%.3f %%.3f' %% ((_ti-_t0)*1000, (_to-_ti)*1000, "
         "(time.perf_counter()-_t0)*1000))" % (URL, NS, DBNAME)],
        capture_output=True, text=True, timeout=900)
    if _boot.returncode == 0 and _boot.stdout.strip():
        return tuple(float(x) for x in _boot.stdout.strip().split()[-3:])
    sys.stderr.write("cold-start subprocess failed (rc=%s); cold columns will be null\n%s\n"
                     % (_boot.returncode, (_boot.stderr or "")[-2000:]))
    return None, None, None


def _base_row(args, n, fs, build_s, stamp):
    out = bench_common.run_conditions(
        lane="lifecycle", backend=args.backend, workload=args.workload,
        scale=args.scale, n_rows=n, dims=DIM, fs_type=fs,
        lc_iters=L.ITERS, lc_warmup=L.WARMUP, build_s=build_s)
    # The engine, not the SDK that carries it (BUGS F39). run_conditions
    # reads the ArcadeDB wheel's version, which this image does not have.
    out["engine_version"] = stamp or surreal_common.engine_stamp()
    out["deployment"] = "embedded"
    out["store"] = "surrealkv"
    # DECISIONS #81/#90: the string the other SurrealDB embedded arms record,
    # at the class this cell asked for; SURREAL_SYNC_DATA was set before the
    # store opened (apply_durability in main).
    bench_common.stamp_durability(
        out, bench_common.at_class(bench_common.DURABILITY_SURREAL_EMBEDDED))
    out["instrument"] = bench_common.INSTRUMENT
    out["cold_warm_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    out["cold_first_query_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    surreal_common.stamp_reconnects(
        out, types.SimpleNamespace(name=args.backend, db=None))   # in-process: 0
    return out


def main(args):
    fs = L._assert_fs()
    n = L.SCALE_ROWS[args.scale]
    surreal_common.apply_durability()      # before the first Surreal(...) call

    t0 = time.perf_counter()
    try:
        build_close_ms, stamp = build(args.workload, n)
    except Unexpressible as e:
        # DECLARED, NOT SKIPPED (DECISIONS #88, #92): the row exists, says
        # why there is no session number, and exits clean.
        out = _base_row(args, n, fs, round(time.perf_counter() - t0, 3), None)
        out["lifecycle_situation_unexpressible"] = str(e)
        bench_common.record_unexpressible(out, "lifecycle_read", str(e))
        _rm(DB)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(out, open(args.out, "w"), indent=1)
        print(f"RESULT {json.dumps(out)[:400]}")
        return
    build_s = round(time.perf_counter() - t0, 3)

    import_ms, first_open_ms, cold_proc_ms = _cold_process()

    out = _base_row(args, n, fs, build_s, stamp)
    if args.workload == "ts":
        out["ts_type"] = TS_NOTE
    if args.workload == "vector":
        out["hnsw_M"], out["ef_construction"], out["ef_search"] = HNSW_M, EF_CONSTRUCTION, EF_SEARCH
        out["k"] = 10
    o, c, w = measure(args.workload, "clean", cold=True)
    out["cold_open_ms"], out["cold_close_ms"] = round(o, 3), round(c, 3)
    out["build_close_ms"] = round(build_close_ms, 3)
    _r3 = lambda x: None if x is None else round(x, 3)
    out["import_ms"] = _r3(import_ms)            # interpreter + SDK import (loads the core)
    out["jvm_start_ms"] = None                   # no JVM; see the module docstring
    out["runtime_start_na"] = ("no JVM: the SurrealDB core is a compiled extension "
                               "loaded by the import, so import_ms is the runtime start")
    out["first_open_ms"] = _r3(first_open_ms)    # first open, SDK already imported
    out["cold_process_ms"] = _r3(cold_proc_ms)   # what a CLI actually waits for
    out["cold_process_cache_state"] = "warm-page-cache"

    for mode in L.MODES:
        o, c, w = measure(args.workload, mode)
        out[f"{mode}_open_ms"] = round(o, 3)
        out[f"{mode}_close_ms"] = round(c, 3)
        out[f"{mode}_action_ms"] = round(w, 3)
        out[f"{mode}_session_ms"] = round(o + w + c, 3)
    out["cold_start_penalty_ms"] = None if out["cold_process_ms"] is None else round(
        max(0.0, out["cold_process_ms"] - (out["clean_open_ms"] + out["clean_close_ms"])), 3)

    if "write_own" in L.MODES:
        o, c, w = measure_stale(args.workload, "clean")
        out["stale_open_ms"], out["stale_close_ms"] = round(o, 3), round(c, 3)
        o, c, w = measure_stale(args.workload, "read")
        out["stale_read_open_ms"], out["stale_read_close_ms"] = round(o, 3), round(c, 3)
        out["stale_read_action_ms"] = round(w, 3)
        out["stale_read_session_ms"] = round(o + w + c, 3)
        out["stale_redirties_every_cycle"] = True

    if args.workload == "vector" and "drop" not in os.environ.get("BENCH_LC_SKIP", ""):
        o, c, w = cycle(args.workload, "drop")
        out["drop_open_ms"], out["drop_close_ms"] = round(o, 3), round(c, 3)
        out["drop_action_ms"] = round(w, 3)
        out["drop_is_single_cycle"] = True

    # THE READ'S ANSWER (DECISIONS #88), after the cycles have run.
    if args.workload == "vector":
        bench_common.record_unexpressible(
            out, "lifecycle_read",
            "the vector situation's read goes through an approximate index; "
            "it is checked by recall on the dense lane, not by an exact digest")
    elif _LAST_READ["rows"] is not None:
        bench_common.record_result(out, "lifecycle_read", _LAST_READ["rows"])
        out["lifecycle_read_situation"] = _LAST_READ["situation"]
    else:
        bench_common.record_unexpressible(
            out, "lifecycle_read",
            f"situation {args.workload!r} issues no read in the modes this cell ran")
    out["close_over_budget"] = out["clean_close_ms"] > 100.0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")
