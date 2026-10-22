#!/usr/bin/env python3
"""Fail a wheel that contains the Studio jar or an ApexCharts file.

Studio bundles ApexCharts, which has not been open source since 5.1.0 (Community/Commercial licence; Studio has
shipped it since upstream 26.1.1). This package is Apache-2.0 and ships nothing that is not open source, so the wheels
leave the Studio jar out (`arcadedb-studio-*.jar` in scripts/jar_exclusions.txt). This check is the guard behind that
line: it fails when a Studio jar, any file named like ApexCharts, or a jar that carries ApexCharts files appears in a wheel,
whatever the cause (a removed exclusion, a shaded or renamed jar, a JAR directory that brings its own copy).
See https://github.com/ArcadeData/arcadedb/issues/10579.

Usage:
    python verify_wheel_no_studio.py WHEEL [WHEEL ...]

Exit status: 0 all wheels clean, 1 a wheel contains Studio or ApexCharts, 2 usage error or not a wheel.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ISSUE_URL = "https://github.com/ArcadeData/arcadedb/issues/10579"


def _is_studio_jar(name: str) -> bool:
    base = name.rsplit("/", 1)[-1].lower()
    return base.startswith("arcadedb-studio") and base.endswith(".jar")


def _is_apexcharts(name: str) -> bool:
    return "apexcharts" in name.lower()


def find_offenders(wheel: Path) -> list[str]:
    """Names inside the wheel (and inside its jars) that are Studio or ApexCharts."""
    offenders: list[str] = []
    with zipfile.ZipFile(wheel) as zf:
        for info in zf.infolist():
            name = info.filename
            if _is_studio_jar(name):
                offenders.append(f"{name} (Studio jar)")
            elif _is_apexcharts(name):
                offenders.append(f"{name} (ApexCharts file)")
            elif name.lower().endswith(".jar"):
                try:
                    inner = zipfile.ZipFile(io.BytesIO(zf.read(info)))
                except zipfile.BadZipFile:
                    offenders.append(
                        f"{name} (jar that is not a zip file: cannot be checked)"
                    )
                    continue
                hits = [n for n in inner.namelist() if _is_apexcharts(n)]
                if hits:
                    offenders.append(
                        f"{name} contains ApexCharts files, for example {hits[0]}"
                    )
    return offenders


def main(argv: list[str] | None = None) -> int:
    wheels = [Path(a) for a in (sys.argv[1:] if argv is None else argv)]
    if not wheels:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: verify_wheel_no_studio.py WHEEL [WHEEL ...]", file=sys.stderr)
        return 2
    status = 0
    for wheel in wheels:
        if not wheel.is_file() or not zipfile.is_zipfile(wheel):
            print(f"ERROR: {wheel} is not a wheel file", file=sys.stderr)
            return 2
        offenders = find_offenders(wheel)
        if offenders:
            status = 1
            print(
                f"ERROR: {wheel.name} contains Studio or ApexCharts, which is not open source:",
                file=sys.stderr,
            )
            for entry in offenders:
                print(f"   {entry}", file=sys.stderr)
            print(
                f"   Keep `arcadedb-studio-*.jar` in scripts/jar_exclusions.txt. Do not publish this wheel. {ISSUE_URL}",
                file=sys.stderr,
            )
        else:
            print(f"OK: {wheel.name} has no Studio jar and no ApexCharts file")
    return status


if __name__ == "__main__":
    sys.exit(main())
