"""Every publish gate, run on the 2026-11 fixture payload and required to pass (humemai/arcadedb-embedded-python#433).

test_publish_2611_e2e.py proves the freeze and the exporter on `fixtures/publish_2611`. This proves the gates that stand between
the frozen rows and the page, run the way PUBLISHING.md runs them: make_paper_tables (whose internal gates are fairness_check and
provenance_check), export_web, then equivalence_check, resource_check, override_registry, degenerate_check, fairness_check,
page_check, version_consistency_check, version_pin_check, provenance_check, make_paper_figures and the table-regeneration half of
claims_check. A gate that fails here either found a fixture row no 2026-11 run could write (fix the fixture: build_fixture.py,
`realistic_2611`) or still encodes an instrument that was retired (fix the gate); a regression in either shows up as a red test.

Not run: claims_check's default mode, which pins the typed numbers of the retired paper's prose to the rows that produced them
(its docstring: nothing runs it as a gate), and refresh_web_page's step 3 table-coverage check, which reads the humem.ai checkout.

Run with `python -m pytest test_publish_gates_2611.py -q` from this directory (needs numpy and pandas; the figures test also
needs matplotlib, pdftotext and Ghostscript, and is skipped with that reason when they are absent).
"""
import json
import shutil
import subprocess
import sys

import pytest

from test_publish_2611_e2e import HERE, _env, _stage

GATES = [
    ("equivalence_check", []),
    ("resource_check", []),
    ("override_registry", []),
    ("degenerate_check", ["{results}/runs_paper.csv"]),
    ("fairness_check", []),
    ("page_check", []),
    ("version_consistency_check", []),
    ("version_pin_check", []),
    ("provenance_check", []),
    ("claims_check", ["--regen"]),
]


def _gate(name, args, results, site, **extra):
    env = _env(results, BENCH_SITE_DIR=str(site), **extra)
    argv = [sys.executable, str(HERE / f"{name}.py")] + [a.format(results=results) for a in args]
    return subprocess.run(argv, cwd=HERE, env=env, capture_output=True, text=True, timeout=900)


@pytest.fixture(scope="module")
def payload_dir(tmp_path_factory):
    """The fixture frozen and exported, as `refresh_web_page` steps 1 and 2 leave it, and an empty site checkout."""
    root = tmp_path_factory.mktemp("gates2611")
    results = _stage(root / "results")
    (root / "site").mkdir()
    for script in ("make_paper_tables.py", "export_web.py"):
        proc = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=_env(results),
                              capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-2000:]
    return {"results": results, "site": root / "site"}


def _tail(proc):
    return (proc.stdout + proc.stderr)[-3000:]


def test_make_paper_tables_gates_pass_on_the_fixture(payload_dir):
    # make_paper_tables prints GATES REPORTED FAILURES and still exits 0 unless --strict, so read the status it writes
    proc = subprocess.run([sys.executable, str(HERE / "make_paper_tables.py"), "--strict"], cwd=HERE,
                          env=_env(payload_dir["results"]), capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0 and "GATES REPORTED FAILURES" not in proc.stdout, _tail(proc)


@pytest.mark.parametrize("name,args", GATES, ids=[g[0] for g in GATES])
def test_the_gate_passes_on_the_fixture_payload(payload_dir, name, args):
    proc = _gate(name, args, payload_dir["results"], payload_dir["site"])
    assert proc.returncode == 0, _tail(proc)


def test_page_check_accepts_the_pq_arms_without_the_pq_switch(payload_dir):
    # runner.LANES lists the PQ arms only under BENCH_DENSE_PQ=1; the payload carries PQ rows regardless
    payload = json.loads((payload_dir["results"] / "web_benchmarks.json").read_text())
    l3d = next(t for t in payload["tables"] if t["id"] == "l3d")
    assert any(e["backend_key"].endswith("_pq") for e in l3d["entries"])
    proc = _gate("page_check", [], payload_dir["results"], payload_dir["site"])
    assert "STRAY" not in proc.stdout and proc.returncode == 0, _tail(proc)


def test_the_page_check_roster_still_refuses_an_arm_that_vanished(payload_dir, tmp_path):
    results = tmp_path / "results"
    shutil.copytree(payload_dir["results"], results)
    path = results / "web_benchmarks.json"
    payload = json.loads(path.read_text())
    e2 = next(t for t in payload["tables"] if t["id"] == "e2")
    e2["entries"] = [e for e in e2["entries"] if e["backend_key"] != "ladybug_e2"]
    path.write_text(json.dumps(payload))
    proc = _gate("page_check", [], results, payload_dir["site"])
    assert proc.returncode != 0 and "MISSING" in proc.stdout and "ladybug_e2" in proc.stdout, _tail(proc)


def test_equivalence_check_still_catches_a_different_answer(payload_dir, tmp_path):
    results = tmp_path / "results"
    shutil.copytree(payload_dir["results"], results)
    rows = [json.loads(l) for l in (results / "runs.jsonl").read_text().splitlines() if l.strip()]
    victim = next(r for r in rows if r["lane"] == "l2" and r["backend"] == "neo4j_graph" and r.get("res_point_digest"))
    victim["res_point_digest"] = "0000000000000000"
    (results / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    proc = _gate("equivalence_check", [], results, payload_dir["site"])
    assert proc.returncode != 0 and "different answers" in proc.stdout, _tail(proc)


def test_the_paper_figures_draw_or_skip_with_a_named_reason(payload_dir):
    pytest.importorskip("matplotlib", reason="make_paper_figures draws with matplotlib")
    for tool in ("pdftotext", "gs"):
        if not shutil.which(tool):
            pytest.skip(f"make_paper_figures needs {tool} (it crops the PDFs and reads their text back)")
    proc = subprocess.run([sys.executable, str(HERE / "make_paper_figures.py")], cwd=HERE, env=_env(payload_dir["results"]),
                          capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, _tail(proc)
    # f3 reads sparse_cliff.jsonl, a one-shot artifact the fixture does not carry: it says so instead of crashing
    assert "f3 skipped: no results/sparse_cliff.jsonl" in proc.stdout
