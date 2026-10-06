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
import subprocess
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runner import BACKENDS, MEM_BY_SCALE, HEAP_BY_SCALE, arm_runs  # noqa: E402  (path set above)


# SIZE LABELS FROM THE LANES' OWN CONSTANTS, not typed. The time-series label
# was typed as "2.59M points" beside a lane constant of 2,592,000, and the
# cross-model one as "50k products" beside E2's default; a raised tier
# (DECISIONS #103b) would have needed a second typed number each. Formatted
# from the constant the lane reads, so the label cannot drift from the rows.
def _l4_scale_points(scale: str) -> int:
    """The point count the LANE defines for a tier, as an int."""
    from l4_tsbs import SCALE_POINTS  # noqa: E402
    return int(SCALE_POINTS[scale])


def _l4_tiers(scales):
    """The tiers present, smallest corpus first, skipping any the lane does
    not define (a row from a retired tier must not name a size we cannot
    source)."""
    out = []
    for t in scales:
        try:
            out.append((_l4_scale_points(t), t))
        except KeyError:
            continue
    return [t for _, t in sorted(out)]


def _l4_points(scale: str) -> str:
    """The time-series corpus size as the lane defines it, formatted for a label."""
    n = _l4_scale_points(scale)
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


def _dominant_cpuset(rows):
    """The cpuset the rows actually recorded, or a refusal naming why not.

    `Counter(...).most_common(1)[0][0]` raises IndexError on an empty counter,
    which is what a payload with no rows produces -- and "IndexError: list
    index out of range" from inside a dict literal says nothing about the
    cause. Rehearsing the l3s landing before that lane has any October rows
    hit exactly this.

    A payload with no rows is not publishable anyway: page_check requires the
    page's hardware paragraph to name this cpuset, so an empty one would take
    a wrong or missing value all the way to the gate that exists to catch it.
    Refuse here, where the reason is known.
    """
    seen = collections.Counter(str(r.get("cpuset")) for r in rows if r.get("cpuset"))
    if not seen:
        _only = os.environ.get("BENCH_ONLY_LANES", "").strip()
        raise SystemExit(
            "REFUSING: no row at this pin records a cpuset, so the page cannot "
            "state the machine its numbers were measured on"
            + (f" -- this landing covers only [{_only}], and that lane has no "
               f"rows at this pin yet" if _only else "")
            + ". Nothing to publish.")
    return seen.most_common(1)[0][0]


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


def _one_version(rs, where):
    """The version an entry prints must be the version EVERY row in it ran.

    An entry pools a group's rows into one median and prints one version
    beside it, read off rs[0]. That is safe only while a group cannot hold two
    versions, and the guarantee comes from the canonical dedupe upstream, not
    from anything here -- a different mechanism, one layer away, which is the
    kind of distance a defect lives in.

    It is not hypothetical either. `runs_page_417314c18.jsonl` holds pg_age_e2
    rows at "PostgreSQL 17.11 + age:1.7.0" AND "PostgreSQL 18.6 + age:1.8.0",
    the stale-image incident behind BUGS F90, where AGE 1.7.0 builds edges 65x
    slower. Measured after dedupe: zero groups disagree, so this refuses
    nothing today. It is here because the consequence of the day it does is a
    published version that names a build the numbers did not come from, which
    is indistinguishable from a correct row to every other gate -- the payload
    carries one string either way, so version_consistency_check sees nothing.
    """
    seen = {str(r.get("engine_version")) for r in rs if r.get("engine_version")}
    if len(seen) > 1:
        raise SystemExit(
            f"REFUSING: {where} pools rows that ran on different engine versions "
            f"{sorted(seen)}, and the entry prints one of them beside a median over "
            f"all of them. Whichever is printed, the cell names a build some of its "
            f"own numbers did not come from. Supersede the stale rows rather than "
            f"publishing across them.")
    return rs[0]


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
    # ONE ENGINE, ONE SPELLING OF ITS COMMIT -- the same rule _one_spelling
    # applies to a version string, and for the same reason. `engine_commit` is
    # stamped verbatim from ARCADEDB_ENGINE_COMMIT (bench_common), so its
    # length is whatever the stage that exported it happened to use. Two l4
    # stages exported the full 40 characters and every other stage nine, which
    # put BOTH spellings of one identifier on the /next page at once: 27 cells
    # reading `417314c18` and two reading
    # `417314c18da782620463bc7c09ac6bd34ac6fbda`. A reader comparing two rows
    # cannot see that those name the same engine, which is the whole job of the
    # identifier (#49).
    #
    # Nine, because that is the width already published across September's
    # page, and because a render-time normalisation must not change what a
    # settled page says. Truncating here rather than at the stamp fixes the
    # rows ALREADY frozen as well as future ones; per this function's contract
    # callers have compared the raw strings long before reaching it.
    if sha and re.fullmatch(r"[0-9a-f]{9,40}", sha):
        sha = sha[:9]
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
        # "qdrant-local" IS NOT "qdrant". The member stamped `qdrant-local` is the
        # Python client's in-process local mode, at the CLIENT package's version,
        # not the Qdrant server the vector tables run (BUGS F133). Dropping the
        # suffix printed "qdrant 1.19.1" under the atomicity table, which reads
        # as the server; the build line says what ran instead.
        def _member(n, v):
            ver = _short_version(v) or v
            if n.endswith("-local"):
                return f"{n[:-len('-local')]}-client {ver} (local mode)"
            return f"{n} {ver}"
        return " + ".join(_member(n, v) for n, v in _members)
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
    # The sensitivity arm at the vendor image's own JVM settings (CAMPAIGN 7 row 69): its
    # own label, so it is printed beside the main served row and never mistaken for it.
    "arcadedb_imgdefaults_server": "ArcadeDB (server, image JVM defaults)",
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
    "memgraph_e2": "Memgraph (vector index)", "ladybug_e2": "LadybugDB (vector extension)",
    "duckdb_e2": "DuckDB (vss + DuckPGQ)",
    "qdrant_sparse": "Qdrant", "qdrant_dense": "Qdrant", "qdrant_dense_int8": "Qdrant",
    "qdrant_sparse_uint8": "Qdrant",
    "milvus_sparse": "Milvus", "milvus_dense": "Milvus", "milvus_dense_int8": "Milvus",
    "sqlite_vec_dense_int8": "sqlite-vec",
    "elasticsearch_sparse": "Elasticsearch",
    "chroma_dense": "Chroma", "lancedb_dense": "LanceDB", "lancedb_dense_fp32": "LanceDB",
    "sqlite_vec_dense": "sqlite-vec", "duckdb_vss_dense": "DuckDB VSS",
    # #131 item 3 (2026-10-02)
    "elasticsearch_dense": "Elasticsearch", "elasticsearch_dense_int8": "Elasticsearch",
    "memgraph_dense": "Memgraph", "falkordb_dense": "FalkorDB", "ladybug_dense": "LadybugDB",
    "memgraph_dense_int8": "Memgraph",
    "duckpgq_graph": "DuckPGQ", "pgage_graph": "PostgreSQL + AGE",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "memgraph_graph": "Memgraph", "falkordb_graph": "FalkorDB",
    "postgres": "PostgreSQL", "postgres_tuned": "PostgreSQL (tuned)",
    "duckdb": "DuckDB", "questdb": "QuestDB", "sqlite": "SQLite", "mongodb": "MongoDB",
    "timescaledb": "TimescaleDB", "postgres_ts": "PostgreSQL", "postgresql": "PostgreSQL", "pgvector_dense": "pgvector", "pgvector_sparse": "pgvector", "neo4j_dense": "Neo4j", "neo4j_dense_int8": "Neo4j",
    "surrealdb_tpc": "SurrealDB (embedded)", "surrealdb_tpc_server": "SurrealDB (server)",
    "surrealdb_graph": "SurrealDB (embedded)", "surrealdb_graph_server": "SurrealDB (server)",
    "surrealdb_dense": "SurrealDB (embedded)", "surrealdb_dense_server": "SurrealDB (server)",
    "surrealdb_ts": "SurrealDB (embedded)", "surrealdb_ts_server": "SurrealDB (server)",
    "surrealdb_lifecycle": "SurrealDB (embedded)",
    "sqlite_lifecycle": "SQLite (embedded)", "duckdb_lifecycle": "DuckDB (embedded)",
    "ladybug_lifecycle": "LadybugDB (embedded)", "chroma_lifecycle": "Chroma (embedded)",
    "lancedb_lifecycle": "LanceDB (embedded)", "sqlite_vec_lifecycle": "sqlite-vec (embedded)",
    # Served only, so bare, like MongoDB and Neo4j; "(server)" marks an engine
    # that also has an embedded row.
    "arangodb_tpc": "ArangoDB", "arangodb_graph": "ArangoDB", "arangodb_dense": "ArangoDB", "arangodb_dense_int8": "ArangoDB", "arangodb_e2": "ArangoDB",
    "arangodb_ts": "ArangoDB",
    "mongodb_graph": "MongoDB", "mongodb_dense": "MongoDB", "mongodb_dense_int8": "MongoDB", "mongodb_e2": "MongoDB",
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
    # SparseIndexParams.datatype uint8, read back from the collection as
    # qdrant_sparse_datatype (DECISIONS #135, 2026-10-02); the fp32 arm now sets
    # float32 and reads it back the same way.
    "qdrant_sparse_uint8": "uint8",
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
    # Neo4j 2026.08.1 quantizes BINARY unless told otherwise (BUGS F164); the arms set NONE and SCALAR and
    # read the applied type back as neo4j_vector_quantization.
    "neo4j_dense": "fp32", "neo4j_dense_int8": "int8",
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
    # #131 item 3 (2026-10-02), checked against the DDL each issues (#53):
    #   elasticsearch_dense       dense_vector, index_options.type hnsw (float)
    #   elasticsearch_dense_int8  index_options.type int8_hnsw, top k rescored with the floats
    #   memgraph_dense            CREATE VECTOR INDEX ... "scalar_kind": "f32"
    #   falkordb_dense            vecf32 property, CREATE VECTOR INDEX (float32)
    #   ladybug_dense             FLOAT[DIM] column, CREATE_VECTOR_INDEX over it
    "elasticsearch_dense": "fp32",
    "elasticsearch_dense_int8": "int8",
    "memgraph_dense": "fp32",
    # The quantization survey's counterparts (DECISIONS #135, 2026-10-02),
    # checked against the DDL each issues and the value each reads back:
    #   mongodb_dense_int8   vectorSearch field "quantization": "scalar" (mongot_vector_quantization)
    #   memgraph_dense_int8  CREATE VECTOR INDEX ... "scalar_kind": "i8" (memgraph_vector_scalar_kind)
    #   lancedb_dense_fp32   index_type IVF_HNSW_FLAT, unquantized (lancedb_index_type)
    #   arangodb_dense_int8  FAISS factory "IVF<nLists>,SQ8" (ivf_factory)
    "mongodb_dense_int8": "int8",
    "memgraph_dense_int8": "int8",
    "lancedb_dense_fp32": "fp32",
    "arangodb_dense_int8": "int8",
    "falkordb_dense": "fp32",
    "ladybug_dense": "fp32",
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
    # The e4 lane decomposes ONE corpus across three deployments; its row
    # labels are the six result sizes, so the scale names the corpus the
    # projection runs over, which is the cross-model lane's 50k products.
    ("e4", "e2"): "50k products",
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
    # THE SERVER RESTART (DECISIONS #139 item 2). Each engine restarts on ONE
    # model's data, at that model's own tiers, so the size says the model too:
    # rows are compared only within a size, never across models.
    ("restart", "tpch1"): "documents, TPC-H SF1 (6.0M line items)",
    ("restart", "tpch10"): "documents, TPC-H SF10 (60.0M line items)",
    ("restart", "sf1"): "graph, LDBC SF1 (11k people)",
    ("restart", "sf10"): "graph, LDBC SF10 (73k people)",
    ("restart", "small"): "dense vectors, 1M (SIFT)",
    ("restart", "deep10m"): "dense vectors, 9.99M (Deep)",
    ("restart", "ts100"): f"time series, {_l4_points('ts100')} points",
    ("restart", "ts1000"): f"time series, {_l4_points('ts1000')} points (1,000 hosts)",
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
    # One micro tier for three models on the laptop: the skeleton shows the
    # table's shape, and the campaign's tiers (above) name each model apart.
    ("restart", "micro"): "each engine's own micro corpus (skeleton)",
    ("restart", "ts100"): f"time series, {_l4_points('ts100')} points (skeleton)",
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
    "restart": f"benchmarks/experiments/results/{FROZEN_NAME}",
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
    # IVF_HNSW_SQ: once the only quantized comparator, and it was unlabelled
    # while ArcadeDB's two arms were, which made quantization read as our quirk.
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
    ("neo4jvec_int8", "neo4j_dense_int8", "Neo4j (int8)", False),
    ("surreal", "surrealdb_dense", "SurrealDB (embedded, fp32)", False),
    ("surrealsrv", "surrealdb_dense_server", "SurrealDB (server, fp32)", False),
    ("arango", "arangodb_dense", "ArangoDB (fp32)", False),
    ("mongo", "mongodb_dense", "MongoDB (fp32)", False),
    # #131 item 3 (2026-10-02); skipped until their overlay files exist.
    ("elastic", "elasticsearch_dense", "Elasticsearch (fp32)", False),
    ("elastic_int8", "elasticsearch_dense_int8", "Elasticsearch (int8)", False),
    ("memgraph", "memgraph_dense", "Memgraph (fp32)", False),
    # DECISIONS #135 (2026-10-02); skipped until their overlay files exist.
    ("mongo_int8", "mongodb_dense_int8", "MongoDB (int8)", False),
    ("memgraph_int8", "memgraph_dense_int8", "Memgraph (int8)", False),
    ("lancedb_fp32", "lancedb_dense_fp32", "LanceDB (fp32)", False),
    ("arango_int8", "arangodb_dense_int8", "ArangoDB (int8)", False),
    ("falkordb", "falkordb_dense", "FalkorDB (fp32)", False),
    ("ladybug", "ladybug_dense", "LadybugDB (fp32)", False),
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
DISK_NOTE = ("Disk is what the workload left on disk, in GiB: the engine's writable "
             "layer plus its volumes after the cell, minus the same engine's empty "
             "footprint.")

# HOW DISK IS READ, SAID ONCE FOR THE PAGE. It used to be said in full on
# every table that prints the column -- eight of them, five clauses each,
# verbatim -- which is the same repetition the censored notes had, one level
# up. Peak memory was already a page-level sentence and disk was the outlier.
# Each table keeps the one line above so it still reads standalone; the rest
# lives beside the other conditions that hold everywhere.
DISK_DETAIL = ("A disk reading is taken after the queries, so it includes anything "
               "querying wrote; for a served row it is the server container alone, the "
               "client being only the driver. A server reading is taken once two samples "
               "agree within 1%, an embedded reading once on the stopped container. A "
               "blank disk cell is a row measured before the disk reading existed "
               "(2026-08-14). Neo4j's value includes the transaction-log files it "
               "preallocates in 256 MiB steps, which is how Neo4j uses disk; turning "
               "that off would have slowed its writes, so it stays on.")


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


def _agg(rows, field, across_scales=False):
    """Median across repetitions, with the spread, matching the paper.

    ONE CELL IS ONE POPULATION. Every caller here aggregates the repetitions of
    a single cell, so the rows it is handed must agree on the corpus they ran
    against. When they do not, the median describes no measurement anyone made:
    the time-series table published ArcadeDB's newest-reading p50 as 2.3889 ms
    over n=10 rows spanning 2,592,000 AND 25,920,000 points, where the two
    corpora alone give 2.1124 and 3.1835 -- and the printed min came from one
    while the max came from the other (BUGS F110).

    All six publish gates passed that, because none of them compares a cell's
    rows against the corpus its table claims. The check belongs here, at the
    one place every table's numbers are actually computed, rather than in a
    gate reading the payload afterwards and trying to reconstruct which rows
    went in.

    `across_scales=True` is for the caller that genuinely spans corpora and
    says so. Nothing sets it today; it exists so that a future caller has to
    write the word rather than discover the behaviour.
    """
    if not across_scales and rows:
        _scales = {str(r.get("scale")) for r in rows if r.get("scale") is not None}
        if len(_scales) > 1:
            raise SystemExit(
                f"REFUSING: a cell would be aggregated across {sorted(_scales)}. "
                f"One cell is one corpus; a median over two is a number that "
                f"describes neither (BUGS F110). Group the rows by scale, or "
                f"pass across_scales=True if the span is deliberate.")
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
        # THE SPLIT, beside the total rather than replacing it (FAIRNESS F14).
        # `ingest total s` keeps meaning what it has always meant, the whole of
        # build(), so September's rows and October's say the same thing by that
        # name. The two below say how that total divides, under the names the
        # dense table has used since it was written. A row with no index_s --
        # every September row, and any arm that builds no index -- does not fill
        # them, and a column no row fills is dropped, so the split shows up
        # exactly where it was measured.
        ("ingest_s", "ingest s"),
        ("index_s", "index s"),
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
        # AND NOW THE TWO HALVES (FAIRNESS F14). The combined name was always
        # honest -- this lane builds the page's most expensive indexes, an
        # LSM_VECTOR, an HNSW, a FAISS IVF, a MongoDB vector search index --
        # but a combined number cannot say whether an engine is slow to load or
        # slow to index, and on this lane that is most of the question. l3d and
        # l3s keep theirs combined for the reason their own conditions give:
        # Qdrant and Chroma build the index while ingesting, so the split is not
        # defined there.
        ("ingest_s", "ingest s"),
        ("index_s", "index s"),
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
        # The split beside the total, as on the document and dense tables.
        # This lane's load-only field is `load_s` rather than `ingest_s`
        # because `ingest_s` was published as the total first; see l4_tsbs.
        ("load_s", "ingest s"),
        ("index_s", "index s"),
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


# THE LANE'S Q1 IS PART OF TPC-H Q1 (BUGS F170, DECISIONS #151 item 3). TPC-H
# Q1, the pricing summary report, returns the ten columns below. The October
# lane's Q1, on every engine, returns seven of them: it never loads `l_tax`, so
# it cannot compute sum_charge, and it leaves out avg_price and avg_disc too.
# The page called it "TPC-H's own Q1". Until the documents analytics rows are
# the full query, the Q1 words and the cold-column sentence say what ran. The
# re-pin loads `l_tax`, runs the full Q1 on every engine, and writes `tpch_q1`
# into every documents analytics row (CAMPAIGN section 7 row 57); a row without
# it ran the partial Q1. The count of columns that ran is read from the rows'
# own answer sample, not typed.
_TPCH_Q1_COLUMNS = ("l_returnflag", "l_linestatus", "sum_qty", "sum_base_price",
                    "sum_disc_price", "sum_charge", "avg_qty", "avg_price", "avg_disc",
                    "count_order")
_TPCH_Q1_FIELD = "tpch_q1"


def _partial_q1(rows):
    """(columns the rows' Q1 returned, TPC-H Q1's column count), as words,
    while any October documents analytics row ran the partial Q1; else None.
    The first count is None when the rows' answer samples disagree on it."""
    rs = [r for r in rows
          if r.get("lane") == "l1tpc" and r.get("workload") == "olap"
          and str(r.get("instrument") or "") == "2026-10"
          and not str(r.get(_TPCH_Q1_FIELD) or "").strip()]
    if not rs:
        return None
    widths = set()
    for r in rs:
        m = re.match(r"\(([^)]*)\)", str(r.get("res_q1_sample") or ""))
        if m:
            widths.add(len(m.group(1).split(",")))
    ran = None
    if len(widths) == 1 and next(iter(widths)) in _WORDS:
        ran = _WORDS[next(iter(widths))].lower()
    return ran, _WORDS[len(_TPCH_Q1_COLUMNS)].lower()


def _partial_q1_words(rows):
    """What the documents analytics table's Q1 is, while it is the partial Q1:
    (words, the values inserted), or None."""
    part = _partial_q1(rows)
    if not part:
        return None
    ran, spec = part
    cols = (f"with {ran} of its {spec} output columns" if ran
            else "with some of its output columns")
    words = (f"TPC-H Q1, the pricing summary, {cols}. It groups and aggregates nearly every "
             f"line item, so it measures a full scan. It leaves out the average price, the average "
             f"discount, and the total charge with tax, which needs the tax column this "
             f"measurement did not load. The next measurement runs the full Q1")
    return _next_item("q1", words), ([ran, spec] if ran else [])


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

# HARNESS DEFECTS THAT TIMED THE WRONG THING (DECISIONS #117). Not a wrong
# answer -- the answers agree -- but a latency that measured our query shape,
# an unsettled index, or a stand-in engine rather than the engine named, fixed
# in the lanes and re-run in qOM.
#
# KEYED ON THE ROWS, NOT ON A DATE. Each entry says how to recognise a row
# measured BEFORE its fix, and the cell (or, with column None, the whole row)
# comes down only while the rows behind it are such rows. The re-run's rows
# supersede them under the canonical-row rule and are not recognised, so the
# numbers return at the landing that carries them with nothing to remember
# and no list to edit. (table id, backend key, column or None) -> (why, stale).
_F132 = ("SurrealDB's graph-filtered search is marked `re-run`: our query scanned every product instead of "
         "reading the candidates by record id, the access path every other engine on this table was "
         "given. It is being re-measured with the fix.")
_F134 = ("SurrealDB (server) retrieval at the 500k tier is marked `re-run`: the server was still building "
         "its vector index in the background when these queries ran. It is being re-measured with the "
         "build waiting for the index to catch up.")
_F133 = ("Qdrant + Neo4j's row is marked `re-run`. Its vector half ran in the "
         "Qdrant client's in-memory local mode, a pure-Python reimplementation rather than the Qdrant "
         "server, so every time, recall, and disk value it produced described that reimplementation. "
         "It is being re-run against the Qdrant server the vector table uses. Its all-or-nothing result "
         "on the atomicity table below does not depend on this.")
_BEFORE_F132 = lambda r: str(r.get("filtered_access") or "") != "record ids"      # noqa: E731
# Neo4j's vector index ran BINARY-quantized (BUGS F164, DECISIONS #135): Neo4j 2026.08.1 builds a vector index with
# `vector.quantization.type: "BINARY"` and a search expansion factor of 3 when the definition names no quantization,
# and neither arm's definition did, while their rows recorded `quantization: "fp32"`. Every cell resting on the index
# comes down; the cross-model atomicity row does not rest on it and stays. The re-measured rows read the applied
# index configuration back as `neo4j_vector_quantization`, so a row without that field is a row from before the fix.
_F164_DENSE = ("Neo4j's row is marked `re-run`: its vector index ran at Neo4j's default quantization, binary with a "
               "three-fold search expansion, which our index definition did not override, while the row recorded it as "
               "unquantized. The next measurement sets the quantization explicitly, unquantized here and as a "
               "separate scalar-quantized row.")
_F164_E2 = ("Neo4j's row is marked `re-run`: its vector index ran at Neo4j's default quantization, binary with a "
            "three-fold search expansion, which our index definition did not override, so its vector search was not "
            "the unquantized search the other engines ran. The next measurement sets the quantization "
            "explicitly. Its all-or-nothing result on the atomicity table does not depend on the index.")
_BEFORE_F164 = lambda r: not r.get("neo4j_vector_quantization")                # noqa: E731

# SurrealDB served ran at its default, a sync to disk at every commit, in BOTH durability classes (BUGS F165).
# Its rows said "behaviour at commit is not verified": the harness held that 3.2.4 had no sync setting, having
# searched only its SURREAL_* variable names, while the setting is a parameter on the storage path
# (`rocksdb:/path?sync=never`) and the server printed "Sync mode: every transaction commit" at INFO in every
# serverlog the October campaign kept (107 of 107). So its single-record writes and its cross-model transaction,
# where one sync is most of the cost, sat beside every other engine's no-wait cells; they come down until the
# re-measurement, whose rows carry the mode read back from the server (`surreal_sync_mode`). Its reads, analytics,
# and ingest stay: ingest commits once per 5,000- or 10,000-record batch. The durability table keeps its writes in
# the waiting column (DECISIONS #136 item 1): a sync at every commit is what that column measures, so
# _durability_stale exempts these entries while withholding every other write withheld on its own table.
_F165_WRITES = ("SurrealDB (server)'s write cells are marked `re-run`: the server ran at its default, a sync to disk "
                "at every commit, although it has a setting that does not wait, and every other engine on this table "
                "that has such a setting ran at it. Our harness missed that setting, and the next measurement runs "
                "its writes at it. Its read cells commit nothing and stay.")
_F165_E2 = ("SurrealDB (server)'s transaction cells are marked `re-run`: the server ran at its default, a sync to "
            "disk at every commit, although it has a setting that does not wait, and every other engine on this "
            "table that has such a setting ran at it. Our harness missed that setting, and the next measurement "
            "runs the transaction at it.")
_SURREAL_SERVED_SYNCED = lambda r: (str(r.get("backend") or "").startswith("surrealdb_")      # noqa: E731
                                    and str(r.get("backend") or "").endswith("_server")
                                    and not r.get("surreal_sync_mode"))
_BEFORE_F134 = lambda r: not str(r.get("settle_s") or "").strip()                  # noqa: E731
_BEFORE_F133 = lambda r: "qdrant-local" in str(r.get("engine_version") or "")     # noqa: E731
# ArangoDB's relaxed cross-model rows predate its `persistent(pid)` index (BUGS F168). The index landed in
# 299e454a8a (2026-09-21) and the stage said to carry it re-ran only the strict class, so the 20 relaxed
# `arangodb_e2` rows on the page scanned every product for each read (2.6x to 25x slower than its own strict
# rows, which have the index). Every row built with the index records `index_s`; a row without it was measured
# before the index existed, and the whole row comes down until a relaxed cell is measured with it.
_F168_E2 = ("ArangoDB's row is marked `re-run`: its rows on this table were measured before the index on the "
            "product id that the protocol builds for it existed, so its reads scanned every product. They are "
            "withheld until it is measured with the index.")
_BEFORE_ARANGO_PID_INDEX = lambda r: str(r.get("index_s") or "").strip() in ("", "None")   # noqa: E731
# LadybugDB's graph arm ran with threads and buffer pool sized from the whole host while its peers were fitted
# to the cell (BUGS F160, DECISIONS #125). Stage qOA5 re-runs its four interactive cells at both durability
# classes in this campaign; the fitted rows record `ladybug_threads` (read back from the engine) and
# `ladybug_buffer_pool_mib` (l2_graph.py, LadybugGraph), so a row without them is an unfitted row and the
# re-run's rows return by themselves.
_F160_L2 = ("LadybugDB's row is marked `re-run`: it sized its thread count and buffer pool from the whole "
            "machine rather than from the cores and memory its cell was given, while every other engine here "
            "that sizes itself from the machine was fitted to its cell. It is being re-measured with both fitted.")
_BEFORE_F160 = lambda r: not str(r.get("ladybug_threads") or "").strip()            # noqa: E731
STALE_UNTIL_RERUN = {
    ("e2", "arangodb_e2", None, None): (_F168_E2, _BEFORE_ARANGO_PID_INDEX),
    ("l2", "ladybug_graph", None, None): (_F160_L2, _BEFORE_F160),
    ("e2", "surrealdb_e2", "graph-filtered search p50 ms", None): (_F132, _BEFORE_F132),
    ("e2", "surrealdb_e2_server", "graph-filtered search p50 ms", None): (_F132, _BEFORE_F132),
    ("e2", "surrealdb_e2_server", "retrieval p50 ms", "e2_500k"): (_F134, _BEFORE_F134),
    ("e2", "surrealdb_e2_server", "retrieval recall@10", "e2_500k"): (_F134, _BEFORE_F134),
    ("e2", "composed_qdrant_neo4j", None, None): (_F133, _BEFORE_F133),
    ("e2", "neo4j_e2", None, None): (_F164_E2, _BEFORE_F164),
    ("l3d", "neo4j_dense", None, None): (_F164_DENSE, _BEFORE_F164),
    **{("docs_oltp", "surrealdb_tpc_server", c, None): (_F165_WRITES, _SURREAL_SERVED_SYNCED)
       for c in ("new-order p50 ms", "new-order p99 ms", "payment p50 ms", "insert p50 ms", "update p50 ms",
                 "delete p50 ms", "OLTP ops/s")},
    **{("l2", "surrealdb_graph_server", c, None): (_F165_WRITES, _SURREAL_SERVED_SYNCED)
       for c in ("insert p50 ms", "update p50 ms", "delete p50 ms")},
    **{("e2", "surrealdb_e2_server", c, None): (_F165_E2, _SURREAL_SERVED_SYNCED)
       for c in ("transaction p50 ms", "transaction p99 ms")},
}


def _rows_behind(table_id, backend_key, scale=None):
    """The frozen rows a table entry is built from: its lane and workload, the
    relaxed class where the cell has one (the main tables drop a strict row
    beside a relaxed one)."""
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    lane, wl = lane_wl
    # A table whose lane has one workload maps to None, which means any workload here: the literal comparison
    # matched no dense, sparse, time-series, or lifecycle row, so a stale entry on those tables could never fire.
    rs = [r for r in (_FROZEN_ROWS or []) if r.get("lane") == lane and (wl is None or r.get("workload") == wl)
          and r.get("backend") == backend_key and (scale is None or str(r.get("scale")) == str(scale))]
    relaxed = [r for r in rs if str(r.get("durability_class")) == "relaxed"]
    return relaxed or rs


def _stale(table_id, backend_key, scale, pred):
    return any(pred(r) for r in _rows_behind(table_id, backend_key, scale))


def _withdrawn_now(table_id):
    """Backend keys whose whole row on `table_id` is down right now."""
    return {bk for (tid, bk, col, _sc), (_why, pred) in STALE_UNTIL_RERUN.items()
            if tid == table_id and col is None and _stale(tid, bk, None, pred)}


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
# cheap "is there anything here at all" test, so untouched prose stays byte
# for byte what its author wrote
_REF_SCAN = re.compile(r"\b(?:%s)\b" % _INTERNAL)


def _public_prose(text):
    """One reader-facing string with our internal citations taken out.

    A STRING WITH NOTHING TO STRIP IS RETURNED UNTOUCHED. The tidy-up below
    collapses runs of whitespace and pulls punctuation back, which is right
    for a sentence a citation was just cut out of and wrong for every other
    sentence on the page: page_check holds each October sentence against
    OCT_PROSE by exact text, and rewriting one space made two registered
    sentences unrecognisable to the gate that registers them. Cleaning what
    was not dirty is how a sanitiser becomes a source of drift.
    """
    if not _REF_SCAN.search(text):
        return text
    out = _REF_PAREN.sub("", text)
    out = _REF_TAIL.sub("", out)
    out = _REF_BARE.sub("", out)
    # the stripping can leave a double space or a space before punctuation
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,;:)])", r"\1", out)
    # A citation removed from the end of a clause leaves its comma behind.
    out = re.sub(r"[,;]\s*$", "", out)
    return out.strip()


# ONE ENGINE, ONE SPELLING OF ITS VERSION. FalkorDB reports "v4.20.6" on the
# graph lanes and "4.20.6" on the durability lane; SurrealDB's server does the
# same with v3.2.4. Same build, two strings, and a reader comparing two tables
# cannot see they agree -- which is exactly what version_consistency_check
# refuses. The leading v is the engine's own habit and carries nothing, so it
# comes off here, once, rather than in each adapter that reports a version.
_V_PREFIX = re.compile(r"\bv(?=[0-9]+(?:\.[0-9]+)+)")


def _one_spelling(text):
    return _V_PREFIX.sub("", text)


def _strip_internal_refs(node):
    if isinstance(node, str):
        return _public_prose(node)
    # version strings ride the same walk: they are reader-facing too
    if isinstance(node, dict):
        # A HOST FIELD IS PROVENANCE AND STILL READER-FACING. `entries[].host`
        # is rendered, and on the live page it rendered the literal "mini" on
        # 35 rows. The value stays exact for a host we do not name -- l4's
        # rows carry "container:<id> (host unknown)" and that is the honest
        # answer -- but one of OUR machines becomes what it is to the reader.
        # The frozen CSV keeps `bench_host` verbatim; this is the published
        # copy, and the two are allowed to differ in how they say it.
        return {k: (HOST_ROLE.get(v, v) if k in ("host", "bench_host") and isinstance(v, str)
                    else v if k in _PROVENANCE_KEYS
                    else _one_spelling(v) if k == "version_name" and isinstance(v, str)
                    else _strip_internal_refs(v))
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

    # OUR MACHINES ARE INTERNAL VOICE TOO (user, 2026-09-22: "whether we use
    # laptop or mini is internal voice. it shouldn't be in the page"). Same
    # rule as the document citations above and found the same way -- by the
    # user reading the page -- so it gets the same refusal rather than a
    # sanitiser that might miss a phrasing. The live page said "mini" in
    # `setup.hosts` and in a condition; the preview said "laptop" 185 times.
    #
    # `bench_host` on a ROW is provenance and stays exact, like the generator
    # path: the rule is about prose the reader is asked to read, not about
    # hiding where a number came from. Hence _PROVENANCE_KEYS is honoured by
    # the same walk.
    hosts = []

    def walk_hosts(node, path=""):
        if isinstance(node, str):
            for m in re.findall(r"\b(?:laptop|mini|bench host|bench-host)\b", node, re.I):
                hosts.append((path, m, node[:90]))
        elif isinstance(node, dict):
            for k, v in node.items():
                if k in _PROVENANCE_KEYS:
                    continue
                for m in re.findall(r"\b(?:laptop|mini)\b", str(k), re.I):
                    hosts.append((path, f"key {k!r}", ""))
                walk_hosts(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk_hosts(v, f"{path}[{i}]")

    walk_hosts(payload)
    if hosts:
        print("REFUSING to publish: a machine of ours is named in reader-facing text")
        for path, m, ctx in hosts[:12]:
            print(f"  {path}: {m!r}" + (f" in {ctx!r}" if ctx else ""))
        raise SystemExit(
            f"{len(hosts)} hostname(s) would have been published. A reader has no "
            f"idea which machine is which and does not need one: say what the "
            f"machine IS (the benchmark machine, a shared machine running other "
            f"work), never what we call it.")


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
    # A MARK, NOT A GAP (DECISIONS #117, the user: "just write place holders").
    # The row stays and its cells say `re-run`, so a reader sees the engine is
    # on the table and why its number is not; `outcome` keeps everything that
    # ranks or averages from reading the row as a measurement.
    for (tid, bkey, column, only_scale), (why, pred) in STALE_UNTIL_RERUN.items():
        for t in tables:
            if t.get("id") != tid:
                continue
            for e in t.get("entries", []):
                hit = (str(e.get("backend_key")) == bkey
                       and (only_scale is None or str(e.get("scale")) == only_scale)
                       and _stale(tid, bkey, e.get("scale"), pred))
                if not hit:
                    continue
                if column is None:
                    e["outcome"] = "withdrawn"
                    e["version_name"] = None   # the stand-in's version would read as the engine's
                    e["metrics"] = {c: {"text": "re-run"} for c in (t.get("columns") or [])}
                    notes[tid].append(_gen(why))
                    _declare_absence(tid, str(e.get("backend")), None, "withdrawn", why)
                elif column in (e.get("metrics") or {}):
                    e["metrics"][column] = {"text": "re-run"}
                    notes[tid].append(_gen(why))
                    _declare_absence(tid, str(e.get("backend")), column, "withheld", why)
    for t in tables:
        for why in dict.fromkeys(notes.get(t.get("id"), [])):
            t.setdefault("conditions", [])
            if why not in t["conditions"]:
                t["conditions"].append(why)
    return tables


# THE ZERO AGES (BUGS F146, DECISIONS #119). Until the re-pin the LDBC loader
# read the epoch-millisecond `birthday` as a date string, so every person's age
# loaded as 0: the three-hop read's filter matched no one on any engine, and
# "average friend age" is 0 for every city. The fixed loader writes
# `ldbc_age_parse` into every graph row; a row without it was measured on the
# zero ages, and the sentence below stays until no such row is left behind the
# table. The rows that lack the marker ran the October query, whose threshold
# was this number (graph_common before HOP3F_MIN_AGE existed).
_ZERO_AGE_HOP3F_MIN_AGE = 30


def _ldbc_age_note(table_id, rows):
    """The zero-ages sentence for the graph table or the graph analytics
    table, or None when every LDBC row behind it carries the fixed parse."""
    workload = {"l2": "oltp", "l2olap": "olap"}.get(table_id)
    if workload is None or not _OCTOBER_ENV:
        # The September page stays as it was frozen (#83, #119 point 2).
        return None
    stale = [r for r in rows
             if r.get("lane") == "l2" and r.get("workload") == workload
             and str(r.get("graph_source") or "").startswith("ldbc")
             and not r.get("ldbc_age_parse")]
    if not stale:
        return None
    if table_id == "l2":
        return _gen("In this measurement every person's age loaded as zero, through a date-parsing "
                    f"error in our data loader, so the 3-hop filtered read (age above "
                    f"{_ZERO_AGE_HOP3F_MIN_AGE}) matched no one on any engine: its times are three "
                    "hops plus a check on every end node. The next measurement parses the ages "
                    "correctly.", _ZERO_AGE_HOP3F_MIN_AGE)
    return _gen("In this measurement every person's age loaded as zero, through a date-parsing "
                "error in our data loader, so average friend age is zero for every city; its "
                "times still read every friend's age. The next measurement parses the ages "
                "correctly.")


# THE FRIENDSHIPS ARE STORED ONE WAY (BUGS F169, DECISIONS #151 items 1 and 2).
# LDBC's person_knows_person file lists each friendship once, always from the
# smaller person id to the larger (180,623 of 180,623 rows at SF1), the lane
# loads each row as one KNOWS edge, and every graph question the October rows
# answer follows `-[:KNOWS]->`. So 1-hop counts only the friends with a larger
# id, 2-hop and 3-hop reach along rising ids, "most friends" and "degree
# distribution" count friends with a larger id, and the triangle count is 0 on
# every engine by construction (a directed 3-cycle needs a < b < c < a). The
# timings stand (identical work on every engine); the meaning is disclosed, the
# way F146's zero ages are. The re-pin asks every question in each dialect's
# undirected form and writes `knows_direction` into every graph row (CAMPAIGN
# section 7 row 56); a row without it asked the directed questions, and the
# sentence stays until no such row is left behind the table. LDBC rows only: the
# synthetic generator's edges point either way. No share is quoted: the share
# of a start person's friends 1-hop sees was measured on the laptop
# (`.notes/bench/repros/validity-20261004`), not by anything the rows carry.
_KNOWS_DIRECTION_FIELD = "knows_direction"


def _knows_one_way_rows(rows, workload):
    """The October LDBC graph rows of this workload that asked the directed
    questions, i.e. that do not record `knows_direction`."""
    return [r for r in rows
            if r.get("lane") == "l2" and r.get("workload") == workload
            and str(r.get("instrument") or "") == "2026-10"
            and str(r.get("graph_source") or "").startswith("ldbc")
            and not str(r.get(_KNOWS_DIRECTION_FIELD) or "").strip()]


def _knows_one_way_note(table_id, rows):
    """The one-way friendship sentence for the graph table or the graph
    analytics table, or None when every LDBC row behind it asked undirected."""
    workload = {"l2": "oltp", "l2olap": "olap"}.get(table_id)
    if workload is None or not _OCTOBER_ENV:
        return None
    if not _knows_one_way_rows(rows, workload):
        return None
    lead = ("Each friendship is one edge, pointing from the person with the smaller id to "
            "the person with the larger.")
    if table_id == "l2":
        text = (f"{lead} The engines can follow an edge from either end, but the 1-hop, 2-hop, "
                "and 3-hop reads follow it only the way it points, so 1-hop counts only the "
                "friends with a larger id than the start person, and 2-hop and 3-hop reach only "
                "people along a chain of rising ids. The next measurement asks the same "
                "questions in both directions of a friendship.")
    else:
        text = (f"{lead} The triangle count follows edges only the way they point, so it looks "
                "for three people whose ids rise all the way round a cycle, which cannot "
                "happen: it finds no triangle on any engine, by construction. For the same "
                "reason, most friends and degree distribution count only the friends with a "
                "larger id. The next measurement asks these questions in both directions of a "
                "friendship.")
    return _next_item("knows", _gen(text))


# LSQB'S NODE INEQUALITY RAN ON THE ID PROPERTY (BUGS F174, DECISIONS #154
# items 1 and 2). LSQB's q5, q6, q8, and q9 ask that two matched nodes be
# different (`tag1 <> tag2`, `person1 <> person3`). From 2026-09-18
# (`d1fe3183a0`) graph_common.LSQB_QUERIES and the other dialects' spellings
# compared their ids instead (`tag1.id <> tag2.id`, `person1.id <> person3.id`),
# on the belief that ArcadeDB's openCypher needed the property form. It does
# not, and its planner recognises only the inequality between two node
# variables for the count operators it has for q5, q6, and q9, and at the pin
# LSQB's text ran faster than the id form on all four; the rewrite cost Neo4j
# time too on q9. The answers are identical either way, so every digest
# agreed. The timings stand and the text is disclosed, the way F146's zero
# ages and F169's one-way friendships are. The re-pin runs LSQB's own text on every engine and writes
# `lsqb_text` into every graph analytics row (CAMPAIGN section 7 row 60); a row
# without it ran the id form, and the sentence stays until no such row is left
# behind the table. The queries are named the way the table's columns name
# them, and only the ones such a row measured (q6 and q9 do not run at the
# full-network tier, DECISIONS #109). No ratio is quoted: the costs were
# measured on the laptop (`.notes/bench/repros/perf-lsqb-q9-20261004`), not by
# anything the rows carry.
_LSQB_TEXT_FIELD = "lsqb_text"
_LSQB_ID_FORM_QUERIES = ("lsqb_q5", "lsqb_q6", "lsqb_q8", "lsqb_q9")


def _lsqb_id_form_queries(rows):
    """The graph analytics table's names ("LSQB Q5", ...) for the id-form
    queries that an October graph analytics row without `lsqb_text`
    measured, in query order; empty when no such row is left."""
    stale = [r for r in rows
             if r.get("lane") == "l2" and r.get("workload") == "olap"
             and str(r.get("instrument") or "") == "2026-10"
             and not str(r.get(_LSQB_TEXT_FIELD) or "").strip()]
    labels = {f: str(lbl) for f, lbl in OCT_TABLE_METRICS["l2olap"] if isinstance(f, str)}
    out = []
    for q in _LSQB_ID_FORM_QUERIES:
        field = f"{q}_p50_ms"
        if field in labels and any(_num(r.get(field)) is not None for r in stale):
            out.append(re.sub(r" p50 ms$", "", labels[field]))
    return out


def _lsqb_id_form_note(table_id, rows):
    """The id-form sentence for the graph analytics table, or None when
    every graph analytics row behind it ran LSQB's own text."""
    if table_id != "l2olap" or not _OCTOBER_ENV:
        return None
    names = _lsqb_id_form_queries(rows)
    if not names:
        return None
    # Only what holds for every query the sentence can name, on the build the
    # rows measured: at the pin (417314c18, config A, laptop) LSQB's text ran
    # faster on ArcadeDB than the id form for each of q5, q6, q8, and q9, with
    # and without the lane's view (perf-lsqb-q9-20261004 out/summary-all-runs.md,
    # recA1-oct and recA2-oct). Not "the operators it has": the hunt found
    # dedicated count operators for q5, q6, and q9, not for q8. Not "slows other
    # engines": that was measured on Neo4j and on q9 only. On newer main q5's
    # order reverses, hence "the build measured here".
    text = (f"In {_join_and(names)}, the check that two matched nodes are different compared "
            f"their id properties, where LSQB's own text compares the nodes themselves. The "
            f"answers are the same either way, but on the build measured here the id form "
            f"keeps ArcadeDB on a slower plan than LSQB's own text gets. The next measurement "
            f"runs LSQB's own text.")
    return _next_item("lsqb_text", _gen(text, *names))


# ARCADEDB'S GRAPH ANALYTICAL VIEW COVERS PERSON AND KNOWS ONLY (DECISIONS
# #154 item 3, found with F174). Both ArcadeDB adapters in l2_graph.py build
# the view with `VERTEX TYPES (Person) EDGE TYPES (KNOWS)`, and every LSQB
# query reads types outside it, so the view serves none of them; the table's
# own sentence calls the view "a copy of the graph". The re-pin builds it over
# every type, as ArcadeDB's documentation and upstream's own LSQB runner do,
# keeps the no-view arm as the like-for-like row, and writes `gav_types` (the
# types the view covers) into every ArcadeDB with-view graph analytics row
# (CAMPAIGN section 7 row 61); a with-view row without it built the narrow view.
_GAV_TYPES_FIELD = "gav_types"


def _gav_narrow_rows(rows):
    """The October ArcadeDB graph analytics rows that built the view over
    Person and KNOWS only, i.e. with-view rows without `gav_types`."""
    return [r for r in rows
            if r.get("lane") == "l2" and r.get("workload") == "olap"
            and str(r.get("instrument") or "") == "2026-10"
            and str(r.get("backend") or "").startswith("arcadedb")
            and str(r.get("gav")) != "False"
            and not str(r.get(_GAV_TYPES_FIELD) or "").strip()]


def _gav_scope_note(table_id, rows):
    """The narrow-view sentence for the graph analytics table, or None when
    every ArcadeDB with-view row behind it recorded the types its view covers."""
    if table_id != "l2olap" or not _OCTOBER_ENV or not _gav_narrow_rows(rows):
        return None
    return _next_item("gav_types", _gen(
        "In this measurement ArcadeDB's Graph Analytical View covers only the persons and their "
        "friendships. Every LSQB query reads kinds of node the view leaves out, so none of them "
        "can use it. The next measurement builds the view over every type in the graph and "
        "keeps the rows without the view beside it."))


# ARCADEDB'S SPARSE SEARCH RETURNS WHOLE RECORDS (DECISIONS #153 item 1). The
# timed ArcadeDB search, embedded and served, is `SELECT expand(
# vector.sparseNeighbors(...))`, which returns each hit's whole record (and
# its properties again), while every comparator is told to return ids
# (Qdrant `with_payload=False`, Elasticsearch `_source=False`, Milvus no output
# fields, pgvector `SELECT id`). The table said nothing about what each engine
# returns. The re-pin projects ArcadeDB to `SELECT id, score FROM (...)` and
# writes `sparse_result` into every ArcadeDB sparse row (CAMPAIGN section 7
# row 62); a row without it returned whole records. Off-page arms do not hold
# the sentence up.
_SPARSE_RESULT_FIELD = "sparse_result"


def _sparse_whole_record_rows(rows):
    """The October ArcadeDB sparse rows on the page that returned whole
    records, i.e. that do not record `sparse_result`."""
    return [r for r in rows
            if r.get("lane") == "l3s"
            and str(r.get("instrument") or "") == "2026-10"
            and str(r.get("backend") or "").startswith("arcadedb")
            and str(r.get("backend")) not in OFF_PAGE_ARMS
            and not str(r.get(_SPARSE_RESULT_FIELD) or "").strip()]


def _sparse_whole_record_note(table_id, rows):
    """The whole-record sentence for the sparse table, or None when every
    ArcadeDB sparse row behind it returned ids."""
    if table_id != "l3s" or not _OCTOBER_ENV or not _sparse_whole_record_rows(rows):
        return None
    return _next_item("sparse_ids", _gen(
        "On this table each ArcadeDB search returns every hit's whole record, while every other "
        "engine returns the ids of its hits, not the records. The next measurement has ArcadeDB "
        "return ids as well."))


# ARCADEDB EMBEDDED'S DOCUMENTS LOAD GOES ROW BY ROW (DECISIONS #153 item 2,
# the user's choice). The documents tables' ingest-path sentence already says
# what ran (insert_many, one JSON payload per batch, beside DuckDB's in-memory
# frames), so there is no table sentence; only the page-level list says what
# changes. The re-pin loads ArcadeDB embedded through the bindings' columnar
# insert once it ships (own issue #150) and writes `columnar_insert` into
# every ArcadeDB embedded documents row (CAMPAIGN section 7 row 63); a row
# without it loaded through insert_many.
_COLUMNAR_INSERT_FIELD = "columnar_insert"
_DOCS_TABLE_WORKLOAD = {"docs_oltp": "oltp", "docs_olap": "olap"}


def _docs_row_load_tables(tables, rows):
    """The titles of the documents tables on the page whose ArcadeDB
    (embedded) rows loaded through insert_many, i.e. lack `columnar_insert`."""
    stale = {str(r.get("workload")) for r in rows
             if r.get("lane") == "l1tpc"
             and str(r.get("instrument") or "") == "2026-10"
             and str(r.get("backend")) == "arcadedb_embedded"
             and not str(r.get(_COLUMNAR_INSERT_FIELD) or "").strip()}
    return [str(t.get("title") or t.get("id")) for t in tables
            if _DOCS_TABLE_WORKLOAD.get(t.get("id")) in stale]


def _equivalence_notes(rows):
    """table id -> one sentence about what its answer check could not compare."""
    import bench_common
    try:
        import equivalence_check as EQ
    except Exception:  # noqa: BLE001 - the page must not depend on the gate importing
        return {}
    groups, _skipped, _seen, _silent = EQ.collect(rows)
    per_table = collections.defaultdict(list)
    # ONE CLAUSE PER (query, reason), every engine that shares it named once:
    # "situation 'empty' issues no read" is true of every lifecycle engine, and
    # a clause per engine made this one sentence a loop's output.
    unexpr = collections.defaultdict(dict)
    for (lane, _scale, workload, query), by_backend in groups.items():
        tid = (EQUIVALENCE_TABLE_OF.get((lane, workload))
               or EQUIVALENCE_TABLE_OF.get((lane, None)))
        if not tid or tid == "lifecycle":
            continue
        why = EQ.NOT_COMPARABLE.get((lane, query))
        if why:
            per_table[tid].append(f"{query}: not compared across arms, because {why}")
        for be, digests in by_backend.items():
            for d in digests:
                if bench_common.is_unexpressible(d):
                    # THE REASON, NOT THE ATTEMPT. A declaration reads "<reason>;
                    # tried `<statement>` and the engine answered: <error>", and
                    # the error is the engine's own text: SurrealDB's parse errors
                    # carry positions like [1:8], digits with no source that
                    # page_check refuses, and with every lifecycle engine declared
                    # the sentence ran to 11,000 characters (rehearsing the
                    # 26.10.1 publish, 2026-10-02). The statement and the answer
                    # stay on the row, as the per-engine sentence says.
                    _why = str(d)[len(bench_common.UNEXPRESSIBLE_PREFIX):].split("; tried ", 1)[0]
                    unexpr[tid].setdefault((query, _why), set()).add(display_name(str(be)))
                elif bench_common.is_censored_answer(d):
                    # NOT "cannot express" (DECISIONS #120): the engine asked,
                    # and its budget stopped it before every start was answered.
                    # Named by the column the reader sees, not the field stem.
                    _labels = (_QUERY_BUDGET_TABLES.get(tid) or (None, None, {}))[2]
                    per_table[tid].append(
                        f"{display_name(str(be))}'s {_labels.get(query, query)} answer is not "
                        f"compared, because it "
                        f"{str(d)[len(bench_common.CENSORED_ANSWER_PREFIX):]}")
    for tid, by_reason in unexpr.items():
        for (query, why), names in by_reason.items():
            _n = sorted(names)
            per_table[tid].append(f"{_join_and(_n)} cannot "
                                  f"express {query}: {why}")
    out = {}
    _lc = _lifecycle_answer_note(groups)
    if _lc:
        out["lifecycle"] = _lc
    for tid, items in per_table.items():
        uniq = sorted(set(items))
        out[tid] = _gen("Every deterministic answer on this table is hashed and "
                        "compared across the engines before anything is published, "
                        "and a publish is refused when two of them disagree. What "
                        "that comparison could not cover, declared rather than "
                        "skipped: " + "; ".join(uniq) + ".", *uniq)
    return out


def _lifecycle_answer_note(groups):
    """The lifecycle table's answer check, in one sentence of what it compared.

    NOT the generic note. That one lists every declared absence with its
    reason, and on this table each engine's missing situations already have
    their own sentence (_lifecycle_table): with six embedded engines it ran to
    5,273 characters restating them (rehearsing the 26.10.1 publish,
    2026-10-02). This says only what those sentences do not: which situations'
    reads were compared with ArcadeDB's and how, which had nothing to compare
    with, and why the server rows stand apart. Derived from the gate's own
    groups (equivalence_check splits the lifecycle read by deployment), so a
    situation moves between the clauses when the rows do.
    """
    import bench_common
    emb = collections.defaultdict(set)    # situation -> embedded engines with an answer
    srv = collections.defaultdict(set)    # situation -> served engines with an answer
    reasons = collections.defaultdict(set)
    for (lane, _scale, workload, query), by_backend in groups.items():
        if lane != "lifecycle" or workload in LIFECYCLE_WITHHELD:
            continue
        served = query.endswith("@served")
        for be, digests in by_backend.items():
            for d in digests:
                if bench_common.is_unexpressible(d):
                    reasons[workload].add(str(d)[len(bench_common.UNEXPRESSIBLE_PREFIX):])
                elif not bench_common.is_censored_answer(d):
                    (srv if served else emb)[workload].add(be)
    sits = [k for k in LIFECYCLE_SITUATION_ORDER if k in emb or k in srv or k in reasons]
    if not sits:
        return None
    phrase = lambda k: LIFECYCLE_SITUATION_PHRASES.get(k, k)          # noqa: E731
    checked = [k for k in sits if len(emb.get(k, ())) >= 2]
    alone = collections.defaultdict(list)
    for k in sits:
        if len(emb.get(k, ())) == 1:
            alone[display_name(str(next(iter(emb[k]))))].append(k)
    nothing = [k for k in sits if not emb.get(k) and not srv.get(k)]
    parts = []
    if checked:
        parts.append(f"The rows each session reads back are hashed, and for "
                     f"{_join_and([phrase(k) for k in checked])} every embedded engine that "
                     f"builds the situation must return the same hash as ArcadeDB embedded, or "
                     f"nothing is published.")
    for who, ks in alone.items():
        parts.append(f"Only {who} builds {_join_and([phrase(k) for k in ks])}, so there is "
                     f"no second answer to compare.")
    if nothing:
        _why = []
        for k in nothing:
            r = " ".join(sorted(reasons.get(k, ())))
            if "approximate" in r:
                _why.append(f"{phrase(k)}, whose read goes through an approximate index and is "
                            f"checked by recall on the dense vector table instead")
            elif "no read" in r:
                _why.append(f"{phrase(k)}, which reads nothing back")
            else:
                _why.append(f"{phrase(k)}, for which no engine recorded a comparable answer")
        # Semicolons between the items, which carry their own commas.
        parts.append("Not compared: " + (_why[0] if len(_why) == 1 else
                                         "; ".join(_why[:-1]) + "; and " + _why[-1]) + ".")
    served = sorted({display_name(str(b)) for v in srv.values() for b in v})
    if served:
        parts.append(
            f"The server rows are compared only with other server rows, because a server "
            f"session runs a different set of modes and its record counts differ by "
            f"construction; "
            + (f"{served[0]} is the only engine served here, so they are compared with nothing."
               if len(served) == 1 else f"{_join_and(served)} are compared with each other."))
    return _gen(" ".join(parts), *[phrase(k) for k in sits], *alone, *served)


def _graph_first_pass_note(rows):
    """The graph table's read columns are the FIRST of two passes, said so.

    The graph lane times every read twice over the same start persons and the
    table prints the first pass (`point_p50_ms`; the second is
    `warm_point_p50_ms`, l2_graph's `_read_pass("warm_")`). Its rows still
    carry NA_COLD_WARM_TXN, "each operation runs against an already-built,
    already-warm database by construction", and for the engines on a JVM that
    is not true of the reads: the first pass includes the JIT compiling the
    query path. October's SF1 point p50 is 3.59x the second pass for ArcadeDB
    embedded, 1.46x served, and 2.13x for Neo4j, against 0.89x to 1.10x for
    every other engine. No ratio is quoted on the page (narrative about the
    numbers is written at the freeze, with pins); the sentence says what the
    column is. It says "includes" on purpose: at this pin the reads format the
    id into the query text, so a cache keyed on that text can also favour the
    second pass over the same ids, and the sentence holds either way.

    KEYED ON THE ROWS: a row without `read_warmup` was measured without the
    untimed warm-up on other start persons that the next measurement's lane
    records, and the sentence stays until no such row is behind the table. The
    JVM engines are named from the rows, by the heap they recorded, the same
    test _jvm_memory_note uses.
    """
    if not _OCTOBER_ENV:
        return None
    stale = [r for r in rows
             if r.get("lane") == "l2" and r.get("workload") == "oltp"
             and str(r.get("instrument") or "") == "2026-10"
             and not str(r.get("read_warmup") or "").strip()]
    if not stale:
        return None
    jvm = sorted({display_name(str(r.get("backend"))) for r in stale
                  if str(r.get("heap") or r.get("server_heap") or "").strip()})
    parts = ["Each read on this table is timed twice over the same start persons, and the "
             "table prints the first pass, so its read columns include each engine's warm-up."]
    if jvm:
        _one = len(jvm) == 1
        parts.append(f"On {_join_and(jvm)}, which {'runs' if _one else 'run'} on a JVM, that "
                     f"warm-up includes the JVM compiling the query path.")
    parts.append("The next measurement gives every engine an untimed warm-up on other start "
                 "persons first, prints the warm median, and adds the first query of a session "
                 "as the cold column.")
    return _next_item("warmup", _gen(" ".join(parts), *jvm))


# THE DOCUMENT OPERATIONS ARE TIMED FROM THE FIRST ONE AFTER THE LOAD
# (DECISIONS #157, found by the commit-cost hunt, `.notes/bench/repros/
# perf-commit-20261004/`). l1_tpc times its 1,000 new-orders right after the
# cell's load, then the payments and the four single-record operations, each
# leaving out only its first 20 from the percentiles, so the statements run
# for the first time inside the timed window. Its rows still stamp
# NA_COLD_WARM_TXN, "already-built, already-warm database by construction",
# and on the JVM engines that is not true: on the October rows ArcadeDB
# embedded's new-order is 2.34x (SF1) and 2.56x (SF10) its own payment, timed
# right after it, against 0.94x to 1.30x for every engine that is not on a
# JVM. No ratio is quoted on the page (narrative about the numbers is written
# at the freeze, with pins); the sentence says what the columns include. The
# durability table prints the same operations from the same rows, both
# classes, so it carries the sentence too.
#
# KEYED ON THE ROWS: the re-pin gives every engine an untimed warm-up on keys
# disjoint from and below the timed ones and writes `oltp_warmup` (the
# warm-up count) into every documents OLTP row (CAMPAIGN section 7 row 65); a
# row without it was timed from the first operation after the load, and the
# sentence stays until no such row is behind the table. The JVM engines are
# named from the rows, by the heap they recorded, as _graph_first_pass_note
# does; off-page arms are never named.
_OLTP_WARMUP_FIELD = "oltp_warmup"


def _docs_cold_window_rows(rows):
    """The October documents OLTP rows on the page timed from the first
    operation after the load, i.e. that do not record `oltp_warmup`."""
    return [r for r in rows
            if r.get("lane") == "l1tpc" and r.get("workload") == "oltp"
            and str(r.get("instrument") or "") == "2026-10"
            and str(r.get("backend")) not in OFF_PAGE_ARMS
            and not str(r.get(_OLTP_WARMUP_FIELD) or "").strip()]


def _docs_warmup_note(table_id, rows):
    """The warm-up sentence for the documents OLTP table and the durability
    table, or None when every documents OLTP row behind it recorded its
    untimed warm-up."""
    if table_id not in ("docs_oltp", "durability") or not _OCTOBER_ENV:
        return None
    stale = _docs_cold_window_rows(rows)
    if not stale:
        return None
    jvm = sorted({display_name(str(r.get("backend"))) for r in stale
                  if str(r.get("heap") or r.get("server_heap") or "").strip()})
    if table_id == "docs_oltp":
        parts = ["The operations on this table are timed from the first one after the data is "
                 "loaded, so its columns include each engine's warm-up."]
    else:
        parts = ["The document operations here are timed from the first one after the data is "
                 "loaded, so their cells include each engine's warm-up."]
    if jvm:
        _one = len(jvm) == 1
        parts.append(f"On {_join_and(jvm)}, which {'runs' if _one else 'run'} on a JVM, that "
                     f"warm-up includes the JVM compiling the statement path.")
    if table_id == "docs_oltp":
        parts.append("The next measurement gives every engine an untimed warm-up on separate "
                     "keys first, prints the warm median, and adds the first operation as the "
                     "cold column.")
    else:
        parts.append("The next measurement gives every engine an untimed warm-up on separate "
                     "keys first, and this table prints their warm median.")
    return _next_item("docs_warmup", _gen(" ".join(parts), *jvm))


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
    # The graph table's rows say "already warm by construction", and its read
    # columns are a first pass that is not (_graph_first_pass_note).
    if table_id == "l2":
        _first = _graph_first_pass_note(rs)
        if _first:
            return _first
    # So do the documents OLTP table's, and its operations are timed from the
    # first one after the load (_docs_warmup_note, DECISIONS #157).
    if table_id == "docs_oltp":
        _window = _docs_warmup_note(table_id, rs)
        if _window:
            return _window
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
    # The documents Q1 is not all of TPC-H Q1 until its rows are (BUGS F170):
    # the cold column names it as the table's own "Q1", which its query words
    # describe, rather than as TPC-H Q1.
    cold_names = (dict(COLD_QUERY_NAMES, q1="Q1")
                  if table_id == "docs_olap" and _partial_q1(rs) else COLD_QUERY_NAMES)
    names = sorted({cold_names.get(str(r.get("cold_first_query_name")),
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
    "These numbers were timed on a shared machine that was running other work at the "
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
    "shared machine that was running other work at the same time, with no cores set "
    "aside for the benchmark and one run per cell, so these times can be out "
    "by a large factor and the engines here cannot be compared with each "
    "other, or with the same table on the live page. The columns, the "
    "conditions, and the sizes are October's; the values are filler until the "
    "the real run measures them.")
# The two invariants that describe the BENCH HOST rather than the comparison.
# A laptop skeleton cannot satisfy either (no cpuset pinning, no per-scale
# memory envelope), and every other gate must pass exactly as it will in
# October. Named in the payload so the waiver is published, not assumed.
# What a laptop skeleton cannot draw, and why, published beside the banner so
# the reader is not left wondering whether a table was dropped or forgotten.
SKELETON_ABSENT = {
    "l3smp": "the second sparse pass is a separate run on the benchmark "
             "machine; this placeholder measures each benchmark once.",
    "l3d warm columns": "the dense warm pass comes from the same multipass "
                        "driver; the skeleton's dense table is cold only.",
    "e4": "the client/server decomposition is its own overlay, measured on "
          "the benchmark machine.",
    "pycost": "the Python-cost table comes from the binding suite's own "
              "measurements, which this placeholder run does not cover.",
    "the summary figure": "it is a ratio of every table against its best "
                          "comparator, and a ratio between two one-repetition "
                          "placeholder cells would look like a result while "
                          "being noise; it is drawn from the real measurements.",
}
# NAMED BY WHAT THEY ARE, not by our invariant numbers: "FAIRNESS F1" means
# nothing to a reader of the page, and the thing it labels -- cpuset pinning
# -- means everything.
SKELETON_WAIVERS = [
    "CPU pinning: the skeleton runs on a shared cpuset, not a "
    "pinned one.",
    "Memory envelope: this placeholder run uses the smallest memory caps, not "
    "the per-size limits the real measurements use.",
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
              if any(str(r.get("backend")).startswith("arangodb_dense") for r in _dense_rows_for_note()) else []),
            *(["ArangoDB's int8 row is the same IVF with the lists holding 8-bit scalar-quantized codes (the FAISS factory `IVF<nLists>,SQ8`), its nProbe calibrated to the same recall target as the fp32 row's."]
              if any(str(r.get("backend")) == "arangodb_dense_int8" for r in _dense_rows_for_note()) else []),
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
        # THE SKELETON'S OLTP CORPUS IS micro, NOT sf1. This branch carried
        # l2olap's value, and the two lanes ran different corpora on the
        # laptop: 22 OLTP rows at micro, and the OLAP slice at sf1. Filtering
        # the transactional table to sf1 left it with no rows at all, so the
        # whole table vanished from the preview -- a silent loss, because a
        # table with no entries is simply not emitted.
        "only_scales": {"micro"} if SKELETON else {"sf1", "sf10"},
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
                    # THE SPLIT, beside the total rather than replacing it (FAIRNESS F14).
                    # `ingest total s` keeps meaning what it has always meant, the whole of
                    # build(), so September's rows and October's say the same thing by that
                    # name. The two below say how that total divides, under the names the
                    # dense table has used since it was written. A row with no index_s --
                    # every September row, and any arm that builds no index -- does not fill
                    # them, and a column no row fills is dropped, so the split shows up
                    # exactly where it was measured.
                    ("ingest_s", "ingest s"),
                    ("index_s", "index s"),
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
        # 2026-09-12) and carries a disk cell. September's composed arm ran
        # its Qdrant half as :memory:, so its disk value is Neo4j's and is
        # printed as such (the condition below says so); October runs the
        # Qdrant server beside Neo4j in one container (DECISIONS #117, BUGS
        # F133) and October tables do not carry these conditions. The key
        # stays for the mechanism at the disk_data_mb skip; it was
        # surrealdb_e2 until 2026-09-13.
        "in_memory": (),
        "conditions": [
            "Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge, and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.",
            "So the interesting result here is not the speed. It is what a crash halfway through leaves behind. The raw data records, for each run, whether an interrupted write left the two stores disagreeing, and whether they still disagreed after restarting. That is what this comparison exists to show.",
            "Read the times with one caveat, which cuts against ArcadeDB. Every engine on this table writes to disk except the composed stack's vector half: Qdrant runs in memory (:memory:), so part of why the composed stack's queries answer as they do is that half of it never touches a disk. The all-or-nothing result above does not depend on this, since a half-finished update is visible in memory just as it is on disk, but the millisecond columns do.",
            "Because the composed stack's Qdrant half runs in memory, its disk value is Neo4j's alone. SurrealDB embedded runs on the SDK's SurrealKV store on disk and SurrealDB server on RocksDB, and each has its own disk reading.",
        ],
    },
    # THE SERVER RESTART (DECISIONS #139 item 2, l6_restart.py): what every
    # served engine costs to come back on the same data, and to go down
    # cleanly. October-only: no September row exists, so its conditions are
    # OCT_PROSE's and the list here stays empty.
    "restart": {
        "title": "Server restart",
        "dataset": "Each engine's own data on one model (documents, graph, dense vectors, or time series), restarted in place",
        "metrics": [("restart_total_s", "restart s"),
                    ("restart_start_s", "start s"),
                    ("restart_first_query_s", "first answer s"),
                    ("restart_after_write_s", "restart after writes s"),
                    ("shutdown_idle_s", "stop s"),
                    ("shutdown_write_s", "stop after writes s")],
        # The two MongoDB rows are two servers: the search arm's container also
        # runs mongot, which a restart has to bring back.
        "labels": {"mongodb_dense": "MongoDB + MongoDB Search",
                   "arcadedb_ts_native_server": "ArcadeDB (server)"},
        "conditions": [],
    },
}

GLOBAL_CONDITIONS = [
    "Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.",
    "Peak memory is the largest amount an engine held in its own address space, added over every container a run used, and it leaves out the file cache the kernel keeps on the engine's behalf. That is the right number for engines that manage their own memory, and an undercount for engines that lean on the kernel instead, so compare it down one engine's rows rather than across engines that work differently.",
    "Each printed cell is the median of 5 repetitions, with min and max carried alongside; nothing here is a single sample.",
    "Defaults first. Where a default would make the comparison meaningless, it is equalized and the override is disclosed rather than hidden.",
    "Comparators are pinned by sha256 image digest, not by a floating tag.",
    DISK_DETAIL,
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
        "time, on one shared machine. That machine was not doing only this: a browser, "
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
        "The benchmark machine is a mobile-class part in a small chassis and it "
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


_DEV_BUILD = re.compile(r"(dev\d*|SNAPSHOT)\b", re.I)


# WHAT THE NEXT MEASUREMENT CHANGES, ONE LINE PER CHANGE, on the page itself
# (the user, 2026-10-04: "let's write what'll change in the October page").
# Each line stands for a sentence under a table, and is printed only while that
# sentence is on the page: the helper that writes the table sentence (keyed on
# the rows) files it here under the line's key, and _next_measurement_note
# looks for it in the tables' conditions. So a line leaves the page on the same
# rows, and in the same publish, as the table sentence it summarises.
_NEXT_ITEM_SENTENCES = {}


def _next_item(key, text):
    """File `text`, a table sentence, under the page-level line `key`."""
    _NEXT_ITEM_SENTENCES.setdefault(key, set()).add(text)
    return text


def _arcadedb_dev_build_date(rows):
    """The date of the development build the ArcadeDB rows measured, read
    from the build timestamp the server stamps into `engine_version`
    ("26.10.1-SNAPSHOT (build <sha>/<epoch ms>/main)"), or None when the rows
    carry no timestamp or more than one date."""
    import datetime as _dt
    dates = set()
    for r in rows:
        ev = str(r.get("engine_version") or "")
        if not str(r.get("backend") or "").startswith("arcadedb") or not _DEV_BUILD.search(ev):
            continue
        m = re.search(r"/(\d{13})/", ev)
        if m:
            dates.add(_dt.datetime.fromtimestamp(int(m.group(1)) / 1000, _dt.timezone.utc)
                      .date().isoformat())
    return dates.pop() if len(dates) == 1 else None


def _next_measurement_note(tables):
    """WHEN "the next measurement" is and WHAT it changes, said for the page:
    a list of sentences, the first saying when and one per change after it.

    When: after this campaign (CAMPAIGN section 7, row 9). No date, because
    none is fixed. What: the release move, then one line per change a table
    sentence describes (_NEXT_ITEM_SENTENCES), then the `re-run` cells, then,
    when a table describes a change no line covers, a pointer to the notes.

    KEYED ON THE ROWS: the whole list is shown while the ArcadeDB rows behind
    the page are a development build, which is what this campaign measured,
    and while a table still defers something. Rows from a release take it off
    the page, and so does a page with nothing left to re-measure. Each line
    after the first is keyed on what its table sentence is keyed on. The one
    change no table sentence describes, ArcadeDB embedded's documents load
    (the tables' ingest-path sentence already says what ran), is keyed on its
    rows directly (_docs_row_load_tables).
    """
    if not _OCTOBER_ENV or SKELETON:
        return []
    dev = any(_DEV_BUILD.search(str(r.get("engine_version") or ""))
              for r in _FROZEN_ROWS if str(r.get("backend") or "").startswith("arcadedb"))
    if not dev:
        return []
    conds = [(t, str(c)) for t in tables for c in t.get("conditions") or []]
    filed = [s for ss in _NEXT_ITEM_SENTENCES.values() for s in ss]

    def carried_by(key):
        """The titles of the tables that carry a sentence filed under `key`."""
        ss = _NEXT_ITEM_SENTENCES.get(key) or ()
        return list(dict.fromkeys(str(t.get("title") or t.get("id"))
                                  for t, c in conds if any(s in c for s in ss)))

    rerun = any((cell or {}).get("text") == "re-run"
                for t in tables for e in t.get("entries") or []
                for cell in (e.get("metrics") or {}).values() if isinstance(cell, dict))
    other = any("the next measurement" in c.lower() and not any(s in c for s in filed)
                for _t, c in conds)
    items = []
    warm = carried_by("warmup")
    if warm:
        items.append(_gen(f"The {_join_and(warm)} reads get an untimed warm-up on other start "
                          f"persons, the table prints their warm median, and a cold column is "
                          f"added.", *warm))
    docs_warm = carried_by("docs_warmup")
    if docs_warm:
        # The cold column is the documents OLTP table's; the durability table
        # prints warm medians only. Its title is a phrase ("What waiting for
        # the disk costs"), so the line names it as the table on that phrase.
        titles = {t.get("id"): str(t.get("title") or t.get("id")) for t in tables}
        oltp = titles.get("docs_oltp") if titles.get("docs_oltp") in docs_warm else None
        dur = titles.get("durability") if titles.get("durability") in docs_warm else None
        dur_words = f"the table on {dur[:1].lower()}{dur[1:]}" if dur else None
        if oltp:
            text = (f"The {oltp} operations get an untimed warm-up on separate keys, the table "
                    f"prints their warm median and adds the first operation as a cold column"
                    + (f", and {dur_words} prints warm medians too" if dur else "") + ".")
        else:
            text = (f"The document operations on {dur_words} get an untimed warm-up on separate "
                    f"keys, and the table prints their warm median.")
        items.append(_gen(text, *docs_warm))
    if carried_by("full_sync"):
        nxt = str(_ARCADEDB_STRICT_NEXT)
        items.append(_gen(f"ArcadeDB's runs that wait for the disk use a data-only sync "
                          f"(`txWalFlush={nxt}`) instead of a full sync.", nxt))
    if carried_by("knows"):
        items.append(_gen("Every graph question is asked in both directions of a friendship."))
    lsqb = carried_by("lsqb_text")
    names = _lsqb_id_form_queries(_FROZEN_ROWS) if lsqb else []
    if lsqb and names:
        items.append(_gen(f"On the {_join_and(lsqb)} table, {_join_and(names)} "
                          f"{'runs' if len(names) == 1 else 'run'} LSQB's own text, which "
                          f"compares the matched nodes themselves rather than their ids.",
                          *lsqb, *names))
    gav = carried_by("gav_types")
    if gav:
        items.append(_gen(f"On the {_join_and(gav)} table, ArcadeDB's Graph Analytical View "
                          f"covers every type in the graph, not only the persons and their "
                          f"friendships, and the rows without the view stay.", *gav))
    q1 = carried_by("q1")
    if q1:
        items.append(_gen(f"The {_join_and(q1)} table runs the full TPC-H Q1.", *q1))
    docs = _docs_row_load_tables(tables, _FROZEN_ROWS)
    if docs:
        items.append(_gen(f"On the {_join_and(docs)} {'table' if len(docs) == 1 else 'tables'}, "
                          f"ArcadeDB (embedded) loads its data through the Python package's "
                          f"columnar insert, which takes whole columns at a time, as DuckDB "
                          f"takes whole frames.", *docs))
    sparse = carried_by("sparse_ids")
    if sparse:
        items.append(_gen(f"On the {_join_and(sparse)} table, ArcadeDB returns the ids of its "
                          f"hits, not the records, as every other engine does.", *sparse))
    if rerun:
        items.append(_gen("The cells marked `re-run` are measured again."))
    if not (items or other):
        return []
    date = _arcadedb_dev_build_date(_FROZEN_ROWS)
    build = f"the development build of {date}" if date else "the development build measured here"
    out = [_gen("The next measurement runs after this one is complete, and it makes the "
                "changes listed below."),
           _gen(f"ArcadeDB moves from {build} to its next release, and every other engine "
                f"to its latest stable release.", *([date] if date else []))]
    out += items
    if other:
        out.append(_gen("The notes under the tables describe the next measurement's other "
                        "changes."))
    return out


def _global_conditions(tables, october):
    reps = _reps_note(tables)
    if october:
        out = [_R("GLOBAL", "docker_skeleton" if SKELETON else "docker"), _R("GLOBAL", "memory")]
        if reps:
            out.append(reps)
        out += [_R("GLOBAL", "defaults"), _R("GLOBAL", "digest")]
        # The next measurement's list goes last, and is appended in main()
        # once _finish_table has run: it reads the finished tables' sentences.
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
    "default and a documented production mode for each of the others.")
# "Every engine's setting was read out of the engine rather than assumed" was
# printed under every table and was false for three kinds of row, each of which
# says so in its own `durability` string: the served ArcadeDB arms, whose flag is
# set on the server's JVM options and cannot be read back; the SurrealDB server,
# whose rows record that no setting was found (BUGS F165); and the sparse lane's
# three served comparators, which time no transactional write and record "engine
# default". The sentence now names them, read off the rows.
_DURABILITY_READ = "Each row records what it ran as `durability`"
_NOT_READ_BACK = "no read-back"
_DEFAULT_UNREAD = "engine default; no transactional write timed"

# OUR ENGINE LOADED THE CROSS-MODEL CATALOG WITH THE LOG OFF (BUGS F113).
# `graph_batch` turns the write-ahead log off for a bulk load unless asked not
# to, and the e2 arm did not ask until 12b2012b74 (2026-09-23), after every
# October e2 row was measured. The timed operations ran after the batch closed,
# with the log on; the ingest column did not. No field on the row records it, so
# the rows are dated against the fix commit's time, kept here as a constant so the
# export never asks git; a row with no readable time counts as before the fix, the
# direction that over-discloses for our own engine.
_F113_FIX = "12b2012b74"
_F113_FIX_UTC = "2026-09-22T20:44:12+00:00"   # `git show -s --format=%cI 12b2012b74`, in UTC
_F113_BACKENDS = {"arcadedb_e2"}


def _loaded_wal_off(r):
    """True for a cross-model ArcadeDB row measured before the F113 fix."""
    if str(r.get("backend")) not in _F113_BACKENDS:
        return False
    import datetime as _dt
    fix = _dt.datetime.fromisoformat(_F113_FIX_UTC)
    try:
        ts = _dt.datetime.fromisoformat(str(r.get("ts_utc") or "").replace("Z", "+00:00"))
    except ValueError:
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)
    return ts < fix


# ARCADEDB'S STRICT CLASS IS AN FSYNC, AND THE NEXT MEASUREMENT'S IS AN
# FDATASYNC. `txWalFlush=2` is FileChannel.force(true) (WALFile.YES_FULL): the
# log's data and metadata at every commit. SQLite's FULL in WAL mode is one
# fdatasync per commit, which is `txWalFlush=1` (force(false)), and upstream's
# own transactions documentation recommends 1 for production and says 2 adds
# no recovery value over it. The strict class moves to 1 at the re-pin
# (CAMPAIGN section 7, row 5, the user's decision of 2026-10-04), and the page
# says so beside the rows measured at 2. Keyed on the text those rows record,
# not on bench_common.DURABILITY_ARCADEDB_STRICT, which changes at the re-pin:
# the sentence goes when the last row recording the full sync does.
_ARCADEDB_FULL_SYNC = "txWalFlush=2: the WAL is flushed and synced at every commit"
_ARCADEDB_STRICT_NEXT = 1     # the re-pin's txWalFlush for the strict class


def _arcadedb_full_sync_note(rows):
    """(sentence, the values it inserted) for a table that shows ArcadeDB rows
    run at the full sync, or None. `rows` are the rows behind its cells."""
    if not _OCTOBER_ENV:
        return None
    full = [str(r.get("durability")) for r in rows
            if str(r.get("backend") or "").startswith("arcadedb")
            and str(r.get("durability") or "").startswith(_ARCADEDB_FULL_SYNC)]
    if not full:
        return None
    measured = re.match(r"txWalFlush=(\d+)", full[0]).group(1)
    nxt = str(_ARCADEDB_STRICT_NEXT)
    # "Was set to", not "synced": on this table a defect note says one
    # ArcadeDB arm's later commits skipped the log, and the setting is what
    # every arm's row records either way.
    text = (f"In the runs that wait for the disk, ArcadeDB was set to sync its write-ahead "
            f"log's data and metadata at every commit (`txWalFlush={measured}`, an fsync). "
            f"The next measurement uses `txWalFlush={nxt}` instead, a data-only sync "
            f"(fdatasync) like SQLite's FULL setting, which ArcadeDB's documentation "
            f"recommends for production and says recovers everything the full sync does.")
    return _next_item("full_sync", text), [measured, nxt]


def _durability_note(entries, rows, table_lane=None):
    """The durability sentence THIS table needs, from the engines it shows.

    Returns None for a table whose rows predate the 2026-10 instrument, so a
    September payload is untouched.

    EXACT LABELS, AND THE TABLE'S OWN LANE. A row counted when its label was a
    SUBSTRING of an entry's, so the graph lane's "Neo4j" rows matched the
    cross-model table's "Neo4j (vector index)" and that table named "Neo4j", an
    engine it has no row for, among its exceptions. And a row taken down
    (`outcome` withdrawn) prints no cell for the sentence to explain.
    """
    import bench_common
    want = {str(e.get("backend")) for e in entries if e.get("outcome") != "withdrawn"}
    seen = {}
    not_read_back, defaults, wal_off = set(), set(), set()
    shown = []
    for r in rows:
        if str(r.get("instrument") or "") != "2026-10":
            continue
        if table_lane and r.get("lane") != table_lane:
            continue
        lbl = display_name(str(r.get("backend") or ""))
        if lbl not in want:
            continue
        shown.append(r)
        cls = ("synced_default" if _SURREAL_SERVED_SYNCED(r)
               else bench_common.durability_class(r.get("durability")))
        if cls:
            seen.setdefault(cls, set()).add(lbl)
        dur = str(r.get("durability") or "")
        if _NOT_READ_BACK in dur:
            not_read_back.add(lbl)
        if dur.startswith(_DEFAULT_UNREAD):
            defaults.add(lbl)
        if _loaded_wal_off(r):
            wal_off.add(lbl)
    if not seen:
        return None
    unread = not_read_back | defaults | seen.get("synced_default", set())
    parts = [OCT_DURABILITY_CONDITION]
    if unread:
        parts.append(f"{_DURABILITY_READ}, and the setting was read out of the engine rather than "
                     f"assumed on every engine except {_join_and(sorted(unread))}.")
    else:
        parts.append(f"{_DURABILITY_READ}, and every engine's setting was read out of the engine "
                     f"rather than assumed.")
    if not_read_back:
        names = sorted(not_read_back)
        _one = len(names) == 1
        parts.append(f"{_join_and(names)} {'is' if _one else 'are'} given the setting when the server "
                     f"starts, and the row records it, because the server offers no way to read it back.")
    if defaults:
        names = sorted(defaults)
        _one = len(names) == 1
        parts.append(f"{_join_and(names)} {'runs' if _one else 'run'} at {'its' if _one else 'their'} "
                     f"defaults, and {'its row says' if _one else 'their rows say'} so without reading a "
                     f"setting back, because this table times no transactional write.")
    # An engine that has a knob has rows in both classes in the frozen set; the
    # exception is the engine with strict rows and no relaxed row (BUGS F52).
    _strict_only = seen.get("strict", set()) - seen.get("relaxed", set())
    if _strict_only:
        names = _join_and(sorted(_strict_only))
        _one = len(_strict_only) == 1
        parts.append(f"The {'exception' if _one else 'exceptions'} on this table {'is' if _one else 'are'} {names}, which "
                     f"{'has' if _one else 'have'} no setting to relax and "
                     f"{'waits' if _one else 'wait'} for the disk at every commit; "
                     f"{'its' if _one else 'their'} write and transaction cells are paying for that.")
    if seen.get("unverified"):
        names = _join_and(sorted(seen["unverified"]))
        parts.append(f"{names} exposes no durability setting at all and what it does at "
                     f"commit could not be established, so it is in neither class and its "
                     f"row says so rather than claiming one.")
    if seen.get("synced_default"):
        names = _join_and(sorted(seen["synced_default"]))
        parts.append(f"{names}'s rows record that no setting was found, and its server log shows "
                     f"what it ran: its default in both runs, a sync to disk at every commit (the log "
                     f"reads \"Sync mode: every transaction commit\" in every run), although it has a "
                     f"setting that does not wait; the next measurement runs both.")
    if wal_off:
        names = sorted(wal_off)
        _one = len(names) == 1
        parts.append(f"{_join_and(names)} loaded {'its' if _one else 'their'} catalog with the write-ahead "
                     f"log off, which the bulk-load helper {'it' if _one else 'they'} used does by default, "
                     f"so {'its' if _one else 'their'} ingest figures had less durability than the relaxed "
                     f"setting; {'its' if _one else 'their'} timed operations ran with the log on. The next "
                     f"measurement loads with the log on.")
    # Today no table reaches this with an ArcadeDB strict row: main() sets a
    # strict row aside wherever its cell has a relaxed one, and the durability
    # table, which shows them, says it in its own conditions. Here for a table
    # that ever shows one.
    _full_sync = _arcadedb_full_sync_note(shown)
    if _full_sync:
        parts.append(_full_sync[0])
    return _gen(" ".join(parts), *sorted(_strict_only | seen.get("unverified", set())
                                         | seen.get("synced_default", set()) | unread | wal_off),
                *(_full_sync[1] if _full_sync else ()))


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

    # AT THE PIN OR NOT, BY COMMIT. This compared the artifact's engine VERSION
    # with "26.9.1", September's release line, so once e4 was re-measured at
    # October's pin (a 26.10.1.dev0 build of 417314c18) it announced "not yet
    # re-run at the engine commit the rest of the page reports" over rows that
    # were. The page's pin is a commit, so the artifact is held to the commit:
    # every arm's engine_commit against BENCH_ENGINE_COMMIT, prefix either way
    # because one side may be truncated. No commit on the artifact is not at
    # the pin.
    _pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    _commits = {str(m.get("engine_commit") or "").strip()
                for m in (meta, meta.get("docker_client_conditions") or {})}
    _at_pin = bool(_pin) and all(c and (c.startswith(_pin) or _pin.startswith(c)) for c in _commits)
    return {
        "id": "e4",
        "title": "What the client/server split costs",
        "dataset": f"{meta.get('rows'):,}-document projection, one engine, three deployments",
        "conditions": [
            *([_gen(f"Measured at ArcadeDB {meta.get('engine_version')} on {str(meta.get('ts_utc'))[:10]}. This table has not yet been re-run at the engine commit the rest of the page reports; the re-run is queued and this line goes away with it.",
                    str(meta.get('engine_version')), str(meta.get('ts_utc'))[:10])]
              if str(meta.get("engine_version") or "") and not _at_pin else []),
            _gen(f"Every number is milliseconds. One engine build "
                 f"({_engine_identity(meta.get('engine_version'), meta.get('engine_commit'))}) in all three deployments, "
                 f"{meta.get('reps')} repetitions after {meta.get('warmup')} warmup, "
                 f"identical cpuset {meta.get('cpuset')}, memory cap {meta.get('mem_cap')} "
                 f"and heap {meta.get('heap')}.",
                 str(_engine_identity(meta.get('engine_version'), meta.get('engine_commit'))),
                 str(meta.get('reps')), str(meta.get('warmup')), str(meta.get('cpuset')),
                 str(meta.get('mem_cap')), str(meta.get('heap'))),
            _R("e4", "same_materialisation"),
            _R("e4", "same_machine"),
        ],
        "columns": [label for _, label in E4_ARMS],
        "withheld_scales": [],
        "withheld_reason": None,
        "entries": entries,
    }


L4_FILE = HERE / "results" / "l4_tsbs.jsonl"
L4_NATIVE = HERE / "results" / "ts_2681"

# One configuration, so these are constants of the experiment.
# The workload name only. "scale" lived here too and was a typed "2.59M
# points" that outlived the one-tier assumption it was written under; the size
# now comes from each row group's own tier through _l4_points.
L4_SHAPE = {"workload": "TSBS cpu-only"}

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
    "postgres_ts":        "postgresql",
    "duckdb":             "duckdb",
    # The plain-table comparators (2026-09-15), named like their rows on the
    # document and graph tables.
    "surrealdb_ts":        "SurrealDB (embedded)",
    "surrealdb_ts_server": "SurrealDB (server)",
    "arangodb_ts":         "ArangoDB",
}


def _l4_settle_note(settles):
    """How long every engine waited before a query was timed, from the rows.

    The registered sentence beside this one says sealing "makes the
    aggregation faster and the last-point query slower" and does not say by
    how long anyone waited. That magnitude is the whole difference between
    this page's newest-reading column and September's: September ran at the
    lane's default settle of 0 and read 0.42 ms, October waits and reads
    2.11 ms on the same corpus, same iteration count, same engine family.
    A reader moving between the two pages sees 5x and is handed the direction
    without the cause.

    Generated from `settle_s` rather than typed, so it cannot outlive the
    value it describes -- which is exactly how the corpus label two functions
    up came to name one tier while the table printed two.
    """
    vals = sorted({float(x) for x in settles
                   if x not in (None, "") and str(x) != "None" and float(x) > 0})
    if not vals:
        return []
    shown = _join_and([f"{v:g} seconds" for v in vals])
    return [_gen(
        f"Every engine was left to settle for {shown} after its ingest returned "
        f"and before any query was timed, outside the ingest timer. The wait is "
        f"the same for every engine, so the comparison below is unaffected by it; "
        f"a table measured without that wait reads a partly sealed store, where "
        f"the newest reading is cheaper to find.",
        *[f"{v:g}" for v in vals])]


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
            # KEYED ON THE TIER TOO. This grouped by display label alone,
            # which was right while the lane had one tier and silently wrong
            # the moment October added `ts1000`: every published cell became a
            # median across BOTH corpora -- 2,592,000 points and 25,920,000
            # together -- under a table labelled "2.59M points". ArcadeDB's
            # newest-reading p50 published as 2.3889 ms with n=10, where the
            # ts100-only median is 2.1124 and the ts1000-only one is 3.1835:
            # a number belonging to neither corpus, with its min taken from
            # one tier and its max from the other.
            #
            # All six gates passed on it. None of them compares a cell's row
            # count against the tiers its table claims to print.
            grouped[(label, str(r.get("scale")))].append(r)
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
    ("qdrant_uint8", "qdrant_sparse_uint8", "Qdrant (uint8)"),   # DECISIONS #135, 2026-10-02
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
# The same situations inside a sentence, in the lane's order, for the one
# declared-situations sentence each engine gets (_lifecycle_table).
LIFECYCLE_SITUATION_ORDER = ["empty", "doc", "doc_idx10", "graph", "graph_gav", "vector", "sparse", "ts"]
LIFECYCLE_SITUATION_PHRASES = {
    "empty": "the empty database", "doc": "documents", "doc_idx10": "documents with ten indexes",
    "graph": "the graph", "graph_gav": "the graph with the analytical view", "vector": "dense vectors",
    "sparse": "sparse vectors", "ts": "time series",
}


def _lifecycle_engine(backend):
    """The engine a lifecycle row belongs to: ArcadeDB for either deployment,
    else the comparator's display name without its deployment."""
    be = str(backend or "")
    return "ArcadeDB" if "arcadedb" in be else display_name(be).split(" (")[0]


def _lifecycle_row_label(backend, situation):
    """The label a lifecycle row prints: the situation first, then the engine
    for a comparator, then the deployment ("Graph (SurrealDB, embedded)").
    One definition for the measured rows and the censored ones, so a censored
    cell names the situation it was measuring rather than only the engine."""
    be = str(backend or "")
    mode = "server" if be.endswith("_server") else "embedded"
    name = LIFECYCLE_SITUATION_LABELS.get(situation, situation)
    engine = _lifecycle_engine(be)
    return f"{name} ({mode})" if engine == "ArcadeDB" else f"{name} ({engine}, {mode})"


def _or_series(items):
    """'a', 'a or b', 'a, b, or c' (the serial comma, as everywhere on the page)."""
    items = list(items)
    if len(items) <= 2:
        return " or ".join(items)
    return ", ".join(items[:-1]) + ", or " + items[-1]


def _lc_short_reason(text):
    """The head of a lifecycle declaration: the adapter's reason up to its
    first colon, without the statement it tried, the engine's answer, or any
    parenthetical (a documentation link or a filing number belongs on the row,
    not in a sentence on the page)."""
    why = text.split("; tried `", 1)[0]
    head = why.split(":", 1)[0]
    return re.sub(r"\s*\([^)]*\)", "", head).strip()

# Situations whose probe is not yet trustworthy. graph_gav's read reaches the
# view now (it is issued in cypher; SQL cannot reach a Graph Analytical View at
# all) but the same edit changed its SCOPE from 100 seeds to an unbounded
# whole-graph 2-hop, so its numbers describe the query written rather than the
# view. Withheld rather than published with a caveat nobody reads.
# The bounded seed set returns with the next measurement (CAMPAIGN section 7 row 34), not in this campaign.
LIFECYCLE_WITHHELD = {"graph_gav": "its query grew from a bounded set of seeds to an unbounded 2-hop, so it stays off this table until the next measurement bounds the query again."}   # PAGE-SPEC rule 7

# SURREALDB'S OCTOBER LIFECYCLE ROWS CARRY OUR INPUT LIST (BUGS F161, DECISIONS #134). Its build fed the
# engine from one in-memory Python list while the ArcadeDB arm streamed, fixed in the lane on 2026-09-30.
# The re-run of every SurrealDB lifecycle cell (qOA6) was stopped by decision, because the 26.10.1
# measurement re-runs them with the streamed input, so the October rows are all from before the fix. Two
# things on them carried our list and come down: each row's peak memory, and the 10M vector row, whose
# kill at the cap was our allocation (the kernel log names python), not SurrealDB's. The two other 10M
# kills named SurrealDB's own storage thread and stand, as does the 1M vector timeout; the session timings
# ran after the build and stand too. KEYED ON THE ROWS (the October pin), so the 26.10.1 rows are not
# recognised and the cells return at their landing with nothing to edit.
# (backend key, situation or None, scale or None, column or None for the whole entry) -> (why, stale)
_SURREAL_LIST = ("SurrealDB's peak memory on this table is withheld, and its 10M dense-vector cell is not shown: "
                 "our build fed SurrealDB from one in-memory Python list while the ArcadeDB arm streamed, so its "
                 "memory reading was partly ours, and the 10M vector build was killed for our allocation, not "
                 "SurrealDB's. Its session timings ran after the build and stand. Both are re-measured in the "
                 "next measurement, with the input streamed.")
_SURREAL_LIST_ROW = lambda r: str(r.get("engine_commit") or "").startswith("417314c18")   # noqa: E731
LIFECYCLE_STALE = {
    ("surrealdb_lifecycle", None, None, "peak memory GiB"): (_SURREAL_LIST, _SURREAL_LIST_ROW),
    ("surrealdb_lifecycle", "vector", "lc10m", None): (_SURREAL_LIST, _SURREAL_LIST_ROW),
}


def _lifecycle_stale(row):
    """The LIFECYCLE_STALE entry that takes this row's whole cell down, if any: the censored-cell
    reader must not print a withdrawn row's failure as the engine's."""
    for (bk, situation, scale, column), (why, pred) in LIFECYCLE_STALE.items():
        if (column is None and str(row.get("backend")) == bk
                and situation in (None, row.get("workload")) and scale in (None, str(row.get("scale")))
                and pred(row)):
            return why
    return None


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
                + _join_and(parts) + ")" + tail
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
        return _lifecycle_engine(r.get("backend", ""))

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

    entries, stale_notes = [], []
    _lc_columns = (["JVM start ms", "first open ms", "cold process ms"]
                   + [LIFECYCLE_SCENARIO_LABELS[k] for k in LIFECYCLE_PAGE_SCENARIOS])
    for (situation, scale, _srv, engine), rs in sorted(by.items()):
        if situation in LIFECYCLE_WITHHELD:
            continue
        _name = LIFECYCLE_SITUATION_LABELS.get(situation, situation)
        _ours = engine == "ArcadeDB"
        _mode = "server" if _srv else "embedded"
        entry = {
            "backend": _lifecycle_row_label(rs[0].get("backend"), situation),
            "backend_key": str(rs[0].get("backend")),
            "is_arcadedb": _ours,
            "engine": engine,
            "scale": scale,
            "scale_label": scale_label("lifecycle", scale),
            "workload": "session",
            "n_docs": str(rs[0].get("n_rows") or ""),
            "deployment": _mode,
            "image": _one_version(rs, f"lifecycle/{rs[0].get('backend')}/{scale}").get("image"),
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
        for (bk, sit, sc, column), (why, pred) in LIFECYCLE_STALE.items():
            if (bk != entry["backend_key"] or sit not in (None, situation) or sc not in (None, str(scale))
                    or not any(pred(r) for r in rs)):
                continue
            if column is None:
                entry["outcome"] = "withdrawn"
                entry["metrics"] = {c: {"text": "re-run"} for c in _lc_columns}
                _declare_absence("lifecycle", entry["backend"], None, "withdrawn", why)
            elif column in entry["metrics"]:
                entry["metrics"][column] = {"text": "re-run"}
                _declare_absence("lifecycle", entry["backend"], column, "withheld", why)
            else:
                continue
            if why not in stale_notes:
                stale_notes.append(why)
        if entry["metrics"]:
            entries.append(entry)

    if not entries:
        return None
    # The declared situations, ONE sentence per engine (2026-10-02): the
    # situations it cannot build, grouped by reason, each reason the head of
    # the adapter's own statement. One sentence per situation printed 21
    # near-identical sentences for four engines; the statement the adapter
    # tried and the engine's exact answer stay on the row and in the CSV. The
    # same fact, as data, is one whole-row absence per engine for the
    # coverage gate.
    by_engine = collections.defaultdict(dict)
    for r in declared:
        by_engine[_engine_of(r)][r.get("workload")] = _lc_short_reason(
            str(r.get("lifecycle_situation_unexpressible")))
    declared_notes = []
    if by_engine:
        declared_notes.append(_R("lifecycle", "declared"))
    for engine, sits in sorted(by_engine.items()):
        _label = f"{engine} (embedded)"
        groups = {}
        for sit in sorted(sits, key=lambda k: LIFECYCLE_SITUATION_ORDER.index(k)
                          if k in LIFECYCLE_SITUATION_ORDER else len(LIFECYCLE_SITUATION_ORDER)):
            groups.setdefault(sits[sit], []).append(LIFECYCLE_SITUATION_PHRASES.get(sit, sit))
        items = [f"{_or_series(names)} ({reason})" for reason, names in groups.items()]
        # Semicolons between the groups once a group is itself a list, so the
        # two levels of list do not run together.
        if len(items) == 1:
            joined = items[0]
        elif any(len(n) > 1 for n in groups.values()):
            joined = "; ".join(items[:-1]) + "; or " + items[-1]
        else:
            joined = _or_series(items)
        note = _gen(f"{_label} has no row for {joined}.", _label,
                    *[n for names in groups.values() for n in names], *groups)
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
           + [_gen(w) for w in stale_notes] + declared_notes
           + _engine_defect_notes("lifecycle", entries),
        "columns": _lc_columns,
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


def _durability_scope_note(entries):
    """What this table actually holds, counted from its own rows.

    The registered sentence said "Every timed write on the page is here: the
    six document operations, the three graph writes, and the cross-model
    transaction" -- a description of the table's DESIGN, printed whatever the
    table contained. The October campaign lands one lane at a time, so on the
    first landing the table held the cross-model transaction alone and said it
    held ten writes; on a graph-only landing it would have held three and said
    the same.

    The design sentence is still the right thing to say once every lane has
    landed, and it is what this returns then. Until then it names what is
    here and what is still to come, from the operations present rather than
    from a list typed beside them.
    """
    kinds = {"doc": 0, "graph": 0, "crossmodel": 0}
    for e in entries:
        op = str(e.get("scale") or "")
        if op.startswith("doc"):
            kinds["doc"] += 1
        elif op.startswith("graph"):
            kinds["graph"] += 1
        elif "crossmodel" in op:
            kinds["crossmodel"] += 1
    # One entry per engine per operation, so the operation count is what the
    # reader needs, not the row count.
    ops = {k: len({str(e.get("scale")) for e in entries
                   if str(e.get("scale") or "").startswith(k)
                   or (k == "crossmodel" and "crossmodel" in str(e.get("scale") or ""))})
           for k in kinds}
    # The cross-model transaction is one operation printed once per catalog
    # size (DURABILITY_PER_SCALE); it counts once.
    ops["crossmodel"] = min(ops["crossmodel"], 1)
    tail = ("Read down the operations for one engine rather than across the "
            "engines for one operation, because what the setting costs is a "
            "property of the engine's commit and the rest of the page already "
            "compares the engines.")
    if ops["doc"] >= 6 and ops["graph"] >= 3 and ops["crossmodel"] >= 1:
        return _R("durability", "every_write")
    have = _join_and([f"{n} {name}" for n, name in
                      ((ops["doc"], "document operation" + ("s" if ops["doc"] != 1 else "")),
                       (ops["graph"], "graph write" + ("s" if ops["graph"] != 1 else "")),
                       (ops["crossmodel"], "cross-model transaction"))
                      if n])
    return _gen(
        f"This table holds {have}. The campaign measures ten timed writes in "
        f"all -- six document operations, three graph writes and the "
        f"cross-model transaction -- and the rest appear here as the runs "
        f"that produce them finish. {tail}",
        *[str(ops[k]) for k in ("doc", "graph", "crossmodel") if ops[k]])


# KNOWN ENGINE DEFECTS AT THE MEASURED BUILD (2026-09-23). A cell can be
# measured correctly and still not mean what its column says, because the
# engine under test had a defect that changes what the operation does. The
# durability table published ArcadeDB's embedded cross-model commit at a
# "cost of waiting" of 1.01x -- durable for free -- and the reason is an engine
# defect, not a property: after an LSM_VECTOR index is built, later commits in
# the same session skipped the write-ahead log entirely, so there was nothing
# to wait for. Filed as ArcadeData/arcadedb#8129, fixed by #8221 (merge
# a618b3ae5a) for 26.10.1, verified on the laptop against cbd0947c18.
#
# The campaign holds its pin, so the row stays and the page says why. Each note
# RETIRES ITSELF: it prints only while the fix commit is not an ancestor of the
# pin being published, so at the re-pin to a build that carries the fix it
# disappears without anyone having to remember to delete it. When git cannot
# answer -- the pin is unknown to this checkout -- it prints: for a number that
# flatters our own engine, over-disclosing is the safe direction.
ENGINE_DEFECTS_AT_PIN = {
    # ArcadeDB #8852 (ours, 2026-10-01; fixed by PR #8863, merge 09a7aeff90, after the
    # October pin 417314c18): the first vector search after a reopen re-reads every
    # vector's document on one thread. The lifecycle sessions that search after opening
    # (one query, write then query) are dominated by it from 1M up at the pin: 853 and
    # 897 ms at 1M (open and close 98 and 16), 17.9 and 18.1 s at 10M (1.4 s and 15 ms),
    # embedded and server alike. One entry names the embedded row and speaks for both.
    "lifecycle": [{
        "backend": "Dense vectors (embedded)",
        "fix": "09a7aeff90",
        "issue": "8852",
        "release": "26.10.1",
        "text": ("The dense-vector rows' one-query and write-then-query sessions, embedded and server alike, "
                 "carry a defect in the engine build measured here, ArcadeDB issue #{issue} "
                 "(https://github.com/ArcadeData/arcadedb/issues/{issue}): the first vector search after a "
                 "database is reopened re-reads every vector's record on one thread, so from a million vectors "
                 "up those sessions are mostly that re-read, and ArcadeDB {release} fixes it."),
    }],
    "durability": [{
        "backend": "ArcadeDB (one transaction)",
        "fix": "a618b3ae5a",
        "issue": "8129",
        "release": "26.10.1",
        "text": ("{backend} shows almost no cost of waiting because of a defect in the "
                 "engine build measured here, ArcadeDB issue #{issue} "
                 "(https://github.com/ArcadeData/arcadedb/issues/{issue}): after the "
                 "vector index is built, later commits in the same session skip the "
                 "write-ahead log, so there is nothing to wait for, and ArcadeDB "
                 "{release} fixes it."),
    }],
}


def _pin_carries(fix, pin):
    """True when commit `fix` is an ancestor of `pin` in this checkout."""
    if not pin:
        return False
    try:
        return subprocess.run(
            ["git", "-C", str(HERE), "merge-base", "--is-ancestor", fix, pin],
            capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _engine_defect_notes(table_id, entries):
    """One generated sentence per known defect whose arm is on this table and
    whose fix the published pin does not carry."""
    pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    names = {str(e.get("backend")) for e in entries}
    out = []
    for d in ENGINE_DEFECTS_AT_PIN.get(table_id, []):
        if d["backend"] in names and not _pin_carries(d["fix"], pin):
            out.append(_gen(d["text"].format(**d), d["issue"], d["release"]))
    return out


# OPERATIONS WHOSE COST GROWS WITH THE CORPUS: one row per corpus size, never a
# median pooled across sizes (_durability_table, "ACROSS CORPORA ON PURPOSE").
DURABILITY_PER_SCALE = {"crossmodel_txn"}

# SurrealDB's graph insert ran as two transactions at the October pin (BUGS F130);
# the re-pin's rows carry another commit.
_F130_ROW = lambda r: str(r.get("engine_commit") or "").startswith("417314c18")   # noqa: E731


def _durability_corpus(lane, scale):
    """The corpus size a per-size durability row names, from the lane's own constant."""
    if lane == "e2":
        return f"{_e2_products(scale)} products"
    return scale_label(lane, scale)


def _durability_scale_rank(lane, scale):
    """Smallest corpus first, so the 50k row precedes the 500k one."""
    if scale is None:
        return 0
    if lane == "e2":
        from e2_hybrid import SCALE_PRODUCTS  # noqa: E402
        return int(SCALE_PRODUCTS.get(scale, 0))
    return SCALE_ORDER.index(scale) if scale in SCALE_ORDER else len(SCALE_ORDER)


def _durability_stale(lane, workload, field, backend, scale):
    """The STALE_UNTIL_RERUN reason that withholds this write on its own table,
    or None. A whole-row entry withholds every write of that backend; a column
    entry withholds the write only when the column is the one this operation
    reads (by OCT_TABLE_METRICS' field -> label mapping)."""
    src_tid = EQUIVALENCE_TABLE_OF.get((lane, workload))
    src_col = next((lbl for f, lbl in OCT_TABLE_METRICS.get(lane, []) if f == field), None)
    for (tid, bkey, column, only_scale), (why, pred) in STALE_UNTIL_RERUN.items():
        if tid != src_tid or bkey != backend:
            continue
        if column is not None and column != src_col:
            continue
        if only_scale is not None and scale is not None and str(only_scale) != str(scale):
            continue
        if pred is _SURREAL_SERVED_SYNCED:
            # DECISIONS #136 item 1: a synced write is exactly what the waiting column measures
            continue
        if _stale(tid, bkey, only_scale if only_scale is not None else scale, pred):
            return why
    return None


def _no_knob_sentence(no_knob):
    """Why each engine with no durability setting prints one number, with the evidence it actually has:
    DuckDB and LadybugDB were traced (strace counted one sync per commit, bench_common), Neo4j's sync at
    commit is its documented behaviour behind a SHOW SETTINGS that offers no durability setting."""
    documented = [b for b in no_knob if "neo4j" in b.lower()]
    on_duckdb = [b for b in no_knob if "duckpgq" in b.lower()]   # DuckDB with an extension: DuckDB's trace is its trace
    traced = [b for b in no_knob if b not in documented and b not in on_duckdb]
    parts = []
    if traced:
        clause = f"{_join_and(traced)} {'were' if len(traced) > 1 else 'was'} traced to a sync at every commit"
        if on_duckdb and any(b.lower() == "duckdb" for b in traced):
            clause += f", and {_join_and(on_duckdb)} {'run' if len(on_duckdb) > 1 else 'runs'} on DuckDB"
        parts.append(clause)
    if documented:
        parts.append(f"{_join_and(documented)} {'force' if len(documented) > 1 else 'forces'} "
                     f"{'their' if len(documented) > 1 else 'its'} log at commit as "
                     f"{'they document' if len(documented) > 1 else 'it documents'}, and "
                     f"{'offer' if len(documented) > 1 else 'offers'} no setting that changes it")
    verb = "have" if len(no_knob) > 1 else "has"
    return (f"{_join_and(no_knob)} {verb} no setting to relax: {'; '.join(parts)}. So each prints one "
            f"number, in the column for a commit that waits. Reading it against the other column would be "
            f"reading a choice the engine does not offer.")


def _durability_table(all_rows):
    """The same write per engine at both durability settings, with the ratio.

    An engine with no setting (Neo4j, DuckDB, LadybugDB) runs the same way in
    both cells, as the SurrealDB 3.2.4 server did at the October pin (its
    default, a sync at every commit, in both; BUGS F165), so printing its two numbers as a
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
    withdrawn = {}        # display name -> [operation label, ...]
    waiting_rows = []     # the rows behind the printed waiting-column cells
    for lane, workload, field, op_key, op_label in DURABILITY_WRITES:
        rows = [r for r in all_rows
                if r.get("lane") == lane and r.get("workload") == workload
                and str(r.get("instrument") or "") == "2026-10"]
        per_scale = op_key in DURABILITY_PER_SCALE
        by = {}
        for r in rows:
            # The tuned PostgreSQL arm is an ablation of one engine's image
            # defaults, and it reads as a second engine on a table (DECISIONS
            # #76). It is kept out of the document tables for that reason and
            # out of this one for the same reason.
            if str(r.get("backend")) in OFF_PAGE_ARMS:
                continue
            by.setdefault((str(r.get("backend")), str(r.get("scale")) if per_scale else None),
                          []).append(r)
        for (backend, sc), rs in sorted(by.items(), key=lambda kv: (_durability_scale_rank(lane, kv[0][1]),
                                                                     kv[0][0])):
            if sc is not None:
                # ONE ROW PER CORPUS SIZE for an operation whose cost grows with
                # the corpus, named in the Size column beside the operation.
                op_key_s = f"{op_key}_{_durability_corpus(lane, sc).split()[0]}"
                op_label_s = (op_label[:-1] + f", {_durability_corpus(lane, sc)})"
                              if op_label.endswith(")") else f"{op_label}, {_durability_corpus(lane, sc)}")
            else:
                op_key_s, op_label_s = op_key, op_label
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
                "scale": op_key_s,
                "scale_label": op_label_s,
                "workload": "write",
                "n_docs": None,
                "deployment": deployment_of(backend),
                "image": _one_version(rs, f"durability/{backend}/{op_key_s}").get("image"),
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
            # NOT rs[0]. The note class decides which sentence explains this
            # engine's single number, and reading it off whichever row happens
            # to sit first in the file is reading one row and calling it the
            # set. DuckPGQ has 17 rows: 15 carry "fsync at commit, not
            # configurable" and 2 early ones carry no durability string at
            # all. The unstamped one sorted first, `durability_class(None)`
            # answered neither "strict" nor "unverified", and DuckPGQ printed
            # a number in the waiting column that NO condition on the table
            # accounted for -- the one engine of six in that column with
            # nothing saying why it is there.
            #
            # Decided by what the stamped rows say, with the unstamped ones
            # ignored rather than allowed to win by position. They are stale,
            # the stamp reached the adapter afterwards, and a row that says
            # nothing should not outvote fifteen that agree.
            _stamped = [r for r in rs if str(r.get("durability") or "").strip()]
            _classes = collections.Counter(
                bench_common.durability_class(r.get("durability")) for r in _stamped)
            entry["_durability_note_class"] = (
                _classes.most_common(1)[0][0] if (no_setting and _classes) else None)
            # BUGS F165: the SurrealDB server's rows say "not verified", and
            # what they ran is now known from its own log: a sync at every
            # commit, its default, in both cells. The setting existed; the
            # harness missed it. Its own sentence, not the unknown's.
            if no_setting and _stamped and all(_SURREAL_SERVED_SYNCED(r) for r in _stamped):
                entry["_durability_note_class"] = "synced_default"
            # ACROSS CORPORA ON PURPOSE, AND MEASURED BEFORE SAYING SO. Each
            # row here is one engine running ONE operation, and the graph
            # lane times its writes at both sf1 and sf10, so these rows span
            # two corpora. That is why the table's Size column names the
            # operation rather than a size.
            #
            # It is only defensible because the operation is a SINGLE record
            # and does not depend on how much is already there. Checked at the
            # October pin before passing the flag: ArcadeDB's delete is 0.494
            # ms at sf1 against 0.464 at sf10, its strict update 8.435 against
            # 8.591, Neo4j's delete 6.062 against 6.452 -- within 6% on every
            # pair. Compare the time-series lane, where the same span put
            # 2.1124 and 3.1835 into one number (BUGS F110): there the corpus
            # decides the answer, here it does not.
            #
            # If a write is ever added whose cost grows with the corpus, this
            # flag is the line that has to be revisited.
            #
            # AND ONE WAS, from the start: the cross-model transaction searches
            # the vector index and expands a hop over the whole catalog, so its
            # cost grows with the catalog, and pooling its 50k and 500k rows
            # put two corpora into one median (ArcadeDB's server row: 7.52 ms
            # at 50k and 7.92 at 500k pooled to 7.66; PostgreSQL + AGE's 4.93
            # and 13.08 to 8.95). It is in DURABILITY_PER_SCALE and gets one
            # row per catalog size, where the flag stays off.
            _span = not per_scale
            if no_setting:
                got = _agg(rs, field, across_scales=_span)
                if got is not None:
                    entry["metrics"]["waits for the disk ms"] = got
            else:
                rel = _agg(relaxed, field, across_scales=_span)
                strc = _agg(strict, field, across_scales=_span)
                if rel is not None:
                    entry["metrics"]["no wait ms"] = rel
                if strc is not None:
                    entry["metrics"]["waits for the disk ms"] = strc
                if rel and strc and rel["median"]:
                    ratio = strc["median"] / rel["median"]
                    entry["metrics"]["cost of waiting"] = {
                        "median": round(ratio, 2), "min": round(ratio, 2),
                        "max": round(ratio, 2), "n": min(rel["n"], strc["n"])}
            # A WRITE WITHHELD ON ITS OWN TABLE IS WITHHELD HERE TOO. This
            # table re-reads the rows the write tables print, and it did not
            # read STALE_UNTIL_RERUN, so a cell marked `re-run` on its own
            # table (Neo4j's and the composed stack's cross-model rows, the
            # SurrealDB server's writes) printed here as a measurement, and
            # ArangoDB's cross-model pair compared a configuration without its
            # index against one with it (BUGS F168). The same entries, keyed
            # the same way, so the cells return here when they return there.
            if entry["metrics"] and _durability_stale(lane, workload, field, backend, sc):
                entry["metrics"] = {c: {"text": "re-run"} for c in entry["metrics"]}
                entry["outcome"] = "withdrawn"
                entry["version_name"] = None
                withdrawn.setdefault(entry["backend"], []).append(op_label_s)
            if entry["metrics"]:
                entries.append(entry)
                if not entry.get("outcome") and "waits for the disk ms" in entry["metrics"]:
                    waiting_rows.extend(rs if no_setting else strict)
    if not entries:
        return None
    # The sentences below explain the numbers a row PRINTS, so a row taken
    # down is not one of the engines they name.
    _shown = [e for e in entries if not e.get("outcome")]
    _no_knob = sorted({e["backend"] for e in _shown
                       if e.get("_durability_note_class") == "strict"})
    _unverified = sorted({e["backend"] for e in _shown
                          if e.get("_durability_note_class") == "unverified"})
    _synced_default = sorted({e["backend"] for e in _shown
                              if e.get("_durability_note_class") == "synced_default"})
    for e in entries:
        e.pop("_durability_note_class", None)
    _gone = sorted(withdrawn)
    _gone_note = (_gen(f"{_join_and(_gone)} {'have' if len(_gone) > 1 else 'has'} cells marked `re-run` "
                       f"here because the same writes are withheld on the table{'s' if len(_gone) > 1 else ''} "
                       f"they come from, and the note under each of those tables says why.", *_gone)
                  if _gone else None)
    for name in _gone:
        _declare_absence("durability", name, None, "withdrawn", _gone_note)
    # TWO TRANSACTIONS WHERE THE OPERATION IS ONE (BUGS F130). At the October
    # pin SurrealDB's graph insert sends `CREATE person ...; RELATE ...` with
    # no BEGIN/COMMIT around them, and SurrealDB commits each statement of
    # such a request on its own, so its strict cell waits for the disk twice
    # per insert. The re-pin wraps them in one transaction; keyed on the rows
    # at this pin, so the sentence goes when the re-pin's rows arrive.
    _two_txn = sorted({e["backend"] for e in _shown
                       if e.get("scale") == "graph_insert" and e["backend"].startswith("SurrealDB")
                       and any(_F130_ROW(r) for r in all_rows
                               if r.get("lane") == "l2" and r.get("workload") == "oltp"
                               and display_name(str(r.get("backend"))) == e["backend"])})
    _two_txn_note = (_gen(f"{_join_and(_two_txn)} {'send' if len(_two_txn) > 1 else 'sends'} the graph insert's person and its edge as two "
                          f"statements with no transaction around them, so each commits on its own: "
                          f"the run that waits for the disk waits twice for each insert, and the cost "
                          f"of waiting on that row counts both. The next measurement wraps the two in "
                          f"one transaction.", *_two_txn)
                     if _two_txn else None)

    def _verb(names):
        return "have" if len(names) > 1 else "has"
    # EVERY SINGLE NUMBER IS ACCOUNTED FOR, or the table does not publish.
    # A cell in the waiting column with nothing in the other one is the table
    # saying "this engine had no choice", and a reader can only take that on
    # trust if a condition names the engine and says how we know. DuckPGQ
    # printed exactly that cell, unexplained, because the note class was read
    # off whichever row sorted first. Refusing here is the capability table's
    # rule -- refuse the kind you cannot define rather than printing it and
    # hoping -- applied to the one other table that prints a lone number.
    _explained = set(_no_knob) | set(_unverified) | set(_synced_default)
    _lone = sorted({e["backend"] for e in _shown
                    if e["metrics"].get("waits for the disk ms")
                    and not e["metrics"].get("no wait ms")}
                   - _explained)
    if _lone:
        raise SystemExit(
            f"REFUSING to publish the durability table: {_lone} print a number in "
            f"the waiting column and nothing in the other one, and no condition "
            f"names them. That cell claims the engine offers no choice; unexplained "
            f"it is indistinguishable from a setting that failed to take. Stamp the "
            f"engine's `durability` on its rows, or add the sentence that says how "
            f"its behaviour at commit was established.")
    # ArcadeDB's waiting column is a full sync until the re-pin's rows arrive.
    _full_sync = _arcadedb_full_sync_note(waiting_rows)

    return {
        "id": "durability",
        "title": "What waiting for the disk costs",
        "dataset": "Every timed write, run twice, once at each durability setting",
        "conditions": [
            _R("durability", "pairs"),
            _durability_scope_note(entries),
            _R("durability", "read_control"),
            _R("durability", "size_column"),
            _R("durability", "cell_property"),
            *([_gen(_no_knob_sentence(_no_knob), *_no_knob)] if _no_knob else []),
            *([_gen(f"{_join_and(_unverified)} {_verb(_unverified)} no durability "
                    f"setting to read and what {'they do' if len(_unverified) > 1 else 'it does'} "
                    f"at commit could not be established from the engine, so the one "
                    f"number printed is in neither class. It is placed in the "
                    f"waiting column because that is the safer reading of an "
                    f"unknown, and this line is why it is there.", *_unverified)] if _unverified else []),
            *([_gen(f"{_join_and(_synced_default)} ran at {'their' if len(_synced_default) > 1 else 'its'} "
                    f"default in both runs, a sync to disk at every commit: the server log of every run "
                    f"reads \"Sync mode: every transaction commit\", and a trace counts one sync per "
                    f"commit. So the one number printed is in the waiting column. "
                    f"{'They have' if len(_synced_default) > 1 else 'It has'} a setting that does not "
                    f"wait, which our harness missed, and the next measurement runs both.",
                    *_synced_default)] if _synced_default else []),
            *([_gen(_full_sync[0], *_full_sync[1])] if _full_sync else []),
            *_engine_defect_notes("durability", _shown),
            *([_two_txn_note] if _two_txn_note else []),
            *([_gone_note] if _gone_note else []),
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
# POSTGRESQL + AGE JOINS THE CAPABILITY TABLE (DECISIONS #131 item 9, from the
# 26.10.1 measurement). It is one engine on two tables under two names: the
# graph arm (pgage_graph, "PostgreSQL + AGE") and the cross-model arm
# (pg_age_e2, "PostgreSQL + pgvector + AGE", which also loads pgvector), both on
# the dbbench:pg-age image, so the table folds them into one row. PostgreSQL's
# other arms (documents, pgvector, TimescaleDB) run other images and stay their
# own engines on their own tables.
MULTIMODEL_ENGINES = ("ArcadeDB", "ArangoDB", "MongoDB", "SurrealDB", "PostgreSQL + AGE")
MULTIMODEL_ALIASES = {"PostgreSQL + pgvector + AGE": "PostgreSQL + AGE"}


def multimodel_engine(name):
    """The capability table's row for an engine name (MULTIMODEL_ALIASES)."""
    return MULTIMODEL_ALIASES.get(name, name)
MULTIMODEL_CELLS = {"measured": "measured", "declared": "declared", "none": "no arm"}
MULTIMODEL_KINDS = {"censored": "censored", "withheld": "withheld",
                    "unexpressible": "cannot express", "envelope": "out of memory",
                    "failed": "failed",
                    # "withdrawn" is not "withheld": a withheld cell is one
                    # number pulled from a row that stands, a withdrawn one is
                    # the whole row taken down until it is measured again.
                    "withdrawn": "withdrawn",
                    # A row a defect in the engine's own release decided
                    # (_not_comparable_entries), marked `n/c` on its table.
                    "not comparable": "not comparable"}


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
            if multimodel_engine(entry_engine(e)) == engine and not e.get("outcome")]
    if rows:
        return MULTIMODEL_CELLS["measured"], []
    kinds = sorted({str(a.get("kind")) for a in table.get("declared_absences") or []
                    if multimodel_engine(engine_family(a.get("backend"))) == engine})
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
    # THE MODE COLUMN NAMES DEPLOYMENTS, and "all three" is not one. The
    # client/server split table labels its rows "all three" because each row
    # holds the in-process, in-process-server, and separate-container arms;
    # read as a deployment it printed "all three, embedded, server" for
    # ArcadeDB. Its three arms are the embedded engine and two servers.
    _MODE_OF = {"all three": ("embedded", "server")}
    for engine in MULTIMODEL_ENGINES:
        modes = sorted({m for t in sources
                        for e in t.get("entries", [])
                        if multimodel_engine(entry_engine(e)) == engine and e.get("deployment")
                        for m in _MODE_OF.get(str(e.get("deployment")), (str(e.get("deployment")),))})
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
            # ONE SPELLING BEFORE THE SET, not after it: the payload's version
            # strings lose a leading "v" only when the payload is written
            # (_one_spelling), so "surrealdb v3.2.4" and "surrealdb 3.2.4" were
            # two members here and printed as "surrealdb 3.2.4" twice.
            "version_name": " / ".join(sorted({
                _one_spelling(str(e["version_name"])) for t in sources
                for e in t.get("entries", [])
                if multimodel_engine(entry_engine(e)) == engine and isinstance(e.get("version_name"), str)
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
        # NOT THE SAME AS withheld. Withheld is one number pulled from a row
        # that stands; withdrawn is the whole row taken down until it is
        # measured again. It said "the query it answered was not the one the
        # other engines answered", which fits a stand-in engine (BUGS F133) and
        # not a row measured before its own index existed (F168).
        "withdrawn": "withdrawn, the row was measured before a fix to our harness and "
                     "came down until it is measured again",
        "unrun": "not run, the placeholder run did not cover this "
                 "workload for that engine",
        "not comparable": "not comparable, a defect in the engine's own release decided "
                          "the result, and the note under that table names it",
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
        # A LANE SCOPED OUT IS NOT A MISSING ARTIFACT, the third place today
        # that needed this told apart (make_paper_tables and
        # make_paper_figures are the others). The refusal is right when l4
        # belongs in the freeze and its rows are absent -- the legacy readers
        # were retired on purpose and a silent fallback is what that retirement
        # prevents. It is wrong when a per-lane landing deliberately left l4
        # out: the table simply does not appear, the way a table with no rows
        # never appears.
        _only = {x.strip() for x in os.environ.get("BENCH_ONLY_LANES", "").split(",") if x.strip()}
        if _only and "l4" not in _only:
            print(f"  l4 table omitted: not in this landing's lanes "
                  f"({','.join(sorted(_only))})")
            return None
        raise SystemExit("no canonical l4 rows at the pin; the legacy l4_tsbs.jsonl/ts_2681 readers were retired 2026-09-08")
    if not grouped:
        return None

    order = ["ArcadeDB (embedded, native time series)", "ArcadeDB (embedded, document path)",
             "questdb", "duckdb", "sqlite", "mongodb", "timescaledb", "postgresql",
             "SurrealDB (embedded)", "SurrealDB (server)", "ArangoDB"]
    # This lane predates runner.BACKENDS and keeps its own adapters, so the
    # topology lookup does not reach it. QuestDB is a server (ILP ingest on
    # 9009, SQL over pg-wire, see l4_tsbs.py); the other two run in-process.
    L4_DEPLOYMENT = {"ArcadeDB (embedded, native time series)": "embedded",
                     "ArcadeDB (server, document path)": "server",
                     "ArcadeDB (server, native time series)": "server",
                     "ArcadeDB (embedded, document path)": "embedded",
                     "questdb": "server", "duckdb": "embedded", "sqlite": "embedded", "mongodb": "server", "timescaledb": "server", "postgresql": "server",
                     "SurrealDB (embedded)": "embedded", "SurrealDB (server)": "server", "ArangoDB": "server"}
    # The October set REPLACES L4_METRICS (see OCT_TABLE_METRICS): five
    # queries, one p99, one cold column, in the order the section reads.
    # Resolved once, before the loop, so the table's column list cannot come
    # from a different instrument than its cells.
    _l4_cols = (OCT_TABLE_METRICS["l4"] if _instrument_of("l4") == "2026-10"
                else list(L4_METRICS))
    entries = []
    # Tier first, then the engine order the section reads, so the table shows
    # each corpus as its own row group the way every other multi-tier lane
    # does rather than interleaving two corpora under one heading.
    _tier_rank = {"ts100": 0, "ts1000": 1}
    for key in sorted(grouped, key=lambda k: (_tier_rank.get(k[1], 99),
                                              order.index(k[0]) if k[0] in order else 99,
                                              k[0])):
        label, _scale = key
        rs = grouped[key]
        entry = {
            "backend": display_name(label) if label in DISPLAY_NAMES else label,
            "backend_key": str(rs[0].get("backend")),
            # case-insensitive: the labels read "ArcadeDB (...)" since
            # 2026-09-11 and the lowercase test unshaded all four rows for a day
            "is_arcadedb": "arcadedb" in label.lower(),
            "scale": f"{_l4_points(_scale)} points",
            # THE SIZE COLUMN NAMES THE CORPUS THAT RAN. This lane has one
            # tier, so its size was a typed constant, and under a skeleton the
            # table then printed the campaign's corpus over a laptop slice of
            # it -- the one thing SKELETON_SCALE_LABELS exists to stop. The
            # scale key stays as it is because page_check and the figures
            # address cells by it.
            # FROM THE ROW'S OWN TIER, via the lane's constant. Typed as one
            # string while the lane had one tier; with two, a typed label puts
            # the smaller corpus's name on the larger corpus's numbers.
            "scale_label": (scale_label("l4", _scale) if SKELETON
                            else f"{_l4_points(_scale)} points"),
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

    _tiers = _l4_tiers({k[1] for k in grouped})
    settles = {r.get("settle_s") for rs in grouped.values() for r in rs}
    symmetric = settles <= {0, 0.0}

    return {
        "id": "l4",
        "title": "Time series",
        # EVERY CORPUS THE TABLE PRINTS. Typed as one size while the lane had
        # one tier; with ts1000 alongside ts100 it named the smaller over both.
        "dataset": _gen("TSBS cpu-only, "
                        + _join_and([f"{_l4_scale_points(t):,} points" for t in _tiers]),
                        *[f"{_l4_scale_points(t):,}" for t in _tiers]),
        "conditions": ([_R("l4", "settle" if symmetric else "settle_rows")]
                       + _l4_settle_note(settles)
                       + [_R("l4", "schema"), _R("l4", "newest")]
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
    if not _ident:
        # ABSENT BEATS UNVERSIONED. This table is fed by the binding suite's own
        # frozen file, not by a lane, and PAGE-SPEC says it returns "when its
        # artifact is re-measured at the October pin". Until then the artifact
        # carries no provenance line this payload can read, and building the
        # table anyway publishes measurements that name no engine -- which
        # version_consistency_check refuses by name, correctly, and which is
        # exactly the defect that check exists for. The skeleton already lists
        # pycost among its declared absences; a real October payload should
        # reach the same answer rather than a worse one.
        print("  pycost table omitted: its artifact carries no engine identity "
              "at this pin (PAGE-SPEC: it returns when re-measured)")
        return None

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
        # ARTIFACT-BACKED, AND THE ARTIFACT PATH IS PIN-SCOPED. The flat
        # "September's" above was true while the only artifacts on disk were
        # September's; it stopped being true the moment e4 was re-measured,
        # and it failed in the direction that matters. `_october` at the
        # bottom of this file is an ALL() over the tables, so one table
        # wrongly marked September made the whole payload September --
        # stamping `instrument: 2026-09` on a page of October rows and
        # handing `_global_conditions` the September condition set.
        #
        # The evidence is the path: these tables read
        # `results/<name>_<BENCH_ENGINE_COMMIT>/`, so an artifact that
        # resolves at all was produced at the pin being published. It cannot
        # be a leftover from the other campaign, because the other campaign's
        # artifacts sit in a differently named directory. A meta stamp is
        # better still and newer artifacts carry one, so prefer it and fall
        # back to the campaign this publish is for.
        return _artifact_instrument(table_id)
    return _instrument_of(lane_wl[0])


def _artifact_instrument(table_id):
    """The instrument behind a table fed by a pin-scoped artifact directory."""
    stamped = set()
    src = SOURCES.get(table_id)
    # SOURCES holds repo-relative paths for the published link; resolve
    # against the repo root rather than the caller's cwd, which is the bench
    # repo for a landing and the experiments directory for a hand run.
    dirs = [HERE.parents[1] / str(src)] if isinstance(src, str) else []
    for path in sorted(p for d in dirs if d.is_dir() for p in d.glob("*.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8")).get("meta") or {}
        except (ValueError, OSError):
            continue
        if meta.get("instrument"):
            stamped.add(str(meta["instrument"]))
    if len(stamped) > 1:
        raise SystemExit(f"REFUSING: the {table_id} artifacts carry two instruments "
                         f"{sorted(stamped)}; a table cannot mix them (DECISIONS #84)")
    if stamped:
        return next(iter(stamped))
    # THE INFERENCE IS ONLY SOUND FOR A PIN-SCOPED PATH. e4 reads
    # `e4decomp_<pin>/`, so its presence dates it; pycost reads a single CSV
    # whose name never changes, and that file is as old as whenever it was
    # last written. Answering "October" for it would be the original bug
    # inverted -- an artifact measured under the old instrument labelled with
    # the new one, which is the direction that puts a wrong provenance under
    # real numbers rather than merely withholding a table.
    _pin = os.environ.get("BENCH_ENGINE_COMMIT", "").strip()
    _scoped = bool(_pin) and isinstance(src, str) and _pin in src
    return "2026-10" if (_OCTOBER_ENV and _scoped) else "2026-09"


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
    "volumes after the cell, minus the same engine's empty footprint.")
OCT_DISK_DETAIL = (
    "A disk reading is taken after the queries, so it includes anything querying wrote; for "
    "a served row it is the server container alone, the client being only the driver. A "
    "server reading is taken once two samples agree within 1%, an embedded reading once on "
    "the stopped container. Neo4j's value includes the transaction-log files it preallocates "
    "in 256 MiB steps, which is how Neo4j uses disk, so they stay in.")

# A pin is (regex with one capture, fn(P, rows) -> number) or the same with a
# third element "const" when the number is a lane or runner constant, which the
# gate compares on a skeleton too (a row-derived pin is presence-only there,
# like the page prose pins).
OCT_PROSE = {
    "GLOBAL": {
        "docker": ("Every engine runs in Docker under an identical cpuset and memory cap, one job at a time, on the same host.", []),
        "docker_skeleton": ("Every engine ran in Docker under the same memory cap, one cell at a "
                            "time, on one shared machine. That machine was not doing only this: a browser, "
                            "an editor, and the rest of a working machine kept running beside every "
                            "cell, so no cell had cores of its own and the times below are not "
                            "comparable between engines.", []),
        "memory": ("Peak memory is the largest amount an engine held in its own address space, added over every container a run used, and it leaves out the file cache the kernel keeps on the engine's behalf. That is the right number for engines that manage their own memory, and an undercount for engines that lean on the kernel instead, so compare it down one engine's rows rather than across engines that work differently.", []),
        "defaults": ("Defaults first. Where a default would make the comparison meaningless, it is equalized and the override is disclosed rather than hidden.", []),
        "digest": ("Comparators are pinned by sha256 image digest, not by a floating tag.", []),
        # THE PIN FOLLOWS THE CLAUSE IT PINS. The settle tolerance moved out of
        # the per-table disk note with the sentence that states it.
        "disk_detail": (OCT_DISK_DETAIL, [(r"agree within (\d+)%", lambda P, rows: _const("runner", "DISK_SETTLE_TOL") * 100, "const")]),
    },
    "*": {
        "skeleton": (SKELETON_TABLE_NOTE, []),
        "disk": (OCT_DISK_NOTE, []),
    },
    # e4's explanatory sentences. They were unregistered until the table
    # was correctly dated October (it is artifact-backed, and the instrument
    # was inferred from a lane map it is not in), at which point the October
    # rule applies: a sentence that is not generated is registered here, by
    # the table that prints it. Neither states a measured quantity, so neither
    # carries a pin. A third ("the separate-process column goes slightly
    # negative at the smaller result sizes") described the two derived
    # difference columns DECISIONS #73 took off the table on 2026-09-12; the
    # cells left behind cross at 1,000 and 10,000 documents, not at the
    # smallest sizes, so it was describing columns that no longer exist and
    # was dropped (2026-10-03).
    "e4": {
        "same_materialisation": ('All three deployments turn the answer into Python objects the same way, so the difference is how the database was deployed and not how we read the result.', []),
        "same_machine": ('The separate container runs on the same machine, talking over the local network interface. It says what running the database beside your program costs, and says nothing about a database on another machine across a real network.', []),
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
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Java API (newDocument with int and float arrays) in 500-record transactions, then COMPACT INDEX; served binds 2,000-row INSERT ... CONTENT batches over HTTP with the tokens and weights as JSON arrays; Qdrant, Milvus, and Elasticsearch upsert or bulk-index in batches, then settle (Elasticsearch refresh and force-merge, Milvus flush and load); pgvector COPY FROM STDIN in sparsevec text form, then CREATE INDEX.",
                   [(r"in (\d+)-record transactions", lambda P, rows: _const("l3_sparse", "INGEST_BATCH"), "const"),
                    (r"binds ([\d,]+)-row INSERT", lambda P, rows: _const("l3_sparse", "ArcadeServer").load_batch, "const")]),
    },
    "l3d": {
        # WHY AN ANGULAR DATASET IS MEASURED WITH EVERY ENGINE ON L2. A fair
        # question from a reader who knows this corpus, and until 2026-09-23
        # the answer lived only in a code comment in load_dataset(). No number
        # in it, so no pin.
        "metric": ("Every engine searches this corpus with the same distance, squared Euclidean, "
                   "although the corpus is one whose published neighbours were computed by angle. "
                   "The two agree here: every vector and every query is scaled to unit length "
                   "before anything is indexed, and once they are, ordering by Euclidean distance "
                   "and ordering by angle produce the same list. So the recall column is measured "
                   "against the dataset's own published neighbours, unchanged, while every engine "
                   "runs one metric rather than each running its own -- which is what makes the "
                   "latencies comparable at all.", []),
        "cold": ("Cold p50 and p99 are the first timed pass over the query set after the index is built; a short untimed warm-up on held-out queries runs before it, so cold means an index that has not yet answered the timed queries, not a process that has done nothing. Warm columns, where present, are the passes after it.", []),
        "degree": ("ArcadeDB's maxConnections is a Vamana per-layer degree, not hnswlib's M. Matching the parameter names would compare a half-degree graph against a full-degree one, so the graphs are matched by effect instead.", []),
        "milvus": ("Milvus's dense rows run with segments sealed at 50% of the maximum segment size, where the image default is 12%, so a large ingest lands in the few-large-segments layout that Milvus's own compaction otherwise reaches at an unpredictable moment. One line changed from the image's configuration; sparse rows are at the default.",
                   [(r"sealed at (\d+)%", lambda P, rows: _milvus_seal_proportion() * 100, "const"),
                    (r"image default is (\d+)%", lambda P, rows: _const("runner", "MILVUS_IMAGE_SEAL_PROPORTION") * 100, "const")]),
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Python package's graph_batch with the WAL on, 10,000 vectors per commit, each vector as one Java float array, then CREATE INDEX ... LSM_VECTOR; served binds 2,000-row INSERT ... CONTENT batches over HTTP with each vector as a JSON array, then the same CREATE INDEX; Chroma add() in batches of 5,000; LanceDB an Arrow table then create_index; Qdrant and Milvus upsert in batches; DuckDB VSS and sqlite-vec executemany; pgvector COPY FROM STDIN then CREATE INDEX; Neo4j loads then builds its vector index; MongoDB insert_many then its vector search index; ArangoDB import_bulk then its FAISS IVF index; SurrealDB inserts through its Python SDK under the HNSW index it defines first; the server builds that index in the background, so the served build time includes waiting until a query probe shows the index has caught up.",
                   [(r"on, ([\d,]+) vectors per commit", lambda P, rows: _const("l3d_dense", "BATCH"), "const"),
                    (r"binds ([\d,]+)-row INSERT", lambda P, rows: _const("l3d_dense", "ArcadeServer").load_batch, "const"),
                    (r"batches of ([\d,]+); LanceDB", lambda P, rows: _const("l3d_dense", "CHROMA_BATCH"), "const")]),
    },
    "l2": {
        "projection": ("Every engine traverses the same persons-and-KNOWS projection, with edges stored in both directions.", []),
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Python package's graph_batch, the engine's bulk graph loader, with the WAL on, fed 5,000 records at a time; served streams the vertices and edges as JSONL to the HTTP batch endpoint with the WAL on; Neo4j and Memgraph UNWIND batches over bolt; FalkorDB the same UNWIND batches over the Redis protocol; LadybugDB COPY from CSV, its native bulk path; DuckPGQ registers each batch as an Arrow table and INSERT ... SELECTs from it into the Person and knows tables, then defines the property graph over them; ArangoDB import_bulk; MongoDB insert_many; SurrealDB inserts the persons through its Python SDK and the KNOWS edges as bulk relation inserts.",
                   [(r"fed ([\d,]+) records at a time", lambda P, rows: _const("l2_graph", "INGEST_BATCH"), "const")]),
    },
    "l2olap": {
        "gav": ("The Graph Analytical View is a copy of the graph that ArcadeDB builds in memory, laid out for questions that sweep the whole graph rather than follow a few links. Rows labelled GAV ran with it built, once, before any query was timed, and the view build column is what that took.", []),
    },
    "e2atom": {
        "trial": ("A trial writes the three products, kills the process between them, reopens, and checks whether every product is present or none. Torn means some but not all.", []),
    },
    "e2": {
        "atomic": ("Atomic means all or nothing: the whole update happens, or none of it does, with no state in between that anyone can observe. One engine can promise that across a vector, a graph edge, and a document because they share a transaction. Qdrant and Neo4j cannot promise it to each other, because nothing spans the two.", []),
        "interesting": ("So the interesting result here is not the speed. It is what a crash halfway through leaves behind, and the atomicity table below shows it: for each engine, how many interrupted writes left the store holding some but not all of the write after it was reopened. That is what this comparison exists to show.", []),
        "disk_split": ("SurrealDB embedded runs on the SDK's SurrealKV store on disk and SurrealDB server on RocksDB, and each has its own disk reading.", []),
        "ingest": ("ingest+index total s is one timer around loading the vertices and edges and creating the vector index. Ingest paths: ArcadeDB embedded loads with the Python package's graph_batch (5,000 records per commit, vertices then edges) and then CREATE INDEX ... LSM_VECTOR; served streams the products and edges as JSONL to the HTTP batch endpoint with the WAL on, then the same CREATE INDEX; SurrealDB embedded inserts through its Python SDK into the SDK's SurrealKV store on disk, and SurrealDB server through the same SDK over WebSocket onto RocksDB; Neo4j and the composed stack load the graph with UNWIND over bolt, and the composed stack upserts its vectors into Qdrant; PostgreSQL + pgvector + AGE loads the products with COPY under a pgvector HNSW index and creates the graph with UNWIND inside Cypher; ArangoDB import_bulk; MongoDB insert_many.",
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
        # THE DOCUMENT ARM'S LOADER CHANGED WITH F115 (2026-09-23). It used to
        # say "issues INSERT per point ... or sqlscript batches over HTTP", and
        # that was accurate until this pin: the arm really was the only one on
        # the table driven a row at a time. September's copy in INGEST_NOTES
        # still says so, correctly, because September's rows were produced that
        # way; only the October sentence moves.
        "ingest": ("Ingest paths: the ArcadeDB document path bulk-inserts through the Python package in batched transactions (embedded) or posts INSERT ... CONTENT batches over HTTP (served); the native TIMESERIES type takes columns through the async executor's append_samples (embedded) or InfluxDB line protocol at /api/v1/ts/{db}/write (served); DuckDB inserts an Arrow table; QuestDB takes line protocol over TCP; SQLite executemany in batched transactions; MongoDB insert_many in batches into a time-series collection; TimescaleDB COPY; ArangoDB import_bulk; SurrealDB inserts through its Python SDK.", []),
    },
    "lifecycle": {
        "session": ("The SESSION is open + action + close. Reporting open and close alone hides work triggered between them.", []),
        "cold_start": ("Cold start is measured in a fresh subprocess and reported beside every session number, because a millisecond open inside a process that takes half a second to reach its first database call is not a millisecond to whoever launched it.", []),
        "clean_close": ("A clean close should be O(what was written), not O(what is stored): write nothing and closing should cost the same at 10k documents and 10M.", []),
        "server_rows": ("Server rows have no JVM start, first open, or cold process: the server is already running when the probe connects, so those three columns describe the embedded process only. The session columns are measured for both.", []),
        # The SurrealDB embedded arm (2026-09-16, DECISIONS #95a): a fact about
        # the engine, not a number, so it carries no pin.
        # BUGS F159, 2026-09-29: l5_lifecycle.cycle() reads LSMVectorIndex.getStats() for the vector situation after
        # the action timer stops and before close(). The read is untimed, but at the October pin it raises the close
        # it precedes (laptop, 1M vectors: 6.4 -> 15.3 ms before #8630; 3.0 -> 3.5 after), so the embedded
        # dense-vector "open and close" cell is not a session that touched nothing. No number here: the split is
        # measured on the laptop only. Retires with CAMPAIGN section 7 row 22 (the read moves to an untimed cycle).
        "vector_stats": ("ArcadeDB's embedded dense-vector rows read the index's statistics just before close, to record whether a rebuild ran. The read is outside the timers, but on this engine build it raises the cost of the close that follows it, so that row's open and close figure is an upper bound for a session that touches nothing.", []),
        # The lead of the declared-situations sentences (one per engine, built in _lifecycle_table).
        "declared": ("An engine with no row for a situation cannot build it, and its adapter says so rather than leaving the row blank; the declared row keeps the statement the adapter tried and the engine's own answer.", []),
        "surreal_rows": ("SurrealDB rows have no JVM start: the SurrealDB core is a compiled extension that the Python import loads, so there is no runtime to start apart from the import. Their first open is the first open with the SDK already imported, and their cold process is interpreter start, import, open, and close, the same span the ArcadeDB embedded rows time. SurrealDB's time-series row is a plain table of timestamped records, the footing its time-series rows elsewhere on this page run on, because the engine has no time-series type.", []),
        # The other in-process engines (row 40, 2026-10-02, l5_lifecycle_embedded): facts about each engine's
        # session, not numbers, so no pins. Printed only when that engine's rows are on the table.
        "ladybug_rows": ("LadybugDB's documents, graph, and time-series rows each carry one index that ArcadeDB's do not: a LadybugDB node table must have a primary key, and the engine keeps a hash index on it. Its time-series row is a plain table of timestamped rows keyed on the timestamp.", []),
        "chroma_rows": ("A Chroma open is the client plus a handle on each collection the database holds, which is what ArcadeDB's open does with its schema, and Chroma loads a collection's HNSW index on its first query. Every Chroma record carries an embedding, so the scratch collection that the empty row writes into holds one-dimensional vectors.", []),
        "lance_rows": ("A LanceDB open is the connection plus a handle on each table the database holds. LanceDB has no close for a session like this one: the connection has none, a table's only close drains writers that its appends never open, and each write commits a new table version as it is made, so its close column times the session dropping its handles. Its dense-vector index is IVF_HNSW_FLAT, unquantized like every dense-vector index on this table.", []),
        "sqlitevec_rows": ("sqlite-vec's dense-vector row is an exact scan: vec0 builds no approximate index, so its query reads every vector and there is no index to drop. It runs inside SQLite under WAL with synchronous=NORMAL, as every SQLite arm on this page does.", []),
    },
    "durability": {
        "pairs": ("Each row is one engine running ONE operation twice: once where a commit returns without waiting for the disk, which is the setting every other table on this page reports, and once where the commit waits for the log to be flushed and synced. Nothing else about the cell changes.", []),
        "every_write": ("Every timed write on the page is here: the six document operations, the three graph writes, and the cross-model transaction. Read down the operations for one engine rather than across the engines for one operation, because what the setting costs is a property of the engine's commit and the rest of the page already compares the engines.", []),
        "read_control": ("The read is the control, and it is the row that makes the rest readable: it runs in both cells like everything else and commits nothing, so it is what the writes are moving against.", []),
        "size_column": ("The Size column names the operation rather than a corpus size, and for the cross-model transaction the catalog size as well: the three lanes that time a write do not write the same thing, so each engine is compared only against the engines running its own operation.", []),
        "cell_property": ("The setting is a property of the cell, not a second measurement inside one: it lives on the database or on the server for most of these engines, so each pair of numbers is two runs.", []),
        "ratio": ("The ratio is what the strict setting costs on that engine for that operation. The document and graph operations write the same few records whatever the corpus holds, so each row pools every corpus size its lane ran it at; the cross-model transaction searches and expands over the whole catalog, so it has one row per catalog size and its ratio holds at that size. It is not a claim about any other write. A large ratio is not a slow engine: it is an engine whose relaxed path was fast, measured against a flush that costs what a flush costs.", []),
    },
    "docs_oltp": {
        "ingest": ("Ingest paths: ArcadeDB embedded loads through the Python package's insert_many in 10,000-row batches, one JSON payload per batch; served binds 2,000-row INSERT ... CONTENT batches over HTTP; PostgreSQL COPY FROM STDIN; DuckDB CREATE TABLE AS SELECT from in-memory frames; SQLite executemany; MongoDB insert_many; ArangoDB import_bulk; SurrealDB inserts through its Python SDK.",
                   [(r"in ([\d,]+)-row batches", lambda P, rows: _const("l1_tpc", "BATCH"), "const"),
                    (r"binds ([\d,]+)-row INSERT", lambda P, rows: _const("l1_tpc", "ArcadeServerTPC").load_batch, "const")]),
    },
}
OCT_PROSE["docs_olap"] = {"ingest": OCT_PROSE["docs_oltp"]["ingest"]}
# The server restart (DECISIONS #139 item 2). Facts about the protocol, no
# numbers, so no pins: the counts (cycles, batch size) are on every row.
OCT_PROSE["restart"] = {
    "what": ("A served engine has no open or close of its own to time, so this table times what it has instead: a "
             "restart. Each engine is stopped the way its own image stops it, started again on the same data in the "
             "same container, and timed until a fixed read answers exactly as it did before the stop. Start is the "
             "time until the engine answers a liveness call; first answer is the time from there to the right answer.", []),
    "stops": ("A stop is timed from the stop signal to the process gone, twice: after a session that wrote nothing, "
              "and after one that wrote a fixed batch of records, each committed. A clean stop should cost what was "
              "written, not what is stored, so it should not grow with the size of the data. Every batch written "
              "before a stop is read back after the restart that follows it, so no engine's stop number comes from "
              "losing writes.", []),
    "warm_cache": ("These are process restarts on the same machine, the case of an upgrade, a configuration change, "
                   "or a crash: the host still holds the engine's files in its page cache, so the restart reads them "
                   "from memory. A restart after a reboot reads them from disk and would be slower for every engine.", []),
    "durability": ("Each engine runs at the durability its own table runs it at: the relaxed setting where that table "
                   "times writes (documents, graph, and time series), and the engine's default for the vector servers, "
                   "whose table times only a load and sets none. So a stop after writes flushes what that setting left "
                   "unflushed, and each row records the setting as `durability`.", []),
    "models": ("Each engine restarts on one model's data, loaded by that model's own table, and is compared only with "
               "the engines on the same data: the size column names the model. ArcadeDB's server runs all four. "
               "PostgreSQL stands for the pgvector, Apache AGE, and TimescaleDB arms, which run the same server and "
               "rebuild nothing in memory at start.", []),
}
OCT_PROSE["l2olap"]["ingest"] = OCT_PROSE["l2"]["ingest"]

# The registered sentences each October table opens with, in order. Sentences
# that depend on which engines are on the table are added by _oct_conditions.
OCT_TABLE_PROSE = {
    "l3s": ["recall", "one_timer", "es_pruning"],
    "l3d": ["metric", "degree"],
    "l2": ["projection"],
    "l2olap": ["gav"],
    "e2atom": ["trial"],
    "e2": ["atomic", "interesting", "disk_split"],
    "restart": ["what", "stops", "warm_cache", "durability", "models"],
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
        # "Nearly every": Q1 keeps the line items shipped on or before its
        # cutoff date, which is almost all of them, not all of them.
        "Q1": "TPC-H's own Q1, the pricing summary: it groups and aggregates nearly every line item, so it measures a full scan",
        # The lane's Q6 also returns `count(*) AS n` (l1_tpc.OLAP_DIGEST,
        # DECISIONS #94), so it is TPC-H Q6 plus a row count, not Q6 itself.
        "Q6": "TPC-H Q6, the forecasting revenue change, with a row count added: it sums one column under a narrow filter, so it measures how well an engine skips what it does not need",
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
    values = []
    # The documents Q1 is described as what ran while the rows are the
    # partial Q1 (_partial_q1_words, BUGS F170); "TPC-H's own Q1" comes back
    # with the rows of the full query.
    if table.get("id") == "docs_olap" and _OCTOBER_ENV:
        _q1 = _partial_q1_words(_FROZEN_ROWS)
        if _q1:
            words = {**words, "Q1": _q1[0]}
            values = _q1[1]
    labels = []
    for c in table.get("columns") or []:
        base = re.sub(r" p(50|99) ms$", "", str(c))
        if base in words and base not in labels:
            labels.append(base)
    if not labels:
        return None
    body = " ".join(f"{lbl[0].upper() + lbl[1:]}: {words[lbl]}." for lbl in labels)
    return _gen(f"{_WORDS.get(len(labels), str(len(labels)))} {kind}. {body} {tail}", *values)


def _surreal_pair_note(table):
    """The two SurrealDB rows are two engines, and the page has to say so.

    Embedded vs served is the axis this page invites a reader to read, and for
    every other engine the pair is one build behind two transports. SurrealDB's
    is not: the embedded arm runs the core the Python SDK carries and the
    served arm runs the container we pin, and on 2026-09-22 those are 2.3.10
    and 3.2.4 -- two major versions, a different store (SurrealKV against
    RocksDB), and a different threading profile. COMPARATORS.md has said this
    since DECISIONS #95 and BUGS F39; the PAGE said nothing, so the whole gap
    between those two rows read as a deployment result.

    Not a defect in the arms and not fixable by re-running: the embedded path
    goes through the SDK, so its core is whatever the SDK ships. The honest
    move is to disclose it where the comparison is made.

    Both version strings are READ FROM THE ENTRIES rather than typed, so the
    sentence cannot drift from the rows the way a typed pin would, and it says
    nothing at all on a table that shows only one of the two arms.
    """
    ent = {str(e.get("backend")): e for e in table.get("entries") or []}
    emb = ent.get("SurrealDB (embedded)")
    srv = ent.get("SurrealDB (server)")
    if not emb or not srv:
        return None
    # ONE SPELLING, here too. `version_name` is normalised on its way into the
    # payload, but a version quoted inside a SENTENCE misses that walk: this
    # note first published "surrealdb 2.3.10 and surrealdb v3.2.4", the exact
    # two-spellings-of-one-identifier defect _one_spelling exists to stop, one
    # layer further out.
    ev = _one_spelling(str(emb.get("version_name") or ""))
    sv = _one_spelling(str(srv.get("version_name") or ""))
    if not ev or not sv or ev == sv:
        return None
    return _gen(
        f"The two SurrealDB rows are not one engine in two deployments. The "
        f"embedded arm runs the core its Python driver carries and the served "
        f"arm runs the released server, and here those are {ev} and {sv} -- "
        f"different versions on different storage engines, released about a "
        f"year apart. Read each row against the other engines on the table "
        f"rather than against each other: the distance between these two is "
        f"not the cost of a network hop.",
        ev, sv)


def _jvm_reported_heap(r):
    """The heap the JVM itself reported for a row of the image-defaults arm ('12g'), which sets
    none of its own (CAMPAIGN 7 row 69): the runner records no tier heap for it, and the figure
    the column prints is what the running process answered. None for every other row."""
    if str(r.get("server_jvm_defaults")).lower() not in ("true", "1"):
        return None
    try:
        gib = float(r.get("server_jvm_max_heap_bytes")) / 2**30
    except (TypeError, ValueError):
        return None
    return f"{gib:.1f}".rstrip("0").rstrip(".") + "g"


def _entry_heaps(e, lane, wl, exact_only=False):
    """The JVM heaps the rows behind a table entry ran with ('4g', ...); empty
    for an engine that records none. Shared by the memory note and the heap
    column (DECISIONS #116 item 7), so the two cannot name different heaps."""
    # SCALE-EXACT FIRST, THEN THE LANE. The cell's own scale is the right
    # match and is what most tables need, but some take their memory figure
    # from an overlay rather than from the lane's rows (the dense table's
    # warm pass is a separate driver), and there the exact match finds
    # nothing. Dropping the scale for everyone was worse -- an arm that ran
    # two heaps across scales then reads as ambiguous and says nothing, which
    # took the note from four tables to two. So: try the cell's scale, fall
    # back to the whole lane, and if THAT is ambiguous say nothing rather
    # than pick a heap.
    # THE DENSE TABLE APPENDS A QUANTIZATION to the arm's name, so its
    # entries read "ArcadeDB (embedded, fp32)" where display_name() gives
    # "ArcadeDB (embedded)". An equality match found nothing there and the
    # note went missing from the one vector table that has it.
    def _same_arm(r, _eb=e.get("backend")):
        dn = display_name(str(r.get("backend")))
        if _eb == dn:
            return True
        # "ArcadeDB (embedded)" -> "ArcadeDB (embedded, fp32)"
        if dn.endswith(")") and str(_eb).startswith(dn[:-1] + ","):
            return True
        # "Neo4j" -> "Neo4j (fp32)": an arm with no deployment in its name
        # still gets the quantization appended on the vector tables, and
        # missing it left Neo4j's 37.7 GiB cell unexplained beside four
        # ArcadeDB ones that were.
        return "(" not in dn and str(_eb).startswith(dn + " (")

    _match = lambda r: (r.get("lane") == lane and (not wl or r.get("workload") == wl)
                        and _same_arm(r))
    rs = [r for r in _FROZEN_ROWS if _match(r) and str(r.get("scale")) == str(e.get("scale"))]
    if not rs and not exact_only:
        rs = [r for r in _FROZEN_ROWS if _match(r)]
    heaps = {str(r.get("heap") or r.get("server_heap") or _jvm_reported_heap(r) or "").strip() for r in rs}
    heaps = {h for h in heaps if h and h[-1].lower() == "g" and h[:-1].replace(".", "").isdigit()}
    return heaps


def _heap_not_pinned(e, lane, wl):
    """True when every row behind this table entry records a JVM that started with far less heap
    than it may take (`server_jvm_initial_heap_bytes` below half of `server_jvm_max_heap_bytes`):
    no -Xms, as ArcadeDB's image defaults run (CAMPAIGN 7 row 69). Read from the JVM's own
    report, never from the arm's name; an entry whose rows recorded neither field is not
    this and gets the fixed-heap sentence as before."""
    rs = [r for r in _FROZEN_ROWS
          if r.get("lane") == lane and (not wl or r.get("workload") == wl)
          and display_name(str(r.get("backend"))) == e.get("backend")
          and str(r.get("scale")) == str(e.get("scale"))]
    if not rs:
        return False
    for r in rs:
        try:
            init, mx = float(r["server_jvm_initial_heap_bytes"]), float(r["server_jvm_max_heap_bytes"])
        except (KeyError, TypeError, ValueError):
            return False
        if not (mx > 0 and init < 0.5 * mx):
            return False
    return True


def _jvm_memory_note(table):
    """The memory sentence for the JVM arms on this table: the fixed-heap one for arms that were
    given a heap, and one clause for an arm that starts with none (it is true of each and of no
    other; CAMPAIGN 7 row 69)."""
    base = _jvm_memory_note_fixed_heap(table)
    lw = _TABLE_LANE.get(table.get("id"))
    unpinned = []
    if lw:
        lane, wl = lw
        if lane == "l1tpc":
            wl = "oltp"
        for e in table.get("entries", []):
            cell = (e.get("metrics") or {}).get("peak memory GiB")
            if (cell and not e.get("outcome") and cell.get("median") is not None
                    and e.get("backend") not in unpinned and _heap_not_pinned(e, lane, wl)):
                unpinned.append(e.get("backend"))
    if not unpinned:
        return base
    names = _join_and(sorted(unpinned))
    one = len(unpinned) == 1
    clause = (f"{names} {'runs' if one else 'run'} on a JVM too, but {'it starts' if one else 'they start'} with "
              f"no initial heap size, so {'its' if one else 'their'} column follows what the work needed and not "
              f"the heap the JVM was allowed to grow into.")
    if base is None:
        return _gen(clause, names)
    vals = [v for rec in _GENERATED if rec["text"] == base for v in rec["values"]]
    return _gen(f"{base} {clause}", *vals, names)


def _jvm_memory_note_fixed_heap(table):
    """What the memory column measures for an engine running on a JVM.

    THE COLUMN IS NOT ONE MEASUREMENT, and it is the column ArcadeDB looks
    worst in, which is exactly why it gets said. An in-process C library's
    cell is what it needed; a JVM engine's cell is close to the heap it was
    given. Measured across September's rows at a FIXED memory cap of 8g, the
    peak moved with the heap and not with the work: 4g heap -> 2,781 MiB,
    8g -> 6,604, 16g -> 17,312, 24g -> 29,103, a ratio of 0.68 to 1.19, and
    every other cap/heap pair on the page sits in the same band.

    The page already makes this disclosure in the other direction for
    PostgreSQL, whose cell reads artificially LOW because its data lives in
    shared memory and the kernel's file cache. Saying it for the JVM arms and
    not for PostgreSQL, or the reverse, is the asymmetry; saying both is the
    page being even-handed about an accounting artifact whoever it favours.

    DERIVED, and every JVM arm on the table is named rather than ArcadeDB
    alone -- Neo4j records a heap too, and the composed stack's Neo4j half is
    in the same position. An arm whose rows record no heap says nothing here.
    """
    lane_wl = _TABLE_LANE.get(table.get("id"))
    # ASK THE ENTRIES, NOT table["columns"]. The column list is not populated
    # yet for a table that is reshaped here -- the document lane becomes two
    # page tables in this function -- so a guard reading it skipped docs_oltp,
    # docs_olap and lifecycle silently while working on the five tables whose
    # columns were already set. A metric that an entry carries is the thing
    # this note is about anyway.
    if not lane_wl or not any("peak memory GiB" in (e.get("metrics") or {})
                              for e in table.get("entries") or []):
        return None
    lane, wl = lane_wl
    if lane == "l1tpc":
        wl = "oltp"
    found = {}
    for e in table.get("entries", []):
        cell = (e.get("metrics") or {}).get("peak memory GiB")
        # A MARK IS NOT A VALUE (DECISIONS #111, #117): a censored or `re-run`
        # row carries text where the median would be.
        if not cell or e.get("outcome") or cell.get("median") is None:
            continue
        # AN ARM THAT STARTED WITH NO HEAP is not "close to the heap it was given" (CAMPAIGN 7
        # row 69): _jvm_memory_note says what its column follows, from the JVM's own report.
        if _heap_not_pinned(e, lane, wl):
            continue
        heaps = _entry_heaps(e, lane, wl)
        if not heaps:
            continue
        # A JVM ARM WITH AN AMBIGUOUS HEAP STILL GETS THE EXPLANATION, just not
        # the example. The dense and lifecycle tables run an arm at two heaps
        # across their scales, so no single number can be quoted for it -- but
        # "this column is close to the heap, not to the work" is true of that
        # arm either way, and dropping the sentence there left the artifact
        # explained on six tables and unexplained on three.
        found.setdefault(e.get("backend"),
                         (heaps.pop() if len(heaps) == 1 else None, float(cell["median"])))
    if not found:
        return None
    names = _join_and(sorted(found))
    _one = len(found) == 1
    # The biggest cell among them carries the example, so the sentence names a
    # number the reader can find in the column rather than an average of them.
    quotable = {k: v for k, v in found.items() if v[0]}
    head = (f"{names} {'runs' if _one else 'run'} on a JVM, and for {'it' if _one else 'them'} "
            f"this column is close to the heap {'it was' if _one else 'they were'} given rather "
            f"than the memory the work needed")
    tail = ("Every engine on a table gets the same memory envelope; how much of it a JVM "
            "takes is a property of the runtime, so read these cells against each other "
            "rather than against an engine that manages its own memory.")
    # NO BAND ACROSS THE OCTOBER PAGE. The sentence adds "across every heap
    # this page has run the peak lands between about two thirds of the heap and
    # a fifth above it", a band measured on September's 8g-cap rows (the
    # docstring above) and typed here. October's rows contradict it (about 40
    # per cent on one table, 3 to 8 per cent on the lifecycle arms), and a
    # typed band has no October row behind it, so an October table quotes only
    # the cell it names. The September page keeps the band it was measured on.
    band = _table_instrument(table.get("id")) != "2026-10"
    if not quotable:
        # Every JVM arm here ran more than one heap across this table's sizes,
        # so there is no single figure to quote and the sentence says the thing
        # that is true without one.
        if not band:
            return _gen(f"{head}. {tail}", names)
        return _gen(f"{head}: across every heap this page has run, the peak lands between "
                    f"about two thirds of the heap and a fifth above it. {tail}", names)
    who, (heap, gib) = max(quotable.items(), key=lambda kv: kv[1][1])
    pct = f"{gib / float(heap[:-1]) * 100:.0f}"
    if not band:
        return _gen(f"{head}: {who}'s {gib:.2f} GiB here is about {pct} per cent of its {heap} heap. {tail}",
                    names, f"{gib:.2f}", pct, heap)
    return _gen(
        f"{head}: {who}'s {gib:.2f} GiB here is about {pct} per cent of its {heap} heap, and "
        f"across every heap this page has run the peak lands between about two thirds of the "
        f"heap and a fifth above it. {tail}",
        names, f"{gib:.2f}", pct, heap)


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
    mid = (f"{_join_and(lacking)} record one timer only, because the index is built while "
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
                    "max beside it are that same single sample. The real run repeats each one five times and "
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


def _filter_strategy_note(table):
    """Which arms pre-filter and which post-filter, from `filtered_mode`.

    The cross-model table's filtered search is a top-k restricted to a
    neighbourhood, and the arms do not all run the same SHAPE of query. Nine
    of them pre-filter -- restrict the candidates, then rank those by distance
    -- and ArcadeDB's two post-filter: fetch an over-large global top-k and
    drop what falls outside. Those are different algorithms with different
    costs, and the page printed the two side by side with nothing saying so:
    9.33 ms against PostgreSQL's 1.37 ms at 500k, read as one query.

    The rows have carried `filtered_mode` all along; nothing published it.

    Named per arm rather than in general, because which arms sit on which side
    is the fact a reader needs, and it is read from the rows so it cannot
    drift from what ran.
    """
    if table.get("id") != "e2":
        return None
    modes = _filtered_modes()
    if not modes:
        return None
    post = sorted({disp for disp, m in modes.items() if m.startswith("post-filter")})
    pre = sorted({disp for disp, m in modes.items() if m.startswith("pre-filter")
                  or m.startswith("cross-system")})
    if not post or not pre:
        return None
    # "FOR THE SAME ANSWER" WAS WRONG, AND THE TABLE SAID SO. The first
    # version of this sentence ended "which is more work for the same answer".
    # It is not the same answer: a global top-k usually does not contain k of
    # the candidates, so the post-filtering arm returns an incomplete list of
    # near-arbitrary candidates, which is exactly what the filtered recall
    # column on this table shows. A disclosure sentence that understates the
    # thing it discloses is worse than none, because it tells the reader the
    # difference has been accounted for.
    return _gen(
        f"The engines do not all run the same SHAPE of filtered search, and it "
        f"shows in the recall column as much as the time one. "
        f"{_join_and(pre)} restrict the candidate set first and rank what is "
        f"left by distance, so they return that set's true nearest matches. "
        f"{_join_and(post)} instead take an over-large global top-k and keep "
        f"whichever candidates happen to fall inside it: more work, and a "
        f"partial answer, because a global list of that size usually does not "
        f"contain enough of the candidates. Read both columns for those arms "
        f"as what this query shape costs rather than as what the engine can "
        f"do.",
        *pre, *post)


def _txn_scope_note(table):
    """What the timed transaction holds, per engine (DECISIONS #118).

    The cross-model operation is a vector search, a one-hop expansion, and an
    update of the touched products. Every engine commits the update
    atomically; they differ in whether the two READS run inside the same
    transaction. The user decided on 2026-09-26 that the operation is defined
    by the atomic update, with the reads allowed outside, since that is what
    every engine here can do (MongoDB refuses $vectorSearch inside a
    multi-document transaction, and says so on its own rows), and that each
    engine's scope is stated rather than equalised. ArcadeDB keeps its reads
    inside, the setting that does not flatter it.

    Read from the rows where they recorded it (MongoDB asks its server) and
    from each adapter's declaration otherwise, so the sentence names what ran.
    """
    if table.get("id") != "e2":
        return None
    try:
        import e2_hybrid as _e2
    except Exception:  # noqa: BLE001 - the page must still build without it
        return None
    groups = {"whole": set(), "update": set(), "none": set()}
    refuses = set()
    for e in table.get("entries", []):
        bk = str(e.get("backend_key"))
        scope = getattr(_e2.BACKENDS.get(bk), "TXN_SCOPE", None)
        recorded = next((str(r.get("txn_scope")) for r in _FROZEN_ROWS
                         if r.get("lane") == "e2" and r.get("backend") == bk
                         and str(r.get("txn_scope") or "") not in ("", "None", "not declared")), None)
        if recorded in groups:
            scope = recorded
        elif recorded and "CANNOT" in recorded:
            scope = "update"
            refuses.add(display_name(bk))
        if scope in groups:
            groups[scope].add(display_name(bk))
    if not groups["whole"] or not groups["update"]:
        return None
    whole, upd = sorted(groups["whole"]), sorted(groups["update"])
    none_ = sorted(groups["none"])
    tail = (f" {_join_and(none_)} {'has' if len(none_) == 1 else 'have'} no transaction spanning "
            f"{'its' if len(none_) == 1 else 'their'} two systems, which is what "
            f"{'that row' if len(none_) == 1 else 'those rows'} exist{'s' if len(none_) == 1 else ''} to show.") if none_ else ""
    why = ""
    if refuses:
        r = _join_and(sorted(refuses))
        why = (f" ({r} cannot do otherwise: {'it refuses' if len(refuses) == 1 else 'they refuse'} "
               f"a vector search inside a multi-document transaction, and {'its' if len(refuses) == 1 else 'their'} "
               f"rows record the refusal)")
    return _gen(
        f"The transaction is the update, and every engine here commits it all or nothing. "
        f"{_join_and(whole)} also run the vector search and the hop inside it; "
        f"{_join_and(upd)} run those two reads first and wrap only the update{why}. "
        f"One client runs at a time, so the answers are the same either way.{tail}",
        *whole, *upd, *none_, *sorted(refuses))


def _filtered_modes():
    """backend display name -> the `filtered_mode` its rows recorded."""
    out = {}
    for r in _FROZEN_ROWS:
        if r.get("lane") != "e2" or r.get("workload") != "hybrid":
            continue
        m = str(r.get("filtered_mode") or "").strip()
        if not m or m == "None":
            continue
        be = str(r.get("backend"))
        out.setdefault(display_name(be) if be in DISPLAY_NAMES else be, m)
    return out


# ARANGODB'S IVF OPERATING POINT, READ FROM ITS ROWS. The registered sentence
# this replaces said its rows record nLists "about the square root of the
# corpus" and nProbe "an eighth of the lists", and neither is what the harness
# does. arango_common.ivf_params builds round(4 * sqrt(n)) lists, the low end
# of FAISS's guideline for 1M to 10M vectors (4 * sqrt(n) to 16 * sqrt(n));
# NPROBE_FRAC, the eighth, is only the cross-model lane's setting and the
# search's first guess. On the dense lane calibrate_nprobe picks the smallest
# nProbe in [1, nLists] whose recall@10 on a held-out slice of the fixture
# queries (never the timed ones) reaches arango_common.recall_target: the
# median frozen recall@10 of ArcadeDB embedded fp32 at the same size, read
# from runs_paper.csv, the previous published measurement's freeze.
#
# Every number comes from the rows behind the table's ArangoDB entries:
# ivf_nlists against n_docs (the multiplier is said only when every row agrees
# with ivf_params, and in words), ivf_calibration_queries, ivf_recall_target
# and ivf_recall_target_source, and ivf_nprobe. A size whose ArangoDB row is
# not on the table (the 10M cell, withheld, _one_list_note) is not described.
_RECALL_TARGET_SOURCE = re.compile(
    r"^(runs_paper(?:_oct)?\.csv) (arcadedb_dense_embedded) (fp32) (\S+) median of (\d+)$")


def _arango_ivf_note(table, rows):
    """The ArangoDB IVF sentence for the dense table, or None when no
    ArangoDB row with an IVF operating point is behind it."""
    shown = {str(e.get("scale")) for e in table.get("entries") or []
             if str(e.get("backend_key") or "").startswith("arangodb") and not e.get("outcome")}
    rs = [r for r in rows
          if r.get("lane") == "l3d" and str(r.get("backend") or "").startswith("arangodb")
          and str(r.get("instrument") or "") == "2026-10" and str(r.get("scale")) in shown
          and _num(r.get("ivf_nlists")) and _num(r.get("n_docs"))]
    if not rs:
        return None
    import arango_common
    by = {}
    for r in rs:
        by.setdefault(str(r.get("scale")), []).append(r)
    order = sorted(by, key=lambda sc: SCALE_ORDER.index(sc) if sc in SCALE_ORDER else len(SCALE_ORDER))
    values = []
    parts = ["ArangoDB's vector index is FAISS IVF (inverted lists over trained centroids), not "
             "HNSW, so the degree match above does not apply to it, and its rows record its "
             "operating point instead."]
    lists = []
    for sc in order:
        got = sorted({int(_num(r.get("ivf_nlists"))) for r in by[sc]})
        size = scale_label("l3d", sc)
        lists.append(f"{_join_and(f'{n:,}' for n in got)} lists at {size}")
        values += [f"{n:,}" for n in got] + [size]
    mults = {round(_num(r.get("ivf_nlists")) / _num(r.get("n_docs")) ** 0.5) for r in rs}
    follows = all(arango_common.ivf_params(int(_num(r.get("n_docs"))))[0] == int(_num(r.get("ivf_nlists")))
                  for r in rs)
    if follows and len(mults) == 1:
        parts.append(f"Its number of lists is {_count_word(mults.pop())} times the square root "
                     f"of the vector count, the low end of the range FAISS's own guidelines give, "
                     f"which makes {_join_and(lists)}.")
    else:
        parts.append(f"Its index has {_join_and(lists)}.")
    probed = [r for r in rs if _num(r.get("ivf_nprobe"))]
    if probed:
        queries = {int(_num(r.get("ivf_calibration_queries"))) for r in probed
                   if _num(r.get("ivf_calibration_queries"))}
        held = (f"{next(iter(queries)):,} queries held out from the timed ones" if len(queries) == 1
                else "queries held out from the timed ones")
        values += [f"{q:,}" for q in queries if len(queries) == 1]
        srcs = {str(r.get("ivf_recall_target_source") or "") for r in probed}
        m = _RECALL_TARGET_SOURCE.match(next(iter(srcs))) if len(srcs) == 1 else None
        if m:
            arc = f"{display_name(m.group(2))[:-1]}, {m.group(3)})"
            when = ("in the previous published measurement" if m.group(1) == "runs_paper.csv"
                    else "in this measurement")
            target = f"the median recall@10 of {arc} at the same size {when}"
            values.append(arc)
        else:
            target = "the recall target its rows record"
        parts.append(f"The number of lists each query probes is calibrated, not set: after the "
                     f"build and before any timed pass, the benchmark picks the smallest number "
                     f"whose recall@10 on {held} reaches {target}.")
        per = []
        for sc in order:
            here = [r for r in probed if str(r.get("scale")) == sc]
            if not here:
                continue
            size = scale_label("l3d", sc)
            nps = sorted(int(_num(r.get("ivf_nprobe"))) for r in here)
            chose = f"{nps[0]:,}" if nps[0] == nps[-1] else f"{nps[0]:,} to {nps[-1]:,}"
            builds = (f" across {_count_word(len(here))} builds" if len(here) > 1 else "")
            tg = {str(r.get("ivf_recall_target")) for r in here if _num(r.get("ivf_recall_target"))}
            lead = (f"At {size} that target is {next(iter(tg))} and the calibration chose"
                    if len(tg) == 1 else f"At {size} the calibration chose")
            per.append(f"{lead} {chose} lists{builds}")
            values += [size, f"{nps[0]:,}", f"{nps[-1]:,}"] + list(tg if len(tg) == 1 else [])
        if per:
            parts.append("; ".join(per) + ".")
    return _gen(" ".join(parts), *dict.fromkeys(values))


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
    f = _filter_strategy_note(table)
    if f:
        head.append(f)
    ts = _txn_scope_note(table)
    if ts:
        head.append(ts)
    if tid == "l3d":
        split = _ingest_split_note(table)
        if split:
            head.append(split)
        if any(c.startswith("cold ") for c in table.get("columns") or []):
            tail.insert(0, _R("l3d", "cold"))
        _ivf = _arango_ivf_note(table, _FROZEN_ROWS)
        if _ivf:
            tail.append(_ivf)
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
    if tid == "lifecycle" and any(n == "Dense vectors (embedded)" for n in names):
        tail.append(_R("lifecycle", "vector_stats"))
    if tid == "lifecycle" and any("SurrealDB" in n for n in names):
        tail.append(_R("lifecycle", "surreal_rows"))
    if tid == "lifecycle":
        # The compiled engines beside SurrealDB, named once rather than a sentence each.
        _native = [e for e in ("SQLite", "DuckDB", "LadybugDB", "Chroma", "LanceDB", "sqlite-vec")
                   if any(f"({e}, embedded)" in n for n in names)]
        if _native:
            _list = (_native[0] if len(_native) == 1 else
                     f"{_native[0]} and {_native[1]}" if len(_native) == 2 else
                     ", ".join(_native[:-1]) + f", and {_native[-1]}")
            tail.append(_gen(f"{_list} rows have no JVM start: each engine is a compiled library that its "
                             f"Python import loads, so the import is its runtime start.", _list))
        for _e, _key in (("LadybugDB", "ladybug_rows"), ("Chroma", "chroma_rows"),
                         ("LanceDB", "lance_rows"), ("sqlite-vec", "sqlitevec_rows")):
            if any(f"({_e}, embedded)" in n for n in names):
                tail.append(_R("lifecycle", _key))
    if tid == "l2olap":
        pair = _gav_pair_note(table)
        if pair:
            tail.append(pair)
    if tid in ("docs_oltp", "docs_olap"):
        pg = _pg_memory_note(table)
        if pg:
            tail.append(pg)
    # THE JVM HALF OF THE SAME DISCLOSURE, which the October path never
    # carried: October's tables said why PostgreSQL's memory cell reads low and
    # not why a JVM engine's reads close to its heap, the one-sided case
    # _jvm_memory_note's own docstring names as the asymmetry. September's
    # tables have carried it since f5a6ccedcb (the user settled on 2026-09-22
    # that the disclosure stays); this is the same generated sentence.
    jvm = _jvm_memory_note(table)
    if jvm:
        tail.append(jvm)
    return head, tail


# The runner's own roster of which backends a lane runs, so "registered for
# this lane" means here what it means to the gate that checks it.
try:
    import runner as _runner_mod
    LANES_RUNNER = {k: tuple(v[1]) for k, v in _runner_mod.LANES.items()}
except Exception:  # noqa: BLE001 - the page must still build without it
    LANES_RUNNER = {}

_TABLE_LANE = {
    "docs_oltp": ("l1tpc", "oltp"), "docs_olap": ("l1tpc", "olap"),
    "l2": ("l2", "oltp"), "l2olap": ("l2", "olap"),
    "l3d": ("l3d", None), "l3s": ("l3s", None), "l4": ("l4", None),
    "e2": ("e2", "hybrid"), "e2atom": ("e2", "atomicity"),
    # The lifecycle table was not here, so a lifecycle cell that exceeded its
    # budget would have left an engine off the table with no note, and the
    # coverage gate had no lane to read its fields from.
    "lifecycle": ("lifecycle", None),
    "restart": ("restart", "restart"),
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


def _server_hit_envelope(r):
    """A served cell whose SERVER was killed at its memory cap (2026-09-26).

    `oom_killed` is the client container's state. Rows since the runner reads
    the server's own State.OOMKilled carry `server_oom_killed`; older rows are
    recognised by the server's ANONYMOUS memory reaching its cap on a cell
    that failed. Anonymous memory cannot be reclaimed, so at the cap the
    kernel kills; the total peak is not evidence, because file cache counts
    toward it and is given back (ArcadeDB's lifecycle 10M row sat at its 28g
    total with 87.8% anonymous and was not killed). The served SurrealDB SF10
    analytics cell reached 32,676 MiB anonymous of 32g and died at its first
    query; its error text (a name-resolution failure while reconnecting to the
    dead container) would otherwise have printed it as a dropped connection."""
    if str(r.get("server_oom_killed")).lower() == "true":
        return True
    try:
        cap_mib = float(r.get("server_mem_cap_g")) * 1024.0
        anon = float(r.get("server_peak_anon_mib"))
    except (TypeError, ValueError):
        return False
    return bool(r.get("error")) and anon >= 0.99 * cap_mib


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
    # THE CENSORED CELLS COME FROM THE ROWS THIS PUBLISH IS BUILT FROM. The
    # comment above says a skeleton reads its own results file, and nothing
    # made that true: BENCH_RUNS_JSONL defaults to runs.jsonl, no skeleton
    # jsonl exists, and so a laptop placeholder page picked up the BENCH
    # HOST's censored cells -- including one at a corpus size the skeleton has
    # no label for, which is how this surfaced (the export died rather than
    # published, which is the good failure). A skeleton refuses bench-host
    # ROWS by design; it must refuse their outcomes for the same reason.
    if _SKELETON_ENV:
        rows = list(csv.DictReader(FROZEN.open())) if FROZEN.exists() else []
    else:
        path = HERE / "results" / os.environ.get("BENCH_RUNS_JSONL", "runs.jsonl")
        rows = []
        if path.exists():
            with open(path) as fh:
                rows = [json.loads(l) for l in fh if l.strip()]
    # SCOPE TO THE PIN THIS PUBLISH IS FOR. `pin` was read at the top of this
    # function and never used, so the only scoping was a date, and BOTH
    # campaigns are after it. A cell censored in September therefore carried
    # its note, and its September budget, onto an October page.
    #
    # The reverse -- an October timeout hidden by a September success -- was
    # never possible, because the cancel below drops any key with a clean row
    # at any pin. So the defect ran one way: a claim about the engine we no
    # longer publish, printed beside numbers from the one we do. Six cells in
    # l2, l3d and l1tpc are censored at September's pin alone today, and all
    # three of those lanes are still to land.
    #
    # Comparator rows carry the campaign's pin too (the launcher stamps every
    # row, not just ArcadeDB's), so scoping does not silently drop the
    # comparator timeouts -- which are most of them, and whose notes are the
    # ones keeping a censored cell distinguishable from an unmeasured one.
    # Prefixes, because a row may hold the full 40 characters and the pin is
    # published truncated.
    def _same_pin(r):
        if not pin:
            return True
        got = str(r.get("engine_commit") or "")
        return bool(got) and (got.startswith(pin) or pin.startswith(got))

    for r in rows:
        if str(r.get("ts_utc", "")) < "2026-09-01":
            continue
        if not _same_pin(r):
            continue
        if r.get("lane") == "lifecycle" and _lifecycle_stale(r):
            continue   # withdrawn, marked `re-run`: its failure was ours (LIFECYCLE_STALE)
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
        elif r.get("oom_killed") or _server_hit_envelope(r):
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
            _peak = ((r.get("server_peak_mib") if _server_hit_envelope(r) else None)
                     or r.get("peak_mib_sum") or r.get("client_peak_mib")
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
    # DECISIONS #117. Not a dash: on this page a dash means an operation the
    # engine cannot express, and these ran; they measured our mistake.
    # Not "is being measured again": some marked cells are re-measured in this campaign and some only in the
    # next measurement, and each note says which.
    "re-run": "the cell was measured before a fix to our harness and stays off the table until it is measured again; the note says what was wrong",
    # Not `re-run`: nothing was wrong with our harness, and the cell is not
    # measured again at this release. Not `err`: the cell finished. A defect in
    # the engine's own release decided what it returned (_one_list_note).
    "n/c": "not comparable, because a defect in the engine's release decided the cell's result; none of its numbers is printed, and the note names the defect",
}


_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven",
                 "eight", "nine", "ten")


def _count_word(n):
    """Small counts in prose are words, which is what every other sentence on
    this page does: "one", "two", "three" appear forty times between them and
    a bare "3 query cells" reads as a field, not a sentence."""
    return _NUMBER_WORDS[n] if 0 <= n <= 10 else f"{n:,}"


def _join_and(items):
    """"a", "a and b", "a, b, and c" -- the page writes lists as sentences,
    with the serial comma (the house style for the page and the papers)."""
    items = list(items)
    if len(items) < 3:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


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
        joined = (" and ".join(f"`{c}`" for c in caps) if len(caps) < 3
                  else ", ".join(f"`{c}`" for c in caps[:-1]) + f", and `{caps[-1]}`")
        parts.append(joined + (" mean" if len(caps) > 1 else " means")
                     + " the cell ran past its tier's cap and was not retried"
                     + ("; each tier has its own cap, the same for every engine on it"
                        if len(caps) > 1 else ""))
    for m in sorted(m for m in marks if not m.startswith(">")):
        if m not in _MARK_MEANINGS:
            raise SystemExit(f"export_web: no legend defined for the cell mark {m!r}; "
                             f"a mark the table cannot define must not reach a reader")
        parts.append(f"`{m}` means {_MARK_MEANINGS[m]}")
    return [_gen("In the cells: " + ". ".join(parts) + ". A dash is an operation the "
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
        # A LIFECYCLE ROW IS LABELLED BY ITS SITUATION, like the measured rows
        # beside it: two censored SurrealDB rows at 10M printed as the same
        # "SurrealDB (embedded)" twice, one for documents with ten indexes and
        # one for the graph, and a reader could not tell which was which.
        _lc = lane == "lifecycle"
        out.append({"backend": _lifecycle_row_label(backend, w) if _lc else display_name(backend),
                    **({"engine": _lifecycle_engine(backend)} if _lc else {}),
                    "backend_key": backend,
                    "is_arcadedb": "arcadedb" in str(backend).lower(),
                    "precision": None, "scale": scale,
                    "scale_label": scale_label(lane, scale), "workload": w,
                    "n_docs": None,
                    "deployment": "server" if str(backend).endswith("_server") else "embedded",
                    "image": None, "version_name": None, "host": None,
                    "outcome": kind,
                    "metrics": {c: {"text": mark} for c in cols}})
    return out, marks


def _delete_settle_notes(table):
    """An engine whose timed delete includes a cleanup step of its own, said
    under the table (DECISIONS #135). Memgraph 3.13.1 keeps deleted points in
    its vector index until its storage garbage collector runs, and a search
    before then raises, so the dense arm runs `FREE MEMORY` inside the timed
    delete and pays for it; the row carries `memgraph_delete_settle`."""
    if table.get("id") != "l3d":
        return []
    rows = [r for r in (_FROZEN_ROWS or []) if r.get("lane") == "l3d" and r.get("memgraph_delete_settle")]
    shown = {str(e.get("backend_key")) for e in table.get("entries", [])}
    if not rows or not any(b.startswith("memgraph_dense") for b in shown):
        return []
    return [_gen("Memgraph's delete time includes a storage cleanup it runs itself (`FREE MEMORY`): Memgraph "
                 "keeps deleted points in its vector index until its garbage collector runs, and a search before "
                 "then fails, so the cell triggers the collection inside the timed delete and pays for it.")]


def _not_comparable_entries(table, held=frozenset()):
    """Rows for the cells a known engine defect decided (_one_list_groups).

    The same shape as a measured row, as _censored_entries builds, with
    `outcome` and an `n/c` mark in every cell: the engine stays on the table at
    that size, and nothing that counts, ranks, or averages a measurement reads
    the row as one. Only at a size the table prints measured rows at, for the
    reason _censored_entries gives, and not where `held`, the (backend key,
    size) pairs a censored row already stands for, has one. The whole row is
    declared absent with the sentence that explains it, which is what the
    coverage gate reads.
    """
    groups = _one_list_groups(table.get("id"))
    if not groups:
        return [], set()
    measured_scales = {str(e.get("scale")) for e in table.get("entries") or []
                       if not e.get("outcome")}
    cols = list(table.get("columns") or [])
    out = []
    for (backend, scale), items in sorted(groups.items()):
        if scale not in measured_scales or (backend, scale) in held:
            continue
        name = display_name(backend)
        prec = DENSE_PRECISION.get(backend)
        label = f"{name[:-1]}, {prec})" if prec and name.endswith(")") else (
            f"{name} ({prec})" if prec else name)
        out.append({"backend": label, "backend_key": backend,
                    "is_arcadedb": "arcadedb" in backend,
                    "precision": prec, "scale": scale,
                    "scale_label": scale_label("l3d", scale), "workload": "search",
                    "n_docs": None, "deployment": deployment_of(backend),
                    "image": None, "version_name": None, "host": None,
                    "outcome": "not comparable",
                    "metrics": {c: {"text": "n/c"} for c in cols}})
        _declare_absence(table.get("id"), label, None, "not comparable",
                         _one_list_note(backend, scale, items))
    return out, ({"n/c"} if out else set())


def _phase_split_notes(table):
    """Arms on a split table that print no `index s`, and why (DECISIONS #132).

    Read from fairness_check's PHASE_SPLIT_DECLARED and PHASE_SPLIT_DISCLOSED,
    the maps the F14c gate reads, so the page and the gate cannot come to
    disagree. Declared arms have no separate index phase to time; disclosed
    arms have one and time it inside the total, which the sentence says so a
    reader does not read their blank `index s` as a fast build.
    """
    lane_wl = _TABLE_LANE.get(table.get("id"))
    cols = set(table.get("columns") or [])
    if not lane_wl or "index s" not in cols:
        return []
    try:
        import fairness_check
        declared = fairness_check.PHASE_SPLIT_DECLARED
        disclosed = fairness_check.PHASE_SPLIT_DISCLOSED
    except Exception:  # noqa: BLE001 - the page must still build without it
        return []
    lane = lane_wl[0]
    shown = {str(e.get("backend")) for e in table.get("entries", [])}
    out = []
    dec = sorted({display_name(b) for (ln, b) in declared if ln == lane} & shown)
    if dec:
        out.append(f"{_join_and(dec)} print{'' if len(dec) > 1 else 's'} no index time "
                   "because there is no separate index phase to time: each builds its "
                   "index during or before the load, or has none.")
    dis = sorted({display_name(b) for (ln, b) in disclosed if ln == lane} & shown)
    if dis:
        out.append(f"{_join_and(dis)} build{'' if len(dis) > 1 else 's'} {'their' if len(dis) > 1 else 'its'} "
                   "index after the load and time it inside the total, so "
                   f"{'their' if len(dis) > 1 else 'its'} total includes the index build "
                   "and the table has no separate index figure for "
                   f"{'them' if len(dis) > 1 else 'it'}; the next measurement splits "
                   f"{'them' if len(dis) > 1 else 'it'}.")
    return out


def _split_note(table):
    """The two phases are INSIDE the total, and do not always fill it.

    The ingest/index split (FAIRNESS F14) prints `ingest s` and `index s`
    beside the total, and the obvious sentence to write over that -- "the
    total is the two added together" -- is false. It was drafted here twice
    and caught twice by checking it against the payload, which is the only
    reason it is not on the page.

    The first draft claimed the sum. The second blamed the difference on
    aggregation, reasoning that three independent medians need not add. Both
    were wrong in the same way: the difference is there ROW BY ROW. Each
    adapter starts its ingest timer after whatever setup it does inside
    `build()` -- ArcadeDB after `CREATE PROPERTY`, Milvus after the collection
    and connection -- so the two timers are named phases within the total, not
    a partition of it. Measured on the dense table: MongoDB and Neo4j lose
    nothing, ArcadeDB 11 to 19 per cent, Milvus 33 to 39.

    So the sentence says what the columns are and states the residue's actual
    range, computed from the entries in front of the reader rather than
    typed, because the range is a property of which engines the table shows.

    Emitted only where both parts are printed AND at least one arm fills them:
    the column list alone was not enough of a test, and firing on it put this
    sentence over two tables whose entries carry neither part.
    """
    cols = set(table.get("columns") or [])
    if not {"ingest s", "index s"} <= cols:
        return []
    total = ("ingest total s" if "ingest total s" in cols
             else "ingest+index total s" if "ingest+index total s" in cols else None)
    if not total:
        return []

    def _m(entry, key):
        v = (entry.get("metrics") or {}).get(key)
        return v.get("median") if isinstance(v, dict) else v

    shares = []
    for e in table.get("entries", []):
        tot, ing, idx = _m(e, total), _m(e, "ingest s"), _m(e, "index s")
        if not tot or ing is None:
            continue
        shares.append(max(0.0, (tot - (ing + (idx or 0.0))) / tot))
    if not shares:
        return []
    hi = round(max(shares) * 100)
    lo = round(min(shares) * 100)
    if hi < 1:
        rest = ("On this table the two account for the whole of it on every "
                "engine shown.")
    else:
        rest = (f"How much is left over depends on the engine: nothing on some "
                f"of the ones here, up to about {hi} per cent on others."
                if lo < 1 else
                f"How much is left over depends on the engine, between about "
                f"{lo} and {hi} per cent on the ones here.")
    return [_gen(
        f"`{total}` is the whole of building this corpus. `ingest s` and "
        f"`index s` are the two phases timed inside it -- writing the data, "
        f"then building whatever index the engine was given -- and they are "
        f"not a division of it: each engine's ingest clock starts after the "
        f"setup it does first, creating a schema or a collection, which "
        f"neither phase counts. {rest} Read the two as what each phase cost, "
        f"and the total as what the whole of it cost.", total, str(hi))]


# WHAT A "NONE" ARM'S INDEX CELL TIMES, in a reader's words, keyed like
# fairness_check.NONE_ARM_TIMED_DDL. The documents table said DuckDB "builds
# none" beside a DuckDB index cell of 0.01 s; both were true, because the index
# it declares away is the analytics one and the cell times a key index its
# transactional workload needs, built on an empty table. Said under the table so
# the two read together.
_NONE_ARM_DDL_WORDS = {
    ("l1tpc", "duckdb"): ("the order-key index of the table new orders are written into, which the "
                          "transactional workload needs and which is built while that table is still empty"),
}


def _index_note(table_id, table=None):
    """Which engines build an index for this table's queries, and which do not.

    PROTOCOL section 7 requires anything that differs between engines to be
    disclosed, and after FAIRNESS F14 the index configuration differs on
    purpose: it is matched by EFFECT, so the engines that gain from an index
    have one and the engines it costs do not. A reader comparing two cells
    cannot see that from the numbers, so the table says it.

    READ FROM fairness_check.INDEX_DECISIONS, which is where the gate reads
    it, so the page and the gate cannot come to disagree about what was
    built -- the failure this repository keeps finding in a list written
    twice.
    """
    lane_wl = _TABLE_LANE.get(table_id)
    if not lane_wl:
        return []
    # ONLY THE WORKLOAD THE DECISION WAS MEASURED ON. The document lane's
    # index question is Q6's, which lives on the analytics table and not on
    # the transactional one; the cross-model lane's is the hybrid
    # retrieval's, not the atomicity trial's. Attaching the note to a table
    # whose queries were never the subject would be a claim about a
    # measurement that was not taken.
    _MEASURED_ON = {"l1tpc": "olap", "e2": "hybrid", "l4": None}
    lane, workload = lane_wl
    if lane not in _MEASURED_ON or _MEASURED_ON[lane] != workload:
        return []
    try:
        import fairness_check
        decided = fairness_check.INDEX_DECISIONS.get(lane)
    except Exception:  # noqa: BLE001 - the page must still build without it
        return []
    if not decided:
        return []
    # Off the table: a withdrawn arm, and an ablation arm the page never
    # prints (OFF_PAGE_ARMS). Naming "PostgreSQL (tuned)" here put a name
    # under the documents table that no row on it carries.
    _gone = {display_name(bk) for bk in _withdrawn_now(table_id)} | {
        display_name(bk) for bk in OFF_PAGE_ARMS} | {
        display_name(bk) for bk, tabs in ARM_TABLES.items() if table_id not in tabs}
    have = sorted({display_name(be) for be, d in decided.items()
                   if not d.startswith("NONE")} - _gone)
    none = sorted({display_name(be) for be, d in decided.items()
                   if d.startswith("NONE")} - _gone)
    if not have and not none:
        return []
    parts = []
    if have:
        parts.append(f"{_join_and(have)} build{'' if len(have) > 1 else 's'} one")
    if none:
        parts.append(f"{_join_and(none)} build{'' if len(none) > 1 else 's'} none, because "
                     f"measuring it showed the index "
                     f"{'costs them' if len(none) > 1 else 'costs it'} or changes nothing")
    # WHERE THE BUILD TIME IS. "The time an index took to build is the index
    # column" was said under the cross-model table too, which prints no index
    # column (its relaxed rows predate the split, so only the combined timer is
    # filled); there the build is inside the ingest+index total. Read off the
    # entries that print a number, the same test _finish_table uses to keep a
    # column.
    def _filled(col):
        return any(isinstance((e.get("metrics") or {}).get(col), dict)
                   and (e["metrics"][col] or {}).get("median") is not None
                   for e in ((table or {}).get("entries") or []) if not e.get("outcome"))
    if table is None or _filled("index s") or _table_instrument(table_id) != "2026-10":
        where = "The time an index took to build is the index column."
    elif _filled("ingest+index total s"):
        where = ("This table has no index column: the time an index took to build is inside "
                 "the ingest+index total.")
    else:
        where = ""
    # A NONE ARM WHOSE INDEX CELL IS NOT ZERO, said beside the claim it seems
    # to contradict (fairness_check.NONE_ARM_TIMED_DDL).
    try:
        import fairness_check as _fc
        _timed = getattr(_fc, "NONE_ARM_TIMED_DDL", {})
    except Exception:  # noqa: BLE001 - the page must still build without it
        _timed = {}
    extra = []
    if where.endswith("is the index column.") and _table_instrument(table_id) == "2026-10":
        for (ln, be), _decl in sorted(_timed.items()):
            words = _NONE_ARM_DDL_WORDS.get((ln, be))
            if ln == lane and words and display_name(be) in none:
                extra.append(f"{display_name(be)}'s index cell is not zero because it times a different "
                             f"index: {words}.")
    # WHAT IS TRUE OF ALL OF THEM, and no more. Ten of these arms were timed
    # with the index and without it; the rest reach the query through a
    # primary key or a record id, which is the same access path by another
    # name and was never a choice to measure. Saying "each engine was
    # measured both ways" would be a claim about work that was not done.
    return [_gen(
        "Indexes on this table are matched by effect rather than by rule: " +
        "; ".join(parts) + ". Where building one was a choice, the engine was timed with it "
        "and without it and the faster configuration kept; where an engine reaches these "
        "queries through its own primary key or record id, that is its equivalent."
        + (f" {where}" if where else "") + "".join(f" {x}" for x in extra),
        *(have + none))]


def _hash_ids_phrase(ids):
    """`Part.p_partkey`, `OrderNew.okey`, and `Crud.ckey`; or, when every id
    is one property on several types, "`id` of Country, City, and Forum"."""
    props = {p for _, p in ids}
    if len(ids) > 1 and len(props) == 1:
        return f"the `{next(iter(props))}` of {_join_and(t for t, _ in ids)}"
    return _join_and(f"`{t}.{p}`" for t, p in ids)


def _arcadedb_hash_index_notes(table):
    """The index kind ArcadeDB's id indexes carry on this table, and what it costs
    (CAMPAIGN section 7 row 68).

    GENERATED FROM THE ROWS, not from the code. Each cell records `index_kinds`, the engine's
    own answer to `SELECT FROM schema:indexes` after the schema was built (bench_common.
    arcadedb_index_readback), and the sentence names an id only where EVERY ArcadeDB row this
    table prints reads HASH for it. A row without the stamp (any row measured before the
    harness recorded it, or a read-back that failed) asserts nothing, so the id drops out and
    a table with no stamped rows says nothing: regenerating a page over rows that ran the old
    DDL cannot claim a hash index. fairness_check.ARCADEDB_HASH_ID_INDEXES names the ids a lane
    is asked to make hash indexes and test_index_kinds.py holds it equal to the DDL; this reads
    which of them the engine reports. No digit: how much the lookups gain and the loads lose
    is in the measured cells beside it.
    """
    lane_wl = _TABLE_LANE.get(table.get("id"))
    shown = {(str(e.get("backend_key")), str(e.get("scale")))
             for e in table.get("entries") or [] if e.get("is_arcadedb") and not e.get("outcome")}
    if not lane_wl or not shown:
        return []
    # A table that prints no ingest or index time (the cross-model atomicity
    # table counts trials) has nowhere for the cost to show, so it says nothing.
    if not any("ingest" in str(c) or "index" in str(c) for c in table.get("columns") or []):
        return []
    try:
        import fairness_check
        import bench_common
        registry = fairness_check.ARCADEDB_HASH_ID_INDEXES
    except Exception:  # noqa: BLE001 - the page must still build without it
        return []
    lane, workload = lane_wl
    rows = [r for r in _FROZEN_ROWS
            if r.get("lane") == lane and r.get("workload") == workload
            and (str(r.get("backend")), str(r.get("scale"))) in shown]
    if not rows:
        return []
    kinds = [bench_common.parse_index_kinds(r.get("index_kinds")) for r in rows]
    ids = []
    for ln, wl, pairs in registry:
        if ln == lane and wl in (None, workload):
            ids += [(t, p) for t, p in pairs if all(k.get(f"{t}.{p}") == "HASH" for k in kinds)]
    if not ids:
        return []
    many = len(ids) > 1
    return [_gen(
        f"ArcadeDB's {'indexes' if many else 'index'} on {_hash_ids_phrase(ids)} "
        f"{'are hash indexes' if many else 'is a hash index'} (`UNIQUE_HASH`), because the benchmark never "
        f"ranges over or orders by {'those ids' if many else 'that id'}. A hash index keeps no key order: an equality "
        f"lookup goes straight to its bucket instead of walking a sorted tree, and building it can cost "
        f"more than building a sorted index when the ids arrive in ascending order, which is the order "
        f"this loader sends them. Any such cost is in ArcadeDB's ingest and index times on this table.")]


JVM_DEFAULTS_ARM = "arcadedb_imgdefaults_server"


def _jvm_defaults_notes(table):
    """What the image-defaults ArcadeDB row runs, said under every table that prints it
    (CAMPAIGN section 7 row 69). Generated from the JVM flags the cells recorded: the arm's
    own heap, collector, and share of its container, and the main served arm's, so the
    sentence cannot say G1 or 8 GiB of a row that ran otherwise. The runner reads both from
    the running process (`server_jvm_*`); a main-arm row without the read-back is said
    without its numbers rather than guessed."""
    lw = _TABLE_LANE.get(table.get("id"))
    if not lw or not any(e.get("backend_key") == JVM_DEFAULTS_ARM and not e.get("outcome")
                         for e in table.get("entries") or []):
        return []
    lane, wl = lw
    mine = lambda r, be: r.get("backend") == be and r.get("lane") == lane and r.get("workload") == wl
    arm = [r for r in _FROZEN_ROWS if mine(r, JVM_DEFAULTS_ARM)]
    scales = {str(r.get("scale")) for r in arm}
    main = [r for r in _FROZEN_ROWS if mine(r, "arcadedb_server") and str(r.get("scale")) in scales]

    def gib(rows, key):
        out = set()
        for r in rows:
            try:
                out.add(float(r[key]) / 2**30)
            except (KeyError, TypeError, ValueError):
                pass
        return sorted(out)

    def fmt(x):
        return f"{x:.1f}".rstrip("0").rstrip(".")

    arm_heap, main_heap = gib(arm, "server_jvm_max_heap_bytes"), gib(main, "server_jvm_max_heap_bytes")
    caps = sorted({float(str(r.get("server_mem_cap")).rstrip("g")) for r in arm
                   if str(r.get("server_mem_cap", "")).rstrip("g").replace(".", "").isdigit()})
    gcs = sorted({str(r.get("server_jvm_gc")) for r in arm if r.get("server_jvm_gc")})
    main_gcs = sorted({str(r.get("server_jvm_gc")) for r in main if r.get("server_jvm_gc")})
    values = []
    other = "The main ArcadeDB server row gives the JVM a fixed heap"
    if len(main_heap) == 1:
        other += f" of {fmt(main_heap[0])} GiB"
        values.append(fmt(main_heap[0]))
    other += " and the " + (f"{main_gcs[0]} collector" if len(main_gcs) == 1 else "collector the JVM chooses by default")
    other += ", and the embedded rows are configured the same way, so that the two deployments differ in transport only"
    took = "this row sets neither, so the image applied its own"
    if len(arm_heap) == 1:
        took += f": a heap of {fmt(arm_heap[0])} GiB"
        values.append(fmt(arm_heap[0]))
        if len(caps) == 1 and caps[0]:
            pct = round(100 * arm_heap[0] / caps[0])
            took += f", {pct} per cent of its {fmt(caps[0])} GiB container"
            values += [str(pct), fmt(caps[0])]
    else:
        took += ": a heap of 75 per cent of its container"
        values.append("75")
    took += (f", the {gcs[0]} collector" if len(gcs) == 1 else ", the image's default collector")
    took += ", and no initial heap size"
    text = (f"{display_name(JVM_DEFAULTS_ARM)} is the one row here that runs the ArcadeDB image's own JVM "
            f"settings. {other}; {took}. Its difference from the main served row is the heap, the collector, "
            f"and the heap's warm-up together, not any one of them.")
    return [_gen(text, *values)]


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
        # The lifecycle lane's workload is its SITUATION, an internal key
        # ("doc_idx10"); the sentence names it the way the row label does.
        _cell = (f"the cell for {LIFECYCLE_SITUATION_PHRASES.get(w, w)}" if lane == "lifecycle"
                 else f"the {what} cell")
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
            tail = (f" at {scale_label(lane, scale)}: {_cell} reached "
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
            tail = (f" at {scale_label(lane, scale)}: {_cell} exceeded "
                    f"its {budget} budget, the same budget every engine on this table had, on its first "
                    f"attempt and was not retried; there is no row.{_in}")
            pins = [scale_label(lane, scale), budget]
        else:
            tail = (f" at {scale_label(lane, scale)}: {_cell} failed "
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
            who = ", ".join(engines[:-1]) + f", and {engines[-1]}"
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
    # THE TRANSACTIONAL READS' BUDGET (DECISIONS #120). A read counts STARTS,
    # not iterations: each start is one query from one seed person, the start
    # set's size depends on the tier, and <read>_iters is how many of them the
    # first pass timed before its budget ran out.
    "l2": ("l2", "oltp", {
        "point": "point", "hop1": "1-hop", "hop2": "2-hop", "hop3f": "3-hop filtered"},
        ("graph_common", "SCALE_OLTP_QUERIES"),
        "starts timed in the first pass", "starts"),
}


def _row_label_for(table_id, r):
    """The label this table gives the row's engine, for a sentence about it."""
    backend = str(r.get("backend") or "")
    if table_id == "l4":
        # THROUGH display_name, LIKE THE TABLE DOES. L4_CANON_LABELS carries
        # the raw key for five comparators (duckdb, mongodb, questdb, sqlite,
        # timescaledb) and the table maps those through DISPLAY_NAMES when it
        # builds its rows, so the cells read "SQLite". This path did not, so
        # the budget sentences under the same table said "sqlite at 25.92M
        # points" -- a backend key in page prose, beside "ArangoDB" and
        # "SurrealDB (server)" in the sentences either side of it.
        canon = L4_CANON_LABELS.get(backend, backend)
        return display_name(canon) if canon in DISPLAY_NAMES else canon
    label = display_name(backend)
    if table_id == "l2olap" and str(r.get("gav")) != "False" and "arcade" in backend:
        label = f"{label[:-1]}, GAV)" if label.endswith(")") else f"{label} (GAV)"
    return label


def _query_budget_notes(table_id):
    spec = _QUERY_BUDGET_TABLES.get(table_id)
    if not spec:
        return []
    lane, wl, labels, (mod, const), counted = spec[:5]
    unit = spec[5] if len(spec) > 5 else "iterations"
    # The asked count comes from the lane module the runner executes, like
    # _counts_note's, so the two sentences cannot disagree.
    try:
        import importlib
        asked = int(getattr(importlib.import_module(mod), const))
    except Exception:  # noqa: BLE001 - the lane module is optional here, and a
        # per-tier count (a dict) has no one number to print: the sentence
        # then gives how far each read got, not "of N"
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
    # ONE CELL READS AS ONE (2026-09-28): the plural-only template would print
    # "One query cells ... in those cells" the first time a table had a single
    # censored query (found on `repin-prep`, where the graph reads' budget
    # censors exactly one).
    one = total == 1
    lead = (f"{_count_word(total).capitalize()} query {'cell' if one else 'cells'} on this "
            f"table stopped at "
            + (f"the {one_budget:g} s budget every engine here is given"
               if one_budget else "their per-query budget, the same for every engine here")
            # "over THOSE <counted>" and not "over the <counted> it reached":
            # `counted` is a noun phrase that already carries its own clause on
            # the document table ("iterations, the first of which is the cold
            # pass"), and anything appended to it lands inside that clause.
            + (f"; its p50 and p99 are over those {counted}, and every other query in "
               f"that cell keeps its numbers." if one else
               f"; each one's p50 and p99 are over those {counted}, and every "
               f"other query in those cells keeps its numbers."))
    notes.append(_gen(lead, _count_word(total).capitalize(),
                      f"{one_budget:g} s budget" if one_budget else "per-query budget"))

    for (label, scale), cols in sorted(by_engine.items(), key=str):
        parts, first = [], True
        for col, occ in cols:
            span, reached = _span(occ)
            # "of 100 iterations" once, on the first query; the rest are bare
            # counts against the same denominator.
            parts.append(f"{col} ({span}{of if first else ''}"
                         + (f" {unit}" if first else "") + f"{reached})")
            first = False
        notes.append(_gen(f"{label} at {scale_label(lane, scale)}: "
                          + _join_and(parts) + ".",
                          label, scale_label(lane, scale), _join_and(parts)))
    return notes


def _mutation_note(rows):
    """Which dense tiers ran the two maintenance operations, and which did not.

    The pass runs at one tier, so on any other tier the six maintenance columns
    (the search after each operation, the cost of each per vector, and the
    recall after each) are blank. A blank with no sentence beside it is also
    how a reader concludes an engine failed the operation when the operation
    was never asked for. Read from the rows' own mutate_ran rather than from
    the tier list here, so a forced run (BENCH_DENSE_MUTATE=1) describes itself.

    The rows' mutate_reason is NOT quoted. It is the harness's own note to
    itself (it names a decision number and the tier by its internal key), and
    it printed on the page as "(scale deep10m is not the one-million tier;
    #82d runs the two mutation operations at small only)" the first time a
    dense table reached the preview (2026-10-06). The tiers are named the way
    the table names them, and the sentence says the one fact.
    """
    ran, skipped = set(), set()
    for r in rows:
        if r.get("lane") != "l3d":
            continue
        sc = str(r.get("scale"))
        flag = str(r.get("mutate_ran")).lower() in ("true", "1")
        (ran if flag else skipped).add(sc)
    # A tier that ran for any engine is a tier the pass runs at: an engine that
    # declined it there (it cannot express the operation) is a declared absence
    # on that engine's cells, not a tier where the pass was not run.
    skipped -= ran
    if not ran and not skipped:
        return None
    parts = []
    if ran:
        parts.append("The insert and delete into a built index, the search after each, "
                     "and the recall after each are measured at "
                     + _join_and(scale_label("l3d", s) for s in sorted(ran))
                     + (" only." if skipped else "."))
    if skipped:
        parts.append("At " + _join_and(scale_label("l3d", s) for s in sorted(skipped))
                     + " those columns are blank because the pass is not run there, "
                       "not because an engine failed it.")
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
    #
    # Each arm is named as its row is (name and precision), and arms whose
    # counters agree share one clause: ArcadeDB's fp32 and int8 embedded arms
    # were both printed as "ArcadeDB (embedded)", each with its own count, which
    # read as one engine saying two different things.
    _rb = _mutation_rebuilds(rows)
    _tokens = []
    if _rb:
        _by_count = collections.OrderedDict()
        for _b, _n, _d in _rb:
            _by_count.setdefault((_n, _d if _n == 0 else 0), []).append(_dense_row_label(_b))
        _said = []
        for (_n, _d), _names in _by_count.items():
            _who, _many = _join_and(_names), len(_names) > 1
            if _n > 0:
                _said.append("%s rebuilt %s whole graph %d time%s to absorb the changes"
                             % (_who, "their" if _many else "its", _n, "" if _n == 1 else "s"))
                _tokens.append(str(_n))
            else:
                _said.append("%s left %s vectors in %s, to be merged by a later full "
                             "rebuild this cell does not pay for"
                             % (_who, f"{_d:,}",
                                "their delta buffers" if _many else "its delta buffer"))
                _tokens.append(f"{_d:,}")
        parts.append(
            "These engines do not all maintain an index the same way: "
            + "; ".join(_said)
            + ". A full rebuild touches every vector in the index and an incremental "
              "insert touches only the new ones, so the per-vector costs here price "
              "different amounts of work and are not a straight speed comparison.")
    return _gen(" ".join(parts),
                *[scale_label("l3d", s) for s in sorted(ran | skipped)],
                *_tokens)


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

    THE MEDIAN OVER REPETITIONS, like every other number on the page. This took
    the maximum, so one build in five that ended with a stray extra vector in
    the buffer (1,001 and 1,002 against 1,000 in the other four) printed as the
    arm's count and made two arms that agree read as two different results.
    """
    seen = {}
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
        per = seen.setdefault(b, ([], []))
        per[0].append(rebuilds)
        per[1].append(delta or 0)
    best = {b: (int(statistics.median(n)), int(statistics.median(d)))
            for b, (n, d) in seen.items()}
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
    # ONE SENTENCE PER ENGINE, NOT PER CELL. Two sizes of the same engine with
    # the same baseline produced two sentences identical apart from the size
    # name -- FalkorDB at SF1 and at SF10, both ending "a floor under 0.01
    # GiB" -- which is the loop-shaped prose the page is not supposed to carry
    # (the user, on forty-seven such sentences: "human won't duplicate things
    # like this that are very similar"). Grouped by what the sentence actually
    # says, so two sizes that agree share a line and two that differ keep
    # their own.
    _by_engine = {}
    for label, scale, lane, sb in hits:
        try:
            sl = scale_label(lane, scale)
        except Exception:  # noqa: BLE001 - a lane whose tier the map does not name
            continue
        _by_engine.setdefault((label, sb), []).append(sl)

    notes = []
    for (label, sb), sls in sorted(_by_engine.items(), key=str):
        sl = _join_and(sorted(set(sls), key=str))
        mb, gib = f"{sb:.0f}", f"{sb / 1024:.2f}"
        # THE CAUSE WAS TRACED ON ONE ENGINE AND WAS BEING TOLD ABOUT ALL OF
        # THEM. The preallocated write-ahead log is SurrealDB 3.2.4's, verified
        # 2026-09-15; the clause naming it was printed on every zero-growth
        # server row, so FalkorDB's sentence read "its disk cell is 0.0 ...
        # which for SurrealDB's server includes a preallocated write-ahead log
        # of about 6 MB" -- another engine's explanation, wearing FalkorDB's
        # own baseline figure. Incoherent to read and false as a claim.
        #
        # The zero itself is measured on every one of them and still needs
        # saying, or the cell reads as "stores nothing". So the fact is
        # printed for all and the cause only where it was established. An
        # engine whose floor we have not traced gets a sentence that says what
        # was measured and stops, which is the honest shape.
        # FALKORDB'S CAUSE, TRACED 2026-09-24 on the pinned image
        # (falkordb/falkordb@sha256:0a9fe4d1...): `CONFIG GET save` answers
        # "3600 1 300 100 60 10000", `appendonly` is "no", the data directory
        # /var/lib/falkordb/data starts empty, and the image declares no volume.
        # At the relaxed class the harness leaves that default (runner.py adds an
        # append-only file only for strict), and its rows measured exactly the
        # empty footprint at both sizes: no snapshot had been written, so the
        # graph was in memory only and the cell says nothing about its size on
        # disk. The timer values stay out of the sentence: a digit on the page
        # needs a pin, and the cause does not depend on them.
        if "SurrealDB" in str(label):
            _why = (f", which for this engine is a preallocated write-ahead log of about "
                    f"{mb} MB that the whole corpus fits inside at this size")
        elif "FalkorDB" in str(label):
            _why = (": at the relaxed setting FalkorDB persists only by timed snapshots, "
                    "with no append-only file, and none had been taken when disk was "
                    "measured, so the graph was held in memory only")
        else:
            _why = ""
        # AGREEMENT FOLLOWS THE GROUPING. Merging two sizes into one sentence
        # left it reading "FalkorDB at SF1 and SF10: its disk cell is 0.0",
        # singular over two cells. Generated prose has to survive its own
        # grouping or the merge just trades duplication for a grammar slip.
        _n = len(set(sls))
        _cell = "its disk cell is" if _n == 1 else "its disk cells are"
        _read = "read the cell" if _n == 1 else "read them"
        notes.append(_gen(
            f"{label} at {sl}: {_cell} 0.0 because the server container did not "
            f"grow over its empty footprint during the run{_why}; {_read} as a floor "
            f"under {gib} GiB, not as a size.",
            label, sl, "0.0", *( [mb, gib] if "SurrealDB" in str(label) else [gib] )))
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
        # "500 at SF1 (10k people, ...) and 200 at SF10 (...)": the scale
        # labels carry their own parentheses, so the counts lead.
        parts = _join_and([f"{n:,} at {scale_label('l2', sc)}" for sc, n in q.items() if n])
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
        # THE SAME START PERSONS EVERYWHERE (BUGS F171). The ids come from
        # pick_query_ids (ldbc_snb's for LDBC, graph_common's for the
        # synthetic graph), one fixed seed and draws with replacement, so
        # every repetition and every engine reads the same ids and one person
        # can be drawn twice. That is what makes the answer digests
        # comparable. The sentence said "a fresh set of start persons".
        reads = f"Every repetition, on every engine, runs each read against the same start persons, {parts}"
        picked = ("The start persons are picked at random with a fixed seed and with replacement, "
                  "so one person can be picked more than once.")
        if writes and len(set(writes.values())) == 1 and len(writes) == 3:
            w = f"{writes['write_ops']:,}"
            return [_gen(f"{reads}, plus {w} each of the insert, update, and delete; the p50 and p99 are over those. {picked}", parts, w)]
        w = f"{writes.get('write_ops', 0):,}" if writes.get("write_ops") else None
        if w:
            return [_gen(f"{reads}, and commits up to {w} writes; the p50 and p99 are over those. {picked}", parts, w)]
        return [_gen(f"{reads}; the p50 and p99 are over those. {picked}", parts)]
    if table_id == "l2olap":
        n = str(L['graph_common'].OLAP_ITERATIONS)
        return [_gen(f"Each repetition runs every query {n} times; the p50 and p99 are over those runs.", n)]
    if table_id == "l3s" and _instrument_of("l3s") == "2026-10":
        # NOT THE DENSE SENTENCE. The branch below describes the dense
        # multipass overlay (one query set, cold then warm passes over the same
        # queries, pooled over five builds), and on this table it printed "warm
        # pools the four passes after it, over five builds" beside the second-
        # pass note that says the opposite and is right: the sparse warm columns
        # come from a separate run, one build per engine, its cold pass over one
        # half of the queries and five warm passes over the other half. So the
        # sparse table says only what both runs did, read from their own
        # records: the lane's queries per timed pass and the warm-up it
        # discards (the rows' n_queries and query_n), and the half each pass of
        # the second-pass run answers (the files' n_queries).
        lrows = [r for r in _FROZEN_ROWS if r.get("lane") == "l3s"]
        nq = {int(v) for v in (_num(r.get("n_queries")) for r in lrows) if v}
        nt = {int(v) for v in (_num(r.get("query_n")) for r in lrows) if v}
        half = set()
        try:
            root = _pinned_dir("sparse_mp")
            for fp in (sorted(root.glob("sp_*.json")) if root.is_dir() else []):
                for rec in json.loads(fp.read_text(encoding="utf-8")):
                    if _num(rec.get("n_queries")):
                        half.add(int(_num(rec.get("n_queries"))))
        except (OSError, ValueError, SystemExit):
            half = set()
        if len(nq) != 1:
            return []
        n = f"{nq.pop():,}"
        warm = (nt.pop() if len(nt) == 1 else None)
        skip = (int(n.replace(",", "")) - warm) if warm is not None else None
        lead = (f"Each timed pass on this table answers {n} queries, and its p50 and p99 leave out the "
                f"first {skip} as warm-up" if skip and skip > 0 else f"Each timed pass on this table answers {n} queries")
        vals = [n] + ([str(skip)] if skip and skip > 0 else [])
        has_warm = any("warm p50 ms" in (e.get("metrics") or {}) for e in entries)
        if has_warm and len(half) == 1:
            h = f"{half.pop():,}"
            return [_gen(f"{lead}; the second-pass run answers {h} of them in its cold pass and the other "
                         f"{h} in each warm pass.", *vals, h)]
        return [_gen(f"{lead}.", *vals)]
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


def _withheld_recall_items():
    """The freeze's record of the approximate-search rows it withheld for a
    recall below make_paper_tables.RECALL_FLOOR (its sidecar), or []."""
    path = GENERATED / "withheld_recall.json"
    try:
        items = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return items if isinstance(items, list) else []


# ARANGODB 3.12.11 ANSWERS FROM ONE LIST (BUGS F175, DECISIONS #156). On that
# release, once an IVF index has 10,000 or more lists, every multithreaded
# query probes the same single list, so its top 10 is one document repeated.
# The October rep 1 at 9.99M vectors (12,643 lists) finished with recall 0.0,
# while the 1M size (4,000 lists) answers correctly. The threshold is exact
# (9,999 lists pass, 10,000 fail, whatever the data), the stored index is sound
# (single-threaded queries on it answer with recall 1.0), and 3.12.12 passes
# the minimal repro (`.notes/bench/repros/arango-recall-20261004/`); it is also
# the cause of September's withheld 10M cell (F55). So this is no longer an
# unexplained broken index: the row stays on the table marked `n/c`, none of
# its numbers is printed, and the sentence says why and that the next
# measurement runs ArangoDB at its latest stable release (CAMPAIGN section 7
# rows 66 and 67). No re-run at this pin with fewer lists (#156 item 2).
#
# KEYED ON THE ROWS, not on the engine's name alone: an ArangoDB dense row the
# freeze withheld, whose recall is below the floor below, whose index had
# 10,000 or more lists, and whose engine version is a release with the defect.
# The freeze records the list count and the version beside each withheld row
# (make_paper_tables.WITHHELD_RECALL). A repeat on 3.12.11 is caught the same
# way, and rows from a new release, or a sidecar written before those two
# fields, keep the unexplained sentence below, so the declaration retires when
# the version changes. October only: September's page stays as it was frozen.
#
# The floor is the defect's own signature, one list of about 800 vectors out
# of ten million, so recall near 0 (0.0 in October, 0.0001 in September), well
# under the freeze's 0.5; a withheld row between the two is some other failure
# and keeps the unexplained sentence.
_ONE_LIST_MIN_NLISTS = 10_000
_ONE_LIST_RELEASES = ("3.12.11",)
_ONE_LIST_RECALL_BELOW = 0.01


def _one_list_release(engine_version):
    """The x.y.z release in an ArangoDB row's engine_version ("arangodb:3.12.11")."""
    m = re.search(r"(\d+\.\d+\.\d+)", str(engine_version or ""))
    return m.group(1) if m else None


def _one_list_groups(table_id):
    """(backend, scale) -> the withheld rows behind this table that the
    one-list defect decided, as the freeze recorded them; {} when none is."""
    if table_id != "l3d" or not _OCTOBER_ENV:
        return {}
    out = {}
    for it in _withheld_recall_items():
        try:
            rec = float(it.get("recall_at_10"))
            nlists = int(it.get("ivf_nlists"))
        except (TypeError, ValueError):
            continue
        if (it.get("lane") == "l3d"
                and str(it.get("backend") or "").startswith("arangodb")
                and rec < _ONE_LIST_RECALL_BELOW
                and nlists >= _ONE_LIST_MIN_NLISTS
                and _one_list_release(it.get("engine_version")) in _ONE_LIST_RELEASES):
            out.setdefault((str(it.get("backend")), str(it.get("scale"))), []).append(it)
    return out


def _one_list_note(backend, scale, items):
    """The not-comparable sentence for one ArangoDB dense cell the one-list
    defect decided. No recall or latency is printed: they are what the defect
    produced, not what the engine's search does."""
    label = display_name(backend)
    size = scale_label("l3d", scale)
    releases = sorted({_one_list_release(it.get("engine_version")) for it in items})
    lists = sorted({int(it.get("ivf_nlists")) for it in items})
    floor = f"{_ONE_LIST_MIN_NLISTS:,}"
    has = (f"The index at this size has {lists[0]:,} lists" if len(lists) == 1
           else "The index at this size has at least that many")
    found = ("none" if all(float(it.get("recall_at_10")) == 0.0 for it in items)
             else "almost none")
    text = (f"{label} at {size} is not comparable. On the release measured here, "
            f"{_join_and(releases)}, an IVF index with {floor} or more lists answers every "
            f"query from one fixed list. {has}, so the search returned {found} of the true "
            f"neighbours, and the cell is not a measurement of {label}'s search. The next "
            f"measurement runs {label} at its latest stable release.")
    # Filed under the release move, which the page's list of changes already
    # states for every engine other than ArcadeDB, so this sentence adds no
    # line of its own and is not counted as a change no line covers.
    return _next_item("release", _gen(text, label, size, *releases, floor,
                                      *(f"{n:,}" for n in lists[:1] if len(lists) == 1)))


def _dense_row_label(backend):
    """The label the dense table prints for this arm: the name and the
    precision it stores, as the entries are labelled (ArcadeDB's two embedded
    arms and sqlite-vec's two arms differ in nothing else). A sentence that
    names an arm has to name it the way its row is named."""
    label = display_name(backend)
    prec = DENSE_PRECISION.get(backend)
    if not prec:
        return label
    return f"{label[:-1]}, {prec})" if label.endswith(")") else f"{label} ({prec})"


def _withheld_recall_cells(table_id):
    """[(backend, scale, note, known)] for every approximate-search cell the
    freeze withheld for a recall below make_paper_tables.RECALL_FLOOR (the
    sidecar it writes), in the order the sentences are printed. `known` is True
    for a cell a known engine defect decided (_one_list_note), whose row stays
    on the table marked `n/c`; the others are gone from the table and are
    declared as absences by _declare_withheld_tier_absences."""
    if table_id not in ("l3d", "l3s"):
        return []
    items = _withheld_recall_items()
    lane = table_id
    known = _one_list_groups(table_id)
    seen = {}
    for it in items:
        if it.get("lane") != lane:
            continue
        key = (str(it.get("backend")), str(it.get("scale")))
        seen.setdefault(key, []).append(float(it.get("recall_at_10") or 0.0))
    notes = []
    for (backend, scale), recs in sorted(seen.items()):
        if (backend, scale) in known:
            notes.append((backend, scale, _one_list_note(backend, scale, known[(backend, scale)]), True))
            continue
        # THE PRECISION, WHERE THE LANE HAS ARMS THAT DIFFER IN IT. This named
        # sqlite-vec's int8 arm "sqlite-vec" while the table prints its fp32 arm
        # at the same size, with a good recall, so the sentence read as a
        # statement about the row beside it (the first October dense landing,
        # 2026-10-06). The table's own label for the arm is the name to use.
        label = (_dense_row_label(backend) if lane == "l3d" and _OCTOBER_ENV
                 else display_name(backend))
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
        notes.append((backend, scale, _gen(
            f"{label} at {size} is withheld: its search answered with a recall@10 of "
            f"{max(recs):.4f} across {len(recs)} repetition(s), which is not a measurement of "
            f"search but of a broken index, so its latency is not printed beside engines "
            f"answering correctly. The cause is investigated on the benchmark machine before anything "
            f"is claimed about it (BUGS F55).",
            label, size, f"{max(recs):.4f}", str(len(recs))), False))
    return notes


def _withheld_recall_notes(table_id):
    """One sentence per approximate-search cell the freeze withheld for a recall
    below make_paper_tables.RECALL_FLOOR (the sidecar it writes). The cell's
    absence is said under the table rather than left as a missing row; a cell
    a known engine defect decided gets the sentence that names it instead
    (_one_list_note)."""
    return [note for _b, _s, note, _known in _withheld_recall_cells(table_id)]


def _declare_withheld_tier_absences(table):
    """Declare, as data, the columns a withheld cell would have carried.

    A cell the freeze withheld for its recall leaves the table with no entry
    for that engine at that size, and the sentence under the table says so, but
    the page's coverage gate reads declarations and not sentences (page_check
    A1). Where the withheld size is the only one that carries a column -- the
    insert and delete maintenance pass runs at the 1M tier alone -- the
    engine's cells in it are absent BECAUSE the cell was withheld, which is the
    `withheld` kind of declared absence. Columns another size also carries are
    left alone: a blank there has some other reason, and this one would be
    claiming it.
    """
    tid = table.get("id")
    entries = table.get("entries", [])
    if not _OCTOBER_ENV:
        return   # September's page stays as it was frozen (DECISIONS #83)
    for backend, scale, note, known in _withheld_recall_cells(tid):
        if known:
            continue
        mine = [e for e in entries if str(e.get("backend_key")) == backend]
        if not mine:
            continue
        label = str(mine[0].get("backend"))
        for col in table.get("columns") or []:
            carried = {str(e.get("scale")) for e in entries
                       if isinstance((e.get("metrics") or {}).get(col), dict)
                       and (e["metrics"][col] or {}).get("median") is not None}
            has = any(isinstance((e.get("metrics") or {}).get(col), dict)
                      and (e["metrics"][col] or {}).get("median") is not None for e in mine)
            if carried == {scale} and not has:
                _declare_absence(tid, label, col, "withheld", note)


# THE SENSITIVITY ARM IS PRINTED ON ONE TABLE (CAMPAIGN 7 row 69): beside the main served
# row on the documents transaction table, and nowhere else. It runs the transaction workload
# only and the relaxed class only, so on the analytics table it would be a row of ingest and
# memory with no query cell, and on the durability table half a pair. {backend key: the
# table ids that print it}. Applied to every table in _finish_table, so no builder has to know.
ARM_TABLES = {"arcadedb_imgdefaults_server": ("docs_oltp",)}


def _drop_arms_not_printed_here(table):
    tid = table.get("id")
    hidden_keys = {k for k, tabs in ARM_TABLES.items() if tid not in tabs}
    if not hidden_keys:
        return
    hidden_labels = {display_name(k) for k in hidden_keys}
    keep = lambda e: not (e.get("backend_key") in hidden_keys or str(e.get("backend")) in hidden_labels)
    table["entries"] = [e for e in table.get("entries") or [] if keep(e)]
    if table.get("declared_absences"):
        table["declared_absences"] = [a for a in table["declared_absences"]
                                      if str(a.get("backend")) not in hidden_labels]


def _finish_table(table: dict) -> dict:
    _drop_arms_not_printed_here(table)
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
        for note in (_surreal_pair_note(table),
                     _jvm_memory_note(table),
                     _pg_memory_note(table) if table.get("id") in ("docs_oltp", "docs_olap") else None,
                     _gav_build_note(table) if table.get("id") == "l2olap" else None,
                     _dense_cold_warm_note(table) if table.get("id") == "l3d" else None):
            if note:
                base.append(note)
    _declare_withheld_tier_absences(table)
    table["conditions"] = (base
                           + _counts_note(table.get("id"), table.get("entries", []))
                           + _index_note(table.get("id"), table)
                           + _arcadedb_hash_index_notes(table)
                           + _jvm_defaults_notes(table)
                           + _split_note(table)
                           + _phase_split_notes(table)
                           + _delete_settle_notes(table)
                           + _censored_notes(table.get("id"))
                           + _query_budget_notes(table.get("id"))
                           + _zero_growth_notes(table.get("id"))
                           + _unexpressible_notes(table.get("id"), table.get("entries", []))
                           + _withheld_recall_notes(table.get("id")))
    # AN ARM THE SKELETON NEVER RAN IS NOT A GAP IN THE CAMPAIGN. The laptop
    # placeholder runs one small corpus per lane and does not always run every
    # workload of it: `surrealdb_tpc` has OLTP rows and no analytics row,
    # while its served twin has both. The coverage gate is right to refuse an
    # engine that is registered for a lane, prints nothing, and says nothing
    # -- that is how a silently dropped arm looks. So the skeleton says it,
    # derived from the rows rather than typed into a list that would go stale
    # the first time the placeholder run changed shape. Campaign payloads are
    # untouched: there an unrun arm IS a finding, and must stay one.
    if SKELETON:
        _lane_wl = _TABLE_LANE.get(table.get("id"))
        if _lane_wl:
            _lane, _wl = _lane_wl
            _have = {str(e.get("backend_key") or "") for e in table.get("entries") or []}
            # MERGED, for the reason every other note on this page is merged:
            # these differ only in a name, and thirteen of them under one
            # table is a loop's output. One sentence, every engine named.
            # Not the off-page arms: they are absent from every table by
            # decision (OFF_PAGE_ARMS), and saying "the skeleton did not cover"
            # them names an arm the page does not print, which page_check's
            # OFF-PAGE check refuses (found rehearsing the 26.10.1 publish).
            # Nor an arm that does not run this table's workload (runner.ARM_RUNS) or is
            # printed on another table only (ARM_TABLES): it is not owed here.
            _norow = [display_name(_be) for _be in (LANES_RUNNER.get(_lane) or ())
                      if _be not in _have and _be not in OFF_PAGE_ARMS
                      and arm_runs(_lane, _wl, _be)
                      and table.get("id") in ARM_TABLES.get(_be, (table.get("id"),))]
            if _norow:
                _who = _join_and(_norow)
                _why = _gen(f"{_who} {'has' if len(_norow) == 1 else 'have'} no row on this "
                            f"table: the skeleton is a placeholder run and did not cover this "
                            f"workload for {'it' if len(_norow) == 1 else 'them'}. The real "
                            f"run does.", _who)
                table.setdefault("conditions", [])
                if _why not in table["conditions"]:
                    table["conditions"].append(_why)
                for _n in _norow:
                    _declare_absence(table.get("id"), _n, None, "unrun", _why)
            # AND THE PARTIAL ROWS, which are the harder half. `surrealdb_tpc`
            # HAS a row here: its OLTP run supplies ingest, disk and memory,
            # so the arm looks present while every analytics cell is empty.
            # A whole-row declaration does not cover it and a reader cannot
            # tell those blanks from a slow engine. One sentence per engine,
            # and a declaration per column, which is what the gate reads.
            _partial = {}
            for _e in table.get("entries") or []:
                _miss = tuple(c for c in (table.get("columns") or [])
                              if (_e.get("metrics") or {}).get(c) is None)
                if not _miss or _e.get("outcome"):
                    continue
                _partial.setdefault(_miss, []).append(str(_e.get("backend")))
            for _miss, _whos in sorted(_partial.items(), key=str):
                _who = _join_and(_whos)
                _why = _gen(f"{_who} {'prints' if len(_whos) == 1 else 'print'} no "
                            f"{_join_and(list(_miss))} here: the skeleton is a placeholder "
                            f"run and did not cover that workload for "
                            f"{'this arm' if len(_whos) == 1 else 'those arms'}, though it ran "
                            f"the ingest the other columns come from. The real run measures both.",
                            _who, _join_and(list(_miss)))
                table.setdefault("conditions", [])
                if _why not in table["conditions"]:
                    table["conditions"].append(_why)
                for _n in _whos:
                    for _c in _miss:
                        _declare_absence(table.get("id"), _n, _c, "unrun", _why)

    # DECISIONS #111. Added AFTER every note and number is computed, so
    # nothing that averages, ranks or counts a measurement can see them.
    _marked, _marks = _censored_entries(table)
    # A cell a known engine defect decided keeps its row, marked `n/c` (BUGS
    # F175): unless a censored row already stands for the same engine and size.
    _nc, _nc_marks = _not_comparable_entries(
        table, {(str(m.get("backend_key")), str(m.get("scale"))) for m in _marked})
    _marked = _marked + _nc
    _marks = set(_marks) | _nc_marks
    # ONE LEGEND for every mark on the table: the censored rows' and the
    # `re-run` cells the #117 withholding placed on rows that stand.
    _marks = set(_marks) | {st["text"] for e in table.get("entries", [])
                            for st in (e.get("metrics") or {}).values()
                            if isinstance(st, dict) and st.get("text") == "re-run"}
    if _marks:
        table["conditions"] = table["conditions"] + _mark_legend(_marks)
    # ONE ROW PER ENGINE AND SIZE. A cell killed after its load finished
    # leaves rows that carry the load's numbers (ingest, peak, disk) beside
    # the error, and the table builder made a measured-looking entry of them
    # next to the censored one: the served SurrealDB SF10 analytics cell would
    # have printed twice, once with 55 minutes of ingest and once as `OOM`
    # (rehearsal of qOE's landing, 2026-09-26). A cell is censored only when
    # it has no clean row, so an entry sharing its engine and size was built
    # from failed rows alone; the censored row and its note stand for it.
    _cens = {(str(m.get("backend_key")), str(m.get("scale"))) for m in _marked}
    table["entries"] = [e for e in table["entries"]
                        if e.get("outcome") or (str(e.get("backend_key")), str(e.get("scale"))) not in _cens]
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
    # THE HEAP BESIDE THE PEAK (DECISIONS #116 item 7, decided 2026-09-26: the
    # memory column stays the peak an operator has to provision, with the heap
    # printed beside it for JVM engines). A JVM engine's peak sits close to the
    # heap it was given, so the setting belongs next to the number. From the
    # rows behind the cell at its own size only; an engine that records no
    # heap, or a cell whose rows ran two, prints none.
    _lw = _TABLE_LANE.get(table.get("id"))
    if _lw:
        _hl, _hw = _lw
        if _hl == "l1tpc":
            _hw = "oltp"
        for _e in table["entries"]:
            _pk = (_e.get("metrics") or {}).get("peak memory GiB")
            if _e.get("outcome") or not isinstance(_pk, dict) or _pk.get("median") is None:
                continue
            _hs = _entry_heaps(_e, _hl, _hw, exact_only=True)
            if len(_hs) == 1:
                _e["metrics"]["JVM heap"] = {"text": _hs.pop()}
    # Every metric a row carries is a column the page shows. l3smp carried
    # peak memory and disk in its rows and listed neither, so the page showed
    # neither (the renderer trusts `columns`).
    cols = list(table["columns"])
    extra = []
    for e in table["entries"]:
        for m in e.get("metrics", {}):
            if m not in cols and m not in extra:
                extra.append(m)
    tail = [m for m in ("peak memory GiB", "JVM heap", "disk GiB") if m in extra]
    cols = cols + [m for m in extra if m not in tail] + tail
    # ONE ORDER FOR EVERY TABLE (2026-09-11): the workload's own columns in
    # the order its spec lists them, then recall, then the ingest pair (rate,
    # then total), then peak memory, then disk. Tables used to put ingest
    # wherever the spec happened to list it.
    def _rank(c):
        if c == "recall@10":
            return 1
        # `index s` is the second half of the ingest split (FAIRNESS F14),
        # printed after `ingest s`; ranked as a workload column it printed
        # before the ingest rate, apart from its other half (#8).
        if c.startswith("ingest") or c == "index s":
            return 2 if "/s" in c else 3
        if c == "peak memory GiB":
            return 4
        if c == "JVM heap":
            return 4.5
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
# What each machine is TO A READER. The keys of HOST_HARDWARE are our own
# hostnames and must stay that way -- rows carry `bench_host` and the lookup
# is by that -- but nothing with a hostname in it reaches the page.
HOST_ROLE = {
    "mini": "benchmark machine",
    "laptop": "development machine",
}

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
    # KEYED BY ROLE, NOT BY OUR HOSTNAME. `setup.hosts` is published, so the
    # key is reader-facing, and it read "mini" on the live page and "laptop"
    # on the preview -- the names of two machines in this room, which tell a
    # reader nothing and are the internal voice the page is not supposed to
    # carry. The hardware underneath is exactly as specific as it was; only
    # the label changes, from a name to what the machine IS to the reader.
    return {HOST_ROLE.get(h, h): HOST_HARDWARE[h] for h in named}


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
    elif "l3s" in by:
        # NO SECOND PASS TO FOLD, the lane's own pass is still the cold one.
        # The skeleton declares l3smp absent, and a sparse landing can arrive
        # before its overlay; either way the single pass is the first after
        # the build, so its columns are labelled cold as the folded table's
        # are, and the query set's `cold p50 ms` is a column (page_check
        # coverage A1 refused the skeleton's `p50 ms`, rehearsing the 26.10.1
        # publish, 2026-10-02). No warm columns: there is no warm pass to show.
        t = by["l3s"]
        for e in t["entries"]:
            m = e["metrics"]
            if "p50 ms" in m:
                m["cold p50 ms"] = m.pop("p50 ms")
            if "p99 ms" in m:
                m["cold p99 ms"] = m.pop("p99 ms")
        t["columns"] = [{"p50 ms": "cold p50 ms", "p99 ms": "cold p99 ms"}.get(c, c) for c in t["columns"]]
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
        # The ingest/index split rides with the total (FAIRNESS F14), as on
        # every other October table; without it here the documents tables
        # printed the total alone although their rows record both phases
        # (humemai/arcadedb-embedded-python#8).
        # In the order every other October table prints them, and named in
        # "columns" up front: the notes that read a table's columns (the
        # ingest/index split sentence among them) run before the columns an
        # entry carries beyond that list are appended, so a column left to
        # that append printed out of order and without its sentence.
        SHARED_ORDER = ["ingest documents/s", "ingest total s", "ingest s", "index s",
                        "peak memory GiB", "disk GiB"]
        SHARED_COLS = set(SHARED_ORDER)
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
                       "dataset": ("TPC-C new-order on the TPC-H tables (SF1, SF10)" if _oct else
                                   "TPC-C new-order on the TPC-H SF1 tables"),
                       "conditions": list(src["conditions"]),
                       "columns": (OCT_OLTP_COLS + SHARED_ORDER if _oct else
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
        #
        # SEPTEMBER'S ROWS ONLY. October runs the corrected query texts, and its
        # answers are checked: at SF1 all ten engines, both ArcadeDB arms
        # included, return the same digest for all five queries, and at SF10
        # both ArcadeDB arms match DuckDB and SQLite on all five. Applied to the
        # October payload too, this block withdrew those checked rows and
        # printed September's reason under a table whose own condition
        # sentences described ArcadeDB's SF10 cells (caught rehearsing qOE's
        # landing, 2026-09-25, BUGS F127).
        _withdrawn = [] if _oct else [e for e in src["entries"]
                                      if str(e.get("backend", "")).lower().startswith("arcadedb")]
        _olap_entries = [clone(e, OLAP_KEEP) for e in src["entries"] if e not in _withdrawn]
        # GENERATED, NOT TYPED. Under the October instrument every sentence
        # must be one or the other, and this one was a bare string: September
        # never checked, so the withdrawal that has been on the page since
        # 2026-09-14 failed the first October-instrument payload to be gated.
        _withdrawal = _gen("ArcadeDB has no row on this table. Answer checking built for the next campaign "
                       "found that the two queries it ran here were not the questions the comparators "
                       "answered: one of the five aggregates was missing from our Q1 text, and its Q6 "
                       "excluded the boundary discount because the engine reads `>= 0.05` against a "
                       "decimal literal as strictly greater. Both errors made its numbers faster than "
                       "the truth, so they are withdrawn rather than shown with a caveat, and the next "
                       "run measures them with every engine's answer compared.", "0.05")
        # THE SENTENCE IS NOT THE DECLARATION. A reader gets the prose above; the
        # coverage gate reads `declared_absences`, and under the 2026-10
        # instrument it fails a registered arm that has neither a row nor an
        # entry there. September never hit it because that check is skipped on
        # the older instrument, so the withdrawal has been prose-only since
        # 2026-09-14 and the first October-instrument payload to be gated --
        # the skeleton -- failed on both ArcadeDB arms.
        for _e in _withdrawn:
            _declare_absence("docs_olap", str(_e.get("backend")), None, "withdrawn", _withdrawal)
        tables.append({"id": "docs_olap", "title": "Document OLAP",
                       "dataset": ("TPC-H Q1, Q6, top parts, ship mode, and by month (SF1, SF10)" if _oct else
                                   "TPC-H Q1 and Q6 at SF1"),
                       "conditions": list(src["conditions"]) + ([_withdrawal] if _withdrawn else []),
                       "columns": (OCT_OLAP_COLS + SHARED_ORDER if _oct else
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
            # THE ARM MOVED IMAGE, NOT JUST DIGEST (DECISIONS #117: the composed
            # stack became dbbench:composed). The stale-pin repair above only
            # swaps a digest inside the same repository, so an arm whose rows
            # ran neo4j@sha256:... would print the new local image beside
            # numbers that image never produced. Its rows say what they ran.
            _row_ref = rs[0].get("server_image_ref")
            if (_row_ref and image and not str(backend).startswith("arcadedb")
                    and str(_row_ref).split("@")[0].split(":")[0] != str(image).split("@")[0].split(":")[0]):
                image = str(_row_ref)
            label = (spec.get("labels") or {}).get(backend) or display_name(backend)
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
                    #
                    # A COMPOSED ARM HAS MORE THAN ONE IMAGE AND ONLY ONE FITS
                    # HERE. `server_image` for Qdrant + Neo4j is the NEO4J
                    # digest, so the pin table named neo4j and the Qdrant half
                    # vanished: the cross-model tables published the composed
                    # stack as "neo4j 2026.08.1", on the two tables whose whole
                    # subject is that it takes two systems. The row's own
                    # string names every member, so it wins wherever it names
                    # more than one.
                    else (rs[0].get("engine_version")
                          if len(_composed_members(rs[0].get("engine_version"))) > 1
                          else (names.get(image) or rs[0].get("engine_version"))
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
                # THE MAINTENANCE COLUMNS LIVE ON THE CAMPAIGN ROW, NOT IN THE
                # OVERLAY. The insert and delete pass runs once per engine, in
                # the single-pass cell at the 1M tier (l3d_dense.MUTATE_SCALES),
                # and the multipass overlay's files carry only the five query
                # passes. Replacing the 1M entries with the overlay's dropped
                # the six #82d columns from the table, and the page's own
                # sentence about them ("run at 1M vectors") stood over columns
                # that were not there (the first October dense landing,
                # 2026-10-06; page_check A1 caught it). They are carried over
                # the way peak memory and disk already are: from the campaign
                # cell of the same arm at the same size. An overlay row keeps
                # its own value where it has one.
                _campaign_small = {e["backend_key"]: e for e in entries if e["scale"] == "small"}
                _mutate_cols = [lbl for fld, lbl in OCT_TABLE_METRICS["l3d"]
                                if isinstance(fld, str) and fld.startswith("mutate_")]
                for _e in _mps:
                    _src = (_campaign_small.get(_e["backend_key"]) or {}).get("metrics", {})
                    for _col in _mutate_cols:
                        if _col in _src and _col not in _e["metrics"]:
                            _e["metrics"][_col] = _src[_col]
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
        _ages = _ldbc_age_note(_t.get("id"), rows)
        if _ages:
            _t.setdefault("conditions", [])
            if _ages not in _t["conditions"]:
                _t["conditions"].append(_ages)
        _one_way = _knows_one_way_note(_t.get("id"), rows)
        if _one_way:
            _t.setdefault("conditions", [])
            if _one_way not in _t["conditions"]:
                _t["conditions"].append(_one_way)
        # The rest of what the next measurement changes about a table, each
        # keyed on a field its rows will record (BUGS F174, DECISIONS #153,
        # #154, #157). The documents OLTP table carries its warm-up sentence
        # in place of the cold-column one (_cold_note); the durability table
        # has no cold column and carries it here.
        for _note in (_lsqb_id_form_note(_t.get("id"), rows),
                      _gav_scope_note(_t.get("id"), rows),
                      _sparse_whole_record_note(_t.get("id"), rows),
                      _docs_warmup_note(_t.get("id"), rows) if _t.get("id") == "durability" else None):
            if _note:
                _t.setdefault("conditions", [])
                if _note not in _t["conditions"]:
                    _t["conditions"].append(_note)
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
        # NOR on the restart table: the note speaks of write and transaction
        # cells matched at the relaxed end, and the restart table has none. Its
        # vector servers run at the engine default their own table never sets,
        # which the note would read as relaxed; the table's own sentence says
        # what each stop is measured against (OCT_PROSE["restart"]["durability"]).
        if _t.get("id") == "restart":
            continue
        _note = _durability_note(_t.get("entries", []), rows,
                                 (_TABLE_LANE.get(_t.get("id")) or (None,))[0])
        if _note:
            _t.setdefault("conditions", [])
            if _note not in _t["conditions"]:
                _t["conditions"].append(_note)
    # A CLEAN STOP THAT DOES NOT END CLEANLY (2026-10-02, milvus-io/milvus#53947).
    # The restart lane sends the image's own stop signal and records the exit
    # code; 0, or 143 for a process that ends by the signal after its shutdown
    # hook ran (every JVM here), is a normal end. Milvus ends every clean stop
    # in a panic in its shutdown path (exit 134) with its data intact, so its
    # stop time is the time to that abort, and the table says so. Generated
    # from the rows, so an engine that starts or stops doing this moves with them.
    for _t in tables:
        if _t.get("id") != "restart":
            continue
        _abnormal = {}
        for _r in rows:
            if _r.get("lane") != "restart" or _r.get("error") or _r.get("stop_killed_after_grace"):
                continue
            _codes = {c for c in (_r.get("stop_exit_codes") or []) if c not in (0, 143)}
            if _codes:
                _abnormal.setdefault(display_name(str(_r.get("backend"))), set()).update(_codes)
        for _name, _codes in sorted(_abnormal.items()):
            _c = ", ".join(str(x) for x in sorted(_codes))
            _what = "an abort" if _codes == {134} else "an abnormal exit"
            _note = _gen(f"{_name}'s clean stop ends in {_what}, exit code {_c}, rather than a normal exit, "
                         f"although every row it wrote is there after the restart; its stop time is the time "
                         f"to that exit.", _c)
            _t.setdefault("conditions", [])
            if _note not in _t["conditions"]:
                _t["conditions"].append(_note)
    # THE OVERRIDES A READER MEETS (CAMPAIGN section 7 row 21). PROTOCOL.md
    # section 7 lists every default this benchmark overrides, and the rows its
    # last column marked NOWHERE were named in no sentence under any table. One
    # sentence per override, under every October table that shows an arm that
    # runs it, generated from the rows (overrides.py); page_check refuses a
    # table that shows such an arm and prints no sentence saying so, and
    # fairness_check refuses a row that lacks the engine's own read-back.
    import overrides as _OV
    for _t in tables:
        if _table_instrument(_t.get("id")) != "2026-10":
            continue
        _lane = (_TABLE_LANE.get(_t.get("id")) or (None,))[0]
        for _text, _vals in _OV.notes_for_table(
                _t.get("id"), _lane,
                [e.get("backend_key") for e in _t.get("entries") or []], rows):
            _note = _gen(_text, *_vals)
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
        # SAID THE WAY A READER READS IT. This sentence used our words for
        # our own plumbing -- which "lanes" record a host, what "this file"
        # can prove -- and the fact it carries is simpler than that: some
        # rows name the machine and some name only the container they ran in,
        # and we publish what the rows actually say rather than filling the
        # gap in. Same rule as the hostnames: say the fact, not the filing.
        "provenance_note": (
            "Some benchmarks record which machine they ran on and some record "
            "only the container, so that column is filled in where it was "
            "measured and left alone where it was not. Everything on this page "
            "ran on the same machine; this note reports what each result can "
            "actually show rather than what we know to be true of all of them."
        ),
        "hosts_recorded": hosts,
        "setup": {
            # Lanes that record the container rather than the machine stamp
            # "container:<id> (host unknown)"; the named hosts are the ones
            # that must have hardware on record.
            "hosts": _host_hardware(hosts, rows),
            "cpuset": _dominant_cpuset(rows),
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
    # WHAT THE NEXT MEASUREMENT CHANGES, last among the page's conditions and
    # read off the FINISHED tables: _finish_table adds the query words and the
    # repetition sentences, so the list cannot be built with the global
    # conditions above, which are computed before it runs.
    if _october:
        payload["conditions"] += _next_measurement_note(payload["tables"])

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
