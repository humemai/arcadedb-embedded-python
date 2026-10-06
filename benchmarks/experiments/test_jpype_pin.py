"""JPype is pinned in the benchmark images and recorded on every row (CAMPAIGN section 7, row 73).

Run with `python -m pytest test_jpype_pin.py -q -rs` from this directory.

The wheel declares `jpype1>=1.5.0` with no upper bound, and Dockerfile.bench used to resolve the newest JPype
at image build time. JPype master changes raw call costs by 15 to 25 percent and stops leaking one Python
object per boxed number, so an image rebuilt on the day of the next release would change the instrument in
the middle of a campaign and split its rows. These tests hold the whole chain: the recipe installs a hard
`==`, the generator refuses a recipe whose default is another version, every stage aborts when the image or
the repo venv runs another JPype (the message is run, not read), and every row says which JPype ran.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import make_2610_stages as G  # noqa: E402

PIN = "1.7.1"
DOCKERFILE = (HERE / "Dockerfile.bench").read_text()


# --------------------------------------------------------------------------- the recipe
def test_the_pin_is_one_release_and_the_dockerfile_default_is_the_same_number():
    assert bench_common.JPYPE_PIN == PIN
    assert re.findall(r"^ARG JPYPE_VERSION=(\S+)$", DOCKERFILE, re.M) == [PIN]


def test_every_jpype_install_in_the_dockerfile_is_a_hard_equals_on_the_arg():
    code = "\n".join(l for l in DOCKERFILE.splitlines() if not l.lstrip().startswith("#"))
    assert code.count("jpype1==${JPYPE_VERSION}") == 2          # beside the local wheel, and beside PIP_PACKAGES
    assert not re.findall(r"jpype1(?!==\$\{JPYPE_VERSION\})", code), "a jpype1 install that is not a hard =="
    assert ">=" not in code.split("RUN", 1)[1]


def _run_block():
    """The Dockerfile's one RUN line, continuations joined, pointed at a scratch wheel directory."""
    run = DOCKERFILE.split("RUN ", 1)[1].split("\n\n", 1)[0]
    return re.sub(r"\\\n\s*", " ", run)


def _build(tmp_path, *, wheel, pip_packages, installed, arg=PIN):
    """Run the Dockerfile's RUN block with a recording `pip` and a fake JPype of the version `installed`
    (None: not installed), and return (returncode, pip command lines, stderr)."""
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    if wheel:
        (wheels / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl").write_bytes(b"x")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "pip.log"
    (bindir / "pip").write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
    # -S: no site-packages, so a JPype installed in the interpreter running this test is never seen
    (bindir / "python").write_text(f'#!/bin/sh\nexec {sys.executable} -S "$@"\n')
    for f in bindir.iterdir():
        f.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "JPYPE_VERSION": arg,
           "PIP_PACKAGES": pip_packages, "PYTHONPATH": ""}
    if installed is not None:
        fake = tmp_path / "fake" / "jpype"
        fake.mkdir(parents=True)
        (fake / "__init__.py").write_text(f'__version__ = "{installed}"\n')
        env["PYTHONPATH"] = str(tmp_path / "fake")
    script = _run_block().replace("/tmp/wheels", str(wheels))
    r = subprocess.run(["sh", "-c", script], env=env, capture_output=True, text=True)
    pips = log.read_text().splitlines() if log.exists() else []
    return r.returncode, pips, r.stderr


def test_the_local_wheel_is_installed_in_the_same_pip_command_as_the_jpype_pin(tmp_path):
    rc, pips, err = _build(tmp_path, wheel=True, pip_packages="numpy==2.5.3", installed=PIN)
    assert rc == 0, err
    assert len(pips) == 2
    assert ".whl" in pips[0] and f"jpype1=={PIN}" in pips[0]
    assert "numpy==2.5.3" in pips[1] and "jpype" not in pips[1]


def test_an_image_that_installs_arcadedb_embedded_from_pypi_pins_jpype_in_that_command(tmp_path):
    rc, pips, err = _build(tmp_path, wheel=False, pip_packages="arcadedb-embedded==26.8.1 numpy==2.5.3", installed=PIN)
    assert rc == 0, err
    assert len(pips) == 1 and "arcadedb-embedded==26.8.1" in pips[0] and f"jpype1=={PIN}" in pips[0]


def test_a_comparator_image_gets_no_jpype_and_no_check(tmp_path):
    rc, pips, err = _build(tmp_path, wheel=False, pip_packages="duckdb==1.5.4 numpy==2.5.3", installed=None)
    assert rc == 0, err
    assert len(pips) == 1 and "jpype" not in pips[0]


def test_the_build_fails_when_the_installed_jpype_is_not_the_pin(tmp_path):
    rc, pips, err = _build(tmp_path, wheel=True, pip_packages="", installed="1.7.2")
    assert rc != 0
    assert "JPype 1.7.2 is installed, the pin is 1.7.1" in err


def test_build_images_reads_the_default_from_the_dockerfile_and_passes_it_down():
    text = (HERE / "build_images.sh").read_text()
    assert "sed -n 's/^ARG JPYPE_VERSION=//p' Dockerfile.bench" in text
    assert '--build-arg JPYPE_VERSION="$JPYPE_VERSION"' in text
    assert "REFUSING: Dockerfile.bench has no usable" in text
    r = subprocess.run(["bash", "-c", "sed -n 's/^ARG JPYPE_VERSION=//p' Dockerfile.bench"], cwd=HERE,
                       capture_output=True, text=True)
    assert r.stdout.strip() == PIN
    assert subprocess.run(["bash", "-n", str(HERE / "build_images.sh")]).returncode == 0


def test_the_pair_check_reads_the_pin_from_the_dockerfile_and_checks_the_embedded_image():
    text = (HERE / "verify_pair_c25.sh").read_text()
    assert """sed -n 's/^ARG JPYPE_VERSION=//p' "$HERE/Dockerfile.bench\"""" in text
    assert "import jpype; print(jpype.__version__)" in text and '"$EMBEDDED_IMAGE"' in text
    assert "runs JPype '$HAVE_J', the pin is $WANT_J" in text
    assert subprocess.run(["bash", "-n", str(HERE / "verify_pair_c25.sh")]).returncode == 0


# --------------------------------------------------------------------------- the generator
def test_the_check_passes_on_this_tree():
    assert G.check_jpype_pin() == []
    assert G.main(["--check"]) == 0


def test_check_refuses_a_dockerfile_default_that_is_not_the_pin(tmp_path, capsys, monkeypatch):
    other = tmp_path / "Dockerfile.bench"
    other.write_text(DOCKERFILE.replace(f"ARG JPYPE_VERSION={PIN}", "ARG JPYPE_VERSION=1.7.2"))
    monkeypatch.setattr(G, "JPYPE_DOCKERFILE", str(other))
    assert G.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "PROBLEM jpype pin" in out and "1.7.2" in out and PIN in out
    # and nothing else ran: no coverage line after a refused pin
    assert "coverage:" not in out


def test_check_refuses_a_constant_that_moved_without_the_dockerfile(capsys, monkeypatch):
    monkeypatch.setattr(bench_common, "JPYPE_PIN", "1.7.2")
    assert G.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "PROBLEM jpype pin" in out and "builds JPype 1.7.1" in out and "JPYPE_PIN is 1.7.2" in out


@pytest.mark.parametrize("bad", ["jpype1>=1.5.0", "jpype1", "jpype1<2", "jpype1~=1.7"])
def test_check_refuses_an_install_line_that_is_not_a_hard_equals(bad):
    text = DOCKERFILE.replace('"jpype1==${JPYPE_VERSION}"', f'"{bad}"', 1)
    problems = G.check_jpype_pin(dockerfile_text=text)
    assert problems and any("not a hard" in p and bad in p for p in problems)


def test_check_refuses_a_pin_that_is_a_range_and_a_dockerfile_with_two_defaults():
    assert any("not one release" in p for p in G.check_jpype_pin(pin=">=1.7"))
    twice = DOCKERFILE.replace(f"ARG JPYPE_VERSION={PIN}", f"ARG JPYPE_VERSION={PIN}\nARG JPYPE_VERSION={PIN}")
    assert any("expected exactly 1" in p for p in G.check_jpype_pin(dockerfile_text=twice))
    gone = DOCKERFILE.replace('jpype1==${JPYPE_VERSION}', "numpy")
    assert any("never installs" in p for p in G.check_jpype_pin(dockerfile_text=gone))


# --------------------------------------------------------------------------- the stages
@pytest.fixture(scope="module")
def stages(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("jpype-stages")
    wheel = tmp / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp / "stages"
    r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out), "--after", "none"],
                       cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return out


def _stage_ids():
    host = [s[0] for s in G.STAGES if s[2] == "pycost"]
    runner_stages = [s[0] for s in G.STAGES if s[2] != "pycost"]
    assert len(host) == 1 and runner_stages
    return host[0], runner_stages


def test_every_runner_stage_reads_jpype_out_of_the_image_after_the_build(stages):
    host, runner_stages = _stage_ids()
    for sid in runner_stages:
        text = (stages / f"{sid}.sh").read_text()
        assert text.count("import jpype; print(jpype.__version__)") == 1, sid
        assert f'[ "$IJ" = "{PIN}" ]' in text, sid
        # after the image build and the wheel check, before the pair check and the first cell
        assert text.index("./build_images.sh") < text.index('IJ=$(docker run') < text.index("./verify_pair_c25.sh"), sid
        assert text.index('IJ=$(docker run') < text.index('trap \'echo "$ID ALL-DONE"'), sid


def test_the_host_stage_checks_the_repo_venv_and_names_the_pinned_install(stages):
    host, _ = _stage_ids()
    text = (stages / f"{host}.sh").read_text()
    assert f'[ "$HAVE_J" = "{PIN}" ]' in text
    assert f"uv pip install --python $REPO/.venv jpype1=={PIN}" in text
    assert f"whl jpype1=={PIN}" in text            # the wheel's own install hint carries the pin too
    assert text.index("HAVE_J=") < text.index("mkdir -p")


def _snippet(text, first, last):
    lines = text.splitlines()
    a = next(i for i, l in enumerate(lines) if l.startswith(first))
    b = next(i for i, l in enumerate(lines) if i >= a and last in l)
    return "\n".join(lines[a:b + 1])


def _run_snippet(tmp_path, preamble, snippet):
    status = tmp_path / "STATUS.txt"
    script = f'set -u\nID=qRX\nS={status}\nsay() {{ echo "$*" >> "$S"; }}\n{preamble}\n{snippet}\necho PASSED\n'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return r, (status.read_text() if status.exists() else "")


@pytest.mark.parametrize("image_says,aborts", [(PIN, False), ("1.7.2", True), ("1.8.0.dev0", True), ("", True)])
def test_a_runner_stage_aborts_when_the_image_runs_another_jpype(stages, tmp_path, image_says, aborts):
    _, runner_stages = _stage_ids()
    text = (stages / f"{runner_stages[0]}.sh").read_text()
    snippet = _snippet(text, "IJ=$(docker run", "ABORT: dbbench:arcadedb runs JPype")
    r, status = _run_snippet(tmp_path, f"docker() {{ printf '%s\\n' '{image_says}'; }}", snippet)
    if not aborts:
        assert r.returncode == 0 and "PASSED" in r.stdout and status == ""
        return
    assert r.returncode == 1 and "PASSED" not in r.stdout
    # the message names the stage, the image, the version found, the pin, and what to do
    assert f"qRX ABORT: dbbench:arcadedb runs JPype '{image_says}', the pin is {PIN} " in status
    assert "Dockerfile.bench" in status and "rebuild dbbench:arcadedb" in status


@pytest.mark.parametrize("venv_says,aborts", [(PIN, False), ("1.7.2", True), ("", True)])
def test_the_host_stage_aborts_when_the_repo_venv_runs_another_jpype(stages, tmp_path, venv_says, aborts):
    host, _ = _stage_ids()
    text = (stages / f"{host}.sh").read_text()
    snippet = _snippet(text, "HAVE_J=", "ABORT: the repo venv runs JPype")
    py = tmp_path / "repo" / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f"#!/bin/sh\n[ -n '{venv_says}' ] && echo '{venv_says}'\nexit 0\n")
    py.chmod(0o755)
    r, status = _run_snippet(tmp_path, f"REPO={tmp_path / 'repo'}", snippet)
    if not aborts:
        assert r.returncode == 0 and "PASSED" in r.stdout and status == ""
        return
    assert r.returncode == 1 and "PASSED" not in r.stdout
    assert f"qRX ABORT: the repo venv runs JPype '{venv_says}', the pin is {PIN}; install it first: " in status
    assert f"uv pip install --python {tmp_path / 'repo'}/.venv jpype1=={PIN}" in status


def test_the_stages_carry_the_pin_the_generator_holds_not_a_literal_of_their_own(stages, monkeypatch, tmp_path):
    """A pin moved in bench_common (with the Dockerfile) reaches the generated scripts."""
    dockerfile = tmp_path / "Dockerfile.bench"
    dockerfile.write_text(DOCKERFILE.replace(f"ARG JPYPE_VERSION={PIN}", "ARG JPYPE_VERSION=1.7.2"))
    monkeypatch.setattr(bench_common, "JPYPE_PIN", "1.7.2")
    monkeypatch.setattr(G, "JPYPE_DOCKERFILE", str(dockerfile))
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"x")
    out = tmp_path / "moved"
    out.mkdir()
    G.emit_all(str(out), {"ARCADEDB_ENGINE_COMMIT": "d36b4ca3ae4c170abc73598e0dffa2bb58e06621",
                          "ARCADEDB_WHEEL": str(wheel), "ARCADEDB_SERVER_IMAGE": "arcadedb-c25:26.10.1"},
               None, allow_dev=False)
    host, runner_stages = _stage_ids()
    assert '[ "$IJ" = "1.7.2" ]' in (out / f"{runner_stages[0]}.sh").read_text()
    assert '[ "$HAVE_J" = "1.7.2" ]' in (out / f"{host}.sh").read_text()
    assert PIN not in "".join(re.findall(r'\[ "\$(?:IJ|HAVE_J)" = "[^"]+" \]', (out / f"{host}.sh").read_text()))


# --------------------------------------------------------------------------- the rows
class _FakeJpype:
    __version__ = "9.9.9"


def test_a_row_built_by_the_recording_path_carries_the_jpype_the_process_ran(monkeypatch):
    monkeypatch.setitem(sys.modules, "jpype", _FakeJpype)
    cond = bench_common.run_conditions(lane="l3d", scale="micro", backend="arcadedb_dense_embedded")
    assert cond["jpype_version"] == "9.9.9"
    assert bench_common.jpype_fields() == {"jpype_version": "9.9.9"}


def test_an_arm_that_never_imports_jpype_records_an_empty_value_and_never_imports_it(monkeypatch):
    monkeypatch.delitem(sys.modules, "jpype", raising=False)
    cond = bench_common.run_conditions(lane="l3d", scale="micro", backend="duckdb_dense")
    assert "jpype_version" in cond and cond["jpype_version"] == ""
    assert "jpype" not in sys.modules, "asking which JPype ran must not load it"


def test_the_row_reads_the_loaded_module_not_the_pin_and_not_the_package_metadata(monkeypatch):
    class Other:
        __version__ = "1.8.0"
    monkeypatch.setitem(sys.modules, "jpype", Other)
    assert bench_common.jpype_version() == "1.8.0" != bench_common.JPYPE_PIN


def test_a_row_stamped_by_the_real_jpype_carries_its_version(monkeypatch):
    jpype = pytest.importorskip("jpype")
    monkeypatch.setitem(sys.modules, "jpype", jpype)
    assert bench_common.run_conditions(lane="l3d")["jpype_version"] == jpype.__version__ != ""


def _calls(tree, name):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and (getattr(n.func, "attr", None) == name or getattr(n.func, "id", None) == name)]


@pytest.mark.parametrize("script", ["l1_tabular.py", "l1_tpc.py", "l2_graph.py", "e2_hybrid.py", "l5_lifecycle_server.py"])
def test_lane_writers_that_skip_run_conditions_stamp_the_version_before_they_write(script):
    tree = ast.parse((HERE / script).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    stamps = _calls(main, "jpype_fields") + _calls(main, "_jpype_fields")
    dumps = [n for n in _calls(main, "dump") if n.args and getattr(n.args[0], "id", None) == "out"]
    assert len(stamps) == 1 and len(dumps) >= 1, script
    assert stamps[0].lineno < min(d.lineno for d in dumps), f"{script} writes the row before stamping jpype_version"


def test_every_lane_script_the_runner_registers_records_the_version():
    import runner
    scripts = {spec[0] for spec in runner.LANES.values()}
    # the e4 lane's rows come from the probe it drives; the lifecycle lane dispatches to its engine scripts
    scripts = {("deployment_decomp_probe.py" if s == "e4_decomp.py" else s) for s in scripts}
    scripts |= {p.name for p in HERE.glob("l5_lifecycle_*.py")}
    assert {"l1_tabular.py", "l2_graph.py", "l3_sparse.py", "l4_tsbs.py", "l6_restart.py"} <= scripts
    missing = [s for s in sorted(scripts)
               if not re.search(r"run_conditions\(|jpype_fields\(", (HERE / s).read_text())]
    assert not missing, f"lane scripts whose rows cannot say which JPype ran: {missing}"


# --------------------------------------------------------------------------- the manifest and the gate
def _args():
    from types import SimpleNamespace
    return SimpleNamespace(tier="paper", scale="micro", reps=5, seed=7)


def test_the_manifest_records_the_jpype_the_bench_image_holds(monkeypatch):
    import runner
    monkeypatch.setattr(runner, "image_digest", lambda image: "sha256:test")
    asked = []
    monkeypatch.setattr(runner, "jpype_version_in_image", lambda image: asked.append(image) or "1.7.1")
    m = runner.build_manifest("t", _args(), 1, ["0-11"], [{"backend": "arcadedb_embedded"}, {"backend": "duckdb"}])
    assert m["jpype_version"] == "1.7.1" and asked == ["dbbench:arcadedb"]


def test_the_manifest_records_an_empty_value_when_no_arm_runs_in_the_arcadedb_image(monkeypatch):
    import runner
    monkeypatch.setattr(runner, "image_digest", lambda image: "sha256:test")
    monkeypatch.setattr(runner, "jpype_version_in_image", lambda image: pytest.fail("no embedded ArcadeDB arm here"))
    assert runner.build_manifest("t", _args(), 1, ["0-11"], [{"backend": "duckdb"}])["jpype_version"] == ""
    assert runner.build_manifest("t", _args(), 1, ["0-11"], [])["jpype_version"] == ""


def test_the_image_reader_returns_the_last_line_and_an_empty_value_for_anything_unreadable(monkeypatch):
    import runner

    def fake(stdout, rc=0, exc=None):
        def run(cmd, **kw):
            assert cmd[:5] == ["docker", "run", "--rm", "--entrypoint", "python3"]
            assert cmd[-1] == "import jpype; print(jpype.__version__)"
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, rc, stdout, "")
        return run

    monkeypatch.setattr(runner.subprocess, "run", fake("noise\n1.7.1\n"))
    assert runner.jpype_version_in_image("dbbench:arcadedb") == "1.7.1"
    monkeypatch.setattr(runner.subprocess, "run", fake("", rc=1))
    assert runner.jpype_version_in_image("dbbench:arcadedb") == ""
    monkeypatch.setattr(runner.subprocess, "run", fake("1.7.1\n", rc=1))
    assert runner.jpype_version_in_image("dbbench:arcadedb") == ""
    monkeypatch.setattr(runner.subprocess, "run", fake("", exc=FileNotFoundError("docker")))
    assert runner.jpype_version_in_image("dbbench:arcadedb") == ""
    monkeypatch.setattr(runner.subprocess, "run", fake("", exc=subprocess.TimeoutExpired("docker", 1)))
    assert runner.jpype_version_in_image("dbbench:arcadedb") == ""


def test_the_page_gate_declares_the_row_field():
    import page_check
    reason = page_check._not_printed_reason("jpype_version")
    assert reason and "CAMPAIGN 7 row 73" in reason, "A2 (every measured field is a column or in NOT_PRINTED) would flag every row"


def test_campaign_section_7_has_row_73_and_names_the_measurement():
    text = (HERE / "CAMPAIGN.md").read_text()
    row = next(l for l in text.splitlines() if l.startswith("| 73 |"))
    assert "JPype is pinned to 1.7.1 in the benchmark images and recorded per row" in row
    assert ".notes/bench/repros/jpype-master-check-20261006/" in row
    assert "\u2014" not in row and "\u2013" not in row
