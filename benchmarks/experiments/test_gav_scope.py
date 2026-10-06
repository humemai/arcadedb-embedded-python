"""ArcadeDB's Graph Analytical View covers every vertex and edge type of the loaded graph (CAMPAIGN section 7 row 61, DECISIONS #154 item 3).

Run with `python -m pytest test_gav_scope.py -q -rs` from this directory.

ArcadeDB's planner uses a view only when it covers the vertex and edge types a query reads, and upstream's own LSQB runner
builds its view over all eight vertex types and all eleven edge types. The lane built it over Person and KNOWS, so no LSQB
query could use it. Both ArcadeDB adapters now build it over every type of the loaded graph, read back which types the ENGINE
says it covers, refuse a view that covers fewer than the statement named, and record them as `gav_types`. The no-view arm
(BENCH_GAV=0) stays as the like-for-like row. The adapters run here against stand-ins that record the statements.
"""
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import l2_graph as L  # noqa: E402
import ldbc_snb  # noqa: E402


def _emb(loaded):
    a = object.__new__(L.ArcadeGraphEmbedded)
    a._load_messages = loaded
    a._scale = "sf1full"
    return a


def test_a_tier_with_no_message_half_keeps_the_view_it_always_had():
    ddl = _emb(False)._gav_ddl()
    assert ddl == ("CREATE GRAPH ANALYTICAL VIEW l2gav VERTEX TYPES (Person) EDGE TYPES (KNOWS) "
                   "PROPERTIES (id, name, age, city) EDGE PROPERTIES (since) UPDATE MODE OFF")


def test_the_full_network_view_covers_every_type_the_adapter_creates():
    """Parse the DDL the adapter issues for the graph and require the view to name every non-abstract vertex and edge type."""
    a = _emb(True)
    created = ["CREATE VERTEX TYPE Person", "CREATE EDGE TYPE KNOWS"] + a._msg_schema_ddl()
    vertices = {m.group(1) for d in created if (m := re.match(r"CREATE VERTEX TYPE (\w+)", d))} - {"Message"}   # abstract supertype
    edges = {m.group(1) for d in created if (m := re.match(r"CREATE EDGE TYPE (\w+)", d))}
    v, e = a._gav_types()
    assert set(v) == vertices and set(e) == edges
    assert len(v) == 8 and len(e) == 11                              # upstream's own LSQB runner: eight and eleven
    ddl = a._gav_ddl()
    assert ddl.startswith("CREATE GRAPH ANALYTICAL VIEW l2gav VERTEX TYPES (Person, ")
    assert ddl.endswith("PROPERTIES (id, name, age, city) EDGE PROPERTIES (since) UPDATE MODE OFF")
    for name in vertices | edges:
        assert re.search(rf"\b{name}\b", ddl), name


def test_the_view_refuses_to_pass_when_the_engine_reports_a_narrower_cover():
    a = _emb(True)
    v, e = a._gav_types()
    a._gav_confirm([{"vertexTypes": v, "edgeTypes": e}])
    assert a.gav_types.startswith("vertex: Person, ") and "; edge: KNOWS, " in a.gav_types
    with pytest.raises(RuntimeError, match="not the"):
        _emb(True)._gav_confirm([{"vertexTypes": ["Person"], "edgeTypes": ["KNOWS"]}])
    with pytest.raises(RuntimeError):
        _emb(True)._gav_confirm([])                                  # an engine that reports nothing is not "covered"


def test_the_report_is_read_as_a_list_or_as_its_json_text():
    assert L._name_list([{"vertexTypes": ["A", "B"]}], "vertexTypes") == ["A", "B"]
    assert L._name_list([{"vertexTypes": json.dumps(["A", "B"])}], "vertexTypes") == ["A", "B"]
    assert L._name_list([{"vertexTypes": "['A', 'B']"}], "vertexTypes") == ["A", "B"]
    assert L._name_list([], "vertexTypes") == [] and L._name_list([{"x": 1}], "vertexTypes") == []


class _Db:
    """Records the statements; reports the view READY over what it was asked to cover."""
    def __init__(self):
        self.commands = []
        self._types = None

    def command(self, language, text):
        self.commands.append(text)
        m = re.search(r"VERTEX TYPES \(([^)]*)\) EDGE TYPES \(([^)]*)\)", text)
        self._types = ([x.strip() for x in m.group(1).split(",")], [x.strip() for x in m.group(2).split(",")])

    def query(self, language, text, *args):
        v, e = self._types

        class _R:
            def to_json_list(_s):
                return [{"name": "l2gav", "status": "READY", "vertexTypes": v, "edgeTypes": e}]
        return _R()


@pytest.mark.parametrize("loaded", [False, True])
def test_the_embedded_arm_creates_the_view_over_every_type_and_records_what_it_covers(loaded, monkeypatch):
    monkeypatch.delenv("BENCH_GAV", raising=False)
    a = _emb(loaded)
    a.db = _Db()
    a.post_build("olap")
    assert a.db.commands == [a._gav_ddl()] and a.gav_build_s >= 0
    v, e = a._gav_types()
    assert a.gav_types == f"vertex: {', '.join(v)}; edge: {', '.join(e)}"


@pytest.mark.parametrize("loaded", [False, True])
def test_the_served_arm_does_the_same_over_http(loaded, monkeypatch):
    monkeypatch.delenv("BENCH_GAV", raising=False)
    a = object.__new__(L.ArcadeGraphServer)
    a._load_messages, a._scale = loaded, "sf1full"
    sent, types = [], {}

    def _http(kind, language, text, params=None):
        if kind == "command":
            sent.append(text)
            m = re.search(r"VERTEX TYPES \(([^)]*)\) EDGE TYPES \(([^)]*)\)", text)
            types["v"], types["e"] = [x.strip() for x in m.group(1).split(",")], [x.strip() for x in m.group(2).split(",")]
            return []
        return [{"name": "l2gav", "status": "READY", "vertexTypes": types["v"], "edgeTypes": types["e"]}]
    a._http = _http
    a.post_build("olap")
    assert sent == [a._gav_ddl()] and a.gav_types.startswith("vertex: Person")


def test_the_no_view_arm_builds_nothing_and_records_no_types(monkeypatch):
    monkeypatch.setenv("BENCH_GAV", "0")
    a = _emb(True)
    a.db = _Db()
    a.post_build("olap")
    assert a.db.commands == [] and a.gav_build_s == 0.0 and not getattr(a, "gav_types", None)


def test_the_interactive_workload_builds_no_view():
    a = _emb(False)
    a.db = _Db()
    a.post_build("oltp")
    assert a.db.commands == []


def test_the_lane_stamps_the_types_and_the_page_reads_the_same_field():
    src = (HERE / "l2_graph.py").read_text()
    main = src[src.index("def main():"):]
    assert 'out["gav_types"] = ad.gav_types' in main and 'getattr(ad, "gav_types", None)' in main
    ew = (HERE / "export_web.py").read_text()
    assert re.search(r'^_GAV_TYPES_FIELD = "gav_types"$', ew, re.M)
    assert len(ldbc_snb.MSG_VERTEX_LABELS) == 7                      # Person + these seven = upstream's eight
