#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ExampleRun:
    number: int
    script_name: str
    args_factory: Callable[[Path, bool], list[str]]
    note: str = ""


def parse_selection(value: str | None) -> set[int] | None:
    if not value:
        return None

    selected: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(token))
    return selected


def find_example11_output(
    db_root: Path,
    dataset: str,
    run_label: str,
    *,
    allow_missing: bool = False,
) -> Path:
    pattern = f"backend=arcadedb_sql_dataset={dataset}_*" f"_run={run_label}"
    matches = sorted(
        (path for path in db_root.glob(pattern) if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        if allow_missing:
            return db_root / (
                f"backend=arcadedb_sql_dataset={dataset}_placeholder"
                f"_run={run_label}"
            )
        raise FileNotFoundError(
            f"Could not find Example 11 output under {db_root} matching {pattern}"
        )
    return matches[0]


def build_examples(_examples_dir: Path) -> list[ExampleRun]:
    small_graph_db = Path("my_test_databases") / "movielens_graph_small_db"
    vector_db_root = Path("my_test_databases") / "example11_minimal"
    table_work_dir = Path("my_test_databases") / "example15_minimal"
    graph_work_dir = Path("my_test_databases") / "example16_minimal"
    example11_run_label = "minimal"

    return [
        ExampleRun(1, "01_simple_document_store.py", lambda _, __: []),
        ExampleRun(2, "02_social_network_graph.py", lambda _, __: []),
        ExampleRun(3, "03_vector_search.py", lambda _, __: []),
        ExampleRun(
            4,
            "04_csv_import_documents.py",
            lambda _, __: [
                "--dataset",
                "movielens-small",
            ],
        ),
        ExampleRun(
            5,
            "05_csv_import_graph.py",
            lambda _, __: [
                "--dataset",
                "movielens-small",
                "--method",
                "sql",
                "--no-async",
                "--export",
            ],
        ),
        ExampleRun(
            6,
            "06_vector_search_recommendations.py",
            lambda _, __: [
                "--source-db",
                str(small_graph_db),
                "--db-path",
                "my_test_databases/movielens_graph_small_db_vectors",
                "--import-jsonl",
                "exports/movielens_graph_small_db.jsonl.tgz",
                "--heap-size",
                "1g",
            ],
            note="May download embedding model assets on first run.",
        ),
        ExampleRun(
            7,
            "07_stackoverflow_tables_oltp.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--threads",
                "1",
                "--transactions",
                "50",
            ],
        ),
        ExampleRun(
            8,
            "08_stackoverflow_tables_olap.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--threads",
                "1",
                "--query-runs",
                "1",
            ],
        ),
        ExampleRun(
            9,
            "09_stackoverflow_graph_oltp.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--threads",
                "1",
                "--transactions",
                "50",
            ],
        ),
        ExampleRun(
            10,
            "10_stackoverflow_graph_olap.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--threads",
                "1",
                "--query-runs",
                "1",
            ],
        ),
        ExampleRun(
            11,
            "11_vector_index_build.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--threads",
                "1",
                "--batch-size",
                "500",
                "--db-root",
                str(vector_db_root),
                "--run-label",
                example11_run_label,
            ],
        ),
        ExampleRun(
            12,
            "12_vector_search.py",
            lambda _, dry_run: [
                "--dataset",
                "stackoverflow-tiny",
                "--db-path",
                str(
                    find_example11_output(
                        vector_db_root,
                        "stackoverflow-tiny",
                        example11_run_label,
                        allow_missing=dry_run,
                    )
                ),
                "--threads",
                "1",
                "--query-limit",
                "10",
                "--k",
                "10",
                "--query-runs",
                "1",
            ],
        ),
        ExampleRun(
            13,
            "13_stackoverflow_hybrid_queries.py",
            lambda _, __: [
                "--dataset",
                "stackoverflow-tiny",
                "--batch-size",
                "1000",
                "--encode-batch-size",
                "16",
                "--top-k",
                "3",
                "--candidate-limit",
                "20",
                "--infer-sample-limit",
                "1000",
            ],
            note="May download sentence-transformer model assets on first run.",
        ),
        ExampleRun(
            14,
            "14_lifecycle_timing.py",
            lambda _, __: [
                "--runs",
                "1",
                "--table-records",
                "50",
                "--graph-vertices",
                "10",
                "--vector-records",
                "10",
                "--query-runs",
                "5",
            ],
        ),
        ExampleRun(
            15,
            "15_import_database_vs_transactional_table_ingest.py",
            lambda _, __: [
                "--rows-per-table",
                "20",
                "--tables",
                "2",
                "--columns",
                "4",
                "--string-size",
                "8",
                "--batch-size",
                "10",
                "--parallel",
                "1",
                "--async-parallel",
                "1",
                "--import-chunk-rows",
                "20",
                "--work-dir",
                str(table_work_dir),
            ],
        ),
        ExampleRun(
            16,
            "16_import_database_vs_transactional_graph_ingest.py",
            lambda _, __: [
                "--vertices",
                "10",
                "--edges",
                "15",
                "--vertex-int-props",
                "1",
                "--vertex-str-props",
                "1",
                "--edge-int-props",
                "1",
                "--edge-str-props",
                "1",
                "--string-size",
                "8",
                "--batch-size",
                "10",
                "--parallel",
                "1",
                "--async-parallel",
                "1",
                "--work-dir",
                str(graph_work_dir),
            ],
        ),
        ExampleRun(
            17,
            "17_timeseries_end_to_end.py",
            lambda _, __: [
                "--hours",
                "2",
                "--interval-minutes",
                "10",
            ],
        ),
        ExampleRun(19, "19_hash_index_exact_match.py", lambda _, __: []),
    ]


def run_command(command: list[str], cwd: Path, dry_run: bool) -> int:
    rendered = " ".join(shlex.quote(part) for part in command)
    print(f"$ {rendered}")
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run examples 01-19 with small inputs for quicker smoke coverage."
    )
    parser.add_argument(
        "--only",
        help="Comma-separated example numbers or ranges to run, e.g. 1,4-6,11-12",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Do not bootstrap example datasets before running.",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    examples_dir = script_path.parents[1]
    selected = parse_selection(args.only)

    examples = [
        example
        for example in build_examples(examples_dir)
        if selected is None or example.number in selected
    ]
    if not examples:
        print("No examples selected.", file=sys.stderr)
        return 2

    bootstrap_commands: list[list[str]] = []
    if not args.skip_download:
        bootstrap_commands = [
            [sys.executable, "download_data.py", "movielens-small"],
            [sys.executable, "download_data.py", "stackoverflow-tiny"],
        ]

    print(f"Examples directory: {examples_dir}")
    print(f"Python executable: {sys.executable}")
    print()

    for command in bootstrap_commands:
        code = run_command(command, examples_dir, args.dry_run)
        if code != 0:
            return code

    failures: list[int] = []
    for example in examples:
        print(f"=== Example {example.number:02d}: {example.script_name} ===")
        if example.note:
            print(f"NOTE: {example.note}")
        command = [
            sys.executable,
            example.script_name,
            *example.args_factory(examples_dir, args.dry_run),
        ]
        code = run_command(command, examples_dir, args.dry_run)
        if code != 0:
            failures.append(example.number)
            print(f"Example {example.number:02d} failed with exit code {code}.")
            if not args.dry_run:
                break
        print()

    if failures:
        print(
            "Failed examples:",
            ", ".join(f"{number:02d}" for number in failures),
            file=sys.stderr,
        )
        return 1

    print("All selected examples completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
