"""`pass2_roster.py` (DECISIONS #164 item 5): which arms of a pin's rows have reps 1 to 3 clean, so pass 2 never repeats a
censored arm at its cap.

Run with `python -m pytest test_pass2_roster.py -q -rs` from this directory.

The rows are tiny and synthetic: every field the roster reads is set by the helper, so each test names the one thing it
changes (a timeout, an OOM kill, a second arm, a repair rerun) and a failure points at that rule.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pass2_roster as R  # noqa: E402

T0 = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def row(be="arcadedb_graph_embedded", rep=1, minute=0, lane="l2", scale="sf1", wl="oltp", **kw):
    r = {"lane": lane, "backend": be, "workload": wl, "scale": scale, "rep": rep, "rc": 0, "tier": "paper",
         "cpuset": "0-11", "durability_class": "relaxed", "engine_commit": "d36b4ca3a", "engine_version": "26.10.1",
         "ts_utc": (T0 + timedelta(minutes=minute)).isoformat()}
    r.update(kw)
    return r


def reps(be, upto=3, start=0, step=6, **kw):
    return [row(be=be, rep=i, minute=start + (i - 1) * step, **kw) for i in range(1, upto + 1)]


def eligible(roster, lane="l2"):
    return {(be, c["scale"], c["workload"], c["durability_class"], c["arm"]): c["clean_reps"]
            for be, cells in roster["lanes"].get(lane, {}).items() for c in cells}


def inel(roster, lane="l2"):
    return {(be, c["scale"], c["workload"], c["durability_class"], c["arm"]): c
            for be, cells in roster["ineligible"].get(lane, {}).items() for c in cells}


def test_an_arm_with_reps_one_to_three_clean_is_on_the_roster():
    r = R.build_roster(reps("a_graph"))
    assert eligible(r) == {("a_graph", "sf1", "oltp", "relaxed", ""): [1, 2, 3]}
    assert r["ineligible"] == {} and r["need_reps"] == [1, 2, 3] and r["format"] == R.FORMAT


def test_a_cell_that_hit_its_cap_is_never_retried_and_says_why():
    rows = reps("a_graph") + [row(be="slow", rep=1, rc=-1, error="timeout_after_7200s", minute=30)]
    r = R.build_roster(rows)
    assert ("slow", "sf1", "oltp", "relaxed", "") not in eligible(r)
    rec = inel(r)[("slow", "sf1", "oltp", "relaxed", "")]
    assert rec["clean_reps"] == [] and rec["last_error"] == "timeout_after_7200s" and rec["reps_seen"] == [1]


def test_every_one_of_reps_one_to_three_must_be_clean_not_any_three():
    rows = [row(rep=1), row(rep=3, minute=6), row(rep=4, minute=12)]
    r = R.build_roster(rows)
    assert inel(r)[("arcadedb_graph_embedded", "sf1", "oltp", "relaxed", "")]["clean_reps"] == [1, 3, 4]
    assert eligible(r) == {}


def test_a_failed_rep_two_leaves_the_arm_off_the_roster():
    rows = [row(rep=1), row(rep=2, minute=6, rc=1, error="boom"), row(rep=3, minute=12)]
    assert eligible(R.build_roster(rows)) == {}


def test_oom_kills_and_errors_and_sweep_cpusets_and_other_tiers_are_not_clean():
    base = row()
    assert R.is_clean(base)
    assert not R.is_clean(dict(base, rc=137))
    assert not R.is_clean(dict(base, rc=None))
    assert not R.is_clean(dict(base, error="x"))
    assert not R.is_clean(dict(base, oom_killed=True))
    assert not R.is_clean(dict(base, server_oom_killed=True))
    assert not R.is_clean(dict(base, cpuset="0-5"))
    assert R.is_clean(dict(base, cpuset=None))
    assert not R.is_clean(dict(base, tier="sweep"))
    assert not R.is_clean(dict(base, rep=None))
    assert not R.is_clean(dict(base, rep=True))


def test_a_row_that_finished_with_censored_queries_is_clean():
    # the cell left a row inside its cap; the table prints its censoring, so the repetition is wanted
    assert R.is_clean(row(triangles_censored=True, lsqb_q2_censored=True))


def test_the_class_and_the_arm_are_part_of_the_cell():
    rows = (reps("a_graph") + reps("a_graph", durability_class="strict", start=60)
            + reps("a_graph", backend_arm="nogav", start=120, lane="l2", scale="sf1full", wl="olap"))
    r = R.build_roster(rows)
    got = eligible(r)
    assert ("a_graph", "sf1", "oltp", "relaxed", "") in got and ("a_graph", "sf1", "oltp", "strict", "") in got
    assert ("a_graph", "sf1full", "olap", "relaxed", "nogav") in got and len(got) == 3


def test_one_class_failing_does_not_take_the_other_off_the_roster():
    rows = reps("a_graph") + [row(be="a_graph", rep=1, minute=60, rc=1, error="e", durability_class="strict")]
    r = R.build_roster(rows)
    assert ("a_graph", "sf1", "oltp", "relaxed", "") in eligible(r)
    assert ("a_graph", "sf1", "oltp", "strict", "") in inel(r)


def test_finished_top_up_reps_are_recorded_so_a_regeneration_does_not_repeat_them():
    r = R.build_roster(reps("a_graph", upto=4))
    assert eligible(r)[("a_graph", "sf1", "oltp", "relaxed", "")] == [1, 2, 3, 4]


def test_a_repair_rerun_after_a_failure_counts_when_it_left_a_clean_row():
    rows = ([row(rep=1, rc=1, error="HTTP body limit"), row(rep=1, minute=40)]
            + [row(rep=2, minute=46), row(rep=3, minute=52)])
    assert eligible(R.build_roster(rows)) == {("arcadedb_graph_embedded", "sf1", "oltp", "relaxed", ""): [1, 2, 3]}


def test_the_minimum_is_a_parameter():
    rows = reps("a_graph", upto=2)
    assert eligible(R.build_roster(rows)) == {}
    assert eligible(R.build_roster(rows, need=(1, 2))) == {("a_graph", "sf1", "oltp", "relaxed", ""): [1, 2]}


def test_every_cell_of_the_file_is_accounted_for_exactly_once():
    rows = reps("a") + reps("b", upto=2, start=100) + [row(be="c", rc=-1, error="timeout_after_7200s", minute=200)]
    r = R.build_roster(rows)
    n = sum(len(c) for d in r["lanes"].values() for c in d.values()) + sum(len(c) for d in r["ineligible"].values() for c in d.values())
    assert n == len({R.cell_key(x) for x in rows}) == 3


def test_the_wall_time_per_repetition_is_the_gap_to_the_next_cell_over_the_reps():
    # 6-minute reps, then the next cell starts 18 minutes after the first: three reps at 360 s
    rows = reps("a") + reps("b", start=18)
    r = R.build_roster(rows)
    a = eligible_cells(r)["a"]
    assert a["wall_s_per_rep"] == 360.0 and a["wall_obs"] == 1
    assert eligible_cells(r)["b"]["wall_s_per_rep"] is None, "the last cell has no next row to end it"


def eligible_cells(roster, lane="l2"):
    return {be: cells[0] for be, cells in roster["lanes"][lane].items()}


def test_a_gap_longer_than_a_cell_can_last_is_not_counted():
    rows = reps("a") + reps("b", start=18 + 24 * 60)   # a day of nothing between the cells
    r = R.build_roster(rows, caps={"sf1": 7200})
    assert eligible_cells(r)["a"]["wall_s_per_rep"] is None


def test_two_runs_of_one_cell_give_the_median_of_their_per_rep_times():
    rows = reps("a") + reps("x", start=18) + reps("a", start=36, step=3) + reps("y", start=45)
    w = R.wall_per_rep(rows)
    key = ("l2", "sf1", "oltp", "a", "relaxed", "")
    assert w[key] == (270.0, 2)    # (360 s and 180 s per rep)


def test_closeness_counts_the_ratios_inside_the_band_per_comparator():
    rows = []
    for be, ms in (("arcadedb_graph_embedded", 10.0), ("close_engine", 9.0), ("far_engine", 100.0)):
        rows += reps(be, point_p50_ms=ms, hop1_p50_ms=ms * 2, warm_point_p50_ms=1.0)
    c = R.build_roster(rows)["closeness"]["l2|sf1|oltp"]
    assert c["close_engine"]["comparisons"] == 2 and c["close_engine"]["within_band"] == 2
    assert c["far_engine"]["comparisons"] == 2 and c["far_engine"]["within_band"] == 0
    assert c["close_engine"]["closest"]["ratio"] == 1.111 and c["close_engine"]["closest"]["arcadedb"] == "arcadedb_graph_embedded"
    assert "warm_point_p50_ms" not in {x["closest"]["metric"] for x in c.values()}


def test_closeness_leaves_the_no_view_arm_and_the_sensitivity_arm_out():
    rows = (reps("arcadedb_graph_embedded", point_p50_ms=10.0) + reps("arcadedb_imgdefaults_server", point_p50_ms=10.0)
            + reps("arcadedb_graph_embedded", point_p50_ms=10.0, backend_arm="nogav", start=100)
            + reps("other", point_p50_ms=10.0, start=200))
    c = R.build_roster(rows)["closeness"]["l2|sf1|oltp"]
    assert c["other"]["comparisons"] == 1


def test_a_lane_with_no_comparator_has_no_closeness_entry():
    assert R.build_roster(reps("arcadedb_graph_embedded", point_p50_ms=10.0))["closeness"] == {}


def test_load_rows_counts_a_line_that_does_not_parse(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps(row()) + "\n\n{not json\n" + json.dumps(row(rep=2)) + "\n")
    rows, bad = R.load_rows(str(p))
    assert len(rows) == 2 and bad == 1


def test_the_command_line_writes_the_roster_and_summarises_it(tmp_path):
    src = tmp_path / "runs_page_x.jsonl"
    src.write_text("".join(json.dumps(x) + "\n" for x in reps("a_graph") + [row(be="slow", rc=-1, error="timeout_after_7200s")]))
    out = tmp_path / "roster.json"
    r = subprocess.run([sys.executable, str(HERE / "pass2_roster.py"), str(src), "-o", str(out), "--summary"],
                       cwd=HERE, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text())
    assert doc["source"] == "runs_page_x.jsonl" and doc["n_rows"] == 4
    assert "eligible" in r.stdout and "not topped up: slow sf1/oltp/relaxed" in r.stdout and "timeout_after_7200s" in r.stdout


def test_an_empty_file_is_refused(tmp_path):
    src = tmp_path / "empty.jsonl"
    src.write_text("")
    r = subprocess.run([sys.executable, str(HERE / "pass2_roster.py"), str(src)], cwd=HERE, capture_output=True, text=True)
    assert r.returncode != 0 and "holds no rows" in (r.stdout + r.stderr)
