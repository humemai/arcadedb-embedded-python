"""The native wheel starts quietly at run time: the first open logs nothing at WARNING or above (#477).

Needs the native library, so conftest.py does not collect this file on the JPype backend (a skip there would fail
scripts/check_test_skips.py); it runs in the native parity run.
"""

import re
import subprocess  # nosec B404 - test-controlled child process
import sys


def test_the_first_open_writes_nothing_at_warning(tmp_path):
    code = (
        "import arcadedb_embedded as a, sys\n"
        f"db = a.create_database({str(tmp_path / 'db')!r})\n"
        "db.query('sql', 'SELECT 1 AS v').first()\n"
        "db.close()\n"
    )
    done = subprocess.run(  # nosec B603 - fixed argv, no shell, test-owned code string
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr
    output = done.stdout + done.stderr
    assert "no languages found" not in output
    assert not re.search(r"\b(WARNI|WARNING|SEVERE|ERROR)\b", output), output
