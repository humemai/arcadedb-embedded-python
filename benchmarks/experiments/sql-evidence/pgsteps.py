"""Shared step definitions for the Postgres-wire tool matrix (README Part B). Standard library only."""
import json

TABLE = "Person"
SQL = {
    "select": "SELECT id, name FROM Person ORDER BY id LIMIT 5",
    "join": "SELECT p.name, c.name AS city FROM Person p JOIN City c ON p.city_id = c.id WHERE p.id < 10",
    "group_by": "SELECT city_id, count(*) AS n FROM Person GROUP BY city_id ORDER BY n DESC LIMIT 5",
}
PARAM_SQL = "SELECT id, name FROM Person WHERE id = {ph}"
PARAM_VALUE = 7
LIST_TABLES_INFO_SCHEMA = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
LIST_COLUMNS_INFO_SCHEMA = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'Person'"


def emit(client, version, step, ok, error=None, note=None):
    rec = {"client": client, "client_version": version, "step": step, "ok": bool(ok),
           "error": None if ok or error is None else str(error)[:400]}
    if note:
        rec["note"] = note
    print(json.dumps(rec), flush=True)


def has_person(names):
    return any(str(n).lower() == "person" for n in names)
