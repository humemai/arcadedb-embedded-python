#!/usr/bin/env python3
"""Export the frozen benchmark rows as one JSON for the humem.ai project page.

The project page must not hard-code measurements. It reads this file, so a
re-measure is `python export_web.py` plus a copy, and no prose gets edited.

Two rules this file exists to enforce:

1. **Numbers come from the frozen CSV, never from prose.** `runs_paper.csv` is
   written by `make_paper_tables.py` under the canonical-row rule (newest
   `ts_utc` per lane/scale/n_docs/workload/backend/gav/rep), so a table and the
   page cannot disagree about which run they describe.

2. **Every comparator carries its image digest.** The CSV's own
   `engine_version` column is not publishable: `qdrant_dense` records `?`,
   sparse Qdrant and Milvus record only `"qdrant"`/`"milvus"`, and
   `l1 arcadedb_server` records `"server:latest"` while actually running a
   pinned digest. "Which version did you benchmark?" is the first question a
   vendor asks about a public comparison, and a sha256 digest answers it
   better than any version string. The digests are taken from `runner.py`'s
   `BACKENDS`, which is what the harness actually pulled.

Anything the data cannot support is omitted rather than guessed. `host` is
recorded on only two of seven lanes, so per-lane host is emitted only where it
exists, and the page says so instead of implying a uniform environment.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runner import BACKENDS  # noqa: E402  (path set above)

FROZEN = HERE / "results" / "runs_paper.csv"
OUT = HERE / "results" / "web_benchmarks.json"

# Version names live as trailing comments beside each pin in runner.py; the
# digest is authoritative and the name is a convenience, so a missing name is
# reported as null rather than inferred from a client library version (the
# clients and servers are pinned separately and do NOT share a version).
_VERSION_COMMENT = re.compile(
    r'"server_image":\s*"([^"]+)",\s*#\s*([^\n]+)'
)


def _image_version_names() -> dict[str, str]:
    src = (HERE / "runner.py").read_text(encoding="utf-8")
    out = {}
    for image, comment in _VERSION_COMMENT.findall(src):
        name = comment.strip()
        # Keep short version-ish comments, drop the long fairness rationales.
        if len(name) <= 60:
            out[image] = name
    return out


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _agg(rows, field):
    """Median across repetitions, with the spread, matching the paper."""
    vals = [v for v in (_num(r.get(field)) for r in rows) if v is not None]
    if not vals:
        return None
    return {
        "median": round(statistics.median(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "n": len(vals),
    }


LANES = {
    "l3s": {
        "title": "Sparse vector search",
        "dataset": "Big-ANN'23 Sparse (real SPLADE over MS MARCO)",
        "metrics": [("query_p50_ms", "p50 ms"), ("recall_at_10", "recall@10"),
                    ("build_s", "build s")],
        "conditions": [
            "Recall is reported beside every latency: ArcadeDB quantizes posting weights to int8 by default, so a latency number without its recall is not comparable.",
            "Elasticsearch runs with index-time token pruning disabled. Its 9.x default prunes on thresholds tuned for a different model's vectors and costs recall on this corpus, which would have printed a quality gap belonging to that default rather than to the engine, and printed it in our favour.",
        ],
    },
    "l3d": {
        "title": "Dense vector search",
        "dataset": "DEEP-10M (deep-image-96-angular) and SIFT-scale tiers",
        "metrics": [("query_p50_ms", "p50 ms"), ("recall_at_10", "recall@10"),
                    ("build_s", "build s")],
        "conditions": [
            "ArcadeDB's maxConnections is a Vamana per-layer degree, not hnswlib's M. Matching the parameter names would compare a half-degree graph against a full-degree one, so the graphs are matched by effect instead.",
        ],
    },
    "l2": {
        "title": "Graph traversal",
        "dataset": "LDBC-SNB Interactive (SF1, SF10)",
        "metrics": [("point_p50_ms", "point p50 ms"), ("hop1_p50_ms", "1-hop p50 ms"),
                    ("hop2_p50_ms", "2-hop p50 ms"), ("write_p50_ms", "write p50 ms")],
        "conditions": [
            "Edges are bidirectional in every arm. In ArcadeDB that is a pointer-storage choice rather than a semantic one, and the OLAP planner needs it.",
            "2-hop latency tracks seed degree, so the spread across repetitions is a property of the seed sample rather than instability.",
        ],
    },
    "l1": {
        "title": "Tabular OLTP and OLAP",
        "dataset": "Synthetic orders workload",
        "metrics": [("read_p50_ms", "read p50 ms"), ("insert_p50_ms", "insert p50 ms"),
                    ("oltp_ops_per_s", "OLTP ops/s"), ("olap_total_ms", "OLAP total ms")],
        "conditions": [],
    },
    "l1tpc": {
        "title": "Tabular (TPC-H and TPC-C shapes)",
        "dataset": "TPC-H queries, TPC-C new-order",
        "metrics": [("q1_ms", "Q1 ms"), ("q6_ms", "Q6 ms"),
                    ("neworder_p50_ms", "new-order p50 ms"), ("oltp_ops_per_s", "OLTP ops/s")],
        "conditions": [],
    },
    "e2": {
        "title": "Cross-model transaction",
        "dataset": "Vector hit to graph traversal to document update, in one transaction",
        "metrics": [("hybrid_p50_ms", "p50 ms"), ("hybrid_p99_ms", "p99 ms")],
        "conditions": [
            "The composed stack (Qdrant plus Neo4j) has no transaction spanning both engines. The comparison is of an atomic path against a non-atomic one, which is the point rather than a caveat.",
            "The torn-state and post-crash columns in the raw data record whether a mid-write failure left the stores disagreeing; that is the result this lane exists for, not the latency.",
        ],
    },
}

GLOBAL_CONDITIONS = [
    "Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.",
    "Each printed cell is the median of 5 repetitions, with min and max carried alongside; nothing here is a single sample.",
    "Defaults first. Where a default would make the comparison meaningless, it is equalized and the override is disclosed rather than hidden.",
    "Comparators are pinned by sha256 image digest, not by a floating tag.",
]


def main() -> int:
    if not FROZEN.exists():
        print(f"missing {FROZEN}; run make_paper_tables.py first", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(FROZEN.open()))
    names = _image_version_names()

    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["lane"], r["scale"], r["backend"], r.get("workload", ""))].append(r)

    tables = []
    for lane, spec in LANES.items():
        entries = []
        for (ln, scale, backend, workload), rs in sorted(grouped.items()):
            if ln != lane:
                continue
            image = BACKENDS.get(backend, {}).get("server_image")
            entry = {
                "backend": backend,
                "is_arcadedb": "arcade" in backend,
                "scale": scale,
                "workload": workload,
                "n_docs": rs[0].get("n_docs") or None,
                "deployment": "server" if "server" in backend else "embedded",
                "image": image,
                "version_name": names.get(image) if image else None,
                "host": rs[0].get("host") or None,
                "metrics": {},
            }
            for field, label in spec["metrics"]:
                got = _agg(rs, field)
                if got is not None:
                    entry["metrics"][label] = got
            if entry["metrics"]:
                entries.append(entry)
        if entries:
            tables.append({
                "id": lane,
                "title": spec["title"],
                "dataset": spec["dataset"],
                "conditions": spec["conditions"],
                "columns": [label for _, label in spec["metrics"]],
                "entries": entries,
            })

    hosts = sorted({r["host"] for r in rows if r.get("host")})
    payload = {
        "source": "benchmarks/experiments/results/runs_paper.csv",
        "generator": "benchmarks/experiments/export_web.py",
        "arcadedb_version": "26.8.1",
        "conditions": GLOBAL_CONDITIONS,
        "provenance_note": (
            "Host identity is recorded on the sparse and dense lanes only; the "
            "remaining lanes record the container but not the machine. Every "
            "lane ran on the same benchmark host, but this file reports only "
            "what the frozen rows can prove."
        ),
        "hosts_recorded": hosts,
        "tables": tables,
    }

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n",
                   encoding="utf-8")
    n_entries = sum(len(t["entries"]) for t in tables)
    print(f"wrote {OUT}")
    print(f"  tables: {len(tables)}   entries: {n_entries}")
    missing = [e["backend"] for t in tables for e in t["entries"]
               if e["image"] is None and not e["backend"].endswith("_embedded")]
    if missing:
        print(f"  NOTE: no pinned image for {sorted(set(missing))} "
              f"(embedded/in-process backends have none by design)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
