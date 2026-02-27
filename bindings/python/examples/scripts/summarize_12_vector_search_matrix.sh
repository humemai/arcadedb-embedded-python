#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep12"

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
for path in glob.glob(os.path.join(input_dir, "**", "search_results_*.json"), recursive=True):
        try:
                with open(path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
        except Exception:
                continue
        run = data.get("run") if isinstance(data.get("run"), dict) else {}
        search = data.get("search") if isinstance(data.get("search"), dict) else {}
        run_label = run.get("run_label") or search.get("run_label")
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
SUMMARY_JSON="$OUTPUT_DIR/summary_12_vector_search_${DATASET_TAG}.json"
SUMMARY_MD="$OUTPUT_DIR/summary_12_vector_search_${DATASET_TAG}.md"

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


def extract_parameters(flat_data):
    params = {
        "backend": first_present(flat_data, ["db.backend", "environment.backend"]),
        "dataset": first_present(flat_data, ["dataset.name"]),
        "dataset_label": first_present(flat_data, ["dataset.label"]),
        "dim": first_present(flat_data, ["dataset.dim"]),
        "rows": first_present(flat_data, ["dataset.rows"]),
        "query_count": first_present(flat_data, ["dataset.query_count"]),
        "query_limit": first_present(flat_data, ["dataset.query_limit"]),
        "threads": first_present(flat_data, ["environment.threads_limit", "budget.total.threads_input"]),
        "mem_limit": first_present(flat_data, ["environment.mem_limit", "budget.total.memory_limit"]),
        "cpus": first_present(flat_data, ["budget.total.cpus"]),
        "server_fraction": first_present(flat_data, ["budget.split.server_fraction"]),
        "k": first_present(flat_data, ["search.k"]),
        "query_runs": first_present(flat_data, ["search.query_runs"]),
        "query_order": first_present(flat_data, ["search.query_order"]),
        "seed": first_present(flat_data, ["search.seed"]),
        "run_label": first_present(flat_data, ["run.run_label", "search.run_label"]),
        "heap": first_present(flat_data, ["environment.heap_size", "db.arcadedb_heap_size_effective"]),
        "quantization": first_present(flat_data, ["db.quantization", "environment.quantization"]),
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
    negative = value < 0
    value = abs(value)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if value < 1024.0:
            text = f"{value:.1f}{unit}"
            return f"-{text}" if negative else text
        value /= 1024.0
    text = f"{value:.1f}EiB"
    return f"-{text}" if negative else text


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


def summarize_numeric(group, key):
    values = [
        row["numeric_metrics"][key]
        for row in group
        if key in row.get("numeric_metrics", {}) and is_number(row["numeric_metrics"][key])
    ]
    if not values:
        return None
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
    return entry


def summarize_boolean(group, key):
    values = [row["boolean_metrics"][key] for row in group if key in row.get("boolean_metrics", {})]
    if not values:
        return None
    true_count = sum(1 for value in values if value)
    return {
        "count": len(values),
        "true_count": true_count,
        "false_count": len(values) - true_count,
        "true_ratio": true_count / len(values),
    }


result_files = sorted(glob.glob(os.path.join(input_dir, "*", "search_results_*.json")))

runs = []
sweep_rows = []

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

    backend = ((data.get("db") or {}).get("backend")) or ((data.get("environment") or {}).get("backend"))
    run_label = ((data.get("run") or {}).get("run_label")) or ((data.get("search") or {}).get("run_label"))

    if dataset_filter and result_dataset != dataset_filter:
        continue
    if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
        continue

    du_path = os.path.join(run_dir, "disk_usage_du_search.json")
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
    if is_number(du_bytes):
        run_numeric["disk_usage_search.du_bytes"] = du_bytes

    run_row = {
        "dataset": result_dataset,
        "backend": backend,
        "run_label": run_label,
        "seed": ((data.get("search") or {}).get("seed")),
        "du_bytes": du_bytes,
        "du_human": du_human,
        "result_file": os.path.relpath(result_path, input_dir),
        "numeric_metrics": run_numeric,
        "boolean_metrics": run_boolean,
        "parameters": extract_parameters(flat_run),
    }

    run_human = {}
    for metric_name, metric_value in run_numeric.items():
        human = humanize_metric(metric_name, metric_value)
        if human is not None:
            run_human[metric_name] = human
    run_row["human_readable_metrics"] = run_human
    runs.append(run_row)

    for sweep in ((data.get("search") or {}).get("sweeps") or []):
        if not isinstance(sweep, dict):
            continue

        search_phase = None
        for phase in sweep.get("phases", []):
            if isinstance(phase, dict) and phase.get("name") == "search":
                search_phase = phase
                break

        phase_numeric = {}
        phase_boolean = {}
        if isinstance(search_phase, dict):
            flat_phase = flatten_dict(search_phase)
            phase_numeric, phase_boolean = metric_buckets(flat_phase)

        base_numeric = {}
        for key in [
            "overquery_factor",
            "effective_ef_search",
            "effective_overquery_factor",
            "recall_mean",
            "recall_count",
            "latency_ms_mean",
            "latency_ms_p95",
            "queries",
        ]:
            value = sweep.get(key)
            if is_number(value):
                base_numeric[key] = value

        sweep_row = {
            "dataset": result_dataset,
            "backend": backend,
            "run_label": run_label,
            "overquery_factor": sweep.get("overquery_factor"),
            "effective_ef_search": sweep.get("effective_ef_search"),
            "effective_overquery_factor": sweep.get("effective_overquery_factor"),
            "numeric_metrics": {**base_numeric, **phase_numeric},
            "boolean_metrics": phase_boolean,
        }
        sweep_rows.append(sweep_row)

if not runs:
    print("No matching search_results_*.json files found.", file=sys.stderr)
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
        entry = summarize_numeric(group, key)
        if entry is not None:
            numeric_summary[key] = entry

    boolean_summary = {}
    for key in bool_metric_keys:
        entry = summarize_boolean(group, key)
        if entry is not None:
            boolean_summary[key] = entry

    by_backend_rows.append(
        {
            "dataset": group_dataset,
            "backend": backend,
            "runs": len(group),
            "numeric_metrics": numeric_summary,
            "boolean_metrics": boolean_summary,
        }
    )

by_sweep = defaultdict(list)
for row in sweep_rows:
    by_sweep[(row["dataset"], row["backend"], row.get("overquery_factor"))].append(row)

by_sweep_rows = []
for (group_dataset, backend, overquery_factor), group in sorted(
    by_sweep.items(), key=lambda item: (str(item[0][0]), str(item[0][1]), float(item[0][2] if item[0][2] is not None else -1))
):
    metric_keys = sorted({k for r in group for k in r.get("numeric_metrics", {}).keys()})
    bool_metric_keys = sorted({k for r in group for k in r.get("boolean_metrics", {}).keys()})

    numeric_summary = {}
    for key in metric_keys:
        entry = summarize_numeric(group, key)
        if entry is not None:
            numeric_summary[key] = entry

    boolean_summary = {}
    for key in bool_metric_keys:
        entry = summarize_boolean(group, key)
        if entry is not None:
            boolean_summary[key] = entry

    ef_values = sorted({str(r.get("effective_ef_search")) for r in group if r.get("effective_ef_search") is not None})
    oq_values = sorted({str(r.get("effective_overquery_factor")) for r in group if r.get("effective_overquery_factor") is not None})

    by_sweep_rows.append(
        {
            "dataset": group_dataset,
            "backend": backend,
            "overquery_factor": overquery_factor,
            "samples": len(group),
            "effective_ef_search_values": ef_values,
            "effective_overquery_values": oq_values,
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

sweep_numeric_metric_keys = sorted({
    key
    for row in sweep_rows
    for key in row.get("numeric_metrics", {}).keys()
})

sweep_boolean_metric_keys = sorted({
    key
    for row in sweep_rows
    for key in row.get("boolean_metrics", {}).keys()
})

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")

summary = {
    "meta": {
        "name": "12 vector search matrix summary",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": input_dir,
        "dataset": dataset_label,
        "dataset_size_profile": dataset_size_profile,
        "dataset_size_source": "dataset name suffix",
        "label_prefix": label_prefix,
        "total_runs": len(runs),
        "datasets_found": sorted({str(r["dataset"]) for r in runs}),
        "backends_found": sorted({str(r["backend"]) for r in runs}),
        "sweep_samples": len(sweep_rows),
    },
    "parameter_keys": all_parameter_keys,
    "parameters_detected": parameters_detected,
    "numeric_metric_keys": all_numeric_metric_keys,
    "boolean_metric_keys": all_boolean_metric_keys,
    "sweep_numeric_metric_keys": sweep_numeric_metric_keys,
    "sweep_boolean_metric_keys": sweep_boolean_metric_keys,
    "run_fields": [
        "dataset", "backend", "run_label", "seed", "du_bytes", "du_human", "result_file",
        "numeric_metrics", "human_readable_metrics", "boolean_metrics", "parameters",
    ],
    "runs": runs,
    "by_backend": by_backend_rows,
    "by_sweep": by_sweep_rows,
}

with open(summary_json, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

lines = []
lines.append("# 12 Vector Search Matrix Summary")
lines.append("")
lines.append(f"- Generated (UTC): {summary['meta']['generated_at_utc']}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(runs)}")
lines.append(f"- Backends: {', '.join(summary['meta']['backends_found'])}")
lines.append(f"- Sweep samples: {len(sweep_rows)}")
lines.append("")

lines.append("## Parameters Used")
lines.append("")
lines.append("| Parameter | Values |")
lines.append("|---|---|")
for key in all_parameter_keys:
    values = ", ".join(parameters_detected.get(key, []))
    lines.append(f"| {key} | {values} |")
lines.append("")

lines.append("## Aggregated Run Metrics by Backend")
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

lines.append("## Aggregated Sweep Metrics")
lines.append("")
for entry in by_sweep_rows:
    lines.append(
        f"### Backend: {entry['backend']} | Overquery: {entry['overquery_factor']} (samples={entry['samples']})"
    )
    lines.append("")
    lines.append(f"- Effective ef_search values: {', '.join(entry.get('effective_ef_search_values', []))}")
    lines.append(f"- Effective overquery values: {', '.join(entry.get('effective_overquery_values', []))}")
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
