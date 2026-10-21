"""The Graph Analytical View must list `Message` from 26.11.1 (humemai/arcadedb-embedded-python#396).

Run with `python -m pytest test_gav_supertype_note.py -q` from this directory.

`l2_graph.py _gav_types()` lists Post and Comment and leaves their abstract supertype out where listing it returns a wrong count
for one LSQB query. From 26.11.1 it must be listed, so the export refuses a 26.11.1-or-later row whose view still lacks it: the
26.11.1 measurement cannot be published with the old list. Rows of an older release are not this check's concern.
"""
import pytest

NARROW = "vertex: Person, Country, City, Forum, Post, Comment, Tag, TagClass; edge: KNOWS, CONTAINER_OF"
WIDE = "vertex: Person, Message, Country, City, Forum, Post, Comment, Tag, TagClass; edge: KNOWS, CONTAINER_OF"


@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    import export_web
    return export_web


def row(version, types, **extra):
    r = {"lane": "l2", "workload": "olap", "instrument": "2026-11", "backend": "arcadedb_embedded", "gav": "True",
         "engine_version": version, "gav_types": types}
    r.update(extra)
    return r


def test_a_26_11_1_row_with_the_stale_list_is_refused(EW):
    with pytest.raises(SystemExit, match="Message supertype"):
        EW._refuse_gav_without_supertype([row("26.11.1", NARROW)])
    with pytest.raises(SystemExit, match="Message supertype"):
        EW._refuse_gav_without_supertype([row("26.11.1-SNAPSHOT (build abc/1790000000000/main)", NARROW)])


def test_a_26_11_1_row_with_the_supertype_passes(EW):
    EW._refuse_gav_without_supertype([row("26.11.1", WIDE)])


def test_only_with_view_graph_analytics_rows_with_a_message_half_are_concerned(EW):
    EW._refuse_gav_without_supertype([row("26.11.1", NARROW, gav="False")])                       # the no-view arm
    EW._refuse_gav_without_supertype([row("26.11.1", "vertex: Person; edge: KNOWS")])             # a tier with no message half
    EW._refuse_gav_without_supertype([row("26.11.1", NARROW, workload="oltp")])                   # the interactive workload
    EW._refuse_gav_without_supertype([row("26.11.1", NARROW, backend="neo4j_graph")])             # not ArcadeDB
    EW._refuse_gav_without_supertype([row("26.10.2", NARROW)])                                    # an older release
