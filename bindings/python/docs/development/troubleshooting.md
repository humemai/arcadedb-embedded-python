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
uv run python -c "import arcadedb_embedded as a; fp = a.jar_fingerprint(); print(a.__version__, fp['engine_sha256'], fp['build_number'])"
```

---

## Runtime Errors

### Database Connection Issues

**Problem**: Can't connect to database

**Solutions**:

1. **Check Database Path**:
    ```python
    import os
    db_path = "databases/mydb"
    print(f"Exists: {os.path.exists(db_path)}")
    ```

2. **Verify Database Created**:
    ```python
    import arcadedb_embedded as arcadedb

    # Create if not exists
    if not os.path.exists(db_path):
        db = arcadedb.create_database(db_path)
    else:
        db = arcadedb.open_database(db_path)
    ```

3. **Check Permissions**:
    ```bash
    ls -la databases/
    chmod -R 755 databases/
    ```
---

### Database Already Exists

**Symptom:**
```python
arcadedb.create_database("./mydb")
# ArcadeDBError: Database already exists
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
   (see [Server Patterns](testing/test-server-patterns.md)).

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

2. **Pass NumPy Arrays Directly as Parameters**: a NumPy array passed as a bound
    parameter is converted to a Java `float[]` automatically. Only `Document.set()`
    needs an explicit `to_java_float_array()` (see
    [Type Conversion Error](#type-conversion-error)).
    ```python
    import numpy as np

    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO EmbeddingDoc SET embedding = ?",
            arr,
        )
    ```
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

### Query Syntax Error

**Symptom:**
```python
db.query("sql", "SELECT * FROM User WHERE name = Alice")
# ArcadeDBError: Query failed: ...
```

**Cause:** String not properly quoted.

**Solution:**

Use parameters (RECOMMENDED):

```python
db.query("sql",
    "SELECT FROM User WHERE name = :name",
    {"name": "Alice"}
)
```

Or quote strings in SQL:

```python
db.query("sql", "SELECT FROM User WHERE name = 'Alice'")
#                                              ↑    ↑ quotes
```

---

### Function Name Errors

**Problem**: SQL function not recognized

SQL function names are case-insensitive (`SYSDATE()` and `sysdate()` are the same
function), so case is not the cause. Check the spelling, and that the function exists
in the bundled engine.

**Solutions**:

1. **Use Built-in Functions**:
    ```python
    # Date/time
    with db.transaction():
        db.command("sql", "INSERT INTO Event SET timestamp = sysdate()")

    # UUID
    with db.transaction():
        db.command("sql", "INSERT INTO User SET id = uuid()")
    ```

---

### Multi-line Query Issues

**Problem**: SQL parser errors with complex queries

**Solution**: Use single-line queries or proper escaping:

```python
# ✅ Single line (wrap in a transaction when executing)
query = "INSERT INTO Product SET name = 'test', created_at = sysdate()"

# ✅ Multi-line with proper formatting
query = """
INSERT INTO Product SET
    name = 'test',
    created_at = sysdate()
""".strip()
```

---

### Type Conversion Error

**Symptom:**
```python
vertex.set("embedding", numpy_array)
# TypeError: Cannot convert numpy.ndarray to Java type
```

**Cause:** NumPy arrays need explicit conversion.

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
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
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

1. **Increase batch size (`commitEvery`):**
```python
db.command(
    "sql",
    "IMPORT DATABASE file:///data/users.csv WITH documentType = 'User', commitEvery = 10000",
)
```

2. **Drop indexes during import:**
```python
# Drop indexes
db.command("sql", "DROP INDEX `User[email]`")

# Import data
db.command(
    "sql",
    "IMPORT DATABASE file:///data/users.csv WITH documentType = 'User'",
)

# Recreate indexes
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
```

3. **Use transactions efficiently:**
```python
# Bad: Many small transactions
for record in records:
    with db.transaction():
        db.command("sql", "INSERT INTO Data SET data = ?", record)

# Good: Batch in larger transactions
batch_size = 10000
for i in range(0, len(records), batch_size):
    with db.transaction():
        for record in records[i:i+batch_size]:
            db.command("sql", "INSERT INTO Data SET data = ?", record)
```

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
# ArcadeDBError: Vector dimension mismatch
```

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

3. **Improve embeddings:**
```python
# Combine title and content
text = f"{doc['title']}. {doc['content']}"
embedding = model.encode(text)

# vs. just content
embedding = model.encode(doc['content'])  # May be less effective
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

### "Property not found"

**Meaning:** Trying to get property that doesn't exist.

**Solution:**
```python
# Check if property exists
row = db.query("sql", "SELECT name FROM User LIMIT 1").first()
if row.has_property("name"):
    name = row.get("name")
else:
    name = "Unknown"

# Or use default
name = row.get("name") or "Unknown"
```

---

### "Type not found"

**Meaning:** Vertex/Edge type doesn't exist.

**Solution:**
```python
# Create type first
result = db.query("sql", "SELECT FROM schema:types WHERE name = 'User'")
if result.first() is None:
    db.command("sql", "CREATE VERTEX TYPE User")

# Then insert data
with db.transaction():
    db.command("sql", "INSERT INTO User SET name = ?", "Alice")
```

---

### "Index already exists"

**Meaning:** Trying to create duplicate index.

**Solution:**
```python
# Drop existing index
try:
    db.command("sql", "DROP INDEX `User[email]`")
except Exception:
    pass  # Index doesn't exist

# Create new index
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
```

---

### "Unique constraint violation"

**Meaning:** Trying to insert duplicate value for unique property.

**Solution:**
```python
# Check if exists first
result = db.query("sql", "SELECT FROM User WHERE email = :email", {"email": "alice@example.com"})

if result.first() is not None:
    with db.transaction():
        db.command(
            "sql",
            "UPDATE User SET name = ? WHERE email = ?",
            "Alice",
            "alice@example.com",
        )
else:
    # Create new
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO User SET email = ?, name = ?",
            "alice@example.com",
            "Alice",
        )
```

## Getting Help

1. **Check Documentation:**
    - [API Reference](../api/database.md)
    - [Guides](../guide/import.md)
    - [Examples](../examples/import.md)

2. **Search Issues:**
    - [GitHub Issues](https://github.com/humemai/arcadedb-embedded-python/issues)
    - [ArcadeDB Documentation](https://docs.arcadedb.com/)

3. **Report Bug:**
    Include:

    - Python version (`python --version`)
    - Package version, engine hash, and engine build
      (`python -c "import arcadedb_embedded as a; fp = a.jar_fingerprint(); print(a.__version__, fp['engine_sha256'], fp['build_number'])"`)
    - Minimal reproducible example
    - Full error message with stack trace
    - Operating system

## See Also

- [Architecture](architecture.md) - System architecture and design
- [Database API](../api/database.md) - Core database operations
- [Exceptions API](../api/exceptions.md) - Error handling reference
