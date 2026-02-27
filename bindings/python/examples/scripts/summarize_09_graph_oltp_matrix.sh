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

if [[ -z "${DATASET// /}" ]]; then
    mapfile -t DATASETS < <(
        python3 - "$INPUT_DIR" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import sys

input_dir, label_prefix = sys.argv[1:]
datasets = set()
for path in glob.glob(os.path.join(input_dir, "**", "results_*.json"), recursive=True):
        try:
                with open(path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
        except Exception:
                continue
        run_label = data.get("run_label")
        if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
                continue
        dataset = data.get("dataset")
        if isinstance(dataset, str) and dataset.strip():
                datasets.add(dataset.strip())
for dataset in sorted(datasets):
        print(dataset)
PY
    )

    if [[ "${#DATASETS[@]}" -eq 0 ]]; then
        echo "No datasets discovered for label prefix '$LABEL_PREFIX' in $INPUT_DIR" >&2
        exit 2
    fi

    for dataset in "${DATASETS[@]}"; do
        echo "Summarizing dataset: $dataset"
        DATASET="$dataset" "$0"
    done

    echo
    echo "Summary files generated in: $OUTPUT_DIR"
    exit 0
fi

DATASET_TAG="${DATASET//-/_}"
if [[ -z "${DATASET_TAG// /}" ]]; then
    DATASET_TAG="all"
fi
SUMMARY_JSON="$OUTPUT_DIR/summary_09_graph_oltp_${DATASET_TAG}.json"
SUMMARY_MD="$OUTPUT_DIR/summary_09_graph_oltp_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_JSON" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

input_dir, summary_json, summary_md, dataset, label_prefix = sys.argv[1:]
dataset_filter = dataset.strip()
dataset_label = dataset_filter or "all"


def flatten_dict(obj, prefix=""):
    flat = {}
    if not isinstance(obj, dict):
        return flat
    for key, value in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_dict(value, full_key))
        else:
            flat[full_key] = value
    return flat


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def first_present(data, keys):
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def extract_parameters(data, flat_data):
    params = {
        "dataset": first_present(data, ["dataset"]),
        "db": first_present(data, ["db"]),
        "threads": first_present(data, ["threads"]),
        "transactions": first_present(data, ["transactions"]),
        "batch_size": first_present(data, ["batch_size"]),
        "mem_limit": first_present(data, ["mem_limit", "memory_limit"]),
        "heap_size": first_present(data, ["heap_size"]),
        "arcadedb_version": first_present(data, ["arcadedb_version"]),
        "ladybug_version": first_present(data, ["ladybug_version"]),
        "docker_image": first_present(data, ["docker_image"]),
        "seed": first_present(data, ["seed"]),
        "run_label": first_present(data, ["run_label"]),
    }

    for key in ["mem_limit", "heap_size", "arcadedb_version", "ladybug_version", "docker_image"]:
        if params.get(key) is None and key in flat_data:
            params[key] = flat_data.get(key)

    return {k: v for k, v in params.items() if v is not None}


def format_value(value):
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return ""
    return str(value)


def format_bytes_binary(value):
    value = float(value)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if value < 1024.0:
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{value:.1f}EiB"


def humanize_metric(metric_name, value):
    if value is None or not is_number(value):
        return None
    if metric_name.endswith("_bytes") or metric_name.endswith(".du_bytes"):
        return format_bytes_binary(value)
    if metric_name.endswith("_kb"):
        return format_bytes_binary(value * 1024)
    return None


dataset_slug = dataset_filter.replace("-", "_")
dir_pattern = f"{dataset_slug}_graph_oltp_*" if dataset_filter else "*_graph_oltp_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))
result_files = []
for run_dir in run_dirs:
    result_files.extend(sorted(glob.glob(os.path.join(run_dir, "results_*.json"))))

rows = []
for result_path in result_files:
    run_dir = os.path.dirname(result_path)
    try:
        with open(result_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
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
    du_human = ""
    if os.path.isfile(du_path):
        try:
            with open(du_path, "r", encoding="utf-8") as handle:
                du_data = json.load(handle)
            du_bytes = du_data.get("du_bytes")
            du_human = du_data.get("du_human", "")
        except Exception:
            pass

    flat_data = flatten_dict(data)
    metric_values = {}
    bool_values = {}
    for key, value in flat_data.items():
        if is_number(value):
            metric_values[key] = value
        elif isinstance(value, bool):
            bool_values[key] = value

    if is_number(du_bytes):
        metric_values["disk_usage.du_bytes"] = du_bytes

    row = {
        "dataset": result_dataset,
        "db": data.get("db"),
        "run_label": run_label,
        "seed": data.get("seed"),
        "du_bytes": du_bytes,
        "du_human": du_human,
        "result_file": os.path.relpath(result_path, input_dir),
        "numeric_metrics": metric_values,
        "boolean_metrics": bool_values,
        "parameters": extract_parameters(data, flat_data),
    }
    row_human = {}
    for metric_name, metric_value in metric_values.items():
        human = humanize_metric(metric_name, metric_value)
        if human is not None:
            row_human[metric_name] = human
    row["human_readable_metrics"] = row_human
    rows.append(row)

if not rows:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

rows.sort(
    key=lambda r: (
        str(r["dataset"]),
        str(r["db"]),
        str(r.get("parameters", {}).get("threads")),
        str(r["run_label"]),
    )
)

by_db = defaultdict(list)
for row in rows:
    by_db[
        (
            row["dataset"],
            row["db"],
            row.get("parameters", {}).get("threads"),
        )
    ].append(row)

by_db_rows = []
for (group_dataset, db, threads), group in sorted(by_db.items()):
    metric_keys = sorted({k for r in group for k in r.get("numeric_metrics", {}).keys()})
    bool_metric_keys = sorted({k for r in group for k in r.get("boolean_metrics", {}).keys()})

    numeric_summary = {}
    for key in metric_keys:
        values = [
            r["numeric_metrics"][key]
            for r in group
            if key in r.get("numeric_metrics", {}) and is_number(r["numeric_metrics"][key])
        ]
        if not values:
            continue
        entry = {
            "count": len(values),
            "mean": statistics.mean(values),
            "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
        mean_human = humanize_metric(key, entry["mean"])
        min_human = humanize_metric(key, entry["min"])
        max_human = humanize_metric(key, entry["max"])
        if mean_human is not None:
            entry["mean_human"] = mean_human
            entry["min_human"] = min_human
            entry["max_human"] = max_human
        numeric_summary[key] = entry

    boolean_summary = {}
    for key in bool_metric_keys:
        values = [r["boolean_metrics"][key] for r in group if key in r.get("boolean_metrics", {})]
        if not values:
            continue
        true_count = sum(1 for value in values if value)
        boolean_summary[key] = {
            "count": len(values),
            "true_count": true_count,
            "false_count": len(values) - true_count,
            "true_ratio": true_count / len(values),
        }

    by_db_rows.append(
        {
            "dataset": group_dataset,
            "db": db,
            "threads": threads,
            "runs": len(group),
            "numeric_metrics": numeric_summary,
            "boolean_metrics": boolean_summary,
        }
    )

all_numeric_metric_keys = sorted({
    key
    for row in rows
    for key in row.get("numeric_metrics", {}).keys()
})

all_boolean_metric_keys = sorted({
    key
    for row in rows
    for key in row.get("boolean_metrics", {}).keys()
})

all_parameter_keys = sorted({
    key
    for row in rows
    for key in row.get("parameters", {}).keys()
})

parameters_detected = {}
for key in all_parameter_keys:
    values = sorted({str(row.get("parameters", {}).get(key)) for row in rows if key in row.get("parameters", {})})
    parameters_detected[key] = values

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")

summary = {
    "meta": {
        "name": "09 graph OLTP matrix summary",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": input_dir,
        "dataset": dataset_label,
        "dataset_size_profile": dataset_size_profile,
        "dataset_size_source": "dataset name suffix",
        "label_prefix": label_prefix,
        "total_runs": len(rows),
        "datasets_found": sorted({str(r["dataset"]) for r in rows}),
    },
    "parameter_keys": all_parameter_keys,
    "parameters_detected": parameters_detected,
    "numeric_metric_keys": all_numeric_metric_keys,
    "boolean_metric_keys": all_boolean_metric_keys,
    "run_fields": [
        "dataset", "db", "run_label", "seed", "du_bytes", "du_human", "result_file",
        "numeric_metrics", "human_readable_metrics", "boolean_metrics", "parameters",
    ],
    "runs": rows,
    "by_db": by_db_rows,
}

with open(summary_json, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

lines = []
lines.append("# 09 Graph OLTP Matrix Summary")
lines.append("")
lines.append(f"- Generated (UTC): {summary['meta']['generated_at_utc']}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(rows)}")
lines.append("")

lines.append("## Parameters Used")
lines.append("")
lines.append("| Parameter | Values |")
lines.append("|---|---|")
for key in all_parameter_keys:
    values = ", ".join(parameters_detected.get(key, []))
    lines.append(f"| {key} | {values} |")
lines.append("")

lines.append("## Aggregated Metrics by DB + Threads")
lines.append("")
for entry in by_db_rows:
    lines.append(
        f"### DB: {entry['db']}, Threads: {entry.get('threads', '')} (runs={entry['runs']})"
    )
    lines.append("")

    lines.append("#### Numeric Metrics")
    lines.append("")
    lines.append("| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    for metric_name in sorted(entry.get("numeric_metrics", {}).keys()):
        metric = entry["numeric_metrics"][metric_name]
        lines.append(
            f"| {metric_name} | {metric.get('count','')} | {format_value(metric.get('mean'))} | {metric.get('mean_human','')} | {format_value(metric.get('stddev'))} | {format_value(metric.get('min'))} | {format_value(metric.get('max'))} |"
        )
    lines.append("")

    lines.append("#### Boolean Metrics")
    lines.append("")
    lines.append("| Metric | Count | True | False | True Ratio |")
    lines.append("|---|---:|---:|---:|---:|")
    for metric_name in sorted(entry.get("boolean_metrics", {}).keys()):
        metric = entry["boolean_metrics"][metric_name]
        lines.append(
            f"| {metric_name} | {metric.get('count','')} | {metric.get('true_count','')} | {metric.get('false_count','')} | {format_value(metric.get('true_ratio'))} |"
        )
    lines.append("")

with open(summary_md, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_json}")
print(f"Wrote: {summary_md}")
PY

echo
echo "Summary file generated in: $OUTPUT_DIR"
