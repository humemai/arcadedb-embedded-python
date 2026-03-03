#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep07"

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
SUMMARY_MD="$OUTPUT_DIR/summary_07_tables_oltp_${DATASET_TAG}.md"

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
dir_pattern = f"{dataset_slug}_tables_oltp_*" if dataset_filter else "*_tables_oltp_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))
result_files = []
for run_dir in run_dirs:
    result_files.extend(sorted(glob.glob(os.path.join(run_dir, "results_*.json"))))

def format_value(value):
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if value is None:
        return ""
    return str(value)

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

def preload_rows_total(preload_counts):
    if not isinstance(preload_counts, dict):
        return None
    total = 0
    for value in preload_counts.values():
        ivalue = to_int(value)
        if ivalue is None:
            continue
        total += ivalue
    return total

COLUMNS = [
    "db",
    "run_label",
    "seed",
    "threads",
    "transactions",
    "batch_size",
    "mem_limit",
    "preload_rows_total",
    "preload_time_s",
    "index_time_s",
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

rows = []
for result_path in result_files:
    run_dir = os.path.dirname(result_path)
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

    du_path = os.path.join(run_dir, "disk_usage_du.json")
    du_bytes = None
    if os.path.isfile(du_path):
        try:
            with open(du_path, "r", encoding="utf-8") as f:
                du_data = json.load(f)
            du_bytes = du_data.get("du_bytes")
        except Exception:
            pass

    latency_overall = (data.get("latency_summary") or {}).get("overall") or {}
    row = {
        "dataset": data.get("dataset"),
        "db": data.get("db"),
        "run_label": data.get("run_label"),
        "seed": to_int(data.get("seed")),
        "threads": to_int(data.get("threads")),
        "transactions": to_int(data.get("transactions")),
        "batch_size": to_int(data.get("batch_size")),
        "mem_limit": data.get("mem_limit"),
        "preload_rows_total": preload_rows_total(data.get("preload_counts")),
        "preload_time_s": to_float(data.get("preload_time_s")),
        "index_time_s": to_float(data.get("index_time_s")),
        "oltp_crud_time_s": to_float(data.get("total_time_s")),
        "throughput_s": to_float(data.get("throughput_ops_s")),
        "p95_ms": to_float(latency_overall.get("p95_ms")),
        "rss_peak_mib": kib_to_mib(data.get("rss_peak_kb")),
        "du_mib": bytes_to_mib(du_bytes),
        "latency_ops": ((data.get("latency_summary") or {}).get("ops") or {}),
    }
    rows.append(row)

if not rows:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

rows.sort(key=lambda r: (str(r.get("dataset")), str(r.get("db")), str(r.get("run_label"))))

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")

generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 07 Tables OLTP Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(rows)}")
lines.append("- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.")
lines.append("- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.")
lines.append("")
datasets = sorted({str(row.get("dataset") or "") for row in rows})
op_order = ["read", "update", "insert", "delete"]
for current_dataset in datasets:
    lines.append(f"## Dataset: {current_dataset}")
    lines.append("")
    lines.append("| " + " | ".join(COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(COLUMNS)) + "|")
    for row in rows:
        if str(row.get("dataset") or "") != current_dataset:
            continue
        values = [format_value(row.get(column)) for column in COLUMNS]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")

    lines.append("### Per-operation OLTP details")
    lines.append("")
    lines.append("| " + " | ".join(OP_COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(OP_COLUMNS)) + "|")

    for row in rows:
        if str(row.get("dataset") or "") != current_dataset:
            continue

        total_time = to_float(row.get("oltp_crud_time_s"))
        ops = row.get("latency_ops") or {}

        for op in op_order:
            op_summary = ops.get(op) or {}
            count = to_int(op_summary.get("count"))
            throughput = None
            if count is not None and total_time and total_time > 0:
                throughput = count / total_time

            values = [
                format_value(row.get("db")),
                format_value(row.get("run_label")),
                format_value(op),
                format_value(count),
                format_value(throughput),
                format_value(to_float(op_summary.get("p50_ms"))),
                format_value(to_float(op_summary.get("p95_ms"))),
                format_value(to_float(op_summary.get("p99_ms"))),
            ]
            lines.append("| " + " | ".join(values) + " |")

    lines.append("")

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
