"""An index defined before the first row does not read as a free index (humemai/arcadedb-embedded-python#396).

The adapters time the index DDL, which on an empty type is a few hundredths of a second, so `index s` beside a load of tens of
seconds read as "this engine builds its index for nothing". The page now says which arms define their index before the load:
the arms whose rows carry `index_before_load`, and the arms export_web lists because their adapters do not set the flag. Run
with `python -m pytest test_index_before_load_note.py -q` from this directory.
"""
import os

import pytest


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


def entry(key, name, index=0.04, **extra):
    e = {"backend_key": key, "backend": name, "metrics": {"index s": {"median": index}, "ingest s": {"median": 27.0}}}
    e.update(extra)
    return e


def table(tid, *entries, columns=("ingest s", "index s")):
    return {"id": tid, "columns": list(columns), "entries": list(entries)}


@pytest.fixture
def rows(EW, monkeypatch):
    def put(rs):
        monkeypatch.setattr(EW, "_FROZEN_ROWS", rs)
    return put


def test_arcadedb_document_time_series_is_declared_though_its_rows_carry_no_flag(EW, rows):
    rows([{"lane": "l4", "backend": "arcadedb_ts_doc", "index_s": "0.04", "index_before_load": "False"}])
    [note] = EW._index_before_load_notes(table(
        "l4", entry("arcadedb_ts_doc", "ArcadeDB (embedded, document path)"), entry("duckdb", "DuckDB", index=3.3)))
    assert note.startswith("ArcadeDB (embedded, document path) defines its index before the first row is loaded")
    assert "DuckDB" not in note and "inside ingest s" in note


def test_the_rule_is_the_same_for_every_engine(EW, rows):
    """SurrealDB's rows carry the flag; ArangoDB's time-series arm and SurrealDB's embedded cross-model arm do not and are listed."""
    rows([{"lane": "l4", "backend": "surrealdb_ts", "index_before_load": True},
          {"lane": "l4", "backend": "surrealdb_ts_server", "index_before_load": "True"}])
    [note] = EW._index_before_load_notes(table(
        "l4", entry("surrealdb_ts", "SurrealDB (embedded)"), entry("arangodb_ts", "ArangoDB"),
        entry("arcadedb_ts_doc_server", "ArcadeDB (served, document path)"), entry("sqlite", "SQLite", index=12.6)))
    for name in ("SurrealDB (embedded)", "ArangoDB", "ArcadeDB (served, document path)"):
        assert name in note
    assert "SQLite" not in note and " define their index " in note
    rows([])
    [e2] = EW._index_before_load_notes(table("e2", entry("surrealdb_e2", "SurrealDB (embedded)"), entry("mongodb_e2", "MongoDB", index=1.2)))
    assert "SurrealDB (embedded) defines its index" in e2 and "MongoDB" not in e2


def test_an_arm_with_a_real_index_after_the_load_is_not_named(EW, rows):
    """ArcadeDB's cross-model arm defines Product(pid) first but builds the vector index after the load: its index s is real."""
    rows([{"lane": "e2", "backend": "arcadedb_e2", "index_before_load": "False"}])
    assert EW._index_before_load_notes(table("e2", entry("arcadedb_e2", "ArcadeDB", index=46.0))) == []


def test_a_withdrawn_or_blank_cell_and_a_table_without_the_column_say_nothing(EW, rows):
    rows([])
    assert EW._index_before_load_notes(table("l4", entry("arcadedb_ts_doc", "ArcadeDB", outcome="withdrawn"))) == []
    blank = entry("arcadedb_ts_doc", "ArcadeDB")
    blank["metrics"] = {"ingest s": {"median": 27.0}}
    assert EW._index_before_load_notes(table("l4", blank)) == []
    assert EW._index_before_load_notes(table("l4", entry("arcadedb_ts_doc", "ArcadeDB"), columns=("ingest s",))) == []
    assert EW._index_before_load_notes({"id": "nowhere", "columns": ["index s"], "entries": [entry("arcadedb_ts_doc", "ArcadeDB")]}) == []


def test_the_two_global_declarations_are_on_the_page(EW):
    text = " ".join(EW._R("GLOBAL", k) for k in ("index_order", "jvm_heap"))
    assert "advise creating indexes after a bulk load" in text and "initial heap pinned to the maximum heap" in text
    assert not any(ch.isdigit() for ch in text) and "—" not in text
