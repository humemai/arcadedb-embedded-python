# Troubleshooting

Common issues, solutions, and debugging techniques for ArcadeDB Python bindings.

## Installation Issues

### Package Import Errors

**Problem**: Can't import arcadedb_embedded module

**Solutions**:

1. **Verify Installation**:
    ```bash
    pip show arcadedb-embedded
    pip list | grep arcadedb
    ```

2. **Reinstall Package**:
    ```bash
    pip uninstall arcadedb-embedded
    pip install arcadedb-embedded
    ```

3. **Reinstall if wheel looks corrupted**:
    Wheels bundle the ArcadeDB JRE and JARs. If imports fail, reinstall the wheel
    (no external Java install is needed):

    ```bash
    pip uninstall arcadedb-embedded
    pip install --no-cache-dir arcadedb-embedded
    ```

4. **Check Python Path**:
    ```python
    import sys
    print(sys.path)
    ```
---

## Development Environment

These apply to the repository's uv environment (the repo-root `pyproject.toml`).

### `uv run` Cannot Resolve `arcadedb-embedded`

The environment takes `arcadedb-embedded` only from the wheels in
`bindings/python/dist/`, and it is pinned to Python 3.12, so it needs a cp312 wheel
there. Build one with `cd bindings/python && ./scripts/build.sh` (on Linux it builds
for Python 3.12 by default).

### The Environment Still Runs an Older Wheel

`build.sh` refreshes the environment only when `CI` is unset and `uv` is on `PATH`.
Refresh it by hand from the repository root:

```bash
uv lock --upgrade-package arcadedb-embedded && uv sync --reinstall-package arcadedb-embedded
```

To see which engine is installed:

```bash
uv run python -c "import arcadedb_embedded as a; print(a.__version__, a.jar_fingerprint()['engine_sha256'])"
```

---

## Runtime Errors

### Database Already Exists

**Symptom:**
```python
arcadedb.create_database("./mydb")
# ArcadeDBError: Failed to create database: ... Database './mydb' already exists
```

**Solution:**

Use `open_database()` instead:

```python
import os
import arcadedb_embedded as arcadedb

if os.path.exists("./mydb"):
    db = arcadedb.open_database("./mydb")
else:
    db = arcadedb.create_database("./mydb")
```

Or delete existing database:

```python
import shutil

# Remove existing database
if os.path.exists("./mydb"):
    shutil.rmtree("./mydb")

# Create fresh database
db = arcadedb.create_database("./mydb")
```

---

### Database Left Open at Exit

The bindings close any database still open when the interpreter exits. Call
`db.close()` (or use a `with` block) to flush and release the database lock at a
known point instead.

---

### Database Locked

**Symptom:** `ArcadeDBError: ... Database '<name>' is locked by another process (path=...)`

**Cause:** Another process has the database open. The engine holds an OS lock on
`database.lck` in the database directory while the database is open, and the OS
releases that lock when the process exits, even after a crash.

**Solution:**

1. **Close the database in the process that holds it:**
```python
# Ensure previous database is closed
db.close()
```

2. **Check for orphaned processes:**
```bash
ps aux | grep python
kill <PID>
```

3. **Share the database through a server** if several processes need it at once
   (see [Server Mode](../guide/server.md)).

!!! warning "Do not delete `database.lck`"
    A `database.lck` left on disk after a crash does not block anything: no process
    holds its lock any more. It is the marker that tells the next open to replay the
    WAL, and a clean close deletes it. Deleting it by hand skips that recovery.

---

### Memory Configuration

#### JVM Memory Configuration

Configure JVM memory in Python **before the first database or server is created**:

**Basic Configuration (preferred):**

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.jvm import start_jvm

# Default: 4GB heap (no changes needed)

# Production: 8GB heap with matching initial size
start_jvm(heap_size="8g", jvm_args="-Xms8g")
```

**Common JVM Options:**

| Option | Description | Example |
|--------|-------------|----------|
| `-Xmx<size>` | Maximum heap memory | `-Xmx8g` (8 gigabytes) |
| `-Xms<size>` | Initial heap size (recommended: same as `-Xmx`) | `-Xms8g` |
| `-XX:MaxDirectMemorySize=<size>` | Limit off-heap direct buffers | `-XX:MaxDirectMemorySize=8g` |
| `-Darcadedb.vectorIndex.graphBuildCacheSize=<count>` | Override for the vectors cached during the graph build (default `0`, automatic; leave it) | `-Darcadedb.vectorIndex.graphBuildCacheSize=2000000` (only to bound a build on a small heap) |
| `-Darcadedb.vectorIndex.mutationsBeforeRebuild=<count>` | FLOOR for the rebuild threshold (default: 100). The effective threshold is `max(floor, min(graphSize x rebuildGraphRatio, maxPendingMutations))`, so on a 1M-vector index at the defaults it is **50,000**, not 100, so raising this alone changes nothing above ~500 vectors. Separately, `arcadedb.vectorIndex.maxDeltaScanRatio` (default 1.0) triggers a rebuild sooner when a query's scan of the pending vectors costs more than that multiple of its graph walk; the floor still applies | `-Darcadedb.vectorIndex.mutationsBeforeRebuild=200` |

**Vector Index Memory Tuning:**

The vector graph-build and search caches live on the JVM heap and size themselves
automatically, each within a share of the heap (25% by default). Size the heap for the
live vector set, and lower the shares if the caches crowd out other work (see
[Out of Memory Errors](#out-of-memory-errors)):

```python
from arcadedb_embedded.jvm import start_jvm

start_jvm(
    heap_size="8g",
    jvm_args=(
        "-Xms8g "
        "-Darcadedb.vectorIndex.graphBuildCacheMaxHeapPercent=20 "
        "-Darcadedb.vectorIndex.searchCacheMaxHeapPercent=20"
    ),
)
```

**Cache Size Guidelines:**

- `locationCacheSize`: not a setting. The bindings raise `ValueError` for
  `location_cache_size`, the engine refuses the per-index metadata key, and the JVM
  property `arcadedb.vectorIndex.locationCacheSize` is ignored. Size the heap for the
  live vector set instead.

- `graphBuildCacheSize`: vectors held in RAM while the graph is built. **Leave
    it at the default.** The default (`0`) is automatic: the engine sizes the
    cache from the heap it actually has free and takes the whole corpus when it
    fits, so a build never re-reads vectors from disk unnecessarily. Set an
    absolute count only when you deliberately run a small heap and want the
    build bounded; memory ≈ cacheSize × (dimensions × 4 + 64) bytes.

**Memory Planning:**

```text
Total Process Memory = JVM Heap + Off-Heap Components

Off-Heap Components:

- Direct buffers (MaxDirectMemorySize)
- Metaspace (class definitions)
- Page cache
- Thread stacks

(The vector index caches are on the heap: they count toward -Xmx.)

Rule of thumb: Plan for 1.5-2× your heap size in actual RAM
```

**Example Configurations:**

```python
# Small datasets (<1M records, <100K vectors)
from arcadedb_embedded.jvm import start_jvm

start_jvm(heap_size="2g", jvm_args="-Xms2g")

# Medium datasets (1M-10M records, 100K-1M vectors)
start_jvm(heap_size="8g", jvm_args="-Xms8g -XX:MaxDirectMemorySize=8g")

# Large datasets (10M+ records, 1M+ vectors)
start_jvm(heap_size="16g", jvm_args="-Xms16g -XX:MaxDirectMemorySize=16g")

# High-dimensional vectors (e.g., 1536-dim embeddings): each cached vector
# costs about dimensions x 4 + 64 bytes, so give the heap room for the corpus
start_jvm(heap_size="8g", jvm_args="-Xms8g -XX:MaxDirectMemorySize=8g")
```

!!! tip "Page cache share (ArcadeDB 26.10.1 and later)"
    `arcadedb.maxPageRAM`, the page cache, defaults to a quarter of the heap, which is a
    safe baseline. For a dedicated process whose database is larger than the cache, the
    maintainers recommend 40-50% of the heap (a value above 80% is reduced to half of the
    heap), for example `start_jvm(heap_size="16g", jvm_args="-Xms16g -Darcadedb.maxPageRAM=7000")`
    (megabytes, here about 45%). Leave it alone when the database fits in the default share
    (ArcadeData/arcadedb#9168).

!!! tip "Index page size (ArcadeDB 26.10.1 and later)"
    A one-record insert copies the whole page of each LSM index it touches into its
    transaction, 256 KB by default. `arcadedb.indexDefaultPageSize` (bytes, default 262144,
    minimum 8192) sets the page size of new plain LSM-tree indexes created by SQL
    `CREATE INDEX`; with 16384, a one-record insert allocated about 97.7 KB per insert instead
    of 339 KB and ran about 2x faster in our repro (10 runs per side on both JDKs, 1.96x to
    2.01x), at the price of slower point lookups through that index (1.11x, interval 1.06x to
    1.18x on JDK 25 and 1.07x to 1.15x on JDK 21). Measure your own workload before changing
    it (ArcadeData/arcadedb#9175).

!!! warning "Configuration Timing"
    JVM options are locked after the JVM starts. Configure `start_jvm(...)` or pass
    `jvm_kwargs` before the first database or server is created. To change settings,
    start a new Python process.

!!! tip "Alternative: ARCADEDB_JVM_ERROR_FILE"
    Set crash log location:

    ```bash
    export ARCADEDB_JVM_ERROR_FILE="/var/log/arcade/errors.log"
    ```

#### Out of Memory Errors

**Problem**: `OutOfMemoryError` or heap space errors

**Solutions**:

1. **Increase Heap (preferred)**:
    ```python
    from arcadedb_embedded.jvm import start_jvm

    start_jvm(heap_size="8g", jvm_args="-Xms8g")
    ```

2. **Lower the caches' heap share** (for vector workloads). The build and
   search caches size themselves automatically inside a share of the heap
   (25% each by default); lower the share rather than pinning a count:
    ```python
    from arcadedb_embedded.jvm import start_jvm
    start_jvm(
        heap_size="8g",
        jvm_args=(
            "-Xms8g "
            "-Darcadedb.vectorIndex.graphBuildCacheMaxHeapPercent=10 "
            "-Darcadedb.vectorIndex.searchCacheMaxHeapPercent=10"
        ),
    )
    ```

3. **Use Batch Processing**:
    ```python
    batch_size = 1000
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        process_batch(batch)
    ```

4. **Close ResultSets**:
    ```python
    result = db.query("sql", "SELECT FROM LargeTable")
    try:
        for row in result:
            process(row)
    finally:
        result.close()
    ```

---

### Data Type Issues

**Problem**: Type conversion errors

**Solutions**:

1. **Use Correct Types**:
    ```python
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO User SET age = ?, name = ?, tags = ?, created = ?",
            25,
            "Alice",
            ["python", "database"],
            datetime.now(timezone.utc),
        )
    ```

2. **Bind Vectors as Java Arrays**: a NumPy array passed as a bound parameter is
    converted to a Java `float[]` automatically, so it works, but it takes the
    general conversion path on every call. Convert it once with
    `to_java_float_array()` and bind the Java array: a Java array crosses as it is,
    which made a loop of single-row vector inserts about 13% faster in our
    measurements (95% interval 4 to 18%). `Document.set()` needs the explicit conversion anyway (see
    [Type Conversion Error](#type-conversion-error)).
    ```python
    import numpy as np
    import arcadedb_embedded as arcadedb

    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    jvec = arcadedb.to_java_float_array(arr)
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO EmbeddingDoc SET embedding = ?",
            jvec,
        )
    ```
    For many vectors, a bulk path (`insert_columns`, `graph_batch`) is faster
    than any loop of single-row statements; see the vectors guide.
---

### Nested Transactions Commit Independently

**Symptom:** Records written in an inner `db.transaction()` survive even though the
outer transaction rolled back.

```python
with db.transaction():
    with db.transaction():  # Nested!
        pass
```

**Cause:** `begin()` inside an active transaction starts a new, independent nested
transaction on the same thread; it raises no error. The inner block commits or rolls
back on its own, so it is not a savepoint of the outer one (see
[Nested Transactions](../api/transactions.md#nested-transactions)).

**Solution:**

Don't nest transactions unless you want the inner block to commit on its own:

```python
# Bad: another_operation() commits on its own, even if the outer block rolls back
with db.transaction():
    some_operation()
    with db.transaction():
        another_operation()

# Good
with db.transaction():
    some_operation()
    another_operation()
```

Or use separate transaction blocks:

```python
with db.transaction():
    some_operation()

# First transaction committed

with db.transaction():
    another_operation()
```

---

### A String Filter Returns Nothing

**Symptom:** A query that filters on a string returns no rows and raises no error.

```python
db.query("sql", "SELECT FROM User WHERE name = Alice").to_list()  # []
```

**Cause:** The unquoted `Alice` is read as a property name, not a string, so the query
compares `name` with a property called `Alice` that no record has.

**Solution:**

Use a parameter (recommended):

```python
db.query("sql", "SELECT FROM User WHERE name = :name", {"name": "Alice"})
```

Or quote the string in SQL:

```python
db.query("sql", "SELECT FROM User WHERE name = 'Alice'")
```

---

### Type Conversion Error

**Symptom:**
```python
vertex.set("embedding", numpy_array)
# TypeError: only integer scalar arrays can be converted to a scalar index
```

The message comes from NumPy (here NumPy 2.5 with JPype 1.7.1) and varies with the versions.

**Cause:** `Document.set()` does not convert a NumPy array. A bound query parameter does.

**Solution:**

Use conversion utilities:

```python
from arcadedb_embedded import to_java_float_array
import numpy as np

embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
vertex.set("embedding", to_java_float_array(embedding))
```

## Performance Issues

### Slow Queries

**Symptom:**
Queries take seconds or minutes.

**Diagnosis:**

Use EXPLAIN to analyze:

```python
result = db.query("sql", "EXPLAIN SELECT FROM User WHERE email = 'alice@example.com'")
for row in result:
    print(row.to_dict())
```

**Solutions:**

1. **Create indexes:**
```python
db.command("sql", "CREATE INDEX ON User (email) UNIQUE_HASH")
```

2. **Use LIMIT:**
```python
# Bad: Load everything
result = db.query("sql", "SELECT FROM User")

# Good: Limit results
result = db.query("sql", "SELECT FROM User LIMIT 100")
```

3. **Project only needed fields:**
```python
# Bad: Load all properties
result = db.query("sql", "SELECT FROM User")

# Good: Only needed fields
result = db.query("sql", "SELECT name, email FROM User")
```

---

### Slow Imports

**Symptom:**
Importing data is very slow.

**Solutions:**

1. **Use the bulk paths.** `db.insert_many(...)` for rows, `db.insert_columns(...)` for
   column data, and `GraphBatch` for vertices and edges cross the Java boundary once per
   batch instead of once per record. A loop of `db.command("sql", "INSERT ...")` calls, even
   inside one large transaction, pays that cost on every row. See
   [Data Import](../guide/import.md#bulk-ingest-recommendation).

2. **For `IMPORT DATABASE`, raise `commitEvery`** and consider dropping heavy indexes during
   the load; see [Performance Guidance](../guide/import.md#performance-guidance).

---

### High Memory Usage

**Symptom:**
Process memory grows continuously.

**Diagnosis:**

Monitor memory:

```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**Solutions:**

1. **Stream large ResultSets:**
```python
# Bad: Load all results
result = db.query("sql", "SELECT FROM LargeTable")
all_results = list(result)  # Loads everything!

# Good: Process streaming
result = db.query("sql", "SELECT FROM LargeTable")
for row in result:
    process(row)
```

2. **Close ResultSets you stop reading early:**
```python
with db.query("sql", "SELECT FROM User") as result:
    for row in result:
        if some_condition(row):
            break
# Closed by the with block
```

Exhausting a result set, or reading it with `first()`, `one()`, or `to_list()`, closes
it for you. After a `break` it is not exhausted: without the `with` block (or an
explicit `result.close()`), it stays open while `result` is still referenced, and
since 26.10.1's parallel scan an open result set can hold engine threads that later
queries need.

3. **Force garbage collection:**
```python
import gc

for batch in large_dataset:
    process_batch(batch)
    gc.collect()  # Trigger GC
```

4. **Smaller transactions:**
```python
# Bad: Huge transaction
with db.transaction():
    for i in range(1000000):
        db.command("sql", "INSERT INTO Data SET id = ?", i)

# Good: Batch transactions
batch_size = 10000
for i in range(0, 1000000, batch_size):
    with db.transaction():
        for j in range(batch_size):
            db.command("sql", "INSERT INTO Data SET id = ?", i + j)
```

## Server Mode Issues

### Server Won't Start

**Symptom:**
```python
server = arcadedb.create_server("./databases", root_password="change-me")
server.start()
# ArcadeDBError: Failed to start server: ...
```

**Solutions:**

1. **Check port availability:**
```bash
lsof -i :2480
```

Use different port:

```python
server = arcadedb.create_server(
    root_path="./databases",
    root_password="change-me",
    config={"http_port": 8080},  # Different port
)
```

Always pass a `root_password` (8 or more characters): on the first start without one,
the server stops and asks for a root password on standard input.

2. **Check permissions:**
```bash
ls -la ./databases
# Ensure write permissions
chmod -R 755 ./databases
```

3. **Check logs:** the engine does not log through Python's `logging`. It writes
   `./log/arcadedb.log.*` relative to the working directory, server events go to
   `<root_path>/log/server-event-log-*.jsonl`, and a JVM crash leaves
   `./log/hs_err_pid*.log` (or the path in `ARCADEDB_JVM_ERROR_FILE`).

---

### Can't Connect to Server

**Symptom:**
Server running but can't connect via HTTP.

**Solutions:**

1. **Verify server is running:**
```python
if server.is_started():
    print("Server is running")
    print(f"URL: http://localhost:{server.get_http_port()}")
```

2. **Check firewall:**
```bash
# Linux
sudo ufw allow 2480

# macOS
# System Preferences > Security & Privacy > Firewall
```

3. **Test with curl:**
```bash
# No credentials needed
curl http://localhost:2480/api/v1/ready

# Most other endpoints need them
curl -u root:change-me http://localhost:2480/api/v1/server
```

## Vector Search Issues

### Vector Dimension Mismatch

**Symptom:**
```python
vertex.save()
# java.lang.IllegalArgumentException: Vector dimension does not match index dimension 384: got float[] of length 768
```

The error reaches Python as the Java exception, not as `ArcadeDBError`.

**Cause:**
Embedding dimension doesn't match index dimension.

**Solution:**

Verify dimensions match:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

# Check model dimension
test_embedding = model.encode("test")
print(f"Model dimension: {len(test_embedding)}")  # 384

# Create index with matching dimension
db.command(
    "sql",
    'CREATE INDEX ON Document (embedding) LSM_VECTOR METADATA {"dimensions": 384}',
)
```

---

### Slow First Query

**Symptom:**
The first vector search query takes significantly longer than subsequent queries.

**Cause:**
Most apps should not see this with current defaults, because SQL `CREATE INDEX ...
LSM_VECTOR` eagerly prepares the graph unless you explicitly disable it. A slow first
query typically means you created the SQL index with `"buildGraphNow": false`, so graph
preparation is deferred.

**Solution:**
If you want predictable first-query latency, either keep the default eager behavior or
explicitly rebuild before serving traffic. This is also useful after bulk vector inserts
or removals/deletes when you want to force rebuild at a controlled time.

```python
# Preferred: eager at creation (default)
db.command(
    "sql",
    'CREATE INDEX ON Document (embedding) LSM_VECTOR METADATA {"dimensions": 384}',
)
```

---

### Poor Search Results

**Symptom:**
Vector search returns irrelevant results.

**Solutions:**

1. **Try different distance function:**
```python
# Cosine (default, usually best for text)
db.command(
    "sql",
    '''
    CREATE INDEX ON Doc (embedding)
    LSM_VECTOR
    METADATA {
        "dimensions": 384,
        "similarity": "COSINE"
    }
    ''',
)

# Euclidean (sometimes better for images)
db.command(
    "sql",
    '''
    CREATE INDEX ON Image (features)
    LSM_VECTOR
    METADATA {
        "dimensions": 512,
        "similarity": "EUCLIDEAN"
    }
    ''',
)
```

2. **Tune vector parameters:**

The defaults are `maxConnections` 32 and `beamWidth` 100. Raising `beamWidth` can
improve recall at the cost of build time:

```python
# Better recall, slower build
db.command(
    "sql",
    '''
    CREATE INDEX ON Doc (embedding)
    LSM_VECTOR
    METADATA {
        "dimensions": 384,
        "similarity": "COSINE",
        "beamWidth": 200
    }
    ''',
)
```

## Debugging

### Enable Logging

**Python logging:**
```python
import logging

# Basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# File logging
logging.basicConfig(
    level=logging.DEBUG,
    filename='arcadedb.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

import arcadedb_embedded as arcadedb
# Python logging carries only the bindings' own records: DEBUG lines for
# exceptions swallowed during cleanup, and a WARNING when a bridge class is missing
```

**Engine and server logs:** the engine writes `./log/arcadedb.log.*` relative to the
working directory, server events go to `<root_path>/log/server-event-log-*.jsonl`,
and a JVM crash leaves `./log/hs_err_pid*.log` (or the path in
`ARCADEDB_JVM_ERROR_FILE`).

**Java logging:**

Pass the option before the first database or server is created (the bindings start
the JVM themselves):

```python
from arcadedb_embedded.jvm import start_jvm

start_jvm(jvm_args="-Djava.util.logging.config.file=logging.properties")
```

logging.properties:

```properties
.level=INFO
handlers=java.util.logging.ConsoleHandler
java.util.logging.ConsoleHandler.level=ALL
com.arcadedb.level=FINE
```

---

### Inspect Java Objects

```python
# Get Java class name
java_obj = vertex._java_document  # the wrapped Java record (Vertex subclasses Document)
print(java_obj.getClass().getName())

# List methods
for method in java_obj.getClass().getMethods():
    print(method.getName())

# Get property value (raw Java)
value = java_obj.get("property_name")
print(f"Type: {type(value)}, Value: {value}")
```

---

### Transaction Debugging

```python
class DebugTransaction:
    """Debug wrapper for transactions."""

    def __init__(self, db):
        self.db = db
        self.transaction = None

    def __enter__(self):
        print("Starting transaction")
        self.transaction = self.db.transaction()
        return self.transaction.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"Transaction failed: {exc_type.__name__}: {exc_val}")
        else:
            print("Transaction committed")
        return self.transaction.__exit__(exc_type, exc_val, exc_tb)

# Usage
with DebugTransaction(db):
    db.command("sql", "INSERT INTO User SET name = ?", "Alice")
```

---

### Query Debugging

```python
def debug_query(db, language, query, *args):
    """Execute query with debugging."""
    print(f"Query: {query}")
    if args:
        print(f"Params: {args}")

    try:
        result = db.query(language, query, *args)
        rows = list(result)
        print(f"Results: {len(rows)} rows")
        return rows
    except Exception as e:
        print(f"Error: {e}")
        raise

# Usage
results = debug_query(db, "sql", "SELECT FROM User WHERE name = :name", {"name": "Alice"})
```

## Common Error Messages

### "Type with name '...' was not found"

**Meaning:** The vertex, edge, or document type does not exist. It arrives as an
`ArcadeDBError` wrapping a `SchemaException`.

**Solution:**
```python
# Create the type if it is missing, then insert
db.command("sql", "CREATE VERTEX TYPE User IF NOT EXISTS")

with db.transaction():
    db.command("sql", "INSERT INTO User SET name = ?", "Alice")
```

---

### "Index '...' already exists"

**Meaning:** The index was created before.

**Solution:**
```python
# A no-op when the index exists. Dropping and recreating it rebuilds it.
db.command("sql", "CREATE INDEX IF NOT EXISTS ON User (email) UNIQUE_HASH")
```

---

### "Duplicated key ... found on index"

**Meaning:** A unique index already holds that value. The engine raises
`DuplicatedKeyException` when the transaction commits, and the bindings raise it as
`ArcadeDBError: Failed to commit transaction: ...`, so the whole transaction is rolled back.

**Solution:**
```python
# Update the existing record, or insert it if there is none, in one statement
with db.transaction():
    db.command(
        "sql",
        "UPDATE User SET name = ?, email = ? UPSERT WHERE email = ?",
        "Alice",
        "alice@example.com",
        "alice@example.com",
    )
```

A missing property is not an error: `Result.get("name")` returns `None` and
`Result.has_property("name")` returns `False`.

## Getting Help

1. **Check Documentation:**
    - [API Reference](../api/database.md)
    - [Guides](../guide/import.md)
    - [Examples](../examples/index.md)

2. **Search Issues:**
    - [GitHub Issues](https://github.com/humemai/arcadedb-embedded-python/issues)
    - [ArcadeDB Documentation](https://docs.arcadedb.com/)

3. **Report Bug:**
    Include:

    - Python version (`python --version`)
    - Package version and engine hash
      (`python -c "import arcadedb_embedded as a; print(a.__version__, a.jar_fingerprint()['engine_sha256'])"`)
    - Minimal reproducible example
    - Full error message with stack trace
    - Operating system

## See Also

- [Architecture](architecture.md) - System architecture and design
- [Database API](../api/database.md) - Core database operations
- [Exceptions API](../api/exceptions.md) - Error handling reference
