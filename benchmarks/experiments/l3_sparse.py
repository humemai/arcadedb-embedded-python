#!/usr/bin/env python3
"""L3 sparse-vector lane: build + top-K search + recall@10 vs exact GT.

Backends: arcadedb_embedded / arcadedb_server (LSM_SPARSE_VECTOR, dot-product
BlockMax-WAND), qdrant_sparse, milvus_sparse, elasticsearch_sparse. Same seeded
SPLADE-shaped corpus (sparse_common.py); ground truth from gen_sparse_gt.py
must exist at /data/sparse/<scale>/gt.npy (mounted read-only by the runner).

Timing: build (ingest incl. transactional index maintenance) and warm query
latency (warmups discarded). Recall resolution (id lookup) happens OUTSIDE the
timed section. Emits one JSON metric block.
"""
import argparse
import json
import os
import statistics
import sys
import time

# Data source: synthetic SPLADE-shaped (default) or real Big-ANN SPLADE/MS MARCO
# (BENCH_SPARSE_SOURCE=bigann). Both expose the same surface.
if os.environ.get("BENCH_SPARSE_SOURCE") == "bigann":
    import bigann_sparse as _src
else:
    import sparse_common as _src
DIMENSIONS, K = _src.DIMENSIONS, _src.K
SCALE_DOCS, SCALE_QUERIES = _src.SCALE_DOCS, _src.SCALE_QUERIES
gen_docs, gen_queries = _src.gen_docs, _src.gen_queries

WARMUP = 5
INGEST_BATCH = 500


def pct(vals):
    v = sorted(vals)
    g = lambda q: v[min(len(v) - 1, int(q * len(v)))]
    return {"mean_ms": round(statistics.mean(v) * 1e3, 3),
            "p50_ms": round(g(0.50) * 1e3, 3), "p95_ms": round(g(0.95) * 1e3, 3),
            "p99_ms": round(g(0.99) * 1e3, 3), "n": len(v)}


def recall_at_k(result_ids, gt_row):
    truth = set(int(x) for x in gt_row)
    return len(truth.intersection(int(x) for x in result_ids)) / len(truth)


class Base:
    # VERSION IS A MEASUREMENT INPUT, not a label.
    #
    # Qdrant already read its server version (see #156 below); Milvus did not,
    # so its rows reached the page as engine_version="milvus" -- the backend NAME
    # where a version belongs. Elastic, duckdb and questdb publish blank or a
    # bare name elsewhere for the same reason. We hold ArcadeDB to naming its
    # build; a table comparing us against Milvus "milvus" is no more defensible.
    #
    # This default catches the next adapter that forgets, which is the actual
    # failure: the gap was never a decision, it was an omission nothing flagged.
    #
    # "unset" rather than "?" so the difference between "nobody asked" and "the
    # engine was asked and would not say" survives into the artifact.
    version = "unset"

    def close(self):
        """Release the engine handle. Overridden where there is one to release.

        Every adapter answers close() so a caller never has to know which
        engines hold a handle. Absent this, l3_sparse held its ArcadeDB
        database open for the life of the process and the lifecycle probe's
        reopen failed outright with "Found active instance of database
        '/tmp/l3_arcade' already in use". That was our omission, not an engine
        limitation: l2_graph and l3d_dense have closed their databases all
        along, and the same binding call works here.
        """
        pass

    name = "base"

    def connect(self):
        raise NotImplementedError

    def reopen(self):
        """Open an ALREADY-BUILT database, with no DDL and no ingest.

        Separate from connect() on purpose. connect() creates the database and
        issues the schema, so calling it twice fails ("already exists") and,
        if it did not, would time creation rather than opening. Reopening is
        the quantity a build/query phase split would introduce and that
        nothing in this project measures today (#154), so it gets its own
        method rather than a flag on the published path.

        Adapters that cannot reopen say so by leaving this unimplemented; the
        probe records the reason instead of reporting a number it did not get.
        """
        raise NotImplementedError(f"{self.name} has no reopen path")

    def build(self, n_docs):
        """Ingest corpus (index maintained per backend's idiomatic path)."""
        raise NotImplementedError

    def search(self, idx, vals, k):
        """Return list of doc ordinals, best first. Must be warm-callable."""
        raise NotImplementedError

    def post_build(self):
        """Optional: wait for index readiness (counts as build time)."""

    def disk_mb(self):
        return None


class ArcadeEmbedded(Base):
    name = "arcadedb_sparse_embedded"
    quant = None  # None = engine default (INT8); "FP32"/"FP16" per engine #5143

    def _index_metadata(self):
        import json as _json
        meta = {"dimensions": DIMENSIONS}
        if self.quant:
            meta["weightQuantization"] = self.quant
        return _json.dumps(meta)

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # -Xms pinned to -Xmx for parity with the server deployment
        # (ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap} in runner.py)
        jvm_args = f"-Xms{heap}"
        # Engine knobs for an ablation arm, e.g.
        #   ARCADEDB_JVM_EXTRA=-Darcadedb.sparseVectorScoringMaxPartitions=8
        # Echoed rather than applied silently: an unread override would make an
        # ablation measure the default and look like a null result.
        extra = os.environ.get("ARCADEDB_JVM_EXTRA", "").strip()
        if extra:
            jvm_args = f"{jvm_args} {extra}"
            print(f"JVM-EXTRA {extra}", flush=True)
        self.db = arcadedb.create_database(
            "/tmp/l3_arcade",
            jvm_kwargs={"heap_size": heap, "jvm_args": jvm_args})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")
        self.db.command("sql", "CREATE DOCUMENT TYPE Doc")
        self.db.command("sql", "CREATE PROPERTY Doc.id LONG")
        self.db.command("sql", "CREATE PROPERTY Doc.tokens ARRAY_OF_INTEGERS")
        self.db.command("sql", "CREATE PROPERTY Doc.weights ARRAY_OF_FLOATS")
        self.db.command("sql", "CREATE INDEX ON Doc (tokens, weights) "
                               "LSM_SPARSE_VECTOR METADATA "
                               + self._index_metadata())
        self.idx_name = "Doc[tokens,weights]"

    def reopen(self):
        """Open the built database again: no create, no DDL, no ingest.

        IN-PROCESS CAVEAT, and it decides how the number may be read. The JVM
        is already running by the time this is called, so heap_size here is
        inert and what gets timed is the engine opening its files, not a JVM
        start. For a phase split implemented as a container restart the JVM
        start is real and would have to be added; measuring it separately is
        the point, since it is charged to every JVM engine and to none of the
        others.
        """
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.open_database(
            "/tmp/l3_arcade",
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
        self.idx_name = "Doc[tokens,weights]"

    def build(self, n_docs):
        # Native document API with primitive arrays — the embedded analog of
        # Qdrant/Milvus binary clients (1.8x faster than SQL INSERT batches;
        # the server adapter keeps SQL-over-HTTP, its native remote surface).
        import jpype
        JInt, JFloat = jpype.JArray(jpype.JInt), jpype.JArray(jpype.JFloat)
        jdb = self.db.get_java_database()
        jdb.begin()
        open_n = 0
        for i, idx, vals in gen_docs(n_docs):
            d = jdb.newDocument("Doc")
            d.set("id", i)
            d.set("tokens", JInt(idx))
            d.set("weights", JFloat(vals))
            d.save()
            open_n += 1
            if open_n == INGEST_BATCH:
                jdb.commit()
                jdb.begin()
                open_n = 0
        jdb.commit()

    def post_build(self):
        # ArcadeDB's settle step (fairness parity with ES forcemerge / Milvus
        # flush+load / Qdrant green-wait): blocking LSM segment compaction via
        # the Java API — embedded-only, no SQL/HTTP trigger exists. Measured at
        # 1M docs: ~2s, query p50 9.5ms -> 7.0ms (control run: no change).
        jdb = self.db.get_java_database()
        for idx in jdb.getSchema().getIndexes():
            if "SparseVector" in str(idx.getClass().getSimpleName()):
                idx.compact()

    def search(self, idx, vals, k):
        import jpype
        ji = jpype.JArray(jpype.JInt)(idx)
        jv = jpype.JArray(jpype.JFloat)(vals)
        rows = self.db.query(
            "sql", "SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?))",
            self.idx_name, ji, jv, k).to_json_list()
        self._last_rids = [r["@rid"] for r in rows]
        return self._last_rids  # RIDs; resolved to ordinals untimed

    def resolve(self, rids):
        # RID list as the query TARGET, not as a WHERE predicate. Engine #5824:
        # `WHERE @rid IN [list]` is planned as FetchFromTypeWithFilterStep, a
        # full bucket scan whose cost is linear in the TYPE and independent of
        # k, while `FROM [list]` plans as FETCH FROM RIDs and is flat. Measured
        # 1143x at 400k docs; at this lane 8.84M it was ~4.7s per resolve call,
        # 82% of a cell wall clock.
        #
        # THIS CHANGES NO RECORDED NUMBER. resolve() runs in the UNTIMED recall
        # pass; only search() is timed. Both forms verified to return identical
        # rows, identical projection shape, and identical -1 handling for a
        # dangling RID.
        if not rids:
            return []
        in_list = ",".join(rids)
        rows = self.db.query(
            "sql", f"SELECT id, @rid AS r FROM [{in_list}]"
        ).to_json_list()
        by_rid = {r["r"]: r["id"] for r in rows}
        return [by_rid.get(x, -1) for x in rids]

    def close(self):
        self.db.close()

class ArcadeEmbeddedFP32(ArcadeEmbedded):
    """Quantization ablation (engine #5143): exact FP32 posting weights vs the
    default INT8. Prices the default's recall cost on our own engine."""
    name = "arcadedb_sparse_embedded_fp32"
    quant = "FP32"


class ArcadeEmbeddedNoCompact(ArcadeEmbedded):
    """Settle-step ablation; de-confounds the deployment axis.

    The server cannot trigger compaction (no SQL/HTTP path, engine #5144), so
    "embedded (compacted) vs server (as-shipped)" mixes transport cost with
    settle-step cost. Skipping compaction here gives the decomposition:
        embedded            vs embedded_nocompact -> settle-step cost
        embedded_nocompact  vs server             -> pure transport cost
    """
    name = "arcadedb_sparse_embedded_nocompact"

    def post_build(self):
        pass  # deliberately no compaction


class ArcadeServer(ArcadeEmbedded):
    name = "arcadedb_sparse_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "dbbenchpass")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        # report the real server version, not a hardcoded guess (the image is
        # digest-pinned in runner.py; keep the results row honest)
        try:
            info = self.rq.get(f"http://{host}:{port}/api/v1/server", timeout=30)
            self.version = "server:" + (info.json().get("version") or "?")
        except Exception:
            self.version = "server:unknown"
        for ddl in ["CREATE DOCUMENT TYPE Doc",
                    "CREATE PROPERTY Doc.id LONG",
                    "CREATE PROPERTY Doc.tokens ARRAY_OF_INTEGERS",
                    "CREATE PROPERTY Doc.weights ARRAY_OF_FLOATS",
                    'CREATE INDEX ON Doc (tokens, weights) LSM_SPARSE_VECTOR '
                    'METADATA {"dimensions": %d}' % DIMENSIONS]:
            self._cmd("sql", ddl)
        self.idx_name = "Doc[tokens,weights]"

    def post_build(self):
        # Settle step, now client-reachable over HTTP/SQL via COMPACT INDEX
        # (engine #5144, in 26.8.x). This gives the server the same settle the
        # embedded adapter gets via idx.compact(), so the deployment axis
        # isolates transport, not the settle asymmetry. Synchronous.
        self._cmd("sql", "COMPACT INDEX `Doc[tokens,weights]`")

    def _cmd(self, language, command, params=None):
        payload = {"language": language, "command": command}
        if params:
            payload["params"] = params
        r = self.rq.post(f"{self.base}/command/bench", json=payload, timeout=600)
        r.raise_for_status()
        return r.json().get("result", [])

    def _query(self, command, params=None):
        payload = {"language": "sql", "command": command}
        if params:
            payload["params"] = params
        r = self.rq.post(f"{self.base}/query/bench", json=payload, timeout=600)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, n_docs):
        buf = []
        for i, idx, vals in gen_docs(n_docs):
            t = ",".join(map(str, idx))
            # 9 decimals: exact float32 round-trip, keeps ingest == GT weights
            w = ",".join(f"{v:.9f}" for v in vals)
            buf.append(f"INSERT INTO Doc SET id = {i}, tokens = [{t}], "
                       f"weights = [{w}]")
            if len(buf) >= INGEST_BATCH:
                self._cmd("sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._cmd("sqlscript", ";".join(buf))

    def search(self, idx, vals, k):
        rows = self._query(
            "SELECT expand(`vector.sparseNeighbors`(:i, :t, :w, :k))",
            {"i": self.idx_name, "t": idx, "w": vals, "k": k})
        self._last_rids = [r["@rid"] for r in rows]
        return self._last_rids

    def resolve(self, rids):
        if not rids:
            return []
        in_list = ",".join(rids)
        rows = self._query(
            f"SELECT id, @rid AS r FROM [{in_list}]")
        by_rid = {r["r"]: r["id"] for r in rows}
        return [by_rid.get(x, -1) for x in rids]
    def close(self):
        # Served arm: the database lives in another container. Closing here
        # releases the HTTP session only, which is why a served arm's
        # lifecycle equivalent is stopping that container, not this call.
        try:
            self.s.close()
        except Exception:
            pass

class Qdrant(Base):
    name = "qdrant_sparse"
    COLL = "docs"

    def connect(self):
        from qdrant_client import QdrantClient, models
        self.models = models
        host = os.environ["BENCH_SERVER_HOST"]
        self.cl = QdrantClient(url=f"http://{host}:6333", timeout=600)
        # THE SERVER'S version, not the string "qdrant" (#156). The paper says
        # served comparators are pinned by image digest, which is true of
        # runner.py's config but was unverifiable from the artifact a reader
        # actually gets. Never lose a run over provenance: record the reason.
        try:
            self.version = "qdrant:" + str(self.cl.info().version)
        except Exception as e:
            self.version = f"qdrant:unknown ({e.__class__.__name__})"
        self.cl.create_collection(
            collection_name=self.COLL,
            vectors_config={},
            sparse_vectors_config={
                "text": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False))})

    def build(self, n_docs):
        m, batch = self.models, []
        for i, idx, vals in gen_docs(n_docs):
            batch.append(m.PointStruct(
                id=i, vector={"text": m.SparseVector(indices=idx, values=vals)}))
            if len(batch) >= INGEST_BATCH:
                self.cl.upsert(self.COLL, batch, wait=False)
                batch = []
        if batch:
            self.cl.upsert(self.COLL, batch, wait=True)

    def post_build(self):
        # wait for indexing/optimizer to settle
        while True:
            info = self.cl.get_collection(self.COLL)
            if str(info.status).lower().endswith("green"):
                return
            time.sleep(0.5)

    def search(self, idx, vals, k):
        m = self.models
        hits = self.cl.query_points(
            self.COLL,
            query=m.SparseVector(indices=idx, values=vals),
            using="text", limit=k, with_payload=False).points
        return [h.id for h in hits]

    def resolve(self, ids):
        return ids


class Milvus(Base):
    name = "milvus_sparse"
    COLL = "docs"

    def connect(self):
        from pymilvus import DataType, MilvusClient
        host = os.environ["BENCH_SERVER_HOST"]
        self.cl = MilvusClient(uri=f"http://{host}:19530")
        try:
            import pymilvus
            self.version = ("milvus:"
                            + str(self.cl.get_server_version())
                            + "/pymilvus:" + pymilvus.__version__)
        except Exception as e:                     # noqa: BLE001
            self.version = f"milvus:unknown ({e.__class__.__name__})"
        # THE SERVER'S version, not the string "milvus" (#156).
        try:
            self.version = "milvus:" + str(self.cl.get_server_version())
        except Exception as e:
            self.version = f"milvus:unknown ({e.__class__.__name__})"
        schema = self.cl.create_schema(auto_id=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("emb", DataType.SPARSE_FLOAT_VECTOR)
        index_params = self.cl.prepare_index_params()
        index_params.add_index(field_name="emb",
                               index_type="SPARSE_INVERTED_INDEX",
                               metric_type="IP")
        self.cl.create_collection(self.COLL, schema=schema,
                                  index_params=index_params)

    def build(self, n_docs):
        batch = []
        for i, idx, vals in gen_docs(n_docs):
            batch.append({"id": i, "emb": dict(zip(idx, vals))})
            if len(batch) >= INGEST_BATCH:
                self.cl.insert(self.COLL, batch)
                batch = []
        if batch:
            self.cl.insert(self.COLL, batch)

    def post_build(self):
        """Wait for the real index, not merely for the collection to load.

        Same defect as the dense lane: `load_collection` returns while the index
        is still building, and the pinned image serves the gap from a temporary
        index (`interimIndex.enableIndex: true` in its own milvus.yaml). The
        published sparse rates give it away -- a graph/inverted build is
        superlinear, so its rate must FALL with corpus size, and ours was flat
        across an 88x range:
            tiny 100k    9,083 docs/s
            small 1M     9,787 docs/s
            medium 8.8M  8,819 docs/s
        That is ingest, not a build. state == "Finished" alone is insufficient;
        the probe caught Finished with pending_index_rows = 855,349.

        This MOVES PUBLISHED NUMBERS: all 15 sparse Milvus rows re-run and the
        change is disclosed.
        """
        self.cl.flush(self.COLL)
        deadline = time.time() + 7200
        d = None
        while time.time() < deadline:
            d = self.cl.describe_index(self.COLL, "emb")
            if (d.get("state") == "Finished"
                    and int(d.get("pending_index_rows", 0)) == 0
                    and int(d.get("indexed_rows", -1)) == int(d.get("total_rows", -2))):
                break
            time.sleep(1.0)
        else:
            raise RuntimeError(f"milvus sparse index did not finish within 7200s: {d}")
        self.cl.load_collection(self.COLL)

    def search(self, idx, vals, k):
        res = self.cl.search(self.COLL, data=[dict(zip(idx, vals))],
                             anns_field="emb", limit=k,
                             search_params={"metric_type": "IP"})
        return [hit["id"] for hit in res[0]]

    def resolve(self, ids):
        return ids


class Elastic(Base):
    name = "elasticsearch_sparse"
    IDX = "docs"

    def connect(self):
        from elasticsearch import Elasticsearch, helpers
        self.helpers = helpers
        host = os.environ["BENCH_SERVER_HOST"]
        self.es = Elasticsearch(f"http://{host}:9200", request_timeout=600)
        self.version = self.es.info()["version"]["number"]
        # INDEX-TIME PRUNING IS OFF HERE, DELIBERATELY, AND THAT IS AN OVERRIDE.
        #
        # Elasticsearch 9.1 turned token pruning on by default for every new
        # sparse_vector field ("With any new indices created, token pruning
        # will be turned on by default"), with thresholds Elastic states were
        # "chosen based on tests using ELSERv2" -- their own sparse model. This
        # corpus is SPLADE-cocondenser, a different weight distribution, and
        # the cost of applying one model's thresholds to another's vectors is
        # measurable in our own history:
        #
        #     ES 9.0.0 (no such default)   recall@10  0.991 - 0.9985
        #     ES 9.4.1 (pruning on)        recall@10  0.725 - 0.929
        #
        # Same corpus, same harness, same adapter. Qdrant and Milvus retrieve
        # exactly and score ~0.99 on the same queries, so leaving this on would
        # compare an approximate Elasticsearch against exact competitors and
        # print 0.75 beside their 0.99 -- which reads as "Elasticsearch is bad
        # at sparse retrieval" and is not what the number means.
        #
        # This is the same class of override as ES's forcemerge, Milvus's
        # flush, Qdrant's green-wait and the matched HNSW degree: equalise the
        # operating point, then disclose it. BENCH_ES_PRUNE=1 restores the
        # stock default, and the choice is recorded on every row either way so
        # no reader has to infer which one produced a given number.
        self.prune = os.environ.get("BENCH_ES_PRUNE", "0") == "1"
        self.es.indices.create(index=self.IDX, mappings={
            "properties": {"emb": {"type": "sparse_vector",
                                   "index_options": {"prune": self.prune}}}},
            settings={"number_of_shards": 1, "number_of_replicas": 0})

    @staticmethod
    def _tok(idx, vals):
        return {f"t{d}": float(v) for d, v in zip(idx, vals)}

    def build(self, n_docs):
        def actions():
            for i, idx, vals in gen_docs(n_docs):
                yield {"_index": self.IDX, "_id": i,
                       "_source": {"emb": self._tok(idx, vals)}}
        self.helpers.bulk(self.es, actions(), chunk_size=INGEST_BATCH,
                          request_timeout=600)

    def post_build(self):
        self.es.indices.refresh(index=self.IDX)
        self.es.indices.forcemerge(index=self.IDX, max_num_segments=1,
                                   request_timeout=1200)

    def search(self, idx, vals, k):
        res = self.es.search(index=self.IDX, size=k, _source=False, query={
            "sparse_vector": {"field": "emb",
                              "query_vector": self._tok(idx, vals)}})
        return [int(h["_id"]) for h in res["hits"]["hits"]]

    def resolve(self, ids):
        return ids


BACKENDS = {c.name: c for c in
            [ArcadeEmbedded, ArcadeEmbeddedFP32, ArcadeEmbeddedNoCompact,
             ArcadeServer, Qdrant, Milvus, Elastic]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", default="search")  # single suite for l3s
    ap.add_argument("--scale", default="micro", choices=list(SCALE_DOCS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # PHASE TIMERS. This lane recorded build_s and nothing else, and build is
    # a MINORITY of the cell: at the 8.84M tier the median build is 15.6 min
    # against cell wall-clocks of 130-190 min, so 85% of the most expensive
    # measurement on the machine was unaccounted for. Not knowing where it
    # goes is also why the campaign could not be honestly costed or shortened.
    _p0 = time.perf_counter()
    # COUNTED, not asserted. n_docs was SCALE_DOCS[scale], a module constant, so
    # PAGE-SPEC rule 4's corpus fingerprint was fingerprinting a constant: point a
    # lane at base_small.csr where base_1M.csr was meant and the row still claims
    # the full corpus, build_docs_per_s is inflated by the same factor, and the
    # gate that exists to catch exactly that passes. The generator is wrapped so
    # the row records what was actually ingested, and a shortfall is a refusal
    # rather than a smaller number nobody reads.
    # `global` FIRST. Defining `def gen_docs` below makes the name local to this
    # entire function, so without this the `_raw = gen_docs` line reads an
    # unassigned local and raises UnboundLocalError -- which compile() cannot
    # catch, being a runtime error, and which failed every l3s cell. The adapters
    # resolve this name from module globals at call time, so rebinding the global
    # is also what makes the count reach them.
    global gen_docs
    n_docs = SCALE_DOCS[args.scale]
    _ingested = {"n": 0}
    _gen_docs_raw = gen_docs

    def _counted_gen_docs(n, *a, **kw):
        for item in _gen_docs_raw(n, *a, **kw):
            _ingested["n"] += 1
            yield item

    gen_docs = _counted_gen_docs

    queries = gen_queries(SCALE_QUERIES[args.scale])
    _query_gen_s = time.perf_counter() - _p0

    _p0 = time.perf_counter()
    gt = None
    if os.environ.get("BENCH_SPARSE_SOURCE") == "bigann":
        gt = _src.load_gt(args.scale)
    else:
        gt_path = f"/data/sparse/{args.scale}/gt.npy"
        if os.path.exists(gt_path):
            import numpy as np
            gt = np.load(gt_path)
    _gt_load_s = time.perf_counter() - _p0

    b = BACKENDS[args.backend]()
    out = {"lane": "l3s", "n_docs": n_docs, "dims": DIMENSIONS, "k": K,
           "n_queries": len(queries),
           "query_gen_s": round(_query_gen_s, 2),
           "gt_load_s": round(_gt_load_s, 2)}

    t0 = time.perf_counter()
    b.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = getattr(b, "version", "?")
    # Only Elasticsearch sets this. A row must say which operating point it
    # measured; the 9.0.0-vs-9.4.1 recall gap was only diagnosable because the
    # engine version happened to be recorded, and pruning is not visible from
    # the version alone once it is configurable.
    if hasattr(b, "prune"):
        out["es_prune"] = b.prune

    t0 = time.perf_counter()
    b.build(n_docs)
    b.post_build()
    build = time.perf_counter() - t0
    out["build_s"] = round(build, 2)
    out["build_docs_per_s"] = round(n_docs / build, 1)

    # timed warm search
    _search_t0 = time.perf_counter()
    lats, raw_results = [], []
    for qi, (idx, vals) in enumerate(queries):
        t0 = time.perf_counter()
        ids = b.search(idx, vals, K)
        dt = time.perf_counter() - t0
        if qi >= WARMUP:
            lats.append(dt)
        raw_results.append(ids)
    out.update({f"query_{k2}": v for k2, v in pct(lats).items()})
    out["qps"] = round(len(lats) / sum(lats), 1)
    out["search_wall_s"] = round(time.perf_counter() - _search_t0, 2)

    # recall: was untimed and is NOT free at scale, since it resolves every
    # returned hit back to a doc ordinal. Untimed does not mean zero, and an
    # unaccounted phase is exactly what made this lane's cost unexplainable.
    _recall_t0 = time.perf_counter()
    if gt is not None:
        recalls = []
        for qi, ids in enumerate(raw_results):
            ordinals = b.resolve(ids)
            recalls.append(recall_at_k(ordinals, gt[qi]))
        out["recall_at_10"] = round(statistics.mean(recalls), 4)
    else:
        out["recall_at_10"] = None
        out["gt_missing"] = True
    out["recall_calc_s"] = round(time.perf_counter() - _recall_t0, 2)
    # WHAT THIS CELL COULD NOT ACCOUNT FOR. Sum of the phases we now time,
    # against the wall clock the runner sees. A large residual means there is
    # still a phase nobody is measuring, and it says so in the row rather than
    # leaving the next person to rediscover it from a campaign log.
    out["phases_accounted_s"] = round(
        out.get("connect_s", 0) + out.get("query_gen_s", 0)
        + out.get("gt_load_s", 0) + out.get("build_s", 0)
        + out.get("search_wall_s", 0) + out.get("recall_calc_s", 0), 2)

    # Read the cpuset, heap and memory cap out of this container's own cgroup.
    # Without them a cell cannot be reproduced or extended from its own
    # artifacts, which is why T4's 8.84M row is permanently stuck at N=3: reps
    # added later under guessed conditions would be worse than an honest N=3.
    # run_conditions() reads rather than accepts assertions, since a driver
    # told its own version is how one overlay stamped dev22 onto a dev20 run.
    #
    # Careful with engine_version: this lane already set it above to the
    # BACKEND's version, which for a Qdrant or Elasticsearch row is that
    # engine's version and not ours. run_conditions() reports the installed
    # arcadedb-embedded wheel, so letting it merge freely would relabel every
    # CLOSE, AND TIME IT (#155). This lane hard-exited without ever shutting an
    # engine down, so deferred shutdown work was never paid by anyone and the
    # on-disk state it left was a crash state. A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. After all measurement, so nothing above moves.
    _t = time.perf_counter()
    b.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)

    # comparator row with ArcadeDB's version. Keep the system-under-test's
    # version under engine_version and file the wheel separately.
    try:
        from bench_common import run_conditions
        cond = run_conditions(lane="l3s", backend=args.backend,
                              scale=args.scale)
        cond["wheel_version"] = cond.pop("engine_version", None)
        out.update(cond)
    except Exception as e:  # never lose a completed run over provenance
        out["conditions_error"] = f"{e.__class__.__name__}: {e}"

    # Recorded at the END, when the generator has actually run. A shortfall is a

    # refusal: a row claiming the full corpus while a fraction was ingested is

    # what rule 4's fingerprint cannot catch on its own, and every per-second

    # figure in the row is inflated by the same factor.

    out["n_docs_ingested"] = _ingested["n"]

    if _ingested["n"] and _ingested["n"] < n_docs:

        raise SystemExit(

            f"ingested {_ingested['n']:,} docs against a declared {n_docs:,} for "

            f"scale {args.scale}: the corpus is short, so build_docs_per_s is "

            f"inflated by {n_docs/_ingested['n']:.2f}x.")


    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    # Fail fast. JPype's JVM keeps non-daemon threads (AsyncFlush,
    # TransactionManager) alive after a Python exception, so a crashed cell
    # would otherwise sit until the runner's multi-hour watchdog. os._exit
    # skips interpreter cleanup and takes the JVM down with it.
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
