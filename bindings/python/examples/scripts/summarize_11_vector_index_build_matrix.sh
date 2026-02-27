#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep11"

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
        config = data.get("config") if isinstance(data.get("config"), dict) else {}
        run_label = config.get("run_label") or data.get("run_label")
        if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
                continue
        dataset = data.get("dataset")
        if isinstance(dataset, dict):
                dataset = dataset.get("name")
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
SUMMARY_JSON="$OUTPUT_DIR/summary_11_vector_index_build_${DATASET_TAG}.json"
SUMMARY_MD="$OUTPUT_DIR/summary_11_vector_index_build_${DATASET_TAG}.md"

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


def metric_buckets(flat_data):
    numeric = {}
    boolean = {}
    for key, value in flat_data.items():
        if is_number(value):
            numeric[key] = value
        elif isinstance(value, bool):
            boolean[key] = value
    return numeric, boolean


def first_present(data, keys):
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def extract_parameters(data, flat_data):
    params = {
        "backend": first_present(flat_data, ["config.backend", "environment.backend"]),
        "dataset": first_present(flat_data, ["dataset.name"]),
        "dataset_label": first_present(flat_data, ["dataset.label"]),
        "dim": first_present(flat_data, ["dataset.dim"]),
        "rows": first_present(flat_data, ["dataset.rows"]),
        "count": first_present(flat_data, ["config.count"]),
        "threads": first_present(flat_data, ["environment.threads_limit", "budget.total.threads_input"]),
        "mem_limit": first_present(flat_data, ["environment.mem_limit", "budget.total.memory_limit"]),
        "cpus": first_present(flat_data, ["budget.total.cpus"]),
        "server_fraction": first_present(flat_data, ["budget.split.server_fraction"]),
        "batch_size": first_present(flat_data, ["config.batch_size"]),
        "max_connections": first_present(flat_data, ["config.max_connections"]),
        "beam_width": first_present(flat_data, ["config.beam_width"]),
        "quantization": first_present(flat_data, ["config.quantization"]),
        "store_vectors_in_graph": first_present(flat_data, ["config.store_vectors_in_graph"]),
        "add_hierarchy": first_present(flat_data, ["config.add_hierarchy"]),
        "heap": first_present(flat_data, ["config.heap", "environment.heap_size"]),
        "run_label": first_present(flat_data, ["config.run_label"]),
        "seed": first_present(flat_data, ["config.seed"]),
        "docker_image": first_present(flat_data, ["environment.docker_image"]),
        "arcadedb_version": first_present(flat_data, ["environment.runtime_versions.arcadedb"]),
        "postgres_version": first_present(flat_data, ["environment.runtime_versions.postgres"]),
        "qdrant_version": first_present(flat_data, ["environment.runtime_versions.qdrant"]),
        "milvus_version": first_present(flat_data, ["environment.runtime_versions.milvus"]),
    }
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
    if metric_name.endswith("_mb"):
        return format_bytes_binary(value * 1024 * 1024)
    return None


result_files = sorted(glob.glob(os.path.join(input_dir, "*", "results_*.json")))

runs = []

for result_path in result_files:
    run_dir = os.path.dirname(result_path)
    try:
        with open(result_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        continue

    dataset_value = data.get("dataset")
    if isinstance(dataset_value, dict):
        result_dataset = dataset_value.get("name")
    elif isinstance(dataset_value, str):
        result_dataset = dataset_value
    else:
        result_dataset = None

    config_value = data.get("config") if isinstance(data.get("config"), dict) else {}
    run_label = config_value.get("run_label") or data.get("run_label")
    backend = config_value.get("backend") or data.get("backend")

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

    flat_run = flatten_dict(data)
    run_numeric, run_boolean = metric_buckets(flat_run)
    params = extract_parameters(data, flat_run)

    if is_number(du_bytes):
        run_numeric["disk_usage.du_bytes"] = du_bytes

    run_row = {
        "dataset": result_dataset,
        "backend": backend,
        "run_label": run_label,
        "seed": config_value.get("seed") if isinstance(config_value, dict) else data.get("seed"),
        "du_bytes": du_bytes,
        "du_human": du_human,
        "result_file": os.path.relpath(result_path, input_dir),
        "numeric_metrics": run_numeric,
        "boolean_metrics": run_boolean,
        "parameters": params,
    }

    run_human = {}
    for metric_name, metric_value in run_numeric.items():
        human = humanize_metric(metric_name, metric_value)
        if human is not None:
            run_human[metric_name] = human
    run_row["human_readable_metrics"] = run_human
    runs.append(run_row)

if not runs:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

runs.sort(key=lambda r: (str(r["dataset"]), str(r["backend"]), str(r["run_label"])))

by_backend = defaultdict(list)
for row in runs:
    by_backend[(row["dataset"], row["backend"])].append(row)

by_backend_rows = []
for (group_dataset, backend), group in sorted(by_backend.items()):
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

    by_backend_rows.append(
        {
            "dataset": group_dataset,
            "backend": backend,
            "runs": len(group),
            "numeric_metrics": numeric_summary,
            "boolean_metrics": boolean_summary,
        }
    )

all_numeric_metric_keys = sorted({
    key
    for row in runs
    for key in row.get("numeric_metrics", {}).keys()
})

all_boolean_metric_keys = sorted({
    key
    for row in runs
    for key in row.get("boolean_metrics", {}).keys()
})

all_parameter_keys = sorted({
    key
    for row in runs
    for key in row.get("parameters", {}).keys()
})

parameters_detected = {}
for key in all_parameter_keys:
    values = sorted({str(row.get("parameters", {}).get(key)) for row in runs if key in row.get("parameters", {})})
    parameters_detected[key] = values

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")

summary = {
    "meta": {
        "name": "11 vector index build matrix summary",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": input_dir,
        "dataset": dataset_label,
        "dataset_size_profile": dataset_size_profile,
        "dataset_size_source": "dataset name suffix",
        "label_prefix": label_prefix,
        "total_runs": len(runs),
        "datasets_found": sorted({str(r["dataset"]) for r in runs}),
        "backends_found": sorted({str(r["backend"]) for r in runs}),
    },
    "parameter_keys": all_parameter_keys,
    "parameters_detected": parameters_detected,
    "numeric_metric_keys": all_numeric_metric_keys,
    "boolean_metric_keys": all_boolean_metric_keys,
    "run_fields": [
        "dataset", "backend", "run_label", "seed", "du_bytes", "du_human", "result_file",
        "numeric_metrics", "human_readable_metrics", "boolean_metrics", "parameters",
    ],
    "runs": runs,
    "by_backend": by_backend_rows,
}

with open(summary_json, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

lines = []
lines.append("# 11 Vector Index Build Matrix Summary")
lines.append("")
lines.append(f"- Generated (UTC): {summary['meta']['generated_at_utc']}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(runs)}")
lines.append(f"- Backends: {', '.join(summary['meta']['backends_found'])}")
lines.append("")

lines.append("## Parameters Used")
lines.append("")
lines.append("| Parameter | Values |")
lines.append("|---|---|")
for key in all_parameter_keys:
    values = ", ".join(parameters_detected.get(key, []))
    lines.append(f"| {key} | {values} |")
lines.append("")

lines.append("## Aggregated Metrics by Backend")
lines.append("")
for entry in by_backend_rows:
    lines.append(f"### Backend: {entry['backend']} (runs={entry['runs']})")
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
