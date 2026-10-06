"""The served ArcadeDB arm at the image's own JVM defaults (CAMPAIGN section 7 row 69).

Run with `python -m pytest test_jvm_defaults_arm.py -q -rs` from this directory.

One served arm, `arcadedb_imgdefaults_server`, is started WITHOUT the two variables every
other served ArcadeDB arm sets (ARCADEDB_OPTS_MEMORY, ARCADEDB_OPTS_GC), so the vendor image
applies its own: a heap of 75% of the container limit, generational ZGC, and no -Xms. These
tests hold the parts of that which a later edit could silently undo, each by the failure it
would cause:

  * the arm really omits both variables, and nothing else about its launch differs from the
    main served arm (it is derived from it, so a new flag on the main arm reaches it);
  * the arm runs the documents transaction workload only, in a stage of its own with three
    repetitions, and the main documents stage leaves it out (coverage still holds);
  * the fairness gate declares it, refuses an undeclared `jvm_defaults` arm, and judges rows
    against the JVM's own report (heap, collector, no -Xms/-Xmx), not against the launcher's
    environment;
  * the readback parses what the JVM printed, and the cell's own check (image_defaults_findings)
    fails when the JVM is not at the image's defaults.

What it cannot test is that the image applies the defaults at all: that is the rehearsal's
evidence (the running process's command line and `jcmd VM.flags`, read from a container).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fairness_check as FC  # noqa: E402
import runner as RN  # noqa: E402

ARM = "arcadedb_imgdefaults_server"
GIB = 1 << 30


def _env_keys(cfg):
    env = cfg["server_env"]
    return [env[i + 1].split("=", 1)[0] for i in range(0, len(env) - 1, 2) if env[i] == "-e"]


def _env_value(cfg, key):
    env = cfg["server_env"]
    return next(env[i + 1].split("=", 1)[1] for i in range(0, len(env) - 1, 2)
                if env[i] == "-e" and env[i + 1].startswith(key + "="))


# ---------------------------------------------------------------- the launch config

def test_the_arm_sets_neither_jvm_variable_and_the_main_arm_sets_both():
    assert "ARCADEDB_OPTS_MEMORY" in _env_keys(RN.BACKENDS["arcadedb_server"])
    assert "ARCADEDB_OPTS_GC" in _env_keys(RN.BACKENDS["arcadedb_server"])
    arm = RN.BACKENDS[ARM]
    assert "ARCADEDB_OPTS_MEMORY" not in _env_keys(arm)
    assert "ARCADEDB_OPTS_GC" not in _env_keys(arm)
    assert "-Xm" not in " ".join(str(x) for x in arm["server_env"])


def test_everything_else_is_the_main_arms():
    main, arm = RN.BACKENDS["arcadedb_server"], RN.BACKENDS[ARM]
    assert _env_value(arm, "JAVA_OPTS") == _env_value(main, "JAVA_OPTS")
    assert [k for k in _env_keys(main) if k not in ("ARCADEDB_OPTS_MEMORY", "ARCADEDB_OPTS_GC")] == _env_keys(arm)
    for key in ("topology", "image", "server_image", "server_port", "ready_regex"):
        assert arm[key] == main[key]
    assert arm["jvm_defaults"] is True and not main.get("jvm_defaults")
    # the one place the main arm's environment is a template, and the arm has no use for it
    assert "{heap}" in " ".join(main["server_env"]) and "{heap}" not in " ".join(arm["server_env"])


def test_derivation_refuses_a_main_arm_that_stopped_setting_the_variables():
    bare = {"server_env": ["-e", "JAVA_OPTS=-Dx=1"]}
    with pytest.raises(SystemExit):
        RN._at_image_jvm_defaults(bare)


def test_the_local_engine_swap_reaches_the_arm():
    """The matched pair swaps every stock-image server arm for the local image; the arm
    keeps the same stock-image prefix the swap matches on, or it would run the 26.8.1 image
    beside a 26.10.1 wheel."""
    assert str(RN.BACKENDS[ARM]["server_image"]).startswith("arcadedata/arcadedb")


# ------------------------------------------------------------- one workload, own stage

def test_the_arm_runs_the_documents_transaction_workload_only():
    assert RN.arm_runs("l1tpc", "oltp", ARM)
    assert not RN.arm_runs("l1tpc", "olap", ARM)
    assert RN.arm_runs("l1tpc", "olap", "arcadedb_server")          # every other arm: unchanged
    assert ARM in RN.LANES["l1tpc"][1]
    jobs = {(j["workload"], j["backend"]) for j in RN.build_jobs(["l1tpc"], [])}
    assert ("oltp", ARM) in jobs and ("olap", ARM) not in jobs
    assert ("olap", "arcadedb_server") in jobs


def test_stage_generator_gives_it_a_stage_of_its_own():
    import make_2610_stages as M
    problems, _excluded, counts = M.check_coverage()
    assert problems == []
    assert counts["l1tpc"] == len(RN.LANES["l1tpc"][1])
    main = next(s for s in M.STAGES if s[0] == "qRD")
    own = next(s for s in M.STAGES if s[0] == "qRO")
    assert ARM not in M.stage_backends(main) and "arcadedb_server" in M.stage_backends(main)
    assert M.stage_backends(own) == [ARM]
    assert own[3] == ["oltp"] and own[4] == ["tpch10"] and "REPS=3" in own[7] and own[9] == "relaxed"


def test_coverage_refuses_the_arm_staged_on_a_workload_it_does_not_run():
    import make_2610_stages as M
    bad = [("qRX", "x", "l1tpc", ["oltp", "olap"], ["tpch10"], [], {}, [], [ARM])]
    problems, _e, _c = M.check_coverage(bad)
    assert any("keeps it off this workload" in p for p in problems)


# ------------------------------------------------------------------- the fairness gate

def _row(**kw):
    base = {"lane": "l1tpc", "scale": "tpch10", "workload": "oltp", "backend": ARM, "rep": 1,
            "server_jvm_defaults": True, "server_mem_cap": "16g",
            "server_jvm_max_heap_bytes": 12 * GIB, "server_jvm_gc": "ZGC generational",
            "server_jvm_flags": "-XX:+UseZGC -XX:+ZGenerational -XX:MaxRAMPercentage=75"}
    base.update(kw)
    return base


def test_gate_passes_a_row_at_the_image_defaults(capsys):
    assert FC.check_jvm_defaults_arms([_row()]) == 0
    assert "ok" in capsys.readouterr().out


@pytest.mark.parametrize("change", [
    {"server_jvm_defaults": None},                                        # unstamped
    {"server_jvm_max_heap_bytes": 8 * GIB},                               # the main arm's 50%
    {"server_jvm_max_heap_bytes": None},                                  # nothing read back
    {"server_jvm_gc": "G1"},                                              # the main arm's collector
    {"server_jvm_gc": "ZGC"},                                             # not generational
    {"server_jvm_flags": "-Xms8g -Xmx8g -XX:+UseZGC"},                    # a heap set on the command line
])
def test_gate_fails_a_row_that_is_not_at_the_image_defaults(change):
    assert FC.check_jvm_defaults_arms([_row(**change)]) >= 1


def test_gate_fails_another_row_claiming_the_stamp():
    assert FC.check_jvm_defaults_arms([_row(backend="arcadedb_server")]) == 1


def test_gate_fails_an_arm_marked_in_the_runner_and_not_declared(monkeypatch):
    monkeypatch.setitem(RN.BACKENDS, "arcadedb_other_server",
                        dict(RN.BACKENDS[ARM]))                            # marked, not declared
    assert FC.check_jvm_defaults_arms([]) >= 1


def test_gate_fails_a_declaration_with_no_marked_arm(monkeypatch):
    monkeypatch.setitem(FC.JVM_DEFAULTS_ARMS, "arcadedb_ghost_server", "x")
    assert FC.check_jvm_defaults_arms([]) >= 1


def test_gate_fails_an_arm_whose_launch_sets_the_variables(monkeypatch):
    cfg = dict(RN.BACKENDS[ARM], server_env=RN.BACKENDS[ARM]["server_env"] + ["-e", "ARCADEDB_OPTS_GC=-XX:+UseG1GC"])
    monkeypatch.setitem(RN.BACKENDS, ARM, cfg)
    assert FC.check_jvm_defaults_arms([]) >= 1


def test_the_static_half_passes_on_the_tree_as_it_stands():
    assert FC.check_jvm_defaults_arms([]) == 0


def test_f3_does_not_call_the_arms_heap_a_violation(monkeypatch):
    """Same cap as the main arm and a different heap: F3 judges the cap only for the declared arm."""
    monkeypatch.setattr(FC, "_dense_rows", lambda: [])        # the dense overlay is a bench-host artifact
    main = {"lane": "l1tpc", "scale": "tpch10", "backend": "arcadedb_server", "mem_split": "full+client",
            "server_mem_cap": "16g", "server_heap": "8g"}
    arm = dict(_row(), mem_split="full+client")
    assert FC.check_envelope([main, arm]) == 0
    # and a cap that differs IS still a violation
    assert FC.check_envelope([main, dict(arm, server_mem_cap="12g")]) == 1


# ---------------------------------------------------------------- the readback

def _fake_run(outputs):
    """subprocess.run stand-in: the docker execs answer in order: /proc/1/cmdline, jcmd VM.flags,
    jcmd VM.version (a missing last answer is an empty one)."""
    outputs = list(outputs) + [""] * (3 - len(outputs))
    calls = iter(outputs)

    def run(cmd, **kw):
        return SimpleNamespace(stdout=next(calls), returncode=0)
    return run


CMDLINE = ("/usr/lib/jvm/java-25-amazon-corretto/bin/java -XX:HeapDumpPath=/home/arcadedb/log "
           "-Darcadedb.server.rootPassword=secret -server -XX:+UseZGC -XX:+ZGenerational "
           "-XX:+UseCompactObjectHeaders -XX:MaxRAMPercentage=75 --add-modules jdk.incubator.vector "
           "-cp /home/arcadedb/lib/* com.arcadedb.server.ArcadeDBServer")
# JDK 25 (the image): ZGC is generational by definition and VM.flags does not list ZGenerational at all.
VMFLAGS = "-XX:InitialHeapSize=33554432 -XX:MaxHeapSize=1610612736 -XX:MaxRAMPercentage=75.000000 -XX:+UseZGC"
VM25 = "OpenJDK 64-Bit Server VM version 25.0.4.1+10-LTS\nJDK 25.0.4.1\n"
VM21 = "OpenJDK 64-Bit Server VM version 21.0.12+7-LTS\nJDK 21.0.12\n"
G1FLAGS = "-XX:InitialHeapSize=8589934592 -XX:MaxHeapSize=8589934592 -XX:+UseG1GC"


def test_readback_reads_the_zgc_image_defaults(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run([CMDLINE, VMFLAGS, VM25]))
    out = RN.server_jvm_readback("cid")
    assert out["server_jvm_major"] == 25
    assert out["server_jvm_max_heap_bytes"] == 1610612736
    assert out["server_jvm_initial_heap_bytes"] == 33554432
    assert out["server_jvm_gc"] == "ZGC generational"
    assert "rootPassword" not in out["server_jvm_flags"]                    # -D properties carry the password
    assert "-XX:MaxRAMPercentage=75" in out["server_jvm_flags"] and "-Xmx" not in out["server_jvm_flags"]
    assert "server_jvm_readback_error" not in out


def test_zgc_is_generational_only_where_the_jdk_says_so(monkeypatch):
    """JDK 21 lists the flag either way, so +UseZGC alone is the old single-generation collector there."""
    monkeypatch.setattr(subprocess, "run", _fake_run([CMDLINE, VMFLAGS + " -XX:-ZGenerational", VM21]))
    assert RN.server_jvm_readback("cid")["server_jvm_gc"] == "ZGC"
    monkeypatch.setattr(subprocess, "run", _fake_run([CMDLINE, VMFLAGS + " -XX:+ZGenerational", VM21]))
    assert RN.server_jvm_readback("cid")["server_jvm_gc"] == "ZGC generational"
    monkeypatch.setattr(subprocess, "run", _fake_run([CMDLINE, VMFLAGS]))        # no version answer, no flag: not claimed
    assert RN.server_jvm_readback("cid")["server_jvm_gc"] == "ZGC"


def test_readback_reads_the_main_arms_g1(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(["java -Xms8g -Xmx8g -XX:+UseCompactObjectHeaders -cp x Main", G1FLAGS]))
    out = RN.server_jvm_readback("cid")
    assert out["server_jvm_gc"] == "G1" and out["server_jvm_max_heap_bytes"] == 8589934592
    assert "-Xms8g -Xmx8g" in out["server_jvm_flags"]


def test_readback_records_a_failure_and_never_raises(monkeypatch):
    def boom(cmd, **kw):
        raise OSError("docker is gone")
    monkeypatch.setattr(subprocess, "run", boom)
    assert "docker is gone" in RN.server_jvm_readback("cid")["server_jvm_readback_error"]
    monkeypatch.setattr(subprocess, "run", _fake_run([CMDLINE, ""]))
    assert "server_jvm_readback_error" in RN.server_jvm_readback("cid")


def test_cell_check_accepts_the_defaults_and_names_what_is_wrong():
    ok = {"server_jvm_max_heap_bytes": 12 * GIB, "server_jvm_gc": "ZGC generational",
          "server_jvm_flags": "-XX:+UseZGC -XX:MaxRAMPercentage=75"}
    assert RN.image_defaults_findings(ok, 16 * GIB) == []
    bad = RN.image_defaults_findings({"server_jvm_max_heap_bytes": 8 * GIB, "server_jvm_gc": "G1",
                                      "server_jvm_flags": "-Xms8g -Xmx8g"}, 16 * GIB)
    assert len(bad) == 3
    assert RN.image_defaults_findings({}, 16 * GIB)[0] == "no heap read back from the JVM"


# ------------------------------------------------------- the page: label, heap, sentence, gate

@pytest.fixture(scope="module")
def EW():
    """export_web, imported once (it refuses to import without a pin in the environment)."""
    import os
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


def _frozen(heap_main=8 * GIB, heap_arm=12 * GIB, gc_main="G1"):
    base = {"lane": "l1tpc", "workload": "oltp", "scale": "tpch10", "server_mem_cap": "16g"}
    return [dict(base, backend="arcadedb_server", server_jvm_max_heap_bytes=heap_main, server_jvm_gc=gc_main),
            dict(base, backend=ARM, server_jvm_defaults=True, server_jvm_max_heap_bytes=heap_arm,
                 server_jvm_gc="ZGC generational")]


def _table(*backends):
    return {"id": "docs_oltp", "entries": [{"backend_key": b, "scale": "tpch10",
                                            "backend": "ArcadeDB (server)"} for b in backends]}


def test_label_is_its_own(EW):
    assert EW.display_name(ARM) == "ArcadeDB (server, image JVM defaults)"
    assert EW.display_name(ARM) != EW.display_name("arcadedb_server")
    assert EW.deployment_of(ARM) == "server"


def test_heap_column_prints_what_the_jvm_reported(EW, monkeypatch):
    monkeypatch.setattr(EW, "_FROZEN_ROWS", _frozen())
    assert EW._jvm_reported_heap(_frozen()[1]) == "12g"
    assert EW._jvm_reported_heap(_frozen()[0]) is None            # the main arm has its tier heap instead
    entry = {"backend": EW.display_name(ARM), "scale": "tpch10"}
    assert EW._entry_heaps(entry, "l1tpc", "oltp", exact_only=True) == {"12g"}


def test_sentence_is_generated_from_the_recorded_flags(EW, monkeypatch):
    monkeypatch.setattr(EW, "_FROZEN_ROWS", _frozen())
    (text,) = EW._jvm_defaults_notes(_table("arcadedb_server", ARM))
    for want in ("the ArcadeDB image's own JVM settings", "fixed heap of 8 GiB", "G1 collector",
                 "a heap of 12 GiB, 75 per cent of its 16 GiB container", "ZGC generational collector",
                 "no initial heap size"):
        assert want in text, want
    assert "—" not in text and "–" not in text and " -- " not in text
    import re
    assert not re.search(r"#\d|DECISIONS|BUGS|\bF\d+\b|row \d+", text)
    # the sentence's own digits are the ones it registered with its values, nothing else
    assert {v for rec in EW._GENERATED if rec["text"] == text for v in rec["values"]} >= {"8", "12", "75", "16"}


def test_sentence_changes_with_the_rows_not_with_the_code(EW, monkeypatch):
    monkeypatch.setattr(EW, "_FROZEN_ROWS", _frozen(heap_main=4 * GIB, heap_arm=6 * GIB, gc_main="Parallel"))
    (text,) = EW._jvm_defaults_notes(_table(ARM))
    assert "fixed heap of 4 GiB" in text and "Parallel collector" in text and "a heap of 6 GiB" in text
    # a main row with no read-back is said without its numbers, not guessed
    rows = [r for r in _frozen() if r["backend"] == ARM]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
    (text,) = EW._jvm_defaults_notes(_table(ARM))
    assert "a fixed heap and the collector the JVM chooses by default" in text


def test_no_arm_no_sentence(EW, monkeypatch):
    monkeypatch.setattr(EW, "_FROZEN_ROWS", _frozen())
    assert EW._jvm_defaults_notes(_table("arcadedb_server")) == []
    assert EW._jvm_defaults_notes({"id": "docs_olap", "entries": []}) == []


def test_page_gate_fails_a_table_that_lost_the_sentence(EW, monkeypatch, capsys):
    import page_check as PC
    monkeypatch.setattr(EW, "_FROZEN_ROWS", _frozen())
    t = _table("arcadedb_server", ARM)
    t["conditions"] = EW._jvm_defaults_notes(t)
    assert PC._check_jvm_defaults_disclosure({"tables": [t]}) == 0
    t["conditions"] = ["An unrelated sentence about heaps and collectors."]
    assert PC._check_jvm_defaults_disclosure({"tables": [t]}) == 1
    # a table that does not print the arm owes nothing
    assert PC._check_jvm_defaults_disclosure({"tables": [_table("arcadedb_server")]}) == 0


def test_roster_does_not_owe_the_arm_on_the_analytics_table(EW, capsys):
    import page_check as PC

    def table(tid, with_arm):
        keys = ["arcadedb_embedded", "arcadedb_server"] + ([ARM] if with_arm else [])
        return {"id": tid, "instrument": "2026-10", "entries": [{"backend_key": k, "backend": k} for k in keys]}

    PC._check_lane_roster({"tables": [table("docs_oltp", True), table("docs_olap", False)]})
    out = capsys.readouterr().out
    assert f"[{ARM}] on docs_olap" not in out                       # not owed there
    PC._check_lane_roster({"tables": [table("docs_oltp", False), table("docs_olap", False)]})
    assert f"[{ARM}] on docs_oltp: registered for lane l1tpc, no row and no declaration" in capsys.readouterr().out
