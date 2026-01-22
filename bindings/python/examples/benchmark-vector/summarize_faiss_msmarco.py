#!/usr/bin/env python3
"""
Summarize MSMARCO runs into markdown tables (one file per dataset).

Reads: my_test_databases/*/results.json produced by benchmark_faiss_msmarco.py.
Writes: summaries/faiss_msmarco_<dataset>.md

Each table includes key params and metrics:
- index, metric, nlist, nprobe, pq_m, pq_nbits, hnsw_m, hnsw_efc, hnsw_efs
- recall@50, search_s, add_s, build_s, save_s, size_mb
Sorted by recall@50 desc, then search time asc.
"""
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path("my_test_databases")
OUT_DIR = Path("summaries")
EVAL_K = 50


def format_duration(seconds: float | int | None) -> str | None:
    if seconds is None or pd.isna(seconds):
        return None
    total = float(seconds)
    minutes, secs = divmod(total, 60)
    if total < 60:
        return f"{total:.3f}s"
    if minutes < 60:
        return f"{int(minutes)}m {secs:.3f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {secs:.3f}s"


def find_results(root: Path) -> List[Path]:
    return sorted(root.glob("*/results.json"))


def _run_dir_value(run_dir_name: str, key: str) -> str | None:
    prefix = f"{key}="
    for part in run_dir_name.split("_"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def parse_record(path: Path, eval_k: int) -> Dict:
    data = json.loads(path.read_text())
    cfg = data.get("config", {})
    phases = data.get("phases", {})
    recall = data.get("recall", {})
    r_entry = recall.get(str(eval_k)) or recall.get(eval_k) or {}

    run_dir_name = path.parent.name
    dataset_tag = _run_dir_value(run_dir_name, "dataset") or run_dir_name
    heap_tag = _run_dir_value(run_dir_name, "heap")

    # approximate peak RSS: max of rss_after across phases (if present)
    rss_afters = [
        phases.get(name, {}).get("rss_after_mb")
        for name in (
            "load_corpus",
            "load_queries",
            "build_index",
            "add_vectors",
            "save_index",
            "search",
        )
    ]
    rss_afters = [x for x in rss_afters if x is not None]
    peak_rss = max(rss_afters) if rss_afters else None

    total_duration = sum(
        v
        for v in [
            phases.get("load_corpus", {}).get("time_sec"),
            phases.get("build_index", {}).get("time_sec"),
            phases.get("add_vectors", {}).get("time_sec"),
            phases.get("save_index", {}).get("time_sec"),
            phases.get("search", {}).get("time_sec"),
        ]
        if v is not None
    )

    return {
        "dataset": dataset_tag,
        "index": cfg.get("index"),
        "heap": heap_tag,
        "nlist": cfg.get("nlist"),
        "nprobe": cfg.get("nprobe"),
        "pq_m": cfg.get("pq_m"),
        "pq_nbits": cfg.get("pq_nbits"),
        "hnsw_m": cfg.get("hnsw_m"),
        "hnsw_efc": cfg.get("hnsw_efc"),
        "hnsw_efs": cfg.get("hnsw_efs"),
        "load_corpus_s": phases.get("load_corpus", {}).get("time_sec"),
        "load_corpus_rss_mb": phases.get("load_corpus", {}).get("rss_delta_mb"),
        "recall@50": r_entry.get("mean"),
        # phase order: load -> build -> add -> save -> search (we capture add/save/search)
        "search_s": phases.get("search", {}).get("time_sec"),
        "search_rss_mb": phases.get("search", {}).get("rss_delta_mb"),
        "add_s": phases.get("add_vectors", {}).get("time_sec"),
        "add_rss_mb": phases.get("add_vectors", {}).get("rss_delta_mb"),
        "build_s": phases.get("build_index", {}).get("time_sec"),
        "save_s": phases.get("save_index", {}).get("time_sec"),
        "size_mb": phases.get("save_index", {}).get("size_mb"),
        "save_rss_mb": phases.get("save_index", {}).get("rss_delta_mb"),
        "total_duration": total_duration,
        "peak_rss_mb": peak_rss,
    }


def load_dataframe(root: Path) -> pd.DataFrame:
    rows = []
    for p in find_results(root):
        try:
            rows.append(parse_record(p, EVAL_K))
        except Exception as exc:  # pragma: no cover
            print(f"Skip {p}: {exc}")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    num_cols = [
        "nlist",
        "nprobe",
        "pq_m",
        "pq_nbits",
        "hnsw_m",
        "hnsw_efc",
        "hnsw_efs",
        "recall@50",
        "search_s",
        "search_rss_mb",
        "add_s",
        "add_rss_mb",
        "build_s",
        "save_s",
        "save_rss_mb",
        "size_mb",
        "total_duration",
        "peak_rss_mb",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Blank irrelevant params per index type for readability
    def _mask_unused(row):
        idx = row["index"]
        if idx == "flat":
            row["nlist"] = row["nprobe"] = row["pq_m"] = row["pq_nbits"] = None
            row["hnsw_m"] = row["hnsw_efc"] = row["hnsw_efs"] = None
        elif idx == "ivf_flat":
            row["pq_m"] = row["pq_nbits"] = None
            row["hnsw_m"] = row["hnsw_efc"] = row["hnsw_efs"] = None
        elif idx == "ivf_pq":
            row["hnsw_m"] = row["hnsw_efc"] = row["hnsw_efs"] = None
        elif idx == "hnsw":
            row["nlist"] = row["nprobe"] = row["pq_m"] = row["pq_nbits"] = None
        elif idx == "hnsw_pq":
            row["nlist"] = row["nprobe"] = None
        return row

    df = df.apply(_mask_unused, axis=1)
    return df


def df_to_markdown(df: pd.DataFrame) -> str:
    cols = [
        "heap",
        "index",
        "nlist",
        "nprobe",
        "pq_m",
        "pq_nbits",
        "hnsw_m",
        "hnsw_efc",
        "hnsw_efs",
        "load_corpus_s",
        "load_corpus_rss_mb",
        "recall@50",
        # chronological: build -> add -> save -> search
        "build_s",
        "add_s",
        "add_rss_mb",
        "save_s",
        "save_rss_mb",
        "search_s",
        "search_rss_mb",
        "peak_rss_mb",
        "size_mb",
        "total_duration",
    ]
    # keep only relevant columns (copy to avoid SettingWithCopy warnings)
    df = df.loc[:, cols].copy()
    # round numeric columns for readability
    for c in [
        "recall@50",
        "load_corpus_s",
        "load_corpus_rss_mb",
        "search_s",
        "search_rss_mb",
        "add_s",
        "add_rss_mb",
        "build_s",
        "save_s",
        "save_rss_mb",
        "size_mb",
        "peak_rss_mb",
    ]:
        if c in df.columns:
            df[c] = df[c].round(4 if c == "recall@50" else 3)
    if "total_duration" in df.columns:
        df["total_duration"] = df["total_duration"].apply(format_duration)
    return df.to_markdown(index=False)


def write_markdown(df: pd.DataFrame, dataset: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"faiss_msmarco_{dataset}.md"
    header = f"# MSMARCO {dataset} (1000 queries, Recall@{EVAL_K})\n"
    body = df_to_markdown(df)
    md_path.write_text(f"{header}\n{body}\n")
    print(f"Wrote {md_path}")


def main() -> None:
    df = load_dataframe(ROOT)
    if df.empty:
        print("No results found.")
        return

    for dataset, sub in df.groupby("dataset"):
        sub = sub.sort_values(["recall@50", "search_s"], ascending=[False, True])
        write_markdown(sub, dataset, OUT_DIR)


if __name__ == "__main__":
    main()
