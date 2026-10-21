#!/usr/bin/env python3
"""Example 28: Python functions in SQL and openCypher, and record event callbacks.

Two things no query language can express:
- db.register_function() makes a Python function callable from SQL and openCypher
- db.on() runs a Python callback when a record is created, updated, or deleted

Workflow covered:
- register `slugify` and call it in SELECT and WHERE (SQL), and as `py.slugify` from openCypher
- see an exception in the function arrive as a query error
- measure the cost of one call (a plain SQL expression against the same expression in Python)
- keep an audit trail with after_create / after_update / after_delete callbacks
- veto a write with a before_create callback that returns False
- remove a callback and unregister a function

Notes:
- No data download; a few seconds end to end.
- The engine registers functions for the whole process, and a Database removes the ones
  it registered when it closes.
"""

from __future__ import annotations

import argparse
import re
import shutil
import time

import arcadedb_embedded as arcadedb


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rows", type=int, default=20_000, help="rows for the cost check")
    p.add_argument("--db-path", default="./my_test_databases/python_functions_events")
    return p.parse_args()


def slugify(text):
    """NULL in, NULL out: the engine passes SQL NULL as None."""
    if text is None:
        return None
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def show_functions(db) -> None:
    print("\n== Python functions ==")
    with db.transaction():
        for name in ("Ann Lee", "Bob O'Ray", None):
            db.command("sql", "INSERT INTO Person SET name = ?", name)
        db.command("sql", "CREATE VERTEX City SET name = 'New York'")

    db.register_function("slugify", slugify)
    # openCypher accepts a namespaced name for functions it does not know
    db.register_function("py.slugify", slugify)

    rows = db.query("sql", "SELECT name, slugify(name) AS slug FROM Person").to_list()
    for row in rows:
        print(f"  SELECT   {row['name']!r:14} -> {row['slug']!r}")

    hits = db.query("sql", "SELECT name FROM Person WHERE slugify(name) = 'ann-lee'")
    print("  WHERE    matches:", [row["name"] for row in hits.to_list()])

    cypher = "MATCH (c:City) RETURN py.slugify(c.name) AS slug"
    print("  openCypher:", db.query("opencypher", cypher).to_list())

    def explode(value):
        raise ValueError(f"cannot handle {value!r}")

    db.register_function("explode", explode)
    try:
        db.query("sql", "SELECT explode(name) FROM Person").to_list()
    except arcadedb.ArcadeDBError as e:
        print("  an exception in the function is a query error:\n   ", e)

    db.unregister_function("explode")


def measure_call_cost(db, rows: int) -> None:
    print("\n== Cost of one call ==")
    with db.transaction():
        for i in range(rows):
            db.command("sql", "INSERT INTO Number SET n = ?", i)
    db.register_function("plus_one", lambda n: n + 1)

    def best_of(statement: str, runs: int = 5) -> float:
        best = float("inf")
        for _ in range(runs):
            start = time.perf_counter()
            db.query("sql", statement).to_list()
            best = min(best, time.perf_counter() - start)
        return best

    with_function = best_of("SELECT plus_one(n) AS m FROM Number")
    plain_sql = best_of("SELECT n + 1 AS m FROM Number")
    per_call_us = (with_function - plain_sql) / rows * 1e6
    print(
        f"  {rows} rows: plus_one(n) {with_function * 1e3:.0f} ms, n + 1 {plain_sql * 1e3:.0f} ms"
    )
    print(
        f"  about {per_call_us:.1f} microseconds per Python call (one JNI round trip each)"
    )
    db.unregister_function("plus_one")


def show_events(db) -> None:
    print("\n== Record events ==")
    audit = []

    def record_event(event):
        def callback(record):
            audit.append((event, record.get_type_name(), record.get("name")))

        return callback

    handles = [
        db.on(event, record_event(event), "Account")
        for event in ("after_create", "after_update", "after_delete")
    ]

    def no_blank_names(record):
        return bool(record.get("name"))  # False vetoes the write

    veto = db.on("before_create", no_blank_names, "Account")

    with db.transaction():
        db.command("sql", "INSERT INTO Account SET name = 'acme'")
        db.command("sql", "INSERT INTO Account SET name = ''")  # vetoed, skipped
        db.command("sql", "UPDATE Account SET name = 'acme inc' WHERE name = 'acme'")
        db.command("sql", "DELETE FROM Account WHERE name = 'acme inc'")

    for entry in audit:
        print("  audit:", entry)
    print("  accounts left:", db.count_type("Account"))

    for handle in handles + [veto]:
        handle.remove()
    with db.transaction():
        db.command("sql", "INSERT INTO Account SET name = 'after removal'")
    print("  audit entries after remove():", len(audit))


def main() -> None:
    args = parse_args()
    shutil.rmtree(args.db_path, ignore_errors=True)
    with arcadedb.create_database(args.db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE Person")
        db.command("sql", "CREATE DOCUMENT TYPE Number")
        db.command("sql", "CREATE DOCUMENT TYPE Account")
        db.command("sql", "CREATE VERTEX TYPE City")
        show_functions(db)
        measure_call_cost(db, args.rows)
        show_events(db)


if __name__ == "__main__":
    main()
