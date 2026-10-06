"""A lean HTTP client for ArcadeDB's served arms: one persistent http.client connection per host, in place of requests.Session.

WHY (levers audit 2026-10-06, `.notes/bench/repros/levers-audit-20261006/LEAN-HTTP.md`). Every served ArcadeDB statement is one HTTP round
trip, and about three quarters of that round trip was the Python client, not the engine: against one ArcadeDB 26.10.1 server a bound one-row
read costs 468 to 628 us through `requests.Session`, 119 to 150 us through a persistent `http.client` connection (3.9x), the server being
the same. Every comparator on the tables is driven by its own official driver (Bolt, the Postgres wire, the Mongo wire, ...), none of which
pays a `requests`-sized client overhead, so the served ArcadeDB column measured the client library as much as the engine. This module is the
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
the October behaviour stays reproducible; the default is `lean`. `row_fields(session)` is what a row records.
"""
import base64
import gzip
import http.client
import json as _json
import os
import select
import socket
import ssl
import urllib.parse
import zlib

CLIENT_ENV = "BENCH_ARCADEDB_HTTP_CLIENT"
LEAN = "lean"
REQUESTS = "requests"
LEAN_NAME = "lean_http (http.client, keep-alive)"


def client_choice():
    """'lean' (the default) or 'requests', from BENCH_ARCADEDB_HTTP_CLIENT; anything else is refused rather than guessed."""
    v = (os.environ.get(CLIENT_ENV) or "").strip().lower()
    if v in ("", LEAN):
        return LEAN
    if v == REQUESTS:
        return REQUESTS
    raise ValueError(f"{CLIENT_ENV} must be 'lean' or 'requests', got {v!r}")


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


# ------------------------------------------------------------------------------------------------------ the factory
def Session():  # noqa: N802 - requests' own spelling, so a lane changes by one import
    """The ArcadeDB served arms' session: lean by default, `requests.Session` when BENCH_ARCADEDB_HTTP_CLIENT=requests."""
    if client_choice() == REQUESTS:
        import requests
        s = requests.Session()
        s.client_name = f"requests {requests.__version__}"
        return s
    return LeanSession()


def row_fields(session):
    """What a served ArcadeDB row records about its client, read from the session it ran with (not from the environment)."""
    return {"arcadedb_http_client": getattr(session, "client_name", None) or type(session).__module__ + "." + type(session).__name__}
