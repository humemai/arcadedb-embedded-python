#!/usr/bin/env python3
"""Rebuild results/ of the 2026-11 publish fixture from a bench checkout's real 2026-10 rows.

The publish tests (test_publish_2611_e2e.py) run make_paper_tables and export_web on `fixtures/publish_2611/results`:
a few real rows per lane, restamped `instrument: 2026-11`, plus the row fields the 2026-11 instrument adds (per-phase memory,
the dense search-beam sweep and matched-recall headline, product-quantization arms, the served-client headline and lean twin,
l4 plain reads, the switch stamps). The numbers are real 2026-10 measurements; the stamps and added fields are synthetic, so
the fixture proves structure and arithmetic, never a published value. Only a developer with a populated results/ needs this
script; the committed output is the fixture.

    python build_fixture.py /path/to/benchmarks/experiments/results
"""
import gzip
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import dense_beam  # noqa: E402

PIN_OLD, PIN_NEW = "417314c18", "261100fix"
KEEP = {"e2": {"e2"}, "e4": {"e2"}, "l1tpc": {"tpch1"}, "l2": {"sf1"}, "l3d": {"small"}, "l3s": {"tiny", "small", "medium"},
        "lifecycle": {"lc10k"}, "l4": {"ts100"}}
MAX_REP = 3
PQ_ARMS = {"arcadedb_dense_embedded": "arcadedb_dense_embedded_pq", "arcadedb_dense_server": "arcadedb_dense_server_pq",
           "qdrant_dense": "qdrant_dense_pq", "milvus_dense": "milvus_dense_pq", "arangodb_dense": "arangodb_dense_pq"}
FULL_REP_LANES = {"l3s"}   # the sparse freeze takes a pinned tier only at five repetitions, at every tier
WITH_PQ = True
OUT = HERE / "results"


def _restamp(text: str) -> str:
    text = text.replace(PIN_OLD, PIN_NEW)
    return re.sub(r"26\.10\.1", "26.11.1", text).replace("2026-10", "2026-11")


def _rows(src: Path):
    seen = {}
    for line in (src / "runs.jsonl").open():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("instrument") != "2026-10" or r.get("rc") != 0 or r.get("scale") not in KEEP.get(r.get("lane"), ())
                or (int(r.get("rep") or 0) > MAX_REP and r.get("lane") not in FULL_REP_LANES)):
            continue
        key = (r["lane"], r["scale"], r["backend"], r.get("workload"), r.get("gav"), r.get("rep"), r.get("durability_class"))
        if key not in seen or r["ts_utc"] > seen[key]["ts_utc"]:
            seen[key] = r
    return [seen[k] for k in sorted(seen, key=str)]


def _beam_points(rep: int, seed: int):
    """A plausible recall/latency curve: recall climbs with the beam, latency grows with it."""
    p50 = 0.6 + 0.05 * seed + 0.01 * rep
    return [{"beam": b, "recall": min(0.999, 0.90 + 0.04 * i + 0.002 * seed), "p50": p50 * (1 + i), "p99": p50 * (2 + 2 * i)}
            for i, b in enumerate(dense_beam.ef_values())]


def _add_2611_fields(rows):
    out = []
    for n, r in enumerate(rows):
        r = json.loads(_restamp(json.dumps(r)))
        r["instrument"] = "2026-11"
        r["mem_queries_owned_mib"] = round(900.0 + 3.5 * (n % 40), 1)
        r["cpu_dma_latency_us"] = 0
        r["cpu_dma_latency_held"] = True
        be, lane = r["backend"], r["lane"]
        if lane == "l3s":
            r["sparse_warmup_queries"] = 1000
            r["sparse_warmup_source"] = "extra_queries"
        if lane == "l3d":
            r["dense_id_index"] = 1
            if be.endswith("sqlite_vec_dense"):
                r.update(dense_beam.row_fields("none", [{"beam": None, "recall": 0.97, "p50": 1.2, "p99": 2.4}], "exact scan"))
            else:
                pts = _beam_points(int(r.get("rep") or 1), n % 7)
                if be == "arangodb_dense":
                    pts = [dict(p, beam=b) for p, b in zip(pts, (4, 8, 16, 32))]
                    r.update(dense_beam.row_fields("nprobe", pts))
                else:
                    r.update(dense_beam.row_fields("ef", pts))
        if lane == "l4" and be in ("duckdb", "sqlite", "arcadedb_ts_native", "arcadedb_ts_doc"):
            for q in ("q_high", "q_groupby"):
                base = r.get(f"{q}_ms") or r.get(f"{q}_p50_ms")
                if base:
                    r[f"{q}_plain_ms"] = round(float(base) * 1.6, 4)
                    r[f"{q}_plain_digest_match"] = True
            r["read_path"] = "arrow" if be != "sqlite" else "fetchall"
        if be.startswith("arcadedb") and "server" in be:
            r["arcadedb_http_client"] = "arcadedb-driver 0.2.0 (sync, httpx)"
            r["arcadedb_http_client_role"] = "headline"
        out.append(r)
    # the labelled lean twin of every served ArcadeDB cell: faster by a fixed factor, so a test can tell it from the headline
    twins = []
    for r in out:
        if r.get("arcadedb_http_client_role") == "headline":
            t = dict(r)
            t["arcadedb_http_client"] = "lean (requests)"
            t["arcadedb_http_client_role"] = "sensitivity"
            t["run_id"] = f"{r.get('run_id', 'x')}_clientlean"
            for k, v in list(t.items()):
                if k.endswith("_ms") and isinstance(v, (int, float)) and not isinstance(v, bool):
                    t[k] = round(v * 0.7, 4)
            twins.append(t)
    # the product-quantization arms (#419) beside the fp32 arm each is derived from: synthetic, there are no real PQ rows. The
    # stamps are the ones l3d_dense writes (quantization PRODUCT for ArcadeDB, pq_subspaces, pq_clusters, pq_rerank, the
    # read-back fields); the numbers are the fp32 arm's, slower queries and a lower recall, as PQ trades them.
    pq = []
    for r in out if WITH_PQ else ():
        arm = PQ_ARMS.get(r["backend"]) if r["lane"] == "l3d" else None
        if arm:
            p = dict(r)
            p["backend"] = arm
            p["quantization"] = "PRODUCT" if arm.startswith("arcadedb") else "fp32"
            p.update(pq_subspaces=32, pq_clusters=256, pq_rerank="engine default" if arm.startswith("arcadedb") else "refine FP32",
                     pq_rerank_option_accepted=True)
            if arm.startswith("arcadedb"):
                p["pq_index_bytes"] = 123456789
            for k in ("recall_at_10", "matched_r095_recall_at_10"):
                if isinstance(p.get(k), (int, float)):
                    p[k] = round(p[k] - 0.02, 4)
            pq.append(p)
    return out + twins + pq


def _copy_overlay(src: Path, name: str):
    s = src / name.replace(PIN_NEW, PIN_OLD)
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    for f in sorted(s.iterdir()):
        text = _restamp(f.read_text())
        obj = json.loads(text)
        (d / f.name.replace(PIN_OLD, PIN_NEW)).write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def main(src: Path):
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = _add_2611_fields(_rows(src))
    # gzipped (mtime 0, so the output is reproducible): 2.7 MB as text, about 150 kB packed; the test unpacks it
    with gzip.GzipFile(OUT / "runs.jsonl.gz", "wb", mtime=0) as fh:
        for r in rows:
            fh.write((json.dumps(r, separators=(",", ":")) + "\n").encode())
    for name in (f"dense_mp5_{PIN_NEW}", f"dense_mp5_small_{PIN_NEW}", f"e4decomp_{PIN_NEW}", f"sparse_mp_{PIN_NEW}"):
        _copy_overlay(src, name)
    print(f"{len(rows)} rows, overlays copied, pin {PIN_NEW}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
