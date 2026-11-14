"""What the 2026-11 instrument measures (CAMPAIGN section 7 rows 72, 81, 82, 84 and the note under that table): each method choice is the
default, with nothing to switch on. Only the two numeric overrides PROTOCOL.md section 7 documents (the warm-up count, the idle-hold target)
and the runner's own client selector for the sensitivity twin remain as variables."""
import os
import subprocess
import sys
import types

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SWITCH_VARS = ("BENCH_INSTRUMENT", "BENCH_SPARSE_WARMUP", "BENCH_CPU_DMA_LATENCY_US",
               "BENCH_ARCADEDB_HTTP_CLIENT", "BENCH_ARCADEDB_CLIENT_ROLE")


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


def test_sparse_warmup_defaults_to_one_full_round():
    import bench_common
    assert run(WARM)[1] == str(bench_common.SPARSE_WARMUP_DEFAULT) == "1000"
    assert run(WARM, "2026-11")[1] == "1000"


def test_sparse_warmup_explicit_count_wins_and_it_cannot_be_turned_off():
    assert run(WARM, BENCH_SPARSE_WARMUP="7")[1] == "7"
    for bad in ("off", "0", "-3", "many"):
        assert run(WARM, BENCH_SPARSE_WARMUP=bad)[0] != 0


def _warm_module(monkeypatch):
    sys.path.insert(0, HERE)
    import l3_sparse
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


def test_the_lane_warms_up_on_disjoint_queries_and_stamps_count_and_source(monkeypatch, tmp_path):
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


def test_cpu_dma_hold_defaults_to_the_target():
    assert run(DMA)[1] == "0"
    assert run(DMA, "2026-11")[1] == "0"


def test_cpu_dma_explicit_target_wins_and_the_hold_cannot_be_turned_off():
    assert run(DMA, BENCH_CPU_DMA_LATENCY_US="10")[1] == "10"
    assert run(DMA, BENCH_CPU_DMA_LATENCY_US="off")[0] != 0


# ------------------------------------------------------------------------------------------------------ the dense id index (row 84)
def test_every_dense_adapter_builds_the_id_index_unconditionally():
    src = open(os.path.join(HERE, "l3d_dense.py")).read()
    assert "id_index_enabled" not in src and "BENCH_DENSE_ID_INDEX" not in src
    assert src.count("self.id_index = self.ID_INDEX_DDL") >= 7       # the seven engines that lacked a key


# ------------------------------------------------------------------------------------------ the served client and its twins (rows 72, 82)
CLIENT = "import lean_http as m; print(m.client_choice())"


def test_served_client_is_the_official_driver_by_default():
    assert run(CLIENT)[1] == "official"


def test_served_client_selector_takes_official_or_lean_only():
    for v in ("lean", "official"):
        assert run(CLIENT, BENCH_ARCADEDB_HTTP_CLIENT=v)[1] == v
    for v in ("lean2", "requests"):
        assert run(CLIENT, BENCH_ARCADEDB_HTTP_CLIENT=v)[0] != 0


JOBS = ("import runner as m\n"
        "j = m.build_jobs(list(m.LANES), [])\n"
        "tw = [x for x in j if x.get('http_client') == 'lean']\n"
        "print(len(tw), sorted({x['backend'] for x in tw}) == sorted({x['backend'] for x in j if x['backend'] in m.ARCADEDB_HTTP_ARMS}),\n"
        "      all(x['run_id'].endswith('_clientlean') for x in tw), len({x['run_id'] for x in j}) == len(j))")


def test_every_served_arcadedb_arm_has_a_lean_twin():
    out = run(JOBS)[1].split()
    assert int(out[0]) > 0 and out[1:] == ["True", "True", "True"]


def test_runner_always_forwards_the_instrument_and_the_twin_selects_the_lean_client():
    src = open(os.path.join(HERE, "runner.py")).read()
    assert 'f"BENCH_INSTRUMENT={bench_common.INSTRUMENT}"' in src          # from the host's own value, never left to the container's default
    assert "BENCH_ARCADEDB_CLIENT_SENSITIVITY" not in src
    assert 'f"BENCH_ARCADEDB_HTTP_CLIENT={job[\'http_client\']}"' in src


def _fake_driver(monkeypatch, calls, version="0.4.0"):
    class ArcadeDBError(Exception):
        def __init__(self, status):
            super().__init__(f"status {status}")
            self.status, self.error, self.detail, self.exception = status, "boom", None, None

    env = types.SimpleNamespace(result=[{"a": 1}], limit=-1, returned=1, truncated=False)

    class HttpxTimeoutException(Exception):
        pass

    class HttpxTransportError(Exception):
        pass

    class Timeout:
        def __init__(self, v):
            self.v = v

    httpx = types.ModuleType("httpx")
    httpx.Timeout, httpx.TimeoutException, httpx.TransportError = Timeout, HttpxTimeoutException, HttpxTransportError
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    class DB:
        def __init__(self, name, timeout=None):
            self.name, self.timeout = name, timeout

        def query(self, **kw):
            calls.append(("query", self.name, kw))
            if kw["command"] == "SLOW":
                raise HttpxTimeoutException("read timed out")
            if kw["command"] == "DOWN":
                raise HttpxTransportError("connection refused")
            return env

        def command(self, **kw):
            calls.append(("command", self.name, kw))
            if kw["command"] == "FAIL":
                raise ArcadeDBError(500)
            return env

    class Server:
        made = []          # every server built, so a test can count them

        def __init__(self, base_url, auth, timeout=None):
            self.base_url, self.auth, self.timeout = base_url, auth, timeout
            Server.made.append(self)
            self.db_calls = 0

        def db(self, name):
            self.db_calls += 1
            return DB(name, self.timeout)

        def close(self):
            pass

    mod = types.ModuleType("arcadedb_driver")
    mod.ArcadeDBServer, mod.ArcadeDBError, mod.__version__ = Server, ArcadeDBError, version
    mod.Server = Server
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
    assert s.post(f"{base}/command/bench", json={"language": "sql", "command": "x", "limit": 3}).status_code == 200   # 0.3.0 gave command() a limit
    assert calls[-1] == ("command", "bench", {"language": "sql", "command": "x", "params": None, "limit": 3})
    assert s.post(f"{base}/command/bench", json={"language": "sql", "command": "x", "other": 1}) == "lean-post"   # a field the driver has no argument for
    assert s.get(f"{base}/server?mode=basic") == "lean-get"
    assert (s.official_calls, s.fallback_calls) == (3, 5)
    bad = s.post(f"{base}/command/bench", json={"language": "sql", "command": "FAIL"})
    assert bad.status_code == 500 and not bad.ok
    with pytest.raises(lean_http.HTTPError):
        bad.raise_for_status()
    assert lean_http.row_fields(s) == {"arcadedb_http_client": "arcadedb-driver 0.4.0 (sync, httpx)",
                                       "arcadedb_http_client_role": "headline"}


def _official(monkeypatch):
    sys.path.insert(0, HERE)
    import lean_http
    calls = []
    _fake_driver(monkeypatch, calls)
    s = lean_http.OfficialSession()
    s.auth = ("root", "pw")
    return lean_http, s, calls, sys.modules["arcadedb_driver"].Server


def test_official_session_builds_one_db_handle_per_root_auth_timeout_and_database(monkeypatch):
    lean_http, s, calls, Server = _official(monkeypatch)
    base = "http://h:2480/api/v1"
    for _ in range(5):
        s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"})
        s.post(f"{base}/command/bench", json={"language": "sql", "command": "INSERT"})
    assert len(Server.made) == 1 and Server.made[0].db_calls == 1                  # ten calls, one server, one db() (the URL cache survives)
    s.post(f"{base}/query/other", json={"language": "sql", "command": "SELECT 1"})
    assert len(Server.made) == 1 and Server.made[0].db_calls == 2                  # another database: another handle, same server
    s.post("http://h2:2480/api/v1/query/bench", json={"language": "sql", "command": "SELECT 1"})
    s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, auth=("u", "p"))
    assert len(Server.made) == 3                                                    # another root, another login: another server
    s.close()
    assert not s._servers and not s._dbs


def test_official_session_forwards_the_call_timeout_to_the_driver_as_an_httpx_timeout(monkeypatch):
    lean_http, s, calls, Server = _official(monkeypatch)
    base = "http://h:2480/api/v1"
    s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"})                       # no timeout: the driver's own None
    s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, timeout=600)
    s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, timeout=600.0)       # the same value: the same server
    s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, timeout=30)
    assert [x.timeout.v for x in Server.made] == [None, 600.0, 30.0]
    assert s.official_calls == 4 and s.fallback_calls == 0
    s._fallback = types.SimpleNamespace(post=lambda url, **kw: ("lean", kw["timeout"]), get=None, close=lambda: None)
    assert s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, timeout=(3, 9)) == ("lean", (3, 9))   # not a number: lean
    assert s.post(f"{base}/query/bench", json={"language": "sql", "command": "SELECT 1"}, timeout=True) == ("lean", True)


def test_official_session_raises_this_modules_errors_for_a_timeout_and_a_dead_connection(monkeypatch):
    lean_http, s, calls, Server = _official(monkeypatch)
    base = "http://h:2480/api/v1"
    with pytest.raises(lean_http.Timeout) as e:
        s.post(f"{base}/query/bench", json={"language": "sql", "command": "SLOW"}, timeout=5)
    assert isinstance(e.value, TimeoutError) and "5.0 s" in str(e.value)
    with pytest.raises(lean_http.ConnectionError):
        s.post(f"{base}/query/bench", json={"language": "sql", "command": "DOWN"})


def test_the_pin_is_0_4_0_and_a_driver_of_another_release_is_refused(monkeypatch):
    sys.path.insert(0, HERE)
    import lean_http
    assert lean_http.OFFICIAL_PIN == "0.4.0"
    _fake_driver(monkeypatch, [], version="0.2.0")
    with pytest.raises(RuntimeError, match="0.2.0.*pins 0.4.0.*client-arcadedb"):
        lean_http.OfficialSession()
    _fake_driver(monkeypatch, [], version=lean_http.OFFICIAL_PIN)
    assert lean_http.OfficialSession().client_name == f"arcadedb-driver {lean_http.OFFICIAL_PIN} (sync, httpx)"


def test_a_lean_row_carries_no_role_unless_the_runner_made_it_a_twin(monkeypatch):
    sys.path.insert(0, HERE)
    import lean_http
    monkeypatch.delenv("BENCH_ARCADEDB_CLIENT_ROLE", raising=False)
    assert set(lean_http.row_fields(lean_http.LeanSession())) == {"arcadedb_http_client"}
    monkeypatch.setenv("BENCH_ARCADEDB_CLIENT_ROLE", "sensitivity")
    assert lean_http.row_fields(lean_http.LeanSession())["arcadedb_http_client_role"] == "sensitivity"


# ----------------------------------------------------------------------------------------------- the large-result read path (DECISIONS)
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


def test_l4_reads_large_results_as_arrow_and_says_when_it_could_not():
    code, out, err = run(BULK)
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == "ArrowResult 2 h arrow"
    assert lines[1] == "list rows True"
    assert lines[2] == "False False True True False"


# -------------------------------------------------------------------------------------------- the embedded JVM's -Xms (DECISIONS, bindings)
def test_no_arcadedb_arm_pins_xms_and_the_other_servers_keep_theirs():
    for f in ("l1_tabular.py", "l2_graph.py", "l3_sparse.py", "l3d_dense.py", "l4_tsbs.py", "l1_tpc.py", "e2_hybrid.py", "l5_lifecycle.py"):
        src = open(os.path.join(HERE, f)).read()
        assert "-Xms{" not in src, f
    runner = open(os.path.join(HERE, "runner.py")).read()
    assert "ARCADEDB_OPTS_MEMORY=-Xms" not in runner                              # served ArcadeDB leaves -Xms unset too (DECISIONS #200)
    assert runner.count("ARCADEDB_OPTS_MEMORY=-Xmx{heap}") >= 5                   # and keeps -Xmx from the tier heap
    assert runner.count("ES_JAVA_OPTS=-Xms{heap} -Xmx{heap}") >= 2               # Elasticsearch keeps its own
