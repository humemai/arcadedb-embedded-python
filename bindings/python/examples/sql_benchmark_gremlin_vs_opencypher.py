#!/usr/bin/env python3
"""Benchmark Gremlin vs OpenCypher query performance and result parity."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import random
import shutil
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any, Callable, Dict, Iterable, List, Tuple

import arcadedb_embedded as arcadedb
from arcadedb_embedded.jvm import shutdown_jvm


@dataclass
class QuerySpec:
    name: str
    opencypher: str
    sql: str
    gremlin: str
    normalize: Callable[[List[Any]], List[Any]]


def _ensure_opencypher(db) -> None:
    _ = list(db.query("opencypher", "RETURN 1 AS one"))


def _ensure_gremlin(db) -> None:
    _ = list(db.query("gremlin", "g.V().limit(1)"))


def _ensure_sql(db) -> None:
    _ = list(db.query("sql", "SELECT 1 AS one"))


def _seed_graph(db) -> None:
    db.schema.create_vertex_type("Person")
    db.schema.create_vertex_type("Company")
    db.schema.create_vertex_type("Project")
    db.schema.create_vertex_type("Department")
    db.schema.create_vertex_type("Skill")
    db.schema.create_vertex_type("Location")
    db.schema.create_vertex_type("Team")
    db.schema.create_vertex_type("Task")
    db.schema.create_vertex_type("Tag")
    db.schema.create_vertex_type("Event")
    db.schema.create_edge_type("KNOWS")
    db.schema.create_edge_type("WORKS_FOR")
    db.schema.create_edge_type("WORKS_ON")
    db.schema.create_edge_type("LIKES")
    db.schema.create_edge_type("MANAGES")
    db.schema.create_edge_type("LOCATED_IN")
    db.schema.create_edge_type("MEMBER_OF")
    db.schema.create_edge_type("HAS_SKILL")
    db.schema.create_edge_type("PART_OF")
    db.schema.create_edge_type("ASSIGNED_TO")
    db.schema.create_edge_type("TAGGED_WITH")
    db.schema.create_edge_type("ATTENDED")
    db.schema.create_edge_type("COLLABORATES_WITH")

    rng = random.Random(42)
    num_people = 10000
    num_companies = 500
    num_projects = 2000
    num_departments = 200
    num_skills = 200
    num_locations = 200
    num_teams = 600
    num_tasks = 8000
    num_tags = 500
    num_events = 300

    people = []
    companies = []
    projects = []
    departments = []
    skills = []
    locations = []
    teams = []
    tasks = []
    tags = []
    events = []

    with db.transaction():
        for i in range(num_companies):
            c = db.new_vertex("Company")
            c.set("name", f"Company_{i}")
            c.set("industry", f"Industry_{i % 5}")
            c.save()
            companies.append(c)

        for i in range(num_projects):
            p = db.new_vertex("Project")
            p.set("name", f"Project_{i}")
            p.set("budget", float(rng.randint(50_000, 500_000)))
            p.save()
            projects.append(p)

        for i in range(num_departments):
            d = db.new_vertex("Department")
            d.set("name", f"Department_{i}")
            d.set("cost_center", f"CC-{i:04d}")
            d.save()
            departments.append(d)

        for i in range(num_skills):
            s = db.new_vertex("Skill")
            s.set("name", f"Skill_{i}")
            s.set("level", rng.choice(["basic", "intermediate", "advanced"]))
            s.save()
            skills.append(s)

        for i in range(num_locations):
            l = db.new_vertex("Location")
            l.set("name", f"Location_{i}")
            l.set("country", f"Country_{i % 25}")
            l.save()
            locations.append(l)

        for i in range(num_teams):
            t = db.new_vertex("Team")
            t.set("name", f"Team_{i}")
            t.set("focus", rng.choice(["platform", "apps", "data", "infra"]))
            t.save()
            teams.append(t)

        for i in range(num_tasks):
            t = db.new_vertex("Task")
            t.set("title", f"Task_{i}")
            t.set("priority", rng.randint(1, 5))
            t.set("estimate", rng.randint(1, 21))
            t.save()
            tasks.append(t)

        for i in range(num_tags):
            t = db.new_vertex("Tag")
            t.set("name", f"Tag_{i}")
            t.set("category", f"Category_{i % 20}")
            t.save()
            tags.append(t)

        for i in range(num_events):
            e = db.new_vertex("Event")
            e.set("name", f"Event_{i}")
            e.set("year", 2015 + (i % 10))
            e.save()
            events.append(e)

        for i in range(num_people):
            person = db.new_vertex("Person")
            person.set("name", f"Person_{i}")
            person.set("age", rng.randint(18, 65))
            person.set("level", rng.choice(["junior", "mid", "senior"]))
            person.save()
            people.append(person)

        for i, person in enumerate(people):
            company = companies[i % num_companies]
            edge = person.new_edge("WORKS_FOR", company)
            edge.set("since", rng.randint(2010, 2024))
            edge.save()

            department = departments[i % num_departments]
            edge = company.new_edge("PART_OF", department)
            edge.set("since", rng.randint(2010, 2024))
            edge.save()

            location = locations[i % num_locations]
            edge = company.new_edge("LOCATED_IN", location)
            edge.set("since", rng.randint(2010, 2024))
            edge.save()

            team = teams[i % num_teams]
            edge = person.new_edge("MEMBER_OF", team)
            edge.set("since", rng.randint(2018, 2024))
            edge.save()

            for _ in range(rng.randint(1, 3)):
                project = rng.choice(projects)
                edge = person.new_edge("WORKS_ON", project)
                edge.set("role", rng.choice(["dev", "lead", "qa", "pm"]))
                edge.save()

            for _ in range(rng.randint(1, 4)):
                skill = rng.choice(skills)
                edge = person.new_edge("HAS_SKILL", skill)
                edge.set("years", rng.randint(1, 15))
                edge.save()

            for _ in range(rng.randint(1, 3)):
                task = rng.choice(tasks)
                edge = person.new_edge("ASSIGNED_TO", task)
                edge.set("status", rng.choice(["todo", "doing", "done"]))
                edge.save()

            for _ in range(rng.randint(0, 2)):
                tag = rng.choice(tags)
                edge = person.new_edge("TAGGED_WITH", tag)
                edge.set("source", rng.choice(["import", "manual", "ml"]))
                edge.save()

            for _ in range(rng.randint(0, 1)):
                event = rng.choice(events)
                edge = person.new_edge("ATTENDED", event)
                edge.set("rating", rng.randint(1, 5))
                edge.save()

            for _ in range(rng.randint(1, 4)):
                other = rng.choice(people)
                if other is person:
                    continue
                edge = person.new_edge("KNOWS", other)
                edge.set("since", rng.randint(2015, 2024))
                edge.save()

            for _ in range(rng.randint(0, 2)):
                other = rng.choice(people)
                if other is person:
                    continue
                edge = person.new_edge("COLLABORATES_WITH", other)
                edge.set("since", rng.randint(2019, 2024))
                edge.save()

            for _ in range(rng.randint(0, 2)):
                project = rng.choice(projects)
                edge = person.new_edge("LIKES", project)
                edge.set("weight", round(rng.random(), 3))
                edge.save()

        for i, company in enumerate(companies):
            manager = people[(i * 7) % num_people]
            edge = manager.new_edge("MANAGES", company)
            edge.set("since", rng.randint(2012, 2024))
            edge.save()


def _normalize_values(values: Iterable[Any]) -> List[Any]:
    return sorted(values)


def _normalize_pairs(values: Iterable[Tuple[Any, Any]]) -> List[Tuple[Any, Any]]:
    return sorted(values, key=lambda x: (x[0], x[1]))


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


def _normalize_company_counts(
    values: Iterable[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    cleaned = []
    for name, count in values:
        coerced = _coerce_int(count)
        cleaned.append((str(name), 0 if coerced is None else coerced))
    return sorted(cleaned, key=lambda x: (-x[1], x[0]))


def _normalize_company_avg(
    values: Iterable[Tuple[str, float]],
) -> List[Tuple[str, float]]:
    rounded = [(name, round(avg, 4)) for name, avg in values]
    return sorted(rounded, key=lambda x: (x[0], x[1]))


def _write_markdown(results: Dict[str, Any], output_path: str) -> None:
    lines = [
        "# Gremlin vs OpenCypher vs SQL Benchmark",
        "",
        "## Dataset",
        "",
        "This benchmark uses a synthetic graph seeded by the script:",
        "",
        "- 10000 `Person` vertices with `name`, `age`, and `level`",
        "- 500 `Company` vertices with `name` and `industry`",
        "- 2000 `Project` vertices with `name` and `budget`",
        "- 200 `Department` vertices with `name` and `cost_center`",
        "- 200 `Skill` vertices with `name` and `level`",
        "- 200 `Location` vertices with `name` and `country`",
        "- 600 `Team` vertices with `name` and `focus`",
        "- 8000 `Task` vertices with `title`, `priority`, and `estimate`",
        "- 500 `Tag` vertices with `name` and `category`",
        "- 300 `Event` vertices with `name` and `year`",
        "- Edges:",
        "  - `WORKS_FOR` (Person → Company) with `since`",
        "  - `WORKS_ON` (Person → Project) with `role`",
        "  - `KNOWS` (Person → Person) with `since`",
        "  - `LIKES` (Person → Project) with `weight`",
        "  - `MANAGES` (Person → Company) with `since`",
        "  - `LOCATED_IN` (Company → Location) with `since`",
        "  - `MEMBER_OF` (Person → Team) with `since`",
        "  - `HAS_SKILL` (Person → Skill) with `years`",
        "  - `PART_OF` (Company → Department) with `since`",
        "  - `ASSIGNED_TO` (Person → Task) with `status`",
        "  - `TAGGED_WITH` (Person → Tag) with `source`",
        "  - `ATTENDED` (Person → Event) with `rating`",
        "  - `COLLABORATES_WITH` (Person → Person) with `since`",
        "",
        f"- OpenCypher DB: {results['opencypher_db_path']}",
        f"- SQL DB: {results['sql_db_path']}",
        f"- Gremlin DB: {results['gremlin_db_path']}",
        f"- Iterations: {results['iterations']}",
        f"- Warmup: {results['warmup']}",
        f"- Parallel: {results['parallel']}",
        "",
        "## Results",
        "",
        "| Query | Cypher vs SQL | Cypher vs Gremlin | OpenCypher mean (ms) | OpenCypher stdev (ms) | SQL mean (ms) | SQL stdev (ms) | Gremlin mean (ms) | Gremlin stdev (ms) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for entry in results["queries"]:
        oc = entry["opencypher"]
        sql = entry["sql"]
        gr = entry["gremlin"]
        lines.append(
            "| {name} | {oc_sql} | {oc_gr} | {oc_mean:.6f} | {oc_std:.6f} | {sql_mean:.6f} | {sql_std:.6f} | {gr_mean:.6f} | {gr_std:.6f} |".format(
                name=entry["name"],
                oc_sql="✅" if entry["accuracy_match_sql"] else "❌",
                oc_gr="✅" if entry["accuracy_match_gremlin"] else "❌",
                oc_mean=oc["mean_ms"],
                oc_std=oc["stdev_ms"],
                sql_mean=sql["mean_ms"],
                sql_std=sql["stdev_ms"],
                gr_mean=gr["mean_ms"],
                gr_std=gr["stdev_ms"],
            )
        )

    oc_means = [entry["opencypher"]["mean_ms"] for entry in results["queries"]]
    oc_stdevs = [entry["opencypher"]["stdev_ms"] for entry in results["queries"]]
    sql_means = [entry["sql"]["mean_ms"] for entry in results["queries"]]
    sql_stdevs = [entry["sql"]["stdev_ms"] for entry in results["queries"]]
    gr_means = [entry["gremlin"]["mean_ms"] for entry in results["queries"]]
    gr_stdevs = [entry["gremlin"]["stdev_ms"] for entry in results["queries"]]
    if oc_means and sql_means and gr_means:
        lines.append(
            "| Average | - | - | {oc_mean:.6f} | {oc_std:.6f} | {sql_mean:.6f} | {sql_std:.6f} | {gr_mean:.6f} | {gr_std:.6f} |".format(
                oc_mean=statistics.mean(oc_means),
                oc_std=statistics.mean(oc_stdevs),
                sql_mean=statistics.mean(sql_means),
                sql_std=statistics.mean(sql_stdevs),
                gr_mean=statistics.mean(gr_means),
                gr_std=statistics.mean(gr_stdevs),
            )
        )

    Path(output_path).write_text("\n".join(lines))


QUERY_SPECS: List[QuerySpec] = [
    QuerySpec(
        name="people_over_20",
        opencypher=(
            "MATCH (p:Person) WHERE p.age > 20 RETURN p.name as name ORDER BY name"
        ),
        sql="SELECT name FROM Person WHERE age > 20 ORDER BY name",
        gremlin="g.V().hasLabel('Person').has('age', gt(20)).values('name').order()",
        normalize=_normalize_values,
    ),
    QuerySpec(
        name="works_for_company",
        opencypher=(
            "MATCH (p:Person)-[:WORKS_FOR]->(c:Company) "
            "RETURN p.name as name, c.name as company ORDER BY name"
        ),
        sql=(
            "MATCH {type: Person, as: p}-WORKS_FOR->{type: Company, as: c} "
            "RETURN p.name as name, c.name as company ORDER BY name"
        ),
        gremlin=(
            "g.V().hasLabel('Person').as('p').out('WORKS_FOR').as('c')"
            ".select('p','c').by('name').by('name').order().by(select('p'))"
        ),
        normalize=_normalize_pairs,
    ),
    QuerySpec(
        name="knows_since_2021",
        opencypher=(
            "MATCH (:Person {name: 'Alice'})-[r:KNOWS]->(b:Person) "
            "WHERE r.since >= 2021 RETURN b.name as name ORDER BY name"
        ),
        sql=(
            "MATCH {type: Person, where: (name = 'Alice')}.outE('KNOWS'){where: (since >= 2021)}"
            ".inV(){as: b} RETURN b.name as name ORDER BY name"
        ),
        gremlin=(
            "g.V().has('Person','name','Alice').outE('KNOWS').has('since', gte(2021))"
            ".inV().values('name').order()"
        ),
        normalize=_normalize_values,
    ),
    QuerySpec(
        name="knows_1_3_hops",
        opencypher=(
            "MATCH (a:Person {name: 'Alice'})-[:KNOWS*1..5]->(b:Person) "
            "RETURN DISTINCT b.name as name ORDER BY name"
        ),
        sql=(
            "MATCH {type: Person, where: (name = 'Alice')}.out('KNOWS')"
            "{as: b, while: ($depth < 6)} RETURN DISTINCT b.name as name ORDER BY name"
        ),
        gremlin=(
            "g.V().has('Person','name','Alice').repeat(out('KNOWS')).emit().times(5)"
            ".values('name').dedup().order()"
        ),
        normalize=_normalize_values,
    ),
    QuerySpec(
        name="optional_company",
        opencypher=(
            "MATCH (p:Person) OPTIONAL MATCH (p)-[:WORKS_FOR]->(c:Company) "
            "RETURN p.name as name, c.name as company ORDER BY name"
        ),
        sql=("SELECT name, out('WORKS_FOR').name as company FROM Person ORDER BY name"),
        gremlin=(
            "g.V().hasLabel('Person').project('name','company')"
            ".by('name')"
            ".by(out('WORKS_FOR').values('name').fold().coalesce(unfold(), constant(null)))"
            ".order().by('name')"
        ),
        normalize=_normalize_pairs,
    ),
    QuerySpec(
        name="count_employees",
        opencypher=(
            "MATCH (p:Person)-[:WORKS_FOR]->(c:Company) "
            "RETURN c.name as company, count(p) as employees ORDER BY employees DESC"
        ),
        sql=(
            "SELECT name as company, count(*) as employees "
            "FROM (SELECT expand(out('WORKS_FOR')) FROM Person) "
            "GROUP BY company ORDER BY employees DESC"
        ),
        gremlin="g.V().hasLabel('Person').out('WORKS_FOR').groupCount().by('name')",
        normalize=_normalize_company_counts,
    ),
    QuerySpec(
        name="senior_count_by_company",
        opencypher=(
            "MATCH (p:Person {level: 'senior'})-[:WORKS_FOR]->(c:Company) "
            "RETURN c.name as company, count(p) as seniors ORDER BY seniors DESC, company"
        ),
        sql=(
            "SELECT name as company, count(*) as seniors "
            "FROM (SELECT expand(out('WORKS_FOR')) FROM Person WHERE level = 'senior') "
            "GROUP BY company ORDER BY seniors DESC, company"
        ),
        gremlin=(
            "g.V().hasLabel('Person').has('level','senior').out('WORKS_FOR')"
            ".groupCount().by('name')"
        ),
        normalize=_normalize_company_counts,
    ),
    QuerySpec(
        name="project_contributors",
        opencypher=(
            "MATCH (p:Person)-[:WORKS_ON]->(pr:Project) "
            "RETURN pr.name as project, count(p) as contributors "
            "ORDER BY contributors DESC, project"
        ),
        sql=(
            "SELECT name as project, count(*) as contributors "
            "FROM (SELECT expand(out('WORKS_ON')) FROM Person) "
            "GROUP BY project ORDER BY contributors DESC, project"
        ),
        gremlin=("g.V().hasLabel('Person').out('WORKS_ON').groupCount().by('name')"),
        normalize=_normalize_company_counts,
    ),
    QuerySpec(
        name="coworkers_of_person_1",
        opencypher=(
            "MATCH (p:Person {name: 'Person_1'})-[:WORKS_FOR]->(c:Company)"
            "<-[:WORKS_FOR]-(coworker:Person) "
            "RETURN DISTINCT coworker.name as name ORDER BY name"
        ),
        sql=(
            "MATCH {type: Person, where: (name = 'Person_1')}-WORKS_FOR->"
            "{type: Company, as: c}<-WORKS_FOR-{type: Person, as: coworker} "
            "RETURN DISTINCT coworker.name as name ORDER BY name"
        ),
        gremlin=(
            "g.V().has('Person','name','Person_1').out('WORKS_FOR').in('WORKS_FOR')"
            ".values('name').dedup().order()"
        ),
        normalize=_normalize_values,
    ),
    QuerySpec(
        name="projects_for_company_1",
        opencypher=(
            "MATCH (c:Company {name: 'Company_1'})<-[:WORKS_FOR]-(p:Person)"
            "-[:WORKS_ON]->(pr:Project) "
            "RETURN DISTINCT pr.name as name ORDER BY name"
        ),
        sql=(
            "MATCH {type: Company, where: (name = 'Company_1')}<-WORKS_FOR-"
            "{type: Person, as: p}-WORKS_ON->{type: Project, as: pr} "
            "RETURN DISTINCT pr.name as name ORDER BY name"
        ),
        gremlin=(
            "g.V().has('Company','name','Company_1').in('WORKS_FOR').out('WORKS_ON')"
            ".values('name').dedup().order()"
        ),
        normalize=_normalize_values,
    ),
    QuerySpec(
        name="high_weight_likes",
        opencypher=(
            "MATCH (p:Person)-[l:LIKES]->(pr:Project) "
            "WHERE l.weight >= 0.7 "
            "RETURN p.name as name, pr.name as project ORDER BY name, project"
        ),
        sql=(
            "MATCH {type: Person, as: p}.outE('LIKES'){where: (weight >= 0.7)}"
            ".inV(){as: pr} RETURN p.name as name, pr.name as project ORDER BY name, project"
        ),
        gremlin=(
            "g.V().hasLabel('Person').as('p').outE('LIKES').has('weight', gte(0.7))"
            ".inV().as('pr')"
            ".select('p','pr').by('name').by('name').order().by(select('p')).by(select('pr'))"
        ),
        normalize=_normalize_pairs,
    ),
]


def _run_query(language: str, query: str, db: arcadedb.Database) -> List[Any]:
    result = db.query(language, query)
    return list(result)


def _to_python_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_python_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_python_value(v) for v in value]
    try:
        return str(value)
    except Exception:
        return value


def _run_benchmark_process(
    language: str,
    query: str,
    db_path: str,
    iterations: int,
    warmup: int,
    query_name: str,
) -> Tuple[List[float], List[Any]]:
    times: List[float] = []
    first_values: List[Any] = []
    with arcadedb.open_database(db_path) as db:
        for _ in range(warmup):
            _ = _run_query(language, query, db)

        for i in range(iterations):
            t0 = time.perf_counter()
            rows = _run_query(language, query, db)
            t1 = time.perf_counter()
            times.append(t1 - t0)
            if i == 0:
                first_values = _extract_results(language, query_name, rows)
                first_values = _to_python_value(first_values)
    return times, first_values


def _benchmark_worker(
    language: str,
    query: str,
    db_path: str,
    iterations: int,
    warmup: int,
    query_name: str,
    out_queue: multiprocessing.Queue,
) -> None:
    try:
        times, first_values = _run_benchmark_process(
            language, query, db_path, iterations, warmup, query_name
        )
        out_queue.put((times, first_values, None))
    except Exception as exc:
        out_queue.put((None, None, repr(exc)))
    finally:
        shutdown_jvm()


def _extract_results(language: str, query_name: str, rows: List[Any]) -> List[Any]:
    if language == "opencypher":
        if query_name in {"people_over_20", "knows_since_2021", "knows_1_3_hops"}:
            return [row.get("name") for row in rows]
        if query_name == "works_for_company":
            return [(row.get("name"), row.get("company")) for row in rows]
        if query_name == "optional_company":
            return [(row.get("name"), row.get("company")) for row in rows]
        if query_name == "count_employees":
            return [
                (row.get("company"), _coerce_int(row.get("employees"))) for row in rows
            ]
        if query_name == "senior_count_by_company":
            return [
                (row.get("company"), _coerce_int(row.get("seniors"))) for row in rows
            ]
        if query_name == "project_contributors":
            return [
                (row.get("project"), _coerce_int(row.get("contributors")))
                for row in rows
            ]
        if query_name == "high_weight_likes":
            return [(row.get("name"), row.get("project")) for row in rows]
    if language == "sql":
        if query_name in {"people_over_20", "knows_since_2021", "knows_1_3_hops"}:
            return [row.get("name") for row in rows]
        if query_name in {"works_for_company", "optional_company"}:
            pairs = []
            for row in rows:
                name = row.get("name")
                company = row.get("company")
                if isinstance(company, (list, tuple)):
                    company = company[0] if company else None
                pairs.append((name, company))
            return pairs
        if query_name in {
            "count_employees",
            "senior_count_by_company",
            "project_contributors",
        }:
            pairs = []
            for row in rows:
                data = row.get("result")
                if data is None:
                    data = row.to_dict()
                if isinstance(data, dict):
                    if ("company" in data or "project" in data) and (
                        "employees" in data
                        or "seniors" in data
                        or "contributors" in data
                    ):
                        pairs.append(
                            (
                                data.get("company") or data.get("project"),
                                _coerce_int(
                                    data.get("employees")
                                    or data.get("seniors")
                                    or data.get("contributors")
                                ),
                            )
                        )
                    else:
                        pairs.extend([(k, _coerce_int(v)) for k, v in data.items()])
                else:
                    pairs.append(tuple(data))
            return pairs
        if query_name == "high_weight_likes":
            return [(row.get("name"), row.get("project")) for row in rows]
        return []
    else:
        # Gremlin results use the 'result' field.
        if query_name in {"people_over_20", "knows_since_2021", "knows_1_3_hops"}:
            return [row.get("result") for row in rows]
        if query_name in {"works_for_company", "optional_company"}:
            pairs = []
            for row in rows:
                data = row.get("result")
                if data is None:
                    data = row.to_dict()
                if isinstance(data, dict):
                    pairs.append(
                        (
                            data.get("p") or data.get("name"),
                            data.get("c") or data.get("company"),
                        )
                    )
                else:
                    pairs.append(tuple(data))
            return pairs
        if query_name == "count_employees":
            counts = []
            for row in rows:
                data = row.get("result")
                if data is None:
                    data = row.to_dict()
                if isinstance(data, dict):
                    counts.extend([(k, _coerce_int(v)) for k, v in data.items()])
            return counts
        if query_name in {"senior_count_by_company", "project_contributors"}:
            pairs = []
            for row in rows:
                data = row.get("result")
                if data is None:
                    data = row.to_dict()
                if isinstance(data, dict):
                    if ("company" in data or "project" in data) and (
                        "seniors" in data or "contributors" in data
                    ):
                        pairs.append(
                            (
                                data.get("company") or data.get("project"),
                                _coerce_int(
                                    data.get("seniors") or data.get("contributors")
                                ),
                            )
                        )
                    else:
                        pairs.extend([(k, _coerce_int(v)) for k, v in data.items()])
                else:
                    pairs.append(tuple(data))
            return pairs
        if query_name == "high_weight_likes":
            pairs = []
            for row in rows:
                data = row.get("result")
                if data is None:
                    data = row.to_dict()
                if isinstance(data, dict):
                    pairs.append(
                        (
                            data.get("p") or data.get("name"),
                            data.get("pr") or data.get("project"),
                        )
                    )
                else:
                    pairs.append(tuple(data))
            return pairs
    return []


def _benchmark_query(
    spec: QuerySpec,
    opencypher_db_path: str,
    sql_db_path: str,
    gremlin_db_path: str,
    iterations: int,
    warmup: int,
    parallel: bool,
) -> Dict[str, Any]:
    timings = {"opencypher": [], "sql": [], "gremlin": []}
    accuracy_sql = None
    accuracy_gremlin = None
    debug_mismatch = True

    if parallel:
        timeout_sec = 120
        ctx = multiprocessing.get_context("spawn")

        oc_queue: multiprocessing.Queue = ctx.Queue()
        sql_queue: multiprocessing.Queue = ctx.Queue()
        gr_queue: multiprocessing.Queue = ctx.Queue()

        oc_proc = ctx.Process(
            target=_benchmark_worker,
            args=(
                "opencypher",
                spec.opencypher,
                opencypher_db_path,
                iterations,
                warmup,
                spec.name,
                oc_queue,
            ),
        )
        gr_proc = ctx.Process(
            target=_benchmark_worker,
            args=(
                "gremlin",
                spec.gremlin,
                gremlin_db_path,
                iterations,
                warmup,
                spec.name,
                gr_queue,
            ),
        )

        sql_proc = ctx.Process(
            target=_benchmark_worker,
            args=(
                "sql",
                spec.sql,
                sql_db_path,
                iterations,
                warmup,
                spec.name,
                sql_queue,
            ),
        )

        oc_proc.start()
        sql_proc.start()
        gr_proc.start()

        try:
            oc_times, oc_vals, oc_err = oc_queue.get(timeout=timeout_sec)
        except Empty:
            oc_times, oc_vals, oc_err = None, None, "timeout"

        try:
            sql_times, sql_vals, sql_err = sql_queue.get(timeout=timeout_sec)
        except Empty:
            sql_times, sql_vals, sql_err = None, None, "timeout"

        try:
            gr_times, gr_vals, gr_err = gr_queue.get(timeout=timeout_sec)
        except Empty:
            gr_times, gr_vals, gr_err = None, None, "timeout"

        oc_proc.join(timeout=2)
        sql_proc.join(timeout=2)
        gr_proc.join(timeout=2)

        if oc_proc.is_alive():
            oc_proc.terminate()
            oc_proc.join()
        if sql_proc.is_alive():
            sql_proc.terminate()
            sql_proc.join()
        if gr_proc.is_alive():
            gr_proc.terminate()
            gr_proc.join()

        if oc_err:
            raise RuntimeError(f"OpenCypher worker failed: {oc_err}")
        if sql_err:
            raise RuntimeError(f"SQL worker failed: {sql_err}")
        if gr_err:
            raise RuntimeError(f"Gremlin worker failed: {gr_err}")
    else:
        oc_times, oc_vals = _run_benchmark_process(
            "opencypher",
            spec.opencypher,
            opencypher_db_path,
            iterations,
            warmup,
            spec.name,
        )
        sql_times, sql_vals = _run_benchmark_process(
            "sql",
            spec.sql,
            sql_db_path,
            iterations,
            warmup,
            spec.name,
        )
        gr_times, gr_vals = _run_benchmark_process(
            "gremlin",
            spec.gremlin,
            gremlin_db_path,
            iterations,
            warmup,
            spec.name,
        )

    timings["opencypher"].extend(oc_times)
    timings["sql"].extend(sql_times)
    timings["gremlin"].extend(gr_times)

    oc_vals = spec.normalize(oc_vals)
    sql_vals = spec.normalize(sql_vals)
    gr_vals = spec.normalize(gr_vals)
    accuracy_sql = oc_vals == sql_vals
    accuracy_gremlin = oc_vals == gr_vals

    if debug_mismatch and not accuracy_sql:
        print(f"\n[SQL mismatch] {spec.name}")
        print(f"OpenCypher: {oc_vals}")
        print(f"SQL: {sql_vals}")

    if debug_mismatch and not accuracy_gremlin:
        print(f"\n[Gremlin mismatch] {spec.name}")
        print(f"OpenCypher: {oc_vals}")
        print(f"Gremlin: {gr_vals}")

    def stats(values: List[float]) -> Dict[str, float]:
        values_ms = [value * 1000.0 for value in values]
        return {
            "mean_ms": statistics.mean(values_ms),
            "stdev_ms": statistics.pstdev(values_ms) if len(values_ms) > 1 else 0.0,
            "min_ms": min(values_ms),
            "max_ms": max(values_ms),
        }

    return {
        "name": spec.name,
        "accuracy_match_sql": accuracy_sql,
        "accuracy_match_gremlin": accuracy_gremlin,
        "opencypher": stats(timings["opencypher"]),
        "sql": stats(timings["sql"]),
        "gremlin": stats(timings["gremlin"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Gremlin vs OpenCypher vs SQL queries (mean/std timing + accuracy)"
    )
    parser.add_argument(
        "--db-path",
        default="sql_gremlin_opencypher_bench_db",
        help=(
            "Database directory name or absolute path. Relative paths are created under "
            "/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/examples/my_test_databases"
        ),
    )
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.set_defaults(parallel=True)
    parser.add_argument(
        "--output-json",
        default="sql_gremlin_opencypher_bench_results.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        default="sql_gremlin_opencypher_bench_results.md",
        help="Output Markdown path",
    )
    parser.add_argument("--keep-db", action="store_true", help="Keep the database")

    args = parser.parse_args()
    try:
        base_dir = Path(
            "/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/examples/my_test_databases"
        )
        base_dir.mkdir(parents=True, exist_ok=True)
        db_path = Path(args.db_path)
        if not db_path.is_absolute():
            db_path = base_dir / db_path

        opencypher_db_path = db_path.with_name(f"{db_path.name}_opencypher")
        sql_db_path = db_path.with_name(f"{db_path.name}_sql")
        gremlin_db_path = db_path.with_name(f"{db_path.name}_gremlin")

        for path in (opencypher_db_path, sql_db_path, gremlin_db_path):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

        with arcadedb.create_database(str(opencypher_db_path)) as db:
            _ensure_opencypher(db)
            _seed_graph(db)

        with arcadedb.create_database(str(sql_db_path)) as db:
            _ensure_sql(db)
            _seed_graph(db)

        with arcadedb.create_database(str(gremlin_db_path)) as db:
            _ensure_gremlin(db)
            _seed_graph(db)

        results = {
            "opencypher_db_path": str(opencypher_db_path),
            "sql_db_path": str(sql_db_path),
            "gremlin_db_path": str(gremlin_db_path),
            "iterations": args.iterations,
            "warmup": args.warmup,
            "parallel": args.parallel,
            "queries": [],
        }

        for spec in QUERY_SPECS:
            results["queries"].append(
                _benchmark_query(
                    spec,
                    str(opencypher_db_path),
                    str(sql_db_path),
                    str(gremlin_db_path),
                    args.iterations,
                    args.warmup,
                    args.parallel,
                )
            )

        Path(args.output_json).write_text(json.dumps(results, indent=2))
        print(f"Wrote {args.output_json}")
        _write_markdown(results, args.output_md)
        print(f"Wrote {args.output_md}")

        if not args.keep_db:
            try:
                with arcadedb.open_database(str(opencypher_db_path)) as db:
                    db.drop()
                with arcadedb.open_database(str(sql_db_path)) as db:
                    db.drop()
                with arcadedb.open_database(str(gremlin_db_path)) as db:
                    db.drop()
            except Exception:
                pass
    finally:
        shutdown_jvm()


if __name__ == "__main__":
    main()
