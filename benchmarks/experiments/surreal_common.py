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


def legacy_stamp_fixup(engine_version: str) -> str:
    """Rows stamped before 2026-09-13 read "surrealdb-embedded:<sdk>". The core
    is a function of the pinned SDK wheel, so the same wheel resolves it."""
    m = re.fullmatch(r"surrealdb-embedded:(\d+\.\d+\.\d+)", str(engine_version or ""))
    if m and core_version() and m.group(1) == sdk_version():
        return engine_stamp()
    return engine_version
