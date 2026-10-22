# JVM API

Helpers for locating the bundled runtime and configuring the JVM before the first
database or server is created.

!!! warning "Configure once per process"
    JVM options are locked after the JVM starts. Call `start_jvm(...)` before the
    first `create_database(...)`, `open_database(...)`, `database_exists(...)`,
    `DatabaseFactory(...)`, or `create_server(...)`. `database_exists()` takes no
    `jvm_kwargs` and starts the JVM with the default settings.

`start_jvm()` is safe to call from several threads at once: one thread starts the JVM, and the others
wait and then join it. Threads whose first call is `create_database()` or `open_database()` need no
earlier `start_jvm()` call. See "Free-threaded Python" on [Known Engine Issues](../guide/known-issues.md)
for what else to know when threads run without the GIL.

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

- `heap_size` (`Optional[str]`, default `None`): Maximum JVM heap, for example `"8g"` or `"4096m"`. `None` sizes the heap as a share of the RAM the JVM sees (`-XX:MaxRAMPercentage=50`); see [Memory](#memory)
- `disable_xml_limits` (`bool`, default `True`): Relaxes the JDK XML entity limits
  (`-Djdk.xml.maxGeneralEntitySizeLimit=0`, `-Djdk.xml.entityExpansionLimit=0`, and
  `-Djdk.xml.totalEntitySizeLimit=0`) for the whole process, for large XML imports.
  Pass `False` to keep the JDK defaults.
- `jvm_args` (`Optional[Iterable[str] | str]`, default `None`): Additional JVM flags as a string or iterable
- `common_pool_parallelism` (`Optional[int]`, default `None`): Explicit cap for `ForkJoinPool.common.parallelism`; a value below 1 raises `ArcadeDBError`
- `interrupt` (`Optional[bool]`, default `None`, meaning `False`): What Ctrl-C does. `False` leaves SIGINT to Python, so a `KeyboardInterrupt` is raised and `finally` blocks, `atexit` hooks, and the rollback of a `with db.transaction():` run. A Java call in progress, such as a slow query, is not interrupted: the `KeyboardInterrupt` arrives when it returns (about 9 s after Ctrl-C for a 10 s query, measured), and `kill -TERM` from another terminal still ends the process at once. A Java call that waits in an interruptible way (`Thread.sleep`, `Object.wait`, `wait_completion()` on an async executor) is woken by Ctrl-C, and JPype 1.7.1 can then raise `java.lang.InterruptedException` or `RuntimeError` and deliver the `KeyboardInterrupt` late; see [Known Engine Issues](../guide/known-issues.md) for the workaround. `True` is JPype's script default: the JVM handles SIGINT and ends the whole process with exit status 130, without Python cleanup. It can be given only to the first `start_jvm()`; a different value afterwards raises `ArcadeDBError`

**Raises:**

- `ArcadeDBError`: If the JVM is already started with a different configuration, the bundled runtime is missing, or JPype cannot start the JVM
- `ValueError`: If an `-Xms` is larger than the maximum heap (`heap_size` or `-Xmx`); raised before the JVM starts, so the Python process survives

**Notes:**

- The bundled JRE is always used; no external Java installation is required
- The module injects required defaults such as `jdk.incubator.vector`, UTF-8 file encoding, and required `--add-opens` flags if they are not already provided
- `ARCADEDB_JVM_ARGS` is always read: its flags come first and `jvm_args` are appended after them. In-code configuration is preferred
- Heap: a `heap_size` you pass always wins and replaces every `-Xmx` from `jvm_args` or the environment (this includes `"4g"`, which used to be the default and meant "not given"). With `heap_size=None`, an `-Xmx`, `-XX:MaxRAMPercentage=`, `-XX:MaxRAM=` or `-XX:MaxHeapSize=` given in `jvm_args` or the environment is kept (the largest `-Xmx` wins if there are several), and `-XX:MaxRAMPercentage=50` is added only when none is given
- JVM crash logs go to `./log/hs_err_pid%p.log` unless `ARCADEDB_JVM_ERROR_FILE` names another path

### Memory

By default the JVM heap is 50 percent of the RAM the JVM sees: the machine's RAM, or the memory limit of the container (cgroup) it runs in. You do not have to size it, and it follows the container limit. The other half is left for what is not heap: the Python process and its objects, thread stacks, metaspace and the JVM's GC structures, and direct (off-heap) buffers, whose cap (`-XX:MaxDirectMemorySize`) defaults to the maximum heap. That holds for one JVM per container: every Python process starts its own JVM, and each JVM sees the whole limit. With several processes in one container, see [Several processes in one container](#several-processes-in-one-container).

ArcadeDB's page cache follows the heap with no setting of its own: when `arcadedb.maxPageRAM` is not set, it is a quarter of the maximum heap. A value you set above 80 percent of the heap is reduced to half of it.

Override the default when you know better:

| You want | Pass |
|---|---|
| A fixed heap | `start_jvm(heap_size="8g")` (an explicit value always wins) |
| A different share of RAM | `start_jvm(jvm_args="-XX:MaxRAMPercentage=70")` or the same in `ARCADEDB_JVM_ARGS` |
| A bigger or smaller page cache | `-Darcadedb.maxPageRAM=<MB>` in `jvm_args` |

**`-Xms` (initial heap).**

- In a Python process, leave `-Xms` unset. The JVM then starts small (1/64 of RAM by default) and grows as needed. Never pin `-Xms` equal to `-Xmx` there: it commits the whole cap at start, and the Python side has to fit beside it. The bindings add no `-Xms` and no `-XX:InitialRAMPercentage`.
- A dedicated ArcadeDB server outside Python (`server.sh`, the Docker image): pinning `-Xms` to `-Xmx` is the usual server practice.
- In containers, size with percentages (`-XX:MaxRAMPercentage`) and leave headroom for direct memory, metaspace and thread stacks.
- If you pass a `heap_size` (or `-Xmx`) and an `-Xms` larger than it, `start_jvm` raises `ValueError` naming both values before the JVM starts, because the JVM would otherwise end the whole Python process ("Initial heap size set to a larger value than the maximum heap size"). `-Xms` alone, without `heap_size` or another max-heap flag, is not an error: the JVM raises the maximum heap to the initial size when that is above the default share (measured: `-Xms17g` on a 31 GB machine gave a 17 GB maximum, above the 50 percent default).

Raise the share when the Python side is small (a script that only runs queries); lower it when Python holds large results (a big `to_list()`, NumPy arrays) in the same process. Read the resolved values with `java.lang.Runtime.getRuntime().maxMemory()` and `GlobalConfiguration.MAX_PAGE_RAM.getValueAsLong()`.

In a container, keep the default share. In a probe at Docker `-m 2g`, a heap of 75 percent of the limit with 600 MB held by Python was killed by the kernel instead of raising a Java `OutOfMemoryError`; a kernel kill gives no Python exception and no cleanup. If the container needs more heap, raise the container limit too. See [Out of Memory Errors](../development/troubleshooting.md#out-of-memory-errors) for the probe.

#### Several processes in one container

Every Python process starts its own JVM, and every JVM sees the whole container limit. The default heap of 50 percent of the limit is right for one process and too large for several: `multiprocessing` workers, gunicorn workers, or two scripts in one container can claim the whole limit between them, and then the kernel kills the processes instead of Java raising an error. Call `start_jvm(heap_size=...)` in each process. For N processes, give each one at most:

```text
heap_size = (container limit - N x 0.4 GB - the data that process holds in Python) / N
```

Each process needs memory outside its heap. In the probe below it was 0.2 to 0.35 GB per process, and the rule uses 0.4 GB. Start lower when the processes hold much data in Python.

Probe (one laptop, one mix: Docker `-m 4g` with no swap, two Python processes in one container, each filling its heap to 85 percent): at the default heap (2048 MB cap each, 4096 MB in total) the kernel killed both processes (`OOMKilled=true`) with no Python exception. With `heap_size="1536m"` each (3072 MB in total) both finished, and the container peaked at 3.6 GB of 4 GB.

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
