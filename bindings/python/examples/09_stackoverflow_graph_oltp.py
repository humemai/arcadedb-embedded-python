#!/usr/bin/env python3
"""
Example 09: Stack Overflow Graph (OLTP)

Builds a Stack Overflow property graph (Phase 2 schema) and runs an OLTP
workload on ArcadeDB and LadybugDB with the same operation mix as Example 08.

Threading note: Databases can exhibit different scaling behavior as thread
count increases. For cross-database comparability, run with --threads 1.
"""

import argparse
import concurrent.futures
import contextlib
import csv
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
    "Scope: CRUD and query-path fairness during OLTP execution. "
    "Ingestion paths differ by engine (ArcadeDB uses Cypher inserts, Ladybug uses staged CSV + COPY), "
    "so load/index timings are not a same-path ingest comparison."
)

DEFAULT_OLTP_MIX = {
    "read": 0.60,
    "update": 0.20,
    "insert": 0.10,
    "delete": 0.10,
}

READ_TARGET_KINDS = [
    "user",
    "question",
    "answer",
    "badge",
    "tag",
    "comment",
    "edge_sample",
]

UPDATE_TARGET_KINDS = [
    "question",
    "answer",
    "comment",
    "user",
    "tag",
    "asked_edge",
    "answered_edge",
    "commented_on_edge",
    "commented_on_answer_edge",
    "earned_edge",
    "linked_to_edge",
]

INSERT_TARGET_KINDS = [
    "user_question",
    "answer",
    "comment",
    "badge",
    "tag_link",
    "post_link",
    "accepted_answer",
]

DELETE_TARGET_KINDS = [
    "question",
    "answer",
    "comment",
    "badge",
    "user",
    "tag",
    "asked_edge",
    "answered_edge",
    "has_answer_edge",
    "accepted_answer_edge",
    "tagged_with_edge",
    "commented_on_edge",
    "commented_on_answer_edge",
    "earned_edge",
    "linked_to_edge",
]

ARCADE_VERTEX_TYPES = ["User", "Question", "Answer", "Tag", "Badge", "Comment"]
ARCADE_EDGE_TYPES = [
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
LADYBUG_VERTEX_TYPES = ARCADE_VERTEX_TYPES
LADYBUG_EDGE_TYPES = [
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


def choose_ops(count: int, mix: Dict[str, float], seed: int) -> List[str]:
    rng = random.Random(seed)
    return rng.choices(
        population=["read", "update", "insert", "delete"],
        weights=[mix["read"], mix["update"], mix["insert"], mix["delete"]],
        k=count,
    )


def run_with_retry(
    action,
    error_class,
    max_retries: int = 100,
    base_delay: float = 0.01,
    max_delay: float = 0.5,
):
    delay = base_delay
    for attempt in range(max_retries):
        try:
            return action()
        except error_class:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            delay = min(max_delay, delay * 2)


def is_transient_record_not_found_error(exc: Exception) -> bool:
    message = str(exc)
    lower = message.lower()
    if "recordnotfoundexception" in lower:
        return True
    return "record #" in lower and "not found" in lower


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

    db.schema.create_index("User", ["Id"], unique=True)
    db.schema.create_index("Question", ["Id"], unique=True)
    db.schema.create_index("Answer", ["Id"], unique=True)
    db.schema.create_index("Tag", ["Id"], unique=True)
    db.schema.create_index("Badge", ["Id"], unique=True)
    db.schema.create_index("Comment", ["Id"], unique=True)

    db.async_executor().wait_completion()


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


def format_counts_by_type(label: str, counts: Dict[str, int]) -> str:
    parts = [f"{name}={value:,}" for name, value in counts.items()]
    return f"{label}: " + ", ".join(parts)


def count_arcadedb_by_type(
    db, vertex_types: List[str], edge_types: List[str]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for label in vertex_types:
        rows = db.query(
            "opencypher",
            f"MATCH (n:{label}) RETURN count(n) AS count",
        ).to_list()
        node_counts[label] = int(rows[0].get("count", 0)) if rows else 0
    for label in edge_types:
        rows = db.query(
            "opencypher",
            f"MATCH ()-[r:{label}]->() RETURN count(r) AS count",
        ).to_list()
        edge_counts[label] = int(rows[0].get("count", 0)) if rows else 0
    return node_counts, edge_counts


def count_ladybug_by_type(
    conn, vertex_types: List[str], edge_types: List[str]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for label in vertex_types:
        rows = conn.execute(f"MATCH (n:{label}) RETURN count(n) AS count").get_all()
        node_counts[label] = int(rows[0][0]) if rows else 0
    for label in edge_types:
        rows = conn.execute(
            f"MATCH ()-[r:{label}]->() RETURN count(r) AS count"
        ).get_all()
        edge_counts[label] = int(rows[0][0]) if rows else 0
    return node_counts, edge_counts


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


def load_graph_arcadedb(db, data_dir: Path, batch_size: int) -> Tuple[dict, dict]:
    stats = {"nodes": {}, "edges": {}}
    ids = {
        "users": [],
        "questions": [],
        "answers": [],
        "tags": [],
        "badges": [],
        "comments": [],
    }
    max_ids = {
        "user": 0,
        "question": 0,
        "answer": 0,
        "tag": 0,
        "badge": 0,
        "comment": 0,
    }
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
        ids["tags"].append(tag_id)
        max_ids["tag"] = max(max_ids["tag"], tag_id)
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
            max_ids["answer"] = max(max_ids["answer"], post_id)
            ids["answers"].append(post_id)
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
        ids["badges"].append(badge_id)
        max_ids["badge"] = max(max_ids["badge"], badge_id)
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
        ids["comments"].append(comment_id)
        max_ids["comment"] = max(max_ids["comment"], comment_id)
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

    return stats, {"ids": ids, "max_ids": max_ids}


def create_edges_arcadedb_asked(db, data_dir: Path, batch_size: int) -> float:
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


def create_edges_arcadedb_answered(db, data_dir: Path, batch_size: int) -> float:
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


def create_edges_arcadedb_has_answer(db, data_dir: Path, batch_size: int) -> float:
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


def create_edges_arcadedb_accepted_answer(db, data_dir: Path, batch_size: int) -> float:
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
    db, data_dir: Path, tag_map: Dict[str, int], batch_size: int
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


def create_edges_arcadedb_earned(db, data_dir: Path, batch_size: int) -> float:
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


def copy_csv_table(conn, table_name: str, csv_path: Path, row_count: int) -> float:
    print(f"  COPY {table_name}: {row_count:,} rows")
    start = time.time()
    conn.execute(f"COPY {table_name} FROM '{csv_path.as_posix()}'")
    elapsed = time.time() - start
    print(f"  COPY {table_name} done in {elapsed:.2f}s")
    return elapsed


def load_graph_ladybug(
    conn,
    db_path: Path,
    data_dir: Path,
    batch_size: int,
) -> Tuple[dict, dict]:
    # Default to native bulk ingest path for Ladybug: staged CSV + COPY.
    stats = {"nodes": {}, "edges": {}}
    ids = {
        "users": [],
        "questions": [],
        "answers": [],
        "tags": [],
        "badges": [],
        "comments": [],
    }
    max_ids = {
        "user": 0,
        "question": 0,
        "answer": 0,
        "tag": 0,
        "badge": 0,
        "comment": 0,
    }
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
        ids["tags"].append(tag_id)
        max_ids["tag"] = max(max_ids["tag"], tag_id)
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
            max_ids["answer"] = max(max_ids["answer"], post_id)
            ids["answers"].append(post_id)
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
        ids["badges"].append(badge_id)
        max_ids["badge"] = max(max_ids["badge"], badge_id)
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
        ids["comments"].append(comment_id)
        max_ids["comment"] = max(max_ids["comment"], comment_id)
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


def run_graph_oltp_arcadedb(
    db_path: Path,
    data_dir: Path,
    batch_size: int,
    transactions: int,
    threads: int,
    seed: int,
    jvm_kwargs: dict,
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
    load_stats, load_info = load_graph_arcadedb(db, data_dir, batch_size)
    load_time = time.time() - load_start

    disk_after_load = get_dir_size_bytes(db_path)

    load_counts_start = time.time()
    load_node_rows = db.query(
        "opencypher", "MATCH (n) RETURN count(n) AS count"
    ).to_list()
    load_edge_rows = db.query(
        "opencypher", "MATCH ()-[r]->() RETURN count(r) AS count"
    ).to_list()
    load_counts_time = time.time() - load_counts_start
    load_node_count = int(load_node_rows[0].get("count", 0)) if load_node_rows else 0
    load_edge_count = int(load_edge_rows[0].get("count", 0)) if load_edge_rows else 0
    load_node_counts_by_type, load_edge_counts_by_type = count_arcadedb_by_type(
        db,
        ARCADE_VERTEX_TYPES,
        ARCADE_EDGE_TYPES,
    )
    print(
        "Load counts: "
        f"nodes={load_node_count:,}, "
        f"edges={load_edge_count:,} "
        f"(time={load_counts_time:.2f}s)"
    )
    print(format_counts_by_type("Load nodes by type", load_node_counts_by_type))
    print(format_counts_by_type("Load edges by type", load_edge_counts_by_type))

    id_lock = threading.Lock()
    # No global write serialization lock: allow concurrent C/U/D operations.
    write_lock = contextlib.nullcontext()
    user_ids = load_info["ids"]["users"]
    question_ids = load_info["ids"]["questions"]
    answer_ids = load_info["ids"]["answers"]
    tag_ids = load_info["ids"]["tags"]
    badge_ids = load_info["ids"]["badges"]
    comment_ids = load_info["ids"]["comments"]
    next_user_id = load_info["max_ids"]["user"] + 1
    next_question_id = load_info["max_ids"]["question"] + 1
    next_answer_id = load_info["max_ids"]["answer"] + 1
    next_badge_id = load_info["max_ids"]["badge"] + 1
    next_comment_id = load_info["max_ids"]["comment"] + 1

    def worker(ops: List[str], worker_id: int) -> Dict[str, List[float]]:
        rng = random.Random(seed + worker_id)
        latencies = {"read": [], "update": [], "insert": [], "delete": []}
        nonlocal next_user_id
        nonlocal next_question_id
        nonlocal next_answer_id
        nonlocal next_badge_id
        nonlocal next_comment_id

        for op in ops:
            start_time = time.perf_counter()
            if op == "read":
                read_kind = rng.choice(READ_TARGET_KINDS)
                try:
                    if read_kind == "user":
                        with id_lock:
                            target_id = rng.choice(user_ids) if user_ids else None
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (u:User {Id: %d})-[:ASKED|ANSWERED]->(p)
                                RETURN p.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                    elif read_kind == "question":
                        with id_lock:
                            target_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (q:Question {Id: %d})-[:TAGGED_WITH]->(t:Tag)
                                RETURN t.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                    elif read_kind == "answer":
                        with id_lock:
                            target_id = rng.choice(answer_ids) if answer_ids else None
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (a:Answer {Id: %d})<-[:COMMENTED_ON_ANSWER]-(c:Comment)
                                RETURN c.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                    elif read_kind == "tag":
                        with id_lock:
                            target_id = rng.choice(tag_ids) if tag_ids else None
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (q:Question)-[:TAGGED_WITH]->(t:Tag {Id: %d})
                                RETURN q.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                    elif read_kind == "comment":
                        with id_lock:
                            target_id = rng.choice(comment_ids) if comment_ids else None
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON|COMMENTED_ON_ANSWER]->(p)
                                RETURN p.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                    elif read_kind == "edge_sample":
                        db.query(
                            "opencypher",
                            """
                            MATCH ()-[r:ASKED|ANSWERED|HAS_ANSWER|ACCEPTED_ANSWER|TAGGED_WITH|COMMENTED_ON|COMMENTED_ON_ANSWER|EARNED|LINKED_TO]->()
                            RETURN r
                            LIMIT 1
                            """,
                        ).to_list()
                    else:
                        with id_lock:
                            target_id = rng.choice(badge_ids) if badge_ids else None
                        if target_id is not None:
                            db.query(
                                "opencypher",
                                """
                                MATCH (u:User)-[:EARNED]->(b:Badge {Id: %d})
                                RETURN u.Id
                                LIMIT 1
                                """
                                % target_id,
                            ).to_list()
                except arcade_error as exc:
                    if not is_transient_record_not_found_error(exc):
                        raise
            elif op == "update":
                with write_lock:
                    update_kind = rng.choice(UPDATE_TARGET_KINDS)
                    with id_lock:
                        if update_kind == "question":
                            target_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif update_kind == "answer":
                            target_id = rng.choice(answer_ids) if answer_ids else None
                        elif update_kind == "comment":
                            target_id = rng.choice(comment_ids) if comment_ids else None
                        elif update_kind == "tag":
                            target_id = rng.choice(tag_ids) if tag_ids else None
                        else:
                            target_id = rng.choice(user_ids) if user_ids else None

                    if target_id is not None:

                        def do_update():
                            with db.transaction():
                                if update_kind == "question":
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (q:Question {Id: %d})
                                        SET q.Score = coalesce(q.Score, 0) + 1
                                        """
                                        % target_id,
                                    )
                                elif update_kind == "answer":
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (a:Answer {Id: %d})
                                        SET a.Score = coalesce(a.Score, 0) + 1
                                        """
                                        % target_id,
                                    )
                                elif update_kind == "comment":
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (c:Comment {Id: %d})
                                        SET c.Score = coalesce(c.Score, 0) + 1
                                        """
                                        % target_id,
                                    )
                                elif update_kind == "tag":
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (t:Tag {Id: %d})
                                        SET t.Count = coalesce(t.Count, 0) + 1
                                        """
                                        % target_id,
                                    )
                                else:
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (u:User {Id: %d})
                                        SET u.Reputation = coalesce(u.Reputation, 0) + 1
                                        """
                                        % target_id,
                                    )

                        try:
                            run_with_retry(do_update, arcade_error)
                        except arcade_error as exc:
                            if not is_transient_record_not_found_error(exc):
                                raise
                    elif update_kind == "asked_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if user_id is not None and question_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (u:User {Id: %d})-[r:ASKED]->(q:Question {Id: %d})
                                        SET r.CreationDate = coalesce(r.CreationDate, 0) + 1
                                        """
                                        % (user_id, question_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif update_kind == "answered_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if user_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (u:User {Id: %d})-[r:ANSWERED]->(a:Answer {Id: %d})
                                        SET r.CreationDate = coalesce(r.CreationDate, 0) + 1
                                        """
                                        % (user_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif update_kind == "commented_on_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if comment_id is not None and question_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON]->(q:Question {Id: %d})
                                        SET r.Score = coalesce(r.Score, 0) + 1
                                        """
                                        % (comment_id, question_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif update_kind == "commented_on_answer_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if comment_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: %d})
                                        SET r.Score = coalesce(r.Score, 0) + 1
                                        """
                                        % (comment_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif update_kind == "earned_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            badge_id = rng.choice(badge_ids) if badge_ids else None
                        if user_id is not None and badge_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (u:User {Id: %d})-[r:EARNED]->(b:Badge {Id: %d})
                                        SET r.Class = coalesce(r.Class, 0) + 1
                                        """
                                        % (user_id, badge_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif update_kind == "linked_to_edge":
                        with id_lock:
                            post_id = rng.choice(question_ids) if question_ids else None
                            related_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if post_id is not None and related_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        """
                                        MATCH (q1:Question {Id: %d})-[r:LINKED_TO]->(q2:Question {Id: %d})
                                        SET r.LinkTypeId = coalesce(r.LinkTypeId, 0) + 1
                                        """
                                        % (post_id, related_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
            elif op == "insert":
                with write_lock:
                    insert_kind = rng.choice(INSERT_TARGET_KINDS)
                    now_ms = int(time.time() * 1000)
                    new_user_id: Optional[int] = None
                    new_question_id: Optional[int] = None
                    new_answer_id: Optional[int] = None
                    new_comment_id: Optional[int] = None
                    new_badge_id: Optional[int] = None
                    user_id: Optional[int] = None
                    question_id: Optional[int] = None
                    tag_id: Optional[int] = None
                    second_question_id: Optional[int] = None
                    answer_id: Optional[int] = None
                    target_kind: Optional[str] = None
                    target_id: Optional[int] = None

                    with id_lock:
                        if insert_kind == "user_question":
                            new_user_id = next_user_id
                            next_user_id += 1
                            new_question_id = next_question_id
                            next_question_id += 1
                        elif insert_kind == "answer":
                            new_answer_id = next_answer_id
                            next_answer_id += 1
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif insert_kind == "comment":
                            new_comment_id = next_comment_id
                            next_comment_id += 1
                            if question_ids and (not answer_ids or rng.random() < 0.6):
                                target_kind = "question"
                                target_id = rng.choice(question_ids)
                            elif answer_ids:
                                target_kind = "answer"
                                target_id = rng.choice(answer_ids)
                            else:
                                target_kind = None
                                target_id = None
                        elif insert_kind == "tag_link":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            tag_id = rng.choice(tag_ids) if tag_ids else None
                        elif insert_kind == "post_link":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            second_question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif insert_kind == "accepted_answer":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        else:
                            new_badge_id = next_badge_id
                            next_badge_id += 1
                            user_id = rng.choice(user_ids) if user_ids else None

                    def do_insert():
                        with db.transaction():
                            if (
                                insert_kind == "user_question"
                                and new_user_id is not None
                                and new_question_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    CREATE (u:User {
                                        Id: %d,
                                        DisplayName: 'Synthetic',
                                        Reputation: 0,
                                        CreationDate: %d
                                    })
                                    CREATE (q:Question {
                                        Id: %d,
                                        Title: 'Synthetic',
                                        Body: 'Synthetic body',
                                        Score: 0,
                                        CreationDate: %d
                                    })
                                    CREATE (u)-[:ASKED {CreationDate: %d}]->(q)
                                    """
                                    % (
                                        new_user_id,
                                        now_ms,
                                        new_question_id,
                                        now_ms,
                                        now_ms,
                                    ),
                                )
                            elif (
                                insert_kind == "answer"
                                and new_answer_id is not None
                                and user_id is not None
                                and question_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    MATCH (u:User {Id: %d}), (q:Question {Id: %d})
                                    CREATE (a:Answer {
                                        Id: %d,
                                        Body: 'Synthetic answer',
                                        Score: 0,
                                        CreationDate: %d,
                                        CommentCount: 0
                                    })
                                    CREATE (u)-[:ANSWERED {CreationDate: %d}]->(a)
                                    CREATE (q)-[:HAS_ANSWER]->(a)
                                    """
                                    % (
                                        user_id,
                                        question_id,
                                        new_answer_id,
                                        now_ms,
                                        now_ms,
                                    ),
                                )
                            elif (
                                insert_kind == "comment"
                                and new_comment_id is not None
                                and target_kind is not None
                                and target_id is not None
                            ):
                                if target_kind == "question":
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (q:Question {Id: %d})
                                        CREATE (c:Comment {
                                            Id: %d,
                                            Text: 'Synthetic comment',
                                            Score: 0,
                                            CreationDate: %d
                                        })
                                        CREATE (c)-[:COMMENTED_ON {CreationDate: %d, Score: 0}]->(q)
                                        """
                                        % (target_id, new_comment_id, now_ms, now_ms),
                                    )
                                else:
                                    db.command(
                                        "opencypher",
                                        """
                                        MATCH (a:Answer {Id: %d})
                                        CREATE (c:Comment {
                                            Id: %d,
                                            Text: 'Synthetic comment',
                                            Score: 0,
                                            CreationDate: %d
                                        })
                                        CREATE (c)-[:COMMENTED_ON_ANSWER {CreationDate: %d, Score: 0}]->(a)
                                        """
                                        % (target_id, new_comment_id, now_ms, now_ms),
                                    )
                            elif (
                                insert_kind == "tag_link"
                                and question_id is not None
                                and tag_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    MATCH (q:Question {Id: %d}), (t:Tag {Id: %d})
                                    CREATE (q)-[:TAGGED_WITH]->(t)
                                    """
                                    % (question_id, tag_id),
                                )
                            elif (
                                insert_kind == "post_link"
                                and question_id is not None
                                and second_question_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    MATCH (q1:Question {Id: %d}), (q2:Question {Id: %d})
                                    CREATE (q1)-[:LINKED_TO {LinkTypeId: 1, CreationDate: %d}]->(q2)
                                    """
                                    % (question_id, second_question_id, now_ms),
                                )
                            elif (
                                insert_kind == "accepted_answer"
                                and question_id is not None
                                and answer_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    MATCH (q:Question {Id: %d}), (a:Answer {Id: %d})
                                    CREATE (q)-[:ACCEPTED_ANSWER]->(a)
                                    """
                                    % (question_id, answer_id),
                                )
                            elif (
                                insert_kind == "badge"
                                and new_badge_id is not None
                                and user_id is not None
                            ):
                                db.command(
                                    "opencypher",
                                    """
                                    MATCH (u:User {Id: %d})
                                    CREATE (b:Badge {
                                        Id: %d,
                                        Name: 'SyntheticBadge',
                                        Date: %d,
                                        Class: 1
                                    })
                                    CREATE (u)-[:EARNED {Date: %d, Class: 1}]->(b)
                                    """
                                    % (user_id, new_badge_id, now_ms, now_ms),
                                )

                    try:
                        run_with_retry(do_insert, arcade_error)
                    except arcade_error as exc:
                        if not is_transient_record_not_found_error(exc):
                            raise
                    else:
                        with id_lock:
                            if new_user_id is not None:
                                user_ids.append(new_user_id)
                            if new_question_id is not None:
                                question_ids.append(new_question_id)
                            if new_answer_id is not None:
                                answer_ids.append(new_answer_id)
                            if new_comment_id is not None:
                                comment_ids.append(new_comment_id)
                            if new_badge_id is not None:
                                badge_ids.append(new_badge_id)
            elif op == "delete":
                with write_lock:
                    delete_kind = rng.choice(DELETE_TARGET_KINDS)
                    node_delete_kinds = {
                        "question",
                        "answer",
                        "comment",
                        "badge",
                        "user",
                        "tag",
                    }

                    if delete_kind in node_delete_kinds:
                        with id_lock:
                            if delete_kind == "question":
                                target_id = (
                                    rng.choice(question_ids) if question_ids else None
                                )
                            elif delete_kind == "answer":
                                target_id = (
                                    rng.choice(answer_ids) if answer_ids else None
                                )
                            elif delete_kind == "comment":
                                target_id = (
                                    rng.choice(comment_ids) if comment_ids else None
                                )
                            elif delete_kind == "user":
                                target_id = rng.choice(user_ids) if user_ids else None
                            elif delete_kind == "tag":
                                target_id = rng.choice(tag_ids) if tag_ids else None
                            else:
                                target_id = rng.choice(badge_ids) if badge_ids else None

                        if target_id is not None:

                            def do_delete():
                                with db.transaction():
                                    db.command(
                                        "opencypher",
                                        "MATCH (n:%s {Id: %d}) DETACH DELETE n"
                                        % (
                                            (
                                                "Question"
                                                if delete_kind == "question"
                                                else (
                                                    "Answer"
                                                    if delete_kind == "answer"
                                                    else (
                                                        "Comment"
                                                        if delete_kind == "comment"
                                                        else (
                                                            "User"
                                                            if delete_kind == "user"
                                                            else (
                                                                "Tag"
                                                                if delete_kind == "tag"
                                                                else "Badge"
                                                            )
                                                        )
                                                    )
                                                )
                                            ),
                                            target_id,
                                        ),
                                    )

                            try:
                                run_with_retry(do_delete, arcade_error)
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                            else:
                                with id_lock:
                                    target_list = (
                                        question_ids
                                        if delete_kind == "question"
                                        else (
                                            answer_ids
                                            if delete_kind == "answer"
                                            else (
                                                comment_ids
                                                if delete_kind == "comment"
                                                else (
                                                    user_ids
                                                    if delete_kind == "user"
                                                    else (
                                                        tag_ids
                                                        if delete_kind == "tag"
                                                        else badge_ids
                                                    )
                                                )
                                            )
                                        )
                                    )
                                    try:
                                        target_list.remove(target_id)
                                    except ValueError:
                                        pass
                    elif delete_kind == "asked_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if user_id is not None and question_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (u:User {Id: %d})-[r:ASKED]->(q:Question {Id: %d}) DELETE r"
                                        % (user_id, question_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "answered_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if user_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (u:User {Id: %d})-[r:ANSWERED]->(a:Answer {Id: %d}) DELETE r"
                                        % (user_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "has_answer_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if question_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (q:Question {Id: %d})-[r:HAS_ANSWER]->(a:Answer {Id: %d}) DELETE r"
                                        % (question_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "accepted_answer_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if question_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (q:Question {Id: %d})-[r:ACCEPTED_ANSWER]->(a:Answer {Id: %d}) DELETE r"
                                        % (question_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "tagged_with_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            tag_id = rng.choice(tag_ids) if tag_ids else None
                        if question_id is not None and tag_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (q:Question {Id: %d})-[r:TAGGED_WITH]->(t:Tag {Id: %d}) DELETE r"
                                        % (question_id, tag_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "commented_on_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if comment_id is not None and question_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON]->(q:Question {Id: %d}) DELETE r"
                                        % (comment_id, question_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "commented_on_answer_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if comment_id is not None and answer_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: %d}) DELETE r"
                                        % (comment_id, answer_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "earned_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            badge_id = rng.choice(badge_ids) if badge_ids else None
                        if user_id is not None and badge_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (u:User {Id: %d})-[r:EARNED]->(b:Badge {Id: %d}) DELETE r"
                                        % (user_id, badge_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise
                    elif delete_kind == "linked_to_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            related_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if question_id is not None and related_id is not None:
                            try:
                                run_with_retry(
                                    lambda: db.command(
                                        "opencypher",
                                        "MATCH (q1:Question {Id: %d})-[r:LINKED_TO]->(q2:Question {Id: %d}) DELETE r"
                                        % (question_id, related_id),
                                    ),
                                    arcade_error,
                                )
                            except arcade_error as exc:
                                if not is_transient_record_not_found_error(exc):
                                    raise

            elapsed = time.perf_counter() - start_time
            latencies[op].append(elapsed)

        return latencies

    ops = choose_ops(transactions, DEFAULT_OLTP_MIX, seed)
    chunks = [ops[i::threads] for i in range(threads)]

    print(f"Running OLTP workload ({transactions:,} ops, {threads} threads)...")

    stop_event, rss_state, rss_thread = start_rss_sampler()
    start_time = time.perf_counter()

    results: Dict[str, List[float]] = {
        "read": [],
        "update": [],
        "insert": [],
        "delete": [],
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, chunk, i) for i, chunk in enumerate(chunks)]
        for future in concurrent.futures.as_completed(futures):
            thread_latencies = future.result()
            for op_name, vals in thread_latencies.items():
                results[op_name].extend(vals)

    total_time = time.perf_counter() - start_time
    stop_event.set()
    rss_thread.join()

    disk_after_oltp = get_dir_size_bytes(db_path)

    counts_start = time.time()
    node_rows = db.query("opencypher", "MATCH (n) RETURN count(n) AS count").to_list()
    edge_rows = db.query(
        "opencypher", "MATCH ()-[r]->() RETURN count(r) AS count"
    ).to_list()
    counts_time = time.time() - counts_start
    node_count = int(node_rows[0].get("count", 0)) if node_rows else 0
    edge_count = int(edge_rows[0].get("count", 0)) if edge_rows else 0
    node_counts_by_type, edge_counts_by_type = count_arcadedb_by_type(
        db,
        ARCADE_VERTEX_TYPES,
        ARCADE_EDGE_TYPES,
    )

    db.close()

    op_counts = {op_name: len(vals) for op_name, vals in results.items()}
    total_ops = sum(op_counts.values())
    throughput = total_ops / total_time if total_time > 0 else 0

    return {
        "total_ops": total_ops,
        "total_time_s": total_time,
        "throughput_ops_s": throughput,
        "load_time_s": load_time,
        "schema_time_s": schema_time,
        "disk_after_load_bytes": disk_after_load,
        "disk_after_oltp_bytes": disk_after_oltp,
        "rss_peak_kb": rss_state["max_kb"],
        "latencies": results,
        "op_counts": op_counts,
        "load_stats": load_stats,
        "load_counts_time_s": load_counts_time,
        "load_node_count": load_node_count,
        "load_edge_count": load_edge_count,
        "load_node_counts_by_type": load_node_counts_by_type,
        "load_edge_counts_by_type": load_edge_counts_by_type,
        "counts_time_s": counts_time,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_counts_by_type": node_counts_by_type,
        "edge_counts_by_type": edge_counts_by_type,
    }


def run_graph_oltp_ladybug(
    db_path: Path,
    data_dir: Path,
    batch_size: int,
    transactions: int,
    threads: int,
    seed: int,
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
    load_stats, load_info = load_graph_ladybug(
        conn,
        db_path,
        data_dir,
        batch_size,
    )
    load_time = time.time() - load_start

    disk_after_load = get_dir_size_bytes(db_path)

    load_counts_start = time.time()
    load_node_rows = conn.execute("MATCH (n) RETURN count(n) AS count").get_all()
    load_edge_rows = conn.execute("MATCH ()-[r]->() RETURN count(r) AS count").get_all()
    load_counts_time = time.time() - load_counts_start
    load_node_count = int(load_node_rows[0][0]) if load_node_rows else 0
    load_edge_count = int(load_edge_rows[0][0]) if load_edge_rows else 0
    load_node_counts_by_type, load_edge_counts_by_type = count_ladybug_by_type(
        conn,
        LADYBUG_VERTEX_TYPES,
        LADYBUG_EDGE_TYPES,
    )
    print(
        "Load counts: "
        f"nodes={load_node_count:,}, "
        f"edges={load_edge_count:,} "
        f"(time={load_counts_time:.2f}s)"
    )
    print(format_counts_by_type("Load nodes by type", load_node_counts_by_type))
    print(format_counts_by_type("Load edges by type", load_edge_counts_by_type))

    id_lock = threading.Lock()
    # No global write serialization lock: allow concurrent C/U/D operations.
    write_lock = contextlib.nullcontext()
    user_ids = load_info["ids"]["users"]
    question_ids = load_info["ids"]["questions"]
    answer_ids = load_info["ids"]["answers"]
    tag_ids = load_info["ids"]["tags"]
    badge_ids = load_info["ids"]["badges"]
    comment_ids = load_info["ids"]["comments"]
    next_user_id = load_info["max_ids"]["user"] + 1
    next_question_id = load_info["max_ids"]["question"] + 1
    next_answer_id = load_info["max_ids"]["answer"] + 1
    next_badge_id = load_info["max_ids"]["badge"] + 1
    next_comment_id = load_info["max_ids"]["comment"] + 1

    def worker(ops: List[str], worker_id: int) -> Dict[str, List[float]]:
        rng = random.Random(seed + worker_id)
        latencies = {"read": [], "update": [], "insert": [], "delete": []}
        nonlocal next_user_id
        nonlocal next_question_id
        nonlocal next_answer_id
        nonlocal next_badge_id
        nonlocal next_comment_id
        local_conn = lb.Connection(db)

        for op in ops:
            start_time = time.perf_counter()
            if op == "read":
                read_kind = rng.choice(READ_TARGET_KINDS)
                if read_kind == "user":
                    with id_lock:
                        target_id = rng.choice(user_ids) if user_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (u:User {Id: $id})-[:ASKED|ANSWERED]->(p) RETURN p.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
                elif read_kind == "question":
                    with id_lock:
                        target_id = rng.choice(question_ids) if question_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (q:Question {Id: $id})-[:TAGGED_WITH]->(t:Tag) RETURN t.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
                elif read_kind == "answer":
                    with id_lock:
                        target_id = rng.choice(answer_ids) if answer_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (a:Answer {Id: $id})<-[:COMMENTED_ON_ANSWER]-(c:Comment) RETURN c.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
                elif read_kind == "tag":
                    with id_lock:
                        target_id = rng.choice(tag_ids) if tag_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (q:Question)-[:TAGGED_WITH]->(t:Tag {Id: $id}) RETURN q.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
                elif read_kind == "comment":
                    with id_lock:
                        target_id = rng.choice(comment_ids) if comment_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (c:Comment {Id: $id})-[r:COMMENTED_ON|COMMENTED_ON_ANSWER]->(p) RETURN p.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
                elif read_kind == "edge_sample":
                    local_conn.execute(
                        "MATCH ()-[r:ASKED|ANSWERED|HAS_ANSWER|ACCEPTED_ANSWER|TAGGED_WITH|COMMENTED_ON|COMMENTED_ON_ANSWER|EARNED|LINKED_TO]->() RETURN r LIMIT 1"
                    )
                else:
                    with id_lock:
                        target_id = rng.choice(badge_ids) if badge_ids else None
                    if target_id is not None:
                        local_conn.execute(
                            "MATCH (u:User)-[:EARNED]->(b:Badge {Id: $id}) RETURN u.Id LIMIT 1",
                            parameters={"id": target_id},
                        )
            elif op == "update":
                with write_lock:
                    update_kind = rng.choice(UPDATE_TARGET_KINDS)
                    with id_lock:
                        if update_kind == "question":
                            target_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif update_kind == "answer":
                            target_id = rng.choice(answer_ids) if answer_ids else None
                        elif update_kind == "comment":
                            target_id = rng.choice(comment_ids) if comment_ids else None
                        elif update_kind == "tag":
                            target_id = rng.choice(tag_ids) if tag_ids else None
                        else:
                            target_id = rng.choice(user_ids) if user_ids else None
                    if target_id is not None:
                        if update_kind == "question":
                            local_conn.execute(
                                "MATCH (q:Question {Id: $id}) SET q.Score = coalesce(q.Score, 0) + 1",
                                parameters={"id": target_id},
                            )
                        elif update_kind == "answer":
                            local_conn.execute(
                                "MATCH (a:Answer {Id: $id}) SET a.Score = coalesce(a.Score, 0) + 1",
                                parameters={"id": target_id},
                            )
                        elif update_kind == "comment":
                            local_conn.execute(
                                "MATCH (c:Comment {Id: $id}) SET c.Score = coalesce(c.Score, 0) + 1",
                                parameters={"id": target_id},
                            )
                        elif update_kind == "tag":
                            local_conn.execute(
                                "MATCH (t:Tag {Id: $id}) SET t.Count = coalesce(t.Count, 0) + 1",
                                parameters={"id": target_id},
                            )
                        else:
                            local_conn.execute(
                                "MATCH (u:User {Id: $id}) SET u.Reputation = coalesce(u.Reputation, 0) + 1",
                                parameters={"id": target_id},
                            )
                    elif update_kind == "asked_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if user_id is not None and question_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:ASKED]->(q:Question {Id: $qid}) SET r.CreationDate = coalesce(r.CreationDate, 0) + 1",
                                parameters={"uid": user_id, "qid": question_id},
                            )
                    elif update_kind == "answered_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if user_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:ANSWERED]->(a:Answer {Id: $aid}) SET r.CreationDate = coalesce(r.CreationDate, 0) + 1",
                                parameters={"uid": user_id, "aid": answer_id},
                            )
                    elif update_kind == "commented_on_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if comment_id is not None and question_id is not None:
                            local_conn.execute(
                                "MATCH (c:Comment {Id: $cid})-[r:COMMENTED_ON]->(q:Question {Id: $qid}) SET r.Score = coalesce(r.Score, 0) + 1",
                                parameters={"cid": comment_id, "qid": question_id},
                            )
                    elif update_kind == "commented_on_answer_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if comment_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (c:Comment {Id: $cid})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: $aid}) SET r.Score = coalesce(r.Score, 0) + 1",
                                parameters={"cid": comment_id, "aid": answer_id},
                            )
                    elif update_kind == "earned_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            badge_id = rng.choice(badge_ids) if badge_ids else None
                        if user_id is not None and badge_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:EARNED]->(b:Badge {Id: $bid}) SET r.Class = coalesce(r.Class, 0) + 1",
                                parameters={"uid": user_id, "bid": badge_id},
                            )
                    elif update_kind == "linked_to_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            related_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if question_id is not None and related_id is not None:
                            local_conn.execute(
                                "MATCH (q1:Question {Id: $qid})-[r:LINKED_TO]->(q2:Question {Id: $rid}) SET r.LinkTypeId = coalesce(r.LinkTypeId, 0) + 1",
                                parameters={"qid": question_id, "rid": related_id},
                            )
            elif op == "insert":
                with write_lock:
                    insert_kind = rng.choice(INSERT_TARGET_KINDS)
                    now_ms = int(time.time() * 1000)
                    new_user_id: Optional[int] = None
                    new_question_id: Optional[int] = None
                    new_answer_id: Optional[int] = None
                    new_comment_id: Optional[int] = None
                    new_badge_id: Optional[int] = None
                    user_id: Optional[int] = None
                    question_id: Optional[int] = None
                    tag_id: Optional[int] = None
                    second_question_id: Optional[int] = None
                    answer_id: Optional[int] = None
                    target_kind: Optional[str] = None
                    target_id: Optional[int] = None

                    with id_lock:
                        if insert_kind == "user_question":
                            new_user_id = next_user_id
                            next_user_id += 1
                            new_question_id = next_question_id
                            next_question_id += 1
                        elif insert_kind == "answer":
                            new_answer_id = next_answer_id
                            next_answer_id += 1
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif insert_kind == "comment":
                            new_comment_id = next_comment_id
                            next_comment_id += 1
                            if question_ids and (not answer_ids or rng.random() < 0.6):
                                target_kind = "question"
                                target_id = rng.choice(question_ids)
                            elif answer_ids:
                                target_kind = "answer"
                                target_id = rng.choice(answer_ids)
                        elif insert_kind == "tag_link":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            tag_id = rng.choice(tag_ids) if tag_ids else None
                        elif insert_kind == "post_link":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            second_question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        elif insert_kind == "accepted_answer":
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        else:
                            new_badge_id = next_badge_id
                            next_badge_id += 1
                            user_id = rng.choice(user_ids) if user_ids else None

                    if (
                        insert_kind == "user_question"
                        and new_user_id is not None
                        and new_question_id is not None
                    ):
                        local_conn.execute(
                            """
                            CREATE (u:User {Id: $uid, DisplayName: 'Synthetic', Reputation: 0, CreationDate: $ts})
                            CREATE (q:Question {Id: $qid, Title: 'Synthetic', Body: 'Synthetic body', Score: 0, CreationDate: $ts})
                            CREATE (u)-[:ASKED {CreationDate: $ts}]->(q)
                            """,
                            parameters={
                                "uid": new_user_id,
                                "qid": new_question_id,
                                "ts": now_ms,
                            },
                        )
                    elif (
                        insert_kind == "answer"
                        and new_answer_id is not None
                        and user_id is not None
                        and question_id is not None
                    ):
                        local_conn.execute(
                            """
                            MATCH (u:User {Id: $uid}), (q:Question {Id: $qid})
                            CREATE (a:Answer {Id: $aid, Body: 'Synthetic answer', Score: 0, CreationDate: $ts, CommentCount: 0})
                            CREATE (u)-[:ANSWERED {CreationDate: $ts}]->(a)
                            CREATE (q)-[:HAS_ANSWER]->(a)
                            """,
                            parameters={
                                "uid": user_id,
                                "qid": question_id,
                                "aid": new_answer_id,
                                "ts": now_ms,
                            },
                        )
                    elif (
                        insert_kind == "comment"
                        and new_comment_id is not None
                        and target_kind is not None
                        and target_id is not None
                    ):
                        if target_kind == "question":
                            local_conn.execute(
                                """
                                MATCH (q:Question {Id: $target_id})
                                CREATE (c:Comment {Id: $cid, Text: 'Synthetic comment', Score: 0, CreationDate: $ts})
                                CREATE (c)-[:COMMENTED_ON {CreationDate: $ts, Score: 0}]->(q)
                                """,
                                parameters={
                                    "target_id": target_id,
                                    "cid": new_comment_id,
                                    "ts": now_ms,
                                },
                            )
                        else:
                            local_conn.execute(
                                """
                                MATCH (a:Answer {Id: $target_id})
                                CREATE (c:Comment {Id: $cid, Text: 'Synthetic comment', Score: 0, CreationDate: $ts})
                                CREATE (c)-[:COMMENTED_ON_ANSWER {CreationDate: $ts, Score: 0}]->(a)
                                """,
                                parameters={
                                    "target_id": target_id,
                                    "cid": new_comment_id,
                                    "ts": now_ms,
                                },
                            )
                    elif (
                        insert_kind == "tag_link"
                        and question_id is not None
                        and tag_id is not None
                    ):
                        local_conn.execute(
                            """
                            MATCH (q:Question {Id: $qid}), (t:Tag {Id: $tid})
                            CREATE (q)-[:TAGGED_WITH]->(t)
                            """,
                            parameters={"qid": question_id, "tid": tag_id},
                        )
                    elif (
                        insert_kind == "post_link"
                        and question_id is not None
                        and second_question_id is not None
                    ):
                        local_conn.execute(
                            """
                            MATCH (q1:Question {Id: $qid}), (q2:Question {Id: $rid})
                            CREATE (q1)-[:LINKED_TO {LinkTypeId: 1, CreationDate: $ts}]->(q2)
                            """,
                            parameters={
                                "qid": question_id,
                                "rid": second_question_id,
                                "ts": now_ms,
                            },
                        )
                    elif (
                        insert_kind == "accepted_answer"
                        and question_id is not None
                        and answer_id is not None
                    ):
                        local_conn.execute(
                            """
                            MATCH (q:Question {Id: $qid}), (a:Answer {Id: $aid})
                            CREATE (q)-[:ACCEPTED_ANSWER]->(a)
                            """,
                            parameters={"qid": question_id, "aid": answer_id},
                        )
                    elif (
                        insert_kind == "badge"
                        and new_badge_id is not None
                        and user_id is not None
                    ):
                        local_conn.execute(
                            """
                            MATCH (u:User {Id: $uid})
                            CREATE (b:Badge {Id: $bid, Name: 'SyntheticBadge', Date: $ts, Class: 1})
                            CREATE (u)-[:EARNED {Date: $ts, Class: 1}]->(b)
                            """,
                            parameters={
                                "uid": user_id,
                                "bid": new_badge_id,
                                "ts": now_ms,
                            },
                        )

                    with id_lock:
                        if new_user_id is not None:
                            user_ids.append(new_user_id)
                        if new_question_id is not None:
                            question_ids.append(new_question_id)
                        if new_answer_id is not None:
                            answer_ids.append(new_answer_id)
                        if new_comment_id is not None:
                            comment_ids.append(new_comment_id)
                        if new_badge_id is not None:
                            badge_ids.append(new_badge_id)
            elif op == "delete":
                with write_lock:
                    delete_kind = rng.choice(DELETE_TARGET_KINDS)
                    node_delete_kinds = {
                        "question",
                        "answer",
                        "comment",
                        "badge",
                        "user",
                        "tag",
                    }
                    if delete_kind in node_delete_kinds:
                        with id_lock:
                            if delete_kind == "question":
                                target_id = (
                                    rng.choice(question_ids) if question_ids else None
                                )
                            elif delete_kind == "answer":
                                target_id = (
                                    rng.choice(answer_ids) if answer_ids else None
                                )
                            elif delete_kind == "comment":
                                target_id = (
                                    rng.choice(comment_ids) if comment_ids else None
                                )
                            elif delete_kind == "user":
                                target_id = rng.choice(user_ids) if user_ids else None
                            elif delete_kind == "tag":
                                target_id = rng.choice(tag_ids) if tag_ids else None
                            else:
                                target_id = rng.choice(badge_ids) if badge_ids else None
                        if target_id is not None:
                            local_conn.execute(
                                "MATCH (n:%s {Id: $id}) DETACH DELETE n"
                                % (
                                    "Question"
                                    if delete_kind == "question"
                                    else (
                                        "Answer"
                                        if delete_kind == "answer"
                                        else (
                                            "Comment"
                                            if delete_kind == "comment"
                                            else (
                                                "User"
                                                if delete_kind == "user"
                                                else (
                                                    "Tag"
                                                    if delete_kind == "tag"
                                                    else "Badge"
                                                )
                                            )
                                        )
                                    )
                                ),
                                parameters={"id": target_id},
                            )
                        with id_lock:
                            target_list = (
                                question_ids
                                if delete_kind == "question"
                                else (
                                    answer_ids
                                    if delete_kind == "answer"
                                    else (
                                        comment_ids
                                        if delete_kind == "comment"
                                        else (
                                            user_ids
                                            if delete_kind == "user"
                                            else (
                                                tag_ids
                                                if delete_kind == "tag"
                                                else badge_ids
                                            )
                                        )
                                    )
                                )
                            )
                            try:
                                target_list.remove(target_id)
                            except ValueError:
                                pass
                    elif delete_kind == "asked_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if user_id is not None and question_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:ASKED]->(q:Question {Id: $qid}) DELETE r",
                                parameters={"uid": user_id, "qid": question_id},
                            )
                    elif delete_kind == "answered_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if user_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:ANSWERED]->(a:Answer {Id: $aid}) DELETE r",
                                parameters={"uid": user_id, "aid": answer_id},
                            )
                    elif delete_kind == "has_answer_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if question_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (q:Question {Id: $qid})-[r:HAS_ANSWER]->(a:Answer {Id: $aid}) DELETE r",
                                parameters={"qid": question_id, "aid": answer_id},
                            )
                    elif delete_kind == "accepted_answer_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if question_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (q:Question {Id: $qid})-[r:ACCEPTED_ANSWER]->(a:Answer {Id: $aid}) DELETE r",
                                parameters={"qid": question_id, "aid": answer_id},
                            )
                    elif delete_kind == "tagged_with_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            tag_id = rng.choice(tag_ids) if tag_ids else None
                        if question_id is not None and tag_id is not None:
                            local_conn.execute(
                                "MATCH (q:Question {Id: $qid})-[r:TAGGED_WITH]->(t:Tag {Id: $tid}) DELETE r",
                                parameters={"qid": question_id, "tid": tag_id},
                            )
                    elif delete_kind == "commented_on_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if comment_id is not None and question_id is not None:
                            local_conn.execute(
                                "MATCH (c:Comment {Id: $cid})-[r:COMMENTED_ON]->(q:Question {Id: $qid}) DELETE r",
                                parameters={"cid": comment_id, "qid": question_id},
                            )
                    elif delete_kind == "commented_on_answer_edge":
                        with id_lock:
                            comment_id = (
                                rng.choice(comment_ids) if comment_ids else None
                            )
                            answer_id = rng.choice(answer_ids) if answer_ids else None
                        if comment_id is not None and answer_id is not None:
                            local_conn.execute(
                                "MATCH (c:Comment {Id: $cid})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: $aid}) DELETE r",
                                parameters={"cid": comment_id, "aid": answer_id},
                            )
                    elif delete_kind == "earned_edge":
                        with id_lock:
                            user_id = rng.choice(user_ids) if user_ids else None
                            badge_id = rng.choice(badge_ids) if badge_ids else None
                        if user_id is not None and badge_id is not None:
                            local_conn.execute(
                                "MATCH (u:User {Id: $uid})-[r:EARNED]->(b:Badge {Id: $bid}) DELETE r",
                                parameters={"uid": user_id, "bid": badge_id},
                            )
                    elif delete_kind == "linked_to_edge":
                        with id_lock:
                            question_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                            related_id = (
                                rng.choice(question_ids) if question_ids else None
                            )
                        if question_id is not None and related_id is not None:
                            local_conn.execute(
                                "MATCH (q1:Question {Id: $qid})-[r:LINKED_TO]->(q2:Question {Id: $rid}) DELETE r",
                                parameters={"qid": question_id, "rid": related_id},
                            )

            elapsed = time.perf_counter() - start_time
            latencies[op].append(elapsed)

        return latencies

    ops = choose_ops(transactions, DEFAULT_OLTP_MIX, seed)
    chunks = [ops[i::threads] for i in range(threads)]

    print(f"Running OLTP workload ({transactions:,} ops, {threads} threads)...")

    stop_event, rss_state, rss_thread = start_rss_sampler()
    start_time = time.perf_counter()

    results: Dict[str, List[float]] = {
        "read": [],
        "update": [],
        "insert": [],
        "delete": [],
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, chunk, i) for i, chunk in enumerate(chunks)]
        for future in concurrent.futures.as_completed(futures):
            thread_latencies = future.result()
            for op_name, vals in thread_latencies.items():
                results[op_name].extend(vals)

    total_time = time.perf_counter() - start_time
    stop_event.set()
    rss_thread.join()

    disk_after_oltp = get_dir_size_bytes(db_path)

    counts_start = time.time()
    node_rows = conn.execute("MATCH (n) RETURN count(n) AS count").get_all()
    edge_rows = conn.execute("MATCH ()-[r]->() RETURN count(r) AS count").get_all()
    counts_time = time.time() - counts_start
    node_count = int(node_rows[0][0]) if node_rows else 0
    edge_count = int(edge_rows[0][0]) if edge_rows else 0
    node_counts_by_type, edge_counts_by_type = count_ladybug_by_type(
        conn,
        LADYBUG_VERTEX_TYPES,
        LADYBUG_EDGE_TYPES,
    )

    op_counts = {op_name: len(vals) for op_name, vals in results.items()}
    total_ops = sum(op_counts.values())
    throughput = total_ops / total_time if total_time > 0 else 0

    return {
        "total_ops": total_ops,
        "total_time_s": total_time,
        "throughput_ops_s": throughput,
        "load_time_s": load_time,
        "schema_time_s": schema_time,
        "disk_after_load_bytes": disk_after_load,
        "disk_after_oltp_bytes": disk_after_oltp,
        "rss_peak_kb": rss_state["max_kb"],
        "latencies": results,
        "op_counts": op_counts,
        "load_stats": load_stats,
        "load_counts_time_s": load_counts_time,
        "load_node_count": load_node_count,
        "load_edge_count": load_edge_count,
        "load_node_counts_by_type": load_node_counts_by_type,
        "load_edge_counts_by_type": load_edge_counts_by_type,
        "counts_time_s": counts_time,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_counts_by_type": node_counts_by_type,
        "edge_counts_by_type": edge_counts_by_type,
    }


def build_latency_summary(latencies: Dict[str, List[float]]) -> dict:
    points = [50, 95, 99]
    summary = {"ops": {}, "overall": None}

    for op_name in ["read", "update", "insert", "delete"]:
        values = latencies.get(op_name, [])
        values_sorted = sorted(values)
        if values_sorted:
            op_summary = {}
            for p in points:
                idx = int(round((p / 100.0) * (len(values_sorted) - 1)))
                op_summary[str(p)] = values_sorted[idx]
            summary["ops"][op_name] = op_summary
        else:
            summary["ops"][op_name] = {str(p): 0.0 for p in points}

    all_values = [v for vals in latencies.values() for v in vals]
    if all_values:
        all_values_sorted = sorted(all_values)
        overall = {}
        for p in points:
            idx = int(round((p / 100.0) * (len(all_values_sorted) - 1)))
            overall[str(p)] = all_values_sorted[idx]
        summary["overall"] = overall

    return summary


def write_results(db_path: Path, args: argparse.Namespace, summary: dict):
    if args.run_label:
        results_path = db_path / f"results_{args.run_label}.json"
    else:
        results_path = db_path / "results.json"
    payload = {
        "dataset": args.dataset,
        "db": args.db,
        "threads": args.threads,
        "transactions": args.transactions,
        "batch_size": args.batch_size,
        "mem_limit": args.mem_limit,
        "heap_size": args.heap_size_effective,
        "arcadedb_version": args.arcadedb_version,
        "ladybug_version": args.ladybug_version,
        "docker_image": args.docker_image,
        "seed": args.seed,
        "run_label": args.run_label,
        "throughput_ops_s": summary["throughput_ops_s"],
        "total_time_s": summary["total_time_s"],
        "schema_time_s": summary["schema_time_s"],
        "load_time_s": summary["load_time_s"],
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
        "disk_after_load_bytes": summary["disk_after_load_bytes"],
        "disk_after_load_human": format_bytes_binary(summary["disk_after_load_bytes"]),
        "disk_after_oltp_bytes": summary["disk_after_oltp_bytes"],
        "disk_after_oltp_human": format_bytes_binary(summary["disk_after_oltp_bytes"]),
        "rss_peak_kb": summary["rss_peak_kb"],
        "rss_peak_human": format_bytes_binary(summary["rss_peak_kb"] * 1024),
        "latency_summary": build_latency_summary(summary["latencies"]),
        "op_counts": summary.get("op_counts"),
        "load_stats": summary.get("load_stats"),
        "run_status": summary.get("run_status", "success"),
        "error_type": summary.get("error_type"),
        "error_message": summary.get("error_message"),
        "db_create_time_s": summary.get("db_create_time_s"),
        "db_open_time_s": summary.get("db_open_time_s"),
        "db_close_time_s": summary.get("db_close_time_s"),
        "query_cold_time_s": summary.get("query_cold_time_s"),
        "query_warm_mean_s": summary.get("query_warm_mean_s"),
        "query_result_hash_stable": summary.get("query_result_hash_stable"),
        "query_row_count_stable": summary.get("query_row_count_stable"),
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
        f"{python_cmd} -u 09_stackoverflow_graph_oltp.py {' '.join(filtered_args)}"
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
        description="Stack Overflow Graph (OLTP)",
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
        "--threads",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)",
    )
    parser.add_argument(
        "--transactions",
        type=int,
        default=100_000,
        help="Number of OLTP operations (default: 100000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="Batch size for XML inserts (default: 10000)",
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
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
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

    db_name = f"{args.dataset.replace('-', '_')}_graph_oltp_{args.db}"
    if args.run_label:
        db_name = f"{db_name}_{args.run_label}"
    db_path = Path("./my_test_databases") / db_name

    print("=" * 80)
    print("Stack Overflow Graph - OLTP")
    print("=" * 80)
    print(f"Dataset: {args.dataset}")
    print(f"DB: {args.db}")
    print(f"Threads: {args.threads}")
    print(f"Operations: {args.transactions:,}")
    print(f"Batch size: {args.batch_size}")
    if args.db == "arcadedb":
        print(f"JVM heap size: {heap_size}")
    print(f"DB path: {db_path}")
    print(BENCHMARK_SCOPE_NOTE)
    print()

    if args.db == "arcadedb":
        summary = run_graph_oltp_arcadedb(
            db_path=db_path,
            data_dir=data_dir,
            batch_size=args.batch_size,
            transactions=args.transactions,
            threads=args.threads,
            seed=args.seed,
            jvm_kwargs=jvm_kwargs,
        )
    elif args.db in ("ladybug", "ladybugdb"):
        summary = run_graph_oltp_ladybug(
            db_path=db_path,
            data_dir=data_dir,
            batch_size=args.batch_size,
            transactions=args.transactions,
            threads=args.threads,
            seed=args.seed,
        )
    else:
        raise NotImplementedError("Only arcadedb and ladybugdb are supported")

    print("\nResults")
    print("-" * 80)
    print(f"Throughput: {summary['throughput_ops_s']:.1f} ops/s")
    print(f"Total time: {summary['total_time_s']:.2f}s")
    print(f"Schema time: {summary['schema_time_s']:.2f}s")
    print(f"Load time: {summary['load_time_s']:.2f}s")
    if summary.get("load_node_count") is not None:
        print(
            "Load counts: "
            f"nodes={summary['load_node_count']:,}, "
            f"edges={summary['load_edge_count']:,} "
            f"(time={summary.get('load_counts_time_s', 0.0):.2f}s)"
        )
        if summary.get("load_node_counts_by_type"):
            print(
                format_counts_by_type(
                    "Load nodes by type",
                    summary["load_node_counts_by_type"],
                )
            )
        if summary.get("load_edge_counts_by_type"):
            print(
                format_counts_by_type(
                    "Load edges by type",
                    summary["load_edge_counts_by_type"],
                )
            )
    print(f"Count time: {summary['counts_time_s']:.2f}s")
    print(
        "Counts: "
        f"nodes={summary['node_count']:,}, "
        f"edges={summary['edge_count']:,}"
    )
    if summary.get("node_counts_by_type"):
        print(
            format_counts_by_type(
                "Nodes by type",
                summary["node_counts_by_type"],
            )
        )
    if summary.get("edge_counts_by_type"):
        print(
            format_counts_by_type(
                "Edges by type",
                summary["edge_counts_by_type"],
            )
        )
    if summary.get("op_counts"):
        print(format_counts_by_type("Ops by type", summary["op_counts"]))
    print(f"Disk after load: {format_bytes_binary(summary['disk_after_load_bytes'])}")
    print(f"Disk after OLTP: {format_bytes_binary(summary['disk_after_oltp_bytes'])}")
    print(f"Peak RSS: {summary['rss_peak_kb'] / 1024:.1f} MB")
    print(BENCHMARK_SCOPE_NOTE)
    print()

    summary["benchmark_scope_note"] = BENCHMARK_SCOPE_NOTE

    write_results(db_path, args, summary)


if __name__ == "__main__":
    main()
