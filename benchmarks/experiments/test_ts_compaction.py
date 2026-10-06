"""ArcadeDB's TIMESERIES types declare COMPACTION_INTERVAL 1 HOURS, and the engine's answer is read back (CAMPAIGN section 7 row 54, DECISIONS #147).

Run with `python -m pytest test_ts_compaction.py -q -rs` from this directory.

The decision was conditional on upstream confirming the declaration (ArcadeData/arcadedb#9166): confirmed 2026-10-05, the
issue closed with PR #9246 (26.10.1). A type bulk-loaded once and then aggregated in hourly buckets declares the hourly
bucket, so compaction cuts sealed blocks at its boundaries and the 12-hour hourly average answers from block statistics.
Both native arms (embedded and served) run it; each row stamps `ts_compaction_interval_ms` as `schema:types` reports it
(`compactionBucketIntervalMs`), never the string the lane sent; the page sentence and its gates live in overrides.py.
The arms run against stand-ins that record the statement they are given.
"""
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import l4_tsbs as T  # noqa: E402
import overrides as OV  # noqa: E402


def test_the_declared_interval_is_the_hourly_buckets_and_matches_what_the_gate_expects():
    assert T.ArcadeNativeTS.COMPACTION_INTERVAL == "1 HOURS"
    assert OV.TS_COMPACTION_MS == 3_600_000


def test_the_embedded_arm_creates_its_type_with_the_interval(monkeypatch):
    seen = []

    class _Ex:
        def append_samples(self, *a, **k):
            pass

        def wait_completion(self):
            pass

    class _Db:
        def command(self, language, text):
            seen.append(text)

        def async_executor(self):
            return _Ex()
    monkeypatch.setitem(sys.modules, "numpy", __import__("numpy"))
    arm = object.__new__(T.ArcadeNativeTS)
    arm.db = _Db()
    arm.ingest([("host_0", 1_700_000_000, 1.0, 2.0, 3.0)])
    assert len(seen) == 1
    assert seen[0].startswith("CREATE TIMESERIES TYPE Point TIMESTAMP ts")
    assert seen[0].endswith(f"SHARDS {T.ArcadeNativeTS.SHARDS} COMPACTION_INTERVAL 1 HOURS")


def test_the_served_arm_creates_its_type_with_the_interval_over_http():
    posted = []

    class _Resp:
        def raise_for_status(self):
            pass

    arm = object.__new__(T.ArcadeNativeTSServer)
    arm.base = "http://server/api/v1"
    arm._post = lambda kind, command, language="sql", timeout=600: posted.append((kind, command)) or []
    arm.rq = types.SimpleNamespace(post=lambda url, data=None, headers=None, timeout=None: _Resp())
    arm.ingest([("host_0", 1_700_000_000, 1.0, 2.0, 3.0)])
    kind, command = posted[0]
    assert kind == "command" and command.startswith("CREATE TIMESERIES TYPE Point TIMESTAMP ts")
    assert command.endswith(f"SHARDS {T.ArcadeNativeTSServer.SHARDS} COMPACTION_INTERVAL 1 HOURS")


@pytest.mark.parametrize("rows,want", [
    ([{"name": "Point", "compactionBucketIntervalMs": 3_600_000}], 3_600_000),
    ([{"name": "Point", "compactionBucketIntervalMs": 0}], 0),                 # a type created without one
    ([{"name": "Point"}], None),                                               # the engine reports nothing: never "declared"
    ([], None),
    ([{"compactionBucketIntervalMs": "3600000"}], 3_600_000),                  # over HTTP
    ([{"compactionBucketIntervalMs": "n/a"}], None),
])
def test_the_interval_is_read_from_the_schema_report(rows, want):
    assert T._compaction_interval_ms(rows) == want


def test_the_row_stamp_is_the_engines_answer_and_a_failed_read_is_named():
    arm = object.__new__(T.ArcadeNativeTS)
    arm._type_report = lambda: [{"compactionBucketIntervalMs": 3_600_000}]
    assert arm.compaction_readback() == {"ts_compaction_interval": "1 HOURS", "ts_compaction_interval_ms": 3_600_000}

    arm._type_report = lambda: [{"name": "Point"}]
    got = arm.compaction_readback()
    assert "ts_compaction_interval_ms" not in got and "no compactionBucketIntervalMs" in got["ts_compaction_interval_readback_error"]

    def boom():
        raise RuntimeError("HTTP 500")
    arm._type_report = boom
    assert "HTTP 500" in arm.compaction_readback()["ts_compaction_interval_readback_error"]


def test_the_served_arm_reads_the_same_report_over_http():
    arm = object.__new__(T.ArcadeNativeTSServer)
    arm._post = lambda kind, command, **kw: [{"compactionBucketIntervalMs": 3_600_000}]
    assert arm.compaction_readback()["ts_compaction_interval_ms"] == 3_600_000


def test_the_lane_stamps_the_readback_after_the_settle_and_before_any_query():
    src = (HERE / "l4_tsbs.py").read_text()
    main = src[src.index("def main():"):]
    stamp = main.index("out.update(b.compaction_readback())")
    assert main.index("b.settle()") < stamp < main.index("corpus-release")


# ---- the October pin's rows ran without the declaration ----------------------------------------------------------

def _row(**kw):
    base = {"lane": "l4", "scale": "ts100", "workload": "ingest", "backend": "arcadedb_ts_native", "instrument": "2026-10",
            "ts_mutable_at_ingest_end": 0}
    base.update(kw)
    return base


def test_rows_of_the_pin_measured_before_the_declaration_are_not_asked_for_the_stamp():
    old = _row(engine_commit="417314c18da782620463bc7c09ac6bd34ac6fbda")
    new = _row(engine_commit="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    assert OV.stamp_findings([old]) == ([], 1)                     # only the unsealed-samples stamp is judged
    findings, judged = OV.stamp_findings([new])
    assert judged == 2 and [f["key"] for f in findings] == ["arcadedb_ts_compaction_interval"]


def test_no_sentence_about_the_interval_stands_under_a_table_built_from_rows_that_ran_without_it():
    old = _row(engine_commit="417314c18")
    new = _row(engine_commit="d36b4ca3a", ts_compaction_interval_ms=OV.TS_COMPACTION_MS)
    keys = ["arcadedb_ts_native"]
    said = lambda rows: [t for t, _v in OV.notes_for_table("l4", "l4", keys, rows) if "compaction interval" in t]
    assert said([old]) == []
    assert len(said([old, new])) == 1 and "one-hour" in said([old, new])[0]
    # and the page gate does not demand the sentence for a table that has none to say
    assert "arcadedb_ts_compaction_interval" not in [o.key for o in OV.applicable("l4", keys, [old])]
    assert "arcadedb_ts_compaction_interval" in [o.key for o in OV.applicable("l4", keys, [old, new])]
    assert "arcadedb_ts_compaction_interval" in [o.key for o in OV.applicable("l4", keys)]       # no rows given: owed
