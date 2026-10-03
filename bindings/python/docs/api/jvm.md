# JVM API

Helpers for locating the bundled runtime and configuring the JVM before the first
database or server is created.

!!! warning "Configure once per process"
    JVM options are locked after the JVM starts. Call `start_jvm(...)` before the
    first `create_database(...)`, `open_database(...)`, `database_exists(...)`,
    `DatabaseFactory(...)`, or `create_server(...)`. `database_exists()` takes no
    `jvm_kwargs` and starts the JVM with the default settings.

## Overview

The `arcadedb_embedded.jvm` module provides these public entry points:

- `start_jvm(...)` to configure and start the bundled JVM explicitly
- `shutdown_jvm()` to shut down a JVM started in the current process
- `jar_fingerprint()` to identify the engine JARs this install carries
- runtime location helpers for jars and the bundled JRE library

## start_jvm

```python
from arcadedb_embedded.jvm import start_jvm

start_jvm(
    heap_size="8g",
    jvm_args="-XX:MaxDirectMemorySize=8g",
    common_pool_parallelism=8,
)
```

**Parameters:**

- `heap_size` (`Optional[str]`, default `"4g"`): Maximum JVM heap, for example `"8g"` or `"4096m"`
- `disable_xml_limits` (`bool`, default `True`): Relaxes the JDK XML entity limits
  (`-Djdk.xml.maxGeneralEntitySizeLimit=0`, `-Djdk.xml.entityExpansionLimit=0`, and
  `-Djdk.xml.totalEntitySizeLimit=0`) for the whole process, for large XML imports.
  Pass `False` to keep the JDK defaults.
- `jvm_args` (`Optional[Iterable[str] | str]`, default `None`): Additional JVM flags as a string or iterable
- `common_pool_parallelism` (`Optional[int]`, default `None`): Explicit cap for `ForkJoinPool.common.parallelism`; a value below 1 raises `ArcadeDBError`
- `interrupt` (`Optional[bool]`, default `None`, meaning `False`): What Ctrl-C does. `False` leaves SIGINT to Python, so a `KeyboardInterrupt` is raised and `finally` blocks, `atexit` hooks, and the rollback of a `with db.transaction():` run. A Java call in progress, such as a slow query, is not interrupted: the `KeyboardInterrupt` arrives when it returns (about 9 s after Ctrl-C for a 10 s query, measured), and `kill -TERM` from another terminal still ends the process at once. `True` is JPype's script default: the JVM handles SIGINT and ends the whole process with exit status 130, without Python cleanup. It can be given only to the first `start_jvm()`; a different value afterwards raises `ArcadeDBError`

**Raises:**

- `ArcadeDBError`: If the JVM is already started with a different configuration, the bundled runtime is missing, or JPype cannot start the JVM

**Notes:**

- The bundled JRE is always used; no external Java installation is required
- The module injects required defaults such as `jdk.incubator.vector`, UTF-8 file encoding, and required `--add-opens` flags if they are not already provided
- `ARCADEDB_JVM_ARGS` is always read: its flags come first and `jvm_args` are appended after them. In-code configuration is preferred
- Heap: a `heap_size` other than `"4g"` replaces every `-Xmx` from `jvm_args` or the environment. With the default `"4g"` (or `None`), an `-Xmx` given there is kept (the largest wins if there are several), and `-Xmx4g` is added only when none is given
- JVM crash logs go to `./log/hs_err_pid%p.log` unless `ARCADEDB_JVM_ERROR_FILE` names another path

## shutdown_jvm

```python
from arcadedb_embedded.jvm import shutdown_jvm

shutdown_jvm()
```

Shuts down the JVM if it is running in the current process.

!!! note
    Most application code does not need to call this directly. Normal database and
    server usage should focus on proper object cleanup; use this helper mainly in
    test harnesses or short-lived tooling.

## jar_fingerprint

```python
import arcadedb_embedded as arcadedb

fp = arcadedb.jar_fingerprint()
print(fp["count"], fp["engine_sha256"][:12])
```

Hashes the JAR files actually on disk, so a results row can record which engine
produced it. `__version__` is the package version and can disagree with the JARs (for
example, a wheel built from a locally patched Java tree).

**Parameters:**

- `per_jar` (`bool`, default `False`): Also return a `jars` list with one dict per JAR:
  `name`, `bytes`, `sha256`, and `engine` (`False` for the bindings' own bridge JAR)

**Returns:** a dict with `count`, `bytes`, `sha256` (every JAR: "is this the same
build?"), `engine_sha256` (every JAR except the bindings' own compiled bridge JAR: "is
this the same ArcadeDB?"), `engine_count`, and `jar_dir`, plus `jars` when `per_jar` is
set.

## get_jar_path

```python
from arcadedb_embedded.jvm import get_jar_path

jar_dir = get_jar_path()
```

Returns the directory containing the bundled ArcadeDB JAR files.

## get_bundled_jre_lib_path

```python
from arcadedb_embedded.jvm import get_bundled_jre_lib_path

jvm_lib = get_bundled_jre_lib_path()
```

Returns the platform-specific JVM library path inside the bundled runtime:

- Linux: `lib/server/libjvm.so`
- macOS: `lib/server/libjvm.dylib`
- Windows: `bin/server/jvm.dll`

Raises `ArcadeDBError` if the bundled runtime is missing or incomplete.

## Recommended Pattern

```python
from arcadedb_embedded.jvm import start_jvm
import arcadedb_embedded as arcadedb

start_jvm(heap_size="8g", jvm_args="-XX:MaxDirectMemorySize=8g")

with arcadedb.create_database("./db") as db:
    row = db.query("sql", "SELECT 1 AS ok").one()
    assert row.get("ok") == 1
```
