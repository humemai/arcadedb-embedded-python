#!/usr/bin/env python3
"""Build the arcadedb-embedded-native wheel from the shared Python sources and a built native image.

  python build_wheel.py --lib-dir ~/build-scratch/native-lib/preview --version 26.10.2.dev1 --engine 26.10.2 --out <dir>

Steps: copy src/arcadedb_embedded to <out>/stage/src/arcadedb_native with every name rewritten (the shared tree is not duplicated in git);
rewrite `import jpype` to the bundled stub; flip the default backend to native; add the library of the build platform (libarcadedb.so on Linux,
libarcadedb.dylib on macOS, libarcadedb.dll on Windows; on Linux x86-64 also libjvector-x86_64.so, jvector's Highway library: no other platform ships it);
add LICENSE/NOTICE/GraalVM licence texts; check THIRD_PARTY_NOTICES.md against gen_notices.py (fails on drift); compute the platform tag from the library
(Linux: manylinux_<glibc floor>_<x86_64|aarch64> from the GLIBC symbol versions; macOS: macosx_<minos>_arm64 from the load commands; Windows: win_amd64);
build with `uv build --wheel`. Run it on the platform the library was built on.
"""

import argparse
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent  # bindings/python
REPO = PKG.parent.parent


LIB_NAMES = {
    "linux": "libarcadedb.so",
    "darwin": "libarcadedb.dylib",
    "win32": "libarcadedb.dll",
}
JVECTOR = "libjvector-x86_64.so"  # Highway, taken from the jvector jar by preview-build.sh on Linux x86-64 only


def host_arch() -> str:
    m = platform.machine().lower()
    return {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }.get(m, m)


def glibc_floor(lib: Path) -> str:
    out = subprocess.run(
        ["objdump", "-T", str(lib)], capture_output=True, text=True, check=True
    ).stdout
    vers = {
        tuple(map(int, m.split(".")))
        for m in re.findall(r"GLIBC_(\d+\.\d+(?:\.\d+)?)", out)
    }
    major, minor = max(v[:2] for v in vers)
    return f"manylinux_{major}_{minor}_{host_arch()}"


def macos_tag(lib: Path) -> str:
    """macosx_<minos>_arm64 from LC_BUILD_VERSION (minos) or LC_VERSION_MIN_MACOSX (version) of the library."""
    out = subprocess.run(
        ["otool", "-l", str(lib)], capture_output=True, text=True, check=True
    ).stdout
    m = re.search(r"minos\s+(\d+)\.(\d+)", out) or re.search(
        r"LC_VERSION_MIN_MACOSX.*?\n\s+cmdsize \d+\n\s+version (\d+)\.(\d+)", out, re.S
    )
    if not m:
        sys.exit(f"no minimum macOS version in the load commands of {lib}:\n{out}")
    print(f"load command minimum macOS version: {m.group(1)}.{m.group(2)}")
    arch = subprocess.run(
        ["lipo", "-archs", str(lib)], capture_output=True, text=True, check=True
    ).stdout.split()
    if arch != ["arm64"]:
        sys.exit(f"{lib} has architectures {arch}, expected only arm64")
    return f"macosx_{m.group(1)}_{m.group(2)}_arm64"


def platform_tag(lib: Path) -> str:
    if sys.platform.startswith("linux"):
        return glibc_floor(lib)
    if sys.platform == "darwin":
        return macos_tag(lib)
    if sys.platform == "win32":
        if host_arch() != "x86_64":
            sys.exit(
                f"Windows wheels are win_amd64 only, this machine is {platform.machine()}"
            )
        return "win_amd64"
    sys.exit(f"unsupported platform {sys.platform}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lib-dir",
        required=True,
        help="directory with the library of this platform (libarcadedb.so / .dylib / .dll) and, on Linux x86-64, libjvector-x86_64.so",
    )
    ap.add_argument(
        "--version",
        default="26.10.2.dev1",
        help="PEP 440: A.B.C.devN -> A.B.C -> A.B.C.postN (no aN/bN/rcN)",
    )
    ap.add_argument(
        "--engine",
        required=True,
        help="engine release the image was built from, e.g. 26.10.2",
    )
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--graalvm-home",
        default=str(
            Path.home()
            / "build-scratch/graalvm-dl-25.4.4.1.1/graalvm-community-25.4.4.1.1+1.1"
        ),
    )
    ap.add_argument(
        "--march",
        default="compatibility",
        help="-march the image was built with (preview-build.sh MARCH)",
    )
    ap.add_argument(
        "--m2-repo",
        default="",
        help="Maven repository the image classpath jars are read from (default ~/.m2/repository; the CI container build uses another)",
    )
    ap.add_argument(
        "--notices-out",
        default="",
        help="also write the generated notices here (CI keeps it in the build record)",
    )
    ap.add_argument(
        "--skip-notices-check",
        action="store_true",
        help="do not compare THIRD_PARTY_NOTICES.md with the gen_notices.py output (needs <lib-dir>/build.log)",
    )
    ap.add_argument("--plat", default="", help="override the computed platform tag")
    a = ap.parse_args()
    lib_dir, out = Path(a.lib_dir), Path(a.out).resolve()
    libname = LIB_NAMES.get(sys.platform) or sys.exit(
        f"unsupported platform {sys.platform}"
    )
    if not a.skip_notices_check:
        # THIRD_PARTY_NOTICES.md is generated from the classpath of the image build (preview-build.sh writes <lib-dir>/build.log):
        # refuse to build a wheel whose notices differ from the library's real contents. Licence-review items are printed, not fatal.
        chk = subprocess.run(
            [
                sys.executable,
                "-I",
                str(HERE / "gen_notices.py"),
                "--build-log",
                str(lib_dir / "build.log"),
                "--engine",
                a.engine,
                "--graalvm-home",
                a.graalvm_home,
                "--check",
                str(HERE / "THIRD_PARTY_NOTICES.md"),
            ]
            + (["--m2-repo", a.m2_repo] if a.m2_repo else [])
            + (["--out", a.notices_out] if a.notices_out else [])
        )
        if chk.returncode:
            sys.exit(
                "THIRD_PARTY_NOTICES.md is out of date: python native-wheel/gen_notices.py --build-log <lib-dir>/build.log "
                f"--engine {a.engine} --graalvm-home {a.graalvm_home} --out native-wheel/THIRD_PARTY_NOTICES.md"
            )
    stage = out / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    dst = stage / "src" / "arcadedb_native"
    shutil.copytree(
        PKG / "src" / "arcadedb_embedded",
        dst,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "_version.py", "jars", "jre"
        ),
    )

    jp = re.compile(
        r"^(\s*)(?:import jpype(?:\.imports)?|import jpype as _jpype|import jpype\.types as jtypes|from jpype import JException)\s*$",
        re.M,
    )
    left = []
    for f in dst.rglob("*.py"):
        t = f.read_text(encoding="utf-8")
        t = (
            t.replace('"arcadedb-embedded"', '"arcadedb-embedded-native"')
            .replace(
                "'arcadedb-embedded[", "'arcadedb-embedded-native["
            )  # the extras named in install hints
            .replace("arcadedb_embedded", "arcadedb_native")
        )

        def sub(m):
            line = m.group(0).strip()
            ind = m.group(1)
            if line == "import jpype.imports":
                return f"{ind}pass  # jpype.imports: no JVM in this wheel"
            tail = {
                "import jpype as _jpype": "_jpype",
                "import jpype.types as jtypes": "jtypes",
            }.get(line, "jpype")
            if line == "from jpype import JException":
                return f"{ind}from arcadedb_native._jpype_stub import JException"
            return f"{ind}from arcadedb_native import _jpype_stub as {tail}"

        t = jp.sub(sub, t)
        if re.search(r"^\s*(import|from)\s+jpype", t, re.M):
            left.append(f.name)
        f.write_text(t, encoding="utf-8")
    if left:
        sys.exit(f"jpype imports left in: {left}")
    init = dst / "_native" / "__init__.py"
    t = init.read_text(encoding="utf-8")
    assert t.count('_DEFAULT_BACKEND = "jpype"') == 1, "default-backend line not found"
    init.write_text(
        t.replace('_DEFAULT_BACKEND = "jpype"', '_DEFAULT_BACKEND = "native"'),
        encoding="utf-8",
    )
    shutil.copy(HERE / "_jpype_stub.py", dst / "_jpype_stub.py")

    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (dst / "_build_info.py").write_text(
        f'"""Written by native-wheel/build_wheel.py."""\n'
        f'ENGINE_VERSION = "{a.engine}"  # the ArcadeDB engine release compiled into {libname}\n'
        f'NATIVE_IMAGE = "GraalVM CE 25.4.4.1.1, -O2, -march={a.march}"\n'
        f'NATIVE_MARCH = "{a.march}"  # _native/cpu.py checks the CPU only for an image above the platform baseline\n'
        f'SOURCE_COMMIT = "{commit}"  # humemai/arcadedb-embedded-python (fork tae898/arcadedb) commit of the bindings and the Java glue\n',
        encoding="utf-8",
    )
    ip = dst / "__init__.py"
    t = ip.read_text(encoding="utf-8")
    t = t.replace(
        "# Import async execution\n",
        "from ._build_info import ENGINE_VERSION, NATIVE_IMAGE, NATIVE_MARCH, SOURCE_COMMIT  # noqa: F401\n\n# Import async execution\n",
        1,
    )
    t = t.replace(
        '__all__ = [\n    "__version__",',
        '__all__ = [\n    "__version__",\n    "ENGINE_VERSION",\n    "NATIVE_IMAGE",\n    "SOURCE_COMMIT",',
        1,
    )
    ip.write_text(t, encoding="utf-8")

    ship = [libname]
    if sys.platform.startswith("linux") and host_arch() == "x86_64":
        ship.append(
            JVECTOR
        )  # the only platform that ships Highway; lib.py does not need it elsewhere
    for n in ship:
        shutil.copy(
            lib_dir / n, dst / "_native" / n
        )  # lib.py looks next to itself (_native/)
    lic = out / "licenses-tmp"
    shutil.rmtree(lic, ignore_errors=True)
    lic.mkdir()
    g = Path(a.graalvm_home)
    for src, name in (
        (g / "LICENSE.txt", "GraalVM-CE-LICENSE.txt"),
        (g / "LICENSE_NATIVEIMAGE.txt", "GraalVM-native-image-LICENSE.txt"),
        (g / "THIRD_PARTY_LICENSE.txt", "GraalVM-THIRD_PARTY_LICENSE.txt"),
    ):
        shutil.copy(src, lic / name)
    shutil.copy(REPO / "LICENSES" / "Apache-2.0.txt", lic / "Apache-2.0.txt")
    shutil.copy(REPO / "LICENSE", stage / "LICENSE")
    for n in ("NOTICE", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy(HERE / n, stage / n)
    shutil.move(
        str(lic), str(stage / "licenses")
    )  # dist-info licenses only: one copy in the wheel
    (stage / "pyproject.toml").write_text(
        (HERE / "pyproject.toml")
        .read_text(encoding="utf-8")
        .replace("@VERSION@", a.version),
        encoding="utf-8",
    )
    shutil.copy(HERE / "setup.py", stage / "setup.py")

    plat = a.plat or platform_tag(lib_dir / libname)
    print("platform tag:", plat)
    import os

    env = dict(os.environ, ARCADEDB_NATIVE_PLAT=plat)
    dist = out / "dist"
    dist.mkdir(exist_ok=True)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist), str(stage)],
        check=True,
        env=env,
    )
    for w in sorted(dist.glob("*.whl")):
        print(w, w.stat().st_size)


if __name__ == "__main__":
    main()
