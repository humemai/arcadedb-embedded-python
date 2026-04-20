#!/usr/bin/env python3
"""Profile ArcadeDB Python bindings with isolated subprocess scenarios.

This script measures:

- JVM startup cost
- end-to-end wall time for representative binding scenarios
- process RSS / peak RSS
- Python heap allocations via tracemalloc
- JVM heap visibility through java.lang.Runtime

Each scenario runs in a separate subprocess so JVM startup and heap state are
isolated per run.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import random
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

PROFILE_DIR = Path(__file__).resolve().parent
BINDINGS_ROOT = PROFILE_DIR.parent.parent
SRC_DIR = BINDINGS_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


AVAILABLE_SCENARIOS = (
    "jvm_startup",
    "db_lifecycle",
    "result_lazy_scan",
    "result_to_list",
    "result_iter_chunks",
    "document_to_dict",
    "lookup_paths",
    "transaction_insert_batch",
    "nested_conversion",
    "graph_traversal",
    "graph_batch_ingest",
    "vector_search",
    "vector_search_breakdown",
    "async_command_insert",
    "async_query_callback",
    "import_documents",
    "export_to_csv",
)

SCENARIO_PRESETS: dict[str, tuple[str, ...]] = {
    "smoke": (
        "lookup_paths",
        "transaction_insert_batch",
        "vector_search_breakdown",
        "async_command_insert",
        "async_query_callback",
        "import_documents",
        "export_to_csv",
    ),
    "core": (
        "jvm_startup",
        "db_lifecycle",
        "result_lazy_scan",
        "result_to_list",
        "result_iter_chunks",
        "document_to_dict",
        "nested_conversion",
        "vector_search",
        "vector_search_breakdown",
    ),
    "full": AVAILABLE_SCENARIOS,
}

DEFAULT_SCENARIOS = AVAILABLE_SCENARIOS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile ArcadeDB embedded Python binding overhead"
    )
    parser.add_argument(
        "--preset",
        choices=sorted(SCENARIO_PRESETS.keys()),
        default="",
        help=(
            "Named scenario preset. Overrides --scenarios when provided. "
            "Choices: smoke, core, full."
        ),
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(DEFAULT_SCENARIOS),
        help="Comma-separated scenarios to run",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of isolated subprocess runs per scenario (default: 3)",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=5000,
        help="Number of records for result/materialization scenarios (default: 5000)",
    )
    parser.add_argument(
        "--graph-vertices",
        type=int,
        default=1500,
        help="Number of vertices for graph scenarios (default: 1500)",
    )
    parser.add_argument(
        "--graph-degree",
        type=int,
        default=2,
        help="Outgoing edges per vertex in graph scenarios (default: 2)",
    )
    parser.add_argument(
        "--vector-records",
        type=int,
        default=1500,
        help="Number of vectors for vector search scenario (default: 1500)",
    )
    parser.add_argument(
        "--vector-dimensions",
        type=int,
        default=32,
        help="Vector dimensionality for vector search (default: 32)",
    )
    parser.add_argument(
        "--vector-k",
        type=int,
        default=10,
        help="Top-k result count for vector scenarios (default: 10)",
    )
    parser.add_argument(
        "--query-runs",
        type=int,
        default=100,
        help="Repeated query count inside scenarios (default: 100)",
    )
    parser.add_argument(
        "--dict-repeats",
        type=int,
        default=500,
        help="How many times to call to_dict() in document scenario (default: 500)",
    )
    parser.add_argument(
        "--nested-width",
        type=int,
        default=250,
        help="Top-level collection width for nested conversion scenario (default: 250)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size for iter_chunks scenario (default: 500)",
    )
    parser.add_argument(
        "--async-parallel-level",
        type=int,
        default=4,
        help="Parallel level for async scenarios (default: 4)",
    )
    parser.add_argument(
        "--async-commit-every",
        type=int,
        default=200,
        help="Commit cadence for async scenarios (default: 200)",
    )
    parser.add_argument(
        "--heap-size",
        default="2g",
        help="JVM heap size passed into start_jvm/create_database (default: 2g)",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help=(
            "Optional output JSON path. Defaults to a timestamped file in "
            "this directory."
        ),
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temp databases created by worker processes",
    )
    parser.add_argument(
        "--worker-scenario",
        default="",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def parse_scenarios(raw: str) -> list[str]:
    scenarios = [item.strip() for item in raw.split(",") if item.strip()]
    if not scenarios:
        raise ValueError("No scenarios selected")

    invalid = [item for item in scenarios if item not in AVAILABLE_SCENARIOS]
    if invalid:
        raise ValueError(
            f"Unknown scenarios: {', '.join(invalid)}. "
            f"Valid choices: {', '.join(AVAILABLE_SCENARIOS)}"
        )
    return scenarios


def resolve_scenarios(args: argparse.Namespace) -> list[str]:
    if args.preset:
        return list(SCENARIO_PRESETS[args.preset])
    return parse_scenarios(args.scenarios)


def rss_bytes() -> int:
    status_path = Path("/proc/self/status")
    if status_path.exists():
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1]) * 1024

    usage = resource.getrusage(resource.RUSAGE_SELF)
    value = getattr(usage, "ru_maxrss", 0)
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


def max_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    value = getattr(usage, "ru_maxrss", 0)
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


def cpu_times() -> dict[str, float]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "user_s": float(getattr(usage, "ru_utime", 0.0)),
        "system_s": float(getattr(usage, "ru_stime", 0.0)),
    }


def safe_jvm_memory() -> dict[str, int | None]:
    try:
        import jpype

        if not jpype.isJVMStarted():
            return {
                "jvm_max_bytes": None,
                "jvm_total_bytes": None,
                "jvm_free_bytes": None,
            }

        runtime = jpype.JPackage("java.lang").Runtime.getRuntime()
        return {
            "jvm_max_bytes": int(runtime.maxMemory()),
            "jvm_total_bytes": int(runtime.totalMemory()),
            "jvm_free_bytes": int(runtime.freeMemory()),
        }
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return {
            "jvm_max_bytes": None,
            "jvm_total_bytes": None,
            "jvm_free_bytes": None,
        }


def force_gc() -> None:
    gc.collect()
    try:
        import jpype

        if jpype.isJVMStarted():
            jpype.JPackage("java.lang").System.gc()
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        pass


def snapshot(label: str) -> dict[str, Any]:
    current, peak = tracemalloc.get_traced_memory()
    snap: dict[str, Any] = {
        "label": label,
        "rss_bytes": rss_bytes(),
        "max_rss_bytes": max_rss_bytes(),
        "python_current_bytes": int(current),
        "python_peak_bytes": int(peak),
    }
    snap.update(cpu_times())
    snap.update(safe_jvm_memory())
    return snap


def delta(snapshot_a: dict[str, Any], snapshot_b: dict[str, Any], key: str) -> Any:
    value_a = snapshot_a.get(key)
    value_b = snapshot_b.get(key)
    if value_a is None or value_b is None:
        return None
    return value_b - value_a


def random_vector(index: int, dimensions: int) -> list[float]:
    rng = random.Random(index * 7919 + dimensions * 104729)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


def make_temp_db_path(prefix: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    return temp_dir / "db"


def populate_items_db(db_path: Path, *, record_count: int, heap_size: str) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE DOCUMENT TYPE Item")
        with db.transaction():
            for index in range(record_count):
                db.command(
                    "sql",
                    "INSERT INTO Item SET name = ?, value = ?, category = ?",
                    f"item-{index}",
                    index,
                    f"cat-{index % 10}",
                )
    finally:
        db.close()


def populate_vector_db(
    db_path: Path,
    *,
    record_count: int,
    dimensions: int,
    heap_size: str,
) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE VERTEX TYPE VectorDoc")
        db.command("sql", "CREATE PROPERTY VectorDoc.doc_id STRING")
        db.command("sql", "CREATE PROPERTY VectorDoc.embedding ARRAY_OF_FLOATS")
        index = db.create_vector_index(
            "VectorDoc",
            "embedding",
            dimensions=dimensions,
            id_property="doc_id",
            build_graph_now=False,
        )
        with db.transaction():
            for index_num in range(record_count):
                db.command(
                    "sql",
                    "INSERT INTO VectorDoc SET doc_id = ?, embedding = ?",
                    f"doc-{index_num}",
                    arcadedb.to_java_float_array(random_vector(index_num, dimensions)),
                )
        index.build_graph_now()
    finally:
        db.close()


def populate_graph_db(
    db_path: Path,
    *,
    vertex_count: int,
    degree: int,
    heap_size: str,
) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE VERTEX TYPE Person")
        db.command("sql", "CREATE PROPERTY Person.person_id INTEGER")
        db.command("sql", "CREATE PROPERTY Person.name STRING")
        db.command("sql", "CREATE INDEX ON Person (person_id) UNIQUE_HASH")
        db.command("sql", "CREATE EDGE TYPE Knows")
        db.command("sql", "CREATE PROPERTY Knows.weight INTEGER")

        with db.transaction():
            for index in range(vertex_count):
                db.command(
                    "sql",
                    "INSERT INTO Person SET person_id = ?, name = ?",
                    index,
                    f"person-{index}",
                )

            for index in range(vertex_count):
                for offset in range(1, degree + 1):
                    target = (index + offset) % vertex_count
                    db.command(
                        "sql",
                        "CREATE EDGE Knows "
                        "FROM (SELECT FROM Person WHERE person_id = ?) "
                        "TO (SELECT FROM Person WHERE person_id = ?) "
                        "SET weight = ?",
                        index,
                        target,
                        offset,
                    )
    finally:
        db.close()


def build_nested_payload(width: int) -> dict[str, Any]:
    return {
        "users": [
            {
                "name": f"user-{index}",
                "age": index % 80,
                "scores": [index, index + 1, index + 2],
                "active": index % 2 == 0,
            }
            for index in range(width)
        ],
        "settings": {
            "theme": "dark",
            "notifications": True,
            "thresholds": {
                "warn": width // 3,
                "critical": width // 2,
            },
        },
        "groups": {
            f"group-{index % 10}": {
                "size": index,
                "enabled": index % 2 == 0,
            }
            for index in range(width)
        },
    }


def populate_lookup_db(db_path: Path, *, record_count: int, heap_size: str) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE DOCUMENT TYPE LookupItem")
        db.command("sql", "CREATE PROPERTY LookupItem.item_id LONG")
        db.command("sql", "CREATE PROPERTY LookupItem.name STRING")
        db.command("sql", "CREATE PROPERTY LookupItem.segment STRING")
        db.command("sql", "CREATE INDEX ON LookupItem (item_id) UNIQUE_HASH")

        with db.transaction():
            for index in range(record_count):
                db.command(
                    "sql",
                    "INSERT INTO LookupItem SET item_id = ?, name = ?, segment = ?",
                    index,
                    f"lookup-{index}",
                    f"bucket-{index % 16}",
                )
    finally:
        db.close()


def write_people_csv(csv_path: Path, row_count: int) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["person_id", "name", "city", "score"])
        for index in range(row_count):
            writer.writerow(
                [index, f"person-{index}", f"city-{index % 25}", index % 100]
            )


def populate_nested_db(db_path: Path, *, width: int, heap_size: str) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE DOCUMENT TYPE NestedDoc")
        with db.transaction():
            document = db.new_document("NestedDoc")
            document.set("name", "nested-root")
            document.set("nested_data", build_nested_payload(width))
            document.save()
    finally:
        db.close()


def cleanup_temp_db(db_path: Path, keep_temp: bool) -> None:
    if keep_temp:
        return
    temp_root = db_path.parent
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)


def scenario_jvm_startup(args: argparse.Namespace) -> dict[str, Any]:
    from arcadedb_embedded.jvm import start_jvm

    before = snapshot("before_start_jvm")
    start = time.perf_counter()
    start_jvm(heap_size=args.heap_size)
    duration = time.perf_counter() - start
    force_gc()
    after = snapshot("after_start_jvm")

    return {
        "scenario": "jvm_startup",
        "durations_s": {
            "start_jvm": duration,
            "wall_total": duration,
        },
        "snapshots": [before, after],
        "derived": {
            "rss_delta_bytes": delta(before, after, "rss_bytes"),
            "python_peak_delta_bytes": delta(before, after, "python_peak_bytes"),
        },
    }


def scenario_db_lifecycle(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_lifecycle_")
    before = snapshot("before_create_database")
    try:
        start = time.perf_counter()
        db = arcadedb.create_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        create_duration = time.perf_counter() - start
        after_create = snapshot("after_create_database")

        start = time.perf_counter()
        db.command("sql", "CREATE DOCUMENT TYPE LifeItem")
        with db.transaction():
            for index in range(args.records):
                db.command(
                    "sql",
                    "INSERT INTO LifeItem SET name = ?, value = ?",
                    f"life-{index}",
                    index,
                )
        populate_duration = time.perf_counter() - start
        force_gc()
        after_populate = snapshot("after_populate")

        start = time.perf_counter()
        db.close()
        close_duration = time.perf_counter() - start
        force_gc()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "db_lifecycle",
        "durations_s": {
            "create_database": create_duration,
            "populate": populate_duration,
            "close": close_duration,
            "wall_total": create_duration + populate_duration + close_duration,
        },
        "snapshots": [before, after_create, after_populate, after_close],
        "derived": {
            "rss_after_create_delta_bytes": delta(before, after_create, "rss_bytes"),
            "rss_after_populate_delta_bytes": delta(
                before,
                after_populate,
                "rss_bytes",
            ),
            "rss_after_close_delta_bytes": delta(before, after_close, "rss_bytes"),
        },
        "counts": {
            "records": args.records,
        },
    }


def scenario_result_lazy_scan(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_lazy_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        start = time.perf_counter()
        result = db.query("sql", "SELECT FROM Item ORDER BY value")
        query_duration = time.perf_counter() - start
        after_query = snapshot("after_query")

        start = time.perf_counter()
        rows_processed = 0
        total_value = 0
        for row in result:
            value = row.get("value")
            total_value += int(value)
            rows_processed += 1
        iterate_duration = time.perf_counter() - start
        force_gc()
        after_iterate = snapshot("after_iterate")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "result_lazy_scan",
        "durations_s": {
            "query_create": query_duration,
            "iterate": iterate_duration,
            "wall_total": query_duration + iterate_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_iterate, after_close],
        "derived": {
            "rss_query_delta_bytes": delta(after_open, after_query, "rss_bytes"),
            "rss_iterate_delta_bytes": delta(after_query, after_iterate, "rss_bytes"),
            "python_peak_iterate_delta_bytes": delta(
                after_query, after_iterate, "python_peak_bytes"
            ),
        },
        "counts": {
            "rows_processed": rows_processed,
            "total_value": total_value,
        },
    }


def scenario_result_to_list(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_list_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        result = db.query("sql", "SELECT FROM Item ORDER BY value")
        after_query = snapshot("after_query")

        start = time.perf_counter()
        rows = result.to_list()
        materialize_duration = time.perf_counter() - start
        checksum = sum(int(row["value"]) for row in rows)
        force_gc()
        after_materialize = snapshot("after_materialize")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "result_to_list",
        "durations_s": {
            "materialize": materialize_duration,
            "wall_total": materialize_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_query,
            after_materialize,
            after_close,
        ],
        "derived": {
            "rss_materialize_delta_bytes": delta(
                after_query, after_materialize, "rss_bytes"
            ),
            "python_peak_materialize_delta_bytes": delta(
                after_query, after_materialize, "python_peak_bytes"
            ),
        },
        "counts": {
            "rows": len(rows),
            "checksum": checksum,
        },
    }


def scenario_result_iter_chunks(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_chunks_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        result = db.query("sql", "SELECT FROM Item ORDER BY value")
        after_query = snapshot("after_query")

        start = time.perf_counter()
        chunk_count = 0
        row_count = 0
        checksum = 0
        for chunk in result.iter_chunks(size=args.chunk_size):
            chunk_count += 1
            row_count += len(chunk)
            checksum += sum(int(row["value"]) for row in chunk)
        iterate_duration = time.perf_counter() - start
        force_gc()
        after_chunks = snapshot("after_chunks")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "result_iter_chunks",
        "durations_s": {
            "iterate_chunks": iterate_duration,
            "wall_total": iterate_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_chunks, after_close],
        "derived": {
            "rss_chunks_delta_bytes": delta(after_query, after_chunks, "rss_bytes"),
            "python_peak_chunks_delta_bytes": delta(
                after_query, after_chunks, "python_peak_bytes"
            ),
        },
        "counts": {
            "chunks": chunk_count,
            "rows": row_count,
            "checksum": checksum,
        },
    }


def scenario_document_to_dict(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_docdict_")
    populate_items_db(
        db_path,
        record_count=max(args.records, 10),
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        record = db.query("sql", "SELECT FROM Item ORDER BY value LIMIT 1").first()
        after_query = snapshot("after_query")

        start = time.perf_counter()
        checksum = 0
        for _ in range(args.dict_repeats):
            payload = record.to_dict()
            checksum += int(payload["value"])
        dict_duration = time.perf_counter() - start
        force_gc()
        after_to_dict = snapshot("after_to_dict")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "document_to_dict",
        "durations_s": {
            "to_dict_repeated": dict_duration,
            "wall_total": dict_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_to_dict, after_close],
        "derived": {
            "rss_to_dict_delta_bytes": delta(after_query, after_to_dict, "rss_bytes"),
            "python_peak_to_dict_delta_bytes": delta(
                after_query, after_to_dict, "python_peak_bytes"
            ),
        },
        "counts": {
            "repeats": args.dict_repeats,
            "checksum": checksum,
        },
    }


def scenario_lookup_paths(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_lookup_")
    populate_lookup_db(
        db_path,
        record_count=max(args.records, args.query_runs),
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        rid_rows = list(
            db.query("sql", "SELECT @rid AS rid FROM LookupItem ORDER BY item_id")
        )
        rid_values = [str(row.get("rid")) for row in rid_rows]
        after_seed = snapshot("after_seed")

        start = time.perf_counter()
        lookup_key_checksum = 0
        for index in range(args.query_runs):
            record = db.lookup_by_key(
                "LookupItem",
                ["item_id"],
                [index % len(rid_values)],
            )
            if record is None:
                raise RuntimeError("lookup_by_key returned None during profiling")
            lookup_key_checksum += int(record.get("item_id"))
        key_duration = time.perf_counter() - start
        force_gc()
        after_lookup_by_key = snapshot("after_lookup_by_key")

        start = time.perf_counter()
        lookup_rid_checksum = 0
        for index in range(args.query_runs):
            record = db.lookup_by_rid(rid_values[index % len(rid_values)])
            if record is None:
                raise RuntimeError("lookup_by_rid returned None during profiling")
            lookup_rid_checksum += int(record.get("item_id"))
        rid_duration = time.perf_counter() - start
        force_gc()
        after_lookup_by_rid = snapshot("after_lookup_by_rid")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "lookup_paths",
        "durations_s": {
            "lookup_by_key": key_duration,
            "lookup_by_rid": rid_duration,
            "wall_total": key_duration + rid_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_seed,
            after_lookup_by_key,
            after_lookup_by_rid,
            after_close,
        ],
        "derived": {
            "rss_lookup_by_key_delta_bytes": delta(
                after_seed,
                after_lookup_by_key,
                "rss_bytes",
            ),
            "python_peak_lookup_by_key_delta_bytes": delta(
                after_seed,
                after_lookup_by_key,
                "python_peak_bytes",
            ),
            "rss_lookup_by_rid_delta_bytes": delta(
                after_lookup_by_key,
                after_lookup_by_rid,
                "rss_bytes",
            ),
            "python_peak_lookup_by_rid_delta_bytes": delta(
                after_lookup_by_key,
                after_lookup_by_rid,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "query_runs": args.query_runs,
            "lookup_by_key_checksum": lookup_key_checksum,
            "lookup_by_rid_checksum": lookup_rid_checksum,
            "rid_count": len(rid_values),
        },
    }


def scenario_transaction_insert_batch(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_tx_")
    before_create = snapshot("before_create")
    try:
        db = arcadedb.create_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_create = snapshot("after_create")

        db.command("sql", "CREATE DOCUMENT TYPE TxItem")
        after_schema = snapshot("after_schema")

        start = time.perf_counter()
        with db.transaction():
            for index in range(args.records):
                db.command(
                    "sql",
                    "INSERT INTO TxItem SET tx_id = ?, payload = ?",
                    index,
                    f"tx-{index}",
                )
        tx_duration = time.perf_counter() - start
        force_gc()
        after_transaction = snapshot("after_transaction")

        inserted = db.query("sql", "SELECT count(*) AS c FROM TxItem").one().get("c")
        after_verify = snapshot("after_verify")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "transaction_insert_batch",
        "durations_s": {
            "transaction_insert": tx_duration,
            "wall_total": tx_duration,
        },
        "snapshots": [
            before_create,
            after_create,
            after_schema,
            after_transaction,
            after_verify,
            after_close,
        ],
        "derived": {
            "rss_transaction_delta_bytes": delta(
                after_schema,
                after_transaction,
                "rss_bytes",
            ),
            "python_peak_transaction_delta_bytes": delta(
                after_schema,
                after_transaction,
                "python_peak_bytes",
            ),
            "rss_transaction_verify_delta_bytes": delta(
                after_transaction,
                after_verify,
                "rss_bytes",
            ),
        },
        "counts": {
            "records": args.records,
            "inserted": int(inserted),
        },
    }


def scenario_nested_conversion(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_nested_")
    populate_nested_db(
        db_path,
        width=args.nested_width,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        record = db.query("sql", "SELECT FROM NestedDoc LIMIT 1").first()
        after_query = snapshot("after_query")

        start = time.perf_counter()
        nested_value = record.get("nested_data")
        get_duration = time.perf_counter() - start
        user_count = len(nested_value["users"])
        group_count = len(nested_value["groups"])
        score_checksum = sum(user["scores"][0] for user in nested_value["users"])
        force_gc()
        after_get = snapshot("after_get_nested")

        start = time.perf_counter()
        payload = record.to_dict()
        dict_duration = time.perf_counter() - start
        force_gc()
        after_to_dict = snapshot("after_to_dict")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "nested_conversion",
        "durations_s": {
            "get_nested": get_duration,
            "to_dict": dict_duration,
            "wall_total": get_duration + dict_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_query,
            after_get,
            after_to_dict,
            after_close,
        ],
        "derived": {
            "rss_get_nested_delta_bytes": delta(after_query, after_get, "rss_bytes"),
            "python_peak_get_nested_delta_bytes": delta(
                after_query,
                after_get,
                "python_peak_bytes",
            ),
            "rss_nested_to_dict_delta_bytes": delta(
                after_get,
                after_to_dict,
                "rss_bytes",
            ),
            "python_peak_nested_to_dict_delta_bytes": delta(
                after_get,
                after_to_dict,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "nested_width": args.nested_width,
            "user_count": user_count,
            "group_count": group_count,
            "score_checksum": score_checksum,
            "payload_keys": len(payload),
        },
    }


def scenario_graph_traversal(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_graph_")
    populate_graph_db(
        db_path,
        vertex_count=args.graph_vertices,
        degree=args.graph_degree,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        root = db.lookup_by_key("Person", ["person_id"], [0])
        if root is None:
            raise RuntimeError("Graph root vertex not found")
        after_lookup = snapshot("after_lookup")

        start = time.perf_counter()
        total_edges_seen = 0
        total_neighbor_checksum = 0
        for _ in range(args.query_runs):
            edges = root.get_out_edges("Knows")
            total_edges_seen += len(edges)
            for edge in edges:
                neighbor = edge.get_in()
                total_neighbor_checksum += int(neighbor.get("person_id"))
        out_duration = time.perf_counter() - start
        force_gc()
        after_out_edges = snapshot("after_out_edges")

        start = time.perf_counter()
        both_edges_seen = 0
        both_checksum = 0
        for _ in range(args.query_runs):
            edges = root.get_both_edges("Knows")
            both_edges_seen += len(edges)
            for edge in edges:
                both_checksum += int(edge.get("weight"))
        both_duration = time.perf_counter() - start
        force_gc()
        after_both_edges = snapshot("after_both_edges")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "graph_traversal",
        "durations_s": {
            "out_edges": out_duration,
            "both_edges": both_duration,
            "wall_total": out_duration + both_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_lookup,
            after_out_edges,
            after_both_edges,
            after_close,
        ],
        "derived": {
            "rss_out_edges_delta_bytes": delta(
                after_lookup,
                after_out_edges,
                "rss_bytes",
            ),
            "python_peak_out_edges_delta_bytes": delta(
                after_lookup,
                after_out_edges,
                "python_peak_bytes",
            ),
            "rss_both_edges_delta_bytes": delta(
                after_out_edges,
                after_both_edges,
                "rss_bytes",
            ),
            "python_peak_both_edges_delta_bytes": delta(
                after_out_edges,
                after_both_edges,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "graph_vertices": args.graph_vertices,
            "graph_degree": args.graph_degree,
            "query_runs": args.query_runs,
            "out_edges_seen": total_edges_seen,
            "neighbor_checksum": total_neighbor_checksum,
            "both_edges_seen": both_edges_seen,
            "both_checksum": both_checksum,
        },
    }


def scenario_graph_batch_ingest(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_graphbatch_")
    before_create = snapshot("before_create")
    try:
        db = arcadedb.create_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_create = snapshot("after_create")

        db.command("sql", "CREATE VERTEX TYPE Person")
        db.command("sql", "CREATE PROPERTY Person.person_id LONG")
        db.command("sql", "CREATE INDEX ON Person (person_id) UNIQUE_HASH")
        db.command("sql", "CREATE EDGE TYPE Knows")
        after_schema = snapshot("after_schema")

        vertex_payloads = [
            {"person_id": index, "name": f"person-{index}"}
            for index in range(args.graph_vertices)
        ]

        start = time.perf_counter()
        with db.graph_batch(
            batch_size=max(args.graph_degree * 4, 8),
            expected_edge_count=args.graph_vertices * args.graph_degree,
            parallel_flush=False,
        ) as batch:
            rids = batch.create_vertices("Person", vertex_payloads)
            for index in range(args.graph_vertices):
                for offset in range(1, args.graph_degree + 1):
                    target = (index + offset) % args.graph_vertices
                    batch.new_edge(
                        rids[index],
                        "Knows",
                        rids[target],
                        since=offset,
                    )
            buffered_edges = batch.get_buffered_edge_count()
            total_edges_created = batch.get_total_edges_created()
        batch_duration = time.perf_counter() - start
        force_gc()
        after_batch = snapshot("after_batch")

        start = time.perf_counter()
        vertex_count = (
            db.query(
                "sql",
                "SELECT count(*) AS c FROM Person",
            )
            .one()
            .get("c")
        )
        edge_rows = list(
            db.query(
                "sql",
                "SELECT expand(out('Knows')) FROM Person WHERE person_id = 0",
            )
        )
        verify_duration = time.perf_counter() - start
        force_gc()
        after_verify = snapshot("after_verify")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "graph_batch_ingest",
        "durations_s": {
            "graph_batch": batch_duration,
            "verify": verify_duration,
            "wall_total": batch_duration + verify_duration,
        },
        "snapshots": [
            before_create,
            after_create,
            after_schema,
            after_batch,
            after_verify,
            after_close,
        ],
        "derived": {
            "rss_batch_delta_bytes": delta(after_schema, after_batch, "rss_bytes"),
            "python_peak_batch_delta_bytes": delta(
                after_schema,
                after_batch,
                "python_peak_bytes",
            ),
            "rss_verify_delta_bytes": delta(after_batch, after_verify, "rss_bytes"),
        },
        "counts": {
            "graph_vertices": args.graph_vertices,
            "graph_degree": args.graph_degree,
            "vertex_count": int(vertex_count),
            "root_out_neighbors": len(edge_rows),
            "buffered_edges_after_close": buffered_edges,
            "total_edges_created": total_edges_created,
        },
    }


def scenario_vector_search(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_vector_")
    populate_vector_db(
        db_path,
        record_count=args.vector_records,
        dimensions=args.vector_dimensions,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        index = db.schema.get_vector_index("VectorDoc", "embedding")
        if index is None:
            raise RuntimeError("Vector index not found for profiling")

        query_vector = random_vector(999_999, args.vector_dimensions)
        start = time.perf_counter()
        search_counts = 0
        score_accumulator = 0.0
        for _ in range(args.query_runs):
            results = index.find_nearest(query_vector, k=args.vector_k)
            search_counts += len(results)
            score_accumulator += sum(float(score) for _, score in results)
        search_duration = time.perf_counter() - start
        force_gc()
        after_search = snapshot("after_search")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "vector_search",
        "durations_s": {
            "search": search_duration,
            "wall_total": search_duration,
        },
        "snapshots": [before_open, after_open, after_search, after_close],
        "derived": {
            "rss_search_delta_bytes": delta(after_open, after_search, "rss_bytes"),
            "python_peak_search_delta_bytes": delta(
                after_open, after_search, "python_peak_bytes"
            ),
        },
        "counts": {
            "query_runs": args.query_runs,
            "vector_k": args.vector_k,
            "vector_records": args.vector_records,
            "results_seen": search_counts,
            "score_accumulator": score_accumulator,
        },
    }


def scenario_vector_search_breakdown(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_vector_breakdown_")
    populate_vector_db(
        db_path,
        record_count=args.vector_records,
        dimensions=args.vector_dimensions,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        index = db.schema.get_vector_index("VectorDoc", "embedding")
        if index is None:
            raise RuntimeError("Vector index not found for profiling")

        get_primary_lsm_index = getattr(index, "_get_primary_lsm_index")
        primary_index = get_primary_lsm_index()
        if primary_index is None:
            raise RuntimeError("Primary LSM vector index not found for profiling")

        query_vector = random_vector(999_999, args.vector_dimensions)

        start = time.perf_counter()
        java_vector = arcadedb.to_java_float_array(query_vector)
        vector_conversion_duration = time.perf_counter() - start
        after_vector_conversion = snapshot("after_vector_conversion")

        start = time.perf_counter()
        find_neighbor_pairs = getattr(index, "_find_neighbor_pairs")
        pairs = find_neighbor_pairs(
            primary_index,
            java_vector=java_vector,
            k=args.vector_k,
            allowed_rids_set=None,
            approximate=False,
        )
        java_pairs_duration = time.perf_counter() - start
        after_java_pairs = snapshot("after_java_pairs")

        start = time.perf_counter()
        sort_results = getattr(index, "_sort_results")
        wrap_pair_results = getattr(index, "_wrap_pair_results")
        wrapped_results = sort_results(wrap_pair_results(pairs))[: args.vector_k]
        python_wrap_duration = time.perf_counter() - start
        force_gc()
        after_python_wrap = snapshot("after_python_wrap")

        start = time.perf_counter()
        hydrated_checksum = 0
        score_accumulator = 0.0
        for record, score in wrapped_results:
            hydrated_checksum += len(record.to_dict())
            score_accumulator += float(score)
        hydrate_duration = time.perf_counter() - start
        force_gc()
        after_hydrate = snapshot("after_hydrate")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "vector_search_breakdown",
        "durations_s": {
            "query_vector_conversion": vector_conversion_duration,
            "java_neighbor_search": java_pairs_duration,
            "python_wrap_results": python_wrap_duration,
            "python_hydrate_records": hydrate_duration,
            "wall_total": (
                vector_conversion_duration
                + java_pairs_duration
                + python_wrap_duration
                + hydrate_duration
            ),
        },
        "snapshots": [
            before_open,
            after_open,
            after_vector_conversion,
            after_java_pairs,
            after_python_wrap,
            after_hydrate,
            after_close,
        ],
        "derived": {
            "rss_query_vector_conversion_delta_bytes": delta(
                after_open,
                after_vector_conversion,
                "rss_bytes",
            ),
            "python_peak_query_vector_conversion_delta_bytes": delta(
                after_open,
                after_vector_conversion,
                "python_peak_bytes",
            ),
            "rss_java_neighbor_search_delta_bytes": delta(
                after_vector_conversion,
                after_java_pairs,
                "rss_bytes",
            ),
            "python_peak_java_neighbor_search_delta_bytes": delta(
                after_vector_conversion,
                after_java_pairs,
                "python_peak_bytes",
            ),
            "rss_python_wrap_results_delta_bytes": delta(
                after_java_pairs,
                after_python_wrap,
                "rss_bytes",
            ),
            "python_peak_python_wrap_results_delta_bytes": delta(
                after_java_pairs,
                after_python_wrap,
                "python_peak_bytes",
            ),
            "rss_python_hydrate_records_delta_bytes": delta(
                after_python_wrap,
                after_hydrate,
                "rss_bytes",
            ),
            "python_peak_python_hydrate_records_delta_bytes": delta(
                after_python_wrap,
                after_hydrate,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "vector_k": args.vector_k,
            "vector_records": args.vector_records,
            "pair_count": int(pairs.size()) if hasattr(pairs, "size") else None,
            "wrapped_results": len(wrapped_results),
            "hydrated_checksum": hydrated_checksum,
            "score_accumulator": score_accumulator,
        },
    }


def scenario_async_command_insert(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_async_insert_")
    before_create = snapshot("before_create")
    try:
        db = arcadedb.create_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_create = snapshot("after_create")

        db.command("sql", "CREATE DOCUMENT TYPE AsyncItem")
        after_schema = snapshot("after_schema")

        async_exec = db.async_executor()
        async_exec.set_parallel_level(args.async_parallel_level)
        async_exec.set_commit_every(args.async_commit_every)
        after_executor = snapshot("after_executor")

        start = time.perf_counter()
        for index in range(args.records):
            async_exec.command(
                "sql",
                "INSERT INTO AsyncItem SET item_id = :item_id, name = :name",
                item_id=index,
                name=f"async-{index}",
            )
        enqueue_duration = time.perf_counter() - start
        after_enqueue = snapshot("after_enqueue")

        start = time.perf_counter()
        async_exec.wait_completion()
        wait_duration = time.perf_counter() - start
        force_gc()
        after_wait = snapshot("after_wait")

        inserted = db.query("sql", "SELECT count(*) AS c FROM AsyncItem").one().get("c")
        after_verify = snapshot("after_verify")

        async_exec.close()
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "async_command_insert",
        "durations_s": {
            "enqueue_commands": enqueue_duration,
            "wait_completion": wait_duration,
            "wall_total": enqueue_duration + wait_duration,
        },
        "snapshots": [
            before_create,
            after_create,
            after_schema,
            after_executor,
            after_enqueue,
            after_wait,
            after_verify,
            after_close,
        ],
        "derived": {
            "rss_async_enqueue_delta_bytes": delta(
                after_executor,
                after_enqueue,
                "rss_bytes",
            ),
            "python_peak_async_enqueue_delta_bytes": delta(
                after_executor,
                after_enqueue,
                "python_peak_bytes",
            ),
            "rss_async_wait_delta_bytes": delta(after_enqueue, after_wait, "rss_bytes"),
            "python_peak_async_wait_delta_bytes": delta(
                after_enqueue,
                after_wait,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "records": args.records,
            "inserted": int(inserted),
            "async_parallel_level": args.async_parallel_level,
            "async_commit_every": args.async_commit_every,
        },
    }


def scenario_async_query_callback(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_async_query_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        async_exec = db.async_executor()
        async_exec.set_parallel_level(args.async_parallel_level)
        async_exec.set_commit_every(max(args.async_commit_every, 1))
        after_executor = snapshot("after_executor")

        seen_rows = 0
        checksum = 0

        def on_row(row):
            nonlocal seen_rows, checksum
            seen_rows += 1
            checksum += int(row.get("value"))

        start = time.perf_counter()
        async_exec.query("sql", "SELECT value FROM Item ORDER BY value", on_row)
        async_exec.wait_completion()
        callback_duration = time.perf_counter() - start
        force_gc()
        after_callback = snapshot("after_callback")

        async_exec.close()
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "async_query_callback",
        "durations_s": {
            "query_with_callback": callback_duration,
            "wall_total": callback_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_executor,
            after_callback,
            after_close,
        ],
        "derived": {
            "rss_async_query_callback_delta_bytes": delta(
                after_executor,
                after_callback,
                "rss_bytes",
            ),
            "python_peak_async_query_callback_delta_bytes": delta(
                after_executor,
                after_callback,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "rows_seen": seen_rows,
            "checksum": checksum,
            "records": args.records,
        },
    }


def scenario_import_documents(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_import_")
    csv_path = db_path.parent / "import_people.csv"
    write_people_csv(csv_path, args.records)
    before_create = snapshot("before_create")
    try:
        db = arcadedb.create_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_create = snapshot("after_create")

        start = time.perf_counter()
        result = db.import_documents(
            csv_path,
            document_type="ImportedPerson",
            file_type="csv",
            commit_every=max(args.async_commit_every, 1),
            parallel=min(args.async_parallel_level, 4),
            wal=False,
        )
        import_duration = time.perf_counter() - start
        force_gc()
        after_import = snapshot("after_import")

        count = (
            db.query("sql", "SELECT count(*) AS c FROM ImportedPerson").one().get("c")
        )
        stats_payload = result.to_dict()
        after_verify = snapshot("after_verify")

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "import_documents",
        "durations_s": {
            "import_documents": import_duration,
            "wall_total": import_duration,
        },
        "snapshots": [
            before_create,
            after_create,
            after_import,
            after_verify,
            after_close,
        ],
        "derived": {
            "rss_import_documents_delta_bytes": delta(
                after_create,
                after_import,
                "rss_bytes",
            ),
            "python_peak_import_documents_delta_bytes": delta(
                after_create,
                after_import,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "records": args.records,
            "imported": int(count),
            "statistics_keys": len(stats_payload),
        },
    }


def scenario_export_to_csv(args: argparse.Namespace) -> dict[str, Any]:
    import arcadedb_embedded as arcadedb

    db_path = make_temp_db_path("arcadedb_profile_export_csv_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    csv_path = db_path.parent / "items.csv"
    before_open = snapshot("before_open")
    try:
        db = arcadedb.open_database(
            str(db_path),
            jvm_kwargs={"heap_size": args.heap_size},
        )
        after_open = snapshot("after_open")

        start = time.perf_counter()
        db.export_to_csv(
            "SELECT name, value, category FROM Item ORDER BY value",
            str(csv_path),
        )
        export_duration = time.perf_counter() - start
        force_gc()
        after_export = snapshot("after_export")

        line_count = 0
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as handle:
                line_count = sum(1 for _ in handle)

        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "export_to_csv",
        "durations_s": {
            "export_to_csv": export_duration,
            "wall_total": export_duration,
        },
        "snapshots": [before_open, after_open, after_export, after_close],
        "derived": {
            "rss_export_to_csv_delta_bytes": delta(
                after_open,
                after_export,
                "rss_bytes",
            ),
            "python_peak_export_to_csv_delta_bytes": delta(
                after_open,
                after_export,
                "python_peak_bytes",
            ),
        },
        "counts": {
            "records": args.records,
            "csv_lines": line_count,
            "file_size_bytes": csv_path.stat().st_size if csv_path.exists() else 0,
        },
    }


SCENARIO_FUNCS = {
    "jvm_startup": scenario_jvm_startup,
    "db_lifecycle": scenario_db_lifecycle,
    "result_lazy_scan": scenario_result_lazy_scan,
    "result_to_list": scenario_result_to_list,
    "result_iter_chunks": scenario_result_iter_chunks,
    "document_to_dict": scenario_document_to_dict,
    "lookup_paths": scenario_lookup_paths,
    "transaction_insert_batch": scenario_transaction_insert_batch,
    "nested_conversion": scenario_nested_conversion,
    "graph_traversal": scenario_graph_traversal,
    "graph_batch_ingest": scenario_graph_batch_ingest,
    "vector_search": scenario_vector_search,
    "vector_search_breakdown": scenario_vector_search_breakdown,
    "async_command_insert": scenario_async_command_insert,
    "async_query_callback": scenario_async_query_callback,
    "import_documents": scenario_import_documents,
    "export_to_csv": scenario_export_to_csv,
}


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


WORKER_JSON_MARKER = "__PROFILE_JSON__"


def run_worker(args: argparse.Namespace) -> int:
    tracemalloc.start(25)
    scenario = args.worker_scenario
    if scenario not in SCENARIO_FUNCS:
        raise ValueError(f"Unknown worker scenario: {scenario}")

    start = time.perf_counter()
    result = SCENARIO_FUNCS[scenario](args)
    result["worker_wall_time_s"] = time.perf_counter() - start
    payload = json.dumps(result, sort_keys=True, default=json_default)
    print(f"{WORKER_JSON_MARKER}{payload}")
    return 0


def build_worker_command(args: argparse.Namespace, scenario: str) -> list[str]:
    script_path = Path(__file__).resolve()
    command = [
        sys.executable,
        str(script_path),
        "--worker-scenario",
        scenario,
        "--records",
        str(args.records),
        "--graph-vertices",
        str(args.graph_vertices),
        "--graph-degree",
        str(args.graph_degree),
        "--vector-records",
        str(args.vector_records),
        "--vector-dimensions",
        str(args.vector_dimensions),
        "--vector-k",
        str(args.vector_k),
        "--query-runs",
        str(args.query_runs),
        "--dict-repeats",
        str(args.dict_repeats),
        "--nested-width",
        str(args.nested_width),
        "--chunk-size",
        str(args.chunk_size),
        "--async-parallel-level",
        str(args.async_parallel_level),
        "--async-commit-every",
        str(args.async_commit_every),
        "--heap-size",
        args.heap_size,
    ]
    if args.keep_temp:
        command.append("--keep-temp")
    return command


def summarize_numeric(values: list[float | int | None]) -> dict[str, float | None]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return {
            "min": None,
            "mean": None,
            "median": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    numeric.sort()
    return {
        "min": numeric[0],
        "mean": statistics.fmean(numeric),
        "median": statistics.median(numeric),
        "p95": percentile(numeric, 0.95),
        "p99": percentile(numeric, 0.99),
        "max": numeric[-1],
    }


def percentile(sorted_values: list[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * weight


def aggregate_runs(scenario: str, run_results: list[dict[str, Any]]) -> dict[str, Any]:
    duration_keys: set[str] = set()
    derived_keys: set[str] = set()
    count_keys: set[str] = set()
    for item in run_results:
        duration_keys.update(item.get("durations_s", {}).keys())
        derived_keys.update(item.get("derived", {}).keys())
        count_keys.update(item.get("counts", {}).keys())

    summary = {
        "scenario": scenario,
        "runs": len(run_results),
        "durations_s": {
            key: summarize_numeric(
                [item.get("durations_s", {}).get(key) for item in run_results]
            )
            for key in sorted(duration_keys)
        },
        "derived": {
            key: summarize_numeric(
                [item.get("derived", {}).get(key) for item in run_results]
            )
            for key in sorted(derived_keys)
        },
        "counts": {
            key: summarize_numeric(
                [item.get("counts", {}).get(key) for item in run_results]
            )
            for key in sorted(count_keys)
        },
        "worker_wall_time_s": summarize_numeric(
            [item.get("worker_wall_time_s") for item in run_results]
        ),
        "worker_overhead_s": summarize_numeric(
            [worker_overhead_seconds(item) for item in run_results]
        ),
    }
    return summary


def worker_overhead_seconds(run_result: dict[str, Any]) -> float | None:
    worker_wall = run_result.get("worker_wall_time_s")
    wall_total = run_result.get("durations_s", {}).get("wall_total")
    if worker_wall is None or wall_total is None:
        return None
    return float(worker_wall) - float(wall_total)


def extract_worker_payload(stdout: str) -> dict[str, Any]:
    marker_index = stdout.rfind(WORKER_JSON_MARKER)
    if marker_index == -1:
        raise ValueError("Worker output did not contain profiler JSON marker")

    payload_text = stdout[marker_index + len(WORKER_JSON_MARKER) :].strip()
    if not payload_text:
        raise ValueError("Worker output marker found but JSON payload was empty")

    return json.loads(payload_text)


def format_bytes(value: float | None) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TiB"


def print_summary(report: dict[str, Any]) -> None:
    print("=" * 88)
    print("ArcadeDB Python Binding Profiler")
    print("=" * 88)
    print(f"Runs per scenario: {report['config']['runs']}")
    if report["config"].get("preset"):
        print(f"Preset: {report['config']['preset']}")
    print(f"Heap size: {report['config']['heap_size']}")
    print(f"Records: {report['config']['records']}")
    print(f"Graph vertices: {report['config']['graph_vertices']}")
    print(f"Vector records: {report['config']['vector_records']}")
    print(f"Vector k: {report['config']['vector_k']}")
    print(f"Nested width: {report['config']['nested_width']}")
    print(f"Async parallel level: {report['config']['async_parallel_level']}")
    print()

    for scenario in report["scenario_summaries"]:
        durations = scenario["durations_s"]
        derived = scenario["derived"]
        wall_mean = durations.get("wall_total", {}).get("mean")
        wall_p95 = durations.get("wall_total", {}).get("p95")
        wall_p99 = durations.get("wall_total", {}).get("p99")
        worker_mean = scenario["worker_wall_time_s"].get("mean")
        overhead_mean = scenario["worker_overhead_s"].get("mean")
        print(f"[{scenario['scenario']}]")
        if wall_mean is not None:
            print(f"  wall mean:          {wall_mean:.6f}s")
        else:
            print("  wall mean:          n/a")
        if wall_p95 is not None:
            print(f"  wall p95:           {wall_p95:.6f}s")
        if wall_p99 is not None:
            print(f"  wall p99:           {wall_p99:.6f}s")
        if worker_mean is not None:
            print(f"  worker mean:        {worker_mean:.6f}s")
        else:
            print("  worker mean:        n/a")
        if overhead_mean is not None:
            print(f"  setup/overhead:     {overhead_mean:.6f}s")

        interesting_duration_keys = [
            key for key in durations.keys() if key != "wall_total"
        ]
        for key in interesting_duration_keys:
            mean_value = durations[key]["mean"]
            if mean_value is not None:
                print(f"  {key:<18} {mean_value:.6f}s")

        for key in sorted(derived.keys()):
            mean_value = derived[key]["mean"]
            if key.endswith("_bytes"):
                print(f"  {key:<18} {format_bytes(mean_value)}")
            elif mean_value is not None:
                print(f"  {key:<18} {mean_value:.6f}")
        print()


def run_parent(args: argparse.Namespace) -> int:
    scenarios = resolve_scenarios(args)
    raw_results: dict[str, list[dict[str, Any]]] = {
        scenario: [] for scenario in scenarios
    }
    total_runs = len(scenarios) * args.runs
    completed_runs = 0

    for scenario in scenarios:
        for run_index in range(1, args.runs + 1):
            completed_runs += 1
            print(
                f"[{completed_runs}/{total_runs}] running {scenario} "
                f"(run {run_index}/{args.runs})...",
                flush=True,
            )
            started_at = time.perf_counter()
            command = build_worker_command(args, scenario)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=str(BINDINGS_ROOT),
                check=False,
            )
            if completed.returncode != 0:
                sys.stderr.write(completed.stdout)
                sys.stderr.write(completed.stderr)
                raise RuntimeError(
                    f"Scenario {scenario} failed on run {run_index} with code "
                    f"{completed.returncode}"
                )
            payload = extract_worker_payload(completed.stdout)
            payload["run_index"] = run_index
            raw_results[scenario].append(payload)
            elapsed = time.perf_counter() - started_at
            print(
                f"[{completed_runs}/{total_runs}] completed {scenario} "
                f"(run {run_index}/{args.runs}) in {elapsed:.2f}s",
                flush=True,
            )

    scenario_summaries = [
        aggregate_runs(scenario, raw_results[scenario]) for scenario in scenarios
    ]
    report = {
        "created_at_epoch_s": time.time(),
        "config": {
            "preset": args.preset or None,
            "scenarios": scenarios,
            "runs": args.runs,
            "records": args.records,
            "graph_vertices": args.graph_vertices,
            "graph_degree": args.graph_degree,
            "vector_records": args.vector_records,
            "vector_dimensions": args.vector_dimensions,
            "vector_k": args.vector_k,
            "query_runs": args.query_runs,
            "dict_repeats": args.dict_repeats,
            "nested_width": args.nested_width,
            "chunk_size": args.chunk_size,
            "async_parallel_level": args.async_parallel_level,
            "async_commit_every": args.async_commit_every,
            "heap_size": args.heap_size,
        },
        "scenario_summaries": scenario_summaries,
        "raw_results": raw_results,
    }

    if args.output_json:
        output_path = Path(args.output_json)
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_path = PROFILE_DIR / f"profile-report-{timestamp}.json"

    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print_summary(report)
    print(f"JSON report written to: {output_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be >= 1")
    if args.records < 1:
        raise ValueError("--records must be >= 1")
    if args.graph_vertices < 2:
        raise ValueError("--graph-vertices must be >= 2")
    if args.graph_degree < 1:
        raise ValueError("--graph-degree must be >= 1")
    if args.vector_records < 1:
        raise ValueError("--vector-records must be >= 1")
    if args.vector_dimensions < 2:
        raise ValueError("--vector-dimensions must be >= 2")
    if args.vector_k < 1:
        raise ValueError("--vector-k must be >= 1")
    if args.query_runs < 1:
        raise ValueError("--query-runs must be >= 1")
    if args.dict_repeats < 1:
        raise ValueError("--dict-repeats must be >= 1")
    if args.nested_width < 1:
        raise ValueError("--nested-width must be >= 1")
    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be >= 1")
    if args.async_parallel_level < 1 or args.async_parallel_level > 16:
        raise ValueError("--async-parallel-level must be between 1 and 16")
    if args.async_commit_every < 0:
        raise ValueError("--async-commit-every must be >= 0")

    if args.worker_scenario:
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
