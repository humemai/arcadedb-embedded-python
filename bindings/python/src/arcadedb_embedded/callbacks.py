"""
ArcadeDB Python Bindings - Python functions in SQL and record event callbacks

``Database.register_function()`` makes a Python callable usable as a SQL (and openCypher)
function. ``Database.on()`` runs a Python callback when a record is created, updated, or
deleted. Both ride the bridge jar (``PythonFunctions``, ``PythonRecordEvents``), which
implements the engine's interfaces and forwards each call to a JPype proxy defined here.
"""

import inspect
import re
import threading
import traceback
import weakref
from typing import Callable, Optional, Tuple

import jpype

from ._logging import get_logger
from .exceptions import ArcadeDBError
from .type_conversion import convert_java_to_python, convert_python_to_java

_LOGGER = get_logger(__name__)

EVENTS = (
    "before_create",
    "after_create",
    "before_update",
    "after_update",
    "before_delete",
    "after_delete",
)

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_UNBOUNDED = 2**31 - 1  # Integer.MAX_VALUE: the engine's "any number of arguments"


def _bridge_class(name: str):
    """Load a bridge class, or raise an ArcadeDBError that says what is missing."""
    try:
        return jpype.JClass(name)
    except Exception as e:
        raise ArcadeDBError(
            f"Bridge class {name} is unavailable: this feature needs "
            "arcadedb-python-bridge.jar from the same wheel as the Python package"
        ) from e


# A KeyboardInterrupt raised inside a Python function or callback cannot cross the engine as it
# is: it ends the statement as a Java exception. It is remembered per thread, and the place that
# turns the statement's Java exception into an ArcadeDBError raises the KeyboardInterrupt instead
# (chained from that ArcadeDBError), so Ctrl-C reaches the caller as KeyboardInterrupt whether the
# signal landed in the function, in the engine, or between the two.
_PENDING = threading.local()


def _is_jpype_interrupt_race(error: BaseException) -> bool:
    """True for the ``RuntimeError`` JPype raises when it loses its race with Ctrl-C.

    JPype's SIGINT handler (``interrupt=False``) interrupts the Java thread first and tells
    Python afterwards (test_sigint.py, #179, jpype-project/jpype#1496). JPype's own Java
    call, while it converts a Java exception to a Python one, then fails with
    ``InterruptedException: sleep interrupted``, and the call ends in
    ``RuntimeError: Fatal error occurred``. It means Ctrl-C: the signal reached the statement
    while the engine handled the failure of a Python function (a KeyboardInterrupt raised on
    entering the callback arrives as ``org.jpype.PyExceptionProxy``, one raised in the
    function as ``KeyboardInterrupt``).
    """
    return isinstance(error, RuntimeError) and "Fatal error occurred" in str(error)


def _raise_to_java(error: BaseException):
    """Hand a Python exception to the engine as a Java RuntimeException.

    The text names the Python exception type, so the query error says what went wrong. The
    Python traceback goes to the debug log. Nothing escapes into the JVM as a Python exception.
    """
    _LOGGER.debug(
        "Python callback raised:\n%s",
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    )
    if isinstance(error, KeyboardInterrupt):
        _PENDING.interrupt = error
    elif _is_jpype_interrupt_race(error):
        _PENDING.interrupt = KeyboardInterrupt(
            "interrupted while a Python function was called"
        )
        _PENDING.interrupt.__cause__ = error
    raise jpype.JClass("java.lang.RuntimeException")(f"{type(error).__name__}: {error}")


def clear_pending_interrupt() -> None:
    """Forget a KeyboardInterrupt left by an earlier statement (called when a statement starts)."""
    _PENDING.interrupt = None


def _escaped_python_exception(exc: BaseException) -> bool:
    """True when a Java exception chain holds JPype's proxy for a Python exception that left a callback.

    Only an exception that arrives outside the callback's own ``try`` can do that, and that is
    in practice a KeyboardInterrupt raised by the signal handler on entering the callback.
    """
    try:
        cause = exc
        for _ in range(16):
            if cause is None:
                return False
            if "PyExceptionProxy" in str(cause.getClass().getName()):
                return True
            cause = cause.getCause()
    except Exception:  # nosec B110 - not a Java exception: nothing escaped
        pass
    return False


def raise_pending_interrupt(error: BaseException, java_exc: BaseException) -> None:
    """Raise the KeyboardInterrupt a Python callback left, chained from ``error``, if there is one."""
    interrupt = getattr(_PENDING, "interrupt", None)
    _PENDING.interrupt = None
    if interrupt is None and (
        _escaped_python_exception(java_exc) or _is_jpype_interrupt_race(java_exc)
    ):
        interrupt = KeyboardInterrupt("interrupted while a Python function was called")
    if interrupt is not None:
        raise interrupt from error


def _arity(fn: Callable) -> Tuple[int, int]:
    """The (min, max) number of positional arguments ``fn`` takes; max is unbounded for ``*args``."""
    try:
        parameters = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return 0, _UNBOUNDED
    minimum = maximum = 0
    for parameter in parameters:
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            maximum += 1
            if parameter.default is inspect.Parameter.empty:
                minimum += 1
        elif parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            maximum = _UNBOUNDED
        elif (
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and parameter.default is inspect.Parameter.empty
        ):
            raise ArcadeDBError(
                f"Function parameter '{parameter.name}' is keyword-only and has no "
                "default: SQL passes positional arguments only"
            )
    return minimum, maximum


# The proxy classes are defined once, on first use (the JVM must be running, so not at import):
# a @JImplements class defined on every registration leaked about 6 KB of Python heap per
# registration, which neither the engine's unregister nor gc gave back. State is per instance.
_PROXY_CLASSES = {}


def _function_proxy_class():
    cls = _PROXY_CLASSES.get("function")
    if cls is None:

        @jpype.JImplements(
            _bridge_class("com.arcadedb.python.PythonFunctions$Callback")
        )
        class _PythonFunction:
            def __init__(self, fn, database_ref):
                self._fn = fn
                self._database_ref = database_ref

            @jpype.JOverride
            def call(self, args):
                from .core import _wrap_java_record

                try:
                    values = []
                    for arg in args:
                        value = convert_java_to_python(arg)
                        values.append(_wrap_java_record(value, self._database_ref()))
                    result = convert_python_to_java(self._fn(*values))
                    if result is not None:
                        # Convert to a Java Object here, inside the try: left to JPype's return
                        # conversion an unconvertible value (a numpy array, an int past 2**63)
                        # reaches the engine as an opaque org.jpype.PyExceptionProxy.
                        result = jpype.JObject(result, jpype.JObject)
                    return result
                except BaseException as e:  # pylint: disable=broad-except
                    _raise_to_java(e)

        cls = _PROXY_CLASSES["function"] = _PythonFunction
    return cls


def _event_proxy_class():
    cls = _PROXY_CLASSES.get("event")
    if cls is None:

        @jpype.JImplements(
            _bridge_class("com.arcadedb.python.PythonRecordEvents$Callback")
        )
        class _PythonListener:
            def __init__(self, fn, is_before, database_ref):
                self._fn = fn
                self._is_before = is_before
                self._database_ref = database_ref

            @jpype.JOverride
            def call(self, record):
                from .core import _wrap_java_record

                try:
                    result = self._fn(_wrap_java_record(record, self._database_ref()))
                except BaseException as e:  # pylint: disable=broad-except
                    _raise_to_java(e)
                return not (self._is_before and result is False)

        cls = _PROXY_CLASSES["event"] = _PythonListener
    return cls


def _function_callback(fn: Callable, database):
    """A PythonFunctions.Callback proxy: Java arguments in, converted result out."""
    # weak: the engine holds this proxy, so a strong Database here would never be released
    return _function_proxy_class()(fn, weakref.ref(database))


def _event_callback(event: str, fn: Callable, database):
    """A PythonRecordEvents.Callback proxy: the record wrapped, a before event may veto."""
    # weak: the engine holds this proxy, so a strong Database here would never be released
    return _event_proxy_class()(fn, event.startswith("before_"), weakref.ref(database))


class FunctionRegistration:
    """Python functions registered through one ``Database``.

    The engine registers functions for the whole process, so each ``Database`` keeps the ones
    it registered to remove them when it is closed.
    """

    def __init__(self, database):
        # Weak: the Database holds this registry, and a strong reference back would make a
        # cycle that keeps the Database (and its engine instance) alive until a gc pass
        # instead of releasing it with its last result (tests/test_results_after_close.py).
        self._database_ref = weakref.ref(database)
        self._handles = {}

    @property
    def _database(self):
        return self._database_ref()

    def register(
        self,
        name: str,
        fn: Callable,
        min_args: Optional[int],
        max_args: Optional[int],
        deterministic: bool,
        replace: bool,
    ) -> None:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise ValueError(
                f"Invalid function name {name!r}: use letters, digits and underscores "
                "(not starting with a digit), optionally joined by dots like 'py.slugify'"
            )
        if not callable(fn):
            raise TypeError("fn must be callable")
        found_min, found_max = _arity(fn)
        min_args = found_min if min_args is None else min_args
        max_args = found_max if max_args is None else max_args
        if min_args < 0 or max_args < min_args:
            raise ValueError(
                f"Invalid argument counts: min_args={min_args}, max_args={max_args}"
            )

        functions = _bridge_class("com.arcadedb.python.PythonFunctions")
        try:
            if functions.isTakenByEngine(name):
                raise ArcadeDBError(
                    f"Cannot register '{name}': it is already a function of the engine"
                )
            if functions.isPythonFunction(name) and not replace:
                raise ArcadeDBError(
                    f"A Python function '{name}' is already registered "
                    "(pass replace=True to replace it)"
                )
            callback = _function_callback(fn, self._database)
            handle = functions.register(
                name, callback, min_args, max_args, bool(deterministic)
            )
        except ArcadeDBError:
            raise
        except Exception as e:
            raise ArcadeDBError(f"Failed to register function '{name}': {e}") from e
        # keep the proxy alive for as long as the engine can call it
        self._handles[name.lower()] = (handle, callback)

    def unregister(self, name: str) -> None:
        entry = self._handles.pop(str(name).lower(), None)
        if entry is None:
            raise ArcadeDBError(
                f"No Python function '{name}' is registered through this database"
            )
        _bridge_class("com.arcadedb.python.PythonFunctions").unregisterHandle(entry[0])

    def clear(self) -> None:
        """Remove every function this database registered (called when it closes)."""
        handles, self._handles = self._handles, {}
        try:
            functions = jpype.JClass("com.arcadedb.python.PythonFunctions")
            for handle, _callback in handles.values():
                functions.unregisterHandle(handle)
        except Exception:  # nosec B110 - the JVM may already be shutting down
            pass


class EventHandle:
    """A registered record event callback; ``remove()`` stops it.

    Returned by ``Database.on()``. It is also a context manager that removes the callback on
    exit.
    """

    def __init__(
        self, events, event: str, type_name: Optional[str], java_handle, proxy
    ):
        self._events = events
        self._java_handle = java_handle
        self._proxy = proxy
        self.event = event
        self.type_name = type_name
        self._active = True

    @property
    def active(self) -> bool:
        """Whether the callback is still registered."""
        return self._active

    def remove(self) -> None:
        """Unregister the callback. Calling it again does nothing."""
        if not self._active:
            return
        self._active = False
        try:
            _bridge_class("com.arcadedb.python.PythonRecordEvents").unregister(
                self._events, self.event, self._java_handle
            )
        except Exception as e:
            raise ArcadeDBError(f"Failed to remove '{self.event}' callback: {e}") from e

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.remove()

    def __repr__(self) -> str:
        scope = f" on {self.type_name}" if self.type_name else ""
        state = "active" if self._active else "removed"
        return f"<EventHandle {self.event}{scope} ({state})>"


def register_event(database, event: str, fn: Callable, type_name: Optional[str]):
    """Register ``fn`` for ``event`` on the database, or on one type, and return its handle."""
    if event not in EVENTS:
        raise ValueError(f"Invalid event {event!r}. Must be one of: {list(EVENTS)}")
    if not callable(fn):
        raise TypeError("fn must be callable")
    java_db = database.get_java_database()
    try:
        if type_name is None:
            events = java_db.getEvents()
        else:
            schema = java_db.getSchema()
            if not schema.existsType(type_name):
                raise ArcadeDBError(f"Type '{type_name}' does not exist")
            events = schema.getType(type_name).getEvents()
        proxy = _event_callback(event, fn, database)
        java_handle = _bridge_class("com.arcadedb.python.PythonRecordEvents").register(
            events, event, proxy
        )
    except ArcadeDBError:
        raise
    except Exception as e:
        raise ArcadeDBError(f"Failed to register '{event}' callback: {e}") from e
    return EventHandle(events, event, type_name, java_handle, proxy)


__all__ = ["EVENTS", "EventHandle", "FunctionRegistration", "register_event"]
