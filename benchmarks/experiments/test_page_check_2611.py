"""page_check.py holds the 2026-11 payload against its own sources, on the fixture payload.

Run with `python -m pytest test_page_check_2611.py -q` from this directory (needs numpy and pandas, as the exporter does).

The fixture rows (fixtures/publish_2611) are a subset, so the whole gate reports roster findings for engines the fixture does not
carry; these tests run the checks that hold on any payload, and tamper with a copy to see each one fail.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import test_publish_2611_e2e as E2E

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import page_check as PC  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    results = E2E._stage(tmp_path_factory.mktemp("pagecheck2611") / "results")
    for script in ("make_paper_tables.py", "export_web.py"):
        done = E2E._run(script, results)
        assert done.returncode == 0, done.stderr[-2000:]
    return results, json.loads((results / "web_benchmarks.json").read_text())


@pytest.fixture
def at(built, monkeypatch):
    """page_check pointed at the staged results tree, the way a publish run reads it."""
    import claims_check
    results, payload = built
    monkeypatch.setenv("BENCH_RESULTS_DIR", str(results))
    monkeypatch.setattr(claims_check, "TABLES", str(results / "generated" / "tables"))
    return results, copy.deepcopy(payload)


def _table(payload, tid):
    return next(t for t in payload["tables"] if t["id"] == tid)


def test_the_payload_is_the_one_instrument_and_not_a_skeleton(at, capsys):
    _results, payload = at
    assert PC._check_instrument(payload) == 0


@pytest.mark.parametrize("change,message", [({"instrument": "2026-10"}, "WRONG INSTRUMENT"),
                                            ({"instrument": None}, "WRONG INSTRUMENT"),
                                            ({"skeleton": True}, "SKELETON")])
def test_another_instrument_or_a_skeleton_fails(at, capsys, change, message):
    _results, payload = at
    payload.update(change)
    assert PC._check_instrument(payload) >= 1
    assert message in capsys.readouterr().out


def test_a_table_stamped_with_another_instrument_fails(at, capsys):
    _results, payload = at
    payload["tables"][0]["instrument"] = "2026-09"
    assert PC._check_instrument(payload) == 1
    assert payload["tables"][0]["id"] in capsys.readouterr().out


def test_the_default_payload_and_freeze_are_the_one_set_of_names(at):
    results, _payload = at
    assert PC.DEFAULT_JSON.name == "web_benchmarks.json"
    assert PC._frozen_path() == results / "runs_paper.csv"
    assert PC._generated_dir() == results / "generated"


def test_the_dense_cells_match_the_generated_table(at):
    _results, payload = at
    checked, bad = PC._check_dense_10m(payload)
    assert bad == 0 and checked > 0


def test_a_dense_cell_that_moved_from_its_table_is_caught(at, capsys):
    _results, payload = at
    for e in _table(payload, "l3d")["entries"]:
        if e.get("scale") == "deep10m" and e["backend"] == "ArcadeDB (embedded, fp32)":
            e["metrics"]["warm p50 ms"]["median"] *= 3
    _checked, bad = PC._check_dense_10m(payload)
    assert bad >= 1 and "DIFFER" in capsys.readouterr().out


def test_the_atomicity_cells_match_the_artifact(at):
    _results, payload = at
    checked, bad = PC._check_page_atomicity(payload)
    assert bad == 0 and checked > 0


def test_an_atomicity_count_that_drifted_from_the_artifact_is_caught(at, capsys):
    _results, payload = at
    _table(payload, "e2atom")["entries"][0]["metrics"]["trials"]["median"] += 7
    _checked, bad = PC._check_page_atomicity(payload)
    assert bad >= 1 and "DISAGREE" in capsys.readouterr().out


def test_a_single_engine_arm_that_tore_is_caught(at, capsys):
    _results, payload = at
    for e in _table(payload, "e2atom")["entries"]:
        if e.get("backend_key") == "arcadedb_e2":
            e["metrics"]["torn results"]["median"] = 3
    _checked, bad = PC._check_page_atomicity(payload)
    assert bad >= 1


def test_every_table_prints_an_arcadedb_row(at, tmp_path, monkeypatch):
    _results, payload = at
    monkeypatch.setattr(PC, "LIVE_JSON", tmp_path / "no-site-data.json")
    checked, bad = PC._check_no_arcadedb_row_lost(payload)
    assert bad == 0 and checked >= 10


def test_a_table_that_lost_its_arcadedb_row_is_caught_unless_it_says_so(at, tmp_path, monkeypatch, capsys):
    _results, payload = at
    monkeypatch.setattr(PC, "LIVE_JSON", tmp_path / "no-site-data.json")
    t = _table(payload, "docs_olap")
    t["entries"] = [e for e in t["entries"] if not e.get("is_arcadedb")]
    assert PC._check_no_arcadedb_row_lost(payload)[1] == 1
    assert "LOST" in capsys.readouterr().out
    t["conditions"] = ["ArcadeDB has no row on this table: " + "its analytics answers were not the question the comparators answered. " * 4]
    assert PC._check_no_arcadedb_row_lost(payload)[1] == 0


def test_a_table_the_site_serves_with_arcadedb_and_the_export_dropped_is_caught(at, tmp_path, monkeypatch, capsys):
    _results, payload = at
    live = {"tables": [{"id": "l2", "entries": [{"backend": "ArcadeDB (embedded)", "is_arcadedb": True}]}]}
    path = tmp_path / "dbbench-benchmarks.json"
    path.write_text(json.dumps(live))
    monkeypatch.setattr(PC, "LIVE_JSON", path)
    payload["tables"] = [t for t in payload["tables"] if t["id"] != "l2"]
    assert PC._check_no_arcadedb_row_lost(payload)[1] == 1
    assert "LOST   table l2" in capsys.readouterr().out


def test_the_gate_run_refuses_a_payload_of_another_instrument(built, tmp_path):
    results, payload = built
    payload["instrument"] = "2026-10"
    bad = tmp_path / "web_benchmarks.json"
    bad.write_text(json.dumps(payload))
    done = subprocess.run([sys.executable, str(HERE / "page_check.py"), "--json", str(bad)], cwd=HERE,
                          env=E2E._env(results), capture_output=True, text=True, timeout=900)
    assert done.returncode == 1 and "WRONG INSTRUMENT" in done.stdout
    assert "Traceback" not in done.stderr
