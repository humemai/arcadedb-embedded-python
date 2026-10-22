#!/usr/bin/env python3
"""Refuse an ArcadeDB bindings wheel whose insert_many materialises the whole input.

The 26.10.1 wheel's insert_many turned one input into one JSON text and parsed it into one Java array, so a large time-series
document load held the whole input in memory and the kernel killed l4/ts1000/arcadedb_ts_doc (2026-10-08). #294/#295 chunked it,
first shipped in 26.10.2: a chunked wheel has `_INSERT_MANY_CHUNK` in arcadedb_embedded/core.py. Rows measured on a wheel without
it are a memory artefact, not the engine's number, so no benchmark image may carry one.

Usage: wheel_guard.py WHEEL     exit 0 when chunked, 1 with the reason and the fix when not (or when the file is no wheel).
"""
import sys
import zipfile

MARKER = "_INSERT_MANY_CHUNK"
CORE = "arcadedb_embedded/core.py"
FIX = "use a 26.10.2 or newer arcadedb_embedded wheel (the first to ship the chunked insert_many, #294/#295)"


def check(wheel):
    """Return None when the wheel's core.py has the chunking marker, else the reason it is refused."""
    try:
        with zipfile.ZipFile(wheel) as z:
            if CORE not in z.namelist():
                return f"{wheel} has no {CORE}, so it is not an arcadedb_embedded wheel"
            if MARKER in z.read(CORE).decode("utf-8", "replace"):
                return None
    except (zipfile.BadZipFile, OSError) as e:
        return f"{wheel} cannot be opened as a wheel ({e})"
    return f"{wheel} has no {MARKER} in {CORE}: its insert_many materialises the whole input (pre-26.10.2)"


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
