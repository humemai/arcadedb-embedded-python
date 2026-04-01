#!/usr/bin/env python3
"""End-to-end ArcadeDB binding overhead benchmark.

This harness measures the same lifecycle and workload steps through two paths:

1. `python_wrapper`: the public Python bindings (`Database`, `ResultSet`, etc.)
2. `java_direct`: direct JPype calls to the underlying Java database objects

The delta between those paths is a practical estimate of Python binding overhead.
It is not a pure engine-only timer because the direct path still crosses JPype,
but it excludes most wrapper/result-conversion work and therefore isolates the
cost that the Python binding layer adds on top of the backend.

Measured areas:

- JVM start
- database create / close / open / drop
- schema creation for document, graph, and vector types
- hash and vector index creation
- OLTP document writes and updates
- graph node and edge creation
- SQL OLAP queries
- OpenCypher graph queries
- vector search queries

Examples:

    python scripts/end_to_end_binding_overhead_benchmark.py
    python scripts/end_to_end_binding_overhead_benchmark.py --runs 5 --warmup-runs 1
    python scripts/end_to_end_binding_overhead_benchmark.py \
        --doc-count 500 --node-count 200 --vector-count 128 --json-out /tmp/arcade-e2e.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

arcadedb = importlib.import_module("arcadedb_embedded")
start_jvm = importlib.import_module("arcadedb_embedded.jvm").start_jvm
jpype = importlib.import_module("jpype")


def get_java_database_factory_class():
    cached = getattr(get_java_database_factory_class, "_cached", None)
    if cached is None:
        cached = jpype.JClass("com.arcadedb.database.DatabaseFactory")
        setattr(get_java_database_factory_class, "_cached", cached)
    return cached


def build_vector(index: int, dimensions: int) -> list[float]:
    rng = random.Random(index * 7919 + dimensions * 104729)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


def build_vector_literal(values: list[float]) -> str:
    return "[" + ", ".join(f"{value:.8f}" for value in values) + "]"


@dataclass(frozen=True)
class Payloads:
    document_rows: list[tuple[str, str, int, int]]
    node_rows: list[tuple[int, str, int]]
    edge_rows: list[tuple[int, int, int]]
    vector_rows: list[tuple[str, Any, str]]
    query_vector_literal: str
    lookup_doc_id: str
    update_doc_ids: list[str]
    temp_doc_ids: list[str]
    range_threshold: int
    cypher_start_node_id: int


class BenchmarkRunner:
    mode_name: str

    def create_database(self, path: Path):
        raise NotImplementedError

    def open_database(self, path: Path):
        raise NotImplementedError

    def close_database(self, db: Any) -> None:
        raise NotImplementedError

    def drop_database(self, db: Any) -> None:
        raise NotImplementedError

    def begin(self, db: Any) -> None:
        raise NotImplementedError

    def commit(self, db: Any) -> None:
        raise NotImplementedError

    def command(self, db: Any, language: str, statement: str, *args: Any) -> Any:
        raise NotImplementedError

    def query_consume_scalar(
        self,
        db: Any,
        language: str,
        statement: str,
        property_name: str,
        *args: Any,
    ) -> Any:
        raise NotImplementedError


class WrapperRunner(BenchmarkRunner):
    mode_name = "python_wrapper"

    def __init__(self, jvm_kwargs: dict[str, Any] | None = None):
        self.jvm_kwargs = dict(jvm_kwargs or {})

    def create_database(self, path: Path):
        return arcadedb.create_database(str(path), jvm_kwargs=self.jvm_kwargs)

    def open_database(self, path: Path):
        return arcadedb.open_database(str(path), jvm_kwargs=self.jvm_kwargs)

    def close_database(self, db: Any) -> None:
        db.close()

    def drop_database(self, db: Any) -> None:
        db.drop()

    def begin(self, db: Any) -> None:
        db.begin()

    def commit(self, db: Any) -> None:
        db.commit()

    def command(self, db: Any, language: str, statement: str, *args: Any) -> Any:
        return db.command(language, statement, *args)

    def query_consume_scalar(
        self,
        db: Any,
        language: str,
        statement: str,
        property_name: str,
        *args: Any,
    ) -> Any:
        result = db.query(language, statement, *args).first()
        if result is None:
            return None
        return result.get(property_name)


class JavaDirectRunner(BenchmarkRunner):
    mode_name = "java_direct"

    def create_database(self, path: Path):
        return get_java_database_factory_class()(str(path)).create()

    def open_database(self, path: Path):
        return get_java_database_factory_class()(str(path)).open()

    def close_database(self, db: Any) -> None:
        db.close()

    def drop_database(self, db: Any) -> None:
        db.drop()

    def begin(self, db: Any) -> None:
        db.begin()

    def commit(self, db: Any) -> None:
        db.commit()

    def command(self, db: Any, language: str, statement: str, *args: Any) -> Any:
        if args:
            return db.command(language, statement, *args)
        return db.command(language, statement)

    def query_consume_scalar(
        self,
        db: Any,
        language: str,
        statement: str,
        property_name: str,
        *args: Any,
    ) -> Any:
        if args:
            result = db.query(language, statement, *args)
        else:
            result = db.query(language, statement)

        if result is None or not result.hasNext():
            return None

        row = result.next()
        if row.hasProperty(property_name):
            return row.getProperty(property_name)
        return None


STEP_ORDER = [
    "db_create_s",
    "schema_types_s",
    "schema_properties_s",
    "index_hash_s",
    "insert_documents_s",
    "insert_nodes_s",
    "insert_edges_s",
    "insert_vectors_s",
    "index_vector_s",
    "db_close_s",
    "db_open_s",
    "sql_point_lookup_s",
    "sql_update_batch_s",
    "sql_insert_delete_batch_s",
    "sql_olap_count_s",
    "sql_olap_group_by_s",
    "sql_node_count_s",
    "sql_edge_count_s",
    "cypher_node_count_s",
    "cypher_edge_count_s",
    "cypher_two_hop_s",
    "vector_search_exact_s",
    "db_drop_s",
]


STEP_LABELS = {
    "db_create_s": "DB create",
    "schema_types_s": "Schema types",
    "schema_properties_s": "Schema properties",
    "index_hash_s": "Hash indexes",
    "insert_documents_s": "OLTP docs insert",
    "insert_nodes_s": "Graph nodes insert",
    "insert_edges_s": "Graph edges insert",
    "insert_vectors_s": "Vector docs insert",
    "index_vector_s": "Vector index create",
    "db_close_s": "DB close",
    "db_open_s": "DB open",
    "sql_point_lookup_s": "SQL point lookup",
    "sql_update_batch_s": "SQL update batch",
    "sql_insert_delete_batch_s": "SQL insert/delete batch",
    "sql_olap_count_s": "SQL OLAP count",
    "sql_olap_group_by_s": "SQL OLAP group-by",
    "sql_node_count_s": "SQL nodes count",
    "sql_edge_count_s": "SQL edges count",
    "cypher_node_count_s": "Cypher nodes count",
    "cypher_edge_count_s": "Cypher edges count",
    "cypher_two_hop_s": "Cypher 2-hop",
    "vector_search_exact_s": "Vector exact search",
    "db_drop_s": "DB drop",
}


TYPE_COMMANDS = [
    "CREATE DOCUMENT TYPE BenchDoc",
    "CREATE VERTEX TYPE BenchNode",
    "CREATE EDGE TYPE BenchEdge",
    "CREATE VERTEX TYPE BenchVector",
]


PROPERTY_COMMANDS = [
    "CREATE PROPERTY BenchDoc.doc_id STRING",
    "CREATE PROPERTY BenchDoc.name STRING",
    "CREATE PROPERTY BenchDoc.group_id INTEGER",
    "CREATE PROPERTY BenchDoc.score INTEGER",
    "CREATE PROPERTY BenchNode.node_id INTEGER",
    "CREATE PROPERTY BenchNode.label STRING",
    "CREATE PROPERTY BenchNode.score INTEGER",
    "CREATE PROPERTY BenchEdge.weight INTEGER",
    "CREATE PROPERTY BenchVector.vector_id STRING",
    "CREATE PROPERTY BenchVector.embedding ARRAY_OF_FLOATS",
    "CREATE PROPERTY BenchVector.category STRING",
]


HASH_INDEX_COMMANDS = [
    "CREATE INDEX ON BenchDoc (doc_id) UNIQUE_HASH",
    "CREATE INDEX ON BenchDoc (group_id) NOTUNIQUE_HASH",
    "CREATE INDEX ON BenchNode (node_id) UNIQUE_HASH",
]


def time_call(target: Callable[[], Any]) -> tuple[float, Any]:
    start = time.perf_counter()
    result = target()
    return time.perf_counter() - start, result


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    median = statistics.median(ordered)
    mean = statistics.fmean(ordered)
    return {
        "runs": len(values),
        "median_s": median,
        "mean_s": mean,
        "min_s": ordered[0],
        "max_s": ordered[-1],
        "all_s": values,
    }


def record(metrics: dict[str, float], name: str, target: Callable[[], Any]) -> Any:
    elapsed, result = time_call(target)
    metrics[name] = elapsed
    return result


def build_payloads(args: argparse.Namespace) -> tuple[Payloads, dict[str, float]]:
    prep_metrics: dict[str, float] = {}

    def make_payloads() -> Payloads:
        document_rows = [
            (
                f"doc-{index}",
                f"Document {index}",
                index % max(1, args.group_count),
                (index * 7) % 1000,
            )
            for index in range(args.doc_count)
        ]

        node_rows = [
            (index, f"Node {index}", (index * 11) % 1000)
            for index in range(args.node_count)
        ]

        edge_rows = []
        for index in range(args.node_count - 1):
            edge_rows.append((index, index + 1, (index % 100) + 1))
            if index + 2 < args.node_count:
                edge_rows.append((index, index + 2, ((index + 13) % 100) + 1))

        vector_rows = []
        for index in range(args.vector_count):
            vector = build_vector(index=index, dimensions=args.vector_dimensions)
            vector_rows.append(
                (
                    f"vec-{index}",
                    arcadedb.to_java_float_array(vector),
                    f"cat-{index % max(1, args.group_count)}",
                )
            )

        query_vector_literal = build_vector_literal(
            build_vector(index=999_999, dimensions=args.vector_dimensions)
        )

        update_doc_ids = [
            f"doc-{index}"
            for index in range(min(args.oltp_batch, max(1, args.doc_count // 2)))
        ]
        temp_doc_ids = [f"temp-{index}" for index in range(args.oltp_batch)]

        return Payloads(
            document_rows=document_rows,
            node_rows=node_rows,
            edge_rows=edge_rows,
            vector_rows=vector_rows,
            query_vector_literal=query_vector_literal,
            lookup_doc_id=document_rows[len(document_rows) // 2][0],
            update_doc_ids=update_doc_ids,
            temp_doc_ids=temp_doc_ids,
            range_threshold=max(1, args.doc_count // 3),
            cypher_start_node_id=min(
                max(0, args.node_count // 4),
                max(0, args.node_count - 3),
            ),
        )

    payloads = record(prep_metrics, "python_payload_build_s", make_payloads)
    return payloads, prep_metrics


def run_schema_setup(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
) -> None:
    record(
        metrics,
        "schema_types_s",
        lambda: [runner.command(db, "sql", command) for command in TYPE_COMMANDS],
    )
    record(
        metrics,
        "schema_properties_s",
        lambda: [runner.command(db, "sql", command) for command in PROPERTY_COMMANDS],
    )
    record(
        metrics,
        "index_hash_s",
        lambda: [runner.command(db, "sql", command) for command in HASH_INDEX_COMMANDS],
    )


def run_document_insert(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    rows: list[tuple[str, str, int, int]],
) -> None:
    def _insert() -> None:
        runner.begin(db)
        try:
            for doc_id, name, group_id, score in rows:
                runner.command(
                    db,
                    "sql",
                    (
                        "INSERT INTO BenchDoc SET doc_id = ?, name = ?, "
                        "group_id = ?, score = ?"
                    ),
                    doc_id,
                    name,
                    group_id,
                    score,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "insert_documents_s", _insert)


def run_node_insert(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    rows: list[tuple[int, str, int]],
) -> None:
    def _insert() -> None:
        runner.begin(db)
        try:
            for node_id, label, score in rows:
                runner.command(
                    db,
                    "sql",
                    "INSERT INTO BenchNode SET node_id = ?, label = ?, score = ?",
                    node_id,
                    label,
                    score,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "insert_nodes_s", _insert)


def run_edge_insert(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    rows: list[tuple[int, int, int]],
) -> None:
    def _insert() -> None:
        runner.begin(db)
        try:
            for from_id, to_id, weight in rows:
                runner.command(
                    db,
                    "sql",
                    (
                        "CREATE EDGE BenchEdge "
                        "FROM (SELECT FROM BenchNode WHERE node_id = ?) "
                        "TO (SELECT FROM BenchNode WHERE node_id = ?) "
                        "SET weight = ?"
                    ),
                    from_id,
                    to_id,
                    weight,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "insert_edges_s", _insert)


def run_vector_insert(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    rows: list[tuple[str, Any, str]],
) -> None:
    def _insert() -> None:
        runner.begin(db)
        try:
            for vector_id, embedding, category in rows:
                runner.command(
                    db,
                    "sql",
                    (
                        "INSERT INTO BenchVector SET vector_id = ?, embedding = ?, "
                        "category = ?"
                    ),
                    vector_id,
                    embedding,
                    category,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "insert_vectors_s", _insert)


def run_vector_index(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    dimensions: int,
) -> None:
    statement = f"""
    CREATE INDEX ON BenchVector (embedding)
    LSM_VECTOR
    METADATA {{
        "dimensions": {int(dimensions)},
        "similarity": "COSINE",
        "quantization": "INT8"
    }}
    """
    record(metrics, "index_vector_s", lambda: runner.command(db, "sql", statement))


def run_steady_state_queries(
    runner: BenchmarkRunner,
    db: Any,
    metrics: dict[str, float],
    payloads: Payloads,
    args: argparse.Namespace,
) -> None:
    record(
        metrics,
        "sql_point_lookup_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                "SELECT doc_id FROM BenchDoc WHERE doc_id = ?",
                "doc_id",
                payloads.lookup_doc_id,
            )
            for _ in range(args.query_runs)
        ],
    )

    def _sql_update_batch() -> None:
        runner.begin(db)
        try:
            for offset, doc_id in enumerate(payloads.update_doc_ids):
                runner.command(
                    db,
                    "sql",
                    "UPDATE BenchDoc SET score = ? WHERE doc_id = ?",
                    10_000 + offset,
                    doc_id,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "sql_update_batch_s", _sql_update_batch)

    def _sql_insert_delete_batch() -> None:
        runner.begin(db)
        try:
            for offset, doc_id in enumerate(payloads.temp_doc_ids):
                runner.command(
                    db,
                    "sql",
                    (
                        "INSERT INTO BenchDoc SET doc_id = ?, name = ?, "
                        "group_id = ?, score = ?"
                    ),
                    doc_id,
                    f"Temp {offset}",
                    offset % max(1, args.group_count),
                    offset,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

        runner.begin(db)
        try:
            for doc_id in payloads.temp_doc_ids:
                runner.command(
                    db,
                    "sql",
                    "DELETE FROM BenchDoc WHERE doc_id = ?",
                    doc_id,
                )
            runner.commit(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    record(metrics, "sql_insert_delete_batch_s", _sql_insert_delete_batch)

    record(
        metrics,
        "sql_olap_count_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                "SELECT count(*) AS count FROM BenchDoc WHERE score >= ?",
                "count",
                payloads.range_threshold,
            )
            for _ in range(args.query_runs)
        ],
    )

    record(
        metrics,
        "sql_olap_group_by_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                (
                    "SELECT group_id, count(*) AS count FROM BenchDoc "
                    "GROUP BY group_id ORDER BY count DESC LIMIT 1"
                ),
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    record(
        metrics,
        "sql_node_count_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                "SELECT count(*) AS count FROM BenchNode",
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    record(
        metrics,
        "sql_edge_count_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                "SELECT count(*) AS count FROM BenchEdge",
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    record(
        metrics,
        "cypher_node_count_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "opencypher",
                "MATCH (n:BenchNode) RETURN count(n) AS count",
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    record(
        metrics,
        "cypher_edge_count_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "opencypher",
                "MATCH ()-[r:BenchEdge]->() RETURN count(r) AS count",
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    cypher_two_hop = f"""
        MATCH (n:BenchNode {{node_id: {payloads.cypher_start_node_id}}})
            -[:BenchEdge]->(mid:BenchNode)
            -[:BenchEdge]->(dst:BenchNode)
    RETURN count(dst) AS count
    """
    record(
        metrics,
        "cypher_two_hop_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "opencypher",
                cypher_two_hop,
                "count",
            )
            for _ in range(args.query_runs)
        ],
    )

    vector_search_sql = (
        "SELECT @rid, distance FROM ("
        "SELECT expand(vectorNeighbors('BenchVector[embedding]', "
        f"{payloads.query_vector_literal}, {args.vector_k}, {args.vector_ef_search}))"
        ") LIMIT 1"
    )
    record(
        metrics,
        "vector_search_exact_s",
        lambda: [
            runner.query_consume_scalar(
                db,
                "sql",
                vector_search_sql,
                "distance",
            )
            for _ in range(args.query_runs)
        ],
    )


def run_single_mode(
    runner: BenchmarkRunner,
    root_dir: Path,
    payloads: Payloads,
    args: argparse.Namespace,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    db_path = root_dir / runner.mode_name

    if db_path.exists():
        shutil.rmtree(db_path)

    db = record(metrics, "db_create_s", lambda: runner.create_database(db_path))
    run_schema_setup(runner, db, metrics)
    run_document_insert(runner, db, metrics, payloads.document_rows)
    run_node_insert(runner, db, metrics, payloads.node_rows)
    run_edge_insert(runner, db, metrics, payloads.edge_rows)
    run_vector_insert(runner, db, metrics, payloads.vector_rows)
    run_vector_index(runner, db, metrics, args.vector_dimensions)
    record(metrics, "db_close_s", lambda: runner.close_database(db))

    reopened = record(metrics, "db_open_s", lambda: runner.open_database(db_path))
    run_steady_state_queries(runner, reopened, metrics, payloads, args)
    record(metrics, "db_drop_s", lambda: runner.drop_database(reopened))

    if db_path.exists():
        shutil.rmtree(db_path, ignore_errors=True)

    return metrics


def build_comparison(summary: dict[str, dict[str, dict[str, float]]]) -> dict[str, Any]:
    wrapper = summary["python_wrapper"]
    direct = summary["java_direct"]
    comparison: dict[str, Any] = {}

    for step in STEP_ORDER:
        wrapper_median = wrapper[step]["median_s"]
        direct_median = direct[step]["median_s"]
        overhead = wrapper_median - direct_median
        overhead_pct = (overhead / direct_median * 100.0) if direct_median > 0 else None
        comparison[step] = {
            "label": STEP_LABELS[step],
            "wrapper_median_s": wrapper_median,
            "java_direct_median_s": direct_median,
            "binding_overhead_s": overhead,
            "binding_overhead_pct": overhead_pct,
        }

    return comparison


def print_results(
    prep_metrics: dict[str, float],
    jvm_start_s: float,
    summary: dict[str, dict[str, dict[str, float]]],
    comparison: dict[str, Any],
) -> None:
    print("\nArcadeDB binding overhead benchmark")
    print("=" * 72)
    print(f"JVM start: {jvm_start_s * 1000:.2f} ms")
    for name, value in prep_metrics.items():
        print(f"{name}: {value * 1000:.2f} ms")

    print("\nPer-step median timings")
    print("-" * 72)
    print(
        f"{'Step':<24} {'Wrapper ms':>12} {'Direct ms':>12} "
        f"{'Overhead ms':>14} {'Overhead %':>12}"
    )
    for step in STEP_ORDER:
        row = comparison[step]
        overhead_pct = row["binding_overhead_pct"]
        overhead_pct_text = "n/a" if overhead_pct is None else f"{overhead_pct:,.2f}"
        print(
            f"{row['label']:<24} "
            f"{row['wrapper_median_s'] * 1000:>12.2f} "
            f"{row['java_direct_median_s'] * 1000:>12.2f} "
            f"{row['binding_overhead_s'] * 1000:>14.2f} "
            f"{overhead_pct_text:>12}"
        )

    print("\nMode summaries")
    print("-" * 72)
    for mode_name in ("python_wrapper", "java_direct"):
        total = sum(summary[mode_name][step]["median_s"] for step in STEP_ORDER)
        print(f"{mode_name}: {total * 1000:.2f} ms total median across measured steps")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end ArcadeDB binding overhead benchmark"
    )
    parser.add_argument("--runs", type=int, default=3, help="Measured runs per mode")
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=1,
        help="Warmup runs per mode excluded from the summary",
    )
    parser.add_argument("--doc-count", type=int, default=1000, help="Document rows")
    parser.add_argument("--node-count", type=int, default=300, help="Graph nodes")
    parser.add_argument("--vector-count", type=int, default=256, help="Vector rows")
    parser.add_argument(
        "--vector-dimensions", type=int, default=32, help="Vector dimensions"
    )
    parser.add_argument(
        "--group-count", type=int, default=8, help="Distinct group/category buckets"
    )
    parser.add_argument(
        "--oltp-batch",
        type=int,
        default=50,
        help="Rows affected in OLTP update/insert/delete",
    )
    parser.add_argument(
        "--query-runs",
        type=int,
        default=25,
        help="Repeated steady-state query executions",
    )
    parser.add_argument("--vector-k", type=int, default=10, help="vectorNeighbors k")
    parser.add_argument(
        "--vector-ef-search", type=int, default=32, help="vectorNeighbors ef_search"
    )
    parser.add_argument(
        "--jvm-heap",
        default="2g",
        help="Heap size passed to start_jvm() before benchmarking",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path to write the benchmark summary as JSON",
    )
    parser.add_argument(
        "--keep-temp-root",
        action="store_true",
        help="Keep the temporary benchmark root directory for inspection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be >= 1")
    if args.warmup_runs < 0:
        raise ValueError("--warmup-runs must be >= 0")

    jvm_start_begin = time.perf_counter()
    start_jvm(heap_size=args.jvm_heap)
    jvm_start_s = time.perf_counter() - jvm_start_begin

    get_java_database_factory_class()
    prep_payloads, prep_metrics = build_payloads(args)

    root_dir = Path(tempfile.mkdtemp(prefix="arcadedb-binding-e2e-"))
    raw_runs: dict[str, dict[str, list[float]]] = {
        "python_wrapper": {step: [] for step in STEP_ORDER},
        "java_direct": {step: [] for step in STEP_ORDER},
    }

    try:
        for iteration in range(args.warmup_runs + args.runs):
            is_measured = iteration >= args.warmup_runs
            phase_label = "measured" if is_measured else "warmup"
            print(
                "Running "
                f"{phase_label} iteration {iteration + 1}/"
                f"{args.warmup_runs + args.runs}..."
            )
            for runner in (
                WrapperRunner(jvm_kwargs={"heap_size": args.jvm_heap}),
                JavaDirectRunner(),
            ):
                iteration_root = (
                    root_dir / f"iteration-{iteration + 1}-{runner.mode_name}"
                )
                iteration_root.mkdir(parents=True, exist_ok=True)
                metrics = run_single_mode(runner, iteration_root, prep_payloads, args)
                if is_measured:
                    for step in STEP_ORDER:
                        raw_runs[runner.mode_name][step].append(metrics[step])
                shutil.rmtree(iteration_root, ignore_errors=True)

        summary = {
            mode_name: {step: summarize(values) for step, values in steps.items()}
            for mode_name, steps in raw_runs.items()
        }
        comparison = build_comparison(summary)
        print_results(prep_metrics, jvm_start_s, summary, comparison)

        if args.json_out:
            output = {
                "environment": {
                    "runs": args.runs,
                    "warmup_runs": args.warmup_runs,
                    "doc_count": args.doc_count,
                    "node_count": args.node_count,
                    "vector_count": args.vector_count,
                    "vector_dimensions": args.vector_dimensions,
                    "query_runs": args.query_runs,
                    "oltp_batch": args.oltp_batch,
                    "vector_k": args.vector_k,
                    "vector_ef_search": args.vector_ef_search,
                    "jvm_heap": args.jvm_heap,
                    "jvm_start_s": jvm_start_s,
                    "prep_metrics": prep_metrics,
                },
                "modes": summary,
                "comparison": comparison,
            }
            out_path = Path(args.json_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
            print(f"\nWrote JSON summary to {out_path}")

        return 0
    finally:
        if args.keep_temp_root:
            print(f"\nKept benchmark temp root: {root_dir}")
        else:
            shutil.rmtree(root_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
