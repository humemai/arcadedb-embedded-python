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
import collections
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runner import BACKENDS, MEM_BY_SCALE, HEAP_BY_SCALE  # noqa: E402  (path set above)

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


# AN ENGINE IDENTITY THAT IDENTIFIES NOTHING.
#
# 35 of 266 published ArcadeDB rows carried one of these in engine_version:
# "server:latest" (a floating tag -- whatever the registry served that day),
# "arcadedb-embedded" and "server" (backend names that leaked into the version
# field), and "unknown (PackageNotFoundError)". A number published under any of
# them cannot be attributed to a build, re-derived, or defended if challenged.
#
# They are not "a bit stale". Stale is knowable and comparable -- 26.8.1 is a
# real build we can diff against the pin. These identify nothing at all, which
# is strictly worse, and they must not render.
_UNUSABLE_VERSION = re.compile(
    r"^\s*(|none|null|unknown.*|arcadedb-embedded|arcadedb|server|server:latest|latest)\s*$",
    re.I)


def _dense_overlay_is_pinned():
    """Always, since 2026-09-08: dense_mp_dir() refuses instead of falling back."""
    import make_paper_tables as _MPT
    _MPT.dense_mp_dir()
    return True


def _pinned_dir(name, expected=None):
    """results/<name>_<pin>, complete, or refuse. PINNED ONLY since 2026-09-08
    (the fallback to results/<name> published a 26.8.1 overlay when the pinned
    one was incomplete; that is a wrong number, not a safety net)."""
    pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    if not pin:
        raise SystemExit(f"BENCH_ENGINE_COMMIT is unset: {name} is pinned only")
    cand = HERE / "results" / f"{name}_{pin}"
    if not cand.is_dir():
        raise SystemExit(f"{cand.name} missing; no fallback, re-run the lane")
    if expected:
        missing = [f for f in expected if not (cand / f).is_file()]
        if missing:
            raise SystemExit(f"{cand.name} has {len(missing)} of {len(expected)} files missing "
                             f"({', '.join(missing[:4])}{' ...' if len(missing) > 4 else ''}); no fallback")
    return cand


def _comparator_versions(rows):
    """backend -> the set of versions it was published under (non-ArcadeDB)."""
    out = {}
    for r in rows:
        b = str(r.get("backend") or "")
        if not b or b.startswith("arcadedb"):
            continue
        v = str(r.get("engine_version") or r.get("version_name") or "").strip()
        out.setdefault(b, set()).add(v or "(no version recorded)")
    return out


def _engine_is_identifiable(raw) -> bool:
    """False when engine_version names no build that could ever be resolved."""
    return not _UNUSABLE_VERSION.match(str(raw or ""))


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
        # "server:26.9.1-SNAPSHOT (build <sha>/<ts>/main)" is the served arm's
        # own banner; the version is the middle, the build sha stands in for a
        # missing commit. Without this the header listed the banner verbatim
        # as a third engine beside the two it already named.
        _m = re.search(r"\(build ([0-9a-f]{9})", ver)
        sha = sha or (_m.group(1) if _m else None)
        ver = re.sub(r"^server:", "", ver).split(" (build")[0].strip()
        # 26.9.1.dev0 / 26.8.1.dev25 / 26.9.1-SNAPSHOT -> 26.9.1-dev
        ver = re.sub(r"[.\-]?(dev\d*|SNAPSHOT)$", "-dev", ver, flags=re.I)
    if ver and sha:
        return f"arcadedb {ver} \u00b7 {sha}"
    return f"arcadedb {ver}" if ver else (f"arcadedb {sha}" if sha else None)


def _row_engine_string(r) -> str | None:
    """engine_version unless it is the driver's "unknown (...)" placeholder, in
    which case lib_version (the served arm's banner, learned on connect())."""
    ev = str(r.get("engine_version") or "")
    if ev.startswith("surrealdb-embedded:"):
        import surreal_common
        ev = surreal_common.legacy_stamp_fixup(ev)   # F39: SDK version was stamped as the engine
    if ev and not ev.startswith("unknown"):
        return ev
    # The served banner lands in backend_version on the L4 lane (its
    # engine_version comes from the wheel import, absent in the client image)
    # and in lib_version on the dense driver.
    for k in ("backend_version", "lib_version"):
        v = str(r.get(k) or "")
        if v and v.lower() != "none" and not v.startswith("unknown"):
            return v
    return None


def _campaign_engine_string(backend) -> str | None:
    """The newest campaign row's engine string for a backend, for overlay files
    that stamped neither engine_version nor lib_version (the served sparse
    multipass files). The overlay ran inside the same campaign envelope."""
    best = None
    try:
        with open(HERE / "results" / "runs.jsonl") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("backend") != backend or r.get("error"):
                    continue
                if _row_engine_string(r) and (best is None or str(r.get("ts_utc")) > str(best.get("ts_utc"))):
                    best = r
    except FileNotFoundError:
        return None
    return _row_engine_string(best) if best else None


def _overlay_commit() -> str | None:
    """The commit an overlay row belongs to: the files carry engine_commit=None
    (the driver never stamped it) but the directory is named by the pin, so a
    pinned overlay's rows are that commit's rows by construction."""
    return os.environ.get("BENCH_ENGINE_COMMIT", "").strip() or None if _dense_overlay_is_pinned() else None


def _engine_version(label: str, raw: str | None,
                    image: str | None = None, commit: str | None = None) -> str | None:
    """"<engine> <version>", from a row label and whatever the adapter stamped.

    The engine name comes from the IMAGE when there is one. A row label names
    the deployment a reader sees, which is not always the thing the version
    belongs to: the composed-stack row is labelled "Qdrant + Neo4j" and its
    pinned image is Neo4j's, so taking the name from the label produced
    "qdrant + neo4j 5-community" for a version only one of them has.
    """
    # OUR ENGINE IS NAMED FROM ITS OWN ROW, never from the image tag. The
    # served rows carry engine_version "server:26.9.1-SNAPSHOT (build <sha>)"
    # and engine_commit; the image in runner.py is the DEFAULT the campaign
    # overrides with ARCADEDB_SERVER_IMAGE, and its tag said 26.8.1 while the
    # container was built from 8d6af9475. 2026-09-07: every served ArcadeDB
    # entry on the page read "arcadedb 26.8.1" beside embedded rows at
    # "arcadedb 26.9.1", two identities for one pinned pair (PAGE-SPEC rule 1).
    if str(label or "").lower().startswith("arcadedb"):
        _raw = re.sub(r"^arcadedb\s+", "", str(raw or ""), flags=re.I)
        _m = re.search(r"\(build ([0-9a-f]{9})", _raw)
        _sha = (commit or "").strip() or (_m.group(1) if _m else None)
        _ver = re.sub(r"^server:", "", _raw.split(" (build")[0]).strip() or None
        return _engine_identity(_ver, _sha)
    if image:
        repo = image.split("@")[0].split(":")[0]
        engine = repo.rsplit("/", 1)[-1].lower()
        # An image WE built (dbbench:pg-age) names no engine; the row's own
        # string does ("PostgreSQL 17.11 + pgvector:0.8.6 + age:1.7.0"), so
        # that string is the identity, spelled as the engines spell it.
        if engine == "dbbench" and raw:
            return re.sub(r"\s*\+\s*", " + ", str(raw).replace(":", " ")).strip()
    else:
        engine = label.split(" (")[0].strip().lower()
    # A composed row stamps every part ("qdrant-local:1.19.0+neo4j:5.26.28");
    # the version that belongs to the image's engine is the one after ITS
    # name, not the first version-shaped token (which gave "neo4j 1.19.0").
    _raw = str(raw or "")
    _k = _raw.lower().find(f"{engine}:")
    ver = _short_version(_raw[_k + len(engine) + 1:] if _k >= 0 else _raw)
    if not ver:
        return None
    return f"{engine} {ver}"


def _dense_rows_for_note():
    """Frozen l3d rows, for notes that apply only when an engine is present."""
    try:
        with open(FROZEN, newline="") as fh:
            return [r for r in csv.DictReader(fh) if r.get("lane") == "l3d"]
    except OSError:
        return []


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
    # The int8 arms fell through to the bare "ArcadeDB" default and the dense
    # table showed two rows both labelled "ArcadeDB (int8)" at 1M (2026-09-09).
    "arcadedb_dense_embedded_int8": "ArcadeDB (embedded)",
    "arcadedb_dense_server_int8": "ArcadeDB (server)",
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
    "arcadedb_sparse_server_fp32": "ArcadeDB (server, fp32)",
    "arcadedb_sparse_embedded_fp32": "ArcadeDB (embedded, fp32)",
    "arcadedb_sparse_embedded_nocompact": "ArcadeDB (embedded, no settle step)",
    "arcadedb_e2": "ArcadeDB (one transaction)",
    "arcadedb_e2_server": "ArcadeDB (server, one transaction)",
    "composed_qdrant_neo4j": "Qdrant + Neo4j (no shared transaction)",
    "surrealdb_e2": "SurrealDB (embedded)",
    "surrealdb_e2_server": "SurrealDB (server)",
    "pg_age_e2": "PostgreSQL + pgvector + AGE",
    "neo4j_e2": "Neo4j (vector index)",
    "qdrant_sparse": "Qdrant", "qdrant_dense": "Qdrant", "qdrant_dense_int8": "Qdrant",
    "milvus_sparse": "Milvus", "milvus_dense": "Milvus", "milvus_dense_int8": "Milvus",
    "sqlite_vec_dense_int8": "sqlite-vec",
    "elasticsearch_sparse": "Elasticsearch",
    "chroma_dense": "Chroma", "lancedb_dense": "LanceDB",
    "sqlite_vec_dense": "sqlite-vec", "duckdb_vss_dense": "DuckDB VSS",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "postgres": "PostgreSQL", "postgres_tuned": "PostgreSQL (tuned)",
    "duckdb": "DuckDB", "questdb": "QuestDB", "sqlite": "SQLite", "mongodb": "MongoDB",
    "timescaledb": "TimescaleDB", "pgvector_dense": "pgvector", "pgvector_sparse": "pgvector", "neo4j_dense": "Neo4j",
    "surrealdb_tpc": "SurrealDB (embedded)", "surrealdb_tpc_server": "SurrealDB (server)",
    "surrealdb_graph": "SurrealDB (embedded)", "surrealdb_graph_server": "SurrealDB (server)",
    "surrealdb_dense": "SurrealDB (embedded)", "surrealdb_dense_server": "SurrealDB (server)",
    # Served only, so bare, like MongoDB and Neo4j; "(server)" marks an engine
    # that also has an embedded row.
    "arangodb_tpc": "ArangoDB", "arangodb_graph": "ArangoDB", "arangodb_dense": "ArangoDB", "arangodb_e2": "ArangoDB",
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
    "arcadedb_sparse_server_fp32": "fp32",
    "qdrant_sparse": "fp32",
    "milvus_sparse": "fp32",
    "pgvector_sparse": "fp32",  # sparsevec stores float4 values
    "elasticsearch_sparse": "~9-bit",
}

DENSE_PRECISION = {
    "arcadedb_dense_embedded": "fp32",
    "arcadedb_dense_server": "fp32",
    "chroma_dense": "fp32",
    "pgvector_dense": "fp32",   # vector(96/128), no quantization used
    "surrealdb_dense": "fp32", "surrealdb_dense_server": "fp32",   # HNSW TYPE F32
    "arangodb_dense": "fp32",   # FAISS IVF over the raw float array
    "neo4j_dense": "fp32",      # float property list, no quantization option
    "qdrant_dense": "fp32",
    "milvus_dense": "fp32",
    "duckdb_vss_dense": "fp32",
    "sqlite_vec_dense": "fp32",
    "lancedb_dense": "int8",
    # The int8 comparator arms. They are written in l3d_dense.py, registered in
    # runner.py, and running in the current campaign, but they had no entry
    # here -- and a dense backend without one makes this script raise
    # SystemExit. So the first campaign to finish them would have failed the
    # export rather than published them. Verified against the DDL each arm
    # issues, per DECISIONS #53, not against its name:
    #   qdrant_dense_int8             ScalarQuantization(type=INT8, quantile .99)
    #   milvus_dense_int8             HNSW_SQ / SQ8
    #   arcadedb_dense_embedded_int8  LSM_VECTOR METADATA quantization INT8
    "qdrant_dense_int8": "int8",
    "milvus_dense_int8": "int8",
    "arcadedb_dense_embedded_int8": "int8",
    # DECISIONS #53 arms, added 2026-08-30. Checked against the DDL each issues:
    #   arcadedb_dense_server_int8  METADATA "quantization": "INT8" in the POSTed DDL
    #   sqlite_vec_dense_int8       vec0(embedding int8[DIM]) + vec_quantize_int8(v,'unit')
    "arcadedb_dense_server_int8": "int8",
    "sqlite_vec_dense_int8": "int8",
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
    ("l3s", "tiny"): "100k vectors",
    ("l3s", "small"): "1M vectors",
    ("l3s", "medium"): "8.84M vectors",
    ("l3d", "small"): "1M vectors",
    ("l3d", "deep10m"): "9.99M vectors",
    # LDBC publishes its tiers as scale factors, so SF1/SF10 are the corpus's
    # own vocabulary rather than ours; the person count says how big that is.
    ("l2", "sf1"): "SF1 (11k people)",
    ("l2", "sf10"): "SF10 (73k people)",
    ("l1", "medium"): "20M orders (synthetic)",
    ("l1tpc", "tpch1"): "TPC-H SF1 (6.0M line items)",
    ("e2", "e2"): "50k products",
    # TSBS publishes its corpus as a point count, which is what the ingest
    # column is per second of.
    ("l4", "ts100"): "2.59M points",
    # The lifecycle tiers are row counts of the structure under test, so the
    # label is the count rather than a tier name a reader cannot size.
    ("lifecycle", "lc10k"): "10k",
    ("lifecycle", "lc100k"): "100k",
    ("lifecycle", "lc1m"): "1M",
    ("lifecycle", "lc10m"): "10M",
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
            "benchmarks/experiments/results/dense_mp5_<pin or 2681>"],   # resolved in _dense_overlay_entries
    "l2": "benchmarks/experiments/results/runs_paper.csv",
    "l1": "benchmarks/experiments/results/runs_paper.csv",
    "l1tpc": "benchmarks/experiments/results/runs_paper.csv",
    "e2": "benchmarks/experiments/results/runs_paper.csv",
    "l4": "benchmarks/experiments/results/runs_paper.csv",
    "e4": "benchmarks/experiments/results/e4decomp_" + (os.environ.get("BENCH_ENGINE_COMMIT", "").strip() or "UNPINNED"),
    "l2olap": "benchmarks/experiments/results/runs_paper.csv",
    "e2atom": "benchmarks/experiments/results/runs_paper.csv",
    "lifecycle": "benchmarks/experiments/results/runs_paper.csv",
    "docs_oltp": "benchmarks/experiments/results/runs_paper.csv",
    "docs_olap": "benchmarks/experiments/results/runs_paper.csv",
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
    ("arcsrv_int8", "arcadedb_dense_server_int8", "ArcadeDB (server, int8)", True),
    ("qdrant", "qdrant_dense", "Qdrant (fp32)", False),
    ("chroma", "chroma_dense", "Chroma (fp32)", False),
    ("duckvss", "duckdb_vss_dense", "DuckDB VSS (fp32)", False),
    # IVF_HNSW_SQ: the only quantized comparator, and it was unlabelled while
    # ArcadeDB's two arms were, which made quantization read as our quirk.
    ("lancedb", "lancedb_dense", "LanceDB (int8)", False),
    ("milvus", "milvus_dense", "Milvus (fp32)", False),
    ("milvus_int8", "milvus_dense_int8", "Milvus (int8)", False),
    ("qdrant_int8", "qdrant_dense_int8", "Qdrant (int8)", False),
    ("sqlitevec_int8", "sqlite_vec_dense_int8", "sqlite-vec (int8)", False),
    ("sqlitevec", "sqlite_vec_dense", "sqlite-vec (fp32)", False),
    # 2026-09-11 additions; their overlay files appear when qDK lands and the
    # rows are skipped until then.
    ("pgvector", "pgvector_dense", "pgvector (fp32)", False),
    ("neo4jvec", "neo4j_dense", "Neo4j (fp32)", False),
    ("surreal", "surrealdb_dense", "SurrealDB (embedded, fp32)", False),
    ("surrealsrv", "surrealdb_dense_server", "SurrealDB (server, fp32)", False),
    ("arango", "arangodb_dense", "ArangoDB (fp32)", False),
]


def _dense_overlay_entries(scale="deep10m"):
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
    import make_paper_tables as _MPT
    # One protocol at both sizes since 2026-09-10 (BUGS F26): deep10m reads
    # dense_mp5_<pin>, small reads dense_mp5_small_<pin>, both pinned-only.
    # Arms come from the overlay's own contents (required set plus every
    # optional September arm whose files are complete; a partial arm
    # refuses), so a landed comparator appears without an edit here.
    if scale == "deep10m":
        root, n_docs = Path(_MPT.dense_mp_dir()), "9,990,000"
        present = _MPT.mp_arms_present(small=False)
    else:
        root, n_docs = Path(_MPT.dense_mp_small_dir()), "1,000,000"
        present = _MPT.mp_arms_present(small=True)
    arms = [a for a in DENSE_10M_ARMS if a[0] in present]
    if not root.is_dir():
        return []
    out = []
    for arm, backend_key, label, ours in arms:
        hits = sorted(root.glob(f"mp_{arm}_b*.json"))
        if not hits:
            continue
        cold, warm, recall, build, peak, ver = [], [], [], [], [], set()
        for h in hits:
            passes = json.loads(h.read_text(encoding="utf-8"))
            if not passes:
                continue
            _ev = passes[0].get("engine_version")
            # engine_version on an overlay pass names the harness's ArcadeDB
            # wheel ("unknown (PackageNotFoundError)" in the client image);
            # a comparator's own version is lib_version ("neo4j:2026.07.1"),
            # and our served arm's is lib_version too ("server:26.9.1...").
            if str(_ev or "").startswith("unknown") and passes[0].get("lib_version"):
                _ev = passes[0]["lib_version"]
            ver.add(_ev)
            build.append({"build_s": passes[0].get("build_s")})
            peak.append({"peak_anon_mib_sum": passes[0].get("peak_anon_mib_sum")})
            cold.append({"p50": passes[0].get("p50"), "p99": passes[0].get("p99")})
            for p in passes[1:]:
                warm.append({"p50": p.get("p50"), "p99": p.get("p99")})
                recall.append({"r": p.get("recall_at_10")})
        metrics = {}
        for label_, rows_, field in (("cold p50 ms", cold, "p50"),
                                     ("cold p99 ms", cold, "p99"),
                                     ("warm p50 ms", warm, "p50"),
                                     ("warm p99 ms", warm, "p99"),
                                     ("recall@10", recall, "r"),
                                     ("ingest+index total s", build, "build_s")):
            got = _agg(rows_, field)
            if got is not None:
                metrics[label_] = got
        if not metrics:
            continue
        if metrics.get("ingest+index total s") and metrics["ingest+index total s"]["median"]:
            _b = metrics["ingest+index total s"]
            _n = 9_990_000 if scale == "deep10m" else 1_000_000
            metrics["ingest+index vectors/s"] = {"median": round(_n / _b["median"], 1), "min": round(_n / _b["max"], 1),
                                           "max": round(_n / _b["min"], 1), "n": _b["n"]}
        # Peak memory is in the multipass files (pass 0 carries the build);
        # disk is not, and comes from the campaign cell of the same arm.
        # The campaign backend name carries the precision (arcadedb_dense_
        # embedded_int8); the arm table keys ArcadeDB's int8 arm by token.
        _cb = backend_key if (not arm.endswith("int8") or backend_key.endswith("_int8")) else backend_key + "_int8"
        # Peak memory and disk from the campaign cell of the same arm: the
        # served arm's multipass file sees only the client container (3.6 GiB
        # against the pair's 28), and no file carries disk. Same build, same
        # envelope; the overlay's own peak is the fallback.
        _pk = _campaign_stat(_cb, scale, "peak_anon_mib_sum") or _agg(peak, "peak_anon_mib_sum")
        if _pk is not None:
            metrics["peak memory GiB"] = _pk
        _dk = _campaign_stat(_cb, scale, "disk_data_mb")
        if _dk is not None:
            metrics["disk GiB"] = _dk
        # Only OUR arms carry a version string; the comparator containers do
        # not expose one to this driver and record "unknown (...)". Reporting
        # that as a build would be worse than reporting nothing.
        v = next((x for x in ver if x and not str(x).startswith("unknown")), None)
        # The comparator files stamp nothing usable, but the same arm ran in
        # the campaign lane at this size with its version recorded; the page
        # showed nine unversioned rows at 10M for that (2026-09-10).
        if v is None and not ours:
            v = _campaign_engine_string(_cb)
        out.append({
            "backend": label,
            "is_arcadedb": ours,
            # NOT `arm == "int8"`. arm is a FILENAME token, and only ArcadeDB's
            # quantized arm is called "int8"; LanceDB's is "lancedb", so the
            # published deep10m row carried precision="fp32" beneath the label
            # "LanceDB (int8)" -- confirmed in web_benchmarks.json. DENSE_PRECISION
            # is the audited answer, and the arm token only has to disambiguate
            # ArcadeDB's two arms, which share one backend name.
            "precision": ("int8" if arm == "int8"
                          else DENSE_PRECISION.get(backend_key, "fp32")),
            "scale": scale,
            "scale_label": scale_label("l3d", scale),
            "workload": "search",
            "n_docs": n_docs,
            "deployment": deployment_of(backend_key),
            "image": None,
            "version_name": _engine_version(label, v, commit=_overlay_commit()),
            "host": "mini",
            "metrics": metrics,
        })
    return out


# Fields whose stored unit is not the unit the column claims. The artifact
# records memory in MiB because that is what cgroup reports; the paper and the
# page both talk in GiB, and a column headed "GiB" printing 8256 would be a
# defect the reader has to catch. Divide here, once, rather than in each table
# spec where the next lane to add memory would forget it.
_UNIT_DIVISOR = {"peak_anon_mib_sum": 1024.0, "end_anon_mib_sum": 1024.0, "disk_data_mb": 1024.0,
                 "cpu_usec_sum": 1e6}
DISK_NOTE = ("Disk is what the workload left on disk, in GiB: the engine's writable layer "
             "plus its volumes after the cell, minus the same engine's empty footprint. It is "
             "read after the queries, so it includes anything querying wrote; a server "
             "reading is taken once two samples agree within 1%, an embedded reading once on "
             "the stopped container. A blank cell is a row measured before the disk "
             "reading existed (2026-08-14). Neo4j's value includes the transaction-log "
             "files it preallocates in 256 MiB steps, which is how Neo4j uses disk; "
             "turning that off would have slowed its writes by 65%, so it stays on.")


def _campaign_stat(backend, scale, field, lanes=("l3d", "l3s")):
    """_agg of one field over the newest campaign row per rep for (backend,
    scale): the overlay files (multipass) carry no disk reading, but the
    campaign cell of the same arm in the same envelope does, and the on-disk
    size is a property of the build, not of which pass was timed."""
    newest = {}
    try:
        with open(HERE / "results" / "runs.jsonl") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("backend") != backend or r.get("scale") != scale or r.get("error"):
                    continue
                if r.get("lane") not in lanes or r.get("rc", 0) not in (0, None):
                    continue
                k = (r.get("workload"), r.get("rep"))
                if k not in newest or str(r.get("ts_utc")) > str(newest[k].get("ts_utc")):
                    newest[k] = r
    except FileNotFoundError:
        return None
    return _agg(list(newest.values()), field)



def _disk_data(r):
    """disk_data_mb, unless this is a served row whose server reading is
    missing: then the field is the client's scratch alone (1.1 MB for a
    SurrealDB server holding 6.0M line items, 2026-09-13) and says nothing."""
    if r.get("server_image") and not r.get("server_disk_mb"):
        return None
    v = r.get("disk_data_mb")
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


_disk_data.unit_field = "disk_data_mb"

def _rate(count_fields, seconds_field):
    """A per-row records-per-second callable for spec tables whose lanes
    record counts and seconds but no rate (graph, TPC, cross-model)."""
    def fn(r):
        n = sum((_num(r.get(f)) or 0) for f in count_fields)
        t = _num(r.get(seconds_field))
        return (n / t) if (n and t) else None
    fn.__name__ = f"rate({'+'.join(count_fields)})/{seconds_field}"
    return fn


def _agg(rows, field):
    """Median across repetitions, with the spread, matching the paper."""
    if callable(field):
        vals = [v for v in (field(r) for r in rows) if v is not None]
        if not vals:
            return None
        # A callable stands in for a row field; it says which one through
        # unit_field so the divisor still applies. 2026-09-13: _disk_data
        # replaced "disk_data_mb" on seven tables and, without this, the page
        # printed megabytes under a "disk GiB" header for a day (gates green:
        # no pin covered a disk cell; page_check now bounds every disk column).
        div = _UNIT_DIVISOR.get(getattr(field, "unit_field", None))
        if div:
            vals = [v / div for v in vals]
        return {"median": round(statistics.median(vals), 4), "min": round(min(vals), 4),
                "max": round(max(vals), 4), "n": len(vals)}
    vals = [v for v in (_num(r.get(field)) for r in rows) if v is not None]
    if field == "gav_build_s":
        # A row without the view records 0.0 for the view it did not build;
        # that is an absent cell, not a zero-second build.
        vals = [v for v in vals if v > 0]
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
        # p50 and p99 only, like every other table: p95 never changed a reading
        # and cost a column on a phone. It stays in the rows and the CSV.
        "metrics": [("query_p50_ms", "p50 ms"), ("query_p99_ms", "p99 ms"),
                    ("recall_at_10", "recall@10"),
                    ("build_docs_per_s", "ingest+index vectors/s"),
                    ("build_s", "ingest+index total s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
        "conditions": [
            "Recall is reported beside every latency: ArcadeDB quantizes posting weights to int8 by default, so a latency number without its recall is not comparable.",
            "ingest+index total s is one timer around inserting the documents and building the index; the two are not timed separately (Qdrant builds its index while ingesting, so the split is not defined there). ingest+index vectors/s divides the document count by it.",
            "Elasticsearch runs with index-time token pruning disabled. Its 9.x default prunes on thresholds tuned for a different model's vectors and costs recall on this corpus, which would have printed a quality gap belonging to that default rather than to the engine, and printed it in our favour.",
            "Cold is the first timed pass after the index is built; warm is the same engine run again over an index it has already read, and gain is cold over warm. Here a second pass changes little and the order of the table is the same either way. The dense table below is not like this: there ArcadeDB gains the most on a second pass and the order depends on which pass you time.",
            "ArcadeDB's server takes roughly twice as long to build as its embedded deployment, and that gap is loading the data, not building the index. Both run the same index code. The embedded one is handed the numbers directly, because the database is running inside the same program. The server has to be sent them, and the only way in is a written-out INSERT statement: a document here has about 127 non-zero weights, so each one arrives as roughly 254 numbers spelled out as text, which the server then has to read back into numbers.",
        ],
    },
    "l3d": {
        "title": "Dense vector search",
        "dataset": "DEEP-10M (deep-image-96-angular) and SIFT-1M",
        # "cold" rather than a bare "p50" because the two passes are different
        # quantities and the page now says so. Both lanes measure the cold
        # column identically: l3d_dense runs 20 untimed warmups then ONE timed
        # pass, and dense_multipass_driver runs those same 20 warmups before
        # each of its five, so overlay pass 0 IS the campaign protocol. The
        # Since 2026-09-10 (qDB) the 1M size has its own multipass overlay, so
        # both sizes carry cold and warm from one protocol.
        "metrics": [("query_p50_ms", "cold p50 ms"), ("query_p99_ms", "cold p99 ms"),
                    ("recall_at_10", "recall@10"),
                    ("build_docs_per_s", "ingest+index vectors/s"),
                    ("build_s", "ingest+index total s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
        "conditions": [
            "ingest+index total s is one timer around inserting the vectors and building the index; the two are not timed separately (Qdrant and Chroma build the index while ingesting, so the split is not defined there). ingest+index vectors/s divides the vector count by it.",
            "ArcadeDB's maxConnections is a Vamana per-layer degree, not hnswlib's M. Matching the parameter names would compare a half-degree graph against a full-degree one, so the graphs are matched by effect instead.",
*(["ArangoDB's vector index is FAISS IVF (inverted lists over trained centroids), not HNSW, so the degree match above does not apply to it; its rows record nLists (about the square root of the corpus) and nProbe (an eighth of the lists) instead."]
              if any(str(r.get("backend")) == "arangodb_dense" for r in _dense_rows_for_note()) else []),
            "Cold is the first timed pass after the index is built; warm is a repeat of the same query set. Only ArcadeDB moves between them, because it pages its index off disk while the others are resident from build. Every comparator here is within 3% of itself.",
            "Milvus's dense rows run with segments sealed at 50% of the maximum segment size (the image default is 12%), so a 10M ingest lands directly in the 6 to 8 segment layout that Milvus's own compaction otherwise reaches at an unpredictable moment; without it, half the runs queried 26 to 28 small segments and read 2.3x slower with higher recall. One line changed from the image's configuration; sparse rows are at the default.",
            *([("ArcadeDB fp32 rows at 9.99M carry graphBuildCacheSize pinned to the corpus size (9,990,000) on both deployments, a user decision so the served build is not left on the wrong side of the engine's cache knee (issue #7146; the budget 26.10.1 makes the default). INT8 rows run this engine's default of 100,000. Comparators have no equivalent setting.")]
              if _dense_overlay_is_pinned() else []),
        ],
    },
    "l2": {
        "title": "Graph OLTP",
        "dataset": "LDBC-SNB Interactive (SF1, SF10)",
        # Peak anon last, and present at all because the page had no memory
        # column anywhere while every lane has measured it since the #52 fix.
        # It is also the column that shows our largest loss on this lane:
        # LadybugDB runs the same SF10 workload in a twenty-second of the
        # memory. A page that omits the resource axis reads as if latency
        # were the only axis anyone deploys on.
        "metrics": [("point_p50_ms", "point p50 ms"), ("point_p99_ms", "point p99 ms"),
                    ("hop1_p50_ms", "1-hop p50 ms"), ("hop1_p99_ms", "1-hop p99 ms"),
                    ("hop2_p50_ms", "2-hop p50 ms"), ("hop2_p99_ms", "2-hop p99 ms"),
                    ("write_p50_ms", "write p50 ms"), ("write_p99_ms", "write p99 ms"),
                    (_rate(("n_persons_ingested", "n_edges_ingested"), "build_s"), "ingest vertices+edges/s"),
                    ("build_s", "ingest total s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
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
    # SF1 and SF10 since 2026-09-07 (qCS measured the view-off arm at SF1;
    # until then it existed at SF10 only). Kept for the record:
    # The ablation was run at SF10, so SF1 has no view-off arm, and a table
    # with an ablation row that is dashed at one scale invites the reader to
    # read the dash as a failure.
    "l2olap": {
        "title": "Graph OLAP",
        "dataset": "LDBC-SNB, SF10",
        "lane_source": "l2",
        "only_scales": {"sf1", "sf10"},
        "only_workload": "olap",
        # p50, not the mean the page printed until 2026-09-10 (the lane's own
        # comment says p50 first, and it recorded one); p99 arrives with the
        # 100-iteration rows (F29).
        "metrics": [(_rate(("n_persons_ingested", "n_edges_ingested"), "build_s"), "ingest vertices+edges/s"),
                    ("build_s", "ingest total s"),
                    ("friend_age_by_city_p50_ms", "average friend age p50 ms"),
                    ("friend_age_by_city_p99_ms", "average friend age p99 ms"),
                    ("same_city_edges_p50_ms", "friends in same city p50 ms"),
                    ("same_city_edges_p99_ms", "friends in same city p99 ms"),
                    ("top_degree_p50_ms", "most friends p50 ms"),
                    ("top_degree_p99_ms", "most friends p99 ms"),
                    ("gav_build_s", "view build s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
        "conditions": [
            "Three questions, each asked of the whole graph. Average friend age: for every city, the average age of the friends of the people who live there. Friends in same city: how many friendships connect two people in the same city. Most friends: which people have the highest number of friends. All three times are milliseconds.",
            "The Graph Analytical View is a copy of the graph that ArcadeDB builds in memory, laid out for questions that sweep the whole graph rather than follow a few links. Building it took 2.0 seconds here, once, before any query was timed.",
            "The two rows labelled ArcadeDB (embedded) are the same engine on the same data, differing only in whether that view is built. Both return identical answers.",
            "The benefit is uneven, and the three queries show why. Top degree gains most because it only walks adjacency. The other two read a property from the far end of every edge traversed, and that lookup costs the same either way, so it comes to dominate once the traversal itself is cheap.",
        ],
    },
    "l1olap": {
        "title": "Document OLAP, query by query",
        "dataset": "Synthetic orders workload, the five analytical queries behind the OLAP total",
        "lane_source": "l1",
        "only_workload": "olap",
        "metrics": [("olap_agg_by_region_ms", "aggregate by region ms"),
                    ("olap_top_customers_ms", "top customers ms"),
                    ("olap_filtered_avg_ms", "filtered average ms"),
                    ("olap_status_histogram_ms", "status histogram ms"),
                    ("olap_range_agg_ms", "range aggregate ms"),
                    # p50/p99 over 100 iterations (F29); the mean columns above
                    # come out once every row carries these.
                    ("olap_agg_by_region_p50_ms", "aggregate by region p50 ms"),
                    ("olap_agg_by_region_p99_ms", "aggregate by region p99 ms"),
                    ("olap_top_customers_p50_ms", "top customers p50 ms"),
                    ("olap_top_customers_p99_ms", "top customers p99 ms"),
                    ("olap_filtered_avg_p50_ms", "filtered average p50 ms"),
                    ("olap_filtered_avg_p99_ms", "filtered average p99 ms"),
                    ("olap_status_histogram_p50_ms", "status histogram p50 ms"),
                    ("olap_status_histogram_p99_ms", "status histogram p99 ms"),
                    ("olap_range_agg_p50_ms", "range aggregate p50 ms"),
                    ("olap_range_agg_p99_ms", "range aggregate p99 ms")],
        "conditions": [
            "The same five queries whose sum is the OLAP total in the table above, one column each, so a reader can see which shapes an engine is slow on rather than one number.",
        ],
    },
    "e2atom": {
        "title": "Cross-model transaction: what survives a crash",
        "dataset": "The same vector-graph-document operation, killed mid-way, then inspected",
        "lane_source": "e2",
        "only_workload": "atomicity",
        # crashes raised equalled trials on every row (2026-09-12, DECISIONS
        # #73): the kill always lands, so the column said nothing.
        "metrics": [("trials", "trials"), ("torn_count", "torn results")],
        "conditions": [
            "A trial writes the three products, kills the process between them, reopens, and checks whether every product is present or none. Torn means some but not all: the counts the page's E2 prose quotes are these.",
        ],
    },
    "l1": {
        "title": "Documents: OLTP and OLAP",
        "dataset": "Synthetic orders workload",
        "metrics": [("read_p50_ms", "read p50 ms"), ("read_p99_ms", "read p99 ms"),
                    ("insert_p50_ms", "insert p50 ms"), ("insert_p99_ms", "insert p99 ms"),
                    ("update_p50_ms", "update p50 ms"), ("update_p99_ms", "update p99 ms"),
                    ("oltp_ops_per_s", "OLTP ops/s"), ("ingest_rows_per_s", "ingest documents/s"),
                    ("ingest_s", "ingest total s"),
                    ("olap_total_ms", "OLAP total ms"),
                    ("olap_total_p50_ms", "OLAP total p50 ms"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
        # The memory column is the one cell on this page a reader can most
        # easily misread, because the gap looks like two orders of magnitude
        # and is mostly an accounting boundary. Stated here rather than left
        # for the reader to work out.
        "conditions": [
            "PostgreSQL's memory cell is not comparable to the other two. It keeps its data in shared memory and in the file cache the kernel holds for it, and this column counts neither, so it reads 0.12 GiB where the run's actual peak was 3.85. Most of even that 0.12 is our own benchmark client rather than the database: 0.105 of it. We checked that this is the measure and not the setting, by giving a PostgreSQL container a 2 GB buffer pool and watching this column stay at 5 MiB.",
        ],
    },
    "l1tpc": {
        "title": "Documents (TPC-H and TPC-C shapes)",
        "dataset": "TPC-H queries, TPC-C new-order",
        "metrics": [("q1_ms", "Q1 p50 ms"), ("q1_p99_ms", "Q1 p99 ms"),
                    ("q6_ms", "Q6 p50 ms"), ("q6_p99_ms", "Q6 p99 ms"),
                    ("neworder_p50_ms", "new-order p50 ms"), ("neworder_p99_ms", "new-order p99 ms"),
                    ("oltp_ops_per_s", "OLTP ops/s"),
                    (_rate(("n_lineitem", "n_part"), "build_s"), "ingest documents/s"),
                    ("build_s", "ingest total s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
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
                    (_rate(("n_products", "n_edges"), "build_s"), "ingest+index vertices+edges/s"),
                    ("build_s", "ingest+index total s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
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
        # SurrealDB runs in-process at mem://, and the composed arm's Qdrant
        # half at :memory:; neither has a disk footprint (2026-09-10, F27).
        "in_memory": ("surrealdb_e2",),
        "conditions": [
            "Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge, and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.",
            "So the interesting result here is not the speed. It is what a crash halfway through leaves behind. The raw data records, for each run, whether an interrupted write left the two stores disagreeing, and whether they still disagreed after restarting. That is what this comparison exists to show.",
            "Read the times with one caveat, which cuts against ArcadeDB. ArcadeDB here writes to disk, while SurrealDB runs entirely in memory and the composed stack's vector half does too. Part of why they answer faster is that they never touch a disk. The all-or-nothing result above does not depend on this, since a half-finished update is visible in memory just as it is on disk, but the millisecond columns do.",
            "SurrealDB runs in memory (mem://), so its disk cell is blank: it leaves nothing on disk. The composed stack's Qdrant half also runs in memory (:memory:), so its disk value is Neo4j's alone.",
        ],
    },
}

GLOBAL_CONDITIONS = [
    "Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.",
    "Peak memory is the largest amount an engine held in its own address space, added over every container a run used, and it leaves out the file cache the kernel keeps on the engine's behalf. That is the right number for engines that manage their own memory, and an undercount for engines that lean on the kernel instead, so compare it down one engine's rows rather than across engines that work differently.",
    "Each printed cell is the median of 5 repetitions, with min and max carried alongside; nothing here is a single sample.",
    "Defaults first. Where a default would make the comparison meaningless, it is equalized and the override is disclosed rather than hidden.",
    "Comparators are pinned by sha256 image digest, not by a floating tag.",
    "Durability is at each engine's default, and the defaults differ: ArcadeDB does "
    "not flush its write-ahead log at commit (txWalFlush=0), PostgreSQL and Neo4j "
    "fsync at every commit, and SQLite is the one comparator not at its default: it runs "
    "in WAL mode with synchronous=NORMAL, the common production setting, because its "
    "default rollback journal fsyncs twice per commit. On the write rows (document OLTP, TPC-C new-order, "
    "graph writes, the cross-model transaction) ArcadeDB's lead over the fsyncing servers is largely this default plus the "
    "absence of a network hop, not the engine. The next campaign runs ArcadeDB "
    "with fsync at commit on every timed write path.",
]


# _pinned_dir cannot be used here: it is defined below and this is module scope.
# Resolved the same way, and for the same reason -- e4decomp_2681 is a 2026-08-07
# artifact on 26.8.1, so a pinned re-run must be able to supersede it without an
# edit here. The "_2681" name is kept as the fallback because that is what exists.
E4_DIR = HERE / "results" / f"e4decomp_{os.environ.get('BENCH_ENGINE_COMMIT', '').strip() or 'UNPINNED'}"
if not E4_DIR.is_dir():
    raise SystemExit(f"{E4_DIR.name} missing; E4 is pinned only since 2026-09-08 (e4decomp_2681 retired), run the e4 lane")

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
    reps = sorted(E4_DIR.glob("decomp3m_*_rep*.json"))
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
        # The two derived differences (packing cost, separate process) left
        # the table on 2026-09-12 (DECISIONS #73): a negative "cost" cell
        # confused more than the subtraction saved, and the prose beside the
        # table names which two columns to subtract.

        entries.append({
            "backend": f"{int(size):,} documents",
            "is_arcadedb": True,
            "scale": f"{int(size):,}",
            "workload": "projection",
            "n_docs": str(meta.get("rows")),
            "deployment": "all three",
            "image": None,
            "version_name": _engine_identity(meta.get("engine_version"), meta.get("engine_commit")),
            "host": meta.get("host"),
            "metrics": metrics,
        })

    return {
        "id": "e4",
        "title": "What the client/server split costs",
        "dataset": f"{meta.get('rows'):,}-document projection, one engine, three deployments",
        "conditions": [
            *([f"Measured at ArcadeDB {meta.get('engine_version')} on {str(meta.get('ts_utc'))[:10]}. This table has not yet been re-run at the engine commit the rest of the page reports; the re-run is queued and this line goes away with it."]
              if str(meta.get("engine_version") or "") and not str(meta.get("engine_version") or "").startswith("26.9.1") else []),
            f"Every number is milliseconds. One engine build "
            f"({_engine_identity(meta.get('engine_version'), meta.get('engine_commit'))}) in all three deployments, "
            f"{meta.get('reps')} repetitions after {meta.get('warmup')} warmup, "
            f"identical cpuset {meta.get('cpuset')}, memory cap {meta.get('mem_cap')} "
            f"and heap {meta.get('heap')}.",
            "All three deployments turn the answer into Python objects the same "
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
        "columns": [label for _, label in E4_ARMS],
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
    ("ingest_pts_per_s", "ingest points/s"),
    ("ingest_s", "ingest total s"),
    # "last-point" is TSBS's own name for this query and it reads as "the
    # final point" rather than "the newest one", which is what it means.
    # The page says what the query does; the papers keep the TSBS term.
    (("q_last_unbounded_ms", "q_last_ms"), "newest reading p50 ms"),
    ("q_last_p99_ms", "newest reading p99 ms"),
    ("q_global_ms", "12h aggregate p50 ms"),
    ("q_global_p99_ms", "12h aggregate p99 ms"),
    ("peak_anon_mib_sum", "peak memory GiB"),
    ("disk_data_mb", "disk GiB"),
]


# backend -> the label this table has always used. Canonical rows name backends
# the way runner.BACKENDS does; the legacy files named them by hand.
L4_CANON_LABELS = {
    # Named like every other table's ArcadeDB rows (2026-09-11): the engine
    # capitalised, the mode first, then which storage path the row took.
    "arcadedb_ts_native": "ArcadeDB (embedded, native time series)",
    "arcadedb_ts_doc":    "ArcadeDB (embedded, document path)",
    "arcadedb_ts_doc_server": "ArcadeDB (server, document path)",
    "arcadedb_ts_native_server": "ArcadeDB (server, native time series)",
    "questdb":            "questdb",
    "sqlite":             "sqlite",
    "mongodb":            "mongodb",
    "timescaledb":        "timescaledb",
    "duckdb":             "duckdb",
}


def _l4_canonical(all_rows):
    """Frozen l4 rows, grouped by display label, or None when the lane is absent.

    PREFERRED OVER THE LEGACY FILES, and the reason is a published number that
    was wrong. _l4_rows() read results/l4_tsbs.jsonl (every ts_utc 2026-08-08,
    engine 26.8.1, engine_commit null) plus the ts_2681 native probe (2026-08-06).
    Against those, published QuestDB ingest is 432,375 pts/s where the pinned
    lane measures 1,305,766 -- so the page read as a 4.3x ArcadeDB ingest lead
    where the corrected rows give 1.41x. The lane also promoted ArcadeNativeTS
    into itself (l4_tsbs.py:113-132), so the bespoke probe is no longer the only
    source of the native arm and need not be read at all.

    Returns None rather than an empty dict when there are no l4 rows, so the
    caller falls back instead of rendering an empty table.
    """
    grouped = defaultdict(list)
    for r in all_rows:
        if r.get("lane") != "l4":
            continue
        label = L4_CANON_LABELS.get(r.get("backend"))
        if label:
            grouped[label].append(r)
    return grouped or None


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
            out["ArcadeDB (embedded, native time series)"].append(d)

    if L4_FILE.exists():
        for line in L4_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            backend = r.get("backend")
            label = ("ArcadeDB (embedded, document path)" if backend == "arcadedb"
                     else str(backend))
            out[label].append(r)

    return out


# (overlay filename arm, runner backend key, display label)
# Optional arms: shown when their files exist, never required for the pinned
# directory to count as complete (the fp32 served arm was added 2026-09-07).
SPARSE_MP_OPTIONAL_ARMS = [
    ("arc_srv_fp32", "arcadedb_sparse_server_fp32", "ArcadeDB (server, fp32)"),
    ("pgvector", "pgvector_sparse", "pgvector"),   # 2026-09-11, files land with qDK
]
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
    root = _pinned_dir("sparse_mp", expected=[
        f"sp_{arm}_{tier}.json"
        for tier in ("medium", "small") for arm, _b, _l in SPARSE_MP_ARMS])
    if not root.is_dir():
        return None
    entries = []
    # 100k joined the second-pass run on 2026-09-11 (qDP); its files are
    # optional so the table renders before they land, and the sparse
    # condition says whether 100k has a second pass by looking, not by text.
    for tier in ("medium", "small", "tiny"):
        for arm, backend, label in SPARSE_MP_ARMS + SPARSE_MP_OPTIONAL_ARMS:
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
            _bs = _num(cold[0].get("build_s")); _nd = _num(cold[0].get("n_docs"))
            c99 = cold[0].get("query_p99_ms")
            w99 = statistics.median(r["query_p99_ms"] for r in warm if r.get("query_p99_ms") is not None) if any(r.get("query_p99_ms") is not None for r in warm) else None
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
                "version_name": _engine_version(label, _row_engine_string(cold[0]) or _campaign_engine_string(backend),
                                                commit=_overlay_commit()),
                "host": "mini",
                "metrics": {
                    "cold p50 ms": {"median": round(c, 3), "min": round(c, 3),
                                    "max": round(c, 3), "n": 1},
                    "warm p50 ms": {"median": round(w, 3), "min": round(w, 3),
                                    "max": round(w, 3), "n": len(warm)},
                    **({"cold p99 ms": {"median": round(c99, 3), "min": round(c99, 3), "max": round(c99, 3), "n": 1}} if c99 is not None else {}),
                    **({"warm p99 ms": {"median": round(w99, 3), "min": round(w99, 3), "max": round(w99, 3), "n": len(warm)}} if w99 is not None else {}),
                    "gain": {"median": round(c / w, 2), "min": round(c / w, 2),
                             "max": round(c / w, 2), "n": 1},
                    **({"ingest+index vectors/s": {"median": round(_nd / _bs, 1), "min": round(_nd / _bs, 1), "max": round(_nd / _bs, 1), "n": 1},
                        "ingest+index total s": {"median": round(_bs, 2), "min": round(_bs, 2), "max": round(_bs, 2), "n": 1}}
                       if (_bs and _nd) else {}),
                    **({"peak memory GiB": _campaign_stat(backend, tier, "peak_anon_mib_sum") or _agg(cold, "peak_anon_mib_sum")}
                       if (_campaign_stat(backend, tier, "peak_anon_mib_sum") or _agg(cold, "peak_anon_mib_sum")) else {}),
                    **({"disk GiB": _campaign_stat(backend, tier, "disk_data_mb")}
                       if _campaign_stat(backend, tier, "disk_data_mb") else {}),
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
            "from that one would compare two different protocols.",
            "The order is the same cold and warm at both sizes. The dense table "
            "further down is not like this: there ArcadeDB alone gains about "
            "nine times on a second pass, so which pass you time decides the "
            "ranking, and it has to say which.",
        ],
        "columns": ["cold p50 ms", "cold p99 ms", "warm p50 ms", "warm p99 ms", "gain"],
        "withheld_scales": [],
        "withheld_reason": None,
        "source_paths": ["benchmarks/experiments/results/sparse_mp"],
        "source_urls": [f"{REPO}/benchmarks/experiments/results/sparse_mp"],
        "entries": entries,
    }


# ---------------------------------------------------------------- lifecycle
# PAGE-SPEC section 2: "cold-start decomposition (4 columns), then per scenario:
# open ms, action ms, close ms, session ms". The SESSION is what the page quotes,
# because open and close alone hide a rebuild triggered BETWEEN them: an earlier
# version of this lane reported ~5 ms open and ~300 ms close for a session that
# actually cost 4.3 s.
LIFECYCLE_SCENARIOS = [
    ("clean", "reopen, touch nothing, close"),
    ("read", "reopen, one query, close"),
    ("write", "reopen, commit one row into a scratch type, close"),
    ("write_own", "reopen, commit into the structure's OWN data, close"),
    ("write_own_read", "write then read in one session"),
]
# Reader-facing names for the page (2026-09-11): the harness keys above stay
# in the rows and the source CSV, the page says what the session did.
LIFECYCLE_SCENARIO_LABELS = {
    "clean": "open and close ms",
    "read": "one query ms",
    "write_own": "one write ms",
    "write_own_read": "write, then query ms",
}
# The scratch-type write ("write": commit one row into a type no situation
# owns) was the control for "what does committing anything cost"; on the
# page it sat beside the real write and read as two writes. It stays in the
# rows and the CSV, not in the columns (2026-09-12, DECISIONS #73).
LIFECYCLE_PAGE_SCENARIOS = [k for k, _ in LIFECYCLE_SCENARIOS if k in LIFECYCLE_SCENARIO_LABELS]
LIFECYCLE_SITUATION_LABELS = {
    "empty": "Empty database", "doc": "Documents", "doc_idx10": "Documents, ten indexes",
    "graph": "Graph", "graph_gav": "Graph with the analytical view", "vector": "Dense vectors",
    "sparse": "Sparse vectors", "ts": "Time series",
}

# Situations whose probe is not yet trustworthy. graph_gav's read reaches the
# view now (it is issued in cypher; SQL cannot reach a Graph Analytical View at
# all) but the same edit changed its SCOPE from 100 seeds to an unbounded
# whole-graph 2-hop, so its numbers describe the query written rather than the
# view. Withheld rather than published with a caveat nobody reads.
LIFECYCLE_WITHHELD = {"graph_gav": "probe scope under revision; see PAGE-SPEC 4c"}


def _lc_vector_note(rows):
    """The disclosure sentence for the vector situation, with its numbers
    computed from the rows it describes (they were typed until 2026-09-08;
    10M then arrived and the sentence still said 1M was the top)."""
    def med(scale, field):
        vals = [_num(r.get(field)) for r in rows
                if r.get("workload") == "vector" and r.get("scale") == scale
                and not str(r.get("backend", "")).endswith("_server") and _num(r.get(field)) is not None]
        return statistics.median(vals) if vals else None
    parts = []
    for scale, label in (("lc10k", "10k"), ("lc1m", "1M"), ("lc10m", "10M")):
        v = med(scale, "clean_session_ms")
        if v is not None:
            parts.append(f"{v / 1000:.1f} s at {label}" if v >= 1000 else f"{v:.0f} ms at {label}")
    rd = med("lc10m", "read_session_ms")
    tail = (f", and a session with one search in it at 10M is {rd / 1000:.1f} s" if rd else "")
    return ("Known at this engine build: a vector database's no-op session close grows with the index ("
            + ", ".join(parts) + ")" + tail
            + ", because the first search after a write started a full asynchronous graph rebuild and close() waited on it. "
            "Filed as #7183, fixed upstream in #7191 for 26.10.1; the October re-pin re-measures it.")


def _lifecycle_table(all_rows):
    """Built from the FROZEN CSV, like every other table in this file.

    The first version called load_canonical(), which is make_paper_tables' name
    and does not exist here: this module reads results/runs_paper.csv, which that
    script generates. It compiled, and the check I ran monkey-patched
    load_canonical INTO the module, so the test supplied the very name that was
    missing and proved nothing.
    """
    rows = [r for r in all_rows if r.get("lane") == "lifecycle"]
    if not rows:
        return None

    by = {}
    for r in rows:
        _srv = str(r.get("backend", "")).endswith("_server")   # served twin, 2026-09-07
        by.setdefault((r.get("workload"), r.get("scale"), _srv), []).append(r)

    entries = []
    for (situation, scale, _srv), rs in sorted(by.items()):
        if situation in LIFECYCLE_WITHHELD:
            continue
        _name = LIFECYCLE_SITUATION_LABELS.get(situation, situation)
        entry = {
            "backend": f"{_name} (server)" if _srv else f"{_name} (embedded)",
            "is_arcadedb": True,
            "scale": scale,
            "scale_label": scale_label("lifecycle", scale),
            "workload": "session",
            "n_docs": str(rs[0].get("n_rows") or ""),
            "deployment": "server" if _srv else "embedded",
            "image": rs[0].get("image"),
            "version_name": _engine_identity(rs[0].get("engine_version"),
                                             rs[0].get("engine_commit")),
            "host": rs[0].get("host"),
            "metrics": {},
        }
        # The four cold-start columns, which the page must print beside any
        # session number: a 5 ms open inside a process that took half a second to
        # reach its first database call is not a 5 ms cost to anyone launching a
        # CLI.
        for field, label in (("jvm_start_ms", "JVM start ms"),
                             ("first_open_ms", "first open ms"),
                             ("cold_process_ms", "cold process ms")):
            got = _agg(rs, field)
            if got is not None:
                entry["metrics"][label] = got
        for key in LIFECYCLE_PAGE_SCENARIOS:
            got = _agg(rs, f"{key}_session_ms")
            if got is not None:
                entry["metrics"][LIFECYCLE_SCENARIO_LABELS[key]] = got
        # The rows carried peak memory and disk from the start; the page
        # never read them here (2026-09-10). Disk is SERVER ROWS ONLY: the
        # embedded database lives on a host bind mount (/lcdb) so its page
        # cache can be evicted for the cold columns, and the disk reading
        # (writable layer plus volumes) does not see a bind mount. Every
        # embedded row read 0.0 GiB beside a 5.6 GiB server twin at 10M
        # (2026-09-11); a blind spot is a blank, not a zero.
        # No disk column on this table (2026-09-13, user): a session-cost
        # table is not about footprint, and the embedded rows could not carry
        # it anyway (bind mount, see the comment above).
        for field, label in (("peak_anon_mib_sum", "peak memory GiB"),):
            got = _agg(rs, field)
            if got is not None:
                entry["metrics"][label] = got
        if entry["metrics"]:
            entries.append(entry)

    if not entries:
        return None
    return {
        "id": "lifecycle",
        "title": "Session cost, open to close",
        "dataset": "synthetic, one structure per row",
        "conditions": [
            "The SESSION is open + action + close. Reporting open and close alone "
            "hides work triggered between them.",
            "Cold start is measured in a fresh subprocess and reported beside every "
            "session number, because a millisecond open inside a process that takes "
            "half a second to reach its first database call is not a millisecond to "
            "whoever launched it.",
            _lc_vector_note(rows),
            "A clean close should be O(what was written), not O(what is stored): "
            "write nothing and closing should cost the same at 10k documents and 10M.",
            "Server rows have no JVM start, first open, or cold process: the server is "
            "already running when the probe connects, so those three columns describe "
            "the embedded process only. The session columns are measured for both.",
        ] + [f"{LIFECYCLE_SITUATION_LABELS.get(k, k)} is withheld: {v}" for k, v in sorted(LIFECYCLE_WITHHELD.items())],
        "columns": ["JVM start ms", "first open ms", "cold process ms"]
                   + [LIFECYCLE_SCENARIO_LABELS[k] for k in LIFECYCLE_PAGE_SCENARIOS],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
        "source_paths": ["benchmarks/experiments/results/runs_paper.csv"],
        "source_urls": ["https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/results/runs_paper.csv"],
        "source_path": "benchmarks/experiments/results/runs_paper.csv",
        "source_url": "https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/results/runs_paper.csv",
    }


def _l4_table(all_rows):
    # Canonical first; the 2026-08 files are the fallback, not the source.
    grouped = _l4_canonical(all_rows)
    if not grouped:
        raise SystemExit("no canonical l4 rows at the pin; the legacy l4_tsbs.jsonl/ts_2681 readers were retired 2026-09-08")
    if not grouped:
        return None

    order = ["ArcadeDB (embedded, native time series)", "ArcadeDB (embedded, document path)",
             "questdb", "duckdb", "sqlite", "mongodb", "timescaledb"]
    # This lane predates runner.BACKENDS and keeps its own adapters, so the
    # topology lookup does not reach it. QuestDB is a server (ILP ingest on
    # 9009, SQL over pg-wire, see l4_tsbs.py); the other two run in-process.
    L4_DEPLOYMENT = {"ArcadeDB (embedded, native time series)": "embedded",
                     "ArcadeDB (server, document path)": "server",
                     "ArcadeDB (server, native time series)": "server",
                     "ArcadeDB (embedded, document path)": "embedded",
                     "questdb": "server", "duckdb": "embedded", "sqlite": "embedded", "mongodb": "server", "timescaledb": "server"}
    entries = []
    for label in sorted(grouped, key=lambda k: (order.index(k) if k in order else 99, k)):
        rs = grouped[label]
        entry = {
            "backend": display_name(label) if label in DISPLAY_NAMES else label,
            # case-insensitive: the labels read "ArcadeDB (...)" since
            # 2026-09-11 and the lowercase test unshaded all four rows for a day
            "is_arcadedb": "arcadedb" in label.lower(),
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
                label, rs[0].get("backend_version") or rs[0].get("engine_version"),
                commit=rs[0].get("engine_commit")),
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
            "No engine settles inside the ingest timer. QuestDB's WAL apply runs after the clock stops, "
            "and the newest-reading query is asked unbounded on every engine, so the unsealed tail a scan "
            "walks costs the same everywhere. Sealing the write buffer makes the aggregation faster and the "
            "last-point query slower, and settling only ours would have been a one-sided advantage."
            + ("" if symmetric else " Rows that record a settle time did that settling after the timer stopped."),
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
# A re-measure at a pin lands beside the tracked file, named by the commit,
# so the bench host's tree stays clean (a modified tracked file aborts every
# queue script's git pull). The pinned file wins when it exists.
if os.environ.get("BENCH_ENGINE_COMMIT", "").strip():
    _ov_pin = OVERHEAD.with_name(f"mini_results_{os.environ['BENCH_ENGINE_COMMIT'].strip()}.csv")
    if _ov_pin.exists():
        OVERHEAD = _ov_pin
PYB_FROZEN = PYB / "results" / "runs_paper.csv"


def _overhead_provenance() -> dict:
    """The PROVENANCE line bench_python/bench_round5 print (run_conditions as
    JSON), if the results file carries one. The 2026-08-10 file does not."""
    if not OVERHEAD.exists():
        return {}
    for line in OVERHEAD.read_text(encoding="utf-8", errors="replace").splitlines():
        if "PROVENANCE," in line:
            try:
                return json.loads(line.split("PROVENANCE,", 1)[1])
            except Exception:
                return {}
    return {}


def _overhead_medians():
    """(workload, arm) -> median microseconds, from the mini re-measure."""
    if not OVERHEAD.exists():
        return {}
    out = defaultdict(list)
    with OVERHEAD.open() as fh:
        for row in csv.reader(fh):
            if len(row) < 8:
                continue
            # Parse BEFORE touching the defaultdict: a PROVENANCE line split by
            # the csv reader reaches here with len >= 8, and `out[k].append(
            # float(...))` created key k and then raised, leaving an empty list
            # that statistics.median refused (2026-09-07, first pinned file).
            try:
                # Column 7 is p50. Column 6 is the MEAN, and the page printed
                # it as a median from 2026-09-07 to 2026-09-11 under a global
                # condition that says every cell is a median (PAGE-PLAN S9).
                val = float(row[7])
            except ValueError:
                continue
            if row[2] != "RESULT":
                continue
            out[(row[3], row[4])].append(val)
    _overhead_medians.counts = {k: len(v) for k, v in out.items()}
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
    _prov = _overhead_provenance()
    _ident = _engine_identity(_prov.get("engine_version"), _prov.get("engine_commit")) if _prov else None

    def us(w, a):
        return m.get((w, a))

    rows_out = []

    _counts = getattr(_overhead_medians, "counts", {})

    def add(label, workload, value_us, baseline_us, note, arm=None):
        if value_us is None or baseline_us is None:
            return
        # n is the number of runs behind the median (5 at the pin, 3-5 in the
        # 2026-08-10 file); it was the literal 1 until 2026-09-07.
        _n = _counts.get((workload_key(workload), arm), 1) if arm else 1
        rows_out.append({
            "backend": label,
            "is_arcadedb": True,
            "scale": workload,
            "workload": note,
            "n_docs": None,
            "deployment": "embedded",
            "image": None,
            "version_name": _ident,
            "host": _prov.get("host") if _prov else None,
            "metrics": {
                "time ms": {"median": round(value_us / 1000, 3), "min": round(value_us / 1000, 3),
                            "max": round(value_us / 1000, 3), "n": _n},
                "vs Java": {"median": round(value_us / baseline_us, 2),
                            "min": round(value_us / baseline_us, 2),
                            "max": round(value_us / baseline_us, 2), "n": _n},
            },
        })

    def workload_key(w):
        return "vector" if w == "vector search" else "query"
    jv, jq = us("vector", "J-direct"), us("query", "J-allcols-100000")
    add("Java, in process", "vector search", jv, jv, "baseline", "J-direct")
    add("Python", "vector search", us("vector", "P-raw-call"), jv, "same call", "P-raw-call")
    add("Java, in process", "100k-document scan", jq, jq, "baseline", "J-allcols-100000")
    add("Python, to_columns", "100k-document scan", us("query", "P-columns-100000"), jq, "columnar", "P-columns-100000")
    add("Python, to_json_list", "100k-document scan", us("query", "P-jsonbatch-100000"), jq, "batched JSON", "P-jsonbatch-100000")
    add("Python, to_list", "100k-document scan", us("query", "P-tolist-100000"), jq, "record objects", "P-tolist-100000")

    if not rows_out:
        return None
    return {
        "id": "pycost",
        "title": "What Python costs",
        "dataset": "Same engine, same query, called from Java and from Python",
        # THE RATIOS IN THESE SENTENCES ARE COMPUTED, not typed: 1.28x, 1.63x and
        # 13.8x sat here as literals from the 2026-08-10 measurement while the
        # table below them was regenerated from the data, and page_check's
        # prose gate reads arcadedb.ts, not this file.
        "conditions": [
            *([("This table's artifact carries no engine identity (it predates "
                "the provenance stamp); the re-measure at the engine commit the "
                "rest of the page reports is queued and this line goes away with it.")]
              if not _ident else []),
            "The engine itself runs at the same speed either way. What Python "
            "is charged for is moving results across the boundary, which is why "
            f"the vector search costs {us('vector', 'P-raw-call') / jv:.2f}x and the scan "
            f"{us('query', 'P-columns-100000') / jq:.2f}x rather than "
            "anything scaling with the work the engine did.",
            "The path you choose inside Python matters far more than the "
            "language boundary does. Asking for record objects is "
            f"{us('query', 'P-tolist-100000') / us('query', 'P-columns-100000'):.1f}x slower "
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


# One row order for every table, applied last so no builder has to remember
# it. The reader asked for it on 2026-09-09: l3smp appended the served fp32
# arm after the comparators, l3d listed fp32 before int8 at 10M and Qdrant
# before Chroma, lifecycle sorted lc100k before lc10k as strings.
#
# Within a tier: our engine first, then the comparators alphabetically. Within
# an engine: embedded before server, int8 before fp32. The sort is stable, so
# rows a builder already ordered deliberately (plain before GAV, native before
# document, lifecycle situations) keep that order inside each group.
SCALE_ORDER = ["tiny", "small", "medium", "large", "deep10m",
               "sf1", "sf10", "tpch1", "tpch10",
               "lc10k", "lc100k", "lc1m", "lc10m"]
DEPLOYMENT_ORDER = {"embedded": 0, "server": 1}
PRECISION_ORDER = {"int8": 0, "fp32": 1}


# The ingest path per engine and deployment, said under every table that
# prints an ingest pair. Embedded goes through the Python package or the Java
# API; served goes through HTTP with statements as text. Read from the lane
# scripts, not from memory (2026-09-11).
INGEST_NOTES = {
    "l1": ("Ingest paths: ArcadeDB embedded sends batches of 500 INSERT statements as one "
           "sqlscript per transaction through the Python package; ArcadeDB served sends the "
           "same batches to the HTTP command endpoint; PostgreSQL uses COPY FROM STDIN; DuckDB "
           "inserts 5,000-row DataFrames with INSERT INTO ... SELECT. The ArcadeDB indexes exist "
           "before its load; PostgreSQL's and DuckDB's are created after theirs."),
    "l1tpc": ("Ingest paths: ArcadeDB embedded loads through the Python package's insert_many in "
              "10,000-row batches, one JSON payload per batch; served sends INSERT statements as "
              "sqlscript batches over HTTP; PostgreSQL COPY FROM STDIN; DuckDB CREATE TABLE AS "
              "SELECT from in-memory frames."),
    "l2": ("Ingest paths: ArcadeDB embedded loads through the Java API (newVertex, newEdge) in "
           "5,000-record transactions; served sends CREATE VERTEX and CREATE EDGE statements as "
           "sqlscript batches over HTTP; Neo4j UNWIND batches over bolt; LadybugDB COPY from CSV, "
           "its native bulk path."),
    "e2": ("ingest+index total s is one timer around loading the vertices and edges and creating the vector index. Ingest paths: ArcadeDB embedded loads with the Python package's graph_batch (5,000 "
           "records per commit, vertices then edges) and then CREATE INDEX ... LSM_VECTOR; served "
           "sends CREATE VERTEX and CREATE EDGE batches as sqlscript over HTTP, then the same CREATE "
           "INDEX; SurrealDB inserts through its Python client into an in-memory database; the "
           "composed stack upserts vectors into Qdrant and loads the graph into Neo4j with UNWIND."),
    "l4": ("Ingest paths: the ArcadeDB document path issues INSERT per point through the Python "
           "package (embedded) or sqlscript batches over HTTP (served); the native TIMESERIES type "
           "takes columns through the async executor's append_samples (embedded) or InfluxDB line "
           "protocol at /api/v1/ts/{db}/write (served); DuckDB inserts an Arrow table; QuestDB takes "
           "line protocol over TCP."),
    "l3d": ("Ingest paths: ArcadeDB embedded issues INSERT per vector in 10,000-row transactions "
            "through the Python package, then CREATE INDEX ... LSM_VECTOR; served sends 500-statement "
            "sqlscript batches over HTTP with each vector spelled out as text, then the same CREATE "
            "INDEX; Chroma add() in batches of 5,000; LanceDB an Arrow table then create_index; Qdrant "
            "and Milvus upsert in batches; DuckDB VSS and sqlite-vec executemany."),
    "l3s": ("Ingest paths: ArcadeDB embedded loads through the Java API (newDocument with int and "
            "float arrays) in 500-record transactions, then COMPACT INDEX; served sends INSERT "
            "statements as sqlscript batches over HTTP; Qdrant, Milvus, and Elasticsearch upsert or "
            "bulk-index in batches, then settle (Elasticsearch refresh and force-merge, Milvus flush "
            "and load)."),
}
INGEST_NOTES["l2olap"] = INGEST_NOTES["l2"]
INGEST_NOTES["l3smp"] = INGEST_NOTES["l3s"]


# Which lane and workload each page table shows, for the censored-cell note.
_TABLE_LANE = {
    "docs_oltp": ("l1tpc", "oltp"), "docs_olap": ("l1tpc", "olap"),
    "l2": ("l2", "oltp"), "l2olap": ("l2", "olap"),
    "l3d": ("l3d", None), "l3s": ("l3s", None), "l4": ("l4", None),
    "e2": ("e2", "hybrid"), "e2atom": ("e2", "atomicity"),
}
_CENSORED_CACHE = None


def _censored_cells():
    """Cells at the pin whose every attempt ended in a timeout: (lane, scale,
    backend, workload) -> budget seconds. A timeout is a censored observation
    (the engine needed more than the budget every arm got), recorded once by
    the probe rule and never retried bigger; the table says so instead of
    leaving a gap a reader cannot tell from an unmeasured cell (2026-09-13)."""
    global _CENSORED_CACHE
    if _CENSORED_CACHE is not None:
        return _CENSORED_CACHE
    pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    timeouts, clean = {}, set()
    path = HERE / "results" / "runs.jsonl"
    if path.exists():
        with open(path) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if str(r.get("ts_utc", "")) < "2026-09-01":
                    continue
                key = (r.get("lane"), str(r.get("scale")), r.get("backend"), r.get("workload"))
                err = str(r.get("error") or "")
                if not err:
                    clean.add(key)
                elif err.startswith("timeout_after_"):
                    try:
                        timeouts[key] = int(err.split("_")[-1].rstrip("s"))
                    except ValueError:
                        timeouts[key] = None
    _CENSORED_CACHE = {k: v for k, v in timeouts.items() if k not in clean}
    return _CENSORED_CACHE


def _censored_notes(table_id):
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    lane, wl = lane_wl
    notes = []
    for (l, scale, backend, w), secs in sorted(_censored_cells().items(), key=str):
        if l != lane or (wl and w != wl):
            continue
        budget = f"{secs / 3600:g} hour" if secs else "its"
        what = {"oltp": "transaction", "olap": "analytics", "hybrid": "transaction",
                "atomicity": "atomicity", "search": "search", "ingest": "ingest"}.get(w, w or "the")
        notes.append(f"{display_name(backend)} at {scale_label(lane, scale)}: the {what} cell exceeded "
                     f"its {budget} budget, the same budget every engine on this table had, on its first "
                     f"attempt and was not retried; there is no row.")
    return notes


def _counts_note(table_id, entries):
    """How many operations stand behind one cell, read from the lane's own
    constants and the rows (user, 2026-09-13: the page said n=5 but not what
    each repetition ran). Never typed here: the numbers come from the lane
    modules the runner executes, so a change there changes the sentence."""
    try:
        import importlib
        L = {n: importlib.import_module(n) for n in ("l1_tpc", "graph_common", "l3d_dense", "l4_tsbs", "e2_hybrid")}
    except Exception:  # noqa: BLE001
        return []
    scales = sorted({str(e.get("scale")) for e in entries})
    if table_id == "docs_oltp":
        return [f"Each repetition runs {L['l1_tpc'].OLTP_OPS:,} new-order transactions; the p50 and p99 are over those, and OLTP ops/s is their rate."]
    if table_id == "docs_olap":
        return [f"Each repetition runs every query {L['l1_tpc'].OLAP_ITER} times; the p50 and p99 are over those runs."]
    if table_id == "l2":
        q = {sc: L["graph_common"].SCALE_OLTP_QUERIES.get(sc) for sc in scales}
        try:
            import ldbc_snb
            q = {sc: (q[sc] or getattr(ldbc_snb, "SCALE_OLTP_QUERIES", {}).get(sc)) for sc in scales}
        except Exception:  # noqa: BLE001
            pass
        parts = ", ".join(f"{scale_label('l2', sc)}: {n:,}" for sc, n in q.items() if n)
        return [f"Each repetition runs every read against a fresh set of start persons ({parts}) and commits up to 1,000 writes; the p50 and p99 are over those."] if parts else []
    if table_id == "l2olap":
        return [f"Each repetition runs every query {L['graph_common'].OLAP_ITERATIONS} times; the p50 and p99 are over those runs."]
    if table_id in ("l3d", "l3s"):
        return [f"Each pass answers {L['l3d_dense'].N_QUERIES:,} queries; cold is the first pass after the build and warm pools the four passes after it, over five builds."]
    if table_id == "l4":
        return [f"Each repetition runs every query {L['l4_tsbs'].QITER} times; the p50 and p99 are over those runs."]
    if table_id == "e2":
        return [f"Each repetition runs the transaction {L['e2_hybrid'].OPS} times; the p50 and p99 are over those."]
    return []


def _finish_table(table: dict) -> dict:
    table["conditions"] = list(table.get("conditions") or []) + _counts_note(table.get("id"), table.get("entries", [])) + _censored_notes(table.get("id"))
    entries = table["entries"]
    seen = []
    for e in entries:
        if e.get("scale") not in seen:
            seen.append(e.get("scale"))

    def scale_rank(e):
        sc = e.get("scale")
        return (SCALE_ORDER.index(sc) if sc in SCALE_ORDER
                else len(SCALE_ORDER) + seen.index(sc))

    def key(e):
        base = re.sub(r"\s*\(.*$", "", str(e["backend"])).lower()
        return (scale_rank(e), 0 if e.get("is_arcadedb") else 1, base,
                DEPLOYMENT_ORDER.get(e.get("deployment"), 2),
                PRECISION_ORDER.get(e.get("precision"), 2))
    table["entries"] = sorted(entries, key=key)
    # Every metric a row carries is a column the page shows. l3smp carried
    # peak memory and disk in its rows and listed neither, so the page showed
    # neither (the renderer trusts `columns`).
    cols = list(table["columns"])
    extra = []
    for e in table["entries"]:
        for m in e.get("metrics", {}):
            if m not in cols and m not in extra:
                extra.append(m)
    tail = [m for m in ("peak memory GiB", "disk GiB") if m in extra]
    cols = cols + [m for m in extra if m not in tail] + tail
    # ONE ORDER FOR EVERY TABLE (2026-09-11): the workload's own columns in
    # the order its spec lists them, then recall, then the ingest pair (rate,
    # then total), then peak memory, then disk. Tables used to put ingest
    # wherever the spec happened to list it.
    def _rank(c):
        if c == "recall@10":
            return 1
        if c.startswith("ingest"):
            return 2 if "/s" in c else 3
        if c == "peak memory GiB":
            return 4
        if c == "disk GiB":
            return 5
        return 0
    cols = sorted(cols, key=lambda c: (_rank(c), cols.index(c)))
    # And no column without a value in any row: a metric a lane records only
    # since a given date would otherwise print a column of dashes until the
    # re-run lands (the analytical p99s, 2026-09-10).
    present = {m for e in table["entries"] for m, v in e.get("metrics", {}).items() if v is not None}
    table["columns"] = [c for c in cols if c in present]
    note = INGEST_NOTES.get(table["id"])
    if note and any("ingest" in c for c in table["columns"]) and note not in table.get("conditions", []):
        table["conditions"] = list(table.get("conditions", [])) + [note]
    # Which way is better, per column, so the header can say it (2026-09-11).
    # Rates, throughput, recall, and gain go up; times and footprints go down;
    # plain counts (trials, crashes raised) have no direction.
    dirs = {}
    for c in table["columns"]:
        if c in ("trials", "crashes raised"):
            continue
        if "/s" in c or c in ("recall@10", "gain"):
            dirs[c] = "up"
        elif c.endswith(" ms") or c.endswith(" s") or c.endswith(" GiB") or c in ("torn results", "vs Java"):
            dirs[c] = "down"
    table["directions"] = dirs
    return table


# The host's hardware, typed once per host name and attached to the payload
# for every host the rows name; a row from an unknown host stops the export
# rather than publishing numbers with no machine behind them.
HOST_HARDWARE = {
    "mini": {
        "cpu": "Intel Core i9-12900HK, 14 cores (6 performance, 8 efficient), 20 threads, 24 MiB L3",
        "memory": "64 GiB",
        "storage": "Samsung 980 PRO 2 TB NVMe",
        "os": "Ubuntu 26.04 LTS, Linux 7.0, Docker 29",
    },
}


# The machine every published row ran on. Typed once, like the "mini" the
# overlay entries carry, because no lane stamps the host into its rows yet
# (they stamp the container id; BENCH_HOST is exported by every queue script
# and never recorded). October: record BENCH_HOST in every row and derive
# this from the rows instead.
PAGE_HOST = "mini"


def _host_hardware(hosts):
    named = sorted({h for h in hosts if h and not str(h).startswith("container:")} | {PAGE_HOST})
    missing = [h for h in named if h not in HOST_HARDWARE]
    if missing:
        raise SystemExit(f"rows name a host with no HOST_HARDWARE entry: {missing}")
    return {h: HOST_HARDWARE[h] for h in named}


def _restructure_tables(tables, rows):
    """Page-level reshaping that no single lane can do (2026-09-11):

    - the sparse second-pass table folds into the sparse search table as warm
      columns, the way the dense table already shows both passes;
    - the three document tables (synthetic orders, its five queries, TPC)
      become two, by workload: transactions and analytics, with the dataset in
      the Size column, the way the graph section is split.
    The tables that fed them are retired (page_check.RETIRED_TABLES)."""
    by = {t["id"]: t for t in tables}
    if "l3s" in by and "l3smp" in by:
        mp = {(e["backend"], e["scale"]): e for e in by["l3smp"]["entries"]}
        for e in by["l3s"]["entries"]:
            m = e["metrics"]
            if "p50 ms" in m:
                m["cold p50 ms"] = m.pop("p50 ms")
            if "p99 ms" in m:
                m["cold p99 ms"] = m.pop("p99 ms")
            src = mp.get((e["backend"], e["scale"]))
            if src:
                for k in ("warm p50 ms", "warm p99 ms", "gain"):
                    if k in src["metrics"]:
                        m[k] = src["metrics"][k]
        t = by["l3s"]
        t["columns"] = (["cold p50 ms", "cold p99 ms", "warm p50 ms", "warm p99 ms", "gain"]
                        + [c for c in t["columns"] if c not in ("p50 ms", "p99 ms")])
        t["conditions"] = list(t["conditions"]) + [
            "Cold p50 and p99 are the first timed pass after the build, median of five builds. "
            "Warm and gain come from a separate run of the same arms: one build per engine, then "
            "five more passes over a different half of the query set, so a warm number cannot be "
            "explained by the engine having already answered that exact query; gain is that run's "
            "cold over its warm."
            + ("" if any(e.get("scale") == "tiny" for e in by["l3smp"].get("entries", [])) else " 100k has no second-pass run yet."),
        ]
        t["source_paths"] = list(t.get("source_paths") or []) + list(by["l3smp"].get("source_paths") or [])
        t["source_urls"] = list(t.get("source_urls") or []) + list(by["l3smp"].get("source_urls") or [])
        tables.remove(by["l3smp"])
    if all(k in by for k in ("l1", "l1olap", "l1tpc")):
        # THE PAGE SHOWS THE STANDARD DOCUMENT BENCHMARKS ONLY (2026-09-11).
        # The synthetic 20M-order workload and TPC measure different things
        # (reads/inserts/updates against a new-order transaction; five bespoke
        # aggregates against Q1/Q6), so one table per workload holding both
        # was half blank. TPC-C is the transactions table, TPC-H the
        # analytics table; the synthetic set stays in the paper and the
        # harness.
        def clone(e, keep):
            n = dict(e)
            n["metrics"] = {k: v for k, v in e["metrics"].items() if k in keep}
            return n
        OLTP_KEEP = {"new-order p50 ms", "new-order p99 ms", "OLTP ops/s",
                     "ingest documents/s", "ingest total s", "peak memory GiB", "disk GiB"}
        OLAP_KEEP = {"Q1 p50 ms", "Q1 p99 ms", "Q6 p50 ms", "Q6 p99 ms",
                     "ingest documents/s", "ingest total s", "peak memory GiB", "disk GiB"}
        src = by["l1tpc"]
        # The tuned PostgreSQL arm answered its question (image defaults do
        # not distort the comparison: 2.33 vs 2.39 ms new-order, 337 vs 331 ms
        # Q1) and stays in the rows; on the page it read as a second engine
        # (user, 2026-09-13, DECISIONS #76).
        src = dict(src, entries=[e for e in src["entries"] if e["backend"] != "PostgreSQL (tuned)"])
        base = {"withheld_scales": [], "withheld_reason": None,
                "source_paths": src.get("source_paths"), "source_urls": src.get("source_urls")}
        tables.append({"id": "docs_oltp", "title": "Document OLTP",
                       "dataset": "TPC-C new-order on the TPC-H SF1 tables",
                       "conditions": list(src["conditions"]),
                       "columns": ["new-order p50 ms", "new-order p99 ms", "OLTP ops/s"],
                       "entries": [clone(e, OLTP_KEEP) for e in src["entries"]], **base})
        tables.append({"id": "docs_olap", "title": "Document OLAP",
                       "dataset": "TPC-H Q1 and Q6 at SF1",
                       "conditions": list(src["conditions"]),
                       "columns": ["Q1 p50 ms", "Q1 p99 ms", "Q6 p50 ms", "Q6 p99 ms"],
                       "entries": [clone(e, OLAP_KEEP) for e in src["entries"]], **base})
        for i in ("l1", "l1olap", "l1tpc"):
            tables.remove(by[i])
    return tables


def main() -> int:
    if not FROZEN.exists():
        print(f"missing {FROZEN}; run make_paper_tables.py first", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(FROZEN.open()))
    # F39: rows frozen before 2026-09-13 stamp the SurrealDB SDK version as the
    # embedded engine; the core is a function of the pinned wheel, resolved once.
    import surreal_common
    for _r in rows:
        if str(_r.get("engine_version") or "").startswith("surrealdb-embedded:"):
            _r["engine_version"] = surreal_common.legacy_stamp_fixup(_r["engine_version"])

    # WITHHELD: ArcadeDB rows whose engine_version identifies no build.
    #
    # Not rendered, and said out loud rather than dropped quietly. A number we
    # cannot attribute to a build cannot be re-derived or defended, and the page
    # is the artifact people cite. Comparator rows are untouched: this is a
    # claim about OUR engine's provenance, not theirs.
    _unusable = [r for r in rows
                 if str(r.get("backend", "")).startswith("arcadedb")
                 and not _engine_is_identifiable(_row_engine_string(r))]
    if _unusable:
        import collections as _c
        _by = _c.Counter((r.get("lane"), str(r.get("engine_version") or "(blank)")[:40])
                         for r in _unusable)
        print(f"  WITHHELD {len(_unusable)} ArcadeDB rows: engine_version identifies no build")
        for (lane, ev), n in sorted(_by.items()):
            print(f"    {lane:<10}{ev:<42}n={n}")
        print("    -> re-run these lanes at the pin; they are the cheap ones")
        rows = [r for r in rows if r not in _unusable]
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
            # Row-level, not group-level: merged lanes (l1, l1tpc) group both
            # workloads under one key with a blank label, so a group-level
            # test never matched and the per-query OLAP table was empty from
            # the day the merge landed until 2026-09-11 (BUGS F30).
            if spec.get("only_workload"):
                rs = [r for r in rs if r.get("workload") == spec["only_workload"]]
                if not rs:
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
            # A comparator row names the image it RAN on (server_image, a bare
            # digest). When the runner has since been re-pinned and the re-run
            # has not landed, the config's image is the wrong one: the Neo4j
            # graph rows measured on 5-community would have carried the
            # 2026.07.1 digest and name (publish rehearsal, 2026-09-11). Same
            # digest: keep the config's ref and its tag name. Different: the
            # row's digest on the config's repository, and the row's own
            # engine_version as the name.
            _row_digest = rs[0].get("server_image") if not str(backend).startswith("arcadedb") else None
            if _row_digest and "@" in str(_row_digest):   # some lanes record the full ref
                _row_digest = str(_row_digest).split("@", 1)[1]
            _stale_pin = bool(image and _row_digest and "@" in image and image.split("@")[1] != _row_digest)
            if _stale_pin:
                image = image.split("@")[0] + "@" + _row_digest
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
                # OUR served rows name the image that ran (the row's
                # server_image_ref, arcadedb-c25:<commit>), never the registry's
                # default string; the page carried arcadedata/arcadedb:26.8.1@sha256
                # on every served ArcadeDB row until 2026-09-08 (BUGS F16, the
                # field the label fix did not touch).
                "image": (rs[0].get("server_image_ref") or rs[0].get("server_image") or image)
                         if str(backend).startswith("arcadedb") else image,
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
                    rs[0].get("engine_version") if str(backend).startswith("arcadedb")
                    # A served comparator whose image has no entry in the pin
                    # table's names (Milvus) still stamps its server version
                    # on the row; the page showed Milvus unversioned for it.
                    else ((names.get(image) or rs[0].get("engine_version"))
                          if (image and not _stale_pin and not str(image).startswith("dbbench"))
                          else rs[0].get("engine_version")),
                    image, commit=rs[0].get("engine_commit")),
                "host": rs[0].get("host") or None,
                "metrics": {},
            }
            for field, label in spec["metrics"]:
                if field == "disk_data_mb" and backend in spec.get("in_memory", ()):
                    # An engine with no disk at all reads as a blank with the
                    # note below, not as 0.00 (SurrealDB at mem://).
                    continue
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
            # ALL-OR-NOTHING, and the canonical set wins once it is complete.
            #
            # The overlay was the matched set while the campaign had no ArcadeDB
            # at this tier: one driver, one protocol, every engine. But it is an
            # August artifact (dense_mp5_2681: engine 26.8.1, image None), so
            # while it wins, the pinned campaign cannot change the dense table at
            # all -- the longest job on the machine, 2-3 days of deep10m cells,
            # rendering not one number. That was invisible because the
            # replacement is unconditional.
            #
            # So: if the canonical rows carry ArcadeDB at deep10m, they ARE the
            # matched set and the overlay is dropped entirely. Otherwise the
            # overlay stands, unchanged. Never both -- mixing them is two engine
            # lines in one table (F5) on top of the double-measurement this
            # REPLACE was written to prevent (Qdrant at 1.295 and again at 1.342).
            #
            # 2026-09-07, REVERSED for the tier: the overlay wins whenever it
            # exists. The 8d6af9475 campaign put single-pass 10M rows in the
            # CSV with ArcadeDB in them, the rule above then dropped the
            # overlay, and the page showed one timed pass per build (cold
            # 8.434) while T5 showed the multipass rows (8.87): page_check
            # DIFFERed on every 10M cell. PAGE-SPEC: the page's 10M dense table
            # is T5's protocol, cold and warm from the multipass files. The
            # single-pass rows stay in the CSV for l3d_params and the ablation;
            # they are never this table. "Never both" still holds: it is all
            # overlay or, with no overlay on disk, all CSV.
            _mp = _dense_overlay_entries("deep10m")
            if _mp:
                entries = [e for e in entries if e["scale"] != "deep10m"]
                entries.extend(_mp)
            # The 1M size reads its own multipass overlay the same way, so the
            # warm column exists at both sizes and both read one protocol.
            # dense_mp_small_dir() refuses a partial directory; while the
            # overlay is absent (qDB not yet landed) the size stays on the
            # single-pass rows, cold only.
            _mps = _dense_overlay_entries("small")
            if _mps:
                entries = [e for e in entries if e["scale"] != "small"]
                entries.extend(_mps)
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
                            ["cold p50 ms", "cold p99 ms", "warm p50 ms",
                             "warm p99 ms", "recall@10", "ingest+index vectors/s",
                             "ingest+index total s", "peak memory GiB", "disk GiB"]),
                "withheld_scales": withheld,
                "withheld_reason": (
                    "Comparator rows exist at these sizes but ArcadeDB's were "
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
    for extra in (_sparse_multipass_table(), _l4_table(rows), _lifecycle_table(rows),
                  _e4_table(), _python_cost_table()):
        if extra and extra["entries"]:
            tables.append(extra)

    hosts = sorted({r["host"] for r in rows if r.get("host")})
    # ON-DISK SIZE, said once per table that prints it (PAGE-SPEC 4a). The
    # number is the engine's writable layer plus its volumes after the cell,
    # minus the same engine's empty footprint; a server reading is taken after
    # two samples agree within 1%, an embedded one once on the stopped
    # container. It is a post-run reading, not the build-point reading 4a asks
    # for, and says so. Milvus's sparse stack is not sampled (blank cell).
    for _t in tables:
        if any("disk GiB" in e.get("metrics", {}) for e in _t.get("entries", [])):
            _t.setdefault("conditions", [])
            if DISK_NOTE not in _t["conditions"]:
                _t["conditions"].append(DISK_NOTE)
    payload = {
        "source": "benchmarks/experiments/results/runs_paper.csv",
        "generator": "benchmarks/experiments/export_web.py",
        # Read from the rows, not asserted here. The literal "26.8.1" survived a
        # re-pin and two campaigns because nothing recomputed it (DECISIONS #49).
        "arcadedb_version": _arcadedb_identity(rows),
        # EVERY ENGINE IN THE PAYLOAD, not just the ones that recorded a commit.
        #
        # This listed engine_commit only, and rows predating the stamp carry
        # none -- so a page whose tables were mostly 26.8.1 published
        # arcadedb_commits: ["d7940d79e"] and read as though the whole thing
        # were pinned to it. The stale rows were invisible precisely BECAUSE
        # they were stale. Absence of provenance rendered as uniform provenance,
        # which is the worst direction for that error to run.
        #
        # arcadedb_version beside this is already None whenever the versions
        # disagree, so the mix was detectable and this field contradicted it.
        # Now they agree: a mixed payload lists every engine it actually holds.
        # EVERY COMPARATOR VERSION, and a flag when one backend shows two.
        #
        # The harness pins moved ahead of the frozen results -- ladybug 0.19.1
        # against a published 0.18.1, lancedb 0.37.1 against 0.34.0, qdrant
        # 1.19.0 against 1.18.0, pymilvus 3.0.1 against 3.0.0 -- so every lane
        # the campaign re-runs picks up a NEWER comparator than the lanes it does
        # not. Nothing checked that: fairness_check has no version assertion at
        # all, and the identifiability gate deliberately exempted comparators as
        # "a claim about OUR engine's provenance, not theirs". That exemption was
        # wrong. A table comparing us against Qdrant version "?" is no more
        # defensible than one comparing us against an engine we cannot name.
        #
        # Disclosed rather than withheld: dropping comparator rows would gut the
        # tables and read as though those engines could not run the workload,
        # which is the claim the tier guard exists to prevent us making.
        "comparator_versions": {
            b: sorted(v) for b, v in sorted(_comparator_versions(rows).items())},
        "comparator_version_split": sorted(
            b for b, v in _comparator_versions(rows).items() if len(v) > 1),
        "arcadedb_engines": sorted({
            _engine_identity(_row_engine_string(r), r.get("engine_commit"))
            or str(_row_engine_string(r) or "").strip() or "(no engine recorded)"
            for r in rows if str(r.get("backend", "")).startswith("arcadedb")}),
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
        "setup": {
            # Lanes that record the container rather than the machine stamp
            # "container:<id> (host unknown)"; the named hosts are the ones
            # that must have hardware on record.
            "hosts": _host_hardware(hosts),
            "cpuset": collections.Counter(str(r.get("cpuset")) for r in rows if r.get("cpuset")).most_common(1)[0][0],
            "memory_cap_by_size": MEM_BY_SCALE,
            "jvm_heap_by_size": HEAP_BY_SCALE,
        },
        "tables": [_finish_table(t) for t in _restructure_tables(tables, rows)],
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
