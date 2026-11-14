"""The PostgreSQL-wire twin of ArcadeDB's served SQL cells (DECISIONS #166, #171, #237; CAMPAIGN section 7 row 6).

Run with `python -m pytest test_pgwire_twin.py -q` from this directory. Nothing starts a server or a container: the wire is a fake psycopg, the server
launch is a dict, the stage generator only writes drafts.
"""
import datetime as dt
import decimal
import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import lean_http  # noqa: E402
import pgwire_gate as gate  # noqa: E402
import runner  # noqa: E402

# THE SERVED SQL CELLS, written out by hand and not read from runner.PGWIRE_SQL_ARMS, so a change to the table is a visible change to this list.
EXPECTED = {("l1", "arcadedb_server"), ("l1tpc", "arcadedb_server"),
            ("l3s", "arcadedb_sparse_server"), ("l3s", "arcadedb_sparse_server_fp32"),
            ("l3d", "arcadedb_dense_server"), ("l3d", "arcadedb_dense_server_int8"),
            ("l4", "arcadedb_ts_doc_server"), ("l4", "arcadedb_ts_native_server")}


# ------------------------------------------------------------------------------------------------------ which cells get the twin
def test_the_twin_is_emitted_for_exactly_the_served_sql_cells_at_the_small_tier():
    jobs = runner.build_jobs(list(runner.LANES), [], scale="tpch1")
    pg = [j for j in jobs if j.get("http_client") == "pgwire"]
    assert {(j["lane"], j["backend"]) for j in pg} == EXPECTED
    heads = {(j["lane"], j["backend"], j["workload"]) for j in jobs if not j.get("http_client")}
    # one twin per workload the headline runs, never more
    assert {(j["lane"], j["backend"], j["workload"]) for j in pg} == {h for h in heads if h[:2] in EXPECTED}
    assert all(j["run_id"].endswith("_clientpgwire") for j in pg)
    assert len({j["run_id"] for j in jobs}) == len(jobs)


@pytest.mark.parametrize("scale", ["deep10m", "tpch10", "sf1full"])
def test_the_large_tier_scales_get_no_wire_twin_and_keep_their_lean_twin(scale):
    """The twin re-runs the whole cell (load, index build, queries), so the large tier (the generator's LARGE_SCALES) would add hours for a sensitivity row."""
    jobs = runner.build_jobs(list(runner.LANES), [], scale=scale)
    assert not [j for j in jobs if j.get("http_client") == "pgwire"]
    assert [j for j in jobs if j.get("http_client") == "lean"]


def test_the_large_tier_is_the_generators_own_definition():
    import make_2611_stages as G
    assert runner.LARGE_SCALES == G.LARGE_SCALES and set(runner.LARGE_SCALES) == {"deep10m", "tpch10", "sf1full"}


def test_cypher_mixed_and_lifecycle_cells_have_no_pgwire_twin():
    jobs = runner.build_jobs(["l2", "e2", "lifecycle", "restart", "e4"], [])
    assert jobs and not [j for j in jobs if j.get("http_client") == "pgwire"]


def test_the_lean_twin_set_is_unchanged_and_the_wire_twin_is_a_third_job():
    jobs = runner.build_jobs(list(runner.LANES), [])
    lean = {(j["lane"], j["backend"], j["workload"]) for j in jobs if j.get("http_client") == "lean"}
    assert lean == {(j["lane"], j["backend"], j["workload"]) for j in jobs if j["backend"] in runner.ARCADEDB_HTTP_ARMS and not j.get("http_client")}
    assert {b for _, b in EXPECTED} <= set(runner.ARCADEDB_HTTP_ARMS)


def test_the_stage_generator_schedules_the_twin_for_exactly_the_served_sql_cells():
    import make_2611_stages as G
    engines = G.parse_engines(None, "arcadedb")
    specs = G.number(G.subset_specs(engines, G.parse_lanes(None, False, "paper-2611"), "biggest-last", G.profile_skip("paper-2611"), True), "qT")
    cells = {(c.lane, c.backend, c.workload) for spec in specs for c in G.stage_cells(spec)}
    assert cells
    scales = {(c.lane, c.backend, c.workload): set() for spec in specs for c in G.stage_cells(spec)}
    for spec in specs:
        for c in G.stage_cells(spec):
            scales[(c.lane, c.backend, c.workload)].add(c.scale)
    served = {c for c in cells if c[1] in runner.ARCADEDB_HTTP_ARMS}
    got, wired_scales = set(), set()
    for lane, be, wl in served:
        for sc in scales[(lane, be, wl)]:
            for j in runner.build_jobs([lane], [wl], scale=sc):
                if j["backend"] == be and j.get("http_client") == "pgwire":
                    got.add((lane, be, wl))
                    wired_scales.add(sc)
    assert {(l, b) for l, b, _ in got} <= EXPECTED and got
    # small-tier cells of the covered arms get it, large-tier ones (tpch10, deep10m) do not
    assert wired_scales == {"tpch1", "small"}
    assert all(c in got for c in served if c[:2] in EXPECTED and scales[c] - set(G.LARGE_SCALES))
    assert not [c for c in got if c[0] in ("l2", "e2")]


def test_a_resume_does_not_treat_a_twin_as_done_because_its_headline_is():
    assert runner._client_of_run_id("l1_arcadedb_server_oltp_clientpgwire_tiny_r1") == "pgwire"
    assert runner._client_of_run_id("l1_arcadedb_server_oltp_clientlean_tiny_r1") == "lean"
    assert runner._client_of_run_id("l1_arcadedb_server_oltp_tiny_r1") == ""


# ------------------------------------------------------------------------------------------------------ the role stamp
def test_the_selector_takes_pgwire_and_still_refuses_the_rest(monkeypatch):
    monkeypatch.setenv("BENCH_ARCADEDB_HTTP_CLIENT", "pgwire")
    assert lean_http.client_choice() == "pgwire"
    monkeypatch.setenv("BENCH_ARCADEDB_HTTP_CLIENT", "grpc")
    with pytest.raises(ValueError):
        lean_http.client_choice()


class _FakePg:
    """psycopg, as far as PgSession uses it; `log` records (sql, args) of every statement the wire got."""

    def __init__(self, monkeypatch, rows=None):
        self.log, self.rows, self.connects = [], rows if rows is not None else [{"a": 1}], []
        fake = self

        class Error(Exception):
            pass

        class Cur:
            description = [("a",)]

            def fetchall(self_):
                return list(fake.rows)

        class Conn:
            closed = False

            def execute(self_, sql, args=None):
                if "BOOM" in sql:
                    raise Error("syntax error at BOOM\nline 2")
                fake.log.append((sql, args))
                return Cur()

            def close(self_):
                self_.closed = True

        mod = types.ModuleType("psycopg")
        mod.__version__, mod.Error = "3.2.9", Error
        mod.pq = types.SimpleNamespace(__impl__="binary")
        mod.connect = lambda **kw: fake.connects.append(kw) or Conn()
        rowsmod = types.ModuleType("psycopg.rows")
        rowsmod.dict_row = "dict_row"
        monkeypatch.setitem(sys.modules, "psycopg", mod)
        monkeypatch.setitem(sys.modules, "psycopg.rows", rowsmod)


BASE = "http://10.0.0.5:2480/api/v1"


def _session(monkeypatch, **kw):
    fake = _FakePg(monkeypatch, **kw)
    s = lean_http.PgSession()
    s._beat = True                                         # no heartbeat thread in a unit test
    fallback = []
    s._fallback = types.SimpleNamespace(post=lambda url, **k: fallback.append(("post", url)) or "lean-post",
                                        get=lambda url, **k: fallback.append(("get", url)) or "lean-get", close=lambda: None)
    s.auth = ("root", "pw")
    return s, fake, fallback


def test_a_wire_row_is_a_sensitivity_row_with_the_wire_stamp_and_a_headline_is_not(monkeypatch):
    monkeypatch.setenv("BENCH_ARCADEDB_CLIENT_ROLE", "sensitivity")
    s, _, _ = _session(monkeypatch)
    got = lean_http.row_fields(s)
    assert got["arcadedb_http_client_role"] == "sensitivity" and got["arcadedb_client_wire"] == "pgwire"
    assert got["arcadedb_http_client"].startswith("psycopg 3.2.9 (PostgreSQL wire")
    assert got["arcadedb_pgwire_client"] == {"psycopg": "3.2.9", "prepare_threshold": None, "autocommit": True, "result_format": "text", "port": 5432}
    assert "read and query statements only" in got["arcadedb_pgwire_scope"]
    lean = lean_http.row_fields(lean_http.LeanSession())
    assert "arcadedb_client_wire" not in lean and lean["arcadedb_http_client_role"] == "sensitivity"


def test_the_runner_stamps_the_wire_on_a_job_that_never_reached_its_lane():
    src = (HERE / "runner.py").read_text()
    assert '**({"arcadedb_client_wire": PGWIRE_CLIENT} if job.get("http_client") == PGWIRE_CLIENT else {})' in src
    assert 'f"BENCH_ARCADEDB_PG_PORT={PGWIRE_PORT}"' in src


def test_the_factory_hands_a_wire_session_only_to_the_wire_twin(monkeypatch):
    _FakePg(monkeypatch)
    monkeypatch.setenv("BENCH_ARCADEDB_HTTP_CLIENT", "pgwire")
    assert isinstance(lean_http.Session(), lean_http.PgSession)
    monkeypatch.setenv("BENCH_ARCADEDB_HTTP_CLIENT", "lean")
    assert isinstance(lean_http.Session(), lean_http.LeanSession)


# ------------------------------------------------------------------------------------------------------ what goes over the wire
def test_a_sql_query_goes_over_the_wire_bound_and_the_rest_stays_on_http(monkeypatch):
    s, fake, fallback = _session(monkeypatch)
    r = s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "SELECT FROM T WHERE k = :k AND s LIKE '%:x%'", "params": {"k": 7}})
    assert r.ok and r.json()["result"] == [{"a": 1}] and r.json()["returned"] == 1
    assert fake.log == [("SELECT FROM T WHERE k = %(k)s AND s LIKE '%%:x%%'", {"k": 7})]
    kw = fake.connects[0]
    assert (kw["host"], kw["port"], kw["dbname"], kw["user"], kw["autocommit"], kw["prepare_threshold"]) == ("10.0.0.5", 5432, "bench", "root", True, None)
    base = f"{BASE}/command/bench"
    assert s.post(base, json={"language": "sql", "command": "INSERT"}) == "lean-post"                      # writes stay on HTTP
    assert s.post(f"{BASE}/batch/bench", data=b"x") == "lean-post"                                           # bulk loads stay on HTTP
    assert s.post(f"{BASE}/query/bench", json={"language": "cypher", "command": "MATCH (n) RETURN n"}) == "lean-post"   # Cypher stays on HTTP
    assert s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "x", "params": {"m": {"a": 1}}}) == "lean-post"   # a dict cannot be bound
    assert s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "x"}, headers={"arcadedb-session-id": "1"}) == "lean-post"
    assert s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "SELECT :gone", "params": {}}) == "lean-post"
    assert s.get(f"{BASE}/server?mode=basic") == "lean-get"
    assert s.pg_calls == 1 and s.fallback_calls == 7
    assert set(s.summary()["fallback_reasons"]) == {"command", "other-endpoint", "language-cypher", "param-type", "headers-or-raw-body", "param-missing", "get"}


def test_a_list_param_travels_as_a_bound_array_and_a_limit_truncates(monkeypatch):
    s, fake, _ = _session(monkeypatch, rows=[{"a": i} for i in range(5)])
    r = s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "SELECT :q", "params": {"q": [0.5, 1.5]}, "limit": 3})
    assert fake.log[0][1] == {"q": [0.5, 1.5]}
    assert r.json()["returned"] == 3 and r.json()["truncated"] is True


def test_a_server_error_is_a_500_answer_not_an_exception(monkeypatch):
    s, _, _ = _session(monkeypatch)
    r = s.post(f"{BASE}/query/bench", json={"language": "sql", "command": "BOOM"})
    assert r.status_code == 500 and not r.ok and r.json()["error"] == "syntax error at BOOM"
    with pytest.raises(lean_http.HTTPError):
        r.raise_for_status()


def test_an_ndjson_query_of_the_wire_twin_is_read_over_the_wire(monkeypatch):
    s, fake, fallback = _session(monkeypatch, rows=[{"a": 1}, {"a": 2}])
    assert lean_http.post_ndjson(s, f"{BASE}/query/bench", {"language": "sql", "command": "SELECT 1"}) == [{"a": 1}, {"a": 2}]
    assert fake.log and not fallback and s.pg_calls == 1
    s.post = lambda *a, **k: types.SimpleNamespace(raise_for_status=lambda: None, content=b'{"record":{"x":1}}\n{"stats":{"returned":1}}\n')
    assert lean_http.post_ndjson(s, f"{BASE}/command/bench", {"language": "sql", "command": "SELECT 1"}) == [{"x": 1}]   # not a query: HTTP


def test_pg_translate_binds_names_and_leaves_quoted_text_alone():
    assert lean_http.pg_translate("SELECT :a, ':b', \":c\", x::y", {"a": 1}) == ("SELECT %(a)s, ':b', \":c\", x::y", {"a": 1})
    assert lean_http.pg_translate("SELECT 1 % 2", None) == ("SELECT 1 % 2", {})
    assert lean_http.pg_translate("SELECT 1 % :a", {"a": 1})[0] == "SELECT 1 %% %(a)s"
    assert lean_http.pg_translate("SELECT :a", {}) is None


# ------------------------------------------------------------------------------------------------------ the plugin's settings
JVM_ARM = {"server_env": ["-e", "JAVA_OPTS=-Darcadedb.server.mode=development", "-e", "X=1"], "server_cmd": []}
NATIVE_ARM = {"server_env": [], "server_cmd": ["-Xmx4g", "-Darcadedb.server.mode=development"], "server_build": "native"}


def test_the_plugin_and_its_settings_are_added_to_the_twin_server_only():
    jvm = runner.pgwire_server_patch(JVM_ARM)
    opts = [e for e in jvm["server_env"] if str(e).startswith("JAVA_OPTS=")]
    assert len(opts) == 1
    for tok in runner.PGWIRE_SERVER_SETTINGS:
        assert f"-D{tok}" in opts[0]
    assert JVM_ARM["server_env"][1] == "JAVA_OPTS=-Darcadedb.server.mode=development"                       # the headline's launch is untouched
    nat = runner.pgwire_server_patch(NATIVE_ARM)
    assert all(f"-D{t}" in nat["server_cmd"] for t in runner.PGWIRE_SERVER_SETTINGS) and NATIVE_ARM["server_cmd"] == ["-Xmx4g", "-Darcadedb.server.mode=development"]
    with pytest.raises(SystemExit):
        runner.pgwire_server_patch(jvm)                                                                       # twice is refused
    for name, cfg in runner.BACKENDS.items():
        if name in runner.ARCADEDB_HTTP_ARMS:
            assert "arcadedb.postgres.port" not in json.dumps(cfg.get("server_env", [])), name               # no headline server carries it


def test_a_setting_the_engine_does_not_list_or_reports_otherwise_fails_the_twin():
    listed = {t.split("=", 1)[0]: t.split("=", 1)[1] for t in runner.PGWIRE_SERVER_SETTINGS}
    assert runner.pgwire_settings_problems(listed) == []
    listed["arcadedb.server.plugins"] = "AutoBackupSchedulerPlugin," + listed["arcadedb.server.plugins"]      # the server puts its own plugin first
    assert runner.pgwire_settings_problems(listed) == []
    assert runner.settings_problems(listed, {"arcadedb.server.plugins": runner.PGWIRE_PLUGIN_SETTING.split("=", 1)[1]}) == []
    gone = dict(listed)
    gone.pop("arcadedb.postgres.port")
    assert "did not list arcadedb.postgres.port" in runner.pgwire_settings_problems(gone)[0]
    other = dict(listed, **{"arcadedb.postgres.port": "5433"})
    assert "engine runs 5433" in runner.pgwire_settings_problems(other)[0]
    assert runner.pgwire_settings_problems(dict(listed, **{"arcadedb.server.plugins": "Other:x.Y"}))


def test_a_boolean_the_engine_reports_as_a_json_boolean_is_the_value_written():
    """GET /api/v1/server?mode=default sends a Boolean setting as a JSON boolean (GlobalConfiguration.publishableValue returns the Object), so json.load
    gives Python True/False, whose str() is 'True'/'False', not the 'true'/'false' of the -D token. The first mini pass failed every twin cell on it."""
    listed = {t.split("=", 1)[0]: t.split("=", 1)[1] for t in runner.PGWIRE_SERVER_SETTINGS}
    listed.update({"arcadedb.postgres.debug": False, "arcadedb.postgres.quotedIdentifiers": True,
                   "arcadedb.postgres.queryMaxRows": 1000000, "arcadedb.postgres.port": "5432"})
    assert runner.pgwire_settings_problems(listed) == []
    asked = {"arcadedb.postgres.debug": "false", "arcadedb.postgres.quotedIdentifiers": "true"}
    assert runner.settings_problems(listed, asked) == []
    # a real difference still fails, in both directions and through both callers
    assert runner.pgwire_settings_problems(dict(listed, **{"arcadedb.postgres.debug": True}))
    assert runner.pgwire_settings_problems(dict(listed, **{"arcadedb.postgres.quotedIdentifiers": False}))
    assert runner.settings_problems(dict(listed, **{"arcadedb.postgres.quotedIdentifiers": False}), asked)
    assert runner.settings_problems({"arcadedb.postgres.debug": False}, {"arcadedb.postgres.debug": "true"})
    assert not runner.setting_matches("arcadedb.postgres.debug", False, "true")
    # numeric and string settings are unchanged
    assert runner.setting_matches("arcadedb.postgres.queryMaxRows", 1000000, "1000000")
    assert not runner.setting_matches("arcadedb.postgres.queryMaxRows", 1000000, "1000001")
    assert runner.setting_matches("arcadedb.postgres.port", "5432", "5432")
    assert not runner.setting_matches("arcadedb.postgres.port", "5433", "5432")
    assert runner.setting_matches("arcadedb.txWalFlush", 0, "0") and not runner.setting_matches("arcadedb.txWalFlush", 1, "0")
    assert not runner.setting_matches("arcadedb.postgres.debug", "False", "false")      # a string is still compared as written


def test_the_cells_log_gives_the_calls_and_the_reasons():
    log = ('noise\nPGWIRE_SUMMARY {"fallback_calls": 9, "fallback_reasons": {"command": 9}, "pg_calls": 1}\nPGWIRE_FALLBACK command\n'
           'PGWIRE_SUMMARY {"fallback_calls": 30, "fallback_reasons": {"command": 20, "get": 10}, "pg_calls": 4000}\n')
    assert runner.pgwire_log_fields(log) == {"arcadedb_pgwire_calls": 4000, "arcadedb_pgwire_fallback_calls": 30,
                                             "arcadedb_pgwire_fallback_reasons": {"command": 20, "get": 10}}
    assert runner.pgwire_log_fields("PGWIRE_FALLBACK get\n") == {"arcadedb_pgwire_fallback_reasons": {"get": None}}
    assert runner.pgwire_log_fields("nothing") == {}


# ------------------------------------------------------------------------------------------------------ the answers-identical gate
def _row(wire=False, **dig):
    r = {"lane": "l1tpc", "scale": "tpch1", "workload": "olap", "backend": "arcadedb_server", "durability_class": "relaxed", "server_build": "jvm",
         "run_id": "x", "arcadedb_http_client_role": "sensitivity" if wire else "headline"}
    if wire:
        r["arcadedb_client_wire"] = "pgwire"
    r.update({f"res_{q}_digest": d for q, d in dig.items()})
    return r


def test_equal_digests_pass():
    res = gate.check(_row(True, q1="aaaa", q6="bbbb"), [_row(q1="aaaa", q6="bbbb"), _row(q1="aaaa", q6="bbbb")])
    assert res["status"] == "ok" and res["queries_checked"] == 2 and res["reasons"] == []


def test_an_unequal_digest_fails_the_twin_row_and_names_the_query():
    twin = _row(True, q1="aaaa", q6="cccc")
    res = gate.stamp(twin, [_row(q1="aaaa", q6="bbbb")])
    assert res["status"] == "failed" and "q6" in res["reasons"][0] and "cccc" in res["reasons"][0] and "bbbb" in res["reasons"][0]
    assert twin["error"].startswith("pg-wire answers differ from the headline: q6") and twin["arcadedb_pgwire_gate"]["status"] == "failed"


def test_a_query_the_wire_row_did_not_record_fails_it():
    res = gate.check(_row(True, q1="aaaa"), [_row(q1="aaaa", q6="bbbb")])
    assert res["status"] == "failed" and "recorded none" in res["reasons"][0]


def test_no_headline_digests_is_unchecked_and_never_a_pass():
    assert gate.check(_row(True, q1="aaaa"), [])["status"] == "unchecked"
    assert gate.check(_row(True, q1="aaaa"), [_row()])["status"] == "unchecked"
    other_cell = dict(_row(q1="aaaa"), scale="tpch10")
    assert gate.check(_row(True, q1="aaaa"), [other_cell])["status"] == "unchecked"
    twin = _row(True, q1="aaaa")
    gate.stamp(twin, [])
    assert "error" not in twin


def test_a_headline_that_disagrees_with_itself_leaves_that_query_unchecked():
    res = gate.check(_row(True, q1="aaaa", q6="bbbb"), [_row(q1="xxxx", q6="bbbb"), _row(q1="yyyy", q6="bbbb")])
    assert res["status"] == "ok" and res["queries_checked"] == 1 and "q1" in res["unchecked"][0]


def test_a_recall_lane_is_compared_by_recall_within_a_tolerance_and_says_so():
    head = [dict(_row(), lane="l3d", recall_at_10=r) for r in (0.95, 0.96, 0.97)]
    twin = dict(_row(True), lane="l3d")
    assert gate.check(dict(twin, recall_at_10=0.955), head)["status"] == "ok"
    bad = gate.check(dict(twin, recall_at_10=0.5), head)
    assert bad["status"] == "failed" and "0.5000" in bad["reasons"][0]
    assert gate.check(twin, head)["status"] == "unchecked"
    assert "not by digest" in gate.check(dict(twin, recall_at_10=0.96), head)["unchecked"][0]
    assert gate.check(dict(_row(True), recall_at_10=0.9), [_row()])["status"] == "unchecked"       # a lane with neither (l1) is never a pass


def test_a_declared_absence_is_not_a_digest():
    assert gate.digests({"res_q_digest": "unexpressible: no such operator", "res_r_digest": "abcd"}) == {"r": "abcd"}


def test_the_headlines_own_failed_or_twin_rows_are_not_the_reference():
    bad = dict(_row(q1="zzzz"), error="boom")
    lean = dict(_row(q1="zzzz"), arcadedb_http_client_role="sensitivity")
    assert gate.check(_row(True, q1="aaaa"), [bad, lean, _row(q1="aaaa")])["status"] == "ok"


def test_the_gate_compares_digests_taken_under_the_lanes_coercions():
    """What the wire changes is the Python TYPES (Decimal for a number, datetime for a timestamp, tuples for dicts); the lane's declared `coerce` makes
    both digests the same, and an uncoerced digest would not be: that is what the gate relies on, and why it compares the lane's own digests."""
    spec = dict(columns=("h", "v"), coerce={"h": "epoch_s", "v": "num"})
    http = [{"h": 1767225600, "v": 12.5}, {"h": 1767229200, "v": 3.0}]
    wire = [{"h": dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc), "v": decimal.Decimal("12.5")},
            {"h": dt.datetime(2026, 1, 1, 1, 0, tzinfo=dt.timezone.utc), "v": decimal.Decimal("3.0")}]
    a, b = bench_common.result_digest(http, **spec)["digest"], bench_common.result_digest(wire, **spec)["digest"]
    assert a == b
    assert gate.check(_row(True, q=b), [_row(q=a)])["status"] == "ok"
    wrong = [dict(wire[0], v=decimal.Decimal("12.6")), wire[1]]
    assert gate.check(_row(True, q=bench_common.result_digest(wrong, **spec)["digest"]), [_row(q=a)])["status"] == "failed"


def test_the_runner_stamps_the_gate_against_the_headline_rows_in_the_results_file(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in (_row(q1="aaaa"), _row(True, q1="aaaa"))) + "\n")
    ok, bad = _row(True, q1="aaaa"), _row(True, q1="bbbb")
    runner.pgwire_gate_stamp(ok, str(path))
    runner.pgwire_gate_stamp(bad, str(path))
    assert ok["arcadedb_pgwire_gate"]["status"] == "ok" and "error" not in ok
    assert bad["arcadedb_pgwire_gate"]["status"] == "failed" and "error" in bad
    runner.pgwire_gate_stamp(_row(True, q1="x"), str(tmp_path / "missing.jsonl"))                          # no file: unchecked, no exception


def test_the_file_gate_exits_1_on_a_failure_and_reads_every_headline_row(tmp_path, capsys):
    path = tmp_path / "runs.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in (_row(True, q1="bbbb"), _row(q1="aaaa"))) + "\n")      # the twin comes first in the file
    assert gate.main(["--rows", str(path)]) == 1
    assert "1 pg-wire twin rows, 1 failed" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------------ landing and export keep the headline
def test_the_freeze_sets_the_wire_twin_aside_and_the_export_has_no_wire_sentence():
    """The wire twin is measured and not published (DECISIONS #285): the freeze sets its rows aside with the vendor driver's, so no table,
    claim or page sentence sees them."""
    import make_paper_tables as M
    wire = {"arcadedb_http_client_role": "sensitivity", "arcadedb_client_wire": "pgwire", "arcadedb_http_client": "psycopg 3.2 (PostgreSQL wire)"}
    lean = {"arcadedb_http_client_role": "sensitivity", "arcadedb_http_client": "lean_http (http.client, keep-alive)"}
    assert M.is_official_client_row(wire) and not M.is_official_client_row(lean)
    assert "_PG_TWIN_ROWS" not in (HERE / "export_web.py").read_text()
