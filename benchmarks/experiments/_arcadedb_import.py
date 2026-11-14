"""The one place the harness decides which ArcadeDB Python package it imports.

Since 26.11.1 the Python bindings ship as two distributions that both install the import name `arcadedb`:
`arcadedb` (the native build) and `arcadedb-jvm` (the Java engine through JPype). Before that the one
distribution was `arcadedb-embedded`, import name `arcadedb_embedded`. The lanes used to write
`import arcadedb_embedded as arcadedb` in every ArcadeDB arm; they now call `load()` here instead:

    import _arcadedb_import
    arcadedb = _arcadedb_import.load()

`load()` imports `arcadedb` first and falls back to `arcadedb_embedded`, so the same harness runs
against the new wheels and against the `arcadedb_embedded` wheels the images carry today. An
`arcadedb_embedded` install resolves to the old package unless `arcadedb` is installed too (the
26.11.1 `arcadedb-embedded` shim re-exports `arcadedb`, so there both names give the same module).

Everything here is lazy: importing this file imports nothing from ArcadeDB, because a lane module is
also imported by cells that never touch ArcadeDB (DuckDB, SQLite, ...), on hosts without the wheel.

What differs between the packages, and what this module hides:

  * module name: `arcadedb` vs `arcadedb_embedded` (module_name()).
  * distribution name for the version stamp: `arcadedb` / `arcadedb-jvm` / `arcadedb-embedded`
    (dist_version(); `importlib.metadata.version("arcadedb-embedded")` is a PackageNotFoundError on a new install).
  * which engine runs: `arcadedb.__backend__` is "native" or "jvm"; the old package has no such
    attribute and is always "jvm" (backend()).
  * `<module>.jvm`: importable in both new wheels, but the native wheel ships no JARs, so
    `start_jvm()` raises ArcadeDBError ("No JAR files found") there (jvm_module()). The cold-start
    subprocess in l5_lifecycle.py therefore starts the native library instead (see its docstring).
  * JVM-only APIs (`get_java_database`, `jpype`, Java arrays): they exist only on the JVM build and
    the native build has no JPype. No lane uses them any more (l3_sparse's embedded arm went through
    insert_many, plain Python lists and SQL COMPACT INDEX); a new arm that needs one must check
    backend() first, and this module does not paper over it.
  * loaded_backend(): backend() once load() has run, else None; it is what the `engine_backend` row field reads.
"""
import importlib
import importlib.metadata
import os

# Import names, in order. The first one that is the real package wins.
MODULES = ("arcadedb", "arcadedb_embedded")
# Distribution names for the version stamp, same order idea: new first.
DISTS = ("arcadedb", "arcadedb-jvm", "arcadedb-embedded")

_loaded = None

# THE NATIVE BUILD HAS NO JVM, SO NO `jvm_kwargs`: the native package ignores `heap_size` and `jvm_args` (with a warning) and reads its isolate
# options from this environment variable when the isolate is created (arcadedb._native.lib). The lanes still pass the JVM spelling, because that
# is the one code path for both packages, so on native `load()` wraps create_database/open_database and turns the same kwargs into isolate
# arguments before the first call: heap_size -> -Xmx<heap>, and the -D<system property> and -Xms/-Xmx entries of jvm_args as they are
# (the engine reads its settings, such as arcadedb.txWalFlush, from system properties; checked on the 26.10.2 native wheel: -Darcadedb.txWalFlush=1
# in the isolate args shows value 1 in `SELECT settings FROM schema:database`). Other JVM flags (-XX:...) have no native meaning and are left out;
# they are recorded in `native_dropped`. An argument already present in the variable wins, as it does inside the package.
NATIVE_ENV = "ARCADEDB_NATIVE_ISOLATE_ARGS"
_PASS_PREFIXES = ("-D", "-Xms", "-Xmx")
native_dropped = []
_isolate_created = False


def _is_engine(mod):
    # `arcadedb` could also resolve as an empty namespace directory on sys.path; require the API.
    return hasattr(mod, "create_database") and hasattr(mod, "DatabaseFactory")


def load():
    """Return the ArcadeDB Python module: `arcadedb`, else `arcadedb_embedded`.

    Raises ImportError (naming both) when neither is installed.
    """
    global _loaded
    if _loaded is not None:
        return _loaded
    errors = []
    for name in MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError as e:
            errors.append(f"{name}: {e}")
            continue
        if _is_engine(mod):
            _loaded = mod
            _wrap_native(mod)
            return mod
        errors.append(f"{name}: imported but is not the ArcadeDB package ({getattr(mod, '__file__', None)})")
    raise ImportError("no ArcadeDB Python package: install arcadedb or arcadedb-jvm (or the older arcadedb-embedded); "
                      + "; ".join(errors))


def module_name():
    """The import name `load()` resolved to ("arcadedb" or "arcadedb_embedded"). For code strings run in a subprocess."""
    return load().__name__


def backend():
    """"native" or "jvm": the engine this process runs. The old `arcadedb_embedded` package is always "jvm"."""
    mod = load()
    return getattr(mod, "__backend__", None) or getattr(mod, "_DISTRIBUTION_BACKEND", None) or "jvm"


def loaded_backend():
    """`backend()` when this process has loaded the package, else None (a comparator arm, a served arm's driver).

    Never imports the engine. This is what the row stamp `engine_backend` reads, so a row of a process that never touched ArcadeDB
    carries an explicit None, not a guess.
    """
    return backend() if _loaded is not None else None


def jvm_module():
    """`<module>.jvm` (start_jvm, shutdown_jvm, jar_fingerprint ...). Importing the submodule does not start a JVM."""
    return importlib.import_module(module_name() + ".jvm")


def dist_version():
    """The installed distribution's version, read from package metadata without importing the engine.

    Same contract as the old `importlib.metadata.version("arcadedb-embedded")`: returns a version string,
    or raises PackageNotFoundError when none of the distributions is installed (callers format that into
    "unknown (PackageNotFoundError)" exactly as before).
    """
    last = None
    for dist in DISTS:
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError as e:
            last = e
    raise last


def _arg_key(tok):
    """The part of an isolate argument that names the setting: `-Darcadedb.txWalFlush=1` -> `-Darcadedb.txWalFlush`, `-Xmx4g` -> `-Xmx`."""
    if tok.startswith("-D"):
        return tok.split("=", 1)[0]
    return tok[:4] if tok[:4] in ("-Xms", "-Xmx") else tok


def native_isolate_args(heap_size=None, jvm_args=None):
    """The isolate arguments that mean what a JVM `heap_size` / `jvm_args` pair means; ([kept], [dropped]). Pure, no environment."""
    toks = [f"-Xmx{heap_size}"] if heap_size else []
    ja = jvm_args.split() if isinstance(jvm_args, str) else list(jvm_args or [])
    dropped = [t for t in ja if not t.startswith(_PASS_PREFIXES)]
    toks += [t for t in ja if t.startswith(_PASS_PREFIXES)]
    return toks, dropped


def apply_native(jvm_kwargs=None, environ=None):
    """Put the isolate arguments for `jvm_kwargs` into ARCADEDB_NATIVE_ISOLATE_ARGS and return the effective string.

    Merge rule: a setting already in the variable wins (the caller or the package's own default is not overridden), a new one is appended,
    two entries for one setting in `jvm_kwargs` keep the first. Meaningful only before the isolate exists; see `_wrap_native`.
    """
    env = os.environ if environ is None else environ
    kw = jvm_kwargs or {}
    new, dropped = native_isolate_args(kw.get("heap_size"), kw.get("jvm_args"))
    have = env.get(NATIVE_ENV, "").split()
    keys = {_arg_key(t) for t in have}
    for t in new:
        if _arg_key(t) not in keys:
            have.append(t)
            keys.add(_arg_key(t))
    for t in dropped:
        if t not in native_dropped:
            native_dropped.append(t)
    env[NATIVE_ENV] = " ".join(have)
    return env[NATIVE_ENV]


def effective_native_args():
    """The isolate arguments this process runs with ("" when none), or None when it is not a native process. What a row records."""
    return os.environ.get(NATIVE_ENV, "") if _loaded is not None and backend() == "native" else None


def _wrap_native(mod):
    """On the native build, make `mod.create_database` / `mod.open_database` apply their `jvm_kwargs` as isolate arguments (see NATIVE_ENV)."""
    if (getattr(mod, "__backend__", None) or getattr(mod, "_DISTRIBUTION_BACKEND", None) or "jvm") != "native":
        return
    for name in ("create_database", "open_database"):
        fn = getattr(mod, name, None)
        if fn is None or getattr(fn, "_bench_native_wrapped", False):
            continue

        def wrapped(*a, __fn=fn, **kw):
            global _isolate_created
            if not _isolate_created:     # the isolate takes its arguments once; a later call cannot change them (the JVM cannot restart either)
                apply_native(kw.get("jvm_kwargs"))
                _isolate_created = True
            return __fn(*a, **kw)

        wrapped._bench_native_wrapped = True
        wrapped.__name__ = getattr(fn, "__name__", name)
        wrapped.__doc__ = getattr(fn, "__doc__", None)
        setattr(mod, name, wrapped)
