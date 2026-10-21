"""The publish side, end to end, on a small 2026-11 fixture (DECISIONS #196).

`fixtures/publish_2611/` holds real 2026-10 rows restamped `instrument: 2026-11`, with the row fields the 2026-11 instrument adds
(see build_fixture.py there). The test freezes them with make_paper_tables.py and exports the page payload with export_web.py,
each as a separate process the way a publish runs them, against a copy of the fixture in a temp directory
(`BENCH_RESULTS_DIR`), and then checks the files they wrote. It proves the one mode the publish side has: 2026-11 rows in,
`runs_paper.csv` and `web_benchmarks.json` out, and every other instrument refused.

Run with `python -m pytest test_publish_2611_e2e.py -q` from this directory (needs numpy and pandas, as the exporter does).
"""
import csv
import gzip
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "publish_2611" / "results"
PIN = "261100fix"


def _env(results: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("BENCH_") or k in ("BENCH_ENGINE_COMMIT_SOURCE",)}
    env.update({"BENCH_RESULTS_DIR": str(results), "BENCH_ENGINE_COMMIT": PIN, "PYTHONHASHSEED": "0"})
    env.update(extra)
    return env


def _run(script: str, results: Path, **extra) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=_env(results, **extra),
                          capture_output=True, text=True, timeout=900)


def _stage(dest: Path) -> Path:
    """A writable copy of the fixture with runs.jsonl unpacked."""
    shutil.copytree(FIXTURE, dest)
    with gzip.open(dest / "runs.jsonl.gz", "rt") as src, open(dest / "runs.jsonl", "w") as out:
        shutil.copyfileobj(src, out)
    (dest / "runs.jsonl.gz").unlink()
    return dest


@pytest.fixture(scope="module")
def published(tmp_path_factory):
    results = _stage(tmp_path_factory.mktemp("publish2611") / "results")
    freeze = _run("make_paper_tables.py", results)
    export = _run("export_web.py", results)
    return {"results": results, "freeze": freeze, "export": export,
            "payload": json.loads((results / "web_benchmarks.json").read_text())
            if (results / "web_benchmarks.json").exists() else None}


def _fixture_rows():
    with gzip.open(FIXTURE / "runs.jsonl.gz", "rt") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _table(payload, table_id):
    return next(t for t in payload["tables"] if t["id"] == table_id)


def test_the_freeze_and_the_export_run_and_write_the_one_set_of_names(published):
    assert published["export"].returncode == 0, published["export"].stderr[-2000:]
    names = {p.name for p in published["results"].iterdir()}
    assert {"runs_paper.csv", "web_benchmarks.json", "generated"} <= names
    # one mode, one set of names: no preview, October or skeleton files
    assert not {n for n in names if n.endswith("_oct.csv") or n.endswith("_next.json") or "skeleton" in n or n == "generated_oct"}


def test_every_frozen_row_is_2026_11(published):
    rows = list(csv.DictReader((published["results"] / "runs_paper.csv").open()))
    assert len(rows) > 300
    assert {r["instrument"] for r in rows} == {"2026-11"}


def test_the_payload_names_its_instrument_and_its_freeze(published):
    p = published["payload"]
    assert p["instrument"] == "2026-11"
    assert p["source"].endswith("results/runs_paper.csv")
    assert p["skeleton"] is False
    assert {t["instrument"] for t in p["tables"]} == {"2026-11"}


def test_the_payload_has_the_page_tables(published):
    ids = {t["id"] for t in published["payload"]["tables"]}
    assert {"l3s", "l3d", "l2", "e2", "e2atom", "l4", "lifecycle", "durability", "e4", "docs_oltp", "docs_olap",
            "multimodel"} <= ids
    for t in published["payload"]["tables"]:
        assert t["entries"], t["id"]
        for e in t["entries"]:
            assert e["metrics"], (t["id"], e.get("backend"))


def test_the_payload_text_names_no_older_instrument(published):
    text = (published["results"] / "web_benchmarks.json").read_text()
    for old in ("2026-10", "2026-09"):
        assert old not in text, old


def test_every_table_with_memory_has_the_per_phase_column(published):
    t = _table(published["payload"], "docs_olap")
    assert all("owned memory after queries GiB" in e["metrics"] for e in t["entries"])


def test_the_dense_table_headlines_latency_at_matched_recall(published):
    t = _table(published["payload"], "l3d")
    labels = set().union(*(e["metrics"] for e in t["entries"]))
    assert {"p50 ms at recall 0.95", "p99 ms at recall 0.95", "ef or nProbe at recall 0.95",
            "p50 ms at recall 0.90", "p50 ms at recall 0.99"} <= labels
    rows = [r for r in _fixture_rows() if r["lane"] == "l3d" and r["backend"] == "arcadedb_dense_embedded"
            and r.get("matched_r095_p50_ms") is not None]
    want = statistics.median(r["matched_r095_p50_ms"] for r in rows)
    entry = next(e for e in t["entries"] if e["backend_key"] == "arcadedb_dense_embedded")
    assert entry["metrics"]["p50 ms at recall 0.95"]["median"] == pytest.approx(want, rel=1e-3)
    assert entry["beam_curve"]["kind"] == "ef" and len(entry["beam_curve"]["points"]) == 4


def test_the_served_arcadedb_twin_row_is_not_in_the_headline(published):
    # every served ArcadeDB cell has a lean twin (role "sensitivity", 30 percent faster); the headline cell is the median of
    # the official-client rows alone
    t = _table(published["payload"], "docs_oltp")
    rows = [r for r in _fixture_rows() if r["lane"] == "l1tpc" and r["backend"].startswith("arcadedb") and "server" in r["backend"]
            and r.get("workload") == "oltp" and r.get("durability_class") == "relaxed"]
    assert rows and {r["arcadedb_http_client_role"] for r in rows} == {"headline", "sensitivity"}
    head = [r for r in rows if r["arcadedb_http_client_role"] == "headline"]
    key = next(k for k in head[0] if k.endswith("_p50_ms") and isinstance(head[0][k], (int, float)))
    entry = next(e for e in t["entries"] if e["backend_key"] == head[0]["backend"])
    got = [m["median"] for m in entry["metrics"].values() if isinstance(m, dict) and "median" in m]
    want = statistics.median(r[key] for r in head if r.get("scale") == entry["scale"])
    assert any(g == pytest.approx(want, rel=1e-3) for g in got), (key, want, got[:8])


def test_the_paper_tables_are_written_beside_the_freeze(published):
    tables = published["results"] / "generated" / "tables"
    assert (tables / "t2_tabular.tex").exists() and (tables / "t3_graph.tex").exists()
    assert "ArcadeDB" in (tables / "t3_graph.tex").read_text()


@pytest.mark.parametrize("stamp", ["2026-10", "2026-09", ""])
def test_a_row_of_another_instrument_is_refused_with_a_clear_message(tmp_path, stamp):
    results = _stage(tmp_path / "results")
    rows = _fixture_rows()
    rows[0]["instrument"] = stamp
    (results / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    proc = _run("make_paper_tables.py", results)
    assert proc.returncode != 0
    assert "2026-11" in proc.stderr and "REFUSING" in proc.stderr


def test_the_old_selector_is_refused(tmp_path):
    results = _stage(tmp_path / "results")
    proc = _run("make_paper_tables.py", results, BENCH_INSTRUMENT="2026-10")
    assert proc.returncode != 0
    assert "2026-11" in proc.stderr


def test_the_exporter_alone_refuses_an_old_row(tmp_path, published):
    results = tmp_path / "results"
    shutil.copytree(published["results"], results)
    frozen = results / "runs_paper.csv"
    rows = list(csv.DictReader(frozen.open()))
    rows[0]["instrument"] = "2026-10"
    with frozen.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    proc = _run("export_web.py", results)
    assert proc.returncode != 0
    assert "2026-11" in proc.stderr
