"""land_stage.py --apply lands from a NEW branch and never pushes `main` (the owner's rule of 2026-11-14: rows land through a pull request,
and `main` of the bindings repo stays frozen until the comparator pass ends).

The rehearsal of 2026-11-14 found `--apply` ended with `git push origin main` in both repos it pushes to. Two tests:

  * `--apply` with no `--branch`, or with `--branch main`, is refused BEFORE anything is pulled, merged or built: every command the
    script could run is replaced by one that fails the test, so an old script that gets that far fails instead of acting;
  * the publish step (`publish_branch`) is run for real against two scratch repos with a bare origin each (the bindings repo and the
    site): afterwards each origin holds the new branch with the commit and its `main` has not moved.

Light: temporary git repos only, no pytest fixture, no network. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage as L  # noqa: E402


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def _repo_with_origin(root, name):
    bare, work = root / f"{name}.git", root / name
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for k, v in (("user.email", "t@example.org"), ("user.name", "t"), ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null")):
        _git(work, "config", k, v)
    (work / "base.txt").write_text("base\n")
    _git(work, "add", "base.txt")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-q", "origin", "main")
    return work, bare


def test_apply_needs_a_branch_and_never_a_protected_one():
    ran = []

    def forbidden(cmd, *a, **k):
        ran.append(cmd)
        raise AssertionError(f"nothing may run before the refusal: {cmd}")

    for extra in ([], ["--branch", "main"], ["--branch", "master"]):
        argv = ["land_stage.py", "--pin", "abc123def", "--apply", "--message", "m", *extra]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sys, "argv", argv), mock.patch.object(L, "SCRATCH", Path(d)), \
                mock.patch.object(L, "sh", forbidden), mock.patch.object(L.subprocess, "run", forbidden), \
                mock.patch.object(L.os, "execv", lambda *a, **k: None):
            try:
                L.main()
            except SystemExit as e:
                msg = str(e.code)
            else:
                raise AssertionError(f"main() returned for {extra}")
        assert msg.startswith("REFUSING") and "--branch" in msg, (extra, msg)
        assert not ran, ran


def test_publish_pushes_the_branch_of_both_repos_and_never_main():
    real_sh = L.sh

    def sh(cmd, **kw):
        if list(cmd[:2]) == ["npm", "run"]:                      # the site build is not what is tested here
            return subprocess.CompletedProcess(cmd, 0)
        return real_sh(cmd, **kw)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        repo, repo_origin = _repo_with_origin(root, "repo")
        site, site_origin = _repo_with_origin(root, "site")
        (site / "payload.json").write_text("{}\n")
        (repo / "frozen.csv").write_text("a,b\n")
        main_before = {o: _git(o, "rev-parse", "main") for o in (repo_origin, site_origin)}
        out = io.StringIO()
        with mock.patch.object(L, "REPO", repo), mock.patch.object(L, "SITE", site), mock.patch.object(L, "sh", sh), \
                contextlib.redirect_stdout(out):
            rc = L.publish_branch("land-rows-test", "rows test", ["payload.json"], ["frozen.csv"])
        assert rc == 0, out.getvalue()
        for origin, path, name in ((repo_origin, "frozen.csv", "bindings"), (site_origin, "payload.json", "site")):
            assert _git(origin, "rev-parse", "main") == main_before[origin], f"main of the {name} repo moved"
            assert _git(origin, "rev-parse", "land-rows-test") != main_before[origin], f"the {name} repo has no commit on the branch"
            assert _git(origin, "show", f"land-rows-test:{path}"), f"the {name} branch lacks {path}"
        assert "land-rows-test" in out.getvalue() and "pull request" in out.getvalue()
