"""Test setup shared by every test in this directory.

HERMETIC RESULTS. The exporter reads untracked overlay directories (dense_mp5_<pin>, e4decomp_<pin>, sparse_mp_<pin>) and the
run log from results/, which a clean checkout does not have. Unless a run names its own BENCH_RESULTS_DIR, the whole session
reads a copy of the 2026-11 fixture (fixtures/publish_2611, pin 261100fix) instead of the developer's results/, so the suite
gives the same answer on a laptop, on mini and in CI.
"""
import atexit
import gzip
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "publish_2611" / "results"


def _hermetic_results():
    if os.environ.get("BENCH_RESULTS_DIR"):
        return
    root = Path(tempfile.mkdtemp(prefix="bench-fixture-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    dest = root / "results"
    shutil.copytree(_FIXTURE, dest)
    with gzip.open(dest / "runs.jsonl.gz", "rt") as src, open(dest / "runs.jsonl", "w") as out:
        shutil.copyfileobj(src, out)
    (dest / "runs.jsonl.gz").unlink()
    os.environ["BENCH_RESULTS_DIR"] = str(dest)
    os.environ.setdefault("BENCH_ENGINE_COMMIT", "261100fix")


_hermetic_results()


@pytest.fixture(autouse=True)
def _no_cap_rule_data(request, monkeypatch):
    if request.module.__name__ == "test_cap_rule":
        return
    import cap_rule
    monkeypatch.setitem(cap_rule._CACHE, cap_rule.RULE_JSON, None)
