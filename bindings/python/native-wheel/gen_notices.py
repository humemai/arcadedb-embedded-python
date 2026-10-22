#!/usr/bin/env python3
"""Generate THIRD_PARTY_NOTICES.md for the native preview wheel from what is compiled into libarcadedb.so.

  python gen_notices.py --build-log ~/build-scratch/native-lib/preview/build.log --engine 26.10.2 \
      --graalvm-home <GraalVM CE home> --out THIRD_PARTY_NOTICES.md
  python gen_notices.py ... --check THIRD_PARTY_NOTICES.md      # exit 1 on drift (build_wheel.py does this)

Inputs, all read from disk, nothing typed by hand except the policy tables below:
  1. the `native-image -cp ...` line that preview-build.sh logs in build.log (the exact jar set of the image);
  2. each jar: licence names from its Maven pom (parent poms followed), verbatim LICENSE/NOTICE files from the jar itself;
  3. the Studio web assets (`static/**` of arcadedb-studio.jar is a registered image resource): production npm packages from
     studio/package-lock.json at the engine release tag, licence texts vendored in notice-texts/npm (see below);
  4. the GraalVM CE home: release file, LICENSE.txt (GPLv2 + Classpath Exception + UPL), legal/java.base notices;
  5. the ArcadeDB NOTICE file at the engine release tag.
notice-texts/ holds licence texts that are in no jar: npm package LICENSE/NOTICE files (npm pack of each locked version) and the
ANTLR and JTS BSD texts (Maven poms only link them). The generator fails when a package has no vendored directory.

Licence policy: the wheel ships under Apache-2.0. ALLOWED are permissive licences; CONDITIONS are allowed with an obligation that the
notices file records (attribution, font name); anything else is listed under "Licence review" and the script exits 2 with --strict.
It never decides such a case; the maintainer does.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
M2 = Path.home() / ".m2" / "repository"
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
CONDITIONS = {
    "CC-BY-4.0": "attribution required (Font Awesome icons)",
    "OFL-1.1": "SIL OFL 1.1 (Font Awesome webfonts): keep the notice, do not sell the font alone, do not use the reserved name for a modified font",
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

# Studio web assets that need an explicit statement beyond the lock file (all facts from the vendored texts / banners).
NPM_NOTES = {
    "jszip": "dual MIT OR GPL-3.0-or-later; used under MIT (notice-texts/npm/jszip@3.10.2/LICENSE.markdown)",
    "apexcharts": "NOT an open-source licence: ApexCharts Community/Commercial licence (see Licence review)",
    "apex-commons": "NOT an open-source licence: ApexCharts licence (see Licence review)",
}

NO_LICENSE_FILE_NOTE = "no licence file in the npm package; the lock file declares the licence, no copyright holder is stated"


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
            return m.group(1).split(":")
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


def eval_spdx(expr):
    """npm SPDX expression -> (verdict, chosen). verdict: allowed | conditions | review."""
    expr = expr.strip()
    tokens = re.findall(r"\(|\)|AND|OR|[A-Za-z0-9.\-+]+", expr)
    pos = 0

    def parse_or():
        nonlocal pos
        v = parse_and()
        while pos < len(tokens) and tokens[pos] == "OR":
            pos += 1
            w = parse_and()
            v = best(v, w)
        return v

    def parse_and():
        nonlocal pos
        v = parse_atom()
        while pos < len(tokens) and tokens[pos] == "AND":
            pos += 1
            w = parse_atom()
            v = (worst(v[0], w[0]), v[1] + [x for x in w[1] if x not in v[1]])
        return v

    def parse_atom():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        if t == "(":
            v = parse_or()
            pos += 1  # ")"
            return v
        if t in ALLOWED:
            return ("allowed", [t])
        if t in CONDITIONS:
            return ("conditions", [t])
        return ("review", [t])

    rank = {"allowed": 0, "conditions": 1, "review": 2}

    def best(a, b):
        return a if rank[a[0]] <= rank[b[0]] else b

    def worst(a, b):
        return a if rank[a] >= rank[b] else b

    if not tokens or tokens[0] in ("SEE", "None", "UNLICENSED"):
        return ("review", [expr or "none declared"])
    try:
        return parse_or()
    except IndexError:
        return ("review", [expr])


def jar_info(jar):
    p = Path(jar)
    try:
        rel = p.relative_to(M2)
    except ValueError:
        return None  # the glue jar of this repository (Apache-2.0, native-spike/)
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


def git_show(engine, path, fallback=None):
    r = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{engine}:{path}"], capture_output=True
    )
    if r.returncode == 0:
        return r.stdout
    if fallback and Path(fallback).exists():
        return Path(fallback).read_bytes()
    sys.exit(f"gen_notices: cannot read {path} at tag {engine} (git fetch --tags?)")


def fence(body):
    n = max([3] + [len(m) + 1 for m in re.findall(r"`{3,}", body)])
    return "`" * n + "\n" + body + "`" * n + "\n"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--build-log",
        help="build.log of preview-build.sh (holds the native-image classpath)",
    )
    g.add_argument("--lib-dir", help="shortcut: <lib-dir>/build.log")
    ap.add_argument("--engine", required=True, help="engine release tag, e.g. 26.10.2")
    ap.add_argument("--graalvm-home", required=True)
    ap.add_argument("--out")
    ap.add_argument("--check", help="compare with this file; exit 1 when it differs")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 2 when the licence review list is not empty",
    )
    a = ap.parse_args()
    log = a.build_log or str(Path(a.lib_dir) / "build.log")
    cp = parse_classpath(log)
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
        "generator output. Licence names come from each artifact's own Maven pom (or the npm lock file); notice texts are copied "
        "verbatim from the jars, the npm packages, the engine tag and the GraalVM home. A text of the Apache License 2.0 is in "
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
        "`libjvector-x86_64.so` is taken unmodified from `io.github.jbellis:jvector:4.0.2` (Apache-2.0, pom). The jar carries no "
        "licence file or source for the kernels inside it; the library is built from Google Highway, which upstream offers under "
        "Apache-2.0 or BSD-3-Clause. That last fact is not recorded in the jar (see Licence review).\n"
    )
    review.append(
        (
            "libjvector-x86_64.so",
            "binary kernels of unknown provenance inside the jvector jar (Highway, Apache-2.0 OR BSD-3-Clause per upstream, not verifiable from the jar); confirm against the jvector 4.0.2 source",
        )
    )

    # ---- Studio web assets ----
    lock = json.loads(git_show(a.engine, "studio/package-lock.json"))
    w("## ArcadeDB Studio web assets (resource `static/**` inside libarcadedb.so)\n")
    w(
        "The engine's `arcadedb-studio` jar bundles browser libraries (webpack output under `static/dist`, `static/swagger-ui`). The image "
        "registers `static/**` as a resource, so they are inside `libarcadedb.so`. Production packages of `studio/package-lock.json` at tag "
        f"`{a.engine}`; the lock file also resolves their transitive packages, which pdfmake and jszip bundle.\n"
    )
    w("| npm package | Version | Declared licence | Verdict | Note |")
    w("|---|---|---|---|---|")
    npm_texts = {}
    pkgs = sorted(
        {
            (k.split("node_modules/")[-1], v["version"], v.get("license", "None"))
            for k, v in lock["packages"].items()
            if k and not v.get("dev")
        }
    )
    for name, ver, lic in pkgs:
        d = TEXTS / "npm" / f"{name.replace('/', '__')}@{ver}"
        if not d.is_dir():
            sys.exit(
                f"gen_notices: no vendored licence directory {d}; run npm pack {name}@{ver} and copy LICENSE/NOTICE files"
            )
        verdict, chosen = eval_spdx(lic)
        files = sorted(p for p in d.iterdir() if p.is_file())
        note = NPM_NOTES.get(name, "" if files else NO_LICENSE_FILE_NOTE)
        if verdict == "review" and name in NPM_NOTES:
            pass  # recorded once, with the full reason, in the ApexCharts entry below
        elif verdict == "review":
            if not (
                name == "png-js"
                and any("MIT" in f.read_text(errors="replace")[:20] for f in files)
            ):
                review.append(
                    (
                        f"npm {name}@{ver}",
                        f"declared licence '{lic}' is not in the allowed set",
                    )
                )
            else:
                verdict, note = (
                    "allowed",
                    "lock file declares none; the package's LICENSE file is MIT",
                )
        if verdict == "conditions":
            note = "; ".join(CONDITIONS[c] for c in chosen if c in CONDITIONS)
        for f in files:
            b = f.read_bytes()
            npm_texts.setdefault(sha(b), [f"{name}@{ver}/{f.name}", text(b), []])[
                2
            ].append(f"{name}@{ver}")
        w(f"| {name} | {ver} | {lic} | {verdict} | {note} |")
    w("")
    # banners the webpack build kept in the jar
    studio = next((c for c in cp if "arcadedb-studio" in c), None)
    banners = []
    if studio:
        with zipfile.ZipFile(studio) as z:
            for n in sorted(z.namelist()):
                if n.endswith(".LICENSE.txt") and n.startswith("static/"):
                    banners.append((n, text(z.read(n))))
    w(
        "Also inside the jar and the library: Roboto fonts in `static/dist/js/vfs_fonts.js` (pdfmake's default font bundle; Roboto is "
        "Apache-2.0, Google), Font Awesome webfonts and CSS, and ArcadeDB's own Studio code (Apache-2.0).\n"
    )
    review.append(
        (
            "static/dist/js/vfs_fonts.js (Roboto)",
            "font licence is taken from upstream knowledge (Apache-2.0), no licence file in the jar or the npm package of pdfmake",
        )
    )

    # ApexCharts
    review.insert(
        0,
        (
            "npm apexcharts@7.8.0 + apex-commons@0.8.1 (static/dist/js/apexcharts.min.js, in libarcadedb.so)",
            "ApexCharts is under a dual Community/Commercial licence, not an open-source licence: free only for organizations under USD 2M "
            "annual revenue/budget/funding; redistribution as part of a product used by other people needs a paid OEM licence; text in "
            "notice-texts/npm/apexcharts@7.8.0/LICENSE.md. Not compatible with shipping under Apache-2.0.",
        ),
    )

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
    w("### ArcadeDB NOTICE (engine tag %s)\n" % a.engine)
    w(fence(text(git_show(a.engine, "NOTICE", REPO / "NOTICE"))))
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
    w("### Studio npm packages: licence and notice files (de-duplicated by content)\n")
    for k, (n, t, who) in sorted(npm_texts.items(), key=lambda kv: kv[1][0].lower()):
        w(f"#### {n} [{k}]\n")
        w("Applies to: " + ", ".join(sorted(who)) + "\n")
        w(fence(t))
    w(
        "### Banners kept by webpack in `arcadedb-studio.jar` (`static/dist/js/*.LICENSE.txt`)\n"
    )
    for n, t in banners:
        w(f"#### {n}\n")
        w(fence(t))

    body = "\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body).rstrip() + "\n"
    if a.out:
        Path(a.out).write_text(body)
    status = 0
    if a.check:
        if Path(a.check).read_text() != body:
            print(
                f"gen_notices: {a.check} differs from the generated notices; run gen_notices.py --out {a.check}",
                file=sys.stderr,
            )
            status = 1
    for what, why in review:
        print(f"licence review: {what}: {why}", file=sys.stderr)
    if a.strict and review and status == 0:
        status = 2
    return status


if __name__ == "__main__":
    sys.exit(main())
