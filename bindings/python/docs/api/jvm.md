# JVM API

Helpers for locating the bundled runtime and configuring the JVM before the first
database is created.

!!! warning "Configure once per process"
    JVM options are locked after the JVM starts. Call `start_jvm(...)` before the
    first `create_database(...)` or `open_database(...)`.

## Overview

The `arcadedb_embedded.jvm` module provides three public entry points:

- `start_jvm(...)` to configure and start the bundled JVM explicitly
- `shutdown_jvm()` to shut down a JVM started in the current process
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

- `heap_size` (`Optional[str]`): Maximum JVM heap, for example `"4g"` or `"4096m"`
- `disable_xml_limits` (`bool`): If `True`, relaxes JDK XML entity limits for large XML imports
- `jvm_args` (`Optional[Iterable[str] | str]`): Additional JVM flags as a string or iterable
- `common_pool_parallelism` (`Optional[int]`): Explicit cap for `ForkJoinPool.common.parallelism`

**Raises:**

- `ArcadeDBError`: If the JVM is already started with a different configuration, the bundled runtime is missing, or JPype cannot start the JVM

**Notes:**

- The bundled JRE is always used; no external Java installation is required
- The module injects required defaults such as `jdk.incubator.vector`, UTF-8 file encoding, and required `--add-opens` flags if they are not already provided
- `ARCADEDB_JVM_ARGS` remains supported as an environment fallback, but in-code configuration is preferred

## shutdown_jvm

```python
from arcadedb_embedded.jvm import shutdown_jvm

shutdown_jvm()
```

Shuts down the JVM if it is running in the current process.

!!! note
    Most application code does not need to call this directly. Normal database
    usage should focus on proper object cleanup; use this helper mainly in
    test harnesses or short-lived tooling.

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
