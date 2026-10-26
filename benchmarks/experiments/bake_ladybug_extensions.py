#!/usr/bin/env python3
"""Install LadybugDB official extensions at IMAGE BUILD time and refuse any binary that is not the pinned one.

    python bake_ladybug_extensions.py vector=<sha256> [fts=<sha256> ...]

WHY. `INSTALL vector` downloads the extension from extension.ladybugdb.com, and until 2026-10-25 every cell did it at
run time. That morning (04:28 UTC) the vendor overwrote the v0.21.0 file that every 0.21.x client reads, with a build
of the 0.22 sources; the engine we had pinned could no longer `LOAD vector` (LadybugDB/ladybug#1390). A pinned pass must
not depend on a file a vendor can replace, so build_images.sh bakes the binary into the image and pins its sha256.

`INSTALL` does nothing when the file is already under ~/.lbdb (checked: same sha256 and mtime after a second INSTALL,
also offline), so the cell's own `INSTALL vector` keeps working and keeps the baked file. This script fails the build when
(1) the downloaded file's sha256 is not the pin, or (2) `LOAD` rejects it (the 2026-10-25 failure mode: an undefined
symbol against the core), so a replaced binary stops the build instead of changing the engine under a pinned pass.
"""
import glob
import hashlib
import os
import sys


def main(argv):
    if not argv:
        sys.exit("usage: bake_ladybug_extensions.py name=sha256 [name=sha256 ...]")
    pins = {}
    for a in argv:
        name, _, want = a.partition("=")
        if not name or len(want) != 64 or any(c not in "0123456789abcdef" for c in want):
            sys.exit(f"bad pin {a!r}: expected name=<64 lowercase hex sha256>")
        pins[name] = want
    import ladybug

    cx = ladybug.Connection(ladybug.Database(":memory:"))
    for name, want in pins.items():
        cx.execute(f"INSTALL {name}")
        found = glob.glob(os.path.expanduser(f"~/.lbdb/extension/*/*/{name}/lib{name}.lbug_extension"))
        if len(found) != 1:
            sys.exit(f"INSTALL {name} left {len(found)} files under ~/.lbdb/extension, expected exactly one: {found}")
        path = found[0]
        with open(path, "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        if got != want:
            os.remove(path)
            sys.exit(
                f"REFUSING: the {name} extension downloaded for ladybug {ladybug.__version__} has sha256 {got}, "
                f"the pin is {want}. The vendor replaced the file (LadybugDB/ladybug#1390 was this). Decide whether "
                f"the new binary is the one to measure, then move the pin in build_images.sh (LADYBUG_EXTENSIONS)."
            )
        cx.execute(f"LOAD {name}")  # a binary built for another core fails here, with the undefined symbol
        print(f"baked ladybug {ladybug.__version__} extension {name} sha256 {got} -> {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
