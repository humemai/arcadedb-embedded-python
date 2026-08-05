#!/usr/bin/env python3
"""Replace the literal "server:latest" with the release the run actually used.

WHY THIS IS NEEDED. l1_tabular and l2_graph hardcoded `self.version =
"server:latest"` where l3_sparse and l3d_dense asked the server. "latest" is a
tag, not a version, and runner.py never used it: it pins the server image by
digest. So those rows named an image nobody ran.

That is not cosmetic. F5 says a table must compare one engine line, and the
check for it compares these strings. A constant makes the check vacuous, and
f8 divided a 26.8.1 embedded row by a "latest" server row across three bars
without anything objecting.

WHAT MAKES THE BACKFILL SOUND, rather than a relabelling to taste: each row
carries a `manifest` id, and the manifest records the RESOLVED digest of every
image the campaign launched. So the version is recoverable from evidence the
run already wrote down. A row is only rewritten when its manifest names an
arcadedb server image whose digest is a release we can name; anything else is
left alone and reported, because "probably 26.8.1" is exactly the guess this
whole exercise exists to stop.

Digests are pinned here rather than inferred from the tag string, so that a
mutable tag pointing somewhere new later cannot silently re-label old rows.

    python3 backfill_server_version.py             # dry run
    python3 backfill_server_version.py --apply
"""
import argparse
import collections
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
CANON = os.path.join(RESULTS, "runs.jsonl")

# digest -> the release it is. Extend deliberately, never programmatically.
KNOWN_DIGESTS = {
    "sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a":
        "26.8.1",
}

STALE = {"server:latest", "latest"}


def manifest_server_release(manifest_id, cache={}):
    """The release named by the arcadedb SERVER image in one manifest."""
    if manifest_id in cache:
        return cache[manifest_id]
    path = os.path.join(RESULTS, f"manifest-{manifest_id}.json")
    out = None
    if os.path.exists(path):
        try:
            m = json.load(open(path))
        except Exception:
            m = {}
        for name, digest in (m.get("images") or {}).items():
            # the SERVER image, not our own dbbench:arcadedb build
            if "arcadedata/arcadedb" in name:
                out = KNOWN_DIGESTS.get(str(digest))
                break
    cache[manifest_id] = out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(CANON):
        sys.exit(f"no canonical store at {CANON}")

    rows = []
    with open(CANON) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    fixed = collections.Counter()
    unresolved = collections.Counter()
    for r in rows:
        if str(r.get("engine_version")) not in STALE:
            continue
        mid = r.get("manifest")
        rel = manifest_server_release(mid) if mid else None
        key = (r.get("lane"), r.get("scale"), r.get("backend"))
        if rel:
            r["engine_version"] = f"server:{rel}"
            r["engine_version_source"] = f"manifest-{mid} digest"
            fixed[key + (rel,)] += 1
        else:
            unresolved[key + (str(mid),)] += 1

    print("RESOLVED from manifest digests:")
    for k, n in sorted(fixed.items(), key=str):
        print("  %-42s -> server:%-8s %d rows" % ("/".join(map(str, k[:3])), k[3], n))
    if not fixed:
        print("  (none)")
    if unresolved:
        print("\nLEFT ALONE, digest not recognised or manifest missing:")
        for k, n in sorted(unresolved.items(), key=str):
            print("  %-42s manifest=%s  %d rows" % ("/".join(map(str, k[:3])), k[3], n))
        print("  These rows keep their stale label deliberately. A version we "
              "cannot evidence is not one to write down.")

    if not a.apply:
        print("\ndry run. re-run with --apply to write.")
        return
    if not fixed:
        print("\nnothing to write.")
        return

    backup = CANON + ".before-version-backfill"
    shutil.copy2(CANON, backup)
    with open(CANON, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nrewrote {sum(fixed.values())} rows. backup at {os.path.basename(backup)}")


if __name__ == "__main__":
    main()
