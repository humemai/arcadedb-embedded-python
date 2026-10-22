#!/usr/bin/env python3
"""Generate THIRD_PARTY_NOTICES.md for the native preview wheel from what is compiled into libarcadedb.so.

  python gen_notices.py --build-log ~/build-scratch/native-lib/preview/build.log --engine 26.10.2 \
      --graalvm-home <GraalVM CE home> --out THIRD_PARTY_NOTICES.md
  python gen_notices.py ... --check THIRD_PARTY_NOTICES.md      # exit 1 on drift (build_wheel.py does this)

Inputs, all read from disk, nothing typed by hand except the policy tables below:
  1. the `native-image -cp ...` line that preview-build.sh logs in build.log (the exact jar set of the image);
  2. each jar: licence names from its Maven pom (parent poms followed), verbatim LICENSE/NOTICE files from the jar itself;
  3. the GraalVM CE home: release file, LICENSE.txt (GPLv2 + Classpath Exception + UPL), legal/java.base notices;
  4. the ArcadeDB NOTICE file: META-INF/NOTICE* of the arcadedb-engine jar on the classpath if it has one (what ships); otherwise the
     NOTICE at the engine release tag (`git show`, needs the tag fetched); otherwise the NOTICE of the checked-out repository.
     The heading in the output does not name the source (the three are the same text for a release); stderr does.
Paths: the classpath of a container build names jars as /root/.m2/repository/...; they are read from --m2-repo (default
~/.m2/repository) by their path below `.m2/repository/`, and no absolute path reaches the output.
notice-texts/ holds licence texts that are in no jar: the ANTLR and JTS BSD texts (their poms only link them) and, for libjvector,
the Highway LICENSE and jvector NOTICE.txt at jvector tag 4.0.2.

NO STUDIO: arcadedb-studio is not on the image classpath (its web assets bundle ApexCharts >= 5.1.0, a Community/Commercial licence
that is not compatible with Apache-2.0). This script refuses a classpath that contains it.

Licence policy: the wheel ships under Apache-2.0. ALLOWED are permissive licences; anything else is listed under "Licence review"
and the script exits 2 with --strict. It never decides such a case; the maintainer does.
"""

import argparse
import difflib
import hashlib
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
M2 = Path.home() / ".m2" / "repository"  # replaced by --m2-repo in main()
M2_MARK = ".m2/repository/"
TEXTS = HERE / "notice-texts"

ALLOWED = {
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Zlib",
    "UPL-1.0",
    "CC0-1.0",
    "BlueOak-1.0.0",
}
# pom <license><name> -> SPDX. Several <license> entries in one pom are alternatives (Maven convention), not a conjunction.
POM_NAMES = [
    (r"apache", "Apache-2.0"),
    (r"^mit$", "MIT"),
    (r"bsd-?2", "BSD-2-Clause"),
    (r"bsd-?3", "BSD-3-Clause"),
    (r"universal permissive", "UPL-1.0"),
    (r"eclipse distribution|^edl", "BSD-3-Clause"),  # EDL-1.0 is the BSD-3-Clause text
    (r"eclipse public license.*2", "EPL-2.0"),
    (r"cc0|public domain", "CC0-1.0"),
]

HIGHWAY_COMMIT = "16f5f5c768064d0bb52952888a14236bec75c104"  # jvector 4.0.2: jvector-native/src/main/native/third_party/highway


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def text(b):
    # trailing whitespace is stripped per line (the repository's pre-commit hook does the same to the committed copy)
    s = b.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(l.rstrip() for l in s.split("\n")).rstrip() + "\n"


def parse_classpath(build_log):
    for line in Path(build_log).read_text(errors="replace").splitlines():
        m = re.search(r"native-image -cp (\S+) --shared", line)
        if m:
            # ':' on Linux/macOS, ';' with C:\... paths on Windows (the repository part is matched below as ".m2/repository/")
            cp = m.group(1).strip('"')  # an @args file quotes the classpath
            return [j.replace("\\", "/") for j in cp.split(";" if ";" in cp else ":")]
    sys.exit(f"gen_notices: no 'native-image -cp ... --shared' line in {build_log}")


def pom_licenses(pom, depth=0):
    if not pom.exists():
        return None
    root = ET.parse(pom).getroot()
    ns = {"m": root.tag.split("}")[0][1:]}
    names = [
        l.findtext("m:name", namespaces=ns)
        for l in root.findall("m:licenses/m:license", ns)
    ]
    if names:
        return names
    p = root.find("m:parent", ns)
    if p is not None and depth < 8:
        g, a, v = (
            p.findtext(f"m:{x}", namespaces=ns)
            for x in ("groupId", "artifactId", "version")
        )
        return pom_licenses(
            M2 / g.replace(".", "/") / a / v / f"{a}-{v}.pom", depth + 1
        )
    return None


def spdx_from_pom(name):
    for pat, spdx in POM_NAMES:
        if re.search(pat, name.strip().lower()):
            return spdx
    return None


def choose(spdx_options):
    """Alternatives: prefer an ALLOWED one (first in the order the project lists them is not meaningful, so pick by policy order)."""
    for o in spdx_options:
        if o in ALLOWED:
            return o
    return None


def jar_info(jar):
    # The classpath may name the repository as /root/.m2/repository (container build) while it is read from M2 here: map by the part
    # below ".m2/repository/", never by the absolute prefix.
    i = jar.find(M2_MARK)
    if i < 0:
        return None  # the glue jar of this repository (Apache-2.0, native-spike/)
    rel = Path(jar[i + len(M2_MARK) :])
    p = M2 / rel
    if not p.exists():
        sys.exit(
            f"gen_notices: {jar} is on the classpath but {p} does not exist (--m2-repo?)"
        )
    ver = rel.parts[-2]
    art = rel.parts[-3]
    grp = ".".join(rel.parts[:-3])
    names = pom_licenses(p.with_suffix(".pom"))
    opts = [spdx_from_pom(n) or f"UNKNOWN({n})" for n in (names or [])]
    chosen = choose(opts)
    files = {}
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if re.search(
                r"(^|/)META-INF/(LICEN[CS]E|NOTICE|COPYING)[^/]*$", n, re.I
            ) and not n.endswith("/"):
                files[n] = z.read(n)
    return dict(
        gav=f"{grp}:{art}:{ver}",
        grp=grp,
        art=art,
        ver=ver,
        pom_names=names,
        opts=opts,
        chosen=chosen,
        files=files,
    )


def engine_notice(engine, jars):
    """(label, bytes) of the ArcadeDB NOTICE: engine jar first, then the release tag, then this checkout's NOTICE."""
    for j in jars:
        if j["grp"] == "com.arcadedb" and j["art"] == "arcadedb-engine":
            for n, b in sorted(j["files"].items()):
                if re.search(r"(^|/)META-INF/NOTICE[^/]*$", n, re.I):
                    return f"{j['gav']}!/{n}", b
    r = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{engine}:NOTICE"], capture_output=True
    )
    if r.returncode == 0:
        return f"tag {engine}", r.stdout
    if (REPO / "NOTICE").exists():
        return "repository checkout (tag not fetched)", (REPO / "NOTICE").read_bytes()
    sys.exit(
        f"gen_notices: no NOTICE in the engine jar, at tag {engine} or in the checkout"
    )


def fence(body):
    n = max([3] + [len(m) + 1 for m in re.findall(r"`{3,}", body)])
    return "`" * n + "\n" + body + "`" * n + "\n"


def main():
    global M2
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--build-log",
        help="build.log of preview-build.sh (holds the native-image classpath)",
    )
    g.add_argument("--lib-dir", help="shortcut: <lib-dir>/build.log")
    ap.add_argument("--engine", required=True, help="engine release tag, e.g. 26.10.2")
    ap.add_argument("--graalvm-home", required=True)
    ap.add_argument(
        "--m2-repo",
        default=str(M2),
        help="Maven repository the classpath jars are read from (a container build logs /root/.m2/repository)",
    )
    ap.add_argument("--out")
    ap.add_argument("--check", help="compare with this file; exit 1 when it differs")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 2 when the licence review list is not empty",
    )
    a = ap.parse_args()
    M2 = Path(a.m2_repo)
    log = a.build_log or str(Path(a.lib_dir) / "build.log")
    cp = parse_classpath(log)
    if any("arcadedb-studio" in c for c in cp):
        sys.exit(
            "gen_notices: arcadedb-studio is on the classpath; its ApexCharts assets are not Apache-2.0 compatible (see module docstring)"
        )
    G = Path(a.graalvm_home)
    rel = dict(re.findall(r'^(\w+)="?(.*?)"?$', (G / "release").read_text(), re.M))

    jars = [j for j in (jar_info(c) for c in cp) if j]
    review = []  # (what, why)
    out = []
    w = out.append

    w("# Third-party notices (native image, preview)\n")
    w(
        f"Generated by `native-wheel/gen_notices.py` from the classpath that built `libarcadedb.so` (engine {a.engine}, "
        f"GraalVM CE {rel.get('GRAALVM_VERSION')}). Do not edit by hand: `build_wheel.py` fails when this file differs from the "
        "generator output. Licence names come from each artifact's own Maven pom; notice texts are copied "
        "verbatim from the jars, the engine tag and the GraalVM home. A text of the Apache License 2.0 is in "
        "`licenses/Apache-2.0.txt`.\n"
    )

    # ---- Java ----
    w("## Java libraries compiled into libarcadedb.so\n")
    w(
        f"{len(jars)} Maven artifacts on the native-image classpath (plus the glue jar of this repository, Apache-2.0).\n"
    )
    w("| Artifact | Declared in pom | Applied | Verbatim texts |")
    w("|---|---|---|---|")
    appendix_java = {}  # sha -> (name, text, [gavs])
    for j in jars:
        decl = " / ".join(j["pom_names"] or ["none"])
        if j["chosen"] is None:
            review.append((j["gav"], f"licence not in the allowed set: {decl}"))
        refs = []
        for n, b in sorted(j["files"].items()):
            k = sha(b)
            appendix_java.setdefault(k, [n.split("/")[-1], text(b), []])[2].append(
                j["gav"]
            )
            refs.append(f"`{n.split('/')[-1]}` [{k}]")
        extra = {
            "org.antlr:antlr4-runtime": "antlr4-runtime-4.13.2.LICENSE.txt",
            "org.locationtech.jts:jts-core": "jts-core-1.20.0.LICENSE_EDLv1.txt",
        }.get(f"{j['grp']}:{j['art']}")
        if extra:
            b = (TEXTS / "java" / extra).read_bytes()
            k = sha(b)
            appendix_java.setdefault(k, [extra, text(b), []])[2].append(j["gav"])
            refs.append(f"`{extra}` [{k}]")
        w(
            f"| {j['gav']} | {decl} | {j['chosen'] or 'REVIEW'} | {', '.join(refs) or 'none in jar'} |"
        )
    w("")
    w(
        "Where a pom lists several licences they are alternatives (JTS: EPL-2.0 or EDL-1.0; HdrHistogram: CC0-1.0 or BSD-2-Clause); "
        "the permissive one is applied. EDL-1.0 is the BSD-3-Clause text.\n"
    )

    # ---- native code ----
    w("## Native code shipped next to the library\n")
    w(
        "`libjvector-x86_64.so` is taken unmodified from `io.github.jbellis:jvector:4.0.2` (Apache-2.0, pom). Its sources are in the "
        "jvector repository at tag `4.0.2` (`jvector-native/src/main/native`): jvector's own C++ kernels (Apache-2.0) and the Google Highway "
        f"library, pinned there as a git submodule at commit `{HIGHWAY_COMMIT}`. Highway's `LICENSE` at that commit says: "
        "dual-licensed under the Apache License 2.0 or the BSD 3-Clause License, except `hwy/contrib/random/random-inl.h` (CC0 1.0). "
        "Applied here: Apache-2.0. The `LICENSE` of Highway and the `NOTICE.txt` of jvector are reproduced verbatim below. "
        "The library links `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1` and `libc.so.6` dynamically (not shipped).\n"
    )
    for f, who in (
        (
            f"highway-{HIGHWAY_COMMIT}.LICENSE.txt",
            "libjvector-x86_64.so (google/highway)",
        ),
        ("jvector-4.0.2.NOTICE.txt", "io.github.jbellis:jvector:4.0.2"),
    ):
        b_ = (TEXTS / "java" / f).read_bytes()
        appendix_java.setdefault(sha(b_), [f, text(b_), []])[2].append(who)

    # ---- GraalVM / JDK ----
    w("## GraalVM Community Edition runtime and JDK classes in libarcadedb.so\n")
    w(
        f"`libarcadedb.so` contains the Substrate VM runtime and the parts of the OpenJDK class library the engine reaches, built with "
        f"GraalVM CE {rel.get('GRAALVM_VERSION')} (Java {rel.get('JAVA_VERSION')}, implementor {rel.get('IMPLEMENTOR')}). Licence: GNU General Public License "
        "version 2 with the Classpath Exception (verbatim below, from `LICENSE.txt` of the GraalVM CE home; also in `licenses/`). The exception "
        "permits linking and distributing these parts with code under other licences. `graal-sdk`, `polyglot`, `collections` (25.0.2, Maven Central) "
        f"and `word` ({rel.get('GRAALVM_VERSION')}) are UPL-1.0. Oracle GraalVM (GFTC) is not used. Sources: https://github.com/oracle/graal (tag vm-{rel.get('GRAALVM_VERSION')}), "
        "https://github.com/openjdk/jdk (jdk-25 line).\n"
    )
    w(
        "Third-party data inside the JDK classes that the image contains (texts from `legal/java.base` of the GraalVM home, verbatim below): "
        "ICU normalisation data (`jdk/internal/icu/impl/data/icudt76b/nfc.nrm`, registered resource), Unicode data files, CLDR locale data. "
        "Other `legal/java.base` notices (aes.md, c-libutl.md, gcc.md, siphash.md, public_suffix.md) concern files or HotSpot code that are not "
        "linked into the image (checked: the library contains no public-suffix data); `jdk.incubator.vector` (sleef.md) is added to the module "
        "path but its vector intrinsics are disabled in the build (`-H:-VectorAPISupport`).\n"
    )
    review.append(
        (
            "libarcadedb.so JDK module set",
            "which JDK modules end up linked is not recorded by the build; the notices above cover java.base/java.logging/jdk.unsupported by module inspection of the legal directory only. A native-image `-H:+DashboardDump` or `--emit build-report` run would confirm it",
        )
    )
    w(
        "System libraries linked dynamically and not shipped: `libz.so.1`, `libc.so.6`, `ld-linux-x86-64.so.2` (checked with `ldd`).\n"
    )

    # ---- review ----
    w("## Licence review\n")
    w(
        "Dependencies whose licence is not in the allowed permissive set or whose provenance is not recorded in the build inputs. "
        "The generator lists them; a maintainer decides.\n"
    )
    for what, why in review:
        w(f"- **{what}**: {why}")
    w("")

    # ---- appendix ----
    w("## Verbatim texts\n")
    src, nb = engine_notice(a.engine, jars)
    print(f"gen_notices: ArcadeDB NOTICE read from {src}", file=sys.stderr)
    w("### ArcadeDB NOTICE (engine release %s)\n" % a.engine)
    w(fence(text(nb)))
    w(
        "### GraalVM Community Edition LICENSE.txt (GPLv2, Classpath Exception, UPL-1.0, BSD-3-Clause)\n"
    )
    w(fence(text((G / "LICENSE.txt").read_bytes())))
    for f in (
        "ADDITIONAL_LICENSE_INFO",
        "ASSEMBLY_EXCEPTION",
        "icu.md",
        "unicode.md",
        "cldr.md",
    ):
        w(f"### OpenJDK java.base legal notice: {f}\n")
        w(fence(text((G / "legal" / "java.base" / f).read_bytes())))
    w(
        "### Texts found inside the jars (de-duplicated by content; bracket = sha256 prefix)\n"
    )
    for k, (n, t, who) in sorted(
        appendix_java.items(), key=lambda kv: (kv[1][0].lower(), kv[1][2])
    ):
        w(f"#### {n} [{k}]\n")
        w("Applies to: " + ", ".join(sorted(who)) + "\n")
        w(fence(t))
    body = "\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body).rstrip() + "\n"
    if a.out:
        Path(a.out).write_text(body)
    status = 0
    if a.check:
        have = Path(a.check).read_text()
        if have != body:
            print(
                f"gen_notices: {a.check} differs from the generated notices; run gen_notices.py --out {a.check}",
                file=sys.stderr,
            )
            diff = list(
                difflib.unified_diff(
                    have.splitlines(),
                    body.splitlines(),
                    "committed",
                    "generated",
                    lineterm="",
                )
            )
            for l in diff[:80]:
                print(l[:300], file=sys.stderr)
            if len(diff) > 80:
                print(f"... {len(diff) - 80} more diff lines", file=sys.stderr)
            status = 1
    for what, why in review:
        print(f"licence review: {what}: {why}", file=sys.stderr)
    if a.strict and review and status == 0:
        status = 2
    return status


if __name__ == "__main__":
    sys.exit(main())
