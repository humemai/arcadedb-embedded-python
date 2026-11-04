"""Seed the tiny Part B dataset over ArcadeDB's HTTP API (stdlib only).

  python seed_pgwire.py HOST HTTP_PORT PASSWORD
Two vertex types (Person 300, City 20) plus one edge type (LIVES_IN, 300 edges). Person.city_id repeats the edge as a
plain property so the relational JOIN step has something to join on. Exits non-zero unless the counts match.
"""
import base64
import json
import sys
import urllib.request

host, port, pw = sys.argv[1:4]
DB = "sqlev"


def post(language, command):
    req = urllib.request.Request(f"http://{host}:{port}/api/v1/command/{DB}",
                                 data=json.dumps({"language": language, "command": command}).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Basic " + base64.b64encode(f"root:{pw}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


lines = ["CREATE VERTEX TYPE City", "CREATE PROPERTY City.id LONG", "CREATE PROPERTY City.name STRING",
         "CREATE INDEX ON City (id) UNIQUE",
         "CREATE VERTEX TYPE Person", "CREATE PROPERTY Person.id LONG", "CREATE PROPERTY Person.name STRING",
         "CREATE PROPERTY Person.age INTEGER", "CREATE PROPERTY Person.city_id LONG",
         "CREATE INDEX ON Person (id) UNIQUE", "CREATE EDGE TYPE LIVES_IN"]
for c in range(1, 21):
    lines.append(f"INSERT INTO City SET id = {c}, name = 'City{c}'")
for p in range(1, 301):
    lines.append(f"INSERT INTO Person SET id = {p}, name = 'Person{p}', age = {20 + p % 50}, city_id = {1 + p % 20}")
for p in range(1, 301):
    lines.append(f"CREATE EDGE LIVES_IN FROM (SELECT FROM Person WHERE id = {p}) TO (SELECT FROM City WHERE id = {1 + p % 20})")
post("sqlscript", ";\n".join(lines) + ";")
counts = {t: post("sql", f"SELECT count(*) AS n FROM {t}")["result"][0]["n"] for t in ("Person", "City", "LIVES_IN")}
print(json.dumps(counts))
sys.exit(0 if counts == {"Person": 300, "City": 20, "LIVES_IN": 300} else 1)
