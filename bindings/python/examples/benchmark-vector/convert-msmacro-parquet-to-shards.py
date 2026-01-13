#!/usr/bin/env python3
"""
Convert pre-downloaded MSMARCO v2.1 parquet parts into raw shard files (FIXED).

Key properties:
- Batched Arrow → NumPy iteration (no per-row Python objects)
- Vectorized cosine normalization
- Flat, predictable RSS usage
- Optional O_DSYNC writes (--direct)

To download the parquet parts first:

```
HF_HOME=/mnt/ssd2/hf_cache
mkdir -p "$HF_HOME"

from datasets import load_dataset
load_dataset(
    "Cohere/msmarco-v2.1-embed-english-v3",
    "passages",
    split="train",
    streaming=False,
    cache_dir="$HF_HOME")
```

Usage:
    HF_HOME=/path/to/hf_cache \
    python convert-msmarco-parquet-to-shards.py \
        --parquet-glob "$HF_HOME/datasets/Cohere___msmarco-v2.1-embed-english-v3/passages_parquet/*.parquet" \
        --out-dir datasets \
        --count 10_000_000 \
        --shard-size 100000 \
        --batch-rows 8192 \
        --fsync-every 50000 \
        --direct
"""

from __future__ import annotations

import argparse
import glob
import heapq
import json
import mmap
import os
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

# ---------------- constants ----------------

TOPK = 50
Q_COUNT = 1000
CHUNK = 4096
PROGRESS_EVERY = 100_000

# ---------------- helpers ----------------


def fmt_secs(secs: float | None) -> str:
    if secs is None or secs <= 0:
        return "?"
    m, s = divmod(int(secs + 0.5), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def sync_and_advise(fd: int) -> None:
    try:
        os.fsync(fd)
    except OSError:
        pass
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    except (AttributeError, OSError):
        pass


def close_memmap(mm: np.memmap | None) -> None:
    if mm is None:
        return
    mm.flush()
    m = getattr(mm, "_mmap", None)
    if m is not None:
        try:
            m.madvise(mmap.MADV_DONTNEED)
        except Exception:
            pass
        m.close()


# ---------------- writer ----------------


class DirectWriter:
    def __init__(self, path: Path, direct: bool):
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if direct and hasattr(os, "O_DSYNC"):
            flags |= os.O_DSYNC
        self.fd = os.open(path, flags, 0o644)

    def write(self, b: bytes) -> None:
        mv = memoryview(b)
        off = 0
        while off < len(mv):
            n = os.write(self.fd, mv[off:])
            if n == 0:
                raise OSError("write returned 0")
            off += n

    def fileno(self) -> int:
        return self.fd

    def close(self) -> None:
        os.close(self.fd)


def open_writer(path: Path, direct: bool):
    if direct:
        return DirectWriter(path, direct=True)
    return open(path, "wb", buffering=1 << 20)


# ---------------- GT computation ----------------


def build_gt_sharded(
    shards: list[dict],
    total_count: int,
    dim: int,
    gt_path: Path,
    q_count: int,
    topk: int,
):
    print(f"[GT] building exact GT for {q_count} queries, k={topk}")

    q_count = min(q_count, total_count)
    rng = np.random.default_rng()
    q_indices = rng.choice(total_count, size=q_count, replace=False)

    # Load query vectors
    queries = np.empty((q_count, dim), dtype=np.float32)
    shard_map = {}

    for qi, gidx in enumerate(q_indices):
        for s in shards:
            if s["start"] <= gidx < s["start"] + s["count"]:
                shard_map.setdefault(s["path"], []).append((qi, gidx - s["start"]))
                break

    for s in shards:
        assigns = shard_map.get(s["path"])
        if not assigns:
            continue
        mm = np.memmap(s["path"], dtype=np.float32, mode="r", shape=(s["count"], dim))
        for qi, li in assigns:
            queries[qi] = mm[li]
        close_memmap(mm)

    # Top-k heaps
    heaps = [[] for _ in range(q_count)]

    for s in shards:
        print(f"[GT] scanning {s['path'].name}")
        mm = np.memmap(s["path"], dtype=np.float32, mode="r", shape=(s["count"], dim))
        for off in range(0, s["count"], CHUNK):
            block = mm[off : off + CHUNK]
            sims = block @ queries.T
            for qi in range(q_count):
                heap = heaps[qi]
                col = sims[:, qi]
                for i, score in enumerate(col):
                    doc_id = s["start"] + off + i
                    if len(heap) < topk:
                        heapq.heappush(heap, (score, doc_id))
                    else:
                        heapq.heappushpop(heap, (score, doc_id))
        close_memmap(mm)

    with open(gt_path, "w") as f:
        for qi, heap in enumerate(heaps):
            heap.sort(reverse=True)
            json.dump(
                {
                    "query_id": int(q_indices[qi]),
                    "topk": [{"doc_id": int(d), "score": float(s)} for s, d in heap],
                },
                f,
            )
            f.write("\n")

    print(f"[GT] wrote {gt_path}")


# ---------------- main ----------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet-glob", required=True)
    ap.add_argument("--out-dir", default="datasets")
    ap.add_argument("--count", default="1_000_000")
    ap.add_argument("--shard-size", type=int, default=100_000)
    ap.add_argument("--batch-rows", type=int, default=8192)
    ap.add_argument("--fsync-every", type=int, default=50_000)
    ap.add_argument("--direct", action="store_true")
    args = ap.parse_args()

    count = int(str(args.count).replace("_", ""))
    shard_size = args.shard_size

    parquet_files = sorted(glob.glob(args.parquet_glob))
    if not parquet_files:
        raise SystemExit("No parquet files found")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[init] Found {len(parquet_files)} parquet files to process")

    dim = None
    written = 0
    filled = 0
    shard_idx = 0
    shard_start = 0
    shards = []

    writer = None
    path = None

    t0 = time.time()
    last_report = 0

    # Process files one at a time; use ParquetFile iter_batches to avoid list offset overflow in datasets
    for file_idx, parquet_file in enumerate(parquet_files):
        if written >= count:
            break

        print(
            f"[process] File {file_idx + 1}/{len(parquet_files)}: {Path(parquet_file).name}"
        )

        pf = pq.ParquetFile(parquet_file)

        for record_batch in pf.iter_batches(
            columns=["emb"], batch_size=args.batch_rows
        ):
            col = record_batch.column(0)  # ListArray
            offsets = col.offsets.to_numpy()
            values = np.asarray(
                col.values.to_numpy(zero_copy_only=False), dtype=np.float32
            )

            # Infer dimension from first batch if unknown
            if dim is None:
                dim = int(offsets[1] - offsets[0])
                path = out_dir / f"msmarco-passages-{count}.shard{shard_idx:04d}.f32"
                writer = open_writer(path, args.direct)

            # Validate fixed-size lists
            spans = offsets[1:] - offsets[:-1]
            if not np.all(spans == dim):
                raise RuntimeError(
                    f"Non-uniform embedding dimension detected in {parquet_file}"
                )

            # Ensure a writable, contiguous float32 view before normalization
            embs = np.asarray(values, dtype=np.float32).reshape(-1, dim)
            embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12)
            embs = np.ascontiguousarray(embs)

            off = 0
            while off < len(embs) and written < count:
                take = min(shard_size - filled, count - written, len(embs) - off)
                writer.write(embs[off : off + take].tobytes(order="C"))
                off += take
                filled += take
                written += take

                if written % args.fsync_every == 0:
                    sync_and_advise(writer.fileno())

                if filled == shard_size and written < count:
                    sync_and_advise(writer.fileno())
                    writer.close()
                    shards.append({"path": path, "count": filled, "start": shard_start})
                    shard_start += filled
                    shard_idx += 1
                    filled = 0
                    path = (
                        out_dir / f"msmarco-passages-{count}.shard{shard_idx:04d}.f32"
                    )
                    writer = open_writer(path, args.direct)

            if written - last_report >= PROGRESS_EVERY:
                elapsed = time.time() - t0
                rate = written / elapsed
                eta = (count - written) / rate if rate else None
                print(
                    f"[convert] {written:,}/{count:,} | {rate:,.0f} v/s | eta {fmt_secs(eta)}"
                )
                last_report = written

            if written >= count:
                break

    if writer is not None:
        sync_and_advise(writer.fileno())
        writer.close()
        if filled > 0:
            shards.append({"path": path, "count": filled, "start": shard_start})

    meta = {
        "dim": dim,
        "dtype": "float32",
        "count": written,
        "shard_size": shard_size,
    }
    (out_dir / f"msmarco-passages-{count}.meta.json").write_text(json.dumps(meta))

    print(f"[done] wrote {written:,} vectors across {len(shards)} shards")

    build_gt_sharded(
        shards=shards,
        total_count=written,
        dim=dim,
        gt_path=out_dir / f"msmarco-passages-{count}.gt.jsonl",
        q_count=Q_COUNT,
        topk=TOPK,
    )


if __name__ == "__main__":
    main()
