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
├── jvm.py               # JVM startup (bundled JRE, JAR discovery)
├── core.py              # Database, DatabaseFactory, convenience helpers
├── graph.py             # Document, Vertex, Edge wrappers
├── schema.py            # Schema/Index/Property helpers
├── type_conversion.py   # Java ↔ Python value conversion
├── async_executor.py    # Async bulk executor wrapper
├── batch.py             # BatchContext (async-powered bulk helper)
├── importer.py          # Importer (CSV/XML)
├── exporter.py          # Export (JSONL/GraphML/GraphSON + CSV helper)
├── vector.py            # VectorIndex + array helpers
├── results.py           # ResultSet, Result (query results)
├── transactions.py      # TransactionContext (ACID guard)
├── server.py            # ArcadeDBServer (HTTP/Studio)
└── exceptions.py        # ArcadeDBError (unified exceptions)
```

### Module Responsibilities

**`__init__.py`**

- Central export surface (Database, AsyncExecutor, BatchContext, Schema, Importer, Exporter, VectorIndex, converters)
- Version metadata

**`jvm.py`**

- Starts JVM using bundled JRE and packaged JARs
- Prefers programmatic configuration (`start_jvm(...)`, `jvm_kwargs`)
- Supports `ARCADEDB_JVM_ARGS` / `ARCADEDB_JVM_ERROR_FILE` as fallback
- Refuses to start twice in a process

**`core.py`**

- `DatabaseFactory`: create/open databases
- `Database`: queries/commands, transactions, lookups, vector index builder
- Convenience: `async_executor()`, `batch_context()`, `schema`, export helpers

**`graph.py`**

- Record wrappers: `Document`, `Vertex`, `Edge`
- Property helpers, `new_edge()`, type-aware wrapping from Java records

**`schema.py`**

- `Schema`: type/property/index management
- `IndexType`, `PropertyType` enums

**`type_conversion.py`**

- `convert_java_to_python` / `convert_python_to_java`
- Datetime/Decimal/collection handling

**`async_executor.py`**

- `AsyncExecutor`: parallel record creation, commitEvery, WAL tuning

**`batch.py`**

- `BatchContext`: high-level bulk helper on top of `AsyncExecutor`

**`importer.py`**

- `Importer`: CSV/XML imports (documents/vertices/edges), FK resolution, commitEvery
- `import_csv` / `import_xml` convenience wrappers

**`exporter.py`**

- `export_database`: JSONL/GraphML/GraphSON
- `export_to_csv`: serialize ResultSet/list to CSV

**`vector.py`**

- `VectorIndex`: JVector-based ANN search
- `to_java_float_array` / `to_python_array`

**`results.py`**

- `ResultSet`: iterator, chunking, DataFrame export
- `Result`: property access with conversion

**`transactions.py`**

- `TransactionContext`: context-managed begin/commit/rollback

**`server.py`**

- `ArcadeDBServer`: HTTP/Studio server lifecycle, db management

**`exceptions.py`**

- `ArcadeDBError`: unified exception wrapper

## JPype Integration

### JVM Lifecycle

```python
def start_jvm(heap_size="4g", disable_xml_limits=True, jvm_args=None):
    if jpype.isJVMStarted():
        return

    # Locate bundled JRE + packaged JARs
    jvm_path = get_bundled_jre_lib_path()
    jar_files = glob.glob(os.path.join(get_jar_path(), "*.jar"))

    # Merge programmatic args (preferred) with optional env fallback
    args = _build_jvm_args(
        heap_size=heap_size,
        disable_xml_limits=disable_xml_limits,
        jvm_args=jvm_args,
    )

    # Single-shot startup per process
    jpype.startJVM(jvm_path, *args, classpath=os.pathsep.join(jar_files))
```

**JVM Startup:**

1. Uses the bundled JRE inside the wheel (no system JVM required)
2. Loads packaged ArcadeDB JARs from `arcadedb_embedded/jars`
3. Configurable via Python API before first database/importer creation (`start_jvm`, `jvm_kwargs`)
4. JVM stays live for the process lifetime and cannot be restarted

**Implications:**

- Set JVM options _before_ creating the first database/importer in a process
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
| `str` | `String` | Manual with `JString()` |
| `int` | `Integer`/`Long` | Automatic |
| `float` | `Float`/`Double` | Automatic |
| `bool` | `Boolean` | Automatic |
| `None` | `null` | Automatic |
| `list` | `ArrayList` | Manual conversion |
| `dict` | `HashMap` | Manual conversion |
| `np.ndarray` | `float[]` | via `to_java_float_array()` |

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

# Better: Context manager
db = arcadedb.open_database("./mydb")
with db.transaction():
    # Work with database
db.close()

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
    ├─ create_database() / open_database() / database_exists()
    └─ returns Database

Database (core.py)
    ├─ query()/command() → ResultSet | None
    ├─ begin()/commit()/rollback()/transaction() → TransactionContext
    ├─ new_vertex()/new_document() → Vertex | Document
    ├─ lookup_by_key()/lookup_by_rid()
    ├─ create_vector_index() → VectorIndex
    ├─ async_executor() → AsyncExecutor (async_executor.py)
    ├─ batch_context() → BatchContext (batch.py)
    ├─ schema → Schema (schema.py)
    ├─ export_database()/export_to_csv()
    └─ close()/is_open()

Schema (schema.py)
    ├─ create_document_type()/create_vertex_type()/create_edge_type()
    ├─ get_or_create_* helpers
    └─ create_property()/create_index()

AsyncExecutor (async_executor.py)
    ├─ set_parallel_level()/set_commit_every()/set_back_pressure()
    ├─ create_record()/update_record()/delete_record()/create_edge_between()
    └─ wait_completion()/close()

BatchContext (batch.py)
    ├─ create_vertex()/create_document()/create_edge()
    ├─ set_total()/get_errors()
    └─ context-managed wait/cleanup

Record wrappers (graph.py)
    ├─ Vertex → new_edge(), modify(), get_out_edges() (todo), property helpers
    ├─ Edge → get_out(), get_in(), modify()
    └─ Document → get()/set()/save()/delete()/modify(), to_dict(), get_rid()

ResultSet (results.py)
    ├─ iterator protocol
    ├─ to_list()/to_dataframe()/iter_chunks()/count()/first()/one()
    └─ wraps Result objects

Result (results.py)
    ├─ has_property()/get()
    └─ to_dict()/to_json()
```

## Threading Model

### Thread Safety

**Database:**

- `Database` instances are **NOT thread-safe**
- Each thread needs its own `Database` instance
- Transactions are thread-local

**Async executor & batch:**

- `AsyncExecutor` is thread-safe; it runs callbacks on Java worker threads
- `BatchContext` wraps a single `Database` + `AsyncExecutor`, so do not share it across threads

**Example:**

```python
import threading
import arcadedb_embedded as arcadedb

def worker(db_path, worker_id):
    """Worker thread with own database instance."""
    db = arcadedb.open_database(db_path)

    try:
        with db.transaction():
            vertex = db.new_vertex("Worker")
            vertex.set("id", worker_id)
            vertex.save()
    finally:
        db.close()

# Spawn workers
threads = []
for i in range(5):
    t = threading.Thread(target=worker, args=("./mydb", i))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
```

**Server Mode:**

- `ArcadeDBServer` is thread-safe
- HTTP requests handled by internal thread pool
- Each request gets isolated transaction

---

### Multiprocessing

**Safe:**

- Separate processes with separate JVMs
- No shared state
- Ideal for parallel imports

**Example:**

```python
import multiprocessing as mp
import arcadedb_embedded as arcadedb

def process_chunk(db_path, chunk):
    """Process chunk in separate process."""
    # Each process has own JVM
    db = arcadedb.open_database(db_path)

    with db.transaction():
        for record in chunk:
            vertex = db.new_vertex("Data")
            vertex.set("data", record)
            vertex.save()

    db.close()

# Split work across processes
if __name__ == "__main__":
    chunks = split_data_into_chunks()

    with mp.Pool(processes=4) as pool:
        pool.starmap(process_chunk,
                     [("./mydb", chunk) for chunk in chunks])
```

## Performance Considerations

### Bottlenecks

1. **JVM Boundary Crossing**
    - Cost: ~1-10 μs per Java method call
    - Impact: High-frequency calls (loops)
    - Solution: Batch operations, use Java bulk APIs
2. **Type Conversion**
    - Cost: Varies by type (arrays expensive)
    - Impact: Large data transfers
    - Solution: Minimize conversions, use efficient formats
3. **Transaction Overhead**
    - Cost: ~100 μs per transaction
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
    orders = db.query("sql", f"SELECT FROM Order WHERE user_id = '{user.get('id')}'")

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
    # Only one row in memory at a time
```

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

```python
# Enable JVM profiling
import jpype

# Before starting JVM (in package __init__.py):
jpype.startJVM(
    classpath=[jar_path],
    convertStrings=False,
    # JVM profiling options:
    "-XX:+PrintGCDetails",
    "-Xloggc:gc.log"
)
```

## Single Package Distribution

The Python binding is distributed as a **single, self-contained package** (`arcadedb-embedded`).

**Features:**

- **Bundled JRE**: Includes a minimal Java 25 Runtime Environment (JRE) via the `arcadedb-embedded-jre` package.
- **Full Feature Set**: Includes all ArcadeDB engines (SQL, OpenCypher, GraphQL, MongoDB).
- **Zero Configuration**: No external Java installation required.

```python
# uv pip install arcadedb-embedded
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")
db.query("sql", "SELECT FROM User")              # ✓
db.query("opencypher", "MATCH (n) RETURN n")     # ✓
db.query("graphql", "{users{name}}")             # ✓
db.query("mongodb", "db.User.find()")            # ✓
```

## Extension Points

### Custom Vertex/Edge Classes

```python
from arcadedb_embedded import Database

class CustomVertex:
    """Custom vertex wrapper with helper methods."""

    def __init__(self, java_vertex):
        self._java_vertex = java_vertex

    def get_friends(self):
        """Get all friends (out edges of type 'Knows')."""
        edges = self._java_vertex.getEdges(
            jpype.JClass('com.arcadedata.engine.api.graph.Vertex$DIRECTION').OUT,
            "Knows"
        )
        return [edge.getVertex() for edge in edges]

# Usage with wrapped database
```

### Custom Importers

```python
class CustomImporter:
    """Custom import format handler."""

    def __init__(self, db):
        self.db = db

    def import_xml(self, file_path, vertex_type):
        """Import XML format."""
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
importer = CustomImporter(db)
importer.import_xml("data.xml", "Data")
```

## Testing

### Unit Tests

```python
import unittest
import arcadedb_embedded as arcadedb
import tempfile
import shutil

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Create temp database for each test."""
        self.db_path = tempfile.mkdtemp()
        self.db = arcadedb.create_database(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        shutil.rmtree(self.db_path)

    def test_create_vertex(self):
        """Test vertex creation."""
        with self.db.transaction():
            vertex = self.db.new_vertex("User")
            vertex.set("name", "Alice")
            vertex.save()

        result = self.db.query("sql", "SELECT count(*) as count FROM User")
        count = result.next().get("count")
        self.assertEqual(count, 1)
```

### Integration Tests

```python
import pytest
import arcadedb_embedded as arcadedb

@pytest.fixture(scope="module")
def database():
    """Shared database for integration tests."""
    db = arcadedb.create_database("./test_db")
    yield db
    db.close()

def test_graph_traversal(database):
    """Test complex graph operations."""
    # Setup
    with database.transaction():
        alice = database.new_vertex("User")
        alice.set("name", "Alice")
        alice.save()

        bob = database.new_vertex("User")
        bob.set("name", "Bob")
        bob.save()

        edge = alice.new_edge("Knows", bob)
        edge.save()

    # Test
    result = database.query("sql", """
        SELECT expand(out('Knows'))
        FROM User
        WHERE name = 'Alice'
    """)

    friends = list(result)
    assert len(friends) == 1
    assert friends[0].get("name") == "Bob"
```

## Build System

### Package Build

```python
# pyproject.toml configuration
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "arcadedb-embedded"
version = "0.1.0"
dependencies = ["JPype1>=1.4.0", "numpy>=1.20.0"]
```

### JAR Management

```python
# setup_jars.py - Download and package JARs

import requests
import os

def download_arcadedb_jars(version):
    """Download ArcadeDB distribution JARs."""

    base_url = f"https://repo1.maven.org/maven2/com/arcadedata/"

    # Core JAR
    jar_url = f"{base_url}arcadedb/{version}/arcadedb-{version}.jar"
    download_jar(jar_url, f"arcadedb-{version}.jar")

    # Download all dependencies (GraphQL, etc.)
    pass

# Called during package build
```

## See Also

- [Database API Reference](../api/database.md) - Core database operations
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [JPype Documentation](https://jpype.readthedocs.io/) - JPype library docs
- [ArcadeDB Java API](https://docs.arcadedb.com/) - Underlying Java API
