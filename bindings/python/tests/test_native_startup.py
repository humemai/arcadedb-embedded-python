"""The native wheel starts quietly: no polyglot-engine warning (#477)."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ARCADE_NATIVE = (
    Path(__file__).resolve().parents[3]
    / "native-spike/src/main/java/org/humemai/nativelib/ArcadeNative.java"
)


def test_the_image_glue_switches_the_polyglot_engine_off_before_any_entry_point():
    """The image has no polyglot languages; leaving the engine on logs 'no languages found' at WARNING in every process.

    Static check (no native build needed): the glue class that holds the entry points must set the option in a static initializer.
    """
    if not ARCADE_NATIVE.is_file():
        pytest.skip("the repository checkout is not available")
    source = ARCADE_NATIVE.read_text()
    assert re.search(
        r"static\s*\{[^{}]*GlobalConfiguration\.POLYGLOT_ENGINE_ENABLED\.setValue\(false\);[^{}]*\}",
        source,
    ), "ArcadeNative must run GlobalConfiguration.POLYGLOT_ENGINE_ENABLED.setValue(false) in a static block"


def test_the_first_open_writes_nothing_at_warning(tmp_path):
    """Needs the native library, so it runs in the native parity run only."""
    if os.environ.get("ARCADEDB_BACKEND", "jpype").lower() != "native":
        pytest.skip("native backend only")
    code = (
        "import arcadedb_embedded as a, sys\n"
        f"db = a.create_database({str(tmp_path / 'db')!r})\n"
        "db.query('sql', 'SELECT 1 AS v').first()\n"
        "db.close()\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr
    output = done.stdout + done.stderr
    assert "no languages found" not in output
    assert not re.search(r"\b(WARNI|WARNING|SEVERE|ERROR)\b", output), output
