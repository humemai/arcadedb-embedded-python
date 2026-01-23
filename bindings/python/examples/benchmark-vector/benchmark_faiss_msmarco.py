#!/usr/bin/env python3
"""
FAISS benchmark on MSMARCO shards with phase-level timing and memory snapshots.

Phases captured:
- load_corpus: read shards into a contiguous float32 array (count derived from dataset unless overridden)
- build_index: construct FAISS index (Flat, HNSW, IVF-Flat, IVF-PQ, HNSW-PQ)
- add_vectors: add corpus to index
- search: run 1,000 queries (GT-provided) with k=50, compute R@50

Example:
    python benchmark_faiss_msmarco.py \
        --dataset-dir datasets/MSMARCO-10M \
        --index hnsw \
        --hnsw-m 32 \
        --hnsw-efc 200 \
        --hnsw-efs 80

Notes:
- Uses the dataset metadata (msmarco-passages-*.meta.json) to infer dimension.
- Uses GT file (msmarco-passages-*.gt.jsonl) to pick query rows from corpus.
- Memory is sampled from psutil if available; otherwise uses resource.getrusage().
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:  # Optional dependency for more accurate RSS reporting
    import psutil
except Exception:  # pragma: no cover - fallback when psutil missing
    psutil = None

try:
    import faiss
except ImportError as exc:  # pragma: no cover
    raise SystemExit("faiss is required (uv pip install faiss-cpu)") from exc

META_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.meta\.json")
GT_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.gt")


# -------------------------
# memory + timing helpers
# -------------------------


def rss_mb() -> float:
    if psutil:
        return psutil.Process().memory_info().rss / (1024 * 1024)
    # Fallback to resource on POSIX
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
        f"[phase] {name:<12} time={dur:8.3f}s | rss_before={start_rss:8.1f} MB | rss_after={end_rss:8.1f} MB | delta={end_rss - start_rss:8.1f} MB"
    )
    return result, dur, start_rss, end_rss


# -------------------------
# dataset helpers
# -------------------------


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
    sources: List[dict], dim: int, batch_size: int, max_rows: int | None = None
):
    """Yield (global_start, batch_view) slices from memmapped shards without loading all rows."""

    remaining = max_rows if max_rows is not None else sum(s["count"] for s in sources)
    for s in sources:
        if remaining <= 0:
            break
        take_total = min(s["count"], remaining)
        if take_total <= 0:
            continue
        mm = np.memmap(s["path"], mode="r", dtype=np.float32, shape=(s["count"], dim))
        start = 0
        while start < take_total:
            end = min(start + batch_size, take_total)
            yield s["start"] + start, mm[start:end]
            start = end
        del mm
        remaining -= take_total


def sample_training_data(
    sources: List[dict], dim: int, count: int, batch_size: int, sample_size: int
) -> np.ndarray:
    """Collect a training sample by streaming across shards."""

    sample_size = min(sample_size, count)
    chunks: list[np.ndarray] = []
    collected = 0
    for _, batch in stream_shards(
        sources, dim=dim, batch_size=batch_size, max_rows=count
    ):
        need = sample_size - collected
        if need <= 0:
            break
        take = min(need, batch.shape[0])
        chunks.append(np.array(batch[:take], copy=True))
        collected += take
        if collected >= sample_size:
            break
    if collected == 0:
        raise RuntimeError("No training data collected")
    return np.vstack(chunks)


IVF_DEFAULT_NLIST = 1024
IVF_DEFAULT_NPROBE = 64
PQ_DEFAULT_M = 16
PQ_DEFAULT_NBITS = 8
BATCH_SIZE_DEFAULT = 100_000
TRAIN_SAMPLE_MAX = 300_000
TRAIN_SAMPLE_MIN = 50_000
TRAIN_SAMPLE_RATIO = 0.05


# -------------------------
# FAISS helpers
# -------------------------


def build_index(
    dim: int,
    index_kind: str,
    metric: str,
    hnsw_m: int,
    hnsw_efc: int,
    hnsw_efs: int,
    nlist: int,
    nprobe: int,
    pq_m: int,
    pq_nbits: int,
):
    if metric == "ip":
        mcode = faiss.METRIC_INNER_PRODUCT
    elif metric == "l2":
        mcode = faiss.METRIC_L2
    else:
        raise SystemExit("metric must be ip or l2")

    if index_kind == "flat":
        index = faiss.IndexFlatIP(dim) if metric == "ip" else faiss.IndexFlatL2(dim)

    elif index_kind == "hnsw":
        index = faiss.IndexHNSWFlat(dim, hnsw_m, mcode)
        index.hnsw.efConstruction = hnsw_efc
        index.hnsw.efSearch = hnsw_efs

    elif index_kind == "ivf_flat":
        quantizer = faiss.IndexFlatIP(dim) if metric == "ip" else faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, mcode)
        index.nprobe = nprobe

    elif index_kind == "ivf_pq":
        quantizer = faiss.IndexFlatIP(dim) if metric == "ip" else faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFPQ(quantizer, dim, nlist, pq_m, pq_nbits, mcode)
        index.nprobe = nprobe

    elif index_kind == "hnsw_pq":
        index = faiss.IndexHNSWPQ(dim, pq_m, hnsw_m, pq_nbits, mcode)
        index.hnsw.efConstruction = hnsw_efc
        index.hnsw.efSearch = hnsw_efs

    else:
        raise SystemExit("index must be one of flat, hnsw, ivf_flat, ivf_pq, hnsw_pq")

    return index


def add_vectors_streaming(
    index,
    index_kind: str,
    sources: List[dict],
    dim: int,
    count: int,
    batch_size: int,
    train_data: np.ndarray | None,
):
    """Train if needed, then add vectors in streaming batches."""

    if index_kind in {"ivf_flat", "ivf_pq", "hnsw_pq"}:
        if train_data is None:
            raise RuntimeError("Training data required for IVF/PQ indexes")
        if not index.is_trained:
            index.train(train_data)

    added = 0
    for _, batch in stream_shards(
        sources, dim=dim, batch_size=batch_size, max_rows=count
    ):
        index.add(batch)
        added += batch.shape[0]
        if added >= count:
            break
    return added


# -------------------------
# main
# -------------------------


def main():
    ap = argparse.ArgumentParser(
        description="FAISS benchmark with phase timings + RSS snapshots"
    )
    ap.add_argument(
        "--dataset-dir",
        required=True,
        help="Path to MSMARCO dataset directory (with shards/meta/gt)",
    )
    ap.add_argument(
        "--count",
        type=int,
        help="Override corpus count; default = dataset size (1M/10M/100M)",
    )
    ap.add_argument(
        "--index",
        choices=["flat", "hnsw", "ivf_flat", "ivf_pq", "hnsw_pq"],
        default="hnsw",
        help="FAISS index type (cosine via inner product)",
    )
    ap.add_argument("--hnsw-m", type=int, default=32, help="HNSW M (graph degree)")
    ap.add_argument("--hnsw-efc", type=int, default=200, help="HNSW efConstruction")
    ap.add_argument("--hnsw-efs", type=int, default=80, help="HNSW efSearch")
    ap.add_argument(
        "--nlist",
        type=int,
        default=IVF_DEFAULT_NLIST,
        help="IVF nlist (coarse centroids)",
    )
    ap.add_argument(
        "--nprobe",
        type=int,
        default=IVF_DEFAULT_NPROBE,
        help="IVF nprobe (searched lists)",
    )
    ap.add_argument(
        "--pq-m",
        type=int,
        default=PQ_DEFAULT_M,
        help="PQ subquantizers (must divide dim)",
    )
    ap.add_argument(
        "--pq-nbits", type=int, default=PQ_DEFAULT_NBITS, help="PQ bits per subvector"
    )
    ap.add_argument(
        "--seed", type=int, default=42, help="Random seed for query sampling"
    )
    ap.add_argument(
        "--save-dir",
        default="my_test_databases",
        help="Directory to store saved FAISS indexes (auto-creates a param-specific subdir)",
    )
    args = ap.parse_args()

    np.random.seed(args.seed)
    eval_ks = [50]
    max_k = 50
    metric = "ip"  # embeddings are normalized; inner product corresponds to cosine

    sources, gt_path, dim, label = resolve_dataset(Path(args.dataset_dir))
    total_rows = sum(s["count"] for s in sources)
    count = args.count if args.count is not None else total_rows
    dataset_info = {
        "label": label or "dataset",
        "dim": dim,
        "shards": len(sources),
        "rows": total_rows,
    }

    # Training sample for IVF/PQ (and harmless for others)
    train_sample_size = min(
        count,
        max(
            TRAIN_SAMPLE_MIN,
            min(int(count * TRAIN_SAMPLE_RATIO), TRAIN_SAMPLE_MAX),
        ),
    )
    config_info = {
        "index": args.index,
        "count": count,
        "queries": 1000,
        "k": max_k,
        "eval_k": eval_ks,
        "hnsw_m": args.hnsw_m,
        "hnsw_efc": args.hnsw_efc,
        "hnsw_efs": args.hnsw_efs,
        "nlist": args.nlist,
        "nprobe": args.nprobe,
        "pq_m": args.pq_m,
        "pq_nbits": args.pq_nbits,
        "seed": args.seed,
        "batch_size": BATCH_SIZE_DEFAULT,
        "train_sample": train_sample_size,
    }

    print(
        f"[config] index={args.index} metric=ip count={count} queries=1000 k={max_k} eval_k={eval_ks} "
        f"hnsw(M={args.hnsw_m}, efc={args.hnsw_efc}, efs={args.hnsw_efs}) "
        f"ivf(nlist={args.nlist}, nprobe={args.nprobe}) pq(m={args.pq_m}, nbits={args.pq_nbits}) "
        f"batch={BATCH_SIZE_DEFAULT} train_sample={train_sample_size}"
    )
    (train_data, load_data_dur, load_data_rss_start, load_data_rss_end) = timed_section(
        "load_corpus",
        lambda: sample_training_data(
            sources,
            dim=dim,
            count=count,
            batch_size=BATCH_SIZE_DEFAULT,
            sample_size=train_sample_size,
        ),
    )

    # Prepare queries
    qids = load_queries(gt_path, limit=1000)  # GT file is 1000 rows; keep consistent
    qids = [qid for qid in qids if qid < total_rows][:1000]
    if not qids:
        raise SystemExit("No valid query IDs found")
    gt_full = load_ground_truth(gt_path)
    qids = [qid for qid in qids if qid in gt_full][:1000]
    if not qids:
        raise SystemExit("No valid query IDs with ground truth found")
    (queries, load_q_dur, load_q_rss_start, load_q_rss_end) = timed_section(
        "load_queries",
        lambda: materialize_queries(sources, qids, dim=dim),
    )

    # Build index
    index = build_index(
        dim=dim,
        index_kind=args.index,
        metric=metric,
        hnsw_m=args.hnsw_m,
        hnsw_efc=args.hnsw_efc,
        hnsw_efs=args.hnsw_efs,
        nlist=args.nlist,
        nprobe=args.nprobe,
        pq_m=args.pq_m,
        pq_nbits=args.pq_nbits,
    )
    (_, build_dur, build_rss_start, build_rss_end) = timed_section(
        "build_index",
        lambda: index,  # creation only; training happens during add for IVF/PQ
    )

    # Add vectors (store)
    (_, add_dur, add_rss_start, add_rss_end) = timed_section(
        "add_vectors",
        lambda: add_vectors_streaming(
            index,
            index_kind=args.index,
            sources=sources,
            dim=dim,
            count=count,
            batch_size=BATCH_SIZE_DEFAULT,
            train_data=train_data,
        ),
    )

    # Save index to disk (mandatory)
    param_dir_components = [
        f"dataset={Path(args.dataset_dir).name}",
        f"label={label or 'dataset'}",
        f"index={args.index}",
        f"count={count}",
        f"nlist={args.nlist}",
        f"nprobe={args.nprobe}",
        f"pq_m={args.pq_m}",
        f"pq_nbits={args.pq_nbits}",
        f"hnsw_m={args.hnsw_m}",
        f"hnsw_efc={args.hnsw_efc}",
        f"hnsw_efs={args.hnsw_efs}",
        f"seed={args.seed}",
    ]
    param_dir = "_".join(param_dir_components)
    save_root = Path(args.save_dir)
    save_root.mkdir(parents=True, exist_ok=True)
    save_dir = save_root / param_dir
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"faiss-{label or 'dataset'}-{args.index}-ip-{count}.index"

    def _save():
        if save_path.exists():
            save_path.unlink()
        faiss.write_index(index, str(save_path))

    (_, save_dur, save_rss_start, save_rss_end) = timed_section("save_index", _save)
    save_size_mb = save_path.stat().st_size / (1024 * 1024)

    # Search
    def _search():
        # ensure efSearch for HNSW
        if hasattr(index, "hnsw"):
            index.hnsw.efSearch = args.hnsw_efs
        if hasattr(index, "nprobe"):
            index.nprobe = args.nprobe
        return index.search(queries, max_k)

    (search_result, search_dur, search_rss_start, search_rss_end) = timed_section(
        "search", _search
    )
    distances, ids = search_result
    queries_count = len(qids)
    latency_ms_mean = (search_dur / queries_count * 1000) if queries_count else None

    # Recall@K
    recalls: dict[int, List[float]] = {k: [] for k in eval_ks}
    for qi, qid in enumerate(qids):
        gt_list = gt_full.get(qid)
        if not gt_list:
            continue
        for k in eval_ks:
            retrieved = set(int(x) for x in ids[qi, :k] if x >= 0)
            gt_set = set(gt_list[:k])
            if k == 0:
                continue
            recalls[k].append(len(retrieved & gt_set) / k)

    phase_stats = {
        "load_corpus": {
            "time_sec": load_data_dur,
            "rss_before_mb": load_data_rss_start,
            "rss_after_mb": load_data_rss_end,
            "rss_delta_mb": load_data_rss_end - load_data_rss_start,
            "rows": int(train_data.shape[0]),
        },
        "load_queries": {
            "time_sec": load_q_dur,
            "rss_before_mb": load_q_rss_start,
            "rss_after_mb": load_q_rss_end,
            "rss_delta_mb": load_q_rss_end - load_q_rss_start,
        },
        "build_index": {
            "time_sec": build_dur,
            "rss_before_mb": build_rss_start,
            "rss_after_mb": build_rss_end,
            "rss_delta_mb": build_rss_end - build_rss_start,
        },
        "add_vectors": {
            "time_sec": add_dur,
            "rss_before_mb": add_rss_start,
            "rss_after_mb": add_rss_end,
            "rss_delta_mb": add_rss_end - add_rss_start,
            "rows": count,
        },
        "save_index": {
            "time_sec": save_dur,
            "rss_before_mb": save_rss_start,
            "rss_after_mb": save_rss_end,
            "rss_delta_mb": save_rss_end - save_rss_start,
            "size_mb": save_size_mb,
            "path": str(save_path),
        },
        "search": {
            "time_sec": search_dur,
            "rss_before_mb": search_rss_start,
            "rss_after_mb": search_rss_end,
            "rss_delta_mb": search_rss_end - search_rss_start,
            "latency_ms_mean": latency_ms_mean,
        },
    }

    recall_stats = {
        k: {"mean": float(np.mean(vals)) if vals else None, "n": len(vals)}
        for k, vals in recalls.items()
    }

    print("\nSummary (seconds / MB):")
    print(
        f"  load_corpus : time={load_data_dur:8.3f}s | delta_rss={load_data_rss_end - load_data_rss_start:8.1f} MB"
    )
    print(
        f"  load_queries: time={load_q_dur:8.3f}s | delta_rss={load_q_rss_end - load_q_rss_start:8.1f} MB"
    )
    print(
        f"  build_index : time={build_dur:8.3f}s | delta_rss={build_rss_end - build_rss_start:8.1f} MB"
    )
    print(
        f"  add_vectors : time={add_dur:8.3f}s | delta_rss={add_rss_end - add_rss_start:8.1f} MB"
    )
    print(
        f"  save_index  : time={save_dur:8.3f}s | delta_rss={save_rss_end - save_rss_start:8.1f} MB | size={save_size_mb:8.1f} MB"
    )
    print(
        f"  search      : time={search_dur:8.3f}s | delta_rss={search_rss_end - search_rss_start:8.1f} MB"
    )
    print("  recall:")
    for k in eval_ks:
        vals = recalls.get(k) or []
        if vals:
            print(f"    R@{k:<3}: {np.mean(vals):.4f} (n={len(vals)})")
        else:
            print(f"    R@{k:<3}: n/a")

    results = {
        "dataset": dataset_info,
        "config": config_info,
        "phases": phase_stats,
        "recall": recall_stats,
        "latency_ms": {"search": {"mean": latency_ms_mean, "p95": None}},
        "save_dir": str(save_dir),
        "index_path": str(save_path),
    }

    results_json = save_dir / "results.json"
    results_json.write_text(json.dumps(results, indent=2))

    md_lines = [
        f"# FAISS benchmark ({dataset_info['label']})",
        "",
        "## Dataset",
        f"- label: {dataset_info['label']}",
        f"- dim: {dataset_info['dim']}",
        f"- shards: {dataset_info['shards']}",
        f"- rows: {dataset_info['rows']}",
        "",
        "## Config",
        f"- index: {config_info['index']}",
        f"- count: {config_info['count']}",
        f"- queries: {config_info['queries']}",
        f"- k: {config_info['k']}",
        f"- eval_k: {config_info['eval_k']}",
        f"- hnsw: M={config_info['hnsw_m']}, efc={config_info['hnsw_efc']}, efs={config_info['hnsw_efs']}",
        f"- ivf: nlist={config_info['nlist']}, nprobe={config_info['nprobe']}",
        f"- pq: m={config_info['pq_m']}, nbits={config_info['pq_nbits']}",
        f"- seed: {config_info['seed']}",
        "",
        "## Phases (time sec / RSS MB)",
    ]

    for name in [
        "load_corpus",
        "load_queries",
        "build_index",
        "add_vectors",
        "save_index",
        "search",
    ]:
        p = phase_stats[name]
        line = (
            f"- {name}: time={p['time_sec']:.3f}s, rss_before={p['rss_before_mb']:.1f} MB, "
            f"rss_after={p['rss_after_mb']:.1f} MB, delta={p['rss_delta_mb']:.1f} MB"
        )
        if name == "save_index":
            line += f", size={p['size_mb']:.1f} MB"
        md_lines.append(line)

    md_lines.append("")
    md_lines.append("## Recall")
    for k, stats in recall_stats.items():
        if stats["mean"] is None:
            md_lines.append(f"- R@{k}: n/a")
        else:
            md_lines.append(f"- R@{k}: {stats['mean']:.4f} (n={stats['n']})")

    md_lines.extend(
        [
            "",
            "## Outputs",
            f"- index: {save_path}",
            f"- results json: {results_json}",
        ]
    )

    results_md = save_dir / "results.md"
    results_md.write_text("\n".join(md_lines))


if __name__ == "__main__":
    main()
