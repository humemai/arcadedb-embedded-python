"""The A/B table generator and its check: a number in the docs comes from a result file, never from a hand edit."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_ab_tables.py"


def _load():
    spec = importlib.util.spec_from_file_location("render_ab_tables", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load()

# Made-up numbers that only exercise the renderer. They are never written under docs/.
ROW = {
    "case": "100 rows, test shape",
    "metric": "total time",
    "unit": "s",
    "better": "lower",
    "a": "arm_a",
    "b": "arm_b",
    "a_median": 2.0,
    "b_median": 1.0,
    "ratio": 0.5,
    "ci_low": 0.4,
    "ci_high": 0.6,
    "clean_pairs": 12,
    "dropped_pairs": 1,
    "sign_b_better": 12,
    "sign_b_worse": 0,
    "sign_p": 0.000488,
}
RESULT = {
    "format": 1,
    "figure": "commit-size",
    "environment": {
        "engine_version": "1.2.3",
        "wheel_version": "1.2.4",
        "cores": "2 (pinned)",
        "machine": "test machine",
    },
    "comparisons": [ROW],
}


def _tree(tmp_path: Path, result: dict | None, doc: str):
    docs = tmp_path / "docs"
    results = docs / "benchmarks" / "ab-results"
    results.mkdir(parents=True)
    (docs / "page.md").write_text(doc, encoding="utf-8")
    if result is not None:
        (results / f"{result['figure']}.json").write_text(
            json.dumps(result), encoding="utf-8"
        )
    return docs, results


def _run(docs, results, flag="--check"):
    return mod.main([flag, "--docs", str(docs), "--results", str(results)])


EMPTY_BLOCK = "intro\n\n<!-- ab-table: commit-size -->\n<!-- /ab-table -->\n\ntail\n"


def test_the_docs_in_the_repository_match_their_result_files(capsys):
    assert mod.main(["--check"]) == 0, capsys.readouterr().out


def test_every_figure_has_a_block_in_the_docs():
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in mod.doc_files(mod.DEFAULT_DOCS)
    )
    for figure in mod.FIGURES:
        assert f"<!-- ab-table: {figure} -->" in text, figure


def test_a_figure_without_a_result_file_renders_the_pending_line(tmp_path, capsys):
    docs, results = _tree(tmp_path, None, EMPTY_BLOCK)
    assert _run(docs, results) == 1  # the empty block is not the rendered one yet
    assert _run(docs, results, "--write") == 0
    text = (docs / "page.md").read_text(encoding="utf-8")
    assert "Measurement pending" in text and "`commit-size`" in text
    assert _run(docs, results) == 0


def test_write_renders_the_table_and_check_passes(tmp_path):
    docs, results = _tree(tmp_path, RESULT, EMPTY_BLOCK)
    assert _run(docs, results, "--write") == 0
    text = (docs / "page.md").read_text(encoding="utf-8")
    assert text.startswith("intro\n\n<!-- ab-table: commit-size -->\n| Case |")
    assert text.endswith("<!-- /ab-table -->\n\ntail\n")
    assert "| 100 rows, test shape |" in text
    assert "0.500 (0.400 to 0.600)" in text
    assert "12 better, 0 worse, p = 0.000488" in text
    assert "B better by 40 to 60 percent" in text
    assert "12 (1 dropped)" in text
    assert "Engine 1.2.3, wheel 1.2.4, cores 2 (pinned), machine test machine." in text
    assert _run(docs, results) == 0


def test_a_hand_edited_number_fails_the_check(tmp_path, capsys):
    docs, results = _tree(tmp_path, RESULT, EMPTY_BLOCK)
    _run(docs, results, "--write")
    page = docs / "page.md"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "0.500 (0.400 to 0.600)", "0.400 (0.400 to 0.600)"
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert _run(docs, results) == 1
    assert "differs from the result file" in capsys.readouterr().out
    assert _run(docs, results, "--write") == 0
    assert _run(docs, results) == 0


def test_a_changed_result_file_fails_until_the_docs_are_rewritten(tmp_path):
    docs, results = _tree(tmp_path, RESULT, EMPTY_BLOCK)
    _run(docs, results, "--write")
    changed = copy.deepcopy(RESULT)
    changed["comparisons"][0]["b_median"] = 1.5
    (results / "commit-size.json").write_text(json.dumps(changed), encoding="utf-8")
    assert _run(docs, results) == 1
    assert _run(docs, results, "--write") == 0
    assert "| 2 | 1.5 |" in (docs / "page.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "ratio,lo,hi,pairs,expected",
    [
        (0.5, 0.4, 0.6, 12, "B better by 40 to 60 percent"),
        (1.5, 1.2, 1.8, 12, "B worse by 20 to 80 percent"),
        (1.0, 0.8, 1.2, 12, "no detectable difference"),
        (0.5, 0.4, 0.6, 6, "too few clean pairs (need 7)"),
        (None, None, None, 5, "too few clean pairs (need 7)"),
    ],
)
def test_the_verdict_is_derived_from_the_interval(ratio, lo, hi, pairs, expected):
    row = {**ROW, "ratio": ratio, "ci_low": lo, "ci_high": hi, "clean_pairs": pairs}
    row["sign_b_better"] = min(pairs, 3)
    assert mod.verdict(row) == expected


def test_rows_on_two_engines_get_an_engine_column(tmp_path):
    result = copy.deepcopy(RESULT)
    second = {**ROW, "case": "other", "environment": {"engine_version": "9.9.9"}}
    result["comparisons"].append(second)
    docs, results = _tree(tmp_path, result, EMPTY_BLOCK)
    assert _run(docs, results, "--write") == 0
    text = (docs / "page.md").read_text(encoding="utf-8")
    assert "| Case | Engine |" in text
    assert "engine 9.9.9, wheel 1.2.4" in text
    assert (
        "- Engine 1.2.3, wheel 1.2.4" in text and "- Engine 9.9.9, wheel 1.2.4" in text
    )


def test_one_figure_may_appear_on_two_pages(tmp_path):
    docs, results = _tree(tmp_path, RESULT, EMPTY_BLOCK)
    (docs / "second.md").write_text(EMPTY_BLOCK, encoding="utf-8")
    assert _run(docs, results, "--write") == 0
    assert (docs / "page.md").read_text() == (docs / "second.md").read_text()


def test_a_marker_inside_a_code_fence_is_an_example(tmp_path):
    doc = "```text\n<!-- ab-table: commit-size -->\nkept\n<!-- /ab-table -->\n```\n"
    docs, results = _tree(tmp_path, None, doc)
    assert _run(docs, results, "--write") == 0
    assert (docs / "page.md").read_text(encoding="utf-8") == doc


@pytest.mark.parametrize(
    "doc,message",
    [
        ("<!-- ab-table: nope -->\n<!-- /ab-table -->\n", "unknown figure id"),
        ("<!-- ab-table: commit-size -->\ntext\n", "not closed"),
        (
            "<!-- ab-table: commit-size -->\n<!-- ab-table: commit-size -->\n<!-- /ab-table -->\n",
            "not closed",
        ),
    ],
)
def test_bad_markers_fail_even_on_write(tmp_path, capsys, doc, message):
    docs, results = _tree(tmp_path, None, doc)
    assert _run(docs, results, "--write") == 1
    assert message in capsys.readouterr().out


def test_a_result_file_nobody_shows_fails(tmp_path, capsys):
    docs, results = _tree(tmp_path, RESULT, "no markers here\n")
    assert _run(docs, results) == 1
    assert "no doc carries" in capsys.readouterr().out


def _mutations():
    def drop(key):
        def go(r):
            del r["comparisons"][0][key]

        return go

    def put(key, value):
        def go(r):
            r["comparisons"][0][key] = value

        return go

    return [
        ("missing key", drop("clean_pairs"), "missing"),
        ("unknown key", put("verdict", "B better"), "unknown"),
        ("ratio outside interval", put("ratio", 0.9), "inside its interval"),
        ("partial interval", put("ci_low", None), "all numbers or all null"),
        ("bad direction", put("better", "faster"), "higher"),
        ("negative count", put("sign_b_worse", -1), "non-negative"),
        ("sign counts too large", put("sign_b_better", 99), "exceed"),
        (
            "interval missing with enough pairs",
            lambda r: r["comparisons"][0].update(ratio=None, ci_low=None, ci_high=None),
            "required",
        ),
        ("bad p", put("sign_p", 2), "sign_p"),
        ("bad environment override", put("environment", {"host": "x"}), "override"),
        ("bad format", lambda r: r.update(format=2), "format"),
        ("unknown figure", lambda r: r.update(figure="made-up"), "unknown figure"),
        (
            "environment missing a key",
            lambda r: r["environment"].pop("machine"),
            "environment",
        ),
        ("no rows", lambda r: r.update(comparisons=[]), "non-empty"),
    ]


@pytest.mark.parametrize(
    "mutate,message",
    [(m, msg) for _, m, msg in _mutations()],
    ids=[n for n, _, _ in _mutations()],
)
def test_invalid_result_files_are_rejected(tmp_path, capsys, mutate, message):
    bad = copy.deepcopy(RESULT)
    mutate(bad)
    docs = tmp_path / "docs"
    results = docs / "benchmarks" / "ab-results"
    results.mkdir(parents=True)
    (docs / "page.md").write_text(EMPTY_BLOCK, encoding="utf-8")
    (results / "commit-size.json").write_text(json.dumps(bad), encoding="utf-8")
    assert _run(docs, results) == 1
    assert message in capsys.readouterr().out


def test_file_name_must_match_the_figure(tmp_path, capsys):
    docs, results = _tree(tmp_path, None, EMPTY_BLOCK)
    (results / "other.json").write_text(json.dumps(RESULT), encoding="utf-8")
    assert _run(docs, results) == 1
    assert "file name must be commit-size.json" in capsys.readouterr().out


def test_a_pipe_in_a_cell_does_not_break_the_table(tmp_path):
    result = copy.deepcopy(RESULT)
    result["comparisons"][0]["case"] = "a|b"
    docs, results = _tree(tmp_path, result, EMPTY_BLOCK)
    assert _run(docs, results, "--write") == 0
    assert "| a\\|b |" in (docs / "page.md").read_text(encoding="utf-8")
