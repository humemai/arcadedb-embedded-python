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


def _native_overlays(results):
    """The native chain's overlay files: a native copy of each in-process arm's files, every pass stamped engine_backend=native."""
    n = 0
    for d in results.glob("dense_mp5_*"):
        for arm in ("fp32", "int8"):
            for fp in sorted(d.glob(f"mp_{arm}_b*.json")):
                passes = json.loads(fp.read_text())
                (d / fp.name.replace(f"mp_{arm}_b", f"mp_{arm}_native_b")).write_text(
                    json.dumps([dict(p, engine_backend="native") for p in passes]))
                n += 1
    for d in results.glob("sparse_mp_*"):
        for arm in ("arc_fp32", "arc_int8"):
            for fp in sorted(d.glob(f"sp_{arm}_*.json")):
                tier = fp.stem.rsplit("_", 1)[1]
                passes = json.loads(fp.read_text())
                (d / f"sp_{arm}_native_{tier}.json").write_text(json.dumps([dict(p, engine_backend="native") for p in passes]))
                n += 1
    assert n
    return n


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    """(payload of the old freeze, payload with native twins everywhere, payload with native twins in every lane but l2, the dir)."""
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    root = tmp_path_factory.mktemp("pair")
    base = _stage(root / "base")
    assert _run("make_paper_tables.py", base).returncode == 0
    out = []
    for name, keep in (("old", None), ("both", lambda r: True), ("partial", lambda r: r.get("lane") != "l2"), ("bare", lambda r: True)):
        d = root / name
        shutil.copytree(base, d)
        if keep:
            _with_native(d, keep)
        if name != "bare":                 # "bare": native rows but no native overlay files (the overlay is unstamped, so the JVM build)
            if keep:
                _native_overlays(d)
        done = _run("export_web.py", d)
        assert done.returncode == 0, done.stderr[-2000:]
        out.append(json.loads((d / "web_benchmarks.json").read_text()))
    return (out[0], out[1], out[2], root, out[3])


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


def test_a_stamped_overlay_stands_per_build_and_the_gate_passes_the_dense_table(pages):
    """An overlay belongs to the build that produced it: the native files (engine_backend=native on every pass) and the JVM files
    (no field: the JVM build) give each in-process dense arm two entries, and l3d no longer fails the build gate."""
    both = pages[1]
    emb = [e["backend"] for e in _t(both, "l3d")["entries"] if e.get("is_arcadedb") and e.get("deployment") == "embedded"]
    for prec in ("fp32", "int8"):
        assert f"ArcadeDB (embedded, {prec}, native build)" in emb and f"ArcadeDB (embedded, {prec}, JVM build)" in emb, emb
    assert PC._check_build_pair({"tables": [_t(both, "l3d")]}, []) == 0
    assert PC._check_build_pair(both, list(csv.DictReader((pages[3] / "both" / "runs_paper.csv").open()))) == 0


def test_an_unstamped_overlay_is_the_jvm_build_and_the_native_build_is_declared_not_measured(pages):
    """The default, chosen on purpose: an overlay file with no engine_backend is the JVM build (what every earlier overlay was). With
    native rows on the page and no native overlay, the dense embedded arms read JVM build, and the native twin is a declared absence."""
    bare = pages[4]
    t = _t(bare, "l3d")
    emb = [e for e in t["entries"] if e.get("is_arcadedb") and e.get("deployment") == "embedded" and e.get("precision") in ("fp32", "int8")]
    assert emb and {e["build"] for e in emb} == {"jvm"}                      # (the PQ arm comes from frozen rows, which have native twins)
    assert any("native build" in a["backend"] and a["kind"] == "not measured" and ("fp32" in a["backend"] or "int8" in a["backend"])
               for a in t["declared_absences"])
    assert PC._check_build_pair({"tables": [t]}, []) == 0


def test_the_sparse_second_pass_table_is_per_build_too(pages, monkeypatch):
    """The second-pass table reads sp_<arm>_<tier>.json (JVM, or unstamped) and sp_<arm>_native_<tier>.json (native), per build."""
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    import export_web as X
    d = pages[3] / "both"
    monkeypatch.setattr(X, "RESULTS", d)
    monkeypatch.setenv("BENCH_ENGINE_COMMIT", PIN)
    monkeypatch.setattr(X, "_SPLIT", True)
    t = X._sparse_multipass_table()
    assert t is not None
    emb = [e for e in t["entries"] if e.get("is_arcadedb") and e.get("deployment") == "embedded"]
    assert {e["build"] for e in emb} == {"native", "jvm"}
    assert all(AI.build_in_label(e["backend"]) == e["build"] for e in emb)
    monkeypatch.setattr(X, "_SPLIT", False)
    plain = X._sparse_multipass_table()
    assert {e["build"] for e in plain["entries"]} == {None}                              # an unsplit page reads the plain files only


def test_the_rows_behind_an_entry_are_that_builds_rows():
    """Notes that read the frozen rows behind an entry (heap, memory) read one build's rows for one build's entry."""
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    import export_web as X
    rows = [row("native", workload="oltp", heap_size="4g"), row("jvm", workload="oltp", heap_size="24g"),
            row(None, backend="arcadedb_graph_server", workload="oltp")]
    old = (X._FROZEN_ROWS, X._SPLIT)
    try:
        X._FROZEN_ROWS, X._SPLIT = rows, True
        nat = X._entry_rows({"backend": "ArcadeDB (embedded, native build)", "build": "native", "scale": "sf1"}, "l2", "oltp")
        jvm = X._entry_rows({"backend": "ArcadeDB (embedded, JVM build)", "build": "jvm", "scale": "sf1"}, "l2", "oltp")
        assert [r["heap_size"] for r in nat] == ["4g"] and [r["heap_size"] for r in jvm] == ["24g"]
    finally:
        X._FROZEN_ROWS, X._SPLIT = old


def test_a_native_cap_or_oom_never_censors_the_jvm_entry(monkeypatch):
    """Censored cells are keyed arm + build + size on a split page; an old run without a build is the JVM build."""
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    import export_web as X
    base = {"lane": "l2", "scale": "sf1", "workload": "oltp", "backend": "arcadedb_graph_embedded", "engine_commit": "abc123def"}
    log = [dict(base, engine_backend="native", error="timeout_after_900s"),
           dict(base, engine_backend="jvm", error=None, rc=0),
           dict(base, scale="sf10", error="timeout_after_900s"),                       # an old row: no field
           dict(base, scale="sf10", engine_backend="native", error=None, rc=0)]
    monkeypatch.delenv("BENCH_ENGINE_COMMIT", raising=False)                             # no pin: every row is in scope
    monkeypatch.setattr(X, "_run_log_rows", lambda: log)
    monkeypatch.setattr(X, "_rule_censored", lambda taken, clean: {})
    monkeypatch.setattr(X, "_CENSORED_CACHE", None)
    monkeypatch.setattr(X, "_SPLIT", True)
    keys = X._censored_cells()
    assert ("l2", "sf1", "arcadedb_graph_embedded@native", "oltp") in keys
    assert ("l2", "sf1", "arcadedb_graph_embedded@jvm", "oltp") not in keys              # the JVM twin ran clean
    assert ("l2", "sf10", "arcadedb_graph_embedded@jvm", "oltp") in keys                 # unstamped old row: the JVM build
    assert ("l2", "sf10", "arcadedb_graph_embedded@native", "oltp") not in keys
    monkeypatch.setattr(X, "_CENSORED_CACHE", None)
    monkeypatch.setattr(X, "_SPLIT", False)
    assert all("@" not in k[2] for k in X._censored_cells())                             # an unsplit page keys as it always did


def test_a_killed_cell_row_names_the_build_of_its_wheel():
    killed = {"lane": "l2", "backend": "arcadedb_graph_embedded", "error": "timeout_after_900s"}
    assert AI.stamp_build(dict(killed), "native")["engine_backend"] == "native"
    assert AI.build_of(AI.stamp_build(dict(killed), "native")) == "native"
    assert AI.build_of(killed) == "jvm"                                                  # unstamped: the default
    served = dict(killed, backend="arcadedb_graph_server")
    assert "engine_backend" not in AI.stamp_build(served, "native")                      # a served arm has no build
    assert AI.stamp_build(dict(killed, engine_backend="jvm"), "native")["engine_backend"] == "jvm"


def test_a_partial_native_overlay_is_refused_and_a_complete_or_absent_one_is_not(tmp_path):
    import make_paper_tables as M
    M._refuse_partial_native(str(tmp_path), "x")                                          # none: nothing to refuse
    for arm in M.MP_INPROCESS_ARMS:
        for b in range(1, M.MP_BUILDS + 1):
            (tmp_path / f"mp_{arm}_native_b{b}.json").write_text("[]")
    M._refuse_partial_native(str(tmp_path), "x")                                          # all of them
    (tmp_path / "mp_int8_native_b2.json").unlink()
    with pytest.raises(SystemExit) as e:
        M._refuse_partial_native(str(tmp_path), "dense_mp5_x")
    assert "partial" in str(e.value)


def test_the_pinned_sparse_path_validates_each_build_and_takes_the_jvm_one_unless_told(monkeypatch):
    import make_paper_tables as M

    def rows(build, n=5):
        return [dict(row(build, backend="arcadedb_sparse_embedded", lane="l3s", scale=t, rep=i), engine_commit="abc123def0")
                for t in ("tiny", "small", "medium") for i in range(n)]
    monkeypatch.setenv("BENCH_ENGINE_COMMIT", "abc123def0")
    monkeypatch.delenv(AI.ENV, raising=False)
    monkeypatch.setattr(M, "load_canonical", lambda *a, **k: rows("native") + rows("jvm"))
    got = M._pinned_sparse_rows()
    assert got and {AI.build_of(r) for rs in got.values() for r in rs} == {"jvm"}
    monkeypatch.setenv(AI.ENV, "native")
    assert {AI.build_of(r) for rs in M._pinned_sparse_rows().values() for r in rs} == {"native"}
    monkeypatch.delenv(AI.ENV)
    monkeypatch.setattr(M, "load_canonical", lambda *a, **k: rows("native", 3) + rows("jvm"))
    assert M._pinned_sparse_rows() is None                                                # a short native build is not published beside a full JVM one


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


def test_a_censored_native_cell_becomes_a_native_row_and_leaves_the_jvm_entry(monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    import export_web as X
    base = {"lane": "l2", "scale": "sf1", "workload": "oltp", "backend": "arcadedb_graph_embedded", "engine_commit": "abc123def"}
    log = [dict(base, engine_backend="native", error="timeout_after_900s"), dict(base, engine_backend="jvm", error=None, rc=0)]
    monkeypatch.delenv("BENCH_ENGINE_COMMIT", raising=False)
    monkeypatch.setattr(X, "_run_log_rows", lambda: log)
    monkeypatch.setattr(X, "_rule_censored", lambda taken, clean: {})
    monkeypatch.setattr(X, "_CENSORED_CACHE", None)
    monkeypatch.setattr(X, "_SPLIT", True)
    measured = {"backend": "ArcadeDB (embedded, JVM build)", "build": "jvm", "backend_key": "arcadedb_graph_embedded", "scale": "sf1",
                "is_arcadedb": True, "metrics": {"point p50 ms": {"median": 1.0}}}
    table = {"id": "l2", "entries": [measured], "columns": ["point p50 ms"]}
    marked, _marks = X._censored_entries(table)
    assert [(m["backend"], m["build"]) for m in marked] == [("ArcadeDB (embedded, native build)", "native")]
    assert table["entries"] == [measured]                                                 # the JVM entry is untouched
