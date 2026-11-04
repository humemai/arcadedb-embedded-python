"""Load the LDBC subset into one engine and run a list of queries against it. Runs INSIDE a container
(gold_check.py, score.py and score_portability.py start it through dockerrun.py): the duckdb engine in the harness's
`sqlev:duckdb-2.0.0` image (docker/duckdb.Dockerfile), the arcadedb engine in the campaign's `dbbench:arcadedb-<version>`.
Standard library plus the engine's own package only.

  python engine_runner.py --engine duckdb|arcadedb --data DIR --jobs jobs.json --out out.json
                          [--person-limit N] [--timeout S] [--heap 2g] [--partial part.jsonl]

jobs.json: {"jobs": [{"key": str, "arm": "sql"|"pgq"|"cypher"|"arcadedb_sql", "query": str}, ...]}
out.json:  {"engine": ..., "engine_version": ..., "engine_versions": {"duckdb": ..., "duckpgq": ...}, "load_s": ...,
            "counts": {...}, "results": [{"key", "arm", "parse_ok", "exec_ok", "error", "rows", "n_rows", "truncated", "ms"}]}
--partial: JSON lines flushed to disk as the run goes, a header line ({"header": {...the out.json fields but results}})
           after the load and one result line per job. dockerrun.py reads it after the container exits, so a container
           that is killed (OOM, signal) mid-run still tells which jobs reported and which one was in flight.

Definitions (README "Scoring"):
  parse_ok  false when the engine's error text names a parse/syntax failure, or the query is rejected before
            running (not a single read-only statement). Heuristic, applied the same way to every arm.
  exec_ok   the query ran to completion and returned rows (an empty result is exec_ok true).
Only single read-only statements run: SELECT/WITH/FROM for SQL arms, MATCH/OPTIONAL/WITH/UNWIND/RETURN for
Cypher, SELECT/MATCH/TRAVERSE for ArcadeDB SQL. A query that hangs past --timeout is recorded as a timeout; on
ArcadeDB the worker thread cannot be killed, so it is abandoned and the process exits hard at the end.
"""
import argparse
import concurrent.futures
import csv
import datetime
import decimal
import json
import os
import re
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldbc_subset  # noqa: E402

ROW_CAP = 200
PARSE_RE = re.compile(r"parse|parsing|syntax|unexpected token|mismatched input|no viable alternative|extraneous input", re.I)
ALLOWED_FIRST = {
    "sql": {"select", "with", "from"},
    "pgq": {"select", "with", "from"},
    "cypher": {"match", "optional", "with", "unwind", "return"},
    "arcadedb_sql": {"select", "match", "traverse"},
}
ARMS_OF_ENGINE = {"duckdb": ("sql", "pgq"), "arcadedb": ("cypher", "arcadedb_sql")}

DUCK_DDL = {
    "Person": "id BIGINT PRIMARY KEY, first_name VARCHAR, last_name VARCHAR, gender VARCHAR, birth_year INTEGER, creation_year INTEGER, city_id BIGINT",
    "City": "id BIGINT PRIMARY KEY, name VARCHAR, country_id BIGINT",
    "Country": "id BIGINT PRIMARY KEY, name VARCHAR",
    "Forum": "id BIGINT PRIMARY KEY, title VARCHAR, moderator_id BIGINT",
    "Tag": "id BIGINT PRIMARY KEY, name VARCHAR, tagclass_id BIGINT",
    "TagClass": "id BIGINT PRIMARY KEY, name VARCHAR",
    "Knows": "person1_id BIGINT, person2_id BIGINT, since_year INTEGER",
    "HasInterest": "person_id BIGINT, tag_id BIGINT",
}
DUCK_SRC = {"Person": "person", "City": "city", "Country": "country", "Forum": "forum", "Tag": "tag",
            "TagClass": "tagclass", "Knows": "knows", "HasInterest": "hasinterest"}

PGQ_DDL = """CREATE PROPERTY GRAPH g
VERTEX TABLES (Person, City, Country, Forum, Tag, TagClass)
EDGE TABLES (
  Knows SOURCE KEY (person1_id) REFERENCES Person (id) DESTINATION KEY (person2_id) REFERENCES Person (id),
  HasInterest SOURCE KEY (person_id) REFERENCES Person (id) DESTINATION KEY (tag_id) REFERENCES Tag (id),
  LocatedIn SOURCE KEY (person_id) REFERENCES Person (id) DESTINATION KEY (city_id) REFERENCES City (id),
  PartOf SOURCE KEY (city_id) REFERENCES City (id) DESTINATION KEY (country_id) REFERENCES Country (id),
  HasModerator SOURCE KEY (forum_id) REFERENCES Forum (id) DESTINATION KEY (person_id) REFERENCES Person (id),
  HasType SOURCE KEY (tag_id) REFERENCES Tag (id) DESTINATION KEY (tagclass_id) REFERENCES TagClass (id))"""


def jsonable(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def screen(arm, query):
    """None when the query may run, else the reason it is rejected."""
    q = re.sub(r"--[^\n]*", " ", query or "")
    q = re.sub(r"/\*.*?\*/", " ", q, flags=re.S).strip()
    q = q.rstrip(";").strip()
    if not q:
        return "empty query"
    if ";" in q:
        return "not a single statement"
    first = re.split(r"\W+", q, maxsplit=1)[0].lower()
    if first not in ALLOWED_FIRST[arm]:
        return f"not a read-only {arm} statement (starts with {first!r})"
    return None


def finish(rows_raw, t0):
    rows = [jsonable(r) for r in rows_raw[:ROW_CAP]]
    return {"parse_ok": True, "exec_ok": True, "error": None, "rows": rows, "n_rows": len(rows_raw),
            "truncated": len(rows_raw) > ROW_CAP, "ms": round((time.time() - t0) * 1000, 1)}


def failed(err, t0, parse_ok=None):
    if parse_ok is None:
        parse_ok = not PARSE_RE.search(err or "")
    return {"parse_ok": parse_ok, "exec_ok": False, "error": (err or "")[:600], "rows": [], "n_rows": 0,
            "truncated": False, "ms": round((time.time() - t0) * 1000, 1)}


# ------------------------------------------------------------------ DuckDB
class DuckEngine:
    name = "duckdb"

    def __init__(self, data, need_pgq, timeout):
        import duckdb
        self.timeout = timeout
        self.cx = {}
        self.cx["sql"] = self._build(duckdb, data, pgq=False)
        if need_pgq:
            self.cx["pgq"] = self._build(duckdb, data, pgq=True)
            pgq_version = self._pgq_version(self.cx["pgq"])
        else:
            # The versions are recorded in every output, also when no pgq job runs: read them from a throwaway connection.
            try:
                pgq_version = self._pgq_version(self._connect(duckdb, pgq=True))
            except Exception as e:  # noqa: BLE001
                pgq_version = f"unavailable ({type(e).__name__})"
        self.versions = {"duckdb": duckdb.__version__, "duckpgq": pgq_version}
        self.version = f"duckdb {duckdb.__version__} + duckpgq {pgq_version}"

    @staticmethod
    def _pgq_version(cx):
        """The extension version the running engine reports (not a number written down in a document)."""
        ext = cx.execute("SELECT extension_version FROM duckdb_extensions() "
                         "WHERE extension_name = 'duckpgq' AND loaded").fetchall()
        return ext[0][0] if ext else "?"

    def _connect(self, duckdb, pgq):
        cx = duckdb.connect(":memory:")
        if pgq:
            ext_dir = os.environ.get("SQLEV_DUCKDB_EXT_DIR")
            if ext_dir:
                # sqlev:duckdb-2.0.0 has DuckPGQ baked in at image build time (docker/duckdb.Dockerfile): LOAD only, so a
                # missing or wrong extension fails loudly and nothing is downloaded in the cell.
                cx.execute(f"SET extension_directory='{ext_dir}'")
                cx.execute("LOAD duckpgq")
            else:
                cx.execute("INSTALL duckpgq FROM community; LOAD duckpgq;")
        return cx

    def _build(self, duckdb, data, pgq):
        cx = self._connect(duckdb, pgq)
        cx.execute(f"PRAGMA threads={len(os.sched_getaffinity(0))}")
        cx.execute("SET memory_limit='3GB'")
        with tempfile.TemporaryDirectory() as td:
            for table, cols in DUCK_DDL.items():
                cx.execute(f"CREATE TABLE {table}({cols})")
                path = os.path.join(td, table + ".csv")
                with open(path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerows(data[DUCK_SRC[table]])
                cx.execute(f"COPY {table} FROM '{path}' (FORMAT csv, HEADER false)")
        if pgq:
            cx.execute("CREATE TABLE LocatedIn AS SELECT id AS person_id, city_id FROM Person")
            cx.execute("CREATE TABLE PartOf AS SELECT id AS city_id, country_id FROM City")
            cx.execute("CREATE TABLE HasModerator AS SELECT id AS forum_id, moderator_id AS person_id FROM Forum")
            cx.execute("CREATE TABLE HasType AS SELECT id AS tag_id, tagclass_id FROM Tag")
            cx.execute(PGQ_DDL)
        return cx

    def run(self, arm, query):
        t0 = time.time()
        why = screen(arm, query)
        if why:
            return failed(why, t0, parse_ok=False)
        cx = self.cx[arm]
        timer = threading.Timer(self.timeout, cx.interrupt)
        timer.start()
        try:
            rows = cx.execute(query.strip().rstrip(";")).fetchall()
            return finish(rows, t0)
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            if "interrupt" in msg.lower():
                return failed(f"timeout after {self.timeout}s", t0, parse_ok=True)
            return failed(msg, t0)
        finally:
            timer.cancel()


# ------------------------------------------------------------------ ArcadeDB
class ArcadeEngine:
    name = "arcadedb"
    VERTS = {
        "Person": [("id", "LONG"), ("firstName", "STRING"), ("lastName", "STRING"), ("gender", "STRING"),
                   ("birthYear", "INTEGER"), ("creationYear", "INTEGER")],
        "City": [("id", "LONG"), ("name", "STRING")],
        "Country": [("id", "LONG"), ("name", "STRING")],
        "Forum": [("id", "LONG"), ("title", "STRING")],
        "Tag": [("id", "LONG"), ("name", "STRING")],
        "TagClass": [("id", "LONG"), ("name", "STRING")],
    }

    def __init__(self, data, timeout, heap):
        import arcadedb_embedded as arcadedb
        self.timeout = timeout
        self.db = arcadedb.create_database(os.path.join(tempfile.mkdtemp(prefix="sqlev_arcade_"), "db"),
                                           jvm_kwargs={"heap_size": heap})
        self.version = f"arcadedb {arcadedb.__version__}"
        self.versions = {"arcadedb": arcadedb.__version__}
        for t, props in self.VERTS.items():
            self.db.command("sql", f"CREATE VERTEX TYPE {t}")
            for p, ty in props:
                self.db.command("sql", f"CREATE PROPERTY {t}.{p} {ty}")
            self.db.command("sql", f"CREATE INDEX ON {t} (id) UNIQUE")
        for et in ("KNOWS", "IS_LOCATED_IN", "IS_PART_OF", "HAS_MODERATOR", "HAS_INTEREST", "HAS_TYPE"):
            self.db.command("sql", f"CREATE EDGE TYPE {et}")
        self.db.command("sql", "CREATE PROPERTY KNOWS.sinceYear INTEGER")
        self._load(data)

    def _load(self, d):
        rows = {
            "Person": [{"id": r[0], "firstName": r[1], "lastName": r[2], "gender": r[3], "birthYear": r[4],
                        "creationYear": r[5]} for r in d["person"]],
            "City": [{"id": r[0], "name": r[1]} for r in d["city"]],
            "Country": [{"id": r[0], "name": r[1]} for r in d["country"]],
            "Forum": [{"id": r[0], "title": r[1]} for r in d["forum"]],
            "Tag": [{"id": r[0], "name": r[1]} for r in d["tag"]],
            "TagClass": [{"id": r[0], "name": r[1]} for r in d["tagclass"]],
        }
        n_edges = len(d["knows"]) + len(d["person"]) + len(d["city"]) + len(d["forum"]) + len(d["hasinterest"]) + len(d["tag"])
        rid = {t: {} for t in rows}
        with self.db.graph_batch(use_wal=True, expected_edge_count=n_edges) as gb:
            for t, rs in rows.items():
                for s in range(0, len(rs), 10000):
                    chunk = rs[s:s + 10000]
                    for rec, r in zip(chunk, gb.create_vertices(t, chunk)):
                        rid[t][rec["id"]] = r

            def edges(etype, src_t, dst_t, pairs, props=None):
                pairs = [(a, b, p) for (a, b, p) in pairs if a in rid[src_t] and b in rid[dst_t]]
                for s in range(0, len(pairs), 10000):
                    ch = pairs[s:s + 10000]
                    gb.new_edges([rid[src_t][a] for a, _, _ in ch], etype, [rid[dst_t][b] for _, b, _ in ch],
                                 [p for _, _, p in ch] if props else None)

            edges("KNOWS", "Person", "Person", [(a, b, {"sinceYear": y}) for a, b, y in d["knows"]], props=True)
            edges("IS_LOCATED_IN", "Person", "City", [(p[0], p[6], None) for p in d["person"]])
            edges("IS_PART_OF", "City", "Country", [(c[0], c[2], None) for c in d["city"]])
            edges("HAS_MODERATOR", "Forum", "Person", [(f[0], f[2], None) for f in d["forum"]])
            edges("HAS_INTEREST", "Person", "Tag", [(p, t, None) for p, t in d["hasinterest"]])
            edges("HAS_TYPE", "Tag", "TagClass", [(t[0], t[2], None) for t in d["tag"]])

    def _exec(self, arm, query):
        lang = "opencypher" if arm == "cypher" else "sql"
        return self.db.query(lang, query).to_json_list()

    def run(self, arm, query):
        t0 = time.time()
        why = screen(arm, query)
        if why:
            return failed(why, t0, parse_ok=False)
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(self._exec, arm, query.strip().rstrip(";"))
        try:
            recs = fut.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError:
            ex.shutdown(wait=False)
            return failed(f"timeout after {self.timeout}s", t0, parse_ok=True)
        except Exception as e:  # noqa: BLE001
            ex.shutdown(wait=False)
            return failed(f"{type(e).__name__}: {e}", t0)
        ex.shutdown(wait=False)
        rows = []
        for r in recs:
            if isinstance(r, dict):
                rows.append([v for k, v in r.items() if not str(k).startswith("@")])
            else:
                rows.append([r])
        return finish(rows, t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=sorted(ARMS_OF_ENGINE))
    ap.add_argument("--data", required=True)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--person-limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--heap", default="2g")
    ap.add_argument("--partial", default=None)
    a = ap.parse_args()

    jobs = json.load(open(a.jobs))["jobs"]
    arms = ARMS_OF_ENGINE[a.engine]
    bad = [j["key"] for j in jobs if j["arm"] not in arms]
    if bad:
        sys.exit(f"jobs for another engine: {bad[:3]}")
    t0 = time.time()
    data = ldbc_subset.load(a.data, a.person_limit)
    if a.engine == "duckdb":
        eng = DuckEngine(data, any(j["arm"] == "pgq" for j in jobs), a.timeout)
    else:
        eng = ArcadeEngine(data, a.timeout, a.heap)
    load_s = round(time.time() - t0, 1)
    out = {"engine": a.engine, "engine_version": eng.version, "engine_versions": eng.versions, "load_s": load_s,
           "person_limit": a.person_limit, "counts": ldbc_subset.counts(data), "results": []}
    part = open(a.partial, "w") if a.partial else None

    def emit(obj):
        if part:
            part.write(json.dumps(obj) + "\n")
            part.flush()
            os.fsync(part.fileno())

    emit({"header": {k: v for k, v in out.items() if k != "results"}})
    for j in jobs:
        r = eng.run(j["arm"], j["query"])
        r.update(key=j["key"], arm=j["arm"])
        out["results"].append(r)
        emit(r)
        print(f"{j['key']} parse={r['parse_ok']} exec={r['exec_ok']} rows={r['n_rows']} ms={r['ms']}", flush=True)
    with open(a.out, "w") as f:
        json.dump(out, f)
    sys.stdout.flush()
    os._exit(0)  # abandoned ArcadeDB worker threads must not keep the container alive


if __name__ == "__main__":
    main()
