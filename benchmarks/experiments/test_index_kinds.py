"""ArcadeDB's id index kinds, and the three places that state them (CAMPAIGN section 7 row 68).

Run with `python -m pytest test_index_kinds.py -q -rs` from this directory. Needs
numpy for the sentence tests (export_web imports the lanes); without it those
tests are skipped and say so under -rs.

The rule (ArcadeData/arcadedb#9169): an id that a lane only reads, updates, and
deletes by equality gets `UNIQUE_HASH`; a key that is also ranged over or ordered
stays `UNIQUE`. Four places must agree, and each test names the drift it catches:

  * the `CREATE INDEX ON <type> (<property>) <kind>` text in each lane's source,
    which is what the engine is told;
  * `fairness_check.ARCADEDB_HASH_ID_INDEXES`, the registry the page sentence reads;
  * `fairness_check.INDEX_DECISIONS`, the declaration the F14 gate prints for the
    cross-model arms;
  * the sentence `export_web` prints under a table that shows an ArcadeDB arm.

The DDL is read from the source text, not from a running engine: the engine's own
answer (`SELECT FROM schema:indexes`) is the rehearsal's evidence, in the log of
the smoke, and this file is the check that keeps the text from moving back.
"""
import ast
import collections
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fairness_check as FC  # noqa: E402

DDL = re.compile(r"CREATE INDEX ON ([A-Za-z_{}]+) \((\w+)\) ([A-Z_]+)")

# lane -> the source file whose ArcadeDB arms (embedded and served) create the index
LANE_FILE = {"l1tpc": "l1_tpc.py", "l1": "l1_tabular.py", "e2": "e2_hybrid.py", "l2": "l2_graph.py"}

# EVERY ArcadeDB `CREATE INDEX ON` statement in those files, with how many arms
# state it (two: the embedded arm and the served arm), as the row words it. What
# stays `UNIQUE` or sorted is here too, so a later "finish the change" fails:
# Person(id) because the untimed person_scan ranges over it, l_shipdate because
# Q6 ranges over it, customer_id because the lane groups by it.
EXPECTED = {
    "l1_tpc.py": {("Part", "p_partkey", "UNIQUE_HASH"): 2,
                  ("OrderNew", "okey", "UNIQUE_HASH"): 2,
                  ("Crud", "ckey", "UNIQUE_HASH"): 2,
                  ("LineItem", "l_shipdate", "NOTUNIQUE"): 2},
    "l1_tabular.py": {("orders", "id", "UNIQUE_HASH"): 2,
                      ("orders", "customer_id", "NOTUNIQUE"): 2},
    "e2_hybrid.py": {("Product", "pid", "UNIQUE_HASH"): 2,
                     # the vector index: its own kind, not an id index
                     ("Product", "embedding", "LSM_VECTOR"): 2},
    # `{label}` is the message half's loop variable, one statement shared by both
    # ArcadeDB arms (_msg_schema_ddl); Person(id) is stated once per arm.
    "l2_graph.py": {("Person", "id", "UNIQUE"): 2,
                    ("{label}", "id", "UNIQUE_HASH"): 1},
}


def ddl_kinds(text):
    """{(type, property, kind): how many times the text states it}."""
    return dict(collections.Counter(DDL.findall(text)))


def _source(name):
    return (HERE / name).read_text(encoding="utf-8")


def _message_labels():
    """ldbc_snb.MSG_VERTEX_LABELS, read from the source so no import is needed."""
    for node in ast.parse(_source("ldbc_snb.py")).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MSG_VERTEX_LABELS" for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("ldbc_snb.MSG_VERTEX_LABELS not found")


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_lane_ddl_is_exactly_the_row(name):
    """Each lane's CREATE INDEX statements are the set the row names: hash on the
    equality-only ids, sorted on the ranged or grouped keys, both deployments."""
    assert ddl_kinds(_source(name)) == EXPECTED[name]


def test_the_check_can_fail():
    """A lane that went back to `UNIQUE` is not equal to the row, so the test
    above fails on it: the property this file exists for, shown on a string."""
    old = _source("l1_tpc.py").replace("UNIQUE_HASH", "UNIQUE")
    assert ddl_kinds(old) != EXPECTED["l1_tpc.py"]
    assert ddl_kinds("CREATE INDEX ON Part (p_partkey) UNIQUE") == {("Part", "p_partkey", "UNIQUE"): 1}


def test_registry_is_the_hash_ddl():
    """fairness_check.ARCADEDB_HASH_ID_INDEXES names exactly the (type, property)
    pairs the lanes create as UNIQUE_HASH, and the message half's types are the
    LDBC loader's."""
    labels = _message_labels()
    want = set()
    for lane, _wl, pairs in FC.ARCADEDB_HASH_ID_INDEXES:
        got_in_file = ddl_kinds(_source(LANE_FILE[lane]))
        for t, p in pairs:
            key = ("{label}", p, "UNIQUE_HASH") if lane == "l2" else (t, p, "UNIQUE_HASH")
            assert key in got_in_file, f"{lane}: registry names {t}.{p} but the DDL does not make it a hash index"
            want.add((lane, t, p))
    l2_types = {t for lane, t, _ in want if lane == "l2"}
    assert l2_types == set(labels)
    # and the other direction: no hash index in a lane file is missing from the registry
    for lane, name in LANE_FILE.items():
        in_registry = {(t, p) for ln, _wl, pairs in FC.ARCADEDB_HASH_ID_INDEXES if ln == lane for t, p in pairs}
        for (t, p, kind) in ddl_kinds(_source(name)):
            if kind == "UNIQUE_HASH":
                tp = (t, p)
                if t == "{label}":
                    assert {(x, p) for x in labels} <= in_registry
                else:
                    assert tp in in_registry, f"{name} makes {t}.{p} a hash index and the registry does not say so"


def test_registry_and_sorted_list_do_not_overlap():
    """Person(id) is the one id that stays sorted on purpose, and the registry
    must never list it."""
    hashed = {(lane, t, p) for lane, _wl, pairs in FC.ARCADEDB_HASH_ID_INDEXES for t, p in pairs}
    for entry in FC.ARCADEDB_SORTED_ID_INDEXES:
        assert entry not in hashed
    assert ("l2", "Person", "id") in FC.ARCADEDB_SORTED_ID_INDEXES
    assert ("Person", "id", "UNIQUE") in ddl_kinds(_source("l2_graph.py"))


def test_e2_declaration_names_the_kind():
    """The F14 declaration string for both ArcadeDB cross-model arms says
    UNIQUE_HASH, as the row words it."""
    decl = FC.INDEX_DECISIONS["e2"]
    assert decl["arcadedb_e2"] == "Product(pid) UNIQUE_HASH"
    assert decl["arcadedb_e2_server"] == "Product(pid) UNIQUE_HASH"


# --------------------------------------------------------------------------
# the page sentence

def _table(table_id, *backends, columns=("ingest s", "index s", "ingest total s")):
    return {"id": table_id, "columns": list(columns),
            "entries": [{"backend_key": b, "is_arcadedb": b.startswith("arcadedb")} for b in backends]}


@pytest.fixture(scope="module")
def EW():
    """export_web, imported once. It refuses to import without a pin in the
    environment (its dense overlay is pinned only), and the sentence under test
    does not read the pin, so a missing one is filled for the import alone."""
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


def test_documents_table_names_the_three_ids(EW):
    for tid in ("docs_oltp", "docs_olap"):
        (text,) = EW._arcadedb_hash_index_notes(_table(tid, "arcadedb_embedded", "arcadedb_server", "sqlite"))
        assert "`Part.p_partkey`, `OrderNew.okey`, and `Crud.ckey`" in text      # Oxford comma
        assert "UNIQUE_HASH" in text and "ascending" in text and "ingest and index times" in text
        assert "Person" not in text and "l_shipdate" not in text


def test_cross_model_table_names_product_pid_and_atomicity_stays_silent(EW):
    (text,) = EW._arcadedb_hash_index_notes(_table("e2", "arcadedb_e2", "neo4j_e2",
                                                   columns=("ingest+index total s",)))
    assert text.startswith("ArcadeDB's index on `Product.pid` is a hash index")
    # the atomicity table counts trials and prints no load time, so the cost has nowhere to show
    assert EW._arcadedb_hash_index_notes(
        _table("e2atom", "arcadedb_e2", columns=("trials", "torn results"))) == []


def test_graph_names_the_message_half_only_on_the_analytics_table(EW):
    assert EW._arcadedb_hash_index_notes(_table("l2", "arcadedb_graph_embedded")) == []   # Person(id) only
    (text,) = EW._arcadedb_hash_index_notes(_table("l2olap", "arcadedb_graph_embedded", "arcadedb_graph_server"))
    assert "`id` of Country, City, Forum, Post, Comment, Tag, and TagClass" in text
    assert "Person" not in text


def test_no_arcadedb_arm_no_sentence(EW):
    assert EW._arcadedb_hash_index_notes(_table("docs_oltp", "sqlite", "duckdb")) == []
    # a censored ArcadeDB row stands for no loaded table
    t = {"id": "docs_oltp", "entries": [{"backend_key": "arcadedb_embedded", "is_arcadedb": True,
                                          "outcome": "censored"}]}
    assert EW._arcadedb_hash_index_notes(t) == []
    assert EW._arcadedb_hash_index_notes(_table("l3d", "arcadedb_dense_embedded")) == []


def test_sentence_house_style(EW):
    """No dash a reader would take for an LLM's, no internal filing number, no
    digit nothing checks."""
    for tid, be in (("docs_oltp", "arcadedb_embedded"), ("e2", "arcadedb_e2"),
                    ("l2olap", "arcadedb_graph_embedded")):
        (text,) = EW._arcadedb_hash_index_notes(_table(tid, be))
        assert "—" not in text and "–" not in text and " -- " not in text
        assert not re.search(r"#\d|DECISIONS|BUGS|\bF\d+\b|row \d+", text)
        assert not re.search(r"\d", text)
