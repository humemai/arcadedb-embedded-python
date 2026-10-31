"""Each chain runs exactly the served ArcadeDB arm of its own build, each once: the native chain on upstream's native server image, the JVM
chain on the Docker JVM server (#222). Run with `python -m pytest test_chain_served_arms.py -q` from this directory. Nothing is run: only drafts are written.
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


def test_the_native_chain_runs_the_served_arms_of_its_build_and_keeps_the_embedded_ones(chains):
    native, jvm, _old = chains
    served = set(G.served_arcadedb_arms())
    per_build = served - set(G.build_less_served_arms())
    assert "arcadedb_server" in per_build and "arcadedb_graph_server" in per_build
    ran = _arms(jvm) & per_build                                           # the arms this profile runs at all
    assert {"arcadedb_server", "arcadedb_graph_server"} <= ran
    assert _arms(native) & per_build == ran                                # each chain runs the served arm of its own build, the same ones
    assert any(b.startswith("arcadedb") for b in _arms(native))
    # the arms with no native counterpart (the JVM image-defaults arm; e4 mixes the wheel with the JVM image) run in the JVM chain only
    assert set(G.build_less_served_arms()) >= {"arcadedb_imgdefaults_server", "arcadedb_e4"}
    assert not (_arms(native) & set(G.build_less_served_arms()))
    assert set(G.build_less_served_arms()) & _arms(jvm)


def test_the_jvm_chain_and_a_chain_of_an_old_wheel_are_unchanged_by_the_native_rule(chains):
    _native, jvm, old = chains
    assert _arms(jvm) == _arms(old)                                        # arcadedb_embedded wheels are the JVM build
    text = lambda d: "".join(f.read_text() for f in d.glob("*.sh"))  # noqa: E731
    assert "ARCADEDB_NATIVE_SERVER_IMAGE" not in text(jvm) and "ARCADEDB_NATIVE_SERVER_IMAGE" not in text(old)
    assert "BENCH_SERVER_BUILD" not in text(jvm)


def test_the_native_chain_pins_upstreams_native_server_image_and_checks_its_commit(chains):
    native, _jvm, _old = chains
    text = "".join(f.read_text() for f in native.glob("*.sh"))
    assert 'export ARCADEDB_NATIVE_SERVER_IMAGE="arcadedata/arcadedb:26.10.2-native" BENCH_SERVER_BUILD="native"' in text \
        or re.search(r'export ARCADEDB_NATIVE_SERVER_IMAGE="arcadedata/arcadedb:[\d.]+-native" BENCH_SERVER_BUILD="native"', text)
    assert 'verify_native_server_image.sh "$ARCADEDB_NATIVE_SERVER_IMAGE" "$SHA"' in text
    assert "ABORT: native server image is not at the pin" in text


def test_the_two_chains_of_one_release_pass_the_served_arm_check(chains):
    native, jvm, _old = chains
    assert G.chain_served_problems(str(native), str(jvm)) == []


def test_the_served_arm_check_fails_for_two_chains_of_one_build(chains):
    _native, jvm, old = chains
    problems = G.chain_served_problems(str(jvm), str(old))
    assert any("same build" in p for p in problems)


def test_the_served_arm_check_fails_when_a_chain_lacks_a_served_arm(chains, tmp_path):
    native, jvm, _old = chains
    cut = tmp_path / "native_cut"
    cut.mkdir()
    victim = next(f for f in sorted(native.glob("*.sh")) if G.served_arcadedb_in(f.read_text()))
    for f in native.glob("*.sh"):
        if f != victim:
            (cut / f.name).write_text(f.read_text())
    problems = G.chain_served_problems(str(cut), str(jvm))
    assert any("each chain runs it once" in p for p in problems)


def test_a_chain_that_runs_the_other_builds_server_arm_fails_the_lint(chains):
    native, jvm, _old = chains
    nat = next(f for f in sorted(native.glob("*.sh")) if G.served_arcadedb_in(f.read_text()))
    jv = next(f for f in sorted(jvm.glob("*.sh")) if G.served_arcadedb_in(f.read_text()))
    # a native chain naming the JVM server build
    forged = nat.read_text().replace('BENCH_SERVER_BUILD="native"', 'BENCH_SERVER_BUILD="jvm"')
    assert any("native-build chain runs the jvm build's server arm" in p for p in G.lint_draft(forged, nat.name))
    # a JVM chain naming the native one
    forged = jv.read_text().replace("export ARCADEDB_WHEEL=", 'export BENCH_SERVER_BUILD="native"\nexport ARCADEDB_WHEEL=')
    assert any("JVM-build chain runs the native build's server arm" in p for p in G.lint_draft(forged, jv.name))
    # a native chain with no pin or no check
    missing = nat.read_text().replace('export ARCADEDB_NATIVE_SERVER_IMAGE=', 'export SOMETHING_ELSE=')
    assert any("no the native server image pin" in p for p in G.lint_draft(missing, nat.name))
    clean = G.lint_draft(nat.read_text(), nat.name)
    assert not [p for p in clean if "server" in p and "native" in p], clean
    assert not [p for p in G.lint_draft(jv.read_text(), jv.name) if "server arm" in p]


def test_the_native_chain_names_its_overlay_files_by_build(chains):
    native, jvm, _old = chains
    text = lambda d: "".join(f.read_text() for f in d.glob("*.sh"))  # noqa: E731
    assert "mp_{label}_native_b{rep}.json" in text(native)
    assert "mp_{label}_native_b{rep}.json" not in text(jvm)
