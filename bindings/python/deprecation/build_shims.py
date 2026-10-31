#!/usr/bin/env python3
# Copyright © 2021-present Arcade Data Ltd (info@arcadedata.com)
# SPDX-License-Identifier: Apache-2.0
"""Build the deprecation shim of ``arcadedb-embedded`` with ``uv build``.

This builds only. It never uploads: publishing is a separate, deliberate step (README.md here).

Where each old name points is set in ``TARGETS`` below, and nowhere else. Before it builds, this script checks that each shim's ``pyproject.toml`` and ``__init__.py`` files agree with ``TARGETS``, so a changed target cannot ship half-changed.

Each shim is copied to a scratch directory first, together with the repository's LICENSE, so the
license file ships in the wheel and the sdist and the source tree stays clean. The version in the
shim's pyproject.toml must pass ``scripts/check_version.py`` (syntax and counting rule).

usage:
    build_shims.py [--out DIR] [--shim NAME ...] [--check-pypi]

    --out DIR      where the wheels and sdists go (default: dist/ next to this script, git-ignored)
    --shim NAME    build only this shim (repeatable; default: all of them, which is one)
    --check-pypi   also run check_version.py against the live PyPI project (needs the network, and
                   fails once that version has been published, as the counting rule says)
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess  # nosec B404 - runs `uv build` with a fixed argument list
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
# There is one shim. `arcadedb-embedded-native` (the native preview package) gets none: its PyPI project has no files and is archived.
SHIMS = ("arcadedb-embedded",)


class Target(NamedTuple):
    """The package an old name points to."""

    dist: str  # the PyPI distribution the shim depends on and tells people to install
    module: str  # the import name that distribution provides: what the shim re-exports


# Where each old name points (the packaging layout v3 decided on 2026-10-25, see ArcadeData/arcadedb-python .notes/MIGRATION.md).
# arcadedb-embedded (the old JVM package) -> `arcadedb`, which is the NATIVE build. The runtime therefore changes for pip users of the old name, and the warning, the README and MIGRATION.md say so in plain words and name `arcadedb-jvm` as the way to keep the JVM build.
# This shim publishes only after the native `arcadedb` 26.11.1 FINAL exists, because it pins `arcadedb==26.11.1` and a `26.11.1.devN` release does not satisfy that pin.
# ASSUMPTION: `arcadedb` provides the import name `arcadedb`. The native wheel does (packages.find and package-data in native/wheel/pyproject.toml on the branch named below), and `arcadedb-jvm` imports as `arcadedb` too, but `arcadedb` has no final release on PyPI yet (0.0.1 is a placeholder), so the published wheel cannot be checked here.
# If the package gets another import name, change it here and in the `_NEW_MODULE` constant of the shim's `__init__.py`; check_target() fails until both agree.
IMPORT_NAME = "arcadedb"
TARGETS = {
    "arcadedb-embedded": Target(dist="arcadedb", module=IMPORT_NAME),
}
# The JVM build the warning and the README name for people who need it (not a dependency of the shim).
JVM_DIST = "arcadedb-jvm"
# The extras of the real `arcadedb` (native) distribution, and nothing else may be forwarded to. Source: ArcadeData/arcadedb-python, branch native-two-dist (commit 56aab39), file native/wheel/pyproject.toml, [project.optional-dependencies]. The root pyproject.toml of that repo builds `arcadedb-jvm` instead (extras test, dev, vector, arrow, pandas, polars, examples) and is NOT the source.
NATIVE_EXTRAS = frozenset({"numpy", "arrow", "pandas", "polars"})
# The extras people installed from the old name -> the extra of `arcadedb` they are forwarded to (the old `vector` extra was numpy; `arcadedb` has no `vector`). The old test, dev and examples extras are not forwarded: `arcadedb` does not define them.
EXTRAS = {"vector": "numpy", "arrow": "arrow", "pandas": "pandas", "polars": "polars"}


def _load_check_version():
    path = HERE.parent / "scripts" / "check_version.py"
    spec = importlib.util.spec_from_file_location("check_version", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_version"] = module
    spec.loader.exec_module(module)
    return module


def shim_version(shim: str) -> str:
    """The version in the shim's pyproject.toml."""
    with open(HERE / shim / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def check_target(shim: str) -> None:
    """Fail unless the shim's metadata and import constants all point at TARGETS[shim]."""
    target = TARGETS[shim]
    version = shim_version(shim)
    with open(HERE / shim / "pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)["project"]
    expected = {
        "name": shim,
        "description": f"Deprecated: {shim} has moved to {target.dist} (import {target.module}), now the native build, not the JVM build; for the JVM build use {JVM_DIST}. Last release, a thin shim.",
        "dependencies": [f"{target.dist}=={version}"],
        "optional-dependencies": {
            old: [f"{target.dist}[{new}]=={version}"] for old, new in EXTRAS.items()
        },
    }
    problems = [
        f"project.{key} is {project.get(key)!r}, expected {want!r}"
        for key, want in expected.items()
        if project.get(key) != want
    ]
    forwarded = {
        match.group(1)
        for requirements in project.get("optional-dependencies", {}).values()
        for requirement in requirements
        if (
            match := re.fullmatch(
                rf"{re.escape(target.dist)}\[(\w+)\]==.+", requirement
            )
        )
    }
    if forwarded != NATIVE_EXTRAS or set(EXTRAS.values()) != NATIVE_EXTRAS:
        problems.append(
            f"the shim forwards the extras {sorted(forwarded)} (EXTRAS: {sorted(set(EXTRAS.values()))}), but {target.dist} defines {sorted(NATIVE_EXTRAS)} (NATIVE_EXTRAS)"
        )
    replaced_by = project["urls"].get("Replaced by")
    if replaced_by != f"https://pypi.org/project/{target.dist}/":
        problems.append(f"project.urls['Replaced by'] is {replaced_by!r}")
    for path in sorted((HERE / shim / "src").glob("*/__init__.py")):
        text = path.read_text(encoding="utf-8")
        for name, want in (
            ("_OLD_DIST", shim),
            ("_NEW_DIST", target.dist),
            ("_NEW_MODULE", target.module),
        ):
            if f'{name} = "{want}"\n' not in text:
                problems.append(f'{path.relative_to(HERE)}: {name} is not "{want}"')
        if f"`pip install {JVM_DIST}`" not in text:
            problems.append(
                f"{path.relative_to(HERE)}: the warning does not name `pip install {JVM_DIST}`"
            )
    if problems:
        raise SystemExit(
            f"{shim} does not point at {target.dist}:\n  " + "\n  ".join(problems)
        )


def check_version(shim: str, check_pypi: bool) -> None:
    """Fail unless the shim's version follows the counting rule (and is the next one on PyPI)."""
    cv = _load_check_version()
    version = shim_version(shim)
    argv = [version]
    if check_pypi:
        argv += ["--pypi", shim]
    if cv.main(argv) != 0:
        raise SystemExit(f"{shim} {version} does not pass check_version.py")


def build(shim: str, out_dir: Path) -> list[Path]:
    """Build one shim into out_dir and return the files it produced."""
    # `uv run` exports its own path as UV; a uv-made test environment (Windows CI) may not have uv on PATH.
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required (https://docs.astral.sh/uv/)")
    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.iterdir())
    with tempfile.TemporaryDirectory(prefix=f"{shim}-") as scratch:
        stage = Path(scratch) / shim
        shutil.copytree(
            HERE / shim, stage, ignore=shutil.ignore_patterns("__pycache__", "dist")
        )
        shutil.copyfile(REPO_ROOT / "LICENSE", stage / "LICENSE")
        subprocess.run(  # nosec B603 - fixed argument list, no shell
            [uv, "build", "--out-dir", str(out_dir), str(stage)], check=True
        )
    made = set(out_dir.iterdir()) - before
    return sorted(p for p in made if p.suffix == ".whl" or p.name.endswith(".tar.gz"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=HERE / "dist")
    parser.add_argument("--shim", action="append", choices=SHIMS)
    parser.add_argument("--check-pypi", action="store_true")
    args = parser.parse_args(argv)

    shims = args.shim or list(SHIMS)
    for shim in shims:
        check_target(shim)
        check_version(shim, args.check_pypi)
    for shim in shims:
        for artifact in build(shim, args.out):
            print(f"built {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
