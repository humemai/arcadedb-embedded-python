"""A lean HTTP client for ArcadeDB's served arms: one persistent http.client connection per host, in place of requests.Session.

WHY (levers audit 2026-10-06, `.notes/bench/repros/levers-audit-20261006/LEAN-HTTP.md`). Every served ArcadeDB statement is one HTTP round
trip, and about three quarters of that round trip was the Python client, not the engine: against one ArcadeDB 26.10.1 server a bound one-row
read costs 468 to 628 us through `requests.Session`, 119 to 150 us through a persistent `http.client` connection (3.9x), the server being
the same. The comparators are driven by their vendors' own clients, which differ in weight: the Postgres and Mongo wire clients are light, but
python-arango is `requests`, qdrant-client over REST is httpx plus pydantic, and elasticsearch-py is urllib3, so `requests` was heavier than most
and the served ArcadeDB column measured the client library as much as the engine. This client is lighter than the official `arcadedb-driver`
(httpx, published 2026-10-06), which measured 3.2x slower on a one-row read (protocol audit round 3); the 26.11.1 re-measure headlines the
official driver and keeps this client as a disclosed sensitivity row. This module is the
one place the lanes get their ArcadeDB HTTP session from; a lane changes by one import.

The interface is the part of `requests.Session` the lanes use: `.auth` (a (user, password) tuple, sent as Basic), `.get(url, auth=, headers=, timeout=)`,
`.post(url, json=, data=, auth=, headers=, timeout=)` (a per-call `auth=` tuple replaces the session's for that call, as in requests; the e4
deployment decomposition passes it), `.close()`, and a response with `.status_code`, `.reason`, `.headers`, `.content`, `.text`,
`.url`, `.ok`, `.json()`, and `.raise_for_status()` whose message is requests' own (`"500 Server Error: <reason> for url: <url>"`).

WHAT IS THE SAME AS requests: the request line, `Authorization: Basic`, `Accept: */*`, `Accept-Encoding: gzip, deflate` (and the response is decoded
the same way, so the server does the same work), `Connection: keep-alive`, `Content-Type: application/json` and a body of
`json.dumps(obj, allow_nan=False).encode("utf-8")` for `json=`, chunked transfer for an iterator `data=`, TCP_NODELAY (without it a request sent
in two writes waits for a delayed ACK, 42 ms a call), the per-call `timeout` as a per-operation socket timeout, an idle connection the server has
closed is replaced before it is used (urllib3 does the same check), and 4xx and 5xx statuses raise only from `raise_for_status()`. The one header
that differs is `User-Agent`.

WHAT DIFFERS ON PURPOSE: the exceptions are this module's (`HTTPError`, `ConnectionError`, `Timeout`, all `OSError` subclasses, as requests' are, and
`Timeout` is a `TimeoutError` too); no lane catches a `requests` exception class by name (checked: every handler around these calls is `except
Exception`, `BaseException`, or none). There are no redirects, cookies, proxies, or TLS verification options: the lanes need none of them, and a 3xx
is returned as it is. A request that dies after it was sent on a reused connection (the server closed it at the same moment) is retried once ONLY
when it is a read (a GET, or a POST to a `/query/` or `/server` endpoint); a write raises `ConnectionError`, as requests' does, so a statement is
never run twice. A request that dies while it is still being SENT (`BrokenPipeError`, `ConnectionResetError`: a server that refuses early answers and
closes) raises a `ConnectionError` that carries the status and the first 500 bytes of the answer the server had already sent, so a refusal
says why (ArcadeDB 26.10.1's 100 MiB request-body limit looked like `[Errno 32] Broken pipe` until this).

A session is for one thread. `BENCH_ARCADEDB_HTTP_CLIENT=requests` restores the October client (`Session()` then returns a `requests.Session`), so
the October behaviour stays reproducible; the default is `lean`. `BENCH_ARCADEDB_HTTP_CLIENT=lean2` selects `LeanSession2`, the same client over a bare socket (see its docstring), OFF
unless asked for. `row_fields(session)` is what a row records.
"""
import base64
import gzip
import http.client
import io
import json as _json
import os
import select
import socket
import ssl
import urllib.parse
import zlib

CLIENT_ENV = "BENCH_ARCADEDB_HTTP_CLIENT"
LEAN = "lean"
LEAN2 = "lean2"
REQUESTS = "requests"
LEAN_NAME = "lean_http (http.client, keep-alive)"
LEAN2_NAME = "lean_http2 (socket, keep-alive)"


def client_choice():
    """'lean' (the default), 'lean2', or 'requests', from BENCH_ARCADEDB_HTTP_CLIENT; anything else is refused rather than guessed."""
    v = (os.environ.get(CLIENT_ENV) or "").strip().lower()
    if v in ("", LEAN):
        return LEAN
    if v == REQUESTS:
        return REQUESTS
    if v == LEAN2:
        return LEAN2
    raise ValueError(f"{CLIENT_ENV} must be 'lean', 'lean2', or 'requests', got {v!r}")


# ------------------------------------------------------------------------------------------------------ exceptions
class RequestException(OSError):
    """The base of this module's errors (requests' is an IOError too, which is OSError)."""

    def __init__(self, *args, response=None):
        super().__init__(*args)
        self.response = response


class HTTPError(RequestException):
    """A 4xx or 5xx status, raised by Response.raise_for_status()."""


class InvalidJSONError(RequestException):
    """A `json=` body that cannot be encoded (a NaN or an infinity, with allow_nan=False): requests raises its InvalidJSONError, an OSError."""


class ConnectionError(RequestException):  # noqa: A001 - requests' own name, for the same meaning
    """The server could not be reached, or closed the connection before it answered."""


class Timeout(RequestException, TimeoutError):
    """A socket operation took longer than the call's timeout."""


ReadTimeout = Timeout


# -------------------------------------------------------------------------------------------------------- response
class Response:
    """What a call returns. The body is read in full (no streaming: no lane asks for it)."""

    __slots__ = ("status_code", "reason", "headers", "content", "url", "_text")

    def __init__(self, status_code, reason, headers, content, url):
        self.status_code, self.reason, self.headers, self.content, self.url = status_code, reason, headers, content, url
        self._text = None

    @property
    def ok(self):
        return self.status_code < 400

    @property
    def encoding(self):
        ctype = self.headers.get("Content-Type") or ""
        for part in ctype.split(";")[1:]:
            k, _, v = part.strip().partition("=")
            if k.lower() == "charset" and v:
                return v.strip("\"'")
        return "utf-8"

    @property
    def text(self):
        if self._text is None:
            try:
                self._text = self.content.decode(self.encoding, "replace")
            except LookupError:
                self._text = self.content.decode("utf-8", "replace")
        return self._text

    def json(self, **kwargs):
        # json.loads on the text: an empty or non-JSON body raises json.JSONDecodeError, a ValueError, as requests' does
        return _json.loads(self.text, **kwargs)

    def raise_for_status(self):
        reason = self.reason
        if isinstance(reason, bytes):
            try:
                reason = reason.decode("utf-8")
            except UnicodeDecodeError:
                reason = reason.decode("iso-8859-1")
        if 400 <= self.status_code < 500:
            msg = f"{self.status_code} Client Error: {reason} for url: {self.url}"
        elif 500 <= self.status_code < 600:
            msg = f"{self.status_code} Server Error: {reason} for url: {self.url}"
        else:
            return
        raise HTTPError(msg, response=self)

    def __repr__(self):
        return f"<Response [{self.status_code}]>"


def _decode_body(raw, encoding):
    enc = (encoding or "").strip().lower()
    if not raw or enc in ("", "identity"):
        return raw
    if enc == "gzip" or enc == "x-gzip":
        return gzip.decompress(raw)
    if enc == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)  # a raw deflate stream, which some servers send
    return raw


# How much of an early answer goes into a ConnectionError, and how long the client waits for one (bytes, seconds).
EARLY_ANSWER_BYTES = 500
EARLY_ANSWER_WAIT_S = 5.0


def _early_answer(conn):
    """What the server already answered to a request it stopped reading, as `"413 Request Entity Too Large: <first 500 bytes of the body>"`, or None.

    A server that refuses a request early (ArcadeDB 26.10.1 refuses a bulk load whose body passes `arcadedb.server.httpBodyContentMaxSize`)
    sends its answer and closes the connection while the client is still writing, so the client's next write fails with BrokenPipeError or
    ConnectionResetError and its own message says nothing about why. The answer is usually already in the socket's receive buffer, so one
    guarded read of it turns "[Errno 32] Broken pipe" into the server's own words. It waits at most EARLY_ANSWER_WAIT_S, never raises, and
    leaves the connection to the caller to drop.
    """
    try:
        if conn.sock is None:
            return None
        conn.sock.settimeout(EARLY_ANSWER_WAIT_S)
        resp = conn.getresponse()
        text = resp.read(EARLY_ANSWER_BYTES).decode("utf-8", "replace").strip()
        return f"{resp.status} {resp.reason}" + (f": {text}" if text else "")
    except Exception:  # noqa: BLE001 - a read that fails says nothing more than the error it was asked to explain
        return None


# --------------------------------------------------------------------------------------------------------- session
def _is_read(method, path):
    return method == "GET" or "/query/" in path or path.rstrip("/").endswith("/server") or "/server?" in path


class LeanSession:
    """requests.Session's surface for the lanes, over one persistent http.client connection per (scheme, host, port)."""

    client_name = LEAN_NAME

    def __init__(self):
        self.auth = None
        self._conns = {}

    # -- connections
    def _connect(self, scheme, host, port, timeout):
        if scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.connect()
        conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return conn

    def _conn_for(self, key, timeout):
        """The live connection for the key, or a new one: an idle connection the server closed (readable at EOF) is dropped first."""
        conn = self._conns.get(key)
        if conn is not None and conn.sock is not None:
            try:
                readable, _, _ = select.select([conn.sock], [], [], 0)
            except (OSError, ValueError):
                readable = [conn.sock]
            if readable:
                self._drop(key)
                conn = None
        if conn is None or conn.sock is None:
            self._drop(key)
            try:
                conn = self._connect(key[0], key[1], key[2], timeout)
            except socket.timeout as e:
                raise Timeout(f"connect to {key[1]}:{key[2]} timed out") from e
            except OSError as e:
                raise ConnectionError(f"cannot connect to {key[1]}:{key[2]}: {e}") from e
            self._conns[key] = conn
            return conn, False
        return conn, True

    def _drop(self, key):
        conn = self._conns.pop(key, None)
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass

    def close(self):
        for key in list(self._conns):
            self._drop(key)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- requests
    def _headers(self, extra, has_json, auth=None):
        h = {
            "User-Agent": "lean_http/1 (http.client)",
            "Accept-Encoding": "gzip, deflate",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        auth = auth if auth is not None else self.auth
        if auth:
            user, password = auth
            h["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode("latin-1")).decode("ascii")
        if has_json:
            h["Content-Type"] = "application/json"
        if extra:
            h.update({str(k): str(v) for k, v in extra.items()})
        return h

    def request(self, method, url, json=None, data=None, headers=None, timeout=None, auth=None):
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme or "http"
        host = parts.hostname
        port = parts.port or (443 if scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        key = (scheme, host, port)
        if json is not None:
            try:
                body = _json.dumps(json, allow_nan=False).encode("utf-8")
            except ValueError as e:
                raise InvalidJSONError(e) from e
        elif data is None:
            body = None
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = data  # bytes, or an iterator of bytes (sent chunked)
        replayable = body is None or isinstance(body, (bytes, bytearray))
        hdrs = self._headers(headers, json is not None, auth)
        retried = False
        while True:
            conn, reused = self._conn_for(key, timeout)
            conn.timeout = timeout
            conn.sock.settimeout(timeout)
            try:
                conn.request(method, path, body=body, headers=hdrs)
                resp = conn.getresponse()
                raw = resp.read()
            except socket.timeout as e:
                self._drop(key)
                raise Timeout(f"{method} {url} timed out after {timeout} s") from e
            except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError,
                    http.client.CannotSendRequest, http.client.NotConnected, http.client.BadStatusLine) as e:
                sent_but_unanswered = isinstance(e, (http.client.RemoteDisconnected, ConnectionResetError, http.client.BadStatusLine))
                safe = replayable and (not sent_but_unanswered or _is_read(method, path))
                if reused and not retried and safe:
                    self._drop(key)
                    retried = True
                    continue
                # Raising: first read the answer the server may already have given to a request that died while it was being SENT
                # (see _early_answer). RemoteDisconnected and BadStatusLine come from the read itself, so there is nothing more to read.
                early = None
                if isinstance(e, (BrokenPipeError, ConnectionResetError)) and not isinstance(e, http.client.RemoteDisconnected):
                    early = _early_answer(conn)
                self._drop(key)
                raise ConnectionError(f"{method} {url}: {e}" + (f" (the server had already answered {early})" if early else "")) from e
            except OSError as e:
                self._drop(key)
                raise ConnectionError(f"{method} {url}: {e}") from e
            if resp.will_close:
                self._drop(key)
            raw = _decode_body(raw, resp.getheader("Content-Encoding"))
            return Response(resp.status, resp.reason, resp.msg, raw, url)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, data=None, json=None, **kw):
        return self.request("POST", url, json=json, data=data, **kw)


LEAN2_UA = "lean_http/2 (socket)"
_RECV_BUF = 65536
_INLINE_BODY = 16384          # a request whose head and body fit in this many bytes goes out in ONE write
_CACHE_MAX = 256


class _Headers2:
    """The answer's header block, parsed into http.client's own message class only when a caller reads `.headers`."""

    __slots__ = ("_raw", "_msg")

    def __init__(self, raw):
        self._raw, self._msg = raw, None

    def msg(self):
        if self._msg is None:
            self._msg = http.client.parse_headers(io.BytesIO(self._raw + b"\r\n\r\n"))
        return self._msg


class Response2(Response):
    """Response for LeanSession2: same fields and methods; `headers` is parsed on first use, `encoding` comes from the scan of the answer."""

    __slots__ = ("_hdr", "_charset")

    def __init__(self, status_code, reason, hdr, content, url, charset):
        self.status_code, self.reason, self.content, self.url = status_code, reason, content, url
        self._text, self._hdr, self._charset = None, hdr, charset

    @property
    def headers(self):
        return self._hdr.msg()

    @property
    def encoding(self):
        return self._charset


def _charset_of(ctype):
    """Response.encoding's rule, on the raw Content-Type value."""
    for part in ctype.split(";")[1:]:
        k, _, v = part.strip().partition("=")
        if k.lower() == "charset" and v:
            return v.strip("\"'")
    return "utf-8"


def _header_value(head, hl, name):
    """The value of header `name` (lower-case, written "\r\nname:") in a header block, or None. `hl` is `head` lower-cased."""
    k = hl.find(name)
    if k < 0:
        return None
    k += len(name)
    e = hl.find(b"\r\n", k)
    return head[k:e if e >= 0 else len(head)].strip()


class _Sock2:
    """One persistent socket with its receive buffer and the timeout it was last given."""

    __slots__ = ("sock", "poll", "timeout", "buf", "mv")

    def __init__(self, sock):
        self.sock = sock
        self.poll = select.poll()
        self.poll.register(sock, select.POLLIN)
        self.timeout = None
        self.buf = bytearray(_RECV_BUF)
        self.mv = memoryview(self.buf)


class LeanSession2(LeanSession):
    """LeanSession over a bare socket: the same requests on the wire, the same answers, less Python per call (BENCH_ARCADEDB_HTTP_CLIENT=lean2).

    WHY (perf-served-point 2026-10-08): a served bound Cypher point read cost about 102 us, and `LeanSession` used 82 us of client CPU of it,
    a hand-built socket 17 us; the rest was http.client's request building, its parsing of every answer header into a message object, and
    the layers around them. WHAT IS THE SAME: the HTTP/1.1 request bytes (request line, `Host`, `Accept-Encoding: gzip, deflate`, `Accept`,
    `Connection: keep-alive`, Basic `Authorization`, `Content-Type`, `Content-Length`; only `User-Agent` differs, as it does between lean and
    requests), the JSON body (the encoding `json.dumps(obj, allow_nan=False)` builds), one persistent connection per (scheme, host, port) with
    TCP_NODELAY, the check that drops a connection the server closed while idle, the per-call timeout, the retry of a read (never of a
    write) that died on a reused connection, the early-answer message for a request that died while being sent, content-coding decoding,
    chunked and close-delimited answers, 1xx interim answers, and the `Response` interface (`.headers` is the same `http.client.HTTPMessage`,
    built on first use).
    WHAT IS DONE ONCE INSTEAD OF PER CALL: the URL split and the request head are cached per (method, url, auth, headers), and the encoder is
    built once. WHAT IS DONE IN LESS: the answer's head is scanned for the six fields the client needs (status, Content-Length,
    Transfer-Encoding, Content-Encoding, Content-Type, Connection) instead of being parsed into a header table, and the answer is read with
    `recv_into` on one buffer. A request with an iterator body (`data=`), or with its own Content-Length header, is sent by the parent's
    http.client path. Nothing about an answer is cached, and every answer is read, decoded, and returned in full.
    """

    client_name = LEAN2_NAME
    _encode = _json.JSONEncoder(allow_nan=False).encode          # what json.dumps(obj, allow_nan=False) builds on every call

    def __init__(self):
        super().__init__()
        self._socks = {}
        self._urls = {}
        self._heads = {}

    # -- connections
    def _conn2(self, key, timeout):
        c = self._socks.get(key)
        if c is not None:
            try:
                if c.poll.poll(0):
                    self._drop2(key)
                    c = None
            except (OSError, ValueError):
                self._drop2(key)
                c = None
        if c is not None:
            return c, True
        try:
            sock = socket.create_connection((key[1], key[2]), timeout)
            if key[0] == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=key[1])
        except socket.timeout as e:
            raise Timeout(f"connect to {key[1]}:{key[2]} timed out") from e
        except OSError as e:
            raise ConnectionError(f"cannot connect to {key[1]}:{key[2]}: {e}") from e
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        c = self._socks[key] = _Sock2(sock)
        c.timeout = timeout
        return c, False

    def _drop2(self, key):
        c = self._socks.pop(key, None)
        if c is not None:
            try:
                c.sock.close()
            except OSError:
                pass

    def close(self):
        for key in list(self._socks):
            self._drop2(key)
        super().close()

    # -- request head: (request line and Host, the other headers); http.client writes Content-Length between the two
    def _head(self, method, scheme, host, port, path, extra, has_json, auth):
        auth = auth if auth is not None else self.auth
        ck = (method, scheme, host, port, path, tuple(extra.items()) if extra else None, has_json, tuple(auth) if auth else None)
        head = self._heads.get(ck)
        if head is None:
            h = self._headers(extra, has_json, auth)
            h["User-Agent"] = LEAN2_UA
            hostname = f"[{host}]" if ":" in host else host
            hh = hostname if port == (443 if scheme == "https" else 80) else f"{hostname}:{port}"
            head = (f"{method} {path} HTTP/1.1\r\nHost: {hh}".encode("latin-1"),
                    "".join(f"\r\n{k}: {v}" for k, v in h.items()).encode("latin-1") + b"\r\n\r\n")
            if len(self._heads) >= _CACHE_MAX:
                self._heads.clear()
            self._heads[ck] = head
        return head

    # -- answer
    def _read_answer(self, c, method):
        """Read one complete answer: (status, reason, header block, its lower-case copy, body, will_close). Interim 1xx answers are skipped."""
        sock, buf, mv = c.sock, c.buf, c.mv
        have = 0
        while True:
            end = buf.find(b"\r\n\r\n", 0, have)
            while end < 0:
                if have == len(buf):
                    nb = bytearray(len(buf) * 2)
                    nb[:have] = mv[:have]
                    c.buf = buf = nb
                    c.mv = mv = memoryview(nb)
                n = sock.recv_into(mv[have:])
                if n == 0:
                    if have == 0:
                        raise http.client.RemoteDisconnected("Remote end closed connection without response")
                    raise http.client.BadStatusLine("connection closed inside an answer head")
                start = max(0, have - 3)
                have += n
                end = buf.find(b"\r\n\r\n", start, have)
            head = bytes(mv[:end])
            first_end = head.find(b"\r\n")
            status_line = head[:first_end] if first_end >= 0 else head
            try:
                if status_line[:5] != b"HTTP/":
                    raise ValueError
                status = int(status_line[9:12])
            except ValueError:
                raise http.client.BadStatusLine(status_line.decode("iso-8859-1")) from None
            if 100 <= status < 200 and status != 101:     # an interim answer: drop it, keep what follows
                rest = bytes(mv[end + 4:have])
                buf[:len(rest)] = rest
                have = len(rest)
                continue
            break
        reason = status_line[13:].decode("iso-8859-1") if len(status_line) > 13 else ""
        hblock = head[first_end:] if first_end >= 0 else b""
        hl = hblock.lower()
        conn_h = _header_value(hblock, hl, b"\r\nconnection:")
        conn_l = conn_h.lower() if conn_h is not None else b""
        will_close = b"close" in conn_l or (status_line[:8] == b"HTTP/1.0" and b"keep-alive" not in conn_l)
        body_start = end + 4
        if method == "HEAD" or status in (204, 304):
            return status, reason, hblock, hl, b"", will_close
        te = _header_value(hblock, hl, b"\r\ntransfer-encoding:")
        if te is not None and b"chunked" in te.lower():
            return status, reason, hblock, hl, self._read_chunked(sock, bytes(mv[body_start:have])), will_close
        cl = _header_value(hblock, hl, b"\r\ncontent-length:")
        if cl is not None:
            try:
                n = int(cl)
            except ValueError:
                raise http.client.BadStatusLine("bad Content-Length " + cl.decode("latin-1")) from None
            got = have - body_start
            if got >= n:
                if got > n:
                    will_close = True            # bytes nobody asked for: the stream is out of step, do not reuse it
                return status, reason, hblock, hl, bytes(mv[body_start:body_start + n]), will_close
            out = bytearray(n)
            out[:got] = mv[body_start:have]
            ov = memoryview(out)
            while got < n:
                k = sock.recv_into(ov[got:])
                if k == 0:
                    raise http.client.IncompleteRead(bytes(out[:got]), n - got)
                got += k
            return status, reason, hblock, hl, bytes(out), will_close
        out = bytearray(mv[body_start:have])          # no length, not chunked: the body runs to the end of the stream
        while True:
            k = sock.recv_into(mv)
            if k == 0:
                break
            out += mv[:k]
        return status, reason, hblock, hl, bytes(out), True

    @staticmethod
    def _read_chunked(sock, data):
        buf = bytearray(data)
        out = bytearray()
        pos = 0

        def more():
            k = sock.recv(_RECV_BUF)
            if not k:
                raise http.client.IncompleteRead(bytes(out))
            buf.extend(k)

        while True:
            e = buf.find(b"\r\n", pos)
            while e < 0:
                more()
                e = buf.find(b"\r\n", pos)
            size = int(bytes(buf[pos:e]).split(b";")[0].strip() or b"0", 16)
            pos = e + 2
            if size == 0:
                while True:                                   # trailers, up to the empty line
                    e = buf.find(b"\r\n", pos)
                    while e < 0:
                        more()
                        e = buf.find(b"\r\n", pos)
                    last = e == pos
                    pos = e + 2
                    if last:
                        return bytes(out)
            while len(buf) < pos + size + 2:
                more()
            out += buf[pos:pos + size]
            pos += size + 2

    @staticmethod
    def _early_answer2(c):
        try:
            c.sock.settimeout(EARLY_ANSWER_WAIT_S)
            data = c.sock.recv(4096)
            line, _, rest = data.partition(b"\r\n")
            _, _, body = rest.partition(b"\r\n\r\n")
            parts = line.decode("iso-8859-1").split(" ", 2)
            text = body[:EARLY_ANSWER_BYTES].decode("utf-8", "replace").strip()
            return f"{parts[1]} {parts[2] if len(parts) > 2 else ''}" + (f": {text}" if text else "")
        except Exception:  # noqa: BLE001 - as _early_answer
            return None

    # -- requests
    def request(self, method, url, json=None, data=None, headers=None, timeout=None, auth=None):
        if (data is not None and not isinstance(data, (str, bytes, bytearray))) or (
                headers and any(str(k).lower() == "content-length" for k in headers)):
            return super().request(method, url, json=json, data=data, headers=headers, timeout=timeout, auth=auth)
        parsed = self._urls.get(url)
        if parsed is None:
            parts = urllib.parse.urlsplit(url)
            scheme = parts.scheme or "http"
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            parsed = (scheme, parts.hostname, parts.port or (443 if scheme == "https" else 80), path)
            if len(self._urls) >= _CACHE_MAX:
                self._urls.clear()
            self._urls[url] = parsed
        scheme, host, port, path = parsed
        key = (scheme, host, port)
        if json is not None:
            try:
                body = self._encode(json).encode("utf-8")
            except ValueError as e:
                raise InvalidJSONError(e) from e
        elif data is None:
            body = None
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = bytes(data)
        head = self._head(method, scheme, host, port, path, headers, json is not None, auth)
        tail = None
        if body is None:
            wire = head[0] + (b"\r\nContent-Length: 0" if method in ("POST", "PUT", "PATCH") else b"") + head[1]
        else:
            wire = head[0] + b"\r\nContent-Length: %d" % len(body) + head[1]
            if len(wire) + len(body) <= _INLINE_BODY:
                wire += body
            else:
                tail = body
        retried = False
        while True:
            c, reused = self._conn2(key, timeout)
            if c.timeout != timeout:
                c.sock.settimeout(timeout)
                c.timeout = timeout
            try:
                c.sock.sendall(wire)
                if tail is not None:
                    c.sock.sendall(tail)
                status, reason, hblock, hl, raw, will_close = self._read_answer(c, method)
            except socket.timeout as e:
                self._drop2(key)
                raise Timeout(f"{method} {url} timed out after {timeout} s") from e
            except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, http.client.BadStatusLine) as e:
                sent_but_unanswered = isinstance(e, (http.client.RemoteDisconnected, ConnectionResetError, http.client.BadStatusLine))
                if reused and not retried and (not sent_but_unanswered or _is_read(method, path)):
                    self._drop2(key)
                    retried = True
                    continue
                early = None
                if isinstance(e, (BrokenPipeError, ConnectionResetError)) and not isinstance(e, http.client.RemoteDisconnected):
                    early = self._early_answer2(c)
                self._drop2(key)
                raise ConnectionError(f"{method} {url}: {e}" + (f" (the server had already answered {early})" if early else "")) from e
            except (http.client.IncompleteRead, OSError) as e:
                self._drop2(key)
                raise ConnectionError(f"{method} {url}: {e}") from e
            if will_close:
                self._drop2(key)
            if raw:
                ce = _header_value(hblock, hl, b"\r\ncontent-encoding:")
                if ce is not None:
                    raw = _decode_body(raw, ce.decode("latin-1"))
            ctype = _header_value(hblock, hl, b"\r\ncontent-type:")
            return Response2(status, reason, _Headers2(hblock[2:]), raw, url,
                             _charset_of(ctype.decode("latin-1")) if ctype is not None else "utf-8")


# ------------------------------------------------------------------------------------------------------ the factory
def Session():  # noqa: N802 - requests' own spelling, so a lane changes by one import
    """The ArcadeDB served arms' session: lean by default, LeanSession2 when BENCH_ARCADEDB_HTTP_CLIENT=lean2, `requests.Session` when it is `requests`."""
    choice = client_choice()
    if choice == LEAN2:
        return LeanSession2()
    if choice == REQUESTS:
        import requests
        s = requests.Session()
        s.client_name = f"requests {requests.__version__}"
        return s
    return LeanSession()


def row_fields(session):
    """What a served ArcadeDB row records about its client, read from the session it ran with (not from the environment)."""
    return {"arcadedb_http_client": getattr(session, "client_name", None) or type(session).__module__ + "." + type(session).__name__}


# --------------------------------------------------------------------------------------------- streamed (NDJSON) results
# ArcadeDB's query endpoint answers `Accept: application/x-ndjson` with a chunked body of one `{"record": {...}}` line per row and a last
# `{"stats": {"returned": N}}` line, so the server sends rows as it produces them instead of building the whole answer first (26.10.1). The
# served time-series arms read their results this way under BENCH_ARCADEDB_TS_NDJSON=1 (CAMPAIGN section 7 row 85). The body is read in full
# by whichever session the lane runs (each one de-chunks and decodes it) and parsed in ONE json.loads, the lines joined into a JSON array;
# the answer is the same rows the buffered call's `result` holds, checked against the server's own count.
NDJSON_ACCEPT = "application/x-ndjson"


class NdjsonError(ValueError):
    """A streamed answer that is not records followed by a count that matches them."""


def ndjson_records(body):
    """The rows of an NDJSON query answer (bytes), after checking the stats line's `returned` against the number of records."""
    lines = [ln for ln in body.split(b"\n") if ln.strip()]
    if not lines:
        raise NdjsonError("empty NDJSON answer: no stats line")
    objs = _json.loads(b"[" + b",".join(lines) + b"]")
    rows, stats = [], None
    for o in objs:
        rec = o.get("record", _MISSING) if isinstance(o, dict) else _MISSING
        if rec is not _MISSING and stats is None:
            rows.append(rec)
        elif isinstance(o, dict) and "stats" in o and stats is None:
            stats = o["stats"]
        else:
            raise NdjsonError(f"unexpected NDJSON line {str(o)[:200]!r} (a record after the stats line, or not a record or stats line)")
    if stats is None:
        raise NdjsonError(f"NDJSON answer of {len(rows)} records has no stats line")
    if stats.get("returned") != len(rows):
        raise NdjsonError(f"NDJSON stats say returned={stats.get('returned')!r} but {len(rows)} records arrived")
    return rows


_MISSING = object()


def post_ndjson(session, url, json, timeout=None):
    """POST a query asking for NDJSON, raise on an HTTP error, and return its rows (`ndjson_records`)."""
    r = session.post(url, json=json, headers={"Accept": NDJSON_ACCEPT}, timeout=timeout)
    r.raise_for_status()
    return ndjson_records(r.content)
