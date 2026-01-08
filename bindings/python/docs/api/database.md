# Database API Reference

Complete API reference for working with ArcadeDB databases in Python.

## Module Functions

### create_database

```python
arcadedb.create_database(path: str) -> Database
```

Create a new database at the specified path.

**Parameters:**

- `path` (str): File system path where the database will be created

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If database creation fails or path already exists

**Example:**

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    # Schema operations are auto-transactional
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
```

!!! tip "Use Context Manager"
    Prefer using `with` statement for automatic cleanup:
    ```python
    with arcadedb.create_database("./mydb") as db:
        # Database automatically closed on exit
        pass
    ```

---

### open_database

```python
arcadedb.open_database(path: str) -> Database
```

Open an existing database.

**Parameters:**

- `path` (str): Path to the existing database

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If database doesn't exist or can't be opened

**Example:**

```python
with arcadedb.open_database("./mydb") as db:
    result = db.query("sql", "SELECT FROM Person")
    print(f"Found {len(list(result))} records")
```

---

### database_exists

```python
arcadedb.database_exists(path: str) -> bool
```

Check if a database exists at the given path.

**Parameters:**

- `path` (str): Path to check

**Returns:**

- `bool`: True if database exists, False otherwise

**Example:**

```python
if arcadedb.database_exists("./mydb"):
    db = arcadedb.open_database("./mydb")
else:
    db = arcadedb.create_database("./mydb")
```

---

## Database Class

The main database interface for executing queries, managing transactions, and creating records.

### Constructor

```python
Database(java_database)
```

**Parameters:**

- `java_database`: Java Database object (internal use - use factory functions instead)

!!! note "Direct Construction"
    Don't create `Database` instances directly. Use `create_database()`, `open_database()`, or `DatabaseFactory` instead.

---

### query

```python
db.query(language: str, command: str, *args) -> ResultSet
```

Execute a query and return results. Queries are read-only and don't require a transaction.

**Parameters:**

- `language` (str): Query language - `"sql"`, `"cypher"`, `"gremlin"`, `"mongo"`, `"graphql"`
- `command` (str): Query string
- `*args`: Optional parameters to bind to the query

**Returns:**

- `ResultSet`: Iterable result set

**Raises:**

- `ArcadeDBError`: If query fails or database is closed

**Example:**

```python
# Simple query
result = db.query("sql", "SELECT FROM Person WHERE age > 25")
for record in result:
    print(record.get('name'))

# Parameterized query
result = db.query("sql", "SELECT FROM Person WHERE age > ?", 25)

# Cypher query
result = db.query("cypher", """
    MATCH (p:Person)-[:Knows]->(friend)
    WHERE p.age > $min_age
    RETURN friend.name
""", {"min_age": 25})
```

**Supported Languages:**

| Language | Notes |
|----------|-------|
| `sql` | ArcadeDB SQL |
| `cypher` | OpenCypher graph query language |
| `mongo` | MongoDB query syntax |
| `gremlin` | Apache TinkerPop traversal |
| `graphql` | GraphQL queries |

---

### command

```python
db.command(language: str, command: str, *args) -> Optional[ResultSet]
```

Execute a command (write operation). Commands modify data and **require a transaction**.

**Parameters:**

- `language` (str): Command language (usually `"sql"` or `"cypher"`)
- `command` (str): Command string
- `*args`: Optional parameters

**Returns:**

- `ResultSet` or `None`: Result set if command returns data, None otherwise

**Raises:**

- `ArcadeDBError`: If command fails, database is closed, or no transaction is active

**Example:**

```python
# Schema operations are auto-transactional
db.schema.create_document_type("Person")
db.schema.create_property("Person", "name", "STRING")
db.schema.create_property("Person", "age", "INTEGER")

# Data operations must be in a transaction
with db.transaction():
    doc = db.new_document("Person")
    doc.set("name", "Alice")
    doc.set("age", 30)
    doc.save()

    # Update data via API
    doc.set("age", 31)
    doc.save()

    # Delete data
    doc.delete()
```

!!! warning "Transaction Required"
    Write operations must be wrapped in a transaction:
    ```python
    # ✅ Correct
    with db.transaction():
        doc = db.new_document("Person")
        doc.set("name", "Alice")
        doc.save()

    # ❌ Will fail
    doc = db.new_document("Person")
    doc.set("name", "Alice")
    # doc.save() outside a transaction will raise
    ```

---

### transaction

```python
db.transaction() -> TransactionContext
```

Create a transaction context manager.

**Returns:**

- `TransactionContext`: Context manager for transaction

**Example:**

```python
with db.transaction():
    for name in ["Alice", "Bob"]:
        doc = db.new_document("Person")
        doc.set("name", name)
        doc.save()
    # Automatic commit on success, rollback on exception
```

**Manual Transaction Control:**

```python
# Alternative: manual control
db.begin()
try:
    for name in ["Alice", "Bob"]:
        doc = db.new_document("Person")
        doc.set("name", name)
        doc.save()
    db.commit()
except Exception as e:
    db.rollback()
    raise
```

---

### begin

```python
db.begin()
```

Begin a new transaction. Prefer using `transaction()` context manager.

**Raises:**

- `ArcadeDBError`: If transaction cannot be started

---

### commit

```python
db.commit()
```

Commit the current transaction.

**Raises:**

- `ArcadeDBError`: If commit fails or no transaction is active

---

### rollback

```python
db.rollback()
```

Rollback the current transaction.

**Raises:**

- `ArcadeDBError`: If rollback fails

---

### new_vertex

```python
db.new_vertex(type_name: str) -> MutableVertex
```

Create a new vertex (graph node). **Requires a transaction.**

**Parameters:**

- `type_name` (str): Vertex type name (must be defined in schema)

**Returns:**

- `MutableVertex`: Java vertex object with `.set()`, `.save()` methods

**Raises:**

- `ArcadeDBError`: If type doesn't exist or transaction not active

**Example:**

```python
with db.transaction():
    vertex = db.new_vertex("Person")
    vertex.set("name", "Alice")
    vertex.set("age", 30)
    vertex.save()

    print(f"Created: {vertex.get_rid()}")
```

!!! info "Creating Edges"
    There is no `db.new_edge()` method. Edges are created **from vertices**:
    ```python
    edge = vertex1.new_edge("Knows", vertex2)
    edge.save()
    ```
    See [Graph Operations](../guide/graphs.md) for details.

---

### new_document

```python
db.new_document(type_name: str) -> MutableDocument
```

Create a new document (non-graph record). **Requires a transaction.**

**Parameters:**

- `type_name` (str): Document type name

**Returns:**

- `MutableDocument`: Java document object

**Example:**

```python
with db.transaction():
    doc = db.new_document("Person")
    doc.set("name", "Alice")
    doc.set("email", "alice@example.com")
    doc.save()
```

---

### lookup_by_rid

```python
db.lookup_by_rid(rid: str) -> Any
```

Lookup a record by its RID.

**Parameters:**

- `rid` (str): Record ID string (e.g. "#10:5")

**Returns:**

- `Record` object (Vertex, Document, or Edge) or `None` if not found

**Example:**

```python
record = db.lookup_by_rid("#10:5")
if record:
    print(record.get("name"))
```

---

### lookup_by_key

```python
db.lookup_by_key(type_name: str, keys: List[str], values: List[Any]) -> Optional[Record]
```

Lookup a record by an indexed key (O(1) index-based lookup).

**Parameters:**

- `type_name` (str): Type name
- `keys` (List[str]): Indexed property names
- `values` (List[Any]): Values for the indexed properties

**Returns:**

- `Record` (Vertex/Document/Edge) or `None` if not found

**Example:**

```python
db.schema.create_vertex_type("User")
db.schema.create_property("User", "email", "STRING")
db.schema.create_index("User", ["email"], unique=True)

with db.transaction():
    db.new_vertex("User").set("email", "alice@example.com").save()

found = db.lookup_by_key("User", ["email"], ["alice@example.com"])
if found:
    print(found.get("email"))
```

---

### count_type

```python
db.count_type(type_name: str) -> int
```

Count records of a specific type (polymorphic). Returns 0 if the type is missing.

---

### drop

```python
db.drop()
```

Drop the entire database (irreversible).

---

### is_transaction_active

```python
db.is_transaction_active() -> bool
```

Check if a transaction is currently active.

---

### set_wal_flush

```python
db.set_wal_flush(mode: str)
```

Configure WAL flush strategy. Modes: `"no"`, `"yes_nometadata"`, `"yes_full"`.

---

### set_read_your_writes

```python
db.set_read_your_writes(enabled: bool)
```

Toggle read-your-writes consistency for the current connection.

---

### set_auto_transaction

```python
db.set_auto_transaction(enabled: bool)
```

Enable or disable automatic transaction management.

---

### async_executor

```python
db.async_executor() -> AsyncExecutor
```

---

### batch_context

```python
db.batch_context(
    batch_size: int = 5000,
    parallel: int = 4,
    use_wal: bool = True,
    back_pressure: int = 50,
    progress: bool = False,
    progress_desc: str = "Processing",
)
```

Convenience context for bulk ingestion built on the async executor (auto-commit, back-pressure, optional progress).

**Example:**

```python
with db.batch_context(batch_size=5000, parallel=8, progress=True) as batch:
    batch.set_total(len(users))
    for user in users:
        batch.create_vertex("User", **user)
```

---

### export_database

```python
db.export_database(
    file_path: str,
    format: str = "jsonl",
    overwrite: bool = False,
    include_types: Optional[List[str]] = None,
    exclude_types: Optional[List[str]] = None,
    verbose: int = 1,
) -> dict
```

Export the database to JSONL (backup/restore), GraphML, or GraphSON.

---

### export_to_csv

```python
db.export_to_csv(query: str, file_path: str, language: str = "sql", fieldnames: Optional[List[str]] = None)
```

Run a query and write results to CSV.

---

### create_vector_index

```python
db.create_vector_index(
    vertex_type: str,
    vector_property: str,
    dimensions: int,
    distance_function: str = "cosine",
    max_connections: int = 32,
    beam_width: int = 256
) -> VectorIndex
```

Create a vector index for similarity search (JVector implementation). Existing records are indexed automatically when the index is created.

**Parameters:**`

- `vertex_type` (str): Vertex type containing vectors
- `vector_property` (str): Property storing vector arrays
- `dimensions` (int): Vector dimensionality
- `distance_function` (str): `"cosine"`, `"euclidean"`, or `"inner_product"`
- `max_connections` (int): Max connections per node (default: 32). Maps to `maxConnections` in HNSW (JVector).
- `beam_width` (int): Beam width for search/construction (default: 256). Maps to `beamWidth` in HNSW (JVector).

**Returns:**

- `VectorIndex`: Index object for similarity search

**Example:**

```python
import numpy as np

# Create schema (auto-transactional)
db.schema.create_vertex_type("Document")
db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")
db.schema.create_property("Document", "id", "STRING")

# Create vector index
index = db.create_vector_index("Document", "embedding", dimensions=384)

# Add vectors
with db.transaction():
    for i, embedding in enumerate(embeddings):
        vertex = db.new_vertex("Document")
        vertex.set("id", f"doc_{i}")
        vertex.set("embedding", arcadedb.to_java_float_array(embedding))
        vertex.save()

# Search
query_vector = np.random.rand(384)
results = index.find_nearest(query_vector, k=5)
```

See [Vector Search Guide](../guide/vectors.md) for details.

---

### close

```python
db.close()
```

Close the database connection.

**Example:**

```python
db = arcadedb.create_database("./mydb")
try:
    # Use database
    pass
finally:
    db.close()
```

!!! tip "Context Manager"
    Prefer using `with` statement for automatic cleanup

---

### is_open

```python
db.is_open() -> bool
```

Check if database connection is open.

**Returns:**

- `bool`: True if database is open

---

### get_name

```python
db.get_name() -> str
```

Get the database name.

**Returns:**

- `str`: Database name

---

### get_database_path

```python
db.get_database_path() -> str
```

Get the file system path to the database.

**Returns:**

- `str`: Database path

---

## DatabaseFactory Class

Factory for creating and opening databases with custom configuration.

### Constructor

```python
DatabaseFactory(path: str)
```

**Parameters:**

- `path` (str): Database path

**Example:**

```python
factory = arcadedb.DatabaseFactory("./mydb")
if factory.exists():
    db = factory.open()
else:
    db = factory.create()
```

---

### create

```python
factory.create() -> Database
```

Create a new database.

---

### open

```python
factory.open() -> Database
```

Open an existing database.

---

### exists

```python
factory.exists() -> bool
```

Check if database exists.

---

## Context Manager Support

All database objects support context managers:

```python
# Database
with arcadedb.create_database("./mydb") as db:
    # Automatic cleanup
    pass

# Transaction
with db.transaction():
    # Auto commit/rollback
    pass
```

---

## Query Languages

### SQL

ArcadeDB's extended SQL with graph and document support:

```python
# Documents
db.query("sql", "SELECT FROM Person WHERE age > 25")

# Graph traversal
db.query("sql", "SELECT expand(out('Knows')) FROM Person WHERE name = 'Alice'")

# Aggregation
db.query("sql", "SELECT count(*) as total, avg(age) as avg_age FROM Person")
```

### Cypher

OpenCypher graph query language:

```python
db.query("cypher", """
    MATCH (person:Person)-[:Knows]->(friend)
    WHERE person.age > 25
    RETURN friend.name, friend.age
""")
```

### Gremlin

Apache TinkerPop graph traversals:

```python
db.query("gremlin", """
    g.V().has('Person', 'name', 'Alice')
        .out('Knows')
        .values('name')
""")
```

---

## Best Practices

### 1. Use Context Managers

```python
# ✅ Good - automatic cleanup
with arcadedb.create_database("./mydb") as db:
    pass

# ❌ Avoid - manual cleanup
db = arcadedb.create_database("./mydb")
db.close()
```

### 2. Always Use Transactions for Writes

```python
# ✅ Good
with db.transaction():
    person = db.new_document("Person")
    person.set("name", "Alice").save()

# ❌ Will fail
db.command("sql", "INSERT INTO Person SET name = 'Alice'")
```

### 3. Use Parameterized Queries

```python
# ✅ Good - safe from injection
name = user_input
db.query("sql", "SELECT FROM Person WHERE name = ?", name)

# ❌ Dangerous - SQL injection risk
db.query("sql", f"SELECT FROM Person WHERE name = '{user_input}'")
```

### 4. Check Database Existence

```python
if arcadedb.database_exists("./mydb"):
    db = arcadedb.open_database("./mydb")
else:
    db = arcadedb.create_database("./mydb")
```

---

## See Also

- [Graph Operations](../guide/graphs.md): Working with vertices and edges
- [Vector Search](../guide/vectors.md): Similarity search with HNSW (JVector) indexes
- [Server Mode](../guide/server.md): HTTP API and Studio UI
- [Quick Start](../getting-started/quickstart.md): Getting started guide
