"""The native server arm (#222): upstream's native-image server next to the Docker JVM server, same client, same explicit settings.

Nothing is started here: only the launch configuration, the identity rules and the read-back parsing are exercised.
Run with `python -m pytest test_native_server_arm.py -q` from this directory.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("BENCH_INSTRUMENT", "2026-11")

import arm_identity as AI  # noqa: E402
import runner as R  # noqa: E402

V = "26.11.1.dev0"
COMMIT = "e353330c5c" + "0" * 30


def row(build="__absent__", backend="arcadedb_server", **kw):
    r = {"lane": "l1", "scale": "small", "workload": "oltp", "backend": backend, "engine_version": V, "engine_commit": COMMIT,
         "durability_class": "relaxed"}
    if build != "__absent__":
        r["engine_backend"] = build
    r.update(kw)
    return r


# ---------------------------------------------------------------- the launch configuration
def test_the_jvm_arm_states_the_settings_the_image_used_to_default():
    env = " ".join(x for x in R.BACKENDS["arcadedb_server"]["server_env"] if isinstance(x, str))
    for tok in R.EXPLICIT_SERVER_SETTINGS:
        assert f"-D{tok}" in env
    assert env.count("-Darcadedb.txWalFlush=") == 1
    for arm in ("arcadedb_graph_server", "arcadedb_sparse_server", "arcadedb_e2_server"):
        assert "-Darcadedb.server.mode=development" in " ".join(R.BACKENDS[arm]["server_env"])


def test_the_strict_class_replaces_the_flush_token_instead_of_adding_a_second():
    cfg, note = R.durability_server_patch(R.BACKENDS["arcadedb_server"], "strict")
    env = " ".join(x for x in cfg["server_env"] if isinstance(x, str))
    assert env.count("-Darcadedb.txWalFlush=") == 1 and "-Darcadedb.txWalFlush=1" in env and "txWalFlush=1" in note
    relaxed, _ = R.durability_server_patch(R.BACKENDS["arcadedb_server"], "relaxed")
    assert "-Darcadedb.txWalFlush=0" in " ".join(x for x in relaxed["server_env"] if isinstance(x, str))


def test_the_native_arm_is_derived_from_the_jvm_arms_own_settings():
    jvm = R.BACKENDS["arcadedb_graph_server"]
    nat = R.native_server_arm(jvm, "arcadedata/arcadedb:26.11.1-native")
    cmd = nat["server_cmd"]
    assert nat["server_image"].endswith("-native") and nat["server_build"] == "native" and nat["server_env"] == []
    assert cmd[0] == "-Xmx{heap}"                                        # the heap the JVM arm gets from ARCADEDB_OPTS_MEMORY
    jvm_d = {t for e in jvm["server_env"] if isinstance(e, str) and e.startswith("JAVA_OPTS=") for t in e.split("=", 1)[1].split() if t.startswith("-D")}
    assert {t for t in cmd if t.startswith("-D")} == jvm_d               # the same -D list, no more, no fewer
    assert any(t.startswith("-Darcadedb.server.httpBodyContentMaxSize=") for t in cmd)   # the graph arm's /batch limit is carried over
    assert "-XX:+UseCompactObjectHeaders" in nat["native_dropped_flags"] and not any(t.startswith("-XX") for t in cmd)
    assert jvm["server_image"] != nat["server_image"] and "server_build" not in jvm   # the JVM arm is untouched


def test_the_strict_patch_reaches_the_native_command_line_too():
    nat = R.native_server_arm(R.BACKENDS["arcadedb_server"], "arcadedata/arcadedb:26.11.1-native")
    cfg, note = R.durability_server_patch(nat, "strict")
    assert [t for t in cfg["server_cmd"] if t.startswith("-Darcadedb.txWalFlush=")] == ["-Darcadedb.txWalFlush=1"] and "txWalFlush=1" in note


def test_a_native_arm_needs_a_heap_and_settings_to_carry():
    with pytest.raises(SystemExit):
        R.native_server_arm({"server_env": ["-e", "JAVA_OPTS=-XX:+UseZGC"], "server_cmd": []}, "x")


# ---------------------------------------------------------------- read-back parsing and refusals
def test_requested_settings_are_read_from_env_and_command_without_the_password():
    text = "ARCADEDB_OPTS_MEMORY=-Xmx4g JAVA_OPTS=-Darcadedb.server.rootPassword=pw -Darcadedb.txWalFlush=0 -Darcadedb.txWalFlush=1"
    assert R.requested_settings(text) == {"arcadedb.txWalFlush": "1"}
    assert R.requested_settings("-Xmx4g -Darcadedb.server.mode=development") == {"arcadedb.server.mode": "development"}


def test_a_setting_the_engine_runs_otherwise_refuses_the_cell_and_an_unlisted_one_does_not():
    want = {"arcadedb.txWalFlush": "1", "arcadedb.server.mode": "development"}
    assert R.settings_problems({"arcadedb.txWalFlush": "0", "arcadedb.server.mode": "development"}, want) == [
        "setting arcadedb.txWalFlush was requested as 1 and the engine runs 0"]
    assert R.settings_problems({"arcadedb.txWalFlush": "1", "arcadedb.server.mode": "development"}, want) == []
    assert R.settings_problems({"arcadedb.txWalFlush": "1", "arcadedb.server.mode": None}, want) == []


def test_the_engine_commit_must_match_the_pin_when_one_is_claimed():
    assert R.engine_commit_problems(COMMIT[:9], COMMIT) == [] and R.engine_commit_problems(COMMIT, COMMIT) == []
    assert R.engine_commit_problems("deadbeef0", COMMIT) and R.engine_commit_problems(None, COMMIT)
    assert R.engine_commit_problems("deadbeef0", "") == []


def test_a_bench_server_build_that_is_not_the_wheels_is_refused_at_import():
    import subprocess
    env = dict(os.environ, BENCH_SERVER_BUILD="native", BENCH_INSTRUMENT="2026-11")
    for k in ("ARCADEDB_WHEEL", "ARCADEDB_SERVER_IMAGE", "ARCADEDB_NATIVE_SERVER_IMAGE", "ARCADEDB_ENGINE_COMMIT"):
        env.pop(k, None)
    r = subprocess.run([sys.executable, "-c", "import runner"], cwd=Path(__file__).parent, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "BENCH_SERVER_BUILD=native" in (r.stderr + r.stdout)


# ---------------------------------------------------------------- identity, labels, gates
def test_a_served_row_carries_the_server_build_and_an_old_one_is_jvm():
    assert AI.served(row()) and not AI.served(row(backend="arcadedb_imgdefaults_server")) and not AI.served(row(backend="arcadedb_sparse_embedded"))
    assert AI.build_of(row()) == "jvm" and AI.build_of(row("native")) == "native"
    stamped = AI.stamp_build(row(server_build="native", engine_backend=None), "native")
    assert stamped["engine_backend"] == "native"
    # a killed served cell is stamped by the SERVER's build, not the wheel's
    assert AI.stamp_build(row(server_build="jvm"), "native")["engine_backend"] == "jvm"


def test_the_four_arms_are_labelled_by_mode_and_build():
    assert AI.build_label("ArcadeDB (server)", "native") == "ArcadeDB (server, native build)"
    assert AI.build_label("ArcadeDB (server)", "jvm") == "ArcadeDB (server, JVM build)"
    assert AI.build_label("ArcadeDB (embedded)", "native") == "ArcadeDB (embedded, native build)"
    assert AI.strip_build("ArcadeDB (server, JVM build)") == "ArcadeDB (server)"


def test_the_cpu_baseline_of_each_artifact_is_stamped_and_not_changed():
    assert AI.stamp_build(row("native", backend="arcadedb_sparse_embedded"), "native")["cpu_baseline"] == "native wheel: -march=compatibility"
    assert AI.stamp_build(row("native"), "native")["cpu_baseline"] == "native server image: -march=x86-64-v3"
    assert AI.stamp_build(row("jvm"), "jvm")["cpu_baseline"].startswith("JVM")
    assert AI.cpu_baseline("native", True, {"ARCADEDB_NATIVE_SERVER_MARCH": "x86-64-v2"}).endswith("-march=x86-64-v2")


SETTINGS = {"arcadedb.server.mode": "development", "arcadedb.server.httpIncomingHost": "0.0.0.0",
            "arcadedb.server.httpIncomingPort": "2480", "arcadedb.txWalFlush": "0"}


def test_the_pair_gate_refuses_servers_whose_settings_differ_and_a_native_row_with_no_read_back():
    a, b = row("native", server_settings=dict(SETTINGS)), row("jvm", server_settings=dict(SETTINGS))
    assert AI.pair_problems([a, b]) == []
    b["server_settings"] = dict(SETTINGS, **{"arcadedb.txWalFlush": "1"})
    assert any("arcadedb.txWalFlush" in p and "native server" in p for p in AI.pair_problems([a, b]))
    assert any("no server_settings" in p for p in AI.pair_problems([row("native"), row("jvm", server_settings=dict(SETTINGS))]))
    # the rows read back from the CSV hold the dict as JSON text
    assert AI.pair_problems([row("native", server_settings=json.dumps(SETTINGS)), row("jvm", server_settings=json.dumps(SETTINGS))]) == []
    # different durability classes are different cells
    c = row("jvm", server_settings=dict(SETTINGS, **{"arcadedb.txWalFlush": "1"}), durability_class="strict")
    assert AI.pair_problems([a, c]) == []


def test_the_pair_gate_covers_the_servers_engine_commit():
    a, b = row("native", server_settings=SETTINGS), row("jvm", server_settings=SETTINGS, engine_commit="f" * 40)
    assert any("engine_commit" in p for p in AI.pair_problems([a, b]))


def test_a_one_build_freeze_drops_the_other_builds_server_rows():
    rows = [row("native"), row("jvm"), row(backend="duckdb")]
    assert [AI.build_of(r) for r in AI.select_build(rows, "native")] == ["native", None]
