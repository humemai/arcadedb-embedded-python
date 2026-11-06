"""The freeze halves the io figures of pre-fix rows from a host that stacks block devices (#555), and changes nothing else.

Run with `python -m pytest test_io_stat_correction.py -q` from this directory. What is held:

  * the field rule takes every io.stat-derived figure (io_*_mib, the _sum pair, the per-side and per-phase ones) and nothing else
    that merely looks like it (a memory or disk figure, a thread count);
  * a mini row without the `io_stat_dedup` stamp predates the fix and is halved (and says "halved"), a mini row stamped 1 is never
    halved, a row of another host is not, and a stamp that is neither absent nor 1 raises;
  * the input rows are never changed, so the tables built from them and runs.jsonl keep the raw values;
  * the freeze writes the halved values to runs_paper.csv and the raw ones to the sidecar report, the committed fix file parses,
    and the stamp is declared in page_check.NOT_PRINTED and ignored by provenance_check's schema-homogeneity check.
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

MINI = {"run_id": "r1", "bench_host": "mini", "lane": "l1", "backend": "arcadedb", "scale": "tiny", "rep": 1,
        "io_read_mib": 0.2, "io_write_mib": 16590.4, "io_read_mib_sum": 0.2, "io_write_mib_sum": 16590.4,
        "client_io_write_mib": 8.0, "server_io_read_mib": 1.0, "server_container_io_write_mib": 6.0,
        "sidecar_x_io_write_mib": 4.0, "io_load_write_mib": 100.0,
        "peak_mib_sum": 123.0, "disk_mb_sum": 50.0, "redis_io_threads": 4, "io_note": "text", "wall_s": 9.0}
STAMPED = dict(MINI, run_id="r2", io_stat_dedup=1)
FIX = {"hosts": ["mini"]}


def test_field_rule():
    for k in ("io_read_mib", "io_write_mib", "io_read_mib_sum", "io_write_mib_sum", "client_io_read_mib", "server_io_write_mib",
              "server_container_io_write_mib", "sidecar_x_io_read_mib", "io_load_write_mib", "io_query_read_mib"):
        assert C.is_io_field(k), k
    for k in ("peak_mib_sum", "disk_mb_sum", "server_disk_rw_mb", "redis_io_threads", "io_note", "ingest_mib", "wall_s",
              "io_read_mib_extra", "io_stat_dedup"):
        assert not C.is_io_field(k), k


def test_unstamped_mini_row_is_halved_and_the_rest_is_untouched():
    before = copy.deepcopy(MINI)
    out, raw = C.correct_row(MINI, ("mini",))
    assert MINI == before, "the input row must not change"
    assert out["io_write_mib"] == 8295.2 and out["io_write_mib_sum"] == 8295.2 and out["io_read_mib"] == 0.1
    assert out["client_io_write_mib"] == 4.0 and out["server_container_io_write_mib"] == 3.0 and out["io_load_write_mib"] == 50.0
    assert raw["io_write_mib"] == 16590.4 and "peak_mib_sum" not in raw and len(raw) == 9
    assert out["io_stat_dedup"] == "halved"
    assert {k: v for k, v in out.items() if not C.is_io_field(k) and k != "io_stat_dedup"} == \
        {k: v for k, v in MINI.items() if not C.is_io_field(k)}
    assert C.correct_row(dict(MINI, io_stat_dedup=None), ("mini",))[1] and C.correct_row(dict(MINI, io_stat_dedup=""), ("mini",))[1]


def test_stamped_row_is_never_halved():
    out, raw = C.correct_row(STAMPED, ("mini",))
    assert raw == {} and out is STAMPED and out["io_write_mib"] == 16590.4 and out["io_stat_dedup"] == 1


def test_rows_not_corrected():
    assert C.correct_row(dict(MINI, bench_host="laptop"), ("mini",))[1] == {}
    assert C.correct_row({k: v for k, v in MINI.items() if k != "bench_host"}, ("mini",))[1] == {}
    assert C.correct_row(dict(MINI, bench_host="laptop", io_stat_dedup="junk"), ("mini",))[1] == {}   # not our host: not read
    # None, text and bool pass through unhalved
    odd = C.correct_row(dict(MINI, io_write_mib=None, io_read_mib="n/a", io_write_mib_sum=True), ("mini",))[1]
    assert odd.keys() == {"io_read_mib_sum", "client_io_write_mib", "server_io_read_mib", "server_container_io_write_mib",
                          "sidecar_x_io_write_mib", "io_load_write_mib"}
    assert C.correct_row(dict(MINI, io_read_mib=None, io_write_mib=None, io_read_mib_sum=None, io_write_mib_sum=None,
                              client_io_write_mib=None, server_io_read_mib=None, server_container_io_write_mib=None,
                              sidecar_x_io_write_mib=None, io_load_write_mib=None), ("mini",))[0]["bench_host"] == "mini"


def test_malformed_stamp_raises():
    for bad in (2, 0, "1", True, "halved", 1.5):
        try:
            C.correct_row(dict(MINI, io_stat_dedup=bad), ("mini",))
        except ValueError:
            continue
        raise AssertionError(f"stamp {bad!r} must raise")


def test_correct_rows_report_names_each_corrected_row_with_its_raw_values():
    rows = [MINI, STAMPED, dict(MINI, run_id="r3", bench_host="laptop")]
    out, report = C.correct_rows(rows, FIX)
    assert [r["run_id"] for r in out] == ["r1", "r2", "r3"]
    assert out[0]["io_write_mib"] == 8295.2 and out[1]["io_write_mib"] == 16590.4 and out[2]["io_write_mib"] == 16590.4
    assert report["rows_frozen"] == 3 and report["rows_corrected"] == 1 and report["rows_stamped_untouched"] == 1
    assert report["corrected"][0]["run_id"] == "r1" and report["corrected"][0]["raw"]["io_write_mib"] == 16590.4
    json.dumps(report)


def test_committed_fix_file_parses():
    assert C.load_fix()["hosts"] == ["mini"]


def test_the_stamp_is_declared_to_the_gates():
    import page_check
    assert page_check._not_printed_reason("io_stat_dedup")
    src = (HERE / "provenance_check.py").read_text()
    assert '"io_stat_dedup")' in src.split("IGNORE_PREFIX = (")[1].split("def measured")[0]


def test_freeze_writes_halved_rows_and_the_raw_values_to_the_sidecar():
    import make_paper_tables as M
    rows = [dict(MINI), dict(STAMPED, rep=2), dict(MINI, run_id="r3", rep=3, bench_host="laptop")]
    before = copy.deepcopy(rows)
    with tempfile.TemporaryDirectory() as d:
        saved = (M.RESULTS, M.GENERATED)
        M.RESULTS, M.GENERATED = d, str(Path(d) / "generated")
        try:
            M.freeze_paper_rows(rows)
        finally:
            M.RESULTS, M.GENERATED = saved
        frozen = {r["run_id"]: r for r in csv.DictReader(open(Path(d) / "runs_paper.csv"))}
        report = json.load(open(Path(d) / "generated" / "io_stat_correction.json"))
    assert rows == before, "freeze_paper_rows must not change the rows the tables are built from"
    assert float(frozen["r1"]["io_write_mib"]) == 8295.2 and frozen["r1"]["io_stat_dedup"] == "halved"
    assert float(frozen["r2"]["io_write_mib"]) == 16590.4 and frozen["r2"]["io_stat_dedup"] == "1"
    assert float(frozen["r3"]["io_write_mib"]) == 16590.4 and frozen["r3"]["io_stat_dedup"] == ""
    assert frozen["r1"]["peak_mib_sum"] == "123.0" and set(frozen["r1"]) == set(frozen["r2"])
    assert report["rows_corrected"] == 1 and report["corrected"][0]["raw"]["io_write_mib"] == 16590.4


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
