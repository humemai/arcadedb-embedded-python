"""The sparse multipass passes keep each engine's own version (CAMPAIGN section 7 row 64, BUGS F173).

Run with `python -m pytest test_sparse_mp_versions.py -q -rs` from this directory.

The driver put the backend's version in `engine_version` and `run_conditions()` then overwrote it with the arcadedb-embedded
wheel's, so every October comparator pass read "26.10.1.dev0" (and a laptop Milvus pass "unknown"). It now keeps the
adapter's own string as `lib_version`, always starting with the engine's name, and restores `engine_version` for the
ArcadeDB arms, as the dense driver does. The driver runs here in a subprocess against a stand-in backend.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sparse_multipass_driver as D  # noqa: E402

# ---- row 64: the multipass driver's version fields --------------------------------------------------------------

@pytest.mark.parametrize("backend,adapter_says", [
    ("qdrant_sparse", "qdrant:1.19.1"), ("qdrant_sparse_uint8", "qdrant:1.19.1"),
    ("milvus_sparse", "milvus:3.0.1"), ("pgvector_sparse", "pgvector:0.8.6 on 18"),
    ("elasticsearch_sparse", "9.5.4"),            # the one adapter that reports the bare number
])
def test_a_comparator_pass_keeps_a_lib_version_that_starts_with_its_engine(backend, adapter_says):
    lv = D.lib_version_of(backend, adapter_says)
    assert lv.lower().startswith(backend.split("_")[0]) and adapter_says.split(":")[-1].split()[0] in lv


def test_lib_version_is_none_when_the_adapter_reported_nothing():
    assert D.lib_version_of("milvus_sparse", None) is None and D.lib_version_of("milvus_sparse", "") is None


_HARNESS = textwrap.dedent('''
    import os, sys
    sys.path.insert(0, {here!r})
    import l3_sparse
    class Fake(l3_sparse.Base):
        name = {backend!r}
        version = {version!r}
        SPARSE_RESULT = {result!r}
        def connect(self): pass
        def build(self, n): pass
        def search(self, idx, vals, k): return list(range(k))
        def resolve(self, ids): return ids
    l3_sparse.BACKENDS[{backend!r}] = Fake
    l3_sparse.SCALE_QUERIES["micro"] = 120          # the driver wants 50 warm queries or it refuses
    os.environ.update(BENCH_MP_BACKEND={backend!r}, BENCH_MP_SCALE="micro", BENCH_MP_PASSES="1", PROBE_OUT={out!r})
    import sparse_multipass_driver as D
    D.main()
''')


def _run_driver(tmp_path, backend, version, result):
    out = tmp_path / "pass.json"
    code = _HARNESS.format(here=str(HERE), backend=backend, version=version, result=result, out=str(out))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, cwd=HERE)
    assert out.exists(), r.stdout[-500:] + r.stderr[-500:]
    return json.loads(out.read_text())


def test_a_comparator_pass_record_names_its_own_version_not_the_wheel(tmp_path):
    for rec in _run_driver(tmp_path, "milvus_sparse", "milvus:3.0.1", None):
        # lib_version is what the page reads for a comparator pass (export_web). engine_version is whatever run_conditions()
        # stamps from the package in the container, the ArcadeDB wheel's version where one is installed (a repo venv) and
        # "unknown" where none is (a bench client image), which is exactly why lib_version exists; asserting on it here made
        # the test pass vacuously in a clean environment and fail in a venv that holds the wheel.
        assert rec["lib_version"] == "milvus:3.0.1"
        assert not rec.get("sparse_result")


def test_an_arcadedb_pass_record_keeps_the_adapters_build_and_says_it_returned_ids(tmp_path):
    for rec in _run_driver(tmp_path, "arcadedb_sparse_server", "server:26.10.1", "id"):
        assert rec["engine_version"] == "server:26.10.1"                 # restored after run_conditions()
        assert rec["lib_version"].startswith("arcadedb")
        assert rec["sparse_result"] == "id"
