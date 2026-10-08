#!/usr/bin/env python3
"""BENCH_ARCADEDB_HTTP_CLIENT=lean2 (lean_http.LeanSession2): OFF by default, and the same requests and answers as lean when on (CAMPAIGN section 7 row 82).

Run with `python -m pytest test_lean_http2.py -q` from this directory.

The 26.10.1 chain pulls main at every stage start, so the default path and the row fields must not move: the first group pins that the
default is `lean`, that `Session()` is a plain LeanSession, that the row records the October-chain name, and that only the three
documented values are accepted. The second group runs LeanSession and LeanSession2 against the same stub server and compares what the
lanes read (status, reason, headers, bytes, text, json(), raise_for_status() text), the bytes each one SENDS (the request head is compared
line by line; only User-Agent may differ), and the connection behaviour (one connection for many calls, a connection the server closed is
replaced, a read that died on a reused connection is retried once and a write never, a timeout is a TimeoutError). The third group feeds
LeanSession2 hand-written answers (chunked, close-delimited, interim 100, a head split over packets, an oversized head) that the stub
server cannot produce.
"""
import socket
import threading
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lean_http as LH  # noqa: E402
from test_lean_http import BIG, server  # noqa: E402,F401  (the stub server fixture)

AUTH = ("root", "dbbenchpass")


def pair():
    a, b = LH.LeanSession(), LH.LeanSession2()
    a.auth = b.auth = AUTH
    return a, b


# ----------------------------------------------------------------------------------------------- default OFF
def test_default_client_is_lean_and_unchanged(monkeypatch):
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    assert LH.client_choice() == "lean"
    s = LH.Session()
    try:
        assert type(s) is LH.LeanSession
        assert LH.row_fields(s) == {"arcadedb_http_client": "lean_http (http.client, keep-alive)"}
        assert s.client_name == LH.LEAN_NAME == "lean_http (http.client, keep-alive)"
    finally:
        s.close()
    monkeypatch.setenv(LH.CLIENT_ENV, "")
    assert LH.client_choice() == "lean" and type(LH.Session()) is LH.LeanSession
    monkeypatch.setenv(LH.CLIENT_ENV, "LEAN")
    assert LH.client_choice() == "lean"


def test_lean2_is_selected_only_by_name_and_is_stamped(monkeypatch):
    monkeypatch.setenv(LH.CLIENT_ENV, "lean2")
    assert LH.client_choice() == "lean2"
    s = LH.Session()
    try:
        assert type(s) is LH.LeanSession2 and isinstance(s, LH.LeanSession)
        assert LH.row_fields(s) == {"arcadedb_http_client": "lean_http2 (socket, keep-alive)"}
        assert LH.row_fields(s)["arcadedb_http_client"] != LH.LEAN_NAME
    finally:
        s.close()
    monkeypatch.setenv(LH.CLIENT_ENV, "requests")
    assert LH.client_choice() == "requests"
    for bad in ("lean3", "fast", "2"):
        monkeypatch.setenv(LH.CLIENT_ENV, bad)
        with pytest.raises(ValueError):
            LH.client_choice()


def test_lean_session_is_not_touched_by_the_new_class():
    """LeanSession's request path is its own: LeanSession2 overrides request() on a subclass and nothing on LeanSession points at it."""
    assert LH.LeanSession.request is not LH.LeanSession2.request
    assert LH.LeanSession.__mro__[1] is object
    assert "LeanSession2" not in LH.LeanSession.request.__code__.co_names


def test_runner_manifest_records_the_choice(monkeypatch):
    runner_src = (HERE / "runner.py").read_text()
    assert 'manifest["arcadedb_http_client"] = lean_http.client_choice()' in runner_src
    assert '"BENCH_ARCADEDB_HTTP_CLIENT"' in runner_src            # forwarded to the lane container


# ------------------------------------------------------------------------------------------------ same answers
@pytest.mark.parametrize("path", ["/ok", "/status/400", "/status/404", "/status/500", "/empty200", "/empty204", "/large", "/unicode",
                                  "/gzip", "/deflate"])
def test_same_answer_as_lean(server, path):
    a, b = pair()
    ra, rb = a.get(server.base + path, timeout=30), b.get(server.base + path, timeout=30)
    assert (ra.status_code, ra.reason, ra.content, ra.text, ra.ok, ra.url) == (rb.status_code, rb.reason, rb.content, rb.text, rb.ok, rb.url)
    assert ra.encoding == rb.encoding
    assert {k: v for k, v in ra.headers.items() if k not in ("Date",)} == {k: v for k, v in rb.headers.items() if k not in ("Date",)}
    assert rb.headers.get("content-type") == ra.headers.get("Content-Type")
    try:
        want = ra.json()
    except ValueError:
        with pytest.raises(ValueError):
            rb.json()
    else:
        assert rb.json() == want
    try:
        ra.raise_for_status()
    except LH.HTTPError as e:
        with pytest.raises(LH.HTTPError) as got:
            rb.raise_for_status()
        assert str(got.value) == str(e) and got.value.response is rb
    else:
        assert rb.raise_for_status() is None


@pytest.mark.parametrize("enc,raw", [("gzip", "0"), ("deflate", "0"), ("deflate", "1")])
def test_same_decoding_as_lean(server, enc, raw):
    a, b = pair()
    u = server.base + f"/encoded?enc={enc}&raw={raw}"
    assert a.get(u, timeout=30).content == b.get(u, timeout=30).content == BIG


@pytest.mark.parametrize("kind", ["json", "bytes", "text", "empty", "extra-headers", "big-body", "query-string"])
def test_same_request_as_lean(server, kind):
    a, b = pair()
    kw = {"json": {"language": "sql", "command": "SELECT FROM T WHERE id = :i", "params": {"i": 5, "f": 2.5, "s": "café"}}}
    path = "/echo"
    if kind == "bytes":
        kw = {"data": b'{"a": 1}\n{"b": 2}\n', "headers": {"Content-Type": "application/x-ndjson"}}
    elif kind == "text":
        kw = {"data": "Point,host=h1 uu=1 1é", "headers": {"Content-Type": "text/plain"}}
    elif kind == "empty":
        kw = {}
    elif kind == "extra-headers":
        kw = {"headers": {"arcadedb-session-id": "AS-123", "X-N": 5}}
    elif kind == "big-body":
        kw = {"data": b"x" * 200_000}
    elif kind == "query-string":
        path = "/echo?wal=true&expectedEdgeCount=7"
    got = []
    for s in (a, b):
        r = s.post(server.base + path, timeout=30, **kw)
        got.append(r.json())
        assert server.log[-1][1] == path
    (ha, hb), (ba, bb) = [g["headers"] for g in got], [g["body"] for g in got]
    assert ba == bb
    assert ha.pop("user-agent") != hb.pop("user-agent")
    assert ha == hb
    ga, gb = a.get(server.base + "/echo", timeout=30).json()["headers"], b.get(server.base + "/echo", timeout=30).json()["headers"]
    ga.pop("user-agent"), gb.pop("user-agent")
    assert ga == gb


def test_per_call_auth_and_changed_session_auth(server):
    a, b = pair()
    for s in (a, b):
        r = s.post(server.base + "/echo", json={"x": 1}, auth=("u", "p"), timeout=30).json()["headers"]["authorization"]
        assert r == "Basic dTpw"
    h1 = b.post(server.base + "/echo", json={"x": 1}, timeout=30).json()["headers"]["authorization"]
    b.auth = ("other", "pw")
    h2 = b.post(server.base + "/echo", json={"x": 1}, timeout=30).json()["headers"]["authorization"]
    assert h1 != h2 and h2 == a.post(server.base + "/echo", json={"x": 1}, auth=("other", "pw"), timeout=30).json()["headers"]["authorization"]


def test_nan_is_refused_like_lean(server):
    a, b = pair()
    for s in (a, b):
        with pytest.raises(LH.InvalidJSONError):
            s.post(server.base + "/ok", json={"x": float("nan")}, timeout=30)


def test_iterator_body_still_works_through_the_parent_path(server):
    _, b = pair()
    chunks = [b"x" * 70_000, b"y" * 3, b"z" * 10]
    r = b.post(server.base + "/echo", data=(c for c in chunks), timeout=30).json()
    assert r["body"] == "x" * 70_000 + "yyy" + "z" * 10 and r["headers"]["transfer-encoding"] == "chunked"


# -------------------------------------------------------------------------------------- the connection behaviour
def test_one_connection_for_many_calls(server):
    _, b = pair()
    for _ in range(50):
        assert b.post(server.base + "/ok", json={"q": 1}, timeout=30).status_code == 200
    assert server.accepted == 1
    b.close()


@pytest.mark.parametrize("path", ["/close", "/silent-close"])
def test_a_closed_connection_is_replaced(server, path):
    _, b = pair()
    assert b.get(server.base + path, timeout=30).status_code == 200
    assert b.get(server.base + "/ok", timeout=30).status_code == 200
    assert b.get(server.base + "/ok", timeout=30).status_code == 200
    assert server.accepted == 2


def test_a_read_is_retried_once_and_a_write_never(server):
    _, b = pair()
    b.get(server.base + "/ok", timeout=30)
    r = b.post(server.base + "/query/drop-once", json={"q": 1}, timeout=30)       # a read: answered after one silent retry
    assert r.json() == {"result": ["answered"]}
    b.get(server.base + "/ok", timeout=30)
    with pytest.raises(LH.ConnectionError):
        b.post(server.base + "/command/drop-once", json={"q": 1}, timeout=30)       # a write on a reused connection that died: raised
    assert server.counts["/command/drop-once"] == 1


def test_a_timeout_is_a_timeout_error(server):
    _, b = pair()
    with pytest.raises(TimeoutError) as e:
        b.get(server.base + "/sleep?t=1.5", timeout=0.2)
    assert isinstance(e.value, LH.Timeout) and isinstance(e.value, OSError)
    assert b.get(server.base + "/ok", timeout=30).status_code == 200


def test_refused_connection_is_a_connection_error():
    _, b = pair()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(LH.ConnectionError):
        b.get(f"http://127.0.0.1:{port}/x", timeout=2)


# ------------------------------------------------------------------------------ hand-written answers (raw server)
class RawServer:
    """Accepts connections; for each request reads head and body, records the bytes, and writes the next scripted reply (a list of byte chunks)."""

    def __init__(self, replies):
        self.replies, self.requests, self.accepted = list(replies), [], 0
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.base = f"http://127.0.0.1:{self.sock.getsockname()[1]}"
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            self.accepted += 1
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        buf = b""
        while self.replies:
            while b"\r\n\r\n" not in buf:
                d = c.recv(65536)
                if not d:
                    return
                buf += d
            head, _, buf = buf.partition(b"\r\n\r\n")
            n = 0
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    n = int(line.split(b":")[1])
            while len(buf) < n:
                buf += c.recv(65536)
            self.requests.append((head, buf[:n]))
            buf = buf[n:]
            chunks, close = self.replies.pop(0)
            for ch in chunks:
                c.sendall(ch)
            if close:
                c.close()
                return

    def stop(self):
        self.sock.close()


@pytest.fixture
def raw():
    made = []

    def make(*replies):
        s = RawServer(replies)
        made.append(s)
        return s
    yield make
    for s in made:
        s.stop()


OKB = b'{"result":[{"a":1}]}'


def test_chunked_answer(raw):
    body = OKB
    ch = b"%x\r\n%s\r\n%x\r\n%s\r\n0\r\nX-T: 1\r\n\r\n" % (5, body[:5], len(body) - 5, body[5:])
    srv = raw(([b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n", ch[:7], ch[7:]], False),
              ([b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + OKB], False))
    s = LH.LeanSession2()
    r = s.get(srv.base + "/a", timeout=5)
    assert r.content == OKB and r.json() == {"result": [{"a": 1}]}
    assert s.get(srv.base + "/b", timeout=5).content == OKB
    assert srv.accepted == 1                      # the connection survived the chunked answer


def test_close_delimited_answer_and_reconnect(raw):
    srv = raw(([b"HTTP/1.1 200 OK\r\n\r\n", OKB], True), ([b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + OKB], False))
    s = LH.LeanSession2()
    assert s.get(srv.base + "/a", timeout=5).content == OKB
    assert s.get(srv.base + "/b", timeout=5).content == OKB
    assert srv.accepted == 2


def test_interim_100_answer_is_skipped(raw):
    srv = raw(([b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + OKB], False))
    assert LH.LeanSession2().get(srv.base + "/a", timeout=5).content == OKB


def test_head_and_body_split_over_many_packets(raw):
    full = b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\nContent-Type: application/json; charset=utf-8\r\n\r\n" + OKB
    srv = raw(([full[i:i + 3] for i in range(0, len(full), 3)], False))
    r = LH.LeanSession2().get(srv.base + "/a", timeout=5)
    assert r.content == OKB and r.encoding == "utf-8" and r.headers["Content-Type"].startswith("application/json")


def test_head_larger_than_the_buffer_and_body_larger_than_the_buffer(raw):
    big = b"x" * 300_000
    srv = raw(([b"HTTP/1.1 200 OK\r\nX-Pad: " + b"p" * 30_000 + b"\r\nX-Pad2: " + b"q" * 30_000 + b"\r\nX-Pad3: " + b"r" * 30_000 + b"\r\nContent-Length: 300000\r\n\r\n" + big], False))
    r = LH.LeanSession2().get(srv.base + "/a", timeout=5)
    assert r.content == big and len(r.headers["X-Pad3"]) == 30_000


def test_header_names_are_matched_case_insensitively_and_not_as_substrings(raw):
    srv = raw(([b"HTTP/1.1 200 OK\r\nX-Content-Length: 5\r\nCONTENT-LENGTH: 20\r\nx-connection: close\r\n\r\n" + OKB], False),
              ([b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + OKB], False))
    s = LH.LeanSession2()
    assert s.get(srv.base + "/a", timeout=5).content == OKB
    assert s.get(srv.base + "/b", timeout=5).content == OKB
    assert srv.accepted == 1


def test_charset_and_reason(raw):
    srv = raw(([b"HTTP/1.1 418 I'm a teapot\r\nContent-Type: text/plain; charset=latin-1\r\nContent-Length: 1\r\n\r\n\xe9"], False))
    r = LH.LeanSession2().get(srv.base + "/a", timeout=5)
    assert (r.status_code, r.reason, r.encoding, r.text) == (418, "I'm a teapot", "latin-1", "é")
    with pytest.raises(LH.HTTPError, match="418 Client Error: I'm a teapot for url"):
        r.raise_for_status()


def test_an_early_refusal_is_reported(raw):
    srv = raw(([b"HTTP/1.1 413 Payload Too Large\r\nContent-Length: 12\r\nConnection: close\r\n\r\ntoo large!!!\n"], True))
    s = LH.LeanSession2()
    r = s.post(srv.base + "/batch", data=b"x" * 50, timeout=5)
    assert r.status_code == 413 and r.content.strip() == b"too large!!!"


def test_request_bytes_match_lean_line_for_line(raw):
    reply = ([b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + OKB], False)
    heads = []
    for cls in (LH.LeanSession, LH.LeanSession2):
        srv = raw(reply, reply)
        s = cls()
        s.auth = AUTH
        s.post(srv.base + "/api/v1/query/bench?x=1", json={"command": "RETURN 1", "limit": -1}, timeout=5)
        s.get(srv.base + "/api/v1/ready", timeout=5)
        heads.append(srv.requests)
    for (ha, ba), (hb, bb) in zip(*heads):
        la, lb = [x for x in ha.split(b"\r\n") if not x.startswith(b"Host:")], [x for x in hb.split(b"\r\n") if not x.startswith(b"Host:")]
        assert ha.split(b"\r\n")[1].startswith(b"Host: 127.0.0.1:") and hb.split(b"\r\n")[1].startswith(b"Host: 127.0.0.1:")
        assert ba == bb
        assert sorted(x for x in la if not x.startswith(b"User-Agent")) == sorted(x for x in lb if not x.startswith(b"User-Agent"))
        assert la[0] == lb[0]                                     # the request line, and Host second in both (checked above)
        assert [x.split(b":")[0] for x in la] == [x.split(b":")[0] for x in lb]            # the same lines in the same order, User-Agent included
