#!/usr/bin/env python3
"""Internal vector query latency probe for ArcadeDB server-mode HTTP.

This script is intentionally internal-only. It starts ArcadeDB server mode over
an existing database root, samples one stored vector from the target document
type, and measures round-trip latency for Luca-style vectorNeighbors SQL over
HTTP.

Default behavior times both query shapes:

1. Raw wrapper:
   SELECT vectorNeighbors('VectorData[vector]', [...], k, ef_search) AS res

2. Expanded rows:
   SELECT @rid, distance FROM (
     SELECT expand(vectorNeighbors('VectorData[vector]', [...], k, ef_search))
   )

The probe can also optionally run the same SQL through the embedded binding for
side-by-side comparison.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import arcadedb_embedded as arcadedb


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Internal ArcadeDB vector latency probe over HTTP"
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to an existing ArcadeDB database directory",
    )
    parser.add_argument(
        "--db-name",
        default=None,
        help="Database name override (default: basename of --db-path)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=2481,
        help="HTTP port for the embedded server (default: 2481)",
    )
    parser.add_argument(
        "--root-password",
        default="internal-vector-probe",
        help="Root password for the temporary local server session",
    )
    parser.add_argument(
        "--type-name",
        default="VectorData",
        help="Document type containing vectors (default: VectorData)",
    )
    parser.add_argument(
        "--vector-field",
        default="vector",
        help="Vector property name (default: vector)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=100,
        help="Nearest-neighbor count (default: 100)",
    )
    parser.add_argument(
        "--ef-search",
        type=int,
        default=100,
        help="ef_search parameter (default: 100)",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=5,
        help="Number of warmup queries per SQL form (default: 5)",
    )
    parser.add_argument(
        "--measure-runs",
        type=int,
        default=30,
        help="Number of measured queries per SQL form (default: 30)",
    )
    parser.add_argument(
        "--sample-pool",
        type=int,
        default=32,
        help="Fetch up to this many vectors, then choose one locally (default: 32)",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Seed for choosing the sample vector from the fetched pool",
    )
    parser.add_argument(
        "--sql-form",
        choices=["raw", "expand", "both"],
        default="both",
        help="Which SQL form to measure (default: both)",
    )
    parser.add_argument(
        "--compare-embedded",
        action="store_true",
        help="Also run the same SQL via embedded access for comparison",
    )
    parser.add_argument(
        "--heap-size",
        default=None,
        help="Optional JVM heap size for the embedded server, e.g. 8g",
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


@contextmanager
def prepare_server_root(
    db_path: Path,
    db_name_override: str | None = None,
):
    db_name = db_name_override or db_path.name

    if db_path.parent.name == "databases":
        yield db_path.parent.parent, db_name, False
        return

    with tempfile.TemporaryDirectory(prefix="arcadedb-server-root-") as tmp_dir:
        wrapper_root = Path(tmp_dir)
        databases_dir = wrapper_root / "databases"
        databases_dir.mkdir(parents=True, exist_ok=True)
        os.symlink(
            str(db_path),
            str(databases_dir / db_name),
            target_is_directory=True,
        )
        yield wrapper_root, db_name, True


def basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def bearer_auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def http_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed for {method} {url}: {exc}") from exc

    if not body.strip():
        return {}

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON from {url}, got: {body}") from exc


def wait_for_server(base_url: str, headers: dict[str, str], timeout_sec: float) -> None:
    start = time.perf_counter()
    while True:
        try:
            http_json_request(
                f"{base_url}/api/v1/server",
                headers=headers,
                timeout=5.0,
            )
            return
        except RuntimeError:
            if time.perf_counter() - start > timeout_sec:
                raise
            time.sleep(0.25)


def to_float_list(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        value = json.loads(value)
    require(value is not None, "Sampled vector is null")
    try:
        return [float(item) for item in value]
    except TypeError as exc:
        raise SystemExit(f"Sampled vector is not iterable: {type(value)!r}") from exc


def vector_literal(vector: list[float]) -> str:
    return "[" + ", ".join(f"{item:.7g}" for item in vector) + "]"


def build_sql(
    index_name: str,
    qvec_literal: str,
    k: int,
    ef_search: int,
    form: str,
) -> str:
    if form == "raw":
        return (
            "SELECT vectorNeighbors("
            f"'{index_name}', {qvec_literal}, {int(k)}, {int(ef_search)}"
            ") AS res"
        )
    if form == "expand":
        return (
            "SELECT @rid, distance FROM ("
            "SELECT expand(vectorNeighbors("
            f"'{index_name}', {qvec_literal}, {int(k)}, {int(ef_search)}"
            "))"
            ")"
        )
    raise ValueError(f"Unsupported SQL form: {form}")


def sample_query_vector(
    db,
    *,
    type_name: str,
    vector_field: str,
    sample_pool: int,
    sample_seed: int,
) -> list[float]:
    pool_size = max(1, int(sample_pool))
    rows = db.query(
        "sql",
        f"SELECT {vector_field} FROM {type_name} LIMIT {pool_size}",
    ).to_list()
    require(rows, f"No rows found in {type_name}")
    rng = random.Random(sample_seed)
    row = rows[rng.randrange(len(rows))]
    return to_float_list(row.get(vector_field))


def normalize_jsonish(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_jsonish(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_jsonish(item) for item in value]
    if hasattr(value, "items"):
        try:
            return {str(key): normalize_jsonish(inner) for key, inner in value.items()}
        except (AttributeError, TypeError, ValueError):
            pass
    if hasattr(value, "to_map"):
        try:
            return normalize_jsonish(value.to_map())
        except (AttributeError, TypeError, ValueError):
            pass
    if hasattr(value, "tolist"):
        try:
            return normalize_jsonish(value.tolist())
        except (AttributeError, TypeError, ValueError):
            pass
    return value


def stable_result_hash(payload: Any) -> str:
    normalized = normalize_jsonish(payload)
    blob = json.dumps(normalized, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def summarize_timings(latencies_ms: list[float]) -> dict[str, float]:
    sorted_vals = sorted(latencies_ms)
    require(sorted_vals, "No latency samples collected")

    def percentile(p: float) -> float:
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        pos = (len(sorted_vals) - 1) * p
        lower = int(pos)
        upper = min(lower + 1, len(sorted_vals) - 1)
        weight = pos - lower
        return sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight

    return {
        "min_ms": sorted_vals[0],
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "mean_ms": mean(sorted_vals),
        "max_ms": sorted_vals[-1],
    }


def run_http_probe(
    *,
    base_url: str,
    db_name: str,
    bearer_headers: dict[str, str],
    sql: str,
    warmup_runs: int,
    measure_runs: int,
) -> dict[str, Any]:
    payload = {"language": "sql", "command": sql}
    latencies_ms: list[float] = []
    result_hashes: list[str] = []
    row_counts: list[int] = []

    for _ in range(max(0, warmup_runs)):
        http_json_request(
            f"{base_url}/api/v1/query/{db_name}",
            method="POST",
            payload=payload,
            headers=bearer_headers,
            timeout=60.0,
        )

    for _ in range(max(1, measure_runs)):
        start = time.perf_counter()
        response = http_json_request(
            f"{base_url}/api/v1/query/{db_name}",
            method="POST",
            payload=payload,
            headers=bearer_headers,
            timeout=60.0,
        )
        latencies_ms.append((time.perf_counter() - start) * 1000.0)

        rows = response.get("result", [])
        row_counts.append(len(rows) if isinstance(rows, list) else 0)
        result_hashes.append(stable_result_hash(rows))

    return {
        **summarize_timings(latencies_ms),
        "runs": len(latencies_ms),
        "row_count": row_counts[0] if row_counts else 0,
        "row_count_stable": len(set(row_counts)) == 1,
        "result_hash": result_hashes[0] if result_hashes else None,
        "result_hash_stable": len(set(result_hashes)) == 1,
    }


def run_embedded_probe(
    *,
    db,
    sql: str,
    warmup_runs: int,
    measure_runs: int,
    form: str,
) -> dict[str, Any]:
    latencies_ms: list[float] = []
    result_hashes: list[str] = []
    row_counts: list[int] = []

    def fetch_rows() -> list[dict[str, Any]]:
        result_set = db.query("sql", sql)
        if form == "raw":
            first_row = result_set.first()
            return [first_row] if first_row is not None else []
        return result_set.to_list()

    for _ in range(max(0, warmup_runs)):
        fetch_rows()

    for _ in range(max(1, measure_runs)):
        start = time.perf_counter()
        rows = fetch_rows()
        latencies_ms.append((time.perf_counter() - start) * 1000.0)
        row_counts.append(len(rows))
        result_hashes.append(stable_result_hash(rows))

    return {
        **summarize_timings(latencies_ms),
        "runs": len(latencies_ms),
        "row_count": row_counts[0] if row_counts else 0,
        "row_count_stable": len(set(row_counts)) == 1,
        "result_hash": result_hashes[0] if result_hashes else None,
        "result_hash_stable": len(set(result_hashes)) == 1,
    }


def print_summary(label: str, summary: dict[str, Any]) -> None:
    print(f"[{label}]")
    print(f"  runs:              {summary['runs']}")
    print(f"  row_count:         {summary['row_count']}")
    print(f"  min_ms:            {summary['min_ms']:.3f}")
    print(f"  p50_ms:            {summary['p50_ms']:.3f}")
    print(f"  p95_ms:            {summary['p95_ms']:.3f}")
    print(f"  mean_ms:           {summary['mean_ms']:.3f}")
    print(f"  max_ms:            {summary['max_ms']:.3f}")
    print(f"  row_count_stable:  {summary['row_count_stable']}")
    print(f"  result_hash_stable:{summary['result_hash_stable']}")
    print(f"  result_hash:       {summary['result_hash']}")
    print()


def main() -> int:
    args = parse_args()

    db_path = Path(args.db_path).resolve()
    require(db_path.is_dir(), f"Database path not found or not a directory: {db_path}")
    index_name = f"{args.type_name}[{args.vector_field}]"
    base_url = f"http://{args.host}:{args.http_port}"

    sql_forms = [args.sql_form] if args.sql_form != "both" else ["raw", "expand"]

    with prepare_server_root(db_path, args.db_name) as (
        server_root,
        db_name,
        using_wrapper_root,
    ):
        server_kwargs: dict[str, Any] = {
            "root_path": str(server_root),
            "root_password": args.root_password,
            "config": {
                "host": args.host,
                "http_port": args.http_port,
                "mode": "development",
            },
        }
        if args.heap_size:
            server_kwargs["jvm_kwargs"] = {"heap_size": args.heap_size}

        print("=" * 72)
        print("ArcadeDB internal vector latency probe")
        print("=" * 72)
        print(f"db_path:       {db_path}")
        print(f"server_root:   {server_root}")
        print(f"db_name:       {db_name}")
        print(f"wrapper_root:  {using_wrapper_root}")
        print(f"index_name:    {index_name}")
        print(f"base_url:      {base_url}")
        print(f"k:             {args.k}")
        print(f"ef_search:     {args.ef_search}")
        print(f"warmup_runs:   {args.warmup_runs}")
        print(f"measure_runs:  {args.measure_runs}")
        print()

        with arcadedb.ArcadeDBServer(**server_kwargs) as server:
            basic_headers = basic_auth_header("root", args.root_password)
            wait_for_server(base_url, basic_headers, timeout_sec=20.0)

            login_payload = http_json_request(
                f"{base_url}/api/v1/login",
                method="POST",
                headers=basic_headers,
            )
            token = login_payload.get("token")
            require(bool(token), "Expected bearer token from /api/v1/login")
            bearer_headers = bearer_auth_header(str(token))

            db = server.get_database(db_name)
            try:
                query_vector = sample_query_vector(
                    db,
                    type_name=args.type_name,
                    vector_field=args.vector_field,
                    sample_pool=args.sample_pool,
                    sample_seed=args.sample_seed,
                )
                qvec_literal = vector_literal(query_vector)
                print(
                    f"sampled_vector_dims: {len(query_vector)} "
                    f"(from up to {max(1, args.sample_pool)} rows)"
                )
                print()

                for form in sql_forms:
                    sql = build_sql(
                        index_name,
                        qvec_literal,
                        args.k,
                        args.ef_search,
                        form,
                    )
                    print(f"SQL form: {form}")
                    print(sql)
                    print()

                    http_summary = run_http_probe(
                        base_url=base_url,
                        db_name=db_name,
                        bearer_headers=bearer_headers,
                        sql=sql,
                        warmup_runs=args.warmup_runs,
                        measure_runs=args.measure_runs,
                    )
                    print_summary(f"http:{form}", http_summary)

                    if args.compare_embedded:
                        embedded_summary = run_embedded_probe(
                            db=db,
                            sql=sql,
                            warmup_runs=args.warmup_runs,
                            measure_runs=args.measure_runs,
                            form=form,
                        )
                        print_summary(f"embedded:{form}", embedded_summary)
            finally:
                db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
