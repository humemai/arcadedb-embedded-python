"""`cell_cost_check.py --backends` scores only the stage's own engines, and every generated stage passes its BACKENDS.

Run with `python -m pytest test_cell_cost_backends.py -q -rs` from this directory.

On 2026-10-17 qP22, a one-engine ArcadeDB stage, aborted because the check scored the whole lane and found
MongoDB and SurrealDB, which that stage does not run, over the cap at tpch10. Every later stage waits for the
aborted stage's ALL-DONE marker, so the chain stopped with it.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _check(tmp_path, *extra):
    rows = tmp_path / "rows.jsonl"
    with rows.open("w") as fh:
        # A lane with no query roster, so the scoring needs no lane module; cap 100 s.
        fh.write(json.dumps({"lane": "lifecycle", "scale": "lc10k", "backend": "slow_engine", "cold_op_ms": 150_000, "ingest_s": 10}) + "\n")
        fh.write(json.dumps({"lane": "lifecycle", "scale": "lc10k", "backend": "fast_engine", "cold_op_ms": 1_000, "ingest_s": 1}) + "\n")
    cmd = [sys.executable, str(HERE / "cell_cost_check.py"), "--lane", "lifecycle", "--tier", "lc10k", "--cap", "100", "--rows", str(rows), *extra]
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)


def test_without_backends_every_engine_counts(tmp_path):
    r = _check(tmp_path)
    assert r.returncode == 1 and "slow_engine" in r.stdout and "fast_engine" in r.stdout


def test_an_engine_the_stage_does_not_run_cannot_stop_it(tmp_path):
    r = _check(tmp_path, "--backends", "fast_engine")
    assert r.returncode == 0, r.stdout
    assert "slow_engine" not in r.stdout


def test_the_stage_s_own_engine_over_the_cap_still_stops_it(tmp_path):
    assert _check(tmp_path, "--backends", "fast_engine,slow_engine").returncode == 1
    assert _check(tmp_path, "--backends", "slow_engine fast_engine").returncode == 1


def test_an_engine_with_no_rows_is_not_scored(tmp_path):
    r = _check(tmp_path, "--backends", "new_arm")
    assert r.returncode == 2 and "not scored" in r.stdout


def test_every_generated_stage_passes_its_own_backends(tmp_path):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = {k: v for k, v in os.environ.items() if k != "BENCH_INSTRUMENT"}
    env.update(ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp_path / "stages"
    r = subprocess.run([sys.executable, str(HERE / "make_2611_stages.py"), "--profile", "full", "--second-list", "--after", "none", "--out", str(out)],
                       cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    scripts = sorted(out.glob("*.sh"))
    checked = 0
    for p in scripts:
        text = p.read_text()
        m = re.search(r'^BACKENDS="([^"]*)"$', text, re.M)
        calls = [l for l in text.splitlines() if "python3 cell_cost_check.py" in l]
        if not calls:
            continue
        assert m, p.name
        for line in calls:
            assert f'--backends "{m.group(1)}"' in line, (p.name, line)
        checked += 1
    assert checked > 0
