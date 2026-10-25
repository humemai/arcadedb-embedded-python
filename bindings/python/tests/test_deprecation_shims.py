"""The deprecation shims for the old PyPI names (deprecation/): built here, checked against a stub.

`arcadedb-embedded` and `arcadedb-embedded-native` get one last release, 26.11.1: a pure-Python shim that
installs the new package at the same version, warns once at import, and re-exports it. The old native package
imported as `arcadedb_native`, so its shim ships that module as well as `arcadedb_embedded`. The tests build both
shims with `uv build` (no upload), and check the wheel, the dependency pin, the warning, and attribute and
submodule access against a stub `arcadedb` module: the real package is not needed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess  # nosec B404 - test-controlled child processes, no untrusted input
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

BINDINGS = Path(__file__).resolve().parents[1]
DEPRECATION = BINDINGS / "deprecation"
VERSION = "26.11.1"
# old distribution -> the package it points to
SHIMS = {"arcadedb-embedded": "arcadedb", "arcadedb-embedded-native": "arcadedb-native"}
# What PyPI listed before the cutover (checked 2026-10-25): the counting rule is applied against this
# snapshot, because once the shims are published the live list contains 26.11.1 itself.
PUBLISHED_BEFORE_CUTOVER = {
    "arcadedb-embedded": ["26.9.1", "26.10.1", "26.10.2", "26.10.2.post1"],
    "arcadedb-embedded-native": ["26.10.2.dev0", "26.10.2.dev1"],
}
# old distribution -> the import names its shim ships (the old native package imported as arcadedb_native)
MODULES = {
    "arcadedb-embedded": ["arcadedb_embedded"],
    "arcadedb-embedded-native": ["arcadedb_embedded", "arcadedb_native"],
}
CASES = [(dist, module) for dist, modules in MODULES.items() for module in modules]
BODY_MARKER = "# ---- shared body"

STUB_FILES = {
    "arcadedb/__init__.py": """
        __version__ = "26.11.1"
        __all__ = ["Database", "open_database"]

        class Database:
            pass

        def open_database(path):
            return Database()

        _private = "p"
        from . import core  # the real package imports its submodules like this
    """,
    "arcadedb/core.py": "class Core:\n    pass\n\nVALUE = 1\n",
    # not imported by __init__: only a lazy import reaches it
    "arcadedb/extra.py": "VALUE = 42\n",
    "arcadedb/sub/__init__.py": "",
    "arcadedb/sub/deep.py": "NAME = 'deep'\n",
}

# written for arcadedb_embedded; _probe() swaps in the module name under test
PROBE = """
import json, sys, warnings
sys.path.insert(0, sys.argv[1])
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import arcadedb_embedded
    import arcadedb_embedded.core
    import arcadedb_embedded.extra
    import arcadedb_embedded.sub.deep
    from arcadedb_embedded.sub import deep
    from arcadedb_embedded.extra import VALUE
import arcadedb
out = {
    "warnings": [[w.category.__name__, str(w.message), w.filename] for w in caught],
    "same_class": arcadedb_embedded.Database is arcadedb.Database,
    "same_function": arcadedb_embedded.open_database is arcadedb.open_database,
    "version": arcadedb_embedded.__version__,
    "all": sorted(arcadedb_embedded.__all__),
    "private": arcadedb_embedded._private,
    "core_alias": arcadedb_embedded.core is arcadedb.core,
    "core_in_modules": sys.modules["arcadedb_embedded.core"] is arcadedb.core,
    "lazy_alias": arcadedb_embedded.extra is arcadedb.extra,
    "lazy_value": VALUE,
    "nested_alias": arcadedb_embedded.sub.deep is arcadedb.sub.deep and deep is arcadedb.sub.deep,
    "no_second_copy": sorted(n for n in sys.modules if n.startswith("arcadedb_embedded.")
                             and sys.modules[n].__name__.startswith("arcadedb_embedded.")),
    "spec_kept": arcadedb.extra.__spec__.name,
    "in_dir": all(n in dir(arcadedb_embedded) for n in ("Database", "core", "_private")),
}
try:
    arcadedb_embedded.missing_name
except AttributeError as err:
    out["missing_attr"] = str(err)
try:
    import arcadedb_embedded.no_such_module
except ModuleNotFoundError:
    out["missing_module"] = True
print(json.dumps(out))
"""


def _load_build_shims():
    spec = importlib.util.spec_from_file_location(
        "build_shims", DEPRECATION / "build_shims.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["build_shims"] = module
    spec.loader.exec_module(module)
    return module


def _load_check_version():
    spec = importlib.util.spec_from_file_location(
        "check_version", BINDINGS / "scripts" / "check_version.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_version"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def wheels(tmp_path_factory):
    """Build both shims once (`uv build`, no upload) and return {old distribution: wheel path}."""
    out = tmp_path_factory.mktemp("shim-dist")
    assert _load_build_shims().main(["--out", str(out)]) == 0
    built = {}
    for dist in SHIMS:
        found = list(out.glob(f"{dist.replace('-', '_')}-{VERSION}-*.whl"))
        assert len(found) == 1, f"{dist}: expected one wheel in {out}, found {found}"
        built[dist] = found[0]
    return built


@pytest.fixture(scope="module")
def sites(wheels, tmp_path_factory):
    """Per shim, a site directory holding the unpacked wheel next to the stub `arcadedb`."""
    result = {}
    for dist, wheel in wheels.items():
        site = tmp_path_factory.mktemp(f"site-{dist}")
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(site)
        for name, body in STUB_FILES.items():
            target = site / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
        result[dist] = site
    return result


def _metadata(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        return archive.read(name).decode("utf-8")


def _probe(site: Path, module: str = "arcadedb_embedded") -> dict:
    done = subprocess.run(  # nosec B603 - fixed argument list, no shell
        [
            sys.executable,
            "-I",
            "-c",
            PROBE.replace("arcadedb_embedded", module),
            str(site),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("dist", SHIMS)
def test_wheel_is_pure_python(dist, wheels):
    wheel = wheels[dist]
    assert wheel.name == f"{dist.replace('-', '_')}-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        wheel_file = archive.read(
            next(n for n in names if n.endswith(".dist-info/WHEEL"))
        ).decode("utf-8")
    assert "Root-Is-Purelib: true" in wheel_file
    assert "Tag: py3-none-any" in wheel_file
    code = [
        n
        for n in names
        if not n.startswith(f"{dist.replace('-', '_')}-{VERSION}.dist-info/")
    ]
    assert sorted(code) == [f"{m}/__init__.py" for m in MODULES[dist]], code
    assert any(n.endswith("licenses/LICENSE") for n in names)


@pytest.mark.parametrize("dist", SHIMS)
def test_dependency_pins_the_new_package_at_the_same_version(dist, wheels):
    metadata = _metadata(wheels[dist])
    new = SHIMS[dist]
    assert f"Name: {dist}\n" in metadata
    assert f"Version: {VERSION}\n" in metadata
    requires = re.findall(r"^Requires-Dist: (.+)$", metadata, flags=re.MULTILINE)
    assert f"{new}=={VERSION}" in requires
    # every requirement is an exact pin on the new package, extras forwarded, nothing else
    assert all(
        re.fullmatch(
            rf"{re.escape(new)}(\[\w+\])?=={re.escape(VERSION)}(; extra == '\w+')?", r
        )
        for r in requires
    ), requires


@pytest.mark.parametrize("dist", SHIMS)
def test_version_follows_the_counting_rule(dist):
    cv = _load_check_version()
    assert str(cv.check_next(VERSION, PUBLISHED_BEFORE_CUTOVER[dist])) == VERSION
    with pytest.raises(cv.VersionError):
        cv.check_next(VERSION, PUBLISHED_BEFORE_CUTOVER[dist] + [VERSION])
    # the build script reads the same version from pyproject.toml, and the rule's script accepts it
    build_shims = _load_build_shims()
    assert build_shims.shim_version(dist) == VERSION
    build_shims.check_version(dist, check_pypi=False)


def test_all_shim_modules_share_one_body():
    bodies = []
    for dist, module in CASES:
        text = (DEPRECATION / dist / "src" / module / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert BODY_MARKER in text
        bodies.append(text[text.index(BODY_MARKER) :])
    assert len(bodies) == 3
    assert all(body == bodies[0] for body in bodies)


def test_the_native_shim_ships_the_old_native_import_name():
    """The old arcadedb-embedded-native package imported as `arcadedb_native`; without this module an upgrader gets a bare ModuleNotFoundError."""
    assert "arcadedb_native" in MODULES["arcadedb-embedded-native"]
    assert "arcadedb_native" not in MODULES["arcadedb-embedded"]
    shim = DEPRECATION / "arcadedb-embedded-native"
    assert (shim / "src" / "arcadedb_native" / "__init__.py").is_file()
    pyproject = (shim / "pyproject.toml").read_text(encoding="utf-8")
    assert '"src/arcadedb_native"' in pyproject


@pytest.mark.parametrize(("dist", "module"), CASES)
def test_warning_fires_once_and_is_visible_by_default(dist, module, sites):
    result = _probe(sites[dist], module)
    assert len(result["warnings"]) == 1, result["warnings"]
    category, message, filename = result["warnings"][0]
    assert category == "FutureWarning"
    assert filename == "<string>"  # attributed to the importing code, not to the shim
    new = SHIMS[dist]
    assert f"pip install {new}" in message
    assert f"`import arcadedb` where you wrote `import {module}`" in message
    assert "https://github.com/ArcadeData/arcadedb-python" in message
    assert "https://docs.arcadedb.com/arcadedb-python/" in message

    # with Python's default filters, with no -W option: shown once on stderr
    shown = subprocess.run(  # nosec B603 - fixed argument list, no shell
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; sys.path.insert(0, sys.argv[1]); import {module}; import {module}.core",
            str(sites[dist]),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert shown.returncode == 0, shown.stderr
    assert shown.stderr.count("FutureWarning") == 1, shown.stderr


@pytest.mark.parametrize(("dist", "module"), CASES)
def test_attributes_and_submodules_come_from_the_new_module(dist, module, sites):
    result = _probe(sites[dist], module)
    assert result["same_class"] and result["same_function"]
    assert result["version"] == VERSION
    assert result["all"] == ["Database", "open_database"]
    assert result["private"] == "p"
    assert result["in_dir"]
    # a submodule the new package already imported, one it has not, and a nested one: the same
    # module objects as under `arcadedb`, never a second copy loaded from disk
    assert result["core_alias"] and result["core_in_modules"]
    assert result["lazy_alias"] and result["lazy_value"] == 42
    assert result["nested_alias"]
    assert result["no_second_copy"] == []
    assert result["spec_kept"] == "arcadedb.extra"
    assert "no attribute 'missing_name'" in result["missing_attr"]
    assert result["missing_module"] is True


BOTH = """
import sys, warnings
sys.path.insert(0, sys.argv[1])
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import arcadedb_embedded
    import arcadedb_native
import arcadedb
# a lazily imported submodule must resolve under each old name, not only under the first one imported
import arcadedb_embedded.extra
import arcadedb_native.extra
assert arcadedb_embedded.extra is arcadedb.extra, "arcadedb_embedded.extra"
assert arcadedb_native.extra is arcadedb.extra, "arcadedb_native.extra"
from arcadedb_native.sub import deep
assert deep is arcadedb.sub.deep
assert [w.category.__name__ for w in caught] == ["FutureWarning", "FutureWarning"], caught
assert [str(w.message).rsplit("`", 2)[-2] for w in caught] == [
    "import arcadedb_embedded",
    "import arcadedb_native",
]
print("ok")
"""


def test_the_native_shim_serves_both_old_names_in_one_process(sites):
    done = subprocess.run(  # nosec B603 - fixed argument list, no shell
        [sys.executable, "-I", "-c", BOTH, str(sites["arcadedb-embedded-native"])],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_the_real_package_has_no_warning():
    """The benchmark harness imports `arcadedb_embedded` from the real package until the split: it must stay quiet."""
    source = (BINDINGS / "src" / "arcadedb_embedded" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "warnings" not in source and "FutureWarning" not in source
