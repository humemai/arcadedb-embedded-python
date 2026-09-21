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

The default mode checks that the four files a human edits cannot disagree
with each other. That is half the problem, and it was NOT the half that cost
machine time: the files agreed perfectly while mini's `dbbench:pg-age` sat
three PostgreSQL majors behind them, because nothing compared a pin to the
artifact that pin was supposed to have produced.

`--runtime` closes that. It runs each `dbbench:*` image that exists locally
and reads the versions back out of it, so a stale image is caught BEFORE the
cells rather than by an `engine_version` field days later. The stages' own
check was existence-only -- "images present: client mongo-search pg-age" is
true of an image built in September for an October pin. AGE 1.7.0 builds
edges 65x slower than 1.8.0, so that gap was worth two hours a cell (F90),
and a check that can only run after the run is an autopsy, not a guard.

COMPARATORS.md truncates digests for readability (8 or 12 hex), so the
comparison is by prefix, and a prefix that matches more than one full digest
is itself reported: an ambiguous pin documents nothing.

Usage:  python version_pin_check.py            # files agree with each other
        python version_pin_check.py --runtime  # ... and the images agree too
"""
import os
import re
import subprocess  # nosec B404
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


_PKGS_BLOCK = re.compile(r"declare -A PKGS=\((.*?)^\)", re.S | re.M)
_PKGS_ENTRY = re.compile(r'^\s*\[([a-z0-9-]+)\]="([^"]*)"', re.M)
_PG_MAJOR = re.compile(r"postgresql-(\d+)-age")


def _pkg_targets(build_images_text):
    """{image target: {distribution: pinned version}} from build_images.sh.

    Only `name==version` entries resolve. `[arcadedb]="$ARCADE_PKGS"` is a
    shell variable and several packages are deliberately unpinned, so the
    caller is told how many entries could not be resolved rather than being
    left to read an empty dict as a pass.
    """
    block = _PKGS_BLOCK.search(build_images_text)
    if not block:
        return {}, ["build_images.sh has no `declare -A PKGS=(` block to read"]
    out, unresolved = {}, []
    for m in _PKGS_ENTRY.finditer(block.group(1)):
        target, spec = m.group(1), m.group(2)
        pins = {p.group(1).lower(): p.group(2) for p in _PKG.finditer(spec)}
        out[target] = pins
        if not pins:
            unresolved.append(f"PKGS[{target}] pins no explicit version "
                              f"({spec.strip() or 'empty'}); nothing to check at runtime")
    return out, unresolved


def _docker(args, timeout=120):
    try:
        r = subprocess.run(["docker"] + args, capture_output=True,  # nosec B603 B607
                           text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip().splitlines()[-1:] or ["failed"]
    return r.stdout, None


def _local_images():
    out, err = _docker(["images", "--format", "{{.Repository}}:{{.Tag}}"])
    if out is None:
        return None
    return {ln.split(":", 1)[1] for ln in out.splitlines() if ln.startswith("dbbench:")}


def _installed(target, dists):
    """Ask the image itself what it has. Returns {dist: version-or-ABSENT}."""
    probe = ("import importlib.metadata as m\n"
             "for p in %r:\n"
             "    try: print(p, m.version(p))\n"
             "    except Exception: print(p, 'ABSENT')\n" % (sorted(dists),))
    out, err = _docker(["run", "--rm", "--entrypoint", "python3",
                        f"dbbench:{target}", "-c", probe])
    if out is None:
        return None, err
    got = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            got[parts[0].lower()] = parts[1]
    return got, None


def check_runtime(code):
    """Every local dbbench:* image carries the versions its pins name."""
    bad, notes = [], []
    targets, unresolved = _pkg_targets(code.get("build_images.sh", ""))
    notes.extend(unresolved)

    present = _local_images()
    if present is None:
        print("  docker is not available here; runtime check skipped entirely")
        return ["--runtime asked for, and no image could be read; that is not a pass"]

    checked = 0
    for target in sorted(targets):
        pins = targets[target]
        if target not in present:
            # A MISSING IMAGE IS NOT A PASS. qOD ran two arms whose images
            # nobody built, and the cells recorded `server_not_ready`, which
            # reads like a slow engine rather than an absent one (F76).
            notes.append(f"dbbench:{target} is not built on this host; "
                         f"a stage naming it would run against nothing")
            continue
        if not pins:
            continue
        got, err = _installed(target, pins)
        if got is None:
            bad.append(f"dbbench:{target} could not be read ({err}); an image that "
                       f"cannot state its versions cannot be trusted to have them")
            continue
        for dist, want in sorted(pins.items()):
            have = got.get(dist, "ABSENT")
            checked += 1
            if have != want:
                bad.append(f"dbbench:{target} carries {dist} {have}, pinned at {want} "
                           f"in build_images.sh -- the image predates the pin")

    # dbbench:pg-age's pin is a Dockerfile apt package, not a PKGS line, and it
    # is the one that actually went stale, so it gets its own probe.
    dockerfile = code.get("Dockerfile.pgage", "")
    want_major = _PG_MAJOR.search(dockerfile)
    if want_major and "pg-age" in present:
        out, err = _docker(["run", "--rm", "--entrypoint", "sh", "dbbench:pg-age",
                            "-c", "postgres --version; dpkg-query -W -f='${Package}\n' "
                                  "'postgresql-*-age' 2>/dev/null"])
        if out is None:
            bad.append(f"dbbench:pg-age could not be read ({err})")
        else:
            checked += 1
            got_major = re.search(r"PostgreSQL\)?\s+(\d+)", out)
            if not got_major:
                bad.append(f"dbbench:pg-age did not report a PostgreSQL version: {out!r}")
            elif got_major.group(1) != want_major.group(1):
                bad.append(f"dbbench:pg-age runs PostgreSQL {got_major.group(1)}, "
                           f"Dockerfile.pgage pins {want_major.group(1)} -- this is the "
                           f"shape of F90, where AGE 1.7.0 built edges 65x slower than "
                           f"1.8.0 and censored a two-hour cell")
    elif want_major:
        notes.append("dbbench:pg-age is not built on this host")

    print(f"{checked} runtime version(s) read out of the images themselves")
    for line in notes:
        print(f"  NOTE     {line}")
    return bad


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
    if "--runtime" in sys.argv:
        bad.extend(check_runtime(code))

    # EVERY FINDING GETS PRINTED. The first version of the runtime half
    # appended to `bad` after this loop, so its findings were counted in the
    # total and never shown: "3 pin disagreement(s)" over one visible line.
    # A gate that reports a number an operator cannot act on is half a gate.
    for line in bad:
        print(f"  DISAGREE {line}")

    print(f"\n{len(bad)} pin disagreement(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
