#!/usr/bin/env python3
"""One engine wears one version across the whole page (DECISIONS #103d, #103e).

BUGS.md F61: the live page carries DuckDB 1.5.5 on the document, time-series and
dense tables beside DuckPGQ on DuckDB 1.5.4, because the stage that would have
moved the other arms was cancelled. Every row was correct about the version it
ran; nothing compared them ACROSS tables, so the only thing that caught it was a
human reading the payload. This is that comparison, run as a gate.

Version strings are not one shape. A row may say "duckdb 1.5.4", or name a
wrapper over an engine ("duckpgq:f386a6c on duckdb:1.5.4"), so the check looks
for each family name anywhere in the string and takes the version beside it,
rather than splitting on the first space and hoping.

Usage:
    python3 version_consistency_check.py <payload.json> [more.json ...]

Exit 0 when every family wears one version, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

# Families whose arms appear under several backend labels and must agree. A
# family is a substring matched case-insensitively inside the version string.
FAMILIES = ("arcadedb", "duckdb", "postgres", "neo4j", "mongo", "surrealdb",
            "arangodb", "qdrant", "milvus", "sqlite", "chroma", "lancedb",
            "memgraph", "falkordb", "timescaledb", "questdb", "elasticsearch",
            # Each of these ships its own version line on a row that also
            # names another engine -- pgvector and AGE are PostgreSQL
            # extensions, DuckPGQ a DuckDB one, ladybug its own engine -- so
            # each is a family in its own right rather than a qualifier.
            "pgvector", "age", "duckpgq", "ladybug", "sqlite-vec")

# Deliberate splits: family -> why more than one version is correct here. An
# entry is a DECISION, not a way to quiet the gate, and it must name two
# genuinely different artifacts rather than two measurements of one.
ALLOWED_SPLITS: dict[str, str] = {
    "surrealdb":
        "embedded and served SurrealDB are two artifacts with independent "
        "version lines, not one engine measured twice: the embedded arm runs "
        "the Rust core bundled inside the pinned SDK wheel "
        "(surrealdb-embedded:2.3.10, sdk 2.0.0) and the served arm runs the "
        "standalone server binary (surrealdb-server:3.2.4). The embedded arm "
        "can only be as new as the wheel ships, which is an asymmetry the "
        "page states rather than hides, and every row names its deployment",
    "qdrant":
        "the composed cross-model stack's vector half is qdrant-local, the "
        "client library's IN-PROCESS engine, not the served qdrant/qdrant "
        "image the vector tables run; two artifacts with their own version "
        "lines. It is also an unsanctioned fairness gap -- that half still "
        "opens location=':memory:' while ArcadeDB runs on disk -- disclosed "
        "on the table in PROTOCOL section 7 and retired in October, at which "
        "point this entry should go rather than be renewed",
}

_VER = r"[ :=v]*([0-9]+(?:\.[0-9]+)+)"

# HOW AN ENGINE SPELLS ITSELF IS NOT ITS FAMILY NAME, and for twelve of the
# seventeen families it never was. The scan below wants the version to follow
# the family token immediately, so "mongo" never matched `mongodb 8.2.12`,
# "postgres" never matched `postgresql 18.6`, and "duckdb" never matched
# `duckdb vss 1.5.5`. 23 of the 191 rows on the live September payload carried
# a version string this gate could not read, and an unreadable string was
# silently dropped rather than flagged -- so the gate passed by seeing almost
# nothing. That is how a cross-model arm ran PostgreSQL 17.11 + age 1.7.0
# under an October instrument declaring 18.6 + 1.8.0 with every gate green.
#
# The qualifiers here are part of a product's NAME (DuckDB VSS, sqlite-vec),
# never a second component with its own version line. Nothing skips a space
# into arbitrary words, and that restraint is load-bearing: MongoDB's row
# reads `mongodb 8.2.12 + MongoDb Search Community Version 1.70.4`, and a
# pattern loose enough to reach across " search community version " would
# read mongot's version as a second MongoDB and report a split that is not
# there. Components that DO have their own version line get their own family.
SPELLINGS = {
    "postgres": r"postgres(?:ql)?",
    "mongo": r"mongo(?:db)?",
    "ladybug": r"ladybug(?:db)?",
    "duckdb": r"duckdb(?:[ -]vss)?",
}

# An ArcadeDB release is YY.M.P with a two-digit year in the twenties. A
# comparator row wearing one of these is not a version disagreement, it is OUR
# version printed on somebody else's engine, which is worse and reads as
# plausible. BUGS.md F63: the live page published "surrealdb 26.9.1" because the
# dense overlay's fallback found an ArcadeDB wheel stamp on a comparator row and
# _engine_version prefixed it with the label's engine name.
_OURS = re.compile(r"^2[0-9]\.[0-9]{1,2}\.[0-9]+$")


def _rows(node, table=None):
    """Yield (table_id, backend, version_name) for every row in a payload."""
    if isinstance(node, dict):
        tid = node.get("id", table) if "entries" in node else table
        if isinstance(node.get("version_name"), str):
            yield tid, node.get("backend", "?"), node["version_name"]
        for value in node.values():
            yield from _rows(value, tid)
    elif isinstance(node, list):
        for value in node:
            yield from _rows(value, table)


def _versionless_measurements(node, table=None):
    """Rows that PUBLISH A NUMBER without naming the engine that produced it.

    `_rows` above can only reason about version strings that exist, so a row
    with no `version_name` at all was invisible to every check in this file --
    one level below the unreadable-string hole and with the same consequence.
    A DECLARED OUTCOME is exempt and must be: a censored or failed cell
    carries `kind`/`why` and no metrics, names no engine because it measured
    nothing, and saying so is the point of it. A row with metrics is a
    measurement, and a measurement that cannot say which engine produced it
    is not publishable.
    """
    if isinstance(node, dict):
        tid = node.get("id", table) if "entries" in node else table
        if "backend" in node and node.get("metrics"):
            if not isinstance(node.get("version_name"), str) or not node["version_name"].strip():
                yield tid, node.get("backend", "?")
        for value in node.values():
            yield from _versionless_measurements(value, tid)
    elif isinstance(node, list):
        for value in node:
            yield from _versionless_measurements(value, table)


def check(path: str) -> list[str]:
    payload = json.load(open(path))
    # A SKELETON is declared placeholder data: laptop timings, one repetition,
    # the smallest corpus, and an `arcadedb_version` of null precisely because
    # it cannot name one. Arms re-measured on the new build sit beside arms
    # that have not been, and that is the point of the route rather than a
    # defect. Comparators are still held: a skeleton may be rough, not wrong
    # about whose engine it ran.
    skeleton = bool(payload.get("skeleton"))
    seen: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    unparsed: list[tuple] = []
    for table, backend, version in _rows(payload):
        low = version.lower()
        hit = False
        for family in FAMILIES:
            pat = SPELLINGS.get(family, re.escape(family))
            for match in re.finditer(r"\b" + pat + _VER, low):
                seen[family][match.group(1)].add((table, backend))
                hit = True
        if not hit:
            unparsed.append((table, backend, version))

    failures = []

    # (0) A VERSION STRING THIS GATE CANNOT READ IS A FAILURE, not a row to
    # skip. Everything below reasons about versions it managed to parse, so
    # an unreadable string used to buy silence: the arm was neither vouched
    # for nor flagged, and the gate reported green having examined nothing.
    # A new engine, or an old one that changes how it spells itself, lands
    # here and says so rather than quietly leaving the instrument.
    for table, backend in sorted(set(_versionless_measurements(payload)),
                                 key=lambda w: (str(w[0]), str(w[1]))):
        failures.append(
            f"{backend} publishes a measurement on table {table} with no "
            f"engine version at all: the row carries numbers and names "
            f"nothing that produced them")

    for table, backend, version in unparsed:
        failures.append(
            f"no engine version could be read from {version!r} "
            f"({backend}, table {table}): the gate cannot tell which engine "
            f"this names, so it can vouch for nothing on this row")

    # (a) our version on somebody else's row
    for family, versions in sorted(seen.items()):
        if family == "arcadedb":
            continue
        for version, where in sorted(versions.items()):
            if _OURS.match(version):
                rows = ", ".join(f"{b} (table {t})" for t, b in sorted(
                    where, key=lambda w: (str(w[0]), w[1])))
                failures.append(
                    f"{family} wears {version}, which is an ArcadeDB release "
                    f"number, not {family}'s: {rows}")

    # (b) one backend label, two spellings of its version
    spellings = defaultdict(set)
    for table, backend, version in _rows(payload):
        spellings[backend].add(version.strip())
    for backend, values in sorted(spellings.items()):
        norm = {re.sub(r"\bv(?=[0-9])", "", v) for v in values}
        if len(values) > 1 and len(norm) == 1:
            failures.append(
                f"{backend} spells one version two ways across tables "
                f"({', '.join(sorted(values))}); a string comparison across "
                f"tables cannot see they agree")
        elif len(values) > 1:
            failures.append(
                f"{backend} publishes {len(values)} different version strings: "
                f"{', '.join(sorted(values))}")

    # (c) one engine family, two versions
    for family, versions in sorted(seen.items()):
        if len(versions) < 2:
            continue
        if family == "arcadedb" and skeleton:
            print(f"  ALLOWED arcadedb: {', '.join(sorted(versions))} -- a "
                  f"skeleton payload, which declares arcadedb_version null and "
                  f"mixes re-measured arms with placeholders by design")
            continue
        if family in ALLOWED_SPLITS:
            print(f"  ALLOWED {family}: {', '.join(sorted(versions))}"
                  f" -- {ALLOWED_SPLITS[family]}")
            continue
        lines = [f"{family} wears {len(versions)} versions on one page:"]
        for version, where in sorted(versions.items()):
            for table, backend in sorted(where, key=lambda w: (str(w[0]), w[1])):
                lines.append(f"      {version:12} {backend:34} table {table}")
        failures.append("\n".join(lines))
    return failures


# Where the payloads live, so the gate can run with no arguments the way
# refresh_web_page.py invokes every other gate.
_HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(_HERE, "results", "web_benchmarks.json")
# TWO PAYLOADS REACH THE PREVIEW ROUTE, and they are not the same file. A
# skeleton publish (DECISIONS #86) exports web_benchmarks_skeleton.json; the
# October campaign (DECISIONS #84, BENCH_INSTRUMENT=2026-10) exports
# web_benchmarks_next.json. Both land on /projects/arcadedb/next, so
# --preview alone does not say which, and the env switch does. Naming only the
# skeleton here would have this gate report "no payload at
# .../web_benchmarks_skeleton.json; nothing to check" and RETURN 0 on every
# October publish: a gate that passes by not running is worse than one that
# fails, because the publish reads it as agreement.
PREVIEW = os.path.join(_HERE, "results", "web_benchmarks_skeleton.json")
PREVIEW_OCT = os.path.join(_HERE, "results", "web_benchmarks_next.json")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--preview"]
    if not args:
        # Default to the payload this publish is about, like page_check.
        preview = (PREVIEW_OCT if os.environ.get("BENCH_INSTRUMENT") == "2026-10"
                   and os.environ.get("BENCH_SKELETON") != "1" else PREVIEW)
        want = preview if "--preview" in argv[1:] else LIVE
        if not os.path.exists(want):
            print(f"  no payload at {want}; nothing to check")
            return 0
        args = [want]
    bad = 0
    for path in args:
        print(f"== {path}")
        failures = check(path)
        for failure in failures:
            print(f"  FAIL {failure}")
        if failures:
            bad = 1
        else:
            print("  ok: every engine family wears one version")
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv))
