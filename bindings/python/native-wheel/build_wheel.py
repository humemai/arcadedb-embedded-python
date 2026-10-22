#!/usr/bin/env python3
"""Build the arcadedb-embedded-native wheel from the shared Python sources and a built native image.

  python build_wheel.py --lib-dir ~/build-scratch/native-lib/preview --version 26.10.2.dev1 --engine 26.10.2 --out <dir>

Steps: copy src/arcadedb_embedded to <out>/stage/src/arcadedb_native with every name rewritten (the shared tree is not duplicated in git);
rewrite `import jpype` to the bundled stub; flip the default backend to native; add libarcadedb.so + libjvector-x86_64.so;
add LICENSE/NOTICE/GraalVM licence texts; compute the manylinux tag from the library's GLIBC symbol versions; build with `uv build --wheel`.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent  # bindings/python
REPO = PKG.parent.parent


def glibc_floor(lib: Path) -> str:
    out = subprocess.run(
        ["objdump", "-T", str(lib)], capture_output=True, text=True, check=True
    ).stdout
    vers = {
        tuple(map(int, m.split(".")))
        for m in re.findall(r"GLIBC_(\d+\.\d+(?:\.\d+)?)", out)
    }
    major, minor = max(v[:2] for v in vers)
    return f"manylinux_{major}_{minor}_x86_64"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lib-dir",
        required=True,
        help="directory with libarcadedb.so and libjvector-x86_64.so",
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
    ap.add_argument("--plat", default="", help="override the computed platform tag")
    a = ap.parse_args()
    lib_dir, out = Path(a.lib_dir), Path(a.out).resolve()
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
        t = f.read_text()
        t = t.replace('"arcadedb-embedded"', '"arcadedb-embedded-native"').replace(
            "arcadedb_embedded", "arcadedb_native"
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
        f.write_text(t)
    if left:
        sys.exit(f"jpype imports left in: {left}")
    init = dst / "_native" / "__init__.py"
    t = init.read_text()
    assert t.count('_DEFAULT_BACKEND = "jpype"') == 1, "default-backend line not found"
    init.write_text(
        t.replace('_DEFAULT_BACKEND = "jpype"', '_DEFAULT_BACKEND = "native"')
    )
    shutil.copy(HERE / "_jpype_stub.py", dst / "_jpype_stub.py")

    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (dst / "_build_info.py").write_text(
        f'"""Written by native-wheel/build_wheel.py."""\n'
        f'ENGINE_VERSION = "{a.engine}"  # the ArcadeDB engine release compiled into libarcadedb.so\n'
        f'NATIVE_IMAGE = "GraalVM CE 25.4.4.1.1, -O2, -march={a.march}"\n'
        f'NATIVE_MARCH = "{a.march}"  # lib.py checks the CPU only for an x86-64-v3 image\n'
        f'SOURCE_COMMIT = "{commit}"  # humemai/arcadedb-embedded-python (fork tae898/arcadedb) commit of the bindings and the Java glue\n'
    )
    ip = dst / "__init__.py"
    t = ip.read_text()
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
    ip.write_text(t)

    for n in ("libarcadedb.so", "libjvector-x86_64.so"):
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
        (HERE / "pyproject.toml").read_text().replace("@VERSION@", a.version)
    )
    shutil.copy(HERE / "setup.py", stage / "setup.py")

    plat = a.plat or glibc_floor(lib_dir / "libarcadedb.so")
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
