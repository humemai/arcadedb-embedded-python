"""Every example in docs/guide/timeseries.md, run and asserted (#388).

Each statement a test sends must appear verbatim in the guide, so an edit to
the page that this file does not follow fails here instead of drifting.
Everything below was measured on the 26.10.2 engine.
"""

from datetime import datetime
from pathlib import Path

import arcadedb_embedded as arcadedb
import numpy as np
import pyarrow as pa
import pytest

DOC = (
    Path(__file__).resolve().parents[1] / "docs" / "guide" / "timeseries.md"
).read_text(encoding="utf-8")

T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z in epoch milliseconds
MINUTE = 60_000

CREATE_TYPE = (
    "CREATE TIMESERIES TYPE Reading TIMESTAMP ts PRECISION MILLISECOND "
    "TAGS (sensor STRING) FIELDS (temp DOUBLE, hum DOUBLE) SHARDS 2 "
    "RETENTION 90 DAYS COMPACTION_INTERVAL 1 HOURS "
    "DOWNSAMPLING POLICY AFTER 7 DAYS GRANULARITY 1 HOURS "
    "AFTER 30 DAYS GRANULARITY 1 DAYS"
)


def doc(statement):
    """Return `statement` after checking that the guide shows it."""
    assert statement in DOC, f"not in docs/guide/timeseries.md: {statement}"
    return statement


def rows(db, statement, *params):
    return [r.to_dict() for r in db.query("sql", doc(statement), *params)]


def utc(minute):
    """The naive datetime a TIMESERIES timestamp comes back as (UTC)."""
    return datetime(2026, 1, 1, 0, minute)


@pytest.fixture
def db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as database:
        database.command("sql", doc(CREATE_TYPE))
        yield database


@pytest.fixture
def loaded(db):
    """Reading with six samples: sensor a at minutes 0, 1, 3; sensor b at 1, 2, 3."""
    db.command(
        "sql",
        doc("INSERT INTO Reading SET ts = ?, sensor = 'a', temp = 20.0, hum = 40.0"),
        T0,
    )
    db.command(
        "sql",
        doc(
            "INSERT INTO Reading (ts, sensor, temp, hum) VALUES (?, 'a', 21.0, 41.0), (?, 'b', 30.0, 50.0)"
        ),
        T0 + MINUTE,
        T0 + MINUTE,
    )
    db.command(
        "sql",
        doc(
            'INSERT INTO Reading CONTENT {"ts": 1767225780000, "sensor": "a", "temp": 22.0, "hum": 42.0}'
        ),
    )
    for minute, temp in [(2, 31.0), (3, 32.0)]:
        db.command(
            "sql",
            "INSERT INTO Reading SET ts = ?, sensor = 'b', temp = ?, hum = 51.0",
            T0 + minute * MINUTE,
            temp,
        )
    return db


def test_type_is_declared_as_written(db):
    row = db.query(
        "sql", doc("SELECT FROM schema:types WHERE name = 'Reading'")
    ).first()
    assert row.get("timestampColumn") == "ts"
    assert row.get("precision") == "MILLISECOND"
    assert row.get("shardCount") == 2
    assert row.get("retentionMs") == 90 * 24 * 3600 * 1000
    assert row.get("compactionBucketIntervalMs") == 3600 * 1000
    assert len(row.get("downsamplingTiers")) == 2


def test_create_if_not_exists(db):
    again = db.command(
        "sql",
        doc(
            "CREATE TIMESERIES TYPE Reading IF NOT EXISTS TIMESTAMP ts TAGS (sensor STRING) FIELDS (temp DOUBLE)"
        ),
    ).first()
    assert again.to_dict() == {
        "operation": "create timeseries type",
        "typeName": "Reading",
        "created": False,
    }


def test_insert_forms_and_read_back(loaded):
    assert rows(loaded, "SELECT count(*) AS n FROM Reading") == [{"n": 6}]
    got = rows(loaded, "SELECT FROM Reading WHERE sensor = 'a' ORDER BY ts")
    assert [(r["ts"], r["temp"]) for r in got] == [
        (utc(0), 20.0),
        (utc(1), 21.0),
        (utc(3), 22.0),
    ]


def test_a_text_timestamp_is_refused_on_insert(db):
    with pytest.raises(arcadedb.ArcadeDBError, match="Cannot convert type"):
        db.command(
            "sql",
            doc(
                "INSERT INTO Reading SET ts = '2026-01-01T00:02:00Z', sensor = 'b', temp = 31.0, hum = 51.0"
            ),
        )


def test_range_queries_take_numbers_or_text(loaded):
    by_number = rows(
        loaded,
        "SELECT FROM Reading WHERE ts BETWEEN ? AND ? AND sensor = 'a' ORDER BY ts",
        T0,
        T0 + 2 * MINUTE,
    )
    assert [r["ts"] for r in by_number] == [utc(0), utc(1)]
    by_text = rows(
        loaded,
        "SELECT FROM Reading WHERE ts >= '2026-01-01T00:01:00Z' AND ts < '2026-01-01T00:03:00Z' ORDER BY ts, sensor",
    )
    assert [(r["ts"], r["sensor"]) for r in by_text] == [
        (utc(1), "a"),
        (utc(1), "b"),
        (utc(2), "b"),
    ]


def test_time_bucket_group_by(loaded):
    got = rows(
        loaded,
        "SELECT ts.timeBucket('2m', ts) AS slot, sensor, avg(temp) AS t, max(temp) AS peak, count(*) AS n FROM Reading GROUP BY slot, sensor ORDER BY slot, sensor",
    )
    assert [(r["slot"], r["sensor"], r["t"], r["peak"], r["n"]) for r in got] == [
        (utc(0), "a", 20.5, 21.0, 2),
        (utc(0), "b", 30.0, 30.0, 1),
        (utc(2), "a", 22.0, 22.0, 1),
        (utc(2), "b", 31.5, 32.0, 2),
    ]


def test_time_bucket_with_a_timezone(loaded):
    got = rows(
        loaded,
        "SELECT ts.timeBucket('1d', ts, {timezone: '+08:00'}) AS day, count(*) AS n FROM Reading GROUP BY day",
    )
    # local midnight in UTC+8 is 16:00 UTC the day before
    assert got == [{"day": datetime(2025, 12, 31, 16, 0), "n": 6}]


def test_first_last_delta_rate_percentile(loaded):
    got = rows(
        loaded,
        "SELECT sensor, ts.first(temp, ts) AS first, ts.last(temp, ts) AS last, ts.delta(temp, ts) AS delta, ts.rate(temp, ts) AS per_second FROM Reading GROUP BY sensor ORDER BY sensor",
    )
    a, b = got
    assert (a["sensor"], a["first"], a["last"], a["delta"]) == ("a", 20.0, 22.0, 2.0)
    assert a["per_second"] == pytest.approx(2.0 / 180)
    assert (b["sensor"], b["first"], b["last"], b["delta"]) == ("b", 30.0, 32.0, 2.0)
    assert b["per_second"] == pytest.approx(2.0 / 120)
    median = rows(
        loaded,
        "SELECT sensor, ts.percentile(temp, 0.5) AS median FROM Reading GROUP BY sensor ORDER BY sensor",
    )
    assert median == [
        {"sensor": "a", "median": 21.0},
        {"sensor": "b", "median": 31.0},
    ]


def test_window_functions_return_one_array(loaded):
    got = rows(
        loaded,
        "SELECT ts.movingAvg(temp, 2) AS ma FROM Reading WHERE sensor = 'a' ORDER BY ts",
    )
    assert len(got) == 1
    assert list(got[0]["ma"]) == [20.0, 20.5, 21.5]


def test_append_samples_then_compact(db):
    n = 1_000
    executor = db.async_executor()
    executor.append_samples(
        "Reading",
        T0 + np.arange(n, dtype=np.int64) * 1_000,
        [f"s{i % 2}" for i in range(n)],
        np.arange(n, dtype=np.float64),
        np.full(n, 50.0),
    )
    executor.wait_completion()
    assert rows(db, "SELECT count(*) AS n FROM Reading") == [{"n": n}]
    sealed = db.command("sql", doc("COMPACT TIMESERIES TYPE Reading")).first()
    assert sealed.get("typeName") == "Reading"
    assert sealed.get("mutableSamples") == 0
    per_tag = rows(
        db, "SELECT sensor, count(*) AS n FROM Reading GROUP BY sensor ORDER BY sensor"
    )
    assert per_tag == [{"sensor": "s0", "n": 500}, {"sensor": "s1", "n": 500}]


def test_result_to_arrow(loaded):
    result = loaded.query(
        "sql",
        doc(
            "SELECT ts.timeBucket('2m', ts) AS slot, avg(temp) AS t FROM Reading GROUP BY slot ORDER BY slot"
        ),
    )
    table = result.to_arrow()
    assert table.schema.field("slot").type == pa.timestamp("ms")
    assert table.num_rows == 2
    assert table.column("t").to_pylist() == [
        pytest.approx(71 / 3),
        pytest.approx(85 / 3),
    ]


def test_alter_downsampling_policy(db):
    dropped = db.command(
        "sql", doc("ALTER TIMESERIES TYPE Reading DROP DOWNSAMPLING POLICY")
    ).first()
    assert dropped.get("operation") == "drop downsampling policy"
    tiers = db.query("sql", "SELECT FROM schema:types WHERE name = 'Reading'").first()
    assert not tiers.get("downsamplingTiers")
    added = db.command(
        "sql",
        doc(
            "ALTER TIMESERIES TYPE Reading ADD DOWNSAMPLING POLICY AFTER 7 DAYS GRANULARITY 1 HOURS"
        ),
    ).first()
    assert added.get("operation") == "add downsampling policy"
    tiers = db.query("sql", "SELECT FROM schema:types WHERE name = 'Reading'").first()
    assert len(tiers.get("downsamplingTiers")) == 1


def test_continuous_aggregate(loaded):
    created = loaded.command(
        "sql",
        doc(
            "CREATE CONTINUOUS AGGREGATE hourly AS SELECT ts.timeBucket('1h', ts) AS hour, sensor, avg(temp) AS t FROM Reading GROUP BY hour, sensor"
        ),
    ).first()
    assert created.get("created") is True
    got = rows(loaded, "SELECT FROM hourly ORDER BY hour, sensor")
    assert [(r["hour"], r["sensor"], r["t"]) for r in got] == [
        (utc(0), "a", 21.0),
        (utc(0), "b", 31.0),
    ]
    # A new sample reaches the aggregate after a refresh.
    loaded.command(
        "sql",
        "INSERT INTO Reading SET ts = ?, sensor = 'a', temp = 24.0, hum = 40.0",
        T0 + 4 * MINUTE,
    )
    loaded.command("sql", doc("REFRESH CONTINUOUS AGGREGATE hourly"))
    got = rows(loaded, "SELECT FROM hourly ORDER BY hour, sensor")
    assert got[0]["t"] == pytest.approx(21.75)

    # The type cannot be dropped while the aggregate reads it.
    with pytest.raises(arcadedb.ArcadeDBError, match="continuous aggregate"):
        loaded.command("sql", doc("DROP TIMESERIES TYPE Reading"))
    loaded.command("sql", doc("DROP CONTINUOUS AGGREGATE hourly"))
    loaded.command("sql", "DROP TIMESERIES TYPE Reading")


def test_bucket_is_a_reserved_alias(loaded):
    with pytest.raises(arcadedb.ArcadeDBError):
        loaded.query(
            "sql",
            doc(
                "SELECT ts.timeBucket('2m', ts) AS bucket, count(*) AS n FROM Reading GROUP BY bucket"
            ),
        ).to_list()
