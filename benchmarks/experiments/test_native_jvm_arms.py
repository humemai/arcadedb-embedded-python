"""One release measured on both ArcadeDB builds: the identity of an arm is (engine_version, build), not engine_version alone.

Run with `python -m pytest test_native_jvm_arms.py -q` from this directory. Nothing here times a cell, starts an engine or builds an image
(docker is not run; the engine is a fake). What each test proves is named in its docstring.
"""
import subprocess
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_identity as AI  # noqa: E402
import engine_pin as E  # noqa: E402
import _arcadedb_import as AIMP  # noqa: E402

V = "26.11.1.dev0"


def row(build="__absent__", backend="arcadedb_sparse_embedded", rep=1, ts="2026-11-01T00:00:00+00:00", **kw):
    r = {"lane": "l3s", "scale": "tiny", "n_docs": 100000, "workload": "search", "backend": backend, "rep": rep, "ts_utc": ts,
         "engine_version": V, "gav": None}
    if build != "__absent__":
        r["engine_backend"] = build
    r.update(kw)
    return r


# ------------------------------------------------------------------ arm_identity
def test_build_of_old_rows_are_the_jvm_build_for_in_process_and_served_arms_and_comparators_have_none():
    assert AI.build_of(row()) == "jvm"                                   # before the field existed
    assert AI.build_of(row("native")) == "native" and AI.build_of(row("jvm")) == "jvm"
    assert AI.build_of(row(None, backend="arcadedb_sparse_server")) == "jvm"    # served rows carry the server's build since #222; old ones = JVM
    assert AI.build_of(row(backend="arcadedb_sparse_server")) == "jvm"          # an older served row is the JVM server, the only one there was
    assert AI.build_of(row("native", backend="arcadedb_sparse_server")) == "native"
    assert AI.build_of(row(None, backend="qdrant_sparse")) is None
    assert AI.build_of(row(backend="arcadedb_http_client")) is None
    assert AI.build_of(row(backend="arcadedb_imgdefaults_server")) is None      # the JVM image-defaults arm has no native counterpart


def test_the_same_release_on_two_builds_is_two_identities():
    a, b = row("native"), row("jvm")
    assert AI.arm_identity(a) != AI.arm_identity(b) and a["engine_version"] == b["engine_version"]
    assert AI.arm_identity(row()) == AI.arm_identity(row("jvm"))        # an old row and a new JVM row are one arm


def test_both_builds_stay_unless_one_is_chosen():
    """Both builds are two arms of one page (test_build_pair_page.py), so a freeze no longer refuses a cell that holds both."""
    rows = [row("native"), row("jvm"), row("native", backend="qdrant_sparse"), row(None, backend="arcadedb_sparse_server")]
    assert AI.select_build(rows, None) == rows
    nat = AI.select_build(rows, "native")
    assert [AI.build_of(r) for r in nat if AI.in_process(r)] == ["native"]
    assert len(nat) == 2                                                 # comparators stay; the served arm of the other build leaves with it
    assert [r["backend"] for r in AI.select_build(rows, "jvm")].count("arcadedb_sparse_embedded") == 1


def test_one_build_needs_no_choice_and_a_bad_choice_is_an_error(monkeypatch):
    rows = [row("native", rep=1), row("native", rep=2)]
    assert AI.select_build(rows, None) == rows
    monkeypatch.setenv(AI.ENV, "native")
    assert AI.wanted_build() == "native"
    monkeypatch.setenv(AI.ENV, "graal")
    with pytest.raises(SystemExit):
        AI.wanted_build()


def test_pooling_two_builds_in_one_entry_is_refused():
    with pytest.raises(SystemExit):
        AI.refuse_pooled_builds([row("native"), row("jvm")], "sparse/tiny")
    assert AI.refuse_pooled_builds([row("jvm"), row()], "x")


# ------------------------------------------------------------------ the canonical key
def test_the_freeze_key_and_the_merge_key_keep_both_builds_of_a_cell():
    """Under the old key the later build replaced the other on ts_utc; both keys now carry the build."""
    import merge_campaign as MC
    rows = [row("native", ts="2026-11-01T00:00:00+00:00"), row("jvm", ts="2026-11-02T00:00:00+00:00")]
    assert MC.key(rows[0]) != MC.key(rows[1])
    assert len(MC.canonicalise(rows)) == 2
    assert MC.key(row()) == MC.key(row("jvm"))                           # old rows still collapse with new JVM rows
    import make_paper_tables as M
    import inspect
    assert "_AI.build_of(r)" in inspect.getsource(M.load_canonical)
    assert MC.version_of(row("native")).endswith("native") and MC.version_of(row("jvm")) == V


# ------------------------------------------------------------------ tags and wheels
def test_the_build_comes_from_the_wheel_file_name():
    assert E.backend_from_wheel(f"/d/arcadedb-{V}-py3-none-manylinux_2_28_x86_64.whl") == "native"
    assert E.backend_from_wheel(f"/d/arcadedb_jvm-{V}-py3-none-manylinux_2_28_x86_64.whl") == "jvm"
    assert E.backend_from_wheel("/d/arcadedb_embedded-26.10.2-cp312-x-y.whl") == ""
    assert E.pin_from_wheel(f"/d/arcadedb_jvm-{V}-py3-none-any.whl") == V


def test_native_and_jvm_images_of_one_release_have_two_tags():
    n, j = E.versioned_image(V, "native"), E.versioned_image(V, "jvm")
    assert (n, j) == (f"dbbench:arcadedb-{V}-native", f"dbbench:arcadedb-{V}-jvm")
    assert E.versioned_image("26.10.2") == "dbbench:arcadedb-26.10.2"      # the old form, for the old wheel
    for t in (n, j):
        assert E.build_target(t) == "arcadedb"
    assert E.build_target("dbbench:arcadedb-26.10.2") == "arcadedb"       # old tag still resolves


def test_a_tag_must_be_the_pinned_build():
    n, j, old = (E.versioned_image(V, "native"), E.versioned_image(V, "jvm"), f"dbbench:arcadedb-{V}")
    assert E.check_image_tag(n, V, "native") is None and E.check_image_tag(j, V, "jvm") is None
    assert "jvm" in E.check_image_tag(j, V, "native")
    assert "unsuffixed" in E.check_image_tag(old, V, "native")             # an old image cannot stand in for a native wheel
    assert E.check_image_tag(old, V) is None and E.check_image_tag(n, V) is None   # no build named: old and new tags both read
    assert E.check_image_tag("dbbench:arcadedb-26.10.2-native", V, "native")        # wrong version still refused


def test_verify_reads_the_build_out_of_the_image():
    img = E.versioned_image(V, "native")

    def run(cmd, **kw):
        # python probe output: version, distribution, jar names (the native package names its engine as one)
        return types.SimpleNamespace(returncode=0, stdout=f"{V}\narcadedb-jvm\narcadedb-engine-{V.replace('.dev0', '-SNAPSHOT')}.jar\n", stderr="")

    _rb, problems = E.verify(V, [img], [], run=run, backend="native")
    assert any("jvm build" in p and "native" in p for p in problems)      # a JVM package inside a -native tag is caught
    _rb, problems = E.verify(V, [E.versioned_image(V, "jvm")], [], run=run, backend="jvm")
    assert problems == []


def test_build_images_and_the_stage_template_tag_with_the_build():
    sh = (HERE / "build_images.sh").read_text()
    assert '${_bk:+-$_bk}' in sh and "arcadedb_jvm) _bk=jvm" in sh
    import make_2611_stages as G
    assert 'WB=""' in G.ARCADE_PRE_TAIL and "arcadedb_jvm) WB=-jvm" in G.ARCADE_PRE_TAIL
    assert "dbbench:arcadedb-$WV$WB" in G.ARCADE_POST_CHECKS and 'if [ "$WB" = "-native" ]' in G.ARCADE_POST_CHECKS
    v = (HERE / "verify_pair_c25.sh").read_text()
    assert "${WB:+-$WB}" in v and "NOT CHECKED (native build)" in v
    for f in ("build_images.sh", "verify_pair_c25.sh"):
        assert subprocess.run(["bash", "-n", str(HERE / f)]).returncode == 0


# ------------------------------------------------------------------ native isolate arguments
def test_jvm_kwargs_become_isolate_arguments():
    kept, dropped = AIMP.native_isolate_args("4g", "-Darcadedb.txWalFlush=0 -Xms4g -XX:+UseG1GC -Darcadedb.queryMaxHeapRAM=2048")
    assert kept == ["-Xmx4g", "-Darcadedb.txWalFlush=0", "-Xms4g", "-Darcadedb.queryMaxHeapRAM=2048"] and dropped == ["-XX:+UseG1GC"]
    assert AIMP.native_isolate_args(None, None) == ([], [])
    assert AIMP.native_isolate_args("1g", ["-Dx=1"]) == (["-Xmx1g", "-Dx=1"], [])


def test_apply_native_merges_and_lets_an_existing_setting_win():
    env = {}
    assert AIMP.apply_native({"heap_size": "4g", "jvm_args": "-Darcadedb.txWalFlush=1"}, env) == "-Xmx4g -Darcadedb.txWalFlush=1"
    env = {AIMP.NATIVE_ENV: "-Xmx2g"}
    assert AIMP.apply_native({"heap_size": "4g", "jvm_args": "-Darcadedb.txWalFlush=0"}, env) == "-Xmx2g -Darcadedb.txWalFlush=0"
    assert AIMP.apply_native(None, {}) == ""


def test_the_native_wrapper_sets_the_arguments_once_before_the_first_call(monkeypatch):
    seen = []
    mod = types.SimpleNamespace(__backend__="native", create_database=lambda p, **kw: seen.append(("c", p)),
                                open_database=lambda p, **kw: seen.append(("o", p)),
                                DatabaseFactory=object)
    monkeypatch.setattr(AIMP, "_loaded", mod)
    monkeypatch.setattr(AIMP, "_isolate_created", False)
    monkeypatch.delenv(AIMP.NATIVE_ENV, raising=False)
    AIMP._wrap_native(mod)
    mod.create_database("/a", jvm_kwargs={"heap_size": "3g", "jvm_args": None})
    mod.open_database("/a", jvm_kwargs={"heap_size": "9g", "jvm_args": None})      # a later call cannot change the isolate
    import os
    assert os.environ[AIMP.NATIVE_ENV] == "-Xmx3g" and seen == [("c", "/a"), ("o", "/a")]
    assert AIMP.effective_native_args() == "-Xmx3g"
    monkeypatch.delenv(AIMP.NATIVE_ENV, raising=False)


def test_the_jvm_build_is_not_wrapped():
    f = lambda *a, **k: None  # noqa: E731
    mod = types.SimpleNamespace(__backend__="jvm", create_database=f, open_database=f)
    AIMP._wrap_native(mod)
    assert mod.create_database is f


# ------------------------------------------------------------------ durability asked in SQL
class FakeDb:
    def __init__(self, value):
        self.value = value
        self.sql = []

    def query(self, lang, q):
        self.sql.append((lang, q))
        s = [{"key": "arcadedb.txWalFlush", "value": self.value, "overridden": False, "default": 0},
             {"key": "arcadedb.txWalGroupCommit", "value": False}]
        return types.SimpleNamespace(first=lambda: types.SimpleNamespace(get=lambda k: s if k == "settings" else None))


@pytest.mark.parametrize("value,want", [(0, "DURABILITY_ARCADEDB"), (1, "DURABILITY_ARCADEDB_STRICT"), (2, "DURABILITY_ARCADEDB_STRICT_FULL_SYNC")])
def test_durability_is_read_from_the_engine_in_sql_without_jpype(monkeypatch, value, want):
    """No jpype in sys.modules at all (the native build has none): the answer still comes from the engine, through the database."""
    import bench_common as B
    monkeypatch.setitem(sys.modules, "jpype", None)       # an import of jpype now raises ImportError
    db = FakeDb(value)
    assert B.arcade_durability_readback(db=db) == getattr(B, want)
    assert db.sql == [("sql", "SELECT settings FROM schema:database")]


def test_a_snapshot_taken_while_the_database_was_open_answers_after_it_closed(monkeypatch):
    import bench_common as B
    monkeypatch.setitem(sys.modules, "jpype", None)
    B.remember_engine_settings(FakeDb(1))
    try:
        assert B.arcade_durability_readback() == B.DURABILITY_ARCADEDB_STRICT
    finally:
        B._ENGINE_SETTINGS.clear()


def test_with_no_database_and_no_jpype_the_string_says_it_is_asserted(monkeypatch):
    import bench_common as B
    monkeypatch.setitem(sys.modules, "jpype", None)
    B._ENGINE_SETTINGS.clear()
    assert "asserted" in B.arcade_durability_readback()


# ------------------------------------------------------------------ the consumers
def _vc_failures(tmp_path, names):
    import json
    import version_consistency_check as VC
    payload = {"tables": [{"id": f"t{i}", "entries": [{"backend": "arcadedb_x", "version_name": n}]} for i, n in enumerate(names)]}
    f = tmp_path / "p.json"
    f.write_text(json.dumps(payload))
    return VC.check(str(f))


def test_version_consistency_treats_native_and_jvm_spellings_of_one_release_as_one_version(tmp_path):
    ok = _vc_failures(tmp_path, ["ArcadeDB 26.11.1 (native)", "ArcadeDB 26.11.1 (jvm)"])
    assert not [f for f in ok if "different version strings" in f or "spells one version" in f], ok
    bad = _vc_failures(tmp_path, ["ArcadeDB 26.11.1 (native)", "ArcadeDB 26.11.2 (jvm)"])
    assert bad, "two releases must still fail"


def test_page_check_names_the_new_row_fields_as_conditions_not_columns():
    import re
    import page_check as PC
    for field in ("engine_backend", "native_isolate_args", "engine_load_ms"):
        assert any(re.match(p, field) for p, _why in PC.NOT_PRINTED), field


def test_the_exporter_refuses_an_entry_that_pools_two_builds():
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    import export_web as X
    with pytest.raises(SystemExit) as e:
        X._one_version([row("native"), row("jvm")], "sparse/tiny")
    assert "different builds" in str(e.value)
    assert X._one_version([row("jvm"), row("jvm", rep=2)], "x")[0]["engine_version"] == V if isinstance(X._one_version([row("jvm")], "x"), list) else True


# ------------------------------------------------------------------ the engine commit, asked in SQL
SHA = "e854692736b48971f92dff78a1e727bc570bb6a2"
ANSWER = f"26.10.2 (build {SHA}/1792085686249/main)"


def test_the_commit_is_read_out_of_select_version():
    assert E.build_sha(ANSWER) == SHA and E.build_sha("26.10.2") == "" and E.build_sha(None) == ""
    assert E.commit_matches(SHA, SHA[:9]) and E.commit_matches(SHA[:9], SHA) and not E.commit_matches(SHA, "0" * 9)
    assert not E.commit_matches(SHA[:4], SHA[:4])        # four characters name nothing


def _fake(answer, dist="arcadedb"):
    def run(cmd, **kw):
        if "SELECT version()" in " ".join(cmd):
            return types.SimpleNamespace(returncode=0, stdout=answer + "\n", stderr="")
        return types.SimpleNamespace(returncode=0, stdout=f"{V}\n{dist}\narcadedb-engine-{V.replace('.dev0', '-SNAPSHOT')}.jar\n", stderr="")
    return run


def test_verify_checks_the_engine_commit_of_a_native_image():
    img = E.versioned_image(V, "native")
    rb, problems = E.verify(V, [img], [], run=_fake(ANSWER.replace("26.10.2", V)), backend="native", commit=SHA)
    assert problems == [] and rb[img]["engine_commit"] == SHA
    _rb, problems = E.verify(V, [img], [], run=_fake(ANSWER.replace(SHA, "1" * 40)), backend="native", commit=SHA)
    assert any("engine commit 111111111" in p for p in problems)
    _rb, problems = E.verify(V, [img], [], run=_fake("26.11.1.dev0"), backend="native", commit=SHA)
    assert any("names no build" in p for p in problems)
    _rb, problems = E.verify(V, [img], [], run=_fake(ANSWER), backend="native")        # no commit pinned: not asked
    assert problems == []


def test_the_pair_script_extracts_the_native_commit_with_the_same_answer_shape():
    """The sed in verify_pair_c25.sh run on a real answer."""
    text = (HERE / "verify_pair_c25.sh").read_text()
    line = next(l for l in text.splitlines() if "sed -n 's/.*(build" in l)
    sed_expr = line[line.index("sed -n"):].rstrip(")")
    out = subprocess.run(["bash", "-c", f"printf '%s\\n' '{ANSWER}' | {sed_expr}"], capture_output=True, text=True)
    assert out.stdout.strip() == SHA, (sed_expr, out)
    assert "4b. THE COMMIT THE NATIVE ENGINE REPORTS" in text and "NOT CHECKED (native build)" in text


def test_e4_reads_durability_through_the_sql_snapshot_and_the_probe_starts_native_without_a_jvm():
    probe = (HERE / "deployment_decomp_probe.py").read_text()
    assert "bench_common.remember_engine_settings(db)" in probe and 'backend() == "native"' in probe
    e4 = (HERE / "e4_decomp.py").read_text()
    assert "arcade_durability_readback()" in e4 and "jpype" not in e4.lower()
