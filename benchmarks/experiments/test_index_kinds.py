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
# the stamp: what the engine reports it built (`index_kinds`)

# The rows of `SELECT FROM schema:indexes` as the engine returned them (probe, CI engine d36b4ca3ae):
# each index twice, once per bucket and once for the type. Only the type-level entry names the type.
SCHEMA_ROWS = [
    {"name": "Part_0_3818899980134249", "indexType": "HASH", "typeName": "Part", "properties": [["p_partkey"]]},
    {"name": "Part[p_partkey]", "indexType": "HASH", "typeName": "Part", "properties": [["p_partkey"]]},
    {"name": "Q_0_3818900051848927", "indexType": "LSM_TREE", "typeName": "Q", "properties": [["k"]]},
    {"name": "Q[k]", "indexType": "LSM_TREE", "typeName": "Q", "properties": [["k"]]},
    {"name": "Product[embedding]", "indexType": "LSM_VECTOR", "typeName": "Product", "properties": [["embedding"]]},
]


def test_stamp_is_the_type_level_kinds_the_engine_reported():
    import bench_common
    assert bench_common.arcadedb_index_kinds(SCHEMA_ROWS) == \
        "Part.p_partkey=HASH;Product.embedding=LSM_VECTOR;Q.k=LSM_TREE"
    assert bench_common.arcadedb_index_kinds([]) == ""
    assert bench_common.parse_index_kinds("Part.p_partkey=HASH;Q.k=LSM_TREE") == \
        {"Part.p_partkey": "HASH", "Q.k": "LSM_TREE"}
    # a row that never recorded the stamp asserts nothing, whatever shape its absence takes
    for absent in (None, "", "nan", "None", float("nan")):
        assert bench_common.parse_index_kinds(absent) == {}


def test_readback_asks_the_engine_and_records_a_failure_without_raising():
    import bench_common
    assert bench_common.arcadedb_index_readback(lambda: SCHEMA_ROWS) == {
        "index_kinds": "Part.p_partkey=HASH;Product.embedding=LSM_VECTOR;Q.k=LSM_TREE"}

    def boom():
        raise OSError("server gone")
    out = bench_common.arcadedb_index_readback(boom)
    assert "index_kinds" not in out and "server gone" in out["index_kinds_error"]
    assert "index_kinds_error" in bench_common.arcadedb_index_readback(lambda: [])      # nothing to stamp


@pytest.mark.parametrize("name,methods", [("l1_tpc.py", 2), ("l1_tabular.py", 2), ("e2_hybrid.py", 2),
                                          ("l2_graph.py", 2)])
def test_every_arcadedb_adapter_reads_the_kinds_back_and_the_lane_puts_them_on_the_row(name, methods):
    """Embedded and served arm each define `index_readback`, and the lane's main calls it after the
    build and before a timed operation, onto the row. (The engine's answer itself is the rehearsal's
    evidence; this holds the wiring so a lane cannot lose it silently.)"""
    src = _source(name)
    assert len(re.findall(r"def index_readback\(self\)", src)) == methods
    assert src.count("arcadedb_index_readback(") == methods
    assert 'hasattr(' in src and ".index_readback()" in src
    # only an ArcadeDB adapter defines it: the lanes' other arms must not grow the stamp
    assert len(re.findall(r"index_readback", src)) >= methods + 1


# --------------------------------------------------------------------------
# F14d: the gate over rows

GOOD = {
    "l1tpc": "Crud.ckey=HASH;LineItem.l_shipdate=LSM_TREE;OrderNew.okey=HASH;Part.p_partkey=HASH",
    "e2": "Product.embedding=LSM_VECTOR;Product.pid=HASH",
    "l2": ("City.id=HASH;Comment.id=HASH;Country.id=HASH;Forum.id=HASH;Person.id=LSM_TREE;Post.id=HASH;"
           "Tag.id=HASH;TagClass.id=HASH"),
}


def _row(lane="l1tpc", backend="arcadedb_embedded", workload="oltp", stamp="@good", **kw):
    r = {"lane": lane, "backend": backend, "workload": workload, "scale": "micro", "rep": 1,
         "instrument": "2026-10", "index_kinds": GOOD[lane] if stamp == "@good" else stamp}
    r.update(kw)
    return r


@pytest.fixture
def strict(monkeypatch):
    """F14d as it is once the re-pin campaign has started: every finding is a failure."""
    monkeypatch.setattr(FC, "INDEX_KINDS_GATE_FAILS", True)


def test_gate_passes_stamped_rows_of_every_lane(capsys):
    rows = [_row(), _row(backend="arcadedb_server"),
            _row("e2", "arcadedb_e2", "hybrid"), _row("e2", "arcadedb_e2_server", "atomicity"),
            _row("l2", "arcadedb_graph_embedded", "olap", msg_vertices=107605)]
    for mode in (False, True):                                   # clean rows pass in both modes
        FC.INDEX_KINDS_GATE_FAILS = mode
        try:
            assert FC.check_index_kinds(rows) == 0
        finally:
            FC.INDEX_KINDS_GATE_FAILS = False
        assert "ok   5 row(s)" in capsys.readouterr().out


UNSTAMPED_ROWS = [
    (_row(stamp=None), "NOT STAMPED"),                                        # no stamp
    (_row(stamp="", index_kinds_error="OSError: gone"), "NOT STAMPED"),       # the read failed
]

WRONG_ROWS = [
    (_row(stamp="Part.p_partkey=LSM_TREE;Crud.ckey=HASH;OrderNew.okey=HASH"), "WRONG"),   # the old DDL
    (_row(stamp="Crud.ckey=HASH;OrderNew.okey=HASH"), "WRONG"),                           # an id the engine did not build
    (_row("l2", "arcadedb_graph_embedded", "olap",
          stamp=GOOD["l2"].replace("Person.id=LSM_TREE", "Person.id=HASH"), msg_vertices=1), "WRONG"),
]


@pytest.mark.parametrize("row,what", WRONG_ROWS)
def test_a_stamped_row_with_the_wrong_kind_always_fails(row, what, capsys, monkeypatch):
    """A STAMPED row can only have been written by this harness, so a kind the registry does not ask for is
    evidence the setting did not take, and there is no old row for the failure to block: it fails from the
    first day, whether or not the gate has been flipped."""
    for flag in (False, True):
        monkeypatch.setattr(FC, "INDEX_KINDS_GATE_FAILS", flag)
        assert FC.check_index_kinds([row]) >= 1
        out = capsys.readouterr().out
        assert what in out and not any(l.lstrip().startswith("WARN") for l in out.splitlines())


@pytest.mark.parametrize("row,what", UNSTAMPED_ROWS)
def test_an_unstamped_row_fails_only_once_the_gate_is_flipped(row, what, strict, capsys):
    assert FC.check_index_kinds([row]) >= 1
    out = capsys.readouterr().out
    assert what in out and "WARN" not in out and "an unstamped row FAILS" in out


@pytest.mark.parametrize("row,what", UNSTAMPED_ROWS)
def test_an_unstamped_row_only_warns_until_the_campaign_starts(row, what, capsys):
    """THE DEFAULT. October's rows predate the stamp and must not block landing an October stage: an
    unstamped row is printed as a warning and the return value (which main() adds to the exit status) is 0."""
    assert FC.INDEX_KINDS_GATE_FAILS is False
    assert FC.check_index_kinds([row]) == 0
    out = capsys.readouterr().out
    assert f"WARN {what}" in out and "do not change the exit status" in out


def test_in_the_default_mode_only_the_wrong_stamped_row_counts(capsys):
    """October-shaped rows (no stamp) beside one wrong stamped row: the unstamped ones warn, the wrong one fails."""
    rows = [_row(stamp=None), _row(backend="arcadedb_server", stamp=None), WRONG_ROWS[0][0]]
    assert FC.check_index_kinds(rows) == 1
    out = capsys.readouterr().out
    assert out.count("WARN NOT STAMPED") == 2 and out.count("WRONG") == 1


def test_the_gate_has_exactly_one_switch():
    src = (HERE / "fairness_check.py").read_text()
    assert len(re.findall(r"^INDEX_KINDS_GATE_FAILS = ", src, re.M)) == 1
    assert "INDEX_KINDS_GATE_FAILS = False" in src                      # report-only is the committed state
    # the switch is documented where the flip is made
    assert "INDEX_KINDS_GATE_FAILS" in (HERE / "CAMPAIGN.md").read_text()


def test_the_flip_changes_the_exit_status_of_the_whole_gate(monkeypatch):
    """main() adds check_index_kinds' return value to its failure count, so the constant is what moves
    the exit status for the UNSTAMPED case: an October-shaped set of rows (no stamp anywhere) passes in the
    default mode and fails after the flip. (A wrong stamped kind never waited for the flip.)"""
    october = [_row(stamp=None), _row(backend="arcadedb_server", stamp=None)]
    assert "bad += check_index_kinds(rows)" in (HERE / "fairness_check.py").read_text()
    assert FC.check_index_kinds(october) == 0
    monkeypatch.setattr(FC, "INDEX_KINDS_GATE_FAILS", True)
    assert FC.check_index_kinds(october) == 2


def test_gate_does_not_owe_the_message_half_to_a_cell_that_never_loaded_it(strict):
    micro = _row("l2", "arcadedb_graph_embedded", "olap", stamp="Person.id=LSM_TREE")      # no msg_vertices
    assert FC.check_index_kinds([micro]) == 0
    assert FC.check_index_kinds([dict(micro, msg_vertices=5)]) >= 1                        # it did: now it is owed


def test_gate_leaves_other_engines_other_lanes_errors_and_other_instruments_alone(strict):
    assert FC.check_index_kinds([_row(backend="sqlite", stamp=None)]) == 0
    other_lane = {"lane": "l3d", "backend": "arcadedb_dense_embedded", "instrument": "2026-10", "workload": "search"}
    assert FC.check_index_kinds([other_lane]) == 0
    assert FC.check_index_kinds([dict(_row(stamp=None), error="boom")]) == 0
    assert FC.check_index_kinds([dict(_row(stamp=None), instrument="2026-09")]) == 0


# --------------------------------------------------------------------------
# the page sentence

def _table(table_id, *backends, columns=("ingest s", "index s", "ingest total s"), scale="micro"):
    return {"id": table_id, "columns": list(columns),
            "entries": [{"backend_key": b, "scale": scale, "is_arcadedb": b.startswith("arcadedb")}
                        for b in backends]}


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


def _frozen(EW, monkeypatch, *rows):
    monkeypatch.setattr(EW, "_FROZEN_ROWS", list(rows))


def test_documents_table_names_the_three_ids_the_engine_reported(EW, monkeypatch):
    _frozen(EW, monkeypatch, _row(), _row(backend="arcadedb_server"), _row(workload="olap"),
            _row(backend="arcadedb_server", workload="olap"))
    for tid in ("docs_oltp", "docs_olap"):
        (text,) = EW._arcadedb_hash_index_notes(_table(tid, "arcadedb_embedded", "arcadedb_server", "sqlite"))
        assert "`Part.p_partkey`, `OrderNew.okey`, and `Crud.ckey`" in text      # Oxford comma
        assert "UNIQUE_HASH" in text and "ascending" in text and "ingest and index times" in text
        assert "Person" not in text and "l_shipdate" not in text


def test_the_sentence_needs_the_stamp_on_every_row_the_table_prints(EW, monkeypatch):
    """THE POINT OF THE STAMP: rows that did not record what the engine built make no claim, so a
    page regenerated over rows measured before the stamp existed cannot say hash index."""
    table = _table("docs_oltp", "arcadedb_embedded", "arcadedb_server")
    _frozen(EW, monkeypatch, _row(stamp=None), _row(backend="arcadedb_server", stamp=None))
    assert EW._arcadedb_hash_index_notes(table) == []                        # no stamp anywhere
    _frozen(EW, monkeypatch, _row(), _row(backend="arcadedb_server", stamp=None))
    assert EW._arcadedb_hash_index_notes(table) == []                        # one unstamped row is enough
    _frozen(EW, monkeypatch, _row(), _row(backend="arcadedb_server", stamp="", index_kinds_error="x"))
    assert EW._arcadedb_hash_index_notes(table) == []                        # a failed read-back too
    _frozen(EW, monkeypatch)
    assert EW._arcadedb_hash_index_notes(table) == []                        # and no rows at all


def test_the_sentence_names_only_ids_the_engine_reported_as_hash(EW, monkeypatch):
    table = _table("docs_oltp", "arcadedb_embedded", "arcadedb_server")
    old_part = "Crud.ckey=HASH;OrderNew.okey=HASH;Part.p_partkey=LSM_TREE"       # Part ran the old DDL
    _frozen(EW, monkeypatch, _row(stamp=old_part), _row(backend="arcadedb_server", stamp=old_part))
    (text,) = EW._arcadedb_hash_index_notes(table)
    assert "`OrderNew.okey` and `Crud.ckey`" in text and "Part.p_partkey" not in text
    # one arm reporting an id as sorted takes it out for the whole table
    _frozen(EW, monkeypatch, _row(), _row(backend="arcadedb_server", stamp=old_part))
    (text,) = EW._arcadedb_hash_index_notes(table)
    assert "Part.p_partkey" not in text


def test_the_sentence_reads_the_rows_of_this_table_and_scale_only(EW, monkeypatch):
    table = _table("docs_oltp", "arcadedb_embedded")
    # an unstamped row at a size the table does not print, and an olap row, make no difference
    _frozen(EW, monkeypatch, _row(), dict(_row(stamp=None), scale="tpch10"), _row(workload="olap", stamp=None))
    assert EW._arcadedb_hash_index_notes(table)
    # but the same unstamped row AT a printed size removes it
    _frozen(EW, monkeypatch, _row(), dict(_row(stamp=None), rep=2))
    assert EW._arcadedb_hash_index_notes(table) == []


def test_cross_model_table_names_product_pid_and_atomicity_stays_silent(EW, monkeypatch):
    _frozen(EW, monkeypatch, _row("e2", "arcadedb_e2", "hybrid"))
    (text,) = EW._arcadedb_hash_index_notes(_table("e2", "arcadedb_e2", "neo4j_e2",
                                                   columns=("ingest+index total s",)))
    assert text.startswith("ArcadeDB's index on `Product.pid` is a hash index")
    # the atomicity table counts trials and prints no load time, so the cost has nowhere to show
    _frozen(EW, monkeypatch, _row("e2", "arcadedb_e2", "atomicity"))
    assert EW._arcadedb_hash_index_notes(
        _table("e2atom", "arcadedb_e2", columns=("trials", "torn results"))) == []


def test_graph_names_the_message_half_only_when_the_engine_built_it(EW, monkeypatch):
    _frozen(EW, monkeypatch, _row("l2", "arcadedb_graph_embedded", "oltp"))
    assert EW._arcadedb_hash_index_notes(_table("l2", "arcadedb_graph_embedded")) == []   # Person(id) only
    _frozen(EW, monkeypatch, _row("l2", "arcadedb_graph_embedded", "olap", msg_vertices=5),
            _row("l2", "arcadedb_graph_server", "olap", msg_vertices=5))
    (text,) = EW._arcadedb_hash_index_notes(_table("l2olap", "arcadedb_graph_embedded", "arcadedb_graph_server"))
    assert "the `id` of Country, City, Forum, Post, Comment, Tag, and TagClass" in text
    assert "Person" not in text
    # a micro cell that never built the message half asserts no message-half id
    _frozen(EW, monkeypatch, _row("l2", "arcadedb_graph_embedded", "olap", stamp="Person.id=LSM_TREE"))
    assert EW._arcadedb_hash_index_notes(_table("l2olap", "arcadedb_graph_embedded")) == []


def test_no_arcadedb_arm_no_sentence(EW, monkeypatch):
    _frozen(EW, monkeypatch, _row())
    assert EW._arcadedb_hash_index_notes(_table("docs_oltp", "sqlite", "duckdb")) == []
    # a censored ArcadeDB row stands for no loaded table
    t = {"id": "docs_oltp", "entries": [{"backend_key": "arcadedb_embedded", "is_arcadedb": True,
                                          "outcome": "censored"}]}
    assert EW._arcadedb_hash_index_notes(t) == []
    assert EW._arcadedb_hash_index_notes(_table("l3d", "arcadedb_dense_embedded")) == []


def test_sentence_house_style(EW, monkeypatch):
    """No dash a reader would take for an LLM's, no internal filing number, no
    digit nothing checks."""
    _frozen(EW, monkeypatch, _row(), _row("e2", "arcadedb_e2", "hybrid"),
            _row("l2", "arcadedb_graph_embedded", "olap", msg_vertices=5))
    for tid, be in (("docs_oltp", "arcadedb_embedded"), ("e2", "arcadedb_e2"),
                    ("l2olap", "arcadedb_graph_embedded")):
        (text,) = EW._arcadedb_hash_index_notes(_table(tid, be))
        assert "\u2014" not in text and "\u2013" not in text and " -- " not in text
        assert not re.search(r"#\d|DECISIONS|BUGS|\bF\d+\b|row \d+", text)
        assert not re.search(r"\d", text)
