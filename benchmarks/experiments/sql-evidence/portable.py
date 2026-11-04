"""SQLite and PostgreSQL engines for the portability check (README, section "Portability of the sql arm").

Shared by score_portability.py (the `sql` arm's generations) and gold_check.py --portability (the `sql` golds). Host side:
SQLite is the standard library `sqlite3` (a file under the run directory), PostgreSQL is the official image
(`postgres:18.6` by default, one container with a unique name on a random free loopback port, `--rm`, removed on every
exit path) reached with psycopg 3 (`uv run --with 'psycopg[binary]==3.3.7'`). Nothing here builds or pulls anything except
that one pinned official image when it is missing.

Same rows: the eight tables of engine_runner.DUCK_DDL are created with the same DDL text on both engines and filled from the
same ldbc_subset rows as the DuckDB arm (engine_runner.DUCK_SRC). Only PRIMARY KEY indexes exist (no index on any foreign
key), as on DuckDB; ANALYZE runs once after the load. Table names are created unquoted, so PostgreSQL folds them to lower
case: a query that writes a quoted mixed-case name ("Person") fails there, and is counted as that engine's failure.
Fingerprints (row count, sum of every integer column, non-null count and summed length of every text column) are taken per
table on all three engines and must be identical, and the counts must equal the source row counts.

Read-only and bounded: the first-word screen of engine_runner.screen is applied to every query; SQLite is reopened
`mode=ro` with `PRAGMA query_only=ON` and a progress handler that interrupts at the statement timeout; the PostgreSQL
session has `default_transaction_read_only=on` and `statement_timeout`. Results are fetched at most engine_runner.ROW_CAP + 1
rows (PostgreSQL through a server-side cursor), so a runaway result is never pulled in full; a result above the cap is
`truncated` and never matches, exactly as on DuckDB.
"""
import atexit
import json
import os
import pathlib
import random
import signal
import socket
import subprocess
import sys
import time

import engine_runner as er

DUCK_DDL, DUCK_SRC, ROW_CAP = er.DUCK_DDL, er.DUCK_SRC, er.ROW_CAP
POSTGRES_IMAGE = os.environ.get("SQLEV_POSTGRES_IMAGE", "postgres:18.6")
PG_PASSWORD = "sqlev-Pass-2026"  # a throwaway container bound to 127.0.0.1 only
INT_TYPES = ("BIGINT", "INTEGER")


def pin_cpus(cpuset):
    """Pin this process to the cores of a cpuset string such as '14,15' (the host-side engines run in this process)."""
    cpus = set()
    for part in cpuset.split(","):
        lo, _, hi = part.partition("-")
        cpus.update(range(int(lo), int(hi or lo) + 1))
    try:
        os.sched_setaffinity(0, cpus)
    except OSError as e:
        sys.exit(f"cannot pin to cores {cpuset}: {e}")


def _columns(table):
    return [tuple(part.split()[:2]) for part in DUCK_DDL[table].split(", ")]


def fingerprint_sql(table):
    parts = ["count(*)"]
    for col, ty in _columns(table):
        if ty in INT_TYPES:
            parts.append(f"sum({col})")
        else:
            parts += [f"count({col})", f"sum(length({col}))"]
    return f"SELECT {', '.join(parts)} FROM {table}"


def duck_fingerprint_jobs():
    """Jobs to append to a DuckDB engine_runner run so its tables can be fingerprinted too."""
    return [{"key": f"__fp__::{t}", "arm": "sql", "query": fingerprint_sql(t)} for t in DUCK_DDL]


def _ints(row):
    return [None if v is None else int(v) for v in row]


class SqliteEngine:
    name = "sqlite"

    def __init__(self, data, path, timeout):
        import sqlite3
        self.sqlite3 = sqlite3
        self.timeout = timeout
        self.version = f"sqlite {sqlite3.sqlite_version}"
        self.deadline = None
        self.timed_out = False
        if os.path.exists(path):
            os.remove(path)
        rw = sqlite3.connect(path)
        for table, cols in DUCK_DDL.items():
            rw.execute(f"CREATE TABLE {table}({cols})")
            marks = ",".join("?" * len(_columns(table)))
            rw.executemany(f"INSERT INTO {table} VALUES ({marks})", data[DUCK_SRC[table]])
        rw.commit()
        rw.execute("ANALYZE")
        rw.commit()
        rw.close()
        uri = pathlib.Path(path).resolve().as_uri() + "?mode=ro"
        self.cx = sqlite3.connect(uri, uri=True)
        self.cx.execute("PRAGMA query_only=ON")
        self.cx.set_progress_handler(self._tick, 10000)

    def _tick(self):
        if self.deadline is not None and time.time() > self.deadline:
            self.timed_out = True
            return 1
        return 0

    def fingerprint(self):
        out = {}
        for t in DUCK_DDL:
            out[t] = _ints(self.cx.execute(fingerprint_sql(t)).fetchone())
        return out

    def run(self, arm, query):
        t0 = time.time()
        why = er.screen(arm, query)
        if why:
            return er.failed(why, t0, parse_ok=False)
        self.timed_out = False
        self.deadline = t0 + self.timeout
        cur = None
        try:
            cur = self.cx.execute(query.strip().rstrip(";"))
            rows = cur.fetchmany(ROW_CAP + 1)
            return er.finish(rows, t0)
        except Exception as e:  # noqa: BLE001
            if self.timed_out:
                return er.failed(f"timeout after {self.timeout}s", t0, parse_ok=True)
            return er.failed(f"{type(e).__name__}: {e}", t0)
        finally:
            self.deadline = None
            if cur is not None:
                cur.close()


def _free_port():
    for _ in range(200):
        port = random.randint(20000, 39999)
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise RuntimeError("no free loopback port found")


def _docker(args, check=True):
    r = subprocess.run(["docker"] + args, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"docker {' '.join(args[:2])} failed: {r.stderr.strip()[:400]}")
    return r


class PostgresEngine:
    """One throwaway PostgreSQL container, loaded and queried over psycopg 3. Use as a context manager."""
    name = "postgres"

    def __init__(self, data, timeout, cpuset="14,15", mem="2g", image=None):
        self.data = data
        self.timeout = timeout
        self.cpuset = cpuset
        self.mem = mem
        self.image = image or POSTGRES_IMAGE
        self.container = None
        self.cx = None

    def _dsn(self):
        return f"host=127.0.0.1 port={self.port} user=postgres password={PG_PASSWORD} dbname=postgres"

    def _connect(self):
        self.cx = self.psycopg.connect(
            self._dsn(), autocommit=False,
            options=f"-c statement_timeout={int(self.timeout * 1000)} -c default_transaction_read_only=on")

    def cleanup(self):
        if self.cx is not None:
            try:
                self.cx.close()
            except Exception:  # noqa: BLE001
                pass
            self.cx = None
        if self.container:
            _docker(["rm", "-f", self.container], check=False)
            self.container = None

    def __enter__(self):
        import psycopg
        self.psycopg = psycopg
        r = _docker(["image", "inspect", "--format", "{{.Id}}", self.image], check=False)
        if r.returncode != 0:
            _docker(["pull", "-q", self.image])  # the official pinned tag
            r = _docker(["image", "inspect", "--format", "{{.Id}}", self.image])
        self.image_id = r.stdout.strip()
        d = _docker(["image", "inspect", "--format", "{{index .RepoDigests 0}}", self.image], check=False)
        self.image_digest = d.stdout.strip() if d.returncode == 0 else "none"
        self.port = _free_port()
        self.container = f"sqlev-pg-{os.getpid()}-{int(time.time())}"
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        _docker(["run", "-d", "--rm", "--name", self.container, "--cpuset-cpus", self.cpuset, "-m", self.mem,
                 "--memory-swap", self.mem, "--shm-size", "512m", "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
                 "-p", f"127.0.0.1:{self.port}:5432", self.image])
        deadline = time.time() + 120
        while True:
            try:
                psycopg.connect(self._dsn(), connect_timeout=3).close()
                break
            except psycopg.OperationalError:
                if time.time() > deadline:
                    sys.exit(f"postgres container {self.container} not ready after 120 s")
                time.sleep(1)
        self._load()
        self._connect()
        cur = self.cx.cursor()
        cur.execute("SHOW transaction_read_only")
        ro = cur.fetchone()[0]
        cur.execute("SHOW statement_timeout")
        st = cur.fetchone()[0]
        self.cx.rollback()
        if ro != "on":
            sys.exit(f"postgres session is not read-only (transaction_read_only={ro})")
        self.session = {"transaction_read_only": ro, "statement_timeout": st}
        return self

    def __exit__(self, *exc):
        self.cleanup()
        return False

    def _load(self):
        with self.psycopg.connect(self._dsn(), autocommit=True) as cx:
            cur = cx.cursor()
            for table, cols in DUCK_DDL.items():
                cur.execute(f"CREATE TABLE {table}({cols})")
                with cur.copy(f"COPY {table} FROM STDIN") as cp:
                    for row in self.data[DUCK_SRC[table]]:
                        cp.write_row(row)
            cur.execute("ANALYZE")
            cur.execute("SELECT version()")
            self.version = cur.fetchone()[0]
            self.settings = {}
            for name in ("server_version", "shared_buffers", "work_mem", "max_parallel_workers_per_gather"):
                cur.execute(f"SHOW {name}")
                self.settings[name] = cur.fetchone()[0]

    def fingerprint(self):
        out = {}
        cur = self.cx.cursor()
        for t in DUCK_DDL:
            cur.execute(fingerprint_sql(t))
            out[t] = _ints(cur.fetchone())
        self.cx.rollback()
        return out

    def _reset(self):
        try:
            self.cx.rollback()
        except Exception:  # noqa: BLE001
            pass
        if self.cx.closed:
            self._connect()

    def run(self, arm, query):
        t0 = time.time()
        why = er.screen(arm, query)
        if why:
            return er.failed(why, t0, parse_ok=False)
        sql = query.strip().rstrip(";")
        try:
            cur = self.cx.cursor()
            cur.execute("DECLARE sqlev_c NO SCROLL CURSOR FOR " + sql)  # a server-side cursor: only ROW_CAP + 1 rows travel
            cur.execute(f"FETCH FORWARD {ROW_CAP + 1} FROM sqlev_c")
            rows = cur.fetchall()
            self.cx.rollback()
            return er.finish(rows, t0)
        except Exception as e:  # noqa: BLE001
            state = getattr(e, "sqlstate", None)
            self._reset()
            if state == "57014":
                r = er.failed(f"timeout after {self.timeout}s (statement_timeout)", t0, parse_ok=True)
            else:
                r = er.failed(f"{type(e).__name__}[{state}]: {str(e).strip()}", t0)
            r["sqlstate"] = state
            return r


def _run_jobs(engine, jobs, label):
    results = []
    for j in jobs:
        r = engine.run(j["arm"], j["query"])
        r.update(key=j["key"], arm=j["arm"])
        results.append(r)
        print(f"[{label}] {j['key']} parse={r['parse_ok']} exec={r['exec_ok']} rows={r['n_rows']} ms={r['ms']}", flush=True)
    return results


def run_extra_engines(data, jobs, work_dir, timeout, cpuset="14,15", pg_mem="2g", pg_image=None, tag="port"):
    """Run `jobs` ([{key, arm: 'sql', query}]) on SQLite, then on PostgreSQL. Returns
    {"sqlite": {...}, "postgres": {...}} each with version, fingerprints and results."""
    os.makedirs(work_dir, exist_ok=True)
    out = {}
    sq = SqliteEngine(data, os.path.join(work_dir, f"sqlite_{tag}.db"), timeout)
    out["sqlite"] = {"version": sq.version, "fingerprints": sq.fingerprint(), "results": _run_jobs(sq, jobs, "sqlite")}
    with PostgresEngine(data, timeout, cpuset, pg_mem, pg_image) as pg:
        out["postgres"] = {"version": pg.version, "image": pg.image, "image_id": pg.image_id, "image_digest": pg.image_digest,
                           "settings": pg.settings, "session": pg.session, "fingerprints": pg.fingerprint(),
                           "results": _run_jobs(pg, jobs, "postgres")}
    return out


def check_loaded(data, duck_results, extra):
    """Every table must hold the same rows on all three engines (fingerprints equal) and the counts must equal the source
    row counts. `duck_results` maps key -> result and holds the __fp__ jobs of duck_fingerprint_jobs(). Exits on a
    difference; returns {"counts": {table: n}, "fingerprints": {engine: {table: [...]}}}."""
    fps = {"duckdb": {}, "sqlite": extra["sqlite"]["fingerprints"], "postgres": extra["postgres"]["fingerprints"]}
    errs = []
    for t in DUCK_DDL:
        r = duck_results.get(f"__fp__::{t}")
        if not r or not r["exec_ok"] or not r["rows"]:
            errs.append(f"{t}: duckdb fingerprint failed: {r and r['error']}")
            continue
        fps["duckdb"][t] = _ints(r["rows"][0])
    counts = {}
    for t in DUCK_DDL:
        want = len(data[DUCK_SRC[t]])
        counts[t] = want
        for eng, fp in fps.items():
            got = fp.get(t)
            if got is None or got[0] != want:
                errs.append(f"{t}: {eng} holds {None if got is None else got[0]} rows, source has {want}")
        if len({json.dumps(fp.get(t)) for fp in fps.values()}) != 1:
            errs.append(f"{t}: fingerprints differ: {json.dumps({e: fp.get(t) for e, fp in fps.items()})}")
    if errs:
        sys.exit("loaded rows differ between engines:\n  " + "\n  ".join(errs))
    return {"counts": counts, "fingerprints": fps}
