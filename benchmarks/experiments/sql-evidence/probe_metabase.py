"""Metabase steps over its HTTP API (stdlib only): setup, add database, sync, native queries.

  python probe_metabase.py BASE_URL PG_HOST PG_PORT PG_USER PG_PASSWORD
"""
import json
import sys
import time
import urllib.error
import urllib.request

import pgsteps

base, pg_host, pg_port, pg_user, pg_pw = sys.argv[1:6]
EMAIL, MBPW = "probe@example.com", "Probe-pass-12345"
session = {}


def call(method, path, body=None, timeout=300):
    headers = {"Content-Type": "application/json"}
    if "id" in session:
        headers["X-Metabase-Session"] = session["id"]
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"message": raw[:300]}


props = call("GET", "/api/session/properties")[1]
ver = "metabase " + str((props.get("version") or {}).get("tag", "?"))
S = {}


def step(name, fn):
    try:
        fn()
        pgsteps.emit("metabase", ver, name, True)
    except Exception as e:  # noqa: BLE001
        pgsteps.emit("metabase", ver, name, False, f"{type(e).__name__}: {e}")


def setup_and_connect():
    code, doc = call("POST", "/api/setup", {"token": props["setup-token"], "user": {"first_name": "p", "last_name": "p", "email": EMAIL, "password": MBPW, "site_name": "probe"},
                                           "prefs": {"site_name": "probe", "allow_tracking": False}})
    if code != 200:
        raise RuntimeError(f"setup http {code}: {doc}")
    session["id"] = doc["id"]
    code, doc = call("POST", "/api/database", {"engine": "postgres", "name": "arcadedb", "details": {
        "host": pg_host, "port": int(pg_port), "dbname": "sqlev", "user": pg_user, "password": pg_pw, "ssl": False}, "is_full_sync": True})
    if code != 200:
        raise RuntimeError(f"add database http {code}: {doc.get('message', doc)}")
    S["db"] = doc["id"]


def metadata():
    code, doc = call("GET", f"/api/database/{S['db']}/metadata?include_hidden=true")
    return doc.get("tables", []) if code == 200 else []


def tables():
    call("POST", f"/api/database/{S['db']}/sync_schema")
    deadline = time.time() + 180
    names = []
    while time.time() < deadline:
        names = [t["name"] for t in metadata()]
        if pgsteps.has_person(names):
            return
        time.sleep(5)
    raise AssertionError(f"Person not in synced tables {names[:10]} after 180 s")


def columns():
    t = next(t for t in metadata() if t["name"].lower() == "person")
    if not t.get("fields"):
        raise AssertionError("no fields synced for Person")


def native(sql, tags=None, params=None):
    native_q = {"query": sql}
    if tags:
        native_q["template-tags"] = tags
    body = {"database": S["db"], "type": "native", "native": native_q}
    if params:
        body["parameters"] = params
    code, doc = call("POST", "/api/dataset", body)
    if code not in (200, 202) or doc.get("error") or doc.get("status") == "failed":
        raise RuntimeError(str(doc.get("error") or doc.get("message") or f"http {code}")[:300])
    if not (doc.get("data") or {}).get("rows"):
        raise AssertionError("no rows returned")


step("connect", setup_and_connect)
if "db" in S:
    step("list_tables", tables)
    step("list_columns", columns)
    step("select", lambda: native(pgsteps.SQL["select"]))
    step("select_param", lambda: native(pgsteps.PARAM_SQL.format(ph="{{pid}}"),
                                        tags={"pid": {"id": "11111111-1111-1111-1111-111111111111", "name": "pid", "display-name": "pid", "type": "number"}},
                                        params=[{"type": "number/=", "target": ["variable", ["template-tag", "pid"]], "value": [pgsteps.PARAM_VALUE]}]))
    step("join", lambda: native(pgsteps.SQL["join"]))
    step("group_by", lambda: native(pgsteps.SQL["group_by"]))
