#!/usr/bin/env python3
"""Rebuild results/ of the 2026-11 publish fixture from a bench checkout's real 2026-10 rows.

The publish tests (test_publish_2611_e2e.py) run make_paper_tables and export_web on `fixtures/publish_2611/results`:
a few real rows per lane, restamped `instrument: 2026-11`, plus the row fields the 2026-11 instrument adds (per-phase memory,
the dense search-beam sweep and matched-recall headline, product-quantization arms, the served-client headline and lean twin,
l4 plain reads, the switch stamps). The numbers are real 2026-10 measurements; the stamps and added fields are synthetic, so
the fixture proves structure and arithmetic, never a published value. Only a developer with a populated results/ needs this
script; the committed output is the fixture.

    python build_fixture.py /path/to/benchmarks/experiments/results
    python build_fixture.py --patch        # re-apply realistic_2611() to the committed runs.jsonl.gz, no real rows needed

THE ROWS ARE 2026-09 AND 2026-10 MEASUREMENTS, so they lack what the 2026-11 instrument stamps and carry what the retired
instruments carried. `realistic_2611()` closes that gap, one named reason per patch, so every publish gate runs on a payload
shaped like a 2026-11 one (test_publish_gates_2611.py). It is idempotent and it is the only place the fixture rows are
edited by hand after the copy from real results; with the old untracked results archived, `--patch` is how the committed
runs.jsonl.gz is regenerated.
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


# ---------------------------------------------------------------------------------------------------------------------------
# THE 2026-11 SHAPE (test_publish_gates_2611.py). Each block says what a real 2026-11 row has that the copied row does not.

LONG_OLD, LONG_NEW = "d36b4ca3ae4c170abc73598e0dffa2bb58e06621", "261100fixda782620463bc7c09ac6bd34ac6fbda"
SERVER_VERSION = f"server:26.11.1-SNAPSHOT (build {LONG_NEW}/1789635068277/main)"
STAMP_TEXT = {
    "es_security_enabled": False, "es_replicas": 0, "duckdb_threads": 12, "duckpgq_threads": 12,
    "duckdb_hnsw_persistence": True, "neo4j_checkpoint_interval": "5s", "neo4j_checkpoint_interval_default": "15m",
    "arcadedb_add_hierarchy": True, "arcadedb_add_hierarchy_source": "read back from the index metadata",
    "server_query_max_heap_source": "read back from the server's configuration",
    "server_http_body_max_source": "read back from the server's configuration", "server_http_body_max_default": 104857600,
    "ts_mutable_at_ingest_end": 0, "ts_compaction_interval_ms": 3600000, "ts_compaction_interval": "1 HOURS",
}
E4_SIZES = (1, 10, 100, 1000, 10000, 100000)


def _pin_and_versions(r):
    """ONE PIN. Every ArcadeDB row of a 2026-11 payload was measured at the one pin (a row under another pin is superseded,
    PUBLISHING.md), and one engine wears one version string. The copied rows mix the 2026-10 pass-1 pin (d36b4ca3a, the
    26.10.1 release) with the fixture pin, and ArangoDB's 3.12.11 (before the 26.10.1 measurement) with 3.12.12 (the pin)."""
    text = json.dumps(r).replace("d36b4ca3a", PIN_NEW).replace(LONG_OLD, LONG_NEW).replace("arangodb:3.12.11", "arangodb:3.12.12")
    r = json.loads(text)
    r["engine_commit"] = PIN_NEW if r.get("engine_commit") else r.get("engine_commit")
    be = r.get("backend", "")
    if be.startswith("arcadedb") and r.get("engine_version"):
        r["engine_version"] = SERVER_VERSION if "server" in be else "26.11.1.dev0"
    return r


def _stamps(r, runner_cap, runner_body, overrides):
    """THE OVERRIDE STAMPS. A 2026-11 row of an arm that runs an override carries the field that proves it ran
    (override_registry.OVERRIDES, FAIRNESS.md F10); the September and October rows predate most of them."""
    lane, be = r["lane"], r["backend"]
    for ov in overrides:
        for c in ov.carriers:
            if (c.lane, c.backend) != (lane, be) or not c.field or c.field in r:
                continue
            if ov.applies is not None and not ov.applies(r):
                continue
            if c.field == "server_query_max_heap_elements" and runner_cap:
                r[c.field] = runner_cap
            elif c.field == "server_http_body_max_bytes" and runner_body:
                r[c.field] = runner_body
            elif c.field == "neo4j_pagecache":
                r[c.field] = r.get("server_pagecache") or "3.00GiB"
            elif c.field in STAMP_TEXT:
                r[c.field] = STAMP_TEXT[c.field]
            else:
                continue
            for comp in ov.companions:
                if comp in STAMP_TEXT and comp not in r:
                    r[comp] = STAMP_TEXT[comp]

# (lane, new arm, donor arm of the same lane, the engine whose version string it wears: a row of that engine's backend prefix)
ROSTER_FILL = (
    ("l1tpc", "arcadedb_imgdefaults_server", "arcadedb_server", None),
    ("e2", "memgraph_e2", "neo4j_e2", "memgraph_graph"), ("e2", "ladybug_e2", "neo4j_e2", "ladybug_graph"),
    ("e2", "duckdb_e2", "neo4j_e2", "duckdb"),
    ("l2", "pgage_graph", "neo4j_graph", "pg_age_e2"),
    ("l3s", "qdrant_sparse_uint8", "qdrant_sparse", None),
    ("l4", "postgres_ts", "sqlite", "postgres"),
)


def _roster_fill(rows):
    """THE ROSTER. The 2026-11 subset measures every arm runner.LANES registers for its lanes except the ones
    make_2611_stages.OUTSIDE names, and page_check refuses a table that lacks one of them. The copied rows are a few real
    rows per lane and lack fourteen of those arms, so each gets the rows of a donor arm of the same lane under its own
    name and its own engine's version string: synthetic numbers, like the PQ arms, proving structure and never a value."""
    have = {(r["lane"], r["backend"]) for r in rows}
    out = []
    for lane, arm, donor, vsrc in ROSTER_FILL:
        if (lane, arm) in have:
            continue
        version = next((r["engine_version"] for r in rows if vsrc and r["backend"].startswith(vsrc) and r.get("engine_version")), None)
        for r in rows:
            if (r["lane"], r["backend"]) != (lane, donor):
                continue
            d = json.loads(json.dumps(r))
            d["backend"] = arm
            d["run_id"] = str(d.get("run_id", "x")).replace(donor, arm)
            if version:
                d["engine_version"] = version
            # a donor's engine-specific fields would read as the new arm's engine (the exporter names an engine's version
            # from them), so the clone of another engine's row keeps none of them
            fam = donor.split("_")[0]
            if fam != arm.split("_")[0]:
                d = {k: v for k, v in d.items() if not k.startswith(fam + "_")}
            if fam != arm.split("_")[0]:
                for k in ("lib_version", "backend_version"):
                    d.pop(k, None)
                for k in ("server_image_ref", "server_image"):
                    if isinstance(d.get(k), str):
                        d[k] = d[k].replace(fam, arm.split("_")[0])
            if arm == "arcadedb_imgdefaults_server":
                # the image-defaults arm's own stamps: the JVM's report of 75% of the 16g cap, generational ZGC, no -Xms/-Xmx
                d.pop("server_heap", None)   # the image applies its own heap: the container's environment sets none
                d.update(server_jvm_defaults=True, server_jvm_max_heap_bytes=int(0.75 * 16 * (1 << 30)),
                         server_jvm_gc="ZGC generational", server_jvm_flags="-XX:+UseZGC -XX:+ZGenerational")
            # the arm's own durability string: a sibling arm of the same engine, same class, where the fixture has one
            sib = next((x for x in rows if vsrc and x["backend"].startswith(vsrc.split("_")[0]) and x["lane"] != "l4"
                        and x.get("durability_class") == d.get("durability_class") and x.get("durability")), None)
            if sib and arm != "postgres_ts":
                d["durability"], d["durability_no_setting"] = sib["durability"], sib.get("durability_no_setting", False)
            if arm.endswith("_int8") or arm.endswith("_uint8"):
                d["quantization"] = "int8"
            out.append(d)
    return rows + out


def _agreeing_answers(rows):
    """DuckPGQ's copied rows are the September adapter's: its answers differ from every other engine's (an age of 0 for 44,
    a smaller visited count) and it records no digest for the two edge writes. The adapter of a 2026-11 row answers the
    query set like the others, so its rows carry the digests of the ArcadeDB embedded row of the same cell."""
    ref = {(r["workload"], r["rep"], r["durability_class"]): r for r in rows
           if r["lane"] == "l2" and r["backend"] == "arcadedb_graph_embedded"}
    for r in rows:
        if r["lane"] == "l2" and r["backend"] == "duckpgq_graph":
            src = ref.get((r["workload"], r["rep"], r["durability_class"]))
            if src:
                r.update({k: v for k, v in src.items() if k.startswith("res_")})
    return rows


def _patch_overlays():
    """The overlay files carry the copied versions too: ArangoDB's 3.12.11 and the 26.10.1 pass-1 pin."""
    for d in OUT.glob("*_261100fix"):
        for f in sorted(d.iterdir()):
            text = f.read_text()
            new = (text.replace("d36b4ca3a", PIN_NEW).replace(LONG_OLD, LONG_NEW).replace("arangodb:3.12.11", "arangodb:3.12.12"))
            if new != text:
                f.write_text(new)


def realistic_2611(rows, deep10m=True):
    import bench_common
    import fairness_check as FC
    import override_registry as OR
    rows = _agreeing_answers(_roster_fill([_pin_and_versions(r) for r in rows]))
    relaxed = next(r["durability"] for r in rows if r["backend"] == "arcadedb_embedded" and r.get("durability_class") == "relaxed")
    cap, body = OR.runner_cap(), OR.runner_body_limit()
    hash_lanes = {lane: (wl, pairs) for lane, wl, pairs in FC.ARCADEDB_HASH_ID_INDEXES}
    for r in rows:
        lane, be = r["lane"], r["backend"]
        _stamps(r, cap, body, OR.OVERRIDES)
        # the engine's own answer to `SELECT FROM schema:indexes`, stamped by the lanes since CAMPAIGN 7 row 68
        if be.startswith("arcadedb") and lane in hash_lanes and not r.get("index_kinds"):
            kinds = {}
            for ln, wl, pairs in FC.ARCADEDB_HASH_ID_INDEXES:
                if ln == lane and wl in (None, r.get("workload")):
                    kinds.update({f"{t}.{p}": "HASH" for t, p in pairs})
            kinds.update({f"{t}.{p}": "LSM_TREE" for ln, t, p in FC.ARCADEDB_SORTED_ID_INDEXES if ln == lane})
            r["index_kinds"] = ";".join(f"{k}={v}" for k, v in sorted(kinds.items()))
        # SurrealDB's served arms have a sync setting since 3.2.4 (BUGS F165): the row reads it back, it is not "no setting"
        if be.startswith("surrealdb") and "server" in be and r.get("durability_no_setting"):
            strict = r.get("durability_class") == "strict"
            r["durability"] = (bench_common.DURABILITY_SURREAL_SERVER_STRICT if strict else bench_common.DURABILITY_SURREAL_SERVER)
            r["durability_no_setting"] = False
        # the decomposition lane records the durability it ran at (F10) and the answer digest per result size (E6)
        if lane == "e4":
            r.setdefault("durability", relaxed)
            for n in E4_SIZES:
                r.setdefault(f"res_limit{n}_digest", f"e4{n:04d}c0ffee{n:06d}"[:16])
                r.setdefault(f"res_limit{n}_sample", f"(row {n})")
                r.setdefault(f"res_limit{n}_n", n)
        # the dense adapters time the index separately from the load since the 2026-10 lanes (F14c)
        if lane == "l3d" and be in ("arangodb_dense", "arangodb_dense_pq", "duckdb_vss_dense") and r.get("index_s") is None:
            r["index_s"] = round(0.3 * float(r["build_s"]), 2)
        # FalkorDB's September disk reading was taken before its RDB reached the disk (growth 0.0, the failure
        # resource_check exists to catch); a 2026-11 row reads the flushed file
        if be == "falkordb_graph" and r.get("server_disk_mb") == r.get("server_disk_baseline_mb"):
            r["server_disk_mb"] = round(float(r["server_disk_baseline_mb"]) + 24.5, 1)
    return rows + _deep10m_envelope_rows(rows) if deep10m else rows


def realistic_2611_deep10m(rows):
    return rows + _deep10m_envelope_rows(rows)


def _deep10m_envelope_rows(rows):
    """THE CAMPAIGN ROW BEHIND EACH DEEP-10M OVERLAY FILE. The multipass driver runs inside the client container and
    writes only the client's cap, and none of the override stamps; the runner stamps the server envelope (server_mem_cap,
    server_heap, mem_split) and the lane stamps the overrides on the campaign row of the same cell, and the gates read them
    from there (fairness_check._dense_rows, _served_envelopes). The copied runs.jsonl has no deep10m campaign rows, so F3
    read the client's 8g as the served arms' memory. One such row per dense arm that has an overlay file, at the embedded
    arms' envelope (36g, heap 24g)."""
    have = {r["backend"] for r in rows if r["lane"] == "l3d" and r["scale"] == "deep10m"}
    overlay = set()
    for f in (OUT / f"dense_mp5_{PIN_NEW}").glob("mp_*_b*.json"):
        d = json.loads(f.read_text())
        overlay.add((d[0] if isinstance(d, list) else d).get("backend"))
    out = []
    for r in rows:
        if (r["lane"] != "l3d" or r["scale"] != "small" or r["backend"] not in overlay or r["backend"] in have
                or int(r.get("rep") or 0) != 1):
            continue
        have.add(r["backend"])
        d = dict(r)
        d.update(scale="deep10m", n_docs=9990000, mem_cap="36g", run_id=f"{r.get('run_id', 'x')}_deep10m")
        # a 10M-vector cell holds the corpus (3.8 GiB of raw vectors) and its index; the ArcadeDB arms sit at their pinned
        # 24 GiB heap, the others well above the small tier's reading the clone copied
        for k in ("peak_anon_mib_sum", "peak_owned_mib_sum"):
            if isinstance(d.get(k), (int, float)):
                d[k] = 27000.0 if r["backend"].startswith("arcadedb") else max(float(d[k]), 9000.0)
        if r.get("heap"):
            d["heap"] = "24g"
        if r.get("server_mem_cap"):
            d.update(server_mem_cap="36g", server_heap="24g", server_mem_cap_g=36.0, mem_split="full+client",
                     client_mem_cap="8g")
        out.append(d)
    return out


def _copy_overlay(src: Path, name: str):
    s = src / name.replace(PIN_NEW, PIN_OLD)
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    for f in sorted(s.iterdir()):
        text = _restamp(f.read_text())
        obj = json.loads(text)
        (d / f.name.replace(PIN_OLD, PIN_NEW)).write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def write_rows(rows):
    # gzipped (mtime 0, so the output is reproducible): 2.7 MB as text, about 150 kB packed; the test unpacks it
    with gzip.GzipFile(OUT / "runs.jsonl.gz", "wb", mtime=0) as fh:
        for r in rows:
            fh.write((json.dumps(r, separators=(",", ":")) + "\n").encode())


def patch_existing():
    """Apply realistic_2611() to the committed runs.jsonl.gz in place (idempotent; needs no real results)."""
    with gzip.open(OUT / "runs.jsonl.gz", "rt") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    _patch_overlays()
    rows = realistic_2611([r for r in rows if not str(r.get("run_id", "")).endswith("_deep10m")])
    write_rows(rows)
    print(f"{len(rows)} rows patched in place")


def main(src: Path):
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = realistic_2611(_add_2611_fields(_rows(src)), deep10m=False)
    for name in (f"dense_mp5_{PIN_NEW}", f"dense_mp5_small_{PIN_NEW}", f"e4decomp_{PIN_NEW}", f"sparse_mp_{PIN_NEW}"):
        _copy_overlay(src, name)
    _patch_overlays()
    rows = realistic_2611_deep10m(rows)
    write_rows(rows)
    print(f"{len(rows)} rows, overlays copied, pin {PIN_NEW}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--patch"]:
        patch_existing()
    else:
        main(Path(sys.argv[1]))
