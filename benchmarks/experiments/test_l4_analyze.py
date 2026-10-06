"""The two PostgreSQL-family time-series arms are timed on the same steps (CAMPAIGN section 7, row 70).

Run with `python -m pytest test_l4_analyze.py -q -rs` from this directory.

Plain PostgreSQL's `ingest` ran `ANALYZE p` after its index, inside the ingest timer; TimescaleDB's did not,
so the two arms were timed on different steps (found writing the re-pin's ingest sentences). The re-pin
re-runs every arm, so TimescaleDB now runs it too. Running the methods needs a database, so the check is
static, on the source of the two `ingest` methods: it fails if either lacks the ANALYZE, puts it before the
index, or puts it inside the index timer.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _method(cls, name="ingest"):
    src = (HERE / "l4_tsbs.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return ast.get_source_segment(src, fn)
    raise AssertionError(f"{cls}.{name} not found")


@pytest.mark.parametrize("cls", ["PostgresTS", "TimescaleTS"])
def test_both_postgresql_family_arms_analyze_after_their_index_inside_the_ingest(cls):
    body = _method(cls)
    assert 'c.execute("ANALYZE p")' in body, f"{cls}.ingest has no ANALYZE: the arms would be timed differently"
    assert body.index("CREATE INDEX p_host_ts") < body.index('"ANALYZE p"')      # after the index, as the sentence says
    assert body.index('"ANALYZE p"') > body.index("index_timer")                 # and outside the index timer
    assert body.count('c.execute("ANALYZE p")') == 1


def test_the_lane_times_ingest_whole():
    """The sentence says ANALYZE is inside the ingest timer: l4's main reads perf_counter around b.ingest."""
    src = (HERE / "l4_tsbs.py").read_text()
    assert re.search(r"t0 = time\.perf_counter\(\)\s+with _beat\.phase\(\"ingest\", n=len\(pts\)\):\s+b\.ingest\(pts\)\s+dt = time\.perf_counter\(\) - t0", src)


def test_campaign_records_the_change():
    row = next(l for l in (HERE / "CAMPAIGN.md").read_text().splitlines() if l.startswith("| 70 |"))
    assert "ANALYZE" in row and "TimescaleDB" in row and "owed at the re-pin" in row and "done on repin-prep-2" in row
