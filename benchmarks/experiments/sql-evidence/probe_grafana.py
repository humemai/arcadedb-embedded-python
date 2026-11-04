"""Grafana steps over its HTTP API (stdlib only): datasource health check, then /api/ds/query.

  python probe_grafana.py BASE_URL DATASOURCE_UID USER PASSWORD
list_tables and list_columns send the information_schema queries Grafana's query builder sends. Grafana has no
server-side parameters: the parameterized step interpolates a dashboard-variable value into the text (note says so).
"""
import base64
import json
import sys
import urllib.error
import urllib.request

import pgsteps

base, uid, user, pw = sys.argv[1:5]
AUTH = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def call(path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


status, props = call("/api/frontend/settings")
ver = "grafana " + str((props.get("buildInfo") or {}).get("version", "?"))


def query(sql):
    code, doc = call("/api/ds/query", {"from": "now-1h", "to": "now", "queries": [
        {"refId": "A", "datasource": {"uid": uid}, "rawSql": sql, "format": "table"}]})
    res = (doc.get("results") or {}).get("A") or {}
    if code != 200 or res.get("error"):
        raise RuntimeError(res.get("error") or doc.get("message") or f"http {code}")
    values = [col for fr in res.get("frames", []) for col in (fr.get("data") or {}).get("values", [])]
    if not values or not values[0]:
        raise AssertionError("no rows returned")
    return values


def step(name, fn, note=None):
    try:
        fn()
        pgsteps.emit("grafana", ver, name, True, note=note)
    except Exception as e:  # noqa: BLE001
        pgsteps.emit("grafana", ver, name, False, f"{type(e).__name__}: {e}", note=note)


def health():
    code, doc = call(f"/api/datasources/uid/{uid}/health")
    if code != 200 or doc.get("status") != "OK":
        raise RuntimeError(doc.get("message") or f"http {code}")


def tables():
    names = query(pgsteps.LIST_TABLES_INFO_SCHEMA)[0]
    if not pgsteps.has_person(names):
        raise AssertionError(f"Person not in {names[:10]}")


step("connect", health)
step("list_tables", tables)
step("list_columns", lambda: query(pgsteps.LIST_COLUMNS_INFO_SCHEMA))
step("select", lambda: query(pgsteps.SQL["select"]))
step("select_param", lambda: query(pgsteps.PARAM_SQL.format(ph=str(pgsteps.PARAM_VALUE))), note="dashboard variable interpolated into the text; no server-side parameter")
step("join", lambda: query(pgsteps.SQL["join"]))
step("group_by", lambda: query(pgsteps.SQL["group_by"]))
