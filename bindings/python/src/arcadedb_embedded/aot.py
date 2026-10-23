"""
ArcadeDB Python Bindings - opt-in JDK AOT cache (Project Leyden, JEP 483/514/515)

``ARCADEDB_AOT=1`` (or ``start_jvm(aot=True)``) lets the JVM keep a per-user
ahead-of-time cache of the classes it loads and links at start-up, which makes
the next start faster (cold start, see the JVM guide). It is off by default.

A cache records the absolute jar paths and each jar's mtime and size, so it
cannot ship inside the wheel: the first process on a machine *trains* it
(``-XX:AOTCacheOutput=``, the JVM writes the file when it exits normally), and
later processes *use* it (``-XX:AOTCache=... -XX:AOTMode=auto``, where the JVM
ignores a cache it cannot use instead of failing).

Everything here degrades to a normal start. No function raises to the caller of
``start_jvm``: any failure (unwritable directory, full disk, unsupported JDK,
unusable cache) leaves the JVM arguments untouched and logs one debug line.

Concurrency: one process at a time trains, chosen by an exclusive lock file
that holds the trainer's pid. The others start normally. The trained file is
written under a unique temporary name; the *next* start promotes it with an
atomic rename after the trainer is gone and after the bundled JVM has accepted
it. A cache that is missing, truncated or altered is rebuilt, never trusted.
"""

import hashlib
import json
import os
import platform
import re
import secrets
import subprocess  # nosec B404 - only runs the bundled JRE's java to validate a cache
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Optional

from ._logging import get_logger

_LOGGER = get_logger(__name__)

ENV_ENABLE = "ARCADEDB_AOT"
ENV_CACHE = "ARCADEDB_AOT_CACHE"

# One-step cache creation (-XX:AOTCacheOutput) arrived with JDK 25 (JEP 514).
MIN_JAVA_MAJOR = 25
# A lock older than this is stale even if its pid looks alive (pid reuse).
LOCK_STALE_SECONDS = 30 * 60
# Upper bound for the one-off check that the JVM accepts a freshly trained cache.
VALIDATE_TIMEOUT_SECONDS = 60

# Flags of the user that already decide how the JVM treats an AOT/CDS archive;
# with any of them present the bindings add nothing.
_USER_FLAG_PREFIXES = (
    "-XX:AOTCache",
    "-XX:AOTMode",
    "-XX:AOTConfiguration",
    "-XX:SharedArchiveFile",
    "-XX:ArchiveClassesAtExit",
    "-Xshare:",
    "-XX:-UseSharedSpaces",
)

_TRUE = {"1", "true", "yes", "on"}


def enabled(aot: Optional[bool]) -> bool:
    """The keyword wins; without it ``ARCADEDB_AOT`` decides. Default off."""
    if aot is not None:
        return bool(aot)
    return os.environ.get(ENV_ENABLE, "").strip().lower() in _TRUE


def cache_dir() -> Path:
    """Per-user cache directory by platform (stdlib only; never raises).

    Linux ``$XDG_CACHE_HOME/arcadedb/aot`` or ``~/.cache/arcadedb/aot``, macOS
    ``~/Library/Caches/arcadedb/aot``, Windows ``%LOCALAPPDATA%\\arcadedb\\Cache\\aot``;
    the system temp directory when no home directory can be found.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "arcadedb" / "Cache" / "aot"
    elif sys.platform != "darwin":
        xdg = os.environ.get("XDG_CACHE_HOME")
        # The XDG spec ignores a relative value.
        if xdg and os.path.isabs(xdg):
            return Path(xdg) / "arcadedb" / "aot"
    try:
        home = Path.home()
    except (RuntimeError, KeyError, OSError):
        return Path(tempfile.gettempdir()) / "arcadedb" / "aot"
    if sys.platform == "win32":
        return home / "AppData" / "Local" / "arcadedb" / "Cache" / "aot"
    if sys.platform == "darwin":
        return home / "Library" / "Caches" / "arcadedb" / "aot"
    return home / ".cache" / "arcadedb" / "aot"


def jpype_support_jar() -> Optional[Path]:
    """JPype's ``org.jpype.jar``, which JPype appends to the JVM class path.

    The cache records the whole class path, so this jar (an absolute path inside
    the Python environment) is part of what the cache is valid for. None when it
    cannot be found, then no cache is used: it could not be checked.
    """
    try:
        import jpype

        jar = Path(jpype.__file__).resolve().parent.parent / "org.jpype.jar"
        return jar if jar.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def jre_identity(jre_dir: Path) -> Optional[tuple]:
    """``(major, token)`` of the bundled JRE, or None when it cannot be read.

    ``token`` stands for ``java.vm.version``: the ``JAVA_VERSION`` of the JRE's
    ``release`` file plus the size of the JVM library (a rebuilt JRE with the
    same version string changes the size). Read from files, so no JVM is needed.
    """
    try:
        text = (Path(jre_dir) / "release").read_text("utf-8", errors="replace")
        match = re.search(r'^JAVA_VERSION="([^"]+)"', text, re.MULTILINE)
        if not match:
            return None
        version = match.group(1)
        major = int(re.match(r"(\d+)", version).group(1))
        size = 0
        for rel in (
            ("lib", "server", "libjvm.so"),
            ("lib", "server", "libjvm.dylib"),
            ("bin", "server", "jvm.dll"),
        ):
            lib = Path(jre_dir).joinpath(*rel)
            if lib.exists():
                size = lib.stat().st_size
                break
        return major, f"{version}+{size}"
    except (OSError, ValueError, AttributeError):
        return None


def cache_key(
    package_version: str,
    jre_token: str,
    jar_sha256: str,
    classpath: str,
    jar_stats: str = "",
) -> str:
    """Hash of everything a cache is only valid for (32 hex characters).

    Package version, bundled JRE version, the sha256 over the sorted (name,
    content) of every jar (``jar_fingerprint``), the exact class path string (the
    cache stores the class path in order), the size and mtime of each jar (the JVM
    refuses a cache when either changed, even if the bytes did not) and the platform.
    """
    h = hashlib.sha256()
    for part in (
        package_version,
        jre_token,
        jar_sha256,
        classpath,
        jar_stats,
        sys.platform,
        platform.machine(),
    ):
        h.update(part.encode("utf-8", errors="surrogateescape"))
        h.update(b"\0")
    return h.hexdigest()[:32]


def _jar_stats(classpath: str) -> str:
    parts = []
    for jar in classpath.split(os.pathsep):
        st = os.stat(jar)
        parts.append(f"{os.path.basename(jar)}:{st.st_size}:{st.st_mtime_ns}")
    return ";".join(sorted(parts))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pid_alive(pid: int) -> bool:
    """True if the process exists (conservative: True when unsure)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return ctypes.windll.kernel32.GetLastError() != 87  # not invalid pid
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001 - unsure means alive
            return True
    try:
        os.kill(pid, 0)  # signal 0 only checks existence
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.part")
    try:
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _unlink(*paths) -> None:
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


def _remove_training_files(tmp: Path) -> None:
    """Remove a training output and the side files the JVM derives from its name."""
    try:
        for p in tmp.parent.glob(tmp.name + "*"):
            _unlink(p)
    except OSError:
        pass


def _jvm_accepts(
    jre_dir: Path, cache: Path, classpath: str, jvm_flags: Iterable[str]
) -> bool:
    """Ask the bundled JVM to start with ``AOTMode=on`` (refuses an unusable cache)."""
    java = Path(jre_dir) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if not java.exists():
        # No launcher to ask: fall back on the file being non-empty. A bad file
        # still cannot hurt, AOTMode=auto ignores a cache it cannot use.
        return cache.stat().st_size > 0
    cmd = [
        str(java),
        f"-XX:AOTCache={cache}",
        "-XX:AOTMode=on",
        *jvm_flags,
        "-cp",
        classpath,
        "-version",
    ]
    result = subprocess.run(  # nosec B603 - argv list, no shell: the bundled java, fixed flags, our own cache path
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # the JVM reports start-up errors on stdout
        timeout=VALIDATE_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        _LOGGER.debug(
            "JVM refused the AOT cache (exit %s): %s",
            result.returncode,
            result.stdout.decode("utf-8", "replace").strip()[-400:],
        )
    return result.returncode == 0


class _Paths:
    def __init__(self, final: Path, key: str):
        self.final = final
        self.key = key
        self.meta = final.with_name(final.name + ".json")
        self.lock = final.with_name(final.name + ".lock")


def _usable_final(p: _Paths) -> bool:
    """Final file present, recorded for this key, same size and same sha256."""
    meta = _read_json(p.meta)
    if not meta or meta.get("key") != p.key:
        return False
    try:
        if p.final.stat().st_size != meta.get("size"):
            return False
        return _sha256_file(p.final) == meta.get("sha256")
    except OSError:
        return False


def _recover(p: _Paths, jre_dir: Path, classpath: str, jvm_flags: list) -> None:
    """Finish a finished or dead training run: promote its file or clean it up.

    Does nothing while the trainer lives (and its lock is fresh). Of several
    processes arriving together, one wins the right to recover by renaming the
    lock file (atomic); the others carry on.
    """
    info = _read_json(p.lock)
    if info is None and not p.lock.exists():
        _remove_orphans(p)
        return
    if info is not None:
        age = time.time() - float(info.get("started", 0))
        if _pid_alive(int(info.get("pid", 0))) and age < LOCK_STALE_SECONDS:
            return
    else:
        # Unreadable: a trainer between creating the lock and writing it, or junk.
        try:
            if time.time() - p.lock.stat().st_mtime < 60:
                return
        except OSError:
            return
    claim = p.lock.with_name(f"{p.lock.name}.{os.getpid()}.claim")
    try:
        os.rename(p.lock, claim)
    except OSError:
        return  # somebody else recovers
    try:
        tmp = Path(info["tmp"]) if info and info.get("tmp") else None
        promoted = False
        if tmp is not None and tmp.exists() and tmp.stat().st_size > 0:
            if info.get("key") == p.key and _jvm_accepts(
                jre_dir, tmp, classpath, jvm_flags
            ):
                size = tmp.stat().st_size
                digest = _sha256_file(tmp)
                os.replace(tmp, p.final)
                _write_json_atomic(
                    p.meta, {"key": p.key, "size": size, "sha256": digest}
                )
                promoted = True
                _LOGGER.debug("AOT cache %s promoted (%d bytes)", p.final, size)
        if not promoted and tmp is not None:
            _LOGGER.debug("AOT training output %s unusable, removed", tmp)
            _remove_training_files(tmp)
        if tmp is not None:
            # The JVM may leave a side file next to its output (name + suffix).
            for extra in tmp.parent.glob(tmp.name + ".*"):
                _unlink(extra)
    finally:
        _unlink(claim)


def _remove_orphans(p: _Paths) -> None:
    """Remove training outputs no lock refers to and that are long finished."""
    try:
        for f in p.final.parent.glob(p.final.name + ".*.tmp*"):
            if time.time() - f.stat().st_mtime > LOCK_STALE_SECONDS:
                _unlink(f)
    except OSError:
        pass


def _try_lock(p: _Paths, tmp: Path) -> bool:
    """Become the one trainer: create the lock exclusively. False if taken."""
    try:
        fd = os.open(p.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "pid": os.getpid(),
                "started": time.time(),
                "tmp": str(tmp),
                "key": p.key,
            },
            fh,
        )
    return True


def _user_flags_present(args: Iterable[str]) -> bool:
    return any(str(a).startswith(_USER_FLAG_PREFIXES) for a in args)


def jvm_flags_for(
    jvm_args: list,
    jre_dir: Path,
    classpath: str,
    package_version: str,
    jar_sha256: str,
) -> list:
    """The AOT flags to add to ``jvm_args`` (an empty list means a normal start).

    Never raises. Assumes the caller checked ``enabled()``.
    """
    try:
        return _plan(jvm_args, Path(jre_dir), classpath, package_version, jar_sha256)
    except Exception as exc:  # noqa: BLE001 - AOT is an optimisation only
        _LOGGER.debug("AOT cache skipped: %s: %s", type(exc).__name__, exc)
        return []


def _plan(
    jvm_args: list,
    jre_dir: Path,
    classpath: str,
    package_version: str,
    jar_sha256: str,
) -> list:
    if _user_flags_present(jvm_args):
        _LOGGER.debug("AOT cache skipped: AOT/CDS flags given in the JVM arguments")
        return []
    ident = jre_identity(jre_dir)
    if ident is None or ident[0] < MIN_JAVA_MAJOR:
        _LOGGER.debug(
            "AOT cache skipped: bundled JRE %s lacks one-step AOT cache (needs JDK %d)",
            ident,
            MIN_JAVA_MAJOR,
        )
        return []
    support = jpype_support_jar()
    if support is None:
        _LOGGER.debug("AOT cache skipped: org.jpype.jar not found")
        return []
    # What the JVM will really see; the cache stores it and must match it.
    classpath = classpath + os.pathsep + str(support)
    key = cache_key(
        package_version, ident[1], jar_sha256, classpath, _jar_stats(classpath)
    )

    override = os.environ.get(ENV_CACHE)
    if override:
        final = Path(override).expanduser()
        if not final.name or str(override).endswith(("/", os.sep)):
            raise ValueError(f"{ENV_CACHE} must name a file, got {override!r}")
    else:
        final = cache_dir() / f"{key}.aot"
    final.parent.mkdir(parents=True, exist_ok=True)
    p = _Paths(final, key)

    # The JVM accepts a cache only with the settings it was trained with (compact
    # object headers, modules, class path), so the validation run gets all of them.
    _recover(p, jre_dir, classpath, list(jvm_args))

    if p.final.exists():
        if _usable_final(p):
            _LOGGER.debug("AOT cache in use: %s", p.final)
            return [f"-XX:AOTCache={p.final}", "-XX:AOTMode=auto"]
        _LOGGER.debug("AOT cache %s is stale or damaged, retraining", p.final)
        _unlink(p.final, p.meta)

    tmp = p.final.with_name(f"{p.final.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    if not _try_lock(p, tmp):
        _LOGGER.debug("AOT cache: another process is training, starting normally")
        return []
    _LOGGER.debug("AOT cache training into %s", tmp)
    return [f"-XX:AOTCacheOutput={tmp}"]


def release_training(flags: Iterable[str]) -> None:
    """Give up a training run whose JVM did not start (frees the lock and file)."""
    for flag in flags:
        if flag.startswith("-XX:AOTCacheOutput="):
            tmp = Path(flag.split("=", 1)[1])
            _remove_training_files(tmp)
            final_name = tmp.name.split(".aot.")[0] + ".aot"
            _unlink(tmp.with_name(final_name + ".lock"))
