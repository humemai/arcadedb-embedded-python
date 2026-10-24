"""The JVM wheel must ship every subpackage the shared Python code imports.

``core.py``, ``server.py``, ``exporter.py`` and ``vector.py`` do ``from . import _native`` to ask which backend is
selected, in the JVM wheel too (the native wheel is built from the same sources). ``pyproject.toml`` lists the packages
by hand, so a subpackage left out of that list gives an ``ImportError`` on the first ``create_database`` in the JVM wheel.

In a source checkout the test builds the package with setuptools (no JARs, no JRE, no native library needed) and checks the
build. In the wheel's test container there is no ``setup.py``, so it checks the installed package instead.
"""

import os
import shutil
import subprocess  # nosec B404 - test-controlled child process
import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parents[1]
SOURCE = PYTHON_DIR / "src" / "arcadedb_embedded"


def _built_root(tmp_path: Path):
    """The directory that holds the built ``arcadedb_embedded``, or None to use the installed one."""
    if not (PYTHON_DIR / "setup.py").exists():
        return None
    # Build from a copy: setuptools writes an egg-info next to the sources, and a stale one lists files
    # the current pyproject.toml would not ship.
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy(PYTHON_DIR / "pyproject.toml", project)
    shutil.copy(PYTHON_DIR / "setup.py", project)
    shutil.copytree(
        SOURCE,
        project / "src" / "arcadedb_embedded",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    build_lib = tmp_path / "lib"
    subprocess.run(  # nosec B603 - fixed argv (sys.executable setup.py build_py), no shell
        [sys.executable, "setup.py", "-q", "build_py", "--build-lib", str(build_lib)],
        cwd=project,
        check=True,
    )
    return build_lib


def test_build_ships_every_subpackage(tmp_path):
    root = _built_root(tmp_path)
    if root is None:
        import arcadedb_embedded

        package = Path(arcadedb_embedded.__file__).parent
        assert (package / "_native" / "__init__.py").exists()
        return
    expected = {p.parent.name for p in SOURCE.glob("*/__init__.py")}
    built = {p.parent.name for p in (root / "arcadedb_embedded").glob("*/__init__.py")}
    assert (
        expected == built
    ), f"subpackages missing from the build: {sorted(expected - built)}"


def test_backend_selection_imports_without_native_library(tmp_path):
    """A fresh interpreter, as the wheel's ``test_install.py`` runs: the JVM backend is the default."""
    root = _built_root(tmp_path)
    env = {"PATH": os.environ["PATH"]}
    if root is not None:
        env["PYTHONPATH"] = str(root)
    code = (
        "import arcadedb_embedded.core, arcadedb_embedded._native as n;"
        "assert n.enabled() is False"
    )
    subprocess.run(  # nosec B603 - fixed argv, no shell, test-owned code string
        [sys.executable, "-c", code], check=True, cwd=tmp_path, env=env
    )
