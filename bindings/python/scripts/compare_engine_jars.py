#!/usr/bin/env python3
"""Compare two ArcadeDB lib directories: an image's and a source build's.

The release gate (.github/workflows/verify-engine-jars.yml) runs this on the
jars of ``arcadedata/arcadedb:<version>`` (the jars a release ships) and on a
build of the release commit from source (``build-engine-jars.yml``, with the
shaded HA jar kept, as in the image). The release publishes only when the two
hold the same code:

- the same jar names;
- every third-party jar byte-identical as a file;
- every ArcadeDB jar (``arcadedb-*``) holding the same entry names, each with
  byte-identical content, except ``com/arcadedb/arcadedb.properties``, where
  only the ``buildNumber``, ``timestamp``, and ``branch`` lines may differ.

Zip metadata (timestamps, compression) is not compared, since a rebuild of the
same source always changes it. Anything else that differs fails the check.

Evidence that this holds for a real release: a CI build of the official 26.9.1
release commit (b6a92623554b) against ``arcadedata/arcadedb:26.9.1`` matched in
all 86 jar names, all 69 third-party jars, and all 75,699 ArcadeDB classes; only
``arcadedb.properties`` differed, in exactly those three lines.

Usage:
    compare_engine_jars.py IMAGE_LIB SOURCE_LIB [--summary FILE]

Exit status: 0 when the two match as described, 1 on any other difference,
2 on a usage error. ``--summary`` appends a Markdown summary to FILE (for
``$GITHUB_STEP_SUMMARY``).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from dataclasses import dataclass, field

PROPERTIES = "com/arcadedb/arcadedb.properties"
STAMP_KEYS = ("buildNumber", "timestamp", "branch")
MAX_LISTED = 20  # differences printed per kind; the counts are always complete


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def properties_key(line: bytes) -> str | None:
    text = line.strip()
    if not text or text[:1] in (b"#", b"!"):
        return None
    for i, ch in enumerate(text):
        if ch in b"=: \t\f":
            return text[:i].decode("latin-1")
    return text.decode("latin-1")


def properties_value(data: bytes, key: str) -> str | None:
    for line in data.splitlines():
        if properties_key(line) == key:
            text = line.strip()[len(key) :].lstrip()
            if text[:1] in (b"=", b":"):
                text = text[1:]
            return text.strip().decode("latin-1")
    return None


def without_stamp(data: bytes) -> bytes:
    return b"".join(
        line
        for line in data.splitlines(keepends=True)
        if properties_key(line) not in STAMP_KEYS
    )


def entries(path: str) -> tuple[dict[str, tuple[str, ...]], dict[str, bytes]]:
    """Entry name -> sorted content digests (a zip can repeat a name), and the
    raw bytes of arcadedb.properties when present."""
    digests: dict[str, list[str]] = {}
    raw: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            data = zf.read(info)
            digests.setdefault(info.filename, []).append(
                hashlib.sha256(data).hexdigest()
            )
            if info.filename == PROPERTIES:
                raw[info.filename] = data
    return {k: tuple(sorted(v)) for k, v in digests.items()}, raw


@dataclass
class Report:
    jars_image: int = 0
    jars_source: int = 0
    only_image: list[str] = field(default_factory=list)
    only_source: list[str] = field(default_factory=list)
    third_party: int = 0
    third_party_same: int = 0
    third_party_differ: list[str] = field(default_factory=list)
    arcadedb_jars: int = 0
    classes: int = 0
    classes_same: int = 0
    other_entries: int = 0
    other_same: int = 0
    stamp_only: list[str] = field(default_factory=list)  # "<jar>: key, key"
    problems: list[str] = field(default_factory=list)
    build_number_image: str | None = None
    build_number_source: str | None = None

    @property
    def ok(self) -> bool:
        return not (
            self.only_image
            or self.only_source
            or self.third_party_differ
            or self.problems
        )


def compare(image_lib: str, source_lib: str) -> Report:
    r = Report()
    a = {f for f in os.listdir(image_lib) if f.endswith(".jar")}
    b = {f for f in os.listdir(source_lib) if f.endswith(".jar")}
    r.jars_image, r.jars_source = len(a), len(b)
    r.only_image, r.only_source = sorted(a - b), sorted(b - a)

    for name in sorted(a & b):
        pa, pb = os.path.join(image_lib, name), os.path.join(source_lib, name)
        if not name.startswith("arcadedb-"):
            r.third_party += 1
            if file_sha256(pa) == file_sha256(pb):
                r.third_party_same += 1
            else:
                r.third_party_differ.append(name)
            continue

        r.arcadedb_jars += 1
        ea, raw_a = entries(pa)
        eb, raw_b = entries(pb)
        for entry in sorted(set(ea) - set(eb)):
            r.problems.append(f"{name}: entry only in the image: {entry}")
        for entry in sorted(set(eb) - set(ea)):
            r.problems.append(f"{name}: entry only in the source build: {entry}")
        for entry in sorted(set(ea) & set(eb)):
            is_class = entry.endswith(".class")
            if is_class:
                r.classes += 1
            else:
                r.other_entries += 1
            if ea[entry] == eb[entry]:
                if is_class:
                    r.classes_same += 1
                else:
                    r.other_same += 1
                continue
            if entry == PROPERTIES:
                da, db = raw_a[entry], raw_b[entry]
                if without_stamp(da) == without_stamp(db):
                    changed = [
                        k
                        for k in STAMP_KEYS
                        if properties_value(da, k) != properties_value(db, k)
                    ]
                    r.stamp_only.append(f"{name}: {', '.join(changed)}")
                    r.other_same += 1  # the same content, less the build stamp
                else:
                    r.problems.append(
                        f"{name}: {entry} differs beyond the {', '.join(STAMP_KEYS)} lines"
                    )
                continue
            r.problems.append(f"{name}: {entry} differs")

        if name.startswith("arcadedb-engine-"):
            r.build_number_image = properties_value(
                raw_a.get(PROPERTIES, b""), "buildNumber"
            )
            r.build_number_source = properties_value(
                raw_b.get(PROPERTIES, b""), "buildNumber"
            )
    return r


def render(r: Report, image_label: str, source_label: str) -> list[str]:
    def listed(items: list[str]) -> str:
        shown = items[:MAX_LISTED]
        more = (
            f" (and {len(items) - MAX_LISTED} more)" if len(items) > MAX_LISTED else ""
        )
        return ", ".join(shown) + more

    lines = [
        f"image:        {image_label} (buildNumber {r.build_number_image})",
        f"source build: {source_label} (buildNumber {r.build_number_source})",
        f"jar names: {r.jars_image} in the image, {r.jars_source} in the source build, "
        f"{len(r.only_image)} only in the image, {len(r.only_source)} only in the source build",
        f"third-party jars byte-identical: {r.third_party_same} of {r.third_party}",
        f"ArcadeDB jars: {r.arcadedb_jars}; classes byte-identical: "
        f"{r.classes_same} of {r.classes}; other entries identical: "
        f"{r.other_same} of {r.other_entries}",
    ]
    if r.stamp_only:
        lines.append(f"build stamp only ({PROPERTIES}): " + "; ".join(r.stamp_only))
    if r.only_image:
        lines.append(f"ONLY IN THE IMAGE: {listed(r.only_image)}")
    if r.only_source:
        lines.append(f"ONLY IN THE SOURCE BUILD: {listed(r.only_source)}")
    if r.third_party_differ:
        lines.append(f"THIRD-PARTY JARS THAT DIFFER: {listed(r.third_party_differ)}")
    if r.problems:
        lines.append(f"ARCADEDB DIFFERENCES ({len(r.problems)}):")
        lines.extend(f"  {p}" for p in r.problems[:MAX_LISTED])
        if len(r.problems) > MAX_LISTED:
            lines.append(f"  (and {len(r.problems) - MAX_LISTED} more)")
    lines.append(
        "RESULT: MATCH (same code; only the build stamp differs)"
        if r.ok
        else "RESULT: MISMATCH"
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("image_lib", help="lib directory copied out of the image")
    parser.add_argument("source_lib", help="lib directory of the source build")
    parser.add_argument("--image-label", default=None, help="name for the image side")
    parser.add_argument("--source-label", default=None, help="name for the source side")
    parser.add_argument("--summary", help="append a Markdown summary to this file")
    args = parser.parse_args(argv)

    for d in (args.image_lib, args.source_lib):
        if not os.path.isdir(d):
            print(f"not a directory: {d}", file=sys.stderr)
            return 2
    report = compare(args.image_lib, args.source_lib)
    if report.jars_image == 0 or report.jars_source == 0:
        print("a lib directory holds no jars; nothing was compared", file=sys.stderr)
        return 1

    lines = render(
        report,
        args.image_label or args.image_lib,
        args.source_label or args.source_lib,
    )
    print("\n".join(lines))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write("## Engine jars: image against source build\n\n```\n")
            fh.write("\n".join(lines))
            fh.write("\n```\n")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
