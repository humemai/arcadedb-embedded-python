"""Streamed (NDJSON) results for the served ArcadeDB time-series arms, default OFF (CAMPAIGN section 7 row 85).

Run with `python -m pytest test_ts_ndjson.py -q -rs` from this directory. The lane and export_web tests need numpy.

With `BENCH_ARCADEDB_TS_NDJSON=1` both served ArcadeDB arms of the time-series lane ask the query endpoint for
`Accept: application/x-ndjson` and read the `{"record": ...}` lines and the last `{"stats": {"returned": N}}` line, checking the
count; their rows stamp `arcadedb_ts_result_format`. Unset, the request, the answer path, and the row fields are what they were. The
/next page says the served ArcadeDB arms read a buffered answer while the rows lack the stamp, and the next-measurement list says the
next measurement reads them as a stream.
"""
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lean_http as LH  # noqa: E402

ROWS = [{"host": f"host_{i % 7}", "ts": 1767225600 + i, "uu": 90.5 + i % 3} for i in range(2500)]


def _ndjson(rows, returned=None):
    lines = [json.dumps({"record": r}) for r in rows]
    lines.append(json.dumps({"stats": {"returned": len(rows) if returned is None else returned}}))
    return ("\n".join(lines) + "\n").encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen = []           # (path, Accept, body) per request
    returned = None     # override the stats count, to test the mismatch

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"version": "26.10.1 (stub)"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        accept = self.headers.get("Accept")
        Handler.seen.append((self.path, accept, json.loads(req)))
        if accept == LH.NDJSON_ACCEPT:
            payload = _ndjson(ROWS, Handler.returned)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for i in range(0, len(payload), 4096):           # several chunks, lines split across them
                part = payload[i:i + 4096]
                self.wfile.write(b"%x\r\n" % len(part) + part + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        else:
            body = json.dumps({"user": "root", "result": ROWS}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


@pytest.fixture()
def server(monkeypatch):
    Handler.seen, Handler.returned = [], None
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setenv("BENCH_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("BENCH_SERVER_PORT", str(srv.server_address[1]))
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def L():
    pytest.importorskip("numpy")
    import l4_tsbs
    return l4_tsbs


@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


# ------------------------------------------------------------------------------------------------ the parser
def test_records_parse_and_the_count_is_checked():
    assert LH.ndjson_records(_ndjson(ROWS)) == ROWS
    assert LH.ndjson_records(_ndjson([])) == []
    with pytest.raises(LH.NdjsonError, match="returned=3"):
        LH.ndjson_records(_ndjson(ROWS[:2], returned=3))
    with pytest.raises(LH.NdjsonError, match="no stats line"):
        LH.ndjson_records(b'{"record": {"a": 1}}\n')
    with pytest.raises(LH.NdjsonError, match="unexpected"):                 # a buffered answer is not mistaken for a stream
        LH.ndjson_records(json.dumps({"user": "root", "result": ROWS}).encode())
    with pytest.raises(LH.NdjsonError, match="unexpected"):                 # nothing after the count
        LH.ndjson_records(_ndjson(ROWS[:1]) + b'{"record": {"a": 1}}\n')


@pytest.mark.parametrize("client", ["lean", "lean2"])
def test_post_ndjson_sends_the_header_and_reads_the_chunked_body(server, monkeypatch, client):
    monkeypatch.setenv(LH.CLIENT_ENV, client)
    s = LH.Session()
    s.auth = ("root", "x")
    url = f"http://127.0.0.1:{server.server_address[1]}/api/v1/query/bench"
    assert LH.post_ndjson(s, url, {"language": "sql", "command": "SELECT 1", "limit": -1}, timeout=10) == ROWS
    assert Handler.seen[-1][1] == LH.NDJSON_ACCEPT
    Handler.returned = len(ROWS) + 1
    with pytest.raises(LH.NdjsonError):
        LH.post_ndjson(s, url, {"language": "sql", "command": "SELECT 1"}, timeout=10)
    s.close()


# ------------------------------------------------------------------------------------------------ the lane
def test_switch_is_off_unless_set_to_1(L, monkeypatch):
    monkeypatch.delenv(L.TS_NDJSON_ENV, raising=False)
    assert L.ts_ndjson_enabled() is False
    monkeypatch.setenv(L.TS_NDJSON_ENV, "1")
    assert L.ts_ndjson_enabled() is True
    monkeypatch.setenv(L.TS_NDJSON_ENV, "yes")       # a typo must not run buffered while the launcher believes otherwise
    with pytest.raises(SystemExit):
        L.ts_ndjson_enabled()


@pytest.mark.parametrize("arm", ["ArcadeTSServer", "ArcadeNativeTSServer"])
def test_unset_is_the_buffered_call_and_no_row_field(L, server, monkeypatch, arm):
    monkeypatch.delenv(L.TS_NDJSON_ENV, raising=False)
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    b = getattr(L, arm)()
    b.connect()
    assert b.q_high() == ROWS
    path, accept, body = Handler.seen[-1]
    assert accept == "*/*" and path == "/api/v1/query/bench" and body["limit"] == L.HTTP_LIMIT
    assert L.TS_RESULT_FORMAT_FIELD not in b.row_extra
    assert set(b.row_extra) == {"arcadedb_http_client"}


@pytest.mark.parametrize("arm", ["ArcadeTSServer", "ArcadeNativeTSServer"])
def test_set_sends_the_header_parses_the_rows_and_stamps(L, server, monkeypatch, arm):
    monkeypatch.setenv(L.TS_NDJSON_ENV, "1")
    monkeypatch.delenv(LH.CLIENT_ENV, raising=False)
    b = getattr(L, arm)()
    b.connect()
    assert b.q_high() == ROWS
    path, accept, body = Handler.seen[-1]
    assert accept == LH.NDJSON_ACCEPT and path == "/api/v1/query/bench" and body["limit"] == L.HTTP_LIMIT
    assert b.row_extra[L.TS_RESULT_FORMAT_FIELD] == "ndjson"
    Handler.returned = 1
    with pytest.raises(LH.NdjsonError):
        b.q_high()


def test_both_served_arms_are_override_carriers(L):
    import overrides
    o = {x.key: x for x in overrides.OVERRIDES}["ts_ndjson"]
    assert {(c.lane, c.backend) for c in o.carriers} == {("l4", L.ArcadeTSServer.name), ("l4", L.ArcadeNativeTSServer.name)}
    assert all(c.field == L.TS_RESULT_FORMAT_FIELD for c in o.carriers)
    assert o.in_manifest is False
    assert o.applies({"arcadedb_ts_result_format": "ndjson"}) and not o.applies({})
    assert o.check({}, "ndjson") is None and o.check({}, "json")
    import re
    text, _ = o.sentence([])
    assert all(re.search(p, text) for p in o.says)


def test_runner_forwards_the_switch_into_the_container():
    assert '"BENCH_ARCADEDB_TS_NDJSON"' in (HERE / "runner.py").read_text()


# ------------------------------------------------------------------------------------------------ the /next page
def _row(**kw):
    r = {"lane": "l4", "instrument": "2026-10", "backend": "arcadedb_ts_native_server", "q_high_ms": 1911.2}
    r.update(kw)
    return r


def test_the_page_promises_no_stream(EW, monkeypatch):
    """The switch measured mixed at ts100 (documents 0.853 [0.713, 0.928], native 1.087 [1.083, 1.088] with the merged
    whole-body reader), so it stays off at 26.11.1 and the page says nothing about it: no table sentence, no
    next-measurement line (CAMPAIGN section 7 row 85)."""
    assert not hasattr(EW, "_ts_ndjson_note")
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "SKELETON", False)
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [{"backend": "arcadedb_embedded", "engine_version": "26.10.1"}])
    monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
    out = EW._next_measurement_note([{"id": "l4", "title": "Time series", "conditions": []}])
    assert not [x for x in out if "stream" in x]
