"""Logs and the JVM crash file go to a per-user directory, never the working directory."""

import os
import subprocess  # nosec B404 - test-controlled child process
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from arcadedb_embedded import jvm
from arcadedb_embedded.jvm import _build_jvm_args, _default_log_dir

SRC = str(Path(__file__).resolve().parents[1] / "src")

CHILD = """
import sys
sys.path.insert(0, sys.argv[1])
import arcadedb_embedded as arcadedb
from arcadedb_embedded import jvm

jvm_args = sys.argv[3:]
db = arcadedb.create_database(sys.argv[2], jvm_kwargs={"jvm_args": jvm_args})
db.command("sql", "CREATE DOCUMENT TYPE Doc")
db.close()
print("LOGDIR=" + str(jvm._LOG_DIR_USED))
"""


def _run_child(tmp_path, env_overrides, jvm_args=()):
    """Start a JVM in a child process whose working directory is empty and read-only."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cwd.chmod(0o555)  # not enforced everywhere; the listing below holds regardless
    env = {k: v for k, v in os.environ.items() if k != "ARCADEDB_JVM_ARGS"}
    env.pop("ARCADEDB_LOG_DIR", None)
    env.pop("ARCADEDB_JVM_ERROR_FILE", None)
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        XDG_STATE_HOME=str(home / "state"),
        LOCALAPPDATA=str(home / "localappdata"),
    )
    env.update(env_overrides)
    try:
        result = subprocess.run(  # nosec B603 - fixed argument list, no shell
            [
                sys.executable,
                "-c",
                CHILD,
                SRC,
                str(tmp_path / "db"),
                *jvm_args,
            ],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        cwd.chmod(0o755)
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(l for l in result.stdout.splitlines() if l.startswith("LOGDIR="))
    return cwd, Path(line[len("LOGDIR=") :]), home


def test_default_logs_land_in_the_state_dir_not_the_cwd(tmp_path):
    cwd, log_dir, home = _run_child(tmp_path, {})
    assert list(cwd.iterdir()) == []
    assert home in log_dir.parents
    assert log_dir.name == "log" and log_dir.parent.name == "arcadedb-embedded"
    assert list(log_dir.glob("arcadedb.log*")), list(log_dir.iterdir())
    config = (log_dir / "logging.properties").read_text("iso-8859-1")
    assert "${arcadedb.server.logsDirectory}/arcadedb.log" in config
    assert "./log" not in config


def test_env_var_sets_the_log_dir(tmp_path):
    target = tmp_path / "chosen logs"
    cwd, log_dir, _ = _run_child(tmp_path, {"ARCADEDB_LOG_DIR": str(target)})
    assert list(cwd.iterdir()) == []
    assert log_dir == target
    assert list(target.glob("arcadedb.log*"))


def test_jvm_args_can_move_the_engine_log(tmp_path):
    target = tmp_path / "from jvm args"
    cwd, _, home = _run_child(
        tmp_path, {}, jvm_args=[f"-Darcadedb.server.logsDirectory={target.as_posix()}"]
    )
    assert list(cwd.iterdir()) == []
    assert list(target.glob("arcadedb.log*"))


def test_unusable_log_dir_falls_back_to_a_temp_dir(tmp_path):
    blocker = tmp_path / "a file"
    blocker.write_text("not a directory")
    cwd, log_dir, _ = _run_child(tmp_path, {"ARCADEDB_LOG_DIR": str(blocker / "log")})
    assert list(cwd.iterdir()) == []
    assert log_dir != blocker / "log"
    assert list(log_dir.glob("arcadedb.log*"))


def test_args_never_name_the_working_directory():
    with patch.dict(os.environ, {}, clear=True):
        args = _build_jvm_args(heap_size="4g", disable_xml_limits=False, jvm_args=None)
    assert not any("./log" in a for a in args)
    log_dir = _default_log_dir().as_posix()
    assert f"-Darcadedb.server.logsDirectory={log_dir}" in args
    assert f"-Djava.util.logging.config.file={log_dir}/logging.properties" in args
    assert f"-XX:ErrorFile={log_dir}/hs_err_pid%p.log" in args


def test_state_dir_by_platform(tmp_path):
    env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    with patch.dict(os.environ, {**env, "XDG_STATE_HOME": str(tmp_path / "xdg")}):
        with patch.object(jvm.sys, "platform", "linux"):
            assert _default_log_dir() == tmp_path / "xdg" / "arcadedb-embedded" / "log"
    with patch.dict(os.environ, {**env, "XDG_STATE_HOME": "relative"}):
        with patch.object(jvm.sys, "platform", "linux"):
            expected = tmp_path / ".local" / "state" / "arcadedb-embedded" / "log"
            assert _default_log_dir() == expected
    with patch.dict(os.environ, env):
        with patch.object(jvm.sys, "platform", "darwin"):
            expected = tmp_path / "Library" / "Logs" / "arcadedb-embedded" / "log"
            assert _default_log_dir() == expected
    with patch.dict(os.environ, {**env, "LOCALAPPDATA": str(tmp_path / "lad")}):
        with patch.object(jvm.sys, "platform", "win32"):
            assert _default_log_dir() == tmp_path / "lad" / "arcadedb-embedded" / "log"


def test_user_arguments_win_over_the_log_defaults(tmp_path):
    user = [
        "-Darcadedb.server.logsDirectory=/x/logs",
        "-Djava.util.logging.config.file=/x/my.properties",
        "-XX:ErrorFile=/x/crash.log",
    ]
    with patch.dict(os.environ, {"ARCADEDB_JVM_ERROR_FILE": "/y/env.log"}, clear=True):
        args = _build_jvm_args(
            heap_size="4g", disable_xml_limits=False, jvm_args=user, log_dir=tmp_path
        )
    for arg in user:
        assert args.count(arg) == 1
    assert sum(a.startswith("-Darcadedb.server.logsDirectory=") for a in args) == 1
    assert sum(a.startswith("-Djava.util.logging.config.file=") for a in args) == 1
    assert sum(a.startswith("-XX:ErrorFile=") for a in args) == 1


def test_env_error_file_still_overrides_the_default(tmp_path):
    with patch.dict(os.environ, {"ARCADEDB_JVM_ERROR_FILE": "/y/env.log"}, clear=True):
        args = _build_jvm_args(
            heap_size="4g", disable_xml_limits=False, jvm_args=None, log_dir=tmp_path
        )
    assert "-XX:ErrorFile=/y/env.log" in args
    assert sum(a.startswith("-XX:ErrorFile=") for a in args) == 1


def test_rendered_config_keeps_the_engine_settings_and_moves_the_file_log():
    engine = (
        "handlers = java.util.logging.ConsoleHandler, java.util.logging.FileHandler\n"
        "java.util.logging.FileHandler.pattern=./log/arcadedb.log\n"
        "java.util.logging.FileHandler.count=10\n"
    )
    rendered = jvm._render_logging_config(engine)
    assert "./log" not in rendered
    assert "FileHandler.count=10" in rendered
    assert rendered.count("FileHandler.pattern") == 1
    assert "${arcadedb.server.logsDirectory}/arcadedb.log" in rendered


def test_the_engine_jar_carries_the_log_config_the_render_starts_from():
    import glob

    jars = glob.glob(os.path.join(jvm.get_jar_path(), "*.jar"))
    text = jvm._read_engine_log_properties(jars)
    assert text is not None
    assert "java.util.logging.FileHandler.pattern" in text
