#!/usr/bin/env python3
"""
ArcadeDB (JVector/LSM) benchmark on MSMARCO shards with phase timings and RSS snapshots.

Steps measured (time + RSS):
- load_corpus: placeholder timing for streaming ingest path
- load_queries: materialize 1,000 query vectors from shards
- create_db: create new ArcadeDB database
- ingest: insert vectors as vertices with id + vector (streamed in batches)
- create_index: create vector index (cosine) with given params
- build_graph_now: eagerly build the graph so warmup/search exclude lazy build
- warmup: single query to warm cache (no graph build expected)
- search: run 1,000 queries (k=50) with ground-truth recall
- close_db: close database after first search
- open_db: reopen existing database
- warmup_after_reopen: single query to warm cache (no graph build expected)
- search_after_reopen: run same 1,000 queries again
- close_db_final: final close

Outputs per run: results.json + results.md under db_root/param_dir/

Cosine only (embeddings are normalized).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:  # Optional dependency for more accurate RSS reporting
    import psutil
except Exception:  # pragma: no cover - fallback when psutil missing
    psutil = None

# -------------------------
# memory + timing helpers
# -------------------------


def rss_mb() -> float:
    if psutil:
        return psutil.Process().memory_info().rss / (1024 * 1024)
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return float("nan")


def timed_section(name: str, fn):
    start_t = time.perf_counter()
    start_rss = rss_mb()
    result = fn()
    end_rss = rss_mb()
    dur = time.perf_counter() - start_t
    print(
        f"[phase] {name:<18} time={dur:8.3f}s | rss_before={start_rss:8.1f} MB | rss_after={end_rss:8.1f} MB | delta={end_rss - start_rss:8.1f} MB"
    )
    return result, dur, start_rss, end_rss


# -------------------------
# dataset helpers (reuse MSMARCO shard layout)
# -------------------------

META_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.meta\.json")
GT_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.gt")


def _match_label(pattern: re.Pattern[str], name: str) -> str | None:
    m = pattern.match(name)
    if m:
        return m.group(1)
    return None


def _sort_key(path: Path, pattern: re.Pattern[str]) -> tuple[int, object]:
    label = _match_label(pattern, path.name)
    if label is None:
        return (2, path.name)
    if label.isdigit():
        return (0, int(label))
    return (1, label)


def resolve_dataset(dataset_dir: Path) -> tuple[List[dict], Path, int, str]:
    if not dataset_dir.is_dir():
        raise SystemExit(f"{dataset_dir} is not a directory")

    meta_files = sorted(
        dataset_dir.glob("msmarco-passages-*.meta.json"),
        key=lambda p: _sort_key(p, META_FILENAME_RE),
    )
    if not meta_files:
        raise SystemExit("No .meta.json found in dataset directory")
    meta_path = meta_files[-1]
    label = _match_label(META_FILENAME_RE, meta_path.name) or ""
    meta = json.loads(meta_path.read_text())
    dim = int(meta["dim"])

    gt_candidates = sorted(
        dataset_dir.glob("msmarco-passages-*.gt.jsonl"),
        key=lambda p: _sort_key(p, GT_FILENAME_RE),
    )
    if not gt_candidates:
        raise SystemExit("No GT jsonl found in dataset directory")
    gt_path = gt_candidates[-1]

    shard_pattern = (
        f"msmarco-passages-{label}.shard*.f32"
        if label
        else "msmarco-passages-*.shard*.f32"
    )
    shards = sorted(dataset_dir.glob(shard_pattern))
    if not shards:
        raise SystemExit("No shard files found (msmarco-passages-*.shard*.f32)")

    sources: List[dict] = []
    total = 0
    for path in shards:
        rows = (path.stat().st_size // 4) // dim
        sources.append({"path": path, "start": total, "count": rows})
        total += rows

    print(
        f"[dataset] label={label or 'unknown'} dim={dim} shards={len(sources)} rows={total}"
    )
    return sources, gt_path, dim, label


def load_queries(gt_path: Path, limit: int | None) -> List[int]:
    qids: List[int] = []
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and len(qids) >= limit:
                break
            obj = json.loads(line)
            qids.append(int(obj["query_id"]))
    return qids


def load_ground_truth(gt_path: Path) -> dict[int, List[int]]:
    gt: dict[int, List[int]] = {}
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            qid = int(obj["query_id"])
            gt[qid] = [int(e["doc_id"]) for e in obj.get("topk", [])]
    return gt


def materialize_queries(
    sources: List[dict], query_ids: List[int], dim: int
) -> np.ndarray:
    queries = np.empty((len(query_ids), dim), dtype=np.float32)
    shard_map: dict[Path, List[Tuple[int, int]]] = {}
    for qi, qid in enumerate(query_ids):
        for s in sources:
            start = s["start"]
            end = start + s["count"]
            if start <= qid < end:
                shard_map.setdefault(s["path"], []).append((qi, qid - start))
                break

    for s in sources:
        assigns = shard_map.get(s["path"])
        if not assigns:
            continue
        mm = np.memmap(s["path"], mode="r", dtype=np.float32, shape=(s["count"], dim))
        for qi, li in assigns:
            queries[qi] = mm[li]
        del mm
    return queries


def stream_shards(
    sources: List[dict],
    dim: int,
    batch_size: int,
    start_offset: int = 0,
    max_rows: int | None = None,
):
    """Yield (global_start, batch_view) slices from memmapped shards without loading all rows."""

    total_rows = sum(s["count"] for s in sources)
    if start_offset >= total_rows:
        return

    to_skip = start_offset
    remaining = max_rows if max_rows is not None else total_rows - start_offset

    for s in sources:
        if remaining <= 0:
            break

        shard_rows = s["count"]
        if to_skip >= shard_rows:
            to_skip -= shard_rows
            continue

        shard_skip = to_skip
        to_skip = 0

        take_total = min(shard_rows - shard_skip, remaining)
        if take_total <= 0:
            continue

        mm = np.memmap(s["path"], mode="r", dtype=np.float32, shape=(shard_rows, dim))
        start = shard_skip
        shard_limit = shard_skip + take_total
        while start < shard_limit:
            end = min(start + batch_size, shard_limit)
            yield s["start"] + start, mm[start:end]
            start = end
        del mm
        remaining -= take_total


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total / (1024 * 1024)


def prune_vecgraph_files(db_path: Path) -> None:
    """Keep only the newest vecgraph file if multiple exist to avoid reopen conflicts."""

    candidates = sorted(db_path.glob("*_vecgraph.*.vecgraph"))
    if len(candidates) <= 1:
        return
    keep = max(candidates, key=lambda p: p.stat().st_mtime)
    for p in candidates:
        if p == keep:
            continue
        try:
            p.unlink()
        except Exception:
            pass


# -------------------------
# ArcadeDB helpers
# -------------------------


def ingest_vectors_streaming(
    db,
    sources: List[dict],
    dim: int,
    count: int,
    batch_size: int = 100_000,
    to_java_float_array=None,
    start_offset: int = 0,
) -> int:
    """Stream shards in batches and ingest without holding the full corpus in RAM."""

    db.schema.get_or_create_vertex_type("VectorData")
    db.schema.get_or_create_property("VectorData", "id", "INTEGER")
    db.schema.get_or_create_property("VectorData", "vector", "ARRAY_OF_FLOATS")

    ingested = 0
    for base_id, batch in stream_shards(
        sources,
        dim=dim,
        batch_size=batch_size,
        start_offset=start_offset,
        max_rows=count,
    ):
        with db.transaction():
            for i, vec in enumerate(batch, start=base_id):
                if to_java_float_array is not None:
                    jvec = to_java_float_array(vec)
                else:
                    jvec = vec.tolist()
                v = db.new_vertex("VectorData")
                v.set("id", i)
                v.set("vector", jvec)
                v.save()
                ingested += 1
    return ingested


def create_index(
    db,
    dim: int,
    max_connections: int,
    beam_width: int,
    quantization: str,
    store_vectors_in_graph: bool = False,
    add_hierarchy: bool = False,
):
    quant = None if quantization.upper() == "NONE" else quantization.upper()
    return db.create_vector_index(
        vertex_type="VectorData",
        vector_property="vector",
        dimensions=dim,
        distance_function="cosine",
        max_connections=max_connections,
        beam_width=beam_width,
        quantization=quant,
        store_vectors_in_graph=store_vectors_in_graph,
        add_hierarchy=add_hierarchy,
    )


def warmup(
    index, queries: np.ndarray, overquery_factor: int, k: int, quantization: str
) -> dict:
    if len(queries) == 0:
        return {"warmup_queries": 0}
    if quantization.upper() == "PRODUCT":
        _ = index.find_nearest_approximate(
            queries[0], k=k, overquery_factor=overquery_factor
        )
    else:
        _ = index.find_nearest(queries[0], k=k, overquery_factor=overquery_factor)
    return {"warmup_queries": 1}


def search_index(
    index,
    queries: np.ndarray,
    qids: List[int],
    gt_full: dict[int, List[int]],
    k: int,
    overquery_factor: int,
    quantization: str,
) -> dict:
    latencies_ms: List[float] = []
    recalls: List[float] = []
    for qi, qid in enumerate(qids):
        qvec = queries[qi]
        t0 = time.perf_counter()
        if quantization.upper() == "PRODUCT":
            results = index.find_nearest_approximate(
                qvec, k=k, overquery_factor=overquery_factor
            )
        else:
            results = index.find_nearest(qvec, k=k, overquery_factor=overquery_factor)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

        result_ids = []
        for rec, _score in results:
            rid = rec.get("id") if hasattr(rec, "get") else None
            if rid is not None:
                result_ids.append(int(rid))
        gt_list = gt_full.get(qid)
        if not gt_list:
            continue
        retrieved = set(result_ids[:k])
        gt_set = set(gt_list[:k])
        recalls.append(len(retrieved & gt_set) / k)

    n = len(recalls)
    recall_mean = float(np.mean(recalls)) if recalls else None
    lat_mean = float(np.mean(latencies_ms)) if latencies_ms else None
    lat_p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else None
    return {
        "queries": len(qids),
        "recall_mean": recall_mean,
        "latency_ms_mean": lat_mean,
        "latency_ms_p95": lat_p95,
        "recall_count": n,
    }


# -------------------------
# main
# -------------------------


def main():
    ap = argparse.ArgumentParser(
        description="ArcadeDB vector benchmark on MSMARCO with phase timings + RSS"
    )
    ap.add_argument("--dataset-dir", required=True, help="Path to MSMARCO dataset dir")
    ap.add_argument(
        "--count",
        type=int,
        help="Override corpus count; default = dataset size (1M/10M/20M/100M)",
    )
    ap.add_argument(
        "--max-connections", type=int, default=32, help="JVector max_connections"
    )
    ap.add_argument("--beam-width", type=int, default=256, help="JVector beam_width")
    ap.add_argument(
        "--overquery-factor",
        type=int,
        default=16,
        help="overquery_factor used at search time (similar to efSearch)",
    )
    ap.add_argument(
        "--quantization",
        choices=["NONE", "INT8", "BINARY", "PRODUCT"],
        default="NONE",
        help="Quantization mode for index",
    )
    ap.add_argument(
        "--store-vectors-in-graph",
        action="store_true",
        help="Persist inline vectors inside the graph file (larger graph, faster reopen/search)",
    )
    ap.add_argument(
        "--add-hierarchy",
        action="store_true",
        help="Enable HNSW hierarchical layers (may increase build size/time, improves recall/latency)",
    )
    ap.add_argument(
        "--db-root",
        default="arcadedb_runs",
        help="Directory to place DBs and results",
    )
    ap.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    ap.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep DB directory after run (default cleans on success)",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=100_000,
        help="Number of vectors to ingest per transaction batch",
    )
    args = ap.parse_args()

    np.random.seed(args.seed)
    eval_k = 50

    # Import after potential JVM arg override
    import arcadedb_embedded as arcadedb

    sources, gt_path, dim, label = resolve_dataset(Path(args.dataset_dir))
    total_rows = sum(s["count"] for s in sources)
    count = args.count if args.count is not None else total_rows
    dataset_info = {
        "label": label or "dataset",
        "dim": dim,
        "shards": len(sources),
        "rows": total_rows,
    }

    # Sample queries
    qids = load_queries(gt_path, limit=1000)
    qids = [qid for qid in qids if qid < total_rows][:1000]
    gt_full = load_ground_truth(gt_path)
    qids = [qid for qid in qids if qid in gt_full][:1000]
    if not qids:
        raise SystemExit("No valid query IDs with ground truth found")

    phases: Dict[str, dict] = {}
    batch_size = args.batch_size

    def record(name: str, result, dur, rss_start, rss_end):
        phases[name] = {
            "time_sec": dur,
            "rss_before_mb": rss_start,
            "rss_after_mb": rss_end,
            "rss_delta_mb": rss_end - rss_start,
        }
        if isinstance(result, dict):
            phases[name].update(result)

    (queries, dur, r0, r1) = timed_section(
        "load_queries", lambda: materialize_queries(sources, qids, dim=dim)
    )
    record("load_queries", {"queries": len(queries)}, dur, r0, r1)

    # Prepare DB path
    param_dir = "_".join(
        [
            f"dataset={Path(args.dataset_dir).name}",
            f"label={label or 'dataset'}",
            f"maxconn={args.max_connections}",
            f"beam={args.beam_width}",
            f"oq={args.overquery_factor}",
            f"quant={args.quantization.lower()}",
            f"store={'on' if args.store_vectors_in_graph else 'off'}",
            f"hier={'on' if args.add_hierarchy else 'off'}",
            f"batch={batch_size}",
            f"seed={args.seed}",
        ]
    )
    db_root = Path(args.db_root)
    db_root.mkdir(parents=True, exist_ok=True)
    db_path = db_root / param_dir
    if db_path.exists() and not args.keep_db:
        shutil.rmtree(db_path)

    # Create DB
    (db, dur, r0, r1) = timed_section(
        "create_db", lambda: arcadedb.create_database(str(db_path))
    )
    record("create_db", {"db_path": str(db_path)}, dur, r0, r1)

    try:
        # Streaming ingestion does not preload the full corpus; record a near-zero load phase for visibility
        (_, dur, r0, r1) = timed_section("load_corpus", lambda: None)
        record("load_corpus", {}, dur, r0, r1)

        first_batch_rows = min(batch_size, count)

        (ingested_first, dur, r0, r1) = timed_section(
            "ingest_initial",
            lambda: ingest_vectors_streaming(
                db,
                sources,
                dim=dim,
                count=first_batch_rows,
                batch_size=batch_size,
                to_java_float_array=arcadedb.to_java_float_array,
                start_offset=0,
            ),
        )
        record("ingest_initial", {"rows": ingested_first, "offset": 0}, dur, r0, r1)

        remaining_rows = count - ingested_first
        if remaining_rows > 0:
            (ingested_rest, dur, r0, r1) = timed_section(
                "ingest_remaining",
                lambda: ingest_vectors_streaming(
                    db,
                    sources,
                    dim=dim,
                    count=remaining_rows,
                    batch_size=batch_size,
                    to_java_float_array=arcadedb.to_java_float_array,
                    start_offset=ingested_first,
                ),
            )
            record(
                "ingest_remaining",
                {"rows": ingested_rest, "offset": ingested_first},
                dur,
                r0,
                r1,
            )

        ingest_time = sum(
            phases[name]["time_sec"]
            for name in ("ingest_initial", "ingest_remaining")
            if name in phases
        )
        ingest_delta = sum(
            phases[name]["rss_delta_mb"]
            for name in ("ingest_initial", "ingest_remaining")
            if name in phases
        )
        phases["ingest"] = {
            "time_sec": ingest_time,
            "rss_before_mb": float("nan"),
            "rss_after_mb": float("nan"),
            "rss_delta_mb": ingest_delta,
            "rows": count,
            "batches": 2 if remaining_rows > 0 else 1,
            "batch_size": batch_size,
        }

        (index, dur, r0, r1) = timed_section(
            "create_index",
            lambda: create_index(
                db,
                dim=dim,
                max_connections=args.max_connections,
                beam_width=args.beam_width,
                quantization=args.quantization,
                store_vectors_in_graph=args.store_vectors_in_graph,
                add_hierarchy=args.add_hierarchy,
            ),
        )
        record(
            "create_index",
            {
                "max_connections": args.max_connections,
                "beam_width": args.beam_width,
                "quantization": args.quantization,
                "store_vectors_in_graph": args.store_vectors_in_graph,
                "add_hierarchy": args.add_hierarchy,
            },
            dur,
            r0,
            r1,
        )

        # Eagerly build the graph after all ingestion so warmup/query timings exclude lazy build cost.
        (_, dur, r0, r1) = timed_section(
            "build_graph_now", lambda: index.build_graph_now()
        )
        record("build_graph_now", {}, dur, r0, r1)

        # Warmup (single query)
        (warm_info, dur, r0, r1) = timed_section(
            "warmup",
            lambda: warmup(
                index, queries, args.overquery_factor, eval_k, args.quantization
            ),
        )
        record("warmup", warm_info, dur, r0, r1)

        # Search (1000 queries)
        (search_stats, dur, r0, r1) = timed_section(
            "search",
            lambda: search_index(
                index,
                queries,
                qids,
                gt_full,
                k=eval_k,
                overquery_factor=args.overquery_factor,
                quantization=args.quantization,
            ),
        )
        record("search", search_stats, dur, r0, r1)

        # Drop stale vecgraph files so reopen does not see duplicate slots when rebuild produced multiple files.
        prune_vecgraph_files(db_path)

        # Close DB
        (_, dur, r0, r1) = timed_section("close_db", lambda: db.close())
        record("close_db", {}, dur, r0, r1)
        db = None

        # Reopen
        (db, dur, r0, r1) = timed_section(
            "open_db", lambda: arcadedb.open_database(str(db_path))
        )
        record("open_db", {}, dur, r0, r1)

        # Warmup after reopen
        index = db.schema.get_vector_index("VectorData", "vector")

        (warm_info2, dur, r0, r1) = timed_section(
            "warmup_after_reopen",
            lambda: warmup(
                index, queries, args.overquery_factor, eval_k, args.quantization
            ),
        )
        record("warmup_after_reopen", warm_info2, dur, r0, r1)

        # Search after reopen
        (search_stats2, dur, r0, r1) = timed_section(
            "search_after_reopen",
            lambda: search_index(
                index,
                queries,
                qids,
                gt_full,
                k=eval_k,
                overquery_factor=args.overquery_factor,
                quantization=args.quantization,
            ),
        )
        record("search_after_reopen", search_stats2, dur, r0, r1)

    finally:
        if db is not None:
            try:
                (_, dur, r0, r1) = timed_section("close_db_final", lambda: db.close())
                record("close_db_final", {}, dur, r0, r1)
            except Exception:
                pass

    db_size = dir_size_mb(db_path)
    rss_after_vals = [
        v.get("rss_after_mb")
        for v in phases.values()
        if v.get("rss_after_mb") is not None
    ]
    peak_rss = max(rss_after_vals) if rss_after_vals else None

    recall_stats = {
        "search": {
            "mean": phases.get("search", {}).get("recall_mean"),
            "n": phases.get("search", {}).get("recall_count"),
        },
        "search_after_reopen": {
            "mean": phases.get("search_after_reopen", {}).get("recall_mean"),
            "n": phases.get("search_after_reopen", {}).get("recall_count"),
        },
    }

    latency_ms = {
        "search": {
            "mean": phases.get("search", {}).get("latency_ms_mean"),
            "p95": phases.get("search", {}).get("latency_ms_p95"),
        },
        "search_after_reopen": {
            "mean": phases.get("search_after_reopen", {}).get("latency_ms_mean"),
            "p95": phases.get("search_after_reopen", {}).get("latency_ms_p95"),
        },
    }

    config_info = {
        "max_connections": args.max_connections,
        "beam_width": args.beam_width,
        "overquery_factor": args.overquery_factor,
        "quantization": args.quantization,
        "store_vectors_in_graph": args.store_vectors_in_graph,
        "add_hierarchy": args.add_hierarchy,
        "batch_size": batch_size,
        "count": count,
        "queries": len(qids),
        "k": eval_k,
        "seed": args.seed,
    }

    results = {
        "dataset": dataset_info,
        "config": config_info,
        "phases": phases,
        "recall": recall_stats,
        "latency_ms": latency_ms,
        "db_path": str(db_path),
        "db_size_mb": db_size,
    }

    save_root = db_path
    save_root.mkdir(parents=True, exist_ok=True)
    results_json = save_root / "results.json"
    results_json.write_text(json.dumps(results, indent=2))

    md_lines = [
        f"# ArcadeDB benchmark ({dataset_info['label']})",
        "",
        "## Dataset",
        f"- label: {dataset_info['label']}",
        f"- dim: {dataset_info['dim']}",
        f"- shards: {dataset_info['shards']}",
        f"- rows: {dataset_info['rows']}",
        "",
        "## Config",
        f"- max_connections: {config_info['max_connections']}",
        f"- beam_width: {config_info['beam_width']}",
        f"- overquery_factor: {config_info['overquery_factor']}",
        f"- quantization: {config_info['quantization']}",
        f"- store_vectors_in_graph: {config_info['store_vectors_in_graph']}",
        f"- add_hierarchy: {config_info['add_hierarchy']}",
        f"- batch_size: {config_info['batch_size']}",
        f"- count: {config_info['count']}",
        f"- queries: {config_info['queries']}",
        f"- k: {config_info['k']}",
        f"- seed: {config_info['seed']}",
        "",
        "## Phases (time sec / RSS MB)",
    ]

    phase_order = [
        "load_queries",
        "create_db",
        "load_corpus",
        "ingest_initial",
        "ingest_remaining",
        "ingest",
        "create_index",
        "build_graph_now",
        "warmup",
        "search",
        "close_db",
        "open_db",
        "warmup_after_reopen",
        "search_after_reopen",
        "close_db_final",
    ]

    for name in phase_order:
        if name not in phases:
            continue
        p = phases[name]
        line = (
            f"- {name}: time={p['time_sec']:.3f}s, rss_before={p['rss_before_mb']:.1f} MB, "
            f"rss_after={p['rss_after_mb']:.1f} MB, delta={p['rss_delta_mb']:.1f} MB"
        )
        if "recall_mean" in p:
            line += f", recall@{eval_k}={p['recall_mean']:.4f}"
        if "latency_ms_mean" in p and p["latency_ms_mean"] is not None:
            line += f", latency_ms={p['latency_ms_mean']:.2f}"
        md_lines.append(line)

    md_lines.extend(
        [
            "",
            "## Recall",
            (
                f"- search: {recall_stats['search']['mean']:.4f} (n={recall_stats['search']['n']})"
                if recall_stats["search"]["mean"] is not None
                else "- search: n/a"
            ),
            (
                f"- search_after_reopen: {recall_stats['search_after_reopen']['mean']:.4f} (n={recall_stats['search_after_reopen']['n']})"
                if recall_stats["search_after_reopen"]["mean"] is not None
                else "- search_after_reopen: n/a"
            ),
            "",
            "## Latency (ms)",
            (
                f"- search mean: {latency_ms['search']['mean']:.2f} | p95: {latency_ms['search']['p95']:.2f}"
                if latency_ms["search"]["mean"] is not None
                else "- search: n/a"
            ),
            (
                f"- search_after_reopen mean: {latency_ms['search_after_reopen']['mean']:.2f} | p95: {latency_ms['search_after_reopen']['p95']:.2f}"
                if latency_ms["search_after_reopen"]["mean"] is not None
                else "- search_after_reopen: n/a"
            ),
            "",
            f"- db_path: {db_path}",
            f"- db_size_mb: {db_size:.1f}",
            f"- peak_rss_mb: {peak_rss:.1f}",
        ]
    )

    results_md = save_root / "results.md"
    results_md.write_text("\n".join(md_lines))
    print(f"Wrote {results_json}")
    print(f"Wrote {results_md}")


if __name__ == "__main__":
    main()
