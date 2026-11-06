"""The freeze halves the io figures of pre-fix rows from a host that stacks block devices (#555), and changes nothing else.

Run with `python -m pytest test_io_stat_correction.py -q` from this directory. What is held:

  * the field rule takes every io.stat-derived figure (io_*_mib, the _sum pair, the per-side and per-phase ones) and nothing else
    that merely looks like it (a memory or disk figure, a thread count);
  * a mini row before the cutoff is halved, a row at or after it is not, a row of another host is not, and while the cutoff is
    null every mini row predates the fix;
  * the input rows are never changed, so the tables built from them and runs.jsonl keep the raw values;
  * the freeze writes the halved values to runs_paper.csv and the raw ones to the sidecar report, and the committed fix file parses.
"""
import copy
import csv
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import io_stat_correction as C  # noqa: E402

CUT = "20261107T000000Z"
MINI = {"run_id": "r1", "bench_host": "mini", "lane": "l1", "backend": "arcadedb", "scale": "tiny", "rep": 1,
        "manifest": "20261101T000000Z", "ts_utc": "2026-11-01T10:25:13+00:00",
        "io_read_mib": 0.2, "io_write_mib": 16590.4, "io_read_mib_sum": 0.2, "io_write_mib_sum": 16590.4,
        "client_io_write_mib": 8.0, "server_io_read_mib": 1.0, "server_container_io_write_mib": 6.0,
        "sidecar_x_io_write_mib": 4.0, "io_load_write_mib": 100.0,
        "peak_mib_sum": 123.0, "disk_mb_sum": 50.0, "redis_io_threads": 4, "io_note": "text", "wall_s": 9.0}
FIX = {"hosts": ["mini"], "fixed_from_manifest": CUT, "fix_commits": []}


def test_field_rule():
    for k in ("io_read_mib", "io_write_mib", "io_read_mib_sum", "io_write_mib_sum", "client_io_read_mib", "server_io_write_mib",
              "server_container_io_write_mib", "sidecar_x_io_read_mib", "io_load_write_mib", "io_query_read_mib"):
        assert C.is_io_field(k), k
    for k in ("peak_mib_sum", "disk_mb_sum", "server_disk_rw_mb", "redis_io_threads", "io_note", "ingest_mib", "wall_s",
              "io_read_mib_extra"):
        assert not C.is_io_field(k), k


def test_mini_row_before_cutoff_is_halved_and_the_rest_is_untouched():
    before = copy.deepcopy(MINI)
    out, raw = C.correct_row(MINI, ("mini",), CUT)
    assert MINI == before, "the input row must not change"
    assert out["io_write_mib"] == 8295.2 and out["io_write_mib_sum"] == 8295.2 and out["io_read_mib"] == 0.1
    assert out["client_io_write_mib"] == 4.0 and out["server_container_io_write_mib"] == 3.0 and out["io_load_write_mib"] == 50.0
    assert raw["io_write_mib"] == 16590.4 and "peak_mib_sum" not in raw and len(raw) == 9
    assert {k: v for k, v in out.items() if not C.is_io_field(k)} == {k: v for k, v in MINI.items() if not C.is_io_field(k)}


def test_rows_not_corrected():
    assert C.correct_row(dict(MINI, manifest="20261107T000000Z"), ("mini",), CUT)[1] == {}     # at the cutoff: fixed
    assert C.correct_row(dict(MINI, manifest="20261201T000000Z"), ("mini",), CUT)[1] == {}
    assert C.correct_row(dict(MINI, bench_host="laptop"), ("mini",), CUT)[1] == {}
    assert C.correct_row({k: v for k, v in MINI.items() if k != "bench_host"}, ("mini",), CUT)[1] == {}
    # None, text and bool pass through unhalved
    odd = C.correct_row(dict(MINI, io_write_mib=None, io_read_mib="n/a", io_write_mib_sum=True), ("mini",), CUT)[1]
    assert odd.keys() == {"io_read_mib_sum", "client_io_write_mib", "server_io_read_mib", "server_container_io_write_mib",
                          "sidecar_x_io_write_mib", "io_load_write_mib"}


def test_cutoff_null_means_every_mini_row_predates_the_fix():
    assert C.correct_row(dict(MINI, manifest="20301231T000000Z"), ("mini",), None)[1]["io_write_mib"] == 16590.4


def test_row_without_a_stamp_predates_the_fix_and_ts_utc_is_the_fallback():
    bare = {k: v for k, v in MINI.items() if k not in ("manifest", "ts_utc")}
    assert C.correct_row(bare, ("mini",), CUT)[1]
    late = dict(bare, ts_utc="2026-11-08T00:00:00+00:00")
    assert not C.correct_row(late, ("mini",), CUT)[1]
    assert C.correct_row(dict(late, ts_utc="2026-11-06T23:59:59+00:00"), ("mini",), CUT)[1]
    assert C.correct_row(dict(bare, ts_utc="garbage"), ("mini",), CUT)[1]


def test_correct_rows_report_names_each_corrected_row_with_its_raw_values():
    rows = [MINI, dict(MINI, run_id="r2", manifest="20261108T000000Z"), dict(MINI, run_id="r3", bench_host="laptop")]
    out, report = C.correct_rows(rows, FIX)
    assert [r["run_id"] for r in out] == ["r1", "r2", "r3"]
    assert out[0]["io_write_mib"] == 8295.2 and out[1]["io_write_mib"] == 16590.4 and out[2]["io_write_mib"] == 16590.4
    assert report["rows_frozen"] == 3 and report["rows_corrected"] == 1
    assert report["corrected"][0]["run_id"] == "r1" and report["corrected"][0]["raw"]["io_write_mib"] == 16590.4
    json.dumps(report)


def test_malformed_cutoff_fails_loudly():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "fix.json"
        p.write_text(json.dumps({"hosts": ["mini"], "fixed_from_manifest": "yesterday"}))
        try:
            C.load_fix(p)
        except ValueError:
            return
    raise AssertionError("a malformed cutoff must raise")


def test_committed_fix_file_parses():
    fix = C.load_fix()
    assert fix["hosts"] == ["mini"] and "fixed_from_manifest" in fix


def test_freeze_writes_halved_rows_and_the_raw_values_to_the_sidecar():
    import make_paper_tables as M
    rows = [dict(MINI), dict(MINI, run_id="r2", rep=2, bench_host="laptop")]
    before = copy.deepcopy(rows)
    with tempfile.TemporaryDirectory() as d:
        saved = (M.RESULTS, M.GENERATED, C.load_fix)
        M.RESULTS, M.GENERATED, C.load_fix = d, str(Path(d) / "generated"), lambda: FIX   # not the committed cutoff, which moves
        try:
            M.freeze_paper_rows(rows)
        finally:
            M.RESULTS, M.GENERATED, C.load_fix = saved
        frozen = {r["run_id"]: r for r in csv.DictReader(open(Path(d) / "runs_paper.csv"))}
        report = json.load(open(Path(d) / "generated" / "io_stat_correction.json"))
    assert rows == before, "freeze_paper_rows must not change the rows the tables are built from"
    assert float(frozen["r1"]["io_write_mib"]) == 8295.2 and float(frozen["r2"]["io_write_mib"]) == 16590.4
    assert frozen["r1"]["peak_mib_sum"] == "123.0" and set(frozen["r1"]) == set(frozen["r2"])
    assert report["rows_corrected"] == 1 and report["corrected"][0]["raw"]["io_write_mib"] == 16590.4


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
