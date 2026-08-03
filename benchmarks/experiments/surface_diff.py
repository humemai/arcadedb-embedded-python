#!/usr/bin/env python3
"""Differential testing across query surfaces: SQL MATCH vs openCypher vs Python.

WHY THIS EXISTS. Every upstream issue this project has filed came out of
measuring speed. Correctness bugs were found only by tripping over them:
#3758 (Cypher self-join returns incorrect empty results), #3759 (Cypher
diverges from Neo4j), #5306 (openCypher silently returns empty results on
multi-hop patterns with IN-list or mid-pattern filters, where SQL MATCH was
correct), #5613 (whole-vertex projection emits declared properties as null).
Three are fixed. None was found on purpose. The find rate has been bounded by
how often we happened to run a breaking query shape, not by how many exist.

THE THIRD ORACLE IS THE POINT. Two surfaces disagreeing tells you something is
wrong; it does not tell you which one. #5306 was actionable precisely because
we could say SQL MATCH was correct. So every case is also computed directly in
Python over the same deterministic graph, and a disagreement is adjudicated
rather than merely reported.

SELF-SKEPTICISM, WHICH THIS PROJECT HAS EARNED THE HARD WAY. A disagreement is
far more likely to be a bug in this file's translation between two query
languages than a bug in the engine. Nothing here should be filed upstream
before the specific case is reduced by hand and re-run standalone. The harness
prints that reminder next to any disagreement it finds.

SCOPE OF THIS ROUND. Set semantics only: every query is written to return
distinct rows, and results are compared as sets of tuples. Bag semantics (how
many times a row appears when several paths reach the same endpoint) differ
legitimately between the two surfaces and is a separate investigation, so
cardinality is reported but never counted as a disagreement.

Axes swept, with the values that produced the four bugs above in caps:
  pattern          1-hop, 2-HOP, 3-hop, SELF-JOIN on the same edge type
  direction        out, in, both
  filter position  source, MID-PATTERN, target
  predicate        equality, IN-LIST, range
  projection       scalar property, WHOLE VERTEX, count
  edge storage     bidirectional, UNIDIRECTIONAL
  view             GAV off, GAV ON
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import traceback

import arcadedb_embedded as arcadedb

N_PERSON = int(os.environ.get("SD_PERSONS", "200"))
DEG = int(os.environ.get("SD_DEG", "4"))
CITIES = ["Berlin", "Munster", "Rome", "Milan", "Oslo"]
SEEDS = [0, 1, 7, 13, 42]          # source vertices the patterns start from


# ---------------------------------------------------------------- the graph

def gen_people():
    return [
        {"id": i, "name": f"p{i}", "age": 18 + (i % 60), "city": CITIES[i % len(CITIES)]}
        for i in range(N_PERSON)
    ]


def gen_edges():
    """Deterministic adjacency. No RNG, so the Python oracle and the database
    are generated from one source of truth and every run is reproducible."""
    out = []
    for i in range(N_PERSON):
        for k in range(DEG):
            j = (i * 7919 + k * 104729 + 13) % N_PERSON
            if j != i:
                out.append((i, j, 2000 + (k % 26)))
    # A deliberate reciprocal pair and a deliberate triangle: the self-join and
    # multi-hop shapes are uninteresting on a graph that happens to have neither.
    out += [(0, 1, 2001), (1, 0, 2002), (0, 2, 2003), (2, 3, 2004), (3, 0, 2005)]
    return sorted(set(out))


PEOPLE = gen_people()
EDGES = gen_edges()
BY_ID = {p["id"]: p for p in PEOPLE}


def adj(direction):
    """direction: 'out' | 'in' | 'both' -> {src: set(dst)}"""
    m = {p["id"]: set() for p in PEOPLE}
    for s, t, _ in EDGES:
        if direction in ("out", "both"):
            m[s].add(t)
        if direction in ("in", "both"):
            m[t].add(s)
    return m


ADJ = {d: adj(d) for d in ("out", "in", "both")}


def inc(direction):
    """Incidence with EDGE IDENTITY: {v: set((neighbour, edge_index))}.

    Needed because openCypher applies RELATIONSHIP UNIQUENESS: within a single
    MATCH, the same relationship may not be traversed twice. Plain adjacency
    composition cannot express that, so a 2-hop undirected oracle built from
    ADJ alone over-counts by exactly the paths that walk back over the edge
    they arrived on.

    Confirmed empirically rather than assumed. The undirected 2-hop cases were
    the only ones where Cypher differed from SQL, and the single row it omitted
    was always the seed vertex itself. The directed cases agreed, including
    seed 0 returning p0 via the distinct edges 0->1 and 1->0, which is what
    distinguishes relationship uniqueness from node uniqueness: Cypher allows
    returning to a vertex, it just will not reuse a relationship.
    """
    m = {p["id"]: set() for p in PEOPLE}
    for k, (s_, t_, _) in enumerate(EDGES):
        if direction in ("out", "both"):
            m[s_].add((t_, k))
        if direction in ("in", "both"):
            m[t_].add((s_, k))
    return m


INC = {d: inc(d) for d in ("out", "in", "both")}


def hop2(seed, direction, mid_pred=None, rel_unique=False):
    """Endpoints of 2-hop paths from seed.

    rel_unique=True models openCypher; False models SQL MATCH, which does not
    impose relationship uniqueness. The two surfaces genuinely disagree here
    and both are right for their own language, so the harness compares each
    against the oracle for ITS OWN semantics rather than declaring a winner.
    """
    out = set()
    for m1, e1 in INC[direction][seed]:
        if mid_pred and not mid_pred(BY_ID[m1]):
            continue
        for g, e2 in INC[direction][m1]:
            if rel_unique and e2 == e1:
                continue
            out.add((BY_ID[g]["name"],))
    return out


# ------------------------------------------------------------- the case set
# Each case supplies three independent computations of the same set. `oracle`
# is plain Python over EDGES/PEOPLE; `sql` and `cypher` are sent to the engine.

def C(name, oracle, sql, cypher, tags, keys=("name",)):
    """keys: the projected column names, declared explicitly.

    The first version derived these from the query text and asked whether
    "AS n" appeared in it. "AS n" is a substring of "AS name", so every
    scalar case looked up a column that did not exist, every row normalised
    to (None,), and the harness reported 70 disagreements that were all its
    own. Declare the contract; do not infer it from a string."""
    return {"name": name, "oracle": oracle, "sql": sql, "cypher": cypher,
            "tags": tags, "keys": list(keys)}


def build_cases():
    cases = []
    ARROW = {"out": ("out", "-[:KNOWS]->"), "in": ("in", "<-[:KNOWS]-"),
             "both": ("both", "-[:KNOWS]-")}

    for seed, (dname, (sqlfn, cyparrow)) in itertools.product(SEEDS, ARROW.items()):
        # 1-hop, scalar projection, filter on source
        cases.append(C(
            f"hop1_{dname}_seed{seed}",
            lambda s=seed, d=dname: {(BY_ID[f]["name"],) for f in ADJ[d][s]},
            f"MATCH {{type: Person, as: p, where: (id = {seed})}}"
            f".{sqlfn}('KNOWS'){{as: f}} RETURN DISTINCT f.name AS name",
            f"MATCH (p:Person {{id: {seed}}}){cyparrow}(f:Person) "
            f"RETURN DISTINCT f.name AS name",
            ["hop1", dname, "equality", "scalar"]))

        # 2-hop, the shape behind #5306
        cases.append(C(
            f"hop2_{dname}_seed{seed}",
            {"sql": lambda s=seed, d=dname: hop2(s, d, rel_unique=False),
             "opencypher": lambda s=seed, d=dname: hop2(s, d, rel_unique=True)},
            f"MATCH {{type: Person, as: p, where: (id = {seed})}}"
            f".{sqlfn}('KNOWS'){{as: m}}.{sqlfn}('KNOWS'){{as: g}} "
            f"RETURN DISTINCT g.name AS name",
            f"MATCH (p:Person {{id: {seed}}}){cyparrow}(m:Person){cyparrow}(g:Person) "
            f"RETURN DISTINCT g.name AS name",
            ["hop2", dname, "equality", "scalar"]))

        # 2-hop with a MID-PATTERN filter: the exact #5306 trigger
        cases.append(C(
            f"hop2_midfilter_{dname}_seed{seed}",
            {"sql": lambda s=seed, d=dname: hop2(
                s, d, lambda v: v["city"] == "Berlin", rel_unique=False),
             "opencypher": lambda s=seed, d=dname: hop2(
                s, d, lambda v: v["city"] == "Berlin", rel_unique=True)},
            f"MATCH {{type: Person, as: p, where: (id = {seed})}}"
            f".{sqlfn}('KNOWS'){{as: m, where: (city = 'Berlin')}}"
            f".{sqlfn}('KNOWS'){{as: g}} RETURN DISTINCT g.name AS name",
            f"MATCH (p:Person {{id: {seed}}}){cyparrow}(m:Person){cyparrow}(g:Person) "
            f"WHERE m.city = 'Berlin' RETURN DISTINCT g.name AS name",
            ["hop2", dname, "midfilter", "scalar"]))

        # 1-hop with an IN-LIST predicate on the far endpoint: the other #5306 trigger
        cases.append(C(
            f"hop1_inlist_{dname}_seed{seed}",
            lambda s=seed, d=dname: {
                (BY_ID[f]["name"],) for f in ADJ[d][s]
                if BY_ID[f]["city"] in ("Berlin", "Rome")},
            f"MATCH {{type: Person, as: p, where: (id = {seed})}}"
            f".{sqlfn}('KNOWS'){{as: f, where: (city IN ['Berlin', 'Rome'])}} "
            f"RETURN DISTINCT f.name AS name",
            f"MATCH (p:Person {{id: {seed}}}){cyparrow}(f:Person) "
            f"WHERE f.city IN ['Berlin', 'Rome'] RETURN DISTINCT f.name AS name",
            ["hop1", dname, "inlist", "scalar"]))

        # range predicate on the far endpoint
        cases.append(C(
            f"hop1_range_{dname}_seed{seed}",
            lambda s=seed, d=dname: {
                (BY_ID[f]["name"],) for f in ADJ[d][s] if BY_ID[f]["age"] >= 50},
            f"MATCH {{type: Person, as: p, where: (id = {seed})}}"
            f".{sqlfn}('KNOWS'){{as: f, where: (age >= 50)}} "
            f"RETURN DISTINCT f.name AS name",
            f"MATCH (p:Person {{id: {seed}}}){cyparrow}(f:Person) "
            f"WHERE f.age >= 50 RETURN DISTINCT f.name AS name",
            ["hop1", dname, "range", "scalar"]))

    # SELF-JOIN on the same edge type: the #3758 shape. Reciprocal pairs only.
    cases.append(C(
        "selfjoin_reciprocal",
        lambda: {(BY_ID[a]["name"], BY_ID[b]["name"])
                 for a in ADJ["out"] for b in ADJ["out"][a] if a in ADJ["out"][b]},
        "MATCH {type: Person, as: a}.out('KNOWS'){as: b}.out('KNOWS'){as: c, "
        "where: ($matched.a.id = id)} RETURN DISTINCT a.name AS name, b.name AS bname",
        "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(a) "
        "RETURN DISTINCT a.name AS name, b.name AS bname",
        ["selfjoin", "out", "equality", "scalar"], keys=("name", "bname")))

    # 3-hop, unfiltered, from one seed (keeps the result set bounded)
    cases.append(C(
        "hop3_out_seed0",
        lambda: {(BY_ID[z]["name"],) for m in ADJ["out"][0]
                 for g in ADJ["out"][m] for z in ADJ["out"][g]},
        "MATCH {type: Person, as: p, where: (id = 0)}.out('KNOWS'){as: m}"
        ".out('KNOWS'){as: g}.out('KNOWS'){as: z} RETURN DISTINCT z.name AS name",
        "MATCH (p:Person {id: 0})-[:KNOWS]->(m:Person)-[:KNOWS]->(g:Person)"
        "-[:KNOWS]->(z:Person) RETURN DISTINCT z.name AS name",
        ["hop3", "out", "equality", "scalar"]))

    # count aggregate over a 1-hop expansion
    cases.append(C(
        "count_hop1_out",
        lambda: {(len(ADJ["out"][0]),)},
        "SELECT count(*) AS n FROM (MATCH {type: Person, as: p, where: (id = 0)}"
        ".out('KNOWS'){as: f} RETURN DISTINCT f)",
        "MATCH (p:Person {id: 0})-[:KNOWS]->(f:Person) "
        "RETURN count(DISTINCT f) AS n",
        ["hop1", "out", "equality", "count"], keys=("n",)))

    return cases


# ------------------------------------------------------------------- runner

def normalise(rows, keys):
    """Rows -> set of value tuples, order-insensitive, JSON-comparable."""
    out = set()
    for r in rows:
        out.add(tuple(_scalar(r.get(k)) for k in keys))
    return out


def _scalar(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return json.dumps(v, sort_keys=True, default=str)


def run(db, language, text):
    rows = db.query(language, text).to_json_list()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bidirectional", default="true", choices=["true", "false"])
    ap.add_argument("--gav", default="off", choices=["on", "off"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    path = f"/tmp/surfdiff_{args.bidirectional}_{args.gav}"
    os.system(f"rm -rf {path}")
    db = arcadedb.create_database(path, jvm_kwargs={"heap_size": "4g"})

    db.command("sql", "CREATE VERTEX TYPE Person")
    for prop, typ in (("id", "INTEGER"), ("name", "STRING"),
                      ("age", "INTEGER"), ("city", "STRING")):
        db.command("sql", f"CREATE PROPERTY Person.{prop} {typ}")
    bidi = "" if args.bidirectional == "true" else " UNIDIRECTIONAL"
    db.command("sql", f"CREATE EDGE TYPE KNOWS{bidi}")
    db.command("sql", "CREATE PROPERTY KNOWS.since INTEGER")
    db.command("sql", "CREATE INDEX ON Person (id) UNIQUE")

    db.begin()
    for p in PEOPLE:
        db.command("sql",
                   "INSERT INTO Person SET id=:i, name=:n, age=:a, city=:c",
                   {"i": p["id"], "n": p["name"], "a": p["age"], "c": p["city"]})
    db.commit()
    db.begin()
    for n, (s, t, since) in enumerate(EDGES):
        db.command("sql",
                   "CREATE EDGE KNOWS FROM (SELECT FROM Person WHERE id=:a) "
                   "TO (SELECT FROM Person WHERE id=:b) SET since=:s",
                   {"a": s, "b": t, "s": since})
        if (n + 1) % 2000 == 0:
            db.commit(); db.begin()
    db.commit()

    if args.gav == "on":
        db.command("sql",
                   "CREATE GRAPH ANALYTICAL VIEW v VERTEX TYPES (Person) "
                   "EDGE TYPES (KNOWS) PROPERTIES (id, name, age, city) "
                   "EDGE PROPERTIES (since) UPDATE MODE OFF")

    cases = build_cases()
    config = f"bidirectional={args.bidirectional} gav={args.gav}"
    print(f"\n=== {config}  |  {len(PEOPLE)} vertices, {len(EDGES)} edges, "
          f"{len(cases)} cases ===\n")

    agree = disagree = errors = divergences = 0
    findings = []
    for c in cases:
        keys = c["keys"]
        # An oracle is either one callable (both surfaces should agree with it)
        # or a dict keyed by surface (the languages differ here by design).
        try:
            o = c["oracle"]
            exp = {k: (o[k]() if isinstance(o, dict) else o())
                   for k in ("sql", "opencypher")}
            divergent = isinstance(o, dict) and exp["sql"] != exp["opencypher"]
        except Exception as e:
            print(f"  ORACLE-ERROR {c['name']}: {e}")
            errors += 1
            continue
        res = {}
        for lang, text in (("sql", c["sql"]), ("opencypher", c["cypher"])):
            try:
                res[lang] = normalise(run(db, lang, text), keys)
            except Exception as e:
                res[lang] = f"ERROR {type(e).__name__}: {str(e)[:120]}"

        sql_r, cy_r = res["sql"], res["opencypher"]
        bad = [k for k, v in res.items() if isinstance(v, str)]
        if bad:
            errors += 1
            findings.append({"case": c["name"], "config": config, "kind": "exception",
                             "detail": {k: res[k] for k in bad},
                             "oracle_size": len(exp["sql"])})
            print(f"  EXCEPTION  {c['name']}: {[res[k] for k in bad][0][:90]}")
            continue

        if sql_r == exp["sql"] and cy_r == exp["opencypher"]:
            agree += 1
            if divergent:
                divergences += 1
            continue

        disagree += 1
        verdict = ("cypher wrong" if sql_r == exp["sql"] else
                   "sql wrong" if cy_r == exp["opencypher"] else
                   "both differ from the Python oracle")
        findings.append({
            "case": c["name"], "config": config, "kind": "disagreement",
            "verdict": verdict,
            "sizes": {"oracle_sql": len(exp["sql"]),
                      "oracle_cypher": len(exp["opencypher"]),
                      "sql": len(sql_r), "cypher": len(cy_r)},
            "only_in_sql": sorted(map(str, sql_r - cy_r))[:5],
            "only_in_cypher": sorted(map(str, cy_r - sql_r))[:5],
            "missing_vs_oracle_sql": sorted(map(str, exp["sql"] - sql_r))[:5],
            "missing_vs_oracle_cypher": sorted(map(str, exp["opencypher"] - cy_r))[:5],
            "sql_text": c["sql"], "cypher_text": c["cypher"],
        })
        print(f"  DISAGREE   {c['name']}  [{verdict}]  "
              f"oracle(sql)={len(exp['sql'])} oracle(cy)={len(exp['opencypher'])} "
              f"sql={len(sql_r)} cypher={len(cy_r)}")

    print(f"\n  agree {agree}   disagree {disagree}   errors {errors}")
    if divergences:
        print(f"  {divergences} of the agreeing cases are ones where SQL MATCH and")
        print("  openCypher return DIFFERENT sets by design (relationship")
        print("  uniqueness). Each matched its own language's oracle.")
    if findings:
        print("\n  A disagreement here is more likely a translation bug in this file")
        print("  than an engine bug. Reduce each case by hand and re-run it")
        print("  standalone before filing anything upstream.")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"config": config, "agree": agree, "disagree": disagree,
                       "errors": errors, "by_design_divergences": divergences,
                       "findings": findings}, f, indent=1)
    db.close()
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        os._exit(1)
