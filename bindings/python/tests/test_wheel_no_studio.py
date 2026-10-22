"""The Studio/ApexCharts guard: a wheel that carries either fails the build.

Studio bundles ApexCharts, which is not open source since 5.1.0 (ArcadeData/arcadedb#10579). The tests build tiny
wheels in a temporary directory, so they run in milliseconds and need no built wheel.
"""

from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify_wheel_no_studio.py"
)
EXCLUSIONS = Path(__file__).resolve().parents[1] / "scripts" / "jar_exclusions.txt"


def _load():
    spec = importlib.util.spec_from_file_location("verify_wheel_no_studio", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _jar(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _wheel(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_studio_jar_is_in_the_exclusion_list():
    lines = [ln.strip() for ln in EXCLUSIONS.read_text().splitlines()]
    assert "arcadedb-studio-*.jar" in lines


def test_a_clean_wheel_passes(tmp_path, capsys):
    module = _load()
    wheel = _wheel(
        tmp_path / "a-1-py3-none-any.whl",
        {
            "arcadedb_embedded/jars/arcadedb-server-1.jar": _jar({"A.class": b"x"}),
            "arcadedb_embedded/server.py": b"",
        },
    )
    assert module.main([str(wheel)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_a_studio_jar_fails_the_wheel(tmp_path, capsys):
    module = _load()
    wheel = _wheel(
        tmp_path / "a-1-py3-none-any.whl",
        {
            "arcadedb_embedded/jars/arcadedb-studio-26.10.2.jar": _jar(
                {"static/index.html": b"x"}
            )
        },
    )
    assert module.main([str(wheel)]) == 1
    assert "Studio jar" in capsys.readouterr().err


def test_an_apexcharts_file_fails_the_wheel(tmp_path, capsys):
    module = _load()
    wheel = _wheel(
        tmp_path / "a-1-py3-none-any.whl",
        {"arcadedb_embedded/static/dist/js/apexcharts.min.js": b"x"},
    )
    assert module.main([str(wheel)]) == 1
    assert "ApexCharts file" in capsys.readouterr().err


def test_a_renamed_jar_that_carries_apexcharts_fails_the_wheel(tmp_path, capsys):
    module = _load()
    wheel = _wheel(
        tmp_path / "a-1-py3-none-any.whl",
        {
            "arcadedb_embedded/jars/ui-1.jar": _jar(
                {"static/dist/js/ApexCharts.min.js": b"x"}
            )
        },
    )
    assert module.main([str(wheel), str(wheel)]) == 1
    assert "contains ApexCharts files" in capsys.readouterr().err


def test_a_missing_file_is_a_usage_error(tmp_path):
    module = _load()
    assert module.main([str(tmp_path / "nope.whl")]) == 2
    assert module.main([]) == 2
