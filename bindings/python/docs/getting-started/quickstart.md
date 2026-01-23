# Quick Start

Get up and running with ArcadeDB Python bindings in 5 minutes!

## Installation

Install the self-contained package with bundled JRE:

```bash
uv pip install arcadedb-embedded
```

!!! note "No Java Installation Required"
    The package includes a bundled platform-specific JRE. You don't need to install Java separately!

## Access Methods

ArcadeDB Python bindings support **two access methods**:

### Java API (Embedded Mode) - Recommended for Getting Started

Direct JVM method calls via JPype, using the Pythonic embedded API:

```python
import arcadedb_embedded as arcadedb

# Direct database access (embedded API)
with arcadedb.create_database("./mydb") as db:
    # Schema (auto-transactional)
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")

    # Insert (requires explicit transaction)
    with db.transaction():
        doc = db.new_document("Person")
        doc.set("name", "Alice")
        doc.save()

    # Query (No transaction needed. SQL is still fine for reads)
    result = db.query("sql", "SELECT FROM Person")
    for record in result:
        print(record.get("name"))
```

### HTTP API (Server Mode) - For Remote Access

REST requests when server is running - enables remote access:

```python
import arcadedb_embedded as arcadedb
import requests
from requests.auth import HTTPBasicAuth

# Start server with Java API
server = arcadedb.create_server("./server", "password123")
server.start()

auth = HTTPBasicAuth("root", "password123")

# Create database via HTTP
requests.post(
    f"http://localhost:{server.get_http_port()}/api/v1/server",
    auth=auth,
    json={"command": "create database mydb"}
)

# Create schema
requests.post(
    f"http://localhost:{server.get_http_port()}/api/v1/command/mydb",
    auth=auth,
    json={"language": "sql", "command": "CREATE DOCUMENT TYPE Person"}
)

# Insert data
requests.post(
    f"http://localhost:{server.get_http_port()}/api/v1/command/mydb",
    auth=auth,
    json={"language": "sql", "command": "INSERT INTO Person SET name = 'Alice'"}
)

# Query data
response = requests.post(
    f"http://localhost:{server.get_http_port()}/api/v1/command/mydb",
    auth=auth,
    json={"language": "sql", "command": "SELECT FROM Person"}
)
result = response.json()
print(result)

server.stop()
```

!!! tip "Choose Your Method"
    - **Java API**: Use for single-process apps (fastest)
    - **HTTP API**: Use for multi-process/remote access
    - **Both**: Can be used simultaneously on same server!

## Your First Database

### 1. Create a Database

```python
import arcadedb_embedded as arcadedb

# Create database (context manager for automatic open and close)
with arcadedb.create_database("./quickstart") as db:
    print(f"Created database at: {db.get_database_path()}")
```

### 2. Create Schema

```python
with arcadedb.create_database("./quickstart") as db:
    # Schema operations are auto-transactional
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")
    print("Schema created!")
```

### 3. Insert Data

All writes must be in a transaction:

```python
with arcadedb.create_database("./quickstart") as db:
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")

    # Use transaction for writes
    with db.transaction():
        for name, age in [("Alice", 30), ("Bob", 25), ("Charlie", 35)]:
            doc = db.new_document("Person")
            doc.set("name", name)
            doc.set("age", age)
            doc.save()

    print("Inserted 3 records")
```

!!! tip "Transactions"
    Always use `with db.transaction():` for INSERT, UPDATE, DELETE operations.

### 4. Query Data

```python
with arcadedb.create_database("./quickstart") as db:
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")
    with db.transaction():
        for name, age in [("Alice", 30), ("Bob", 25)]:
            doc = db.new_document("Person")
            doc.set("name", name)
            doc.set("age", age)
            doc.save()

    # Query data
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")

    for record in result:
        name = record.get('name')
        age = record.get('age')
        print(f"Name: {name}, Age: {age}")
```

Output:
```
Name: Alice, Age: 30
```

## Complete Example

Here's a complete working example:

```python
import arcadedb_embedded as arcadedb

def main():
    # Create database
    with arcadedb.create_database("./quickstart") as db:
        # Create schema (pythonic API)
        db.schema.create_document_type("Person")
        db.schema.create_property("Person", "name", "STRING")
        db.schema.create_property("Person", "age", "INTEGER")
        db.schema.create_index("Person", ["name"], unique=False)

        # Insert data (in transaction)
        with db.transaction():
            for name, age, email in [
                ("Alice", 30, "alice@example.com"),
                ("Bob", 25, "bob@example.com"),
                ("Charlie", 35, "charlie@example.com"),
            ]:
                doc = db.new_document("Person")
                doc.set("name", name)
                doc.set("age", age)
                doc.set("email", email)
                doc.save()

        print("✅ Inserted 3 records")

        # Query all (No transaction needed. SQL still fine for reads)
        print("\n📋 All people:")
        result = db.query("sql", "SELECT FROM Person ORDER BY age")
        for record in result:
            print(f"  - {record.get('name')}, age {record.get('age')}")

        # Query with filter
        print("\n🔍 People over 25:")
        result = db.query("sql", "SELECT FROM Person WHERE age > 25 ORDER BY age")
        for record in result:
            print(f"  - {record.get('name')}, age {record.get('age')}")

        # Count
        result = db.query("sql", "SELECT count(*) as total FROM Person")
        total = result.first().get('total')
        print(f"\n📊 Total people: {total}")

if __name__ == "__main__":
    main()
```

Output:
```
✅ Inserted 3 records

📋 All people:
  - Bob, age 25
  - Alice, age 30
  - Charlie, age 35

🔍 People over 25:
  - Alice, age 30
  - Charlie, age 35

📊 Total people: 3
```

## Key Concepts

### Context Managers

Always use `with` statements for automatic cleanup:

```python
# ✅ Good - automatic cleanup
with arcadedb.create_database("./mydb") as db:
    # Use database
    pass
# Database automatically closed

# ❌ Avoid - manual cleanup required
db = arcadedb.create_database("./mydb")
# Use database
db.close()  # Easy to forget!
```

### Transactions

All writes require a transaction:

```python
# ✅ Good - in transaction
with db.transaction():
    doc = db.new_document("Person")
    doc.set("name", "Alice")
    doc.save()

# ❌ Will fail - no transaction
doc = db.new_document("Person")
doc.set("name", "Alice")
# doc.save() outside a transaction will raise
```

!!! info "Read-Only Operations"
    `db.query()` doesn't require a transaction - only `db.command()` for writes.

## Next Steps

Now that you've created your first database, explore more features:

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } [__Core Operations__](../guide/core/database.md)

    Learn about database management, queries, and transactions

-   :material-vector-triangle:{ .lg .middle } [__Vector Search__](../guide/vectors.md)

    Store and query embeddings with vector indexing

-   :material-graph:{ .lg .middle } [__Graph Operations__](../guide/graphs.md)

    Work with vertices, edges, and graph traversals

-   :material-upload:{ .lg .middle } [__Import Data__](../guide/import.md)

    Bulk import from CSV and ArcadeDB JSONL exports

</div>

## Common Patterns

### Working with Existing Database

```python
# Open existing database
with arcadedb.open_database("./quickstart") as db:
    result = db.query("sql", "SELECT FROM Person")
    print(f"Found {len(list(result))} records")
```

### Batch Inserts

```python
with db.transaction():
    for i in range(100):
        doc = db.new_document("Person")
        doc.set("name", f"User{i}")
        doc.set("age", 20 + i)
        doc.save()
```

### Error Handling

```python
try:
    with arcadedb.create_database("./mydb") as db:
        # Schema operations are auto-transactional
        db.schema.create_document_type("User")
        db.schema.create_property("User", "email", "STRING")
        db.schema.create_index("User", ["email"], unique=True)

        # Data operations require an explicit transaction
        with db.transaction():
            doc = db.new_document("User")
            doc.set("email", "alice@example.com").save()

            # This will raise an exception due to unique constraint
            dup = db.new_document("User")
            dup.set("email", "alice@example.com").save()
except Exception as e:
    print(f"Database error: {e}")
```

## Need Help?

- **Examples**: Check [Examples](../examples/basic.md) for more code samples
- **API Reference**: See [Database API](../api/database.md) for all methods
- **Troubleshooting**: Visit [Troubleshooting Guide](../development/troubleshooting.md)
