#!/usr/bin/env python3
"""
Example 10: Stack Overflow Graph (OLAP)

Builds a Stack Overflow property graph (Phase 2 schema) and runs a fixed
OLAP query suite using OpenCypher.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from lxml import etree
except ImportError:
    print("Missing dependency: lxml")
    print("Install with: uv pip install lxml")
    sys.exit(1)

EXPECTED_DATASETS = {
    "stackoverflow-tiny",
    "stackoverflow-small",
    "stackoverflow-medium",
    "stackoverflow-large",
    "stackoverflow-xlarge",
    "stackoverflow-full",
}

BENCHMARK_SCOPE_NOTE = (
    "Scope: OLAP query fairness on a common query suite. "
    "Ingestion paths differ by engine (ArcadeDB uses Cypher inserts, Ladybug uses staged CSV + COPY), "
    "so load/index timings are not a same-path ingest comparison."
)

INDEX_DEFS: List[Tuple[str, List[str], bool]] = [
    ("User", ["Id"], True),
    ("Question", ["Id"], True),
    ("Answer", ["Id"], True),
    ("Tag", ["Id"], True),
    ("Badge", ["Id"], True),
    ("Comment", ["Id"], True),
]

VERTEX_TYPES = ["User", "Question", "Answer", "Tag", "Badge", "Comment"]
EDGE_TYPES = [
    "ASKED",
    "ANSWERED",
    "HAS_ANSWER",
    "ACCEPTED_ANSWER",
    "TAGGED_WITH",
    "COMMENTED_ON",
    "COMMENTED_ON_ANSWER",
    "EARNED",
    "LINKED_TO",
]

QUERY_DEFS: List[Dict[str, str]] = [
    {
        "name": "top_askers",
        "cypher": """
            MATCH (u:User)-[:ASKED]->(q:Question)
            RETURN u.Id AS user_id, u.DisplayName AS name, count(q) AS questions
            ORDER BY questions DESC, user_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "top_answerers",
        "cypher": """
            MATCH (u:User)-[:ANSWERED]->(a:Answer)
            RETURN u.Id AS user_id, u.DisplayName AS name, count(a) AS answers
            ORDER BY answers DESC, user_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "top_accepted_answerers",
        "cypher": """
            MATCH (u:User)-[:ANSWERED]->(a:Answer)<-[:ACCEPTED_ANSWER]-(:Question)
            RETURN u.Id AS user_id, u.DisplayName AS name, count(a) AS accepted
            ORDER BY accepted DESC, user_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "top_tags_by_questions",
        "cypher": """
            MATCH (q:Question)-[:TAGGED_WITH]->(t:Tag)
            RETURN t.Id AS tag_id, t.TagName AS tag, count(q) AS questions
            ORDER BY questions DESC, tag_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "tag_cooccurrence",
        "cypher": """
            MATCH (q:Question)-[:TAGGED_WITH]->(t1:Tag)
            MATCH (q)-[:TAGGED_WITH]->(t2:Tag)
            WHERE t1.Id < t2.Id
            RETURN t1.TagName AS tag1, t2.TagName AS tag2, count(*) AS cooccurs
            ORDER BY cooccurs DESC, tag1 ASC, tag2 ASC
            LIMIT 10
        """,
    },
    {
        "name": "top_questions_by_score",
        "cypher": """
            MATCH (q:Question)
            RETURN q.Id AS question_id, q.Score AS score
            ORDER BY score DESC, question_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "questions_with_most_answers",
        "cypher": """
            MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
            RETURN q.Id AS question_id, count(a) AS answers
            ORDER BY answers DESC, question_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "asker_answerer_pairs",
        "cypher": """
            MATCH (asker:User)-[:ASKED]->(q:Question)<-[:HAS_ANSWER]-(a:Answer)<-[:ANSWERED]-(answerer:User)
            RETURN asker.Id AS asker_id, answerer.Id AS answerer_id, count(a) AS interactions
            ORDER BY interactions DESC, asker_id ASC, answerer_id ASC
            LIMIT 10
        """,
    },
    {
        "name": "top_badges",
        "cypher": """
            MATCH (:User)-[:EARNED]->(b:Badge)
            RETURN b.Name AS badge, count(*) AS earned
            ORDER BY earned DESC, badge ASC
            LIMIT 10
        """,
    },
    # Luca is investigating the COUNT() optimization regression that breaks this query.
    {
        "name": "top_questions_by_total_comments",
        "cypher": """
            MATCH (q:Question)
            OPTIONAL MATCH (c1:Comment)-[:COMMENTED_ON]->(q)
            WITH q, count(c1) AS direct_comments
            OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
            OPTIONAL MATCH (c2:Comment)-[:COMMENTED_ON_ANSWER]->(a)
            WITH q, direct_comments, count(c2) AS answer_comments
            RETURN q.Id AS question_id, direct_comments + answer_comments AS total_comments
            ORDER BY total_comments DESC, question_id ASC
            LIMIT 10
        """,
    },
]


def get_arcadedb_module():
    try:
        import arcadedb_embedded as arcadedb
        from arcadedb_embedded.exceptions import ArcadeDBError
    except ImportError:
        return None, None
    return arcadedb, ArcadeDBError


def get_ladybug_module():
    try:
        import real_ladybug as lb
    except ImportError:
        return None
    return lb


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None


def to_epoch_millis(value: Optional[datetime]) -> Optional[int]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def format_bytes_binary(value: int) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if value < 1024:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}PiB"


def get_dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _, files in os.walk(path):
        for name in files:
            total += (Path(root) / name).stat().st_size
    return total


def start_rss_sampler(
    interval_sec: float = 0.2,
) -> Tuple[threading.Event, dict, threading.Thread]:
    stop_event = threading.Event()
    state = {"max_kb": 0}

    def run():
        while not stop_event.is_set():
            try:
                with open("/proc/self/status", "r", encoding="utf-8") as handle:
                    for line in handle:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                rss_kb = int(parts[1])
                                state["max_kb"] = max(state["max_kb"], rss_kb)
                            break
            except FileNotFoundError:
                pass
            time.sleep(interval_sec)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop_event, state, thread


class CsvTableWriter:
    def __init__(self, path: Path, fieldnames: List[str], label: str):
        self.path = path
        self.fieldnames = fieldnames
        self.label = label
        self.row_count = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=self.fieldnames)
        self.writer.writeheader()

    def write_rows(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        for row in rows:
            payload = {}
            for key in self.fieldnames:
                value = row.get(key)
                if value is None:
                    payload[key] = ""
                elif isinstance(value, str):
                    payload[key] = value.replace("\r", " ").replace("\n", " ")
                else:
                    payload[key] = value
            self.writer.writerow(payload)
            self.row_count += 1

    def close(self) -> None:
        self.handle.close()


def iter_xml_rows(xml_path: Path) -> Iterable[Dict[str, str]]:
    context = etree.iterparse(str(xml_path), events=("end",), tag="row")
    for _, elem in context:
        yield elem.attrib
        elem.clear()


def parse_tags(tags_str: Optional[str]) -> List[str]:
    if not tags_str:
        return []
    if "|" in tags_str:
        return [t for t in tags_str.split("|") if t]
    return [
        t
        for t in tags_str.replace(
            "><",
            "|",
        )
        .replace("<", "")
        .replace(">", "")
        .split("|")
        if t
    ]


def get_retry_config(dataset_size: str) -> Dict[str, int]:
    size = dataset_size.split("-")[-1] if "-" in dataset_size else dataset_size
    configs = {
        "tiny": {"retry_delay": 10, "max_retries": 60},
        "small": {"retry_delay": 60, "max_retries": 120},
        "medium": {"retry_delay": 180, "max_retries": 200},
        "large": {"retry_delay": 300, "max_retries": 200},
    }
    return configs.get(size, configs["tiny"])


def count_arcadedb_by_type(db) -> Tuple[Dict[str, int], Dict[str, int]]:
    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for label in VERTEX_TYPES:
        rows = db.query(
            "opencypher",
            f"MATCH (n:{label}) RETURN count(n) AS count",
        ).to_list()
        node_counts[label] = int(rows[0].get("count", 0)) if rows else 0
    for label in EDGE_TYPES:
        rows = db.query(
            "opencypher",
            f"MATCH ()-[r:{label}]->() RETURN count(r) AS count",
        ).to_list()
        edge_counts[label] = int(rows[0].get("count", 0)) if rows else 0
    return node_counts, edge_counts


def count_ladybug_by_type(conn) -> Tuple[Dict[str, int], Dict[str, int]]:
    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for label in VERTEX_TYPES:
        rows = conn.execute(f"MATCH (n:{label}) RETURN count(n) AS count").get_all()
        node_counts[label] = int(rows[0][0]) if rows else 0
    for label in EDGE_TYPES:
        rows = conn.execute(
            f"MATCH ()-[r:{label}]->() RETURN count(r) AS count"
        ).get_all()
        edge_counts[label] = int(rows[0][0]) if rows else 0
    return node_counts, edge_counts


def collect_graph_counts_arcadedb(db) -> Dict[str, object]:
    node_rows = db.query("opencypher", "MATCH (n) RETURN count(n) AS count").to_list()
    edge_rows = db.query(
        "opencypher", "MATCH ()-[r]->() RETURN count(r) AS count"
    ).to_list()
    node_total = int(node_rows[0].get("count", 0)) if node_rows else 0
    edge_total = int(edge_rows[0].get("count", 0)) if edge_rows else 0
    node_counts, edge_counts = count_arcadedb_by_type(db)
    return {
        "node_total": node_total,
        "edge_total": edge_total,
        "node_counts_by_type": node_counts,
        "edge_counts_by_type": edge_counts,
    }


def collect_graph_counts_ladybug(conn) -> Dict[str, object]:
    node_rows = conn.execute("MATCH (n) RETURN count(n) AS count").get_all()
    edge_rows = conn.execute("MATCH ()-[r]->() RETURN count(r) AS count").get_all()
    node_total = int(node_rows[0][0]) if node_rows else 0
    edge_total = int(edge_rows[0][0]) if edge_rows else 0
    node_counts, edge_counts = count_ladybug_by_type(conn)
    return {
        "node_total": node_total,
        "edge_total": edge_total,
        "node_counts_by_type": node_counts,
        "edge_counts_by_type": edge_counts,
    }


def create_arcadedb_schema(db):
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "Id", "INTEGER")
    db.schema.create_property("User", "DisplayName", "STRING")
    db.schema.create_property("User", "Reputation", "INTEGER")
    db.schema.create_property("User", "CreationDate", "INTEGER")
    db.schema.create_property("User", "Views", "INTEGER")
    db.schema.create_property("User", "UpVotes", "INTEGER")
    db.schema.create_property("User", "DownVotes", "INTEGER")

    db.schema.create_vertex_type("Question")
    db.schema.create_property("Question", "Id", "INTEGER")
    db.schema.create_property("Question", "Title", "STRING")
    db.schema.create_property("Question", "Body", "STRING")
    db.schema.create_property("Question", "Score", "INTEGER")
    db.schema.create_property("Question", "ViewCount", "INTEGER")
    db.schema.create_property("Question", "CreationDate", "INTEGER")
    db.schema.create_property("Question", "AnswerCount", "INTEGER")
    db.schema.create_property("Question", "CommentCount", "INTEGER")
    db.schema.create_property("Question", "FavoriteCount", "INTEGER")

    db.schema.create_vertex_type("Answer")
    db.schema.create_property("Answer", "Id", "INTEGER")
    db.schema.create_property("Answer", "Body", "STRING")
    db.schema.create_property("Answer", "Score", "INTEGER")
    db.schema.create_property("Answer", "CreationDate", "INTEGER")
    db.schema.create_property("Answer", "CommentCount", "INTEGER")

    db.schema.create_vertex_type("Tag")
    db.schema.create_property("Tag", "Id", "INTEGER")
    db.schema.create_property("Tag", "TagName", "STRING")
    db.schema.create_property("Tag", "Count", "INTEGER")

    db.schema.create_vertex_type("Badge")
    db.schema.create_property("Badge", "Id", "INTEGER")
    db.schema.create_property("Badge", "Name", "STRING")
    db.schema.create_property("Badge", "Date", "INTEGER")
    db.schema.create_property("Badge", "Class", "INTEGER")

    db.schema.create_vertex_type("Comment")
    db.schema.create_property("Comment", "Id", "INTEGER")
    db.schema.create_property("Comment", "Text", "STRING")
    db.schema.create_property("Comment", "Score", "INTEGER")
    db.schema.create_property("Comment", "CreationDate", "INTEGER")

    db.schema.create_edge_type("ASKED")
    db.schema.create_property("ASKED", "CreationDate", "INTEGER")
    db.schema.create_edge_type("ANSWERED")
    db.schema.create_property("ANSWERED", "CreationDate", "INTEGER")
    db.schema.create_edge_type("HAS_ANSWER")
    db.schema.create_edge_type("ACCEPTED_ANSWER")
    db.schema.create_edge_type("TAGGED_WITH")
    db.schema.create_edge_type("COMMENTED_ON")
    db.schema.create_property("COMMENTED_ON", "CreationDate", "INTEGER")
    db.schema.create_property("COMMENTED_ON", "Score", "INTEGER")
    db.schema.create_edge_type("COMMENTED_ON_ANSWER")
    db.schema.create_property("COMMENTED_ON_ANSWER", "CreationDate", "INTEGER")
    db.schema.create_property("COMMENTED_ON_ANSWER", "Score", "INTEGER")
    db.schema.create_edge_type("EARNED")
    db.schema.create_property("EARNED", "Date", "INTEGER")
    db.schema.create_property("EARNED", "Class", "INTEGER")
    db.schema.create_edge_type("LINKED_TO")
    db.schema.create_property("LINKED_TO", "LinkTypeId", "INTEGER")
    db.schema.create_property("LINKED_TO", "CreationDate", "INTEGER")

    db.async_executor().wait_completion()


def create_arcadedb_indexes(db, retry_delay: int = 10, max_retries: int = 60) -> float:
    start = time.time()
    failed_indexes: List[Tuple[str, List[str], str]] = []

    for idx, (table, props, unique) in enumerate(INDEX_DEFS, 1):
        created = False
        for attempt in range(1, max_retries + 1):
            try:
                db.schema.create_index(table, props, unique=unique)
                created = True
                break
            except Exception as exc:
                error_msg = str(exc)
                retryable = (
                    "NeedRetryException" in error_msg
                    and "asynchronous tasks" in error_msg
                )
                if retryable and attempt < max_retries:
                    elapsed = attempt * retry_delay
                    print(
                        "    Waiting for background tasks to finish "
                        f"(index {idx}/{len(INDEX_DEFS)}, "
                        f"attempt {attempt}/{max_retries}, "
                        f"{elapsed}s elapsed)..."
                    )
                    time.sleep(retry_delay)
                    continue

                failed_indexes.append((table, props, error_msg))
                break
        if not created:
            continue

    async_exec = db.async_executor()
    async_exec.wait_completion()
    elapsed = time.time() - start
    if failed_indexes:
        table, props, error_msg = failed_indexes[0]
        prop_list = ",".join(props)
        raise RuntimeError(
            "Failed to create "
            f"{len(failed_indexes)} indexes. "
            f"First failure: {table}[{prop_list}]: {error_msg}"
        )
    return elapsed


def create_ladybug_schema(conn):
    conn.execute(
        "CREATE NODE TABLE User(Id INT64 PRIMARY KEY, DisplayName STRING, Reputation INT64, CreationDate INT64, Views INT64, UpVotes INT64, DownVotes INT64)"
    )
    conn.execute(
        "CREATE NODE TABLE Question(Id INT64 PRIMARY KEY, Title STRING, Body STRING, Score INT64, ViewCount INT64, CreationDate INT64, AnswerCount INT64, CommentCount INT64, FavoriteCount INT64)"
    )
    conn.execute(
        "CREATE NODE TABLE Answer(Id INT64 PRIMARY KEY, Body STRING, Score INT64, CreationDate INT64, CommentCount INT64)"
    )
    conn.execute(
        "CREATE NODE TABLE Tag(Id INT64 PRIMARY KEY, TagName STRING, Count INT64)"
    )
    conn.execute(
        "CREATE NODE TABLE Badge(Id INT64 PRIMARY KEY, Name STRING, Date INT64, Class INT64)"
    )
    conn.execute(
        "CREATE NODE TABLE Comment(Id INT64 PRIMARY KEY, Text STRING, Score INT64, CreationDate INT64)"
    )

    conn.execute("CREATE REL TABLE ASKED(FROM User TO Question, CreationDate INT64)")
    conn.execute("CREATE REL TABLE ANSWERED(FROM User TO Answer, CreationDate INT64)")
    conn.execute("CREATE REL TABLE HAS_ANSWER(FROM Question TO Answer)")
    conn.execute("CREATE REL TABLE ACCEPTED_ANSWER(FROM Question TO Answer)")
    conn.execute("CREATE REL TABLE TAGGED_WITH(FROM Question TO Tag)")
    conn.execute(
        "CREATE REL TABLE COMMENTED_ON(FROM Comment TO Question, CreationDate INT64, Score INT64)"
    )
    conn.execute(
        "CREATE REL TABLE COMMENTED_ON_ANSWER(FROM Comment TO Answer, CreationDate INT64, Score INT64)"
    )
    conn.execute("CREATE REL TABLE EARNED(FROM User TO Badge, Date INT64, Class INT64)")
    conn.execute(
        "CREATE REL TABLE LINKED_TO(FROM Question TO Question, LinkTypeId INT64, CreationDate INT64)"
    )


def arcadedb_insert_vertices(db, vertex_type: str, rows: List[Dict[str, Any]]):
    if not rows:
        return
    chunk_size = 1000
    for offset in range(0, len(rows), chunk_size):
        chunk = rows[offset : offset + chunk_size]
        for row in chunk:
            props = format_cypher_props(row)
            statement = f"CREATE (n:{vertex_type} {props})"
            db.command("opencypher", statement)


def cypher_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    text = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def format_cypher_props(props: Dict[str, Any]) -> str:
    if not props:
        return ""
    items = [f"{key}: {cypher_literal(value)}" for key, value in props.items()]
    return "{" + ", ".join(items) + "}"


def arcadedb_insert_edges(
    db,
    edge_type: str,
    from_label: str,
    to_label: str,
    rows: List[Dict[str, Any]],
    prop_keys: List[str],
):
    if not rows:
        return
    chunk_size = 1000
    for offset in range(0, len(rows), chunk_size):
        chunk = rows[offset : offset + chunk_size]
        for row in chunk:
            props = {key: row.get(key) for key in prop_keys}
            prop_sql = format_cypher_props(props)
            if prop_sql:
                prop_sql = " " + prop_sql
            from_id = cypher_literal(row.get("from_id"))
            to_id = cypher_literal(row.get("to_id"))
            statement = (
                f"MATCH (a:{from_label} {{Id: {from_id}}}), "
                f"(b:{to_label} {{Id: {to_id}}}) "
                f"CREATE (a)-[:{edge_type}{prop_sql}]->(b)"
            )
            db.command("opencypher", statement)


def ladybug_insert_vertices(conn, label: str, rows: List[Dict[str, Any]]):
    if not rows:
        return
    chunk_size = 1000
    for offset in range(0, len(rows), chunk_size):
        chunk = rows[offset : offset + chunk_size]
        statements = []
        for row in chunk:
            props = format_cypher_props(row)
            statements.append(f"CREATE (n:{label} {props})")
        conn.execute(";".join(statements))


def ladybug_insert_edges(
    conn,
    edge_type: str,
    from_label: str,
    to_label: str,
    rows: List[Dict[str, Any]],
    prop_keys: List[str],
):
    if not rows:
        return
    chunk_size = 1000
    for offset in range(0, len(rows), chunk_size):
        chunk = rows[offset : offset + chunk_size]
        statements = []
        for row in chunk:
            props = {key: row.get(key) for key in prop_keys}
            prop_sql = format_cypher_props(props)
            if prop_sql:
                prop_sql = " " + prop_sql
            from_id = cypher_literal(row.get("from_id"))
            to_id = cypher_literal(row.get("to_id"))
            statements.append(
                f"MATCH (a:{from_label} {{Id: {from_id}}}), "
                f"(b:{to_label} {{Id: {to_id}}}) "
                f"CREATE (a)-[:{edge_type}{prop_sql}]->(b)"
            )
        conn.execute(";".join(statements))


def copy_csv_table(conn, table_name: str, csv_path: Path, row_count: int) -> float:
    print(f"  COPY {table_name}: {row_count:,} rows")
    start = time.time()
    conn.execute(f"COPY {table_name} FROM '{csv_path.as_posix()}'")
    elapsed = time.time() - start
    print(f"  COPY {table_name} done in {elapsed:.2f}s")
    return elapsed


def load_graph_arcadedb(
    db,
    data_dir: Path,
    batch_size: int,
    retry_config: Dict[str, int],
) -> Tuple[dict, dict, float]:
    stats = {"nodes": {}, "edges": {}}
    ids = {"users": [], "questions": [], "answers": []}
    max_ids = {"user": 0, "question": 0}
    tag_map: Dict[str, int] = {}
    question_ids: set[int] = set()
    answer_ids: set[int] = set()

    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Tags.xml"):
        tag_id = parse_int(attrs.get("Id"))
        tag_name = attrs.get("TagName")
        if tag_id is None or tag_name is None:
            continue
        tag_map[tag_name] = tag_id
        batch.append(
            {
                "Id": tag_id,
                "TagName": tag_name,
                "Count": parse_int(attrs.get("Count")),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_vertices(db, "Tag", batch)
            batch = []
    if batch:
        arcadedb_insert_vertices(db, "Tag", batch)
    stats["nodes"]["Tag"] = time.time() - start

    start = time.time()
    batch = []
    for attrs in iter_xml_rows(data_dir / "Users.xml"):
        user_id = parse_int(attrs.get("Id"))
        if user_id is None:
            continue
        max_ids["user"] = max(max_ids["user"], user_id)
        ids["users"].append(user_id)
        batch.append(
            {
                "Id": user_id,
                "DisplayName": attrs.get("DisplayName"),
                "Reputation": parse_int(attrs.get("Reputation")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
                "Views": parse_int(attrs.get("Views")),
                "UpVotes": parse_int(attrs.get("UpVotes")),
                "DownVotes": parse_int(attrs.get("DownVotes")),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_vertices(db, "User", batch)
            batch = []
    if batch:
        arcadedb_insert_vertices(db, "User", batch)
    stats["nodes"]["User"] = time.time() - start

    start = time.time()
    batch_questions: List[Dict[str, Any]] = []
    batch_answers: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        post_id = parse_int(attrs.get("Id"))
        post_type = parse_int(attrs.get("PostTypeId"))
        if post_id is None or post_type is None:
            continue
        if post_type == 1:
            max_ids["question"] = max(max_ids["question"], post_id)
            ids["questions"].append(post_id)
            question_ids.add(post_id)
            batch_questions.append(
                {
                    "Id": post_id,
                    "Title": attrs.get("Title"),
                    "Body": attrs.get("Body"),
                    "Score": parse_int(attrs.get("Score")),
                    "ViewCount": parse_int(attrs.get("ViewCount")),
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                    "AnswerCount": parse_int(attrs.get("AnswerCount")),
                    "CommentCount": parse_int(attrs.get("CommentCount")),
                    "FavoriteCount": parse_int(attrs.get("FavoriteCount")),
                }
            )
        elif post_type == 2:
            answer_ids.add(post_id)
            batch_answers.append(
                {
                    "Id": post_id,
                    "Body": attrs.get("Body"),
                    "Score": parse_int(attrs.get("Score")),
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                    "CommentCount": parse_int(attrs.get("CommentCount")),
                }
            )
        if len(batch_questions) >= batch_size:
            arcadedb_insert_vertices(db, "Question", batch_questions)
            batch_questions = []
        if len(batch_answers) >= batch_size:
            arcadedb_insert_vertices(db, "Answer", batch_answers)
            batch_answers = []
    if batch_questions:
        arcadedb_insert_vertices(db, "Question", batch_questions)
    if batch_answers:
        arcadedb_insert_vertices(db, "Answer", batch_answers)
    stats["nodes"]["Post"] = time.time() - start

    start = time.time()
    batch = []
    for attrs in iter_xml_rows(data_dir / "Badges.xml"):
        badge_id = parse_int(attrs.get("Id"))
        if badge_id is None:
            continue
        batch.append(
            {
                "Id": badge_id,
                "Name": attrs.get("Name"),
                "Date": to_epoch_millis(parse_datetime(attrs.get("Date"))),
                "Class": parse_int(attrs.get("Class")),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_vertices(db, "Badge", batch)
            batch = []
    if batch:
        arcadedb_insert_vertices(db, "Badge", batch)
    stats["nodes"]["Badge"] = time.time() - start

    start = time.time()
    batch = []
    for attrs in iter_xml_rows(data_dir / "Comments.xml"):
        comment_id = parse_int(attrs.get("Id"))
        if comment_id is None:
            continue
        batch.append(
            {
                "Id": comment_id,
                "Text": attrs.get("Text"),
                "Score": parse_int(attrs.get("Score")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_vertices(db, "Comment", batch)
            batch = []
    if batch:
        arcadedb_insert_vertices(db, "Comment", batch)
    stats["nodes"]["Comment"] = time.time() - start

    # Build indexes before edge creation so batched MATCH-by-Id edge inserts
    # can resolve endpoints efficiently.
    print("Building indexes...")
    print(
        "  Retry: "
        f"{retry_config['retry_delay']}s delay, "
        f"{retry_config['max_retries']} max attempts"
    )
    index_time = create_arcadedb_indexes(
        db,
        retry_delay=retry_config["retry_delay"],
        max_retries=retry_config["max_retries"],
    )

    stats["edges"]["ASKED"] = create_edges_arcadedb_asked(db, data_dir, batch_size)
    stats["edges"]["ANSWERED"] = create_edges_arcadedb_answered(
        db, data_dir, batch_size
    )
    stats["edges"]["HAS_ANSWER"] = create_edges_arcadedb_has_answer(
        db, data_dir, batch_size
    )
    stats["edges"]["ACCEPTED_ANSWER"] = create_edges_arcadedb_accepted_answer(
        db, data_dir, batch_size
    )
    stats["edges"]["TAGGED_WITH"] = create_edges_arcadedb_tagged_with(
        db, data_dir, tag_map, batch_size
    )
    commented_stats = create_edges_arcadedb_commented_on(
        db, data_dir, question_ids, answer_ids, batch_size
    )
    stats["edges"].update(commented_stats)
    stats["edges"]["EARNED"] = create_edges_arcadedb_earned(db, data_dir, batch_size)
    stats["edges"]["LINKED_TO"] = create_edges_arcadedb_linked_to(
        db, data_dir, question_ids, batch_size
    )

    return stats, {"ids": ids, "max_ids": max_ids}, index_time


def create_edges_arcadedb_asked(
    db,
    data_dir: Path,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": post_id,
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "ASKED",
                "User",
                "Question",
                batch,
                ["CreationDate"],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "ASKED",
            "User",
            "Question",
            batch,
            ["CreationDate"],
        )
    return time.time() - start


def create_edges_arcadedb_answered(
    db,
    data_dir: Path,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": post_id,
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "ANSWERED",
                "User",
                "Answer",
                batch,
                ["CreationDate"],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "ANSWERED",
            "User",
            "Answer",
            batch,
            ["CreationDate"],
        )
    return time.time() - start


def create_edges_arcadedb_has_answer(
    db,
    data_dir: Path,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        parent_id = parse_int(attrs.get("ParentId"))
        answer_id = parse_int(attrs.get("Id"))
        if parent_id is None or answer_id is None:
            continue
        batch.append({"from_id": parent_id, "to_id": answer_id})
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "HAS_ANSWER",
                "Question",
                "Answer",
                batch,
                [],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "HAS_ANSWER",
            "Question",
            "Answer",
            batch,
            [],
        )
    return time.time() - start


def create_edges_arcadedb_accepted_answer(
    db,
    data_dir: Path,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        answer_id = parse_int(attrs.get("AcceptedAnswerId"))
        if question_id is None or answer_id is None:
            continue
        batch.append({"from_id": question_id, "to_id": answer_id})
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "ACCEPTED_ANSWER",
                "Question",
                "Answer",
                batch,
                [],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "ACCEPTED_ANSWER",
            "Question",
            "Answer",
            batch,
            [],
        )
    return time.time() - start


def create_edges_arcadedb_tagged_with(
    db,
    data_dir: Path,
    tag_map: Dict[str, int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        if question_id is None:
            continue
        tags = parse_tags(attrs.get("Tags"))
        for tag in tags:
            tag_id = tag_map.get(tag)
            if tag_id is None:
                continue
            batch.append({"from_id": question_id, "to_id": tag_id})
            if len(batch) >= batch_size:
                arcadedb_insert_edges(
                    db,
                    "TAGGED_WITH",
                    "Question",
                    "Tag",
                    batch,
                    [],
                )
                batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "TAGGED_WITH",
            "Question",
            "Tag",
            batch,
            [],
        )
    return time.time() - start


def create_edges_arcadedb_commented_on(
    db,
    data_dir: Path,
    question_ids: set,
    answer_ids: set,
    batch_size: int,
) -> Dict[str, float]:
    start = time.time()
    batch_question: List[Dict[str, Any]] = []
    batch_answer: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Comments.xml"):
        comment_id = parse_int(attrs.get("Id"))
        post_id = parse_int(attrs.get("PostId"))
        if comment_id is None or post_id is None:
            continue
        edge_type = None
        target_id = None
        if post_id in question_ids:
            edge_type = "COMMENTED_ON"
            target_id = post_id
        elif post_id in answer_ids:
            edge_type = "COMMENTED_ON_ANSWER"
            target_id = post_id
        if target_id is None:
            continue
        payload = {
            "from_id": comment_id,
            "to_id": target_id,
            "CreationDate": to_epoch_millis(parse_datetime(attrs.get("CreationDate"))),
            "Score": parse_int(attrs.get("Score")),
        }
        if edge_type == "COMMENTED_ON":
            batch_question.append(payload)
        elif edge_type == "COMMENTED_ON_ANSWER":
            batch_answer.append(payload)
        if len(batch_question) >= batch_size:
            arcadedb_insert_edges(
                db,
                "COMMENTED_ON",
                "Comment",
                "Question",
                batch_question,
                ["CreationDate", "Score"],
            )
            batch_question = []
        if len(batch_answer) >= batch_size:
            arcadedb_insert_edges(
                db,
                "COMMENTED_ON_ANSWER",
                "Comment",
                "Answer",
                batch_answer,
                ["CreationDate", "Score"],
            )
            batch_answer = []
    if batch_question:
        arcadedb_insert_edges(
            db,
            "COMMENTED_ON",
            "Comment",
            "Question",
            batch_question,
            ["CreationDate", "Score"],
        )
    if batch_answer:
        arcadedb_insert_edges(
            db,
            "COMMENTED_ON_ANSWER",
            "Comment",
            "Answer",
            batch_answer,
            ["CreationDate", "Score"],
        )
    elapsed = time.time() - start
    return {
        "COMMENTED_ON": elapsed,
        "COMMENTED_ON_ANSWER": elapsed,
    }


def create_edges_arcadedb_earned(
    db,
    data_dir: Path,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Badges.xml"):
        user_id = parse_int(attrs.get("UserId"))
        badge_id = parse_int(attrs.get("Id"))
        if user_id is None or badge_id is None:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": badge_id,
                "Date": to_epoch_millis(parse_datetime(attrs.get("Date"))),
                "Class": parse_int(attrs.get("Class")),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "EARNED",
                "User",
                "Badge",
                batch,
                ["Date", "Class"],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "EARNED",
            "User",
            "Badge",
            batch,
            ["Date", "Class"],
        )
    return time.time() - start


def create_edges_arcadedb_linked_to(
    db,
    data_dir: Path,
    question_ids: set,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "PostLinks.xml"):
        post_id = parse_int(attrs.get("PostId"))
        related_id = parse_int(attrs.get("RelatedPostId"))
        if post_id is None or related_id is None:
            continue
        if post_id not in question_ids or related_id not in question_ids:
            continue
        batch.append(
            {
                "from_id": post_id,
                "to_id": related_id,
                "LinkTypeId": parse_int(attrs.get("LinkTypeId")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            arcadedb_insert_edges(
                db,
                "LINKED_TO",
                "Question",
                "Question",
                batch,
                ["LinkTypeId", "CreationDate"],
            )
            batch = []
    if batch:
        arcadedb_insert_edges(
            db,
            "LINKED_TO",
            "Question",
            "Question",
            batch,
            ["LinkTypeId", "CreationDate"],
        )
    return time.time() - start


def load_graph_ladybug(
    conn,
    db_path: Path,
    data_dir: Path,
    batch_size: int,
) -> Tuple[dict, dict]:
    # Default to native bulk ingest path for Ladybug: staged CSV + COPY.
    stats = {"nodes": {}, "edges": {}}
    ids = {"users": [], "questions": [], "answers": []}
    max_ids = {"user": 0, "question": 0}
    tag_map: Dict[str, int] = {}
    question_ids: set[int] = set()
    answer_ids: set[int] = set()
    user_ids: set[int] = set()
    badge_ids: set[int] = set()
    comment_ids: set[int] = set()

    csv_dir = db_path / "ladybug_csv_bulk"
    if csv_dir.exists():
        shutil.rmtree(csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)

    writers = {
        "Tag": CsvTableWriter(csv_dir / "Tag.csv", ["Id", "TagName", "Count"], "Tag"),
        "User": CsvTableWriter(
            csv_dir / "User.csv",
            [
                "Id",
                "DisplayName",
                "Reputation",
                "CreationDate",
                "Views",
                "UpVotes",
                "DownVotes",
            ],
            "User",
        ),
        "Question": CsvTableWriter(
            csv_dir / "Question.csv",
            [
                "Id",
                "Title",
                "Body",
                "Score",
                "ViewCount",
                "CreationDate",
                "AnswerCount",
                "CommentCount",
                "FavoriteCount",
            ],
            "Question",
        ),
        "Answer": CsvTableWriter(
            csv_dir / "Answer.csv",
            ["Id", "Body", "Score", "CreationDate", "CommentCount"],
            "Answer",
        ),
        "Badge": CsvTableWriter(
            csv_dir / "Badge.csv",
            ["Id", "Name", "Date", "Class"],
            "Badge",
        ),
        "Comment": CsvTableWriter(
            csv_dir / "Comment.csv",
            ["Id", "Text", "Score", "CreationDate"],
            "Comment",
        ),
        "ASKED": CsvTableWriter(
            csv_dir / "ASKED.csv", ["FROM", "TO", "CreationDate"], "ASKED"
        ),
        "ANSWERED": CsvTableWriter(
            csv_dir / "ANSWERED.csv", ["FROM", "TO", "CreationDate"], "ANSWERED"
        ),
        "HAS_ANSWER": CsvTableWriter(
            csv_dir / "HAS_ANSWER.csv", ["FROM", "TO"], "HAS_ANSWER"
        ),
        "ACCEPTED_ANSWER": CsvTableWriter(
            csv_dir / "ACCEPTED_ANSWER.csv", ["FROM", "TO"], "ACCEPTED_ANSWER"
        ),
        "TAGGED_WITH": CsvTableWriter(
            csv_dir / "TAGGED_WITH.csv", ["FROM", "TO"], "TAGGED_WITH"
        ),
        "COMMENTED_ON": CsvTableWriter(
            csv_dir / "COMMENTED_ON.csv",
            ["FROM", "TO", "CreationDate", "Score"],
            "COMMENTED_ON",
        ),
        "COMMENTED_ON_ANSWER": CsvTableWriter(
            csv_dir / "COMMENTED_ON_ANSWER.csv",
            ["FROM", "TO", "CreationDate", "Score"],
            "COMMENTED_ON_ANSWER",
        ),
        "EARNED": CsvTableWriter(
            csv_dir / "EARNED.csv", ["FROM", "TO", "Date", "Class"], "EARNED"
        ),
        "LINKED_TO": CsvTableWriter(
            csv_dir / "LINKED_TO.csv",
            ["FROM", "TO", "LinkTypeId", "CreationDate"],
            "LINKED_TO",
        ),
    }

    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Tags.xml"):
        tag_id = parse_int(attrs.get("Id"))
        tag_name = attrs.get("TagName")
        if tag_id is None or tag_name is None:
            continue
        tag_map[tag_name] = tag_id
        batch.append(
            {
                "Id": tag_id,
                "TagName": tag_name,
                "Count": parse_int(attrs.get("Count")),
            }
        )
        if len(batch) >= batch_size:
            writers["Tag"].write_rows(batch)
            batch = []
    if batch:
        writers["Tag"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Users.xml"):
        user_id = parse_int(attrs.get("Id"))
        if user_id is None:
            continue
        max_ids["user"] = max(max_ids["user"], user_id)
        ids["users"].append(user_id)
        user_ids.add(user_id)
        batch.append(
            {
                "Id": user_id,
                "DisplayName": attrs.get("DisplayName"),
                "Reputation": parse_int(attrs.get("Reputation")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
                "Views": parse_int(attrs.get("Views")),
                "UpVotes": parse_int(attrs.get("UpVotes")),
                "DownVotes": parse_int(attrs.get("DownVotes")),
            }
        )
        if len(batch) >= batch_size:
            writers["User"].write_rows(batch)
            batch = []
    if batch:
        writers["User"].write_rows(batch)

    batch_questions: List[Dict[str, Any]] = []
    batch_answers: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        post_id = parse_int(attrs.get("Id"))
        post_type = parse_int(attrs.get("PostTypeId"))
        if post_id is None or post_type is None:
            continue
        if post_type == 1:
            max_ids["question"] = max(max_ids["question"], post_id)
            ids["questions"].append(post_id)
            question_ids.add(post_id)
            batch_questions.append(
                {
                    "Id": post_id,
                    "Title": attrs.get("Title"),
                    "Body": attrs.get("Body"),
                    "Score": parse_int(attrs.get("Score")),
                    "ViewCount": parse_int(attrs.get("ViewCount")),
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                    "AnswerCount": parse_int(attrs.get("AnswerCount")),
                    "CommentCount": parse_int(attrs.get("CommentCount")),
                    "FavoriteCount": parse_int(attrs.get("FavoriteCount")),
                }
            )
        elif post_type == 2:
            answer_ids.add(post_id)
            batch_answers.append(
                {
                    "Id": post_id,
                    "Body": attrs.get("Body"),
                    "Score": parse_int(attrs.get("Score")),
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                    "CommentCount": parse_int(attrs.get("CommentCount")),
                }
            )
        if len(batch_questions) >= batch_size:
            writers["Question"].write_rows(batch_questions)
            batch_questions = []
        if len(batch_answers) >= batch_size:
            writers["Answer"].write_rows(batch_answers)
            batch_answers = []
    if batch_questions:
        writers["Question"].write_rows(batch_questions)
    if batch_answers:
        writers["Answer"].write_rows(batch_answers)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Badges.xml"):
        badge_id = parse_int(attrs.get("Id"))
        if badge_id is None:
            continue
        badge_ids.add(badge_id)
        batch.append(
            {
                "Id": badge_id,
                "Name": attrs.get("Name"),
                "Date": to_epoch_millis(parse_datetime(attrs.get("Date"))),
                "Class": parse_int(attrs.get("Class")),
            }
        )
        if len(batch) >= batch_size:
            writers["Badge"].write_rows(batch)
            batch = []
    if batch:
        writers["Badge"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Comments.xml"):
        comment_id = parse_int(attrs.get("Id"))
        if comment_id is None:
            continue
        comment_ids.add(comment_id)
        batch.append(
            {
                "Id": comment_id,
                "Text": attrs.get("Text"),
                "Score": parse_int(attrs.get("Score")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            writers["Comment"].write_rows(batch)
            batch = []
    if batch:
        writers["Comment"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        post_type = parse_int(attrs.get("PostTypeId"))
        if post_type not in (1, 2):
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        if user_id not in user_ids:
            continue
        if post_type == 1 and post_id in question_ids:
            batch.append(
                {
                    "FROM": user_id,
                    "TO": post_id,
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                }
            )
            if len(batch) >= batch_size:
                writers["ASKED"].write_rows(batch)
                batch = []
    if batch:
        writers["ASKED"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        if user_id in user_ids and post_id in answer_ids:
            batch.append(
                {
                    "FROM": user_id,
                    "TO": post_id,
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                }
            )
            if len(batch) >= batch_size:
                writers["ANSWERED"].write_rows(batch)
                batch = []
    if batch:
        writers["ANSWERED"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        parent_id = parse_int(attrs.get("ParentId"))
        answer_id = parse_int(attrs.get("Id"))
        if parent_id is None or answer_id is None:
            continue
        if parent_id in question_ids and answer_id in answer_ids:
            batch.append({"FROM": parent_id, "TO": answer_id})
            if len(batch) >= batch_size:
                writers["HAS_ANSWER"].write_rows(batch)
                batch = []
    if batch:
        writers["HAS_ANSWER"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        answer_id = parse_int(attrs.get("AcceptedAnswerId"))
        if question_id is None or answer_id is None:
            continue
        if question_id in question_ids and answer_id in answer_ids:
            batch.append({"FROM": question_id, "TO": answer_id})
            if len(batch) >= batch_size:
                writers["ACCEPTED_ANSWER"].write_rows(batch)
                batch = []
    if batch:
        writers["ACCEPTED_ANSWER"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        if question_id is None or question_id not in question_ids:
            continue
        for tag in parse_tags(attrs.get("Tags")):
            tag_id = tag_map.get(tag)
            if tag_id is None:
                continue
            batch.append({"FROM": question_id, "TO": tag_id})
            if len(batch) >= batch_size:
                writers["TAGGED_WITH"].write_rows(batch)
                batch = []
    if batch:
        writers["TAGGED_WITH"].write_rows(batch)

    batch_question: List[Dict[str, Any]] = []
    batch_answer: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Comments.xml"):
        comment_id = parse_int(attrs.get("Id"))
        post_id = parse_int(attrs.get("PostId"))
        if comment_id is None or post_id is None:
            continue
        if comment_id not in comment_ids:
            continue
        payload = {
            "FROM": comment_id,
            "TO": post_id,
            "CreationDate": to_epoch_millis(parse_datetime(attrs.get("CreationDate"))),
            "Score": parse_int(attrs.get("Score")),
        }
        if post_id in question_ids:
            batch_question.append(payload)
        elif post_id in answer_ids:
            batch_answer.append(payload)
        if len(batch_question) >= batch_size:
            writers["COMMENTED_ON"].write_rows(batch_question)
            batch_question = []
        if len(batch_answer) >= batch_size:
            writers["COMMENTED_ON_ANSWER"].write_rows(batch_answer)
            batch_answer = []
    if batch_question:
        writers["COMMENTED_ON"].write_rows(batch_question)
    if batch_answer:
        writers["COMMENTED_ON_ANSWER"].write_rows(batch_answer)

    batch = []
    for attrs in iter_xml_rows(data_dir / "Badges.xml"):
        user_id = parse_int(attrs.get("UserId"))
        badge_id = parse_int(attrs.get("Id"))
        if user_id is None or badge_id is None:
            continue
        if user_id in user_ids and badge_id in badge_ids:
            batch.append(
                {
                    "FROM": user_id,
                    "TO": badge_id,
                    "Date": to_epoch_millis(parse_datetime(attrs.get("Date"))),
                    "Class": parse_int(attrs.get("Class")),
                }
            )
            if len(batch) >= batch_size:
                writers["EARNED"].write_rows(batch)
                batch = []
    if batch:
        writers["EARNED"].write_rows(batch)

    batch = []
    for attrs in iter_xml_rows(data_dir / "PostLinks.xml"):
        post_id = parse_int(attrs.get("PostId"))
        related_id = parse_int(attrs.get("RelatedPostId"))
        if post_id is None or related_id is None:
            continue
        if post_id in question_ids and related_id in question_ids:
            batch.append(
                {
                    "FROM": post_id,
                    "TO": related_id,
                    "LinkTypeId": parse_int(attrs.get("LinkTypeId")),
                    "CreationDate": to_epoch_millis(
                        parse_datetime(attrs.get("CreationDate"))
                    ),
                }
            )
            if len(batch) >= batch_size:
                writers["LINKED_TO"].write_rows(batch)
                batch = []
    if batch:
        writers["LINKED_TO"].write_rows(batch)

    for writer in writers.values():
        writer.close()

    stats["nodes"]["Tag"] = copy_csv_table(
        conn, "Tag", writers["Tag"].path, writers["Tag"].row_count
    )
    stats["nodes"]["User"] = copy_csv_table(
        conn, "User", writers["User"].path, writers["User"].row_count
    )
    stats["nodes"]["Question"] = copy_csv_table(
        conn,
        "Question",
        writers["Question"].path,
        writers["Question"].row_count,
    )
    stats["nodes"]["Answer"] = copy_csv_table(
        conn, "Answer", writers["Answer"].path, writers["Answer"].row_count
    )
    stats["nodes"]["Badge"] = copy_csv_table(
        conn, "Badge", writers["Badge"].path, writers["Badge"].row_count
    )
    stats["nodes"]["Comment"] = copy_csv_table(
        conn,
        "Comment",
        writers["Comment"].path,
        writers["Comment"].row_count,
    )
    stats["nodes"]["Post"] = stats["nodes"]["Question"] + stats["nodes"]["Answer"]

    stats["edges"]["ASKED"] = copy_csv_table(
        conn, "ASKED", writers["ASKED"].path, writers["ASKED"].row_count
    )
    stats["edges"]["ANSWERED"] = copy_csv_table(
        conn,
        "ANSWERED",
        writers["ANSWERED"].path,
        writers["ANSWERED"].row_count,
    )
    stats["edges"]["HAS_ANSWER"] = copy_csv_table(
        conn,
        "HAS_ANSWER",
        writers["HAS_ANSWER"].path,
        writers["HAS_ANSWER"].row_count,
    )
    stats["edges"]["ACCEPTED_ANSWER"] = copy_csv_table(
        conn,
        "ACCEPTED_ANSWER",
        writers["ACCEPTED_ANSWER"].path,
        writers["ACCEPTED_ANSWER"].row_count,
    )
    stats["edges"]["TAGGED_WITH"] = copy_csv_table(
        conn,
        "TAGGED_WITH",
        writers["TAGGED_WITH"].path,
        writers["TAGGED_WITH"].row_count,
    )
    stats["edges"]["COMMENTED_ON"] = copy_csv_table(
        conn,
        "COMMENTED_ON",
        writers["COMMENTED_ON"].path,
        writers["COMMENTED_ON"].row_count,
    )
    stats["edges"]["COMMENTED_ON_ANSWER"] = copy_csv_table(
        conn,
        "COMMENTED_ON_ANSWER",
        writers["COMMENTED_ON_ANSWER"].path,
        writers["COMMENTED_ON_ANSWER"].row_count,
    )
    stats["edges"]["EARNED"] = copy_csv_table(
        conn, "EARNED", writers["EARNED"].path, writers["EARNED"].row_count
    )
    stats["edges"]["LINKED_TO"] = copy_csv_table(
        conn,
        "LINKED_TO",
        writers["LINKED_TO"].path,
        writers["LINKED_TO"].row_count,
    )

    return stats, {"ids": ids, "max_ids": max_ids}


def create_edges_ladybug_asked(
    conn,
    data_dir: Path,
    user_ids: set[int],
    question_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        if user_id not in user_ids or post_id not in question_ids:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": post_id,
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "ASKED",
                "User",
                "Question",
                batch,
                ["CreationDate"],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "ASKED",
            "User",
            "Question",
            batch,
            ["CreationDate"],
        )
    return time.time() - start


def create_edges_ladybug_answered(
    conn,
    data_dir: Path,
    user_ids: set[int],
    answer_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        user_id = parse_int(attrs.get("OwnerUserId"))
        post_id = parse_int(attrs.get("Id"))
        if user_id is None or post_id is None:
            continue
        if user_id not in user_ids or post_id not in answer_ids:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": post_id,
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "ANSWERED",
                "User",
                "Answer",
                batch,
                ["CreationDate"],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "ANSWERED",
            "User",
            "Answer",
            batch,
            ["CreationDate"],
        )
    return time.time() - start


def create_edges_ladybug_has_answer(
    conn,
    data_dir: Path,
    question_ids: set[int],
    answer_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 2:
            continue
        parent_id = parse_int(attrs.get("ParentId"))
        answer_id = parse_int(attrs.get("Id"))
        if parent_id is None or answer_id is None:
            continue
        if parent_id not in question_ids or answer_id not in answer_ids:
            continue
        batch.append({"from_id": parent_id, "to_id": answer_id})
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "HAS_ANSWER",
                "Question",
                "Answer",
                batch,
                [],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "HAS_ANSWER",
            "Question",
            "Answer",
            batch,
            [],
        )
    return time.time() - start


def create_edges_ladybug_accepted_answer(
    conn,
    data_dir: Path,
    question_ids: set[int],
    answer_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        answer_id = parse_int(attrs.get("AcceptedAnswerId"))
        if question_id is None or answer_id is None:
            continue
        if question_id not in question_ids or answer_id not in answer_ids:
            continue
        batch.append({"from_id": question_id, "to_id": answer_id})
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "ACCEPTED_ANSWER",
                "Question",
                "Answer",
                batch,
                [],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "ACCEPTED_ANSWER",
            "Question",
            "Answer",
            batch,
            [],
        )
    return time.time() - start


def create_edges_ladybug_tagged_with(
    conn,
    data_dir: Path,
    tag_map: Dict[str, int],
    question_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Posts.xml"):
        if parse_int(attrs.get("PostTypeId")) != 1:
            continue
        question_id = parse_int(attrs.get("Id"))
        if question_id is None:
            continue
        if question_id not in question_ids:
            continue
        tags = parse_tags(attrs.get("Tags"))
        for tag in tags:
            tag_id = tag_map.get(tag)
            if tag_id is None:
                continue
            batch.append({"from_id": question_id, "to_id": tag_id})
            if len(batch) >= batch_size:
                ladybug_insert_edges(
                    conn,
                    "TAGGED_WITH",
                    "Question",
                    "Tag",
                    batch,
                    [],
                )
                batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "TAGGED_WITH",
            "Question",
            "Tag",
            batch,
            [],
        )
    return time.time() - start


def create_edges_ladybug_commented_on(
    conn,
    data_dir: Path,
    comment_ids: set[int],
    question_ids: set,
    answer_ids: set,
    batch_size: int,
) -> Dict[str, float]:
    # Ladybug requires edge endpoints to match table types, so split COMMENTED_ON by target type.
    start = time.time()
    batch_question: List[Dict[str, Any]] = []
    batch_answer: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Comments.xml"):
        comment_id = parse_int(attrs.get("Id"))
        post_id = parse_int(attrs.get("PostId"))
        if comment_id is None or post_id is None:
            continue
        if comment_id not in comment_ids:
            continue
        payload = {
            "from_id": comment_id,
            "to_id": post_id,
            "CreationDate": to_epoch_millis(parse_datetime(attrs.get("CreationDate"))),
            "Score": parse_int(attrs.get("Score")),
        }
        if post_id in question_ids:
            batch_question.append(payload)
        elif post_id in answer_ids:
            batch_answer.append(payload)
        else:
            continue
        if len(batch_question) >= batch_size:
            ladybug_insert_edges(
                conn,
                "COMMENTED_ON",
                "Comment",
                "Question",
                batch_question,
                ["CreationDate", "Score"],
            )
            batch_question = []
        if len(batch_answer) >= batch_size:
            ladybug_insert_edges(
                conn,
                "COMMENTED_ON_ANSWER",
                "Comment",
                "Answer",
                batch_answer,
                ["CreationDate", "Score"],
            )
            batch_answer = []
    if batch_question:
        ladybug_insert_edges(
            conn,
            "COMMENTED_ON",
            "Comment",
            "Question",
            batch_question,
            ["CreationDate", "Score"],
        )
    if batch_answer:
        ladybug_insert_edges(
            conn,
            "COMMENTED_ON_ANSWER",
            "Comment",
            "Answer",
            batch_answer,
            ["CreationDate", "Score"],
        )
    elapsed = time.time() - start
    return {
        "COMMENTED_ON": elapsed,
        "COMMENTED_ON_ANSWER": elapsed,
    }


def create_edges_ladybug_earned(
    conn,
    data_dir: Path,
    user_ids: set[int],
    badge_ids: set[int],
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "Badges.xml"):
        user_id = parse_int(attrs.get("UserId"))
        badge_id = parse_int(attrs.get("Id"))
        if user_id is None or badge_id is None:
            continue
        if user_id not in user_ids or badge_id not in badge_ids:
            continue
        batch.append(
            {
                "from_id": user_id,
                "to_id": badge_id,
                "Date": to_epoch_millis(parse_datetime(attrs.get("Date"))),
                "Class": parse_int(attrs.get("Class")),
            }
        )
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "EARNED",
                "User",
                "Badge",
                batch,
                ["Date", "Class"],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "EARNED",
            "User",
            "Badge",
            batch,
            ["Date", "Class"],
        )
    return time.time() - start


def create_edges_ladybug_linked_to(
    conn,
    data_dir: Path,
    question_ids: set,
    batch_size: int,
) -> float:
    start = time.time()
    batch: List[Dict[str, Any]] = []
    for attrs in iter_xml_rows(data_dir / "PostLinks.xml"):
        post_id = parse_int(attrs.get("PostId"))
        related_id = parse_int(attrs.get("RelatedPostId"))
        if post_id is None or related_id is None:
            continue
        if post_id not in question_ids or related_id not in question_ids:
            continue
        batch.append(
            {
                "from_id": post_id,
                "to_id": related_id,
                "LinkTypeId": parse_int(attrs.get("LinkTypeId")),
                "CreationDate": to_epoch_millis(
                    parse_datetime(attrs.get("CreationDate"))
                ),
            }
        )
        if len(batch) >= batch_size:
            ladybug_insert_edges(
                conn,
                "LINKED_TO",
                "Question",
                "Question",
                batch,
                ["LinkTypeId", "CreationDate"],
            )
            batch = []
    if batch:
        ladybug_insert_edges(
            conn,
            "LINKED_TO",
            "Question",
            "Question",
            batch,
            ["LinkTypeId", "CreationDate"],
        )
    return time.time() - start


def normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_value(v) for v in value]
    if isinstance(value, tuple):
        return [normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): normalize_value(v) for k, v in value.items()}
    return value


def extract_return_aliases(cypher: str) -> List[str]:
    match = re.search(r"\bRETURN\b(.*)", cypher, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    return_clause = match.group(1)
    return_clause = re.split(
        r"\bORDER\s+BY\b|\bLIMIT\b|\bSKIP\b",
        return_clause,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    parts = [part.strip() for part in return_clause.split(",") if part.strip()]
    aliases: List[str] = []
    for part in parts:
        alias_match = re.search(
            r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b", part, flags=re.IGNORECASE
        )
        if alias_match:
            aliases.append(alias_match.group(1))
            continue
        last_token = part.split(".")[-1].strip()
        aliases.append(last_token)
    return aliases


def extract_limit(cypher: str) -> Optional[int]:
    match = re.search(r"\bLIMIT\s+(\d+)", cypher, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def normalize_rows(
    rows: List[Any], alias_order: Optional[List[str]] = None
) -> List[Any]:
    normalized: List[Any] = []
    for row in rows:
        if alias_order and isinstance(row, dict):
            normalized.append(
                {alias: normalize_value(row.get(alias)) for alias in alias_order}
            )
            continue
        if alias_order and isinstance(row, (list, tuple)):
            payload = {}
            for idx, alias in enumerate(alias_order):
                payload[alias] = normalize_value(row[idx]) if idx < len(row) else None
            normalized.append(payload)
            continue
        if isinstance(row, (list, tuple)):
            normalized.append([normalize_value(value) for value in row])
            continue
        normalized.append(normalize_value(row))
    return normalized


def row_sort_key(row: Any) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)


def hash_rows(rows: List[Any]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_count_rows(rows: List[Any]) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for row in rows:
        if isinstance(row, dict):
            question_id = row.get("question_id")
            count_value = row.get("count")
        else:
            question_id = row[0] if len(row) > 0 else None
            count_value = row[1] if len(row) > 1 else None
        if question_id is None:
            continue
        counts[int(question_id)] = int(count_value or 0)
    return counts


def compute_manual_total_comments(query_runner) -> Dict[str, Any]:
    start = time.time()
    direct_rows = query_runner(
        """
        MATCH (q:Question)
        OPTIONAL MATCH (c:Comment)-[:COMMENTED_ON]->(q)
        RETURN q.Id AS question_id, count(c) AS count
        """.strip()
    )
    answer_rows = query_runner(
        """
        MATCH (q:Question)
        OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)<-[:COMMENTED_ON_ANSWER]-(c:Comment)
        RETURN q.Id AS question_id, count(c) AS count
        """.strip()
    )
    direct_counts = _normalize_count_rows(direct_rows)
    answer_counts = _normalize_count_rows(answer_rows)
    totals: List[Dict[str, int]] = []
    for question_id in sorted(set(direct_counts) | set(answer_counts)):
        total_comments = direct_counts.get(question_id, 0) + answer_counts.get(
            question_id, 0
        )
        totals.append({"question_id": question_id, "total_comments": total_comments})
    totals_sorted = sorted(
        totals,
        key=lambda row: (-row["total_comments"], row["question_id"]),
    )
    top_rows = totals_sorted[:10]
    elapsed = time.time() - start
    result_hash = hash_rows(top_rows)
    return {
        "name": "top_questions_by_total_comments_manual",
        "elapsed_s": elapsed,
        "row_count": len(top_rows),
        "result_hash": result_hash,
        "sample_rows": top_rows,
    }


def run_queries(
    query_runner,
    only_query: Optional[str] = None,
    query_runs: int = 1,
    query_order: str = "fixed",
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], float]:
    if query_runs < 1:
        raise ValueError("query_runs must be >= 1")

    if query_order not in {"fixed", "shuffled"}:
        raise ValueError("query_order must be 'fixed' or 'shuffled'")

    total_start = time.time()

    items = QUERY_DEFS
    if only_query:
        items = [item for item in QUERY_DEFS if item["name"] == only_query]
        if not items:
            raise ValueError(f"Unknown query name: {only_query}")

    per_query: Dict[str, Dict[str, Any]] = {
        item["name"]: {
            "name": item["name"],
            "elapsed_runs_s": [],
            "row_count": None,
            "result_hash": None,
            "sample_rows": [],
            "consistent_across_runs": True,
        }
        for item in items
    }

    for run_idx in range(query_runs):
        run_items = list(items)
        if query_order == "shuffled":
            rng = random.Random(seed + run_idx)
            rng.shuffle(run_items)

        for idx, item in enumerate(run_items, 1):
            query = item["cypher"].strip()
            alias_order = extract_return_aliases(query)
            sample_limit = extract_limit(query) or 5
            print(
                f"  Run {run_idx + 1}/{query_runs} - "
                f"Query {idx}/{len(run_items)}: {item['name']}..."
            )
            start = time.time()
            rows = query_runner(query)
            elapsed = time.time() - start
            print(f"    Done in {elapsed:.3f}s (rows={len(rows)})")

            normalized = normalize_rows(rows, alias_order=alias_order)
            normalized_sorted = sorted(normalized, key=row_sort_key)
            result_hash = hash_rows(normalized_sorted)

            entry = per_query[item["name"]]
            entry["elapsed_runs_s"].append(elapsed)

            if entry["row_count"] is None:
                entry["row_count"] = len(rows)
                entry["result_hash"] = result_hash
                entry["sample_rows"] = normalized_sorted[:sample_limit]
            else:
                if (
                    entry["row_count"] != len(rows)
                    or entry["result_hash"] != result_hash
                ):
                    entry["consistent_across_runs"] = False

    results: List[Dict[str, Any]] = []
    for item in items:
        entry = per_query[item["name"]]
        runs = entry["elapsed_runs_s"]
        runs_sorted = sorted(runs)
        median_elapsed = runs_sorted[len(runs_sorted) // 2]
        mean_elapsed = sum(runs) / len(runs)
        results.append(
            {
                "name": entry["name"],
                "elapsed_s": median_elapsed,
                "elapsed_runs_s": runs,
                "elapsed_mean_s": mean_elapsed,
                "elapsed_min_s": min(runs),
                "elapsed_max_s": max(runs),
                "row_count": entry["row_count"],
                "result_hash": entry["result_hash"],
                "sample_rows": entry["sample_rows"],
                "consistent_across_runs": entry["consistent_across_runs"],
            }
        )

    total_elapsed = time.time() - total_start
    return results, total_elapsed


def build_query_telemetry(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    cold_times = []
    warm_means = []
    hash_stable = True
    row_count_stable = True

    for item in items:
        runs = item.get("elapsed_runs_s") or []
        if runs:
            cold_times.append(float(runs[0]))
        if len(runs) > 1:
            warm_means.append(float(sum(runs[1:]) / len(runs[1:])))

        if item.get("consistent_across_runs") is False:
            hash_stable = False
            row_count_stable = False

    return {
        "query_cold_time_s": (
            (sum(cold_times) / len(cold_times)) if cold_times else None
        ),
        "query_warm_mean_s": (
            (sum(warm_means) / len(warm_means)) if warm_means else None
        ),
        "query_result_hash_stable": hash_stable,
        "query_row_count_stable": row_count_stable,
    }


def run_olap_arcadedb(
    db_path: Path,
    data_dir: Path,
    batch_size: int,
    jvm_kwargs: dict,
    dataset_name: str,
    only_query: Optional[str] = None,
    manual_checks: bool = False,
    query_runs: int = 1,
    query_order: str = "fixed",
    seed: int = 42,
) -> dict:
    arcadedb, arcade_error = get_arcadedb_module()
    if arcadedb is None or arcade_error is None:
        raise RuntimeError("arcadedb-embedded is not installed")

    if db_path.exists():
        shutil.rmtree(db_path)
    if Path("./log").exists():
        shutil.rmtree("./log")

    db = arcadedb.create_database(str(db_path), jvm_kwargs=jvm_kwargs)

    print("Creating schema...")
    schema_start = time.time()
    create_arcadedb_schema(db)
    schema_time = time.time() - schema_start

    print("Loading graph...")
    load_start = time.time()
    retry_config = get_retry_config(dataset_name)
    load_stats, _, index_time = load_graph_arcadedb(
        db,
        data_dir,
        batch_size,
        retry_config,
    )
    load_time_including_index = time.time() - load_start
    load_time = max(0.0, load_time_including_index - index_time)

    load_counts_start = time.time()
    load_counts = collect_graph_counts_arcadedb(db)
    load_counts_time = time.time() - load_counts_start

    disk_after_load = get_dir_size_bytes(db_path)
    disk_after_index = disk_after_load

    print("Running OLAP queries...")
    query_results, query_time = run_queries(
        lambda cypher: db.query("opencypher", cypher).to_list(),
        only_query=only_query,
        query_runs=query_runs,
        query_order=query_order,
        seed=seed,
    )
    manual_results = None
    if manual_checks:
        manual_results = [
            compute_manual_total_comments(
                lambda cypher: db.query("opencypher", cypher).to_list()
            )
        ]

    disk_after_queries = get_dir_size_bytes(db_path)

    counts_start = time.time()
    final_counts = collect_graph_counts_arcadedb(db)
    counts_time = time.time() - counts_start

    db.close()

    return {
        "schema_time_s": schema_time,
        "load_time_s": load_time,
        "load_time_including_index_s": load_time_including_index,
        "index_time_s": index_time,
        "query_time_s": query_time,
        "load_counts_time_s": load_counts_time,
        "load_node_count": load_counts["node_total"],
        "load_edge_count": load_counts["edge_total"],
        "load_node_counts_by_type": load_counts["node_counts_by_type"],
        "load_edge_counts_by_type": load_counts["edge_counts_by_type"],
        "counts_time_s": counts_time,
        "node_count": final_counts["node_total"],
        "edge_count": final_counts["edge_total"],
        "node_counts_by_type": final_counts["node_counts_by_type"],
        "edge_counts_by_type": final_counts["edge_counts_by_type"],
        "load_stats": load_stats,
        "queries": query_results,
        "manual_checks": manual_results,
        "disk_after_load_bytes": disk_after_load,
        "disk_after_index_bytes": disk_after_index,
        "disk_after_queries_bytes": disk_after_queries,
    }


def run_olap_ladybug(
    db_path: Path,
    data_dir: Path,
    batch_size: int,
    only_query: Optional[str] = None,
    manual_checks: bool = False,
    query_runs: int = 1,
    query_order: str = "fixed",
    seed: int = 42,
) -> dict:
    lb = get_ladybug_module()
    if lb is None:
        raise RuntimeError("real_ladybug is not installed")

    if db_path.exists():
        shutil.rmtree(db_path)
    db_path.mkdir(parents=True, exist_ok=True)
    db_file = db_path / "ladybug.lbug"

    db = lb.Database(str(db_file))
    conn = lb.Connection(db)

    print("Creating schema...")
    schema_start = time.time()
    create_ladybug_schema(conn)
    schema_time = time.time() - schema_start

    print("Loading graph...")
    load_start = time.time()
    load_stats, _ = load_graph_ladybug(
        conn,
        db_path,
        data_dir,
        batch_size,
    )
    load_time_including_index = time.time() - load_start
    load_time = load_time_including_index

    load_counts_start = time.time()
    load_counts = collect_graph_counts_ladybug(conn)
    load_counts_time = time.time() - load_counts_start

    disk_after_load = get_dir_size_bytes(db_path)

    print("Building indexes...")
    # Ladybug primary keys are created with the schema; treat this stage as a no-op.
    index_time = 0.0

    disk_after_index = get_dir_size_bytes(db_path)

    print("Running OLAP queries...")
    query_results, query_time = run_queries(
        lambda cypher: conn.execute(cypher).get_all(),
        only_query=only_query,
        query_runs=query_runs,
        query_order=query_order,
        seed=seed,
    )
    manual_results = None
    if manual_checks:
        manual_results = [
            compute_manual_total_comments(lambda cypher: conn.execute(cypher).get_all())
        ]

    disk_after_queries = get_dir_size_bytes(db_path)

    counts_start = time.time()
    final_counts = collect_graph_counts_ladybug(conn)
    counts_time = time.time() - counts_start

    return {
        "schema_time_s": schema_time,
        "load_time_s": load_time,
        "load_time_including_index_s": load_time_including_index,
        "index_time_s": index_time,
        "query_time_s": query_time,
        "load_counts_time_s": load_counts_time,
        "load_node_count": load_counts["node_total"],
        "load_edge_count": load_counts["edge_total"],
        "load_node_counts_by_type": load_counts["node_counts_by_type"],
        "load_edge_counts_by_type": load_counts["edge_counts_by_type"],
        "counts_time_s": counts_time,
        "node_count": final_counts["node_total"],
        "edge_count": final_counts["edge_total"],
        "node_counts_by_type": final_counts["node_counts_by_type"],
        "edge_counts_by_type": final_counts["edge_counts_by_type"],
        "load_stats": load_stats,
        "queries": query_results,
        "manual_checks": manual_results,
        "disk_after_load_bytes": disk_after_load,
        "disk_after_index_bytes": disk_after_index,
        "disk_after_queries_bytes": disk_after_queries,
    }


def write_results(db_path: Path, args: argparse.Namespace, summary: dict):
    if args.run_label:
        results_path = db_path / f"results_{args.run_label}.json"
    else:
        results_path = db_path / "results.json"
    query_telemetry = build_query_telemetry(summary.get("queries", []))
    payload = {
        "dataset": args.dataset,
        "db": args.db,
        "batch_size": args.batch_size,
        "mem_limit": args.mem_limit,
        "heap_size": args.heap_size_effective,
        "arcadedb_version": args.arcadedb_version,
        "ladybug_version": args.ladybug_version,
        "docker_image": args.docker_image,
        "seed": args.seed,
        "run_label": args.run_label,
        "query_runs": args.query_runs,
        "query_order": args.query_order,
        "schema_time_s": summary["schema_time_s"],
        "load_time_s": summary["load_time_s"],
        "load_time_including_index_s": summary.get("load_time_including_index_s"),
        "index_time_s": summary["index_time_s"],
        "query_time_s": summary["query_time_s"],
        "load_counts_time_s": summary.get("load_counts_time_s", 0.0),
        "load_node_count": summary.get("load_node_count"),
        "load_edge_count": summary.get("load_edge_count"),
        "load_node_counts_by_type": summary.get("load_node_counts_by_type"),
        "load_edge_counts_by_type": summary.get("load_edge_counts_by_type"),
        "counts_time_s": summary.get("counts_time_s", 0.0),
        "node_count": summary.get("node_count"),
        "edge_count": summary.get("edge_count"),
        "node_counts_by_type": summary.get("node_counts_by_type"),
        "edge_counts_by_type": summary.get("edge_counts_by_type"),
        "load_stats": summary["load_stats"],
        "queries": summary["queries"],
        "manual_checks": summary.get("manual_checks"),
        "disk_after_load_bytes": summary["disk_after_load_bytes"],
        "disk_after_load_human": format_bytes_binary(summary["disk_after_load_bytes"]),
        "disk_after_index_bytes": summary["disk_after_index_bytes"],
        "disk_after_index_human": format_bytes_binary(
            summary["disk_after_index_bytes"]
        ),
        "disk_after_queries_bytes": summary["disk_after_queries_bytes"],
        "disk_after_queries_human": format_bytes_binary(
            summary["disk_after_queries_bytes"]
        ),
        "rss_peak_kb": summary["rss_peak_kb"],
        "rss_peak_human": format_bytes_binary(summary["rss_peak_kb"] * 1024),
        "total_time_s": summary["total_time_s"],
        "run_status": summary.get("run_status", "success"),
        "error_type": summary.get("error_type"),
        "error_message": summary.get("error_message"),
        "db_create_time_s": summary.get("db_create_time_s"),
        "db_open_time_s": summary.get("db_open_time_s"),
        "db_close_time_s": summary.get("db_close_time_s"),
        "query_cold_time_s": query_telemetry.get("query_cold_time_s"),
        "query_warm_mean_s": query_telemetry.get("query_warm_mean_s"),
        "query_result_hash_stable": query_telemetry.get("query_result_hash_stable"),
        "query_row_count_stable": query_telemetry.get("query_row_count_stable"),
        "benchmark_scope_note": summary.get("benchmark_scope_note"),
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Results saved to: {results_path}")


def is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    try:
        content = Path("/proc/1/cgroup").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return "docker" in content or "containerd" in content


SIZE_TOKEN_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*([kmgt]?)(?:i?b)?\s*$",
    re.IGNORECASE,
)


def parse_size_to_mib(value: str) -> int:
    match = SIZE_TOKEN_RE.match(value)
    if not match:
        raise ValueError(f"Invalid size: {value}")

    amount = float(match.group(1))
    unit = (match.group(2) or "m").lower()
    scale = {"k": 1 / 1024, "m": 1, "g": 1024, "t": 1024 * 1024, "": 1}[unit]
    return max(1, int(amount * scale))


def resolve_arcadedb_heap_size(
    mem_limit: str,
    heap_fraction: float,
) -> str:
    if heap_fraction <= 0 or heap_fraction > 1:
        raise ValueError(f"Invalid heap fraction: {heap_fraction}")

    total_mib = parse_size_to_mib(mem_limit)
    heap_mib = max(256, int(total_mib * heap_fraction))
    return f"{heap_mib}m"


def run_in_docker(args) -> bool:
    if is_running_in_docker():
        return False

    docker = shutil.which("docker")
    if not docker:
        return False

    repo_root = Path(__file__).resolve().parents[3]
    user_spec = f"{os.getuid()}:{os.getgid()}"

    filtered_args = []
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--docker-image"}:
            skip_next = True
            continue
        filtered_args.append(arg)

    packages = ["lxml"]
    if args.db == "arcadedb":
        packages.append(f"arcadedb-embedded=={args.arcadedb_version}")
    if args.db in ("ladybug", "ladybugdb"):
        if args.ladybug_version:
            packages.append(f"real_ladybug=={args.ladybug_version}")
        else:
            packages.append("real_ladybug")

    packages_str = " ".join(packages)

    inner_cmd_parts = []
    python_cmd = "python"
    inner_cmd_parts.append(f"{python_cmd} -m venv /tmp/bench-venv")
    inner_cmd_parts.append(". /tmp/bench-venv/bin/activate")
    inner_cmd_parts.append(f"{python_cmd} -m pip install --no-cache-dir uv")
    inner_cmd_parts.append(f"uv pip install {packages_str}")
    inner_cmd_parts.append("echo 'Starting benchmark...'")
    inner_cmd_parts.append(
        f"{python_cmd} -u 10_stackoverflow_graph_olap.py {' '.join(filtered_args)}"
    )

    inner_cmd = " && ".join(inner_cmd_parts)

    cmd = [
        docker,
        "run",
        "--rm",
        "-u",
        user_spec,
        "--memory",
        args.mem_limit,
        "--cpus",
        str(args.threads),
        "-e",
        "UV_CACHE_DIR=/tmp/uv-cache",
        "-e",
        "XDG_CACHE_HOME=/tmp",
        "-v",
        f"{repo_root}:/workspace",
        "-w",
        "/workspace/bindings/python/examples",
        args.docker_image,
        "sh",
        "-lc",
        inner_cmd,
    ]

    print("Launching Docker container...")
    subprocess.run(cmd, check=True)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Stack Overflow Graph (OLAP)",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(EXPECTED_DATASETS),
        default="stackoverflow-tiny",
        help="Dataset size to use (default: stackoverflow-tiny)",
    )
    parser.add_argument(
        "--db",
        choices=["arcadedb", "ladybug", "ladybugdb"],
        default="arcadedb",
        help="Database to test (default: arcadedb)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="Batch size for XML inserts (default: 10000)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Docker CPU limit (default: 4)",
    )
    parser.add_argument(
        "--mem-limit",
        type=str,
        default="4g",
        help="Memory limit for Docker and JVM heap (default: 4g)",
    )
    parser.add_argument(
        "--jvm-heap-fraction",
        type=float,
        default=0.80,
        help="JVM heap fraction of --mem-limit (default: 0.80)",
    )
    parser.add_argument(
        "--arcadedb-version",
        type=str,
        default="26.2.1",
        help="arcadedb-embedded version to install in Docker (default: 26.2.1)",
    )
    parser.add_argument(
        "--ladybug-version",
        type=str,
        default="0.14.1",
        help="real_ladybug version to install in Docker (default: 0.14.1)",
    )
    parser.add_argument(
        "--docker-image",
        type=str,
        default="python:3.12-slim",
        help="Docker image to use (default: python:3.12-slim)",
    )
    parser.add_argument(
        "--only-query",
        type=str,
        default=None,
        help="Run only a single query by name (default: run all)",
    )
    parser.add_argument(
        "--manual-checks",
        action="store_true",
        help="Compute manual cross-check queries for validation",
    )
    parser.add_argument(
        "--query-runs",
        type=int,
        default=1,
        help="Number of measured executions per query (default: 1)",
    )
    parser.add_argument(
        "--query-order",
        choices=["fixed", "shuffled"],
        default="shuffled",
        help="Query execution order across repeated runs (default: fixed)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed used for deterministic shuffled query order (default: 42)",
    )
    parser.add_argument(
        "--run-label",
        type=str,
        default=None,
        help="Optional label appended to DB directory and result filename",
    )

    args = parser.parse_args()
    if args.run_label:
        args.run_label = args.run_label.strip().replace("/", "-").replace(" ", "_")
    if args.jvm_heap_fraction <= 0 or args.jvm_heap_fraction > 1:
        parser.error("--jvm-heap-fraction must be > 0 and <= 1")

    ran = run_in_docker(args)
    if ran:
        return

    heap_size = (
        resolve_arcadedb_heap_size(
            args.mem_limit,
            args.jvm_heap_fraction,
        )
        if args.db == "arcadedb"
        else args.mem_limit
    )
    args.heap_size_effective = heap_size
    jvm_kwargs = {"heap_size": heap_size}

    data_dir = Path(__file__).parent / "data" / args.dataset
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Dataset not found: {data_dir}. Run download_data.py first."
        )

    db_name = f"{args.dataset.replace('-', '_')}_graph_olap_{args.db}"
    if args.run_label:
        db_name = f"{db_name}_{args.run_label}"
    db_path = Path("./my_test_databases") / db_name

    print("=" * 80)
    print("Stack Overflow Graph - OLAP")
    print("=" * 80)
    print(f"Dataset: {args.dataset}")
    print(f"DB: {args.db}")
    print(f"Batch size: {args.batch_size}")
    print(f"Query runs: {args.query_runs}")
    print(f"Query order: {args.query_order}")
    print(f"Seed: {args.seed}")
    print(f"JVM heap size: {heap_size}")
    print(f"DB path: {db_path}")
    print(BENCHMARK_SCOPE_NOTE)
    print()

    stop_event, rss_state, rss_thread = start_rss_sampler()
    start_time = time.perf_counter()

    if args.db == "arcadedb":
        summary = run_olap_arcadedb(
            db_path=db_path,
            data_dir=data_dir,
            batch_size=args.batch_size,
            jvm_kwargs=jvm_kwargs,
            dataset_name=args.dataset,
            only_query=args.only_query,
            manual_checks=args.manual_checks,
            query_runs=args.query_runs,
            query_order=args.query_order,
            seed=args.seed,
        )
    elif args.db in ("ladybug", "ladybugdb"):
        summary = run_olap_ladybug(
            db_path=db_path,
            data_dir=data_dir,
            batch_size=args.batch_size,
            only_query=args.only_query,
            manual_checks=args.manual_checks,
            query_runs=args.query_runs,
            query_order=args.query_order,
            seed=args.seed,
        )
    else:
        raise NotImplementedError("Only arcadedb and ladybugdb are supported")

    total_time = time.perf_counter() - start_time
    stop_event.set()
    rss_thread.join()

    summary["rss_peak_kb"] = rss_state["max_kb"]
    summary["total_time_s"] = total_time

    print("\nResults")
    print("-" * 80)
    print(f"Schema time: {summary['schema_time_s']:.2f}s")
    print(f"Load time: {summary['load_time_s']:.2f}s")
    print(f"Index time: {summary['index_time_s']:.2f}s")
    print(f"Query time: {summary['query_time_s']:.2f}s")
    print(f"Total time: {summary['total_time_s']:.2f}s")
    print(f"Disk after load: {format_bytes_binary(summary['disk_after_load_bytes'])}")
    print(f"Disk after index: {format_bytes_binary(summary['disk_after_index_bytes'])}")
    print(
        f"Disk after queries: {format_bytes_binary(summary['disk_after_queries_bytes'])}"
    )
    print(f"Peak RSS: {summary['rss_peak_kb'] / 1024:.1f} MB")
    print(BENCHMARK_SCOPE_NOTE)
    print()

    for item in summary["queries"]:
        print(
            f"{item['name']}: {item['elapsed_s']:.3f}s, "
            f"rows={item['row_count']}, hash={item['result_hash'][:12]}"
        )

    print()
    summary["benchmark_scope_note"] = BENCHMARK_SCOPE_NOTE
    write_results(db_path, args, summary)


if __name__ == "__main__":
    main()
