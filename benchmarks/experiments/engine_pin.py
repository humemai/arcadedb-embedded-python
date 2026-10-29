#!/usr/bin/env python3
"""The engine a benchmark cell runs is the engine the stage pinned, read from the thing that will run, before any cell.

WHY (2026-10-22). After October was retired the laptop still held `dbbench:arcadedb` at ArcadeDB 26.10.1 while `dbbench:arcadedb-26102` held
26.10.2, and the l4/ts1000 ts_doc kernel kill of 2026-10-08 came from exactly such an image (a whole-input insert_many, fixed in 26.10.2). Every
existing check read rows AFTER the run (version_consistency_check.py, provenance_check.py), and the stage scripts read the version once, from the
image they had just built. Nothing stopped `runner.py` itself from starting a cell on an image or server it had not read.

THE RULE. The stage pins one ArcadeDB version by exporting `ARCADEDB_WHEEL` (the pinned wheel file, whose name carries the version). Before the
first cell, for every ArcadeDB arm in the batch, `runner.py` reads the version out of what will run and refuses to start unless it is the pin:
  embedded  the image's installed ArcadeDB distribution version AND the engine the wheel ships: `arcadedb-jvm` (JVM build) or the older
            `arcadedb-embedded` carry `arcadedb-engine-<version>.jar`; `arcadedb` (the native build, no JVM, no jars) carries the engine
            inside libarcadedb.so and names its version in `_build_info.ENGINE_VERSION`, read here as the same jar name;
  served    the engine jar of the server image (`/home/arcadedb/lib/arcadedb-engine-<version>.jar`), which is the engine the server loads.
Nothing is started to ask, so the check costs two short `docker run`s per image and measures nothing.

NO FLOATING ENGINE TAGS. An image that carries ArcadeDB is tagged `dbbench:arcadedb-<version>` (build_images.sh writes it) and the runner refuses
any other tag for it, `dbbench:arcadedb` included: a floating tag points at whatever was built last, which is how a retired version stayed
reachable. `dbbench:arcadedb` survives only as the logical build target name in runner.BACKENDS; the runner swaps it for the versioned tag from the
pin, and a batch with an ArcadeDB arm and no pin is refused. The comparator images (client, duckdb, dense, pg-age, mongo-search, composed) keep
their `dbbench:<target>` names: their engines are pinned by `==` in build_images.sh or by digest in the Dockerfiles and are read back out of the
images by version_pin_check.py --runtime; they do not move with the ArcadeDB release.
"""
import os
import re
import subprocess

LOGICAL_IMAGE = "dbbench:arcadedb"
TARGET = "arcadedb"
VERSION_RE = r"\d+\.\d+\.\d+(?:\.(?:dev|post)\d+)?"
FLOATING_OK = ("client", "duckdb", "dense", "pg-age", "mongo-search", "composed")
SERVER_LIB = "/home/arcadedb/lib"
_JAR_RE = re.compile(r"^arcadedb-engine-(.+)\.jar$")
_EMBEDDED_PROBE = """
import importlib.metadata as m, importlib.util as u, os
s = next((x for x in (u.find_spec(n) for n in ('arcadedb', 'arcadedb_embedded')) if x and x.origin), None)
dist = None
for n in ('arcadedb', 'arcadedb-jvm', 'arcadedb-embedded'):
    try:
        v = m.version(n)
        dist = n
        break
    except m.PackageNotFoundError:
        pass
print(v)
print(dist)
pkg = os.path.dirname(s.origin)
jars = os.path.join(pkg, 'jars')
if os.path.isdir(jars):
    print(' '.join(sorted(os.listdir(jars))))
else:
    from importlib import import_module
    print('arcadedb-engine-' + import_module(os.path.basename(pkg) + '._build_info').ENGINE_VERSION + '.jar')
"""
# The native distribution is `arcadedb`, the JVM one `arcadedb-jvm`; the old `arcadedb-embedded` is a JVM build.
BACKEND_OF = {"arcadedb": "native", "arcadedb-jvm": "jvm", "arcadedb-embedded": "jvm"}


def pin_from_wheel(path):
    """The version a wheel file name carries (arcadedb_embedded-26.10.2-cp312-...whl, arcadedb_jvm-26.11.1.dev0-py3-...whl or
    arcadedb-26.11.1.dev0-py3-...whl -> the version), or "" when it carries none."""
    parts = os.path.basename(path or "").split("-")
    return parts[1] if len(parts) > 2 and re.fullmatch(VERSION_RE, parts[1]) else ""


def versioned_image(version):
    return f"{LOGICAL_IMAGE}-{version}"


def build_target(image):
    """The build_images.sh target an image name stands for: dbbench:arcadedb-26.10.2 -> arcadedb, dbbench:duckdb -> duckdb."""
    tag = image.split(":", 1)[1]
    return TARGET if re.fullmatch(rf"{TARGET}(?:-{VERSION_RE})?", tag) else tag


def check_image_tag(image, pin=None):
    """None when `image` may run, else why it is refused. Only `dbbench:*` names are judged here (digest-pinned third-party images are not ours)."""
    if not image.startswith("dbbench:"):
        return None
    tag = image.split(":", 1)[1]
    if tag.startswith(TARGET):
        if not re.fullmatch(rf"{TARGET}-{VERSION_RE}", tag):
            return (f"{image} is an ArcadeDB image tag without a version. A floating tag points at whatever was built last; "
                    f"the tag must be {LOGICAL_IMAGE}-<version>")
        if pin and tag != f"{TARGET}-{pin}":
            return f"{image} names ArcadeDB {tag[len(TARGET) + 1:]}, the stage pins {pin}"
        return None
    if tag not in FLOATING_OK:
        return f"{image} is not a known benchmark image ({', '.join(FLOATING_OK)}, or {LOGICAL_IMAGE}-<version>)"
    return None


def normalize_jar_version(v):
    """The jar of a snapshot build says 26.11.1-SNAPSHOT where its wheel says 26.11.1.dev0."""
    return re.sub(r"-SNAPSHOT$", ".dev0", v)


def _docker(args, run, timeout=180):
    run = run or subprocess.run
    try:
        r = run(["docker", "run", "--rm"] + args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"docker failed ({e.__class__.__name__}: {e})"
    if r.returncode != 0:
        return None, f"docker run exited {r.returncode}: {(r.stderr or '').strip()[-200:]}"
    return r.stdout, None


def _engine_jar_versions(names):
    return sorted({normalize_jar_version(m.group(1)) for n in names for m in [_JAR_RE.match(n)] if m})


def read_embedded(image, run=None):
    """({"wheel": ..., "dist": ..., "backend": ..., "engine_jar": [...]}, None) read out of a bench image by running python in it, or (None, why).

    Three lines from the probe (version, distribution name, engine jar names). Two lines (version, jars) are still read, for a probe
    or a test double that predates the new package names: the distribution is then the old `arcadedb-embedded`.
    """
    out, err = _docker(["--entrypoint", "python3", image, "-c", _EMBEDDED_PROBE], run)
    if err:
        return None, err
    lines = out.strip().splitlines()
    if len(lines) == 2:
        lines = [lines[0], "arcadedb-embedded", lines[1]]
    if len(lines) < 3:
        return None, f"the probe in {image} printed {out.strip()!r}, not a wheel version, a distribution name and a jar list"
    dist = lines[1].strip()
    return {"wheel": lines[0].strip(), "dist": dist, "backend": BACKEND_OF.get(dist),
            "engine_jar": _engine_jar_versions(lines[2].split())}, None


def read_served(image, run=None):
    """({"engine_jar": [...]}, None): the engine jar(s) a server image loads, or (None, why)."""
    out, err = _docker(["--entrypoint", "sh", image, "-c", f"ls {SERVER_LIB}"], run)
    if err:
        return None, err
    return {"engine_jar": _engine_jar_versions(out.split())}, None


def verify(pin, embedded_images=(), served_images=(), run=None):
    """(readback, problems): what each image reports, and one sentence per way it is not the pin. Empty `problems` means every image runs `pin`."""
    problems, readback = [], {}
    if not pin:
        return readback, ["no pinned version: ARCADEDB_WHEEL is unset or its file name carries no version"]
    for image in sorted(set(embedded_images)):
        why = check_image_tag(image, pin)
        got, err = (None, why) if why else read_embedded(image, run)
        readback[image] = got
        if err:
            problems.append(f"{image}: {err}")
            continue
        if got["wheel"] != pin:
            problems.append(f"{image} has {got['dist']} {got['wheel']}, the stage pins {pin}")
        if got["engine_jar"] != [pin]:
            problems.append(f"{image} ships engine jar {','.join(got['engine_jar']) or '(none)'}, the stage pins {pin}")
    for image in sorted(set(served_images)):
        got, err = read_served(image, run)
        readback[image] = got
        if err:
            problems.append(f"{image}: {err}")
        elif got["engine_jar"] != [pin]:
            problems.append(f"{image} loads engine jar {','.join(got['engine_jar']) or '(none)'}, the stage pins {pin}")
    return readback, problems
