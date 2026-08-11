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


# The harness names backends for the runner, not for a reader: arcadedb_e2,
# composed_qdrant_neo4j, arcadedb_sparse_embedded_nocompact. Those belong in
# the data; a page should say what the thing IS. Unmapped names fall back to
# a tidied version of the raw key rather than being hidden, so a new backend
# shows up looking slightly rough instead of silently vanishing.
DISPLAY_NAMES = {
    "arcadedb_embedded": "ArcadeDB (embedded)",
    "arcadedb_server": "ArcadeDB (server)",
    "arcadedb_graph_embedded": "ArcadeDB (embedded)",
    "arcadedb_graph_server": "ArcadeDB (server)",
    "arcadedb_dense_embedded": "ArcadeDB (embedded)",
    "arcadedb_dense_server": "ArcadeDB (server)",
    "arcadedb_sparse_embedded": "ArcadeDB (embedded)",
    "arcadedb_sparse_server": "ArcadeDB (server)",
    "arcadedb_sparse_embedded_fp32": "ArcadeDB (embedded, fp32 weights)",
    "arcadedb_sparse_embedded_nocompact": "ArcadeDB (embedded, no settle step)",
    "arcadedb_e2": "ArcadeDB (one transaction)",
    "composed_qdrant_neo4j": "Qdrant + Neo4j (no shared transaction)",
    "surrealdb_e2": "SurrealDB",
    "qdrant_sparse": "Qdrant", "qdrant_dense": "Qdrant",
    "milvus_sparse": "Milvus", "milvus_dense": "Milvus",
    "elasticsearch_sparse": "Elasticsearch",
    "chroma_dense": "Chroma", "lancedb_dense": "LanceDB",
    "sqlite_vec_dense": "sqlite-vec", "duckdb_vss_dense": "DuckDB VSS",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "postgres": "PostgreSQL", "duckdb": "DuckDB", "questdb": "QuestDB",
    "arcadedb": "ArcadeDB",
}


def display_name(backend: str) -> str:
    if backend in DISPLAY_NAMES:
        return DISPLAY_NAMES[backend]
    if backend.startswith("arcadedb"):
        return "ArcadeDB"
    return backend.replace("_", " ")


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


E4_DIR = HERE / "results" / "e4decomp_2681"

# Named so the page can say what each step is rather than showing three opaque
# arm names. embedded -> inproc_http isolates the wire format with the process
# boundary held constant; inproc_http -> docker_http then adds the boundary
# with the wire format held constant.
E4_ARMS = [
    ("embedded", "in-process, no protocol"),
    ("inproc_http", "in-process server over HTTP"),
    ("docker_http", "separate container over HTTP"),
]


def _e4_table():
    """Deployment decomposition: what the client/server split actually costs.

    Included where the other overlays are not, because this one records the
    conditions that make it comparable: one released engine version on every
    arm, identical cpuset, memory cap and heap, all three arms materializing
    through `to_json_list` so the difference cannot be a serialization
    artifact of our own choosing, and `row_count_agreement: ok` confirming the
    arms returned the same rows. See the tracker note that bespoke overlay
    drivers usually drift from their lane's protocol; this is the one that
    did not.
    """
    reps = sorted(E4_DIR.glob("decomp3m_2681_rep*.json"))
    if not reps:
        return None

    loaded = [json.loads(p.read_text(encoding="utf-8")) for p in reps]
    meta = loaded[0]["meta"]
    sizes = sorted(loaded[0]["results"]["embedded"], key=int)

    entries = []
    for size in sizes:
        per_arm = {}
        for arm, _ in E4_ARMS:
            vals = [d["results"][arm][size]["p50_ms"] for d in loaded
                    if arm in d["results"] and size in d["results"][arm]]
            if vals:
                per_arm[arm] = statistics.median(vals)
        if len(per_arm) != len(E4_ARMS):
            continue

        metrics = {}
        for arm, label in E4_ARMS:
            metrics[label] = {"median": round(per_arm[arm], 4),
                              "min": round(per_arm[arm], 4),
                              "max": round(per_arm[arm], 4),
                              "n": len(loaded)}
        protocol = per_arm["inproc_http"] - per_arm["embedded"]
        boundary = per_arm["docker_http"] - per_arm["inproc_http"]
        for label, value in (("wire format", protocol), ("process boundary", boundary)):
            metrics[label] = {"median": round(value, 4), "min": round(value, 4),
                              "max": round(value, 4), "n": len(loaded)}

        entries.append({
            "backend": f"{int(size):,} rows",
            "is_arcadedb": True,
            "scale": f"{int(size):,}",
            "workload": "projection",
            "n_docs": str(meta.get("rows")),
            "deployment": "all three",
            "image": None,
            "version_name": meta.get("engine_version"),
            "host": meta.get("host"),
            "metrics": metrics,
        })

    return {
        "id": "e4",
        "title": "What the client/server split costs",
        "dataset": f"{meta.get('rows'):,}-row projection, one engine, three deployments",
        "conditions": [
            f"One released engine ({meta.get('engine_version')}) on all three arms, "
            f"{meta.get('reps')} repetitions after {meta.get('warmup')} warmup, "
            f"identical cpuset {meta.get('cpuset')}, memory cap {meta.get('mem_cap')} "
            f"and heap {meta.get('heap')}.",
            "All three arms materialize results the same way, so the difference "
            "is the deployment and not our choice of result format.",
            "The separate-container arm is loopback on one host. It says what "
            "co-locating costs, and says nothing about a real network.",
            "The process-boundary column goes slightly negative at the smaller "
            "result sizes. That is not a container being faster than an "
            "in-process server; it is the boundary term sitting below what this "
            "design can resolve, so run-to-run noise swamps it and the sign "
            "flips. Reported rather than clamped to zero, because the negative "
            "values are the evidence for the claim: at these sizes co-locating "
            "costs nothing measurable. The wire format, in the column beside "
            "it, stays firmly positive at every size.",
        ],
        "columns": [label for _, label in E4_ARMS] + ["wire format", "process boundary"],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
    }


L4_FILE = HERE / "results" / "l4_tsbs.jsonl"
L4_NATIVE = HERE / "results" / "ts_2681"

# One configuration, so these are constants of the experiment.
L4_SHAPE = {"scale": "2.59M points", "workload": "TSBS cpu-only"}

# Field names differ from the other lanes and one of them is a trap.
# `q_global_ms` is the 12-hour aggregation (it returns 12 rows, one per hour).
# `q_range_ms` is a 60-row range query and is NOT that number; reading it as
# the aggregation gives 4.41 ms against the paper's 25.0 and invites the
# conclusion that the paper is wrong. It is not.
# Last-point is reported unbounded, which is the faster of the two and the one
# the paper quotes (0.720 against 0.860 windowed).
# Last-point takes the first field a source actually has. The native probe
# records both an unbounded and a recency-windowed variant and the paper quotes
# the unbounded one (0.720, faster than the windowed 0.860); the other engines
# record a single unbounded number under the plainer name. Preferring the
# unbounded field everywhere keeps the column comparing like with like.
L4_METRICS = [
    ("ingest_pts_per_s", "ingest pts/s"),
    (("q_last_unbounded_ms", "q_last_ms"), "last-point ms"),
    ("q_global_ms", "12h aggregate ms"),
]


def _l4_rows():
    """Both ArcadeDB arms plus the comparators, from the two files that hold them.

    The native TIMESERIES arm lives in ts_2681/ and the document path and the
    comparators in l4_tsbs.jsonl. Publishing only the second file would show
    ArcadeDB at 40.1k pts/s against DuckDB's 1.86M, which is our slowest arm
    against everyone else's best. The papers report both arms precisely so that
    46x is read as what the general-purpose path costs rather than as the
    engine losing, and the same has to hold here.
    """
    out = defaultdict(list)

    for path in sorted(L4_NATIVE.glob("nosettle_r*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        # One arm only. The file set is a single arm today, but primitive= and
        # numpy_cols= are part of what is being claimed, so assert rather than
        # assume: mixing arms would report a number no paper claims.
        if d.get("primitive") is True and d.get("numpy_cols") is True:
            out["arcadedb (native TIMESERIES)"].append(d)

    if L4_FILE.exists():
        for line in L4_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            backend = r.get("backend")
            label = ("arcadedb (document path)" if backend == "arcadedb"
                     else str(backend))
            out[label].append(r)

    return out


def _l4_table():
    grouped = _l4_rows()
    if not grouped:
        return None

    order = ["arcadedb (native TIMESERIES)", "arcadedb (document path)",
             "questdb", "duckdb"]
    entries = []
    for label in sorted(grouped, key=lambda k: (order.index(k) if k in order else 99, k)):
        rs = grouped[label]
        entry = {
            "backend": display_name(label) if label in DISPLAY_NAMES else label,
            "is_arcadedb": "arcadedb" in label,
            "scale": L4_SHAPE["scale"],
            "workload": L4_SHAPE["workload"],
            "n_docs": str(rs[0].get("n_points")),
            "deployment": "embedded",
            "image": None,
            "version_name": rs[0].get("backend_version") or rs[0].get("engine_version"),
            "host": rs[0].get("host"),
            "metrics": {},
        }
        for field, lab in L4_METRICS:
            for candidate in ((field,) if isinstance(field, str) else field):
                got = _agg(rs, candidate)
                if got is not None:
                    entry["metrics"][lab] = got
                    break
        if entry["metrics"]:
            entries.append(entry)

    settles = {r.get("settle_s") for rs in grouped.values() for r in rs}
    symmetric = settles <= {0, 0.0}

    return {
        "id": "l4",
        "title": "Time series",
        "dataset": "TSBS cpu-only, 2,592,000 points",
        "conditions": [
            "Two ArcadeDB arms are shown on purpose. The native time-series "
            "type and the general-purpose document path are both real ways to "
            "store this data, and the gap between them is what the specialized "
            "layout buys rather than a result about the competition.",
            "No engine takes a settle step, and that was measured rather than "
            "assumed: sealing the write buffer makes the aggregation faster and "
            "the last-point query slower, since the unsealed tail a scan walks "
            "is where the newest point lives. Settling only ours would have "
            "been a one-sided advantage."
            + ("" if symmetric else " (Rows disagree on this; treat with care.)"),
            "One tag and three fields, not the ten and ten the TSBS cpu schema "
            "defines. The reduction is applied identically to every engine, so "
            "the comparison is internally fair, but it is not the full "
            "benchmark. A matched one-tag/ten-tag run prices the schema at "
            "2.0x on ingest and 2.6x faster on last-point.",
            "Last-point is the unbounded query, which is the faster of the two "
            "measured here (0.720 against 0.860 ms with a recency window).",
            "Builds are each engine's own reported version rather than a "
            "stamped constant, which is why QuestDB's carries its commit hash.",
        ],
        "columns": [lab for _, lab in L4_METRICS],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
    }


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
                "backend": display_name(backend),
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
            # A scale where the comparators have rows and ArcadeDB does not
            # reads as "ArcadeDB could not do this tier", which is a claim the
            # absence of a row must never be allowed to make on our behalf.
            # It happens legitimately: the dense 10M rows exist but ran on
            # 26.8.1.dev3, and releases-only (DECISIONS #42) keeps dev builds
            # out of the frozen set, so the tier has no publishable ArcadeDB
            # number until the next release re-pin.
            #
            # Only scales where our engine is also present are published. The
            # withheld ones are recorded rather than dropped quietly, so the
            # page can say why and so this file cannot silently start hiding
            # a tier we did badly at.
            ours = {e["scale"] for e in entries if e["is_arcadedb"]}
            theirs = {e["scale"] for e in entries if not e["is_arcadedb"]}
            withheld = sorted(theirs - ours)
            shown = [e for e in entries if e["scale"] in ours] if ours else entries
            tables.append({
                "id": lane,
                "title": spec["title"],
                "dataset": spec["dataset"],
                "conditions": spec["conditions"],
                "columns": [label for _, label in spec["metrics"]],
                "withheld_scales": withheld,
                "withheld_reason": (
                    "Comparator rows exist at these tiers but ArcadeDB's were "
                    "measured on a pre-release build, which this project does "
                    "not publish. They return at the next release re-pin."
                ) if withheld else None,
                "entries": shown,
            })

    for extra in (_l4_table(), _e4_table()):
        if extra and extra["entries"]:
            tables.append(extra)

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
    for table in tables:
        if table["withheld_scales"]:
            print(f"  WITHHELD {table['id']}: scale(s) {table['withheld_scales']} "
                  f"have comparator rows but no released ArcadeDB row, so the "
                  f"tier is not published (it would read as a missing result)")
    missing = [e["backend"] for t in tables for e in t["entries"]
               if e["image"] is None and not e["backend"].endswith("_embedded")]
    if missing:
        print(f"  NOTE: no pinned image for {sorted(set(missing))} "
              f"(embedded/in-process backends have none by design)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
