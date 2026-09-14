"""What the embedded SurrealDB actually is.

The Python SDK (`surrealdb` on PyPI) compiles a SurrealDB core into its
extension module; `db.version()` reports the SDK's own version, not that
core's. At the September 2026 pin the SDK is 2.0.0 (uploaded 2026-04-23) and
the core it carries is surrealdb-core 2.3.10 (released 2025-09-19), while the
served twin runs v3.2.4. Every embedded row stamped "surrealdb-embedded:2.0.0"
until 2026-09-13, which named the client library as the engine (BUGS F39).

The core version is read from the compiled extension's bytes (the crate
records its own name and version there), so it follows the installed wheel
and is never typed.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_CORE = re.compile(rb"surrealdb-core-(\d+\.\d+\.\d+)")


@lru_cache(maxsize=1)
def core_version() -> str | None:
    try:
        import surrealdb
    except ImportError:
        return None
    pkg = Path(surrealdb.__file__).parent
    for so in sorted(pkg.rglob("*.so")) + sorted(pkg.rglob("*.pyd")):
        m = _CORE.search(so.read_bytes())
        if m:
            return m.group(1).decode()
    return None


def sdk_version(db=None) -> str | None:
    if db is not None:
        try:
            return str(db.version()).replace("surrealdb-", "")
        except Exception:  # noqa: BLE001
            pass
    try:
        from importlib.metadata import version
        return version("surrealdb")
    except Exception:  # noqa: BLE001
        return None


def engine_stamp(db=None) -> str:
    """"surrealdb-embedded:<core> (sdk <sdk>)": the engine first, the client
    library that carries it second, in the shape the exporter reads."""
    core, sdk = core_version(), sdk_version(db)
    if core:
        return f"surrealdb-embedded:{core} (sdk {sdk or '?'})"
    return f"surrealdb-embedded:{sdk or '?'}"


def apply_durability(cls: str | None = None) -> str:
    """Set SURREAL_SYNC_DATA before the embedded store is opened (DECISIONS #90).

    The variable is read by the compiled core when the datastore opens, so it
    has to be in the environment BEFORE the first Surreal(...) call rather than
    passed to it. Verified by strace in #81's evidence block: unset gives 6
    fsync calls at both 50 and 250 commits, "true" gives 56 and 256.

    The served twin has no equivalent -- SurrealDB 3.2.4 exposes no sync
    setting at all -- and is a declared no-setting engine instead of being
    given a flag the server does not read.
    """
    import os
    import bench_common
    cls = cls or bench_common.DURABILITY_CLASS
    if cls == bench_common.CLASS_STRICT:
        os.environ["SURREAL_SYNC_DATA"] = "true"
    else:
        os.environ.pop("SURREAL_SYNC_DATA", None)
    return cls


def legacy_stamp_fixup(engine_version: str) -> str:
    """Rows stamped before 2026-09-13 read "surrealdb-embedded:<sdk>". The core
    is a function of the pinned SDK wheel, so the same wheel resolves it."""
    m = re.fullmatch(r"surrealdb-embedded:(\d+\.\d+\.\d+)", str(engine_version or ""))
    if m and core_version() and m.group(1) == sdk_version():
        return engine_stamp()
    return engine_version


# ---------------------------------------------------------------------------
# SURVIVING A DROPPED WEBSOCKET (DECISIONS #91).
#
# Both served dense cells at the ten-million tier on mini built their index and
# then died inside the timed queries with "ConnectionClosedError: no close frame
# received or sent", at 5,007 s and about 4,700 s of a 28,800 s budget. Not a
# timeout, not an OOM kill, and the server container was up and healthy
# afterwards with nothing in its log after startup: the server survived and the
# client's socket went away.
#
# WHY IT GOES AWAY, read out of the SDK rather than guessed. The blocking
# WebSocket connection opens its socket lazily inside _send:
#
#     self.socket = ws_sync.connect(self.raw_url, max_size=None,
#                                   subprotocols=[websockets.Subprotocol("cbor")])
#
# Every other option is the websockets library's default, and two of those
# defaults decide this: ping_interval=20 and ping_timeout=20. The sync client
# runs a keepalive thread that pings every twenty seconds and CLOSES THE
# CONNECTION when no pong arrives within twenty more. A query that keeps the
# server busy for minutes is exactly the case where a pong does not come back
# in time, so the client hangs up on a server that is still working. That is a
# client-side default, not an engine limit, and it is set explicitly here
# instead of being inherited.
#
# The treatment is MongoDB's after a primary election, one file over in
# l1_tpc.py: when the connection is gone, build a new one, re-authenticate,
# re-select the namespace and database, and let the call through again once.
# The difference is that a reconnect must not be free: the retried call ran on
# a new socket after an unknown pause, so its LATENCY IS DISCARDED (see
# sample_kept below) and the row records how many reconnects happened.
WS_OPTIONS = {"ping_interval": None, "open_timeout": 60}
WS_OPTIONS_NOTE = ("websockets client keepalive disabled (ping_interval=None, "
                   "open_timeout=60): its 20 s ping and 20 s pong deadline "
                   "close the socket on a server that is busy answering "
                   "(DECISIONS #91)")


def _apply_ws_options():
    """Set the socket options the SDK leaves at the library's defaults.

    The SDK takes no keyword for them and reaches the library through a module
    attribute, so the patch goes on that attribute. It is process-wide, which
    is safe here for one reason worth stating: the only WebSocket client in a
    cell IS this SDK.
    """
    try:
        import surrealdb.connections.blocking_ws as bws
    except Exception:  # noqa: BLE001 - embedded-only images have no ws module
        return False
    if getattr(bws.ws_sync.connect, "_bench_patched", False):
        return True
    _orig = bws.ws_sync.connect

    def connect(*a, **kw):
        for k, v in WS_OPTIONS.items():
            kw.setdefault(k, v)
        return _orig(*a, **kw)

    connect._bench_patched = True
    bws.ws_sync.connect = connect
    return True


# The exception the SDK raises when the socket is gone comes from the
# websockets library and from the standard library underneath it, and the SDK
# wraps some of them in its own types, so this matches on the NAME and the
# TEXT rather than on a class. Matching a class we import would miss exactly
# the case that produced this: a wrapped ConnectionClosedError.
_DROPPED_MARKS = (
    "connectionclosed", "no close frame", "connection closed",
    "websocketexception", "connectionreset", "broken pipe", "not connected",
    "socket is closed", "eof occurred",
)


def is_dropped_connection(exc) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    return any(m in text for m in _DROPPED_MARKS)


class ReconnectingClient:
    """A SurrealDB server connection that rebuilds itself when the socket dies.

    Wraps the SDK client rather than subclassing it: the SDK returns one of
    three connection classes from Surreal(url) depending on the scheme, so
    there is no single base to inherit from.
    """

    def __init__(self, open_fn):
        self._open_fn = open_fn
        self._c = open_fn()
        self.reconnects = 0
        # Bumped on every reconnect. sample_kept() reads it to decide whether
        # the sample just timed ran on an unbroken connection.
        self.reconnect_epoch = 0

    # Reconnecting to close is a reconnect that exists only to be thrown away,
    # and it would count itself on the row. A close that fails because the
    # socket is already gone has done its job.
    NO_RETRY = {"close"}

    def __getattr__(self, name):
        attr = getattr(self._c, name)
        if not callable(attr):
            return attr
        if name in self.NO_RETRY:
            return attr

        def call(*a, **kw):
            try:
                return attr(*a, **kw)
            except Exception as e:  # noqa: BLE001
                if not is_dropped_connection(e):
                    raise
                self.reconnect()
                # ONCE. A second drop on a fresh connection is not a dropped
                # socket any more, it is a server that cannot answer, and the
                # cell should fail with that rather than retry forever.
                return getattr(self._c, name)(*a, **kw)

        return call

    # How long to keep trying to get the connection back. A socket that dropped
    # because the server bounced cannot be reopened in the same millisecond,
    # and a reconnect that gives up instantly would turn every recoverable
    # drop into a dead cell -- which is the outcome this whole path exists to
    # avoid. Bounded, because a server that is gone for a minute is a failure
    # and the cell should say so rather than sit there.
    RECONNECT_WINDOW_S = 60
    RECONNECT_SLEEP_S = 1.0

    def reconnect(self):
        import time as _time
        try:
            self._c.close()
        except Exception:  # noqa: BLE001
            pass
        deadline = _time.monotonic() + self.RECONNECT_WINDOW_S
        last = None
        while True:
            try:
                self._c = self._open_fn()
                break
            except Exception as e:  # noqa: BLE001
                last = e
                if _time.monotonic() >= deadline:
                    raise
                _time.sleep(self.RECONNECT_SLEEP_S)
        self.reconnects += 1
        self.reconnect_epoch += 1
        self.last_reconnect_error = None if last is None else f"{last.__class__.__name__}: {last}"
        return self.reconnects


def served_client(url=None, ns="bench", db="bench", user="root", password="root"):
    """The served SurrealDB connection every lane opens, with #91's treatment.

    One function rather than four copies of the same four lines, so a lane
    cannot end up with the reconnect path and another without it.
    """
    import os
    _apply_ws_options()

    def _open():
        from surrealdb import Surreal
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        c = Surreal(url or f"ws://{host}:8000/rpc")
        c.signin({"username": user, "password": password})
        c.use(ns, db)
        return c

    return ReconnectingClient(_open)


_SAMPLE_EPOCHS = {}


def _counter(client, name):
    """The int a ReconnectingClient keeps under `name`, or None.

    NOT `getattr(client, name, None)`, AND THE DIFFERENCE KILLED EVERY MONGODB
    CELL IN THE TPC LANE (2026-09-14, found at SF1). A pymongo `Database`
    answers ANY attribute name by returning a `Collection` of that name, so
    `getattr(db, "reconnects", None)` is not None, it is
    `Collection(bench.reconnects)`. `stamp_reconnects` then wrote that object
    onto the row and the cell died four and a half minutes in, at the final
    `json.dump`, with "Object of type Collection is not JSON serializable" --
    after the load, after every query, having produced nothing. The same
    duck-typing made `sample_kept` compare two freshly minted Collections on
    every timed sample; pymongo's `__eq__` happened to call them equal, so it
    returned True by luck rather than by design.

    The skeleton sweep did not catch it because DECISIONS #91 landed mid-sweep
    and the l1tpc MongoDB cells had already run. It is not scale-dependent: SF1
    is simply the first size at which those cells were run again.

    A reconnect counter is an int. Anything else is an adapter answering a
    question it was not asked, and the right reading of it is "this adapter has
    no reconnect counter".
    """
    v = getattr(client, name, None)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def sample_kept(adapter) -> bool:
    """Did the sample just timed run on a connection that never dropped?

    False exactly once per reconnect, for the call that hit the dead socket:
    that call paid for a fresh connection and a re-authentication, so its
    latency is the reconnect's, not the query's, and #91 says it is not
    counted. Every other call, and every adapter that is not a reconnecting
    SurrealDB client, returns True and nothing changes.

    Conservative in one direction on purpose: if a connection drops during
    UNTIMED work (a build, a schema statement), the next timed sample is the
    one discarded. One sample out of a thousand is the cheaper error.
    """
    client = getattr(adapter, "db", None)
    epoch = _counter(client, "reconnect_epoch")
    if epoch is None:
        return True
    key = id(client)
    was = _SAMPLE_EPOCHS.get(key, epoch)
    _SAMPLE_EPOCHS[key] = epoch
    return epoch == was


def keep(adapter, samples, value):
    """Append a timed sample unless the connection broke while it was taken."""
    if sample_kept(adapter):
        samples.append(value)


def stamp_reconnects(out, adapter):
    """`reconnects` on every SurrealDB row, zero when nothing happened.

    A number on the row rather than an exception in a log: the ten-million
    failures were only ever visible as a traceback, so nothing downstream could
    see them and no gate could refuse a cell that had silently lost its server
    and come back.
    """
    client = getattr(adapter, "db", None)
    n = _counter(client, "reconnects")
    if n is not None:
        out["reconnects"] = n
        out["surreal_ws_options"] = WS_OPTIONS_NOTE
        return n
    # The embedded arm has no socket to lose, and it still records the field,
    # at zero: a column that exists only on the rows that failed is a column
    # nobody reads until it is too late.
    if "surreal" in str(getattr(adapter, "name", "")).lower():
        out["reconnects"] = 0
        out["surreal_ws_options"] = "in-process: no connection to drop"
        return 0
    return None
