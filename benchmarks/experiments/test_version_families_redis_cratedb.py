"""version_consistency_check reads Redis and CrateDB version strings (2026-11-14, first landing of the n=3 rows).

The two comparators joined the document lane in 2026-10 and were never in FAMILIES, so on the first publish with their rows the gate reported
'no engine version could be read from redis 8.10.2' and 'crate 6.4.6' (rule 0: a string it cannot read is a failure, not a row to skip).
Light: a temporary payload. Run with pytest, or as plain functions from this directory.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import version_consistency_check as V  # noqa: E402


def _payload(version_name, backend):
    return {"tables": [{"id": "docs_olap", "entries": [{"backend": backend, "version_name": version_name, "metrics": {"Q1 p50 ms": {"median": 1.0}}}]}]}


def test_redis_and_cratedb_versions_are_read():
    for backend, version in (("Redis", "redis 8.10.2"), ("cratedb tpc", "crate 6.4.6"), ("cratedb tpc", "cratedb 6.4.6")):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "p.json")
            path.write_text(json.dumps(_payload(version, backend)))
            bad = [f for f in V.check(str(path)) if "no engine version could be read" in f]
        assert not bad, (version, bad)


def test_an_unknown_engine_is_still_refused():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "p.json")
        path.write_text(json.dumps(_payload("frobnicate 1.2.3", "Frob")))
        assert any("no engine version could be read" in f for f in V.check(str(path)))


if __name__ == "__main__":
    test_redis_and_cratedb_versions_are_read()
    test_an_unknown_engine_is_still_refused()
    print("ok")
