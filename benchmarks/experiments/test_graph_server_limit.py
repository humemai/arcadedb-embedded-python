"""ArangoDB's, MongoDB's and Memgraph's analytics queries are cut by the SERVER at their budget (DECISIONS #179).

Run with `python -m pytest test_graph_server_limit.py -q -rs` from this directory.

The analytics loop checked each query's budget only BETWEEN iterations, so one iteration of ArangoDB's triangle count ran
3,136 s against a 300 s budget (SF1-full graph analytics, 2026-10-09) and the 7,200 s cell cap then killed the cell with no
row. MongoDB's lsqb_q1 cold pass then ran 79 min against the same 300 s budget. The adapters now pass the AQL option maxRuntime = the query's budget on the cold pass and every timed iteration; a query
the server kills (error 1500) is a CENSORED measurement: the row says so, the time is a floor, there is no answer digest, and
the cell does not fail. Every other engine runs exactly as before.

The lane runs here, in-process, against stand-in adapters and a fake python-arango database. No engine is needed; the real
server's kill (error number, kill latency on a long traversal) is the pending smoke test, smoke_arangodb_server_limit.sh.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arango_common  # noqa: E402
import mongo_common  # noqa: E402
import bench_common  # noqa: E402
import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402

TRI = "triangles"


class _Err(Exception):
    """What python-arango raises: ArangoServerError carries the server's errorNum as error_code."""

    def __init__(self, code, msg="query killed"):
        super().__init__(f"[HTTP 410][ERR {code}] {msg}")
        self.error_code = code
        self.http_code = 410


# ---- the adapter, against a fake python-arango database -------------------------------------------------------------

class _FakeAql:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def execute(self, query, bind_vars=None, **kw):
        self.calls.append((query, bind_vars, kw))
        return self.behaviour(len(self.calls), kw)


class _FakeDb:
    def __init__(self, behaviour):
        self.aql = _FakeAql(behaviour)


def _adapter(behaviour):
    ad = L.ArangoGraph()
    ad.db = _FakeDb(behaviour)
    return ad


def test_the_limit_is_passed_as_max_runtime_in_seconds():
    ad = _adapter(lambda n, kw: iter([{"n": 5}]))
    ad.olap_limit_s = 300
    assert ad.run_olap(TRI) == [{"n": 5}]
    (_q, _bv, kw), = ad.db.aql.calls
    assert kw == {"max_runtime": 300.0}


def test_no_limit_means_the_call_is_the_old_one():
    ad = _adapter(lambda n, kw: iter([{"n": 5}]))
    assert ad.olap_limit_s is None
    ad.run_olap(TRI)
    (_q, bv, kw), = ad.db.aql.calls
    assert kw == {} and bv == {}                      # no maxRuntime, same bind vars as before


def test_error_1500_is_a_killed_query_and_other_errors_still_raise():
    ad = _adapter(lambda n, kw: (_ for _ in ()).throw(_Err(1500)))
    ad.olap_limit_s = 1
    with pytest.raises(G.QueryKilled):
        ad.run_olap(TRI)
    ad = _adapter(lambda n, kw: (_ for _ in ()).throw(_Err(1203, "collection not found")))
    ad.olap_limit_s = 1
    with pytest.raises(_Err):                          # a real failure is not censoring
        ad.run_olap(TRI)
    ad = _adapter(lambda n, kw: (_ for _ in ()).throw(ConnectionError("reset")))
    ad.olap_limit_s = 1
    with pytest.raises(ConnectionError):
        ad.run_olap(TRI)


def test_only_arango_mongo_and_memgraph_declare_a_server_side_limit():
    assert all(c.SERVER_SIDE_LIMIT is True for c in (L.ArangoGraph, L.MongoGraph, L.MemgraphGraph))
    assert L.Neo4jGraph.SERVER_SIDE_LIMIT is False              # the Memgraph subclass sets it; its parent does not
    for name, cls in L.ADAPTERS.items():
        if cls not in (L.ArangoGraph, L.MongoGraph, L.MemgraphGraph):
            assert getattr(cls, "SERVER_SIDE_LIMIT", False) is False, name
    assert arango_common.is_query_killed(_Err(1500)) and not arango_common.is_query_killed(_Err(1203))
    assert not arango_common.is_query_killed(ValueError("x"))


# ---- MongoDB: maxTimeMS on the one aggregate command each analytics query is ---------------------------------------

class _ExecutionTimeout(Exception):
    """What pymongo raises: ExecutionTimeout, an OperationFailure with code 50 (MaxTimeMSExpired)."""
    code = 50


class _FakeColl:
    def __init__(self, log, behaviour):
        self.log, self.behaviour = log, behaviour

    def aggregate(self, pipeline, **kw):
        self.log.append(kw)
        return self.behaviour(len(self.log))


class _FakeMongoDb:
    def __init__(self, behaviour):
        self.log = []
        self.behaviour = behaviour

    def __getitem__(self, name):
        return _FakeColl(self.log, self.behaviour)


def _mongo(behaviour):
    ad = L.MongoGraph()
    ad.db = _FakeMongoDb(behaviour)
    return ad


def test_mongo_passes_the_budget_as_max_time_ms_on_every_pipeline():
    for qname in ("triangles", "top_degree", "lsqb_q1", "lsqb_q2", "lsqb_q3", "lsqb_q4", "lsqb_q7", "lsqb_q8"):
        ad = _mongo(lambda n: iter([{"n": 4}]))
        ad.olap_limit_s = 300
        ad.run_olap(qname)
        assert ad.db.log == [{"allowDiskUse": True, "maxTimeMS": 300000}], qname      # ONE command, limit on it


def test_mongo_without_a_limit_is_the_old_call():
    ad = _mongo(lambda n: iter([{"n": 4}]))
    ad.run_olap("lsqb_q1")
    assert ad.db.log == [{"allowDiskUse": True}]


def test_mongo_error_50_is_a_killed_query_and_other_errors_still_raise():
    def boom(code):
        class E(Exception):
            pass
        e = E("op failed")
        e.code = code
        return e
    ad = _mongo(lambda n: (_ for _ in ()).throw(_ExecutionTimeout("operation exceeded time limit")))
    ad.olap_limit_s = 1
    with pytest.raises(G.QueryKilled):
        ad.run_olap("lsqb_q1")
    ad = _mongo(lambda n: (_ for _ in ()).throw(boom(50)))
    ad.olap_limit_s = 1
    with pytest.raises(G.QueryKilled):
        ad.run_olap("triangles")
    ad = _mongo(lambda n: (_ for _ in ()).throw(boom(2)))             # BadValue: a real failure
    ad.olap_limit_s = 1
    with pytest.raises(Exception) as ei:
        ad.run_olap("triangles")
    assert not isinstance(ei.value, G.QueryKilled)
    assert mongo_common.is_query_killed(_ExecutionTimeout()) and not mongo_common.is_query_killed(ValueError("x"))


# ---- Memgraph: the Bolt transaction timeout, one query per session ---------------------------------------------------

class _BoltTimeout(Exception):
    """What the neo4j driver raises for Memgraph 3.13.1's abort (verified on the pinned image): a TransientError with a generic code."""
    code = "Memgraph.TransientError.MemgraphError.MemgraphError"

    def __init__(self, msg="{neo4j_code: Memgraph.TransientError.MemgraphError.MemgraphError} {message: Transaction was asked to "
                           "abort because of transaction timeout.}"):
        super().__init__(msg)


class _FakeSession:
    def __init__(self, log, behaviour):
        self.log, self.behaviour = log, behaviour

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, query, params=None):
        self.log.append(query)
        return self.behaviour(len(self.log))


class _FakeDriver:
    def __init__(self, behaviour):
        self.log = []
        self.behaviour = behaviour

    def session(self):
        return _FakeSession(self.log, self.behaviour)


def _memgraph(behaviour):
    ad = L.MemgraphGraph()
    ad.driver = _FakeDriver(behaviour)
    return ad


def test_memgraph_passes_the_budget_as_a_bolt_tx_timeout():
    neo4j = pytest.importorskip("neo4j")
    ad = _memgraph(lambda n: iter([{"n": 7}]))
    ad.olap_limit_s = 300
    assert ad.run_olap("triangles") == [{"n": 7}]
    (q,) = ad.driver.log
    assert isinstance(q, neo4j.Query) and q.timeout == 300.0 and q.text == G.OLAP_QUERIES["triangles"]


def test_memgraph_without_a_limit_is_the_old_call():
    ad = _memgraph(lambda n: iter([{"n": 7}]))
    assert ad.run_olap("triangles") == [{"n": 7}]
    assert ad.driver.log == [G.OLAP_QUERIES["triangles"]]                # a plain string, no Query, no timeout


def test_memgraph_transaction_timeout_is_a_killed_query_and_other_errors_still_raise():
    pytest.importorskip("neo4j")
    ad = _memgraph(lambda n: (_ for _ in ()).throw(_BoltTimeout()))
    ad.olap_limit_s = 1
    with pytest.raises(G.QueryKilled):
        ad.run_olap("triangles")
    other = _BoltTimeout("{neo4j_code: Memgraph.TransientError.MemgraphError.MemgraphError} {message: Memory limit exceeded!}")
    ad = _memgraph(lambda n: (_ for _ in ()).throw(other))               # same class and code, another cause: a real failure
    ad.olap_limit_s = 1
    with pytest.raises(_BoltTimeout):
        ad.run_olap("triangles")
    assert G.is_bolt_tx_timeout(_BoltTimeout()) and not G.is_bolt_tx_timeout(other) and not G.is_bolt_tx_timeout(ValueError("x"))
    neo = ValueError("neo4j says no")
    neo.code = "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration"
    assert G.is_bolt_tx_timeout(neo)                                     # Neo4j's own code names it too


def test_memgraph_stamp_says_the_server_timeout_stays_off():
    assert "--query-execution-timeout-sec stays 0" in L.MemgraphGraph.SERVER_LIMIT_STAMP
    assert "equal to the lane budget" in L.MemgraphGraph.SERVER_LIMIT_STAMP


# ---- the lane, end to end ------------------------------------------------------------------------------------------

ANSWER = [{"n": 3}]


def _make(server_limit, script):
    """A stand-in analytics adapter. `script` maps (query, call number from 1) to a sleep in seconds or 'kill'."""
    class _Stub(L.Base):
        name = "stub_graph"
        version = "stub"
        QUERY_LANGUAGE = "stub"
        SERVER_SIDE_LIMIT = server_limit
        SERVER_LIMIT_NAME = "stubLimit"
        SERVER_LIMIT_STAMP = "stub stamp"
        LIMITS = []          # the olap_limit_s each call was handed
        N = {}

        def connect(self):
            self.LIMITS.clear()
            self.N.clear()

        def build(self, n):
            for _ in L.gen_persons(n):
                pass
            for _ in L.gen_edges(n):
                pass

        def run_olap(self, qname):
            import time
            self.N[qname] = self.N.get(qname, 0) + 1
            self.LIMITS.append((qname, self.N[qname], self.olap_limit_s))
            what = script.get((qname, self.N[qname]), 0)
            if what == "kill":
                if self.olap_limit_s is None:
                    raise AssertionError("killed with no limit set")
                raise G.QueryKilled(f"{qname} killed")
            if what:
                time.sleep(what)
            return ANSWER
    return _Stub


@pytest.fixture
def lane(monkeypatch, tmp_path):
    def run(server_limit, script, **env):
        stub = _make(server_limit, script)
        monkeypatch.setitem(L.ADAPTERS, "stub_graph", stub)
        monkeypatch.setattr(L, "OLAP_ITERATIONS", 3)
        monkeypatch.setenv("BENCH_GRAPH_OLAP_BUDGET_S", env.pop("budget", "50"))
        out = tmp_path / "row.json"
        monkeypatch.setattr(sys, "argv", ["l2_graph.py", "--backend", "stub_graph", "--workload", "olap",
                                           "--scale", "micro", "--out", str(out)])
        L.main()
        return json.loads(out.read_text()), stub
    return run


def test_every_pass_gets_the_budget_and_the_row_says_the_limit_ran(lane):
    row, stub = lane(True, {}, budget="50")
    t = [(c, lim) for q, c, lim in stub.LIMITS if q == TRI]
    assert t == [(1, 50.0), (2, 50.0), (3, 50.0), (4, 50.0)]       # cold pass + 3 timed iterations
    assert row["olap_server_limit"] == "stub stamp"
    assert row[f"{TRI}_server_limit_s"] == 50.0 == row[f"{TRI}_budget_s"]
    assert f"{TRI}_server_killed" not in row and row[f"{TRI}_censored"] is False
    assert row[f"{TRI}_iters"] == 3 and row[f"res_{TRI}_n"] == 1
    assert stub.olap_limit_s is None                                 # the limit does not leak past the loop


def test_a_query_killed_on_the_cold_pass_is_a_censored_row_with_no_answer(lane):
    row, stub = lane(True, {(TRI, 1): "kill"})
    assert row[f"{TRI}_censored"] is True
    assert row[f"{TRI}_iters"] == 0 and row[f"{TRI}_warm_missing"] is True
    assert "stubLimit" in row[f"{TRI}_server_killed"]
    assert "cold pass" in row[f"{TRI}_server_killed"] and "lower bound" in row[f"{TRI}_server_killed"]
    assert row[f"{TRI}_rows"] is None
    digest = row[f"res_{TRI}_digest"]
    assert bench_common.is_censored_answer(digest) and "killed by the server" in digest   # honest: no digest of an answer
    assert row[f"res_{TRI}_sample"] == digest and row[f"res_{TRI}_n"] is None
    assert "killed" in row[f"cold_warm_{TRI}_na"]
    assert [c for q, c, _l in stub.LIMITS if q == TRI] == [1]        # no timed iteration after a kill
    # the cell goes on: the next query ran and answered, and the row is a row
    assert row["top_degree_iters"] == 3 and row["res_top_degree_n"] == 1
    assert row["instrument"] == bench_common.INSTRUMENT


def test_a_kill_in_a_timed_iteration_keeps_the_cold_answer_and_the_completed_samples(lane):
    row, stub = lane(True, {(TRI, 3): "kill"})                       # cold + one iteration done, the second is cut
    assert row[f"{TRI}_censored"] is True and row[f"{TRI}_iters"] == 1
    assert "timed iteration 2" in row[f"{TRI}_server_killed"]
    assert not bench_common.is_censored_answer(row[f"res_{TRI}_digest"]) and row[f"res_{TRI}_n"] == 1
    assert row[f"{TRI}_rows"] == 1 and f"{TRI}_warm_missing" not in row


def test_a_kill_of_the_first_timed_iteration_leaves_the_cold_pass_as_the_one_sample(lane):
    row, _stub = lane(True, {(TRI, 2): "kill"})
    assert row[f"{TRI}_iters"] == 0 and row[f"{TRI}_warm_missing"] is True
    assert "timed iteration 1" in row[f"{TRI}_server_killed"]
    assert not bench_common.is_censored_answer(row[f"res_{TRI}_digest"])       # the cold pass answered


def test_a_normal_query_is_unchanged_and_a_non_limit_engine_gets_no_limit(lane):
    row, stub = lane(False, {})
    assert all(lim is None for _q, _c, lim in stub.LIMITS)
    assert not any(k in row for k in ("olap_server_limit", f"{TRI}_server_limit_s", f"{TRI}_server_killed"))
    assert row[f"{TRI}_censored"] is False and row[f"{TRI}_iters"] == 3
    assert row[f"res_{TRI}_n"] == 1 and not bench_common.is_censored_answer(row[f"res_{TRI}_digest"])


def test_other_engines_keep_the_old_censoring_between_iterations(lane):
    # a fast cold pass, then 0.3 s per iteration against a 0.5 s budget: the loop stops by its own clock after two.
    row, stub = lane(False, {(TRI, n): 0.3 for n in range(2, 6)}, budget="0.5")
    assert row[f"{TRI}_censored"] is True and f"{TRI}_server_killed" not in row
    assert all(lim is None for _q, _c, lim in stub.LIMITS)
    assert row[f"{TRI}_iters"] == 2


def test_a_server_killed_row_does_not_vote_in_the_derived_budgets():
    import derive_budgets as D
    base = {"lane": "l2", "scale": "sf1full", "backend": "a", f"{TRI}_p50_ms": 300000.0, f"cold_{TRI}_ms": 300000.0}
    ok = {**base, "backend": "b", f"{TRI}_p50_ms": 1000.0, f"cold_{TRI}_ms": 1200.0}
    killed = {**base, f"{TRI}_server_killed": "killed ..."}
    got = D.medians([ok, killed])
    assert got[("l2", "sf1full", TRI)][1] == 1                        # one engine voted, the killed one did not
