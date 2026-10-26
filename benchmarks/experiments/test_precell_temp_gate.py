"""The pre-cell temperature gate of make_2611_stages.py (the user, 2026-10-26; OPEN-ITEMS #28): a timed cell starts only with the package at or
below 70 C, waiting at most 15 min, and the outcome reaches STATUS and the row (runner.precell_gate_stamp).

Run with `python -m pytest test_precell_temp_gate.py -q` from this directory. The bash of TEMP_GATE_HELPERS runs for real against a fake hwmon
tree; the poll and the cap are shortened by assigning the plain variables after the helpers are sourced."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2611_stages as G  # noqa: E402
import runner  # noqa: E402


def _hwmon(root, name, temp_mc):
    d = root / name
    d.mkdir(parents=True)
    (d / "name").write_text("coretemp\n" if name == "hwmon3" else "acpitz\n")
    (d / "temp1_input").write_text(f"{temp_mc}\n")
    return d / "temp1_input"


def _gate(tmp_path, root, cap=2, poll=1):
    (tmp_path / "helpers.sh").write_text(G.TEMP_GATE_HELPERS)
    script = f'''set -u
ID=qT; S={tmp_path}/status; say() {{ echo "$*" >> "$S"; }}
source {tmp_path}/helpers.sh
GATE_WAIT_CAP_S={cap}; GATE_POLL_S={poll}
temp_gate "l2/sf1/x/oltp"
echo "$BENCH_PRECELL_GATE_TEMP_C|$BENCH_PRECELL_GATE_WAIT_S|$BENCH_PRECELL_GATE_OK|$BENCH_PRECELL_GATE_MAX_C"
'''
    p = subprocess.run(["bash", "-c", script], env=dict(os.environ, BENCH_GATE_HWMON=str(root)), capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    status = (tmp_path / "status").read_text() if (tmp_path / "status").exists() else ""
    return p.stdout.strip(), status


def test_a_cool_package_passes_at_once_and_the_sensor_is_found_by_name_not_number(tmp_path):
    _hwmon(tmp_path / "hw", "hwmon0", 99000)   # acpitz: hot, but not the package
    _hwmon(tmp_path / "hw", "hwmon3", 70000)   # coretemp at the limit: <= passes
    out, status = _gate(tmp_path, tmp_path / "hw")
    assert out == "70.0|0|true|70"
    assert "TEMP GATE: start 70.0 C, waited 0 s, gate_ok=true" in status and "waiting" not in status


def test_a_hot_package_waits_until_it_is_at_or_below_the_limit(tmp_path):
    f = _hwmon(tmp_path / "hw", "hwmon3", 89000)
    _hwmon(tmp_path / "hw", "hwmon0", 30000)
    threading.Thread(target=lambda: (time.sleep(2.5), f.write_text("69500\n")), daemon=True).start()
    out, status = _gate(tmp_path, tmp_path / "hw", cap=30, poll=1)
    temp, wait, ok, limit = out.split("|")
    assert temp == "69.5" and ok == "true" and limit == "70" and 2 <= int(wait) <= 5
    assert "package 89.0 C is above 70 C, waiting" in status and "gate_ok=true" in status


def test_a_package_that_stays_hot_starts_anyway_after_the_cap_with_gate_ok_false(tmp_path):
    _hwmon(tmp_path / "hw", "hwmon3", 88000)
    out, status = _gate(tmp_path, tmp_path / "hw", cap=2, poll=1)
    temp, wait, ok, _ = out.split("|")
    assert temp == "88.0" and ok == "false" and int(wait) >= 2
    assert "gate_ok=false" in status


def test_no_coretemp_sensor_starts_ungated_and_says_so(tmp_path):
    (tmp_path / "hw").mkdir()
    out, status = _gate(tmp_path, tmp_path / "hw")
    assert out == "|0|false|70"
    assert "start unknown C, waited 0 s, gate_ok=false" in status


def test_every_run_cell_and_run_overlay_gates_after_the_skip_checks_and_before_the_runner():
    t = G.HEAD
    for fn in ("run_overlay", "run_cell"):
        body = t[t.index(f"\n{fn}() {{"):]
        body = body[:body.index("\n}}\n")]
        assert body.index("rep_gate") < body.index("temp_gate") < body.index("python3 runner.py"), fn


def test_the_runner_stamps_the_gate_into_the_row_and_leaves_ungated_rows_alone():
    env = {"BENCH_PRECELL_GATE_TEMP_C": "68.4", "BENCH_PRECELL_GATE_WAIT_S": "112", "BENCH_PRECELL_GATE_OK": "true", "BENCH_PRECELL_GATE_MAX_C": "70"}
    assert runner.precell_gate_stamp({"rc": 0}, env) == {"rc": 0, "precell_gate_ok": True, "precell_gate_temp_c": 68.4,
                                                         "precell_gate_wait_s": 112, "precell_gate_max_c": 70}
    assert runner.precell_gate_stamp({"rc": 0}, {}) == {"rc": 0}
    bad = dict(env, BENCH_PRECELL_GATE_TEMP_C="", BENCH_PRECELL_GATE_OK="false")
    assert runner.precell_gate_stamp({}, bad) == {"precell_gate_ok": False, "precell_gate_wait_s": 112, "precell_gate_max_c": 70}
