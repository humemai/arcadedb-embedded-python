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

A session is for one thread. `row_fields(session)` is what a row records.

THE CLIENT (CAMPAIGN section 7 rows 72 and 82): the headline is `official`, the vendor's own `arcadedb-driver` (sync, httpx) for every
`/query` and `/command` call, and this client is the labelled sensitivity row (the runner schedules it as a twin cell and sets
`BENCH_ARCADEDB_HTTP_CLIENT=lean` for it). Bulk loads, the server probe, transactions and NDJSON streams stay on this client.
"""
import base64
import gzip
import http.client
import io
import json as _json
import os
import re
import select
import socket
import ssl
import urllib.parse
import zlib

CLIENT_ENV = "BENCH_ARCADEDB_HTTP_CLIENT"
LEAN = "lean"
OFFICIAL = "official"
OFFICIAL_PIN = "0.2.0"       # the arcadedb-driver release the 2026-11 headline measures; recorded per row from the installed package
LEAN_NAME = "lean_http (http.client, keep-alive)"


def client_choice():
    """'official' (the headline, the default) or 'lean' (the sensitivity twin), from BENCH_ARCADEDB_HTTP_CLIENT, which the runner
    sets for the twin cell; anything else is refused rather than guessed."""
    v = (os.environ.get(CLIENT_ENV) or "").strip().lower()
    if v in ("", OFFICIAL):
        return OFFICIAL
    if v == LEAN:
        return LEAN
    raise ValueError(f"{CLIENT_ENV} must be 'official' or 'lean', got {v!r}")


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


# ----------------------------------------------------------------------------------------------- the official driver
_DATA_URL = re.compile(r"^(?P<root>https?://[^/]+)/api/v1/(?P<kind>query|command)/(?P<db>[^/?#]+)$")


class _OfficialResponse:
    """What an official-driver call returns, in the part of requests' Response the lanes read: the answer is the envelope the driver
    already parsed, so `.json()` hands it back as it is and nothing is serialised inside the timed call. `.content` and `.text` encode it
    on demand (a lane that reads them pays for them, as it would on any client)."""

    def __init__(self, status_code, obj, url, reason=""):
        self.status_code, self._obj, self.url, self.reason, self.headers = status_code, obj, url, reason, {}

    ok = property(lambda self: self.status_code < 400)

    def json(self):
        return self._obj

    @property
    def content(self):
        return _json.dumps(self._obj, default=str).encode("utf-8")

    @property
    def text(self):
        return self.content.decode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Server Error: {self.reason} for url: {self.url}", response=self)


class OfficialSession:
    """The official `arcadedb-driver` (sync, httpx) behind the part of `requests.Session` the lanes use, so a lane changes by no line.

    Every `POST /api/v1/query/<db>` and `/command/<db>` whose body is `{language, command, params?, limit?}` goes through
    `ArcadeDBServer(...).db(<db>).query(...)` or `.command(...)`, which is what the vendor documents for a Python client. Everything
    else goes through a `LeanSession`: the `GET /server` probe, the bulk `/batch` load, transactions (`begin`/`commit`/`rollback` and any
    call carrying a session id), NDJSON streams, raw text bodies, and a body with a field the driver has no argument for. Bulk loads stay
    on HTTP `batch` and `command` as the protocol-audit decision says; the driver's `batch_load` is a different request shape and is not
    used. `official_calls` and `fallback_calls` count the two (a test reads them).
    """

    client_name = None   # set per instance from the installed package

    def __init__(self):
        import arcadedb_driver
        from arcadedb_driver.auth import basic_auth
        self._driver, self._basic_auth = arcadedb_driver, basic_auth
        self.version = getattr(arcadedb_driver, "__version__", None) or _driver_version()
        self.client_name = f"arcadedb-driver {self.version} (sync, httpx)"
        self.auth = None
        self._servers = {}
        self._fallback = LeanSession()
        self.official_calls = 0
        self.fallback_calls = 0

    def _server(self, root, auth):
        key = (root, auth)
        srv = self._servers.get(key)
        if srv is None:
            user, password = auth
            srv = self._driver.ArcadeDBServer(base_url=root, auth=self._basic_auth(user, password))
            self._servers[key] = srv
        return srv

    def get(self, url, **kw):
        kw.setdefault("auth", self.auth)
        self.fallback_calls += 1
        return self._fallback.get(url, **kw)

    def post(self, url, json=None, data=None, auth=None, headers=None, timeout=None, **kw):
        auth = auth or self.auth
        m = _DATA_URL.match(url)
        if (m and auth and isinstance(json, dict) and data is None and not headers and not kw
                and set(json) <= {"language", "command", "params", "limit"}
                and "language" in json and "command" in json
                and not (m["kind"] == "command" and "limit" in json)):
            srv = self._server(m["root"], tuple(auth))
            db = srv.db(m["db"])
            self.official_calls += 1
            try:
                if m["kind"] == "query":
                    env = db.query(language=json["language"], command=json["command"], params=json.get("params"), limit=json.get("limit"))
                else:
                    env = db.command(language=json["language"], command=json["command"], params=json.get("params"))
            except self._driver.ArcadeDBError as e:
                return _OfficialResponse(e.status, {"error": e.error, "detail": e.detail, "exception": e.exception}, url, e.error or "")
            return _OfficialResponse(200, {"result": env.result, "limit": env.limit, "returned": env.returned, "truncated": env.truncated}, url, "OK")
        self.fallback_calls += 1
        return self._fallback.post(url, json=json, data=data, auth=auth or self.auth, headers=headers, timeout=timeout, **kw)

    def close(self):
        for srv in self._servers.values():
            try:
                srv.close()
            except Exception:  # noqa: BLE001 - closing must not fail a cell
                pass
        self._servers.clear()
        self._fallback.close()


def _driver_version():
    try:
        from importlib.metadata import version
        return version("arcadedb-driver")
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------------ the factory
def Session():  # noqa: N802 - requests' own spelling, so a lane changes by one import
    """The ArcadeDB served arms' session: the official driver (the headline), or `LeanSession` when BENCH_ARCADEDB_HTTP_CLIENT=lean."""
    return OfficialSession() if client_choice() == OFFICIAL else LeanSession()


def row_fields(session):
    """What a served ArcadeDB row records about its client, read from the session it ran with (not from the environment)."""
    out = {"arcadedb_http_client": getattr(session, "client_name", None) or type(session).__module__ + "." + type(session).__name__}
    if isinstance(session, OfficialSession):
        out["arcadedb_http_client_role"] = "headline"
    elif os.environ.get("BENCH_ARCADEDB_CLIENT_ROLE"):
        out["arcadedb_http_client_role"] = os.environ["BENCH_ARCADEDB_CLIENT_ROLE"]
    return out


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
