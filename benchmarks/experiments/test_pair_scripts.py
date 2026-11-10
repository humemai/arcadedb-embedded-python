"""build_c25_wheel.sh, build_matched_pair.sh and verify_pair_c25.sh work on the checkout they live in.

Run with `python -m pytest test_pair_scripts.py -q -rs` from this directory.

They each set REPO=$HOME/repos/humemai/arcadedb-embedded-python, the MAIN checkout, so run from a
worktree they built from, wrote into, and verified against main's bindings/python/dist and .venv:
"PAIR VERIFIED" was a statement about another tree (found re-pin rehearsal, 2026-10-06). REPO is
now derived from the script's own location. `BENCH_PRINT_REPO=1` prints it and exits, which is what
these tests (and a person asking "which tree?") use; the docker steps are not run.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = ("build_c25_wheel.sh", "build_matched_pair.sh", "verify_pair_c25.sh")
MAIN = "/home/tk/repos/humemai/arcadedb-embedded-python"


def _print_repo(script, cwd=None):
    out = subprocess.run(["bash", str(script), "dummy-argument"], capture_output=True, text=True,
                         env={**os.environ, "BENCH_PRINT_REPO": "1"}, cwd=cwd)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.mark.parametrize("name", SCRIPTS)
def test_no_script_names_the_main_checkout(name):
    import re
    text = (HERE / name).read_text()
    assert not re.search(r"^\s*REPO=\$HOME", text, re.M), "REPO is a fixed path again"
    assert not re.search(r'"?\$HOME/repos/humemai/arcadedb-embedded-python', "\n".join(
        l for l in text.splitlines() if not l.lstrip().startswith("#"))), "a command names the main checkout"


@pytest.mark.parametrize("name", SCRIPTS)
def test_repo_is_the_tree_the_script_lives_in(name, tmp_path):
    """A copy of the script in another tree's benchmarks/experiments reports that tree, wherever it is
    run from, and through a symlink too."""
    tree = tmp_path / "some-worktree" / "benchmarks" / "experiments"
    tree.mkdir(parents=True)
    shutil.copy(HERE / name, tree / name)
    want = f"REPO={tmp_path / 'some-worktree'}"
    assert _print_repo(tree / name, cwd="/") == want
    assert _print_repo(tree / name, cwd=str(tmp_path)) == want
    link = tmp_path / "elsewhere" / name
    link.parent.mkdir()
    link.symlink_to(tree / name)
    assert _print_repo(link, cwd="/") == want
    assert want != f"REPO={MAIN}"


@pytest.mark.parametrize("name", SCRIPTS)
def test_this_checkouts_scripts_report_this_checkout(name):
    assert _print_repo(HERE / name, cwd="/") == f"REPO={HERE.parents[1]}"


def test_the_wheel_script_takes_its_work_directory_from_the_environment():
    text = (HERE / "build_c25_wheel.sh").read_text()
    assert 'WORK="${C25_WORK:-$HOME/engine-builds/c25}"' in text
    assert "LIB=$WORK/ctx/arcadedb-assembly/lib" in text
    # the matched-pair builder deletes its work directory: it must refuse an empty or root one
    pair = (HERE / "build_matched_pair.sh").read_text()
    assert 'rm -rf "$WORK"' in pair and '[ "$WORK" != / ]' in pair


# A wheels-only X.Y.Z.postN carries the engine of X.Y.Z (DECISIONS #297): the native package's _build_info.ENGINE_VERSION says X.Y.Z while the wheel
# is X.Y.Z.postN, and the pair check refused it ("PAIR UNVERIFIED ... native engine is '26.11.1', the wheel is 26.11.1.post2") on the 2026-11-11 smoke.
@pytest.mark.parametrize("engine,wheel,ok", [
    ("26.11.1", "26.11.1.post2", True),          # the post2 native wheel: engine of its base version
    ("26.11.1", "26.11.1.post1", True),
    ("26.11.1", "26.11.1", True),
    ("26.11.1.dev0", "26.11.1.dev0", True),      # unchanged: .devN on both sides
    ("26.11.1", "26.11.1.dev0", True),           # unchanged: a snapshot jar reports the bare version
    ("26.11.2", "26.11.1.post2", False),         # a different base version must still fail
    ("26.11.1", "26.11.2.post2", False),
    ("26.11.1.post2", "26.11.1.post2", False),   # only the wheel side is stripped: an engine that says .postN is not the engine of 26.11.1
    ("26.11.1", "26.11.1.postx", False),         # .postN needs digits
    ("", "26.11.1.post2", False),                # the image did not answer
])
def test_the_pair_check_compares_the_engine_with_the_wheels_base_version(engine, wheel, ok):
    out = subprocess.run(["bash", str(HERE / "verify_pair_c25.sh"), "dummy-argument"], capture_output=True, text=True,
                         env={**os.environ, "BENCH_PAIR_VERSION_CHECK": f"{engine} {wheel}".strip()})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ("MATCH" if ok else "MISMATCH"), (engine, wheel, out)


def test_the_native_engine_check_calls_that_comparison():
    """The tested function is the one the check runs, and the old .devN-only comparison is gone."""
    text = (HERE / "verify_pair_c25.sh").read_text()
    assert 'engine_matches "$NV" "$WV" || fail' in text
    assert '[ "${NV%.dev*}" = "${WV%.dev*}" ]' not in text
