"""LadybugDB is pinned in the benchmark images, and its `vector` extension is baked in at build time (CAMPAIGN section 7, row 92).

Run with `python -m pytest test_ladybug_pin.py -q -rs` from this directory.

On 2026-10-25 at 04:28 UTC the vendor overwrote the `v0.21.0` extension download that every 0.21.x client reads, and the pinned
`ladybug==0.21.2` could no longer `LOAD vector` (LadybugDB/ladybug#1390). The pin moved to 0.22.0, and the extension is now installed
while the image is built and checked against a sha256 written in build_images.sh. These tests hold the chain: one pin on the client
and dense images, the documents say the same number, the sha256 pin is well formed and reaches only the client image, the Dockerfile
runs the bake step, and the bake script refuses a binary that is not the pinned one (run here against a fake `ladybug`, no network).
"""
import hashlib
import re
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = "0.22.0"
BUILD = (HERE / "build_images.sh").read_text()
DOCKERFILE = (HERE / "Dockerfile.bench").read_text()
BAKE = HERE / "bake_ladybug_extensions.py"


def _pkgs_line(key):
    m = re.search(rf'^\s*\[{key}\]="([^"]*)"', BUILD, re.M)
    assert m, f"no [{key}] line in build_images.sh"
    return m.group(1)


def test_client_and_dense_images_pin_the_same_ladybug_with_a_hard_equals():
    for key in ("client", "dense"):
        assert re.findall(r"\bladybug(?:[=<>!~]=?\S*)?", _pkgs_line(key)) == [f"ladybug=={PIN}"], key


def test_the_documents_name_the_pin_and_no_other_current_one():
    for name in ("COMPARATORS.md", "CAMPAIGN.md", "QUANTIZATION.md"):
        text = (HERE / name).read_text()
        stale = [l[:100] for l in text.splitlines() if re.search(r"ladybug==0\.2[01]\.\d+", l) and "0.22.0" not in l]
        assert not stale, (name, stale)
    assert f"`ladybug=={PIN}`" in (HERE / "COMPARATORS.md").read_text()


def test_the_extension_pin_is_a_sha256_and_reaches_only_the_client_image():
    m = re.search(r'^LADYBUG_EXTENSIONS="(\S+)"$', BUILD, re.M)
    assert m, "no LADYBUG_EXTENSIONS pin in build_images.sh"
    pairs = dict(p.split("=", 1) for p in m.group(1).split())
    assert set(pairs) == {"vector"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in pairs.values())
    assert '[ "$be" = "client" ] && _ext="$LADYBUG_EXTENSIONS"' in BUILD
    assert '--build-arg LADYBUG_EXTENSIONS="$_ext"' in BUILD


def test_the_dockerfile_runs_the_bake_step_only_when_given_a_pin():
    assert 'ARG LADYBUG_EXTENSIONS=""' in DOCKERFILE
    assert "COPY bake_ladybug_extensions.py /tmp/bake_ladybug_extensions.py" in DOCKERFILE
    assert 'if [ -n "${LADYBUG_EXTENSIONS}" ]; then python /tmp/bake_ladybug_extensions.py ${LADYBUG_EXTENSIONS}; fi' in DOCKERFILE
    assert BAKE.exists()


FAKE_LADYBUG = textwrap.dedent('''
    import os
    __version__ = "0.22.0"
    class Database:
        def __init__(self, path): pass
    class Connection:
        def __init__(self, db): pass
        def execute(self, q):
            op, name = q.split()
            if op == "INSTALL":
                d = os.path.expanduser(f"~/.lbdb/extension/0.22.0/linux_amd64/{name}")
                os.makedirs(d, exist_ok=True)
                open(f"{d}/lib{name}.lbug_extension", "wb").write(b"the vendor's bytes")
            elif op == "LOAD" and os.environ.get("FAKE_LOAD_FAILS"):
                raise RuntimeError("undefined symbol: Transaction::getMinUncommittedNodeOffset")
''')


def _bake(tmp_path, pin, **env):
    (tmp_path / "ladybug.py").write_text(FAKE_LADYBUG)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    # -I ignores PYTHONPATH, so the fake module's directory goes on sys.path inside the child before the script runs
    code = (f"import sys, runpy; sys.path.insert(0, {str(tmp_path)!r}); sys.argv = [{str(BAKE)!r}, {pin!r}]; "
            f"runpy.run_path({str(BAKE)!r}, run_name='__main__')")
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                       env={"HOME": str(home), "PATH": "/usr/bin:/bin", **env})
    return r, home / ".lbdb/extension/0.22.0/linux_amd64/vector/libvector.lbug_extension"


def test_bake_keeps_a_binary_with_the_pinned_sha256(tmp_path):
    good = hashlib.sha256(b"the vendor's bytes").hexdigest()
    r, f = _bake(tmp_path, f"vector={good}")
    assert r.returncode == 0, r.stderr
    assert f.exists() and good in r.stdout


def test_bake_refuses_and_removes_a_binary_the_vendor_replaced(tmp_path):
    r, f = _bake(tmp_path, "vector=" + "0" * 64)
    assert r.returncode != 0
    assert "REFUSING" in r.stderr and "LadybugDB/ladybug#1390" in r.stderr
    assert not f.exists()


def test_bake_fails_the_build_when_load_rejects_the_binary(tmp_path):
    good = hashlib.sha256(b"the vendor's bytes").hexdigest()
    r, _ = _bake(tmp_path, f"vector={good}", FAKE_LOAD_FAILS="1")
    assert r.returncode != 0 and "undefined symbol" in r.stderr


def test_bake_rejects_a_malformed_pin(tmp_path):
    r, _ = _bake(tmp_path, "vector=abc")
    assert r.returncode != 0 and "bad pin" in r.stderr
