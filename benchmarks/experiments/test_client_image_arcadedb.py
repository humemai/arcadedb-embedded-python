"""The served ArcadeDB client image (DECISIONS #259): the official driver at lean_http.OFFICIAL_PIN reaches the served arms through a layer of its
own, and the shared `dbbench:client` image is not changed. Nothing is built or started here: the registry, the build script and the Dockerfile
are read as text.
Run with `python -m pytest test_client_image_arcadedb.py -q` from this directory.
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_INSTRUMENT", "2026-11")

import engine_pin  # noqa: E402
import lean_http  # noqa: E402
import runner as R  # noqa: E402

BUILD = (HERE / "build_images.sh").read_text()
IMAGE = "dbbench:client-arcadedb"


def _pins(text):
    return dict(re.findall(r"([A-Za-z][A-Za-z0-9_.-]*)==([0-9][A-Za-z0-9_.+-]*)", text))


def test_every_served_arcadedb_arm_runs_in_the_driver_layer_and_no_other_arm_does():
    served = {n: c for n, c in R.BACKENDS.items() if n.startswith("arcadedb") and c.get("topology") == "client_server"}
    assert "arcadedb_server" in served and "arcadedb_graph_server" in served and "arcadedb_imgdefaults_server" in served
    for name, cfg in served.items():
        if name == "arcadedb_e4":
            assert cfg["image"] == "dbbench:arcadedb"       # the wheel image: not a driver client
        else:
            assert cfg["image"] == IMAGE, name
    assert [n for n, c in R.BACKENDS.items() if c.get("image") == IMAGE and n not in served] == []
    assert R.ARCADEDB_CLIENT_IMAGE == IMAGE
    # a comparator's served arm still runs on the unchanged shared image
    assert R.BACKENDS["postgres"]["image"] == "dbbench:client" and R.BACKENDS["mongodb"]["image"] == "dbbench:client"


def test_the_image_is_a_known_floating_name_and_builds_as_its_own_target():
    assert engine_pin.check_image_tag(IMAGE, "26.11.1") is None
    assert engine_pin.build_target(IMAGE) == "client-arcadedb"
    assert engine_pin.check_image_tag("dbbench:client-pre-m303", "26.11.1")          # an unknown name is still refused


def test_the_build_script_pins_the_driver_at_the_harness_pin_and_leaves_the_client_line_alone():
    m = re.search(r'^ARCADEDB_DRIVER_PKGS="([^"]+)"', BUILD, re.M)
    assert m, "build_images.sh has no ARCADEDB_DRIVER_PKGS"
    specs = m.group(1).split()
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*==[0-9][A-Za-z0-9_.+-]*", s) for s in specs), specs      # everything pinned with ==
    pins = _pins(m.group(1))
    assert pins["arcadedb-driver"] == lean_http.OFFICIAL_PIN == "0.4.0"
    for dep in ("httpx", "httpcore", "h11", "anyio", "websockets", "attrs", "typing-extensions"):
        assert dep in pins, dep                                                                                  # the driver's own requirements, pinned
    # dbbench:client's build arg must not move: its digest would change for every comparator row already measured
    client = re.search(r'^\s*\[client\]="([^"]+)"', BUILD, re.M).group(1)
    assert _pins(client)["arcadedb-driver"] == "0.2.0"
    assert "httpx" not in _pins(client) and "websockets" not in _pins(client)


def test_the_layer_builds_from_the_unchanged_client_image_after_it():
    docker = (HERE / "Dockerfile.client-arcadedb").read_text()
    assert re.search(r"^FROM dbbench:client$", docker, re.M)
    assert "pip install --no-cache-dir ${DRIVER_PACKAGES}" in docker and "not at the pin" in docker
    assert "docker build -q -t dbbench:client-arcadedb" in BUILD and "-f Dockerfile.client-arcadedb" in BUILD
    default = re.search(r"\[ \$\{#targets\[@\]\} -eq 0 \] && targets=\(([^)]*)\)", BUILD).group(1).split()
    assert default.index("client") < default.index("client-arcadedb")
    assert sorted(["client-arcadedb", "client"]) == ["client", "client-arcadedb"]                               # the stage scripts pass a sorted list


def test_building_the_layer_runs_one_build_for_it_and_none_for_dbbench_client(tmp_path):
    import shutil
    import subprocess
    work, bindir, log = tmp_path / "w", tmp_path / "bin", tmp_path / "docker.log"
    work.mkdir()
    bindir.mkdir()
    for n in ("build_images.sh", "Dockerfile.bench", "Dockerfile.client-arcadedb", "wheel_guard.py"):
        shutil.copy(HERE / n, work / n)
    (bindir / "docker").write_text('#!/bin/sh\necho "$@" >> "' + str(log) + '"\n')
    (bindir / "docker").chmod(0o755)
    env = {"PATH": f"{bindir}:{os.environ['PATH']}", "HOME": str(tmp_path)}
    r = subprocess.run(["bash", str(work / "build_images.sh"), "client-arcadedb"], cwd=work, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    builds = [ln for ln in log.read_text().splitlines() if ln.startswith("build ")]
    assert len(builds) == 1 and "-t dbbench:client-arcadedb " in builds[0] and "-f Dockerfile.client-arcadedb" in builds[0]
    assert f"DRIVER_PACKAGES=arcadedb-driver=={lean_http.OFFICIAL_PIN} " in builds[0]
