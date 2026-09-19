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
import re
import sys
from collections import defaultdict

# Families whose arms appear under several backend labels and must agree. A
# family is a substring matched case-insensitively inside the version string.
FAMILIES = ("arcadedb", "duckdb", "postgres", "neo4j", "mongo", "surrealdb",
            "arangodb", "qdrant", "milvus", "sqlite", "chroma", "lancedb",
            "memgraph", "falkordb", "timescaledb", "questdb", "elasticsearch")

# Deliberate splits: family -> why more than one version is correct here. Empty
# by design. An entry is a decision, not a way to quiet the gate.
ALLOWED_SPLITS: dict[str, str] = {}

_VER = r"[ :=v]*([0-9]+(?:\.[0-9]+)+)"

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


def check(path: str) -> list[str]:
    payload = json.load(open(path))
    seen: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for table, backend, version in _rows(payload):
        low = version.lower()
        for family in FAMILIES:
            for match in re.finditer(re.escape(family) + _VER, low):
                seen[family][match.group(1)].add((table, backend))

    failures = []

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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    bad = 0
    for path in argv[1:]:
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
