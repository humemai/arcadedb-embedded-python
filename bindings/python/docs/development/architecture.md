# Architecture

Technical documentation for the ArcadeDB Python bindings architecture, JPype integration, and implementation details.

## Overview

The ArcadeDB Python bindings are a **thin wrapper** around the ArcadeDB Java library using JPype for JVM integration. This design provides:

- **Full API Coverage**: Access to all ArcadeDB features
- **Performance**: Minimal Python overhead
- **Maintenance**: Automatic feature parity with Java releases
- **Type Safety**: Python type hints with Java type conversion

## Module Structure

```
arcadedb_embedded/
├── __init__.py          # Package exports and version
├── _logging.py          # Internal logging helpers
├── async_executor.py    # Async command/query + record wrapper
├── core.py              # Database, DatabaseFactory, convenience helpers
├── exceptions.py        # ArcadeDBError (unified exceptions)
├── exporter.py          # Export (JSONL + CSV helper)
├── graph.py             # Document, Vertex, Edge wrappers
├── graph_batch.py       # High-throughput graph ingest wrapper
├── importer.py          # Document import helpers and result payloads
├── jvm.py               # JVM startup (bundled JRE, JAR discovery)
├── results.py           # ResultSet, Result (query results)
├── schema.py            # Schema/Index/Property helpers
├── server.py            # ArcadeDBServer (HTTP/Studio)
├── transactions.py      # TransactionContext (ACID guard)
├── type_conversion.py   # Java ↔ Python value conversion
└── vector.py            # VectorIndex + array helpers
```

### Module Responsibilities

**`__init__.py`**

- Central export surface, defined by `__all__`: `Database`, `DatabaseFactory`, and the module functions `create_database`, `open_database`, and `database_exists`; the record wrappers `Document`, `Vertex`, and `Edge`; `ResultSet` and `Result`; `Schema`, `IndexType`, and `PropertyType`; `TransactionContext`; `AsyncExecutor`, `GraphBatch`, and `ImportResult`; the type converters; `VectorIndex` and the array helpers (`to_java_float_array`, `to_java_int_array`, `to_java_byte_array`, and `to_python_array`); `ArcadeDBServer` and `create_server`; `export_database` and `export_to_csv`; `jar_fingerprint`; and `ArcadeDBError`
- Version metadata

**`_logging.py`**

- Internal logger access and swallowed-exception helpers for cleanup/finalizer paths

**`jvm.py`**

- Starts JVM using bundled JRE and packaged JARs
- Prefers programmatic configuration (`start_jvm(...)`, `jvm_kwargs`)
- Supports explicit heap and common-pool thread limits via `heap_size` and `common_pool_parallelism`
- Always reads `ARCADEDB_JVM_ARGS` and puts its flags before `jvm_args`; `ARCADEDB_JVM_ERROR_FILE` sets the crash-log path
- Adds default flags unless the merged arguments already set them: `--add-modules=jdk.incubator.vector`, `-Djava.awt.headless=true`, `--enable-native-access=ALL-UNNAMED`, `-Dfile.encoding=UTF8`, `--add-opens` flags (for `java.util.concurrent.atomic`, `java.nio.channels.spi`, and `java.lang`), `-Dpolyglot.engine.WarnInterpreterOnly=false`, `-XX:+UseCompactObjectHeaders`, and `-Xmx4g` when no heap is given; the `jdk.xml` entity limits are lifted while `disable_xml_limits` is true, and `-XX:ErrorFile` defaults to `./log/hs_err_pid%p.log`
- Starts once per process: a later `start_jvm()` with no settings, or the same ones, joins the running JVM; different settings raise `ArcadeDBError`
- From a source checkout (no `jars/` or `jre/` next to the package), extracts them from the newest wheel in `dist/` into `bindings/python/.runtime-cache/`, stamped with that wheel and re-extracted when the wheel changes
- `jar_fingerprint()` hashes the JARs on disk (`sha256` over all of them, `engine_sha256` without the bridge JAR), so two installs can be compared by engine rather than by version string
- `shutdown_jvm()` closes open databases and shuts the JVM down
- Registers an `atexit` hook that closes any database still open when the interpreter exits
- On Windows, disables Python's `faulthandler` right after the JVM starts, because the JVM's handled access violations would otherwise print as fatal exceptions

**`core.py`**

- `DatabaseFactory`: create/open databases
- `Database`: queries/commands, transactions, lookups, vector index builder
- `insert_many()`: bulk document ingest via the bridge's `DocumentBatcher`
- Convenience: `async_executor()`, `schema`, export helpers

**`graph.py`**

- Record wrappers: `Document`, `Vertex`, `Edge`
- Property helpers, `new_edge()`, type-aware wrapping from Java records

**`graph_batch.py`**

- `GraphBatch`: builder-backed high-throughput graph ingest API
- Batch vertex/edge creation plus flush/close lifecycle helpers

**`importer.py`**

- `import_documents()`: narrow Python wrapper around document import flows
- `ImportResult`: normalized import result payload and statistics accessor

**`schema.py`**

- `Schema`: type/property/index management
- `IndexType`, `PropertyType` enums

**`type_conversion.py`**

- `convert_java_to_python` / `convert_python_to_java`
- Datetime/Decimal/collection handling

**`async_executor.py`**

- `AsyncExecutor`: async SQL/OpenCypher command/query flows plus parallel record helpers, commitEvery, WAL tuning

**`exporter.py`**

- `export_database`: JSONL only; GraphML and GraphSON need the engine's arcadedb-gremlin module, which the wheel excludes, so they raise `ArcadeDBError`
- `export_to_csv`: serialize ResultSet/list to CSV

**`vector.py`**

- `VectorIndex`: JVector-based ANN search
- `to_java_float_array` / `to_java_int_array` / `to_java_byte_array` / `to_python_array`

**`results.py`**

- `ResultSet`: iterator, chunking, bulk materialization (`to_json_list`, `iter_json_batches`, `to_columns`), DataFrame and Arrow export (`to_dataframe`, `to_arrow`)
- `ResultSet.close()` and context-manager use: a set read to its end closes itself; one closed before its end (by `first()`, `one()`, `close()`, or leaving its `with` block) raises `ArcadeDBError` when read again
- An unclosed result set can keep the engine's parallel-scan threads parked, and they stall later queries that need the pool ([ArcadeData/arcadedb#8594](https://github.com/ArcadeData/arcadedb/issues/8594)), so close a set you stop reading early
- `Result`: property access with conversion

**`transactions.py`**

- `TransactionContext`: context-managed begin/commit/rollback

**`server.py`**

- `ArcadeDBServer`: HTTP/Studio server lifecycle, db management

**`exceptions.py`**

- `ArcadeDBError`: unified exception wrapper

### Java Bridge Jar

Alongside the engine JARs, the wheel ships `arcadedb-python-bridge.jar`:
small Java helpers (`RowBatcher`, `RowAccess`, `ColumnBatcher`,
`DocumentBatcher`, `EdgeBatcher`, `VertexBatcher`, and `TimeSeriesBatcher`, sources in
`bindings/python/src/java/com/arcadedb/python/`)
that move per-row/per-record loops to the Java side so bulk operations cost
one JPype crossing per batch instead of several per row. See
[Java Bridge](bridge.md) for which Python APIs use it and which of them have no
pure-JPype fallback.

## JPype Integration

### JVM Lifecycle

```python
def start_jvm(
    heap_size="4g",
    disable_xml_limits=True,
    jvm_args=None,
    common_pool_parallelism=None,
):
    if jpype.isJVMStarted():
        # No explicit settings: join the running JVM.
        # Same settings as the first start: return.
        # Different settings: raise ArcadeDBError (the JVM is configured once).
        ...
        return

    # Locate bundled JRE + packaged JARs
    jvm_path = get_bundled_jre_lib_path()
    jar_files = glob.glob(os.path.join(get_jar_path(), "*.jar"))

    # ARCADEDB_JVM_ARGS first, then jvm_args, then any missing default flags
    args = _build_jvm_args(
        heap_size=heap_size,
        disable_xml_limits=disable_xml_limits,
        jvm_args=jvm_args,
        common_pool_parallelism=common_pool_parallelism,
    )

    # Single-shot startup per process
    jpype.startJVM(jvm_path, *args, classpath=os.pathsep.join(jar_files))
```

**JVM Startup:**

1. Uses the bundled JRE inside the wheel (no system JVM required)
2. Loads packaged ArcadeDB JARs from `arcadedb_embedded/jars`
3. Configurable via Python API before first database or server creation (`start_jvm`, `jvm_kwargs`)
4. JVM stays live for the process lifetime and cannot be restarted

Thread control example:

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database(
    "./mydb",
    jvm_kwargs={
        "heap_size": "8g",
        "common_pool_parallelism": 8,
    },
)
```

**Implications:**

- Set JVM options _before_ creating the first database or server in a process
- Tests that need different JVM args must run in separate processes
- Server and embedded modes share the same in-process JVM

---

### Type Conversion

**Python → Java:**

```python
# String
python_str = "hello"
java_str = jpype.JString(python_str)

# Array
python_array = [1.0, 2.0, 3.0]
java_array = jpype.JArray(jpype.JFloat)(python_array)

# NumPy → Java (vectors)
import numpy as np
from arcadedb_embedded import to_java_float_array

numpy_array = np.array([1.0, 2.0, 3.0], dtype=np.float32)
java_array = to_java_float_array(numpy_array)
```

**Java → Python:**

```python
# Automatic for primitives
java_int = some_java_method()  # Returns Java int
python_int = int(java_int)      # Automatic conversion

# Manual for complex types
java_list = some_java_method()
python_list = [item for item in java_list]

# Java array → NumPy
from arcadedb_embedded import to_python_array

java_array = vertex.get("embedding")
numpy_array = to_python_array(java_array)
```

**Type Mapping:**

| Python Type | Java Type | Notes |
|-------------|-----------|-------|
| `str` | `String` | Automatic |
| `int` | `Long` | Automatic |
| `float` | `Double` | Automatic |
| `bool` | `Boolean` | Automatic |
| `None` | `null` | Automatic |
| `list` | `ArrayList` | Converted by `convert_python_to_java()` (used by `set()`, and by a bound parameter that is one of several arguments) |
| `tuple` | `ArrayList` | Converted by `convert_python_to_java()` |
| `set` | `HashSet` | Converted by `convert_python_to_java()` |
| `dict` | `HashMap` | Converted by `convert_python_to_java()` |
| `Decimal` | `BigDecimal` | Converted by `convert_python_to_java()` |
| `datetime` | `java.util.Date` | Converted by `convert_python_to_java()` |
| `date` | `LocalDate` | Converted by `convert_python_to_java()` |
| `bytes` / `bytearray` | `byte[]` | Converted by `convert_python_to_java()` |
| `np.ndarray` | `float[]` | via `to_java_float_array()`; a bound parameter is converted automatically |
| `np.ndarray` (integer dtype) | `int[]` | via `to_java_int_array()` |

A single `list` or `tuple` passed as the only bound argument is not one parameter: it
expands into the positional parameters, one element per `?`.

---

### Memory Management

**Garbage Collection:**

- Python GC: Manages Python objects
- Java GC: Manages Java objects
- JPype: Bridges both, uses Java GC for wrapped objects

**Best Practices:**

```python
# Good: Explicit cleanup
db = arcadedb.open_database("./mydb")
try:
    # Use database
    pass
finally:
    db.close()

# Better: Context manager (closes the database on exit)
with arcadedb.open_database("./mydb") as db:
    with db.transaction():
        ...  # Work with database

# Long-running processes: Periodic GC
import gc
for batch in large_dataset:
    process_batch(batch)
    gc.collect()  # Trigger Python GC
```

**Memory Leaks:**

- Holding references to Java objects prevents GC
- Large ResultSets should be consumed and released
- Server mode: Monitor JVM heap usage

## Class Hierarchy

```
DatabaseFactory (core.py)
    ├─ create() / open() / exists()
    └─ returns Database

create_database() / open_database() / database_exists() (core.py, module functions)

Database (core.py)
    ├─ query()/command() → ResultSet | None
    ├─ begin()/commit()/rollback()/transaction() → TransactionContext
    ├─ run_in_transaction(fn, retries=12) (retries on conflicts)
    ├─ is_transaction_active()
    ├─ new_vertex()/new_document() → Vertex | Document
    ├─ insert_many() → int
    ├─ import_documents() → ImportResult
    ├─ graph_batch() → GraphBatch (graph_batch.py)
    ├─ lookup_by_key()/lookup_by_rid()/count_type()
    ├─ create_vector_index() → VectorIndex
    ├─ async_executor() → AsyncExecutor (async_executor.py)
    ├─ schema → Schema (schema.py)
    ├─ set_wal_flush()/set_read_your_writes()/set_auto_transaction()
    ├─ export_database()/export_to_csv()
    ├─ get_name()
    └─ close()/is_open()/drop()

Schema (schema.py)
    ├─ create_document_type()/create_vertex_type()/create_edge_type()
    ├─ get_or_create_* helpers
    └─ create_property()/create_index()

AsyncExecutor (async_executor.py)
    ├─ set_parallel_level()/set_commit_every()/set_back_pressure()
    ├─ command()/query()/scan_type()/new_edge()/transaction()
    └─ wait_completion()/close()

Record wrappers (graph.py)
    ├─ Vertex → new_edge(), modify(), get_out_edges()/get_in_edges()/get_both_edges(), property helpers
    ├─ Edge → get_out(), get_in(), modify()
    └─ Document → get()/set()/save()/delete()/modify(), to_dict(), get_rid()

ResultSet (results.py)
    ├─ iterator protocol, context manager
    ├─ to_list()/to_dataframe()/iter_chunks()/count()/first()/one()
    ├─ to_json_list()/iter_json_batches()/to_columns()/to_arrow()
    ├─ close()
    └─ wraps Result objects

Result (results.py)
    ├─ has_property()/get()
    └─ to_dict()/to_json()
```

## Threading Model

### Thread Safety

**Database:**

- One `Database` instance can be shared by the threads of a process; open it once and
  pass it around rather than opening it again per thread
- Transactions are per thread: each thread's `db.transaction()` is its own
- Two threads that update the same record can conflict: the losing commit raises
  `ArcadeDBError` with `ConcurrentModificationException` in the message, and the usual
  answer is to retry that transaction: `db.run_in_transaction(fn, retries=12)` rolls
  back and re-runs `fn` on a conflict

`tests/test_concurrency.py` covers this: `test_thread_safety` runs four threads against
one shared `Database`, and `test_oltp_mixed_workload_threads` mixes reads with retried
updates. See [Concurrency Tests](testing/test-concurrency.md).

**Example:**

```python
import threading
import arcadedb_embedded as arcadedb

db = arcadedb.open_database("./mydb")  # one instance, shared (has a Worker vertex type)

def worker(worker_id):
    """Worker thread using the shared database."""
    with db.transaction():
        vertex = db.new_vertex("Worker")
        vertex.set("id", worker_id)
        vertex.save()

threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

db.close()
```

**Server Mode:**

- The server shares the same in-process JVM and database instances
- HTTP requests are handled by the server's own thread pool

---

### Multiprocessing

Only one process can open a database directory at a time: the engine holds an OS lock on
`database.lck` while the database is open, and a second process gets
`ArcadeDBError: ... is locked by another process` (asserted by
`test_concurrency.py::test_concurrent_access_limitation`). Separate processes can work
on separate databases. To share one database across processes, open it in one process
that runs a server, and have the others use its HTTP API (see
[Server Patterns](testing/test-server-patterns.md)).

## Performance Considerations

### Bottlenecks

1. **JVM Boundary Crossing**
    - Cost: a fixed cost on every Java method call
    - Impact: High-frequency calls (loops)
    - Solution: Batch operations, use Java bulk APIs
2. **Type Conversion**
    - Cost: Varies by type (arrays expensive)
    - Impact: Large data transfers
    - Solution: Minimize conversions, use efficient formats
3. **Transaction Overhead**
    - Cost: a fixed cost on every commit
    - Impact: Many small transactions
    - Solution: Batch into larger transactions

---

### Optimization Strategies

**Batch Operations:**

```python
# Bad: Many small transactions
for record in records:
    with db.transaction():
        vertex = db.new_vertex("Data")
        vertex.set("data", record)
        vertex.save()
# 1000 records = 1000 transactions

# Good: One large transaction
with db.transaction():
    for record in records:
        vertex = db.new_vertex("Data")
        vertex.set("data", record)
        vertex.save()
# 1000 records = 1 transaction
```

**Query Optimization:**

```python
# Bad: N+1 queries
users = db.query("sql", "SELECT FROM User")
for user in users:
    # Separate query per user!
    orders = db.query("sql", "SELECT FROM Order WHERE user_id = ?", user.get("id"))

# Good: Single query with traversal
result = db.query("sql", """
    SELECT
        name,
        out('Placed').name as orders
    FROM User
""")
```

**ResultSet Streaming:**

```python
# Bad: Load all results
result = db.query("sql", "SELECT FROM LargeTable")
all_results = list(result)  # Loads everything into memory

# Good: Stream results
result = db.query("sql", "SELECT FROM LargeTable")
for row in result:
    process(row)
```

When you do need the whole result materialized, prefer the bulk APIs
(`to_columns()`/`to_dataframe()` or `to_json_list()`) over `list(result)` /
`to_list()`; see the [Performance guide](../guide/performance.md).

---

### Profiling

**Python Side:**

```python
import cProfile
import pstats

def benchmark():
    db = arcadedb.create_database("./bench")
    with db.transaction():
        for i in range(10000):
            vertex = db.new_vertex("Data")
            vertex.set("id", i)
            vertex.save()
    db.close()

# Profile
cProfile.run('benchmark()', 'stats.prof')
stats = pstats.Stats('stats.prof')
stats.sort_stats('cumulative')
stats.print_stats(20)
```

**Java Side:**

The bindings start the JVM themselves (`jvm.py`), so pass JVM options through
`start_jvm()` (or `jvm_kwargs`, or the `ARCADEDB_JVM_ARGS` environment variable)
before the first database or server is created:

```python
from arcadedb_embedded.jvm import start_jvm

# GC logging with JDK unified logging
start_jvm(jvm_args="-Xlog:gc*:file=gc.log")
```

## Single Package Distribution

The Python binding is distributed as a **single, self-contained package** (`arcadedb-embedded`).

**Features:**

- **Bundled JRE**: Includes a minimal Java 25 Runtime Environment (JRE) bundled directly in the wheel.
- **Query engines**: SQL, OpenCypher, and GraphQL ship in the wheel.
  `scripts/jar_exclusions.txt` drops the Gremlin, MongoDB, and gRPC modules, Raft HA
  (so the server is single-node), metrics and tracing, the JavaScript stack (js,
  truffle, icu4j, and regex), commons-math3, Jackson, snappy-java, and jline.
- **Wire protocols**: the Postgres, Redis, and Bolt plugins ship, and the server starts
  each one only when its plugin is configured (see `create_server()`).
- **Zero Configuration**: No external Java installation required.

```python
# pip install arcadedb-embedded
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")
db.query("sql", "SELECT FROM User")
db.query("opencypher", "MATCH (n) RETURN n")
```

## Extension Points

### Custom Vertex/Edge Classes

```python
import jpype

class CustomVertex:
    """Custom vertex wrapper with helper methods."""

    def __init__(self, java_vertex):
        self._java_vertex = java_vertex

    def get_friends(self):
        """Get the vertices reached by outgoing 'Knows' edges."""
        direction = jpype.JClass("com.arcadedb.graph.Vertex$DIRECTION")
        return list(self._java_vertex.getVertices(direction.OUT, "Knows"))
```

### Custom Loaders

```python
class CustomXmlLoader:
    """Custom XML loading helper."""

    def __init__(self, db):
        self.db = db

    def load_xml(self, file_path, vertex_type):
        """Load XML records into a vertex type."""
        import xml.etree.ElementTree as ET

        tree = ET.parse(file_path)
        root = tree.getroot()

        with self.db.transaction():
            for elem in root.findall('.//record'):
                vertex = self.db.new_vertex(vertex_type)
                for child in elem:
                    vertex.set(child.tag, child.text)
                vertex.save()

# Usage
xml_loader = CustomXmlLoader(db)
xml_loader.load_xml("data.xml", "Data")
```

## Testing

The test suite, its fixtures, and the patterns it uses are documented under
[Testing](testing.md), with one page per test file and a
[Best Practices](testing/best-practices.md) summary.

## Build System

### Package Build

```python
# pyproject.toml configuration
[build-system]
requires = ["build>=0.7.0", "setuptools>=61.0", "wheel", "jpype1"]
build-backend = "setuptools.build_meta"

[project]
name = "arcadedb-embedded"
# Placeholder: the build overwrites this from the parent pom.xml
version = "0.0.0"
requires-python = ">=3.10"
dependencies = ["jpype1>=1.5.0"]
```

`jpype1` is the only runtime dependency. `numpy` is an optional extra
(`arcadedb-embedded[vector]`) rather than a hard requirement, so a plain install
stays minimal. The extras' floors are audited in CI, so treat
`bindings/python/pyproject.toml` as authoritative rather than this excerpt.

### JAR Management

`scripts/setup_jars.py` downloads nothing. It runs inside the Docker build
(`scripts/Dockerfile.build`, `python-builder` stage) and stages what earlier
stages produced into the package:

- `find_jar_files()` looks for the already-filtered JARs in `/build/jars`
  (the Docker build location) or `/home/arcadedb/lib`
- `copy_jars_to_package()` clears `src/arcadedb_embedded/jars/` and copies
  those JARs into it
- `copy_jre()` replaces `src/arcadedb_embedded/jre/` with the `jlink` JRE
  from `/build/jre`
- `main()` runs the two copies and exits non-zero if either fails

The JARs themselves come from the `arcadedata/arcadedb` image, unless
`build.sh` is given a local JAR directory (its third argument, `JAR_LIB_DIR`), and
`jar_exclusions.txt` is applied before this script runs. Native builds
(`scripts/build-native.sh`) do the same staging themselves and do not call it.
See [Build Architecture](build-architecture.md).

## See Also

- [Database API Reference](../api/database.md) - Core database operations
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [JPype Documentation](https://jpype.readthedocs.io/) - JPype library docs
- [ArcadeDB Java API](https://docs.arcadedb.com/) - Underlying Java API
