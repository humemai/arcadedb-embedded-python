#!/usr/bin/env python3
# Copyright © 2021-present Arcade Data Ltd (info@arcadedata.com)
# SPDX-License-Identifier: Apache-2.0
"""Build the two deprecation shims (``arcadedb-embedded``, ``arcadedb-embedded-native``) with ``uv build``.

This builds only. It never uploads: publishing is a separate, deliberate step (README.md here).

Each shim is copied to a scratch directory first, together with the repository's LICENSE, so the
license file ships in the wheel and the sdist and the source tree stays clean. The version in the
shim's pyproject.toml must pass ``scripts/check_version.py`` (syntax and counting rule).

usage:
    build_shims.py [--out DIR] [--shim NAME ...] [--check-pypi]

    --out DIR      where the wheels and sdists go (default: dist/ next to this script, git-ignored)
    --shim NAME    build only this shim (repeatable; default: both)
    --check-pypi   also run check_version.py against the live PyPI project (needs the network, and
                   fails once that version has been published, as the counting rule says)
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess  # nosec B404 - runs `uv build` with a fixed argument list
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SHIMS = ("arcadedb-embedded", "arcadedb-embedded-native")


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
        check_version(shim, args.check_pypi)
    for shim in shims:
        for artifact in build(shim, args.out):
            print(f"built {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
