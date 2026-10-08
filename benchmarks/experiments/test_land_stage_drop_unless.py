"""land_stage.py --drop-unless: rows a repair stage replaced are dropped at landing, keyed on the stamp only the repair carries.

Run with `python -m pytest test_land_stage_drop_unless.py -q` from this directory.

The 26.10.1 campaign's first stage measured ArcadeDB's served graph OLTP before the bulk-load body limit was raised (DECISIONS
#172); the repair stage re-ran it with the raise, and its rows carry `server_http_body_max_bytes` = 68719476736. The old rows
(six clean sf1 rows and two failed sf10 rows) must not merge: they measured the engine default that broke the load.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage  # noqa: E402

SPEC = "arcadedb_graph_server:l2:oltp:server_http_body_max_bytes=68719476736"


def _row(backend="arcadedb_graph_server", lane="l2", workload="oltp", stamp=None):
    r = {"backend": backend, "lane": lane, "workload": workload}
    if stamp is not None:
        r["server_http_body_max_bytes"] = stamp
    return r


def test_parse_and_reject_malformed():
    assert land_stage.parse_drop_unless(SPEC) == ("arcadedb_graph_server", "l2", "oltp", "server_http_body_max_bytes",
                                                  "68719476736")
    for bad in ("arcadedb_graph_server:l2:oltp", "a:b:c:field", ":l2:oltp:f=v", "a:b::f=v"):
        with pytest.raises(SystemExit):
            land_stage.parse_drop_unless(bad)


def test_drops_only_the_unstamped_rows_of_that_cell():
    u = land_stage.parse_drop_unless(SPEC)
    assert land_stage.replaced_by_repair(_row(), u)                              # no stamp: replaced
    assert land_stage.replaced_by_repair(_row(stamp=104857600), u)               # the old default: replaced
    assert not land_stage.replaced_by_repair(_row(stamp=68719476736), u)         # the repair's rows stay
    assert not land_stage.replaced_by_repair(_row(workload="olap"), u)           # another workload stays
    assert not land_stage.replaced_by_repair(_row(backend="arcadedb_graph_embedded"), u)
    assert not land_stage.replaced_by_repair(_row(lane="e2"), u)


def test_the_campaign_shape_keeps_twelve_and_drops_eight():
    u = land_stage.parse_drop_unless(SPEC)
    rows = [_row() for _ in range(8)] + [_row(stamp=68719476736) for _ in range(12)] + [_row(workload="olap", stamp=68719476736)] * 6
    dropped = [r for r in rows if land_stage.replaced_by_repair(r, u)]
    assert len(dropped) == 8 and len(rows) - len(dropped) == 18
