"""refresh_web_page.py publishes one payload to one site target: the sync and the tableId coverage step, on a fixture payload.

Run with `python -m pytest test_refresh_web_page_2611.py -q` from this directory (needs numpy and pandas, as the exporter does).

The whole script needs a humem.ai checkout and a Next.js build, so this runs the steps that need neither: the payload the exporter
writes from the 2026-11 fixture (freeze and export as separate processes, the way a publish runs them) is synced into a fake site
directory, and the coverage step reads the fake site's `src/lib/dbbench/lanes.ts`.
"""
import json
import re
import sys
from pathlib import Path

import pytest

import test_publish_2611_e2e as E2E

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import refresh_web_page as R  # noqa: E402


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    results = E2E._stage(tmp_path_factory.mktemp("refresh2611") / "results")
    for script in ("make_paper_tables.py", "export_web.py"):
        done = E2E._run(script, results)
        assert done.returncode == 0, done.stderr[-2000:]
    return results / "web_benchmarks.json"


def _lanes_ts(ids):
    body = "\n".join(f'      {{\n        tableId: "{t}",\n        caption: "x",\n      }},' for t in ids)
    return f"export const dbbenchLanes = [\n  {{\n    tables: [\n{body}\n    ],\n  }},\n];\n"


def _site(tmp_path, ids):
    site = tmp_path / "site"
    (site / "src" / "lib" / "dbbench").mkdir(parents=True)
    (site / "src" / "lib" / "dbbench" / "lanes.ts").write_text(_lanes_ts(ids))
    return site


def _ids(exported):
    return [t["id"] for t in json.loads(exported.read_text())["tables"]]


def test_the_one_target_is_the_dbbench_lane_pages():
    assert R.PAGE_SOURCE == "src/lib/dbbench/lanes.ts"
    assert R.PAGE_DATA == "src/data/dbbench-benchmarks.json"
    assert "page_check" in R.GATES and len(R.GATES) == 7


def test_there_is_no_preview_or_skeleton_route(monkeypatch):
    for flag in ("--preview", "--skeleton"):
        monkeypatch.setattr(sys, "argv", ["refresh_web_page.py", flag])
        with pytest.raises(SystemExit) as exc:
            R.main()
        assert exc.value.code == 2


def test_another_instrument_is_refused_before_anything_runs(monkeypatch):
    monkeypatch.setenv("BENCH_INSTRUMENT", "2026-10")
    monkeypatch.setattr(sys, "argv", ["refresh_web_page.py", "--site", "/nonexistent"])
    with pytest.raises(SystemExit) as exc:
        R.main()
    assert "2026-11 rows only" in str(exc.value)


def test_the_payload_the_exporter_wrote_passes_the_stamp_guard(exported):
    R._refuse_wrong_payload(exported)


@pytest.mark.parametrize("change", [{"instrument": "2026-10"}, {"instrument": None}, {"skeleton": True}])
def test_a_payload_of_another_instrument_or_a_skeleton_is_refused(exported, tmp_path, change):
    doc = json.loads(exported.read_text())
    doc.update(change)
    bad = tmp_path / "web_benchmarks.json"
    bad.write_text(json.dumps(doc))
    with pytest.raises(SystemExit) as exc:
        R._refuse_wrong_payload(bad)
    assert "REFUSING" in str(exc.value)


def test_a_page_and_a_payload_that_name_the_same_tables_agree(exported, tmp_path, capsys):
    site = _site(tmp_path, _ids(exported))
    assert R.check_table_coverage(exported, site / R.PAGE_SOURCE, set()) == 0
    assert "the two agree" in capsys.readouterr().out


def test_a_table_the_page_names_and_the_payload_lacks_is_refused(exported, tmp_path, capsys):
    site = _site(tmp_path, _ids(exported) + ["l2olap_gone"])
    assert R.check_table_coverage(exported, site / R.PAGE_SOURCE, set()) == 1
    assert "l2olap_gone" in capsys.readouterr().err


def test_a_table_the_payload_carries_and_the_page_never_names_is_refused(exported, tmp_path, capsys):
    ids = _ids(exported)
    site = _site(tmp_path, ids[1:])
    assert R.check_table_coverage(exported, site / R.PAGE_SOURCE, set()) == 1
    assert ids[0] in capsys.readouterr().err


def test_a_staged_landing_declares_the_missing_tables_pending(exported, tmp_path):
    payload = tmp_path / "web_benchmarks.json"
    payload.write_text(exported.read_text())
    site = _site(tmp_path, _ids(exported) + ["l2olap", "multimodel_later"])
    assert R.check_table_coverage(payload, site / R.PAGE_SOURCE, {"l2"}) == 0
    pending = json.loads(payload.read_text())["pending_tables"]
    assert set(pending) == {"l2olap", "multimodel_later"}
    assert all("measured" in why for why in pending.values())


def test_the_capability_table_is_pending_with_its_own_reason(exported, tmp_path):
    ids = [t for t in _ids(exported) if t != "multimodel"]
    payload = tmp_path / "web_benchmarks.json"
    doc = json.loads(exported.read_text())
    doc["tables"] = [t for t in doc["tables"] if t["id"] != "multimodel"]
    payload.write_text(json.dumps(doc))
    site = _site(tmp_path, ids + ["multimodel"])
    assert R.check_table_coverage(payload, site / R.PAGE_SOURCE, {"e2"}) == 0
    assert "capability summary" in json.loads(payload.read_text())["pending_tables"]["multimodel"]


def test_sync_copies_the_payload_to_the_site_data_file(exported, tmp_path, capsys):
    site = _site(tmp_path, _ids(exported))
    target = site / R.PAGE_DATA
    R.sync_payload(exported, target)
    assert target.read_bytes() == exported.read_bytes()
    assert "updated" in capsys.readouterr().out
    R.sync_payload(exported, target)
    assert "unchanged" in capsys.readouterr().out


def test_the_spec_inventory_is_the_payloads_table_list(exported, tmp_path):
    spec = tmp_path / "PAGE-SPEC.md"
    spec.write_text("# spec\n\n## Published tables (stale)\n\n| old |\n\n## Next section\n\nkept\n")
    R._rewrite_page_spec_inventory(exported, spec)
    text = spec.read_text()
    assert "## Next section\n\nkept" in text and "| old |" not in text
    assert sorted(re.findall(r"^\| `(\w+)` \|", text, flags=re.M)) == sorted(_ids(exported))
