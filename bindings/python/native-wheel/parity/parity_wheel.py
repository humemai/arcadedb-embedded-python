#!/usr/bin/env python3
"""parity_wheel.py (parity.py for the installed arcadedb-embedded-native wheel; --alias maps arcadedb_embedded to arcadedb_native): run the bindings test suite file by file and count outcomes per file.

  ARCADEDB_NATIVE_LIB=/path/libarcadedb.so python3 parity.py --repo <worktree> --python <venv python> --backend native --out parity-native.tsv

A run per test file in its own process (a hang or crash costs one file), junit XML per file, then one table:
passed / failed / error / NOTYET (the test needs a Java-object API, reported by tests/conftest.py as a skip whose reason starts
with NOTYET) / other skips / TIMEOUT-or-crash. Files in tests/conftest.py's NATIVE_NOT_APPLICABLE are not collected (JVM-only).
"""

import argparse
import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

p = argparse.ArgumentParser()
p.add_argument("--repo", required=True)
p.add_argument("--python", default=sys.executable)
p.add_argument("--backend", default="native")
p.add_argument("--out", required=True)
p.add_argument("--timeout", type=int, default=900)
p.add_argument("--cores", default="0-5,8-11")
p.add_argument("--files", default="")
p.add_argument("--alias", required=True)
a = p.parse_args()

pkg = os.path.join(a.repo, "bindings", "python")
files = sorted(glob.glob(os.path.join(pkg, "tests", "test_*.py")))
import ast

na_files = {}
for node in ast.parse(open(os.path.join(pkg, "tests", "conftest.py")).read()).body:
    if (
        isinstance(node, ast.Assign)
        and getattr(node.targets[0], "id", "") == "NATIVE_NOT_APPLICABLE"
    ):
        na_files = ast.literal_eval(node.value)
if a.backend == "native":
    files = [f for f in files if os.path.basename(f) not in na_files]
if a.files:
    want = set(a.files.split(","))
    files = [f for f in files if os.path.basename(f) in want]
env = dict(
    os.environ, PYTHONPATH=a.alias, ARCADEDB_BACKEND=a.backend, PYTHONUNBUFFERED="1"
)
env.pop("ARCADEDB_NATIVE_LIB", None)  # the library comes from the installed wheel
chk = subprocess.run(
    [
        a.python,
        "-c",
        'import arcadedb_embedded as m, arcadedb_native as n; print(n.__file__, n.__version__, n.ENGINE_VERSION, n.SOURCE_COMMIT); assert m is n; assert "site-packages" in n.__file__',
    ],
    env=env,
    cwd="/",
    capture_output=True,
    text=True,
)
print("WHEEL CHECK:", chk.stdout.strip(), chk.stderr.strip()[-300:], flush=True)
assert chk.returncode == 0, "tests would not run against the installed wheel"
a.out = os.path.abspath(a.out)
xmldir = os.path.splitext(a.out)[0] + "-xml"
os.makedirs(xmldir, exist_ok=True)
rows, tot = [], dict.fromkeys(
    ["passed", "failed", "error", "notyet", "na_jvm", "skipped", "timeout"], 0
)
for f in files:
    name = os.path.basename(f)
    xml = os.path.join(xmldir, name + ".xml")
    cmd = [
        "taskset",
        "-c",
        a.cores,
        "nice",
        "-n",
        "10",
        a.python,
        "-m",
        "pytest",
        f"tests/{name}",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--junitxml={xml}",
        "-o",
        "junit_family=xunit1",
    ]
    try:
        r = subprocess.run(
            cmd, cwd=pkg, env=env, capture_output=True, text=True, timeout=a.timeout
        )
        status = ""
        open(os.path.join(xmldir, name + ".log"), "w").write(
            r.stdout[-20000:] + "\n" + r.stderr[-5000:]
        )
    except subprocess.TimeoutExpired as e:
        status = "TIMEOUT"
        open(os.path.join(xmldir, name + ".log"), "w").write(
            ((e.stdout or b"")[-8000:]).decode()
            if isinstance(e.stdout, bytes)
            else str(e.stdout)[-8000:]
        )
    c = dict.fromkeys(["passed", "failed", "error", "notyet", "na_jvm", "skipped"], 0)
    fails = []
    if os.path.exists(xml):
        try:
            for tc in ET.parse(xml).getroot().iter("testcase"):
                if tc.find("failure") is not None:
                    c["failed"] += 1
                    fails.append(tc.get("name"))
                elif tc.find("error") is not None:
                    c["error"] += 1
                    fails.append(tc.get("name"))
                elif tc.find("skipped") is not None:
                    msg = tc.find("skipped").get("message") or ""
                    c[
                        (
                            "notyet"
                            if msg.startswith("NOTYET")
                            else "na_jvm" if msg.startswith("NA-JVM") else "skipped"
                        )
                    ] += 1
                else:
                    c["passed"] += 1
        except ET.ParseError:
            status = status or "BADXML"
    else:
        status = status or "CRASH"
    for k in c:
        tot[k] += c[k]
    if status == "TIMEOUT":
        tot["timeout"] += 1
    rows.append((name, c, status, fails))
    print(
        f"{name:45s} pass={c['passed']:4d} fail={c['failed']:3d} err={c['error']:3d} notyet={c['notyet']:3d} na_jvm={c['na_jvm']:3d} skip={c['skipped']:3d} {status}",
        flush=True,
    )
with open(a.out, "w") as fh:
    fh.write(
        "file\tpassed\tfailed\terror\tnotyet\tna_jvm\tskipped\tstatus\tfailing_tests\n"
    )
    for name, c, status, fails in rows:
        fh.write(
            f"{name}\t{c['passed']}\t{c['failed']}\t{c['error']}\t{c['notyet']}\t{c['na_jvm']}\t{c['skipped']}\t{status}\t{';'.join(fails[:40])}\n"
        )
    fh.write(
        f"TOTAL\t{tot['passed']}\t{tot['failed']}\t{tot['error']}\t{tot['notyet']}\t{tot['na_jvm']}\t{tot['skipped']}\ttimeouts={tot['timeout']}\t\n"
    )
print("TOTAL", tot)
