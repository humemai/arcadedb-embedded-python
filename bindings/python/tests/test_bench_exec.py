"""Tests for the Docker-wrapper pieces of the benchmark examples 07 to 12.

The wrappers run each example as ``uv run --no-project --with ... python
bench_exec.py <script>``. These tests check that ``bench_exec.py`` records the
interpreter and installed versions of the process it then becomes, and that no
wrapper goes back to ``uv pip`` or a hand-made venv.
"""

import re
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
WRAPPERS = sorted(EXAMPLES.glob("0[7-9]_*.py")) + sorted(EXAMPLES.glob("1[0-2]_*.py"))


def test_bench_exec_prints_environment_then_becomes_the_script(tmp_path):
    script = tmp_path / "probe.py"
    script.write_text(
        "import sys\nprint('PROBE', sys.executable, sys.stdout.write_through, sys.argv[1:])\n"
    )
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / "bench_exec.py"), str(script), "--a", "1"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    env_lines = [line for line in lines if line.startswith("[bench-env] ")]
    assert env_lines[0].startswith(
        f"[bench-env] python={sys.version.split()[0]} "
    ), env_lines[0]
    packages = [
        line for line in env_lines[1:] if re.fullmatch(r"\[bench-env\] \S+==\S+", line)
    ]
    assert packages, "no package versions printed"
    # The measured process is the interpreter that printed the versions, unbuffered.
    assert lines[-1] == f"PROBE {sys.executable} True ['--a', '1']"


def test_wrappers_use_uv_run_not_uv_pip_or_venv():
    assert len(WRAPPERS) == 6
    for path in WRAPPERS:
        text = path.read_text(encoding="utf-8")
        assert "uv pip" not in text, path.name
        assert "bench-venv" not in text, path.name
        assert "-m venv" not in text, path.name
        assert "python bench_exec.py" in text, path.name
