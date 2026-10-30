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


LOG = {"server_mode": "development", "server_cpus": 4, "server_max_heap_bytes": 2 << 30}


def test_the_pair_gate_refuses_servers_whose_settings_differ_and_a_native_row_with_no_read_back():
    a, b = row("native", server_settings=dict(SETTINGS), **LOG), row("jvm", server_settings=dict(SETTINGS), **LOG)
    assert AI.pair_problems([a, b]) == []
    b["server_settings"] = dict(SETTINGS, **{"arcadedb.txWalFlush": "1"})
    assert any("arcadedb.txWalFlush" in p and "native server" in p for p in AI.pair_problems([a, b]))
    assert any("no server_settings" in p for p in AI.pair_problems([row("native"), row("jvm", server_settings=dict(SETTINGS))]))
    # the rows read back from the CSV hold the dict as JSON text
    assert AI.pair_problems([row("native", server_settings=json.dumps(SETTINGS), **LOG), row("jvm", server_settings=json.dumps(SETTINGS))]) == []
    # different durability classes are different cells
    c = row("jvm", server_settings=dict(SETTINGS, **{"arcadedb.txWalFlush": "1"}), durability_class="strict")
    assert AI.pair_problems([a, c]) == []


def test_the_pair_gate_covers_the_servers_engine_commit():
    a, b = row("native", server_settings=SETTINGS, **LOG), row("jvm", server_settings=SETTINGS, engine_commit="f" * 40)
    assert any("engine_commit" in p for p in AI.pair_problems([a, b]))


def test_a_one_build_freeze_drops_the_other_builds_server_rows():
    rows = [row("native"), row("jvm"), row(backend="duckdb")]
    assert [AI.build_of(r) for r in AI.select_build(rows, "native")] == ["native", None]


# ---------------------------------------------------------------- the server's own start line (mode, CPUs, MAXRAM)
LINE = "2026-10-30 10:00:00.123 INFO  ArcadeDB Server started in 'development' mode (CPUs=4 MAXRAM=2.00GB) [ArcadeDBServer]"


def test_the_start_line_is_parsed_from_the_log_and_the_last_one_wins():
    got = R.parse_server_started("noise\n" + LINE + "\n" + LINE.replace("CPUs=4", "CPUs=6").replace("2.00GB", "512MB"))
    assert got == {"server_mode": "development", "server_cpus": 6, "server_max_heap": "512MB", "server_max_heap_bytes": 512 << 20}
    assert R.parse_server_started(LINE)["server_max_heap_bytes"] == 2 << 30
    assert R.parse_server_started("no such line") == {}
    assert R.size_to_bytes("1.5 GiB") == 3 << 29 and R.size_to_bytes("garbage") is None


def test_the_cell_fails_when_maxram_cpus_or_mode_differ_from_the_request():
    ok = R.parse_server_started(LINE)
    assert R.server_log_problems(ok, 2 << 30, 4, "development") == []
    assert R.server_log_problems(dict(ok, server_max_heap_bytes=int((2 << 30) * 0.97)), 2 << 30, 4) == []        # rounding is allowed
    assert any("MAXRAM" in p for p in R.server_log_problems(dict(ok, server_max_heap_bytes=1 << 30), 2 << 30, 4))   # a -Xmx that did not take
    assert any("CPUs" in p for p in R.server_log_problems(ok, 2 << 30, 2))
    assert any("mode" in p for p in R.server_log_problems(ok, 2 << 30, 4, "production"))
    assert R.server_log_problems(ok, None, 4) == []                          # the image-defaults arm names no -Xmx
    assert R.server_log_problems({}, 2 << 30, 4)                             # no start line is a failure


def test_the_pair_gate_compares_the_start_line_and_the_page_cache():
    a, b = row("native", server_settings=dict(SETTINGS), **LOG), row("jvm", server_settings=dict(SETTINGS), **LOG)
    assert AI.pair_problems([a, b]) == []
    assert AI.pair_problems([a, dict(b, server_max_heap_bytes=int((2 << 30) * 0.98))]) == []
    assert any("MAXRAM" in p for p in AI.pair_problems([a, dict(b, server_max_heap_bytes=1 << 30)]))
    assert any("server_cpus" in p for p in AI.pair_problems([a, dict(b, server_cpus=8)]))
    assert any("server_mode" in p for p in AI.pair_problems([a, dict(b, server_mode="production")]))
    assert any("start-line" in p for p in AI.pair_problems([row("native", server_settings=dict(SETTINGS)), b]))
    page_a = dict(SETTINGS, **{"arcadedb.maxPageRAM": "4096"})
    page_b = dict(SETTINGS, **{"arcadedb.maxPageRAM": "1024"})
    assert any("arcadedb.maxPageRAM" in p for p in AI.pair_problems([dict(a, server_settings=page_a), dict(b, server_settings=page_b)]))
    assert AI.pair_problems([dict(a, server_settings=page_a), dict(b, server_settings=page_a)]) == []
