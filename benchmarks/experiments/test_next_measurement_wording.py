"""No promise on the benchmark page says "the next measurement" (CAMPAIGN section 7, "Switches and the 26.11.1 re-measure").

Run with `python -m pytest test_next_measurement_wording.py -q -rs` from this directory. Needs numpy (export_web imports it).

There is no one next measurement. The 26.10.2 and 26.11.1 measurements run ArcadeDB again with the method of the measurement the paper
reports, so only a newer release can move a row. A default-off switch or a method change goes on in a measurement after the paper,
where every engine it touches is measured again. A change that is already in the rows the page will carry has no promise at all.
So a sentence that promises a switch-gated change must say "a measurement after the paper", a sentence that promises a newer release
must name the release, and nothing may say "the next measurement".
"""
import ast
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# The page-level lines (export_web._next_item keys) and the kind of measurement each promises.
RELEASE_ONLY = {"release", "ts_doc_oom"}      # 26.10.2 / 26.11.1: a newer engine or bindings release only
SWITCH_GATED = {"dense_id_index"}             # CAMPAIGN section 7 row 84: default OFF, goes on after the paper


@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


def _strings(path):
    tree = ast.parse(Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


@pytest.mark.parametrize("name", ["export_web.py", "page_check.py"])
def test_no_string_promises_the_next_measurement(name):
    bad = [(n, t[:70]) for n, t in _strings(HERE / name) if re.search(r"next[ -]measurement", t, re.I)]
    assert not bad, f"{name} says 'next measurement': {bad}"


def test_every_filed_line_has_a_class():
    """A new `_next_item` key must be placed in one of the two classes here, or it is a promise nobody classified."""
    src = (HERE / "export_web.py").read_text()
    keys = set(re.findall(r'_next_item\(\s*"([a-z_0-9]+)"', src))
    assert keys == RELEASE_ONLY | SWITCH_GATED


def test_the_switch_gated_sentence_says_after_the_paper(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
    row = {"lane": "l3d", "instrument": "2026-10", "backend": "arcadedb_dense_embedded", "mutate_delete_per_op_ms": 1.5}
    s = EW._dense_id_index_note("l3d", [row])
    assert "A measurement after the paper" in s
    assert not re.search(r"next measurement|26\.1[01]\.\d measurement", s)


def test_the_switch_gated_list_line_says_after_the_paper(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "SKELETON", False)
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [{"backend": "arcadedb_embedded", "engine_version": "26.10.1"}])
    monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
    row = {"lane": "l3d", "instrument": "2026-10", "backend": "arcadedb_dense_embedded", "mutate_delete_per_op_ms": 1.5}
    s = EW._dense_id_index_note("l3d", [row])
    out = EW._next_measurement_note([{"id": "l3d", "title": "Dense vectors", "conditions": [s]}])
    [line] = [x for x in out if "index on the vector id" in x]
    assert "a measurement after the paper" in line
    assert not any(re.search(r"next measurement", x, re.I) for x in out)


def test_the_release_sentences_name_the_release(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "SKELETON", False)
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [{"backend": "arcadedb_embedded", "engine_version": "26.10.1"}])
    out = EW._next_measurement_note([])
    assert any(f"The {EW._PAPER_RELEASE} measurement runs ArcadeDB again" in x for x in out)
    assert any(f"The {EW._BINDINGS_FASTER_FROM} and {EW._PAPER_RELEASE} measurements run ArcadeDB on newer" in x for x in out)
    assert not any("after the paper" in x for x in out)      # no switch-gated change is filed, so none is promised
