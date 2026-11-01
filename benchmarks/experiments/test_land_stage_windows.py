"""land_stage.py never lands rows timed inside a known-bad window (excluded_windows.json, #557).

Run with `python -m pytest test_land_stage_windows.py -q` from this directory.

The bench host's results file is append-only: a stage re-run adds new rows next to the old ones. A window drops the old rows at landing,
by their ts_utc, start inclusive and end exclusive.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage as L  # noqa: E402


def _windows(tmp_path, windows):
    p = tmp_path / "excluded_windows.json"
    p.write_text(json.dumps({"windows": windows}))
    return L.load_windows(p)


W = [{"from": "2026-10-31T16:33:00+00:00", "to": "2026-11-01T05:25:00+00:00", "reason": "turbo on"}]


@pytest.mark.parametrize(
    "ts, excluded",
    [
        ("2026-10-31T16:33:00+00:00", True),  # the start is inclusive
        ("2026-10-31T17:23:41.512+00:00", True),  # microseconds
        ("2026-11-01T03:01:00Z", True),  # 'Z'
        ("2026-11-01T05:25:00+00:00", False),  # the end is exclusive
        ("2026-10-31T16:32:59+00:00", False),
        ("2026-11-01T14:26:21+09:00", False),  # 05:26:21Z, after the window, in another offset
    ],
)
def test_a_row_is_excluded_only_inside_the_window(tmp_path, ts, excluded):
    assert bool(L.excluded_by_window({"ts_utc": ts}, _windows(tmp_path, W))) is excluded


def test_a_row_without_a_readable_timestamp_is_never_excluded(tmp_path):
    w = _windows(tmp_path, W)
    assert L.excluded_by_window({}, w) is None
    assert L.excluded_by_window({"ts_utc": "not a time"}, w) is None


def test_no_file_means_no_windows(tmp_path):
    assert L.load_windows(tmp_path / "missing.json") == []


@pytest.mark.parametrize(
    "bad",
    [
        {"from": "2026-11-01T05:25:00+00:00", "to": "2026-10-31T16:33:00+00:00"},  # reversed
        {"from": "2026-10-31T16:33:00", "to": "2026-11-01T05:25:00"},  # no timezone
        {"from": "yesterday", "to": "2026-11-01T05:25:00+00:00"},
    ],
)
def test_a_malformed_window_ends_the_run(tmp_path, bad):
    with pytest.raises(SystemExit):
        _windows(tmp_path, [bad])


def test_the_committed_window_drops_qc14_and_keeps_its_neighbours():
    # ts_utc values of real rows: qC13's last documents row, qC14's first and last dense rows, qC15's first row after the relaunch
    w = L.load_windows()
    assert w, "excluded_windows.json holds no window"
    assert L.excluded_by_window({"ts_utc": "2026-10-31T15:08:26+00:00"}, w) is None
    assert L.excluded_by_window({"ts_utc": "2026-10-31T17:23:02+00:00"}, w)
    assert L.excluded_by_window({"ts_utc": "2026-11-01T03:01:44+00:00"}, w)
    assert L.excluded_by_window({"ts_utc": "2026-11-01T05:26:21+00:00"}, w) is None
