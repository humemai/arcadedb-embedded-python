#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep09"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Edit INPUT_DIR, OUTPUT_DIR, DATASET, and LABEL_PREFIX in this file instead." >&2
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Input directory not found: $INPUT_DIR" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

DATASET_TAG="${DATASET//-/_}"
if [[ -z "${DATASET_TAG// /}" ]]; then
    DATASET_TAG="all_datasets"
fi
SUMMARY_MD="$OUTPUT_DIR/summary_09_graph_oltp_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" "$SCRIPT_DIR" << 'PY'
import glob
import json
import os
import sys
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix, script_dir = sys.argv[1:]
sys.path.insert(0, script_dir)

from _summary_helpers import normalize_db_label, normalize_run_label, normalized_run_key

dataset_filter = dataset.strip()
dataset_label = dataset_filter or "all"

dataset_slug = dataset_filter.replace("-", "_")
dir_pattern = f"{dataset_slug}_graph_oltp_*" if dataset_filter else "*_graph_oltp_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))


def to_int(value):
    try:
        return int(value)
    except Exception:
        return None


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def bytes_to_mib(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue / (1024.0 ** 2)


def kib_to_mib(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue / 1024.0


def seconds_to_ms(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue * 1000.0


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    return str(value)


def resolve_db_label(data, status_for_run):
    status_db = status_for_run.get("db") if isinstance(status_for_run, dict) else None
    if isinstance(status_db, str) and status_db.strip():
        return normalize_db_label(status_db.strip())

    return normalize_db_label(data.get("db"))

def add_version(version_sets, key, value):
    if key in (None, "", "collected_at_utc"):
        return
    if value in (None, ""):
        return
    version_sets.setdefault(str(key), set()).add(str(value))

def collect_version_metadata(version_sets, data, run_dir):
    add_version(version_sets, "sqlite_version", data.get("sqlite_version"))

    wheel_meta = data.get("arcadedb_wheel_metadata")
    if isinstance(wheel_meta, dict):
        for key, value in wheel_meta.items():
            add_version(version_sets, key, value)

    runtime_versions = data.get("runtime_versions")
    if not isinstance(runtime_versions, dict):
        env_obj = data.get("environment")
        if isinstance(env_obj, dict):
            runtime_versions = env_obj.get("runtime_versions")
    if isinstance(runtime_versions, dict):
        for key, value in runtime_versions.items():
            add_version(version_sets, key, value)

    dep_path = os.path.join(run_dir, "dependency_versions.json")
    if os.path.isfile(dep_path):
        try:
            with open(dep_path, "r", encoding="utf-8") as f:
                dep_data = json.load(f)
            if isinstance(dep_data, dict):
                for key, value in dep_data.items():
                    add_version(version_sets, key, value)
        except Exception:
            pass

    wheel_path = os.path.join(run_dir, "arcadedb_wheel_build.json")
    if os.path.isfile(wheel_path):
        try:
            with open(wheel_path, "r", encoding="utf-8") as f:
                wheel_data = json.load(f)
            if isinstance(wheel_data, dict):
                for key, value in wheel_data.items():
                    add_version(version_sets, key, value)
        except Exception:
            pass

def format_version_summary_lines(version_sets, max_values=3):
    out = []
    for key in sorted(version_sets.keys()):
        if key == "sqlite" and (version_sets.get("sqlite_version") or set()):
            continue
        values = sorted(version_sets.get(key) or [])
        if len(values) > 1 and "auto" in values:
            values = [value for value in values if value != "auto"]
        if not values:
            continue
        shown = ", ".join(values[:max_values])
        extra = len(values) - max_values
        if extra > 0:
            shown += f", ... (+{extra} more)"
        out.append(f"{key}: {shown}")
    return out

def ensure_versions_for_db_set(version_sets, db_values):
    expected = set()
    db_values = {str(v or "").strip() for v in db_values}
    if any(v in db_values for v in ("arcadedb", "arcadedb_sql", "arcadedb_cypher")):
        expected.add("arcadedb_embedded")
    if any(v in db_values for v in ("ladybug", "ladybugdb")):
        expected.add("real_ladybug")
    if "graphqlite" in db_values:
        expected.add("graphqlite")
    if "duckdb" in db_values:
        expected.add("duckdb")
    if "sqlite" in db_values:
        expected.add("sqlite")
    if "python_memory" in db_values:
        expected.add("python_memory")
    for key in expected:
        if key not in version_sets or not version_sets[key]:
            version_sets[key] = {"unknown"}


status_rows = []
status_by_run = {}
rows = []
op_rows = []
scope_notes = set()
version_sets = {}

for run_dir in run_dirs:
    status_path = os.path.join(run_dir, "run_status.json")
    status = None
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            status = None

    if status is not None:
        normalized_status_label = normalize_run_label(
            status.get("run_label"),
            mem_limit=status.get("mem_limit"),
            run_dir=run_dir,
        )
        if normalized_status_label:
            status["run_label"] = normalized_status_label
        status_rows.append(status)
        run_key = normalized_run_key(
            status.get("run_label"),
            mem_limit=status.get("mem_limit"),
            run_dir=run_dir,
        )
        if run_key[0]:
            status_by_run[run_key] = status

    result_paths = sorted(glob.glob(os.path.join(run_dir, "results_*.json")))
    if not result_paths:
        continue

    du_path = os.path.join(run_dir, "disk_usage_du.json")
    du_mib = None
    if os.path.isfile(du_path):
        try:
            with open(du_path, "r", encoding="utf-8") as f:
                du_mib = bytes_to_mib((json.load(f) or {}).get("du_bytes"))
        except Exception:
            du_mib = None

    for result_path in result_paths:
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        result_dataset = data.get("dataset")
        run_label = data.get("run_label")
        if dataset_filter and result_dataset != dataset_filter:
            continue
        if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
            continue

        normalized_run_label = normalize_run_label(
            run_label,
            mem_limit=data.get("mem_limit"),
            run_dir=run_dir,
        )
        run_key = normalized_run_key(
            run_label,
            mem_limit=data.get("mem_limit"),
            run_dir=run_dir,
        )

        collect_version_metadata(version_sets, data, run_dir)

        status_for_run = status_by_run.get(run_key, {})
        latency_overall = (data.get("latency_summary") or {}).get("overall") or {}
        latency_ops = (data.get("latency_summary") or {}).get("ops") or {}
        op_counts = data.get("op_counts") or {}
        load_stats = data.get("load_stats") or {}
        index_stats = (load_stats.get("indexes") or {}) if isinstance(load_stats, dict) else {}
        index_time_s = to_float(index_stats.get("id_unique"))

        scope_note = data.get("benchmark_scope_note")
        if scope_note:
            scope_notes.add(str(scope_note))

        row = {
            "dataset": data.get("dataset"),
            "db": resolve_db_label(data, status_for_run),
            "run_label": normalized_run_label,
            "seed": to_int(data.get("seed")) or to_int(status_for_run.get("seed")),
            "threads": to_int(data.get("threads")) or to_int(status_for_run.get("threads")),
            "transactions": to_int(data.get("transactions")) or to_int(status_for_run.get("transactions")),
            "batch_size": to_int(data.get("batch_size")) or to_int(status_for_run.get("batch_size")),
            "mem_limit": data.get("mem_limit"),
            "load_node_count": to_int(data.get("load_node_count")),
            "load_edge_count": to_int(data.get("load_edge_count")),
            "schema_time_s": to_float(data.get("schema_time_s")),
            "index_time_s": index_time_s,
            "load_time_s": to_float(data.get("load_time_s")),
            "counts_time_s": to_float(data.get("counts_time_s")),
            "oltp_crud_time_s": to_float(data.get("total_time_s")),
            "throughput_s": to_float(data.get("throughput_ops_s")),
            "p95_ms": seconds_to_ms(latency_overall.get("95") or latency_overall.get(95)),
            "rss_peak_mib": kib_to_mib(data.get("rss_peak_kb")),
            "du_mib": du_mib,
            "latency_ops": latency_ops,
            "op_counts": op_counts,
        }
        rows.append(row)

        total_time = row.get("oltp_crud_time_s")
        op_order = ["read", "update", "insert", "delete"]
        for op in op_order:
            op_summary = latency_ops.get(op) or {}
            count = to_int(op_counts.get(op))
            throughput = None
            if count is not None and total_time and total_time > 0:
                throughput = count / total_time

            op_rows.append(
                {
                    "dataset": row.get("dataset"),
                    "db": row.get("db"),
                    "run_label": row.get("run_label"),
                    "op": op,
                    "count": count,
                    "throughput_s": throughput,
                    "p50_ms": seconds_to_ms(op_summary.get("50") or op_summary.get(50)),
                    "p95_ms": seconds_to_ms(op_summary.get("95") or op_summary.get(95)),
                    "p99_ms": seconds_to_ms(op_summary.get("99") or op_summary.get(99)),
                }
            )

if not rows:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

rows.sort(
    key=lambda r: (
        str(r.get("dataset")),
        str(r.get("db")),
        str(r.get("run_label")),
    )
)
op_rows.sort(
    key=lambda r: (
        str(r.get("dataset")),
        str(r.get("db")),
        str(r.get("run_label")),
        str(r.get("op")),
    )
)

status_scoped = []
for status in status_rows:
    ds = status.get("dataset")
    rl = status.get("run_label")
    if dataset_filter and ds != dataset_filter:
        continue
    if label_prefix and (not rl or not str(rl).startswith(label_prefix)):
        continue
    status_scoped.append(status)

status_total = len(status_scoped)
status_success = sum(1 for s in status_scoped if s.get("status") == "success")
status_failed = sum(1 for s in status_scoped if s.get("status") == "failed")

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")
generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ensure_versions_for_db_set(version_sets, {row.get("db") for row in rows})
version_summary_lines = format_version_summary_lines(version_sets)

COLUMNS = [
    "db",
    "run_label",
    "seed",
    "threads",
    "transactions",
    "batch_size",
    "mem_limit",
    "load_node_count",
    "load_edge_count",
    "schema_time_s",
    "index_time_s",
    "load_time_s",
    "counts_time_s",
    "oltp_crud_time_s",
    "throughput_s",
    "p95_ms",
    "rss_peak_mib",
    "du_mib",
]

OP_COLUMNS = [
    "db",
    "run_label",
    "op",
    "count",
    "throughput_s",
    "p50_ms",
    "p95_ms",
    "p99_ms",
]

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 09 Graph OLTP Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(rows)}")
if version_summary_lines:
    lines.append("- Versions/digest observed:")
    for item in version_summary_lines:
        lines.append(f"  - {item}")
if status_total > 0:
    lines.append(f"- Run status files: total={status_total}, success={status_success}, failed={status_failed}")
lines.append("- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.")
lines.append("- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.")
if scope_notes:
    for note in sorted(scope_notes):
        lines.append(f"- Scope note: {note}")
lines.append("")

datasets = sorted({str(row.get("dataset") or "") for row in rows})
for current_dataset in datasets:
    lines.append(f"## Dataset: {current_dataset}")
    lines.append("")
    lines.append("| " + " | ".join(COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(COLUMNS)) + "|")
    for row in rows:
        if str(row.get("dataset") or "") != current_dataset:
            continue
        values = [fmt(row.get(column)) for column in COLUMNS]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")

    lines.append("### Per-operation OLTP details")
    lines.append("")
    lines.append("| " + " | ".join(OP_COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(OP_COLUMNS)) + "|")
    for row in op_rows:
        if str(row.get("dataset") or "") != current_dataset:
            continue
        values = [fmt(row.get(column)) for column in OP_COLUMNS]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
