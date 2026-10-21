"""What the exporter adds for 2026-11 rows, on the publish fixture: the served ArcadeDB client twin kept out of every headline
median and attached to the headline entry, the l4 plain-read columns, and the sentences that say what the rows stamp (the idle
hold, the sparse warm-up, the official driver).

Run with `python -m pytest test_export_client_twin.py -q` from this directory (needs numpy and pandas, as the exporter does).
"""
import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "publish_2611" / "results"
PIN = "261100fix"


def _run(script, results, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("BENCH_")}
    env.update({"BENCH_RESULTS_DIR": str(results), "BENCH_ENGINE_COMMIT": PIN, "PYTHONHASHSEED": "0"}, **extra)
    return subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=env, capture_output=True, text=True, timeout=900)


def _stage(dest):
    shutil.copytree(FIXTURE, dest)
    with gzip.open(dest / "runs.jsonl.gz", "rt") as src, open(dest / "runs.jsonl", "w") as out:
        shutil.copyfileobj(src, out)
    (dest / "runs.jsonl.gz").unlink()
    return dest


@pytest.fixture(scope="module")
def payloads(tmp_path_factory):
    """(payload exported from the freeze, payload exported from the same freeze plus the twin's rows)."""
    results = _stage(tmp_path_factory.mktemp("twin") / "results")
    assert _run("make_paper_tables.py", results).returncode == 0
    assert _run("export_web.py", results).returncode == 0
    plain = json.loads((results / "web_benchmarks.json").read_text())
    rows = list(csv.DictReader((results / "runs_paper.csv").open()))
    fields = list(rows[0])
    twins = [json.loads(l) for l in (results / "runs.jsonl").open() if l.strip()]
    twins = [r for r in twins if r.get("arcadedb_http_client_role") == "sensitivity" and not r.get("error")]
    assert twins, "the fixture carries the lean twin's rows"
    with (results / "runs_paper.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        for r in twins:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    assert _run("export_web.py", results).returncode == 0
    return plain, json.loads((results / "web_benchmarks.json").read_text())


def _table(p, tid):
    return next(t for t in p["tables"] if t["id"] == tid)


def test_the_twin_never_moves_a_headline_cell(payloads):
    plain, twinned = payloads
    for t in twinned["tables"]:
        want = {(e["backend"], e.get("scale")): e["metrics"] for e in _table(plain, t["id"])["entries"]}
        for e in t["entries"]:
            assert e["metrics"] == want[(e["backend"], e.get("scale"))], (t["id"], e["backend"])


def test_the_twin_rides_on_the_headline_entry_over_the_same_labels(payloads):
    _plain, p = payloads
    seen = set()
    for t in p["tables"]:
        for e in t["entries"]:
            twin = e.get("client_twin")
            if not twin:
                continue
            seen.add(t["id"])
            assert twin["client"] == "lean (requests)" and e["deployment"] in ("server", "all three") or t["id"] == "lifecycle"
            assert twin["metrics"] and set(twin["metrics"]) <= set(e["metrics"]), (t["id"], set(twin["metrics"]) - set(e["metrics"]))
            for stat in twin["metrics"].values():
                assert set(stat) == {"median", "min", "max", "n"}
    assert {"docs_oltp", "docs_olap", "l2", "l3s", "l4", "lifecycle"} <= seen
    assert not [e for t in p["tables"] for e in t["entries"] if "client_twin" in e and not e["is_arcadedb"]]


def test_the_page_names_the_official_driver_and_the_labelled_sensitivity(payloads):
    _plain, p = payloads
    text = " ".join(_table(p, "docs_oltp")["conditions"])
    assert "arcadedb-driver 0.2.0 (sync, httpx)" in text and "labelled sensitivity" in text and "lean (requests)" in text
    assert not any("client" in c and "labelled sensitivity" in c for c in _table(p, "durability")["conditions"])


def test_l4_prints_the_plain_read_beside_the_bulk_read(payloads):
    plain, _p = payloads
    t = _table(plain, "l4")
    for col in ("high-usage plain-read p50 ms", "per-host hourly plain-read p50 ms"):
        assert col in t["columns"]
        assert any(col in e["metrics"] for e in t["entries"])
    text = " ".join(t["conditions"])
    assert "Arrow table" in text and "plain-read columns" in text


def test_the_setup_and_the_sparse_table_say_what_the_rows_stamp(payloads):
    plain, _p = payloads
    assert "held out of their deep idle states" in plain["setup"]["cpu_idle_note"]
    assert "at 0 microseconds" in plain["setup"]["cpu_idle_note"]
    sparse = " ".join(_table(plain, "l3s")["conditions"])
    assert "1,000 untimed searches" in sparse and "the dataset's extra queries" in sparse
    dense = " ".join(_table(plain, "l3d")["conditions"])
    assert "index on the vector id" in dense
    glob = " ".join(plain["conditions"])
    assert "ArcadeDB embedded sets only the maximum heap" in glob


def test_the_exporter_refuses_another_selector(tmp_path):
    results = _stage(tmp_path / "results")
    proc = _run("export_web.py", results, BENCH_INSTRUMENT="2026-10")
    assert proc.returncode != 0 and "2026-11 rows only" in proc.stderr
