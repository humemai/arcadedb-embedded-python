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

# Import names, in order. The first one that is the real package wins.
MODULES = ("arcadedb", "arcadedb_embedded")
# Distribution names for the version stamp, same order idea: new first.
DISTS = ("arcadedb", "arcadedb-jvm", "arcadedb-embedded")

_loaded = None


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
