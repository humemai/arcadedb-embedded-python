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

db = arcadedb.create_database("/tmp/mydb")
try:
    # Use database
    db.command("sql", "CREATE DOCUMENT TYPE Person")
finally:
    db.close()
```

!!! tip "Use Context Manager"
    Prefer using `with` statement for automatic cleanup:
    ```python
    with arcadedb.create_database("/tmp/mydb") as db:
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
with arcadedb.open_database("/tmp/mydb") as db:
    result = db.query("sql", "SELECT FROM Person")
    print(f"Found {len(result)} records")
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
if arcadedb.database_exists("/tmp/mydb"):
    db = arcadedb.open_database("/tmp/mydb")
else:
    db = arcadedb.create_database("/tmp/mydb")
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
    print(record.get_property('name'))

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
# Must be in a transaction
with db.transaction():
    # Create type
    db.command("sql", "CREATE DOCUMENT TYPE Person")

    # Insert data
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)

    # Update data
    db.command("sql", "UPDATE Person SET age = 31 WHERE name = 'Alice'")

    # Delete data
    db.command("sql", "DELETE FROM Person WHERE name = 'Alice'")
```

!!! warning "Transaction Required"
    Write operations must be wrapped in a transaction:
    ```python
    # ✅ Correct
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice'")

    # ❌ Will fail
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
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
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET name = 'Bob'")
    # Automatic commit on success, rollback on exception
```

**Manual Transaction Control:**

```python
# Alternative: manual control
db.begin()
try:
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET name = 'Bob'")
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

    print(f"Created: {vertex.getIdentity()}")
```

!!! info "Creating Edges"
    There is no `db.new_edge()` method. Edges are created **from vertices**:
    ```python
    edge = vertex1.newEdge("Knows", vertex2)
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

### create_vector_index

```python
db.create_vector_index(
    vertex_type: str,
    vector_property: str,
    dimensions: int,
    distance_function: str = "cosine",
    max_connections: int = 32,
    beam_width: int = 256,
    quantization: str = None
) -> VectorIndex
```

Create a vector index for similarity search (default JVector implementation).

**Note:** The index is built lazily. Construction happens upon the first query, not at creation time.

**Parameters:**

- `vertex_type` (str): Vertex type containing vectors
- `vector_property` (str): Property storing vector arrays
- `dimensions` (int): Vector dimensionality
- `distance_function` (str): `"cosine"`, `"euclidean"`, or `"inner_product"`
- `max_connections` (int): Max connections per node (default: 32). Maps to `maxConnections` in JVector.
- `beam_width` (int): Beam width for search/construction (default: 256). Maps to `beamWidth` in JVector.
- `quantization` (str): Vector quantization type (default: None). Options: `"INT8"`, `"BINARY"`. Reduces memory usage and speeds up search at the cost of some precision.

**Returns:**

- `VectorIndex`: Index object for similarity search

**Example:**

```python
import numpy as np

# Create schema
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE Document")
    db.command("sql", "CREATE PROPERTY Document.embedding ARRAY_OF_FLOATS")
    db.command("sql", "CREATE PROPERTY Document.id STRING")

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
db = arcadedb.create_database("/tmp/mydb")
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
factory = arcadedb.DatabaseFactory("/tmp/mydb")
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
with arcadedb.create_database("/tmp/mydb") as db:
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

### MongoDB

MongoDB query syntax:

```python
db.query("mongo", """{
    find: 'Person',
    filter: { age: { $gt: 25 } }
}""")
```

---

## Error Handling

All database operations can raise `ArcadeDBError`:

```python
from arcadedb_embedded import ArcadeDBError

try:
    with arcadedb.create_database("/tmp/mydb") as db:
        db.command("sql", "INVALID SQL")
except ArcadeDBError as e:
    print(f"Error: {e}")
```

---

## Best Practices

### 1. Use Context Managers

```python
# ✅ Good - automatic cleanup
with arcadedb.create_database("/tmp/mydb") as db:
    pass

# ❌ Avoid - manual cleanup
db = arcadedb.create_database("/tmp/mydb")
db.close()
```

### 2. Always Use Transactions for Writes

```python
# ✅ Good
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")

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
if arcadedb.database_exists("/tmp/mydb"):
    db = arcadedb.open_database("/tmp/mydb")
else:
    db = arcadedb.create_database("/tmp/mydb")
```

---

## See Also

- [Graph Operations](../guide/graphs.md): Working with vertices and edges
- [Vector Search](../guide/vectors.md): Similarity search with JVector indexes
- [Server Mode](../guide/server.md): HTTP API and Studio UI
- [Quick Start](../getting-started/quickstart.md): Getting started guide
