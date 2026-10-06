#!/usr/bin/env python3
"""The e4 deployment decomposition names its HTTP client and measures both (CAMPAIGN section 7 row 72, addendum).

Run with `python -m pytest test_e4_client_axis.py -q -rs` from this directory (needs numpy for the export_web tests and `requests` for the
parity ones; both skip with a reason without them).

Before the addendum the decomposition's three arms (embedded, in-process server over HTTP, server in a container) were timed through ONE Python
client, the probe's own session: requests where it imports, and the urllib shim e4_decomp.py installs where it does not. The e4 cell's image
(dbbench:arcadedb) has no requests, so the cell's client was the shim, which opens a new connection for every call. The served cells moved to
lean_http's persistent connection, so the table's "HTTP costs X over in-process" no longer described anything a served cell pays. These tests pin
what replaced it: lean_http takes the per-call `auth=` the probe passes, every HTTP arm is measured under both clients in one rotating
interleave, the artifact names the client of every arm and records it on the measurement, the row lists the clients, and the page table names
the client in each HTTP column (an artifact measured before the axis existed keeps its three columns).
"""
import importlib.util
import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lean_http as LH  # noqa: E402

requests = pytest.importorskip("requests", reason="the parity tests compare against requests")
pytest.importorskip("numpy")


# ------------------------------------------------------------------------------------------------ a stub ArcadeDB endpoint
class Stub(ThreadingHTTPServer):
    """Answers the four calls the probe makes. It insists on one password, so a client that sent the wrong per-call credentials fails."""
    daemon_threads = True

    def __init__(self, password):
        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                self.connection.setsockopt(__import__("socket").IPPROTO_TCP, __import__("socket").TCP_NODELAY, 1)

            def log_message(self, *a):
                pass

            def _go(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                srv = self.server
                srv.seen.append((self.command, self.path, dict(self.headers), body))
                import base64
                want = "Basic " + base64.b64encode(f"root:{srv.password}".encode()).decode()
                if self.headers.get("Authorization") != want:
                    out, code = b'{"error": "unauthorized"}', 401
                elif self.path.startswith("/api/v1/query/"):
                    req = json.loads(body)
                    k = int(req["command"].rsplit("LIMIT", 1)[1])
                    out, code = json.dumps({"result": _rows(k)}).encode(), 200
                elif self.path.startswith("/api/v1/server") and self.command == "GET":
                    out, code = b'{"version": "stub"}', 200
                else:
                    out, code = b"{}", 200
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            do_GET = do_POST = _go

        super().__init__(("127.0.0.1", 0), H)
        self.password, self.seen = password, []

    def handle_error(self, request, client_address):
        pass

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server_address[1]}"


def _rows(k):
    return [{"id": i, "customer_id": i % 1000, "amount": (i * 37 % 100000) / 100.0, "region": f"r{i % 8}"} for i in range(k)]


@pytest.fixture
def stub():
    srv = Stub("dbbenchpass")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


# ------------------------------------------------------------------------------------------------------ lean_http auth=
def test_a_per_call_auth_replaces_the_sessions_for_that_call(stub):
    s = LH.LeanSession()
    s.auth = ("root", "the-wrong-password")
    r = s.post(stub.base + "/api/v1/server", auth=("root", "dbbenchpass"), json={"command": "x"}, timeout=5)
    assert r.status_code == 200
    r = s.get(stub.base + "/api/v1/server?mode=basic", auth=("root", "dbbenchpass"), timeout=5)
    assert r.json() == {"version": "stub"}
    assert s.get(stub.base + "/api/v1/server?mode=basic", timeout=5).status_code == 401   # the session's own credentials apply again


def test_per_call_auth_alone_authenticates_a_session_that_has_none(stub):
    s = LH.LeanSession()
    assert s.get(stub.base + "/api/v1/server?mode=basic", timeout=5).status_code == 401
    assert s.get(stub.base + "/api/v1/server?mode=basic", auth=("root", "dbbenchpass"), timeout=5).status_code == 200


def test_per_call_auth_sends_the_header_requests_sends(stub):
    lean, rq = LH.LeanSession(), requests.Session()
    for sess in (lean, rq):
        sess.post(stub.base + "/api/v1/query/db", auth=("root", "dbbenchpass"), json={"command": "SELECT 1 LIMIT 1", "limit": -1}, timeout=5)
    a, b = stub.seen[-1], stub.seen[-2]
    assert a[2]["Authorization"] == b[2]["Authorization"] and a[3] == b[3]


# --------------------------------------------------------------------------------------------------------- the probe
@pytest.fixture
def probe():
    import deployment_decomp_probe as P
    return P


def test_the_interleave_gives_every_arm_every_position(probe):
    order = []
    fns = {k: (lambda n, k=k: order.append(k) or 1) for k in ("a", "b", "c", "d", "e")}
    probe.timeit_paired(fns, 1, reps=5, warmup=0)
    rounds = [order[i * 5:(i + 1) * 5] for i in range(5)]
    for pos in range(5):
        assert {r[pos] for r in rounds} == set(fns), f"position {pos} is held by one arm only"
    assert all(sorted(r) == sorted(fns) for r in rounds)             # still one timed call of each arm per round


def test_the_interleave_still_warms_every_arm_first_and_returns_every_arm(probe):
    calls = []
    fns = {k: (lambda n, k=k: calls.append(k) or 7) for k in ("x", "y")}
    out = probe.timeit_paired(fns, 3, reps=2, warmup=2)
    assert calls[:4] == ["x", "y", "x", "y"]                         # two warm-up rounds, every arm, before any timed call
    assert set(out) == {"x", "y"} and all(len(lat) == 2 and got == 7 for lat, got in out.values())


def test_the_arms_name_their_clients(probe):
    assert probe.arm_clients("requests", True) == {"inproc_http": "requests", "inproc_http_lean": "lean",
                                                   "docker_http": "requests", "docker_http_lean": "lean"}
    assert probe.arm_clients("urllib_shim", False) == {"inproc_http": "urllib_shim", "inproc_http_lean": "lean"}


def test_the_legacy_client_names_itself_as_what_it_is(probe, monkeypatch):
    import e4_decomp
    assert probe.legacy_client(requests.Session()) == ("requests", f"requests {requests.__version__}")
    monkeypatch.setitem(sys.modules, "requests", requests)           # restored on exit; the shim replaces the module for the test
    e4_decomp._shim_requests()
    shim = sys.modules["requests"].Session()
    key, name = probe.legacy_client(shim)
    assert key == "urllib_shim" and "one connection per call" in name


def test_the_client_decomposition_is_legacy_minus_lean_at_the_same_place(probe):
    res = {"inproc_http": {1: {"p50_ms": 2.5}, 10: {"p50_ms": 3.0}}, "inproc_http_lean": {1: {"p50_ms": 1.0}, 10: {"p50_ms": 2.5}},
           "docker_http": {1: {"p50_ms": 4.0}}, "docker_http_lean": {1: {"p50_ms": 1.5}}}
    got = {r["rows"]: r for r in probe.client_decomposition(res, [1, 10, 100])}
    assert got[1]["inproc_http"] == {"legacy_ms": 2.5, "lean_ms": 1.0, "client_ms": 1.5, "ratio": 2.5}
    assert got[1]["docker_http"]["client_ms"] == 2.5 and 10 in got and "docker_http" not in got[10] and 100 not in got


@pytest.mark.parametrize("mk", ["lean", "requests"])
def test_the_probes_http_runner_runs_through_either_client_and_authenticates_per_call(probe, stub, mk):
    sess = LH.LeanSession() if mk == "lean" else requests.Session()
    run = probe.http_runner(sess, stub.base, ("root", "dbbenchpass"), "db")
    assert run(7) == 7 and run(100) == 100
    method, path, headers, body = stub.seen[-1]
    assert path == "/api/v1/query/db" and json.loads(body)["limit"] == -1
    assert all(c[2].get("Authorization") for c in stub.seen)


# ---------------------------------------- main(), end to end, against stubs standing in for the in-process server and the container
class _Result:
    def __init__(self, rows):
        self._rows = rows

    def to_json_list(self):
        return self._rows


class _FakeDb:
    def command(self, *a, **k):
        pass

    begin = commit = command

    def insert_many(self, *a, **k):
        pass

    def query(self, lang, sql):
        return _Result(_rows(int(sql.rsplit("LIMIT", 1)[1])))


class _FakeServer:
    def __init__(self, port):
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def create_database(self, name):
        return _FakeDb()

    def get_http_port(self):
        return self.port


@pytest.fixture
def run_probe(monkeypatch, tmp_path, probe):
    """main() with the engine faked (an in-process 'server' that is a stub, an embedded 'db' that returns the same rows) and the container
    a second stub; returns (rc, artifact, stubs)."""
    inproc, docker = Stub(probe.PASSWORD), Stub("dbbenchpass")
    for s in (inproc, docker):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    fake = types.ModuleType("arcadedb_embedded")
    fake.__version__ = "0.0-stub"
    fake.create_server = lambda root, root_password, config: _FakeServer(inproc.server_address[1])
    jvm = types.ModuleType("arcadedb_embedded.jvm")
    jvm.start_jvm = lambda **k: None
    fake.jvm = jvm
    monkeypatch.setitem(sys.modules, "arcadedb_embedded", fake)
    monkeypatch.setitem(sys.modules, "arcadedb_embedded.jvm", jvm)
    monkeypatch.setattr(probe, "SIZES", [1, 10, 100])
    monkeypatch.setattr(probe, "ROWS", 300)
    monkeypatch.setattr(probe, "REPS", 4)
    monkeypatch.setattr(probe, "WARMUP", 1)
    monkeypatch.setattr(probe, "run_conditions", lambda **k: {"cpuset": "stub", "mem_cap": "stub"})

    def run(legacy):
        out = tmp_path / f"art-{legacy}.json"
        if legacy == "shim":
            import e4_decomp
            monkeypatch.setitem(sys.modules, "requests", requests)
            e4_decomp._shim_requests()
        monkeypatch.setattr(sys, "argv", ["probe", "--docker", docker.base, "--docker-password", "dbbenchpass", "--heap", "1g",
                                          "--out", str(out), "--root", str(tmp_path / "root")])
        rc = probe.main()
        return rc, json.loads(out.read_text()), (inproc, docker)

    yield run
    for s in (inproc, docker):
        s.shutdown()
        s.server_close()


@pytest.mark.parametrize("legacy", ["requests", "shim"])
def test_main_measures_every_http_arm_under_both_clients_and_names_them(run_probe, legacy):
    rc, art, (inproc, docker) = run_probe(legacy)
    assert rc == 0
    meta, res = art["meta"], art["results"]
    assert set(res) == {"embedded", "inproc_http", "inproc_http_lean", "docker_http", "docker_http_lean"}
    key = "requests" if legacy == "requests" else "urllib_shim"
    assert meta["arm_clients"] == {"inproc_http": key, "inproc_http_lean": "lean", "docker_http": key, "docker_http_lean": "lean"}
    assert meta["client_names"]["lean"] == LH.LEAN_NAME
    if legacy == "requests":
        assert meta["client_names"][key] == f"requests {requests.__version__}"
    else:
        assert "urllib shim" in meta["client_names"][key]
    for arm, ckey in meta["arm_clients"].items():                     # THE CLIENT ON THE MEASUREMENT, every size
        assert all(v["arcadedb_http_client"] == meta["client_names"][ckey] for v in res[arm].values())
    assert all("arcadedb_http_client" not in v for v in res["embedded"].values())
    # the same rows through every path, the two clients included
    assert meta["row_count_agreement"] == "ok" and meta["answer_agreement"] == "ok"
    for size, per in meta["answers"].items():
        assert len({d["digest"] for d in per.values()}) == 1 and set(per) == set(res)
    assert [r["rows"] for r in meta["client_decomposition"]] == [1, 10, 100]
    # each client authenticated against each server with that server's own password (a wrong one is a 401 and the probe raises), and both
    # clients really talked to the container: the User-Agent tells them apart
    assert {c[1].split("?")[0] for c in docker.seen} >= {"/api/v1/query/deploy_decomp", "/api/v1/server"}
    ua = {c[2].get("User-Agent", "") for c in docker.seen}
    assert any(u.startswith("lean_http/") for u in ua) and any(not u.startswith("lean_http/") for u in ua)
    assert any(c[2].get("Connection", "").lower() == "close" for c in docker.seen) == (legacy == "shim")   # the shim opens a connection per call


def test_the_artifact_stays_loadable_where_the_old_one_was(run_probe):
    rc, art, _ = run_probe("requests")
    for arm in ("embedded", "inproc_http", "docker_http"):            # export_web's three October arms keep their keys and fields
        assert set(art["results"][arm]) == {"1", "10", "100"} and "p50_ms" in art["results"][arm]["10"]


def test_the_row_lists_the_clients_it_measured(run_probe):
    import e4_decomp
    rc, art, _ = run_probe("shim")
    names = e4_decomp.stamp_clients(art)
    assert names == [art["meta"]["client_names"]["urllib_shim"], LH.LEAN_NAME] and art["arcadedb_http_clients"] == names


# ------------------------------------------------------------------------------------------------- the page table
@pytest.fixture(scope="module")
def EW():
    """export_web, loaded as a PRIVATE module (skeleton mode, so it does not insist on the pin's artifact directory) so the shared
    `export_web` other tests import is untouched."""
    mp = pytest.MonkeyPatch()
    mp.setenv("BENCH_SKELETON", "1")
    mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        spec = importlib.util.spec_from_file_location("export_web_e4_client_axis", HERE / "export_web.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        mp.undo()
    return mod


def _artifact(arms, arm_clients=None, client_names=None, rep=1):
    meta = {"rows": 200000, "engine_version": "26.10.1", "engine_commit": "417314c18", "reps": 15, "warmup": 3, "cpuset": "0-11",
            "mem_cap": "8g", "heap": "6g", "ts_utc": "2026-10-07T00:00:00+00:00", "host": "h", "row_count_agreement": "ok"}
    if arm_clients:
        meta["arm_clients"], meta["client_names"] = arm_clients, client_names
    ms = {"embedded": 1.0, "inproc_http": 2.5, "inproc_http_lean": 1.5, "docker_http": 3.0, "docker_http_lean": 2.0}
    return {"meta": meta, "results": {a: {s: {"p50_ms": ms[a] * (1 + 0.01 * rep)} for s in ("1", "100")} for a in arms}}


def _write(tmp_path, arts):
    d = tmp_path / "e4decomp_stub"
    d.mkdir(exist_ok=True)
    for i, a in enumerate(arts, 1):
        (d / f"decomp3m_stub_rep{i}.json").write_text(json.dumps(a))
    return d


def test_the_table_names_the_client_in_every_http_column(EW, tmp_path, monkeypatch):
    names = {"urllib_shim": "urllib shim (e4_decomp._shim_requests, one connection per call)", "lean": LH.LEAN_NAME}
    clients = {"inproc_http": "urllib_shim", "inproc_http_lean": "lean", "docker_http": "urllib_shim", "docker_http_lean": "lean"}
    arms = ["embedded", *clients]
    monkeypatch.setattr(EW, "E4_DIR", _write(tmp_path, [_artifact(arms, clients, names, r) for r in (1, 2, 3)]))
    t = EW._e4_table()
    assert t["columns"] == ["in-process ms",
                            "in-process server, HTTP ms, urllib client", "in-process server, HTTP ms, lean client",
                            "separate container, HTTP ms, urllib client", "separate container, HTTP ms, lean client"]
    assert [e["backend"] for e in t["entries"]] == ["1 documents", "100 documents"]
    assert set(t["entries"][0]["metrics"]) == set(t["columns"]) and t["entries"][0]["metrics"][t["columns"][2]]["n"] == 3
    sentence = next(c for c in t["conditions"] if "two Python clients" in c)
    assert names["urllib_shim"] in sentence and LH.LEAN_NAME in sentence
    assert any(g["text"] == sentence and names["urllib_shim"] in g["values"] for g in EW._GENERATED)        # registered as generated


def test_an_artifact_measured_before_the_axis_keeps_its_three_columns(EW, tmp_path, monkeypatch):
    monkeypatch.setattr(EW, "E4_DIR", _write(tmp_path, [_artifact(["embedded", "inproc_http", "docker_http"], rep=r) for r in (1, 2)]))
    t = EW._e4_table()
    assert t["columns"] == ["in-process ms", "in-process server, HTTP ms", "separate container, HTTP ms"]
    assert not any("two Python clients" in c for c in t["conditions"])


def test_repetitions_that_disagree_about_the_client_refuse_to_build(EW, tmp_path, monkeypatch):
    names = {"requests": "requests 2.34.2", "lean": LH.LEAN_NAME}
    clients = {"inproc_http": "requests", "inproc_http_lean": "lean"}
    new = _artifact(["embedded", *clients], clients, names)
    old = _artifact(["embedded", "inproc_http"], rep=2)
    monkeypatch.setattr(EW, "E4_DIR", _write(tmp_path, [new, old]))
    with pytest.raises(SystemExit, match="disagree about which client"):
        EW._e4_table()


def test_the_page_gate_declares_the_rows_client_list():
    import page_check
    for field in ("arcadedb_http_client", "arcadedb_http_clients"):
        assert page_check._not_printed_reason(field), field


def test_e4_ignores_the_switch_and_says_so():
    src = (HERE / "e4_decomp.py").read_text()
    assert "BENCH_ARCADEDB_HTTP_CLIENT does not apply to this lane" in src
    assert "lean_http" not in (HERE / "e4_decomp.py").read_text().split("def main")[1], "e4_decomp must not pick a client from the switch"
