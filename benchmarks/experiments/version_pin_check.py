#!/usr/bin/env python3
"""Every version pin says the same thing in every file that states one.

THE PINS LIVE IN FIVE PLACES AND NOTHING CHECKED THEY AGREE. Image digests
are in `runner.py` (BACKENDS) and the two Dockerfiles; client library
versions are in `build_images.sh` (PKGS); and COMPARATORS.md states both for
a reader. That is 86 pins with no cross-check, and the failure mode is not
theoretical: on 2026-09-21 `dbbench:pg-age` was running PostgreSQL 17.11
while the re-pin had moved it to 18.6, and the only evidence was a row's own
`engine_version` field days into the campaign (BUGS F76).

What this refuses:

  a digest used in code that COMPARATORS.md does not state
  a digest stated in COMPARATORS.md that no code uses
  a package pinned in build_images.sh at a version COMPARATORS.md contradicts

It does NOT check the running artifact -- that is what the stage's image
verification and the row's `engine_version` do. This checks that the four
files a human edits cannot disagree with each other, which is the half that
was unguarded.

COMPARATORS.md truncates digests for readability (8 or 12 hex), so the
comparison is by prefix, and a prefix that matches more than one full digest
is itself reported: an ambiguous pin documents nothing.

Usage:  python version_pin_check.py        # exit 1 on any disagreement
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_FILES = ["runner.py", "build_images.sh", "Dockerfile.pgage", "Dockerfile.mongosearch"]
DOC = "COMPARATORS.md"
_DIGEST = re.compile(r"sha256:([0-9a-f]{8,64})")
# `name==1.2.3` in a PKGS line or in the doc's prose
_PKG = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*)==([0-9][A-Za-z0-9_.+-]*)")


def _strip_history(doc):
    """The re-pin section's From/To table states OLD versions on purpose.

    "| Qdrant client | `qdrant-client==1.19.0` | `1.19.1` |" is a record of a
    move, not a claim about what runs now, and reading it as one produced
    three false disagreements the first time this ran. Everything between the
    **Moved.** table and the **Unmoved** prose is history; the per-engine
    table above it and the prose below it both state the CURRENT pin and are
    kept.
    """
    start = doc.find("**Moved.**")
    if start < 0:
        return doc
    end = doc.find("**Unmoved", start)
    return doc[:start] + (doc[end:] if end > 0 else "")


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def _digests(text):
    return {m.group(1) for m in _DIGEST.finditer(text)}


def main() -> int:
    code = {f: _read(f) for f in CODE_FILES if os.path.isfile(os.path.join(HERE, f))}
    doc = _strip_history(_read(DOC))
    code_digests = set()
    for text in code.values():
        code_digests |= _digests(text)
    # full digests only; a truncated one in code would be a different bug
    code_full = {d for d in code_digests if len(d) == 64}
    doc_digests = _digests(doc)

    bad = []

    # THE CHECK IS DIRECTIONAL. Every digest the code USES must be documented;
    # the reverse is not a defect, because the doc legitimately discusses
    # digests we do not run -- a tag whose amd64 digest moved upstream "while
    # the pin holds", and the retired-pins table. Both appeared as findings on
    # the first run and neither was one.
    for short in sorted(doc_digests):
        hits = [d for d in code_full if d.startswith(short)]
        if len(hits) > 1:
            bad.append(f"COMPARATORS.md's sha256:{short}… matches {len(hits)} different "
                       f"pins; truncate to more characters, an ambiguous digest "
                       f"documents nothing")

    for full in sorted(code_full):
        if not any(full.startswith(s) for s in doc_digests):
            where = ", ".join(sorted(f for f, t in code.items() if full in t))
            bad.append(f"{where} pins sha256:{full[:12]}… and COMPARATORS.md states no "
                       f"digest with that prefix; a comparator moved without the page's "
                       f"own record of it moving")

    # client library pins: build_images.sh is the source, the doc must agree
    doc_pkgs = {}
    for m in _PKG.finditer(doc):
        doc_pkgs.setdefault(m.group(1).lower(), set()).add(m.group(2))
    for m in _PKG.finditer(code.get("build_images.sh", "")):
        name, ver = m.group(1).lower(), m.group(2)
        stated = doc_pkgs.get(name)
        if stated and ver not in stated:
            bad.append(f"build_images.sh pins {name}=={ver}; COMPARATORS.md says "
                       f"{sorted(stated)} -- one of them is stale")

    print(f"{len(code_full)} image digest(s) in code, {len(doc_digests)} stated in "
          f"{DOC}, {sum(len(v) for v in doc_pkgs.values())} package pin(s) stated")
    for line in bad:
        print(f"  DISAGREE {line}")
    print(f"\n{len(bad)} pin disagreement(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
