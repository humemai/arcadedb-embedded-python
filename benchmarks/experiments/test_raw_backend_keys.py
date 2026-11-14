"""No backend key reaches page text as a raw, lowercase, underscored name (2026-11-14, after the first landing was published).

The live page said 'cratedb tpc was not run on the transaction workload' and 'cratedb tpc, SurrealDB (embedded), and SurrealDB (server) define their index before the
first row is loaded': display_name() falls back to the key with its underscores made spaces for a key with no DISPLAY_NAMES entry, and cratedb_tpc had none
(the Redis document arm had the same hole until dc33e2d0c2). Two tests:

  * every backend key of the exporter's own roster (runner.LANES, runner.ARM_RUNS, DISPLAY_NAMES) has a display name that is not the key respelled
    (no underscore, not the key with spaces);
  * page_check._check_raw_backend_keys finds a roster key, or the key with spaces, in page prose (conditions, declared absences, pending
    tables, titles, row labels) outside backticks, and passes the display name and code in backticks.
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="raw-keys-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l1tpc")
import export_web as EW  # noqa: E402
import page_check as PC  # noqa: E402
import runner as RN  # noqa: E402


def _roster():
    keys = set(RN.ARM_RUNS) | set(EW.DISPLAY_NAMES)
    for spec in RN.LANES.values():
        keys |= set(spec[1])
    return keys


def test_every_roster_key_has_a_display_name_that_is_not_the_key_respelled():
    bad = {k: EW.display_name(k) for k in sorted(_roster())
           if "_" in EW.display_name(k) or EW.display_name(k) == k.replace("_", " ")}
    assert not bad, bad


def _payload(text=None, why=None, label=None):
    return {"conditions": [], "tables": [{"id": "docs_oltp", "title": "Document OLTP", "conditions": [text] if text else [],
                                          "declared_absences": [{"backend": label or "CrateDB", "column": None, "kind": "not measured", "why": why or "fine."}],
                                          "entries": [{"backend": label or "CrateDB", "backend_key": "cratedb_tpc"}]}],
            "pending_tables": {}}


def _check(payload):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bad = PC._check_raw_backend_keys(payload)
    return bad, out.getvalue()


def test_the_check_finds_a_raw_key_in_prose_and_passes_the_display_name_and_code():
    assert _check(_payload(text="CrateDB was not run on the transaction workload."))[0] == 0
    assert _check(_payload(text="the setting `cratedb_tpc` is in code"))[0] == 0
    assert _check(_payload(text="cratedb tpc was not run on the transaction workload."))[0] == 1
    assert _check(_payload(text="the arm cratedb_tpc did not finish"))[0] == 1
    bad, out = _check(_payload(why="cratedb tpc was not run."))
    assert bad == 1 and "cratedb_tpc" in out, out
    assert _check(_payload(label="cratedb tpc"))[0] >= 1          # a row label is page text too
    assert _check(_payload(text="PostgreSQL + AGE and DuckDB are named as the page names them, sqlite-vec is a library."))[0] == 0


if __name__ == "__main__":
    test_every_roster_key_has_a_display_name_that_is_not_the_key_respelled()
    test_the_check_finds_a_raw_key_in_prose_and_passes_the_display_name_and_code()
    print("ok")
