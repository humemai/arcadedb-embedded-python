"""`make_2610_stages.py --rep-pass N` (DECISIONS #164): a stage runs reps 1..N of the REPS it declares.

Run with `python -m pytest test_stage_rep_pass.py -q -rs` from this directory.

The user's plan for the 26.10.1 measurement is N=3 first and the other two repetitions in a later pass. What these tests hold fixed:
`--reps` stays the declared total in every runner call (the rows carry reps=5 whatever pass made them, and the runner's shuffle
draws from it), `--only-reps` names the pass, rep 1 still goes first, a cell that declares fewer reps than the pass runs its own,
the overlay follows the same rule, and a generation without `--rep-pass` is byte-for-byte what it was. The shell functions are run
for real against a stub runner, because a stage that passes `bash -n` can still run the wrong reps.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2610_stages as G  # noqa: E402


def _generate(tmp_path, *extra):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp_path / ("stages" + "".join(extra).replace("-", "").replace(" ", ""))
    r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out), "--after", "none", *extra],
                       cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return out


def _function(text, name):
    m = re.search(rf"^{name}\(\) \{{.*?^\}}$", text, re.S | re.M)
    assert m, name
    return m.group(0)


def _stub_runner(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    calls = tmp_path / "calls.txt"
    stub = bindir / "python3"
    stub.write_text(f'#!/bin/bash\necho "$*" >> {calls}\nexit 0\n')
    stub.chmod(0o755)
    calls.write_text("")
    return bindir, calls


def _run(tmp_path, script_text, driver, reps, call):
    """Run the stage's LAST_REP line and its functions for real; return the runner's argument lines."""
    bindir, calls = _stub_runner(tmp_path)
    last = re.search(r"^LAST_REP=.*$", script_text, re.M)
    prelude = (last.group(0) if last else "LAST_REP=$REPS") + "\n"
    body = (f'say() {{ :; }}\nS=/dev/null\nRF=rf.jsonl\nID=T\nREPS={reps}\n{prelude}'
            f'{_function(script_text, "run_overlay")}\n{_function(script_text, "run_cell")}\n{call}\n')
    r = subprocess.run(["bash", "-c", body], env=dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}"),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return [l for l in calls.read_text().splitlines() if l.strip()]


def _only_reps(line):
    return re.search(r"--only-reps (\S+)", line).group(1) if "--only-reps" in line else None


def _declared(line):
    return re.search(r"--reps (\S+)", line).group(1)


@pytest.fixture(scope="module")
def stages(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("repstages")
    first = _generate(tmp, "--rep-pass", "3")
    default = _generate(tmp, "--order", "tiers")
    return first, default, tmp


def _dense(dirpath, prefix):
    for p in sorted(dirpath.glob(f"{prefix}*.sh")):
        t = p.read_text()
        if "dense_multipass_driver" in t:
            return t
    raise AssertionError("no dense stage")


CELL = 'run_cell "l3d/small/b/search" small 7200 b search ""'
OVER = 'run_overlay "lbl" small 7200 b search drv.py outdir orf.jsonl {n} ""'


def test_the_first_pass_runs_reps_one_to_three_and_keeps_five_as_the_declared_total(stages):
    first, _default, tmp = stages
    calls = _run(tmp, _dense(first, "qP"), "x", 5, CELL)
    assert [_only_reps(c) for c in calls] == ["1", "2,3"]
    assert {_declared(c) for c in calls} == {"5"}


def test_without_a_pass_every_declared_rep_runs(stages):
    _first, default, tmp = stages
    calls = _run(tmp, _dense(default, "qT"), "x", 5, CELL)
    assert [_only_reps(c) for c in calls] == ["1", "2,3,4,5"]


def test_a_cell_that_declares_fewer_reps_than_the_pass_runs_its_own(stages):
    first, _default, tmp = stages
    text = _dense(first, "qP")
    assert [_only_reps(c) for c in _run(tmp, text, "x", 2, CELL)] == ["1", "2"]
    assert [_only_reps(c) for c in _run(tmp, text, "x", 3, CELL)] == ["1", "2,3"]
    one = _run(tmp, text, "x", 1, CELL)
    assert [_only_reps(c) for c in one] == ["1"], "REPS=1 has no second invocation"


def test_a_failed_rep_one_still_ends_the_arm(stages):
    first, _default, tmp = stages
    bindir, calls = _stub_runner(tmp)
    (bindir / "python3").write_text(f'#!/bin/bash\necho "$*" >> {calls}\nexit 1\n')
    text = _dense(first, "qP")
    body = (f'say() {{ :; }}\nS=/dev/null\nRF=rf.jsonl\nID=T\nREPS=5\n{re.search(r"^LAST_REP=.*$", text, re.M).group(0)}\n'
            f'{_function(text, "run_overlay")}\n{_function(text, "run_cell")}\n{CELL}\n{OVER.format(n=5)}\n')
    subprocess.run(["bash", "-c", body], env=dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}"), capture_output=True)
    assert [_only_reps(c) for c in calls.read_text().splitlines()] == ["1", "1"], "one call per arm: rep 1 failed, nothing repeats"


def test_the_overlay_follows_the_pass(stages):
    first, default, tmp = stages
    pass_calls = _run(tmp, _dense(first, "qP"), "x", 5, OVER.format(n=5))
    assert [_only_reps(c) for c in pass_calls] == ["1", "2,3"] and {_declared(c) for c in pass_calls} == {"5"}
    assert [_only_reps(c) for c in _run(tmp, _dense(default, "qT"), "x", 5, OVER.format(n=5))] == ["1", "2,3,4,5"]
    # the sparse overlay declares one rep (the driver repeats inside itself) and runs as is
    single = _run(tmp, _dense(first, "qP"), "x", 5, OVER.format(n=1))
    assert len(single) == 1 and _only_reps(single[0]) is None


def test_every_stage_declares_its_pass_and_the_ids_are_new(stages):
    first, default, _tmp = stages
    ids = sorted(p.stem for p in first.glob("*.sh"))
    assert ids == [f"qP{i:02d}" for i in range(1, len(G.tiered_stages()) + 1)]
    assert not set(ids) & {p.stem for p in default.glob("*.sh")}
    for p in first.glob("*.sh"):
        t = p.read_text()
        if "pycost" in t.split("\n", 2)[1].lower() or "Python-cost" in t.split("\n", 2)[1]:
            continue
        assert re.search(r"^LAST_REP=\$\(\( REPS < 3 \? REPS : 3 \)\)$", t, re.M), p.name
        assert 'seq -s, 2 "$REPS"' not in t, p.name
        assert subprocess.run(["bash", "-n", str(p)], capture_output=True).returncode == 0, p.name


def test_the_default_generation_is_untouched_by_the_option(stages):
    _first, default, _tmp = stages
    for p in default.glob("*.sh"):
        assert "LAST_REP" not in p.read_text(), p.name


def test_a_pass_outside_one_to_five_is_refused(tmp_path):
    env = dict(os.environ, ARCADEDB_WHEEL="x", ARCADEDB_SERVER_IMAGE="y", ARCADEDB_ENGINE_COMMIT="0" * 40)
    for bad in ("0", "6"):
        r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--check", "--rep-pass", bad],
                           cwd=HERE, env=env, capture_output=True, text=True)
        assert r.returncode != 0 and "--rep-pass must be 1 to 5" in (r.stdout + r.stderr)
