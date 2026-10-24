"""The version counting rule: X.Y.Z.devN from 0, X.Y.Z, X.Y.Z.postN from 1, never aN/bN/rcN (#471)."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_version.py"
PYPROJECT_FIELD = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


def _load():
    spec = importlib.util.spec_from_file_location("check_version", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_version"] = module
    spec.loader.exec_module(module)
    return module


cv = _load()


@pytest.mark.parametrize(
    "text",
    [
        "26.11.1",
        "26.11.1.dev0",
        "26.11.1.dev12",
        "26.5.1.post1",
        "26.10.2.post7",
        "26.10.2.dev0",
    ],
)
def test_valid_forms(text):
    assert str(cv.parse_version(text)) == text


@pytest.mark.parametrize(
    "text",
    [
        "26.10.2a1",
        "26.10.2.a1",
        "26.10.2b1",
        "26.10.2rc1",
        "26.10.2.rc1",
        "26.10.2-rc1",
        "26.10.2.post0",
        "26.10.2.dev01",
        "26.10.2.post01",
        "26.10.2.dev",
        "26.10.2.post",
        "26.10.2.dev1.post1",
        "26.10.2.post1.dev0",
        "26.10",
        "26.10.2.1",
        "v26.10.2",
        "026.10.2",
        "26.10.2.DEV0",
        "26.10.2+local",
        "",
    ],
)
def test_forbidden_forms(text):
    with pytest.raises(cv.VersionError):
        cv.parse_version(text)


def test_first_dev_is_zero():
    assert str(cv.check_next("26.11.1.dev0", [])) == "26.11.1.dev0"
    with pytest.raises(cv.VersionError, match="dev0"):
        cv.check_next("26.11.1.dev1", [])


def test_dev_increments_without_skipping():
    published = ["26.11.1.dev0", "26.11.1.dev1"]
    assert str(cv.check_next("26.11.1.dev2", published)) == "26.11.1.dev2"
    with pytest.raises(cv.VersionError, match="dev2"):
        cv.check_next("26.11.1.dev3", published)
    with pytest.raises(cv.VersionError, match="already published"):
        cv.check_next("26.11.1.dev1", published)


def test_dev_after_a_gap_continues_from_the_highest():
    # the real history has gaps (26.8.1.dev16 and dev19 were never published); only the highest counts
    assert (
        str(cv.check_next("26.8.1.dev28", ["26.8.1.dev25", "26.8.1.dev27"]))
        == "26.8.1.dev28"
    )


def test_counters_are_per_base():
    published = ["26.8.1.dev9", "26.10.2.post3"]
    assert str(cv.check_next("26.11.1.dev0", published)) == "26.11.1.dev0"


def test_stable_release():
    assert str(cv.check_next("26.11.1", ["26.11.1.dev0", "26.11.1.dev1"])) == "26.11.1"
    with pytest.raises(cv.VersionError, match="already published"):
        cv.check_next("26.11.1", ["26.11.1"])


def test_dev_after_the_release_is_refused():
    with pytest.raises(cv.VersionError, match="already released"):
        cv.check_next("26.11.1.dev5", ["26.11.1", "26.11.1.dev4"])


def test_post_starts_at_one_and_needs_the_release():
    assert str(cv.check_next("26.10.2.post1", ["26.10.2"])) == "26.10.2.post1"
    with pytest.raises(cv.VersionError, match="post1"):
        cv.check_next("26.10.2.post2", ["26.10.2"])
    with pytest.raises(cv.VersionError, match="not been released"):
        cv.check_next("26.10.2.post1", ["26.10.2.dev0"])


def test_post_increments_without_skipping():
    published = ["26.10.2", "26.10.2.post1"]
    assert str(cv.check_next("26.10.2.post2", published)) == "26.10.2.post2"
    with pytest.raises(cv.VersionError, match="post2"):
        cv.check_next("26.10.2.post3", published)


def test_native_series_restarts_at_dev0_on_a_new_base():
    # native 26.10.2.dev0 and dev1 are published under the old base (a naming mistake, they stay);
    # the engine moved to 26.11.1-SNAPSHOT, so the next native preview is 26.11.1.dev0
    old = ["26.10.2.dev0", "26.10.2.dev1"]
    assert str(cv.check_next("26.11.1.dev0", old)) == "26.11.1.dev0"
    with pytest.raises(cv.VersionError, match="dev0"):
        cv.check_next("26.11.1.dev1", old)
    with pytest.raises(cv.VersionError, match="dev0"):
        cv.check_next("26.11.1.dev2", old)
    for form in ("26.11.1a1", "26.11.1b1", "26.11.1rc1", "26.11.1.post0"):
        with pytest.raises(cv.VersionError):
            cv.check_next(form, old)


def test_full_sequence_of_a_base():
    published = ["26.10.2.dev0", "26.10.2.dev1"]
    for version in ("26.11.1.dev0", "26.11.1.dev1", "26.11.1", "26.11.1.post1"):
        cv.check_next(version, published)
        published.append(version)
    with pytest.raises(cv.VersionError):
        cv.check_next("26.11.1.post3", published)


def test_foreign_published_entries_are_ignored():
    assert (
        str(cv.check_next("26.11.1.dev0", ["latest", "26.11.1rc1", "26.11.1a1"]))
        == "26.11.1.dev0"
    )


def test_existing_versions_pass_in_order():
    history = [
        "26.5.1",
        "26.5.1.post1",
        "26.7.2.dev0",
        "26.7.2.dev1",
        "26.7.2.dev2",
        "26.8.1.dev0",
        "26.10.1",
        "26.10.2",
        "26.10.2.post1",
    ]
    published: list[str] = []
    for version in history:
        cv.check_next(version, published)
        published.append(version)


def test_current_pyproject_version_is_syntactically_valid():
    # pyproject.toml carries a placeholder; build.sh and the release workflow write the real version
    text = (SCRIPT_PATH.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    cv.parse_version(PYPROJECT_FIELD.search(text).group(1))


def _run(*args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exit_codes(tmp_path):
    listing = tmp_path / "published.txt"
    listing.write_text("26.11.1.dev0\n26.11.1.dev1\n", encoding="utf-8")
    assert _run("26.11.1.dev2", "--published-file", str(listing)).returncode == 0
    assert _run("26.11.1.dev3", "--published-file", str(listing)).returncode == 1
    assert _run("26.11.1rc1").returncode == 1
    assert _run("26.11.1.dev0").returncode == 0
    assert (
        _run("26.11.1.dev0", "--published-file", "-", stdin="26.11.1.dev0\n").returncode
        == 1
    )


def test_cli_fails_closed_when_a_source_cannot_be_read(tmp_path):
    result = _run("26.11.1.dev0", "--published-file", str(tmp_path / "missing.txt"))
    assert result.returncode == 2
    assert result.stdout.startswith("ERROR")
    assert (
        _run(
            "26.11.1.dev0", "--git-remote", str(tmp_path / "no-such-remote")
        ).returncode
        == 2
    )


def test_git_remote_source_strips_prefix_and_leaves_the_version_itself_out(tmp_path):
    remote = tmp_path / "remote"
    subprocess.run(["git", "init", "-q", str(remote)], check=True)
    git = [
        "git",
        "-C",
        str(remote),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    for tag in ("26.11.1.dev0", "26.11.1.dev1", "native-v26.11.1.dev0"):
        subprocess.run([*git, "tag", tag], check=True)
    # the tag being released is already pushed: it must not count as published
    assert _run("26.11.1.dev1", "--git-remote", str(remote)).returncode == 0
    assert _run("26.11.1.dev2", "--git-remote", str(remote)).returncode == 0
    assert _run("26.11.1.dev3", "--git-remote", str(remote)).returncode == 1
    native = ["--git-remote", str(remote), "--tag-prefix", "native-v"]
    assert _run("26.11.1.dev1", *native).returncode == 0
    assert _run("26.11.1.dev2", *native).returncode == 1
