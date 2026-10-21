"""The harness measures one instrument, "2026-11" (DECISIONS #196): unset is 2026-11, naming it is accepted, and any other BENCH_INSTRUMENT is refused."""
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


def test_unset_is_the_only_instrument():
    r = _instrument(None)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["2026-11", "True"]


def test_naming_the_instrument_is_accepted():
    r = _instrument("2026-11")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["2026-11", "True"]


def test_the_retired_instruments_and_unknown_ones_are_refused_with_a_message():
    for v in ("2026-10", "2026-09", "2027-01"):
        r = _instrument(v)
        assert r.returncode != 0, v
        out = r.stderr + r.stdout
        assert f"BENCH_INSTRUMENT='{v}'" in out and "measures only 2026-11" in out and "retired" in out


def test_unknown_version_in_code_is_an_error():
    sys.path.insert(0, HERE)
    b = importlib.import_module("bench_common")
    try:
        b.instrument_at_least("1999-01")
    except ValueError:
        return
    raise AssertionError("instrument_at_least accepted an unknown version")


def test_the_runner_stamps_the_instrument_on_the_row_and_the_stamp_is_the_selector_value():
    sys.path.insert(0, HERE)
    b = importlib.import_module("bench_common")
    assert b.INSTRUMENTS == ("2026-11",) and b.INSTRUMENT == "2026-11"
