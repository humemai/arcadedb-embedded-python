"""degenerate_check.py and the answer profile (CAMPAIGN section 7 row 59).

Run with `python -m pytest test_degenerate_check.py -q -rs` from this directory.

An agreed answer can still mean nothing: every LDBC age loaded as 0 and nine engines agreed on it (F146); the
triangle count is 0 on every engine because each friendship is stored once (F169). `record_result` now writes
`res_<q>_profile` and `degenerate_check` reads it. These tests hold that the profile is written and counts what
it says, that the report flags ZERO / CONSTANT / SCALE / EMPTY answers and leaves by-design constants alone, and
that its own self-test (October's three F146 answers must each be flagged) passes.
"""
import io
import json
import contextlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common as B  # noqa: E402
import degenerate_check as DC  # noqa: E402


def _run(tmp_path, rows, *extra):
    p = tmp_path / "rows.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    buf = io.StringIO()
    argv, sys.argv = sys.argv, ["degenerate_check.py", str(p), "--instrument", "t", *extra]
    try:
        with contextlib.redirect_stdout(buf):
            DC.main()
    finally:
        sys.argv = argv
    return buf.getvalue()


def _row(lane, workload, scale, name, rows, **kw):
    out = {"lane": lane, "workload": workload, "scale": scale, "instrument": "t"}
    B.record_result(out, name, rows, **kw)
    return out


def test_every_recorded_answer_carries_a_profile():
    out = {}
    B.record_result(out, "q", [(1, 2.5), (1, 0.0)], columns=("a", "b"))
    assert out["res_q_profile"] == {"a": {"distinct": 1, "zero_or_null": 0}, "b": {"distinct": 2, "zero_or_null": 1}}
    assert B.answer_profile([{"a": 0}, {"a": None}, {"a": 0.0}, {"a": 3}], columns=("a",)) == \
        {"a": {"distinct": 3, "zero_or_null": 3}}                    # zero, null and 0.0 are counted alike


def test_the_self_test_flags_the_three_f146_answers(capsys):
    assert DC.self_test() == 0
    assert "self-test ok" in capsys.readouterr().out


def test_a_constant_column_over_many_rows_is_flagged(tmp_path):
    rows = [{"name": f"p{i}", "age": 0} for i in range(40)]
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "point", rows, columns=("name", "age"))])
    assert "CONSTANT" in text and "column 'age' is 0 or null in all 40 rows" in text
    assert "column 'name'" not in text                              # key-like columns are not judged


def test_a_one_value_column_that_is_not_zero_is_flagged_too(tmp_path):
    rows = [{"name": f"p{i}", "city": "same"} for i in range(40)]
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "pointx", rows, columns=("name", "city"))])
    assert "column 'city' has one value over 40 rows" in text


def test_a_varying_answer_is_left_alone(tmp_path):
    rows = [{"name": f"p{i}", "age": i} for i in range(40)]
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "pointy", rows, columns=("name", "age"))])
    assert "0 flag(s)" in text


def test_a_by_design_constant_is_not_a_flag(tmp_path):
    rows = [{"okey": i, "pkey": i, "qty": 1, "paid": 0} for i in range(40)]
    text = _run(tmp_path, [_row("l1tpc", "oltp", "tpch1", "neworder", rows, columns=("okey", "pkey", "qty", "paid"))])
    assert "0 flag(s)" in text


def test_a_one_row_answer_of_zero_is_flagged(tmp_path):
    text = _run(tmp_path, [_row("l2", "olap", "sf1", "triangles", [{"n": 0}], columns=("n",))])
    assert "ZERO" in text and "l2/olap/sf1/triangles" in text


def test_an_empty_read_is_flagged(tmp_path):
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "hop9", [], columns=("n",))])
    assert "EMPTY" in text


def test_the_same_answer_at_two_scales_is_flagged(tmp_path):
    same = [{"n": 7}]
    text = _run(tmp_path, [_row("l2", "olap", "sf1", "cityx", same, columns=("n",)),
                           _row("l2", "olap", "sf10", "cityx", same, columns=("n",))])
    assert "SCALE" in text


def test_the_field_is_declared_to_the_page_gate():
    src = (HERE / "page_check.py").read_text()
    assert r'^res_\w+_profile$' in src


def test_a_frozen_csv_row_is_read_too(tmp_path):
    """The freeze writes the profile through csv, which stores a dict as its Python repr (single quotes)."""
    import csv
    rows = [{"name": f"p{i}", "age": 0} for i in range(40)]
    row = _row("l2", "oltp", "sf1", "point", rows, columns=("name", "age"))
    p = tmp_path / "frozen.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerow({k: v for k, v in row.items()})
    assert "'distinct'" in p.read_text()                           # a repr, not JSON
    buf = io.StringIO()
    argv, sys.argv = sys.argv, ["degenerate_check.py", str(p), "--instrument", "t"]
    try:
        with contextlib.redirect_stdout(buf):
            DC.main()
    finally:
        sys.argv = argv
    assert "column 'age' is 0 or null in all 40 rows" in buf.getvalue()


def test_the_edge_read_back_after_a_delete_is_empty_by_design_and_not_a_flag(tmp_path):
    """CAMPAIGN row 58: the graph lane reads the KNOWS edges into the written persons after the insert and again after the
    delete; the second answer is empty because the delete removed them, which is the point of reading it."""
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "graph_delete_edges", [], columns=("src", "dst"))])
    assert "0 flag(s)" in text and "EMPTY" not in text


def test_the_edge_read_back_after_an_insert_is_still_flagged_when_it_is_empty(tmp_path):
    """The allowance is for the delete only: an insert that left no edge behind is a defect the check must still name."""
    text = _run(tmp_path, [_row("l2", "oltp", "sf1", "graph_insert_edges", [], columns=("src", "dst"))])
    assert "EMPTY" in text
