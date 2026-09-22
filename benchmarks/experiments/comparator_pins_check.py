#!/usr/bin/env python3
"""Every published comparator number must come from the version we pin today.

WHY. On 2026-08-27 the pins in build_images.sh had drifted ahead of the frozen
results without anything noticing: ladybug 0.19.1 pinned against a published
0.18.1, lancedb 0.37.1 against 0.34.0, qdrant-client 1.19.0 against 1.18.0,
pymilvus 3.0.1 against 3.0.0. A campaign re-runs every backend in the lanes it
touches, so re-run lanes silently move to the newer comparator while lanes it
does not touch keep the older one -- and the page then compares ArcadeDB against
two different Qdrants in two different tables.

Nothing checked it. fairness_check.py has no version assertion at all, and the
identifiability gate in export_web deliberately exempted comparators.

WHAT THIS DOES. Reads the pins out of build_images.sh (the file the images are
actually built from, not a copy that can drift) and compares them against the
version recorded on every published comparator row. Reports three states:

  MATCHES  the row came from the pinned version
  STALE    the row predates a pin bump; the lane needs re-running
  UNKNOWN  the row records a name or a blank where a version belongs

Exit 1 if anything is STALE or UNKNOWN, because either means the page cannot say
what it compared against.

    python3 comparator_pins_check.py
    python3 comparator_pins_check.py --frozen results/runs_paper.csv
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(HERE, "build_images.sh")
FROZEN = os.path.join(HERE, "results", "runs_paper.csv")

# backend name in results -> the pypi package whose pin governs it. A backend
# absent here is one whose version does not come from a pinned python package
# (a server image, say), and is reported rather than silently skipped.
BACKEND_PKG = {
    "ladybug_graph": "ladybug",
    "neo4j_graph": "neo4j",
    "qdrant_dense": "qdrant-client",
    "qdrant_sparse": "qdrant-client",
    "milvus_dense": "pymilvus",
    "milvus_sparse": "pymilvus",
    "chroma_dense": "chromadb",
    "lancedb_dense": "lancedb",
    "sqlite_vec_dense": "sqlite-vec",
    "duckdb_vss_dense": "duckdb",
    "duckdb": "duckdb",
    "duckpgq_graph": "duckdb",
    "elasticsearch_sparse": "elasticsearch",
    "surrealdb_e2": "surrealdb",
}


def read_pins():
    """package -> pinned version, from the file the images are built from."""
    try:
        body = open(IMAGES).read()
    except OSError as exc:
        print(f"cannot read {IMAGES}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    pins = dict(re.findall(r"([a-zA-Z0-9_.\-]+)==([0-9][0-9a-zA-Z.\-]*)", body))
    if not pins:
        print("no ==pins found in build_images.sh; the format changed and this "
              "check would pass everything", file=sys.stderr)
        raise SystemExit(2)
    return pins


def image_versions():
    """backend -> the version its PINNED IMAGE carries, where the tag names one.

    The other half of "what governs this comparator's version". A backend whose
    engine runs in a container takes its version from the image digest in
    `runner.BACKENDS`, not from a pypi pin, and comparing the two is a category
    error: `neo4j_graph` records the SERVER's 2026.07.1 while BACKEND_PKG maps
    it to the `neo4j` python DRIVER pinned at 6.3.1, so a correct row was
    reported STALE against a number that describes a different piece of
    software. Same for milvus (server 2.6.13 against pymilvus 3.0.1).

    Returns only what a tag states. A digest-only reference pins the version
    without naming it, which is checked by `version_pin_check.py` against the
    registry and is reported here as image-pinned rather than guessed at.
    """
    try:
        sys.path.insert(0, HERE)
        import runner
    except Exception as exc:  # noqa: BLE001  (a missing runner is not this check's failure)
        print(f"  (cannot import runner, so image pins are not read: {exc})")
        return {}, {}
    tags, pinned_by_image = {}, {}
    for be, spec in (runner.BACKENDS or {}).items():
        if not isinstance(spec, dict):
            continue
        ref = str(spec.get("server_image") or spec.get("image") or "")
        if not ref:
            continue
        pinned_by_image[be] = ref
        name = ref.split("@", 1)[0]
        if ":" in name:
            tag = name.rsplit(":", 1)[1]
            if re.match(r"^[0-9]", tag):
                tags[be] = tag
    return tags, pinned_by_image


def classify(recorded, pinned):
    """MATCHES / STALE / UNKNOWN for one row's recorded version."""
    v = (recorded or "").strip()
    if not v or re.fullmatch(r"[a-z_\-]+|[?]|unset|none|null", v, re.I):
        return "UNKNOWN"
    # Versions are recorded in several shapes: bare (0.34.0), prefixed
    # (ladybug:0.18.1), or compound (milvus:2.6/pymilvus:3.0.1). Any occurrence
    # of the pinned string counts, so a compound that names it still matches.
    return "MATCHES" if pinned and pinned in v else "STALE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default=FROZEN)
    args = ap.parse_args()
    pins = read_pins()
    img_tags, img_pinned = image_versions()
    rows = list(csv.DictReader(open(args.frozen)))
    seen, bad = {}, 0
    for r in rows:
        be = str(r.get("backend") or "")
        if not be or be.startswith("arcadedb"):
            continue
        rec = r.get("engine_version") or r.get("version_name") or ""
        pkg = BACKEND_PKG.get(be)
        # WHICH PIN GOVERNS THIS ROW'S VERSION. A pypi pin where the version
        # comes from a package, the image tag where it comes from a container,
        # and neither is the only real finding: a published comparator whose
        # version nothing pins.
        _ref = img_pinned.get(be, "")
        _ours = _ref.startswith("dbbench:")
        if pkg is not None and (_ours or not _ref):
            # OUR OWN IMAGE, so the version is whatever we installed into it
            # and the pypi pin is what governs. ladybug, duckdb, lancedb and
            # chroma all live here.
            state = classify(rec, pins.get(pkg))
        elif _ref and not _ours:
            # A THIRD-PARTY IMAGE PINNED BY DIGEST. What the row records is the
            # ENGINE's own version, read out of the running server, and the
            # digest is what fixes it -- resolvable only against the registry,
            # which is `version_pin_check.py`'s job and not this file's.
            #
            # Comparing it to a pypi pin is a category error and produced four
            # false STALEs: neo4j_graph's server 2026.07.1 against the `neo4j`
            # DRIVER at 6.3.1, and milvus_dense/milvus_sparse's server 2.6.13
            # against `pymilvus` 3.0.1. Those rows are correct and pinned; the
            # check was comparing two different pieces of software.
            pkg, state = "image digest", "IMAGE-PINNED"
        elif be in img_tags:
            pkg, state = f"image:{img_tags[be]}", classify(rec, img_tags[be])
        elif be in img_pinned:
            pkg, state = "image digest", "IMAGE-PINNED"
        else:
            state = "NO PIN MAPPED"
        seen.setdefault((be, pkg, rec.strip() or "(blank)", state), 0)
        seen[(be, pkg, rec.strip() or "(blank)", state)] += 1
    print(f"pins from build_images.sh: {len(pins)} packages\n")
    order = {"NO PIN MAPPED": 0, "STALE": 1, "UNKNOWN": 2, "IMAGE-PINNED": 3,
             "MATCHES": 4}
    for (be, pkg, rec, state), n in sorted(seen.items(), key=lambda kv: (order[kv[0][3]], kv[0][0])):
        want = pins.get(pkg, "-")
        print(f"  {state:<14}{be:<24}{rec[:30]:<32}pinned={want:<10}n={n}")
        if state in ("STALE", "UNKNOWN"):
            bad += n
    unpinned = sum(n for (be, pkg, rec, st), n in seen.items() if st == "NO PIN MAPPED")
    print(f"\n  {bad} published comparator rows whose recorded version disagrees "
          f"with the pin that governs it")
    if bad:
        print("  -> re-run those lanes, or record why the pin legitimately differs")
    print(f"  {unpinned} published comparator rows whose version nothing pins at all")
    if unpinned:
        print("  -> give the backend a pypi pin or a pinned image; a comparator "
              "whose version is not pinned is not reproducible")
    return 1 if (bad or unpinned) else 0


if __name__ == "__main__":
    raise SystemExit(main())
