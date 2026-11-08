"""What the exporter adds for 2026-11 rows, on the publish fixture: every served ArcadeDB headline cell comes from the
benchmark's own HTTP client (DECISIONS #268, #285), the vendor's driver is neither printed nor named, the cell of the arm with
no lean row is dropped and said so, the l4 plain-read columns, and the sentences that say what the rows stamp (the idle hold,
the sparse warm-up).

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
LEAN = "lean_http (http.client, keep-alive)"   # lean_http.LEAN_NAME


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
def built(tmp_path_factory):
    """(results dir, the paper-table run's stdout, the payload exported from the freeze)."""
    results = _stage(tmp_path_factory.mktemp("lean") / "results")
    proc = _run("make_paper_tables.py", results)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert _run("export_web.py", results).returncode == 0
    return results, proc.stdout, json.loads((results / "web_benchmarks.json").read_text())


@pytest.fixture(scope="module")
def payloads(built):
    """(payload, payload): the old two-payload fixture's shape, for the tests below that read the plain one."""
    return built[2], built[2]


def _table(p, tid):
    return next(t for t in p["tables"] if t["id"] == tid)


def _raw_rows(results):
    return [json.loads(l) for l in (results / "runs.jsonl").open() if l.strip()]


def test_the_fixture_holds_both_clients_and_the_freeze_keeps_only_the_lean_rows(built):
    results, out, _p = built
    raw = [r for r in _raw_rows(results) if r.get("arcadedb_http_client")]
    assert {r["arcadedb_http_client_role"] for r in raw} == {"headline", "sensitivity"}
    assert any("arcadedb-driver" in r["arcadedb_http_client"] for r in raw)
    frozen = [r for r in csv.DictReader((results / "runs_paper.csv").open()) if r.get("arcadedb_http_client")]
    assert frozen and {r["arcadedb_http_client"] for r in frozen} == {LEAN}
    # the arm with no lean row has no frozen row at all, and the freeze says what it set aside
    assert not [r for r in csv.DictReader((results / "runs_paper.csv").open()) if r["backend"] == "arcadedb_imgdefaults_server"]
    assert "not measured through the benchmark's own HTTP client" in out and "arcadedb_imgdefaults_server" in out


def test_no_twin_and_no_vendor_driver_anywhere_on_the_page(built):
    _results, _out, p = built
    text = json.dumps(p)
    assert "client_twin" not in text
    for banned in ("arcadedb-driver", "official driver", "official Python client", "sensitivity", "httpx"):
        assert banned not in text, banned
    import page_check
    assert page_check._check_banned_terms(p) == 0


def test_the_page_names_the_benchmarks_own_client_and_says_the_others_differ(built):
    _results, _out, p = built
    for tid in ("docs_oltp", "docs_olap", "l2", "l3s", "l4", "lifecycle"):
        text = " ".join(_table(p, tid)["conditions"])
        assert LEAN in text and "benchmarks/experiments/lean_http.py" in text, tid
        assert "vendors' own Python clients" in text and "client weight differs between the served engines" in text, tid
        assert "lean_http.py" in " ".join(_table(p, tid)["source_urls"]), tid


def test_the_arm_without_a_lean_row_is_not_printed_and_the_table_says_so(built):
    _results, _out, p = built
    t = _table(p, "docs_oltp")
    assert not [e for e in t["entries"] if e["backend_key"] == "arcadedb_imgdefaults_server"]
    label = "ArcadeDB (server, image JVM defaults)"
    text = " ".join(t["conditions"])
    assert f"{label} is not printed: it was not measured through the benchmark's own HTTP client" in text
    assert any(a["backend"] == label and a["kind"] == "withheld" for a in t["declared_absences"])
    assert "image's own JVM settings" not in text


def test_the_exporter_refuses_a_frozen_row_of_the_other_client(built, tmp_path):
    results, _out, _p = built
    bad = tmp_path / "results"
    shutil.copytree(results, bad)
    rows = list(csv.DictReader((bad / "runs_paper.csv").open()))
    served = next(r for r in rows if r["backend"] == "arcadedb_server" and r.get("arcadedb_http_client"))
    served["arcadedb_http_client"] = "arcadedb-driver 0.2.0 (sync, httpx)"
    with (bad / "runs_paper.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    proc = _run("export_web.py", bad)
    assert proc.returncode != 0 and "not measured through the benchmark's own HTTP client" in proc.stderr


def test_the_exporter_refuses_an_overlay_of_the_other_client(built, tmp_path):
    results, _out, _p = built
    bad = tmp_path / "results"
    shutil.copytree(results, bad)
    fp = bad / f"dense_mp5_{PIN}" / "mp_arcsrv_b1.json"
    passes = json.loads(fp.read_text())
    for r in passes:
        r["arcadedb_http_client"] = "arcadedb-driver 0.2.0 (sync, httpx)"
    fp.write_text(json.dumps(passes))
    proc = _run("export_web.py", bad)
    assert proc.returncode != 0 and "overlay file(s) were not measured through the benchmark's own HTTP client" in proc.stderr


def test_the_banned_term_gate_flags_the_driver_and_nothing_else():
    import page_check
    assert page_check._check_banned_terms({"conditions": ["through the official ArcadeDB Python driver"]}) == 1
    assert page_check._check_banned_terms({"tables": [{"conditions": ["arcadedb-driver 0.2.0"]}]}) == 1
    assert page_check._check_banned_terms({"conditions": ["through the benchmark's own minimal HTTP client"]}) == 0


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
    # #456: the served arms leave -Xms unset too, so the sentence names both deployments
    assert "ArcadeDB, embedded and served, sets only the maximum heap" in glob


def test_the_exporter_refuses_another_selector(tmp_path):
    results = _stage(tmp_path / "results")
    proc = _run("export_web.py", results, BENCH_INSTRUMENT="2026-10")
    assert proc.returncode != 0 and "2026-11" in proc.stderr
