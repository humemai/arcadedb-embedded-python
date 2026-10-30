"""The page shows ArcadeDB's native build and JVM build side by side, as two arms of one release.

Run with `python -m pytest test_build_pair_page.py -q` from this directory (the exporter tests need numpy and pandas and stage the
publish_2611 fixture, like test_export_client_twin.py). The unit tests need neither. What each test proves is in its docstring.
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
sys.path.insert(0, str(HERE))

import arm_identity as AI  # noqa: E402
import page_check as PC  # noqa: E402

FIXTURE = HERE / "fixtures" / "publish_2611" / "results"
PIN = "261100fix"
V = "26.11.1.dev0"


def row(build="__absent__", backend="arcadedb_graph_embedded", **kw):
    r = {"lane": "l2", "scale": "sf1", "workload": "oltp", "backend": backend, "engine_version": V, "engine_commit": "abc123def"}
    if build != "__absent__":
        r["engine_backend"] = build
    r.update(kw)
    return r


# ------------------------------------------------------------------ arm_identity: what splits a page, what labels it
def test_a_freeze_of_old_rows_is_not_split_and_a_native_row_splits_it():
    old = [row(), row(backend="arcadedb_graph_server"), row("", backend="arcadedb_graph_embedded"), row("jvm")]
    assert not AI.splits_page(old)                                      # empty field read back from the CSV is the JVM build
    assert AI.builds_in(old) == {"jvm"}
    assert AI.splits_page(old + [row("native")]) and AI.builds_in(old + [row("native")]) == {"native", "jvm"}
    assert AI.splits_page([row("native")])                              # native only: an unlabelled arm would read as the JVM build
    assert not AI.splits_page([row("native", backend="arcadedb_graph_server"), row(backend="qdrant_dense")])


def test_an_empty_engine_backend_from_the_csv_is_the_jvm_build_for_in_process_arms_only():
    assert AI.build_of(row("")) == "jvm" and AI.build_of(row(None)) == "jvm"
    assert AI.build_of(row("", backend="arcadedb_graph_server")) is None
    assert AI.build_of(row("", backend="qdrant_dense")) is None


def test_both_builds_stay_in_a_freeze_unless_one_is_chosen():
    rows = [row("native"), row("jvm"), row(None, backend="arcadedb_graph_server")]
    assert AI.select_build(rows, None) == rows                          # the page shows both: nothing is refused or dropped
    assert [AI.build_of(r) for r in AI.select_build(rows, "native") if AI.in_process(r)] == ["native"]
    assert len(AI.select_build(rows, "jvm")) == 2


@pytest.mark.parametrize("label", ["ArcadeDB (embedded)", "ArcadeDB (embedded, GAV)", "ArcadeDB (one transaction)", "ArcadeDB"])
@pytest.mark.parametrize("build", ["native", "jvm"])
def test_the_build_goes_last_in_the_label_and_comes_off_again(label, build):
    got = AI.build_label(label, build)
    assert got.endswith(f"{AI.BUILD_NAMES[build]})") and AI.build_in_label(got) == build and AI.strip_build(got) == label
    assert AI.build_in_label(label) is None and AI.strip_build(label) == label


def test_the_two_labels_of_one_arm_differ_only_in_the_build():
    assert AI.build_label("ArcadeDB (embedded)", "native") == "ArcadeDB (embedded, native build)"
    assert AI.build_label("ArcadeDB (embedded)", "jvm") == "ArcadeDB (embedded, JVM build)"
    # "native" is also a storage path in the time-series lane; the build says "build" so the two never read alike
    assert AI.build_label("ArcadeDB (embedded, native time series)", "native") == "ArcadeDB (embedded, native time series, native build)"


# ------------------------------------------------------------------ one engine commit
def test_two_builds_of_one_commit_pass_and_a_single_build_has_nothing_to_compare():
    assert AI.pair_problems([row("native"), row("jvm"), row(None, backend="arcadedb_graph_server")]) == []
    assert AI.pair_problems([row("native"), row("native", engine_commit="other")]) == []


def test_two_builds_naming_different_engines_are_refused():
    bad_v = AI.pair_problems([row("native"), row("jvm", engine_version="26.11.2.dev0")])
    assert len(bad_v) == 1 and "engine_version" in bad_v[0]
    bad_c = AI.pair_problems([row("native"), row("jvm", engine_commit="fff000999")])
    assert len(bad_c) == 1 and "engine_commit" in bad_c[0]
    assert len(AI.pair_problems([row("native"), row("jvm", engine_version="x", engine_commit="y")])) == 2


# ------------------------------------------------------------------ the gate over a payload
def entry(label, build, version="arcadedb 26.11.1 (abc123def)", key="arcadedb_graph_embedded", scale="sf1"):
    return {"backend": label, "build": build, "backend_key": key, "is_arcadedb": True, "scale": scale, "version_name": version}


def payload(entries, absences=()):
    return {"tables": [{"id": "l2", "entries": list(entries), "declared_absences": list(absences)}]}


NATIVE = entry("ArcadeDB (embedded, native build)", "native")
JVM = entry("ArcadeDB (embedded, JVM build)", "jvm")


def test_the_gate_passes_a_pair_of_one_release_and_a_page_with_no_builds(capsys):
    assert PC._check_build_pair(payload([NATIVE, JVM]), [row("native"), row("jvm")]) == 0
    old = payload([{"backend": "ArcadeDB (embedded)", "build": None, "backend_key": "arcadedb_graph_embedded", "is_arcadedb": True}])
    assert PC._check_build_pair(old, [row()]) == 0                      # an old freeze: nothing to pair


def test_the_gate_fails_when_the_builds_name_different_engines(capsys):
    assert PC._check_build_pair(payload([NATIVE, dict(JVM, version_name="arcadedb 26.11.1 (fff000999)")]), []) == 1
    assert "VERSION" in capsys.readouterr().out
    assert PC._check_build_pair(payload([NATIVE, JVM]), [row("native"), row("jvm", engine_commit="fff000999")]) == 1
    assert "COMMIT" in capsys.readouterr().out


def test_the_gate_fails_when_one_build_is_missing_without_a_declaration(capsys):
    assert PC._check_build_pair(payload([NATIVE]), []) == 1
    assert "ONEBUILD" in capsys.readouterr().out
    assert PC._check_build_pair(payload([JVM]), []) == 1


def test_a_missing_build_that_the_page_declares_not_measured_passes(capsys):
    absence = {"backend": "ArcadeDB (embedded, JVM build)", "column": None, "kind": "not measured", "why": "x"}
    assert PC._check_build_pair(payload([NATIVE], [absence]), []) == 0
    assert PC._check_build_pair(payload([NATIVE], [dict(absence, backend="ArcadeDB (embedded)")]), []) == 0   # the bare arm covers both
    other = dict(absence, backend="ArcadeDB (server)")
    assert PC._check_build_pair(payload([NATIVE], [other]), []) == 1                                          # another arm's declaration does not


def test_the_gate_fails_an_in_process_arm_that_names_no_build_on_a_page_that_does(capsys):
    assert PC._check_build_pair(payload([NATIVE, JVM, entry("ArcadeDB (embedded, fp32)", None)]), []) == 1
    assert "NOBUILD" in capsys.readouterr().out
    served = entry("ArcadeDB (server)", None, key="arcadedb_graph_server")
    assert PC._check_build_pair(payload([NATIVE, JVM, served]), []) == 0                                      # one served arm, no build


# ------------------------------------------------------------------ the exporter, on the publish fixture
def _stage(dest):
    shutil.copytree(FIXTURE, dest)
    with gzip.open(dest / "runs.jsonl.gz", "rt") as src, open(dest / "runs.jsonl", "w") as out:
        shutil.copyfileobj(src, out)
    (dest / "runs.jsonl.gz").unlink()
    return dest


def _run(script, results):
    env = {k: v for k, v in os.environ.items() if not k.startswith("BENCH_")}
    env.update({"BENCH_RESULTS_DIR": str(results), "BENCH_ENGINE_COMMIT": PIN, "PYTHONHASHSEED": "0"})
    return subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=env, capture_output=True, text=True, timeout=900)


def _with_native(results, keep=lambda r: True, commit=None):
    """Rewrite the freeze: every in-process ArcadeDB row gains a native twin (for the rows `keep` accepts)."""
    rows = list(csv.DictReader((results / "runs_paper.csv").open()))
    fields = list(rows[0]) + (["engine_backend"] if "engine_backend" not in rows[0] else [])
    twins = []
    for r in rows:
        if AI.in_process(r) and keep(r):
            t = dict(r, engine_backend="native")
            if commit:
                t["engine_commit"] = commit
            twins.append(t)
    assert twins
    with (results / "runs_paper.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows + twins)


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    """(payload of the old freeze, payload with native twins everywhere, payload with native twins in every lane but l2, the dir)."""
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    root = tmp_path_factory.mktemp("pair")
    base = _stage(root / "base")
    assert _run("make_paper_tables.py", base).returncode == 0
    out = []
    for name, keep in (("old", None), ("both", lambda r: True), ("partial", lambda r: r.get("lane") != "l2")):
        d = root / name
        shutil.copytree(base, d)
        if keep:
            _with_native(d, keep)
        done = _run("export_web.py", d)
        assert done.returncode == 0, done.stderr[-2000:]
        out.append(json.loads((d / "web_benchmarks.json").read_text()))
    return (*out, root)


def _t(p, tid):
    return next(t for t in p["tables"] if t["id"] == tid)


def _inproc(t):
    return [e for e in t["entries"] if e.get("is_arcadedb") and "server" not in e["backend"]]


def test_an_old_freeze_renders_exactly_as_before(pages):
    old = pages[0]
    for t in old["tables"]:
        assert all(e.get("build") is None for e in t["entries"]), t["id"]
        assert not any("build" in e["backend"] for e in t["entries"] if e.get("is_arcadedb")), t["id"]
        assert not [a for a in t.get("declared_absences", []) if a["kind"] == "not measured"], t["id"]


def test_every_in_process_arm_of_a_lane_table_stands_twice_native_first(pages):
    both = pages[1]
    for tid in ("docs_oltp", "docs_olap", "l2", "e2", "l4"):
        arms = [e["backend"] for e in _inproc(_t(both, tid))]
        assert arms and all(AI.build_in_label(a) for a in arms), (tid, arms)
        bare = [AI.strip_build(a) for a in arms]
        for b in set(bare):
            i = [k for k, x in enumerate(bare) if x == b]
            labels = [arms[k] for k in i]
            assert any(AI.build_in_label(x) == "native" for x in labels) and any(AI.build_in_label(x) == "jvm" for x in labels)
            assert AI.build_in_label(arms[i[0]]) == "native"            # the default install first
    assert [e["backend"] for e in _t(both, "l2")["entries"] if e.get("is_arcadedb")][:2] == [
        "ArcadeDB (embedded, native build)", "ArcadeDB (embedded, JVM build)"]


def test_the_served_arm_stays_one_row_and_both_builds_name_one_engine(pages):
    both = pages[1]
    for tid in ("docs_oltp", "l2"):
        t = _t(both, tid)
        served = [e for e in t["entries"] if e.get("is_arcadedb") and e.get("deployment") == "server"]
        assert served and all(e["build"] is None and "build" not in e["backend"] for e in served)
        names = {e["version_name"] for e in _inproc(t)}
        assert len(names) == 1, names
    rows = list(csv.DictReader((pages[3] / "both" / "runs_paper.csv").open()))
    assert PC._check_build_pair({"tables": [t for t in both["tables"] if t["id"] != "l3d"]}, rows) == 0


def test_the_dense_overlay_arms_name_no_build_and_the_gate_says_so(pages):
    """OPEN: the dense multipass overlay (files, not frozen rows) carries no engine_backend, so its fp32 and int8 arms print without a
    build. On a page that names builds the gate refuses that, which is the loud behaviour wanted until the overlay says its build."""
    both = pages[1]
    assert PC._check_build_pair({"tables": [_t(both, "l3d")]}, []) > 0


def test_neither_build_is_a_median_over_both(pages):
    old, both = pages[0], pages[1]
    one = {(e["scale"], e["metrics"]["new-order p50 ms"]["n"]) for e in _inproc(_t(old, "docs_oltp")) if "new-order p50 ms" in e["metrics"]}
    two = {(e["scale"], e["metrics"]["new-order p50 ms"]["n"]) for e in _inproc(_t(both, "docs_oltp")) if "new-order p50 ms" in e["metrics"]}
    assert one and two == one                                           # twins of the same rows: each build keeps the old n, none doubles it


def test_a_lane_with_one_build_prints_the_other_as_not_measured_and_the_gate_reads_it(pages):
    part = pages[2]
    t = _t(part, "l2")
    assert [AI.build_in_label(e["backend"]) for e in _inproc(t)] == ["jvm"] * len(_inproc(t))
    absent = [a for a in t["declared_absences"] if a["kind"] == "not measured"]
    assert absent and all("native build" in a["backend"] for a in absent)
    assert any("native build was not measured for" in c for c in t["conditions"])
    assert not [a for a in _t(part, "docs_oltp").get("declared_absences", []) if a["kind"] == "not measured"]
    assert PC._check_build_pair({"tables": [t]}, []) == 0
    stripped = dict(t, declared_absences=[a for a in t["declared_absences"] if a["kind"] != "not measured"])
    assert PC._check_build_pair({"tables": [_t(part, "docs_oltp"), stripped]}, []) > 0       # undeclared, the page is refused


def test_a_freeze_whose_builds_name_two_commits_is_not_exported(pages):
    d = pages[3] / "mixed"
    shutil.copytree(pages[3] / "base", d)
    _with_native(d, commit="fffffffff")
    done = _run("export_web.py", d)
    assert done.returncode != 0 and "engine_commit" in (done.stderr + done.stdout)
