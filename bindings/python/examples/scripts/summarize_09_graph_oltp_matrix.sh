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

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import sys
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix = sys.argv[1:]
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
        return status_db.strip()

    return data.get("db")


status_rows = []
status_by_run = {}
rows = []
op_rows = []
scope_notes = set()

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
        status_rows.append(status)
        run_label = status.get("run_label")
        if run_label:
            status_by_run[str(run_label)] = status

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

        status_for_run = status_by_run.get(str(run_label) if run_label else "", {})
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
            "run_label": run_label,
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
