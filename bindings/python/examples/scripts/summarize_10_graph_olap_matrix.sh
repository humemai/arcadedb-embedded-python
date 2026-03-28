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

DATASET_TAG="${DATASET//-/_}"
if [[ -z "${DATASET_TAG// /}" ]]; then
    DATASET_TAG="all_datasets"
fi
SUMMARY_MD="$OUTPUT_DIR/summary_10_graph_olap_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" "$SCRIPT_DIR" << 'PY'
import glob
import json
import os
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix, script_dir = sys.argv[1:]
sys.path.insert(0, script_dir)

from _summary_helpers import normalize_db_label, normalize_run_label, normalized_run_key

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


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None


def first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def parse_threads_from_run_label(run_label):
    if not run_label:
        return None
    match = re.search(r"_t(\d+)_", str(run_label))
    if not match:
        return None
    return to_int(match.group(1))


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


def compute_du_mib_from_dir(path):
    if not path or not os.path.isdir(path):
        return None
    metadata_patterns = (
        "results_",
        "run_status.json",
        "disk_usage_du",
        "dependency_versions.json",
        "arcadedb_wheel_build.json",
    )
    try:
        entries = os.listdir(path)
    except Exception:
        return None
    non_metadata_entries = [
        name
        for name in entries
        if not any(name.startswith(prefix) for prefix in metadata_patterns)
    ]
    if not non_metadata_entries:
        return None
    try:
        out = subprocess.check_output(["du", "-sB1", path], text=True)
        first_field = out.strip().split()[0] if out else ""
        return bytes_to_mib(first_field)
    except Exception:
        return None


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


def percentile(values, p):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    k = (len(values) - 1) * p
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


def shorten_hash(value, width=12):
    text = str(value or "")
    if len(text) <= width:
        return text
    return text[:width]


def format_groups(group_map):
    if not group_map:
        return ""
    parts = []
    for key in sorted(group_map.keys()):
        dbs = ", ".join(sorted(group_map[key]))
        parts.append(f"{key}: {dbs}")
    return "; ".join(parts)


def split_majority_group(group_map):
    if not group_map:
        return "", "none"
    ordered = sorted(
        ((key, sorted(values)) for key, values in group_map.items()),
        key=lambda item: (-len(item[1]), item[0]),
    )
    _majority_key, majority_dbs = ordered[0]
    differing = []
    for _key, dbs in ordered[1:]:
        differing.extend(dbs)
    differing_value = ", ".join(sorted(differing)) if differing else "none"
    return ", ".join(majority_dbs), differing_value


def resolve_db_label(db, arcadedb_olap_language, run_label=None):
    label = str(normalize_db_label(db) or "")
    run_label_s = str(run_label or "")

    if "_arcadedb_cypher_" in run_label_s:
        return "arcadedb_cypher"

    if label == "arcadedb":
        lang = str(arcadedb_olap_language or "").strip().lower()
        if lang in ("sql", "cypher"):
            return f"arcadedb_{lang}"
    return label


def add_version(version_sets, key, value):
    if key in (None, "", "collected_at_utc"):
        return
    if value in (None, ""):
        return
    version_sets.setdefault(str(key), set()).add(str(value))


def collect_version_metadata(version_sets, data, run_dir):
    add_version(version_sets, "arcadedb_embedded", data.get("arcadedb_version"))
    add_version(version_sets, "real_ladybug", data.get("ladybug_version"))
    add_version(version_sets, "graphqlite", data.get("graphqlite_version"))
    add_version(
        version_sets,
        "duckdb",
        data.get("duckdb_runtime_version") or data.get("duckdb_version"),
    )
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


dataset_slug = dataset_filter.replace("-", "_")
dir_pattern = f"{dataset_slug}_graph_olap_*" if dataset_filter else "*_graph_olap_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))
status_rows = []
status_by_run = {}
result_rows = []
query_rows = []
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

        resolved_db = resolve_db_label(
            data.get("db"),
            data.get("arcadedb_olap_language"),
            normalized_run_label,
        )

        status_for_run = status_by_run.get(run_key, {})

        du_path = os.path.join(run_dir, "disk_usage_du.json")
        du_mib = None
        if os.path.isfile(du_path):
            try:
                with open(du_path, "r", encoding="utf-8") as f:
                    du_mib = bytes_to_mib((json.load(f) or {}).get("du_bytes"))
            except Exception:
                du_mib = None
        if du_mib is None:
            du_mib = compute_du_mib_from_dir(run_dir)

        result_rows.append(
            {
                "dataset": data.get("dataset"),
                "db": resolved_db,
                "source_db": data.get("db"),
                "run_label": normalized_run_label,
                "seed": first_not_none(
                    to_int(data.get("seed")),
                    to_int(status_for_run.get("seed")),
                ),
                "threads": to_int(data.get("threads"))
                or to_int(status_for_run.get("threads"))
                or parse_threads_from_run_label(normalized_run_label),
                "batch_size": to_int(data.get("batch_size")),
                "query_runs": to_int(data.get("query_runs")),
                "query_order": data.get("query_order"),
                "mem_limit": first_not_none(
                    data.get("mem_limit"),
                    status_for_run.get("mem_limit"),
                ),
                "load_time_s": to_float(data.get("load_time_s")),
                "index_time_s": to_float(data.get("index_time_s")),
                "query_time_s": to_float(data.get("query_time_s")),
                "gav_enabled": to_bool(data.get("gav_enabled")),
                "gav_ready_wait_time_s": to_float(data.get("gav_ready_wait_time_s")),
                "rss_peak_mib": kib_to_mib(data.get("rss_peak_kb")),
                "du_mib": du_mib,
            }
        )

        for query in data.get("queries") or []:
            elapsed_runs_s = query.get("elapsed_runs_s")
            if isinstance(elapsed_runs_s, list) and elapsed_runs_s:
                for sample_idx, sample_s in enumerate(elapsed_runs_s, start=1):
                    sample_s_float = to_float(sample_s)
                    if sample_s_float is None:
                        continue
                    query_rows.append(
                        {
                            "dataset": data.get("dataset"),
                            "db": resolved_db,
                            "threads": to_int(data.get("threads"))
                            or to_int(status_for_run.get("threads"))
                            or parse_threads_from_run_label(normalized_run_label),
                            "run_label": normalized_run_label,
                            "query_name": query.get("name"),
                            "run": sample_idx,
                            "elapsed_ms": sample_s_float * 1000.0,
                            "row_count": to_int(query.get("row_count")),
                            "result_hash": query.get("result_hash"),
                        }
                    )
            else:
                elapsed_s = to_float(query.get("elapsed_s"))
                query_rows.append(
                    {
                        "dataset": data.get("dataset"),
                        "db": resolved_db,
                        "threads": to_int(data.get("threads"))
                        or to_int(status_for_run.get("threads"))
                        or parse_threads_from_run_label(normalized_run_label),
                        "run_label": normalized_run_label,
                        "query_name": query.get("name"),
                        "run": to_int(query.get("run")),
                        "elapsed_ms": (elapsed_s * 1000.0) if elapsed_s is not None else None,
                        "row_count": to_int(query.get("row_count")),
                        "result_hash": query.get("result_hash"),
                    }
                )

if not result_rows:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

result_rows.sort(key=lambda r: (str(r["dataset"]), str(r["db"]), str(r["run_label"])))
query_rows.sort(
    key=lambda r: (
        str(r["dataset"]),
        str(r["query_name"]),
        str(r["db"]),
        str(r["run_label"]),
        r["run"] or 0,
    )
)

load_col = "load_s"
index_col = "index_s"
query_col = "query_s"
rss_col = "rss_peak_mib"
du_col = "du_mib"

by_query_db = defaultdict(list)
for row in query_rows:
    by_query_db[(row["dataset"], row["db"], row.get("threads"), row["query_name"])].append(row)

query_agg_rows = []
for (dataset_name, db, threads, query_name), rows in sorted(by_query_db.items()):
    elapsed_vals = [r["elapsed_ms"] for r in rows if r["elapsed_ms"] is not None]
    row_counts = sorted({r["row_count"] for r in rows if r["row_count"] is not None})
    hashes = sorted({str(r["result_hash"]) for r in rows if r["result_hash"] is not None})

    query_agg_rows.append(
        {
            "dataset": dataset_name,
            "db": db,
            "threads": threads,
            "query": query_name,
            "samples": len(rows),
            "elapsed_mean_ms": statistics.mean(elapsed_vals) if elapsed_vals else None,
            "elapsed_p95_ms": percentile(elapsed_vals, 0.95) if elapsed_vals else None,
            "row_counts": row_counts,
            "hash_stable_within_db": len(hashes) <= 1,
            "hashes": hashes,
        }
    )

by_query_cross = defaultdict(list)
for row in query_rows:
    by_query_cross[(row["dataset"], row["query_name"])].append(row)

cross_rows = []
for (dataset_name, query_name), rows in sorted(by_query_cross.items()):
    db_hashes = defaultdict(set)
    db_rows = defaultdict(set)
    for row in rows:
        if row["db"]:
            if row["result_hash"] is not None:
                db_hashes[str(row["db"])].add(str(row["result_hash"]))
            if row["row_count"] is not None:
                db_rows[str(row["db"])].add(int(row["row_count"]))

    all_hashes = sorted({h for hs in db_hashes.values() for h in hs})
    all_row_counts = sorted({c for cs in db_rows.values() for c in cs})
    hash_groups = defaultdict(list)
    for db, hashes in sorted(db_hashes.items()):
        label = " / ".join(shorten_hash(h) for h in sorted(hashes)) if hashes else "missing"
        hash_groups[label].append(db)
    row_count_groups = defaultdict(list)
    for db, row_counts in sorted(db_rows.items()):
        label = " / ".join(str(value) for value in sorted(row_counts)) if row_counts else "missing"
        row_count_groups[label].append(db)

    cross_rows.append(
        {
            "dataset": dataset_name,
            "query": query_name,
            "dbs": sorted(set(list(db_hashes.keys()) + list(db_rows.keys()))),
            "hash_equal_across_dbs": len(all_hashes) <= 1,
            "row_counts_equal_across_dbs": len(all_row_counts) <= 1,
            "all_values_equal_across_dbs": len(all_hashes) <= 1 and len(all_row_counts) <= 1,
            "all_hashes": all_hashes,
            "all_row_counts": all_row_counts,
            "hash_groups": dict(hash_groups),
            "row_count_groups": dict(row_count_groups),
        }
    )

dataset_size_profile = (
    dataset_filter.split("-")[-1]
    if dataset_filter and "-" in dataset_filter
    else (dataset_filter or "all")
)
generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ensure_versions_for_db_set(version_sets, {row.get("db") for row in result_rows})
version_summary_lines = format_version_summary_lines(version_sets)

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 10 Graph OLAP Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total result files: {len(result_rows)}")
if version_summary_lines:
    lines.append("- Versions/digest observed:")
    for item in version_summary_lines:
        lines.append(f"  - {item}")
lines.append(
    "- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution."
)
lines.append("- `gav_enabled` shows whether ArcadeDB queries ran after a Graph Analytical View was built.")
lines.append("- `gav_ready_wait_s` measures the wall-clock wait until the GAV reported `READY`.")
lines.append("- DB summary timing/memory/disk columns are single-run values (no averaging).")
lines.append("- Query parity is evaluated via `result_hash` and `row_count` across DBs.")
lines.append("")

datasets = sorted({str(row.get("dataset") or "") for row in result_rows})
for current_dataset in datasets:
    lines.append(f"## Dataset: {current_dataset}")
    lines.append("")

    lines.append("### DB summary")
    lines.append("")
    lines.append(
        f"| db | gav_enabled | gav_ready_wait_s | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | {load_col} | {index_col} | {query_col} | {rss_col} | {du_col} |"
    )
    lines.append("|---|---|---:|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for row in result_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["db"]),
                    fmt(row["gav_enabled"]),
                    fmt(row["gav_ready_wait_time_s"]),
                    fmt(row["run_label"]),
                    fmt(row["seed"]),
                    fmt(row["batch_size"]),
                    fmt(row["mem_limit"]),
                    fmt(row["threads"]),
                    fmt(row["query_runs"]),
                    fmt(row["query_order"]),
                    fmt(row["load_time_s"]),
                    fmt(row["index_time_s"]),
                    fmt(row["query_time_s"]),
                    fmt(row["rss_peak_mib"]),
                    fmt(row["du_mib"]),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("### Per-query latency (aggregated)")
    lines.append("")
    lines.append(
        "| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |"
    )
    lines.append("|---|---:|---|---:|---:|---:|---|---|")
    for row in query_agg_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["db"]),
                    fmt(row["threads"]),
                    fmt(row["query"]),
                    fmt(row["samples"]),
                    fmt(row["elapsed_mean_ms"]),
                    fmt(row["elapsed_p95_ms"]),
                    fmt(", ".join(str(v) for v in row["row_counts"])),
                    fmt(row["hash_stable_within_db"]),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("### Cross-DB query parity checks")
    lines.append("")
    lines.append(
        "| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for row in cross_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["query"]),
                    fmt(", ".join(row["dbs"])),
                    fmt(row["hash_equal_across_dbs"]),
                    fmt(format_groups(row["hash_groups"])),
                    fmt(row["row_counts_equal_across_dbs"]),
                    fmt(format_groups(row["row_count_groups"])),
                    fmt(row["all_values_equal_across_dbs"]),
                ]
            )
            + " |"
        )
    lines.append("")

    mismatch_rows = [
        row
        for row in cross_rows
        if str(row["dataset"] or "") == current_dataset
        and not row["all_values_equal_across_dbs"]
    ]
    if mismatch_rows:
        lines.append("### Cross-DB mismatches only")
        lines.append("")
        lines.append(
            "| query | majority_hash_dbs | differing_hash_dbs | majority_row_count_dbs | differing_row_count_dbs |"
        )
        lines.append("|---|---|---|---|---|")
        for row in mismatch_rows:
            majority_hash_dbs, differing_hash_dbs = split_majority_group(row["hash_groups"])
            majority_row_dbs, differing_row_dbs = split_majority_group(row["row_count_groups"])
            lines.append(
                "| "
                + " | ".join(
                    [
                        fmt(row["query"]),
                        fmt(majority_hash_dbs),
                        fmt(differing_hash_dbs),
                        fmt(majority_row_dbs),
                        fmt(differing_row_dbs),
                    ]
                )
                + " |"
            )
        lines.append("")

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
