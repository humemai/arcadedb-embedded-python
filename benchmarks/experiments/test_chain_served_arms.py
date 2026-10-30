"""The served ArcadeDB cells run in ONE chain: the JVM chain. The native chain skips them, and a check fails when both have them.

The server is the ARCADEDB_SERVER_IMAGE container, the same Java server whichever wheel is installed; a second run would put two sets of
rows under one key. Run with `python -m pytest test_chain_served_arms.py -q` from this directory. Nothing is run: only drafts are written.
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_stage_generator_2611 as T  # noqa: E402

G = T.G
NATIVE_WHEEL = T.REL_WHEEL.replace("arcadedb_embedded-", "arcadedb-")
JVM_WHEEL = T.REL_WHEEL.replace("arcadedb_embedded-", "arcadedb_jvm-")


def _chain(tmp_path, name, wheel, prefix):
    out = tmp_path / name
    r = T.run(T._release_args(**{"--wheel-name": wheel, "--wheel-url": "https://files.pythonhosted.org/packages/x/" + wheel})
              + ["--after", "none", "--id-prefix", prefix, "--out", str(out)])
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    return out


def _arms(directory):
    found = set()
    for f in Path(directory).glob("*.sh"):
        for m in re.finditer(r'^BACKENDS="([^"]*)"', f.read_text(), re.M):
            found.update(m.group(1).split())
    return found


@pytest.fixture(scope="module")
def chains(tmp_path_factory):
    root = tmp_path_factory.mktemp("chains")
    return _chain(root, "native", NATIVE_WHEEL, "qN"), _chain(root, "jvm", JVM_WHEEL, "qJ"), _chain(root, "old", T.REL_WHEEL, "qO")


def test_the_served_arcadedb_arms_are_the_client_server_ones():
    served = G.served_arcadedb_arms()
    assert "arcadedb_server" in served and "arcadedb_graph_server" in served
    assert not [b for b in served if "embedded" in b and "server" not in b]
    assert "arcadedb_graph_embedded" not in served


def test_the_native_chain_runs_no_served_arcadedb_cell_and_keeps_the_embedded_ones(chains):
    native, jvm, _old = chains
    served = set(G.served_arcadedb_arms())
    assert _arms(native) and not (_arms(native) & served)
    assert any(b.startswith("arcadedb") for b in _arms(native))
    assert _arms(jvm) & served                                             # the JVM chain is the one that runs the server


def test_the_jvm_chain_and_a_chain_of_an_old_wheel_are_unchanged_by_the_native_rule(chains):
    _native, jvm, old = chains
    assert _arms(jvm) == _arms(old)                                        # arcadedb_embedded wheels are the JVM build


def test_the_two_chains_of_one_release_pass_the_overlap_check(chains):
    native, jvm, _old = chains
    assert G.chain_overlap_problems(str(native), str(jvm)) == []


def test_the_overlap_check_fails_when_a_served_arm_is_in_both_chains(chains):
    _native, jvm, old = chains
    problems = G.chain_overlap_problems(str(jvm), str(old))
    assert problems and all("one image" in p for p in problems)
    assert any("arcadedb_graph_server" in p for p in problems)


def test_a_native_draft_that_runs_a_served_arm_fails_the_lint(chains):
    native, jvm, _old = chains
    served_stage = next(f for f in sorted(jvm.glob("*.sh")) if G.served_arcadedb_in(f.read_text()))
    forged = served_stage.read_text().replace("dist/" + JVM_WHEEL, "dist/" + NATIVE_WHEEL)
    assert "dist/" + NATIVE_WHEEL in forged
    assert any("native-build chain runs served ArcadeDB arms" in p for p in G.lint_draft(forged, "qN01.sh"))
    clean = next(f for f in sorted(native.glob("*.sh")) if 'BACKENDS="' in f.read_text())
    assert not [p for p in G.lint_draft(clean.read_text(), clean.name) if "native-build chain" in p]


def test_the_native_chain_names_its_overlay_files_by_build(chains):
    native, jvm, _old = chains
    text = lambda d: "".join(f.read_text() for f in d.glob("*.sh"))  # noqa: E731
    assert "mp_{label}_native_b{rep}.json" in text(native)
    assert "mp_{label}_native_b{rep}.json" not in text(jvm)
