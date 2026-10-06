"""`make_2610_stages.py --after none` emits a chain whose first stage does not wait (CAMPAIGN section 7, the re-pin start).

Run with `python -m pytest test_stage_generator_after.py -q -rs` from this directory.

The chain was generated to start after the old October queue's last stage (`qOA5`). When that queue is
cancelled the first stage must start when launched, and a chain that still waits on a marker nobody will
write idles forever with every script alive. The empty-string trap is the other way round: `grep -q " ALL-DONE"`
matches the first marker line in STATUS.txt, so a stage would start at once while reading as a wait.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2610_stages as G  # noqa: E402


def test_after_arg_none_and_empty_mean_no_wait():
    assert G._after_arg("none") is None and G._after_arg("None") is None and G._after_arg("") is None
    assert G._after_arg(" ") is None
    assert G._after_arg("qOA5") == "qOA5"


def _generate(tmp_path, after):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp_path / "stages"
    cmd = [sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out)] + (["--after", after] if after is not None else [])
    r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return out, r.stdout


def _waits(path):
    return [l for l in path.read_text().splitlines() if l.startswith("while ! grep -q") and "ALL-DONE" in l]


def test_none_leaves_the_first_stage_without_a_wait_and_the_rest_chained(tmp_path):
    out, listing = _generate(tmp_path, "none")
    assert _waits(out / "qRA.sh") == []
    assert "qRA ALL-DONE" in "\n".join(_waits(out / "qRB.sh"))
    assert "qRN ALL-DONE" in "\n".join(_waits(out / "qRO.sh"))
    assert "after=None" in listing and "qOA5" not in (out / "qRA.sh").read_text().split("set -u")[1][:400]


def test_the_default_still_waits_on_the_old_chain(tmp_path):
    out, _ = _generate(tmp_path, None)
    assert any("qOA5 ALL-DONE" in w for w in _waits(out / "qRA.sh"))
