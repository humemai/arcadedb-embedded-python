#!/usr/bin/env python3
"""The ArcadeDB served arms' HTTP client: lean_http.Session against requests.Session (CAMPAIGN section 7 row 72).

Run with `python -m pytest test_lean_http.py -q -rs` from this directory (the parity tests need `requests`; they skip without it).

About three quarters of a served ArcadeDB statement was the Python HTTP client (levers audit 2026-10-06): one persistent http.client
connection answers a bound one-row read in 119 to 150 us where requests.Session needs 468 to 628 us against the same server. A client that
replaces requests must give every caller the same answers, so these tests run the two against a local server and compare what the lanes
read: status, reason, headers, bytes, text, json(), the text of raise_for_status(), and the request each one SENDS (headers and body bytes, the
chunked stream of an iterator body included). They also pin what keep-alive adds: one connection for many calls, a connection the server
closed is replaced, a read that dies on a reused connection is retried once and a write never is, a timeout raises an OSError that is a
TimeoutError, and the choice of client is switchable, read from the session, forwarded to the lane container, and recorded on the manifest.
"""
import gzip
import json
import socket
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lean_http as LH  # noqa: E402

requests = pytest.importorskip("requests", reason="the parity tests compare against requests")

BIG = json.dumps({"result": [{"id": i, "name": "n%d" % i, "pad": "x" * 40} for i in range(60_000)]}).encode()

def _raw_deflate(b):
    c = zlib.compressobj(wbits=-zlib.MAX_WBITS)       # a raw deflate stream (no zlib header), which some servers send as "deflate"
    return c.compress(b) + c.flush()


# THE CONTENT CODINGS THE STUB SERVER CAN ENCODE, which is the set a client may advertise: a coding the client sends in
# Accept-Encoding and the tests cannot encode is one nobody has shown it can decode (brotli and zstd are only offered by
# requests when the installed urllib3 has the optional libraries, so the venv a test runs in must not decide the expectation).
ENCODERS = {"identity": lambda b: b, "gzip": gzip.compress, "deflate": zlib.compress}
NON_ASCII = json.dumps({"result": [{"name": "caf\u00e9 \u4e2d\u6587"}]}, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # headers and body go in two writes; ArcadeDB's server sends one

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/json", extra=None, close=False, reason=None):
        self.send_response(code, reason)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            out = b""
            while True:
                size = int(self.rfile.readline().strip(), 16)
                if size == 0:
                    self.rfile.readline()
                    return out
                out += self.rfile.read(size)
                self.rfile.readline()
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _handle(self):
        srv = self.server
        body = self._read_body()
        srv.log.append((self.command, self.path, dict(self.headers), body))
        p = self.path.split("?")[0]
        if p == "/ok":
            self._send(200, b'{"result": [{"a": 1}]}')
        elif p.startswith("/status/"):
            code = int(p.rsplit("/", 1)[1])
            self._send(code, json.dumps({"error": "boom", "code": code}).encode())
        elif p == "/empty200":
            self._send(200, b"")
        elif p == "/empty204":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif p == "/large":
            self._send(200, BIG)
        elif p == "/unicode":
            self._send(200, NON_ASCII, ctype="application/json; charset=utf-8")
        elif p == "/gzip":
            self._send(200, gzip.compress(BIG), extra={"Content-Encoding": "gzip"})
        elif p == "/deflate":
            self._send(200, zlib.compress(BIG), extra={"Content-Encoding": "deflate"})
        elif p == "/encoded":
            q = dict(kv.split("=", 1) for kv in self.path.split("?", 1)[1].split("&"))
            enc, raw = q["enc"], q.get("raw") == "1"
            payload = _raw_deflate(BIG) if raw else ENCODERS[enc](BIG)
            self._send(200, payload, extra={} if enc == "identity" else {"Content-Encoding": enc})
        elif p == "/sleep":
            time.sleep(float(self.path.split("t=")[1]))
            self._send(200, b"{}")
        elif p == "/echo":
            self._send(200, json.dumps({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": body.decode("latin-1")}).encode())
        elif p == "/close":
            self._send(200, b'{"closed": true}', close=True)
        elif p == "/silent-close":
            self._send(200, b'{"result": []}')
            self.close_connection = True      # no Connection: close header; the socket just goes away after the response
        elif p in ("/drop-once-read", "/drop-once-write", "/query/drop-once", "/command/drop-once"):
            n = srv.counts.get(p, 0)
            srv.counts[p] = n + 1
            if n == 0:
                self.close_connection = True   # read the request, answer nothing, close
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            self._send(200, b'{"result": ["answered"]}')
        else:
            self._send(404, b"{}")

    do_GET = do_POST = do_PUT = _handle


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.log, self.counts, self.accepted = [], {}, 0

    def handle_error(self, request, client_address):
        pass                                                                # a client that hangs up mid-request is part of the tests

    def get_request(self):
        r = super().get_request()
        self.accepted += 1
        return r


@pytest.fixture
def server():
    srv = Server()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    srv.base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield srv
    srv.shutdown()
    srv.server_close()


def both(server):
    lean = LH.LeanSession()
    lean.auth = ("root", "dbbenchpass")
    rq = requests.Session()
    rq.auth = ("root", "dbbenchpass")
    return lean, rq


# ---------------------------------------------------------------------------------------------- the answers
@pytest.mark.parametrize("path", ["/ok", "/status/200", "/status/400", "/status/404", "/status/409", "/status/500", "/status/503",
                                  "/empty200", "/empty204", "/large", "/unicode", "/gzip", "/deflate"])
def test_the_response_reads_the_same_as_requests(server, path):
    lean, rq = both(server)
    a, b = lean.get(server.base + path, timeout=30), rq.get(server.base + path, timeout=30)
    assert a.status_code == b.status_code
    assert a.reason == b.reason
    assert a.content == b.content
    assert a.text == b.text
    assert a.ok == b.ok
    assert a.url == b.url
    assert a.headers.get("content-type") == b.headers.get("Content-Type")
    assert a.headers.get("Content-Length") == b.headers.get("Content-Length") or "Content-Encoding" in b.headers
    try:
        want = b.json()
    except ValueError:
        with pytest.raises(ValueError):                    # an empty body: JSONDecodeError in both, a ValueError either way
            a.json()
    else:
        assert a.json() == want


@pytest.mark.parametrize("code", [200, 204, 301, 399, 400, 404, 409, 429, 500, 502, 503])
def test_raise_for_status_has_the_same_text(server, code):
    lean, rq = both(server)
    a, b = lean.post(server.base + f"/status/{code}", json={"x": 1}, timeout=30), rq.post(server.base + f"/status/{code}", json={"x": 1}, timeout=30)
    try:
        b.raise_for_status()
    except requests.HTTPError as e:
        with pytest.raises(LH.HTTPError) as got:
            a.raise_for_status()
        assert str(got.value) == str(e)
        assert isinstance(got.value, OSError) and got.value.response is a
    else:
        assert a.raise_for_status() is None


# ----------------------------------------------------------------------------------------- what each one sends
def _sent(server, n_before):
    method, path, headers, body = server.log[-1]
    return {k.lower(): v for k, v in headers.items()}, body


@pytest.mark.parametrize("kind", ["json", "bytes", "text", "empty", "extra-headers", "stream"])
def test_the_request_sent_is_the_same_as_requests_sends(server, kind):
    lean, rq = both(server)
    kw = {"json": {"language": "sql", "command": "SELECT FROM T WHERE id = :i", "params": {"i": 5, "f": 2.5, "s": "caf\u00e9"}}}
    if kind == "bytes":
        kw = {"data": b'{"a": 1}\n{"b": 2}\n', "headers": {"Content-Type": "application/x-ndjson"}}
    elif kind == "text":
        kw = {"data": b"Point,host=h1 uu=1,us=2,ui=3 1", "headers": {"Content-Type": "text/plain"}}
    elif kind == "empty":
        kw = {}
    elif kind == "extra-headers":
        kw = {"headers": {"arcadedb-session-id": "AS-123"}}
    elif kind == "stream":
        chunks = [b"x" * 70_000, b"y" * 3, b"z" * 10]
        kw_lean, kw_rq = {"data": (c for c in chunks)}, {"data": (c for c in chunks)}
    if kind != "stream":
        kw_lean = kw_rq = kw
    a = lean.post(server.base + "/echo?wal=true&expectedEdgeCount=7", timeout=30, **kw_lean)
    b = rq.post(server.base + "/echo?wal=true&expectedEdgeCount=7", timeout=30, **kw_rq)
    ha, hb = a.json()["headers"], b.json()["headers"]
    assert a.json()["body"] == b.json()["body"]                           # the same bytes on the wire
    # accept-encoding is NOT compared for equality: requests advertises "gzip, deflate" or "gzip, deflate, br, zstd" depending on
    # which optional libraries its urllib3 found, so the installed environment would decide the expectation. It is judged below
    # by what the lean client can actually decode (test_the_lean_client_advertises_only_codings_it_decodes).
    for h in ("authorization", "content-type", "content-length", "transfer-encoding", "accept", "connection", "arcadedb-session-id"):
        assert ha.get(h) == hb.get(h), h
    assert _codings(ha["accept-encoding"]) <= _codings(hb["accept-encoding"]), "the lean client asks for a coding requests would not"
    assert set(ha) - set(hb) == set()                                      # nothing extra but the User-Agent value
    assert ha["user-agent"] != hb["user-agent"]
    assert server.log[-1][1] == server.log[-2][1] == "/echo?wal=true&expectedEdgeCount=7"


def _codings(header):
    """The content codings an Accept-Encoding header names, q-values dropped: "gzip, deflate;q=0.5" -> {"gzip", "deflate"}."""
    return {t.split(";")[0].strip().lower() for t in header.split(",") if t.strip()}


def _undecodable(server, lean, advertised):
    """The advertised codings the lean client does NOT decode correctly: each is asked of the stub server in that coding and the
    answer must equal the identity answer. A coding the stub cannot encode counts as undecodable (nothing shows the client reads it)."""
    bad = []
    for coding in sorted(advertised):
        if coding not in ENCODERS:
            bad.append(coding)
            continue
        got = lean.get(server.base + f"/encoded?enc={coding}", timeout=30)
        if got.status_code != 200 or got.content != BIG:
            bad.append(coding)
    return bad


def test_the_lean_client_advertises_only_codings_it_decodes(server):
    """Whatever the installed requests advertises, the lean client's Accept-Encoding is stable and every coding in it round-trips."""
    lean, rq = both(server)
    seen = set()
    for i in range(3):
        lean.get(server.base + "/echo", timeout=5)
        lean.post(server.base + "/echo", json={"i": i}, timeout=5)
        seen.add({k.lower(): v for k, v in server.log[-1][2].items()}["accept-encoding"])
        seen.add({k.lower(): v for k, v in server.log[-2][2].items()}["accept-encoding"])
    assert len(seen) == 1, f"the lean client's Accept-Encoding changes between calls: {sorted(seen)}"
    advertised = _codings(seen.pop())
    assert advertised, "the lean client sends no Accept-Encoding at all"
    assert not _undecodable(server, lean, advertised), \
        f"the lean client advertises {_undecodable(server, lean, advertised)} and does not decode it"
    rq.get(server.base + "/echo", timeout=5)
    assert advertised <= _codings({k.lower(): v for k, v in server.log[-1][2].items()}["accept-encoding"])


@pytest.mark.parametrize("header", ["gzip, deflate, br", "gzip, deflate, br, zstd", "gzip, deflate, zstd;q=0.5", "br"])
def test_the_decodability_check_fails_for_a_coding_the_client_cannot_read(server, header):
    """The guard above is not vacuous: a header naming brotli or zstd is reported, by name."""
    lean, _ = both(server)
    bad = _undecodable(server, lean, _codings(header))
    assert bad and set(bad) <= {"br", "zstd"} and set(bad) == _codings(header) - set(ENCODERS)


def test_a_lean_client_that_advertised_brotli_would_fail_the_advertised_check(server, monkeypatch):
    """The same check, run on a client that does advertise a coding it cannot decode (the headers it builds are patched)."""
    original = LH.LeanSession._headers

    def headers(self, extra, has_json, auth=None):
        h = original(self, extra, has_json, auth)
        h["Accept-Encoding"] = "gzip, deflate, br, zstd"
        return h
    monkeypatch.setattr(LH.LeanSession, "_headers", headers)
    lean, _ = both(server)
    lean.get(server.base + "/echo", timeout=5)
    advertised = _codings({k.lower(): v for k, v in server.log[-1][2].items()}["accept-encoding"])
    assert _undecodable(server, lean, advertised) == ["br", "zstd"]


@pytest.mark.parametrize("coding,raw", [("identity", False), ("gzip", False), ("deflate", False), ("deflate", True)])
def test_the_lean_client_decodes_what_the_server_sends_the_way_requests_does(server, coding, raw):
    """gzip, deflate (zlib-wrapped and raw), and identity, each equal to the plain body and to what requests returns."""
    lean, rq = both(server)
    url = server.base + f"/encoded?enc={coding}" + ("&raw=1" if raw else "")
    a, b = lean.get(url, timeout=30), rq.get(url, timeout=30)
    assert a.content == b.content == BIG
    assert a.text == b.text and a.json() == b.json()
    assert (a.headers.get("Content-Encoding") or "identity").lower() == coding


def test_a_json_body_that_cannot_be_json_is_refused_like_requests_refuses_it(server):
    lean, rq = both(server)
    with pytest.raises(LH.InvalidJSONError) as a:
        lean.post(server.base + "/ok", json={"x": float("nan")}, timeout=5)
    with pytest.raises(requests.exceptions.InvalidJSONError) as b:
        rq.post(server.base + "/ok", json={"x": float("nan")}, timeout=5)
    assert isinstance(a.value, OSError) and isinstance(b.value, OSError)
    assert str(a.value) == str(b.value)                                     # "Out of range float values are not JSON compliant: nan"
    assert not any(e[1] == "/ok" for e in server.log)                       # and nothing was sent


# ---------------------------------------------------------------------------------------------- the connection
def test_many_calls_share_one_connection(server):
    lean, _ = both(server)
    for i in range(60):
        assert lean.post(server.base + "/ok", json={"i": i}, timeout=5).status_code == 200
    assert server.accepted == 1
    lean.close()


def test_a_connection_the_server_closed_between_calls_is_replaced(server):
    lean, _ = both(server)
    for _ in range(5):
        assert lean.post(server.base + "/silent-close", json={}, timeout=5).json() == {"result": []}
        time.sleep(0.05)                                                   # the FIN arrives while the connection idles
    assert server.accepted == 5
    assert lean.post(server.base + "/ok", json={}, timeout=5).status_code == 200


def test_a_connection_close_answer_is_followed_by_a_new_connection(server):
    lean, _ = both(server)
    assert lean.get(server.base + "/close", timeout=5).json() == {"closed": True}
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200
    assert server.accepted == 2


@pytest.mark.parametrize("path, method", [("/drop-once-read", "GET"), ("/query/drop-once", "POST")])
def test_a_read_that_dies_on_a_reused_connection_is_retried_once(server, path, method):
    lean, _ = both(server)
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200      # makes the connection a reused one
    r = lean.request(method, server.base + path, json={} if method == "POST" else None, timeout=5)
    assert r.json() == {"result": ["answered"]}
    assert server.counts[path] == 2


@pytest.mark.parametrize("path", ["/drop-once-write", "/command/drop-once"])
def test_a_write_that_dies_after_it_was_sent_is_never_retried(server, path):
    lean, _ = both(server)
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200
    with pytest.raises(LH.ConnectionError) as e:
        lean.post(server.base + path, json={"command": "INSERT"}, timeout=5)
    assert isinstance(e.value, OSError)
    assert server.counts[path] == 1                                        # the statement reached the server once, and only once
    assert lean.post(server.base + path, json={}, timeout=5).status_code == 200   # and the session works afterwards


def test_nothing_listening_raises_a_connection_error():
    lean = LH.LeanSession()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(LH.ConnectionError) as e:
        lean.get(f"http://127.0.0.1:{port}/ok", timeout=2)
    assert isinstance(e.value, OSError)
    with pytest.raises(requests.ConnectionError):
        requests.Session().get(f"http://127.0.0.1:{port}/ok", timeout=2)


def test_a_timeout_is_an_oserror_and_a_timeouterror(server):
    lean, rq = both(server)
    with pytest.raises(LH.Timeout) as e:
        lean.get(server.base + "/sleep?t=2", timeout=0.2)
    assert isinstance(e.value, OSError) and isinstance(e.value, TimeoutError)
    with pytest.raises(requests.Timeout) as r:
        rq.get(server.base + "/sleep?t=2", timeout=0.2)
    assert isinstance(r.value, OSError)                                     # what a caller can catch on both: OSError and Exception
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200      # the session survives a timeout


def test_a_call_may_use_a_different_timeout_than_the_one_before(server):
    lean, _ = both(server)
    assert lean.get(server.base + "/ok", timeout=5).status_code == 200
    assert lean.get(server.base + "/sleep?t=0.3", timeout=20).status_code == 200
    with pytest.raises(LH.Timeout):
        lean.get(server.base + "/sleep?t=1", timeout=0.1)


# ------------------------------------------------------------------------------- a server that refuses while the client is still sending
def _refusing_server(status_line, body, close=True):
    """A bare TCP server that reads the request line and the headers, answers `status_line` with a text body, and closes while the
    client is still writing its body: what ArcadeDB 26.10.1 does to a bulk load past `arcadedb.server.httpBodyContentMaxSize`.
    Returns (port, thread, the request lines it saw)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    seen = []

    def run():
        conn, _ = srv.accept()
        buf = b""
        while b"\r\n\r\n" not in buf:
            part = conn.recv(65536)
            if not part:
                break
            buf += part
        seen.append(buf.split(b"\r\n", 1)[0].decode("latin-1"))
        raw = body.encode()
        conn.sendall(f"{status_line}\r\nContent-Type: text/plain\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode() + raw)
        if close:
            conn.close()
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], t, seen


def _big_body(mib=64):
    """An iterator body of `mib` MiB in 1 MiB chunks (sent chunked, not replayable), far more than any socket buffer holds."""
    for _ in range(mib):
        yield b"x" * (1 << 20)


def test_a_refusal_sent_while_the_client_is_still_sending_is_in_the_error():
    """The 26.10.1 campaign's served graph load died as `[Errno 32] Broken pipe` with the reason (a 413-style refusal naming
    httpBodyContentMaxSize) in the socket the client never read. The error now carries the server's status and the first 500 bytes."""
    reason = ("Batch load on database 'bench' was refused after 65645 vertices because the request body exceeded "
              "'arcadedb.server.httpBodyContentMaxSize' (currently 104857600 bytes). Raise that setting or split the payload")
    port, t, seen = _refusing_server("HTTP/1.1 413 Request Entity Too Large", reason)
    lean = LH.LeanSession()
    with pytest.raises(LH.ConnectionError) as e:
        lean.post(f"http://127.0.0.1:{port}/api/v1/batch/bench?wal=true", data=_big_body(),
                  headers={"Content-Type": "application/x-ndjson"}, timeout=20)
    t.join(10)
    msg = str(e.value)
    assert isinstance(e.value, OSError)
    assert "413" in msg and "httpBodyContentMaxSize" in msg and "Raise that setting or split the payload" in msg, msg
    assert seen and seen[0].startswith("POST /api/v1/batch/bench?wal=true"), seen
    assert not lean._conns                                                # the dead connection is dropped


def test_only_the_first_500_bytes_of_an_early_answer_go_into_the_error():
    port, t, _ = _refusing_server("HTTP/1.1 413 Payload Too Large", "A" * 400 + "B" * 4000)
    with pytest.raises(LH.ConnectionError) as e:
        LH.LeanSession().post(f"http://127.0.0.1:{port}/batch", data=_big_body(), timeout=20)
    t.join(10)
    msg = str(e.value)
    assert "413" in msg and "A" * 400 in msg and "B" * 100 in msg and "B" * 101 not in msg, len(msg)


def test_a_connection_that_dies_while_sending_with_no_answer_keeps_the_plain_message():
    """A server that closes without a word: the error is the old one, with nothing invented after it."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        conn.recv(65536)
        conn.close()
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    with pytest.raises(LH.ConnectionError) as e:
        LH.LeanSession().post(f"http://127.0.0.1:{srv.getsockname()[1]}/batch", data=_big_body(), timeout=20)
    t.join(10)
    assert "already answered" not in str(e.value) and "POST http://127.0.0.1:" in str(e.value)


# ------------------------------------------------------------------------------------------- the switch and the record
def test_the_factory_follows_BENCH_ARCADEDB_HTTP_CLIENT(monkeypatch):
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    s = LH.Session()
    assert isinstance(s, LH.LeanSession) and s.client_name == LH.LEAN_NAME
    monkeypatch.setenv(LH.CLIENT_ENV, "lean")
    assert isinstance(LH.Session(), LH.LeanSession)
    monkeypatch.setenv(LH.CLIENT_ENV, "requests")
    r = LH.Session()
    assert isinstance(r, requests.Session) and r.client_name == f"requests {requests.__version__}"
    monkeypatch.setenv(LH.CLIENT_ENV, "urllib")
    with pytest.raises(ValueError):
        LH.Session()


def test_the_row_records_the_client_the_session_ran_with(monkeypatch):
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    assert LH.row_fields(LH.Session()) == {"arcadedb_http_client": LH.LEAN_NAME}
    monkeypatch.setenv(LH.CLIENT_ENV, "requests")
    assert LH.row_fields(LH.Session()) == {"arcadedb_http_client": f"requests {requests.__version__}"}


def test_the_manifest_records_the_client(monkeypatch):
    import types
    import runner
    args = types.SimpleNamespace(tier="smoke", scale="micro", reps=1, seed=0)
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    assert runner.build_manifest("t", args, 1, 1, [])["arcadedb_http_client"] == "lean"
    monkeypatch.setenv(LH.CLIENT_ENV, "requests")
    m = runner.build_manifest("t", args, 1, 1, [])
    assert m["arcadedb_http_client"] == "requests" and m["runner_env"][LH.CLIENT_ENV] == "requests"


def test_the_lane_container_receives_the_switch():
    src = (HERE / "runner.py").read_text()
    block = src[src.index("for _k in (\"ARCADEDB_ENGINE_COMMIT\""):src.index("if os.environ.get(_k):", src.index("for _k in (\"ARCADEDB_ENGINE_COMMIT\""))]
    assert '"BENCH_ARCADEDB_HTTP_CLIENT"' in block


def test_the_page_gate_declares_the_new_row_field():
    import page_check
    reason = page_check._not_printed_reason("arcadedb_http_client")
    assert reason and "lean_http" in reason, "A2 (every measured field is a column or in NOT_PRINTED) would flag every served row"


# the ArcadeDB served arms: which sessions the lanes get from where ---------------------------------------------------------------
SERVED_LANES = ["l1_tabular.py", "l1_tpc.py", "l2_graph.py", "l3_sparse.py", "l3d_dense.py", "l4_tsbs.py", "e2_hybrid.py",
                "l5_lifecycle_server.py", "l6_restart.py"]


@pytest.mark.parametrize("lane", SERVED_LANES)
def test_no_served_arcadedb_arm_builds_a_requests_session_itself(lane):
    src = (HERE / lane).read_text()
    assert "requests.Session()" not in src, f"{lane} still builds its own requests.Session"
    assert "lean_http.Session()" in src


def _stub_server_answering_everything():
    class H(Handler):
        def _handle(self):
            body = self._read_body()
            self.server.log.append((self.command, self.path, dict(self.headers), body))
            self._send(200, b'{"version": "stub", "result": []}')

        do_GET = do_POST = _handle

    srv = Server.__new__(Server)
    ThreadingHTTPServer.__init__(srv, ("127.0.0.1", 0), H)
    srv.log, srv.counts, srv.accepted = [], {}, 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.mark.parametrize("module, cls", [("l2_graph", "ArcadeGraphServer"), ("l3_sparse", "ArcadeServer"), ("l3d_dense", "ArcadeServer"),
                                         ("l4_tsbs", "ArcadeTSServer"), ("l4_tsbs", "ArcadeNativeTSServer"), ("l1_tabular", "ArcadeServer"),
                                         ("l1_tpc", "ArcadeServerTPC")])
@pytest.mark.parametrize("choice, want", [("", LH.LEAN_NAME), ("requests", f"requests {requests.__version__}")])
def test_every_served_adapter_records_the_client_it_ran_with(monkeypatch, module, cls, choice, want):
    srv = _stub_server_answering_everything()
    try:
        if choice:
            monkeypatch.setenv(LH.CLIENT_ENV, choice)
        else:
            monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
        monkeypatch.setenv("BENCH_SERVER_HOST", "127.0.0.1")
        monkeypatch.setenv("BENCH_SERVER_PORT", str(srv.server_address[1]))
        mod = __import__(module)
        ad = getattr(mod, cls)()
        ad.connect()
        assert ad.row_extra["arcadedb_http_client"] == want
        assert (type(ad.rq).__name__ == "LeanSession") == (not choice)
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_e2_served_adapter_records_the_client_it_ran_with(monkeypatch):
    srv = _stub_server_answering_everything()
    try:
        monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
        monkeypatch.setenv("BENCH_SERVER_HOST", "127.0.0.1")
        monkeypatch.setenv("BENCH_SERVER_PORT", str(srv.server_address[1]))
        import e2_hybrid
        ad = e2_hybrid.ArcadeE2Server()
        assert ad.row_extra["arcadedb_http_client"] == LH.LEAN_NAME
        # and the lane's own helper reads and writes through it: the session id header travels
        ad._post("query", "SELECT 1", sid="SID-1")
        assert {k.lower(): v for k, v in srv.log[-1][2].items()}["arcadedb-session-id"] == "SID-1"
    finally:
        srv.shutdown()
        srv.server_close()
