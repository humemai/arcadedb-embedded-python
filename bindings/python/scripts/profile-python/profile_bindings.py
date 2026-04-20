#!/usr/bin/env python3
"""Profile SQL/OpenCypher-first ArcadeDB Python binding workloads.

This profiler measures the Python-side cost of consuming results after ArcadeDB
has already executed the query in Java.

Each scenario runs in an isolated subprocess so JVM startup and heap state remain
separate across runs.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE_DIR = Path(__file__).resolve().parent
BINDINGS_ROOT = PROFILE_DIR.parent.parent
SRC_DIR = BINDINGS_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

WORKER_JSON_MARKER = "__PROFILE_JSON__"

AVAILABLE_SCENARIOS = (
    "jvm_startup",
    "db_lifecycle",
    "sql_projected_lazy_scan",
    "sql_projected_to_list",
    "sql_full_records_to_list",
    "sql_full_records_to_list_no_convert",
    "sql_full_records_wrapper_scan",
    "sql_full_records_to_list_retained",
    "sql_aggregate_first",
    "sql_aggregate_one",
    "opencypher_lazy_scan",
    "opencypher_to_list",
    "sql_vector_neighbors_extract_hits",
    "sql_vector_neighbors_followup_query",
    "async_query_callback",
    "export_to_csv",
)

SCENARIO_PRESETS: dict[str, tuple[str, ...]] = {
    "smoke": (
        "sql_aggregate_first",
        "sql_projected_lazy_scan",
        "opencypher_lazy_scan",
        "sql_vector_neighbors_extract_hits",
        "async_query_callback",
        "export_to_csv",
    ),
    "core": (
        "jvm_startup",
        "db_lifecycle",
        "sql_projected_lazy_scan",
        "sql_projected_to_list",
        "sql_full_records_to_list",
        "sql_full_records_to_list_no_convert",
        "sql_full_records_wrapper_scan",
        "sql_full_records_to_list_retained",
        "sql_aggregate_first",
        "sql_aggregate_one",
        "opencypher_lazy_scan",
        "opencypher_to_list",
        "sql_vector_neighbors_extract_hits",
        "sql_vector_neighbors_followup_query",
    ),
    "full": AVAILABLE_SCENARIOS,
}

DEFAULT_SCENARIOS = AVAILABLE_SCENARIOS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile ArcadeDB embedded Python SQL/OpenCypher workloads"
    )
    parser.add_argument(
        "--preset",
        choices=sorted(SCENARIO_PRESETS.keys()),
        default="",
        help="Named scenario preset. Overrides --scenarios when provided.",
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
        help="Number of isolated subprocess runs per scenario",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=5000,
        help="Item records for SQL materialization scenarios",
    )
    parser.add_argument(
        "--person-count",
        type=int,
        default=1500,
        help="Person vertices for OpenCypher scenarios",
    )
    parser.add_argument(
        "--graph-degree",
        type=int,
        default=3,
        help="Outgoing FRIEND_OF edges per person",
    )
    parser.add_argument(
        "--vector-records",
        type=int,
        default=1500,
        help="Vector documents for SQL vector scenarios",
    )
    parser.add_argument(
        "--vector-dimensions",
        type=int,
        default=32,
        help="Vector dimensionality",
    )
    parser.add_argument(
        "--vector-k",
        type=int,
        default=10,
        help="Top-k vector result count",
    )
    parser.add_argument(
        "--query-runs",
        type=int,
        default=100,
        help="Repeated query count inside each scenario",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for CSV export scenario",
    )
    parser.add_argument(
        "--heap-size",
        default="2g",
        help="JVM heap size passed into start_jvm/create_database",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output JSON path",
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
        raise ValueError("At least one scenario must be selected")

    invalid = [item for item in scenarios if item not in AVAILABLE_SCENARIOS]
    if invalid:
        raise ValueError(f"Unknown scenarios: {', '.join(invalid)}")
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
                return int(line.split()[1]) * 1024

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
                "jvm_free_bytes": None,
                "jvm_total_bytes": None,
                "jvm_max_bytes": None,
            }

        runtime = jpype.JClass("java.lang.Runtime").getRuntime()
        return {
            "jvm_free_bytes": int(runtime.freeMemory()),
            "jvm_total_bytes": int(runtime.totalMemory()),
            "jvm_max_bytes": int(runtime.maxMemory()),
        }
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return {
            "jvm_free_bytes": None,
            "jvm_total_bytes": None,
            "jvm_max_bytes": None,
        }


def force_gc() -> None:
    gc.collect()
    try:
        import jpype

        if jpype.isJVMStarted():
            jpype.java.lang.System.gc()
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


def vector_literal(values: list[float]) -> str:
    return "[" + ", ".join(f"{value:.6f}" for value in values) + "]"


def make_temp_db_path(prefix: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    return temp_dir / "db"


def cleanup_temp_db(db_path: Path, keep_temp: bool) -> None:
    if keep_temp:
        return
    temp_root = db_path.parent
    if temp_root.exists():
        for path in sorted(temp_root.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            else:
                path.rmdir()
        temp_root.rmdir()


def populate_items_db(db_path: Path, *, record_count: int, heap_size: str) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE DOCUMENT TYPE Item")
        with db.transaction():
            for index in range(record_count):
                db.command(
                    "sql",
                    (
                        "INSERT INTO Item (name, value, category, bucket_id, "
                        "payload) VALUES (?, ?, ?, ?, ?)"
                    ),
                    f"item-{index:05d}",
                    index,
                    f"cat-{index % 10}",
                    index % 32,
                    f"payload-{index:05d}-{index % 7}",
                )
    finally:
        db.close()


def populate_graph_query_db(
    db_path: Path,
    *,
    person_count: int,
    degree: int,
    heap_size: str,
) -> None:
    import arcadedb_embedded as arcadedb

    db = arcadedb.create_database(str(db_path), jvm_kwargs={"heap_size": heap_size})
    try:
        db.command("sql", "CREATE VERTEX TYPE Person")
        db.command("sql", "CREATE EDGE TYPE FRIEND_OF")

        with db.transaction():
            for index in range(person_count):
                db.command(
                    "sql",
                    (
                        "INSERT INTO Person (name, city, age, person_id) "
                        "VALUES (?, ?, ?, ?)"
                    ),
                    f"person-{index:05d}",
                    f"city-{index % 25}",
                    20 + (index % 40),
                    index,
                )

        with db.transaction():
            for index in range(person_count):
                source_name = f"person-{index:05d}"
                for hop in range(1, degree + 1):
                    target_name = f"person-{(index + hop) % person_count:05d}"
                    db.command(
                        "sql",
                        (
                            "CREATE EDGE FRIEND_OF FROM "
                            "(SELECT FROM Person WHERE name = ?) TO "
                            "(SELECT FROM Person WHERE name = ?)"
                        ),
                        source_name,
                        target_name,
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
        db.command("sql", "CREATE VERTEX TYPE Doc")
        db.command("sql", "CREATE PROPERTY Doc.id LONG")
        db.command("sql", "CREATE PROPERTY Doc.title STRING")
        db.command("sql", "CREATE PROPERTY Doc.category STRING")
        db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

        with db.transaction():
            for index in range(record_count):
                db.command(
                    "sql",
                    (
                        "INSERT INTO Doc (id, title, category, embedding) "
                        "VALUES (?, ?, ?, ?)"
                    ),
                    index,
                    f"doc-{index:05d}",
                    f"cat-{index % 8}",
                    arcadedb.to_java_float_array(random_vector(index, dimensions)),
                )

        db.create_vector_index("Doc", "embedding", dimensions=dimensions)
    finally:
        db.close()


def extract_vector_hit_id(hit: Any) -> int | None:
    candidate = hit
    if isinstance(candidate, tuple) and candidate:
        candidate = candidate[0]

    if hasattr(candidate, "get"):
        try:
            direct = candidate.get("id")
            if direct is not None:
                return int(direct)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

        try:
            nested = candidate.get("record")
            if nested is not None and hasattr(nested, "get"):
                record_id = nested.get("id")
                if record_id is not None:
                    return int(record_id)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

    if isinstance(candidate, dict):
        record_id = candidate.get("id")
        if record_id is not None:
            return int(record_id)

        nested = candidate.get("record")
        if isinstance(nested, dict) and nested.get("id") is not None:
            return int(nested["id"])

    return None


def open_database(db_path: Path, heap_size: str):
    import arcadedb_embedded as arcadedb

    return arcadedb.open_database(str(db_path), jvm_kwargs={"heap_size": heap_size})


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
        "durations_s": {"start_jvm": duration, "wall_total": duration},
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
            str(db_path), jvm_kwargs={"heap_size": args.heap_size}
        )
        create_duration = time.perf_counter() - start
        after_create = snapshot("after_create_database")

        start = time.perf_counter()
        db.command("sql", "CREATE DOCUMENT TYPE Item")
        with db.transaction():
            for index in range(args.records):
                db.command(
                    "sql",
                    "INSERT INTO Item SET name = ?, value = ?",
                    f"item-{index:05d}",
                    index,
                )
        populate_duration = time.perf_counter() - start
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
                before, after_populate, "rss_bytes"
            ),
            "rss_after_close_delta_bytes": delta(before, after_close, "rss_bytes"),
        },
        "counts": {"records": args.records},
    }


def scenario_sql_projected_lazy_scan(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_lazy_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = (
            "SELECT name, value FROM Item WHERE bucket_id < 16 ORDER BY value "
            "LIMIT ?"
        )
        checksum = 0
        rows_processed = 0
        query_duration = 0.0
        iterate_duration = 0.0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            iterate_start = time.perf_counter()
            for row in result:
                rows_processed += 1
                checksum += int(row.get("value"))
            iterate_duration += time.perf_counter() - iterate_start
        after_query = snapshot("after_query")
        force_gc()
        after_iterate = snapshot("after_iterate")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_projected_lazy_scan",
        "durations_s": {
            "query_create": query_duration,
            "iterate": iterate_duration,
            "wall_total": query_duration + iterate_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_iterate, after_close],
        "derived": {
            "rss_iterate_delta_bytes": delta(after_query, after_iterate, "rss_bytes"),
            "python_peak_iterate_delta_bytes": delta(
                after_query, after_iterate, "python_peak_bytes"
            ),
        },
        "counts": {"rows_processed": rows_processed, "checksum": checksum},
    }


def scenario_sql_projected_to_list(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_list_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = (
            "SELECT name, value FROM Item WHERE bucket_id < 16 ORDER BY value "
            "LIMIT ?"
        )
        before_materialize = snapshot("before_materialize")
        query_duration = 0.0
        materialize_duration = 0.0
        checksum = 0
        row_count = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            materialize_start = time.perf_counter()
            rows = result.to_list()
            materialize_duration += time.perf_counter() - materialize_start
            row_count += len(rows)
            checksum += sum(int(row["value"]) for row in rows)
        after_materialize = snapshot("after_materialize")
        force_gc()
        after_release = snapshot("after_release")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_projected_to_list",
        "durations_s": {
            "query_create": query_duration,
            "materialize": materialize_duration,
            "wall_total": query_duration + materialize_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            before_materialize,
            after_materialize,
            after_release,
            after_close,
        ],
        "derived": {
            "rss_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "rss_bytes"
            ),
            "python_peak_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "python_peak_bytes"
            ),
            "rss_release_delta_bytes": delta(
                after_materialize, after_release, "rss_bytes"
            ),
            "python_peak_release_delta_bytes": delta(
                after_materialize, after_release, "python_peak_bytes"
            ),
        },
        "counts": {"rows": row_count, "checksum": checksum},
    }


def scenario_sql_full_records_to_list(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_fullrecords_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT FROM Item ORDER BY value LIMIT ?"
        before_materialize = snapshot("before_materialize")
        query_duration = 0.0
        materialize_duration = 0.0
        checksum = 0
        row_count = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            materialize_start = time.perf_counter()
            rows = result.to_list()
            materialize_duration += time.perf_counter() - materialize_start
            row_count += len(rows)
            checksum += sum(int(row["value"]) for row in rows)
        after_materialize = snapshot("after_materialize")
        force_gc()
        after_release = snapshot("after_release")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_full_records_to_list",
        "durations_s": {
            "query_create": query_duration,
            "materialize": materialize_duration,
            "wall_total": query_duration + materialize_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            before_materialize,
            after_materialize,
            after_release,
            after_close,
        ],
        "derived": {
            "rss_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "rss_bytes"
            ),
            "python_peak_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "python_peak_bytes"
            ),
            "rss_release_delta_bytes": delta(
                after_materialize, after_release, "rss_bytes"
            ),
            "python_peak_release_delta_bytes": delta(
                after_materialize, after_release, "python_peak_bytes"
            ),
        },
        "counts": {"rows": row_count, "checksum": checksum},
    }


def scenario_sql_full_records_to_list_no_convert(
    args: argparse.Namespace,
) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_fullrecords_raw_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT FROM Item ORDER BY value LIMIT ?"
        before_materialize = snapshot("before_materialize")
        query_duration = 0.0
        materialize_duration = 0.0
        checksum = 0
        row_count = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            materialize_start = time.perf_counter()
            rows = result.to_list(convert_types=False)
            materialize_duration += time.perf_counter() - materialize_start
            row_count += len(rows)
            checksum += len(rows)
        after_materialize = snapshot("after_materialize")
        force_gc()
        after_release = snapshot("after_release")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_full_records_to_list_no_convert",
        "durations_s": {
            "query_create": query_duration,
            "materialize": materialize_duration,
            "wall_total": query_duration + materialize_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            before_materialize,
            after_materialize,
            after_release,
            after_close,
        ],
        "derived": {
            "rss_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "rss_bytes"
            ),
            "python_peak_materialize_delta_bytes": delta(
                before_materialize, after_materialize, "python_peak_bytes"
            ),
            "rss_release_delta_bytes": delta(
                after_materialize, after_release, "rss_bytes"
            ),
            "python_peak_release_delta_bytes": delta(
                after_materialize, after_release, "python_peak_bytes"
            ),
        },
        "counts": {"rows": row_count, "checksum": checksum},
    }


def scenario_sql_full_records_wrapper_scan(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_fullrecords_wrappers_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT FROM Item ORDER BY value LIMIT ?"
        before_iterate = snapshot("before_iterate")
        query_duration = 0.0
        iterate_duration = 0.0
        rows_seen = 0
        checksum = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            iterate_start = time.perf_counter()
            for row in result:
                rows_seen += 1
                rid = row.get_rid()
                checksum += 0 if rid is None else len(rid)
            iterate_duration += time.perf_counter() - iterate_start
        after_iterate = snapshot("after_iterate")
        force_gc()
        after_release = snapshot("after_release")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_full_records_wrapper_scan",
        "durations_s": {
            "query_create": query_duration,
            "iterate": iterate_duration,
            "wall_total": query_duration + iterate_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            before_iterate,
            after_iterate,
            after_release,
            after_close,
        ],
        "derived": {
            "rss_iterate_delta_bytes": delta(
                before_iterate, after_iterate, "rss_bytes"
            ),
            "python_peak_iterate_delta_bytes": delta(
                before_iterate, after_iterate, "python_peak_bytes"
            ),
            "rss_release_delta_bytes": delta(after_iterate, after_release, "rss_bytes"),
            "python_peak_release_delta_bytes": delta(
                after_iterate, after_release, "python_peak_bytes"
            ),
        },
        "counts": {"rows_seen": rows_seen, "checksum": checksum},
    }


def scenario_sql_full_records_to_list_retained(
    args: argparse.Namespace,
) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_fullrecords_retained_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT FROM Item ORDER BY value LIMIT ?"
        before_materialize = snapshot("before_materialize")
        query_duration = 0.0
        materialize_duration = 0.0
        retained_rows: list[list[dict[str, Any]]] = []
        checksum = 0
        row_count = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text, args.records)
            query_duration += time.perf_counter() - query_start

            materialize_start = time.perf_counter()
            rows = result.to_list()
            retained_rows.append(rows)
            materialize_duration += time.perf_counter() - materialize_start
            row_count += len(rows)
            checksum += sum(int(row["value"]) for row in rows)
        after_retained = snapshot("after_retained")
        retained_batch_count = len(retained_rows)
        retained_checksum = checksum
        retained_rows = []
        force_gc()
        after_release = snapshot("after_release")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_full_records_to_list_retained",
        "durations_s": {
            "query_create": query_duration,
            "materialize": materialize_duration,
            "wall_total": query_duration + materialize_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            before_materialize,
            after_retained,
            after_release,
            after_close,
        ],
        "derived": {
            "rss_retained_delta_bytes": delta(
                before_materialize, after_retained, "rss_bytes"
            ),
            "python_peak_retained_delta_bytes": delta(
                before_materialize, after_retained, "python_peak_bytes"
            ),
            "rss_release_delta_bytes": delta(
                after_retained, after_release, "rss_bytes"
            ),
            "python_peak_release_delta_bytes": delta(
                after_retained, after_release, "python_peak_bytes"
            ),
        },
        "counts": {
            "rows": row_count,
            "checksum": retained_checksum,
            "retained_batches": retained_batch_count,
        },
    }


def scenario_sql_aggregate_first(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_first_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT count(*) as c, avg(value) as avg_value FROM Item"
        query_duration = 0.0
        first_duration = 0.0
        checksum = 0.0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text)
            query_duration += time.perf_counter() - query_start

            first_start = time.perf_counter()
            row = result.first()
            first_duration += time.perf_counter() - first_start
            checksum += float(row.get("c")) + float(row.get("avg_value"))
        after_query = snapshot("after_query")
        force_gc()
        after_first = snapshot("after_first")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_aggregate_first",
        "durations_s": {
            "query_create": query_duration,
            "first": first_duration,
            "wall_total": query_duration + first_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_first, after_close],
        "derived": {
            "rss_first_delta_bytes": delta(after_query, after_first, "rss_bytes"),
            "python_peak_first_delta_bytes": delta(
                after_query, after_first, "python_peak_bytes"
            ),
        },
        "counts": {"checksum": checksum},
    }


def scenario_sql_aggregate_one(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_one_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = "SELECT count(*) as c, avg(value) as avg_value FROM Item"
        query_duration = 0.0
        one_duration = 0.0
        checksum = 0.0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("sql", query_text)
            query_duration += time.perf_counter() - query_start

            one_start = time.perf_counter()
            row = result.one()
            one_duration += time.perf_counter() - one_start
            checksum += float(row.get("c")) + float(row.get("avg_value"))
        after_query = snapshot("after_query")
        force_gc()
        after_one = snapshot("after_one")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_aggregate_one",
        "durations_s": {
            "query_create": query_duration,
            "one": one_duration,
            "wall_total": query_duration + one_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_one, after_close],
        "derived": {
            "rss_one_delta_bytes": delta(after_query, after_one, "rss_bytes"),
            "python_peak_one_delta_bytes": delta(
                after_query, after_one, "python_peak_bytes"
            ),
        },
        "counts": {"checksum": checksum},
    }


def scenario_opencypher_lazy_scan(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_cypher_lazy_")
    populate_graph_query_db(
        db_path,
        person_count=args.person_count,
        degree=args.graph_degree,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = (
            "MATCH (p:Person {name: 'person-00000'})-[:FRIEND_OF]->(friend:Person) "
            "RETURN friend.name AS name, friend.city AS city ORDER BY name"
        )
        query_duration = 0.0
        iterate_duration = 0.0
        checksum = 0
        rows_processed = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("opencypher", query_text)
            query_duration += time.perf_counter() - query_start

            iterate_start = time.perf_counter()
            for row in result:
                rows_processed += 1
                checksum += len(str(row.get("name"))) + len(str(row.get("city")))
            iterate_duration += time.perf_counter() - iterate_start
        after_query = snapshot("after_query")
        force_gc()
        after_iterate = snapshot("after_iterate")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "opencypher_lazy_scan",
        "durations_s": {
            "query_create": query_duration,
            "iterate": iterate_duration,
            "wall_total": query_duration + iterate_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_iterate, after_close],
        "derived": {
            "rss_iterate_delta_bytes": delta(after_query, after_iterate, "rss_bytes"),
            "python_peak_iterate_delta_bytes": delta(
                after_query, after_iterate, "python_peak_bytes"
            ),
        },
        "counts": {"rows_processed": rows_processed, "checksum": checksum},
    }


def scenario_opencypher_to_list(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_cypher_list_")
    populate_graph_query_db(
        db_path,
        person_count=args.person_count,
        degree=args.graph_degree,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_text = (
            "MATCH (p:Person {name: 'person-00000'})-[:FRIEND_OF]->(friend:Person) "
            "RETURN friend.name AS name, friend.city AS city ORDER BY name"
        )
        query_duration = 0.0
        materialize_duration = 0.0
        checksum = 0
        row_count = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            result = db.query("opencypher", query_text)
            query_duration += time.perf_counter() - query_start

            materialize_start = time.perf_counter()
            rows = result.to_list()
            materialize_duration += time.perf_counter() - materialize_start
            row_count += len(rows)
            checksum += sum(
                len(str(row["name"])) + len(str(row["city"])) for row in rows
            )
        after_query = snapshot("after_query")
        force_gc()
        after_materialize = snapshot("after_materialize")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "opencypher_to_list",
        "durations_s": {
            "query_create": query_duration,
            "materialize": materialize_duration,
            "wall_total": query_duration + materialize_duration,
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
        "counts": {"rows": row_count, "checksum": checksum},
    }


def scenario_sql_vector_neighbors_extract_hits(
    args: argparse.Namespace,
) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_vector_extract_")
    populate_vector_db(
        db_path,
        record_count=args.vector_records,
        dimensions=args.vector_dimensions,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query = vector_literal(random_vector(0, args.vector_dimensions))
        sql = (
            "SELECT vectorNeighbors("
            f"'Doc[embedding]', {query}, {int(args.vector_k)}"
            ") as res"
        )
        query_duration = 0.0
        extract_duration = 0.0
        hit_count = 0
        checksum = 0
        for _ in range(args.query_runs):
            query_start = time.perf_counter()
            row = db.query("sql", sql).first()
            query_duration += time.perf_counter() - query_start

            extract_start = time.perf_counter()
            neighbors = row.get("res") if row else []
            ids = [
                value
                for value in (extract_vector_hit_id(hit) for hit in neighbors)
                if value is not None
            ]
            extract_duration += time.perf_counter() - extract_start
            hit_count += len(ids)
            checksum += sum(ids)
        after_query = snapshot("after_query")
        force_gc()
        after_extract = snapshot("after_extract")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_vector_neighbors_extract_hits",
        "durations_s": {
            "query": query_duration,
            "extract_hits": extract_duration,
            "wall_total": query_duration + extract_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_extract, after_close],
        "derived": {
            "rss_extract_hits_delta_bytes": delta(
                after_query, after_extract, "rss_bytes"
            ),
            "python_peak_extract_hits_delta_bytes": delta(
                after_query, after_extract, "python_peak_bytes"
            ),
        },
        "counts": {"hits_seen": hit_count, "checksum": checksum},
    }


def scenario_sql_vector_neighbors_followup_query(
    args: argparse.Namespace,
) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_sql_vector_followup_")
    populate_vector_db(
        db_path,
        record_count=args.vector_records,
        dimensions=args.vector_dimensions,
        heap_size=args.heap_size,
    )
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query = vector_literal(random_vector(0, args.vector_dimensions))
        sql = (
            "SELECT vectorNeighbors("
            f"'Doc[embedding]', {query}, {int(args.vector_k)}"
            ") as res"
        )
        vector_duration = 0.0
        followup_duration = 0.0
        row_count = 0
        checksum = 0
        for _ in range(args.query_runs):
            vector_start = time.perf_counter()
            row = db.query("sql", sql).first()
            vector_duration += time.perf_counter() - vector_start

            neighbors = row.get("res") if row else []
            ids = [
                value
                for value in (extract_vector_hit_id(hit) for hit in neighbors)
                if value is not None
            ]
            if not ids:
                continue

            followup_start = time.perf_counter()
            id_list = ", ".join(str(value) for value in ids)
            followup_rows = db.query(
                "sql",
                (
                    "SELECT id, title, category FROM Doc "
                    f"WHERE id IN [{id_list}] ORDER BY id"
                ),
            ).to_list()
            followup_duration += time.perf_counter() - followup_start
            row_count += len(followup_rows)
            checksum += sum(int(item["id"]) for item in followup_rows)
        after_query = snapshot("after_query")
        force_gc()
        after_followup = snapshot("after_followup")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "sql_vector_neighbors_followup_query",
        "durations_s": {
            "vector_query": vector_duration,
            "followup_query": followup_duration,
            "wall_total": vector_duration + followup_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_query,
            after_followup,
            after_close,
        ],
        "derived": {
            "rss_followup_delta_bytes": delta(after_query, after_followup, "rss_bytes"),
            "python_peak_followup_delta_bytes": delta(
                after_query, after_followup, "python_peak_bytes"
            ),
        },
        "counts": {"rows": row_count, "checksum": checksum},
    }


def scenario_async_query_callback(args: argparse.Namespace) -> dict[str, Any]:
    db_path = make_temp_db_path("arcadedb_profile_async_query_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        executor = db.async_executor()
        after_executor = snapshot("after_executor")
        seen_rows = 0
        checksum = 0

        def on_row(row):
            nonlocal seen_rows, checksum
            seen_rows += 1
            checksum += int(row.get("value"))

        query_text = (
            "SELECT name, value FROM Item WHERE bucket_id < 16 ORDER BY value LIMIT ?"
        )
        enqueue_start = time.perf_counter()
        for _ in range(args.query_runs):
            executor.query("sql", query_text, on_row, args=[args.records])
        enqueue_duration = time.perf_counter() - enqueue_start

        wait_start = time.perf_counter()
        executor.wait_completion()
        wait_duration = time.perf_counter() - wait_start

        force_gc()
        after_callback = snapshot("after_callback")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "async_query_callback",
        "durations_s": {
            "enqueue_queries": enqueue_duration,
            "wait_completion": wait_duration,
            "wall_total": enqueue_duration + wait_duration,
        },
        "snapshots": [
            before_open,
            after_open,
            after_executor,
            after_callback,
            after_close,
        ],
        "derived": {
            "rss_callback_delta_bytes": delta(
                after_executor, after_callback, "rss_bytes"
            ),
            "python_peak_callback_delta_bytes": delta(
                after_executor, after_callback, "python_peak_bytes"
            ),
        },
        "counts": {"rows_seen": seen_rows, "checksum": checksum},
    }


def scenario_export_to_csv(args: argparse.Namespace) -> dict[str, Any]:
    from arcadedb_embedded.exporter import export_to_csv

    db_path = make_temp_db_path("arcadedb_profile_export_")
    populate_items_db(db_path, record_count=args.records, heap_size=args.heap_size)
    csv_path = db_path.parent / "items.csv"
    before_open = snapshot("before_open")
    try:
        db = open_database(db_path, args.heap_size)
        after_open = snapshot("after_open")

        query_duration = 0.0
        export_duration = 0.0
        bytes_written = 0
        for run_index in range(args.query_runs):
            target_path = csv_path.parent / f"items-{run_index:03d}.csv"
            query_start = time.perf_counter()
            result = db.query(
                "sql",
                "SELECT name, value, category FROM Item ORDER BY value LIMIT ?",
                args.records,
            )
            query_duration += time.perf_counter() - query_start

            export_start = time.perf_counter()
            export_to_csv(
                result,
                str(target_path),
                fieldnames=["name", "value", "category"],
            )
            export_duration += time.perf_counter() - export_start
            bytes_written += target_path.stat().st_size
        after_query = snapshot("after_query")
        force_gc()
        after_export = snapshot("after_export")
        db.close()
        after_close = snapshot("after_close")
    finally:
        cleanup_temp_db(db_path, args.keep_temp)

    return {
        "scenario": "export_to_csv",
        "durations_s": {
            "query_create": query_duration,
            "export_csv": export_duration,
            "wall_total": query_duration + export_duration,
        },
        "snapshots": [before_open, after_open, after_query, after_export, after_close],
        "derived": {
            "rss_export_delta_bytes": delta(after_query, after_export, "rss_bytes"),
            "python_peak_export_delta_bytes": delta(
                after_query, after_export, "python_peak_bytes"
            ),
        },
        "counts": {"bytes_written": bytes_written},
    }


SCENARIO_FUNCS = {
    "jvm_startup": scenario_jvm_startup,
    "db_lifecycle": scenario_db_lifecycle,
    "sql_projected_lazy_scan": scenario_sql_projected_lazy_scan,
    "sql_projected_to_list": scenario_sql_projected_to_list,
    "sql_full_records_to_list": scenario_sql_full_records_to_list,
    "sql_full_records_to_list_no_convert": scenario_sql_full_records_to_list_no_convert,
    "sql_full_records_wrapper_scan": scenario_sql_full_records_wrapper_scan,
    "sql_full_records_to_list_retained": scenario_sql_full_records_to_list_retained,
    "sql_aggregate_first": scenario_sql_aggregate_first,
    "sql_aggregate_one": scenario_sql_aggregate_one,
    "opencypher_lazy_scan": scenario_opencypher_lazy_scan,
    "opencypher_to_list": scenario_opencypher_to_list,
    "sql_vector_neighbors_extract_hits": scenario_sql_vector_neighbors_extract_hits,
    "sql_vector_neighbors_followup_query": scenario_sql_vector_neighbors_followup_query,
    "async_query_callback": scenario_async_query_callback,
    "export_to_csv": scenario_export_to_csv,
}


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def run_worker(args: argparse.Namespace) -> int:
    tracemalloc.start()
    force_gc()

    scenario = args.worker_scenario
    if scenario not in SCENARIO_FUNCS:
        raise ValueError(f"Unknown worker scenario: {scenario}")

    result = SCENARIO_FUNCS[scenario](args)
    print(WORKER_JSON_MARKER + json.dumps(result, default=json_default))
    return 0


def build_worker_command(args: argparse.Namespace, scenario: str) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-scenario",
        scenario,
        "--runs",
        "1",
        "--records",
        str(args.records),
        "--person-count",
        str(args.person_count),
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
        "--chunk-size",
        str(args.chunk_size),
        "--heap-size",
        args.heap_size,
    ]
    if args.keep_temp:
        command.append("--keep-temp")
    return command


def summarize_numeric(values: list[float | int | None]) -> dict[str, float | None]:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return {"min": None, "mean": None, "median": None, "max": None}
    return {
        "min": min(filtered),
        "mean": statistics.fmean(filtered),
        "median": statistics.median(filtered),
        "max": max(filtered),
    }


def percentile(sorted_values: list[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def aggregate_runs(scenario: str, run_results: list[dict[str, Any]]) -> dict[str, Any]:
    wall_values = [
        result.get("durations_s", {}).get("wall_total") for result in run_results
    ]
    sorted_wall = sorted(float(value) for value in wall_values if value is not None)
    return {
        "scenario": scenario,
        "runs": run_results,
        "wall_summary_s": summarize_numeric(wall_values),
        "wall_p95_s": percentile(sorted_wall, 0.95),
        "wall_p99_s": percentile(sorted_wall, 0.99),
    }


def worker_overhead_seconds(run_result: dict[str, Any]) -> float | None:
    worker_wall = run_result.get("worker_wall_s")
    scenario_wall = run_result.get("durations_s", {}).get("wall_total")
    if worker_wall is None or scenario_wall is None:
        return None
    return float(worker_wall) - float(scenario_wall)


def extract_worker_payload(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.startswith(WORKER_JSON_MARKER):
            return json.loads(line[len(WORKER_JSON_MARKER) :])
    raise RuntimeError("Worker did not emit JSON payload")


def format_bytes(value: float | None) -> str:
    if value is None:
        return "n/a"
    units = ["B", "KiB", "MiB", "GiB"]
    size = float(value)
    unit = units[0]
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            break
        size /= 1024.0
    return f"{size:.2f} {unit}"


def print_summary(report: dict[str, Any]) -> None:
    print("\nSummary")
    print("=======")
    for scenario_report in report["scenario_reports"]:
        wall = scenario_report["wall_summary_s"]
        overhead_values = [
            worker_overhead_seconds(run) for run in scenario_report["runs"]
        ]
        overhead = summarize_numeric(overhead_values)
        sample_run = scenario_report["runs"][0]
        derived = sample_run.get("derived", {})
        peak_keys = [key for key in derived if key.startswith("python_peak_")]
        peak_text = "n/a"
        if peak_keys:
            peak_text = format_bytes(derived[peak_keys[0]])

        print(f"- {scenario_report['scenario']}")
        print(
            (
                f"  wall mean={wall['mean']:.4f}s "
                f"median={wall['median']:.4f}s "
                f"p95={scenario_report['wall_p95_s']:.4f}s"
            )
            if wall["mean"] is not None and scenario_report["wall_p95_s"] is not None
            else "  wall=n/a"
        )
        print(
            (
                f"  worker overhead mean={overhead['mean']:.4f}s "
                f"peak python delta={peak_text}"
            )
            if overhead["mean"] is not None
            else f"  peak python delta={peak_text}"
        )


def run_parent(args: argparse.Namespace) -> int:
    scenarios = resolve_scenarios(args)
    scenario_reports: list[dict[str, Any]] = []

    for scenario in scenarios:
        run_results: list[dict[str, Any]] = []
        for run_index in range(args.runs):
            print(
                (
                    f"[profile] scenario={scenario} "
                    f"run={run_index + 1}/{args.runs} starting"
                )
            )
            command = build_worker_command(args, scenario)
            start = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=str(BINDINGS_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            worker_wall = time.perf_counter() - start
            if completed.returncode != 0:
                sys.stderr.write(completed.stdout)
                sys.stderr.write(completed.stderr)
                raise RuntimeError(
                    (
                        f"Worker failed for scenario {scenario!r} "
                        f"with code {completed.returncode}"
                    )
                )

            payload = extract_worker_payload(completed.stdout)
            payload["worker_wall_s"] = worker_wall
            run_results.append(payload)
            print(
                (
                    f"[profile] scenario={scenario} "
                    f"run={run_index + 1}/{args.runs} done "
                    f"wall={payload['durations_s']['wall_total']:.4f}s"
                )
            )

        scenario_reports.append(aggregate_runs(scenario, run_results))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "scenarios": scenarios,
            "runs": args.runs,
            "records": args.records,
            "person_count": args.person_count,
            "graph_degree": args.graph_degree,
            "vector_records": args.vector_records,
            "vector_dimensions": args.vector_dimensions,
            "vector_k": args.vector_k,
            "query_runs": args.query_runs,
            "chunk_size": args.chunk_size,
            "heap_size": args.heap_size,
        },
        "scenario_reports": scenario_reports,
    }

    output_path = (
        Path(args.output_json)
        if args.output_json
        else PROFILE_DIR
        / f"profile-report-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    )
    output_path.write_text(
        json.dumps(report, indent=2, default=json_default),
        encoding="utf-8",
    )

    print_summary(report)
    print(f"\nWrote report to {output_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    if args.records < 1:
        raise ValueError("--records must be at least 1")
    if args.person_count < 2:
        raise ValueError("--person-count must be at least 2")
    if args.graph_degree < 1:
        raise ValueError("--graph-degree must be at least 1")
    if args.vector_records < 1:
        raise ValueError("--vector-records must be at least 1")
    if args.vector_dimensions < 2:
        raise ValueError("--vector-dimensions must be at least 2")
    if args.vector_k < 1:
        raise ValueError("--vector-k must be at least 1")
    if args.query_runs < 1:
        raise ValueError("--query-runs must be at least 1")

    if args.worker_scenario:
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
