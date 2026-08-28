#!/usr/bin/env python3
"""L3d dense-vector lane: SIFT1M (ann-benchmarks, exact L2 ground truth).

Data: /data/dense/sift_{train,test,neighbors}.npy (host-prepped by
gen_dense_npy.py; containers need only numpy).

Fairness: matched HNSW operating point, ef_construction=100, ef_search=100,
L2 metric, FP32 vectors everywhere. "Matched" is expressed in TWO constants
because the engines do not share units: ArcadeDB's maxConnections is a
per-layer bound (M, default 32) while hnswlib-style engines double M at the
base layer (COMPARATOR_M, default 16). Equal base-layer degree is the match;
a single shared number would not be one. Every row records the value its own
backend received, under degree_param/degree_family, so a reader never has to
know which units a given row is in. Disclosed deviations: LanceDB's HNSW variant
is IVF_HNSW_SQ (int8 scalar-quantized, its only HNSW offering; nprobes=20
default); sqlite-vec is an exact scan (no ANN index exists), so it is the
recall=1.0 embedded baseline. Recall@10 is reported next to latency so every
precision/algorithm difference is visible.

Scales: small = full 1M (the canonical unit). Smaller scales cap the corpus and
keep only queries whose true top-k lies inside the cap (subset-exact recall).
"""
import argparse
import json
import os
import statistics
import sys
import time
import traceback

import numpy as np

DATA = os.environ.get("BENCH_DENSE_DATA", "/data/dense")
DIM = 128
K = 10
# Default is 32, NOT 16, and the difference is the whole point of #5352.
# ArcadeDB's maxConnections is a per-layer bound; hnswlib doubles M at the base
# layer. So maxConnections=32 is the equivalent of the M=16 that Chroma, Qdrant,
# Milvus, DuckDB-VSS and LanceDB are all given below, and 16 would silently
# build ArcadeDB at half their degree. That mistake is already on the record: it
# published "recall 0.951 vs 0.971, a small deficit" in the scipy paper, and it
# is what took this lane's dense recall from 0.87 to 0.95 once corrected.
#
# The paper reports this lane as "degree-matched", so the DEFAULT has to be the
# configuration the paper describes. runner.py only passes BENCH_DENSE_M
# through, it never sets it, so a default of 16 meant every re-run that forgot
# to export it reproduced the unmatched configuration and would have read as a
# regression, or worse been folded into the paper at the October freeze re-measure.
# Set BENCH_DENSE_M=16 explicitly to run the half-degree ablation on purpose.
M = int(os.environ.get("BENCH_DENSE_M", "32"))

# The comment above says maxConnections=32 is the equivalent of M=16 for the
# hnswlib-style engines, and until 2026-08-01 the code did not implement that:
# ONE constant was handed to both a per-layer bound (ArcadeDB) and to hnswlib's
# M (Chroma, Qdrant, Milvus, DuckDB-VSS, LanceDB), which are different units.
#
# It was harmless while the default was 16, which is why every published
# comparator row records m=16 and the T5 dense block as printed today IS
# degree-matched. Raising the default to 32 fixed ArcadeDB and silently
# mis-set all five comparators, so the code stopped being able to reproduce
# the configuration the paper describes. Nothing had run since, so no
# published number is affected -- but the October freeze re-measures this lane,
# and would have built every comparator at twice its intended degree while
# ArcadeDB stayed correct. That is the same hazard the comment above was
# written to prevent, aimed the other way, and it lands in our favour.
#
# Verified against the artifacts before changing anything: at deep10m every
# comparator row carries m=16 dated 2026-07-19, and the ArcadeDB rows that T5
# prints carry m=32 dated 2026-07-20.
COMPARATOR_M = int(os.environ.get("BENCH_DENSE_COMPARATOR_M", str(M // 2)))

EF_CONSTRUCTION = 100
EF_SEARCH = 100
SCALE_DOCS = {"micro": 5_000, "tiny": 100_000, "small": 1_000_000,
              "deep10m": 9_990_000}
N_QUERIES = 1_000
BATCH = 10_000

# The DDL's vocabulary and the results' vocabulary disagreed, and a recorded
# label could not be fed back in as an input.
#
# LSM_VECTOR accepts NONE/INT8/BINARY/PRODUCT, and unquantized is spelled by
# OMITTING the key entirely. But dense_multipass_driver.py records that same
# state as "fp32", and every T5 fp32 row, task and paper cell calls it fp32
# too. So the one name everyone uses for the arm was the one name the DDL
# rejects, and BENCH_DENSE_QUANT=fp32 dies inside CREATE INDEX with
# "Invalid quantization type: fp32".
#
# That cost three full DEEP-10M builds on 2026-08-03 (q3_fp32_b1..b3, ~2.5 min
# each before the throw). The F5 version gate above them passed, because the
# wheel WAS the right version; nothing validated the value. Published fp32
# numbers are unaffected: the lane scripts reach this path with the variable
# unset, which was always correct.
#
# So accept the reported label as input and normalise it, rather than only
# rejecting it. Anything outside the engine's set now fails here, in the first
# second, naming the valid values, instead of after the corpus is ingested.
_QUANT_ALIASES = {"": "", "fp32": "", "float32": "", "f32": "", "none": ""}
_QUANT_DDL = {"INT8", "BINARY", "PRODUCT"}


def lib_version(module, dist):
    """Report a library's version from its installed distribution metadata.

    `getattr(mod, "__version__", "?")` is not a version check, it is a coin
    toss: a package that simply does not define the attribute records "?" and
    the row looks like a lookup failure rather than a package that never
    exposed it. qdrant-client is exactly that case, and provenance_check
    rejected the whole Qdrant row on 2026-08-04 for a field that could never
    have been populated. importlib.metadata reads what pip installed, so it
    answers for every distribution whether or not the module cooperates.

    Falls back to the attribute, then to a marker that says which lookup
    failed, because "unknown" with no cause is what made the original problem
    hard to see.
    """
    try:
        from importlib.metadata import version
        return version(dist)
    except Exception:
        v = getattr(module, "__version__", None)
        return v if v else f"unknown (no metadata for {dist!r}, no __version__)"


def resolve_quant(raw):
    """Map BENCH_DENSE_QUANT to what LSM_VECTOR's METADATA accepts.

    Returns "" when the quantization key must be omitted (unquantized fp32).
    """
    v = (raw or "").strip()
    if v.lower() in _QUANT_ALIASES:
        return _QUANT_ALIASES[v.lower()]
    if v.upper() in _QUANT_DDL:
        return v.upper()
    raise SystemExit(
        f"BENCH_DENSE_QUANT={raw!r} is not a quantization LSM_VECTOR accepts.\n"
        f"  unquantized (reported as 'fp32'): leave unset, or fp32/none\n"
        f"  quantized: {'/'.join(sorted(_QUANT_DDL))}"
    )


def degree_stamp(backend):
    """The degree this backend was given, and the unit it is in.

    Shared so the lane script and dense_multipass_driver cannot disagree. They
    did: the driver stamped no degree at all, so the DEEP-10M cells the paper
    prints could not be shown to be degree-matched, while the lane's own small
    tier could. F7 reported the tier as passing by reading superseded rows.
    One function, called from both, is the only version of this that stays
    true.
    """
    hnswlib_style = {"chroma_dense", "lancedb_dense", "qdrant_dense",
                     "milvus_dense", "duckdb_vss_dense"}
    # A PRECISION ARM IS THE SAME INDEX AT A DIFFERENT PRECISION, so it keeps
    # its parent's degree and unit. Without this strip, qdrant_dense_int8 and
    # milvus_dense_int8 missed the set and were stamped "exact_scan_no_ann" --
    # a false provenance claim (they are HNSW at M=16) that would also have
    # made F7's degree-matching invariant vacuous for exactly the rows the
    # ablation exists to compare.
    base = str(backend)
    if base.endswith("_int8"):
        base = base[:-len("_int8")]
    if base.startswith("arcadedb"):
        return M, "arcadedb_maxconnections_per_layer"
    if base in hnswlib_style:
        return COMPARATOR_M, "hnswlib_m_doubled_at_base"
    return None, "exact_scan_no_ann"


def canonical_quant_label(raw):
    """The one name for this arm in results, whatever the input spelled."""
    return resolve_quant(raw) or "fp32"


def load_dataset(scale):
    global DIM
    if scale == "deep10m":
        # ann-benchmarks deep-image-96-angular: cosine GT. Rows are normalized
        # to unit length so L2 ranking == cosine ranking and every adapter's
        # L2 configuration (and the shipped GT) stays valid unchanged.
        DIM = 96
        mm = np.load(os.path.join(DATA, "..", "deep10m", "deep_base.npy"),
                     mmap_mode="r")
        # chunked copy+normalize: a single np.array(memmap) holds the 3.8GB
        # anon copy WHILE the read fills 3.8GB of page cache — transiently
        # ~7.6GB, which OOM-killed the 7GB client share of server-topology
        # cells. Chunking keeps cache pages clean/reclaimable (peak ~4.2GB).
        base = np.empty(mm.shape, dtype=np.float32)
        CH = 500_000
        for s in range(0, mm.shape[0], CH):
            c = np.array(mm[s:s + CH], dtype=np.float32)  # copy: asarray on a float32 memmap returns a read-only view
            c /= np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-12)
            base[s:s + CH] = c
        test = np.load(os.path.join(DATA, "..", "deep10m",
                                    "deep_query.npy"))[:N_QUERIES]
        test = test / np.maximum(
            np.linalg.norm(test, axis=1, keepdims=True), 1e-12)
        gt = np.load(os.path.join(DATA, "..", "deep10m",
                                  "deep_gt.npy"))[:N_QUERIES, :K]
        return base, test.astype(np.float32), gt
    train = np.load(os.path.join(DATA, "sift_train.npy"), mmap_mode="r")
    test = np.load(os.path.join(DATA, "sift_test.npy"))[:N_QUERIES]
    n = SCALE_DOCS[scale]
    full = np.load(os.path.join(DATA, "sift_train.npy"), mmap_mode="r").shape[0]
    train = np.asarray(train[:n], dtype=np.float32)
    if n == full:  # full corpus: use the shipped exact GT
        gt = np.load(os.path.join(DATA, "sift_neighbors.npy"))[:N_QUERIES, :K]
    else:  # subset scale: exact GT by chunked brute force (L2)
        qn = (test ** 2).sum(1)
        best_d = np.full((len(test), K), np.inf, dtype=np.float64)
        best_i = np.full((len(test), K), -1, dtype=np.int64)
        CH = 100_000
        for s in range(0, n, CH):
            c = train[s:s + CH]
            d = qn[:, None] - 2.0 * test @ c.T + (c ** 2).sum(1)[None, :]
            md = np.concatenate([best_d, d], axis=1)
            mi = np.concatenate(
                [best_i, np.broadcast_to(np.arange(s, s + len(c)),
                                         (len(test), len(c)))], axis=1)
            top = np.argpartition(md, K - 1, axis=1)[:, :K]
            rows = np.arange(len(test))[:, None]
            order = np.argsort(md[rows, top], axis=1)
            best_d = md[rows, top][rows, order]
            best_i = mi[rows, top][rows, order]
        gt = best_i
    return train, test, gt


class Base:
    # Same default as l3_sparse.Base. Every adapter in this lane already sets a
    # version, which is why the dense table's identities are clean; this exists
    # so the next one added cannot publish without one by simply forgetting.
    version = "unset"

    name = "?"
    version = "?"

    def connect(self):
        pass

    def build(self, vecs):
        raise NotImplementedError

    def post_build(self):
        pass

    def engine_stats(self):
        """Engine-side counters for this run, or {} for engines that have none.

        WHY THIS EXISTS NOW. The pin moved to b7c6c800d, which carries #6858:
        a query-side delta-scan trigger that is ON BY DEFAULT and deliberately
        does MORE background rebuild work than the engine used to. If dense
        timings move against the previous pin, the row has to be able to say
        whether that trigger fired -- otherwise the campaign records a number
        and loses the reason, which is the failure this whole harness keeps
        relearning. Upstream added graphWalkVisitedAvg, deltaScanBudget,
        deltaScanWorkSinceRebuild and deltaScanWorkTarget precisely so the
        decision is observable instead of inferred.

        Pass-through, never a fixed key list: the engine grows counters between
        releases and a whitelist here would silently drop the next one.
        """
        return {}

    def search(self, qvec, k):
        raise NotImplementedError

    def close(self):
        """Release the engine handle. Overridden where there is one to release.

        A no-op here records close_s=0.0, and 0.0 must mean "this engine has
        nothing to release", never "we did not ask". The distinction decides
        whether a close cost is comparable: ArcadeDB measured 157.5 s against
        a 185.9 s build at l3d/small, and reporting that beside an unmeasured
        0.0 would be the same asymmetry, pointed the other way. Adapters with
        a real handle override this; adapters whose library exposes none set
        close_note instead, so the row says which case it is.
        """

    close_note = None


class ArcadeEmbedded(Base):
    name = "arcadedb_dense_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        self._a = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # ARCADEDB_EXTRA_JVM_ARGS: space-separated extras (e.g. an
        # -agentpath:...  profiler agent for the #3144 heap investigation)
        extra = os.environ.get("ARCADEDB_EXTRA_JVM_ARGS", "")
        # THE HNSW BUILD CACHE IS BOUNDED, and this is a disclosed fairness
        # override rather than a tuning choice.
        #
        # Since #3144 the engine auto-sizes this cache to hold the WHOLE corpus
        # when it fits graphBuildCacheMaxHeapPercent (default 25). At 9.99M x
        # 128 that is 5.36 GiB of heap, against the flat 100,000-vector bound
        # (55 MiB) the engine shipped before the fix -- a 100x increase, and it
        # applies only to the fp32 path where vectors live in the documents.
        #
        # No comparator caches its corpus during an index build. Accepting the
        # default would mean ArcadeDB takes 5.36 GiB that Qdrant, Milvus,
        # Chroma and LanceDB do not, and then raising the tier's envelope so it
        # fits -- room only one engine gets. That is the apples-to-oranges
        # default the config policy exists to equalize, so the bound is
        # restored to the engine's OWN previous default rather than to a number
        # we invented.
        #
        # BENCH_DENSE_BUILD_CACHE=0 restores the auto-sizing for the ablation
        # arm, so the cost of the default is measurable rather than asserted.
        cache = os.environ.get("BENCH_DENSE_BUILD_CACHE", "100000").strip()
        extra = (f"{extra} -Darcadedb.vectorIndex.graphBuildCacheSize={cache}").strip()
        self.build_cache_size = int(cache)
        # THE OTHER HALF OF THE AUTO POLICY. graphBuildCacheSize=0 caches the
        # whole corpus WHEN IT FITS this percentage of heap, so the percentage
        # is what decides whether auto-sizing degrades to eviction or takes
        # everything. At deep10m the corpus cache is 5.36 GiB against a 6.0 GiB
        # budget at the default 25% of a 24g heap: it fits by 11%, so the
        # engine grants the full cache and the build is left short. Lowering
        # the percentage is therefore the knob that could make AUTO-SIZING work
        # rather than the knob that bypasses it, which is the difference
        # between testing Luca's mechanism and routing around it.
        #
        # HOW SHORT IS NOT SETTLED (2026-08-20). The stall that made the default
        # look fatal was a SECOND build of the same graph (#6489, see the close()
        # comment below), so the 5.36 GiB cache and the redundant build were
        # never separated. Re-run this ablation on a release carrying #6490
        # before quoting a cost for the default.
        pct = os.environ.get("BENCH_DENSE_BUILD_CACHE_PCT", "").strip()
        if pct:
            extra = f"{extra} -Darcadedb.vectorIndex.graphBuildCacheMaxHeapPercent={pct}"
            self.build_cache_pct = int(pct)
        self.db = arcadedb.create_database(
            "/tmp/l3d_arcade",
            jvm_kwargs={"heap_size": heap,
                        "jvm_args": f"-Xms{heap} {extra}".strip()})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")

    def build(self, vecs):
        db = self.db
        db.command("sql", "CREATE VERTEX TYPE Article")
        db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
        db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
        db.begin()
        for vid in range(len(vecs)):
            db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                       {"v": vid, "e": self._a.to_java_float_array(vecs[vid])})
            if (vid + 1) % BATCH == 0:
                db.commit()
                db.begin()
        db.commit()
        quant = resolve_quant(os.environ.get("BENCH_DENSE_QUANT", ""))
        qline = f'"quantization": "{quant}", ' if quant else ""
        db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                   METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                   "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION}, {qline}
                   "storeVectorsInGraph": false, "addHierarchy": true }}''')

    def engine_stats(self):
        """The engine's own counters for this run.

        schema.get_index_by_name returns the raw Java TypeIndex, not the Python
        wrapper, so this is getStats() and not get_stats(), and the per-bucket
        LSMVectorIndex underneath is what carries the counters. Same access path
        delta_scan_probe.py uses, which was verified against the wheel after a
        first version guessed get_stats() and died having built 200k vectors.
        """
        try:
            ti = self.db.schema.get_index_by_name("Article[embedding]")
            st = ti.getIndexesOnBuckets()[0].getStats()
            return {str(k): int(st.get(k)) for k in st.keySet()}
        except Exception as e:                     # noqa: BLE001
            # Recorded, not swallowed: a missing stat block must read as a
            # reason, not as an empty dict indistinguishable from a comparator
            # that legitimately has no counters.
            return {"engine_stats_error": f"{type(e).__name__}: {e}"}

    def search(self, qvec, k):
        rows = self.db.query(
            "sql",
            "SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
            "ORDER BY distance",
            "Article[embedding]", self._a.to_java_float_array(qvec), k, EF_SEARCH,
        ).to_list()
        return [int(r["vid"]) for r in rows]

    def close(self):
        self.db.close()


class ArcadeServer(Base):
    """ArcadeDB over HTTP (client-server), same index/params as embedded."""
    # fp32, DECLARED, because this arm has no qline path: it cannot pass the
    # METADATA quantization key that ArcadeEmbedded uses. Before this the row
    # was labelled from BENCH_DENSE_QUANT, so a campaign exporting INT8 -- the
    # only way to drive the fp32/int8 axis from outside -- wrote server rows
    # stamped INT8 for an unquantized index, and the l3d table printed them as
    # the quantized arm.
    quantization = "fp32"
    name = "arcadedb_dense_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "dbbenchpass")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        try:
            r = self.rq.get(f"{self.base}/server", timeout=30).json()
            self.version = "server:" + str(r.get("version", "?"))
        except Exception:
            self.version = "server:?"

    def _cmd(self, language, command, timeout=1800):
        r = self.rq.post(f"{self.base}/command/bench",
                         json={"language": language, "command": command},
                         timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, vecs):
        self._cmd("sql", "CREATE VERTEX TYPE Article")
        self._cmd("sql", "CREATE PROPERTY Article.vid INTEGER")
        self._cmd("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
        buf = []
        for vid in range(len(vecs)):
            # 9 significant digits: exact float32 round-trip, matching the
            # sparse adapter. The embedded side passes exact float32 arrays via
            # to_java_float_array, so anything lossy here means the two
            # deployments index different numbers. Measured before changing it:
            # the previous "%.6f" kept ~4.5 significant digits and changed 0 of
            # 500 top-10 sets at 200k docs, so this is not a correction to any
            # published number, just removal of a question a reviewer would
            # rightly ask. Not tested at 10M, where neighbour gaps are tighter.
            w = ", ".join("%.9g" % x for x in vecs[vid])
            buf.append(f"INSERT INTO Article SET vid = {vid}, embedding = [{w}]")
            if len(buf) >= 500:
                self._cmd("sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._cmd("sqlscript", ";".join(buf))
        self._cmd("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                  METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                  "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION},
                  "storeVectorsInGraph": false, "addHierarchy": true }}''',
                  # A CLIENT TIMEOUT IS NOT A MEASUREMENT. At deep10m under the
                  # bounded 100k cache this fired at 6h with the server still
                  # working: its log showed insertion completing in 17,511 s and
                  # the optimization phase starting, so the row recorded rc=1
                  # for a build that was progressing normally. Four more reps
                  # would have spent 24 hours reproducing that. 12h is chosen to
                  # sit above the slowest build we have observed rather than
                  # near it, because the cost of a too-short timeout is a whole
                  # cell and the cost of a too-long one is only lateness.
                  timeout=12 * 3600)

    def search(self, qvec, k):
        w = ", ".join("%.9g" % x for x in qvec)  # see build(): float32 round-trip
        r = self.rq.post(f"{self.base}/query/bench", json={
            "language": "sql",
            "command": f"SELECT vid FROM (SELECT expand(vectorNeighbors("
                       f"'Article[embedding]', [{w}], {k}, {EF_SEARCH}))) "
                       f"ORDER BY distance"}, timeout=600)
        r.raise_for_status()
        return [int(x["vid"]) for x in r.json().get("result", [])]


class Chroma(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "chroma_dense"
    # chromadb 1.5.9 exposes no close/shutdown on PersistentClient (checked
    # dir(chromadb.Client)); it flushes per write. Nothing to ask for.
    close_note = "chromadb exposes no close()"

    def connect(self):
        import chromadb
        self.version = lib_version(chromadb, "chromadb")
        client = chromadb.PersistentClient(path="/tmp/l3d_chroma")
        self.col = client.create_collection("articles", metadata={
            "hnsw:space": "l2", "hnsw:M": COMPARATOR_M,
            "hnsw:construction_ef": EF_CONSTRUCTION, "hnsw:search_ef": EF_SEARCH})

    def build(self, vecs):
        ids = [str(i) for i in range(len(vecs))]
        for i in range(0, len(vecs), 5000):
            self.col.add(ids=ids[i:i + 5000],
                         embeddings=vecs[i:i + 5000].tolist())

    def search(self, qvec, k):
        res = self.col.query(query_embeddings=[qvec.tolist()], n_results=k)
        return [int(x) for x in res["ids"][0]]


class LanceDB(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "lancedb_dense"
    # lancedb 0.37.1 exposes no close on the connection (checked dir); its
    # tables are files written on commit.
    close_note = "lancedb exposes no close()"

    def connect(self):
        import lancedb
        self.version = lib_version(lancedb, "lancedb")
        self.db = lancedb.connect("/tmp/l3d_lance")

    def build(self, vecs):
        import pyarrow as pa
        tbl = pa.table({"id": pa.array(range(len(vecs)), type=pa.int64()),
                        "vector": pa.FixedSizeListArray.from_arrays(
                            pa.array(vecs.ravel(), type=pa.float32()), DIM)})
        self.tbl = self.db.create_table("articles", tbl)
        # IVF_HNSW_SQ is LanceDB's HNSW offering (int8 SQ; disclosed above)
        self.tbl.create_index(metric="l2", index_type="IVF_HNSW_SQ",
                              m=COMPARATOR_M, ef_construction=EF_CONSTRUCTION)

    def search(self, qvec, k):
        # Apply the search-time knobs. Without .ef() LanceDB used its own
        # default while every other engine ran at the lane's EF_SEARCH, which
        # is the operating-point matching F3 requires, and it showed up as
        # recall 0.711 against ~0.93 for everyone else. That was us measuring
        # it at defaults, not LanceDB being weak.
        #
        # nprobes is set because IVF_HNSW_SQ is IVF-partitioned where the other
        # HNSW engines are not, so it has a knob they do not have; a sweep
        # (out_lance_sweep.json) shows recall is flat across nprobes 10/20/50
        # at 0.9303, so 10 is chosen as the cheapest value that matches.
        rs = (self.tbl.search(qvec).limit(k)
              .ef(EF_SEARCH)
              .nprobes(10)
              .to_list())
        return [int(r["id"]) for r in rs]


class SqliteVec(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "sqlite_vec_dense"

    def close(self):
        self.cx.close()

    def connect(self):
        import sqlite3
        import sqlite_vec
        self.version = lib_version(sqlite_vec, "sqlite-vec")
        self.cx = sqlite3.connect("/tmp/l3d_sqlitevec.db")
        self.cx.enable_load_extension(True)
        sqlite_vec.load(self.cx)
        self.cx.enable_load_extension(False)

    def build(self, vecs):
        self.cx.execute(
            f"CREATE VIRTUAL TABLE v USING vec0(embedding float[{DIM}])")
        for i in range(0, len(vecs), BATCH):
            chunk = vecs[i:i + BATCH]
            self.cx.executemany(
                "INSERT INTO v (rowid, embedding) VALUES (?, ?)",
                [(i + j, chunk[j].tobytes()) for j in range(len(chunk))])
            self.cx.commit()

    def search(self, qvec, k):
        rows = self.cx.execute(
            "SELECT rowid FROM v WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance", (qvec.tobytes(), k)).fetchall()
        return [int(r[0]) for r in rows]


class DuckVSS(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "duckdb_vss_dense"

    def close(self):
        self.cx.close()

    def connect(self):
        import duckdb
        self.version = lib_version(duckdb, "duckdb")
        self.cx = duckdb.connect("/tmp/l3d_duck.db")
        self.cx.execute("INSTALL vss; LOAD vss;")
        self.cx.execute("SET hnsw_enable_experimental_persistence=true;")

    def build(self, vecs):
        # native bulk path: Arrow FixedSizeList -> DuckDB FLOAT[DIM] in one
        # relational insert (fairness: executemany over Python lists measured
        # ~2h for 1M x 128 and is a harness artifact, not the engine)
        import pyarrow as pa
        flat = pa.array(vecs.astype("float32").reshape(-1), type=pa.float32())
        tbl = pa.table({
            "id": pa.array(range(len(vecs)), type=pa.int64()),
            "vec": pa.FixedSizeListArray.from_arrays(flat, DIM),
        })
        self.cx.register("src", tbl)
        self.cx.execute(f"CREATE TABLE t AS SELECT id, vec::FLOAT[{DIM}] AS vec FROM src")
        self.cx.unregister("src")
        self.cx.execute(
            f"CREATE INDEX hn ON t USING HNSW (vec) "
            f"WITH (metric = 'l2sq', M = {COMPARATOR_M}, "
            f"ef_construction = {EF_CONSTRUCTION})")
        self.cx.execute(f"SET hnsw_ef_search = {EF_SEARCH}")

    def search(self, qvec, k):
        rows = self.cx.execute(
            f"SELECT id FROM t ORDER BY array_distance(vec, ?::FLOAT[{DIM}]) "
            f"LIMIT {k}", [qvec.tolist()]).fetchall()
        return [int(r[0]) for r in rows]


class Qdrant(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "qdrant_dense"

    def connect(self):
        from qdrant_client import QdrantClient
        import qdrant_client
        self.cl = QdrantClient(host=os.environ["BENCH_SERVER_HOST"], port=6333,
                               timeout=600)
        # THE SERVER'S version, and AFTER the client exists. lib_version reads
        # the CLIENT package, which is right for an embedded comparator and
        # wrong for a served one: the sparse lane records "qdrant:1.18.2" (the
        # server) while this recorded "1.19.0" (the client), so one paper
        # carried two meanings under one column name. The first version of this
        # fix asked before constructing self.cl, so the fallback fired every
        # time and it silently kept reporting the client -- caught by the smoke
        # only because the recorded string named which branch had run.
        try:
            self.version = "qdrant:" + str(self.cl.info().version)
        except Exception as e:
            self.version = ("qdrant-client:" + lib_version(qdrant_client, "qdrant-client")
                            + f" (server unreachable: {e.__class__.__name__})")

    def build(self, vecs):
        from qdrant_client import models as qm
        self.cl.create_collection(
            "articles",
            vectors_config=qm.VectorParams(
                size=DIM, distance=qm.Distance.EUCLID,
                hnsw_config=qm.HnswConfigDiff(m=COMPARATOR_M,
                                              ef_construct=EF_CONSTRUCTION)))
        for i in range(0, len(vecs), BATCH):
            self.cl.upsert("articles", points=qm.Batch(
                ids=list(range(i, i + len(vecs[i:i + BATCH]))),
                vectors=vecs[i:i + BATCH].tolist()))

    def post_build(self):  # settle: wait for green status (indexing done)
        from qdrant_client import models as qm  # noqa: F401
        for _ in range(600):
            if self.cl.get_collection("articles").status == "green":
                return
            time.sleep(1)

    def search(self, qvec, k):
        from qdrant_client import models as qm
        res = self.cl.query_points(
            "articles", query=qvec.tolist(), limit=k,
            search_params=qm.SearchParams(hnsw_ef=EF_SEARCH))
        return [int(p.id) for p in res.points]


class Milvus(Base):
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "fp32"
    name = "milvus_dense"

    def connect(self):
        from pymilvus import MilvusClient
        import pymilvus
        self.cl = MilvusClient(
            uri=f"http://{os.environ['BENCH_SERVER_HOST']}:19530", timeout=600)
        # THE SERVER'S version, and AFTER the client exists (see Qdrant above
        # for the ordering bug this had). The sparse lane records
        # "milvus:pkg/v2.6.13" while this recorded "3.0.1", which is pymilvus.
        try:
            self.version = "milvus:" + str(self.cl.get_server_version())
        except Exception as e:
            self.version = ("pymilvus:" + lib_version(pymilvus, "pymilvus")
                            + f" (server unreachable: {e.__class__.__name__})")

    def build(self, vecs):
        from pymilvus import DataType
        sch = self.cl.create_schema()
        sch.add_field("id", DataType.INT64, is_primary=True)
        sch.add_field("vec", DataType.FLOAT_VECTOR, dim=DIM)
        idx = self.cl.prepare_index_params()
        idx.add_index("vec", index_type="HNSW", metric_type="L2",
                      params={"M": COMPARATOR_M, "efConstruction": EF_CONSTRUCTION})
        self.cl.create_collection("articles", schema=sch, index_params=idx)
        for i in range(0, len(vecs), BATCH):
            self.cl.insert("articles", [
                {"id": i + j, "vec": vecs[i + j].tolist()}
                for j in range(min(BATCH, len(vecs) - i))])

    def post_build(self):  # settle: flush + load (Milvus's own recommended path)
        self.cl.flush("articles")
        self.cl.load_collection("articles")

    def search(self, qvec, k):
        res = self.cl.search("articles", data=[qvec.tolist()], limit=k,
                             search_params={"params": {"ef": EF_SEARCH}})
        return [int(h["id"]) for h in res[0]]


# ---------------------------------------------------------------- int8 arms
#
# EVERY ENGINE THAT CAN QUANTIZE, MEASURED AT BOTH PRECISIONS. The sparse lane
# has done this for ArcadeDB since #5143 (int8 default + an fp32 ablation); the
# dense lane did not, so T5 compared our fp32 against a mix of fp32 engines and
# ONE int8 engine (LanceDB, whose IVF_HNSW_SQ is its only HNSW offering), with
# the precision visible only in a row label. Our own int8 dense numbers came
# from a bespoke overlay rather than the lane.
#
# Each arm SUBCLASSES its fp32 sibling so the operating point cannot drift:
# same corpus, same degree, same ef, same settle step, same queries. Precision
# is the only variable, which is what makes the pair an ablation rather than
# two unrelated configurations.
#
# Chroma, DuckDB-VSS and sqlite-vec have no int8 path and get no arm:
# sqlite-vec is an exact scan by construction, and inventing a quantized
# configuration an engine does not ship would be a worse comparison than
# omitting it.


class ArcadeEmbeddedInt8(ArcadeEmbedded):
    """ArcadeDB with LSM_VECTOR INT8 quantization, its documented compact mode."""
    name = "arcadedb_dense_embedded_int8"
    # DECLARED, not inferred from the environment. See the stamping site: the
    # row's quantization used to be read from BENCH_DENSE_QUANT before connect(),
    # while this arm sets that variable inside build(), which runs later. Every
    # int8 row therefore recorded "fp32" while genuinely building an INT8 index.
    # The measurements were right and the label was wrong, which is the harder
    # defect to notice: nothing fails, the arm just stops being distinguishable
    # from the fp32 one in any check or table keyed on quantization.
    quantization = "INT8"

    def build(self, vecs):
        # resolve_quant reads BENCH_DENSE_QUANT; set it for this arm only so
        # the parent's DDL path is reused verbatim rather than duplicated.
        prev = os.environ.get("BENCH_DENSE_QUANT")
        os.environ["BENCH_DENSE_QUANT"] = "INT8"
        try:
            super().build(vecs)
        finally:
            if prev is None:
                os.environ.pop("BENCH_DENSE_QUANT", None)
            else:
                os.environ["BENCH_DENSE_QUANT"] = prev


class QdrantInt8(Qdrant):
    """Qdrant with scalar quantization (int8), its documented compact mode.

    quantile=0.99 and always_ram are Qdrant's own recommended defaults for
    scalar quantization.

    RESCORE MUST BE ASKED FOR AT SEARCH TIME, and assuming otherwise cost a
    whole tier of rows. The first version of this arm configured quantization
    on the collection and inherited Qdrant's plain search params, so every
    query was answered from int8 approximations alone with no re-ranking
    against the stored vectors. Recall came out at 0.2355 where every other
    dense arm sits between 0.93 and 1.00 -- caught by the monitor's recall
    range rule, not by reading the code.

    Rescore is what makes a quantized index a compression technique rather than
    a different algorithm: the int8 vectors narrow the candidate set and the
    originals decide the order. Without it the comparison would have published
    Qdrant-at-int8 as catastrophically inaccurate, which would have been our
    misconfiguration reported as their result -- the exact failure this lane's
    matched-operating-point rule exists to prevent.
    """
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "INT8"
    name = "qdrant_dense_int8"

    def search(self, qvec, k):
        from qdrant_client import models as qm
        res = self.cl.query_points(
            "articles", query=qvec.tolist(), limit=k,
            search_params=qm.SearchParams(
                hnsw_ef=EF_SEARCH,
                quantization=qm.QuantizationSearchParams(rescore=True)))
        return [int(p.id) for p in res.points]

    def build(self, vecs):
        from qdrant_client import models as qm
        self.cl.create_collection(
            "articles",
            vectors_config=qm.VectorParams(
                size=DIM, distance=qm.Distance.EUCLID,
                hnsw_config=qm.HnswConfigDiff(m=COMPARATOR_M,
                                              ef_construct=EF_CONSTRUCTION)),
            quantization_config=qm.ScalarQuantization(
                scalar=qm.ScalarQuantizationConfig(
                    type=qm.ScalarType.INT8, quantile=0.99, always_ram=True)))
        for i in range(0, len(vecs), BATCH):
            self.cl.upsert("articles", points=qm.Batch(
                ids=list(range(i, i + len(vecs[i:i + BATCH]))),
                vectors=vecs[i:i + BATCH].tolist()))


class MilvusInt8(Milvus):
    """Milvus HNSW_SQ at SQ8, its int8 scalar-quantized HNSW variant."""
    # DECLARED, not inferred from BENCH_DENSE_QUANT. Every arm that is genuinely
    # quantized says so on the class, so the row never has to consult an
    # environment variable that a different arm may have set for a different
    # reason. Before this, qdrant_dense_int8, milvus_dense_int8 and lancedb_dense
    # all recorded quantization="fp32", which made every int8 comparator row
    # indistinguishable from its fp32 sibling on the one field that names the
    # ablation.
    quantization = "INT8"
    name = "milvus_dense_int8"

    def build(self, vecs):
        from pymilvus import DataType
        sch = self.cl.create_schema()
        sch.add_field("id", DataType.INT64, is_primary=True)
        sch.add_field("vec", DataType.FLOAT_VECTOR, dim=DIM)
        idx = self.cl.prepare_index_params()
        idx.add_index("vec", index_type="HNSW_SQ", metric_type="L2",
                      params={"M": COMPARATOR_M, "efConstruction": EF_CONSTRUCTION,
                              "sq_type": "SQ8"})
        self.cl.create_collection("articles", schema=sch, index_params=idx)
        for i in range(0, len(vecs), BATCH):
            self.cl.insert("articles", [
                {"id": i + j, "vec": vecs[i + j].tolist()}
                for j in range(min(BATCH, len(vecs) - i))])


BACKENDS = {b.name: b for b in
            (ArcadeEmbedded, ArcadeServer, Chroma, LanceDB, SqliteVec, DuckVSS, Qdrant, Milvus,
             ArcadeEmbeddedInt8, QdrantInt8, MilvusInt8)}


def pct(vals):
    s = sorted(vals)
    n = len(s)
    return {"p50": s[n // 2], "p95": s[int(n * .95)], "p99": s[int(n * .99)],
            "mean": statistics.mean(s), "max": s[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", default="search")
    ap.add_argument("--scale", default="micro")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    train, test, gt = load_dataset(args.scale)
    out = {"lane": "l3d", "n_docs": len(train), "dims": DIM, "k": K,
           "n_queries": len(test), "m": M, "ef_construction": EF_CONSTRUCTION,
           "ef_search": EF_SEARCH}

    b = BACKENDS[args.backend]()
    out["hnsw_M"] = M  # recorded so degree-matched ablation rows are self-describing

    # What THIS backend actually received, and in which units. Recording one
    # shared M was how the mismatch above stayed invisible: every row quoted
    # the same number whether or not the backend was given it, so no artifact
    # could contradict the claim that the lane was degree-matched. A row that
    # names its own value and its own unit can be checked without reading the
    # adapter.
    out["degree_param"], out["degree_family"] = degree_stamp(args.backend)
    # Canonical label, so one state has one name. This recorder called
    # unquantized "none" while dense_multipass_driver.py called it "fp32", and
    # results/ carries both (36 "fp32", 30 "none") for runs that built the
    # identical index. Neither was wrong, they just never agreed, which is the
    # same split that made BENCH_DENSE_QUANT=fp32 look like a legal input.
    # Nothing consumes this field programmatically (it is provenance), so
    # normalising costs nothing and old artifacts stay readable.
    # THE OVERRIDE, ON THE ROW. A disclosed fairness override that only lives in
    # a comment is not disclosed to anyone reading the artifact.
    _bc = getattr(b, "build_cache_size", None)
    _bp = getattr(b, "build_cache_pct", None)
    if _bp is not None:
        out["graph_build_cache_pct"] = _bp
    if _bc is not None:
        out["graph_build_cache_size"] = _bc
        out["graph_build_cache_policy"] = (
            "engine auto (whole corpus up to 25% of heap)" if _bc == 0
            else "bounded to the engine's pre-#3144 default")
    # The ARM's own declaration wins over the environment. An adapter that
    # quantizes knows it; reading an env var here samples whatever happens to be
    # set at this instant, which for an arm that sets it later is the wrong
    # answer and a silent one.
    # NO ENV FALLBACK. Every arm declares what it actually built; an arm that does
    # not is a bug, not an invitation to guess from whatever happens to be set at
    # this instant. The old fallback is how three comparator arms came to record
    # fp32 while building int8, and how the server arm wore a label for a knob it
    # ignores.
    _declared = getattr(b, "quantization", None)
    if not _declared:
        raise SystemExit(
            f"{args.backend}: the arm declares no `quantization`. Add it to the class. "
            f"Reading BENCH_DENSE_QUANT here would label the row from a knob this arm "
            f"may not honour, which is exactly how the int8 comparator rows came to say fp32.")
    _asked = os.environ.get("BENCH_DENSE_QUANT", "").strip()
    if _asked and canonical_quant_label(_asked) != canonical_quant_label(_declared):
        raise SystemExit(
            f"{args.backend}: BENCH_DENSE_QUANT={_asked!r} but this arm builds "
            f"{_declared!r} and cannot honour the request. Refusing rather than "
            f"labelling the row from a knob that changed nothing.")
    out["quantization"] = canonical_quant_label(_declared)
    t0 = time.perf_counter()
    b.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = b.version

    t0 = time.perf_counter()
    b.build(train)
    b.post_build()
    build = time.perf_counter() - t0
    out["build_s"] = round(build, 2)
    out["build_docs_per_s"] = round(len(train) / build, 1)
    # Captured AFTER the build and again after the timed passes below, because
    # #6858's trigger fires from the QUERY path: a build-time snapshot alone
    # cannot show a rebuild that the searches provoked.
    out["engine_stats_after_build"] = b.engine_stats()

    WARM = 20
    timed_n = len(test) - WARM
    # HELD OUT, not the head of the timed set. This warmed on test[:20] and
    # then timed range(len(test)), so the first 20 queries of every pass -
    # including pass 0, the one published as COLD - had already been asked
    # and answered. A cold pass must answer only questions the engine has
    # never seen. sparse_multipass_driver.py already draws from a held-out
    # slice; this is the same fix.
    for q in test[timed_n:]:  # warmup, untimed, held out of the timed set
        b.search(q, K)
    lats, recalls = [], []
    t0 = time.perf_counter()
    for qi in range(timed_n):
        t1 = time.perf_counter()
        ids = b.search(test[qi], K)
        lats.append((time.perf_counter() - t1) * 1e3)
        recalls.append(len(set(ids[:K]) & set(gt[qi].tolist())) / K)
    span = time.perf_counter() - t0
    p = pct(lats)
    out.update({f"query_{k}_ms": round(v, 3) for k, v in p.items()})
    out["qps"] = round(timed_n / span, 1)
    out["n_queries_timed"] = timed_n
    out["warmup_held_out"] = WARM
    out["recall_at_10"] = round(statistics.mean(recalls), 4)
    # The second snapshot: #6858's trigger is evaluated when queries run, so a
    # rebuild it provoked exists only in the AFTER-SEARCH counters. Comparing
    # the two is what tells a reader whether the timings above include one.
    out["engine_stats_after_search"] = b.engine_stats()

    # TIME THE CLOSE, do not merely perform it (#155). A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. An unrecorded close is an unpriced one, and
    # the row cannot be told apart from a lane that never settles.
    # BENCH_SKIP_CLOSE=1 runs the cell WITHOUT closing the database.
    #
    # It existed for one question -- is the fp32 deep10m failure a BUILD cost or
    # a CLOSE cost -- and it ANSWERED it on 2026-08-20: a BUILD cost belonging to
    # a second build nobody asked for. Keeping the flag because the question
    # recurs, but the reasoning it was written with was wrong twice over and the
    # correction is the useful part:
    #
    # NOT #5747, and the OOM was NOT inside close(). #5747 was the LOADING path
    # ("a session that never searched pays a rebuild on close"), fixed by our own
    # PR #5787 and never what this tier hit. The real cause is #6489: a build
    # that leaves ANY node unreachable merges those orphans into the
    # pending-mutation list, so graphState is MUTABLE even though the build
    # succeeded, persisted, and has zero pending writes -- and flush() tests
    # graphState alone. The run that settled it (qI) had close SKIPPED and still
    # OOM'd, inside a SECOND full build.
    #
    # What the tier actually does on 26.8.1 at the standard 24g/36g envelope:
    # build #1 peaks 21,851/24,576 MB and COMPLETES, then a redundant build dies
    # at 24,554 MB. With #6490 applied: one build, peak 22,664 MB, close 0.158 s,
    # recall 0.9506, rc=0, same envelope. The tier never needed a bigger heap.
    #
    # The arm RECORDS that it skipped, because a cell that silently omits a phase
    # is not comparable with one that does not.
    if os.environ.get("BENCH_SKIP_CLOSE") == "1":
        out["close_s"] = None
        out["close_skipped"] = True
        out["close_skip_reason"] = ("diagnostic: isolating build cost from the "
                                    "#6489 redundant graph rebuild")
    else:
        _t = time.perf_counter()
        b.close()
        out["close_s"] = round(time.perf_counter() - _t, 3)
    # 0.0 MUST MEAN "nothing to release", NEVER "we did not ask". Without this
    # the dense table would read ArcadeDB 157.5 s against six flat zeros, four
    # of which were simply unmeasured.
    if getattr(b, "close_note", None):
        out["close_note"] = b.close_note

    # Stamp the conditions. runner.py wraps this script and adds cpuset, heap,
    # mem_cap and a manifest to runs.jsonl, so a full campaign row is already
    # provenanced -- but only when the runner is the caller. Run standalone
    # (which is how every targeted re-measure is done, because the runner
    # cannot select a single backend at a single envelope without also
    # rewriting its per-scale maps) the row carried nothing. Stamping here
    # means a standalone row is as auditable as a campaign row instead of
    # being a second class of artifact nobody thought to check.
    try:
        import bench_common
        # The adapter already recorded the version of the engine actually under
        # test (chromadb.__version__, duckdb.__version__, ...). run_conditions
        # stamps engine_version from the arcadedb wheel, which is the right
        # answer for the ArcadeDB rows and the WRONG one for every comparator:
        # inside a comparator container the wheel is not installed, the lookup
        # raises, and the adapter's correct version is overwritten with
        # "unknown (PackageNotFoundError)". That is what happened to all 20 rows
        # of the DEEP-10M envelope run. Keep the adapter's answer, and move the
        # wheel's to a key that says what it is.
        backend_version = out.get("engine_version")
        out.update(bench_common.run_conditions(lane="l3d", scale=args.scale,
                                               backend=args.backend))
        out["backend_version"] = backend_version
        # THE ADAPTER ALWAYS WINS, and the test is no longer the backend NAME.
        # It used to be `not backend.startswith("arcadedb")`, which is true for
        # arcadedb_dense_server -- an ArcadeDB arm that runs in dbbench:client,
        # where the wheel is not installed. So the one arm the special case was
        # meant to protect kept run_conditions' answer and published
        # engine_version="unknown (PackageNotFoundError)" while its adapter had
        # correctly read "server:26.8.1 (build ...)" from the server itself.
        # The adapter measured the engine under test; run_conditions read the
        # container. Keep both, and never let the second overwrite the first.
        out["harness_arcadedb_version"] = out.pop("engine_version", None)
        out["engine_version"] = backend_version
    except Exception as e:                     # never lose a measured result
        out["conditions_error"] = f"{e.__class__.__name__}: {e}"

    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT", json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
