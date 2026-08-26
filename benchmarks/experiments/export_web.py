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


_VERSION_TOKEN = re.compile(r"\bv?\d+(?:\.\d+)+\b|\b\d+-[a-z]+\b")


def _short_version(raw: str | None) -> str | None:
    """A version, not a sentence.

    This used to publish the pin's CODE COMMENT verbatim, capped at 60
    characters, which is how the page came to print "9.4.1, matches the 9.4.1
    client" as Elasticsearch's version and nothing at all for ArcadeDB, whose
    comment ran past the cap. The time-series lane had its own variant: QuestDB
    reports a build banner, so the page carried its JDK version and its git
    commit hash in a provenance line meant to say which release ran.

    The first version-shaped token is what a reader wants. The full string is
    still in the artifact, and the image digest below it is the real identity.
    """
    if not raw:
        return None
    # Only a version-shaped token counts. The adapters also stamp things like
    # "server:latest", "arcadedb-embedded" and "unknown (PackageNotFoundError)"
    # when they cannot determine a version, and printing those as if they were
    # releases is worse than printing nothing.
    m = _VERSION_TOKEN.search(raw)
    return m.group(0) if m else None


def _arcadedb_identity(rows) -> str | None:
    """The engine identity for the payload header, derived from the rows.

    A STABLE release tag identifies an engine on its own: 26.8.1 names exactly
    one build. A DEV version does not, because our build line prints
    26.9.1.dev0 for every commit we build, and that asymmetry is the whole
    basis of #42 (paper, releases) against #49 (page, commits). So a release
    needs no commit, and a dev version without one is not an identity at all.

    None when the rows disagree, rather than a guess: one string over two
    engines is precisely the claim #49 forbids. arcadedb_commits beside this
    lists what is actually in the payload, and each table carries its own pin
    under PAGE-SPEC rule 3.
    """
    vers = {str(r.get("engine_version")).strip() for r in rows
            if str(r.get("backend", "")).startswith("arcadedb") and r.get("engine_version")}
    shas = {str(r.get("engine_commit")).strip() for r in rows
            if str(r.get("backend", "")).startswith("arcadedb") and r.get("engine_commit")}
    if len(vers) != 1:
        return None
    ver = next(iter(vers))
    if len(shas) == 1:
        return _engine_identity(ver, next(iter(shas)))
    if not shas and not _IS_PRERELEASE(ver):
        return _engine_identity(ver, None)   # a release names itself
    return None


def _IS_PRERELEASE(ver: str) -> bool:
    v = (ver or "").lower()
    return "dev" in v or "snapshot" in v or "-rc" in v


def _engine_identity(raw: str | None, commit: str | None) -> str | None:
    """How an ArcadeDB cell says which engine produced it.

    DECISIONS #49 (2026-08-21): the page identifies ArcadeDB by upstream COMMIT
    SHA, not by a release number, because our build line prints the same version
    for every commit we build. That decision was recorded and then never reached
    this file: `arcadedb_version` was the literal "26.8.1" and every entry came
    out with engine_commit=None, so the page spent five days identifying the
    engine the one way #49 says cannot do the job.

    Both, per the user 2026-08-26, and in this order for a reason. The commit is
    the identifier; the version is context saying which release line to expect it
    in.

    THE DEV SUFFIX IS NORMALISED, and that is the user's correction on the same
    day: the `0` in `26.9.1.dev0` is a literal chosen when the wheel is built,
    not a build counter, so printing it implies a sequence that does not exist
    and invites a reader to think dev0 and dev1 are different engines. They are
    not distinguishable that way at all, which is the entire reason the commit is
    the identifier. `26.9.1.dev0` renders `26.9.1-dev`.

    Normalisation happens at RENDER time only. Callers compare raw version
    strings before getting here, so two genuinely different version strings are
    still caught as a disagreement rather than collapsed into one label.
    """
    ver = (raw or "").strip() or None
    sha = (commit or "").strip() or None
    if ver:
        # 26.9.1.dev0 / 26.8.1.dev25 / 26.9.1-SNAPSHOT -> 26.9.1-dev
        ver = re.sub(r"[.\-]?(dev\d*|SNAPSHOT)$", "-dev", ver, flags=re.I)
    if ver and sha:
        return f"arcadedb {ver} \u00b7 {sha}"
    return f"arcadedb {ver}" if ver else (f"arcadedb {sha}" if sha else None)


def _engine_version(label: str, raw: str | None,
                    image: str | None = None) -> str | None:
    """"<engine> <version>", from a row label and whatever the adapter stamped.

    The engine name comes from the IMAGE when there is one. A row label names
    the deployment a reader sees, which is not always the thing the version
    belongs to: the composed-stack row is labelled "Qdrant + Neo4j" and its
    pinned image is Neo4j's, so taking the name from the label produced
    "qdrant + neo4j 5-community" for a version only one of them has.
    """
    ver = _short_version(raw)
    if not ver:
        return None
    if image:
        repo = image.split("@")[0].split(":")[0]
        engine = repo.rsplit("/", 1)[-1].lower()
    else:
        engine = label.split(" (")[0].strip().lower()
    return f"{engine} {ver}"


def _image_version_names() -> dict[str, str]:
    src = (HERE / "runner.py").read_text(encoding="utf-8")
    out = {}
    for image, comment in _VERSION_COMMENT.findall(src):
        # Prefer the image's own tag: arcadedata/arcadedb:26.8.1@sha256:... is
        # the engine saying its version, where the comment is us saying it.
        tag = None
        if "@" in image and ":" in image.split("@")[0]:
            tag = image.split("@")[0].rsplit(":", 1)[1]
        name = tag or _short_version(comment)
        if name:
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
    # Name the quantization on BOTH sparse rows. Left as a bare
    # "ArcadeDB (embedded)" next to "ArcadeDB (embedded, fp32)", the
    # default row reads as the plain one and the ablation as a variant, when
    # they are two points on one axis. Spelling out int8 makes it a pair.
    "arcadedb_sparse_embedded": "ArcadeDB (embedded, int8)",
    # int8 like the embedded default, and for the same reason: the server's DDL
    # is CREATE INDEX ... LSM_SPARSE_VECTOR METADATA {"dimensions": N} with no
    # quantization key, so it takes the engine default. Labelled because a row
    # sitting between "embedded, int8" and "embedded, fp32"
    # with no precision of its own reads as a third, unstated option.
    "arcadedb_sparse_server": "ArcadeDB (server, int8)",
    "arcadedb_sparse_embedded_fp32": "ArcadeDB (embedded, fp32)",
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
    "postgres": "PostgreSQL", "postgres_tuned": "PostgreSQL (tuned)",
    "duckdb": "DuckDB", "questdb": "QuestDB",
    "arcadedb": "ArcadeDB",
    "sqlite": "SQLite", "chroma": "Chroma", "ladybug": "LadybugDB",
}


# What each dense engine actually STORES its vectors as, read from the adapter
# that configures it in l3d_dense.py. Not from the data.
#
# The rows carry a `quantization` field and it is USELESS for comparators: it
# echoes BENCH_DENSE_QUANT, an ArcadeDB-only knob, so it reports "fp32" for
# LanceDB, which builds IVF_HNSW_SQ and is int8. Publishing that field would
# have put a false label on a competitor's row.
#
# So this is read from the code that creates each index, the same way image
# version names are read from runner.py rather than guessed:
#
#   ArcadeDB     ARRAY_OF_FLOATS, LSM_VECTOR with the "quantization" key set
#                only when BENCH_DENSE_QUANT asks; fp32 when omitted
#   LanceDB      create_index(index_type="IVF_HNSW_SQ")  <- int8 scalar quant,
#                LanceDB's only HNSW offering, already noted in the adapter
#   Chroma       collection metadata sets hnsw:* only; stores float32
#   Qdrant       VectorParams(size, distance) with NO quantization_config
#   Milvus       DataType.FLOAT_VECTOR + HNSW
#   DuckDB VSS   vec::FLOAT[DIM] + HNSW
#   sqlite-vec   vec0(embedding float[DIM])
#
# WHY IT IS ON THE PAGE: ArcadeDB's two arms were labelled and nobody else was,
# so a reader saw quantization as an ArcadeDB peculiarity and read every
# unlabelled row as full precision. One of them is not. LanceDB's 0.93 recall
# and ArcadeDB-int8's 0.94 are then the same kind of number, where Chroma's
# 0.93 at fp32 is a different kind, and only the label makes that visible.
# Sparse weight precision, ArcadeDB only. LSM_SPARSE_VECTOR quantizes posting
# weights to int8 by default and the fp32 arm is our own ablation, so these
# three are read off the backend name the harness ran.
#
# The comparators are deliberately absent, which renders as a dash rather than
# a guess. Unlike the dense lane, where each engine's index type states what it
# stores, sparse weight encoding is internal to Qdrant, Milvus and
# Elasticsearch and we have not audited it. A dash is a true statement about
# what we know; "fp32" would not be.
# AUDITED 2026-08-14. Until then this held only our own three rows and every
# comparator printed a dash. The dash was honest ("we have not read their
# formats") but it left a reader to assume quantization is an ArcadeDB
# peculiarity, when two of the three comparators store weights at full
# precision and the third is lossier than our default.
#
# Read from each vendor's docs AND source at the version we run, never inferred
# from the recall we measured:
#
#   Qdrant v1.18.2   fp32. SparseIndexParams.datatype defaults to Float32
#                    (openapi.json at tag v1.18.2); source has
#                    `pub type DimWeight = f32`, and with on_disk=false the
#                    mutable RAM inverted index never consults datatype at all.
#                    Sparse quantization exists as that datatype field and is
#                    off by default. It is NOT quantization_config, which is
#                    dense-only; our call passes neither.
#   Milvus v2.6.13   fp32, from SOURCE, and the citation matters here. The
#                    often-quoted sentence "the value part can be a
#                    non-negative 32-bit floating-point number" is on the
#                    v2.4.x and v3.0.x doc pages but NOT on v2.6.x, which
#                    dropped that FAQ, so quoting it against the version we run
#                    would be citing a page that does not say it. A skeptic
#                    refuted exactly that and was right to.
#                    What holds at our version: the digest resolves to
#                    v2.6.13, which pins knowhere v2.6.10, whose
#                    include/knowhere/operands.h has
#                    `struct sparse_u32_f32 { using ValueType = float; }` and
#                    sparse_utils.h a `static_assert(is_same_v<T, fp32>,
#                    "SparseRow supports float only")`. sparse_index_node.cc
#                    instantiates InvertedIndex<float, float> for metric IP;
#                    the uint16-quantized variant of the same class is chosen
#                    only for BM25, which we do not use. The shipped
#                    libknowhere.so in that image carries the matching
#                    typeinfo symbols, so the binary agrees with the source.
#   Elasticsearch 9  ~9 significant bits, their own wording: "sparse_vector
#                    fields only preserve 9 significant bits for the precision,
#                    which translates to a relative error of about 0.4%."
#
# The trap both claims were checked against: Qdrant and Milvus document DENSE
# quantization far more loudly than sparse storage, so a citation that is
# really about dense vectors is the likeliest way to put a wrong label on a
# competitor's row. Both were confirmed against version-pinned source.
SPARSE_PRECISION = {
    "arcadedb_sparse_embedded": "int8",
    "arcadedb_sparse_embedded_fp32": "fp32",
    "arcadedb_sparse_server": "int8",
    "qdrant_sparse": "fp32",
    "milvus_sparse": "fp32",
    "elasticsearch_sparse": "~9-bit",
}

DENSE_PRECISION = {
    "arcadedb_dense_embedded": "fp32",
    "arcadedb_dense_server": "fp32",
    "chroma_dense": "fp32",
    "qdrant_dense": "fp32",
    "milvus_dense": "fp32",
    "duckdb_vss_dense": "fp32",
    "sqlite_vec_dense": "fp32",
    "lancedb_dense": "int8",
}


# The Scale column showed the harness's own tier names: "tiny", "small",
# "medium", "deep10m", "tpch1". Those mean something to us and nothing to a
# reader, and worse, they mean different things in different lanes -- "small"
# is a million sparse vectors in one table and a million dense ones in another,
# while "medium" is 8.84 million in the sparse table and 20 million rows in the
# tabular one. A reader comparing tables across the page would be comparing
# labels that look identical and are not.
#
# So the page prints the size. The raw tier name stays on the entry as `scale`
# because it is the grouping key and page_check pins cells by it; this is the
# rendered string only.
SCALE_LABELS = {
    ("l3s", "tiny"): "100k",
    ("l3s", "small"): "1M",
    ("l3s", "medium"): "8.84M",
    ("l3d", "small"): "1M",
    ("l3d", "deep10m"): "9.99M",
    # LDBC publishes its tiers as scale factors, so SF1/SF10 are the corpus's
    # own vocabulary rather than ours; the person count says how big that is.
    ("l2", "sf1"): "SF1 (11k people)",
    ("l2", "sf10"): "SF10 (73k people)",
    ("l1", "medium"): "20M rows",
    ("l1tpc", "tpch1"): "SF1",
    ("e2", "e2"): "50k products",
}


def scale_label(lane: str, scale: str) -> str:
    """Reader-facing size for a lane's tier name.

    Raises rather than falling back to the raw name: a new tier that reaches
    the page under its harness label is exactly the defect this map exists to
    prevent, and a silent fallback would let it through looking deliberate.
    """
    try:
        return SCALE_LABELS[(lane, scale)]
    except KeyError:
        raise SystemExit(
            f"no SCALE_LABELS entry for lane {lane!r} scale {scale!r}.\n"
            "  Add one: the page prints corpus sizes, not harness tier names.")


# The Mode column said "embedded" for Qdrant, Milvus, Elasticsearch, Neo4j and
# PostgreSQL, every one of which runs as a server container that the benchmark
# talks to over the wire. The rule was `"server" if "server" in backend`, which
# reads a DEPLOYMENT off a NAME: it happens to be right for ours, because our
# server arms are called *_server, and wrong for every comparator, because
# theirs are called qdrant_sparse and neo4j_graph.
#
# That is not a cosmetic mislabel. The page's deployment story is that ArcadeDB
# can run in-process where the specialists cannot, and the Mode column was
# quietly awarding the comparators the same property. It also inverted the E4
# section's point one table earlier: the client/server split costs something,
# and the table said nobody was paying it.
#
# runner.py's topology is the fact of the matter, since it is what decides
# whether a cell gets a server container at all.
def deployment_of(backend: str) -> str:
    try:
        topo = BACKENDS[backend]["topology"]
    except KeyError:
        raise SystemExit(
            f"backend {backend!r} is not in runner.BACKENDS, so its deployment "
            "cannot be read from its topology.\n  Do not guess from the name: "
            "that is the bug this function replaced.")
    return "server" if topo == "client_server" else "embedded"


def display_name(backend: str) -> str:
    if backend in DISPLAY_NAMES:
        return DISPLAY_NAMES[backend]
    if backend.startswith("arcadedb"):
        return "ArcadeDB"
    return backend.replace("_", " ")


REPO = "https://github.com/humemai/arcadedb-embedded-python/blob/main"

# Where each table's numbers physically come from. Published per table so a
# reader can open the rows rather than take the page's word for them, which is
# the whole point of generating these from data in the first place.
SOURCES = {
    "l3s": "benchmarks/experiments/results/runs_paper.csv",
    # Two tiers, two artifacts: small comes from the campaign's frozen rows,
    # DEEP-10M from the matched multipass overlay. Both are published.
    "l3d": ["benchmarks/experiments/results/runs_paper.csv",
            "benchmarks/experiments/results/dense_mp5_2681"],
    "l2": "benchmarks/experiments/results/runs_paper.csv",
    "l1": "benchmarks/experiments/results/runs_paper.csv",
    "l1tpc": "benchmarks/experiments/results/runs_paper.csv",
    "e2": "benchmarks/experiments/results/runs_paper.csv",
    "l4": "benchmarks/experiments/results/l4_tsbs.jsonl",
    "e4": "benchmarks/experiments/results/e4decomp_2681",
    "pycost": "benchmarks/python-bindings/jpype_overhead/results/mini_results.csv",
    "pyb_tabular": "benchmarks/python-bindings/results/runs_paper.csv",
    "pyb_graph": "benchmarks/python-bindings/results/runs_paper.csv",
    "pyb_vector": "benchmarks/python-bindings/results/runs_paper.csv",
}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# overlay arm -> (label the page prints, is it ours)
# (overlay filename arm, runner backend key, display label, is ours)
# The backend key is here so Mode can be read off runner.py's topology instead
# of guessed from a name -- see deployment_of().
DENSE_10M_ARMS = [
    ("fp32", "arcadedb_dense_embedded", "ArcadeDB (embedded, fp32)", True),
    ("int8", "arcadedb_dense_embedded", "ArcadeDB (embedded, int8)", True),
    # the server overlay stamps quantization='fp32'
    ("arcsrv", "arcadedb_dense_server", "ArcadeDB (server, fp32)", True),
    ("qdrant", "qdrant_dense", "Qdrant (fp32)", False),
    ("chroma", "chroma_dense", "Chroma (fp32)", False),
    ("duckvss", "duckdb_vss_dense", "DuckDB VSS (fp32)", False),
    # IVF_HNSW_SQ: the only quantized comparator, and it was unlabelled while
    # ArcadeDB's two arms were, which made quantization read as our quirk.
    ("lancedb", "lancedb_dense", "LanceDB (int8)", False),
    ("milvus", "milvus_dense", "Milvus (fp32)", False),
    ("sqlitevec", "sqlite_vec_dense", "sqlite-vec (fp32)", False),
]


def _dense_10m_entries():
    """The DEEP-10M tier, every engine, both passes.

    THIS TIER WAS WITHHELD AND SHOULD NOT HAVE BEEN. The withheld note said
    ArcadeDB's 10M rows "were measured on a pre-release build, which this
    project does not publish", and that was true when it was written and false
    by the time anyone read it: dense_mp5_2681 stamps engine_version 26.8.1 on
    every ArcadeDB arm, a release. So the page hid the tier for a reason that
    had expired, while f4 plotted that same tier immediately above the table,
    and the figure's caption discussed six numbers a reader could not find
    anywhere on the page.

    The rows live here rather than in runs_paper.csv because the whole tier was
    re-measured by dense_multipass_driver.py, which gives every engine the same
    build-then-five-passes protocol. The withholding logic keys on ArcadeDB
    having a canonical row at a scale, and ours are in the overlay, so it
    dropped the tier without anyone deciding to.

    Cold is pass 0, warm pools passes 1-4 over all five builds. Reported
    together because separating them is the point: only ArcadeDB moves.
    """
    root = HERE / "results" / "dense_mp5_2681"
    if not root.is_dir():
        return []
    out = []
    for arm, backend_key, label, ours in DENSE_10M_ARMS:
        hits = sorted(root.glob(f"mp_{arm}_b*.json"))
        if not hits:
            continue
        cold, warm, recall, build, ver = [], [], [], [], set()
        for h in hits:
            passes = json.loads(h.read_text(encoding="utf-8"))
            if not passes:
                continue
            ver.add(passes[0].get("engine_version"))
            build.append({"build_s": passes[0].get("build_s")})
            cold.append({"p50": passes[0].get("p50")})
            for p in passes[1:]:
                warm.append({"p50": p.get("p50")})
                recall.append({"r": p.get("recall_at_10")})
        metrics = {}
        for label_, rows_, field in (("cold p50 ms", cold, "p50"),
                                     ("warm p50 ms", warm, "p50"),
                                     ("recall@10", recall, "r"),
                                     ("build s", build, "build_s")):
            got = _agg(rows_, field)
            if got is not None:
                metrics[label_] = got
        if not metrics:
            continue
        # Only OUR arms carry a version string; the comparator containers do
        # not expose one to this driver and record "unknown (...)". Reporting
        # that as a build would be worse than reporting nothing.
        v = next((x for x in ver if x and not str(x).startswith("unknown")), None)
        out.append({
            "backend": label,
            "is_arcadedb": ours,
            "precision": "int8" if arm == "int8" else "fp32",
            "scale": "deep10m",
            "scale_label": scale_label("l3d", "deep10m"),
            "workload": "search",
            "n_docs": "9,990,000",
            "deployment": deployment_of(backend_key),
            "image": None,
            "version_name": _engine_version(label, v),
            "host": "mini",
            "metrics": metrics,
        })
    return out


# Fields whose stored unit is not the unit the column claims. The artifact
# records memory in MiB because that is what cgroup reports; the paper and the
# page both talk in GiB, and a column headed "GiB" printing 8256 would be a
# defect the reader has to catch. Divide here, once, rather than in each table
# spec where the next lane to add memory would forget it.
_UNIT_DIVISOR = {"peak_anon_mib_sum": 1024.0, "end_anon_mib_sum": 1024.0}


def _agg(rows, field):
    """Median across repetitions, with the spread, matching the paper."""
    vals = [v for v in (_num(r.get(field)) for r in rows) if v is not None]
    if not vals:
        return None
    div = _UNIT_DIVISOR.get(field)
    if div:
        vals = [v / div for v in vals]
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
                    ("build_s", "build s"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        "conditions": [
            "Recall is reported beside every latency: ArcadeDB quantizes posting weights to int8 by default, so a latency number without its recall is not comparable.",
            "Elasticsearch runs with index-time token pruning disabled. Its 9.x default prunes on thresholds tuned for a different model's vectors and costs recall on this corpus, which would have printed a quality gap belonging to that default rather than to the engine, and printed it in our favour.",
            "Every number here is the first timed pass after the index is built. Running the same engines again over an index they have already read shows almost nothing: the largest gain any of the six makes is 1.18x at a million and 1.13x at 8.84 million, and the order of the table is identical either way. That is worth stating because the dense table below is NOT like this, where ArcadeDB alone gains about 9x on a second pass and the order depends on which pass you time.",
            "ArcadeDB's server takes roughly twice as long to build as its embedded deployment, and that gap is loading the data, not building the index. Both run the same index code. The embedded one is handed the numbers directly, because the database is running inside the same program. The server has to be sent them, and the only way in is a written-out INSERT statement: a document here has about 127 non-zero weights, so each one arrives as roughly 254 numbers spelled out as text, which the server then has to read back into numbers.",
        ],
    },
    "l3d": {
        "title": "Dense vector search",
        "dataset": "DEEP-10M (deep-image-96-angular) and SIFT-scale tiers",
        # "cold" rather than a bare "p50" because the two passes are different
        # quantities and the page now says so. Both lanes measure the cold
        # column identically: l3d_dense runs 20 untimed warmups then ONE timed
        # pass, and dense_multipass_driver runs those same 20 warmups before
        # each of its five, so overlay pass 0 IS the campaign protocol. The
        # small tier has no second pass, so it shows a dash there rather than a
        # number borrowed from a different measurement.
        "metrics": [("query_p50_ms", "cold p50 ms"),
                    ("recall_at_10", "recall@10"),
                    ("build_s", "build s"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        "conditions": [
            "ArcadeDB's maxConnections is a Vamana per-layer degree, not hnswlib's M. Matching the parameter names would compare a half-degree graph against a full-degree one, so the graphs are matched by effect instead.",
            "Cold is the first timed pass after the index is built; warm is a repeat of the same query set. Only ArcadeDB moves between them, because it pages its index off disk while the others are resident from build. Every comparator here is within 3% of itself.",
        ],
    },
    "l2": {
        "title": "Graph traversal",
        "dataset": "LDBC-SNB Interactive (SF1, SF10)",
        # Peak anon last, and present at all because the page had no memory
        # column anywhere while every lane has measured it since the #52 fix.
        # It is also the column that shows our largest loss on this lane:
        # LadybugDB runs the same SF10 workload in a twenty-second of the
        # memory. A page that omits the resource axis reads as if latency
        # were the only axis anyone deploys on.
        "metrics": [("point_p50_ms", "point p50 ms"), ("hop1_p50_ms", "1-hop p50 ms"),
                    ("hop2_p50_ms", "2-hop p50 ms"), ("write_p50_ms", "write p50 ms"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        # OLTP only. The OLAP rows live in the l2olap table below, which is
        # also where the GAV ablation belongs: at SF10 the OLAP cell splits
        # into view-on and view-off, and this table does not group on gav, so
        # both land here as two rows identical in every printed field.
        #
        # That stayed invisible while every metric here was an OLTP one and
        # the OLAP rows came out empty. Adding peak memory, which every row
        # has, made the pair appear. A metric that is present for ALL rows
        # exposes any grouping key the table is missing, which is worth
        # remembering the next time a column is added anywhere.
        "only_workload": "oltp",
        # Two conditions came off this list on 2026-08-14 for being written to a
        # reviewer and read by everyone else. One explained that bidirectional
        # edges are a pointer-storage choice rather than a semantic one, which
        # answers a fairness objection nobody browsing the page has raised; the
        # other explained 2-hop dispersion in terms of seed degree, which needs
        # the seed-sampling method in hand to parse. Both remain in the papers,
        # where the reader has that context. The page states what was run.
        "conditions": [
            "Every engine traverses the same persons-and-KNOWS projection, with edges stored in both directions.",
        ],
    },
    # A second view of the graph lane: the same corpus and the same engines,
    # but the analytical queries rather than the transactional ones. It is a
    # separate table because it is a separate question, and because it carries
    # a row no other table has: the same engine with its Graph Analytical View
    # turned off. The paper reports all six numbers.
    #
    # SF10 only, and that is a real limit rather than a presentation choice.
    # The ablation was run at SF10, so SF1 has no view-off arm, and a table
    # with an ablation row that is dashed at one scale invites the reader to
    # read the dash as a failure.
    "l2olap": {
        "title": "Graph analytics, with and without the Graph Analytical View",
        "dataset": "LDBC-SNB, SF10",
        "lane_source": "l2",
        "only_scales": {"sf10"},
        "only_workload": "olap",
        "metrics": [("friend_age_by_city_mean_ms", "average friend age ms"),
                    ("same_city_edges_mean_ms", "friends in same city ms"),
                    ("top_degree_mean_ms", "most friends ms"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        "conditions": [
            "Three questions, each asked of the whole graph. Average friend age: for every city, the average age of the friends of the people who live there. Friends in same city: how many friendships connect two people in the same city. Most friends: which people have the highest number of friends. All three times are milliseconds.",
            "The Graph Analytical View is a copy of the graph that ArcadeDB builds in memory, laid out for questions that sweep the whole graph rather than follow a few links. Building it took 2.0 seconds here, once, before any query was timed.",
            "The two rows labelled ArcadeDB (embedded) are the same engine on the same data, differing only in whether that view is built. Both return identical answers.",
            "The benefit is uneven, and the three queries show why. Top degree gains most because it only walks adjacency. The other two read a property from the far end of every edge traversed, and that lookup costs the same either way, so it comes to dominate once the traversal itself is cheap.",
        ],
    },
    "l1": {
        "title": "Tabular OLTP and OLAP",
        "dataset": "Synthetic orders workload",
        "metrics": [("read_p50_ms", "read p50 ms"), ("insert_p50_ms", "insert p50 ms"),
                    ("oltp_ops_per_s", "OLTP ops/s"), ("olap_total_ms", "OLAP total ms"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        # The memory column is the one cell on this page a reader can most
        # easily misread, because the gap looks like two orders of magnitude
        # and is mostly an accounting boundary. Stated here rather than left
        # for the reader to work out.
        "conditions": [
            "PostgreSQL's memory cell is not comparable to the other two. It keeps its data in shared memory and in the file cache the kernel holds for it, and this column counts neither, so it reads 0.12 GiB where the run's actual peak was 3.85. Most of even that 0.12 is our own benchmark client rather than the database: 0.105 of it. We checked that this is the measure and not the setting, by giving a PostgreSQL container a 2 GB buffer pool and watching this column stay at 5 MiB.",
        ],
    },
    "l1tpc": {
        "title": "Tabular (TPC-H and TPC-C shapes)",
        "dataset": "TPC-H queries, TPC-C new-order",
        "metrics": [("q1_ms", "Q1 ms"), ("q6_ms", "Q6 ms"),
                    ("neworder_p50_ms", "new-order p50 ms"), ("oltp_ops_per_s", "OLTP ops/s"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        "conditions": [
            "Q1 and Q6 are TPC-H's own query numbers. Q1 groups and aggregates the whole line-item table, so it measures a full scan; Q6 sums one column under a narrow filter, so it measures how well an engine skips what it does not need.",
            "New-order is TPC-C's checkout transaction: it reads a customer and a warehouse, inserts an order with its line items, and updates stock, all in one transaction.",
            "PostgreSQL's memory cell is not comparable to the other two, for the reason given under the table above: this column counts memory an engine holds in its own address space, and PostgreSQL holds its data in shared memory and the kernel's file cache instead. On this workload the effect is at its most extreme, because the 1.58 GiB shown is 1.578 of Python client and 0.006 of database.",
        ],
    },
    "e2": {
        "title": "Cross-model transaction",
        "dataset": "Vector hit to graph traversal to document update, in one transaction",
        "metrics": [("hybrid_p50_ms", "p50 ms"), ("hybrid_p99_ms", "p99 ms"),
                    ("peak_anon_mib_sum", "peak memory GiB")],
        # HYBRID ONLY. The atomicity workload has no latency to print, so
        # while every metric here was a latency its rows came out empty and
        # collapsed invisibly onto the hybrid ones. Adding peak memory, which
        # every row has, made them appear as duplicates a reader cannot tell
        # apart. Same defect the graph table had, same cause: a metric present
        # for ALL rows exposes any grouping the table does not do.
        #
        # The atomicity RESULT is not lost, it is prose on the page: 200
        # injections per system, composed half-updated in all 200, both single
        # engines in none.
        "only_workload": "hybrid",
        "conditions": [
            "Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.",
            "So the interesting result here is not the speed. It is what a crash halfway through leaves behind. The raw data records, for each run, whether an interrupted write left the two stores disagreeing, and whether they still disagreed after restarting. That is what this comparison exists to show.",
            "Read the times with one caveat, which cuts against ArcadeDB. ArcadeDB here writes to disk, while SurrealDB runs entirely in memory and the composed stack's vector half does too. Part of why they answer faster is that they never touch a disk. The all-or-nothing result above does not depend on this, since a half-finished update is visible in memory just as it is on disk, but the millisecond columns do.",
        ],
    },
}

GLOBAL_CONDITIONS = [
    "Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.",
    "Peak memory is the largest amount an engine held in its own address space, added over every container a run used, and it deliberately leaves out the file cache the kernel keeps on the engine's behalf. That makes it the honest number for engines that manage their own memory, and an undercount for engines that lean on the kernel instead, so compare it down one engine's rows rather than across engines that work differently.",
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
    ("embedded", "in-process ms"),
    ("inproc_http", "in-process server, HTTP ms"),
    ("docker_http", "separate container, HTTP ms"),
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
        for label, value in (("packing cost ms", protocol),
                             ("separate process ms", boundary)):
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
            f"Every number is milliseconds. One released engine "
            f"({meta.get('engine_version')}) in all three setups, "
            f"{meta.get('reps')} repetitions after {meta.get('warmup')} warmup, "
            f"identical cpuset {meta.get('cpuset')}, memory cap {meta.get('mem_cap')} "
            f"and heap {meta.get('heap')}.",
            "All three setups turn the answer into Python objects the same "
            "way, so the difference is how the database was deployed and not "
            "how we read the result.",
            "The separate container runs on the same machine, talking over the "
            "local network interface. It says what running the database beside "
            "your program costs, and says nothing about a database on another "
            "machine across a real network.",
            "The separate-process column goes slightly negative at the smaller "
            "result sizes. That is not a container being faster than an "
            "in-process server; it is the boundary term sitting below what this "
            "design can resolve, so run-to-run noise swamps it and the sign "
            "flips. Reported rather than clamped to zero, because the negative "
            "values are the evidence for the claim: at these sizes co-locating "
            "costs nothing measurable. The packing cost, in the column beside "
            "it, stays firmly positive at every size.",
        ],
        "columns": [label for _, label in E4_ARMS] + ["packing cost ms",
                                                       "separate process ms"],
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
    # "last-point" is TSBS's own name for this query and it reads as "the
    # final point" rather than "the newest one", which is what it means.
    # The page says what the query does; the papers keep the TSBS term.
    (("q_last_unbounded_ms", "q_last_ms"), "newest reading ms"),
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


# (overlay filename arm, runner backend key, display label)
SPARSE_MP_ARMS = [
    ("arc_int8", "arcadedb_sparse_embedded", "ArcadeDB (embedded, int8)"),
    ("arc_fp32", "arcadedb_sparse_embedded_fp32", "ArcadeDB (embedded, fp32)"),
    ("arc_srv", "arcadedb_sparse_server", "ArcadeDB (server, int8)"),
    ("elastic", "elasticsearch_sparse", "Elasticsearch"),
    ("milvus", "milvus_sparse", "Milvus"),
    ("qdrant", "qdrant_sparse", "Qdrant"),
]


def _sparse_multipass_table():
    """What a second pass buys each engine on the sparse lane.

    A SEPARATE table rather than two more columns on the sparse one, and the
    reason is the defect this whole exercise started from. The sparse table's
    p50 comes from the lane at N=5; these numbers come from one build of a
    different driver. Putting them side by side in one row would be a warm
    number from one protocol next to a cold number from another, which is
    exactly what f4 did before it was fixed.

    The dense table CAN carry both columns because both of its passes come out
    of the same overlay. This one cannot, so it says so instead.
    """
    root = HERE / "results" / "sparse_mp"
    if not root.is_dir():
        return None
    entries = []
    for tier in ("medium", "small"):
        for arm, backend, label in SPARSE_MP_ARMS:
            fp = root / f"sp_{arm}_{tier}.json"
            if not fp.is_file():
                continue
            passes = json.loads(fp.read_text(encoding="utf-8"))
            cold = [r for r in passes if r.get("rep") == 0]
            warm = [r for r in passes if r.get("rep", 0) >= 1]
            if not cold or not warm:
                continue
            c = cold[0]["query_p50_ms"]
            w = statistics.median(r["query_p50_ms"] for r in warm)
            entries.append({
                "backend": label,
                "is_arcadedb": "arcade" in backend,
                "precision": SPARSE_PRECISION.get(backend),
                "scale": tier,
                "scale_label": scale_label("l3s", tier),
                "workload": "search",
                "n_docs": str(cold[0].get("n_docs") or ""),
                "deployment": deployment_of(backend),
                "image": None,
                "version_name": _engine_version(label, cold[0].get("engine_version")),
                "host": "mini",
                "metrics": {
                    "cold p50 ms": {"median": round(c, 3), "min": round(c, 3),
                                    "max": round(c, 3), "n": 1},
                    "warm p50 ms": {"median": round(w, 3), "min": round(w, 3),
                                    "max": round(w, 3), "n": len(warm)},
                    "gain": {"median": round(c / w, 2), "min": round(c / w, 2),
                             "max": round(c / w, 2), "n": 1},
                },
            })
    if not entries:
        return None
    return {
        "id": "l3smp",
        "title": "Sparse search: what a second pass buys",
        "dataset": "Big-ANN'23 Sparse, one build per engine, cold then warm",
        "conditions": [
            "Cold is the first timed pass after the index is built. Warm is the "
            "median of five more passes over a DIFFERENT half of the query set, "
            "so a warm number cannot be explained by the engine having already "
            "answered that exact query. Both halves are drawn from the same "
            "1,000 dev queries in the same order.",
            "One build per engine here, against five in the table above, which "
            "is why these are a separate table rather than two more columns on "
            "it. Reading a warm number from this protocol beside a cold number "
            "from that one is the mistake this table exists to avoid.",
            "The order is the same cold and warm at both sizes. The dense table "
            "further down is not like this: there ArcadeDB alone gains about "
            "nine times on a second pass, so which pass you time decides the "
            "ranking, and it has to say which.",
        ],
        "columns": ["cold p50 ms", "warm p50 ms", "gain"],
        "withheld_scales": [],
        "withheld_reason": None,
        "source_paths": ["benchmarks/experiments/results/sparse_mp"],
        "source_urls": [f"{REPO}/benchmarks/experiments/results/sparse_mp"],
        "entries": entries,
    }


def _l4_table():
    grouped = _l4_rows()
    if not grouped:
        return None

    order = ["arcadedb (native TIMESERIES)", "arcadedb (document path)",
             "questdb", "duckdb"]
    # This lane predates runner.BACKENDS and keeps its own adapters, so the
    # topology lookup does not reach it. QuestDB is a server (ILP ingest on
    # 9009, SQL over pg-wire, see l4_tsbs.py); the other two run in-process.
    L4_DEPLOYMENT = {"arcadedb (native TIMESERIES)": "embedded",
                     "arcadedb (document path)": "embedded",
                     "questdb": "server", "duckdb": "embedded"}
    entries = []
    for label in sorted(grouped, key=lambda k: (order.index(k) if k in order else 99, k)):
        rs = grouped[label]
        entry = {
            "backend": display_name(label) if label in DISPLAY_NAMES else label,
            "is_arcadedb": "arcadedb" in label,
            "scale": L4_SHAPE["scale"],
            "workload": L4_SHAPE["workload"],
            "n_docs": str(rs[0].get("n_points")),
            "deployment": L4_DEPLOYMENT[label],
            "image": None,
            # One engine name plus one version. The two ArcadeDB arms recorded
            # this differently ("26.8.1" from one adapter, "arcadedb 26.8.1"
            # from the other), so the provenance block listed the same build
            # twice under two spellings and looked like two builds.
            "version_name": _engine_version(
                label, rs[0].get("backend_version") or rs[0].get("engine_version")),
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
            # The two-arm explanation moved into the page caption, where a
            # reader meets the rows; saying it in both places said it twice.
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
            "Newest reading means the most recent value each sensor has "
            "reported, which is what a monitoring dashboard asks for when it "
            "shows the current state of a fleet. TSBS calls this query "
            "last-point. It is run without a time bound: telling the engine to "
            "look only at the past hour made it slower, 0.860 ms against "
            "0.720, because evaluating the time filter costs more than the "
            "scan it saves.",
        ],
        "columns": [lab for _, lab in L4_METRICS],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# The Python-binding suite. A DIFFERENT experiment from the lanes above:
# different corpora (Stack Exchange), different comparators (SQLite, DuckDB,
# Chroma, LadybugDB) and a different cpuset (0-7, not 0-11). It answers the
# question a reader of the embedded distribution actually has, which is what
# using this from Python costs, so it belongs on the page. It must NOT be read
# as continuous with the engine lanes, which is why both tables carry their own
# conditions saying so.
PYB = HERE.parent / "python-bindings"
OVERHEAD = PYB / "jpype_overhead" / "results" / "mini_results.csv"
PYB_FROZEN = PYB / "results" / "runs_paper.csv"


def _overhead_medians():
    """(workload, arm) -> median microseconds, from the mini re-measure."""
    if not OVERHEAD.exists():
        return {}
    out = defaultdict(list)
    with OVERHEAD.open() as fh:
        for row in csv.reader(fh):
            if len(row) < 8:
                continue
            try:
                out[(row[3], row[4])].append(float(row[6]))
            except ValueError:
                continue
    return {k: statistics.median(v) for k, v in out.items()}


def _python_cost_table():
    """What using the engine from Python costs, and where that cost lives.

    Two facts, in one table. Against an in-process Java baseline doing the
    same work, Python costs 1.28x on vector search and 1.63x on a 100k-row
    scan: the engine runs at engine speed and only handing results across the
    boundary is charged for. But WITHIN Python the choice of materialization
    path is worth far more than the language boundary is, which is the part a
    reader can act on.

    Arm pairing matters and is easy to get wrong: the vector ratio is
    P-raw-call against J-direct, and the scan ratio is P-columns against
    J-allcols, both sides reading the same columns. Pairing P-SQL with J-SQL
    instead gives 1.12x, a real number answering a different question.
    """
    m = _overhead_medians()
    if not m:
        return None

    def us(w, a):
        return m.get((w, a))

    rows_out = []

    def add(label, workload, value_us, baseline_us, note):
        if value_us is None or baseline_us is None:
            return
        rows_out.append({
            "backend": label,
            "is_arcadedb": True,
            "scale": workload,
            "workload": note,
            "n_docs": None,
            "deployment": "embedded",
            "image": None,
            "version_name": None,
            "host": None,
            "metrics": {
                "time ms": {"median": round(value_us / 1000, 3), "min": round(value_us / 1000, 3),
                            "max": round(value_us / 1000, 3), "n": 1},
                "vs Java": {"median": round(value_us / baseline_us, 2),
                            "min": round(value_us / baseline_us, 2),
                            "max": round(value_us / baseline_us, 2), "n": 1},
            },
        })

    jv, jq = us("vector", "J-direct"), us("query", "J-allcols-100000")
    add("Java, in process", "vector search", jv, jv, "baseline")
    add("Python", "vector search", us("vector", "P-raw-call"), jv, "same call")
    add("Java, in process", "100k-row scan", jq, jq, "baseline")
    add("Python, to_columns", "100k-row scan", us("query", "P-columns-100000"), jq, "columnar")
    add("Python, to_json_list", "100k-row scan", us("query", "P-jsonbatch-100000"), jq, "batched JSON")
    add("Python, to_list", "100k-row scan", us("query", "P-tolist-100000"), jq, "row objects")

    if not rows_out:
        return None
    return {
        "id": "pycost",
        "title": "What Python costs",
        "dataset": "Same engine, same query, called from Java and from Python",
        "conditions": [
            "The engine itself runs at the same speed either way. What Python "
            "is charged for is moving results across the boundary, which is why "
            "the vector search costs 1.28x and the scan 1.63x rather than "
            "anything scaling with the work the engine did.",
            "The path you choose inside Python matters far more than the "
            "language boundary does. Asking for row objects is 13.8x slower "
            "than asking for columns over the same query, so the practical "
            "advice is to use the columnar or batched call for anything large.",
        ],
        "columns": ["time ms", "vs Java"],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": rows_out,
    }


PYB_LANES = {
    "tabular": ("Tabular, embedded", [("oltp_ops_per_s", "OLTP ops/s"),
                                      ("olap_total_ms", "OLAP ms")]),
    "graph": ("Graph, embedded", [("oltp_ops_per_s", "OLTP ops/s"),
                                  ("olap_total_ms", "OLAP ms")]),
    "vector": ("Vector, embedded", [("q_mean_ms", "query ms"),
                                    ("recall@10", "recall@10"),
                                    ("build_s", "build s")]),
}


def _embedded_vs_tables():
    """ArcadeDB embedded against the embeddable engines people reach for."""
    if not PYB_FROZEN.exists():
        return []
    rows = list(csv.DictReader(PYB_FROZEN.open()))
    tables = []
    for lane, (title, metrics) in PYB_LANES.items():
        grouped = defaultdict(list)
        for r in rows:
            if r.get("lane") == lane and r.get("dataset") == "medium":
                grouped[r.get("backend")].append(r)
        entries = []
        for backend, rs in sorted(grouped.items()):
            entry = {
                "backend": display_name(backend),
                "is_arcadedb": "arcade" in str(backend),
                "scale": "medium",
                "workload": lane,
                "n_docs": None,
                "deployment": "embedded",
                "image": None,
                "version_name": rs[0].get("lib_version"),
                "host": None,
                "metrics": {},
            }
            for field, label in metrics:
                got = _agg(rs, field)
                if got is not None:
                    entry["metrics"][label] = got
            if entry["metrics"]:
                entries.append(entry)
        if entries:
            tables.append({
                "id": f"pyb_{lane}",
                "title": title,
                "dataset": "Stack Exchange (Cross Validated), all engines in one Python process",
                # NO conditions on these three. What used to be here is now
                # said once each, in the right place: the shared protocol in
                # the page's Reproducing section, and the cross-set caveat in
                # the paragraph that CLOSES these tables. Rendered per table it
                # was three tables times three paragraphs, and the protocol
                # sentence alone appeared eight times down the page.
                # The caveat sits after rather than before them on purpose: it
                # only means anything once the reader has the rows in hand, and
                # in front it read as an apology for numbers not yet seen.
                "conditions": [],
                "columns": [label for _, label in metrics],
                "withheld_scales": [],
                "withheld_reason": None,
                "entries": entries,
            })
    return tables


def main() -> int:
    if not FROZEN.exists():
        print(f"missing {FROZEN}; run make_paper_tables.py first", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(FROZEN.open()))
    names = _image_version_names()

    # The tabular lanes run OLTP and OLAP as separate workloads over ONE corpus
    # and one engine, and grouping by workload gave each engine two rows whose
    # columns were disjoint: an OLAP row with three dashes and an OLTP row with
    # one. Eight rows to carry four engines' worth of numbers, every cell that
    # was not dashed sitting in a different row from its neighbour.
    #
    # They merge because the split is an artefact of how the harness schedules
    # work, not of what was measured. A metric only ever appears in the rows of
    # the workload that produced it, so aggregating over the union puts each
    # number in exactly the cell it belongs to. The vector and graph lanes are
    # unaffected: they run a single workload each.
    MERGED_WORKLOAD_LANES = {"l1", "l1tpc"}
    # ... with one exception, added when memory arrived. The merge is sound for
    # a metric that appears in only ONE workload's rows: aggregating over the
    # union puts each number in the cell it belongs to. Memory is not like
    # that. peak_anon_mib_sum is recorded for every row of every workload, so
    # merging pools two different runs into one median: PostgreSQL's l1 cell
    # read 0.135 GiB, the midpoint of 0.119 (OLTP) and 0.152 (OLAP), a figure
    # describing neither. Keep only the transactional rows of a merged lane
    # when aggregating a metric that spans workloads.
    MEM_FIELDS = {"peak_anon_mib_sum", "end_anon_mib_sum"}
    grouped = defaultdict(list)
    for r in rows:
        wl = ("" if r["lane"] in MERGED_WORKLOAD_LANES
              else r.get("workload", ""))
        # gav belongs in the key. It is the Graph Analytical View ablation, run
        # as extra rows under the SAME backend name, so without it the five
        # ablation rows pooled with the five default rows and every graph OLAP
        # median would have been taken over a mixture of view-on and view-off.
        # Nothing published today reads those fields, so this fixes a trap
        # rather than a wrong number, and the l2olap table below is what would
        # have sprung it.
        grouped[(r["lane"], r["scale"], r["backend"], wl,
                 r.get("gav") or "")].append(r)

    tables = []
    for lane, spec in LANES.items():
        entries = []
        # A page table usually IS a lane, but l2olap is a second view of the
        # graph lane's rows, so the spec may name the lane it reads.
        src_lane = spec.get("lane_source", lane)
        only_scales = spec.get("only_scales")
        for (ln, scale, backend, workload, gav), rs in sorted(grouped.items()):
            if ln != src_lane:
                continue
            if only_scales and scale not in only_scales:
                continue
            if spec.get("only_workload") and workload != spec["only_workload"]:
                continue
            # The no-settle ablation is MEASURED but not PUBLISHED, and the
            # page was the only place it appeared. Neither paper reports it:
            # T4 is a clean head-to-head, one ArcadeDB row against three
            # comparators, and claims_check has no claim for it.
            #
            # It was a fair row in the sense that matters least. It costs us
            # (11.3 -> 36.7 ms at 1M, fourth place to last) so nobody was
            # flattered, but it sat among engine rows while being an ablation,
            # and no comparator has one, because nobody has run Elasticsearch
            # without its force-merge. So it could never answer the question it
            # invited: is leaning on compaction an ArcadeDB trait, or normal?
            #
            # The experiment stays in the harness; it is what de-confounded the
            # deployment axis. It comes off the page for the same reason the
            # f5 figure did: a number no paper reports is a number nobody
            # proofreads. Publish it when a comparator has the matching arm.
            if backend == "arcadedb_sparse_embedded_nocompact":
                continue
            image = BACKENDS.get(backend, {}).get("server_image")
            label = display_name(backend)
            if lane == "l3d":
                prec = DENSE_PRECISION.get(backend)
                if prec is None:
                    raise SystemExit(
                        f"l3d backend {backend!r} has no DENSE_PRECISION entry.\n"
                        "  Every dense row must state what it stores. Read the "
                        "adapter in l3d_dense.py, NOT the rows' `quantization` "
                        "field: that field echoes BENCH_DENSE_QUANT, an "
                        "ArcadeDB-only knob, and reports 'fp32' for LanceDB, "
                        "which builds IVF_HNSW_SQ and is int8.")
                label = (f"{label[:-1]}, {prec})" if label.endswith(")")
                         else f"{label} ({prec})")
            # The ablation runs under the same backend name, so the row has to
            # say which arm it is or the table shows one engine twice.
            # The VIEW-ON rows carry the label, because the view is the thing
            # worth naming; the ablation is plain ArcadeDB with a feature off.
            if lane == "l2olap" and gav != "False" and "arcade" in backend:
                label = (f"{label[:-1]}, GAV)" if label.endswith(")")
                         else f"{label} (GAV)")
            entry = {
                "backend": label,
                "is_arcadedb": "arcade" in backend,
                # Precision is a FIELD, not a suffix on the name. The page
                # renders it as its own column beside Mode, so the label does
                # not have to carry it in brackets. Kept in the label too,
                # because page_check pins that string to the paper's table and
                # a gate key should not move for a layout change.
                "precision": (DENSE_PRECISION.get(backend) if lane == "l3d"
                              else SPARSE_PRECISION.get(backend)),
                "scale": scale,
                "scale_label": scale_label(src_lane, scale),
                "workload": workload,
                "n_docs": rs[0].get("n_docs") or None,
                "deployment": deployment_of(backend),
                "image": image,
                # A served backend is identified by its pinned image; an
                # embedded one has no image, and used to end up with no build
                # line at all. So the sparse, graph and tabular tables named
                # every comparator's release and left OUR engine's version
                # blank, on the tables where the engine under test is the whole
                # point. The rows have carried engine_version all along.
                # Prefixed with the engine either way, so one engine's two
                # artifacts (the wheel and the pinned server image) read as the
                # same version rather than as "26.8.1" and "arcadedb 26.8.1",
                # which listed as two unrelated builds.
                "version_name": _engine_version(
                    label,
                    names.get(image) if image else rs[0].get("engine_version"),
                    image),
                "host": rs[0].get("host") or None,
                "metrics": {},
            }
            for field, label in spec["metrics"]:
                src = rs
                if field in MEM_FIELDS and src_lane in MERGED_WORKLOAD_LANES:
                    # See MEM_FIELDS above: this lane's rows were merged across
                    # workloads, which is right for a metric that only one
                    # workload produces and wrong for one both produce. Report
                    # the transactional run rather than a median straddling two.
                    src = [r for r in rs if r.get("workload") == "oltp"] or rs
                got = _agg(src, field)
                if got is not None:
                    entry["metrics"][label] = got
            if entry["metrics"]:
                entries.append(entry)
        if lane == "l3d":
            # REPLACE, never append. runs_paper.csv also holds deep10m
            # comparator rows, from the campaign path, and appending put two
            # measurements of the same cell in one table: Qdrant at 1.295 and
            # again at 1.342, Chroma at 0.686 and 0.700. Same engine, same
            # tier, different runs. That is the exact defect this whole pass
            # started from, reproduced one function later.
            #
            # The overlay wins because it is the matched set: one driver, one
            # protocol, every engine, and it is what T5 and f4 read.
            entries = [e for e in entries if e["scale"] != "deep10m"]
            entries.extend(_dense_10m_entries())
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
                "columns": ([label for _, label in spec["metrics"]]
                            if lane != "l3d" else
                            # warm exists only where a second pass was run,
                            # so it sits beside cold rather than replacing it
                            ["cold p50 ms", "warm p50 ms",
                             "recall@10", "build s"]),
                "withheld_scales": withheld,
                "withheld_reason": (
                    "Comparator rows exist at these tiers but ArcadeDB's were "
                    "measured on a pre-release build, which this project does "
                    "not publish. They return at the next release re-pin."
                ) if withheld else None,
                "entries": shown,
            })

    # _embedded_vs_tables() is NOT exported. It builds the SciPy paper's three
    # one-process tables (tabular/graph/vector over Stack Exchange), and they
    # were pulled from the page on 2026-08-13.
    #
    # They are legal under the papers-only rule and were still the wrong thing
    # to publish here. In the SciPy paper they sit beside a capability matrix
    # that states the claim they support: only the multi-model engine covers
    # documents, graph traversal and vector search in one process. The page
    # carries the tables and not the matrix, so it printed the evidence for an
    # argument it never made, and what a reader saw was three small benchmarks
    # ArcadeDB loses (13x to SQLite on OLTP, 150x to DuckDB on OLAP, 12.8x to
    # LadybugDB on graph OLAP, 3.5x to Chroma on vector) for no stated reason.
    #
    # The framing written to rescue them did not survive its own check either.
    # "No other row appears in all three" holds only because each table picked
    # a different comparator: on this page's own data DuckDB covers tabular,
    # time series and vector, and SQLite covers tabular and vector. Graph is
    # the model nothing else here combines with the rest.
    #
    # The page makes the point better twice already, with one atomic operation
    # instead of three separate benchmarks: the cross-model transaction section
    # and f4's cross-model bar at 10x against a composed stack.
    #
    # The function stays because the SciPy paper still publishes these rows and
    # a future page may want them WITH the matrix. Restoring them means adding
    # the matrix too, and re-adding their cells to page_check.MAPPING.
    for extra in (_sparse_multipass_table(), _l4_table(), _e4_table(),
                  _python_cost_table()):
        if extra and extra["entries"]:
            tables.append(extra)

    hosts = sorted({r["host"] for r in rows if r.get("host")})
    payload = {
        "source": "benchmarks/experiments/results/runs_paper.csv",
        "generator": "benchmarks/experiments/export_web.py",
        # Read from the rows, not asserted here. The literal "26.8.1" survived a
        # re-pin and two campaigns because nothing recomputed it (DECISIONS #49).
        "arcadedb_version": _arcadedb_identity(rows),
        "arcadedb_commits": sorted({
            c for c in (r.get("engine_commit") for r in rows
                        if str(r.get("backend", "")).startswith("arcadedb")) if c}),
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

    # A table can draw on more than one artifact, so this is a LIST. It was a
    # single string, and on 2026-08-13 that made the page lie: the DEEP-10M
    # rows were added to l3d from results/dense_mp5_2681/ while the table went
    # on printing "Measured rows: runs_paper.csv" under all of them. Nine rows
    # pointed a reader at a file that does not contain them.
    #
    # No gate caught it. provenance_check asks whether every CELL traces to a
    # run, which these do; nothing asked whether the SOURCE LINK the page
    # prints actually holds the rows above it. Adding a tier to a table has to
    # add its source here, and a list makes that the obvious thing to do rather
    # than a choice between two paths that only fits one.
    for table in tables:
        rel = SOURCES.get(table["id"])
        paths = [rel] if isinstance(rel, str) else list(rel or [])
        table["source_paths"] = paths
        table["source_urls"] = [f"{REPO}/{p}" for p in paths]
        # Kept so an older page build still renders something true: the first
        # entry, never a silently-wrong one.
        table["source_path"] = paths[0] if paths else None
        table["source_url"] = f"{REPO}/{paths[0]}" if paths else None

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
