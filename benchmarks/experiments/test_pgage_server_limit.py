"""PG+AGE: the visited probe has a time budget and the analytics queries have a server-side limit (mmdbbench#24).

Run with `python -m pytest test_pgage_server_limit.py -q -rs` from this directory.

Three PG+AGE cells of the 2611 pass never produced a row. At SF1 the timed reads were censored at their 540 s budgets and the
cell then sat in the untimed `visited probe` (20 start persons, one query each, no budget) until the 3600 s cap; at SF1-full
analytics single iterations ran 739.5 s, 801.7 s and 847.0 s against 60 to 300 s budgets, because the budget is checked only
between iterations and PgAgeGraph, unlike the Memgraph, ArangoDB and MongoDB adapters, had no server-side limit (DECISIONS #179).

Now `PgAgeGraph` runs each analytics statement and each probe query under `SET statement_timeout` and `RESET`s it afterwards.
SQLSTATE 57014 with the text "statement timeout" is a killed query (a censored measurement), and every other error still raises.
The probe stops at READ_WARMUP_BUDGET_SHARE of the hop3f read budget and records a censored answer, not a digest of the partial
list. Every other adapter runs as before.

The lane runs here, in-process, against stand-in adapters and a fake psycopg connection, in the style of
test_graph_server_limit.py. No engine is needed. Whether AGE honors statement_timeout inside a long operator, and how fast it
stops, is not answerable here: the first PG+AGE cell on the mini is the real-engine evidence.
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import equivalence_check as E  # noqa: E402
import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402
import page_check as P  # noqa: E402

TRI = "triangles"


class _Canceled(Exception):
    """What psycopg raises for SQLSTATE 57014 (psycopg.errors.QueryCanceled): `sqlstate` on the exception, the server's text."""

    def __init__(self, msg="canceling statement due to statement timeout", sqlstate="57014"):
        super().__init__(msg)
        self.sqlstate = sqlstate


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _FakeConn:
    """A psycopg connection to a server where a cypher() statement takes `cost(sql)` seconds.

    It keeps the session's `statement_timeout` the way PostgreSQL does (SET until RESET), so a statement that would run longer
    than the setting is cut at the setting and answers SQLSTATE 57014, and one with no setting runs to its end.
    """

    def __init__(self, cost=lambda sql: 0.0, fail=None):
        self.log = []              # every statement, in order
        self.timeout_ms = None     # the session's statement_timeout now
        self.seen_limits = []      # the statement_timeout in force when each cypher() statement started
        self.cost, self.fail = cost, fail
        self.closed = False

    def execute(self, sql, params=None):
        self.log.append(sql)
        s = sql.strip()
        if s.startswith("SET statement_timeout"):
            self.timeout_ms = int(s.split("=")[1])
            return _Result([])
        if s == "RESET statement_timeout":
            self.timeout_ms = None
            return _Result([])
        self.seen_limits.append(self.timeout_ms)
        if self.fail is not None:
            raise self.fail
        d = self.cost(s)
        if self.timeout_ms is not None and d * 1000.0 > self.timeout_ms:
            time.sleep(self.timeout_ms / 1000.0)
            raise _Canceled()
        time.sleep(d)
        return _Result([("7",) * 5])       # agtype text; run_cypher zips it onto the RETURN aliases

    def close(self):
        self.closed = True


def _pg(conn):
    ad = L.PgAgeGraph()
    ad.cx = conn
    ad._sql = {}
    return ad


# ---- the adapter, against a fake connection --------------------------------------------------------------------------

def test_the_olap_limit_is_set_before_the_statement_and_reset_after_it():
    conn = _FakeConn()
    ad = _pg(conn)
    ad.olap_limit_s = 300
    assert ad.run_olap(TRI) == [{"n": 7}]
    assert [conn.log[0], conn.log[-1]] == ["SET statement_timeout = 300000", "RESET statement_timeout"]
    assert len(conn.log) == 3 and "cypher(" in conn.log[1]          # the one statement the lane text is
    assert conn.seen_limits == [300000] and conn.timeout_ms is None


def test_the_limit_is_reset_when_the_server_cuts_the_statement_too():
    conn = _FakeConn(cost=lambda sql: 5.0)
    ad = _pg(conn)
    ad.olap_limit_s = 0.05
    with pytest.raises(G.QueryKilled):
        ad.run_olap(TRI)
    assert conn.log[0] == "SET statement_timeout = 50" and conn.log[-1] == "RESET statement_timeout"
    assert conn.timeout_ms is None                                      # the next statement is not cut by this one's limit


def test_sqlstate_57014_with_the_statement_timeout_text_is_a_killed_query_and_other_errors_still_raise():
    ad = _pg(_FakeConn(fail=_Canceled()))
    ad.olap_limit_s = 1
    with pytest.raises(G.QueryKilled):
        ad.run_olap(TRI)
    for err in (_Canceled("relation \"l2g.Person\" does not exist", sqlstate="42P01"),    # a real failure
                _Canceled("canceling statement due to user request"),                    # pg_cancel_backend: 57014, not our limit
                ConnectionError("reset by peer")):
        ad = _pg(_FakeConn(fail=err))
        ad.olap_limit_s = 1
        with pytest.raises(Exception) as ei:
            ad.run_olap(TRI)
        assert ei.value is err and not isinstance(ei.value, G.QueryKilled)
    assert G.is_pg_statement_timeout(_Canceled())
    assert not G.is_pg_statement_timeout(_Canceled("canceling statement due to user request"))
    assert not G.is_pg_statement_timeout(_Canceled("canceling statement due to statement timeout", sqlstate="57P01"))
    assert not G.is_pg_statement_timeout(ValueError("canceling statement due to statement timeout"))   # no SQLSTATE at all


def test_no_limit_means_the_call_is_the_old_one():
    conn = _FakeConn()
    ad = _pg(conn)
    assert ad.olap_limit_s is None and ad.visited_limit_s is None
    ad.run_olap(TRI)
    ad.run_visited(1)
    assert len(conn.log) == 2 and not any("statement_timeout" in s for s in conn.log)     # no SET, no RESET
    assert conn.seen_limits == [None, None]


def test_the_probe_query_runs_under_its_remaining_budget_and_the_server_kill_is_a_killed_query():
    conn = _FakeConn()
    ad = _pg(conn)
    ad.visited_limit_s = 120
    assert ad.run_visited(1) == [{"n": 7}]
    assert [conn.log[0], conn.log[-1]] == ["SET statement_timeout = 120000", "RESET statement_timeout"]
    conn = _FakeConn(cost=lambda sql: 5.0)
    ad = _pg(conn)
    ad.visited_limit_s = 0.05
    with pytest.raises(G.QueryKilled):
        ad.run_visited(1)
    assert conn.timeout_ms is None


# ---- the lane, end to end ------------------------------------------------------------------------------------------

ANSWER = {"point": [{"name": "p", "age": 40}], "hop1": [{"n": 3, "a": 41.0}], "hop2": [{"n": 9}], "hop3f": [{"n": 20}]}


def _stub_for(conn):
    """A PgAgeGraph whose connection is `conn` and whose load and interactive reads are stand-ins: run_visited and run_olap are
    the adapter's own, which is what these tests are about."""
    class _PgStub(L.PgAgeGraph):
        name = "stub_pgage"
        version = "stub"
        QUERY_LANGUAGE = "stub"

        def connect(self):
            self.cx, self._sql = conn, {}

        def build(self, n):
            for _ in L.gen_persons(n):
                pass
            for _ in L.gen_edges(n):
                pass

        def post_build(self, workload):
            pass

        def reopen(self):
            pass

        def run_read(self, op, pid):
            return ANSWER[op]

        def run_write(self, pid, new_id):
            pass

        def run_update(self, new_id):
            pass

        def run_delete(self, new_id):
            pass

        def person_scan(self, id_from):
            return []

        def edge_scan(self, id_from):
            return []
    return _PgStub


@pytest.fixture
def lane(monkeypatch, tmp_path):
    def run(stub, workload="oltp", **env):
        monkeypatch.setitem(L.ADAPTERS, stub.name, stub)
        monkeypatch.setattr(L, "CRUD_OPS", 10)
        monkeypatch.setenv("BENCH_CRUD_OPS", "10")
        monkeypatch.setattr(L, "OLAP_ITERATIONS", 3)
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        out = tmp_path / "row.json"
        monkeypatch.setattr(sys, "argv", ["l2_graph.py", "--backend", stub.name, "--workload", workload,
                                           "--scale", "micro", "--out", str(out)])
        L.main()
        return json.loads(out.read_text())
    return run


def test_the_probe_stops_at_its_budget_and_records_a_censored_answer_not_a_partial_digest(lane):
    # hop3f budget 1 s, so the probe budget is READ_WARMUP_BUDGET_SHARE of it (0.25 s). Each probe query takes 0.1 s: the third
    # is cut by the server at what is left of the budget.
    conn = _FakeConn(cost=lambda sql: 0.1)
    row = lane(_stub_for(conn), BENCH_GRAPH_READ_BUDGET_S=1)
    assert G.READ_WARMUP_BUDGET_SHARE == 0.25
    assert row["hop3_visited_budget_s"] == 0.25
    assert row["hop3_visited_error"].startswith("QueryKilled") and "statement_timeout" in row["hop3_visited_error"]
    assert row["hop3_visited_censored"] is True
    digest = row["res_hop3_visited_digest"]
    n_ids = row["hop3_visited_n_ids"]                                         # the probes that answered are still counted
    assert n_ids in (1, 2)                                                    # 2 unless the host stalled for 50 ms in between
    assert bench_common.is_censored_answer(digest) and "probe budget" in digest and f"{n_ids} of 20" in digest
    assert row["res_hop3_visited_sample"] == digest and row["res_hop3_visited_n"] is None
    assert "statement_timeout" in row["hop3_visited_server_limit"]
    limits = list(conn.seen_limits)
    assert len(limits) == n_ids + 1 and all(x is not None and 0 < x <= 250 for x in limits)
    assert limits == sorted(limits, reverse=True)                              # each probe is given what is left, not the whole budget
    assert conn.timeout_ms is None                                            # reset: the writes and the read-back are not cut by it


def test_a_probe_that_finishes_inside_its_budget_is_unchanged(lane):
    conn = _FakeConn()
    row = lane(_stub_for(conn), BENCH_GRAPH_READ_BUDGET_S=1)
    assert row["hop3_visited_n_ids"] == G.VISITED_SAMPLE == len(conn.seen_limits)
    assert not bench_common.is_censored_answer(row["res_hop3_visited_digest"]) and row["res_hop3_visited_n"] == G.VISITED_SAMPLE
    assert "hop3_visited_censored" not in row and "hop3_visited_error" not in row
    assert row["hop3_visited_budget_s"] == 0.25


def test_a_probe_with_no_server_limit_that_runs_over_its_budget_stops_between_probes(lane):
    class _Slow(L.Base):
        name = "stub_slow_probe"
        version = "stub"
        QUERY_LANGUAGE = "stub"
        VISITED_PROBE_LIMIT = True          # asks for the budget but has no server-side way to enforce it mid-query
        N = []

        def connect(self):
            self.N.clear()

        def build(self, n):
            for _ in L.gen_persons(n):
                pass
            for _ in L.gen_edges(n):
                pass

        def run_read(self, op, pid):
            return ANSWER[op]

        def run_visited(self, pid):
            self.N.append(self.visited_limit_s)
            time.sleep(0.1)
            return [{"n": 5}]

        def run_write(self, pid, new_id):
            pass

        def run_update(self, new_id):
            pass

        def run_delete(self, new_id):
            pass

        def person_scan(self, id_from):
            return []

        def edge_scan(self, id_from):
            return []

    row = lane(_Slow, BENCH_GRAPH_READ_BUDGET_S=1)
    assert 2 <= len(_Slow.N) <= 3 and all(0 < x <= 0.25 for x in _Slow.N)
    assert row["hop3_visited_censored"] is True and "hop3_visited_error" not in row   # no error: the budget ran out between probes
    assert "probe budget" in row["res_hop3_visited_digest"] and bench_common.is_censored_answer(row["res_hop3_visited_digest"])
    assert _Slow.N == sorted(_Slow.N, reverse=True)                           # each probe is handed what is left


def _plain_stub(visit):
    class _Plain(L.Base):
        name = "stub_plain_probe"
        version = "stub"
        QUERY_LANGUAGE = "stub"
        LIMITS = []
        N = [0]

        def connect(self):
            self.LIMITS.clear()
            self.N[0] = 0

        def build(self, n):
            for _ in L.gen_persons(n):
                pass
            for _ in L.gen_edges(n):
                pass

        def run_read(self, op, pid):
            return ANSWER[op]

        def run_visited(self, pid):
            self.LIMITS.append(self.visited_limit_s)
            self.N[0] += 1
            return visit(self.N[0])

        def run_write(self, pid, new_id):
            pass

        def run_update(self, new_id):
            pass

        def run_delete(self, new_id):
            pass

        def person_scan(self, id_from):
            return []

        def edge_scan(self, id_from):
            return []
    return _Plain


def test_another_engine_gets_no_probe_budget_and_no_new_field_when_the_probe_answers(lane):
    stub = _plain_stub(lambda n: [{"n": 5}])
    row = lane(stub, BENCH_GRAPH_READ_BUDGET_S=1)
    assert stub.LIMITS == [None] * G.VISITED_SAMPLE
    assert row["hop3_visited_n_ids"] == G.VISITED_SAMPLE and row["res_hop3_visited_n"] == G.VISITED_SAMPLE
    assert not any(k in row for k in ("hop3_visited_budget_s", "hop3_visited_censored", "hop3_visited_server_limit",
                                       "hop3_visited_error"))


def test_a_probe_error_on_any_engine_is_a_censored_answer_and_not_a_digest_of_the_partial_list(lane):
    def visit(n):
        if n == 3:
            raise ValueError("connection lost")
        return [{"n": 5}]
    row = lane(_plain_stub(visit), BENCH_GRAPH_READ_BUDGET_S=1)
    assert row["hop3_visited_error"] == "ValueError: connection lost"
    assert row["hop3_visited_n_ids"] == 2 and row["hop3_visited_censored"] is True
    digest = row["res_hop3_visited_digest"]
    assert bench_common.is_censored_answer(digest) and "ValueError" in digest and "2 of 20" in digest
    assert row["res_hop3_visited_n"] is None and "res_hop3_visited_profile" not in row


def test_the_analytics_lane_hands_pgage_the_budget_and_a_killed_query_is_a_censored_cell(lane):
    conn = _FakeConn(cost=lambda sql: 5.0 if G.OLAP_QUERIES[TRI] in sql else 0.0)
    row = lane(_stub_for(conn), workload="olap", BENCH_GRAPH_OLAP_BUDGET_S="0.3")
    assert row["olap_server_limit"] == L.PgAgeGraph.SERVER_LIMIT_STAMP and "statement_timeout" in row["olap_server_limit"]
    assert row[f"{TRI}_server_limit_s"] == 0.3 == row[f"{TRI}_budget_s"]
    assert "statement_timeout" in row[f"{TRI}_server_killed"] and "cold pass" in row[f"{TRI}_server_killed"]
    assert row[f"{TRI}_censored"] is True and row[f"{TRI}_iters"] == 0
    assert bench_common.is_censored_answer(row[f"res_{TRI}_digest"]) and row[f"res_{TRI}_n"] is None
    # the cell goes on: the other queries answered, each under the same limit, and the limit never outlives its statement
    assert row["top_degree_iters"] == 3 and row["res_top_degree_n"] == 1 and "top_degree_server_killed" not in row
    assert set(conn.seen_limits) == {300} and conn.timeout_ms is None
    sets = [s for s in conn.log if s.startswith("SET ")]
    assert len(sets) == len(conn.seen_limits) == conn.log.count("RESET statement_timeout")     # one SET and one RESET per statement


def test_the_new_row_fields_have_a_registry_entry_in_page_check(lane):
    conn = _FakeConn(cost=lambda sql: 0.1 if "count(DISTINCT" in sql else (5.0 if G.OLAP_QUERIES[TRI] in sql else 0.0))
    oltp = lane(_stub_for(conn), BENCH_GRAPH_READ_BUDGET_S=1)
    olap = lane(_stub_for(_FakeConn(cost=lambda sql: 5.0 if G.OLAP_QUERIES[TRI] in sql else 0.0)), workload="olap",
                BENCH_GRAPH_OLAP_BUDGET_S="0.3")
    new = [k for r in (oltp, olap) for k in r
           if k.startswith("hop3_visited_") or k == "olap_server_limit" or k.endswith(("_server_killed", "_server_limit_s"))]
    assert {"hop3_visited_budget_s", "hop3_visited_censored", "hop3_visited_server_limit", "hop3_visited_error",
            "olap_server_limit", f"{TRI}_server_killed", f"{TRI}_server_limit_s"} <= set(new)
    for k in new:
        assert P._not_printed_reason(k), f"{k} is a measured row field with no registry entry in page_check.NOT_PRINTED"
    assert "probe" in P._not_printed_reason("hop3_visited_budget_s")             # its own entry, not only the diagnostics family
    assert "probe" in P._not_printed_reason("hop3_visited_censored")


def test_a_censored_probe_answer_is_listed_by_the_equivalence_gate_where_a_partial_digest_failed_it(lane):
    conn = _FakeConn(cost=lambda sql: 0.1)
    row = lane(_stub_for(conn), BENCH_GRAPH_READ_BUDGET_S=1)
    base = {"lane": "l2", "scale": "micro", "workload": "oltp", "rc": 0, "rep": 1, "instrument": E.REQUIRED_INSTRUMENT,
            "durability_class": "relaxed"}
    full = {}
    bench_common.record_result(full, "hop3_visited", [(i, 5) for i in range(G.VISITED_SAMPLE)], **G.VISITED_DIGEST)
    partial = {}
    bench_common.record_result(partial, "hop3_visited", [(i, 5) for i in range(2)], **G.VISITED_DIGEST)
    pg = {**base, "backend": "pgage_graph", **{k: v for k, v in row.items() if k.startswith("res_hop3_visited_")}}
    other = {**base, "backend": "other_graph", **full}

    def report(rows):
        groups, _skipped, seen, _silent = E.collect(rows)
        lines = []
        bad, *_ = E.report(groups, seen, out=lines.append)
        return bad, "\n".join(lines)

    bad, text = report([pg, other])
    assert bad == 0 and "E4b" in text and "probe budget" in text
    # the control: the old row (a digest of the 2 answered starts beside another engine's 20) is a disagreement
    bad, text = report([{**base, "backend": "pgage_graph", **partial}, other])
    assert bad == 1 and "hop3_visited" in text


# ---- confinement: only PgAgeGraph changed -----------------------------------------------------------------------------

def test_the_server_side_limit_census_names_pgage_and_no_other_adapter_gained_one():
    declared = {L.ArangoGraph, L.MongoGraph, L.MemgraphGraph, L.PgAgeGraph}
    assert {c for c in L.ADAPTERS.values() if c.SERVER_SIDE_LIMIT is True} == declared
    assert L.PgAgeGraph.SERVER_LIMIT_NAME == "statement_timeout" and "statement_timeout" in L.PgAgeGraph.SERVER_LIMIT_STAMP
    for name, cls in L.ADAPTERS.items():
        if cls is not L.PgAgeGraph:
            assert getattr(cls, "VISITED_PROBE_LIMIT", False) is False, name       # no other engine is handed a probe budget
            assert getattr(cls, "visited_limit_s", None) is None, name


def test_every_other_adapters_probe_and_analytics_methods_are_the_ones_it_had():
    # By class, from origin/main: who OVERRIDES the two methods. A new override on any other adapter is a change to it.
    assert {c.__name__ for c in L.ADAPTERS.values() if "run_visited" in vars(c)} == {
        "DuckpgqGraph", "SurrealGraph", "ArangoGraph", "MongoGraph", "PgAgeGraph"}
    assert {c.__name__ for c in L.ADAPTERS.values() if "run_olap" in vars(c)} == {
        "MemgraphGraph", "FalkorGraph", "LadybugGraph", "DuckpgqGraph", "SurrealGraph", "ArangoGraph", "MongoGraph",
        "PgAgeGraph"}
    for cls in L.ADAPTERS.values():
        if cls is L.PgAgeGraph:
            continue
        if "run_visited" not in vars(cls) and cls.__mro__[1] in (L.Base, L.Neo4jGraph, L.ArcadeGraphEmbedded):
            assert cls.run_visited is L.Base.run_visited, cls.__name__
    assert L.Neo4jGraph.run_olap is L.Base.run_olap and L.ArcadeGraphEmbedded.run_olap is L.Base.run_olap


# ---- the PHASE line: a clock only when BENCH_PHASE_TS=1 ---------------------------------------------------------------

def _beat(monkeypatch, ts):
    monkeypatch.delenv("BENCH_MEMPROBE_DIR", raising=False)
    if ts is None:
        monkeypatch.delenv("BENCH_PHASE_TS", raising=False)
    else:
        monkeypatch.setenv("BENCH_PHASE_TS", ts)
    buf = io.StringIO()
    beat = bench_common.PhaseBeat(every_s=0.01, out=buf)
    monkeypatch.setattr(beat, "_rss_mib", lambda: 12.5)
    return beat, buf


def test_the_phase_line_is_exactly_the_old_one_without_the_stamp(monkeypatch):
    beat, buf = _beat(monkeypatch, None)
    beat.mark("visited-probe-start", n=20)
    beat.mark("reads-done")
    assert buf.getvalue() == "PHASE visited-probe-start n=20 rss=12.5MiB\nPHASE reads-done rss=12.5MiB\n"    # golden
    for off in ("", "0", "true"):                    # only the value 1 turns it on
        beat, buf = _beat(monkeypatch, off)
        beat.mark("reads-done")
        assert buf.getvalue() == "PHASE reads-done rss=12.5MiB\n", off


def test_the_running_beat_is_exactly_the_old_one_without_the_stamp(monkeypatch):
    beat, buf = _beat(monkeypatch, None)
    with beat.phase("build"):
        time.sleep(0.2)
    lines = buf.getvalue().splitlines()
    running = [x for x in lines if "-running" in x]
    assert running and all(re.fullmatch(r"PHASE build-running t=[0-9.]+s rss=12\.5MiB", x) for x in running)
    assert lines[0] == "PHASE build-start rss=12.5MiB" and re.fullmatch(r"PHASE build-done t=[0-9.]+s rss=12\.5MiB", lines[-1])


def test_with_the_stamp_every_phase_line_ends_in_a_utc_wall_clock(monkeypatch):
    beat, buf = _beat(monkeypatch, "1")
    beat.mark("visited-probe-start", n=20)
    assert re.fullmatch(r"PHASE visited-probe-start n=20 rss=12\.5MiB ts=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", buf.getvalue().strip())
    beat, buf = _beat(monkeypatch, "1")
    with beat.phase("build"):
        time.sleep(0.2)
    lines = buf.getvalue().splitlines()
    assert len(lines) >= 3 and all(re.search(r" ts=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", x) for x in lines)
    assert any("-running" in x for x in lines)                                 # the heartbeat carries it too
    old = re.sub(r" ts=\S+$", "", lines[0])
    assert old == "PHASE build-start rss=12.5MiB"                              # the stamp is the whole difference
