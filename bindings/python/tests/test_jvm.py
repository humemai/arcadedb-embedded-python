"""Tests for start_jvm() re-entry behavior once the JVM is running."""

import os

import arcadedb_embedded as arcadedb
import jpype
import pytest
from arcadedb_embedded import jvm
from arcadedb_embedded.exceptions import ArcadeDBError


@pytest.fixture(autouse=True)
def _jvm_running(tmp_path):
    """All tests here assume a started JVM (any earlier DB use starts it)."""
    if not jpype.isJVMStarted():
        db = arcadedb.create_database(str(tmp_path / "jvm_boot"))
        db.close()
    assert jpype.isJVMStarted()


def test_bare_start_jvm_joins_running_jvm(monkeypatch):
    # Regression: create_database(jvm_kwargs={"heap_size": "6g"}) followed by
    # open_database() raised, because the default-built args were compared
    # against the stored custom config instead of noticing no override was
    # requested.
    monkeypatch.setattr(jvm, "_JVM_CONFIG", ("-Xmx6g", "-Xms6g"))
    jvm.start_jvm()  # must not raise


def test_identical_config_is_idempotent(monkeypatch):
    args = tuple(
        jvm._build_jvm_args(
            heap_size="6g",
            disable_xml_limits=False,
            jvm_args="-Xms6g",
            common_pool_parallelism=None,
            log_dir=jvm._LOG_DIR_USED,
        )
    )
    monkeypatch.setattr(jvm, "_JVM_CONFIG", args)
    jvm.start_jvm(heap_size="6g", jvm_args="-Xms6g")  # must not raise


def test_conflicting_override_raises(monkeypatch):
    monkeypatch.setattr(jvm, "_JVM_CONFIG", ("-XX:MaxRAMPercentage=50",))
    with pytest.raises(ArcadeDBError, match="already started"):
        jvm.start_jvm(heap_size="99g")


def test_create_close_reopen_same_process(tmp_path):
    path = str(tmp_path / "reopen_db")
    db = arcadedb.create_database(path)
    db.command("sql", "CREATE DOCUMENT TYPE Doc")
    with db.transaction():
        db.command("sql", "INSERT INTO Doc SET k = 1")
    db.close()
    db2 = arcadedb.open_database(path)
    rows = db2.query("sql", "SELECT k FROM Doc").to_list()
    db2.close()
    assert rows == [{"k": 1}]


def test_interpreter_exits_with_unclosed_database(tmp_path):
    """A leaked (unclosed) Database must not hang interpreter exit.

    The engine's non-daemon background threads (e.g. AsyncFlush) keep the
    JVM alive; the bindings close active databases from an atexit hook so
    JPype's shutdown can complete. Without the hook this hangs forever.
    """
    import subprocess  # nosec B404 - test-controlled child process
    import sys as _sys

    script = (
        "import arcadedb_embedded as a\n"
        f"db = a.create_database({str(tmp_path / 'leak_db')!r})\n"
        "db.command('sql', 'CREATE DOCUMENT TYPE Doc')\n"
        "print('OK', flush=True)\n"
    )
    proc = subprocess.run(  # nosec B603 - fixed argv, no shell, test-owned
        [_sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "OK" in proc.stdout
    assert proc.returncode == 0


def _args(monkeypatch, env=None, **kwargs):
    if env is None:
        monkeypatch.delenv("ARCADEDB_JVM_ARGS", raising=False)
    else:
        monkeypatch.setenv("ARCADEDB_JVM_ARGS", env)
    kwargs.setdefault("heap_size", None)
    kwargs.setdefault("disable_xml_limits", True)
    kwargs.setdefault("jvm_args", None)
    return jvm._build_jvm_args(**kwargs)


def test_default_heap_is_a_share_of_ram(monkeypatch):
    args = _args(monkeypatch)
    assert f"-XX:MaxRAMPercentage={jvm._DEFAULT_MAX_RAM_PERCENTAGE}" in args
    assert not any(a.startswith("-Xmx") for a in args)


def test_explicit_heap_size_wins_over_everything(monkeypatch):
    args = _args(monkeypatch, env="-Xmx16g", heap_size="8g", jvm_args="-Xmx2g")
    assert [a for a in args if a.startswith("-Xmx")] == ["-Xmx8g"]
    assert not any("MaxRAMPercentage" in a for a in args)
    # "4g" is an ordinary explicit value now, not a stand-in for "default"
    args = _args(monkeypatch, env="-Xmx16g", heap_size="4g")
    assert [a for a in args if a.startswith("-Xmx")] == ["-Xmx4g"]


def test_user_xmx_is_kept_and_no_default_is_added(monkeypatch):
    args = _args(monkeypatch, jvm_args="-Xmx3g")
    assert [a for a in args if a.startswith("-Xmx")] == ["-Xmx3g"]
    assert not any("MaxRAMPercentage" in a for a in args)
    args = _args(monkeypatch, env="-Xmx3g", jvm_args="-Xmx6g")
    assert [a for a in args if a.startswith("-Xmx")] == ["-Xmx6g"]  # largest wins


@pytest.mark.parametrize(
    "flag", ["-XX:MaxRAMPercentage=70", "-XX:MaxRAM=6g", "-XX:MaxHeapSize=5g"]
)
def test_user_max_heap_flag_suppresses_the_default(monkeypatch, flag):
    args = _args(monkeypatch, env=flag)
    assert flag in args
    assert not any(a.startswith("-Xmx") for a in args)
    assert not any(a.startswith("-XX:MaxRAMPercentage=") and a != flag for a in args)


def test_default_heap_resolves_in_a_fresh_jvm(tmp_path):
    """A JVM started with no heap setting gets the share of RAM it sees.

    Reads the RAM the JVM itself reports (container limit in a container) and
    the page cache default that follows the heap.
    """
    import subprocess  # nosec B404 - test-controlled child process
    import sys as _sys

    script = (
        "import arcadedb_embedded as a\n"
        f"db = a.create_database({str(tmp_path / 'heap_db')!r})\n"
        "import jpype\n"
        "Runtime = jpype.JClass('java.lang.Runtime')\n"
        "MX = jpype.JClass('java.lang.management.ManagementFactory')\n"
        "GC = jpype.JClass('com.arcadedb.GlobalConfiguration')\n"
        "ram = int(MX.getOperatingSystemMXBean().getTotalMemorySize())\n"
        "heap = int(Runtime.getRuntime().maxMemory())\n"
        "page_mb = int(GC.MAX_PAGE_RAM.getValueAsLong())\n"
        "print('R', ram, heap, page_mb, flush=True)\n"
        "db.close()\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "ARCADEDB_JVM_ARGS"}
    proc = subprocess.run(  # nosec B603 - fixed argv, no shell, test-owned
        [_sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("R ")]
    assert lines, proc.stderr[-1500:] + proc.stdout[-500:]
    line = lines[0]
    ram, heap, page_mb = (int(x) for x in line.split()[1:])
    expected = ram * jvm._DEFAULT_MAX_RAM_PERCENTAGE / 100
    assert 0.9 * expected <= heap <= 1.1 * expected
    assert page_mb == pytest.approx(heap / 4 / 1024 / 1024, abs=2)


def test_no_initial_heap_flag_is_added(monkeypatch):
    args = _args(monkeypatch)
    assert not any(a.startswith(("-Xms", "-XX:InitialRAMPercentage")) for a in args)
    args = _args(monkeypatch, heap_size="8g")
    assert not any(a.startswith(("-Xms", "-XX:InitialRAMPercentage")) for a in args)
    args = _args(monkeypatch, jvm_args="-Xms1g")  # a user's own -Xms is kept
    assert "-Xms1g" in args


@pytest.mark.parametrize(
    "kwargs",
    [
        {"heap_size": "1g", "jvm_args": "-Xms2g"},
        {"jvm_args": "-Xmx512M -Xms1G"},
        {"heap_size": "1g", "jvm_args": "-Xms1100m"},
        {"heap_size": "1T", "jvm_args": "-Xms2t"},
        {"heap_size": "1048576", "jvm_args": "-Xms2m"},  # bytes, no suffix
    ],
)
def test_xms_larger_than_max_heap_raises_before_start(tmp_path, kwargs):
    """The JVM would end the process; start_jvm raises ValueError first."""
    import subprocess  # nosec B404 - test-controlled child process
    import sys as _sys

    script = (
        "import arcadedb_embedded as a\n"
        "try:\n"
        f"    a.create_database({str(tmp_path / 'xms_db')!r}, jvm_kwargs={kwargs!r})\n"
        "except ValueError as e:\n"
        "    print('VALUEERROR', e, flush=True)\n"
        "print('ALIVE', flush=True)\n"
    )
    proc = subprocess.run(  # nosec B603 - fixed argv, no shell, test-owned
        [_sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "VALUEERROR" in proc.stdout and "-Xms" in proc.stdout, proc.stderr[-800:]
    assert "ALIVE" in proc.stdout  # the Python process survived
    assert proc.returncode == 0


def test_check_initial_heap_accepts_valid_and_percentage_only():
    check = jvm._check_initial_heap
    check(["-Xmx2g", "-Xms2g"])  # equal is fine
    check(["-Xmx2g", "-Xms512m"])
    check(["-Xms64g", "-XX:MaxRAMPercentage=50"])  # percentage only: skipped
    check(["-Xms2g", "-Xmx4g"])
    with pytest.raises(ValueError, match="2g.*1g"):
        check(["-Xmx1g", "-Xms2g"])
