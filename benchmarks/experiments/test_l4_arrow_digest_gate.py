"""The precondition for the 2026-11 large-result headline (DECISIONS #170 amendment, CAMPAIGN section 7, PR #413): on l4 `q_high` and
`q_groupby` the typed Arrow read must give an answer whose digest equals the plain read's, including the native time-series datetime column.
Found by the 2026-10-21 gate run: DuckDB's unaliased `avg(uu)` came back from the Arrow table under that name, the digest looked for `v`,
and the typed digest read <missing> where fetchall() had the number."""
import datetime as dt
import os
import sys

import pytest

pa = pytest.importorskip("pyarrow")
duckdb = pytest.importorskip("duckdb")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_common  # noqa: E402
import l4_tsbs as m  # noqa: E402


def digest(rows, query):
    return bench_common.result_digest(rows, **m.Q_DIGEST[query])["digest"]


@pytest.fixture()
def duck():
    cx = duckdb.connect(":memory:")
    cx.execute("CREATE TABLE p (host VARCHAR, ts BIGINT, uu DOUBLE)")
    cx.executemany("INSERT INTO p VALUES (?,?,?)",
                   [(f"host_{h}", 1767225600 + 60 * i, float((7 * h + i) % 100)) for h in range(3) for i in range(300)])
    return cx


GROUPBY = "SELECT host, (ts - ts % 3600) AS h, avg(uu) FROM p GROUP BY host, h ORDER BY host, h"
HIGH = "SELECT host, ts, uu FROM p WHERE uu > 90"


@pytest.mark.parametrize("query,sql", [("q_groupby", GROUPBY), ("q_high", HIGH)])
def test_duckdb_typed_read_has_the_plain_reads_digest(duck, query, sql):
    plain = duck.execute(sql).fetchall()
    typed = m.ArrowResult(duck.execute(sql).to_arrow_table(), positional=True)
    assert len(typed) == len(plain) > 0
    assert digest(list(typed), query) == digest(plain, query)


def test_dict_rows_would_have_missed_the_unaliased_aggregate(duck):
    plain = duck.execute(GROUPBY).fetchall()
    by_name = list(m.ArrowResult(duck.execute(GROUPBY).to_arrow_table()))
    assert digest(by_name, "q_groupby") != digest(plain, "q_groupby")


@pytest.mark.parametrize("tz", [None, "UTC"])
@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_native_timeseries_datetime_column_digests_as_the_epoch_millisecond(tz, unit):
    """ArcadeDB's native time-series `ts` is epoch milliseconds in to_list() and a timestamp column in to_arrow(), naive or UTC-aware."""
    epoch_ms = [1767225600000 + 60000 * i for i in range(5)]
    plain = [{"host": "host_0", "ts": t, "uu": 91.0} for t in epoch_ms]
    table = pa.table({"host": ["host_0"] * 5,
                      "ts": pa.array(epoch_ms, pa.int64()).cast(pa.timestamp(unit, tz=tz), safe=False) if unit == "ms" else
                      pa.array([t * (1000 if unit == "us" else 1_000_000) for t in epoch_ms], pa.int64()).cast(pa.timestamp(unit, tz=tz)),
                      "uu": [91.0] * 5})
    typed = list(m.ArrowResult(table))
    assert all(isinstance(r["ts"], (dt.datetime, int)) for r in typed)
    assert digest(typed, "q_high") == digest(plain, "q_high")
