"""The graph writes are inside an answer check: the edge half of the write and of the delete (CAMPAIGN section 7 row 58, BUGS F172).

Run with `python -m pytest test_graph_post_state.py -q -rs` from this directory.

OLTP_WRITE creates a person AND the KNOWS edge into them; OLTP_DELETE removes the person AND the edge (DETACH DELETE). The
person digests read the persons only, so an engine that skipped the edge write, or left the edge behind on delete, printed a
faster write and passed every gate. The lane now reads back, untimed, the KNOWS edges into the written persons after the
insert (one per person) and after the delete (none), as `res_graph_insert_edges_*` and `res_graph_delete_edges_*`.
The lane runs here against stand-in adapters that keep a tiny graph in memory, one honest and two that skip half the write.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402

READS = {"point": [{"name": "p", "age": 40}], "hop1": [{"n": 3, "a": 41.0}], "hop2": [{"n": 9}], "hop3f": [{"n": 20}]}


class _Graph(L.Base):
    name = "stub_graph"
    version = "stub"
    QUERY_LANGUAGE = "stub"
    SKIP_EDGE_ON_WRITE = False
    LEAVE_EDGE_ON_DELETE = False

    def connect(self):
        self.persons, self.edges = {}, []

    def build(self, n):
        for _ in L.gen_persons(n):
            pass
        for _ in L.gen_edges(n):
            pass

    def run_read(self, op, pid):
        return READS[op]

    def run_visited(self, pid):
        return [{"n": 3}]

    def run_write(self, pid, new_id):
        self.persons[new_id] = {"id": new_id, "name": f"w{new_id}", "age": 33, "city": "city_0"}
        if not self.SKIP_EDGE_ON_WRITE:
            self.edges.append((pid, new_id))

    def run_update(self, new_id):
        self.persons[new_id]["age"] = G.UPDATE_AGE

    def run_delete(self, new_id):
        del self.persons[new_id]
        if not self.LEAVE_EDGE_ON_DELETE:
            self.edges = [e for e in self.edges if e[1] != new_id]

    def person_scan(self, id_from):
        return [p for i, p in self.persons.items() if i >= id_from]

    def edge_scan(self, id_from):
        return [{"src": a, "dst": b} for a, b in self.edges if b >= id_from]


class _SkipsTheEdge(_Graph):
    name = "stub_skip"
    SKIP_EDGE_ON_WRITE = True


class _LeavesTheEdge(_Graph):
    name = "stub_leave"
    LEAVE_EDGE_ON_DELETE = True


@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "CRUD_OPS", 20)
    for cls in (_Graph, _SkipsTheEdge, _LeavesTheEdge):
        monkeypatch.setitem(L.ADAPTERS, cls.name, cls)

    def go(backend):
        out = tmp_path / f"{backend}.json"
        monkeypatch.setattr(sys, "argv", ["l2_graph.py", "--backend", backend, "--workload", "oltp",
                                           "--scale", "micro", "--out", str(out)])
        L.main()
        return json.loads(out.read_text())
    return go


def test_an_honest_write_leaves_one_edge_per_person_and_a_delete_leaves_none(run):
    row = run("stub_graph")
    assert row["res_graph_insert_edges_n"] == 20 and row["res_graph_delete_edges_n"] == 0
    assert row["res_graph_insert_n"] == 20 and row["res_graph_delete_n"] == 0


def test_a_write_that_skips_the_edge_no_longer_passes_on_its_persons_alone(run):
    good, bad = run("stub_graph"), run("stub_skip")
    assert good["res_graph_insert_digest"] == bad["res_graph_insert_digest"]           # the person digests agree: the old gap
    assert good["res_graph_insert_edges_digest"] != bad["res_graph_insert_edges_digest"]
    assert bad["res_graph_insert_edges_n"] == 0


def test_a_delete_that_leaves_the_edge_behind_no_longer_passes_on_its_persons_alone(run):
    good, bad = run("stub_graph"), run("stub_leave")
    assert good["res_graph_delete_digest"] == bad["res_graph_delete_digest"]
    assert good["res_graph_delete_edges_digest"] != bad["res_graph_delete_edges_digest"]
    assert bad["res_graph_delete_edges_n"] == 20


def test_every_engine_has_an_edge_read_back():
    """Cypher arms read the shared text; the four dialects with their own person read-back have their own."""
    assert "KNOWS]->(q:Person) WHERE q.id >= $f" in G.EDGE_SCAN and "AS src" in G.EDGE_SCAN and "AS dst" in G.EDGE_SCAN
    for cls in (L.DuckpgqGraph, L.SurrealGraph, L.ArangoGraph, L.MongoGraph):
        assert "edge_scan" in cls.__dict__, cls.__name__
    for cls in (L.ArcadeGraphEmbedded, L.ArcadeGraphServer, L.Neo4jGraph, L.MemgraphGraph, L.FalkorGraph,
                L.LadybugGraph, L.PgAgeGraph):
        assert "edge_scan" not in cls.__dict__ and callable(cls.edge_scan), cls.__name__


def test_the_lane_digests_the_edges_straight_after_the_persons_they_belong_to():
    src = (HERE / "l2_graph.py").read_text()
    main = src[src.index("def main():"):]
    a = main.index('record_result(out, "graph_insert", ad.person_scan')
    b = main.index('record_result(out, "graph_insert_edges", ad.edge_scan')
    c = main.index('record_result(out, "graph_delete", ad.person_scan')
    d = main.index('record_result(out, "graph_delete_edges", ad.edge_scan')
    assert a < b < main.index('record_result(out, "graph_update"') < c < d


def test_the_cross_engine_gate_knows_age_misses_the_first_edge_for_the_reason_it_misses_the_first_person():
    import equivalence_check as E
    assert "pgage_graph" in E.KNOWN_DISAGREEMENTS[("l2", "graph_insert_edges")]
    assert ("l2", "graph_delete_edges") not in E.KNOWN_DISAGREEMENTS       # a delete that leaves nothing agrees everywhere
