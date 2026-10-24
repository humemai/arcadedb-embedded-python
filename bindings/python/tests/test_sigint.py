"""Ctrl-C reaches Python once the JVM is started (#118).

JPype's own default in a script is ``interrupt=True``: the JVM handles SIGINT
and ends the whole process with status 130, so no ``KeyboardInterrupt``,
``finally`` block, or ``atexit`` hook runs and a ``with db.transaction():`` block
is left without its rollback. ``start_jvm`` now passes ``interrupt=False``
unless asked otherwise. Each case needs a fresh JVM, hence the child process.

The ``java`` case blocks in a Java call that Ctrl-C cannot wake, on purpose
(#179). JPype's Java handler for SIGINT first calls ``Thread.interrupt()`` on the
main thread and only then marks the interrupt for Python. A call blocked in an
interruptible wait (``Thread.sleep``, ``Object.wait``) wakes in between, and
JPype 1.7.1 raises ``java.lang.InterruptedException`` or ``RuntimeError: Fatal
error occurred`` and delivers the ``KeyboardInterrupt`` late. That failed 14 of
400 interrupts with two cores idle and 26 of 200 with two busy cores. A call
that Ctrl-C cannot wake leaves no such window, and it is the case ``start_jvm``
documents: the ``KeyboardInterrupt`` arrives when the call returns.
"""

import os
import signal
import subprocess  # nosec B404 - test-controlled child process
import sys
import time

import pytest

_CHILD = """
import atexit, sys, time
import arcadedb_embedded as arcadedb
from arcadedb_embedded.jvm import start_jvm

start_jvm(heap_size="512m", interrupt=(sys.argv[3] == "1"))
db = arcadedb.create_database(sys.argv[2])
db.command("sql", "CREATE DOCUMENT TYPE T")
atexit.register(lambda: print("ATEXIT", flush=True))
print("READY", flush=True)
try:
    with db.transaction():
        db.command("sql", "INSERT INTO T SET n = 1")
        if sys.argv[1] == "java":
            import jpype
            # A Java call that blocks for 4 s and ignores Thread.interrupt():
            # a classic socket accept() polls with a timeout. It is not a
            # Thread.sleep(), which JPype's SIGINT handler can wake before it
            # records the interrupt for Python (#179).
            loopback = jpype.JClass("java.net.InetAddress").getLoopbackAddress()
            server = jpype.JClass("java.net.ServerSocket")(0, 1, loopback)
            server.setSoTimeout(4000)
            server.accept()
        elif sys.argv[1] == "sleep":
            # ONE long blocking call, not a loop of short ones: the main thread is
            # in a single clock_nanosleep() and only a signal delivered to it wakes it.
            time.sleep(60)
        else:
            while True:
                time.sleep(0.05)
except KeyboardInterrupt:
    print("KEYBOARD_INTERRUPT", flush=True)
finally:
    print("FINALLY", flush=True)
print("COUNT", db.count_type("T"), flush=True)
db.close()
"""


def _run_signal(tmp_path, mode, interrupt, sig=signal.SIGINT, bound=60):
    """Send ``sig`` to a child with an open transaction; fail if it has not exited within
    ``bound`` seconds (a KeyboardInterrupt stuck behind a blocking call looks like this).
    """
    proc = subprocess.Popen(  # nosec B603 - fixed argv, no shell, test-owned
        [sys.executable, "-c", _CHILD, mode, str(tmp_path / "db"), interrupt],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=dict(os.environ),
        # A runner that started pytest as a background job leaves SIGINT ignored,
        # and Python then installs no KeyboardInterrupt handler at all.
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),  # nosec B602
    )
    assert "READY" in proc.stdout.readline()
    time.sleep(1.0)
    proc.send_signal(sig)
    try:
        out, _ = proc.communicate(timeout=bound)
    except subprocess.TimeoutExpired:
        proc.kill()  # our own child
        proc.communicate()
        pytest.fail(f"child still running {bound} s after signal {int(sig)}")
    return proc.returncode, out


def _run_sigint(tmp_path, mode, interrupt):
    return _run_signal(tmp_path, mode, interrupt)


@pytest.mark.parametrize("mode", ["python", "java"])
def test_ctrl_c_raises_keyboard_interrupt_and_runs_cleanup(tmp_path, mode):
    """Python loop and a blocked Java call that Ctrl-C cannot wake (the
    KeyboardInterrupt arrives when it returns): KeyboardInterrupt, the
    transaction rolled back (COUNT 0), finally and atexit run, exit 0."""
    code, out = _run_sigint(tmp_path, mode, "0")
    assert code == 0, out
    lines = out.split()
    assert "KEYBOARD_INTERRUPT" in lines and "FINALLY" in lines
    assert "COUNT" in lines and lines[lines.index("COUNT") + 1] == "0"
    assert "ATEXIT" in lines


def test_ctrl_c_wakes_a_long_blocking_call_with_a_transaction_open(tmp_path):
    """A single time.sleep(60) in the main thread inside a transaction: Ctrl-C ends it at once
    (KeyboardInterrupt, rollback, cleanup, exit 0). With JPype's own SIGINT handler left in
    place the KeyboardInterrupt was pending but nobody woke the sleeping thread, so the
    process did not exit for the 60 s (10 of 10 runs on the JVM wheel; never on the native).
    """
    t0 = time.monotonic()
    code, out = _run_signal(tmp_path, "sleep", "0", bound=20)
    assert time.monotonic() - t0 < 25
    assert code == 0, out
    lines = out.split()
    assert "KEYBOARD_INTERRUPT" in lines and "FINALLY" in lines
    assert lines[lines.index("COUNT") + 1] == "0"
    assert "ATEXIT" in lines


def test_sigterm_ends_the_process_with_status_minus_15(tmp_path):
    """No Python handler for SIGTERM, as in a plain script: the process dies by SIGTERM, as
    without a JVM. JPype's handler used to crash it with SIGABRT (exit -6, jpype#1497).
    """
    code, _ = _run_signal(tmp_path, "sleep", "0", sig=signal.SIGTERM, bound=20)
    assert code == -signal.SIGTERM


def test_interrupt_true_keeps_the_jvm_handling_sigint(tmp_path):
    """The opt-back: the JVM ends the process with 130 and Python never sees
    the interrupt."""
    code, out = _run_sigint(tmp_path, "python", "1")
    assert code == 130
    assert "KEYBOARD_INTERRUPT" not in out
