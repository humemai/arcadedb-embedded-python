#!/usr/bin/env python3
"""Refuse an ArcadeDB bindings wheel whose insert_many materialises the whole input.

The 26.10.1 wheel's insert_many turned one input into one JSON text and parsed it into one Java array, so a large time-series
document load held the whole input in memory and the kernel killed l4/ts1000/arcadedb_ts_doc (2026-10-08). #294/#295 chunked it,
first shipped in 26.10.2: a chunked wheel has `_INSERT_MANY_CHUNK` in its core.py (`arcadedb/core.py` in the `arcadedb` and `arcadedb-jvm`
wheels, `arcadedb_embedded/core.py` in the older one). Rows measured on a wheel without
it are a memory artefact, not the engine's number, so no benchmark image may carry one.

Usage: wheel_guard.py WHEEL     exit 0 when chunked, 1 with the reason and the fix when not (or when the file is no wheel).
"""
import sys
import zipfile

MARKER = "_INSERT_MANY_CHUNK"
CORES = ("arcadedb/core.py", "arcadedb_embedded/core.py")     # new package name first, as _arcadedb_import.py
FIX = "use a 26.10.2 or newer arcadedb, arcadedb-jvm or arcadedb_embedded wheel (the first to ship the chunked insert_many, #294/#295)"


def check(wheel):
    """Return None when the wheel's core.py has the chunking marker, else the reason it is refused."""
    try:
        with zipfile.ZipFile(wheel) as z:
            names = z.namelist()
            core = next((c for c in CORES if c in names), None)
            if core is None:
                return f"{wheel} has none of {', '.join(CORES)}, so it is not an ArcadeDB bindings wheel"
            if MARKER in z.read(core).decode("utf-8", "replace"):
                return None
    except (zipfile.BadZipFile, OSError) as e:
        return f"{wheel} cannot be opened as a wheel ({e})"
    return f"{wheel} has no {MARKER} in {core}: its insert_many materialises the whole input (pre-26.10.2)"


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    reason = check(argv[1])
    if reason:
        print(f"REFUSING: {reason}.\n          Fix: {FIX}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
