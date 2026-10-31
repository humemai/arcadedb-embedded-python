"""A benchmark cell cannot run an ArcadeDB build other than the stage's pinned version (engine_pin.py, 2026-10-22).

Run with `python -m pytest test_engine_pin.py -q` from this directory. Nothing here times a cell or builds an image: docker is a fake.

The incident: after October was retired the laptop still held `dbbench:arcadedb` at 26.10.1 beside `dbbench:arcadedb-26102` at 26.10.2, and the
only checks read rows after the run. These tests hold the two new rules: the version is read out of the image that will run, before any cell,
and no ArcadeDB image tag is floating.
"""
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine_pin as E  # noqa: E402
import runner  # noqa: E402

PIN = "26.10.2"
WHEEL = f"arcadedb_embedded-{PIN}-cp312-cp312-manylinux_2_34_x86_64.whl"


def fake_docker(images):
    """A subprocess.run stand-in. `images` maps an image to ("embedded", wheel_version, [jar names]) or ("served", [jar names]) or an rc."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        image = next(a for a in cmd if a in images)
        spec = images[image]
        if isinstance(spec, int):
            return SimpleNamespace(returncode=spec, stdout="", stderr="no such image")
        if spec[0] == "embedded":
            assert "python3" in cmd
            return SimpleNamespace(returncode=0, stdout=f"{spec[1]}\n{' '.join(spec[2])}\n", stderr="")
        if spec[0] == "embedded3":     # the probe's three lines: version, distribution, jars (26.11.1+ names)
            assert "python3" in cmd
            return SimpleNamespace(returncode=0, stdout=f"{spec[1]}\n{spec[2]}\n{' '.join(spec[3])}\n", stderr="")
        assert "sh" in cmd
        return SimpleNamespace(returncode=0, stdout="\n".join(spec[1]) + "\n", stderr="")

    run.calls = calls
    return run


GOOD_EMB = ("embedded", PIN, [f"arcadedb-engine-{PIN}.jar", f"arcadedb-network-{PIN}.jar", "other.jar"])
GOOD_SRV = ("served", [f"arcadedb-engine-{PIN}.jar", f"arcadedb-server-{PIN}.jar"])
EMB = f"dbbench:arcadedb-{PIN}"
SRV = "arcadedb-c25:abcdef123"


# --------------------------------------------------------------------------- names and tags
def test_the_pin_is_the_version_in_the_wheel_file_name():
    assert E.pin_from_wheel(f"/x/dist/{WHEEL}") == PIN
    assert E.pin_from_wheel("arcadedb_embedded-26.11.1.dev0-cp312-x-y.whl") == "26.11.1.dev0"
    for bad in ("", "wheel.whl", "arcadedb_embedded-latest-cp312-x-y.whl", None):
        assert E.pin_from_wheel(bad) == ""


@pytest.mark.parametrize("tag", ["dbbench:arcadedb", "dbbench:arcadedb-26102", "dbbench:arcadedb-latest", "dbbench:arcadedb-"])
def test_a_floating_or_versionless_arcadedb_tag_is_refused(tag):
    assert E.check_image_tag(tag, PIN) and E.check_image_tag(tag)


def test_a_versioned_tag_must_name_the_pin():
    assert E.check_image_tag(EMB, PIN) is None
    assert E.check_image_tag(EMB) is None
    why = E.check_image_tag("dbbench:arcadedb-26.10.1", PIN)
    assert "26.10.1" in why and PIN in why


def test_comparator_images_keep_their_names_and_unknown_dbbench_names_are_refused():
    for t in E.FLOATING_OK:
        assert E.check_image_tag(f"dbbench:{t}", PIN) is None
    assert E.check_image_tag("dbbench:client-pre-m303", PIN)
    assert E.check_image_tag("qdrant/qdrant@sha256:" + "0" * 64, PIN) is None


def test_build_target_maps_the_versioned_tag_back_to_the_build_script_name():
    assert E.build_target(EMB) == "arcadedb" and E.build_target("dbbench:arcadedb") == "arcadedb"
    assert E.build_target("dbbench:duckdb") == "duckdb" and E.build_target("dbbench:pg-age") == "pg-age"


def test_a_snapshot_jar_reads_as_the_dev_wheel_version():
    assert E.normalize_jar_version("26.11.1-SNAPSHOT") == "26.11.1.dev0"
    assert E.normalize_jar_version("26.10.2") == "26.10.2"


# --------------------------------------------------------------------------- read back from what will run
def test_matching_images_pass_and_the_readback_names_what_was_read():
    run = fake_docker({EMB: GOOD_EMB, SRV: GOOD_SRV})
    readback, problems = E.verify(PIN, [EMB], [SRV], run=run)
    assert problems == []
    # a two-line probe answer is the old `arcadedb-embedded`, a JVM build
    assert readback[EMB] == {"wheel": PIN, "dist": "arcadedb-embedded", "backend": "jvm", "engine_jar": [PIN]}
    assert readback[SRV] == {"engine_jar": [PIN]}
    assert len(run.calls) == 2


def test_the_new_distributions_are_read_back_as_native_or_jvm():
    pin = "26.11.1.dev0"
    native = ("embedded3", pin, "arcadedb", ["arcadedb-engine-26.11.1-SNAPSHOT.jar"])   # no jars dir: _build_info.ENGINE_VERSION
    jvm = ("embedded3", pin, "arcadedb-jvm", ["arcadedb-engine-26.11.1-SNAPSHOT.jar", "arcadedb-network-26.11.1-SNAPSHOT.jar", "x.jar"])
    n_img, j_img = f"dbbench:arcadedb-{pin}", "dbbench:arcadedb-jvm-img"
    run = fake_docker({n_img: native, j_img: jvm})
    readback, problems = E.verify(pin, [n_img], [], run=run)
    assert problems == [] and readback[n_img]["backend"] == "native" and readback[n_img]["dist"] == "arcadedb"
    # the other image's tag is not a versioned ArcadeDB tag, so the check_image_tag refusal is what is read here; the probe itself:
    got, err = E.read_embedded(j_img, run)
    assert err is None and got["backend"] == "jvm" and got["engine_jar"] == [pin]
    # a native image whose engine is another version is refused with the distribution named
    stale = ("embedded3", pin, "arcadedb", ["arcadedb-engine-26.11.0.jar"])
    _, problems = E.verify(pin, [n_img], [], run=fake_docker({n_img: stale}))
    assert any("engine jar 26.11.0" in p for p in problems)


def test_the_probe_in_the_image_resolves_the_new_names_first():
    # not run here (it runs in the image): pin the order the probe reads, the same as _arcadedb_import.py
    assert "('arcadedb', 'arcadedb_embedded')" in E._EMBEDDED_PROBE
    assert "('arcadedb', 'arcadedb-jvm', 'arcadedb-embedded')" in E._EMBEDDED_PROBE
    compile(E._EMBEDDED_PROBE, "probe", "exec")
    assert E.pin_from_wheel("/x/arcadedb_jvm-26.11.1.dev0-py3-none-manylinux_2_28_x86_64.whl") == "26.11.1.dev0"
    assert E.pin_from_wheel("/x/arcadedb-26.11.1.dev0-py3-none-manylinux_2_28_x86_64.whl") == "26.11.1.dev0"


def test_the_incident_an_image_that_carries_the_retired_version_is_refused():
    # the tag says 26.10.2 (a retag, a stale layer) but the image holds 26.10.1
    old = ("embedded", "26.10.1", ["arcadedb-engine-26.10.1.jar"])
    _, problems = E.verify(PIN, [EMB], [], run=fake_docker({EMB: old}))
    assert any("arcadedb-embedded 26.10.1" in p and PIN in p for p in problems)
    assert any("engine jar 26.10.1" in p for p in problems)


def test_a_wheel_that_matches_while_the_engine_jar_does_not_is_refused():
    odd = ("embedded", PIN, ["arcadedb-engine-26.10.1.jar"])
    _, problems = E.verify(PIN, [EMB], [], run=fake_docker({EMB: odd}))
    assert len(problems) == 1 and "engine jar 26.10.1" in problems[0]


def test_a_server_image_on_another_version_is_refused():
    old = ("served", ["arcadedb-engine-26.10.1.jar"])
    _, problems = E.verify(PIN, [], [SRV], run=fake_docker({SRV: old}))
    assert len(problems) == 1 and "loads engine jar 26.10.1" in problems[0]


def test_a_server_image_with_two_engine_jars_is_refused():
    two = ("served", [f"arcadedb-engine-{PIN}.jar", "arcadedb-engine-26.10.1.jar"])
    assert E.verify(PIN, [], [SRV], run=fake_docker({SRV: two}))[1]


def test_an_image_that_cannot_be_read_is_a_refusal_not_a_pass():
    _, problems = E.verify(PIN, [EMB], [SRV], run=fake_docker({EMB: 125, SRV: 125}))
    assert len(problems) == 2


def test_no_pin_is_a_refusal():
    assert E.verify("", [EMB], [], run=fake_docker({EMB: GOOD_EMB}))[1]


def test_an_embedded_image_with_a_floating_tag_is_refused_before_docker_is_asked():
    run = fake_docker({"dbbench:arcadedb": GOOD_EMB})
    _, problems = E.verify(PIN, ["dbbench:arcadedb"], [], run=run)
    assert problems and not run.calls


# --------------------------------------------------------------------------- the runner
def _env_without_engine():
    return {k: v for k, v in os.environ.items() if not k.startswith("ARCADEDB_")}


def test_the_runner_swaps_the_logical_image_for_the_versioned_tag_when_a_pin_is_set(tmp_path):
    wheel = tmp_path / WHEEL
    wheel.write_bytes(b"")
    code = ("import runner; print(runner.BACKENDS['arcadedb_ts_doc']['image'], runner.BACKENDS['arcadedb_e4']['image'], "
            "runner.ARCADEDB_BENCH_IMAGE)")
    env = dict(_env_without_engine(), ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE=SRV)
    out = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out[-3:] == [EMB, EMB, EMB]
    env = _env_without_engine()
    out = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out[-3:] == ["dbbench:arcadedb"] * 3  # no pin: the logical name stays, and _require_engine_pin refuses it


@pytest.fixture
def pinned(monkeypatch):
    """The runner as a stage leaves it: pin 26.10.2, the embedded and served arms on the pinned names."""
    monkeypatch.setattr(runner, "_ENGINE_PIN", PIN)
    monkeypatch.setattr(runner, "_LOCAL_SERVER_IMAGE", SRV)
    monkeypatch.setitem(runner.BACKENDS, "arcadedb_ts_doc", dict(runner.BACKENDS["arcadedb_ts_doc"], image=EMB))
    monkeypatch.setitem(runner.BACKENDS, "arcadedb_server", dict(runner.BACKENDS["arcadedb_server"], server_image=SRV))
    monkeypatch.setattr(runner, "_ENGINE_PIN_READBACK", {})


EMBEDDED_JOB = [{"backend": "arcadedb_ts_doc"}]
SERVED_JOB = [{"backend": "arcadedb_server"}]


def test_runner_starts_when_every_arcadedb_image_reports_the_pin(pinned, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", fake_docker({EMB: GOOD_EMB, SRV: GOOD_SRV}))
    runner._require_engine_pin(EMBEDDED_JOB + SERVED_JOB)
    assert "read back and match" in capsys.readouterr().out
    assert set(runner._ENGINE_PIN_READBACK) == {EMB, SRV}


def test_runner_refuses_a_stale_embedded_image(pinned, monkeypatch):
    old = ("embedded", "26.10.1", ["arcadedb-engine-26.10.1.jar"])
    monkeypatch.setattr(subprocess, "run", fake_docker({EMB: old}))
    with pytest.raises(SystemExit) as e:
        runner._require_engine_pin(EMBEDDED_JOB)
    assert "26.10.1" in str(e.value) and "REFUSING" in str(e.value)


def test_runner_refuses_a_stale_server_image(pinned, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_docker({SRV: ("served", ["arcadedb-engine-26.10.1.jar"])}))
    with pytest.raises(SystemExit) as e:
        runner._require_engine_pin(SERVED_JOB)
    assert "26.10.1" in str(e.value)


def test_runner_refuses_a_floating_tag_even_with_a_pin(pinned, monkeypatch):
    monkeypatch.setitem(runner.BACKENDS, "arcadedb_ts_doc", dict(runner.BACKENDS["arcadedb_ts_doc"], image="dbbench:arcadedb"))
    monkeypatch.setattr(subprocess, "run", fake_docker({"dbbench:arcadedb": GOOD_EMB}))
    with pytest.raises(SystemExit) as e:
        runner._require_engine_pin(EMBEDDED_JOB)
    assert "without a version" in str(e.value)


def test_runner_refuses_an_arcadedb_arm_without_a_pin(pinned, monkeypatch):
    monkeypatch.setattr(runner, "_ENGINE_PIN", "")
    with pytest.raises(SystemExit) as e:
        runner._require_engine_pin(EMBEDDED_JOB)
    assert "no version is pinned" in str(e.value)


def test_a_batch_without_an_arcadedb_arm_is_not_judged_and_asks_docker_nothing(monkeypatch):
    monkeypatch.setattr(runner, "_ENGINE_PIN", "")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("docker was asked"))
    runner._require_engine_pin([{"backend": "duckdb"}])


def test_the_manifest_records_the_pin_and_what_each_image_said(pinned, monkeypatch):
    monkeypatch.setattr(runner, "_ENGINE_PIN_READBACK", {EMB: {"wheel": PIN, "engine_jar": [PIN]}})
    src = Path(runner.__file__).read_text()
    assert 'manifest["engine_pin"] = {"pin": _ENGINE_PIN, "readback": _ENGINE_PIN_READBACK}' in src


def test_main_calls_the_check_before_the_manifest_and_before_any_cell():
    src = Path(runner.__file__).read_text()
    main = src[src.index("def main():"):]
    assert 0 < main.index("_require_engine_pin(jobs)") < main.index("build_manifest(ts, args")
    assert main.index("_require_engine_pin(jobs)") < main.index("jsonl = open(")


def test_no_backend_names_a_floating_tag_other_than_the_logical_arcadedb_name():
    for name, cfg in runner.BACKENDS.items():
        for key in ("image", "server_image"):
            img = cfg.get(key) or ""
            if img.startswith("dbbench:"):
                assert img == E.LOGICAL_IMAGE or E.check_image_tag(img) is None, (name, img)


# --------------------------------------------------------------------------- build_images.sh and the stage generator
def _chunked_wheel(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("arcadedb_embedded/core.py", "_INSERT_MANY_CHUNK = 10000\n")


@pytest.fixture
def build_dir(tmp_path):
    """A copy of build_images.sh with a fake docker in front of PATH: nothing is built, and the copy's docker-wheels/ is not the real one."""
    d = tmp_path / "exp"
    d.mkdir()
    for f in ("build_images.sh", "wheel_guard.py", "Dockerfile.bench"):
        shutil.copy(HERE / f, d / f)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text('#!/bin/sh\necho "$@" >> "$DOCKER_LOG"\n')
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    return d, bindir, tmp_path / "docker.log"


def _build(build_dir, wheel_name, *targets):
    d, bindir, log = build_dir
    w = d / wheel_name
    _chunked_wheel(w)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", DOCKER_LOG=str(log), ARCADEDB_WHEEL=str(w))
    r = subprocess.run(["bash", str(d / "build_images.sh"), *targets], env=env, capture_output=True, text=True)
    return r, (log.read_text() if log.exists() else "")


def test_build_images_tags_the_arcadedb_image_with_the_wheels_version_and_never_floating(build_dir):
    r, log = _build(build_dir, WHEEL, "arcadedb")
    assert r.returncode == 0, r.stderr
    assert f"-t {EMB} " in log and "-t dbbench:arcadedb " not in log


def test_build_images_refuses_a_wheel_name_without_a_version(build_dir):
    r, log = _build(build_dir, "arcadedb_embedded-latest-cp312-x-y.whl", "arcadedb")
    assert r.returncode != 0 and log == ""


def test_build_images_still_names_comparator_images_by_target(build_dir):
    r, log = _build(build_dir, WHEEL, "duckdb")
    assert r.returncode == 0, r.stderr
    assert "-t dbbench:duckdb " in log


def test_the_stage_generator_builds_the_arcadedb_target_whatever_the_images_name_is(monkeypatch):
    import make_2611_stages as G
    monkeypatch.setitem(runner.BACKENDS, "arcadedb_ts_doc", dict(runner.BACKENDS["arcadedb_ts_doc"], image=EMB))
    assert G._images_for(["arcadedb_ts_doc"]) == ["arcadedb"]


def test_the_stage_generators_checks_read_the_versioned_image():
    text = (HERE / "make_2611_stages.py").read_text()
    assert "--entrypoint python3 dbbench:arcadedb " not in text
    assert text.count('"dbbench:arcadedb-$WV$WB"') == 2   # the wheel's build is the tag's suffix (26.11.1)
    assert 'dbbench:arcadedb-$(basename "$ARCADEDB_WHEEL"' in text
