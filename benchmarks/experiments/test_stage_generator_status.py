"""`make_2611_stages.py --status-file`: a start marker that is already in the machine's STATUS.txt is refused.

Run with `python -m pytest test_stage_generator_status.py -q` from this directory.

2026-10-23: the drafts waited for `qMA06 ALL-DONE`. Mini's STATUS.txt already held that line (the study was skipped with
conf/skip-qMA06, and the skipped stage still writes its marker), so installed stages would have started at once, beside
the A/B jobs still running. The marker must be the LAST item of the queue. First choice was `jvcall-last ALL-DONE`; after the
queue was reordered (bindings-r2 and jvcall-last left mini) it is `mini-ab FINAL ALL-DONE`, the line a waiter writes after
native-scale, the last A/B item. The marker has a space: the wait and the lint must take it whole. The fixture is an excerpt of mini's STATUS.txt of that day.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_stage_generator_2611 import run, waits  # noqa: E402
import make_2611_stages as G  # noqa: E402

MINI_STATUS = HERE / "fixtures" / "mini_status_20261023.txt"
LAST_MARKER = "mini-ab FINAL"


def test_the_fixture_is_the_state_that_bit_us():
    assert G.marker_in_status("qMA06", str(MINI_STATUS))
    assert not G.marker_in_status(LAST_MARKER, str(MINI_STATUS))
    assert not G.marker_in_status("qMA0", str(MINI_STATUS))      # a prefix of a marker is not the marker


def test_a_marker_already_in_status_is_refused_and_nothing_is_written(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", "qMA06", "--status-file", str(MINI_STATUS), "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 1
    assert "qMA06 ALL-DONE` is already a line" in r.stdout and not list(out.glob("*.sh"))


def test_the_last_queue_item_is_accepted_and_the_first_stage_waits_on_it(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", LAST_MARKER, "--status-file", str(MINI_STATUS), "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    assert waits(out / "qS01.sh") == [LAST_MARKER]


def test_a_marker_needs_a_status_file_and_none_must_be_said(tmp_path):
    r = run(["--after", LAST_MARKER, "--lanes", "graph", "--out", str(tmp_path / "o")], tmp_path)
    assert r.returncode != 0 and "--status-file is required" in (r.stdout + r.stderr)
    r = run(["--after", "none", "--lanes", "graph", "--out", str(tmp_path / "o2")], tmp_path)    # no marker, no queue: no file needed
    assert r.returncode == 0, r.stdout[-400:]
    r = run(["--after", LAST_MARKER, "--status-file", str(tmp_path / "missing.txt"), "--lanes", "graph", "--out", str(tmp_path / "o3")], tmp_path)
    assert r.returncode == 1 and "no such file" in r.stdout


def test_a_marker_is_matched_as_a_whole_line_like_the_stage_wait(tmp_path):
    f = tmp_path / "STATUS.txt"
    f.write_text("[2026-10-23T06:02:49+00:00] qMA06 ALL-DONE (a log line, not the marker)\nxqMA06 ALL-DONE\nqMA06 ALL-DONE extra\n")
    assert not G.marker_in_status("qMA06", str(f))
    f.write_text("qMA06 ALL-DONE\n")
    assert G.marker_in_status("qMA06", str(f))


def test_check_drafts_refuses_drafts_whose_first_wait_is_already_true(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", "qMA06", "--status-file", "none", "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 0
    r = run(["--check", "--drafts", str(out), "--status-file", str(MINI_STATUS)], tmp_path)
    assert r.returncode == 1 and "qS01.sh: the start marker `qMA06 ALL-DONE` is already a line" in r.stdout
    good = tmp_path / "good"
    r = run(["--after", LAST_MARKER, "--status-file", str(MINI_STATUS), "--out", str(good)], tmp_path)
    assert r.returncode == 0
    r = run(["--check", "--drafts", str(good), "--status-file", str(MINI_STATUS)], tmp_path)
    assert r.returncode == 0, r.stdout[-400:]
    r = run(["--check", "--drafts", str(good)], tmp_path)         # without a file: the old lint only
    assert r.returncode == 0
