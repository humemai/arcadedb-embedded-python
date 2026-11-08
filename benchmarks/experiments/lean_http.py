"""A lean HTTP client for ArcadeDB's served arms: one persistent http.client connection per host, in place of requests.Session.

WHY (levers audit 2026-10-06, `.notes/bench/repros/levers-audit-20261006/LEAN-HTTP.md`). Every served ArcadeDB statement is one HTTP round
trip, and about three quarters of that round trip was the Python client, not the engine: against one ArcadeDB 26.10.1 server a bound one-row
read costs 468 to 628 us through `requests.Session`, 119 to 150 us through a persistent `http.client` connection (3.9x), the server being
the same. The comparators are driven by their vendors' own clients, which differ in weight: the Postgres and Mongo wire clients are light, but
python-arango is `requests`, qdrant-client over REST is httpx plus pydantic, and elasticsearch-py is urllib3, so `requests` was heavier than most
and the served ArcadeDB column measured the client library as much as the engine. This client is the headline client of the served ArcadeDB
rows: the page and the paper name it as the benchmark's own minimal HTTP client, and say that the other engines are measured through their
vendors' own Python clients, so client weight differs between the served engines (DECISIONS #268, #285). This module is the
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

THE CLIENT (CAMPAIGN section 7 rows 72 and 82): the published cell of a served ArcadeDB arm is the one measured through this client
(the runner schedules the cell as a second job and sets `BENCH_ARCADEDB_HTTP_CLIENT=lean` for it; the freeze keeps those rows and sets
the other client's rows aside). Bulk loads, the server probe, transactions and NDJSON streams use this client in every job.
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
import threading
import time
import urllib.parse
import zlib

CLIENT_ENV = "BENCH_ARCADEDB_HTTP_CLIENT"
LEAN = "lean"
OFFICIAL = "official"
PGWIRE = "pgwire"            # the PostgreSQL-wire twin of the served SQL arms (DECISIONS #166, #171, #237): SQL reads over psycopg, all else over lean HTTP
PG_PORT_ENV = "BENCH_ARCADEDB_PG_PORT"
PG_DEFAULT_PORT = 5432
PGWIRE_SCOPE = ("read and query statements only: `POST /query` SQL goes over the PostgreSQL wire; every write, DDL, transaction, bulk load, probe and "
                "Cypher statement stays on lean HTTP (DECISIONS #171 (c), #162)")
OFFICIAL_PIN = "0.4.0"       # the vendor package release the default session measures (DECISIONS #258, #259); recorded per row from the installed package,
                             # and OfficialSession refuses to start on any other version, so a stale image cannot stamp 0.4.0 or run 0.2.0 unnoticed
LEAN_NAME = "lean_http (http.client, keep-alive)"


def client_choice():
    """'official' (the default while the pass runs: a mid-run change would split rows), 'lean' (the client whose rows are published)
    or 'pgwire' (the PostgreSQL-wire twin, measured and not published), from BENCH_ARCADEDB_HTTP_CLIENT, which the runner sets for the
    twin jobs of each cell; anything else is refused rather than guessed."""
    v = (os.environ.get(CLIENT_ENV) or "").strip().lower()
    if v in ("", OFFICIAL):
        return OFFICIAL
    if v in (LEAN, PGWIRE):
        return v
    raise ValueError(f"{CLIENT_ENV} must be 'official', 'lean' or 'pgwire', got {v!r}")


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
    `ArcadeDBServer(...).db(<db>).query(...)` or `.command(...)`, which is what the vendor documents for a Python client (0.4.0: both take
    `limit`; `db()` handles are kept per (root, auth, timeout, database) so the driver's per-database URL cache, PR #168, is used). Everything
    else goes through a `LeanSession`: the `GET /server` probe, the bulk `/batch` load, transactions (`begin`/`commit`/`rollback` and any
    call carrying a session id), NDJSON streams, raw text bodies, and a body with a field the driver has no argument for. Bulk loads stay
    on HTTP `batch` and `command` as the protocol-audit decision says; the driver's `batch_load` is a different request shape and is not
    used. `official_calls` and `fallback_calls` count the two (a test reads them).

    PER-CALL TIMEOUT. The driver has no per-call timeout; its only one is the `httpx.Timeout` given to `ArcadeDBServer(timeout=...)`, and its
    default is None, which is NO timeout. So the call's `timeout=` (seconds or None, as for `LeanSession`, where it is a per-operation socket
    timeout) becomes `httpx.Timeout(seconds)` (connect, read, write and pool each, the same per-operation meaning) on a server object of its own:
    one server, with its own connection pool, per distinct (root, auth, timeout). The lanes use a handful of values (30, 60, 300, 600), so a lane
    holds a few pools, not one per call. A timeout surfaces as this module's `Timeout` and any other transport failure as `ConnectionError`,
    as for `LeanSession`. A timeout that is not None or a number goes to the lean session.
    """

    client_name = None   # set per instance from the installed package

    def __init__(self):
        import arcadedb_driver
        from arcadedb_driver.auth import basic_auth
        self._driver, self._basic_auth = arcadedb_driver, basic_auth
        self.version = getattr(arcadedb_driver, "__version__", None) or _driver_version()
        self.client_name = f"arcadedb-driver {self.version} (sync, httpx)"
        self.auth = None
        import httpx
        self._httpx = httpx
        # the pin is enforced, not just stamped: the headline is one driver release for the whole pass (DECISIONS #259 (1))
        if self.version != OFFICIAL_PIN:
            raise RuntimeError(f"arcadedb-driver {self.version} is installed, the harness pins {OFFICIAL_PIN} (lean_http.OFFICIAL_PIN): the served "
                               f"ArcadeDB client cells run in the image built by build_images.sh target client-arcadedb, not in dbbench:client")
        self._servers = {}
        self._dbs = {}
        self._fallback = LeanSession()
        self.official_calls = 0
        self.fallback_calls = 0

    def _server(self, root, auth, timeout=None):
        key = (root, auth, timeout)
        srv = self._servers.get(key)
        if srv is None:
            user, password = auth
            srv = self._driver.ArcadeDBServer(base_url=root, auth=self._basic_auth(user, password),
                                              timeout=self._httpx.Timeout(timeout))   # Timeout(None) = no timeout, as the driver's own default
            self._servers[key] = srv
        return srv

    def _db(self, root, auth, timeout, name):
        """The driver's database handle, built once per (root, auth, timeout, database): `ArcadeDBServer.db()` makes a new handle with a new
        per-database URL cache every time, which is what the driver's fast path (arcadedb-drivers PR #168) lives in."""
        key = (root, auth, timeout, name)
        db = self._dbs.get(key)
        if db is None:
            db = self._dbs[key] = self._server(root, auth, timeout).db(name)
        return db

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
                and (timeout is None or (isinstance(timeout, (int, float)) and not isinstance(timeout, bool)))):
            timeout = None if timeout is None else float(timeout)
            db = self._db(m["root"], tuple(auth), timeout, m["db"])
            self.official_calls += 1
            run = db.query if m["kind"] == "query" else db.command
            try:
                env = run(language=json["language"], command=json["command"], params=json.get("params"), limit=json.get("limit"))
            except self._driver.ArcadeDBError as e:
                return _OfficialResponse(e.status, {"error": e.error, "detail": e.detail, "exception": e.exception}, url, e.error or "")
            except self._httpx.TimeoutException as e:
                raise Timeout(f"POST {url} timed out after {timeout} s") from e
            except self._httpx.TransportError as e:
                raise ConnectionError(f"POST {url}: {e}") from e
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
        self._dbs.clear()
        self._fallback.close()


# ------------------------------------------------------------------------------------------------------- the PostgreSQL wire
# THE PG-WIRE TWIN (DECISIONS #166, #171, #237; CAMPAIGN section 7 row 6, PROTOCOL.md "ArcadeDB SERVED arms"). The same served SQL cell run again with
# its read statements on ArcadeDB's PostgreSQL-wire plugin through psycopg, as a labelled sensitivity row beside the headline (the official HTTP driver)
# and the lean HTTP twin. It flatters ArcadeDB most (the lightest client of the three, #166 addendum 2), so it is never a headline.
# SCOPE. Only `POST /query/<db>` with language `sql` goes to the wire. Every `/command` (writes, DDL, `sqlscript` transactions), `/batch` (bulk
# loads, #171 (c)), `/server` probe, any other language (Cypher stays on HTTP, #162), a session id, a statement whose params the wire cannot carry
# (a dict) and an NDJSON stream the lane did not ask the wire for, go to a `LeanSession`; each is counted by reason in `fallback_reasons`.
# NEVER PREPARED (`prepare_threshold=None`): psycopg's default prepares a statement at its 5th execution, and the plugin's prepared path sends rows of
# a schemaless type under one row description (upstream ArcadeData/arcadedb#9009), so every execution is an unnamed Parse/Bind/Execute.
_SQL_NAMED = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def pg_translate(sql, params):
    """(psycopg SQL, params) for an ArcadeDB statement with `:name` placeholders (the HTTP form every lane writes): each becomes `%(name)s`, a bound
    parameter on the wire; text inside quotes and backticks is left alone; with params, a literal `%` is doubled for psycopg. Returns None when a
    placeholder has no entry in `params` (the HTTP path then reports the error in the server's own words)."""
    params = params or {}
    out, i, n, used = [], 0, len(sql), []
    while i < n:
        c = sql[i]
        if c in "'\"`":
            j = i + 1
            while j < n:
                if sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == c:
                    break
                j += 1
            seg = sql[i:j + 1]
            out.append(seg.replace("%", "%%") if params else seg)
            i = j + 1
            continue
        m = _SQL_NAMED.match(sql, i) if c == ":" and not (i and (sql[i - 1].isalnum() or sql[i - 1] in "_:")) else None
        if m:
            if m.group(1) not in params:
                return None
            out.append(f"%({m.group(1)})s")
            used.append(m.group(1))
            i = m.end()
            continue
        out.append("%%" if c == "%" and params else c)
        i += 1
    return "".join(out), {k: params[k] for k in used}


def pg_param_ok(v):
    """Can this value travel as a bound PostgreSQL parameter: None, a bool, int, float, str, or a flat list or tuple of them."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return True
    return isinstance(v, (list, tuple)) and all(x is None or isinstance(x, (bool, int, float, str)) for x in v)


class PgSession:
    """The part of `requests.Session` the lanes use, with a served SQL read sent over the PostgreSQL wire (see the block above); the rest goes through
    a `LeanSession`. `pg_calls`, `fallback_calls` and `fallback_reasons` count the two; `summary()` is what the cell's log carries."""

    client_name = None

    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row
        self._psycopg, self._dict_row = psycopg, dict_row
        self.version = getattr(psycopg, "__version__", "unknown")
        impl = getattr(getattr(psycopg, "pq", None), "__impl__", "unknown")
        self.client_name = f"psycopg {self.version} (PostgreSQL wire, {impl}, unnamed statements)"
        self.auth = None
        self._conns = {}
        self._fallback = LeanSession()
        self.pg_calls = 0
        self.fallback_calls = 0
        self.fallback_reasons = {}

    def _port(self):
        return int(os.environ.get(PG_PORT_ENV) or PG_DEFAULT_PORT)

    def _conn(self, host, db, auth):
        key = (host, db, tuple(auth))
        cx = self._conns.get(key)
        if cx is None or cx.closed:
            cx = self._psycopg.connect(host=host, port=self._port(), dbname=db, user=auth[0], password=auth[1], autocommit=True,
                                       prepare_threshold=None, row_factory=self._dict_row, connect_timeout=30)
            self._conns[key] = cx
            if not getattr(self, "_beat", None):
                # a lane may exit without closing (os._exit), so the counters reach the cell's log on a clock too
                self._beat = threading.Thread(target=self._heartbeat, daemon=True)
                self._beat.start()
        return cx

    def _heartbeat(self, every=10):
        last = None
        while True:
            time.sleep(every)
            cur = self.summary()
            if cur != last:
                print("PGWIRE_SUMMARY " + _json.dumps(cur, sort_keys=True), flush=True)
                last = cur

    def _fall(self, reason):
        self.fallback_calls += 1
        if reason not in self.fallback_reasons:
            print(f"PGWIRE_FALLBACK {reason}", flush=True)       # the first sight of each reason, so the cell's log names it even if the lane exits hard
        self.fallback_reasons[reason] = self.fallback_reasons.get(reason, 0) + 1

    def summary(self):
        return {"pg_calls": self.pg_calls, "fallback_calls": self.fallback_calls, "fallback_reasons": dict(sorted(self.fallback_reasons.items()))}

    def _route(self, url, json, data, headers, kw):
        """(match, reason): the data-plane match when this call goes to the wire, else None and why not."""
        m = _DATA_URL.match(url)
        if not m:
            return None, "other-endpoint"
        if m["kind"] != "query":
            return None, "command"
        if not (isinstance(json, dict) and data is None and not kw and not headers):
            return None, "headers-or-raw-body"
        if not (set(json) <= {"language", "command", "params", "limit"} and "language" in json and "command" in json):
            return None, "body-fields"
        if str(json["language"]).lower() != "sql":
            return None, f"language-{str(json['language']).lower()}"
        if not all(pg_param_ok(v) for v in (json.get("params") or {}).values()):
            return None, "param-type"
        return m, None

    def _run(self, m, json, auth):
        """Run one routed statement on the wire; returns (rows, truncated). The rows are dicts, the shape the HTTP answers have."""
        t = pg_translate(json["command"], json.get("params"))
        if t is None:
            raise _Unroutable("param-missing")
        sql, args = t
        host = m["root"].split("://", 1)[1].rsplit(":", 1)[0]
        cur = self._conn(host, m["db"], auth).execute(sql, args or None)
        rows = cur.fetchall() if cur.description is not None else []
        limit = json.get("limit")
        truncated = False
        if limit and limit > 0 and len(rows) > limit:
            rows, truncated = rows[:limit], True
        return rows, truncated

    def get(self, url, **kw):
        kw.setdefault("auth", self.auth)
        self._fall("get")
        return self._fallback.get(url, **kw)

    def post(self, url, json=None, data=None, auth=None, headers=None, timeout=None, **kw):
        auth = auth or self.auth
        m, why = self._route(url, json, data, headers, kw) if auth else (None, "no-auth")
        if m is not None:
            try:
                rows, truncated = self._run(m, json, tuple(auth))
            except _Unroutable as e:
                why = str(e)
            except self._psycopg.Error as e:
                self.pg_calls += 1
                return _OfficialResponse(500, {"error": str(e).splitlines()[0] if str(e) else type(e).__name__, "detail": str(e),
                                               "exception": type(e).__name__}, url, type(e).__name__)
            else:
                self.pg_calls += 1
                if self.pg_calls == 1:
                    print("PGWIRE_SUMMARY " + _json.dumps(self.summary(), sort_keys=True), flush=True)      # the first call proves the wire in the log
                return _OfficialResponse(200, {"result": rows, "limit": json.get("limit", -1), "returned": len(rows), "truncated": truncated}, url, "OK")
        self._fall(why or "other")
        return self._fallback.post(url, json=json, data=data, auth=auth or self.auth, headers=headers, timeout=timeout, **kw)

    def ndjson_rows(self, url, json):
        """The rows of a query a lane asked to stream as NDJSON, read over the wire instead (the wire has no NDJSON): a list, or None when this
        statement does not go to the wire and the caller streams it over HTTP."""
        auth = self.auth
        m, why = self._route(url, json, None, None, {}) if auth else (None, "no-auth")
        if m is None:
            return None
        try:
            rows, _ = self._run(m, json, tuple(auth))
        except _Unroutable:
            return None
        except self._psycopg.Error as e:
            raise HTTPError(f"500 Server Error: {type(e).__name__} for url: {url}") from e
        self.pg_calls += 1
        return rows

    def close(self):
        print("PGWIRE_SUMMARY " + _json.dumps(self.summary(), sort_keys=True), flush=True)
        for cx in self._conns.values():
            try:
                cx.close()
            except Exception:  # noqa: BLE001 - closing must not fail a cell
                pass
        self._conns.clear()
        self._fallback.close()


class _Unroutable(Exception):
    """A statement the wire cannot take after all (a placeholder with no value): it goes over HTTP."""


def _driver_version():
    try:
        from importlib.metadata import version
        return version("arcadedb-driver")
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------------ the factory
def Session():  # noqa: N802 - requests' own spelling, so a lane changes by one import
    """The ArcadeDB served arms' session: the default session, `LeanSession` (the published client) when BENCH_ARCADEDB_HTTP_CLIENT=lean, `PgSession` when it is pgwire."""
    choice = client_choice()
    return OfficialSession() if choice == OFFICIAL else PgSession() if choice == PGWIRE else LeanSession()


def row_fields(session):
    """What a served ArcadeDB row records about its client, read from the session it ran with (not from the environment)."""
    out = {"arcadedb_http_client": getattr(session, "client_name", None) or type(session).__module__ + "." + type(session).__name__}
    if isinstance(session, OfficialSession):
        out["arcadedb_http_client_role"] = "headline"
    elif os.environ.get("BENCH_ARCADEDB_CLIENT_ROLE"):
        out["arcadedb_http_client_role"] = os.environ["BENCH_ARCADEDB_CLIENT_ROLE"]
    if isinstance(session, PgSession):
        # the role stays `sensitivity` (every filter that keeps twins out of a headline keys on it); the wire is the second stamp that tells the
        # two twins apart (make_paper_tables' key, export_web's split)
        out["arcadedb_client_wire"] = PGWIRE
        out["arcadedb_pgwire_client"] = {"psycopg": session.version, "prepare_threshold": None, "autocommit": True, "result_format": "text",
                                         "port": session._port()}
        out["arcadedb_pgwire_scope"] = PGWIRE_SCOPE
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
    """POST a query asking for NDJSON, raise on an HTTP error, and return its rows (`ndjson_records`). On the PG-wire twin a SQL query is read over the wire."""
    if isinstance(session, PgSession):
        rows = session.ndjson_rows(url, json)
        if rows is not None:
            return rows
    r = session.post(url, json=json, headers={"Accept": NDJSON_ACCEPT}, timeout=timeout)
    r.raise_for_status()
    return ndjson_records(r.content)
