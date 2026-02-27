#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep10"

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
SUMMARY_JSON="$OUTPUT_DIR/summary_10_graph_olap_${DATASET_TAG}.json"
SUMMARY_MD="$OUTPUT_DIR/summary_10_graph_olap_${DATASET_TAG}.md"

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
        "dataset": first_present(data, ["dataset"]),
        "db": first_present(data, ["db"]),
        "threads": first_present(data, ["threads"]),
        "batch_size": first_present(data, ["batch_size"]),
        "query_runs": first_present(data, ["query_runs"]),
        "query_order": first_present(data, ["query_order"]),
        "only_query": first_present(data, ["only_query"]),
        "manual_checks": first_present(data, ["manual_checks"]),
        "mem_limit": first_present(data, ["mem_limit", "memory_limit"]),
        "heap_size": first_present(data, ["heap_size"]),
        "arcadedb_version": first_present(data, ["arcadedb_version"]),
        "ladybug_version": first_present(data, ["ladybug_version"]),
        "docker_image": first_present(data, ["docker_image"]),
        "seed": first_present(data, ["seed"]),
        "run_label": first_present(data, ["run_label"]),
    }

    for key in [
        "mem_limit",
        "heap_size",
        "arcadedb_version",
        "ladybug_version",
        "docker_image",
        "query_order",
        "only_query",
        "manual_checks",
    ]:
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
dir_pattern = f"{dataset_slug}_graph_olap_*" if dataset_filter else "*_graph_olap_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))
result_files = []
for run_dir in run_dirs:
    result_files.extend(sorted(glob.glob(os.path.join(run_dir, "results_*.json"))))

runs = []
query_rows = []

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

    flat_run = flatten_dict(data)
    run_numeric, run_boolean = metric_buckets(flat_run)
    params = extract_parameters(data, flat_run)
    if is_number(du_bytes):
        run_numeric["disk_usage.du_bytes"] = du_bytes

    run_row = {
        "dataset": result_dataset,
        "db": data.get("db"),
        "run_label": run_label,
        "seed": data.get("seed"),
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

    query_items = data.get("queries")
    if isinstance(query_items, dict):
        query_items = query_items.get("items", [])
    if not isinstance(query_items, list):
        query_items = []

    for query in query_items:
        if not isinstance(query, dict):
            continue
        flat_query = flatten_dict(query)
        query_numeric, query_boolean = metric_buckets(flat_query)

        query_rows.append(
            {
                "dataset": result_dataset,
                "db": data.get("db"),
                "run_label": run_label,
                "query_name": query.get("name"),
                "numeric_metrics": query_numeric,
                "boolean_metrics": query_boolean,
                "row_count": query.get("row_count"),
                "result_hash": query.get("result_hash"),
            }
        )

if not runs:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

runs.sort(key=lambda r: (str(r["dataset"]), str(r["db"]), str(r["run_label"])))

by_db = defaultdict(list)
for row in runs:
    by_db[(row["dataset"], row["db"])].append(row)

by_db_rows = []
for (group_dataset, db), group in sorted(by_db.items()):
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
            "runs": len(group),
            "numeric_metrics": numeric_summary,
            "boolean_metrics": boolean_summary,
        }
    )

by_query_group = defaultdict(list)
for row in query_rows:
    by_query_group[(row["dataset"], row["db"], row["query_name"])].append(row)

by_query_rows = []
for (group_dataset, db, query_name), group in sorted(by_query_group.items()):
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

    row_counts = sorted({r.get("row_count") for r in group})
    hashes = sorted({str(r.get("result_hash")) for r in group if r.get("result_hash") is not None})

    by_query_rows.append(
        {
            "dataset": group_dataset,
            "db": db,
            "query_name": query_name,
            "samples": len(group),
            "numeric_metrics": numeric_summary,
            "boolean_metrics": boolean_summary,
            "row_counts": row_counts,
            "result_hashes": hashes,
            "hash_stable": len(hashes) <= 1,
        }
    )


all_dbs = sorted({str(r.get("db")) for r in runs if r.get("db") is not None})

by_query_cross_db_group = defaultdict(list)
for row in query_rows:
    by_query_cross_db_group[(row["dataset"], row["query_name"])].append(row)

by_query_cross_db_rows = []
for (group_dataset, query_name), group in sorted(by_query_cross_db_group.items()):
    db_hashes = {}
    db_row_counts = {}

    for db in sorted({str(r.get("db")) for r in group if r.get("db") is not None}):
        hashes = sorted({
            str(r.get("result_hash"))
            for r in group
            if r.get("db") == db and r.get("result_hash") is not None
        })
        row_counts = sorted({
            r.get("row_count")
            for r in group
            if r.get("db") == db
        })
        db_hashes[db] = hashes
        db_row_counts[db] = row_counts

    hashes_by_db_stable = {
        db: len(hashes) <= 1
        for db, hashes in db_hashes.items()
    }

    row_counts_by_db_stable = {
        db: len(row_counts) <= 1
        for db, row_counts in db_row_counts.items()
    }

    all_hashes = sorted({
        hash_value
        for hashes in db_hashes.values()
        for hash_value in hashes
    })

    all_row_counts = sorted({
        row_count
        for row_counts in db_row_counts.values()
        for row_count in row_counts
    })

    present_dbs = sorted(db_hashes.keys())
    missing_dbs = sorted(set(all_dbs) - set(present_dbs))

    hash_equal_across_dbs = len(all_hashes) <= 1 and len(missing_dbs) == 0
    row_counts_equal_across_dbs = len(all_row_counts) <= 1 and len(missing_dbs) == 0

    by_query_cross_db_rows.append(
        {
            "dataset": group_dataset,
            "query_name": query_name,
            "samples": len(group),
            "dbs_present": present_dbs,
            "dbs_missing": missing_dbs,
            "db_hashes": db_hashes,
            "db_row_counts": db_row_counts,
            "hashes_by_db_stable": hashes_by_db_stable,
            "row_counts_by_db_stable": row_counts_by_db_stable,
            "all_hashes": all_hashes,
            "all_row_counts": all_row_counts,
            "hash_equal_across_dbs": hash_equal_across_dbs,
            "row_counts_equal_across_dbs": row_counts_equal_across_dbs,
            "all_values_equal_across_dbs": hash_equal_across_dbs and row_counts_equal_across_dbs,
        }
    )

cross_db_parity = {
    "enabled": True,
    "dbs_expected": all_dbs,
    "queries_compared": len(by_query_cross_db_rows),
    "mismatch_count": sum(
        1
        for row in by_query_cross_db_rows
        if not row.get("all_values_equal_across_dbs")
    ),
    "all_queries_match": all(
        row.get("all_values_equal_across_dbs")
        for row in by_query_cross_db_rows
    ) if by_query_cross_db_rows else True,
}

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

query_numeric_metric_keys = sorted({
    key
    for row in query_rows
    for key in row.get("numeric_metrics", {}).keys()
})

query_boolean_metric_keys = sorted({
    key
    for row in query_rows
    for key in row.get("boolean_metrics", {}).keys()
})

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")

summary = {
    "meta": {
        "name": "10 graph OLAP matrix summary",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": input_dir,
        "dataset": dataset_label,
        "dataset_size_profile": dataset_size_profile,
        "dataset_size_source": "dataset name suffix",
        "label_prefix": label_prefix,
        "total_runs": len(runs),
        "datasets_found": sorted({str(r["dataset"]) for r in runs}),
        "query_samples": len(query_rows),
    },
    "parameter_keys": all_parameter_keys,
    "parameters_detected": parameters_detected,
    "numeric_metric_keys": all_numeric_metric_keys,
    "boolean_metric_keys": all_boolean_metric_keys,
    "query_numeric_metric_keys": query_numeric_metric_keys,
    "query_boolean_metric_keys": query_boolean_metric_keys,
    "cross_db_parity": cross_db_parity,
    "run_fields": [
        "dataset", "db", "run_label", "seed", "du_bytes", "du_human", "result_file",
        "numeric_metrics", "human_readable_metrics", "boolean_metrics", "parameters",
    ],
    "runs": runs,
    "by_db": by_db_rows,
    "by_query": by_query_rows,
    "by_query_cross_db": by_query_cross_db_rows,
}

with open(summary_json, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)

lines = []
lines.append("# 10 Graph OLAP Matrix Summary")
lines.append("")
lines.append(f"- Generated (UTC): {summary['meta']['generated_at_utc']}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(runs)}")
lines.append(f"- Query samples: {len(query_rows)}")
lines.append(f"- Cross-DB parity: {cross_db_parity['all_queries_match']}")
lines.append("")

lines.append("## Parameters Used")
lines.append("")
lines.append("| Parameter | Values |")
lines.append("|---|---|")
for key in all_parameter_keys:
    values = ", ".join(parameters_detected.get(key, []))
    lines.append(f"| {key} | {values} |")
lines.append("")

lines.append("## Aggregated Metrics by DB")
lines.append("")
for entry in by_db_rows:
    lines.append(f"### DB: {entry['db']} (runs={entry['runs']})")
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

lines.append("## Aggregated Query Metrics")
lines.append("")
for entry in by_query_rows:
    lines.append(f"### DB: {entry['db']} | Query: {entry['query_name']} (samples={entry['samples']})")
    lines.append("")
    lines.append(f"- Row counts: {', '.join(str(v) for v in entry.get('row_counts', []))}")
    lines.append(f"- Hash stable: {entry.get('hash_stable')}")
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

lines.append("## Cross-DB Query Result Checks")
lines.append("")
lines.append("| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | Row Counts Equal Across DBs | All Values Equal Across DBs |")
lines.append("|---|---:|---|---|---|---|---|")
for entry in by_query_cross_db_rows:
    dbs_present = ", ".join(entry.get("dbs_present", []))
    dbs_missing = ", ".join(entry.get("dbs_missing", []))
    lines.append(
        f"| {entry.get('query_name','')} | {entry.get('samples','')} | {dbs_present} | {dbs_missing} | {entry.get('hash_equal_across_dbs')} | {entry.get('row_counts_equal_across_dbs')} | {entry.get('all_values_equal_across_dbs')} |"
    )
lines.append("")

for entry in by_query_cross_db_rows:
    lines.append(f"### {entry.get('query_name','')}")
    lines.append("")
    lines.append("| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |")
    lines.append("|---|---|---|---|---|")
    for db in sorted(entry.get("db_hashes", {}).keys()):
        db_hashes = ", ".join(entry["db_hashes"].get(db, []))
        db_row_counts = ", ".join(str(value) for value in entry["db_row_counts"].get(db, []))
        hash_stable = entry.get("hashes_by_db_stable", {}).get(db)
        row_count_stable = entry.get("row_counts_by_db_stable", {}).get(db)
        lines.append(f"| {db} | {db_hashes} | {db_row_counts} | {hash_stable} | {row_count_stable} |")
    lines.append("")

with open(summary_md, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_json}")
print(f"Wrote: {summary_md}")
PY

echo
echo "Summary file generated in: $OUTPUT_DIR"
