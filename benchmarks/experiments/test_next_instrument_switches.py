"""What BENCH_INSTRUMENT=2026-11 turns on (CAMPAIGN section 7 rows 72, 81, 82, 84 and the note under that table), and that unset keeps
2026-10 exactly: for each switch, one test under 2026-10 and one under 2026-11. An explicit variable overrides the default in both."""
import os
import subprocess
import sys
import types

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SWITCH_VARS = ("BENCH_INSTRUMENT", "BENCH_SPARSE_WARMUP", "BENCH_CPU_DMA_LATENCY_US", "BENCH_DENSE_ID_INDEX",
               "BENCH_ARCADEDB_HTTP_CLIENT", "BENCH_LARGE_RESULT_PATH", "BENCH_ARCADEDB_EMBEDDED_XMS",
               "BENCH_ARCADEDB_CLIENT_SENSITIVITY", "BENCH_ARCADEDB_CLIENT_ROLE")


def run(code, instrument=None, **env_vars):
    """Run `code` in a fresh interpreter with exactly these switch variables; returns (returncode, stdout, stderr)."""
    env = {k: v for k, v in os.environ.items() if k not in SWITCH_VARS}
    if instrument:
        env["BENCH_INSTRUMENT"] = instrument
    env.update(env_vars)
    r = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr


# ----------------------------------------------------------------------------------------------- the sparse warm-up (row 81)
WARM = "import l3_sparse as m; print(m.sparse_warmup_n())"


def test_sparse_warmup_stays_off_under_2026_10():
    assert run(WARM)[1] == "0"
    assert run(WARM, "2026-10")[1] == "0"


def test_sparse_warmup_defaults_on_under_2026_11():
    import bench_common
    assert run(WARM, "2026-11")[1] == str(bench_common.SPARSE_WARMUP_DEFAULT) == "1000"


def test_sparse_warmup_explicit_value_wins_in_both_instruments():
    assert run(WARM, "2026-10", BENCH_SPARSE_WARMUP="7")[1] == "7"
    assert run(WARM, "2026-11", BENCH_SPARSE_WARMUP="7")[1] == "7"
    assert run(WARM, "2026-11", BENCH_SPARSE_WARMUP="off")[1] == "0"
    assert run(WARM, "2026-11", BENCH_SPARSE_WARMUP="0")[1] == "0"
    assert run(WARM, "2026-10", BENCH_SPARSE_WARMUP="0")[0] != 0      # 2026-10 still refuses a non-positive count


def _warm_module(monkeypatch):
    sys.path.insert(0, HERE)
    import bench_common
    import l3_sparse
    monkeypatch.setattr(bench_common, "INSTRUMENT", "2026-11")
    return l3_sparse


def test_warmup_queries_are_the_datasets_extra_queries_and_never_the_timed_ones(monkeypatch):
    S = _warm_module(monkeypatch)
    allq = [([i], [1.0]) for i in range(30)]
    monkeypatch.setattr(S, "gen_queries", lambda n: allq[:n])
    got, src = S.disjoint_warmup_queries(10, 12, 1000)
    assert src == "extra_queries" and got == allq[12:22]
    assert not set(map(str, got)) & set(map(str, allq[:12]))


def test_warmup_falls_back_to_a_fixed_sample_of_documents_when_the_dataset_has_no_extra_queries(monkeypatch):
    S = _warm_module(monkeypatch)
    timed = [([i], [1.0]) for i in range(12)]
    monkeypatch.setattr(S, "gen_queries", lambda n: timed[:n])
    monkeypatch.setattr(S, "gen_docs", lambda n, *a, **k: iter([(i, [1000 + i], [0.5]) for i in range(n)]))
    a, src = S.disjoint_warmup_queries(10, 12, 500)
    b, _ = S.disjoint_warmup_queries(10, 12, 500)
    assert src == "document_sample" and a == b and len(a) == 10 and all(q[0][0] >= 1000 for q in a)


def test_the_lane_warms_up_on_disjoint_queries_under_2026_11_and_stamps_count_and_source(monkeypatch, tmp_path):
    S = _warm_module(monkeypatch)
    import test_idle_and_warmup as T
    warm = [([900 + i], [1.0]) for i in range(7)]
    monkeypatch.setattr(S, "disjoint_warmup_queries", lambda n, nt, nd: (warm[:n], "extra_queries"))
    monkeypatch.setenv(S.WARMUP_ENV, "7")
    row, calls = T._run_lane(monkeypatch, tmp_path)
    searches = [c for c in calls if c[0] == "search"]
    assert searches[:7] == [("search", tuple(q[0])) for q in warm] and searches[7:] == T.TIMED
    assert row["sparse_warmup_queries"] == 7 and row["sparse_warmup_source"] == "extra_queries"


# ------------------------------------------------------------------------------------------------ the idle-state hold (row 81)
DMA = "import runner as m; print(m.cpu_dma_latency_target())"


def test_cpu_dma_hold_stays_off_under_2026_10():
    assert run(DMA)[1] == "None"
    assert run(DMA, "2026-10")[1] == "None"


def test_cpu_dma_hold_defaults_to_the_target_under_2026_11():
    assert run(DMA, "2026-11")[1] == "0"


def test_cpu_dma_explicit_target_wins_in_both_instruments():
    assert run(DMA, "2026-10", BENCH_CPU_DMA_LATENCY_US="10")[1] == "10"
    assert run(DMA, "2026-11", BENCH_CPU_DMA_LATENCY_US="10")[1] == "10"
    assert run(DMA, "2026-11", BENCH_CPU_DMA_LATENCY_US="off")[1] == "None"
    assert run(DMA, "2026-10", BENCH_CPU_DMA_LATENCY_US="off")[0] != 0


# ------------------------------------------------------------------------------------------------------ the dense id index (row 84)
IDX = "import l3d_dense as m; print(m.id_index_enabled())"


def test_dense_id_index_stays_off_under_2026_10():
    assert run(IDX)[1] == "False"
    assert run(IDX, "2026-10")[1] == "False"


def test_dense_id_index_defaults_on_under_2026_11():
    assert run(IDX, "2026-11")[1] == "True"


def test_dense_id_index_explicit_value_wins_in_both_instruments():
    assert run(IDX, "2026-10", BENCH_DENSE_ID_INDEX="1")[1] == "True"
    assert run(IDX, "2026-11", BENCH_DENSE_ID_INDEX="1")[1] == "True"
    assert run(IDX, "2026-11", BENCH_DENSE_ID_INDEX="0")[1] == "False"
    assert run(IDX, "2026-10", BENCH_DENSE_ID_INDEX="0")[0] != 0


# ------------------------------------------------------------------------------------------ the served client and its twins (rows 72, 82)
CLIENT = "import lean_http as m; print(m.client_choice())"


def test_served_client_stays_lean_under_2026_10():
    assert run(CLIENT)[1] == "lean"
    assert run(CLIENT, "2026-10")[1] == "lean"


def test_served_client_is_the_official_driver_under_2026_11():
    assert run(CLIENT, "2026-11")[1] == "official"


def test_served_client_explicit_value_wins_in_both_instruments():
    for inst in ("2026-10", "2026-11"):
        for v in ("lean", "lean2", "requests", "official"):
            assert run(CLIENT, inst, BENCH_ARCADEDB_HTTP_CLIENT=v)[1] == v


JOBS = ("import runner as m\n"
        "j = m.build_jobs(list(m.LANES), [])\n"
        "tw = [x for x in j if x.get('http_client')]\n"
        "print(len(tw), sorted({x['backend'] for x in tw}) == sorted({x['backend'] for x in j if x['backend'] in m.ARCADEDB_HTTP_ARMS}),\n"
        "      all(x['run_id'].endswith('_clientlean') for x in tw), len({x['run_id'] for x in j}) == len(j))")


def test_no_sensitivity_twin_cells_under_2026_10():
    out = run(JOBS, "2026-10")[1].split()
    assert out[0] == "0" and out[3] == "True"


def test_every_served_arcadedb_arm_has_a_lean_twin_under_2026_11():
    out = run(JOBS, "2026-11")[1].split()
    assert int(out[0]) > 0 and out[1:] == ["True", "True", "True"]


def test_twin_cells_follow_the_explicit_switch_in_both_instruments():
    assert run(JOBS, "2026-11", BENCH_ARCADEDB_CLIENT_SENSITIVITY="0")[1].split()[0] == "0"
    assert int(run(JOBS, "2026-10", BENCH_ARCADEDB_CLIENT_SENSITIVITY="1")[1].split()[0]) > 0


def test_runner_forwards_the_instrument_and_the_new_switches_to_the_cell():
    src = open(os.path.join(HERE, "runner.py")).read()
    for v in ("BENCH_INSTRUMENT", "BENCH_LARGE_RESULT_PATH", "BENCH_ARCADEDB_EMBEDDED_XMS"):
        assert f'"{v}"' in src


def _fake_driver(monkeypatch, calls):
    class ArcadeDBError(Exception):
        def __init__(self, status):
            super().__init__(f"status {status}")
            self.status, self.error, self.detail, self.exception = status, "boom", None, None

    env = types.SimpleNamespace(result=[{"a": 1}], limit=-1, returned=1, truncated=False)

    class DB:
        def __init__(self, name):
            self.name = name

        def query(self, **kw):
            calls.append(("query", self.name, kw))
            return env

        def command(self, **kw):
            calls.append(("command", self.name, kw))
            if kw["command"] == "FAIL":
                raise ArcadeDBError(500)
            return env

    class Server:
        def __init__(self, base_url, auth):
            self.base_url, self.auth = base_url, auth

        def db(self, name):
            return DB(name)

        def close(self):
            pass

    mod = types.ModuleType("arcadedb_driver")
    mod.ArcadeDBServer, mod.ArcadeDBError, mod.__version__ = Server, ArcadeDBError, "0.2.0"
    auth = types.ModuleType("arcadedb_driver.auth")
    auth.basic_auth = lambda u, p: {"Authorization": f"{u}:{p}"}
    monkeypatch.setitem(sys.modules, "arcadedb_driver", mod)
    monkeypatch.setitem(sys.modules, "arcadedb_driver.auth", auth)


def test_official_session_sends_query_and_command_through_the_driver_and_the_rest_through_lean(monkeypatch):
    sys.path.insert(0, HERE)
    import lean_http
    calls = []
    _fake_driver(monkeypatch, calls)
    s = lean_http.OfficialSession()
    fallback = []
    s._fallback = types.SimpleNamespace(
        post=lambda url, **kw: fallback.append(("post", url)) or "lean-post",
        get=lambda url, **kw: fallback.append(("get", url)) or "lean-get", close=lambda: None)
    s.auth = ("root", "pw")
    base = "http://h:2480/api/v1"
    r = s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1", "limit": 5})
    assert r.status_code == 200 and r.json()["result"] == [{"a": 1}] and r.ok
    assert calls[-1] == ("query", "bench", {"language": "sql", "command": "SELECT 1", "params": None, "limit": 5})
    s.post(f"{base}/command/bench", json={"language": "sql", "command": "INSERT", "params": {"x": 1}})
    assert calls[-1][0] == "command" and calls[-1][2]["params"] == {"x": 1}
    assert s.post(f"{base}/batch/bench?wal=true", data=b"x") == "lean-post"                 # bulk load stays on HTTP batch
    assert s.post(f"{base}/begin/bench") == "lean-post"                                     # transactions are not the driver's data plane here
    assert s.post(f"{base}/query/bench", json={"language": "sql", "command": "x"}, headers={"arcadedb-session-id": "1"}) == "lean-post"
    assert s.post(f"{base}/command/bench", json={"language": "sql", "command": "x", "limit": 3}) == "lean-post"   # the driver's command() has no limit
    assert s.get(f"{base}/server?mode=basic") == "lean-get"
    assert (s.official_calls, s.fallback_calls) == (2, 5)
    bad = s.post(f"{base}/command/bench", json={"language": "sql", "command": "FAIL"})
    assert bad.status_code == 500 and not bad.ok
    with pytest.raises(lean_http.HTTPError):
        bad.raise_for_status()
    assert lean_http.row_fields(s) == {"arcadedb_http_client": "arcadedb-driver 0.2.0 (sync, httpx)",
                                       "arcadedb_http_client_role": "headline"}


def test_a_lean_row_carries_no_role_unless_the_runner_made_it_a_twin(monkeypatch):
    sys.path.insert(0, HERE)
    import lean_http
    monkeypatch.delenv("BENCH_ARCADEDB_CLIENT_ROLE", raising=False)
    assert set(lean_http.row_fields(lean_http.LeanSession())) == {"arcadedb_http_client"}
    monkeypatch.setenv("BENCH_ARCADEDB_CLIENT_ROLE", "sensitivity")
    assert lean_http.row_fields(lean_http.LeanSession())["arcadedb_http_client_role"] == "sensitivity"


# ----------------------------------------------------------------------------------------------- the large-result read path (DECISIONS)
PATH = "import bench_common as m; print(m.large_result_path())"


def test_large_results_stay_on_rows_under_2026_10():
    assert run(PATH)[1] == "rows"
    assert run(PATH, "2026-10")[1] == "rows"


def test_large_results_use_the_documented_bulk_path_under_2026_11():
    assert run(PATH, "2026-11")[1] == "arrow"


def test_large_result_path_explicit_value_wins_in_both_instruments():
    assert run(PATH, "2026-10", BENCH_LARGE_RESULT_PATH="arrow")[1] == "arrow"
    assert run(PATH, "2026-11", BENCH_LARGE_RESULT_PATH="rows")[1] == "rows"
    assert run(PATH, "2026-11", BENCH_LARGE_RESULT_PATH="x")[0] != 0


BULK = """
import l4_tsbs as m
class Table:
    num_rows = 2
    def to_pylist(self): return [{"host": "h", "ts": 1, "uu": 2.0}, {"host": "h", "ts": 2, "uu": 3.0}]
class RS:
    def __init__(self, table): self.t = table
    def to_arrow(self): return self.t
    def to_list(self): return ["row", "row"]
a = m.ArcadeTS()
r = a._large(RS(Table()))
print(type(r).__name__, len(r), (list(r)[0]["host"] if hasattr(r, "table") else "-"), a.read_path_fields()["read_path"])
a2 = m.ArcadeTS()
r2 = a2._large(RS(None))
print(type(r2).__name__, a2.read_path_fields().get("read_path"), a2.read_path_fields().get("read_path_arrow_missing"))
print(m.ArcadeTSServer.bulk_read, m.ArcadeNativeTSServer.bulk_read, m.ArcadeNativeTS.bulk_read, m.DuckTS.bulk_read, hasattr(m.SQLiteTS, "bulk_read"))
"""


def test_l4_reads_large_results_as_rows_under_2026_10():
    code, out, err = run(BULK, "2026-10")
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == "list 2 - rows"


def test_l4_reads_large_results_as_arrow_under_2026_11_and_says_when_it_could_not():
    code, out, err = run(BULK, "2026-11")
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == "ArrowResult 2 h arrow"
    assert lines[1] == "list rows True"
    assert lines[2] == "False False True True False"


# -------------------------------------------------------------------------------------------- the embedded JVM's -Xms (DECISIONS, bindings)
XMS = "import bench_common as m; print(repr(m.embedded_xms('4g')), repr(m.embedded_jvm_args('4g', '-Dx=1', '')))"


def test_embedded_arms_pin_xms_under_2026_10():
    assert run(XMS)[1] == "'-Xms4g' '-Xms4g -Dx=1'"
    assert run(XMS, "2026-10")[1] == "'-Xms4g' '-Xms4g -Dx=1'"


def test_embedded_arms_leave_xms_unset_under_2026_11():
    assert run(XMS, "2026-11")[1] == "'' '-Dx=1'"


def test_embedded_xms_explicit_value_wins_in_both_instruments():
    assert run(XMS, "2026-11", BENCH_ARCADEDB_EMBEDDED_XMS="pin")[1] == "'-Xms4g' '-Xms4g -Dx=1'"
    assert run(XMS, "2026-10", BENCH_ARCADEDB_EMBEDDED_XMS="unset")[1] == "'' '-Dx=1'"
    assert run(XMS, "2026-10", BENCH_ARCADEDB_EMBEDDED_XMS="x")[0] != 0


def test_no_embedded_arm_hardcodes_xms_and_the_servers_keep_theirs():
    for f in ("l1_tabular.py", "l2_graph.py", "l3_sparse.py", "l3d_dense.py", "l4_tsbs.py", "l1_tpc.py", "e2_hybrid.py", "l5_lifecycle.py"):
        src = open(os.path.join(HERE, f)).read()
        assert 'f"-Xms{heap}' not in src, f
    runner = open(os.path.join(HERE, "runner.py")).read()
    assert runner.count("ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}") >= 5      # served ArcadeDB keeps its pin
    assert runner.count("ES_JAVA_OPTS=-Xms{heap} -Xmx{heap}") >= 2               # Elasticsearch keeps its own
