"""Stand-in for ``jpype`` inside the arcadedb-embedded-native wheel (generated package only).

The Python sources are shared with ``arcadedb-embedded`` and import ``jpype`` at module level. The native wheel has no JVM and does
not depend on JPype, so the build rewrites those imports to this module. Names resolve to placeholder classes: ``isinstance`` checks
against them are simply False, and any attempt to call, subscript or build one raises :class:`NotOnNativeYet`. ``isJVMStarted()`` is
always False. Code paths that need real JPype (``jvm_kwargs``, ``get_java_database``, Java-object APIs) are the JVM-only APIs listed in the README.
"""

from arcadedb_native._native import NotOnNativeYet


class JException(Exception):
    """Placeholder for ``jpype.JException`` (never raised here)."""


class _Placeholder(type):
    def __call__(cls, *a, **k):
        raise NotOnNativeYet(
            f"{cls.__name__} needs a JVM; this is the native backend (arcadedb-embedded-native)"
        )

    def __getitem__(cls, item):
        raise NotOnNativeYet(
            f"{cls.__name__}[...] needs a JVM; this is the native backend"
        )

    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        raise NotOnNativeYet(
            f"{cls.__name__}.{name} needs a JVM; this is the native backend"
        )


def isJVMStarted() -> bool:
    return False


def __getattr__(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    ph = _Placeholder(name, (), {})
    globals()[name] = ph
    return ph
