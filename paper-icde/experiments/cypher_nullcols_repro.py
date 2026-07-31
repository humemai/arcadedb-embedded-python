#!/usr/bin/env python3
"""Minimal repro: does the openCypher surface emit the matched TYPE's declared
properties as null columns in every result row?

Observed on LDBC SF1: `RETURN DISTINCT f` yields
  {"id": null, "name": null, "age": null, "city": null, "f": {...}}
where id/name/age/city are exactly Person's declared properties, while the
equivalent SQL MATCH yields {"f": {...}} alone. 1.6x the JSON bytes for the
same rows.

Isolated here on a fresh 3-vertex database so the result cannot be blamed on
LDBC data, scale, or the harness.
"""
import json, os, sys

def main():
    import arcadedb_embedded as arcadedb
    db = arcadedb.create_database(os.path.expanduser("~/.cache/nullcols_db"),
                                  jvm_kwargs={"heap_size": "2g"})
    print("engine", arcadedb.__version__)
    for ddl in ["CREATE VERTEX TYPE Person",
                "CREATE PROPERTY Person.id LONG",
                "CREATE PROPERTY Person.name STRING",
                "CREATE PROPERTY Person.age INTEGER",
                "CREATE PROPERTY Person.city STRING",
                "CREATE INDEX ON Person (id) UNIQUE",
                "CREATE EDGE TYPE KNOWS"]:
        db.command("sql", ddl)
    db.begin()
    for i in (1, 2, 3):
        db.command("sql", f"INSERT INTO Person SET id={i}, name='n{i}', "
                          f"age={20+i}, city='c{i}'")
    db.command("sql", "CREATE EDGE KNOWS FROM (SELECT FROM Person WHERE id=1) "
                      "TO (SELECT FROM Person WHERE id=2)")
    db.commit()

    cases = [
        ("cypher whole vertex",  "opencypher",
         "MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = 1 RETURN DISTINCT f"),
        ("cypher one property",  "opencypher",
         "MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = 1 RETURN f.name"),
        ("cypher no DISTINCT",   "opencypher",
         "MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = 1 RETURN f"),
        ("cypher no edge",       "opencypher",
         "MATCH (f:Person) WHERE f.id = 1 RETURN f"),
        ("sql MATCH whole",      "sql",
         "MATCH {type: Person, as: p, where: (id = 1)}.out('KNOWS'){as: f} "
         "RETURN DISTINCT f"),
    ]
    for label, lang, q in cases:
        try:
            rows = db.query(lang, q).to_json_list()
        except Exception as e:
            print(f"  {label:22} ERROR {type(e).__name__}: {e}")
            continue
        keys = sorted({k for r in rows for k in r})
        nulls = sorted({k for r in rows for k, v in r.items() if v is None})
        print(f"  {label:22} rows={len(rows)} keys={keys} all-null={nulls}")
        if rows:
            print(f"  {'':22} row0={json.dumps(rows[0])[:150]}")
    db.close()

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
