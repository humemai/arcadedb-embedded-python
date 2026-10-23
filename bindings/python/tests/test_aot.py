"""Opt-in JDK AOT cache (arcadedb_embedded.aot): key, paths, fallbacks. No JVM is started."""

import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from arcadedb_embedded import aot, jvm


def _fake_jre(tmp_path: Path, version="25.0.4.1", libsize=1234) -> Path:
    jre = tmp_path / "jre"
    (jre / "lib" / "server").mkdir(parents=True)
    (jre / "release").write_text(f'JAVA_VERSION="{version}"\nMODULES="java.base"\n')
    (jre / "lib" / "server" / "libjvm.so").write_bytes(b"x" * libsize)
    return jre


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fake JRE, one jar and org.jpype.jar, and a cache directory under tmp_path."""
    jre = _fake_jre(tmp_path)
    jar = tmp_path / "a.jar"
    jar.write_bytes(b"jar")
    support = tmp_path / "org.jpype.jar"
    support.write_bytes(b"jpype")
    monkeypatch.setattr(aot, "jpype_support_jar", lambda: support)
    monkeypatch.delenv(aot.ENV_CACHE, raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(aot.sys, "platform", "linux")
    return dict(jre=jre, cp=str(jar), dir=tmp_path / "cache" / "arcadedb" / "aot")


def _plan(env, args=(), version="1.0", sha="s"):
    return aot.jvm_flags_for(list(args), env["jre"], env["cp"], version, sha)


def test_enabled_keyword_beats_environment(monkeypatch):
    monkeypatch.delenv(aot.ENV_ENABLE, raising=False)
    assert aot.enabled(None) is False
    monkeypatch.setenv(aot.ENV_ENABLE, "1")
    assert aot.enabled(None) is True
    assert aot.enabled(False) is False
    monkeypatch.setenv(aot.ENV_ENABLE, "0")
    assert aot.enabled(None) is False
    assert aot.enabled(True) is True


def test_cache_dir_by_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(aot.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert aot.cache_dir() == tmp_path / "arcadedb" / "aot"
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/ignored")
    assert aot.cache_dir() == Path.home() / ".cache" / "arcadedb" / "aot"
    monkeypatch.setattr(aot.sys, "platform", "darwin")
    assert aot.cache_dir() == Path.home() / "Library" / "Caches" / "arcadedb" / "aot"
    monkeypatch.setattr(aot.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert aot.cache_dir() == tmp_path / "arcadedb" / "Cache" / "aot"


def test_jre_identity(tmp_path):
    assert aot.jre_identity(_fake_jre(tmp_path, "25.0.4.1", 10)) == (25, "25.0.4.1+10")
    assert aot.jre_identity(tmp_path / "nowhere") is None
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "release").write_text("no version here")
    assert aot.jre_identity(bad) is None


def test_key_depends_on_every_input_and_is_stable():
    base = ("1.0", "25.0.4.1+9", "sha", "cp", "stats")
    key = aot.cache_key(*base)
    assert key == aot.cache_key(*base)
    assert len(key) == 32
    for i in range(len(base)):
        changed = list(base)
        changed[i] += "x"
        assert aot.cache_key(*changed) != key, i


def test_first_start_trains_with_a_unique_tmp_and_a_lock(env):
    flags = _plan(env)
    assert len(flags) == 1 and flags[0].startswith("-XX:AOTCacheOutput=")
    tmp = Path(flags[0].split("=", 1)[1])
    assert tmp.parent == env["dir"] and tmp.name.endswith(".tmp")
    assert str(os.getpid()) in tmp.name
    locks = list(env["dir"].glob("*.lock"))
    assert len(locks) == 1
    assert json.loads(locks[0].read_text())["pid"] == os.getpid()


def test_second_live_process_starts_normally(env):
    assert _plan(env)[0].startswith("-XX:AOTCacheOutput=")
    assert _plan(env) == []  # the first trainer is this (alive) process


def test_dead_trainer_output_is_promoted_then_used(env, monkeypatch):
    tmp = Path(_plan(env)[0].split("=", 1)[1])
    tmp.write_bytes(b"cache-bytes")
    lock = next(env["dir"].glob("*.lock"))
    info = json.loads(lock.read_text())
    info["pid"] = 2**22 + 12345  # not a live pid
    lock.write_text(json.dumps(info))
    monkeypatch.setattr(aot, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(aot, "_jvm_accepts", lambda *a, **k: True)
    flags = _plan(env)
    assert flags[0].startswith("-XX:AOTCache=") and flags[1] == "-XX:AOTMode=auto"
    final = Path(flags[0].split("=", 1)[1])
    assert final.read_bytes() == b"cache-bytes" and not tmp.exists()
    assert not list(env["dir"].glob("*.lock")) and not list(env["dir"].glob("*.tmp"))
    # and a third start just uses it
    assert _plan(env) == flags


def test_output_the_jvm_refuses_is_removed_and_retrained(env, monkeypatch):
    tmp = Path(_plan(env)[0].split("=", 1)[1])
    tmp.write_bytes(b"partial")
    monkeypatch.setattr(aot, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(aot, "_jvm_accepts", lambda *a, **k: False)
    flags = _plan(env)
    assert flags[0].startswith("-XX:AOTCacheOutput=")
    assert not tmp.exists() and not list(env["dir"].glob("*.aot"))


def test_missing_output_of_a_dead_trainer_clears_the_lock(env, monkeypatch):
    _plan(env)  # lock held, no output ever written (os._exit, crash)
    monkeypatch.setattr(aot, "_pid_alive", lambda pid: False)
    assert _plan(env)[0].startswith("-XX:AOTCacheOutput=")


def test_old_lock_of_a_live_pid_is_stale(env, monkeypatch):
    _plan(env)
    lock = next(env["dir"].glob("*.lock"))
    info = json.loads(lock.read_text())
    info["started"] = time.time() - aot.LOCK_STALE_SECONDS - 5
    lock.write_text(json.dumps(info))
    assert _plan(env)[0].startswith("-XX:AOTCacheOutput=")  # took over


def _good_cache(env, monkeypatch, payload=b"cache-bytes"):
    tmp = Path(_plan(env)[0].split("=", 1)[1])
    tmp.write_bytes(payload)
    monkeypatch.setattr(aot, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(aot, "_jvm_accepts", lambda *a, **k: True)
    flags = _plan(env)
    return Path(flags[0].split("=", 1)[1]), flags


@pytest.mark.parametrize(
    "damage", ["truncate", "flip", "empty", "meta-gone", "meta-junk"]
)
def test_damaged_cache_is_never_used_and_is_rebuilt(env, monkeypatch, damage):
    final, _ = _good_cache(env, monkeypatch)
    meta = final.with_name(final.name + ".json")
    if damage == "truncate":
        final.write_bytes(b"cache")
    elif damage == "flip":
        final.write_bytes(b"cache-byteX")
    elif damage == "empty":
        final.write_bytes(b"")
    elif damage == "meta-gone":
        meta.unlink()
    else:
        meta.write_text("{nope")
    monkeypatch.undo()  # real pid check again; the earlier trainer is gone
    monkeypatch.setenv("XDG_CACHE_HOME", str(env["dir"].parents[1]))
    monkeypatch.setattr(
        aot, "jpype_support_jar", lambda: Path(env["cp"]).parent / "org.jpype.jar"
    )
    flags = _plan(env)
    assert flags[0].startswith("-XX:AOTCacheOutput=")
    assert not final.exists()


@pytest.mark.parametrize(
    "change",
    [
        dict(version="2.0"),
        dict(sha="other-jars"),
    ],
)
def test_other_version_or_jars_get_another_cache_file(env, monkeypatch, change):
    final, _ = _good_cache(env, monkeypatch)
    flags = _plan(env, **change)
    assert flags[0].startswith("-XX:AOTCacheOutput=")
    assert final.exists()  # the old one is left alone


def test_touched_jar_changes_the_key(env, monkeypatch):
    final, _ = _good_cache(env, monkeypatch)
    jar = Path(env["cp"])
    st = jar.stat()
    os.utime(jar, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert _plan(env)[0].startswith("-XX:AOTCacheOutput=")


def test_user_flags_win(env):
    for flag in (
        "-XX:AOTCache=/x.aot",
        "-XX:AOTMode=off",
        "-Xshare:off",
        "-XX:SharedArchiveFile=/x",
    ):
        assert _plan(env, args=[flag]) == []
    assert not env["dir"].exists()


def test_unsupported_or_unreadable_jre_falls_back(tmp_path, env):
    old = _fake_jre(tmp_path / "old", "21.0.5")
    assert aot.jvm_flags_for([], old, env["cp"], "1", "s") == []
    assert aot.jvm_flags_for([], tmp_path / "nowhere", env["cp"], "1", "s") == []
    assert not env["dir"].exists()


def test_missing_jpype_jar_falls_back(env, monkeypatch):
    monkeypatch.setattr(aot, "jpype_support_jar", lambda: None)
    assert _plan(env) == []


def test_unwritable_location_never_raises(env, tmp_path, monkeypatch):
    blocker = tmp_path / "cache"
    blocker.write_text("a file where the directory should be")
    assert _plan(env) == []
    blocker.unlink()
    monkeypatch.setattr(
        aot.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(PermissionError("ro"))
    )
    assert _plan(env) == []


def test_lock_failure_is_a_normal_start(env, monkeypatch):
    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(aot.os, "open", boom)
    assert _plan(env) == []


def test_override_path_is_used_and_keyed(env, tmp_path, monkeypatch):
    target = tmp_path / "mine" / "c.aot"
    monkeypatch.setenv(aot.ENV_CACHE, str(target))
    flags = _plan(env)
    assert flags[0].startswith("-XX:AOTCacheOutput=") and str(target.parent) in flags[0]
    assert (target.parent / "c.aot.lock").exists()
    # a cache recorded for another key is not trusted
    target.write_bytes(b"x")
    (target.parent / "c.aot.json").write_text(
        json.dumps(
            {"key": "other", "size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
        )
    )
    assert not aot._usable_final(aot._Paths(target, "this-key"))
    assert aot._usable_final(aot._Paths(target, "other"))


def test_release_training_removes_lock_and_output(env):
    flag = _plan(env)[0]
    tmp = Path(flag.split("=", 1)[1])
    tmp.write_bytes(b"x")
    aot.release_training([flag])
    assert not tmp.exists() and not list(env["dir"].glob("*.lock"))


def test_pid_alive():
    assert aot._pid_alive(os.getpid())
    assert not aot._pid_alive(0)


def test_jvm_aot_flags_off_by_default_and_never_raises(monkeypatch):
    monkeypatch.delenv(aot.ENV_ENABLE, raising=False)
    monkeypatch.setattr(
        aot, "jvm_flags_for", lambda *a, **k: pytest.fail("called while off")
    )
    assert jvm._aot_flags(None, [], "cp") == []
    monkeypatch.setattr(
        aot, "jvm_flags_for", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    monkeypatch.setattr(jvm, "_extract_runtime_resource", lambda n: Path("."))
    monkeypatch.setattr(jvm, "jar_fingerprint", lambda **k: {"sha256": "s"})
    assert jvm._aot_flags(True, [], "cp") == []
