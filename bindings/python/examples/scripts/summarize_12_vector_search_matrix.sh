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

DATASET_TAG="${DATASET//-/_}"
if [[ -z "${DATASET_TAG// /}" ]]; then
    DATASET_TAG="all_datasets"
fi
SUMMARY_MD="$OUTPUT_DIR/summary_12_vector_search_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import sys
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix = sys.argv[1:]
dataset_filter = dataset.strip()
dataset_label = dataset_filter or "all"

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

def add_version(version_sets, key, value):
    if key in (None, "", "collected_at_utc"):
        return
    if value in (None, ""):
        return
    version_sets.setdefault(str(key), set()).add(str(value))

def collect_version_metadata(version_sets, data, run_dir):
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
        values = sorted(version_sets.get(key) or [])
        if not values:
            continue
        shown = ", ".join(values[:max_values])
        extra = len(values) - max_values
        if extra > 0:
            shown += f", ... (+{extra} more)"
        out.append(f"{key}: {shown}")
    return out

def ensure_versions_for_backend_set(version_sets, backend_values):
    expected = set()
    backend_values = {str(v or "").strip() for v in backend_values}
    if "arcadedb" in backend_values:
        expected.add("arcadedb_embedded")
    if "faiss" in backend_values:
        expected.add("faiss_cpu")
    if "lancedb" in backend_values:
        expected.add("lancedb")
    if "pgvector" in backend_values:
        expected.add("pgvector_image")
    if "qdrant" in backend_values:
        expected.add("qdrant_image")
    if "milvus" in backend_values:
        expected.add("milvus_compose_version")
    if "bruteforce" in backend_values:
        expected.add("bruteforce")
    for key in expected:
        if key not in version_sets or not version_sets[key]:
            version_sets[key] = {"unknown"}

rows = []
status_rows = []
version_sets = {}

for result_path in sorted(glob.glob(os.path.join(input_dir, "*", "search_results_*.json"))):
    run_dir = os.path.dirname(result_path)

    try:
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    dataset_obj = data.get("dataset")
    dataset_name = dataset_obj.get("name") if isinstance(dataset_obj, dict) else dataset_obj

    run_obj = data.get("run") if isinstance(data.get("run"), dict) else {}
    search_obj = data.get("search") if isinstance(data.get("search"), dict) else {}
    db_obj = data.get("db") if isinstance(data.get("db"), dict) else {}
    telemetry_obj = data.get("telemetry") if isinstance(data.get("telemetry"), dict) else {}

    run_label = run_obj.get("run_label") or search_obj.get("run_label")
    if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
        continue
    if dataset_filter and dataset_name != dataset_filter:
        continue

    collect_version_metadata(version_sets, data, run_dir)

    status_path = os.path.join(run_dir, "search_run_status.json")
    status_obj = None
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status_obj = json.load(f)
        except Exception:
            status_obj = None
    if status_obj is not None:
        status_rows.append(status_obj)

    du_mib = None
    du_path = os.path.join(run_dir, "disk_usage_du_search.json")
    if os.path.isfile(du_path):
        try:
            with open(du_path, "r", encoding="utf-8") as f:
                du_mib = bytes_to_mib((json.load(f) or {}).get("du_bytes"))
        except Exception:
            du_mib = None

    sweeps = search_obj.get("sweeps") if isinstance(search_obj.get("sweeps"), list) else []
    for sweep in sweeps:
        if not isinstance(sweep, dict):
            continue

        phases = sweep.get("phases") if isinstance(sweep.get("phases"), list) else []
        phase_by_name = {
            phase.get("name"): phase
            for phase in phases
            if isinstance(phase, dict) and phase.get("name")
        }

        rows.append(
            {
                "dataset": dataset_name,
                "backend": db_obj.get("backend"),
                "run_label": run_label,
                "seed": to_int(search_obj.get("seed")),
                "query_runs": to_int(search_obj.get("query_runs")),
                "query_order": search_obj.get("query_order"),
                "k": to_int(search_obj.get("k")),
                "overquery_factor": to_float(sweep.get("overquery_factor")),
                "effective_ef_search": to_int(sweep.get("effective_ef_search")),
                "effective_nprobes": to_int(sweep.get("effective_nprobes")),
                "queries": to_int(sweep.get("queries")),
                "recall_mean": to_float(sweep.get("recall_mean")),
                "latency_ms_mean": to_float(sweep.get("latency_ms_mean")),
                "latency_ms_p95": to_float(sweep.get("latency_ms_p95")),
                "run_total_s": to_float(run_obj.get("total_time_s")),
                "open_db_s": to_float((phase_by_name.get("open_db") or {}).get("time_sec")),
                "search_s": to_float((phase_by_name.get("search") or {}).get("time_sec")),
                "close_db_s": to_float((phase_by_name.get("close_db") or {}).get("time_sec")),
                "peak_rss_mib": to_float(data.get("peak_rss_mb")),
                "du_mib": du_mib,
                "status": (status_obj or {}).get("status") or telemetry_obj.get("run_status"),
            }
        )

if not rows:
    print("No matching search_results_*.json files found.", file=sys.stderr)
    sys.exit(2)

rows.sort(
    key=lambda r: (
        str(r.get("dataset") or ""),
        str(r.get("backend") or ""),
        str(r.get("run_label") or ""),
        float(r.get("overquery_factor") or 0),
    )
)

status_scoped = []
for status in status_rows:
    rl = status.get("search_run_label") or status.get("run_label")
    ds = status.get("dataset")
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
ensure_versions_for_backend_set(version_sets, {row.get("backend") for row in rows})
version_summary_lines = format_version_summary_lines(version_sets)

COLUMNS = [
    "backend",
    "run_label",
    "seed",
    "k",
    "query_runs",
    "query_order",
    "overquery_factor",
    "effective_ef_search",
    "effective_nprobes",
    "queries",
    "recall_mean",
    "latency_ms_mean",
    "latency_ms_p95",
    "run_total_s",
    "open_db_s",
    "search_s",
    "close_db_s",
    "peak_rss_mib",
    "du_mib",
    "status",
]

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 12 Vector Search Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total sweep rows: {len(rows)}")
if version_summary_lines:
    lines.append("- Versions/digest observed:")
    for item in version_summary_lines:
        lines.append(f"  - {item}")
if status_total > 0:
    lines.append(f"- Search run status files: total={status_total}, success={status_success}, failed={status_failed}")
lines.append("- Note: one row = one backend run + one overquery sweep point.")
lines.append("- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.")
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

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
