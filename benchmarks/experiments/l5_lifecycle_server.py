#!/usr/bin/env python3
"""Lifecycle on the SERVER: the served twin of l5_lifecycle.py (2026-09-07).

The embedded lane asks what opening and closing a database costs, per
situation, from a process that owns the engine. A server is a running process,
so the twin question is what OPENING AND CLOSING A DATABASE ON THE SERVER
costs, over HTTP, for the same situations at the same sizes: POST
/api/v1/server {"command": "open database lc"} ... action ... {"command":
"close database lc"}. The situations are built with l5_lifecycle's own
generators (`_bulk`, `_vectors`, `_sparse`) through an HTTP shim, so the data
is identical to the byte; only the transport differs.

Columns kept: <mode>_open_ms / _action_ms / _close_ms / _session_ms for the
same modes. JVM start, first open and cold process are the embedded process's
own costs and are null here: there is no process to start.
"""
import json
import os
import statistics as st
import time

import l5_lifecycle as L

DB = "lc"


class HttpDb:
    """Enough of the embedded Database surface for l5_lifecycle's generators:
    command() buffers into SQLSCRIPT batches flushed at commit(), query() is
    immediate. Everything runs against database `lc` on the server."""

    def __init__(self, base, session):
        self.base, self.rq, self.buf = base, session, []

    # A 10M vector index build over one HTTP command takes the better part of
    # an hour; the 900 s default timed out the served lc10m vector cell
    # (2026-09-08). Build-time posts get four hours; queries keep 900 s.
    def _post(self, kind, command, language="sql", timeout=14400):
        r = self.rq.post(f"{self.base}/{kind}/{DB}",
                         json={"language": language, "command": command}, timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def begin(self):
        pass

    def commit(self):
        if self.buf:
            self._post("command", ";".join(self.buf), "sqlscript")
            self.buf = []

    def command(self, language, text):
        if language != "sql":
            return self._post("command", text, language)
        self.buf.append(text)
        if len(self.buf) >= 2000:
            self.commit()

    def command_now(self, language, text):
        self.commit()
        return self._post("command", text, language)

    def query(self, language, text):
        self.commit()
        return self._post("query", text, language, timeout=900)


def server_cmd(rq, root, command):
    r = rq.post(f"{root}/api/v1/server", json={"command": command}, timeout=900)
    if r.status_code >= 400 and "already" not in r.text and "not exist" not in r.text and "does not exist" not in r.text:
        r.raise_for_status()
    return r


def build(db, situation, n):
    c = db.command_now
    c("sql", "CREATE DOCUMENT TYPE Scratch")
    c("sql", "CREATE PROPERTY Scratch.n INTEGER")
    if situation == "empty":
        pass
    elif situation == "doc":
        c("sql", "CREATE DOCUMENT TYPE D")
        c("sql", "CREATE PROPERTY D.id INTEGER")
        L._bulk(db, "INSERT INTO D SET id = %d", n)
    elif situation == "doc_idx10":
        c("sql", "CREATE DOCUMENT TYPE D")
        for i in range(10):
            c("sql", f"CREATE PROPERTY D.p{i} INTEGER")
            c("sql", f"CREATE INDEX ON D (p{i}) NOTUNIQUE")
        L._bulk(db, "INSERT INTO D SET " + ", ".join(f"p{i} = %d" for i in range(10)), n, nargs=10)
    elif situation in ("graph", "graph_gav"):
        c("sql", "CREATE VERTEX TYPE P")
        c("sql", "CREATE PROPERTY P.id INTEGER")
        c("sql", "CREATE EDGE TYPE E")
        c("sql", "CREATE INDEX ON P (id) UNIQUE")
        L._bulk(db, "CREATE VERTEX P SET id = %d", n)
        for i in range(n):
            for f in range(1, 5):
                db.command("sql", f"CREATE EDGE E FROM (SELECT FROM P WHERE id = {i}) "
                                  f"TO (SELECT FROM P WHERE id = {(i + f * 7919) % n})")
        db.commit()
        c("sql", "DROP INDEX `P[id]`")
        if situation == "graph_gav":
            c("sql", "CREATE GRAPH ANALYTICAL VIEW lcv VERTEX TYPES (P) EDGE TYPES (E) PROPERTIES (id) UPDATE MODE OFF")
            L._await_gav(db)
    elif situation == "vector":
        c("sql", "CREATE VERTEX TYPE V")
        c("sql", "CREATE PROPERTY V.id INTEGER")
        c("sql", "CREATE PROPERTY V.emb ARRAY_OF_FLOATS")
        L._vectors(db, n)
        c("sql", f'CREATE INDEX ON V (emb) LSM_VECTOR METADATA {{ "dimensions": {L.DIM}, "similarity": "COSINE" }}')
    elif situation == "sparse":
        c("sql", "CREATE DOCUMENT TYPE S")
        c("sql", "CREATE PROPERTY S.tokens ARRAY_OF_INTEGERS")
        c("sql", "CREATE PROPERTY S.weights ARRAY_OF_FLOATS")
        L._sparse(db, n)
        c("sql", 'CREATE INDEX ON S (tokens, weights) LSM_SPARSE_VECTOR METADATA { "dimensions": 30000 }')
    elif situation == "ts":
        c("sql", "CREATE TIMESERIES TYPE T TIMESTAMP ts TAGS (sensor STRING) FIELDS (value DOUBLE)")
        build_ts(db, n)
    else:
        raise SystemExit(f"unknown situation {situation}")


def build_ts(db, n):
    # _bulk's template is `tmpl % i`; the embedded lane writes 1_700_000_000_000 + i*1000.
    db.begin()
    for i in range(n):
        db.command("sql", f"INSERT INTO T SET ts = {1_700_000_000_000 + i * 1000}, sensor = 's0', value = 1.0")
    db.commit()


_SEQ = [0]


def _read(db, situation):
    if situation == "empty":
        return
    if situation == "vector":
        v = ", ".join("0.5" for _ in range(L.DIM))
        db.query("sql", f"SELECT FROM (SELECT expand(vectorNeighbors('V[emb]', [{v}], 10)))")
        return
    q = L.READS.get(situation)
    if q:
        db.query(*q)


def _write(db, situation):
    _SEQ[0] += 1
    db.command_now("sql", f"INSERT INTO Scratch SET n = {_SEQ[0]}")


def _write_own(db, situation):
    _SEQ[0] += 1
    i = 10_000_000 + _SEQ[0]
    if situation == "vector":
        v = ", ".join("0.25" for _ in range(L.DIM))
        stmt = f"INSERT INTO V SET id = {i}, emb = [{v}]"
    elif situation in ("graph", "graph_gav"):
        stmt = f"INSERT INTO P SET id = {i}"
    elif situation == "doc":
        stmt = f"INSERT INTO D SET id = {i}"
    elif situation == "doc_idx10":
        stmt = "INSERT INTO D SET " + ", ".join(f"p{k} = {i + k}" for k in range(10))
    elif situation == "sparse":
        toks = ", ".join(str(1 + 7 * k) for k in range(16))
        wts = ", ".join("0.25" for _ in range(16))
        stmt = f"INSERT INTO S SET tokens = [{toks}], weights = [{wts}]"
    elif situation == "ts":
        stmt = f"INSERT INTO T SET ts = {1_800_000_000_000 + i}, sensor = 's0', value = 1.0"
    else:
        stmt = f"INSERT INTO Scratch SET n = {i}"
    db.command_now("sql", stmt)


def cycle(rq, root, db, situation, mode):
    t0 = time.perf_counter()
    server_cmd(rq, root, f"open database {DB}").raise_for_status()
    t1 = time.perf_counter()
    if mode == "read":
        _read(db, situation)
    elif mode == "write":
        _write(db, situation)
    elif mode == "write_read":
        _write(db, situation); _read(db, situation)
    elif mode == "write_own":
        _write_own(db, situation)
    elif mode == "write_own_read":
        _write_own(db, situation); _read(db, situation)
    t2 = time.perf_counter()
    server_cmd(rq, root, f"close database {DB}").raise_for_status()
    t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000, (t2 - t1) * 1000


def measure(rq, root, db, situation, mode):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        a, b, act = cycle(rq, root, db, situation, mode)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def main(args):
    import requests
    rq = requests.Session()
    rq.auth = ("root", "dbbenchpass")
    host = os.environ["BENCH_SERVER_HOST"]
    port = os.environ.get("BENCH_SERVER_PORT", "2480")
    root = f"http://{host}:{port}"
    base = f"{root}/api/v1"
    try:
        info = rq.get(f"{base}/server", timeout=30)
        version = "server:" + (info.json().get("version") or "?")
    except Exception:  # noqa: BLE001
        version = "server:unknown"
    n = L.SCALE_ROWS[args.scale]
    out = {"situation": args.workload, "n_rows": n, "engine_version": version,
           "deployment": "server", "import_ms": None, "jvm_start_ms": None,
           "first_open_ms": None, "cold_process_ms": None}
    server_cmd(rq, root, f"drop database {DB}")
    server_cmd(rq, root, f"create database {DB}").raise_for_status()
    db = HttpDb(base, rq)
    t = time.perf_counter()
    build(db, args.workload, n)
    out["build_s"] = round(time.perf_counter() - t, 2)
    _bt = time.perf_counter()
    server_cmd(rq, root, f"close database {DB}").raise_for_status()
    out["build_close_ms"] = round((time.perf_counter() - _bt) * 1000, 3)
    # First open after the build's close: the served analogue of first_open.
    _ft = time.perf_counter()
    server_cmd(rq, root, f"open database {DB}").raise_for_status()
    out["first_open_server_ms"] = round((time.perf_counter() - _ft) * 1000, 3)
    server_cmd(rq, root, f"close database {DB}").raise_for_status()
    for mode in L.MODES:
        o, c, w = measure(rq, root, db, args.workload, mode)
        out[f"{mode}_open_ms"], out[f"{mode}_close_ms"], out[f"{mode}_action_ms"] = round(o, 3), round(c, 3), round(w, 3)
        out[f"{mode}_session_ms"] = round(o + w + c, 3)
    out["close_over_budget"] = out.get("clean_close_ms", 0) > 100.0
    server_cmd(rq, root, f"open database {DB}")
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(json.dumps({k: v for k, v in out.items() if k.endswith("_session_ms") or k in ("build_s", "first_open_server_ms")}), flush=True)
