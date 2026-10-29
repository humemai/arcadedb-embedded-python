"""_arcadedb_import: one import path for the `arcadedb` (26.11.1+) and `arcadedb_embedded` (older) packages.

The harness must run on the wheels the images carry today (`arcadedb_embedded`) and on the new ones (`arcadedb`, `arcadedb-jvm`), so
the order (new first, old as the fallback), the failure when neither exists, the native/jvm answer and the version lookup are pinned here.
Run: python -m pytest -q test_arcadedb_import.py
"""
import importlib.metadata
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _arcadedb_import as AI  # noqa: E402


def _fake(name, **attrs):
    m = types.ModuleType(name)
    m.create_database = lambda *a, **k: None
    m.DatabaseFactory = object
    for k, v in attrs.items():
        setattr(m, k, v)
    m.jvm = types.ModuleType(name + ".jvm")
    return m


@pytest.fixture
def reset(monkeypatch):
    monkeypatch.setattr(AI, "_loaded", None)

    def install(**mods):
        for n in ("arcadedb", "arcadedb.jvm", "arcadedb_embedded", "arcadedb_embedded.jvm"):
            monkeypatch.setitem(sys.modules, n, None)        # None in sys.modules makes the import raise ImportError
        for n, m in mods.items():
            monkeypatch.setitem(sys.modules, n, m)
            monkeypatch.setitem(sys.modules, n + ".jvm", m.jvm)
    return install


def test_new_name_wins_when_both_exist(reset):
    new, old = _fake("arcadedb", __backend__="jvm"), _fake("arcadedb_embedded")
    reset(arcadedb=new, arcadedb_embedded=old)
    assert AI.load() is new and AI.module_name() == "arcadedb"


def test_falls_back_to_the_old_package(reset):
    old = _fake("arcadedb_embedded")
    reset(arcadedb_embedded=old)
    assert AI.load() is old and AI.module_name() == "arcadedb_embedded"
    assert AI.backend() == "jvm"                       # the old package has no __backend__ and is always the JVM build
    assert AI.jvm_module() is old.jvm


def test_a_namespace_directory_called_arcadedb_is_not_the_engine(reset):
    empty = types.ModuleType("arcadedb")               # what an empty `arcadedb/` directory on sys.path imports as
    empty.jvm = types.ModuleType("arcadedb.jvm")
    old = _fake("arcadedb_embedded")
    reset(arcadedb_embedded=old)
    sys.modules["arcadedb"] = empty
    assert AI.load() is old


def test_neither_installed_says_what_to_install(reset):
    reset()
    with pytest.raises(ImportError, match="arcadedb-jvm"):
        AI.load()


@pytest.mark.parametrize("backend", ["native", "jvm"])
def test_backend_is_what_the_new_package_says_it_runs(reset, backend):
    reset(arcadedb=_fake("arcadedb", __backend__=backend, _DISTRIBUTION_BACKEND="jvm"))
    assert AI.backend() == backend


def test_dist_version_tries_the_new_names_first_and_keeps_the_old_failure(monkeypatch):
    have = {"arcadedb-jvm": "26.11.1.dev0"}

    def version(dist):
        if dist in have:
            return have[dist]
        raise importlib.metadata.PackageNotFoundError(dist)

    monkeypatch.setattr(importlib.metadata, "version", version)
    assert AI.dist_version() == "26.11.1.dev0"
    have.clear()
    have["arcadedb-embedded"] = "26.10.2"
    assert AI.dist_version() == "26.10.2"
    have.clear()
    with pytest.raises(importlib.metadata.PackageNotFoundError):   # callers format it as "unknown (PackageNotFoundError)"
        AI.dist_version()
