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
import ast as _ast
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


# SIZE LABELS FROM THE LANES' OWN CONSTANTS, not typed. The time-series label
# was typed as "2.59M points" beside a lane constant of 2,592,000, and the
# cross-model one as "50k products" beside E2's default; a raised tier
# (DECISIONS #103b) would have needed a second typed number each. Formatted
# from the constant the lane reads, so the label cannot drift from the rows.
def _l4_points(scale: str) -> str:
    """The time-series corpus size as the lane defines it, formatted for a label."""
    from l4_tsbs import SCALE_POINTS  # noqa: E402
    n = SCALE_POINTS[scale]
    return f"{n / 1e6:.2f}M" if n >= 1_000_000 else f"{n // 1000}k"


def _e2_products(scale: str) -> str:
    """The cross-model catalog size as the lane defines it, formatted for a label."""
    from e2_hybrid import SCALE_PRODUCTS  # noqa: E402
    n = SCALE_PRODUCTS[scale]
    return f"{n // 1000}k" if n < 1_000_000 else f"{n / 1e6:.1f}M"


def _l2_full_network(scale: str) -> str:
    """The full-network graph tier's size from the loader's own expected counts
    (ldbc_snb.FULL_NETWORK_COUNTS, the numbers the lane refuses a shortfall
    against), persons and KNOWS included."""
    from ldbc_snb import FULL_NETWORK_COUNTS  # noqa: E402
    c = FULL_NETWORK_COUNTS[scale]
    v = c["persons"] + c["msg_vertices"]
    e = c["knows"] + c["msg_edges"]
    return f"{v / 1e6:.1f}M vertices, {e / 1e6:.1f}M edges"


# The frozen selection this payload is built from. A skeleton publish reads
# its own freeze (DECISIONS #86), so the campaign's tracked runs_paper.csv is
# never touched and the page's source link names the file it really used.
#
# The October campaign reads its own freeze for the same reason (DECISIONS
# #84): make_paper_tables writes runs_paper_oct.csv under BENCH_INSTRUMENT
# =2026-10, and these two names must move together or the exporter reads one
# campaign's rows while the freeze step wrote the other's. Skeleton is tested
# first: it is a laptop placeholder run and keeps its own names whatever
# campaign is selected.
_SKELETON_ENV = os.environ.get("BENCH_SKELETON") == "1"
_OCTOBER_ENV = os.environ.get("BENCH_INSTRUMENT") == "2026-10"
FROZEN_NAME = ("runs_skeleton_laptop.csv" if _SKELETON_ENV
               else "runs_paper_oct.csv" if _OCTOBER_ENV
               else "runs_paper.csv")
FROZEN = HERE / "results" / FROZEN_NAME
# A SKELETON WRITES ITS OWN PAYLOAD, for the same reason it writes its own
# freeze. web_benchmarks.json is the tracked record of what the LIVE page
# serves, and a skeleton export overwrote it: the repository then held a
# laptop placeholder payload as the published one, with the live page still
# serving the campaign's. Same name, two meanings, and nothing to tell them
# apart after the fact.
#
# THE OCTOBER CAMPAIGN WRITES ITS OWN PAYLOAD, for the third time for the same
# reason. web_benchmarks.json is what the LIVE page serves and stays
# September's until the preview route is promoted; October fills
# web_benchmarks_next.json, which is what /projects/arcadedb/next is served
# from (DECISIONS #83). One name per published thing, so a stale copy is
# always identifiable as one.
OUT_NAME = ("web_benchmarks_skeleton.json" if _SKELETON_ENV
            else "web_benchmarks_next.json" if _OCTOBER_ENV
            else "web_benchmarks.json")
OUT = HERE / "results" / OUT_NAME
# AND THE GENERATED ARTIFACTS, for the fourth time for the same reason
# (make_paper_tables.GENERATED_NAME, which is the definition; this is the
# third name that has to move with the other two). The only one this module
# reads is the withheld-recall sidecar, and reading September's while
# exporting October's payload would declare September's withheld cells under
# October's tables -- a sentence under a table, sourced from a campaign the
# table has no rows from.
GENERATED_NAME = ("generated_skeleton" if _SKELETON_ENV
                  else "generated_oct" if _OCTOBER_ENV
                  else "generated")
GENERATED = HERE / "results" / GENERATED_NAME

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


# DECISIONS #86, declared here because the module-level artifact readers below
# depend on it: BENCH_SKELETON=1 says the frozen rows are the laptop's
# micro-scale placeholder run. A skeleton reads NO bench-host overlay, so the
# readers that refuse a missing pinned directory must not fire for it.
SKELETON = os.environ.get("BENCH_SKELETON") == "1"


def _dense_overlay_is_pinned():
    """Always, since 2026-09-08: dense_mp_dir() refuses instead of falling back."""
    if SKELETON:
        return False
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
    # ABSENT IS NOT PARTIAL. A PARTIAL directory is what this refusal is for:
    # an incomplete overlay standing in for a complete one is a wrong number,
    # not a safety net. An ABSENT one is a lane that has not run at this pin,
    # which for most of a campaign is the normal state -- sparse_mp comes from
    # stage 8 of 10 and the dense overlays from stage 9, while October lands
    # table by table from stage 1. Callers already expect this: the sparse
    # multipass builder immediately below does `if not root.is_dir(): return
    # None`, which the raise made unreachable, and the table is simply not
    # drawn. Returning the path lets that guard do its job.
    if not cand.is_dir():
        return cand
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


# Canonical spelling per engine, so an image repo name and a row label cannot
# publish one build under two names. Keys are what the derivation produces.
_ENGINE_SPELLING = {
    "mongo": "mongodb",
    "postgres": "postgresql",
}


# NOT _VERSION_TOKEN: that name is taken at the top of this file by a
# different pattern with no capture group, and defining it twice would
# silently hand every earlier caller this one instead.
_MEMBER_VERSION = re.compile(r"\b(\d+(?:\.\d+)+(?:[.-]?\w+)?)\b")
# A MEMBER MAY BE IDENTIFIED BY COMMIT rather than by a release number,
# which is the identifier DECISIONS #49 chose for our own engine and is
# the only one DuckPGQ publishes. "duckdb:1.5.4 + duckpgq:f386a6c" used
# to render as None -- one member with a version is one member, so the
# composed branch never fired and the single-engine path then looked for
# a release number after "duckpgq:" and found a sha. A row that says
# nothing about its engine is worse than one that says a commit.
_MEMBER_COMMIT = re.compile(r":([0-9a-f]{7,40})\b")


def _composed_members(raw):
    """(name, version) for each "+"-separated member that carries a version.

    A member is "<name><sep><version>" with the separator either a colon
    ("pgvector:0.8.6") or a space ("PostgreSQL 17.11"); the version is the
    member's FIRST version-shaped token, so trailing prose after it -- the
    "at localhost 27028" MongoDB's search node appends -- is left off rather
    than published as part of the stack's identity.
    """
    out = []
    for part in str(raw or "").split("+"):
        found = _MEMBER_VERSION.search(part) or _MEMBER_COMMIT.search(part)
        if not found:
            continue
        name = part[:found.start()].strip().rstrip(":").strip()
        if name:
            out.append((name, found.group(1)))
    return out


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
    # A COMPOSED STACK NAMES EVERY MEMBER. The row already carries them
    # ("qdrant-local:1.19.0+neo4j:2026.07.1"); what reduced it to one was this
    # function taking a single engine name and finding a single version. On the
    # table reached without an image that produced "qdrant + neo4j 1.19.1",
    # which reads as the pair at Qdrant's version, and on the table reached
    # WITH one it produced "neo4j 2026.08.1", which names half the stack. Two
    # tables, one row, two version strings, neither complete (BUGS F63c).
    # This is the rendering the dbbench branch below already used; it just was
    # not reachable unless the image happened to be one we built.
    # The version class must EXCLUDE "+", or it swallows the separator and the
    # next member's name with it: "qdrant-local:1.19.0+neo4j:2026.07.1" then
    # yields one pair whose version is "1.19.0+neo4j" and this branch never
    # fires. A build-metadata "+" inside a single version (surrealdb-server's
    # 3.2.4+20260803) is unaffected: one pair does not reach here.
    # A MEMBER MAY SPELL ITSELF WITH A SPACE, and the colon-only pair regex
    # this replaces dropped every one that did. The cross-model arm's row
    # reads "PostgreSQL 17.11 + pgvector:0.8.6 + age:1.7.0" -- PostgreSQL, the
    # arm's PRIMARY engine, separated by a space -- so the live September page
    # published that stack as "pgvector 0.8.6 + age 1.7.0" under a label
    # reading "PostgreSQL + pgvector + AGE": the one engine the row is named
    # for was the one engine the version line did not name. Splitting on "+"
    # and taking each member's own first version reads both spellings.
    #
    # Splitting on "+" FIRST is also what keeps build metadata intact:
    # surrealdb-server's "3.2.4+20260803" yields a single member carrying a
    # version and one member never reaches this branch, so it renders through
    # the single-engine path below exactly as before.
    _members = _composed_members(raw)
    if len(_members) > 1 and "+" in str(raw or ""):
        return " + ".join(f"{n.replace('-local', '')} {_short_version(v) or v}"
                          for n, v in _members)
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
    # ONE ENGINE, ONE SPELLING. The name comes from the image repo where there
    # is one and from the row label where there is not, and the two disagree:
    # MongoDB's image is "mongo" and its label is "MongoDB", so the same build
    # published as "mongo 8.2.12" on one table and "mongodb 8.2.12" on another.
    # Every string comparison across tables -- including the version gate --
    # then reads one engine as two (BUGS F63d).
    engine = _ENGINE_SPELLING.get(engine, engine)
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
    "duckpgq_graph": "DuckPGQ",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "memgraph_graph": "Memgraph", "falkordb_graph": "FalkorDB",
    "postgres": "PostgreSQL", "postgres_tuned": "PostgreSQL (tuned)",
    "duckdb": "DuckDB", "questdb": "QuestDB", "sqlite": "SQLite", "mongodb": "MongoDB",
    "timescaledb": "TimescaleDB", "pgvector_dense": "pgvector", "pgvector_sparse": "pgvector", "neo4j_dense": "Neo4j",
    "surrealdb_tpc": "SurrealDB (embedded)", "surrealdb_tpc_server": "SurrealDB (server)",
    "surrealdb_graph": "SurrealDB (embedded)", "surrealdb_graph_server": "SurrealDB (server)",
    "surrealdb_dense": "SurrealDB (embedded)", "surrealdb_dense_server": "SurrealDB (server)",
    "surrealdb_ts": "SurrealDB (embedded)", "surrealdb_ts_server": "SurrealDB (server)",
    "surrealdb_lifecycle": "SurrealDB (embedded)",
    # Served only, so bare, like MongoDB and Neo4j; "(server)" marks an engine
    # that also has an embedded row.
    "arangodb_tpc": "ArangoDB", "arangodb_graph": "ArangoDB", "arangodb_dense": "ArangoDB", "arangodb_e2": "ArangoDB",
    "arangodb_ts": "ArangoDB",
    "mongodb_graph": "MongoDB", "mongodb_dense": "MongoDB", "mongodb_e2": "MongoDB",
    # memgraph_graph, falkordb_graph and sqlite are named above and were bound
    # a second time here by the branch merge, same value both times. One key
    # per dict: a duplicate literal key is how four tier caps were silently
    # overridden in runner.TIMEOUT_BY_SCALE.
    "arcadedb": "ArcadeDB",
    "chroma": "Chroma", "ladybug": "LadybugDB",
}

# Backends runner.LANES registers that the page deliberately does not print,
# each with its reason. These are ABLATION ARMS of an engine that IS on the
# table, not absent engines, so they are neither a row nor a declared absence
# (censored, withheld, unexpressible) and the roster gate
# (page_check._check_lane_roster) needs to be told so by name. Every entry
# here is also skipped by a builder below, at the site the reason names.
OFF_PAGE_ARMS = {
    "postgres_tuned": "an ablation of one engine's image defaults, not a second "
                      "engine; it answered its question (2.33 vs 2.39 ms new-order) "
                      "and stays in the rows, off the document and durability "
                      "tables (user, 2026-09-13, DECISIONS #76)",
    "arcadedb_sparse_embedded_nocompact": "the settle-step ablation; it sat among "
                      "engine rows while being an ablation no comparator has run, "
                      "so it stays in the harness and off the page until a "
                      "comparator has the matching arm (2026-09-10)",
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
#   Qdrant v1.19.1   fp32. RE-VERIFIED AT THE NEW PIN 2026-09-19, and one
#                    clause of the old citation was wrong. `datatype` is
#                    NOT documented with a default: the schema text for
#                    SparseIndexParams.datatype is byte-identical at v1.18.2
#                    and v1.19.1 and states none. The Float32 default lives in
#                    Rust -- VectorStorageDatatype carries #[default] Float32
#                    (lib/segment/src/types.rs) and the sparse index resolves
#                    it with `config.datatype.unwrap_or_default()`
#                    (segment_constructor_base/sparse_vector_index.rs). So
#                    cite the Rust, not openapi.json.
#                    `pub type DimWeight = f32` is unchanged
#                    (lib/sparse/src/common/types.rs at tag v1.19.1), and a
#                    full file-tree diff of lib/sparse/ between v1.18.2 and
#                    v1.19.1 is IDENTICAL: still the same three inverted-index
#                    implementations, still #[default] MutableRam. 1.19 adds
#                    Turbo4 as a datatype, which is DENSE storage only, and
#                    1.19.0's one sparse entry is per-query IDF (scoring, not
#                    storage); 1.19.1 lists nothing sparse.
#                    THE "NEVER CONSULTS DATATYPE" ARGUMENT IS NARROWER THAN
#                    IT READ. The wildcard match arm is (MutableRam, _), so it
#                    holds for the APPENDABLE segment only; an optimized
#                    segment uses ImmutableRam, which does consult datatype --
#                    and at the default selects SparseCompressedImmutableRamF32.
#                    fp32 is therefore right on both paths, for two reasons,
#                    and the row is labelled from that rather than from the
#                    one path the old note covered.
#                    Our call passes on_disk=False; note that 1.19.1
#                    DEPRECATES on_disk in favour of a `memory` field
#                    (pinned/cached/cold, default pinned). It still works, and
#                    is the next thing here that will need rewording.
#   Milvus v3.0.1    fp32 -- BUT CONDITIONAL, AND THE OLD CITATION IS DEAD.
#                    Re-derived at the new pin 2026-09-19 (was v2.6.13).
#                    FIRST, DROP THE DOC SENTENCE ENTIRELY. "the value part
#                    can be a non-negative 32-bit floating-point number" is
#                    NOT on the v3.0.x pages either: grepping milvus-docs at
#                    branch v3.0.x finds zero occurrences of "value part". It
#                    exists only at v2.4.x (reference/sparse_vector.md). The
#                    old note said it was on v3.0.x and it is not, so the
#                    sentence is not re-pointed, it is dropped.
#                    SECOND, THE SOURCE CITATION MOVED. v3.0.1 pins knowhere
#                    v3.0.11, not v2.6.10, and sparse_index_node.cc no longer
#                    instantiates InvertedIndex<float, float> unconditionally
#                    for IP. What survives is operands.h, which still has
#                    `struct sparse_u32_f32 { using ValueType = float; }`, so
#                    the RAW sparse data is fp32 whatever the index does.
#                    THIRD, AND THIS IS THE REAL FINDING: 3.0 rebuilt sparse
#                    around SINDI, whose posting values are HARD-QUANTIZED to
#                    fp16 for IP (sindi_inverted_index.h asserts QuantType is
#                    fp16 for IP or uint16_t for BM25). SINDI is not a new
#                    index type -- SPARSE_INVERTED_INDEX is still the only one
#                    -- it is an algorithm behind a VERSION GATE:
#                      version_default_to_daat_maxscore() { index_version_ < 10 }
#                      ValidateInvertedIndexAlgo accepts "SINDI" only at >= 10
#                      version_support_fp16_quant_for_ip() { index_version_ >= 10 }
#                    and 3.0.1 ships targetVecIndexVersion 8 while knowhere's
#                    current_version is 8, so ResolveVecIndexVersion yields 8.
#                    At 8 the algo is DAAT_MAXSCORE and the posting values are
#                    float32. Milvus's own 3.0 notes say it out loud: "New
#                    index versions are opt-in for now", and SINDI is the IP
#                    default only "once the new index version is enabled".
#                    So STOCK 3.0.1 DOES NOT RUN SINDI AND IS fp32, and this
#                    row is fp32 BECAUSE the index version is 8. Raising
#                    dataCoord.targetVecIndexVersion to 10 or 11 would switch
#                    sparse weights to fp16 silently and this label would be
#                    wrong. The harness sets no targetVecIndexVersion, no
#                    inverted_index_algo and no quant_type (checked), the
#                    sparse arm mounts no milvus.yaml at all, and AUTOINDEX's
#                    sparse default carries none of them either -- so every
#                    path lands on 8. quant_type: "fp32" is the escape hatch
#                    that would keep fp32 under an opt-in, if it ever happens.
#   Elasticsearch 9  ~9 significant bits, their own wording: "sparse_vector
#                    fields only preserve 9 significant bits for the precision,
#                    which translates to a relative error of about 0.4%."
#                    Re-verified across the 9.4.1 -> 9.5.4 move: the file
#                    docs/reference/elasticsearch/mapping-reference/sparse-vector.md
#                    has the SAME sha256 at tags v9.4.1 and v9.5.4, so the
#                    wording is unchanged by construction. Cite the versioned
#                    tag path; elastic.co/docs is unversioned ("current") and
#                    cannot substantiate a 9.5.x-specific claim.
#
# The trap both claims were checked against: Qdrant and Milvus document DENSE
# quantization far more loudly than sparse storage, so a citation that is
# really about dense vectors is the likeliest way to put a wrong label on a
# competitor's row. Both were confirmed against version-pinned source.
#
# AND THE TRAP THE 2026-09-19 RE-PIN ADDED: a precision label sourced at one
# version is not evidence about another. All three entries here were pinned to
# versions we no longer run, one of them cited a page that never said what it
# was quoted for, and Milvus's answer now depends on a config key rather than
# on the version alone. Re-derive this table at every comparator re-pin.
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
    # mongot's vectorSearch index with "quantization": "none", read back off
    # the created index and recorded on the row as mongot_quantization.
    "mongodb_dense": "fp32",
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
    # THE SEPTEMBER EXTENSION'S RAISED SIZES (DECISIONS #103b). Each is a
    # tier of its own so its rows never share a canonical key with the rows
    # they replace; the page table switches tiers when every engine on it has
    # landed at the new size, never before, so a table is never two corpora.
    # sf1full: the full SF1 social network, persons+KNOWS plus the message
    # half, for the analytics table only (the interactive table keeps the
    # projection at SF1 and SF10).
    ("l2", "sf1full"): f"SF1, full network ({_l2_full_network('sf1full')})",
    ("l1", "medium"): "20M orders (synthetic)",
    ("l1tpc", "tpch1"): "TPC-H SF1 (6.0M line items)",
    # 59,986,052 line items in the DuckDB 1.5.4 dbgen output (the corpus
    # README's parquet metadata; the lane records the file's own count as
    # n_lineitem on every row).
    ("l1tpc", "tpch10"): "TPC-H SF10 (60.0M line items)",
    ("e2", "e2"): f"{_e2_products('e2')} products",
    ("e2", "e2_500k"): f"{_e2_products('e2_500k')} products",
    # TSBS publishes its corpus as a point count, which is what the ingest
    # column is per second of.
    ("l4", "ts100"): f"{_l4_points('ts100')} points",
    ("l4", "ts1000"): f"{_l4_points('ts1000')} points (1,000 hosts)",
    # The lifecycle tiers are row counts of the structure under test, so the
    # label is the count rather than a tier name a reader cannot size.
    ("lifecycle", "lc10k"): "10k",
    ("lifecycle", "lc100k"): "100k",
    ("lifecycle", "lc1m"): "1M",
    ("lifecycle", "lc10m"): "10M",
}

# THE SKELETON'S OWN LABELS (DECISIONS #86). The placeholder run uses the
# laptop's micro corpora, and the campaign labels above would print "2.59M
# points" over 12 hours of TSBS or "TPC-H SF1" over SF0.01. A banner saying
# the numbers are placeholders does not excuse a size column that names a
# corpus the cell never read, so the sizes here are the ones actually
# measured, each marked so it cannot be mistaken for a campaign tier.
SKELETON_SCALE_LABELS = {
    ("l1tpc", "micro"): "TPC-H SF0.01 (60k line items, skeleton)",
    # NAMED AS SYNTHETIC. These two lanes read a real corpus in the campaign,
    # LDBC-SNB and the Big-ANN sparse track, and neither is staged on a laptop,
    # so the skeleton runs the lane's own generator. A size column that said
    # only "2k people" under prose about LDBC would be naming a corpus the cell
    # never read, which is the whole reason this table exists.
    ("l2", "micro"): "2k people (synthetic, skeleton)",
    ("l3d", "micro"): "5k vectors (skeleton)",
    ("l3s", "micro"): "5k vectors (synthetic, skeleton)",
    # THE SKELETON READS THE SAME CORPUS AS THE CAMPAIGN, so the count comes
    # from the lane's constant, not from a typed guess: the first version of
    # this line said "432k points, 12 h" over rows carrying 2,592,000.
    ("l4", "ts100"): f"{_l4_points('ts100')} points (skeleton)",
    ("e2", "e2"): "50k products (skeleton)",
    ("lifecycle", "lc10k"): "10k (skeleton)",
}


def _l2_size(scale: str) -> str | None:
    """The graph corpus as the rows record it: people and friendships loaded.

    The labels used to type "73k people" and said nothing about the edges,
    which are the part that is millions; read from the frozen rows so the
    number cannot drift from what was loaded (DECISIONS #102)."""
    people = edges = None
    for r in _FROZEN_ROWS:
        if r.get("lane") != "l2" or str(r.get("scale")) != str(scale):
            continue
        try:
            # What was LOADED, not the tier's constant: under the smoke cap
            # (DECISIONS #104) n_persons still names the whole tier while
            # n_persons_ingested is the 2,000 the cell read.
            people = people or int(float(r.get("n_persons_ingested") or 0)) \
                or int(float(r.get("n_persons") or 0)) or None
            edges = edges or int(float(r.get("n_edges_ingested") or 0)) or None
        except ValueError:
            continue
        if people and edges:
            break
    if not people:
        return None
    def _k(n):
        return f"{n / 1e6:.1f}M" if n >= 1_000_000 else f"{round(n / 1000)}k"
    return f"{_k(people)} people, {_k(edges)} friendships" if edges else f"{_k(people)} people"


def scale_label(lane: str, scale: str) -> str:
    """Reader-facing size for a lane's tier name.

    Raises rather than falling back to the raw name: a new tier that reaches
    the page under its harness label is exactly the defect this map exists to
    prevent, and a silent fallback would let it through looking deliberate.
    """
    if lane == "l2":
        size = _l2_size(scale)
        if size:
            if SKELETON:
                # The skeleton's analytics rows read a capped slice of the
                # real LDBC SF1 network (DECISIONS #104a); its interactive
                # rows read the micro generator. The rows say which.
                src = next((str(r.get("graph_source") or "") for r in _FROZEN_ROWS
                            if r.get("lane") == "l2" and str(r.get("scale")) == str(scale)), "")
                if src.startswith("ldbc"):
                    return f"{size} (LDBC SF1 slice, skeleton)"
                return f"{size} (synthetic, skeleton)"
            return f"{str(scale).upper()} ({size})"
    try:
        if SKELETON:
            return SKELETON_SCALE_LABELS[(lane, scale)]
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
    "l3s": f"benchmarks/experiments/results/{FROZEN_NAME}",
    # Two tiers, two artifacts: small comes from the campaign's frozen rows,
    # DEEP-10M from the matched multipass overlay. Both are published.
    "l3d": [f"benchmarks/experiments/results/{FROZEN_NAME}",
            "benchmarks/experiments/results/dense_mp5_<pin or 2681>"],   # resolved in _dense_overlay_entries
    "l2": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "l1": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "l1tpc": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "e2": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "l4": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "e4": "benchmarks/experiments/results/e4decomp_" + (os.environ.get("BENCH_ENGINE_COMMIT", "").strip() or "UNPINNED"),
    "l2olap": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "e2atom": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "lifecycle": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "docs_oltp": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "docs_olap": f"benchmarks/experiments/results/{FROZEN_NAME}",
    "multimodel": f"benchmarks/experiments/results/{FROZEN_NAME}",
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
    ("mongo", "mongodb_dense", "MongoDB (fp32)", False),
]


def _dense_overlay_entries(scale="deep10m"):
    # See _extras in main(): a skeleton draws only what it measured, so the
    # multipass overlay (a bench-host artifact) is not read and the dense
    # table comes from the skeleton's own single-pass rows, cold only.
    if SKELETON:
        return []
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
            # wheel; a comparator's own version is lib_version
            # ("neo4j:2026.07.1"), and our served arm's is lib_version too
            # ("server:26.9.1...").
            #
            # That is what the comment said before 2026-09-19 and NOT what the
            # code did: it substituted lib_version only when engine_version
            # began "unknown", on the assumption that the client image always
            # fails to resolve the wheel. It does not always fail. Where the
            # wheel IS importable the overlay stamps its version on every row,
            # comparators included, so the dense table published
            # "surrealdb 26.9.1" -- an ArcadeDB release number worn by
            # SurrealDB, formed by _engine_version taking the NAME from the row
            # label and the NUMBER from this field (BUGS F63a).
            #
            # For a comparator, lib_version wins whenever it exists. Only our
            # own arms may take engine_version, and theirs is the same wheel.
            _lib = passes[0].get("lib_version") or passes[0].get("backend_version")
            if _lib and (not ours or str(_ev or "").startswith("unknown")):
                _ev = _lib
            elif str(_ev or "").startswith("unknown") and _lib:
                _ev = _lib
            ver.add(_ev)
            # build_s, and the two timers beside it where the engine has the
            # boundary (DECISIONS #74 item 2). The overlay is what the dense
            # table prints, so the split has to be read HERE as well as from
            # the campaign rows: a September file carries neither and _agg
            # returns None, which drops the column rather than printing blanks.
            build.append({"build_s": passes[0].get("build_s"),
                          "ingest_s": passes[0].get("ingest_s"),
                          "index_s": passes[0].get("index_s")})
            peak.append({"peak_anon_mib_sum": passes[0].get("peak_anon_mib_sum")})
            cold.append({"p50": passes[0].get("p50"), "p99": passes[0].get("p99")})
            for p in passes[1:]:
                warm.append({"p50": p.get("p50"), "p99": p.get("p99")})
                recall.append({"r": p.get("recall_at_10")})
        # The same floor the freeze applies to the campaign rows (BUGS F55): an
        # arm whose passes answer below it is a broken index, not a slow one,
        # and its cold and warm columns are not printed; the freeze sidecar's
        # sentence under the table says so.
        _recs = [x["r"] for x in recall if x.get("r") is not None]
        if _recs and max(float(v) for v in _recs) < _MPT.RECALL_FLOOR:
            continue
        metrics = {}
        for label_, rows_, field in (("cold p50 ms", cold, "p50"),
                                     ("cold p99 ms", cold, "p99"),
                                     ("warm p50 ms", warm, "p50"),
                                     ("warm p99 ms", warm, "p99"),
                                     ("recall@10", recall, "r"),
                                     ("ingest+index total s", build, "build_s"),
                                     ("ingest s", build, "ingest_s"),
                                     ("index s", build, "index_s")):
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
            "backend_key": _cb,
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
             "plus its volumes after the cell, minus the same engine's empty footprint; for a "
             "served row that is the server container alone, the client is only the driver. It is "
             "read after the queries, so it includes anything querying wrote; a server "
             "reading is taken once two samples agree within 1%, an embedded reading once on "
             "the stopped container. A blank cell is a row measured before the disk "
             "reading existed (2026-08-14). Neo4j's value includes the transaction-log "
             "files it preallocates in 256 MiB steps, which is how Neo4j uses disk; "
             "turning that off would have slowed its writes, so it stays on.")


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
                # PAGE-SPEC 4a rule 3: settled=False blocks publication of
                # the DISK reading. This path feeds the dense and sparse disk
                # columns straight from the campaign log, bypassing
                # load_canonical, which is why F72's 26 unsettled Milvus rows
                # reached the page. Scoped to the disk field: the same row's
                # peak-memory reading did converge and is still wanted.
                if ("disk" in field.lower()
                        and str(r.get("server_disk_settled")) == "False"):
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
    if r.get("server_image"):
        # A served row: the engine's bytes are the server container's growth
        # over its empty footprint. The client container is only the driver
        # (its growth is at most 1.1 MB across every served row frozen by
        # 2026-09-14), and adding it made the column mean two different things
        # in the two modes (user, 2026-09-14: "do you combine server and
        # client"). disk_data_mb on the row keeps the sum for the record.
        try:
            sv, sb = float(r.get("server_disk_mb") or ""), float(r.get("server_disk_baseline_mb") or 0.0)
        except (TypeError, ValueError):
            return None
        return round(sv - sb, 1)
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


# THE 2026-10 COLUMNS (DECISIONS #82, #74), keyed on the ROWS, not on a flag:
# a lane whose frozen rows all carry instrument "2026-10" gets these beside
# its September columns; a lane whose rows carry none is printed as before;
# a lane with both refuses, because a table cannot mix two instruments
# (make_paper_tables refuses the same mix at freeze). Rows without the field
# are the September instrument.
OCT_METRICS = {
    "l1tpc": [("payment_p50_ms", "payment p50 ms"), ("payment_p99_ms", "payment p99 ms"),
              ("top_parts_ms", "top parts p50 ms"), ("top_parts_p99_ms", "top parts p99 ms"),
              ("ship_mode_ms", "ship mode p50 ms"), ("ship_mode_p99_ms", "ship mode p99 ms"),
              ("by_month_ms", "by month p50 ms"), ("by_month_p99_ms", "by month p99 ms")],
    "l2": [("hop3f_p50_ms", "3-hop filtered p50 ms"), ("hop3f_p99_ms", "3-hop filtered p99 ms"),
           ("delete_p50_ms", "delete p50 ms"), ("delete_p99_ms", "delete p99 ms")],
    "l3d": [("ingest_s", "ingest s"), ("index_s", "index s")],
    "l4": [("q_groupby_ms", "per-host hourly p50 ms"), ("q_groupby_p99_ms", "per-host hourly p99 ms"),
           ("q_high_ms", "high-usage p50 ms"), ("q_high_p99_ms", "high-usage p99 ms")],
}
OCT_DOCS_OLTP = {"payment p50 ms", "payment p99 ms"}
OCT_DOCS_OLAP = {"top parts p50 ms", "top parts p99 ms", "ship mode p50 ms", "ship mode p99 ms",
                 "by month p50 ms", "by month p99 ms"}
_FROZEN_ROWS = []   # set by main() once the CSV is read; the switch reads it


# THE OCTOBER COLUMN SET, PER TABLE (DECISIONS #89 as amended). The dict above
# ADDS to the September columns, which is how the new queries first reached the
# page; applied to the whole October set that arithmetic gives twenty-one
# columns on the widest table, which is what #89 was written to stop. So a lane
# named here REPLACES its September list: one warm median per query, a
# ninety-ninth percentile for that table's headline query only, one cold column
# for the first query after the database opens (where the lane has one --
# a transactional cell declares in `cold_warm_na` that it does not), throughput
# where the operation has a rate, recall where the index is approximate, peak
# memory, on-disk size, and for the vector tables ingest and index build as
# separate timers.
#
# The headline query is the FIRST one in each list, so the p99 belongs to the
# query the section leads with rather than to whichever one happened to have
# the column already.
#
# A September payload is untouched: _metrics_for reaches this only for a lane
# whose rows all carry instrument 2026-10.
OCT_TABLE_METRICS = {
    # Both document tables come from this one lane spec and are split by
    # _restructure_tables; the union of their columns lives here.
    "l1tpc": [
        ("neworder_p50_ms", "new-order p50 ms"), ("neworder_p99_ms", "new-order p99 ms"),
        ("payment_p50_ms", "payment p50 ms"),
        # #82a: the four single-record operations, the ones every engine
        # expresses without dialect argument and the first thing a reader
        # looks for.
        ("crud_insert_p50_ms", "insert p50 ms"),
        ("crud_read_p50_ms", "read p50 ms"),
        ("crud_update_p50_ms", "update p50 ms"),
        ("crud_delete_p50_ms", "delete p50 ms"),
        ("oltp_ops_per_s", "OLTP ops/s"),
        ("q1_ms", "Q1 p50 ms"), ("q1_p99_ms", "Q1 p99 ms"),
        ("q6_ms", "Q6 p50 ms"),
        ("top_parts_ms", "top parts p50 ms"),
        ("ship_mode_ms", "ship mode p50 ms"),
        ("by_month_ms", "by month p50 ms"),
        ("cold_first_query_ms", "cold first query ms"),
        (_rate(("n_lineitem", "n_part"), "build_s"), "ingest documents/s"),
        ("build_s", "ingest total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "l2": [
        ("point_p50_ms", "point p50 ms"), ("point_p99_ms", "point p99 ms"),
        ("hop1_p50_ms", "1-hop p50 ms"),
        ("hop2_p50_ms", "2-hop p50 ms"),
        ("hop3f_p50_ms", "3-hop filtered p50 ms"),
        ("write_p50_ms", "insert p50 ms"),
        ("update_p50_ms", "update p50 ms"),
        ("delete_p50_ms", "delete p50 ms"),
        (_rate(("n_persons_ingested", "n_edges_ingested"), "build_s"), "ingest vertices+edges/s"),
        ("build_s", "ingest total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "l2olap": [
        ("friend_age_by_city_p50_ms", "average friend age p50 ms"),
        ("friend_age_by_city_p99_ms", "average friend age p99 ms"),
        ("same_city_edges_p50_ms", "friends in same city p50 ms"),
        ("top_degree_p50_ms", "most friends p50 ms"),
        # #82b: the two queries that make this table as thorough as the
        # document one. The triangle count is the cell most likely to hit its
        # budget at the larger size, and a censored cell is a result.
        ("degree_dist_p50_ms", "degree distribution p50 ms"),
        ("triangles_p50_ms", "triangle count p50 ms"),
        # LSQB's nine (DECISIONS #104): one exact count each, p50 only.
        ("lsqb_q1_p50_ms", "LSQB Q1 p50 ms"),
        ("lsqb_q2_p50_ms", "LSQB Q2 p50 ms"),
        ("lsqb_q3_p50_ms", "LSQB Q3 p50 ms"),
        ("lsqb_q4_p50_ms", "LSQB Q4 p50 ms"),
        ("lsqb_q5_p50_ms", "LSQB Q5 p50 ms"),
        ("lsqb_q6_p50_ms", "LSQB Q6 p50 ms"),
        ("lsqb_q7_p50_ms", "LSQB Q7 p50 ms"),
        ("lsqb_q8_p50_ms", "LSQB Q8 p50 ms"),
        ("lsqb_q9_p50_ms", "LSQB Q9 p50 ms"),
        ("cold_first_query_ms", "cold first query ms"),
        (_rate(("n_persons_ingested", "n_edges_ingested"), "build_s"), "ingest vertices+edges/s"),
        ("build_s", "ingest total s"),
        ("gav_build_s", "view build s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "e2": [
        ("hybrid_p50_ms", "transaction p50 ms"), ("hybrid_p99_ms", "transaction p99 ms"),
        # #82c: the table was one write path and said nothing about the shape
        # most people run, which is retrieval.
        ("retrieval_p50_ms", "retrieval p50 ms"),
        ("filtered_p50_ms", "graph-filtered search p50 ms"),
        ("recall_retrieval", "retrieval recall@10"),
        ("recall_filtered", "filtered recall@10"),
        (_rate(("n_products", "n_edges"), "build_s"), "ingest+index vertices+edges/s"),
        ("build_s", "ingest+index total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "l3d": [
        ("query_p50_ms", "cold p50 ms"), ("query_p99_ms", "cold p99 ms"),
        # #82d: search, insert into a built index then search, delete from a
        # built index then search.
        ("mutate_insert_query_p50_ms", "after insert p50 ms"),
        ("mutate_delete_query_p50_ms", "after delete p50 ms"),
        ("recall_at_10", "recall@10"),
        # WHAT THE MAINTENANCE ITSELF COSTS, not only what a search costs
        # afterwards. The two search columns above went up while the two
        # operations that produce them stayed off the page, so the table
        # showed the consequence of a mutation and not the mutation. These
        # four are the measurement nothing else on this page publishes: an
        # index that is fast only until it is written to is a different
        # product from one that stays fast, and recall after each says whether
        # the index absorbed the change or merely survived it.
        ("mutate_insert_per_op_ms", "insert into index ms/vector"),
        ("mutate_insert_recall_at_10", "recall@10 after insert"),
        ("mutate_delete_per_op_ms", "delete from index ms/vector"),
        ("mutate_delete_recall_at_10", "recall@10 after delete"),
        # #66/#74: two timers where the engine has the boundary, not one.
        ("ingest_s", "ingest s"), ("index_s", "index s"),
        ("build_docs_per_s", "ingest+index vectors/s"),
        ("build_s", "ingest+index total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "l3s": [
        ("query_p50_ms", "p50 ms"), ("query_p99_ms", "p99 ms"),
        ("recall_at_10", "recall@10"),
        # No ingest/index split here: the sparse lane builds the index as it
        # ingests on every engine it runs, so the boundary #74 asks to split
        # does not exist and the row records one timer. Stated in the
        # conditions rather than left as a missing column.
        ("build_docs_per_s", "ingest+index vectors/s"),
        ("build_s", "ingest+index total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        (_disk_data, "disk GiB"),
    ],
    "l4": [
        (("q_last_unbounded_ms", "q_last_ms"), "newest reading p50 ms"),
        ("q_last_p99_ms", "newest reading p99 ms"),
        ("q_global_ms", "12h aggregate p50 ms"),
        ("q_groupby_ms", "per-host hourly p50 ms"),
        ("q_high_ms", "high-usage p50 ms"),
        ("q_orderlimit_ms", "grouped, ordered, limited p50 ms"),
        ("cold_first_query_ms", "cold first query ms"),
        ("ingest_pts_per_s", "ingest points/s"),
        ("ingest_s", "ingest total s"),
        ("peak_anon_mib_sum", "peak memory GiB"),
        ("disk_data_mb", "disk GiB"),
    ],
}

# Which rows carry each October table's cold column, so a table can say what
# its cold number is -- or, where the lane declares there is no cold and warm
# split, say that instead of leaving a reader to wonder why the column is
# missing (DECISIONS #89: "Where a measurement genuinely does not apply, the
# table says so in one clause instead of leaving a blank").
OCT_COLD_SOURCE = {
    "docs_oltp": ("l1tpc", "oltp"), "docs_olap": ("l1tpc", "olap"),
    "l2": ("l2", "oltp"), "l2olap": ("l2", "olap"),
    "e2": ("e2", "hybrid"), "l4": ("l4", "ingest"),
    "l3d": ("l3d", "search"), "l3s": ("l3s", "search"),
}
COLD_QUERY_NAMES = {
    "q1": "TPC-H Q1", "top_degree": "most friends", "q_last": "the newest reading",
    "point": "the point lookup", "new_order": "new-order", "retrieval": "the retrieval path",
}


# WHAT THE ANSWER CHECK COULD NOT COMPARE, ON THE TABLE IT APPLIES TO
# (DECISIONS #88). The gate refuses a publish whose engines disagree, so a
# published table's engines agree -- but "agree" has two holes the gate itself
# prints and the page never did: a query an engine CANNOT EXPRESS, declared in
# its adapter with a reason, and a group declared not like for like. Both are
# the thing #88 says must never be silent, and a reader looking at a column
# with one engine missing from the comparison deserves the reason next to it
# rather than in a gate's log.
EQUIVALENCE_TABLE_OF = {
    ("l1tpc", "oltp"): "docs_oltp", ("l1tpc", "olap"): "docs_olap",
    ("l2", "oltp"): "l2", ("l2", "olap"): "l2olap",
    ("e2", "hybrid"): "e2", ("e2", "atomicity"): "e2atom",
    ("l4", "ingest"): "l4", ("l3d", "search"): "l3d", ("l3s", "search"): "l3s",
    ("lifecycle", None): "lifecycle",
}


# CELLS WITHHELD BECAUSE THE ANSWER IS WRONG (DECISIONS #88).
#
# The answer check found one engine returning a different answer from every
# other engine to the same question, the disagreement was reproduced and
# understood, and equivalence_check carries it as a KNOWN disagreement so the
# publish is not blocked on an upstream fix. What must NOT follow from that is
# the page printing the latency anyway: a time for a query that answered
# something else is not a measurement of that query. The cell comes out and the
# table says why, which is the same treatment a censored cell gets.
#
# Keyed (table id, backend label, column) -> the sentence the table prints.
#
# EMPTY SINCE 2026-09-18, and the entry it held is why the withholding is a
# table and not a hard-coded column. The l4 per-host hourly cell for ArcadeDB's
# served native arm was withheld from 2026-09-08: the server's SQL path
# returned a CONSTANT bucket for the function-derived key when a second
# grouping key was present, 100 hosts x 1 bucket where every other engine
# returned 100 x 12. Upstream #7610 (the served time-bucket serializer) is in
# the October pin, and the re-run on that pin answers it:
#
#   arcadedb_ts_native_server, l4/ts100          digest    hosts x buckets = pairs
#     26.8.1        (2026-09-08, withheld)   cf8b95166d59727f   100 x  1 =  100
#     417314c18d    (2026-09-18, published)  18c9985de67433e6   100 x 12 = 1200
#   every other engine, both dates             18c9985de67433e6   100 x 12 = 1200
#
# So the cell publishes: 921.5705 ms p50, beside its embedded twin's 915.4556.
# Removed here AND from equivalence_check.KNOWN_DISAGREEMENTS, which is the
# pair that has to move together -- the gate declaration without the
# withholding would print a latency for a wrong answer, and the withholding
# without the declaration would fail the gate.
WITHHELD_CELLS = {}


# EVERY ABSENCE ON A TABLE, AS DATA RATHER THAN AS PROSE.
#
# The conditions already tell a READER why a cell is blank -- a censored cell,
# a withheld answer, a query the engine cannot ask. Nothing told a GATE, so
# page_check could not tell a declared absence from a column that had silently
# stopped being measured, which is the failure it now has to catch
# (page_check.OPERATION_MANIFEST). Both surfaces come from the same call: the
# sentence goes in conditions, the structure goes here.
#
#   table id -> [{"backend": display name, "column": label or None,
#                 "kind": "censored"|"withheld"|"unexpressible", "why": text}]
#
# column None means the whole row is absent, which is what a censored cell is.
_DECLARED_ABSENCES = collections.defaultdict(list)


# THE PAGE IS READ BY PEOPLE WHO HAVE NEVER SEEN THIS REPOSITORY. Our prose
# cites its own paper trail -- "(DECISIONS #82b, #100)", "(BUGS F55)" -- and
# those citations were going out on the page, where they name documents no
# reader can open. Found 2026-09-21 by the user reading /next: forty-seven of
# them on one table.
#
# Stripped at the single point the payload is written rather than at the forty
# places the sentences are built, because those live in three modules and the
# next one written would have leaked again. What the stripper cannot repair,
# _refuse_internal_refs below refuses to publish: a silent sanitiser that
# misses a form is worse than no sanitiser, since nothing would look wrong.
_INTERNAL = r"DECISIONS?|BUGS?|FAIRNESS|PAGE-SPEC|PROTOCOL|CAMPAIGN|COMPARATORS|READING-RESULTS"
# " (DECISIONS #82b, #100)." -> "." and " (BUGS F55)." -> "."
_REF_PAREN = re.compile(r"\s*\((?:see\s+)?(?:%s)(?:\.md)?[^()]*\)" % _INTERNAL)
# "..., DECISIONS #95b)" -> "...)"  (a parenthetical with real content too)
_REF_TAIL = re.compile(r"[,;]\s*(?:%s)(?:\.md)?[^()]*(?=\))" % _INTERNAL)
# a bare citation left in running text
_REF_BARE = re.compile(r"\s*\b(?:%s)(?:\.md)?\s+#?[A-Z]?\d+[a-z]?\b" % _INTERNAL)


def _public_prose(text):
    """One reader-facing string with our internal citations taken out."""
    out = _REF_PAREN.sub("", text)
    out = _REF_TAIL.sub("", out)
    out = _REF_BARE.sub("", out)
    # the stripping can leave a double space or a space before punctuation
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,;:)])", r"\1", out)
    # A citation removed from the end of a clause leaves its comma behind.
    out = re.sub(r"[,;]\s*$", "", out)
    return out.strip()


def _strip_internal_refs(node):
    if isinstance(node, str):
        return _public_prose(node)
    if isinstance(node, dict):
        return {k: (v if k in _PROVENANCE_KEYS else _strip_internal_refs(v))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_strip_internal_refs(v) for v in node]
    return node


# Fields that name an artifact ON PURPOSE and are provenance rather than
# prose: the generator's own path, and the source files a table was built
# from. A reader who wants them wants them exact.
_PROVENANCE_KEYS = {"generator", "sources", "source", "artifact", "artifacts"}


def _refuse_internal_refs(payload):
    """Publish nothing that still cites a document the reader cannot open."""
    bad = []

    def walk(node, path=""):
        if isinstance(node, str):
            for m in re.findall(r"(?:%s)(?:\.md)?(?:\s+#?[A-Z]?\d+[a-z]?)?" % _INTERNAL, node):
                bad.append((path, m, node[:90]))
        elif isinstance(node, dict):
            for k, v in node.items():
                if k not in _PROVENANCE_KEYS:
                    walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(payload)
    if bad:
        print("REFUSING to publish: internal references survive in reader-facing text")
        for path, m, ctx in bad[:12]:
            print(f"  {path}: {m!r} in {ctx!r}")
        raise SystemExit(f"{len(bad)} internal reference(s) would have been published")


def _declare_absence(table_id, backend, column, kind, why):
    rec = {"backend": backend, "column": column, "kind": kind, "why": why}
    if rec not in _DECLARED_ABSENCES[table_id]:
        _DECLARED_ABSENCES[table_id].append(rec)


def _withhold_cells(tables):
    """Take out the cells whose answer was wrong, and say so on the table."""
    notes = collections.defaultdict(list)
    for (tid, backend, column), why in WITHHELD_CELLS.items():
        for t in tables:
            if t.get("id") != tid:
                continue
            for e in t.get("entries", []):
                if str(e.get("backend")) == backend and column in (e.get("metrics") or {}):
                    e["metrics"].pop(column)
                    notes[tid].append(why)
                    _declare_absence(tid, backend, column, "withheld", why)
    for t in tables:
        for why in dict.fromkeys(notes.get(t.get("id"), [])):
            t.setdefault("conditions", [])
            if why not in t["conditions"]:
                t["conditions"].append(why)
    return tables


def _equivalence_notes(rows):
    """table id -> one sentence about what its answer check could not compare."""
    import bench_common
    try:
        import equivalence_check as EQ
    except Exception:  # noqa: BLE001 - the page must not depend on the gate importing
        return {}
    groups, _skipped, _seen, _silent = EQ.collect(rows)
    per_table = collections.defaultdict(list)
    for (lane, _scale, workload, query), by_backend in groups.items():
        tid = (EQUIVALENCE_TABLE_OF.get((lane, workload))
               or EQUIVALENCE_TABLE_OF.get((lane, None)))
        if not tid:
            continue
        why = EQ.NOT_COMPARABLE.get((lane, query))
        if why:
            per_table[tid].append(f"{query}: not compared across arms, because {why}")
        for be, digests in by_backend.items():
            for d in digests:
                if bench_common.is_unexpressible(d):
                    per_table[tid].append(
                        f"{display_name(str(be))} cannot express {query}: "
                        f"{str(d)[len(bench_common.UNEXPRESSIBLE_PREFIX):]}")
    out = {}
    for tid, items in per_table.items():
        uniq = sorted(set(items))
        out[tid] = _gen("Every deterministic answer on this table is hashed and "
                        "compared across the engines before anything is published, "
                        "and a publish is refused when two of them disagree. What "
                        "that comparison could not cover, declared rather than "
                        "skipped: " + "; ".join(uniq) + ".", *uniq)
    return out


def _cold_note(table_id, rows, columns=()):
    """The one clause this table owes about its cold column."""
    src = OCT_COLD_SOURCE.get(table_id)
    if not src:
        return None
    lane, workload = src
    rs = [r for r in rows if r.get("lane") == lane and r.get("workload") == workload
          and str(r.get("instrument") or "") == "2026-10"]
    if not rs:
        return None
    na = sorted({str(r["cold_warm_na"]) for r in rs if r.get("cold_warm_na")})
    if na:
        # A table whose cold columns come from elsewhere (the dense table's
        # first timed pass, the sparse table's multipass overlay) must not
        # also say it has none; the sentence that describes those columns is
        # the registered one (2026-09-16, the October audit).
        if any(str(c).startswith("cold ") for c in columns):
            return None
        return _gen("There is no cold column on this table, and the reason is "
                    "recorded on the rows themselves: " + na[0], na[0])
    names = sorted({COLD_QUERY_NAMES.get(str(r.get("cold_first_query_name")),
                                         str(r.get("cold_first_query_name")))
                    for r in rs if r.get("cold_first_query_name")})
    if not names:
        return None
    return _gen(f"The cold column is the very first query of a session, "
                f"{' / '.join(names)}, timed once on a database that has just been "
                f"opened; every other latency column is the warm median of the "
                f"iterations that follow it. It answers what the first query of a "
                f"session costs against the hundredth, which is a different "
                f"question from the steady-state one and is the one an application "
                f"that opens a database per request actually asks.", *names)


def _instrument_of(lane):
    """'2026-10', '2026-09', or a refusal when the lane's rows mix the two."""
    seen = {str(r.get("instrument") or "2026-09") for r in _FROZEN_ROWS if r.get("lane") == lane}
    if len(seen) > 1:
        raise SystemExit(f"REFUSING: lane {lane} carries rows from two instruments {sorted(seen)}; "
                         "a table cannot mix them (DECISIONS #84). Re-freeze from one campaign.")
    return next(iter(seen), "2026-09")


def _metrics_for(table_id, spec, src_lane=None):
    """The columns this TABLE prints, under the instrument its ROWS were run on.

    Two identifiers, deliberately: l2olap is a second view of the graph lane's
    rows, so the instrument comes from the lane that produced them (src_lane)
    while the column set belongs to the table (table_id). Keyed on the lane
    alone, the graph analytics table would have been handed the graph
    transactional table's October columns.
    """
    src_lane = src_lane or table_id
    oct_ = _instrument_of(src_lane) == "2026-10"
    if oct_ and table_id in OCT_TABLE_METRICS:
        return list(OCT_TABLE_METRICS[table_id])
    return list(spec["metrics"]) + (OCT_METRICS.get(src_lane, []) if oct_ else [])


# ---------------------------------------------------------------------------
# SKELETON MODE (DECISIONS #86). BENCH_SKELETON=1 says the frozen rows are the
# laptop's micro-scale placeholder run, published to the preview route so the
# October page's SHAPE can be read weeks before mini measures anything. It
# changes nothing about how a cell is aggregated; it stamps the payload so
# that neither a reader nor the live publish can mistake a placeholder for a
# measurement.
# SAID IN THE WORDS A READER WOULD USE (user, 2026-09-14: "laptop runs other
# processes in parallel, so the time measurement like latency should be taken
# with a grain of salt"). "Placeholder at micro scale" is benchmark jargon for
# a reader who has just landed on a table of millisecond figures; what they
# need to be told is that the machine was busy with other things while these
# were timed, so the numbers cannot be compared with each other or with the
# live page.
SKELETON_BANNER = (
    "These numbers were timed on a laptop that was running other work at the "
    "same time: a browser, an editor, and whatever else happened to be open. "
    "Nothing here had the machine to itself, no cell was given cores of its "
    "own, and each one ran once instead of five times, on the smallest data "
    "set each benchmark has. A time on this page can therefore be out by a "
    "large factor in either direction, and two engines in the same table "
    "cannot be compared with each other, or with anything on the live page. "
    "They are here so the shape of the October page can be read and edited "
    "early: its tables, its columns, its conditions, and its prose. The "
    "machine the real numbers will be measured on has measured nothing yet.")
SKELETON_TABLE_NOTE = (
    "Take every number in this table with a grain of salt. It was timed on a "
    "laptop that was running other work at the same time, with no cores set "
    "aside for the benchmark and one run per cell, so these times can be out "
    "by a large factor and the engines here cannot be compared with each "
    "other, or with the same table on the live page. The columns, the "
    "conditions, and the sizes are October's; the values are filler until the "
    "campaign measures them on the bench machine.")
# The two invariants that describe the BENCH HOST rather than the comparison.
# A laptop skeleton cannot satisfy either (no cpuset pinning, no per-scale
# memory envelope), and every other gate must pass exactly as it will in
# October. Named in the payload so the waiver is published, not assumed.
# What a laptop skeleton cannot draw, and why, published beside the banner so
# the reader is not left wondering whether a table was dropped or forgotten.
SKELETON_ABSENT = {
    "l3smp": "the sparse second pass is a separate multipass driver on the "
             "bench host; the skeleton runs the lane once.",
    "l3d warm columns": "the dense warm pass comes from the same multipass "
                        "driver; the skeleton's dense table is cold only.",
    "e4": "the client/server decomposition is its own overlay, measured on "
          "the bench host.",
    "pycost": "the Python-cost table is the binding suite's own frozen file, "
              "not a lane the skeleton runs.",
    "the summary figure": "it is a ratio of every table against its best "
                          "comparator, and a ratio between two one-repetition "
                          "placeholder cells would look like a result while "
                          "being noise; it is drawn from the campaign's rows.",
}
# NAMED BY WHAT THEY ARE, not by our invariant numbers: "FAIRNESS F1" means
# nothing to a reader of the page, and the thing it labels -- cpuset pinning
# -- means everything.
SKELETON_WAIVERS = [
    "CPU pinning: the skeleton runs on the laptop's shared cpuset, not a "
    "pinned one.",
    "Memory envelope: the skeleton runs at the laptop's micro caps, not the "
    "campaign's per-size envelope.",
]


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
            # The build ratio ("roughly twice"), the per-document non-zero count
            # (about 127) and the numbers-per-document (about 254) came off this
            # sentence on 2026-09-16: they were typed from a September run and
            # nothing pinned them. The ratio is in the two build cells; the
            # corpus statistics belong in the notes, not under a table.
            "ArcadeDB's server takes longer to build than its embedded deployment, and that gap is loading the data, not building the index. Both run the same index code. The embedded one is handed the numbers directly, because the database is running inside the same program. The server has to be sent them, and the only way in is a written-out INSERT statement: every non-zero weight of every document arrives as an index and a value spelled out as text, which the server then has to read back into numbers.",
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
            "Milvus's dense rows run with segments sealed at 50% of the maximum segment size (the image default is 12%), so a 10M ingest lands directly in the few-large-segments layout that Milvus's own compaction otherwise reaches at an unpredictable moment; without it, half the runs queried many small segments and read slower with higher recall. One line changed from the image's configuration; sparse rows are at the default.",
            *([("ArcadeDB fp32 rows at 9.99M carry graphBuildCacheSize pinned to the corpus size (9,990,000) on both deployments, a user decision so the served build is not left on the wrong side of the engine's cache knee (issue #7146; the budget 26.10.1 makes the default). INT8 rows run this engine's default of 100,000. Comparators have no equivalent setting.")]
              if _dense_overlay_is_pinned() else []),
        ],
    },
    "l2": {
        "title": "Graph OLTP",
        "dataset": "LDBC-SNB Interactive (SF1, SF10)",
        # THE PROJECTION TIERS, NAMED RATHER THAN INHERITED. October adds
        # sf1full to PAPER_SCALES["l2"] for the ANALYTICS table, and this
        # table draws from the same lane; without naming its tiers it would
        # print the persons-and-KNOWS projection beside the full network,
        # which is two corpora in one table and PAGE-SPEC rule 4's whole
        # subject.
        "only_scales": {"sf1"} if SKELETON else {"sf1", "sf10"},
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
        # The campaign's published graph tiers. A laptop skeleton runs the
        # lane's micro generator instead, and with this set to the campaign's
        # two tiers the graph analytics table was the one section of the
        # October page the skeleton silently did not draw: the rows were
        # frozen, the table was never built, and nothing said so.
        # The skeleton's analytics rows are the capped LDBC SF1 slice the LSQB
        # smoke ran (DECISIONS #104a), not the micro generator: the nine LSQB
        # columns need the message half, which only the ldbc source loads.
        #
        # OCTOBER MOVES THIS TO {"sf1full"}, the full SF1 network, as this
        # table's SINGLE size: it is the one table #108 leaves at one size,
        # because the full network at SF10 is not feasible. It stays at the
        # two projection tiers until October's rows land. #103b's rule that a
        # raise REPLACES a tier once every engine has landed is retired by
        # #108: elsewhere the large size is a row group, and an engine absent
        # from it is a declared outcome (#103g) rather than a block on every
        # other engine's rows. September's attempt did not switch, and those
        # nine sf1full rows publish in October at October's pin.
        # OCTOBER IS THE FULL NETWORK, one size (#108's table: "graph
        # analytics -- full SF1 network -- SF10 full network is not
        # feasible"). September keeps the two projection tiers it published,
        # so the live page is untouched. This is the switch the comment above
        # anticipated: the sf1full rows publish in October at October's pin.
        "only_scales": ({"sf1"} if SKELETON
                        else {"sf1full"} if _OCTOBER_ENV else {"sf1", "sf10"}),
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
                    ("lsqb_q1_p50_ms", "LSQB Q1 p50 ms"),
                    ("lsqb_q2_p50_ms", "LSQB Q2 p50 ms"),
                    ("lsqb_q3_p50_ms", "LSQB Q3 p50 ms"),
                    ("lsqb_q4_p50_ms", "LSQB Q4 p50 ms"),
                    ("lsqb_q5_p50_ms", "LSQB Q5 p50 ms"),
                    ("lsqb_q6_p50_ms", "LSQB Q6 p50 ms"),
                    ("lsqb_q7_p50_ms", "LSQB Q7 p50 ms"),
                    ("lsqb_q8_p50_ms", "LSQB Q8 p50 ms"),
                    ("lsqb_q9_p50_ms", "LSQB Q9 p50 ms"),
                    ("gav_build_s", "view build s"),
                    ("peak_anon_mib_sum", "peak memory GiB"),
                    (_disk_data, "disk GiB")],
        "conditions": [
            "Three questions, each asked of the whole graph. Average friend age: for every city, the average age of the friends of the people who live there. Friends in same city: how many friendships connect two people in the same city. Most friends: which people have the highest number of friends. All three times are milliseconds.",
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
        # Nothing on this table is blanked for running in memory any more:
        # SurrealDB embedded re-ran on the SDK's SurrealKV disk store (qDN,
        # 2026-09-12) and carries a disk cell. The composed arm's Qdrant half
        # is still :memory: until qDT, but its disk value is Neo4j's and is
        # printed as such (the condition below says so). The key stays for
        # the mechanism at the disk_data_mb skip; it was surrealdb_e2 until
        # 2026-09-13.
        "in_memory": (),
        "conditions": [
            "Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge, and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.",
            "So the interesting result here is not the speed. It is what a crash halfway through leaves behind. The raw data records, for each run, whether an interrupted write left the two stores disagreeing, and whether they still disagreed after restarting. That is what this comparison exists to show.",
            "Read the times with one caveat, which cuts against ArcadeDB. Every engine on this table writes to disk except the composed stack's vector half: Qdrant runs in memory (:memory:), so part of why the composed stack's queries answer as they do is that half of it never touches a disk. The all-or-nothing result above does not depend on this, since a half-finished update is visible in memory just as it is on disk, but the millisecond columns do.",
            "Because the composed stack's Qdrant half runs in memory, its disk value is Neo4j's alone. SurrealDB embedded runs on the SDK's SurrealKV store on disk and SurrealDB server on RocksDB, and each has its own disk reading.",
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
    "absence of a network hop, not the engine. The next campaign matches every engine at the "
    "relaxed end instead: each one commits without waiting for the disk, which is what SQLite\'s "
    "setting above already means. Three engines have no setting for it, Neo4j, DuckDB, and "
    "LadybugDB, each measured rather than assumed, and each is named on the tables it appears on.",
]

# WHAT A SKELETON CAN AND CANNOT SAY ABOUT ITS OWN CONDITIONS (DECISIONS #86).
# Two of the sentences above describe the bench machine's protocol and are
# false on this page: the cells did not have the machine to themselves, and
# each printed cell is one run rather than the median of five. A page that
# repeats them under a placeholder banner is still telling a reader the numbers
# were measured carefully. They are replaced, in the reader's own words, rather
# than dropped, so the page says what actually happened.
SKELETON_CONDITION_SWAPS = {
    "Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.":
        "Every engine ran in Docker under the same memory cap, one cell at a "
        "time, on one laptop. The laptop was not doing only this: a browser, "
        "an editor, and the rest of a working machine kept running beside every "
        "cell, so no cell had cores of its own and the times below are not "
        "comparable between engines.",
    "Each printed cell is the median of 5 repetitions, with min and max carried alongside; nothing here is a single sample.":
        "Each printed cell here is ONE run, not the median of five, and the "
        "min and max beside it are that same single sample. The campaign runs "
        "five and prints the median; this page does not.",
}


def _thermal_note():
    """NOT PUBLISHED since 2026-09-21, by the user's decision: the throttle
    data is internal documentation, so no page carries it in any phrasing.

    Kept, not deleted: every row still records `host_temp_c_*`,
    `host_throttle_count_*` and `host_throttled_ms` (and since BUGS F80 the
    embedded arms record them too), and this is the reader for that evidence
    when a question about the host needs answering off the page.

    Was: the bench host throttles, and the page has to say so (PAGE-SPEC 7).

    The September page does NOT carry this: the spec required it and the
    payload never had it, in any phrasing (BUGS.md F71). Generated from the
    rows rather than typed, so the numbers describe the campaign that is
    publishing rather than a measurement taken once in September: a row that
    records no throttle counter contributes nothing, and if no row records
    one the sentence is omitted instead of guessed.
    """
    ms = []
    for r in _FROZEN_ROWS:
        v = r.get("host_throttled_ms")
        try:
            if v not in (None, ""):
                ms.append(float(v))
        except (TypeError, ValueError):
            continue
    if not ms:
        return None
    ms.sort()
    med = ms[len(ms) // 2] / 1000.0
    worst = ms[-1] / 1000.0
    return _gen(
        "The bench host is a mobile-class part in a small chassis and it "
        "throttles under sustained load. The power mode is left exactly as the "
        "machine ships -- governor `powersave`, turbo enabled -- because "
        "pinning the clock would lower every absolute number here, so a long "
        "build and a short query do not see the same clock. That is also why "
        f"every cell runs one at a time. Of the {len(ms)} cells on this page "
        "that record the kernel's throttle counters, the median spent "
        f"{med:.1f} s throttled and the worst {worst:.0f} s; every row carries "
        "its package temperature and both counters either side of the cell, so "
        "a slow run can be told from a throttled machine.",
        len(ms), f"{med:.1f}", f"{worst:.0f}")


def _global_conditions(tables, october):
    reps = _reps_note(tables)
    if october:
        out = [_R("GLOBAL", "docker_skeleton" if SKELETON else "docker"), _R("GLOBAL", "memory")]
        if reps:
            out.append(reps)
        out += [_R("GLOBAL", "defaults"), _R("GLOBAL", "digest")]
        return out
    out = []
    for c in GLOBAL_CONDITIONS:
        if c.startswith("Each printed cell is the median of") and reps:
            c = reps
        out.append(SKELETON_CONDITION_SWAPS.get(c, c) if SKELETON else c)
    return out

# THE 2026-10 DURABILITY CONDITION (DECISIONS #81). It replaces the paragraph
# above, which describes the September rows: from October every engine that
# has the knob is set to the same class, so the sentence stops being a list of
# differences and becomes one rule plus its named exceptions. Written from the
# ROWS, not typed: each table's own engines decide which exceptions it names,
# so a table with no Neo4j row never mentions Neo4j.
OCT_DURABILITY_CONDITION = (
    "Durability is matched at the relaxed end: on every engine that has the "
    "setting, a commit returns without waiting for the disk and the log is "
    "flushed by the engine's own background policy, which is ArcadeDB's engine "
    "default and a documented production mode for each of the others. Every "
    "engine's setting was read out of the engine rather than assumed, and each "
    "row records what it ran as `durability`.")


def _durability_note(entries, rows, table_lane=None):
    """The durability sentence THIS table needs, from the engines it shows.

    Returns None for a table whose rows predate the 2026-10 instrument, so a
    September payload is untouched.
    """
    import bench_common
    want = {str(e.get("backend")) for e in entries}
    seen = {}
    for r in rows:
        if str(r.get("instrument") or "") != "2026-10":
            continue
        lbl = display_name(str(r.get("backend") or ""))
        if lbl not in want and not any(lbl in w for w in want):
            continue
        cls = bench_common.durability_class(r.get("durability"))
        if cls:
            seen.setdefault(cls, set()).add(lbl)
    if not seen:
        return None
    parts = [OCT_DURABILITY_CONDITION]
    # An engine that has a knob has rows in both classes in the frozen set; the
    # exception is the engine with strict rows and no relaxed row (BUGS F52).
    _strict_only = seen.get("strict", set()) - seen.get("relaxed", set())
    if _strict_only:
        names = ", ".join(sorted(_strict_only))
        _one = len(_strict_only) == 1
        parts.append(f"The exception on this table is {names}, which "
                     f"{'has' if _one else 'have'} no setting to relax and "
                     f"{'waits' if _one else 'wait'} for the disk at every commit; "
                     f"{'its' if _one else 'their'} write and transaction cells are paying for that.")
    if seen.get("unverified"):
        names = ", ".join(sorted(seen["unverified"]))
        parts.append(f"{names} exposes no durability setting at all and what it does at "
                     f"commit could not be established, so it is in neither class and its "
                     f"row says so rather than claiming one.")
    return _gen(" ".join(parts), *sorted(_strict_only | seen.get("unverified", set())))


# _pinned_dir cannot be used here: it is defined below and this is module scope.
# Resolved the same way, and for the same reason -- e4decomp_2681 is a 2026-08-07
# artifact on 26.8.1, so a pinned re-run must be able to supersede it without an
# edit here. The "_2681" name is kept as the fallback because that is what exists.
E4_DIR = HERE / "results" / f"e4decomp_{os.environ.get('BENCH_ENGINE_COMMIT', '').strip() or 'UNPINNED'}"
if not E4_DIR.is_dir() and not SKELETON:
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
            *([_gen(f"Measured at ArcadeDB {meta.get('engine_version')} on {str(meta.get('ts_utc'))[:10]}. This table has not yet been re-run at the engine commit the rest of the page reports; the re-run is queued and this line goes away with it.",
                    str(meta.get('engine_version')), str(meta.get('ts_utc'))[:10])]
              if str(meta.get("engine_version") or "") and not str(meta.get("engine_version") or "").startswith("26.9.1") else []),
            _gen(f"Every number is milliseconds. One engine build "
                 f"({_engine_identity(meta.get('engine_version'), meta.get('engine_commit'))}) in all three deployments, "
                 f"{meta.get('reps')} repetitions after {meta.get('warmup')} warmup, "
                 f"identical cpuset {meta.get('cpuset')}, memory cap {meta.get('mem_cap')} "
                 f"and heap {meta.get('heap')}.",
                 str(_engine_identity(meta.get('engine_version'), meta.get('engine_commit'))),
                 str(meta.get('reps')), str(meta.get('warmup')), str(meta.get('cpuset')),
                 str(meta.get('mem_cap')), str(meta.get('heap'))),
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
    # The plain-table comparators (2026-09-15), named like their rows on the
    # document and graph tables.
    "surrealdb_ts":        "SurrealDB (embedded)",
    "surrealdb_ts_server": "SurrealDB (server)",
    "arangodb_ts":         "ArangoDB",
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
                "backend_key": backend,
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
        "source_paths": ["benchmarks/experiments/results/sparse_mp_<pin>"],   # _pinned_dir reads the pinned name
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
LIFECYCLE_WITHHELD = {"graph_gav": "its query grew from a bounded set of seeds to an unbounded 2-hop, so the cell is re-measured in October"}   # PAGE-SPEC rule 7


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
    return _gen("Known at this engine build: a vector database's no-op session close grows with the index ("
                + ", ".join(parts) + ")" + tail
                + ", because the first search after a write started a full asynchronous graph rebuild and close() waited on it. "
                "Filed as #7183, fixed upstream in #7191 for 26.10.1; the October re-pin re-measures it.",
                *parts, (f"{rd / 1000:.1f} s" if rd else None))


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

    # Rows fold by situation, size, deployment, and ENGINE. Until 2026-09-16
    # every row was ArcadeDB's and the label named only the situation; the
    # SurrealDB embedded arm (DECISIONS #95a) shares the table now, so a
    # comparator row names its engine inside the parentheses and carries an
    # explicit `engine` for the coverage table, which otherwise reads the
    # engine off the label. The ArcadeDB labels are unchanged: the page's
    # prose pins address them (page_check PROSE).
    def _engine_of(r):
        be = str(r.get("backend", ""))
        return "ArcadeDB" if "arcadedb" in be else display_name(be).split(" (")[0]

    by, declared = {}, []
    for r in rows:
        _srv = str(r.get("backend", "")).endswith("_server")   # served twin, 2026-09-07
        if r.get("lifecycle_situation_unexpressible"):
            # DECLARED, NOT BUILT (DECISIONS #88, #92): the arm could not
            # express the situation and the row says why. No session number
            # exists, so no entry; the reason prints under the table and is
            # registered as an absence the coverage gate reads.
            declared.append(r)
            continue
        by.setdefault((r.get("workload"), r.get("scale"), _srv, _engine_of(r)), []).append(r)

    entries = []
    for (situation, scale, _srv, engine), rs in sorted(by.items()):
        if situation in LIFECYCLE_WITHHELD:
            continue
        _name = LIFECYCLE_SITUATION_LABELS.get(situation, situation)
        _ours = engine == "ArcadeDB"
        _mode = "server" if _srv else "embedded"
        entry = {
            "backend": f"{_name} ({_mode})" if _ours else f"{_name} ({engine}, {_mode})",
            "backend_key": str(rs[0].get("backend")),
            "is_arcadedb": _ours,
            "engine": engine,
            "scale": scale,
            "scale_label": scale_label("lifecycle", scale),
            "workload": "session",
            "n_docs": str(rs[0].get("n_rows") or ""),
            "deployment": _mode,
            "image": rs[0].get("image"),
            "version_name": (_engine_identity(rs[0].get("engine_version"),
                                              rs[0].get("engine_commit")) if _ours
                             else _engine_version(f"{engine} ({_mode})",
                                                  _row_engine_string(rs[0]))),
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
    # The declared situations, one sentence each, in the row's own words
    # (the reason carries the documentation cited and the engine's exact
    # error), and the same fact as data for the coverage gate.
    declared_notes = []
    for (engine, situation), why in sorted({
            (_engine_of(r), r.get("workload")): str(r.get("lifecycle_situation_unexpressible"))
            for r in declared}.items()):
        _label = f"{engine} (embedded)"
        _sit = LIFECYCLE_SITUATION_LABELS.get(situation, situation)
        note = _gen(f"{_label} has no {_sit} row: the situation cannot be built in "
                    f"the engine's own language, declared by the adapter rather than "
                    f"left blank ({why}).", _label, _sit, why)
        declared_notes.append(note)
        _declare_absence("lifecycle", _label, None, "unexpressible", note)
    return {
        "id": "lifecycle",
        "title": "Session cost, open to close",
        "dataset": "synthetic, one structure per row",
        "conditions": ([_R("lifecycle", k) for k in ("session", "cold_start", "clean_close", "server_rows")]
                       if _instrument_of("lifecycle") == "2026-10" else [
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
        ]) + [_gen(f"{LIFECYCLE_SITUATION_LABELS.get(k, k)} is withheld: {v}", v) for k, v in sorted(LIFECYCLE_WITHHELD.items())]
           + declared_notes,
        "columns": ["JVM start ms", "first open ms", "cold process ms"]
                   + [LIFECYCLE_SCENARIO_LABELS[k] for k in LIFECYCLE_PAGE_SCENARIOS],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
        "source_paths": [f"benchmarks/experiments/results/{FROZEN_NAME}"],
        "source_urls": ["https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/results/runs_paper.csv"],
        "source_path": f"benchmarks/experiments/results/{FROZEN_NAME}",
        "source_url": "https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/results/runs_paper.csv",
    }


# THE DURABILITY TABLE (DECISIONS #90). Every timed write runs twice, once at
# each setting, and the main tables print the relaxed number because that is
# the matched class and the common deployment. This is the table where the
# size of the effect is settled, so a reader who wants to know what a commit
# that waits for the disk costs on each engine reads it here instead of
# inferring it from a sentence.
#
# ONE OPERATION PER LANE, not one for the whole table. The three lanes that
# run a write run different writes -- a single record, a person with an edge,
# one transaction across three models -- and the engines on them barely
# overlap: Neo4j and LadybugDB never appear on the document lane, and #90 names
# both as rows this table owes a number. So the operation rides the Size axis,
# which is also what makes the renderer's per-size bolding correct: the fastest
# engine is picked within one operation and never across two.
#
# EVERY TIMED WRITE, not one representative per lane. The table showed three
# operations while the rows held ten, and the three it showed were the three
# that argue the point least well. Reading all of them together is what makes
# the finding legible: whatever an operation costs when the commit does not
# wait, it converges on roughly the same number when it does, because each one
# pays a single flush -- so a multi-statement transaction pays the same tax as
# a one-record insert, and the ratio is large exactly where the relaxed path
# was fast.
#
# AND THE READ, WHICH IS THE CONTROL. It is the sixth document operation
# (#90), it is not a write, and it is on the table for the reason a control is
# ever on a table: five writes converging while the read does not move is the
# proof that the tax is per commit rather than per operation. Its label says
# so, and the conditions say so again.
DURABILITY_WRITES = [
    # (lane, workload, p50 field, operation key, operation label)
    ("l1tpc", "oltp", "neworder_p50_ms", "doc_neworder",
     "TPC-C new-order, one transaction (documents)"),
    ("l1tpc", "oltp", "payment_p50_ms", "doc_payment",
     "TPC-C payment, one transaction (documents)"),
    ("l1tpc", "oltp", "crud_insert_p50_ms", "doc_insert",
     "one record inserted (documents)"),
    ("l1tpc", "oltp", "crud_update_p50_ms", "doc_update",
     "one record updated (documents)"),
    ("l1tpc", "oltp", "crud_delete_p50_ms", "doc_delete",
     "one record deleted (documents)"),
    ("l1tpc", "oltp", "crud_read_p50_ms", "doc_read",
     "one record read (documents) -- the control: a read commits nothing"),
    ("l2", "oltp", "write_p50_ms", "graph_insert",
     "one person and one edge inserted (graph)"),
    ("l2", "oltp", "update_p50_ms", "graph_update",
     "one person's property updated (graph)"),
    ("l2", "oltp", "delete_p50_ms", "graph_delete",
     "one person and its edges deleted (graph)"),
    ("e2", "hybrid", "hybrid_p50_ms", "crossmodel_txn",
     "one transaction across three models (cross-model)"),
]


def _durability_table(all_rows):
    """The same write per engine at both durability settings, with the ratio.

    An engine with no setting (Neo4j, DuckDB, LadybugDB, the SurrealDB 3.2.4
    server) runs the same way in both cells, so printing its two numbers as a
    relaxed/strict pair would invent a comparison the engine cannot make. It
    gets ONE number, and the conditions name it, which is also what puts it on
    an equal footing rather than reading as fast-or-slow against everyone
    else's relaxed column. Two of those cases, kept apart in the conditions:
    an engine traced to a sync at every commit, whose one number belongs in the
    waiting column, and one whose behaviour at commit could not be established
    at all, whose number is in neither class and says so.
    """
    import bench_common
    entries = []
    for lane, workload, field, op_key, op_label in DURABILITY_WRITES:
        rows = [r for r in all_rows
                if r.get("lane") == lane and r.get("workload") == workload
                and str(r.get("instrument") or "") == "2026-10"]
        by = {}
        for r in rows:
            # The tuned PostgreSQL arm is an ablation of one engine's image
            # defaults, and it reads as a second engine on a table (DECISIONS
            # #76). It is kept out of the document tables for that reason and
            # out of this one for the same reason.
            if str(r.get("backend")) in OFF_PAGE_ARMS:
                continue
            by.setdefault(str(r.get("backend")), []).append(r)
        for backend, rs in sorted(by.items()):
            # The CELL's class, not the engine string: the string is what the
            # engine answered, and on a no-knob engine both cells answer the
            # same thing, which is precisely the case this table has to keep
            # apart from a knob that did not take (F10b fails that one).
            relaxed = [r for r in rs if str(r.get("durability_class")) == "relaxed"]
            strict = [r for r in rs if str(r.get("durability_class")) == "strict"]
            no_setting = any(str(r.get("durability_no_setting")).lower() in ("true", "1")
                             for r in rs)
            entry = {
                "backend": display_name(backend),
                "is_arcadedb": "arcadedb" in backend,
                "scale": op_key,
                "scale_label": op_label,
                "workload": "write",
                "n_docs": None,
                "deployment": deployment_of(backend),
                "image": rs[0].get("image"),
                # ArcadeDB is identified by commit (#49); a comparator by its
                # own stamp, else its row read "arcadedb surrealdb-embedded:...".
                "version_name": (_engine_identity(rs[0].get("engine_version"),
                                                  rs[0].get("engine_commit"))
                                 if "arcadedb" in backend
                                 else _engine_version(display_name(backend), _row_engine_string(rs[0]),
                                                      image=rs[0].get("image"))),
                "host": rs[0].get("host"),
                "metrics": {},
            }
            # An engine with no knob answers the same string in both cells,
            # and that string is also how we know WHICH no-knob case it is: one
            # that was traced to a sync at every commit, or one whose behaviour
            # at commit could not be established at all. Both print once; only
            # the first can be called a commit that waits.
            entry["_durability_note_class"] = (
                bench_common.durability_class(rs[0].get("durability"))
                if no_setting else None)
            if no_setting:
                got = _agg(rs, field)
                if got is not None:
                    entry["metrics"]["waits for the disk ms"] = got
            else:
                rel, strc = _agg(relaxed, field), _agg(strict, field)
                if rel is not None:
                    entry["metrics"]["no wait ms"] = rel
                if strc is not None:
                    entry["metrics"]["waits for the disk ms"] = strc
                if rel and strc and rel["median"]:
                    ratio = strc["median"] / rel["median"]
                    entry["metrics"]["cost of waiting"] = {
                        "median": round(ratio, 2), "min": round(ratio, 2),
                        "max": round(ratio, 2), "n": min(rel["n"], strc["n"])}
            if entry["metrics"]:
                entries.append(entry)
    if not entries:
        return None
    _no_knob = sorted({e["backend"] for e in entries
                       if e.get("_durability_note_class") == "strict"})
    _unverified = sorted({e["backend"] for e in entries
                          if e.get("_durability_note_class") == "unverified"})
    for e in entries:
        e.pop("_durability_note_class", None)

    def _verb(names):
        return "have" if len(names) > 1 else "has"
    return {
        "id": "durability",
        "title": "What waiting for the disk costs",
        "dataset": "Every timed write, run twice, once at each durability setting",
        "conditions": [
            _R("durability", "pairs"),
            _R("durability", "every_write"),
            _R("durability", "read_control"),
            _R("durability", "size_column"),
            _R("durability", "cell_property"),
            *([_gen(f"{', '.join(_no_knob)} {_verb(_no_knob)} no setting to relax, "
                    f"established by tracing the commits rather than assumed, so "
                    f"each prints one number, in the column for a commit that "
                    f"waits. Reading it against the other column would be reading a "
                    f"choice the engine does not offer.", *_no_knob)] if _no_knob else []),
            *([_gen(f"{', '.join(_unverified)} {_verb(_unverified)} no durability "
                    f"setting to read and what {'they do' if len(_unverified) > 1 else 'it does'} "
                    f"at commit could not be established from the engine, so the one "
                    f"number printed is in neither class. It is placed in the "
                    f"waiting column because that is the safer reading of an "
                    f"unknown, and this line is why it is there.", *_unverified)] if _unverified else []),
            _R("durability", "ratio"),
        ],
        "columns": ["no wait ms", "waits for the disk ms", "cost of waiting"],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
        "source_paths": [f"benchmarks/experiments/results/{FROZEN_NAME}"],
        "source_path": f"benchmarks/experiments/results/{FROZEN_NAME}",
    }


# THE FOUR SINGLE-STACK MULTI-MODEL ENGINES, ON ONE TABLE (DECISIONS #95).
# The roster is the decision's, typed once here and checked by page_check
# against the payload (an engine named here that no table carries fails the
# publish). Every cell is derived from the finished tables: which engine has
# a row where, and where a table declares it absent instead. Nothing about
# what an engine covers is typed.
MULTIMODEL_ENGINES = ("ArcadeDB", "ArangoDB", "MongoDB", "SurrealDB")
MULTIMODEL_CELLS = {"measured": "measured", "declared": "declared", "none": "no arm"}
MULTIMODEL_KINDS = {"censored": "censored", "withheld": "withheld",
                    "unexpressible": "cannot express", "envelope": "out of memory",
                    "failed": "failed"}


def engine_family(backend, is_arcadedb=False):
    """'ArcadeDB (server, int8)' -> 'ArcadeDB'; a lifecycle row, whose label
    is the situation rather than the engine, folds by its flag."""
    if is_arcadedb:
        return "ArcadeDB"
    return re.sub(r"\s*\(.*$", "", str(backend)).strip()


def entry_engine(e):
    """The engine an entry belongs to. A lifecycle comparator row is labelled
    by its situation ("Documents (SurrealDB, embedded)") and carries the
    engine explicitly, derived from the row's backend by the table builder;
    every other entry reads it off the label."""
    return e.get("engine") or engine_family(e.get("backend"), e.get("is_arcadedb"))


def multimodel_cell(table, engine):
    """(cell text, declared kinds) for one engine on one finished table, by
    the coverage gate's own reading of declared_absences: a whole-row absence
    or a per-cell one, either naming any arm of the engine."""
    # A MARKED ROW IS NOT A MEASURED ONE (DECISIONS #111). These rows exist
    # so a censored engine stays in the comparison; reading one as "measured"
    # here would claim a number the campaign never took.
    rows = [e for e in table.get("entries", [])
            if entry_engine(e) == engine and not e.get("outcome")]
    if rows:
        return MULTIMODEL_CELLS["measured"], []
    kinds = sorted({str(a.get("kind")) for a in table.get("declared_absences") or []
                    if engine_family(a.get("backend")) == engine})
    if kinds:
        return (MULTIMODEL_CELLS["declared"] + ", "
                + "; ".join(MULTIMODEL_KINDS.get(k, k) for k in kinds)), kinds
    return MULTIMODEL_CELLS["none"], []


def _page_table_order():
    """The order the October page places its tables in, read from the prose
    file's own benchmarkTable blocks (documents first, then graph, ...), so
    the coverage table's columns read left to right as the page reads top to
    bottom. Payload order when the site checkout is not at hand."""
    site = os.environ.get("BENCH_SITE_DIR")
    prose = Path(site) / "src" / "lib" / "projects" / "items" / "arcadedb-next.ts" if site else None
    if not prose or not prose.exists():
        return []
    return re.findall(r'tableId:\s*"([A-Za-z0-9_]+)"', prose.read_text(encoding="utf-8"))


def multimodel_sources(finished):
    """The October tables the coverage table reads, in the page's order."""
    order = _page_table_order()
    rank = {tid: i for i, tid in enumerate(order)}
    sources = [t for t in finished
               if t.get("id") != "multimodel" and t.get("instrument") == "2026-10"]
    return sorted(sources, key=lambda t: (rank.get(t.get("id"), len(rank)), sources.index(t)))


def _multimodel_table(finished):
    """One row per engine in MULTIMODEL_ENGINES, one column per October
    comparison table already in the payload (its title), each cell derived
    from that table's rows and declared absences. Built AFTER _finish_table
    has run on every other table, because that is where the absences land."""
    sources = multimodel_sources(finished)
    if not sources:
        return None
    columns = [str(t.get("title")) for t in sources]
    if len(set(columns)) != len(columns):
        raise SystemExit("REFUSING: two October tables share a title, so the "
                         "capability table cannot key its columns on titles: "
                         f"{columns}")
    entries, kinds_seen = [], set()
    for engine in MULTIMODEL_ENGINES:
        modes = sorted({str(e.get("deployment")) for t in sources
                        for e in t.get("entries", [])
                        if entry_engine(e) == engine and e.get("deployment")})
        metrics = {}
        for t, col in zip(sources, columns):
            text, kinds = multimodel_cell(t, engine)
            kinds_seen.update(kinds)
            metrics[col] = {"text": text}
        entries.append({
            "backend": engine,
            "is_arcadedb": engine == "ArcadeDB",
            "scale": "all",
            "scale_label": "every size above",
            "workload": "coverage",
            "n_docs": None,
            "deployment": ", ".join(modes) if modes else "none",
            "precision": None,
            "image": None,
            # DERIVED, not None. This table publishes one row per engine
            # summarising every other October table, and a reader needs to
            # know which build that coverage describes. The sources carry it;
            # if they disagree the join makes the disagreement visible and
            # version_consistency_check's family rules then refuse it, which
            # is the behaviour wanted over a silent None.
            "version_name": " / ".join(sorted({
                str(e["version_name"]) for t in sources
                for e in t.get("entries", [])
                if entry_engine(e) == engine and isinstance(e.get("version_name"), str)
                and e["version_name"].strip()})) or None,
            "host": None,
            "metrics": metrics,
        })
    legend = {
        "censored": "censored, the cell exceeded the budget every engine had",
        "withheld": "withheld, the answer disagreed and the number was taken off the page",
        "unexpressible": "cannot express, the engine's own language cannot ask the query",
        "envelope": "out of memory, the cell reached the memory envelope every engine "
                    "on that table had and was killed by the kernel",
        "failed": "failed, the cell reported an error inside its budget",
    }
    # ITERATE THE KINDS THAT ARE PRESENT, not a list typed beside the legend.
    # The tuple this replaces named three, so "failed" -- a kind
    # _censored_notes has always been able to declare -- appeared in the cells
    # above with nothing in the legend explaining it, and any kind added later
    # would have joined it silently.
    _unknown = sorted(k for k in kinds_seen if k not in legend)
    if _unknown:
        raise SystemExit(f"REFUSING: the capability table declares {_unknown} "
                         "with no legend entry; a reader would see a word the "
                         "page never defines")
    kinds_text = "; ".join(legend[k] for k in sorted(kinds_seen) if k in legend)
    n_tables = _WORDS.get(len(sources), str(len(sources))).lower()
    sentence = _gen(
        f"This table is derived from the {n_tables} tables above and carries no "
        f"measurement of its own. Each column is one of those tables. "
        f"{MULTIMODEL_CELLS['measured']} means the engine has at least one row on "
        f"that table, counting every arm of one engine as one, so both ArcadeDB "
        f"deployments are ArcadeDB and both SurrealDB modes are SurrealDB; "
        f"{MULTIMODEL_CELLS['declared']} means the table has no row for the engine "
        f"and says why beneath itself, in the words printed there"
        + (f" ({kinds_text})" if kinds_text else "")
        + f"; {MULTIMODEL_CELLS['none']} means the engine was not run on that "
        f"workload, with neither a row nor a declared reason. The Mode column "
        f"lists the deployments the engine has rows for anywhere on the page.",
        n_tables)
    return {
        "id": "multimodel",
        "title": "What the four multi-model engines cover",
        "dataset": "Every October table on this page, read for which engine has a row",
        "instrument": "2026-10",
        "conditions": [sentence],
        "columns": columns,
        "directions": {},
        "withheld_scales": [],
        "withheld_reason": None,
        "declared_absences": [],
        "entries": entries,
        "source_paths": [f"benchmarks/experiments/results/{FROZEN_NAME}"],
        "source_path": f"benchmarks/experiments/results/{FROZEN_NAME}",
    }


def _l4_table(all_rows):
    # Canonical first; the 2026-08 files are the fallback, not the source.
    grouped = _l4_canonical(all_rows)
    if not grouped:
        raise SystemExit("no canonical l4 rows at the pin; the legacy l4_tsbs.jsonl/ts_2681 readers were retired 2026-09-08")
    if not grouped:
        return None

    order = ["ArcadeDB (embedded, native time series)", "ArcadeDB (embedded, document path)",
             "questdb", "duckdb", "sqlite", "mongodb", "timescaledb",
             "SurrealDB (embedded)", "SurrealDB (server)", "ArangoDB"]
    # This lane predates runner.BACKENDS and keeps its own adapters, so the
    # topology lookup does not reach it. QuestDB is a server (ILP ingest on
    # 9009, SQL over pg-wire, see l4_tsbs.py); the other two run in-process.
    L4_DEPLOYMENT = {"ArcadeDB (embedded, native time series)": "embedded",
                     "ArcadeDB (server, document path)": "server",
                     "ArcadeDB (server, native time series)": "server",
                     "ArcadeDB (embedded, document path)": "embedded",
                     "questdb": "server", "duckdb": "embedded", "sqlite": "embedded", "mongodb": "server", "timescaledb": "server",
                     "SurrealDB (embedded)": "embedded", "SurrealDB (server)": "server", "ArangoDB": "server"}
    # The October set REPLACES L4_METRICS (see OCT_TABLE_METRICS): five
    # queries, one p99, one cold column, in the order the section reads.
    # Resolved once, before the loop, so the table's column list cannot come
    # from a different instrument than its cells.
    _l4_cols = (OCT_TABLE_METRICS["l4"] if _instrument_of("l4") == "2026-10"
                else list(L4_METRICS))
    entries = []
    for label in sorted(grouped, key=lambda k: (order.index(k) if k in order else 99, k)):
        rs = grouped[label]
        entry = {
            "backend": display_name(label) if label in DISPLAY_NAMES else label,
            "backend_key": str(rs[0].get("backend")),
            # case-insensitive: the labels read "ArcadeDB (...)" since
            # 2026-09-11 and the lowercase test unshaded all four rows for a day
            "is_arcadedb": "arcadedb" in label.lower(),
            "scale": L4_SHAPE["scale"],
            # THE SIZE COLUMN NAMES THE CORPUS THAT RAN. This lane has one
            # tier, so its size was a typed constant, and under a skeleton the
            # table then printed the campaign's corpus over a laptop slice of
            # it -- the one thing SKELETON_SCALE_LABELS exists to stop. The
            # scale key stays as it is because page_check and the figures
            # address cells by it.
            "scale_label": (scale_label("l4", "ts100") if SKELETON
                            else L4_SHAPE["scale"]),
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
        for field, lab in _l4_cols:
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
        "conditions": ([_R("l4", "settle" if symmetric else "settle_rows"), _R("l4", "schema"), _R("l4", "newest")]
                       if _instrument_of("l4") == "2026-10" else [
            # The two-arm explanation moved into the page caption, where a
            # reader meets the rows; saying it in both places said it twice.
            "No engine settles inside the ingest timer. QuestDB's WAL apply runs after the clock stops, "
            "and the newest-reading query is asked unbounded on every engine, so the unsealed tail a scan "
            "walks costs the same everywhere. Sealing the write buffer makes the aggregation faster and the "
            "last-point query slower, and settling only ours would have been a one-sided advantage."
            + ("" if symmetric else " Rows that record a settle time did that settling after the timer stopped."),
            # The one-tag/ten-tag pricing (2.0x, 2.6x) was an ablation result,
            # not a row; it lives in the notes, the statement stays.
            "One tag and three fields, not the ten and ten the TSBS cpu schema "
            "defines. The reduction is applied identically to every engine, so "
            "the comparison is internally fair, but it is not the full "
            "benchmark.",
            _l4_lastpoint_note(all_rows),
        ]),
        "columns": [lab for _, lab in _l4_cols],
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
                # condition that says every cell is a median (PAGE-SPEC rule 2, the conditions block).
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
            _gen("The engine itself runs at the same speed either way. What Python "
                 "is charged for is moving results across the boundary, which is why "
                 f"the vector search costs {us('vector', 'P-raw-call') / jv:.2f}x and the scan "
                 f"{us('query', 'P-columns-100000') / jq:.2f}x rather than "
                 "anything scaling with the work the engine did.",
                 f"{us('vector', 'P-raw-call') / jv:.2f}", f"{us('query', 'P-columns-100000') / jq:.2f}"),
            _gen("The path you choose inside Python matters far more than the "
                 "language boundary does. Asking for record objects is "
                 f"{us('query', 'P-tolist-100000') / us('query', 'P-columns-100000'):.1f}x slower "
                 "than asking for columns over the same query, so the practical "
                 "advice is to use the columnar or batched call for anything large.",
                 f"{us('query', 'P-tolist-100000') / us('query', 'P-columns-100000'):.1f}"),
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
           "sqlscript batches over HTTP; Neo4j and Memgraph UNWIND batches over bolt; FalkorDB the "
           "same UNWIND batches over the Redis protocol; LadybugDB COPY from CSV, its native bulk "
           "path; DuckPGQ Arrow INSERT SELECT into the persons and knows tables under a property "
           "graph."),
    "e2": ("ingest+index total s is one timer around loading the vertices and edges and creating the vector index. Ingest paths: ArcadeDB embedded loads with the Python package's graph_batch (5,000 "
           "records per commit, vertices then edges) and then CREATE INDEX ... LSM_VECTOR; served "
           "sends CREATE VERTEX and CREATE EDGE batches as sqlscript over HTTP, then the same CREATE "
           "INDEX; SurrealDB embedded inserts through its Python SDK into the SDK's SurrealKV store "
           "on disk, and SurrealDB server through the same SDK over WebSocket onto RocksDB; the "
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

# ---------------------------------------------------------------------------
# WHERE A CONDITION SENTENCE MAY COME FROM (2026-09-16, after BUGS F52).
#
# The rule for the page is that every number on it is produced from the frozen
# rows by this file, and a typed number appears only under a pin that
# page_check evaluates at every publish. Table cells always met it; the
# condition sentences under the tables never did, and an audit of the October
# preview found typed September numbers (a memory split, a build ratio, two
# ablation results, a view build time) under tables whose rows said otherwise.
# So a condition sentence now has exactly two sources, and the gate
# (page_check._check_conditions) can tell which one produced it:
#
#   GENERATED: written by a function of the rows or of a lane constant, and
#   registered through _gen() together with the strings it inserted. The gate
#   requires every numeric token in such a sentence to be one of those strings
#   or a non-measurement token (an issue number, a date, a tier name), so a
#   generator that types a number beside the ones it computes is caught too.
#
#   REGISTERED: an October sentence typed here in OCT_PROSE, keyed by table,
#   with a pin (regex, lambda over the page cells and the rows) for each
#   number it carries; a number no pin can reach is not typed.
#
# Under the 2026-10 instrument a table's conditions may come from nowhere
# else: the September lists (LANES[...]["conditions"], INGEST_NOTES, DISK_NOTE,
# GLOBAL_CONDITIONS) are not a source for an October payload, and the gate
# refuses an October sentence that is neither generated nor registered.
# Narrative that comments on the numbers ("only ArcadeDB moves between them",
# "the benefit is uneven", "every comparator is within 3%") is not written
# during the campaign at all; it is written at the freeze, with pins, so it is
# absent here on purpose.
#
# The September page keeps every sentence it has; its typed numbers are pinned
# in page_check.SEPT_CONDITION_PINS.
_GENERATED = []


def _gen(text, *values):
    """Register `text` as a generated condition sentence, with the strings the
    generator inserted into it (formatted exactly as they appear in it).
    Returns the text, so a call can sit where the literal sat."""
    rec = {"text": text, "values": [str(v) for v in values if v not in (None, "")]}
    if rec not in _GENERATED:
        _GENERATED.append(rec)
    return text


def _table_instrument(table_id):
    """'2026-10' when every row behind this table ran on the October
    instrument, else '2026-09'. The durability table exists only under
    2026-10; artifact-backed tables (e4, pycost, l3smp) are September's."""
    if table_id in ("durability", "multimodel"):
        return "2026-10"
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return "2026-09"
    return _instrument_of(lane_wl[0])


def _const(module, name):
    import importlib
    return getattr(importlib.import_module(module), name)


def _milvus_seal_proportion():
    """The sealProportion docker-conf/milvus-dense.yaml mounts over the
    image's own (BUGS F8), read from the file the runner mounts."""
    for line in (HERE / "docker-conf" / "milvus-dense.yaml").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*sealProportion:\s*([0-9.]+)", line)
        if m:
            return float(m.group(1))
    return None


L3S_SECOND_PASS = (
    "Cold p50 and p99 are the first timed pass after the build, median of five builds. "
    "Warm and gain come from a separate run of the same arms: one build per engine, then "
    "five more passes over a different half of the query set, so a warm number cannot be "
    "explained by the engine having already answered that exact query; gain is that run's "
    "cold over its warm.")
L3S_SECOND_PASS_100K = L3S_SECOND_PASS + " 100k has no second-pass run yet."

OCT_DISK_NOTE = (
    "Disk is what the workload left on disk, in GiB: the engine's writable layer plus its "
    "volumes after the cell, minus the same engine's empty footprint; for a served row that "
    "is the server container alone, the client is only the driver. It is read after the "
    "queries, so it includes anything querying wrote; a server reading is taken once two "
    "samples agree within 1%, an embedded reading once on the stopped container. Neo4j's "
    "value includes the transaction-log files it preallocates in 256 MiB steps, which is how "
    "Neo4j uses disk, so they stay in.")

# A pin is (regex with one capture, fn(P, rows) -> number) or the same with a
# third element "const" when the number is a lane or runner constant, which the
# gate compares on a skeleton too (a row-derived pin is presence-only there,
# like the page prose pins).
OCT_PROSE = {
    "GLOBAL": {
        "docker": ("Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.", []),
        "docker_skeleton": ("Every engine ran in Docker under the same memory cap, one cell at a "
                            "time, on one laptop. The laptop was not doing only this: a browser, "
                            "an editor, and the rest of a working machine kept running beside every "
                            "cell, so no cell had cores of its own and the times below are not "
                            "comparable between engines.", []),
        "memory": ("Peak memory is the largest amount an engine held in its own address space, added over every container a run used, and it leaves out the file cache the kernel keeps on the engine's behalf. That is the right number for engines that manage their own memory, and an undercount for engines that lean on the kernel instead, so compare it down one engine's rows rather than across engines that work differently.", []),
        "defaults": ("Defaults first. Where a default would make the comparison meaningless, it is equalized and the override is disclosed rather than hidden.", []),
        "digest": ("Comparators are pinned by sha256 image digest, not by a floating tag.", []),
    },
    "*": {
        "skeleton": (SKELETON_TABLE_NOTE, []),
        "disk": (OCT_DISK_NOTE, [(r"agree within (\d+)%", lambda P, rows: _const("runner", "DISK_SETTLE_TOL") * 100, "const")]),
    },
    "l3s": {
        "recall": ("Recall is reported beside every latency: ArcadeDB quantizes posting weights to int8 by default, so a latency number without its recall is not comparable.", []),
        "one_timer": ("ingest+index total s is one timer around inserting the documents and building the index; on this lane every engine builds its sparse index as it ingests, so there is no boundary to time separately. ingest+index vectors/s divides the document count by it.", []),
        "es_pruning": ("Elasticsearch runs with index-time token pruning disabled. Its 9.x default prunes on thresholds tuned for a different model's vectors and costs recall on this corpus, which would have printed a quality gap belonging to that default rather than to the engine, and printed it in our favour.", []),
        "second_pass": (L3S_SECOND_PASS, []),
        "second_pass_100k": (L3S_SECOND_PASS_100K, []),
        # THE THREE MULTI-MODEL ENGINES WITH NO SPARSE ARM, declared with the
        # reason (DECISIONS #92: an engine is left off a table only when its
        # documentation shows the query cannot be expressed, and then the
        # absence is declared, never left blank). Facts about documentation,
        # read 2026-09-16, with no number in them, so no pin. _oct_conditions
        # prints them under the sparse table and registers each as a
        # whole-row absence the coverage gate and the four-engine table read.
        "no_sparse_arangodb": (
            "ArangoDB has no row on this table. Its index types are the primary, edge, vertex-centric, "
            "persistent, inverted, TTL, geo, and vector indexes and the deprecated fulltext index "
            "(https://docs.arango.ai/arangodb/stable/indexes-and-search/indexing/basics/), and the "
            "vector index is FAISS IVF over one attribute that holds an array of numbers of a fixed "
            "dimension (https://docs.arango.ai/arangodb/stable/indexes-and-search/indexing/working-with-indexes/vector-indexes/); "
            "its sparse option means an index that skips documents missing the attribute. Nothing "
            "indexes a sparse vector, so the sparse nearest-neighbour search this table times cannot "
            "be expressed.", []),
        "no_sparse_mongodb": (
            "MongoDB has no row on this table. Its index types are single field, compound, multikey, "
            "wildcard, geospatial, hashed, text, clustered, and unique "
            "(https://www.mongodb.com/docs/manual/indexes/), and a Vector Search index's vector field "
            "must hold an array of numbers, as doubles or as a BinData vector of floats or small "
            "integers, with a fixed number of dimensions "
            "(https://www.mongodb.com/docs/vector-search/indexes/vector-search-type/); the field types "
            "an index accepts are vector, filter, and autoEmbed, and none is a sparse or "
            "token-and-weight form. Nothing indexes a sparse vector, so the sparse nearest-neighbour "
            "search this table times cannot be expressed.", []),
        "no_sparse_surrealdb": (
            "SurrealDB has no row on this table. Its index types are the standard, unique, composite, "
            "count, full-text, HNSW, and DISKANN indexes, with brute force for an unindexed field and "
            "the MTREE index the embedded core also accepts, and every vector form is declared with a "
            "DIMENSION over one field that holds an array of numbers "
            "(https://surrealdb.com/docs/surrealql/statements/define/indexes); the nearest-neighbour "
            "operator takes one dense array (https://surrealdb.com/docs/surrealql/operators). Nothing "
            "indexes a sparse vector, so the sparse nearest-neighbour search this table times cannot "
            "be expressed.", []),
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Java API (newDocument with int and float arrays) in 500-record transactions, then COMPACT INDEX; served sends INSERT statements as sqlscript batches over HTTP; Qdrant, Milvus, and Elasticsearch upsert or bulk-index in batches, then settle (Elasticsearch refresh and force-merge, Milvus flush and load); pgvector COPY FROM STDIN in sparsevec text form, then CREATE INDEX.",
                   [(r"in (\d+)-record transactions", lambda P, rows: _const("l3_sparse", "INGEST_BATCH"), "const")]),
    },
    "l3d": {
        "cold": ("Cold p50 and p99 are the first timed pass over the query set after the index is built; the lane runs a short untimed warm-up on held-out queries before it, so cold means an index that has not yet answered the timed queries, not a process that has done nothing. Warm columns, where present, are the passes after it from the multipass driver.", []),
        "degree": ("ArcadeDB's maxConnections is a Vamana per-layer degree, not hnswlib's M. Matching the parameter names would compare a half-degree graph against a full-degree one, so the graphs are matched by effect instead.", []),
        "arango_ivf": ("ArangoDB's vector index is FAISS IVF (inverted lists over trained centroids), not HNSW, so the degree match above does not apply to it; its rows record nLists (about the square root of the corpus) and nProbe (an eighth of the lists) instead.", []),
        "milvus": ("Milvus's dense rows run with segments sealed at 50% of the maximum segment size, where the image default is 12%, so a large ingest lands in the few-large-segments layout that Milvus's own compaction otherwise reaches at an unpredictable moment. One line changed from the image's configuration; sparse rows are at the default.",
                   [(r"sealed at (\d+)%", lambda P, rows: _milvus_seal_proportion() * 100, "const"),
                    (r"image default is (\d+)%", lambda P, rows: _const("runner", "MILVUS_IMAGE_SEAL_PROPORTION") * 100, "const")]),
        "ingest": ("Ingest paths: ArcadeDB embedded issues INSERT per vector in 10,000-row transactions through the Python package, then CREATE INDEX ... LSM_VECTOR; served sends 500-statement sqlscript batches over HTTP with each vector spelled out as text, then the same CREATE INDEX; Chroma add() in batches of 5,000; LanceDB an Arrow table then create_index; Qdrant and Milvus upsert in batches; DuckDB VSS and sqlite-vec executemany; pgvector COPY FROM STDIN then CREATE INDEX; Neo4j loads then builds its vector index; MongoDB insert_many then its vector search index; ArangoDB import_bulk then its FAISS IVF index; SurrealDB inserts through its Python SDK.",
                   [(r"in ([\d,]+)-row transactions", lambda P, rows: _const("l3d_dense", "BATCH"), "const"),
                    (r"sends (\d+)-statement", lambda P, rows: _const("l3d_dense", "SERVER_BATCH"), "const"),
                    (r"batches of ([\d,]+); LanceDB", lambda P, rows: _const("l3d_dense", "CHROMA_BATCH"), "const")]),
    },
    "l2": {
        "projection": ("Every engine traverses the same persons-and-KNOWS projection, with edges stored in both directions.", []),
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Java API (newVertex, newEdge) in 5,000-record transactions; served sends CREATE VERTEX and CREATE EDGE statements as sqlscript batches over HTTP; Neo4j and Memgraph UNWIND batches over bolt; FalkorDB the same UNWIND batches over the Redis protocol; LadybugDB COPY from CSV, its native bulk path; ArangoDB import_bulk; MongoDB insert_many; SurrealDB inserts the persons through its Python SDK and the KNOWS edges as bulk relation inserts.",
                   [(r"in ([\d,]+)-record transactions", lambda P, rows: _const("l2_graph", "INGEST_BATCH"), "const")]),
    },
    "l2olap": {
        "gav": ("The Graph Analytical View is a copy of the graph that ArcadeDB builds in memory, laid out for questions that sweep the whole graph rather than follow a few links. Rows labelled GAV ran with it built, once, before any query was timed, and the view build column is what that took.", []),
    },
    "e2atom": {
        "trial": ("A trial writes the three products, kills the process between them, reopens, and checks whether every product is present or none. Torn means some but not all: the counts the page's E2 prose quotes are these.", []),
    },
    "e2": {
        "atomic": ("Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge, and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.", []),
        "interesting": ("So the interesting result here is not the speed. It is what a crash halfway through leaves behind. The raw data records, for each run, whether an interrupted write left the two stores disagreeing, and whether they still disagreed after restarting. That is what this comparison exists to show.", []),
        "caveat": ("Read the times with one caveat, which cuts against ArcadeDB. Every engine on this table writes to disk except the composed stack's vector half: Qdrant runs in memory (:memory:), so part of why the composed stack's queries answer as they do is that half of it never touches a disk. The all-or-nothing result above does not depend on this, since a half-finished update is visible in memory just as it is on disk, but the millisecond columns do.", []),
        "disk_split": ("Because the composed stack's Qdrant half runs in memory, its disk value is Neo4j's alone. SurrealDB embedded runs on the SDK's SurrealKV store on disk and SurrealDB server on RocksDB, and each has its own disk reading.", []),
        "ingest": ("ingest+index total s is one timer around loading the vertices and edges and creating the vector index. Ingest paths: ArcadeDB embedded loads with the Python package's graph_batch (5,000 records per commit, vertices then edges) and then CREATE INDEX ... LSM_VECTOR; served sends CREATE VERTEX and CREATE EDGE batches as sqlscript over HTTP, then the same CREATE INDEX; SurrealDB embedded inserts through its Python SDK into the SDK's SurrealKV store on disk, and SurrealDB server through the same SDK over WebSocket onto RocksDB; Neo4j and the composed stack load the graph with UNWIND over bolt, and the composed stack upserts its vectors into Qdrant; PostgreSQL + pgvector + AGE loads the products with COPY under a pgvector HNSW index and creates the graph with UNWIND inside Cypher; ArangoDB import_bulk; MongoDB insert_many.",
                   [(r"graph_batch \(([\d,]+) records per commit", lambda P, rows: _const("e2_hybrid", "BATCH"), "const")]),
    },
    "l4": {
        "settle": ("No engine settles inside the ingest timer. QuestDB's WAL apply runs after the clock stops, and the newest-reading query is asked unbounded on every engine, so the unsealed tail a scan walks costs the same everywhere. Sealing the write buffer makes the aggregation faster and the last-point query slower, and settling only ours would have been a one-sided advantage.", []),
        "settle_rows": ("No engine settles inside the ingest timer. QuestDB's WAL apply runs after the clock stops, and the newest-reading query is asked unbounded on every engine, so the unsealed tail a scan walks costs the same everywhere. Sealing the write buffer makes the aggregation faster and the last-point query slower, and settling only ours would have been a one-sided advantage. Rows that record a settle time did that settling after the timer stopped.", []),
        "schema": ("One tag and three fields, not the ten and ten the TSBS cpu schema defines. The reduction is applied identically to every engine, so the comparison is internally fair, but it is not the full benchmark.", []),
        "newest": ("Newest reading means the most recent value each sensor has reported, which is what a monitoring dashboard asks for when it shows the current state of a fleet. TSBS calls this query last-point. It is run without a time bound; the same query bounded to the past hour is measured beside it and kept on the row rather than printed.", []),
        # "withheld_hourly" was registered here while the served native arm's
        # per-host hourly cell was withheld. The October pin carries the fix
        # (see WITHHELD_CELLS above), the cell publishes, and the sentence is
        # no longer emitted, so its registration is gone with it.
        "ingest": ("Ingest paths: the ArcadeDB document path issues INSERT per point through the Python package (embedded) or sqlscript batches over HTTP (served); the native TIMESERIES type takes columns through the async executor's append_samples (embedded) or InfluxDB line protocol at /api/v1/ts/{db}/write (served); DuckDB inserts an Arrow table; QuestDB takes line protocol over TCP; SQLite executemany in batched transactions; MongoDB insert_many in batches into a time-series collection; TimescaleDB COPY; ArangoDB import_bulk; SurrealDB inserts through its Python SDK.", []),
    },
    "lifecycle": {
        "session": ("The SESSION is open + action + close. Reporting open and close alone hides work triggered between them.", []),
        "cold_start": ("Cold start is measured in a fresh subprocess and reported beside every session number, because a millisecond open inside a process that takes half a second to reach its first database call is not a millisecond to whoever launched it.", []),
        "clean_close": ("A clean close should be O(what was written), not O(what is stored): write nothing and closing should cost the same at 10k documents and 10M.", []),
        "server_rows": ("Server rows have no JVM start, first open, or cold process: the server is already running when the probe connects, so those three columns describe the embedded process only. The session columns are measured for both.", []),
        # The SurrealDB embedded arm (2026-09-16, DECISIONS #95a): a fact about
        # the engine, not a number, so it carries no pin.
        "surreal_rows": ("SurrealDB rows have no JVM start: the SurrealDB core is a compiled extension that the Python import loads, so there is no runtime to start apart from the import. Their first open is the first open with the SDK already imported, and their cold process is interpreter start, import, open, and close, the same span the ArcadeDB embedded rows time. SurrealDB's time-series row is a plain table of timestamped records, the footing its time-series rows elsewhere on this page run on, because the engine has no time-series type.", []),
    },
    "durability": {
        "pairs": ("Each row is one engine running ONE operation twice: once where a commit returns without waiting for the disk, which is the setting every other table on this page reports, and once where the commit waits for the log to be flushed and synced. Nothing else about the cell changes.", []),
        "every_write": ("Every timed write on the page is here: the six document operations, the three graph writes, and the cross-model transaction. Read down the operations for one engine rather than across the engines for one operation, because what the setting costs is a property of the engine's commit and the rest of the page already compares the engines.", []),
        "read_control": ("The read is the control, and it is the row that makes the rest readable: it runs in both cells like everything else and commits nothing, so it is what the writes are moving against.", []),
        "size_column": ("The Size column names the operation rather than a corpus size: the three lanes that time a write do not write the same thing, so each engine is compared only against the engines running its own operation.", []),
        "cell_property": ("The setting is a property of the cell, not a second measurement inside one: it lives on the database or on the server for most of these engines, so each pair of numbers is two runs.", []),
        "ratio": ("The ratio is what the strict setting costs on that engine, at this corpus size and this operation count. It is not a claim about any other write. A large ratio is not a slow engine: it is an engine whose relaxed path was fast, measured against a flush that costs what a flush costs.", []),
    },
    "docs_oltp": {
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Python package's insert_many in 10,000-row batches, one JSON payload per batch; served sends INSERT statements as sqlscript batches over HTTP; PostgreSQL COPY FROM STDIN; DuckDB CREATE TABLE AS SELECT from in-memory frames; SQLite executemany; MongoDB insert_many; ArangoDB import_bulk; SurrealDB inserts through its Python SDK.",
                   [(r"in ([\d,]+)-row batches", lambda P, rows: _const("l1_tpc", "BATCH"), "const")]),
    },
}
OCT_PROSE["docs_olap"] = {"ingest": OCT_PROSE["docs_oltp"]["ingest"]}
OCT_PROSE["l2olap"]["ingest"] = OCT_PROSE["l2"]["ingest"]

# The registered sentences each October table opens with, in order. Sentences
# that depend on which engines are on the table are added by _oct_conditions.
OCT_TABLE_PROSE = {
    "l3s": ["recall", "one_timer", "es_pruning"],
    "l3d": ["degree"],
    "l2": ["projection"],
    "l2olap": ["gav"],
    "e2atom": ["trial"],
    "e2": ["atomic", "interesting", "caveat", "disk_split"],
}


def _oct_entries(table_id):
    """{text: pins} a table may carry: its own entries plus the shared ones."""
    out = {}
    for key in ("*", table_id):
        for text, pins in (OCT_PROSE.get(key) or {}).values():
            out[text] = list(pins)
    return out


def _R(table_id, key):
    return OCT_PROSE[table_id][key][0]


_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
          6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
          11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
          15: "Fifteen", 16: "Sixteen"}

# What each timed query or operation asks, in plain words, keyed by the page's
# own column label with its statistic stripped. The sentence is generated
# from the table's columns, so a query added to a table describes itself and a
# query dropped from one stops being described: the September sentence said
# "three questions" under a five-query table.
QUERY_WORDS = {
    "l2olap": ("questions, each asked of the whole graph", "All times are milliseconds.", {
        "average friend age": "for every city, the average age of the friends of the people who live there",
        "friends in same city": "how many friendships connect two people in the same city",
        "most friends": "which people have the highest number of friends",
        "degree distribution": "how many people have each number of friends, counted over every edge in the graph",
        "triangle count": "how many sets of three people are all friends with one another, each triangle counted once",
        "LSQB Q1": "LSQB's first query, the eight-label chain: a country, a city in it, a person living there, a forum that person belongs to, a post in that forum, a comment replying to the post, the comment's tag, and the tag's class, every match counted",
        "LSQB Q2": "LSQB's second query: pairs of friends where one wrote a comment replying to a post the other wrote",
        "LSQB Q3": "LSQB's third query: three people who all live in the same country and are all friends with one another, each ordering counted",
        "LSQB Q4": "LSQB's fourth query: a tagged message with its creator, a person who liked it, and a comment replying to it, every combination counted",
        "LSQB Q5": "LSQB's fifth query: a tagged message and a reply to it carrying a different tag",
        "LSQB Q6": "LSQB's sixth query: a friend of a friend and that far person's tag interests, the two ends being different people",
        "LSQB Q7": "LSQB's seventh query, the fourth with the liker and the reply optional, so a tagged message with neither still counts once per creator",
        "LSQB Q8": "LSQB's eighth query, the fifth where the reply does not also carry the message's own tag",
        "LSQB Q9": "LSQB's ninth query, the sixth where the two people at the ends are not themselves friends",
    }),
    "docs_olap": ("analytical queries, each over the whole line-item table", "All times are milliseconds.", {
        "Q1": "TPC-H's own Q1, the pricing summary: it groups and aggregates every line item, so it measures a full scan",
        "Q6": "TPC-H's own Q6, the forecasting revenue change: it sums one column under a narrow filter, so it measures how well an engine skips what it does not need",
        "top parts": "the ten parts with the highest revenue, a group-by over every line item with a sort and a limit",
        "ship mode": "how many line items went by each ship mode, a group-by over the whole table",
        "by month": "revenue by month of shipment, a group-by on a date expression",
    }),
    "docs_oltp": ("transactional operations", "OLTP ops/s is the rate of the two TPC-C transactions together; the four single-record operations are timed one at a time.", {
        "new-order": "TPC-C's checkout transaction: it reads a customer and a warehouse, inserts an order with its line items, and updates stock, all in one transaction",
        "payment": "TPC-C's payment against one of the orders new-order just placed, chosen at random: the order is read, marked paid, and the payment inserted, in one transaction",
        "insert": "one record inserted by key",
        "read": "one record read back by key",
        "update": "one record's quantity updated by key",
        "delete": "one record deleted by key",
    }),
}


def _query_words_note(table):
    spec = QUERY_WORDS.get(table.get("id"))
    if not spec:
        return None
    kind, tail, words = spec
    labels = []
    for c in table.get("columns") or []:
        base = re.sub(r" p(50|99) ms$", "", str(c))
        if base in words and base not in labels:
            labels.append(base)
    if not labels:
        return None
    body = " ".join(f"{lbl[0].upper() + lbl[1:]}: {words[lbl]}." for lbl in labels)
    return _gen(f"{_WORDS.get(len(labels), str(len(labels)))} {kind}. {body} {tail}")


def _pg_memory_note(table):
    """PostgreSQL's memory cell, split into client and server from the row's
    own fields (client_peak_anon_mib, server_peak_anon_mib). The split was
    typed until 2026-09-16 and had drifted from the cell it sat under."""
    lane_wl = _TABLE_LANE.get(table.get("id"))
    if not lane_wl:
        return None
    lane, wl = lane_wl
    # The document lane's memory cell is the transactional run's on both
    # document tables (MEM_FIELDS in main: the lane merges workloads), so the
    # split must read the same rows the cell did.
    if lane == "l1tpc":
        wl = "oltp"
    pg = [e for e in table.get("entries", [])
          if e.get("backend") == display_name("postgres") and "peak memory GiB" in (e.get("metrics") or {})]
    if not pg:
        return None
    e = max(pg, key=lambda x: SCALE_ORDER.index(x["scale"]) if x["scale"] in SCALE_ORDER else -1)
    rs = [r for r in _FROZEN_ROWS if r.get("lane") == lane and (not wl or r.get("workload") == wl)
          and str(r.get("backend")) == "postgres" and str(r.get("scale")) == str(e["scale"])]
    client = [v for v in (_num(r.get("client_peak_anon_mib")) for r in rs) if v is not None]
    server = [v for v in (_num(r.get("server_peak_anon_mib")) for r in rs) if v is not None]
    head = ("PostgreSQL's memory cell is not comparable to the others: this column counts "
            "memory an engine holds in its own address space, and PostgreSQL holds its data "
            "in shared memory and the kernel's file cache instead")
    if not client or not server:
        return _gen(head + ", so most of what its cell shows is our own Python client rather than the database.")
    cell = f"{float(e['metrics']['peak memory GiB']['median']):.2f}"
    c, s = f"{statistics.median(client) / 1024:.3f}", f"{statistics.median(server) / 1024:.3f}"
    sl = e.get("scale_label") or scale_label(lane, e["scale"])
    return _gen(head + f". At {sl}, of the {cell} GiB shown, {c} GiB is our Python client and {s} GiB is the database.",
                cell, c, s, sl)


def _gav_pair_note(table):
    """Only when the table carries both arms of the ablation; a skeleton has
    the view-on rows alone and the September sentence described a pair that
    was not there."""
    names = {str(e["backend"]) for e in table.get("entries", [])}
    pairs = [(a, a[:-1] + ", GAV)") for a in sorted(names)
             if a.startswith("ArcadeDB (") and "GAV" not in a and (a[:-1] + ", GAV)") in names]
    if not pairs:
        return None
    listed = "; ".join(f"{a} and {b}" for a, b in pairs)
    return _gen(f"Each pair of rows labelled with and without GAV ({listed}) is the same engine on "
                f"the same data, differing only in whether that view is built; the answer check "
                f"confirms both return the same answers.", *[n for p in pairs for n in p])


def _gav_build_note(table):
    """September: the view build time, from the cell rather than typed (the
    literal 2.0 s sat under a cell reading 2.058)."""
    gav = [e for e in table.get("entries", [])
           if str(e.get("backend")) == "ArcadeDB (embedded, GAV)" and "view build s" in (e.get("metrics") or {})]
    if not gav:
        return None
    e = max(gav, key=lambda x: SCALE_ORDER.index(x["scale"]) if x["scale"] in SCALE_ORDER else -1)
    v = f"{float(e['metrics']['view build s']['median']):.1f}"
    sl = e.get("scale_label") or scale_label("l2", e["scale"])
    return _gen(f"The Graph Analytical View is a copy of the graph that ArcadeDB builds in memory, laid "
                f"out for questions that sweep the whole graph rather than follow a few links. Building "
                f"it took {v} seconds here at {sl}, once, before any query was timed.", v, sl)


def _dense_cold_warm_note(table):
    """September: what the cold and warm passes are, and how far each side
    moves between them, from the cells. The typed version said every
    comparator was within 3% of itself while SurrealDB's served 1M row moved
    from 1.5 s to 4 ms and Neo4j by a tenth (2026-09-16)."""
    ours, theirs = [], []
    for e in table.get("entries", []):
        m = e.get("metrics") or {}
        if "cold p50 ms" not in m or "warm p50 ms" not in m:
            continue
        c, w = float(m["cold p50 ms"]["median"]), float(m["warm p50 ms"]["median"])
        if not w:
            continue
        (ours if e.get("is_arcadedb") else theirs).append((abs(c - w) / w, c / w, e))
    if not ours or not theirs:
        return None
    a = f"{max(x[1] for x in ours):.1f}"
    worst = max(theirs, key=lambda x: x[0])
    # A change past 100% reads as a factor, not a percentage (SurrealDB's
    # served 1M row: a cold pass 378 times its warm one).
    pct = (f"a factor of {worst[1]:.0f}" if worst[0] >= 1 else f"{worst[0] * 100:.0f}%")
    who = f"{worst[2]['backend']} at {worst[2].get('scale_label') or worst[2].get('scale')}"
    rest = sorted(theirs, key=lambda x: x[0])[:-1]
    rest_pct = f"{max(x[0] for x in rest) * 100:.0f}" if rest else None
    tail = (f"; every other comparator is within {rest_pct}% of itself" if rest_pct else "")
    return _gen("Cold is the first timed pass after the index is built; warm is a repeat of the same "
                f"query set. ArcadeDB's cold pass is up to {a}x its warm one, because it pages its index "
                f"off disk while the others are resident from build. Among the comparators the largest "
                f"cold-to-warm change is {pct} ({who}){tail}.", a, pct, who, rest_pct)


def _ingest_split_note(table):
    """Which engines on the dense table have the ingest/index boundary and
    which build the index while ingesting, from the cells (DECISIONS #74)."""
    ents = table.get("entries", [])
    if not any("index s" in (e.get("metrics") or {}) for e in ents):
        return None
    lacking = sorted({str(e["backend"]) for e in ents if "index s" not in (e.get("metrics") or {})})
    mid = (f"{', '.join(lacking)} record one timer only, because the index is built while "
           f"ingesting or the adapter times no boundary, so their ingest s and index s are blank. "
           if lacking else "Every engine on this table has that boundary. ")
    return _gen("ingest s and index s are two timers where the engine has the boundary: inserting "
                "the vectors, then building the index. " + mid +
                "ingest+index total s is one timer around both, and ingest+index vectors/s divides "
                "the vector count by it.", *lacking)


def _reps_note(tables):
    """How many repetitions stand behind a printed cell, from the cells' own n."""
    ns = collections.Counter(int(stat.get("n") or 0) for t in tables for e in t.get("entries", [])
                             for stat in (e.get("metrics") or {}).values() if isinstance(stat, dict))
    n = ns.most_common(1)[0][0] if ns else None
    if not n:
        return None
    if n == 1:
        return _gen("Each printed cell here is ONE run, not the median of five, and the min and "
                    "max beside it are that same single sample. The campaign runs five and "
                    "prints the median; this page does not.")
    return _gen(f"Each printed cell is the median of {n} repetitions, with min and max carried "
                f"alongside; nothing here is a single sample.", str(n))


def _l4_lastpoint_note(rows):
    """September: the bounded/unbounded pair for the newest-reading query,
    from the rows (q_last_windowed_ms beside q_last_ms) rather than typed."""
    head = ("Newest reading means the most recent value each sensor has reported, which is what a "
            "monitoring dashboard asks for when it shows the current state of a fleet. TSBS calls "
            "this query last-point. It is run without a time bound; the same query bounded to the "
            "past hour is measured beside it and stays on the row")
    rs = [r for r in rows if r.get("lane") == "l4" and str(r.get("backend")) == "arcadedb_ts_native"
          and _num(r.get("q_last_windowed_ms")) is not None
          and (_num(r.get("q_last_unbounded_ms")) is not None or _num(r.get("q_last_ms")) is not None)]
    if not rs:
        return _gen(head + ".")
    w = statistics.median(_num(r.get("q_last_windowed_ms")) for r in rs)
    u = statistics.median((_num(r.get("q_last_unbounded_ms")) if _num(r.get("q_last_unbounded_ms")) is not None
                           else _num(r.get("q_last_ms"))) for r in rs)
    ws, us_ = f"{w:.3f}", f"{u:.3f}"
    return _gen(head + f" (ArcadeDB embedded, native time series: {ws} ms bounded against {us_} unbounded).",
                ws, us_)


def _oct_conditions(table):
    """The registered and generated sentences an October table carries beyond
    what its builder and main() already put there: (head, tail). The head
    goes right after the skeleton note when there is one."""
    tid = table.get("id")
    names = {str(e.get("backend")) for e in table.get("entries", [])}
    head, tail = [], [_R(tid, k) for k in OCT_TABLE_PROSE.get(tid, [])]
    q = _query_words_note(table)
    if q:
        head.append(q)
    if tid == "l3d":
        split = _ingest_split_note(table)
        if split:
            head.append(split)
        if any(c.startswith("cold ") for c in table.get("columns") or []):
            tail.insert(0, _R("l3d", "cold"))
        if any(n.startswith("ArangoDB") for n in names):
            tail.append(_R("l3d", "arango_ivf"))
        if any(n.startswith("Milvus") for n in names):
            tail.append(_R("l3d", "milvus"))
    if tid == "l3s":
        # The three multi-model engines with no sparse index type (DECISIONS
        # #92, #95): printed under the table and registered as whole-row
        # absences, so the coverage gate counts them declared and the
        # four-engine table reads "declared, cannot express" rather than
        # "no arm". October only, which is where this function runs.
        for engine, key in (("ArangoDB", "no_sparse_arangodb"),
                            ("MongoDB", "no_sparse_mongodb"),
                            ("SurrealDB", "no_sparse_surrealdb")):
            if any(n.startswith(engine) for n in names):
                continue      # an arm arrived; the declaration would be false
            why = _R("l3s", key)
            tail.append(why)
            _declare_absence("l3s", engine, None, "unexpressible", why)
    if tid == "lifecycle" and any("SurrealDB" in n for n in names):
        tail.append(_R("lifecycle", "surreal_rows"))
    if tid == "l2olap":
        pair = _gav_pair_note(table)
        if pair:
            tail.append(pair)
    if tid in ("docs_oltp", "docs_olap"):
        pg = _pg_memory_note(table)
        if pg:
            tail.append(pg)
    return head, tail


_TABLE_LANE = {
    "docs_oltp": ("l1tpc", "oltp"), "docs_olap": ("l1tpc", "olap"),
    "l2": ("l2", "oltp"), "l2olap": ("l2", "olap"),
    "l3d": ("l3d", None), "l3s": ("l3s", None), "l4": ("l4", None),
    "e2": ("e2", "hybrid"), "e2atom": ("e2", "atomicity"),
    # The lifecycle table was not here, so a lifecycle cell that exceeded its
    # budget would have left an engine off the table with no note, and the
    # coverage gate had no lane to read its fields from.
    "lifecycle": ("lifecycle", None),
}


def _table_scales(table_id):
    """The tiers a table prints (its spec's only_scales), or None for all.

    A note about a cell the table does not show is a note about nothing: the
    graph analytics table prints the LDBC slice and its notes named the micro
    generator's rows (2026-09-18)."""
    spec = LANES.get(table_id) or {}
    return spec.get("only_scales")

_CENSORED_CACHE = None


_CENSORED_PHASE = {}   # (lane, scale, backend, workload) -> phase phrase


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
    # THE LOG THIS PUBLISH IS BUILT FROM, not always the campaign's. A skeleton
    # reads its own results file (DECISIONS #86), and with this pinned to
    # runs.jsonl a laptop timeout left the engine off the table with no note at
    # all, which is exactly the gap-versus-censored confusion this function
    # exists to remove.
    path = HERE / "results" / os.environ.get("BENCH_RUNS_JSONL", "runs.jsonl")
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
                    # WHICH PHASE THE CAP INTERRUPTED, kept beside the seconds
                    # rather than folded into them, because the branch below
                    # tells a censored cell from a failed one by the TYPE of
                    # this value and changing that would silently reclassify
                    # every timeout as an error string.
                    _ph = _timeout_phase(r.get("timeout_phase_hint"))
                    if _ph:
                        _CENSORED_PHASE[key] = _ph
                elif r.get("oom_killed"):
                    # AN ENVELOPE FAILURE IS NOT A TIMEOUT (DECISIONS #103g).
                    # The cell was killed by the kernel at the memory cap; it
                    # did not run out of TIME, and "failed inside its budget"
                    # -- what the branch below would have said -- is false
                    # about it. `oom_killed` has been on 943 rows since the
                    # runner started setting it and nothing read it, so the
                    # classification fell through to parsing the error text,
                    # which for two of the three real cases is a phase marker
                    # or a log tail that tells a reader nothing.
                    _cap = str(r.get("mem_cap") or (f"{r.get('server_mem_cap_g')}g"
                                                    if r.get("server_mem_cap_g") else "") or "")
                    _peak = (r.get("peak_mib_sum") or r.get("client_peak_mib")
                             or r.get("server_peak_mib"))
                    timeouts[key] = ("envelope", _cap, _peak)
                else:
                    # A CELL THAT FAILED FOR ANOTHER REASON IS STILL A CENSORED
                    # OBSERVATION. 2026-09-14: the served SurrealDB cells at
                    # 9.99M built their index and then lost the connection
                    # mid-query, twice; a timeout-only rule left the page with
                    # no row and no note, which reads as a cell nobody ran.
                    # The reason is carried as a string so the note can say it.
                    timeouts[key] = err.strip().splitlines()[-1][:90] or "an error"
    _CENSORED_CACHE = {k: v for k, v in timeouts.items() if k not in clean}
    return _CENSORED_CACHE


_PHASE_WORDS = (
    # (match in the phase token, how the page says it). Ordered: the first
    # match wins, so "build-messages" is read as the build it is.
    ("ingest", "the ingest"),
    ("build", "the index build"),
    ("load", "the corpus load"),
    ("warmup", "the warm-up"),
    ("connect", "connecting to the engine"),
    ("close", "closing the database"),
)


def _timeout_phase(hint):
    """Which phase was running when the cap hit, as a phrase, or None.

    THE ROW HAS ALWAYS KNOWN AND THE PAGE NEVER SAID. `timeout_phase_hint` is
    the cell's last three PHASE markers, written by the runner since the
    cypherglot audit standard, and read by nothing -- so a censored cell said
    only "exceeded its budget", leaving a reader unable to tell an engine that
    spent two hours ingesting from one that reached the queries and stalled on
    the ninth. The two censored cells of the October campaign are exactly that
    pair: SurrealDB at 500k was `build-running t=7046.8s` and never queried,
    while ArcadeDB's graph analytics cell was on `olap-lsqb_q9-start` after
    lsqb_q8 returned a p50 of 77,857 ms.

    Returns None when the hint cannot be read, so the sentence simply omits
    the clause rather than guessing a phase.
    """
    text = str(hint or "")
    marks = re.findall(r"PHASE\s+([A-Za-z0-9_.-]+)", text)
    if not marks:
        return None
    last = marks[-1].lower()
    # a query phase names the query: "olap-lsqb_q9-start", "search-q_high-done"
    q = re.match(r"^(?:olap|oltp|search|hybrid|ts)-([a-z0-9_]+?)-(?:start|done|censored|abandoned)$", last)
    if q:
        return f"query {q.group(1)}"
    for needle, phrase in _PHASE_WORDS:
        if needle in last:
            return phrase
    return None


# DECISIONS #111: a censored engine keeps its row and prints its outcome in
# the cell. The classification lives HERE, once, and both the note and the
# mark read it -- writing the same three-way test twice is how a note and a
# cell end up disagreeing about what happened to one run.
def _outcome_kind(secs):
    """(kind, mark) for a value out of _censored_cells()."""
    if isinstance(secs, tuple) and secs and secs[0] == "envelope":
        return "envelope", "OOM"
    if isinstance(secs, int) or secs is None:
        return "censored", _cap_label(secs)
    text = str(secs).lower()
    if "connection" in text or "closed" in text or "reset" in text:
        return "failed", "lost"
    return "failed", "err"


def _cap_label(secs):
    """`>2h` from 7200. The cap is a property of the TIER and identical for
    every engine on it, which is what makes the bound comparable along a row;
    it ranges from 15 minutes to 48 hours, so it is derived and never typed."""
    if not secs:
        return ">cap"
    secs = int(secs)
    if secs % 3600 == 0:
        return f">{secs // 3600}h"
    return f">{secs // 60}m"


# The legend is BUILT FROM THE MARKS PRESENT and refuses one it cannot
# define, which is the trap the capability table's legend fell into: a typed
# tuple of three kinds, and a fourth printed into the cells with nothing
# explaining it (BUGS F76's sibling).
_MARK_MEANINGS = {
    "OOM": "killed at the cell's memory envelope rather than running out of time",
    "lost": "the connection dropped mid-query",
    "err": "the cell failed inside its budget; the note says what it reported",
}


def _mark_legend(marks):
    if not marks:
        return []
    parts = []
    # THE CAP MARKS SHARE ONE ENTRY. A table carrying two sizes carries two
    # caps, and listing `>4h` and `>8h` separately printed the same sentence
    # twice; the marks differ because the TIERS do, which is the thing worth
    # saying, and the cap is identical for every engine at a tier.
    caps = sorted((m for m in marks if m.startswith(">")),
                  key=lambda m: (m.endswith("m"), int(m[1:-1])))
    if caps:
        parts.append(", ".join(f"`{c}`" for c in caps)
                     + " the cell ran past its tier's cap and was not retried"
                     + (" (each tier has its own cap, the same for every engine on it)"
                        if len(caps) > 1 else ""))
    for m in sorted(m for m in marks if not m.startswith(">")):
        if m not in _MARK_MEANINGS:
            raise SystemExit(f"export_web: no legend defined for the cell mark {m!r}; "
                             f"a mark the table cannot define must not reach a reader")
        parts.append(f"`{m}` {_MARK_MEANINGS[m]}")
    return [_gen("In the cells: " + "; ".join(parts) + ". A dash is an operation the "
                 "engine cannot express, never a slow one.", *sorted(marks))]


def _censored_entries(table):
    """Rows for the engines whose cell did not finish (DECISIONS #111).

    They carry `outcome` and text-only metrics, so everything that counts a
    MEASUREMENT must skip them -- a mark is a statement about a run, not a
    number. `page_check` skips a metric with no median for the same reason.
    """
    lane_wl = _TABLE_LANE.get(table.get("id"))
    if not lane_wl:
        return [], set()
    lane, wl = lane_wl
    scales = _table_scales(table.get("id"))
    cols = list(table.get("columns") or [])
    # A MARK KEEPS A COMPARISON COMPLETE, SO IT NEEDS A COMPARISON TO JOIN.
    # Found on the publish diff, 2026-09-21: docs_olap withholds its SF10 row
    # group under #103b -- DuckDB and both PostgreSQL arms MEASURED there and
    # are not printed -- so adding the five censored SF10 rows gave the page a
    # size at which every engine failed, hiding that three had succeeded. That
    # is the same distortion as a vanished row, pointing the other way. A
    # scale the table prints no measured row at stays as it was: explained in
    # the note, absent from the table.
    measured_scales = {str(e.get("scale")) for e in table.get("entries") or []
                       if not e.get("outcome")}
    out, marks = [], set()
    for (l, scale, backend, w), secs in sorted(_censored_cells().items(), key=str):
        if l != lane or (wl and w != wl):
            continue
        if scales and str(scale) not in scales:
            continue
        if str(scale) not in measured_scales:
            continue
        kind, mark = _outcome_kind(secs)
        marks.add(mark)
        # THE SAME SHAPE AS A MEASURED ROW, so nothing that walks entries
        # trips over a key that is not there; `outcome` is what tells the
        # consumers that care this row is a statement and not a number.
        out.append({"backend": display_name(backend), "backend_key": backend,
                    "is_arcadedb": "arcadedb" in str(backend).lower(),
                    "precision": None, "scale": scale,
                    "scale_label": scale_label(lane, scale), "workload": w,
                    "n_docs": None,
                    "deployment": "server" if str(backend).endswith("_server") else "embedded",
                    "image": None, "version_name": None, "host": None,
                    "outcome": kind,
                    "metrics": {c: {"text": mark} for c in cols}})
    return out, marks


def _censored_notes(table_id):
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    lane, wl = lane_wl
    notes = []
    merged = {}
    scales = _table_scales(table_id)
    for (l, scale, backend, w), secs in sorted(_censored_cells().items(), key=str):
        if l != lane or (wl and w != wl):
            continue
        if scales and str(scale) not in scales:
            continue
        what = {"oltp": "transaction", "olap": "analytics", "hybrid": "transaction",
                "atomicity": "atomicity", "search": "search", "ingest": "ingest"}.get(w, w or "the")
        # TWO OUTCOMES, WORDED DIFFERENTLY (PAGE-SPEC, "a cell with no row is
        # accounted for by outcome"). An int (or None) in _censored_cells is a
        # cell that ran past the tier's cap; anything else is what the cell
        # reported when it failed inside its budget, and a lost connection
        # must not read as slowness.
        kind, _ = _outcome_kind(secs)
        if kind == "envelope":
            _, _cap, _peak = secs
            _cap_txt = f"{_cap} memory envelope" if _cap else "cell's memory envelope"
            _peak_txt = f" (peak {_peak:,.0f} MiB)" if isinstance(_peak, (int, float)) else ""
            # EVERY DIGIT IN THE SENTENCE IS PINNED TO ITS SOURCE, including
            # the peak. page_check refuses an unpinned number in a generated
            # condition, and the peak comes off the row the same way the
            # envelope does -- passing one and not the other is how a real
            # number ends up looking typed.
            tail = (f" at {scale_label(lane, scale)}: the {what} cell reached "
                    f"the {_cap_txt}{_peak_txt} and was killed by the kernel, the same envelope every "
                    f"engine on this table had; it did not run out of time, and there is no row.")
            # EVERY DIGIT IN THE SENTENCE IS PINNED TO ITS SOURCE, including
            # the peak. page_check refuses an unpinned number in a generated
            # condition, and the peak comes off the row the same way the
            # envelope does -- passing one and not the other is how a real
            # number ends up looking typed.
            pins = [scale_label(lane, scale), _cap_txt,
                    _peak_txt.strip(" ()").replace("peak ", "") if _peak_txt else None]
        elif kind == "censored":
            budget = f"{secs / 3600:g} hour" if secs else "its"
            _phase = _CENSORED_PHASE.get((lane, str(scale), backend, w))
            _in = f" It was still in {_phase} when the budget ran out." if _phase else ""
            tail = (f" at {scale_label(lane, scale)}: the {what} cell exceeded "
                    f"its {budget} budget, the same budget every engine on this table had, on its first "
                    f"attempt and was not retried; there is no row.{_in}")
            pins = [scale_label(lane, scale), budget]
        else:
            tail = (f" at {scale_label(lane, scale)}: the {what} cell failed "
                    f"inside its budget and was not retried, so there is no row. What it reported: "
                    f"{secs}")
            pins = [scale_label(lane, scale), str(secs)]
        merged.setdefault((kind, tail, tuple(pins)), []).append(display_name(backend))

    # ONE SENTENCE FOR THE ENGINES THAT HAVE THE SAME THING TO SAY. Three
    # engines were censored at TPC-H SF10 and the page printed three sentences
    # that differed in one word each, which is a loop's output and reads like
    # one. Merged only where the wording is otherwise IDENTICAL, so an
    # envelope failure keeps its own peak and a failed cell keeps its own
    # reported line; those never collapse, and should not.
    for (kind, tail, pins), engines in sorted(merged.items(), key=str):
        if len(engines) == 1:
            who = engines[0]
        elif len(engines) == 2:
            who = f"{engines[0]} and {engines[1]}"
        else:
            who = ", ".join(engines[:-1]) + f" and {engines[-1]}"
        why = _gen(who + tail, who, *[p for p in pins if p is not None])
        notes.append(why)
        for e in engines:
            _declare_absence(table_id, e, None, kind, why)
    return notes


# A QUERY THAT EXCEEDED ITS BUDGET, NAMED ON THE TABLE (DECISIONS #82b, #100).
#
# _censored_notes above is the WHOLE-CELL case: a timeout, no row. This is the
# per-query case the graph lane's OLAP budget and the time-series lane's query
# budget produce: the loop stopped at the budget, the row carries a p50 over
# the iterations it took (the cold pass always runs, so there is at least one)
# and says so in <q>_censored, <q>_budget_s and <q>_iters (the time-series
# lane adds <q>_elapsed_s). The cell keeps its number; what the table owed and
# did not print until 2026-09-15 is the sentence beside the counts note that
# says which cells did NOT run the hundred iterations it announces -- three
# skeleton triangle counts stood at 16, 5 and 18 iterations under a note that
# said 100. Not a declared absence: the coverage gate reads absences as blanks
# and this cell is not blank.
#
#   table id -> (lane, workload, {query field stem: column label},
#                (lane module, iteration constant), what <q>_iters counts)
# The graph lane times its cold pass OUTSIDE the warm loop, so its <q>_iters
# is the warm count and its p50 is over warm samples; the time-series lane's
# first iteration IS the cold pass and is inside the count. The sentence has
# to say which, or "5 of 100" reads as five warm samples on one lane and four
# on the other.
_QUERY_BUDGET_TABLES = {
    "docs_olap": ("l1tpc", "olap", {
        "q1": "Q1", "q6": "Q6", "top_parts": "top parts", "ship_mode": "ship mode",
        "by_month": "by month"}, ("l1_tpc", "OLAP_ITER"),
        "iterations, the first of which is the cold pass"),
    "l2olap": ("l2", "olap", {
        "friend_age_by_city": "average friend age", "same_city_edges": "friends in same city",
        "top_degree": "most friends", "degree_dist": "degree distribution",
        "triangles": "triangle count",
        "lsqb_q1": "LSQB Q1", "lsqb_q2": "LSQB Q2", "lsqb_q3": "LSQB Q3", "lsqb_q4": "LSQB Q4", "lsqb_q5": "LSQB Q5", "lsqb_q6": "LSQB Q6", "lsqb_q7": "LSQB Q7", "lsqb_q8": "LSQB Q8", "lsqb_q9": "LSQB Q9"}, ("graph_common", "OLAP_ITERATIONS"),
        "warm iterations after the cold pass"),
    "l4": ("l4", None, {
        "q_last": "newest reading", "q_range": "one-hour range", "q_global": "12h aggregate",
        "q_groupby": "per-host hourly", "q_high": "high-usage",
        "q_orderlimit": "grouped, ordered, limited"}, ("l4_tsbs", "QITER"),
        "iterations, the first of which is the cold pass"),
}


def _row_label_for(table_id, r):
    """The label this table gives the row's engine, for a sentence about it."""
    backend = str(r.get("backend") or "")
    if table_id == "l4":
        return L4_CANON_LABELS.get(backend, display_name(backend))
    label = display_name(backend)
    if table_id == "l2olap" and str(r.get("gav")) != "False" and "arcade" in backend:
        label = f"{label[:-1]}, GAV)" if label.endswith(")") else f"{label} (GAV)"
    return label


def _query_budget_notes(table_id):
    spec = _QUERY_BUDGET_TABLES.get(table_id)
    if not spec:
        return []
    lane, wl, labels, (mod, const), counted = spec
    # The asked count comes from the lane module the runner executes, like
    # _counts_note's, so the two sentences cannot disagree.
    try:
        import importlib
        asked = int(getattr(importlib.import_module(mod), const))
    except Exception:  # noqa: BLE001 - the lane module is optional here
        asked = None
    # (label, scale, query) -> [(iters, elapsed_s, budget_s)] across reps
    hits = collections.defaultdict(list)
    scales = _table_scales(table_id)
    for r in _FROZEN_ROWS:
        if r.get("lane") != lane or (wl and r.get("workload") != wl):
            continue
        if scales and str(r.get("scale")) not in scales:
            continue
        for q, col in labels.items():
            if str(r.get(f"{q}_censored") or "").strip().lower() != "true":
                continue
            try:
                iters = int(float(r.get(f"{q}_iters") or 0))
                budget = float(r.get(f"{q}_budget_s") or 0)
            except ValueError:
                continue
            el = r.get(f"{q}_elapsed_s")
            hits[(_row_label_for(table_id, r), str(r.get("scale")), col)].append(
                (iters, float(el) if el not in (None, "") else None, budget))
    # ONE SENTENCE PER ENGINE, NOT PER QUERY. This emitted a separate
    # sentence for every censored (engine, query) pair, so MongoDB alone
    # printed nine of them differing in two tokens each -- forty-four under
    # one table on the preview. A loop's output reads like a loop's output,
    # and nobody writes the same clause nine times. The shared half (the
    # budget, what the percentiles are over, what happens to the other
    # queries) is stated ONCE for the table; each engine then gets one line
    # naming its queries and how far each got.
    by_engine = collections.defaultdict(list)
    for (label, scale, col), occ in sorted(hits.items(), key=str):
        by_engine[(label, scale)].append((col, occ))
    if not by_engine:
        return []

    budgets = {o[2] for occs in hits.values() for o in occs}
    one_budget = budgets.pop() if len(budgets) == 1 else None
    total = sum(len(v) for v in by_engine.values())

    def _span(occ):
        its = sorted(o[0] for o in occ)
        span = f"{its[0]}" if its[0] == its[-1] else f"{its[0]} to {its[-1]}"
        els = [o[1] for o in occ if o[1] is not None]
        reached = (f", reaching {min(els):.0f} s" if len(els) == 1 or min(els) == max(els)
                   else f", reaching {min(els):.0f} to {max(els):.0f} s") if els else ""
        return span, reached

    notes = []
    of = f" of {asked}" if asked else ""
    lead = (f"{total} query cells on this table stopped at "
            + (f"the {one_budget:g} s budget every engine here is given"
               if one_budget else "their per-query budget, the same for every engine here")
            # "over THOSE <counted>" and not "over the <counted> it reached":
            # `counted` is a noun phrase that already carries its own clause on
            # the document table ("iterations, the first of which is the cold
            # pass"), and anything appended to it lands inside that clause.
            + f"; each one's p50 and p99 are over those {counted}, and every "
              f"other query in those cells keeps its numbers.")
    notes.append(_gen(lead, str(total),
                      f"{one_budget:g} s budget" if one_budget else "per-query budget"))

    for (label, scale), cols in sorted(by_engine.items(), key=str):
        parts, first = [], True
        for col, occ in cols:
            span, reached = _span(occ)
            # "of 100 iterations" once, on the first query; the rest are bare
            # counts against the same denominator.
            parts.append(f"{col} ({span}{of if first else ''}"
                         + (" iterations" if first else "") + f"{reached})")
            first = False
        notes.append(_gen(f"{label} at {scale_label(lane, scale)}: "
                          + ", ".join(parts) + ".",
                          label, scale_label(lane, scale), ", ".join(parts)))
    return notes


def _mutation_note(rows):
    """Which dense tiers ran the two maintenance operations, and which did not.

    #82d runs them at one tier, so on any other tier the four maintenance
    columns are blank. A blank with no sentence beside it is what #89 forbids,
    and it is also how a reader concludes an engine failed the operation when
    the operation was never asked for. Read from the rows' own mutate_ran and
    mutate_reason rather than from the tier list here, so a forced run
    (BENCH_DENSE_MUTATE=1) describes itself.
    """
    ran, skipped = {}, {}
    for r in rows:
        if r.get("lane") != "l3d":
            continue
        sc = str(r.get("scale"))
        flag = str(r.get("mutate_ran")).lower() in ("true", "1")
        why = str(r.get("mutate_reason") or "").strip()
        (ran if flag else skipped)[sc] = why
    if not ran and not skipped:
        return None
    parts = []
    if ran:
        parts.append("The insert and delete into a built index, and the recall "
                     "after each, run at " + ", ".join(scale_label("l3d", s) for s in sorted(ran))
                     + " (" + "; ".join(sorted(set(ran.values()))) + ").")
    if skipped:
        parts.append("They do not run at " + ", ".join(scale_label("l3d", s) for s in sorted(skipped))
                     + ", where those four columns are blank because the pass was "
                       "not asked for rather than because an engine failed it ("
                     + "; ".join(sorted(set(w for w in skipped.values() if w))) + ").")
    # WHAT THE MUTATION COLUMNS ARE COMPARING, which is not one thing. Most
    # dense engines patch their graph incrementally on insert; ArcadeDB's
    # LSM_VECTOR buffers into a delta and rebuilds the WHOLE graph from
    # scratch when a trigger fires -- the counter is incremented inside
    # buildGraphFromScratchExclusively, read at the pin. So "insert into index
    # ms/vector" can be a thousand nodes touched on one engine and a million
    # on another, and a reader comparing 0.026 against 8.7 ms/vector without
    # that is comparing two different amounts of work.
    #
    # Generated from the rows' own engine counters, never from a list here: an
    # engine that rebuilds says so because ITS stats say so. Omitted entirely
    # when no row carries the counter -- rows measured before
    # engine_stats_after_mutate existed, or engines exposing no such metric --
    # so silence means "not recorded", never "did not rebuild".
    _rb = _mutation_rebuilds(rows)
    if _rb:
        _said = []
        for _b, _n, _d in _rb:
            if _n > 0:
                _said.append("%s rebuilt its whole graph %d time%s to absorb them"
                             % (display_name(_b), _n, "" if _n == 1 else "s"))
            else:
                _said.append("%s left %s of them in its delta buffer, to be merged by a "
                             "later full rebuild this cell does not pay for"
                             % (display_name(_b), f"{_d:,}"))
        parts.append(
            "These engines do not all maintain an index the same way: "
            + "; ".join(_said)
            + ". A full rebuild touches every vector in the index and an incremental "
              "insert touches only the new ones, so the per-vector costs here price "
              "different amounts of work and are not a straight speed comparison.")
    return _gen(" ".join(parts),
                *[scale_label("l3d", s) for s in sorted(set(ran) | set(skipped))],
                *sorted(set(ran.values()) | set(skipped.values())),
                *[str(v) for _b, _n, _d in (_rb or ()) for v in (_n, f"{_d:,}") if v])


def _stats_int(row, field, key):
    """One integer out of an engine_stats_* cell, whatever shape it arrives in."""
    raw = row.get(field)
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        d = raw
    else:
        try:
            d = _ast.literal_eval(str(raw))
        except (ValueError, SyntaxError):
            return None
    if not isinstance(d, dict):
        return None
    try:
        return int(d.get(key))
    except (TypeError, ValueError):
        return None


def _mutation_rebuilds(rows):
    """[(backend, rebuilds, vectors left in the delta)], from the rows.

    REPORTING ONLY REBUILDS WOULD BE SILENT WHERE IT MATTERS MOST. The rebuild
    threshold at the pin is max(100, min(graphSize * 0.2, 50_000)), so the
    1,000 deletes and 1,000 re-inserts of the mutation pass cross it at 5,000
    vectors (threshold 1,000, and a micro cell showed exactly two rebuilds)
    and come nowhere near it at the 1M tier the page publishes (threshold
    50,000). At 1M the work is DEFERRED into the delta buffer instead -- which
    is precisely the case a reader needs told, and a rebuild-only sentence
    would say nothing about it.

    So both halves are reported: what a rebuild absorbed, and what is still
    pending. An engine appears if either is positive; an engine whose counters
    are absent does not appear at all, because silence must read as "not
    recorded" rather than "nothing happened".
    """
    best = {}
    for r in rows:
        if r.get("lane") != "l3d":
            continue
        if str(r.get("mutate_ran", "")).lower() not in ("true", "1"):
            continue
        before = _stats_int(r, "engine_stats_after_build", "graphRebuildCount")
        after = _stats_int(r, "engine_stats_after_mutate", "graphRebuildCount")
        delta = _stats_int(r, "engine_stats_after_mutate", "deltaVectorsCount")
        if after is None and delta is None:
            continue
        rebuilds = (after - before) if (before is not None and after is not None) else 0
        b = str(r.get("backend"))
        prev = best.get(b, (0, 0))
        best[b] = (max(rebuilds, prev[0]), max(delta or 0, prev[1]))
    return sorted((b, n, d) for b, (n, d) in best.items() if n > 0 or d > 0)


_UNEXPRESSIBLE_CACHE = None


def _unexpressible_cells():
    """(lane, workload, backend) -> {query key: reason}, from the rows.

    DECISIONS #88 makes an adapter DECLARE a query it cannot ask rather than
    skip it, and the declaration lands on the row as
    `res_<query>_digest = unexpressible:<reason>`. The page has always shown
    the sentence; this is the same fact as data, so the coverage gate can tell
    a declared absence from a column nobody noticed had stopped being
    measured. Reads the log the publish is built from, like _censored_cells.
    """
    global _UNEXPRESSIBLE_CACHE
    if _UNEXPRESSIBLE_CACHE is not None:
        return _UNEXPRESSIBLE_CACHE
    import bench_common
    out = collections.defaultdict(dict)
    path = HERE / "results" / os.environ.get("BENCH_RUNS_JSONL", "runs.jsonl")
    if path.exists():
        with open(path) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                for field, value in r.items():
                    m = re.match(r"^res_(.+)_digest$", str(field))
                    if m and bench_common.is_unexpressible(value):
                        key = (r.get("lane"), r.get("workload"), str(r.get("backend")))
                        out[key][m.group(1)] = str(value).split(":", 1)[-1].strip()
    _UNEXPRESSIBLE_CACHE = out
    return out


def _unexpressible_notes(table_id, entries):
    """One sentence per engine that declared it cannot ask a query here, and
    the same fact registered as a structured absence."""
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    lane, wl = lane_wl
    notes = []
    for (l, w, backend), queries in sorted(_unexpressible_cells().items(), key=str):
        if l != lane or (wl and w != wl):
            continue
        name = display_name(backend)
        if not any(str(e.get("backend")) == name for e in entries):
            continue
        for query, reason in sorted(queries.items()):
            why = _gen(f"{name} does not answer {query} on this table: the engine's "
                       f"own language cannot express it, declared by the adapter "
                       f"rather than left blank ({reason}).", name, query, reason)
            notes.append(why)
            rec = {"backend": name, "column": None, "kind": "unexpressible",
                   "query": query, "why": why}
            if rec not in _DECLARED_ABSENCES[table_id]:
                _DECLARED_ABSENCES[table_id].append(rec)
    return notes


def _zero_growth_notes(table_id):
    """One sentence per served row whose server container did not grow at all.

    A served row's disk cell is the server container's growth over its empty
    footprint (_disk_data). A growth of exactly zero after a corpus was loaded
    is not a size, it is a floor: verified 2026-09-15 on SurrealDB 3.2.4, whose
    RocksDB store preallocates a write-ahead log of about 70 MB at start (the
    74.4 MB baseline is that log plus its manifest files), so 100,000 inserted
    rows changed the container's SizeRw by zero bytes and only the tiers whose
    corpus exceeds the memtable flush to segment files that count. Printing
    0.0 GiB with no sentence would read as "stores nothing".
    """
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    lane_of_table, wl = lane_wl
    hits = []
    for r in _FROZEN_ROWS:
        if not r.get("server_image") or r.get("lane") != lane_of_table:
            continue
        if wl and r.get("workload") != wl:
            continue
        try:
            sv = float(r.get("server_disk_mb") or "")
            sb = float(r.get("server_disk_baseline_mb") or 0.0)
        except (TypeError, ValueError):
            continue
        if abs(sv - sb) >= 0.05:
            continue
        label = _row_label_for(table_id, r)
        if label is None:
            continue
        key = (label, str(r.get("scale")), r.get("lane"), sb)
        if key not in hits:
            hits.append(key)
    notes = []
    for label, scale, lane, sb in sorted(hits, key=str):
        try:
            sl = scale_label(lane, scale)
        except Exception:  # noqa: BLE001 - a lane whose tier the map does not name
            continue
        mb, gib = f"{sb:.0f}", f"{sb / 1024:.2f}"
        notes.append(_gen(
            f"{label} at {sl}: its disk cell is 0.0 because the server container did not "
            f"grow over its empty footprint during the run, which for SurrealDB's server "
            f"includes a preallocated write-ahead log of about {mb} MB that the whole corpus "
            f"fits inside at this size; read the cell as a floor under {gib} GiB, not as a size.",
            label, sl, "0.0", mb, gib))
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
        n, c = f"{L['l1_tpc'].OLTP_OPS:,}", f"{L['l1_tpc'].CRUD_OPS:,}"
        if _instrument_of("l1tpc") == "2026-10":
            return [_gen(f"Each repetition runs {n} new-order transactions and {n} payments, then {c} each of the single-record insert, read, update, and delete; the p50 and p99 are over those, and OLTP ops/s is the rate of the two transactions together.", n, c)]
        return [_gen(f"Each repetition runs {n} new-order transactions; the p50 and p99 are over those, and OLTP ops/s is their rate.", n)]
    if table_id == "docs_olap":
        n = str(L['l1_tpc'].OLAP_ITER)
        return [_gen(f"Each repetition runs every query {n} times; the p50 and p99 are over those runs.", n)]
    if table_id == "l2":
        q = {sc: L["graph_common"].SCALE_OLTP_QUERIES.get(sc) for sc in scales}
        try:
            import ldbc_snb
            q = {sc: (q[sc] or getattr(ldbc_snb, "SCALE_OLTP_QUERIES", {}).get(sc)) for sc in scales}
        except Exception:  # noqa: BLE001
            pass
        parts = ", ".join(f"{scale_label('l2', sc)}: {n:,}" for sc, n in q.items() if n)
        if not parts:
            return []
        # The write count from the rows (write_ops, update_ops, delete_ops),
        # not typed: it was "up to 1,000" here while the lane read CRUD_OPS.
        writes = {}
        for f in ("write_ops", "update_ops", "delete_ops"):
            vals = [_num(r.get(f)) for r in _FROZEN_ROWS
                    if r.get("lane") == "l2" and r.get("workload") == "oltp" and _num(r.get(f)) is not None]
            if vals:
                writes[f] = int(max(vals))
        if writes and len(set(writes.values())) == 1 and len(writes) == 3:
            w = f"{writes['write_ops']:,}"
            return [_gen(f"Each repetition runs every read against a fresh set of start persons ({parts}) and {w} each of the insert, update, and delete; the p50 and p99 are over those.", parts, w)]
        w = f"{writes.get('write_ops', 0):,}" if writes.get("write_ops") else None
        if w:
            return [_gen(f"Each repetition runs every read against a fresh set of start persons ({parts}) and commits up to {w} writes; the p50 and p99 are over those.", parts, w)]
        return [_gen(f"Each repetition runs every read against a fresh set of start persons ({parts}); the p50 and p99 are over those.", parts)]
    if table_id == "l2olap":
        n = str(L['graph_common'].OLAP_ITERATIONS)
        return [_gen(f"Each repetition runs every query {n} times; the p50 and p99 are over those runs.", n)]
    if table_id in ("l3d", "l3s"):
        n = f"{L['l3d_dense'].N_QUERIES:,}"
        if not any("warm p50 ms" in (e.get("metrics") or {}) for e in entries):
            # No second pass on this table (a skeleton, or a table before its
            # multipass overlay lands): the sentence must not describe one.
            return [_gen(f"Each timed pass answers {n} queries.", n)]
        builds = collections.Counter(int(st.get("n") or 0) for e in entries
                                     for st in (e.get("metrics") or {}).values() if isinstance(st, dict))
        b = builds.most_common(1)[0][0] if builds else None
        try:
            k = int(importlib.import_module("dense_multipass_driver").PASSES) - 1
        except Exception:  # noqa: BLE001 - the driver is a bench-host script
            k = None
        warm = (f"warm pools the {_WORDS.get(k, str(k)).lower()} passes after it" if k
                else "warm pools the passes after it")
        over = f", over {_WORDS.get(b, str(b)).lower()} builds" if b else ""
        return [_gen(f"Each pass answers {n} queries; cold is the first pass after the build and {warm}{over}.", n, str(k or ""), str(b or ""))]
    if table_id == "l4":
        n = str(L['l4_tsbs'].QITER)
        return [_gen(f"Each repetition runs every query {n} times; the p50 and p99 are over those runs.", n)]
    if table_id == "e2":
        n = str(L['e2_hybrid'].OPS)
        return [_gen(f"Each repetition runs the transaction {n} times; the p50 and p99 are over those.", n)]
    return []


def _withheld_recall_notes(table_id):
    """One sentence per approximate-search cell the freeze withheld for a recall
    below make_paper_tables.RECALL_FLOOR (the sidecar it writes). The cell's
    absence is said under the table rather than left as a missing row."""
    if table_id not in ("l3d", "l3s"):
        return []
    path = GENERATED / "withheld_recall.json"
    try:
        items = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    lane = table_id
    seen = {}
    for it in items:
        if it.get("lane") != lane:
            continue
        key = (str(it.get("backend")), str(it.get("scale")))
        seen.setdefault(key, []).append(float(it.get("recall_at_10") or 0.0))
    notes = []
    for (backend, scale), recs in sorted(seen.items()):
        label = display_name(backend)
        try:
            size = scale_label(lane, scale)
        except Exception:  # noqa: BLE001
            size = scale
        # THROUGH _gen, not as a bare f-string. This sentence's recall and
        # repetition count come from the rows, so it is a GENERATED sentence
        # and has to declare itself as one: the condition gate reads an
        # unregistered sentence as typed and fails every number in it as
        # UNPINNED, which is what it did the moment this generator (main) met
        # the condition-source rule (october-instrument) in one tree.
        notes.append(_gen(
            f"{label} at {size} is withheld: its search answered with a recall@10 of "
            f"{max(recs):.4f} across {len(recs)} repetition(s), which is not a measurement of "
            f"search but of a broken index, so its latency is not printed beside engines "
            f"answering correctly. The cause is investigated on the bench host before anything "
            f"is claimed about it (BUGS F55).",
            label, size, f"{max(recs):.4f}", str(len(recs))))
    return notes


def _finish_table(table: dict) -> dict:
    table["instrument"] = _table_instrument(table.get("id"))
    october = table["instrument"] == "2026-10"
    base = list(table.get("conditions") or [])
    if october:
        head, tail = _oct_conditions(table)
        at = 1 if base and base[0] == SKELETON_TABLE_NOTE else 0
        base = base[:at] + head + base[at:] + tail
    else:
        # September's generated replacements for two typed numbers: the
        # PostgreSQL client/server split and the view build time.
        for note in (_pg_memory_note(table) if table.get("id") in ("docs_oltp", "docs_olap") else None,
                     _gav_build_note(table) if table.get("id") == "l2olap" else None,
                     _dense_cold_warm_note(table) if table.get("id") == "l3d" else None):
            if note:
                base.append(note)
    table["conditions"] = (base
                           + _counts_note(table.get("id"), table.get("entries", []))
                           + _censored_notes(table.get("id"))
                           + _query_budget_notes(table.get("id"))
                           + _zero_growth_notes(table.get("id"))
                           + _unexpressible_notes(table.get("id"), table.get("entries", []))
                           + _withheld_recall_notes(table.get("id")))
    # DECISIONS #111. Added AFTER every note and number is computed, so
    # nothing that averages, ranks or counts a measurement can see them.
    _marked, _marks = _censored_entries(table)
    if _marked:
        table["conditions"] = table["conditions"] + _mark_legend(_marks)
    entries = table["entries"] + _marked
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
    # A MARK IS NOT A VALUE. Without the outcome filter a column that only
    # censored rows carry would print as a column of `>2h` and nothing else,
    # which is a column the campaign never measured (DECISIONS #111).
    present = {m for e in table["entries"] if not e.get("outcome")
               for m, v in e.get("metrics", {}).items() if v is not None}
    table["columns"] = [c for c in cols if c in present]
    note = ((OCT_PROSE.get(table["id"]) or {}).get("ingest", (None,))[0] if october
            else INGEST_NOTES.get(table["id"]))
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
    # Every absence this table declares, as data (page_check.OPERATION_MANIFEST
    # reads it). Written after the notes above, because the notes are what
    # register them.
    table["declared_absences"] = list(_DECLARED_ABSENCES.get(table["id"], []))
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
    # The development machine. It publishes nothing but the skeleton
    # (DECISIONS #86), and the skeleton's own banner says so on every table.
    "laptop": {
        "cpu": "Intel Core Ultra X9 388H, 16 cores, 16 threads, 18 MiB L3",
        "memory": "30 GiB",
        "storage": "NVMe",
        "os": "Ubuntu 26.04 LTS, Linux 7.0, Docker 29",
    },
}


# The machine the published rows ran on, READ FROM THE ROWS since 2026-10
# (DECISIONS #74 item 3): every row records bench_host. It was typed as "mini"
# while no lane stamped the host, which is also why the skeleton could not
# have been published honestly before. A payload whose rows disagree about the
# host names them all; one with no bench_host at all (a September freeze)
# falls back to the machine every September row ran on.
PAGE_HOST = "mini"


def _page_hosts(rows):
    named = sorted({str(r.get("bench_host")).strip() for r in rows
                    if str(r.get("bench_host") or "").strip()})
    return named or [PAGE_HOST]


def _host_hardware(hosts, rows=()):
    named = sorted({h for h in hosts if h and not str(h).startswith("container:")}
                   | set(_page_hosts(rows)))
    missing = [h for h in named if h not in HOST_HARDWARE]
    if missing:
        raise SystemExit(f"rows name a host with no HOST_HARDWARE entry: {missing}")
    return {h: HOST_HARDWARE[h] for h in named}


def _dense_columns(spec, src_lane):
    """The dense table's column list, with the warm pair kept beside the cold.

    Warm and gain come from the multipass overlay rather than from the lane,
    so they are not in any metrics list and have always been spliced in here.
    Under the October instrument the rest of the list is OCT_TABLE_METRICS,
    which adds the ingest and index timers as two columns (DECISIONS #74) and
    the search-after-insert and search-after-delete passes (#82d); a skeleton
    has no overlay, so the warm columns render empty and the banner names them
    as a table the skeleton cannot draw.
    """
    cols = [label for _, label in _metrics_for("l3d", spec, src_lane)]
    warm = ["warm p50 ms", "warm p99 ms"]
    if "cold p99 ms" in cols:
        at = cols.index("cold p99 ms") + 1
        cols[at:at] = warm
    else:
        cols = warm + cols
    return cols


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
            L3S_SECOND_PASS if any(e.get("scale") == "tiny" for e in by["l3smp"].get("entries", []))
            else L3S_SECOND_PASS_100K,
        ]
        t["source_paths"] = list(t.get("source_paths") or []) + list(by["l3smp"].get("source_paths") or [])
        t["source_urls"] = list(t.get("source_urls") or []) + list(by["l3smp"].get("source_urls") or [])
        tables.remove(by["l3smp"])
    # KEYED ON l1tpc ALONE, because that is the only table this split reads.
    # It used to require l1 and l1olap to be present too, which was true in
    # September and stops being true in October: DECISIONS #72 withdrew the
    # synthetic document set, so those two lanes are not run, `all(...)` is
    # false, and the page would quietly go back to one raw l1tpc table with
    # every transactional and analytical column in it. The two retired tables
    # are still removed when they exist, which is what the condition was
    # actually for.
    if "l1tpc" in by:
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
        _oct = _instrument_of("l1tpc") == "2026-10"
        # The October set is a REPLACEMENT, matching OCT_TABLE_METRICS: six
        # transactional operations (#82a) and five analytical queries (#82),
        # each a warm median, with a ninety-ninth percentile on the headline
        # query only and the cold column on the analytical table, where the
        # split applies (#89).
        OCT_OLTP_COLS = ["new-order p50 ms", "new-order p99 ms", "payment p50 ms",
                         "insert p50 ms", "read p50 ms", "update p50 ms",
                         "delete p50 ms", "OLTP ops/s"]
        OCT_OLAP_COLS = ["Q1 p50 ms", "Q1 p99 ms", "Q6 p50 ms", "top parts p50 ms",
                         "ship mode p50 ms", "by month p50 ms", "cold first query ms"]
        SHARED_COLS = {"ingest documents/s", "ingest total s",
                       "peak memory GiB", "disk GiB"}
        if _oct:
            OLTP_KEEP = set(OCT_OLTP_COLS) | SHARED_COLS
            OLAP_KEEP = set(OCT_OLAP_COLS) | SHARED_COLS
        src = by["l1tpc"]
        # The tuned PostgreSQL arm answered its question (image defaults do
        # not distort the comparison: 2.33 vs 2.39 ms new-order, 337 vs 331 ms
        # Q1) and stays in the rows; on the page it read as a second engine
        # (user, 2026-09-13, DECISIONS #76).
        src = dict(src, entries=[e for e in src["entries"] if e.get("backend_key") not in OFF_PAGE_ARMS])
        base = {"withheld_scales": [], "withheld_reason": None,
                "source_paths": src.get("source_paths"), "source_urls": src.get("source_urls")}
        tables.append({"id": "docs_oltp", "title": "Document OLTP",
                       "dataset": "TPC-C new-order on the TPC-H SF1 tables",
                       "conditions": list(src["conditions"]),
                       "columns": (OCT_OLTP_COLS if _oct else
                                   ["new-order p50 ms", "new-order p99 ms", "OLTP ops/s"]),
                       "entries": [clone(e, OLTP_KEEP) for e in src["entries"]], **base})
        # THE ARCADEDB ROWS ARE WITHDRAWN FROM THIS TABLE (2026-09-14, BUGS F42
        # and F43). Cross-engine answer checking, built for October, found that
        # the two queries ArcadeDB ran here were not the questions the
        # comparators answered: our Q1 text computed four aggregates where every
        # comparator computes five, and Q6's discount bound excluded the 0.05
        # bucket because the engine evaluates `>= 0.05` against a decimal literal
        # as strictly greater (reproduced on fifty rows: `= 0.05` returns none,
        # `BETWEEN` is correct). Both errors make ArcadeDB's numbers faster than
        # the truth, so the cells come down rather than stand with a caveat, and
        # October re-measures them with the answers checked.
        _olap_entries = [clone(e, OLAP_KEEP) for e in src["entries"]
                         if not str(e.get("backend", "")).lower().startswith("arcadedb")]
        tables.append({"id": "docs_olap", "title": "Document OLAP",
                       "dataset": "TPC-H Q1 and Q6 at SF1",
                       "conditions": list(src["conditions"]) + [
                           "ArcadeDB has no row on this table. Answer checking built for the next campaign "
                           "found that the two queries it ran here were not the questions the comparators "
                           "answered: one of the five aggregates was missing from our Q1 text, and its Q6 "
                           "excluded the boundary discount because the engine reads `>= 0.05` against a "
                           "decimal literal as strictly greater. Both errors made its numbers faster than "
                           "the truth, so they are withdrawn rather than shown with a caveat, and the next "
                           "campaign measures them with every engine's answer compared."],
                       "columns": (OCT_OLAP_COLS if _oct else
                                   ["Q1 p50 ms", "Q1 p99 ms", "Q6 p50 ms", "Q6 p99 ms"]),
                       "entries": _olap_entries, **base})
        for i in ("l1", "l1olap", "l1tpc"):
            if i in by:
                tables.remove(by[i])
    return tables


def main() -> int:
    if not FROZEN.exists():
        print(f"missing {FROZEN}; run make_paper_tables.py first", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(FROZEN.open()))
    global _FROZEN_ROWS
    _FROZEN_ROWS = rows
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

    # ONE SETTING PER TABLE. The 2026-10 instrument runs every timed write
    # twice, once at each durability setting (DECISIONS #90), and the frozen
    # set holds both. Every table except the durability table reports the
    # relaxed setting, as its condition says, so a strict row is dropped here
    # whenever a relaxed row of the same cell exists. Without this the
    # skeleton's write cells were medians over one relaxed and one strict run
    # (BUGS F52). An engine with no setting has strict rows only and keeps them.
    _all_rows = list(rows)
    _has_relaxed = {(r.get("lane"), r.get("workload"), r.get("backend"), str(r.get("scale")))
                    for r in rows if str(r.get("durability_class")) == "relaxed"}
    _dropped = [r for r in rows if str(r.get("durability_class")) == "strict"
                and (r.get("lane"), r.get("workload"), r.get("backend"), str(r.get("scale"))) in _has_relaxed]
    if _dropped:
        print(f"  one setting per table: {len(_dropped)} strict rows set aside for the durability table only")
        rows = [r for r in rows if r not in _dropped]
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
            if backend == "arcadedb_sparse_embedded_nocompact":  # OFF_PAGE_ARMS
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
                # The runner's own key for the arm, so a gate can hold the
                # table against runner.LANES without parsing the label
                # (page_check._check_lane_roster, 2026-09-18).
                "backend_key": backend,
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
            for field, label in _metrics_for(lane, spec, src_lane):
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
                # An October table starts from nothing: its sentences come from
                # OCT_PROSE and the generators (_finish_table), never from the
                # September list above.
                "conditions": ([] if _instrument_of(src_lane or lane) == "2026-10" else spec["conditions"]),
                "columns": ([label for _, label in _metrics_for(lane, spec, src_lane)]
                            if lane != "l3d" else _dense_columns(spec, src_lane)),
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
    # A SKELETON CARRIES NO CELL IT DID NOT MEASURE (DECISIONS #86). The
    # sparse second-pass table, the client/server decomposition, and the
    # Python-cost table are all built from artifacts of the bench host's
    # campaign, not from the skeleton's own rows, and dropping a laptop banner
    # over a mini measurement is the same lie in the other direction. They are
    # withheld and NAMED in the payload, so the reader can see which of the
    # October page's tables the skeleton could not draw and why.
    # The durability table sits beside the session-cost table (DECISIONS #90)
    # and is built from the same 2026-10 rows the write tables are; a September
    # payload has no cell that ran twice, so it returns None and the page does
    # not carry it.
    _extras = [_l4_table(rows), _lifecycle_table(rows), _durability_table(_all_rows)]
    if not SKELETON:
        _extras = [_sparse_multipass_table()] + _extras + [_e4_table(), _python_cost_table()]
    for extra in _extras:
        if extra and extra["entries"]:
            tables.append(extra)

    # RESHAPE FIRST, THEN ANNOTATE. The document lane becomes two page tables
    # here, and the per-table notes below are keyed by the PAGE table's id: run
    # in the other order, the cold-column clause and the equivalence
    # declarations looked up "l1tpc", found nothing, and both document tables
    # published without them.
    tables = _restructure_tables(tables, rows)

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
            _dn = OCT_DISK_NOTE if _table_instrument(_t.get("id")) == "2026-10" else DISK_NOTE
            if _dn not in _t["conditions"]:
                _t["conditions"].append(_dn)
    # EVERY TABLE SAYS IT, not only the banner at the top (DECISIONS #86). A
    # reader who lands on one table, or who screenshots one, must see it.
    # THE DURABILITY CLASS, ON THE TABLE THAT PAYS FOR IT (DECISIONS #81).
    # Before the skeleton note, so the placeholder warning stays first.
    # WHAT THE COLD COLUMN IS, OR WHY THERE IS NONE (DECISIONS #89). One
    # clause per table, from the rows: the lane either records a first-query
    # timing or records the reason a cold and warm split does not apply to it,
    # and a blank column with no sentence beside it is the thing #89 forbids.
    _withhold_cells(tables)
    _eq_notes = _equivalence_notes(rows)
    for _t in tables:
        _eq = _eq_notes.get(_t.get("id"))
        if _eq:
            _t.setdefault("conditions", [])
            if _eq not in _t["conditions"]:
                _t["conditions"].append(_eq)
    for _t in tables:
        _cold = _cold_note(_t.get("id"), rows, _t.get("columns") or [])
        if _cold:
            _t.setdefault("conditions", [])
            if _cold not in _t["conditions"]:
                _t["conditions"].append(_cold)
    for _t in tables:
        if _t.get("id") != "l3d":
            continue
        _mut = _mutation_note(rows)
        if _mut:
            _t.setdefault("conditions", [])
            if _mut not in _t["conditions"]:
                _t["conditions"].append(_mut)
    for _t in tables:
        # NOT on the durability table itself. That note reads the engine's own
        # durability string to decide which engines are stuck at the strict end,
        # and on this one table every engine with a knob has a strict cell by
        # construction -- so the note would name all of them as engines with no
        # setting to relax, which is the opposite of what the table shows. Its
        # own conditions say all of this, per column.
        if _t.get("id") in ("durability", "e2atom"):
            continue
        _note = _durability_note(_t.get("entries", []), rows)
        if _note:
            _t.setdefault("conditions", [])
            if _note not in _t["conditions"]:
                _t["conditions"].append(_note)
    if SKELETON:
        for _t in tables:
            _t.setdefault("conditions", [])
            if SKELETON_TABLE_NOTE not in _t["conditions"]:
                _t["conditions"].insert(0, SKELETON_TABLE_NOTE)
    _october = bool(tables) and all(_table_instrument(_t.get("id")) == "2026-10" for _t in tables)
    payload = {
        "source": f"benchmarks/experiments/results/{FROZEN_NAME}",
        "generator": "benchmarks/experiments/export_web.py",
        # DECISIONS #86. Present and false on a real payload, so a reader (and
        # refresh_web_page's live publish) tests a field that always exists
        # rather than an absence that could mean "old file".
        "skeleton": SKELETON,
        "skeleton_banner": SKELETON_BANNER if SKELETON else None,
        "gates_waived": SKELETON_WAIVERS if SKELETON else [],
        "skeleton_absent_tables": SKELETON_ABSENT if SKELETON else {},
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
        # The instrument the whole payload ran on; a table carries its own.
        "instrument": "2026-10" if _october else "2026-09",
        "conditions": _global_conditions(tables, _october),
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
            "hosts": _host_hardware(hosts, rows),
            "cpuset": collections.Counter(str(r.get("cpuset")) for r in rows if r.get("cpuset")).most_common(1)[0][0],
            "memory_cap_by_size": MEM_BY_SCALE,
            "jvm_heap_by_size": HEAP_BY_SCALE,
        },
        "tables": [_finish_table(t) for t in tables],
    }
    # THE CAPABILITY TABLE LAST (DECISIONS #95): it reads the other tables'
    # rows and declared absences, and those are complete only once
    # _finish_table has run on all of them. Appended to both lists so the
    # source-path loop and the entry count below see it; the global
    # conditions above were computed before it existed, so its text cells
    # never enter the repetition count.
    _mm = _multimodel_table(payload["tables"]) if _october else None
    if _mm:
        if SKELETON:
            # The every-table skeleton banner speaks of timings; this table has
            # none, so it says what a skeleton means for a coverage table.
            _mm["conditions"].insert(0, _gen(
                "This table carries no number. On the skeleton it is derived "
                "from placeholder tables, so it shows which engines the October "
                "page will compare on each workload, not anything measured yet."))
        tables.append(_mm)
        payload["tables"].append(_mm)

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

    # WHICH SENTENCES WERE GENERATED, with the strings they inserted, so
    # page_check can hold every other sentence to the registry (October) or
    # to its pins (September). Recorded after _finish_table, which is where
    # most generators run.
    payload["condition_provenance"] = {"generated": list(_GENERATED)}
    # Last thing before the bytes: take our paper trail out of the prose, then
    # refuse to write anything that still carries one.
    payload = _strip_internal_refs(payload)
    _refuse_internal_refs(payload)
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
               if e.get("image") is None and not e.get("outcome")
               and not e["backend"].endswith("_embedded")]
    if missing:
        print(f"  NOTE: no pinned image for {sorted(set(missing))} "
              f"(embedded/in-process backends have none by design)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
