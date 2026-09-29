# Basic Examples

This page provides quick links to basic ArcadeDB examples to get you started.

## Getting Started Examples

### Document Store

Start with the simplest use case - storing and querying documents:

**[Example 01 - Simple Document Store](01_simple_document_store.md)**

Learn how to:

- Create a database and document types
- Insert documents with various data types
- Query using SQL
- Handle NULL values

### Graph Database

Build your first graph database with vertices and edges:

**[Example 02 - Social Network Graph](02_social_network_graph.md)**

Learn how to:

- Create vertices and edges
- Use OpenCypher queries for graph traversal
- Traverse graph relationships efficiently
- Implement social network patterns

## Quick Start Code

### Opening a Database

```python
import arcadedb_embedded as arcadedb

# Create a new database with context manager (auto-closes)
with arcadedb.create_database("./mydb") as db:
    # Your operations here
    pass

# Or open existing database
with arcadedb.open_database("./mydb") as db:
    # Perform operations
    pass
```

### Basic Document Operations

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./products_db") as db:
    # Create document type (schema statements apply immediately)
    db.command("sql", "CREATE DOCUMENT TYPE Product")
    db.command("sql", "CREATE PROPERTY Product.name STRING")
    db.command("sql", "CREATE PROPERTY Product.price DOUBLE")
    db.command("sql", "CREATE PROPERTY Product.inStock BOOLEAN")

    # Insert document
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO Product SET name = ?, price = ?, inStock = ?",
            "Laptop",
            999.99,
            True,
        )

    # Query documents (reads don't need transaction)
    results = db.query("sql", "SELECT FROM Product WHERE price < ?", 1000)
    for record in results:
        print(record.get("name"), record.get("price"))
```

### Basic Graph Operations

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./graph_db") as db:
    # Create graph schema (schema statements apply immediately)
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")
    db.command("sql", "CREATE PROPERTY Person.name STRING")

    # Create vertices and edges
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = ?", "Alice")
        db.command("sql", "INSERT INTO Person SET name = ?", "Bob")
        db.command(
            "sql",
            """
            CREATE EDGE Knows
            FROM (SELECT FROM Person WHERE name = ?)
            TO (SELECT FROM Person WHERE name = ?)
            """,
            "Alice",
            "Bob",
        )

    # Traverse graph (reads don't need transaction)
    results = db.query("opencypher", """
        MATCH (p:Person)-[:Knows]->(other:Person)
        RETURN other.name as name
        ORDER BY name
    """)

    for record in results:
        print(record.get("name"))
```

## More Examples

The [Examples Overview](index.md) lists all 26 examples, and the
[Dataset Downloader](download_data.md) prepares the datasets the larger ones use.

## Source Code

All example source code is available in the [`examples/`]({{ config.repo_url }}/tree/{{ config.extra.version_tag }}/bindings/python/examples) directory of the repository.

## Additional Resources

- **[Quick Start Guide](../getting-started/quickstart.md)** - Installation and setup
- **[API Reference](../api/database.md)** - Complete API documentation
- **[User Guide](../guide/core/database.md)** - In-depth guides
