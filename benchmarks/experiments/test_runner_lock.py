"""The runner's host-wide lock and its container sweep (re-pin rehearsal defect 2).

Run with `python -m pytest test_runner_lock.py -q -rs` from this directory.

The lock lived in tempfile.gettempdir(), which follows $TMPDIR, so two sessions with different TMPDIR (an
agent working in a private scratch directory is exactly that) held different "host-wide" locks, and the
second one's sweep_orphans() force-removed the first one's containers. Now the first lock is at a path
that depends on nothing in the environment, and a container carries the pid of the runner that started it,
so the sweep removes only what no live runner owns.
"""
import os
import pwd
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import runner as RN  # noqa: E402


# ----------------------------------------------------------------------------- the lock path

def test_the_first_lock_path_does_not_depend_on_the_environment(monkeypatch, tmp_path):
    home = pwd.getpwuid(os.getuid()).pw_dir
    want = os.path.join(home, ".cache", "dbbench-runner.lock")
    assert RN.lock_paths()[0] == want
    monkeypatch.setenv("TMPDIR", str(tmp_path / "a"))
    monkeypatch.setenv("HOME", str(tmp_path / "other-home"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert RN.lock_paths()[0] == want
    # the legacy path is still the second one, and it is the only one that follows TMPDIR
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "b"))
    assert RN.lock_paths() == [want, os.path.join(str(tmp_path / "b"), "dbbench-runner.lock")]


_HOLDER = textwrap.dedent('''
    import sys
    sys.path.insert(0, {here!r})
    import runner
    held = runner.acquire_host_lock({paths!r})
    print("held", flush=True)
    sys.stdin.readline()
''')

_TRIER = textwrap.dedent('''
    import sys
    sys.path.insert(0, {here!r})
    import runner
    try:
        runner.acquire_host_lock({paths!r})
        print("ACQUIRED")
    except SystemExit as e:
        print("REFUSED:", e)
''')


def _run(code, tmpdir, stdin=subprocess.PIPE):
    return subprocess.Popen([sys.executable, "-c", code], stdin=stdin, stdout=subprocess.PIPE, text=True,
                            env={**os.environ, "TMPDIR": str(tmpdir)}, cwd="/")


def test_two_sessions_with_different_tmpdir_cannot_hold_different_locks(tmp_path):
    """The failure the fix is for: runner one under TMPDIR=a holds the lock; runner two under TMPDIR=b, a
    different temporary directory, is still refused, because the lock is the same file."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    shared = [str(tmp_path / "home-cache" / "dbbench-runner.lock")]
    one = _run(_HOLDER.format(here=str(HERE), paths=shared), a)
    try:
        assert one.stdout.readline().strip() == "held"
        two = _run(_TRIER.format(here=str(HERE), paths=shared), b, stdin=None)
        out = two.communicate(timeout=60)[0]
        assert "REFUSED: another runner already holds" in out and shared[0] in out
    finally:
        one.communicate("\n", timeout=30)
    # and once the first is gone the second may go
    three = _run(_TRIER.format(here=str(HERE), paths=shared), b, stdin=None)
    assert "ACQUIRED" in three.communicate(timeout=60)[0]


def test_an_older_runner_holding_only_the_legacy_lock_still_excludes_this_one(tmp_path):
    fixed, legacy = str(tmp_path / "fixed.lock"), str(tmp_path / "legacy.lock")
    old = _run(_HOLDER.format(here=str(HERE), paths=[legacy]), tmp_path)        # the old code takes one lock
    try:
        assert old.stdout.readline().strip() == "held"
        new = _run(_TRIER.format(here=str(HERE), paths=[fixed, legacy]), tmp_path, stdin=None)
        assert "REFUSED" in new.communicate(timeout=60)[0]
    finally:
        old.communicate("\n", timeout=30)


def test_the_default_acquires_every_lock_path(monkeypatch, tmp_path):
    paths = [str(tmp_path / "x" / "one.lock"), str(tmp_path / "y" / "two.lock")]
    monkeypatch.setattr(RN, "lock_paths", lambda: paths)
    held = RN.acquire_host_lock()
    assert len(held) == 2 and all(Path(p).read_text().strip() == str(os.getpid()) for p in paths)
    with pytest.raises(SystemExit):
        RN.acquire_host_lock()                    # the same process again is a second runner: refused


# ------------------------------------------------------------------------------- the sweep

def _proc(root, pid, cmdline):
    d = Path(root) / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")


LISTING = "\n".join([
    "aaa111 cli-live 4242",           # a LIVE runner's client container
    "bbb222 srv-dead 999999",                   # its runner is gone
    "ccc333 srv-recycled 7777",                 # the pid exists but is some other process now
    "ddd444 cli-old-code",                      # no owner label: an older runner's
    "eee555 cli-ours 31337",                    # started by this very process
])


def _fake_proc(tmp_path):
    root = tmp_path / "proc"
    _proc(root, 4242, "python3 -u runner.py --lanes l1tpc")
    _proc(root, 7777, "bash -c sleep")
    return str(root)


def test_a_live_runners_containers_are_left_alone(tmp_path):
    gone, kept = RN.split_orphans(LISTING, own_pid=31337, proc_root=_fake_proc(tmp_path))
    assert kept == [("cli-live", "4242")]
    assert sorted(n for _, n in gone) == ["cli-old-code", "cli-ours", "srv-dead", "srv-recycled"]


def test_owner_is_alive_means_a_running_runner_not_just_a_pid(tmp_path):
    root = _fake_proc(tmp_path)
    assert RN.owner_is_alive("4242", root)
    assert not RN.owner_is_alive("7777", root) and not RN.owner_is_alive("999999", root)
    assert not RN.owner_is_alive("", root) and not RN.owner_is_alive("not-a-pid", root)


def test_sweep_removes_only_the_orphans(monkeypatch, tmp_path, capsys):
    removed = []
    monkeypatch.setattr(RN, "sh", lambda cmd, **kw: LISTING)
    monkeypatch.setattr(RN.subprocess, "run", lambda cmd, **kw: removed.append(cmd) or SimpleNamespace(stdout=""))
    monkeypatch.setattr(RN.os, "getpid", lambda: 31337)
    RN.sweep_orphans(proc_root=_fake_proc(tmp_path))
    assert removed == [["docker", "rm", "-f", "bbb222", "ccc333", "ddd444", "eee555"]]
    out = capsys.readouterr().out
    assert "leaving cli-live alone: it belongs to the live runner 4242" in out
    assert "aaa111" not in " ".join(removed[0])
    removed.clear()
    monkeypatch.setattr(RN, "sh", lambda cmd, **kw: "aaa111 cli-live 4242")
    RN.sweep_orphans(proc_root=_fake_proc(tmp_path))
    assert removed == []                             # nothing to remove: no docker rm at all


def test_every_container_the_runner_starts_names_its_runner():
    assert RN.RUNNER_LABELS == ("--label", "dbbench=1", "--label", f"dbbench.runner={os.getpid()}")
    src = (HERE / "runner.py").read_text()
    assert src.count("*RUNNER_LABELS") == 2                       # the server and the client container
    assert '"--label", "dbbench=1"' not in src.replace('RUNNER_LABELS = ("--label", "dbbench=1"', "")
    assert '{{.Label "dbbench.runner"}}' in src                  # the sweep reads it
