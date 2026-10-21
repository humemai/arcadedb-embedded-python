"""The Graph Analytical View must not list `Message` on 26.10.x and must list it from 26.11.1 (humemai/arcadedb-embedded-python#396).

REMOVE WHEN: the 26.11.1 pass has landed with `Message` in `gav_types`. Run with `python -m pytest test_gav_supertype_note.py -q`
from this directory.

`l2_graph.py _gav_types()` lists Post and Comment and leaves their abstract supertype out, because listing it returns a wrong count for
one LSQB query on 26.10.x. From 26.11.1 it must be listed. The page declares the stale list while the rows are 26.10.x, and the
export refuses a 26.11.1-or-later row whose view still lacks it, so the 26.11.1 measurement cannot be published with the old list.
"""
import os

import pytest

NARROW = "vertex: Person, Country, City, Forum, Post, Comment, Tag, TagClass; edge: KNOWS, CONTAINER_OF"
WIDE = "vertex: Person, Message, Country, City, Forum, Post, Comment, Tag, TagClass; edge: KNOWS, CONTAINER_OF"


@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        try:
            import export_web
        except SystemExit as e:                      # the e4 artifacts are not in this checkout
            pytest.skip(f"export_web does not import here: {e}")
    finally:
        mp.undo()
    return export_web


@pytest.fixture(autouse=True)
def october(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)


def row(version, types, **extra):
    r = {"lane": "l2", "workload": "olap", "instrument": "2026-10", "backend": "arcadedb_embedded", "gav": "True",
         "engine_version": version, "gav_types": types}
    r.update(extra)
    return r


def test_the_stale_list_on_26_10_x_is_declared_in_one_sentence(EW):
    note = EW._gav_supertype_note("l2olap", [row("26.10.2", NARROW), row("server:26.10.1 (build d36b4ca3a)", NARROW)])
    assert note.startswith("ArcadeDB's Graph Analytical View covers the message types Post and Comment but not their Message supertype")
    assert "26.11.1" in note and note.count(". ") == 0


def test_only_the_graph_analytics_table_and_only_with_view_rows_with_a_message_half(EW):
    assert EW._gav_supertype_note("l2", [row("26.10.2", NARROW)]) is None
    assert EW._gav_supertype_note("l2olap", [row("26.10.2", NARROW, gav="False")]) is None
    assert EW._gav_supertype_note("l2olap", [row("26.10.2", "vertex: Person; edge: KNOWS")]) is None      # a tier with no message half
    assert EW._gav_supertype_note("l2olap", [row("26.10.2", "")]) is None                                 # narrow rows have their own sentence
    assert EW._gav_supertype_note("l2olap", [row("26.10.2", WIDE)]) is None


def test_a_26_11_1_row_with_the_stale_list_is_refused(EW):
    with pytest.raises(SystemExit, match="26.11.1 or later built the view without the Message supertype"):
        EW._gav_supertype_note("l2olap", [row("26.11.1", NARROW)])
    with pytest.raises(SystemExit):
        EW._gav_supertype_note("l2olap", [row("26.11.1-SNAPSHOT (build abc/1790000000000/main)", NARROW)])


def test_a_26_11_1_row_with_the_supertype_retires_the_sentence(EW):
    assert EW._gav_supertype_note("l2olap", [row("26.11.1", WIDE)]) is None
    assert EW._gav_supertype_note("l2olap", [row("26.11.1", WIDE), row("26.10.2", NARROW)]) is not None


def test_the_lane_still_lists_the_stale_set_so_the_declaration_is_true():
    """If _gav_types() already lists Message the declaration describes the old rows only, and this test says so."""
    import l2_graph as L
    a = object.__new__(L.ArcadeGraphEmbedded)
    a._load_messages = True
    v, _e = a._gav_types()
    assert "Message" not in v and {"Post", "Comment"} <= set(v)
