"""BENCH_INSTRUMENT selects the instrument; unset it stays "2026-10" so a running chain that pulls main is unchanged."""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _instrument(env_value):
    env = dict(os.environ)
    env.pop("BENCH_INSTRUMENT", None)
    if env_value is not None:
        env["BENCH_INSTRUMENT"] = env_value
    code = "import bench_common as b; print(b.INSTRUMENT, b.instrument_at_least('2026-11'))"
    return subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True)


def test_unset_keeps_the_running_instrument():
    r = _instrument(None)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["2026-10", "False"]


def test_next_instrument_is_selected_by_the_env():
    r = _instrument("2026-11")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["2026-11", "True"]


def test_an_unknown_instrument_is_refused():
    r = _instrument("2027-01")
    assert r.returncode != 0
    assert "is not one of" in (r.stderr + r.stdout)


def test_unknown_version_in_code_is_an_error():
    sys.path.insert(0, HERE)
    b = importlib.import_module("bench_common")
    try:
        b.instrument_at_least("1999-01")
    except ValueError:
        return
    raise AssertionError("instrument_at_least accepted an unknown version")
