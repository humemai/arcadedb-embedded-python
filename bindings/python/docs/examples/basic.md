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

with arcadedb.create_database("./mydb") as db:
    # Create document type (schema ops are auto-transactional)
    db.command("sql", "CREATE DOCUMENT TYPE Product")
    db.command("sql", "CREATE PROPERTY Product.name STRING")
    db.command("sql", "CREATE PROPERTY Product.price DOUBLE")
    db.command("sql", "CREATE PROPERTY Product.inStock BOOLEAN")

    # Insert document
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO Product SET name = 'Laptop', price = 999.99, inStock = true",
        )

    # Query documents (reads don't need transaction)
    results = db.query("sql", "SELECT FROM Product WHERE price < 1000")
    for record in results:
        print(record.get("name"), record.get("price"))
```

### Basic Graph Operations

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    # Create graph schema (schema ops are auto-transactional)
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")
    db.command("sql", "CREATE PROPERTY Person.name STRING")

    # Create vertices and edges
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice'")
        db.command("sql", "INSERT INTO Person SET name = 'Bob'")
        db.command(
            "sql",
            """
            CREATE EDGE Knows
            FROM (SELECT FROM Person WHERE name = 'Alice')
            TO (SELECT FROM Person WHERE name = 'Bob')
            """,
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

Browse all examples:

- **[Examples Overview](index.md)** - Complete list of examples
- **[Dataset Downloader](download_data.md)** - Download and prepare example datasets
- **[01 - Simple Document Store](01_simple_document_store.md)** - Document database basics
- **[02 - Social Network Graph](02_social_network_graph.md)** - Graph database basics
- **[03 - Vector Search](03_vector_search.md)** - AI-powered semantic search
- **[04 - CSV Import (Tables)](04_csv_import_documents.md)** - Import tabular data
- **[05 - CSV Import (Graph)](05_csv_import_graph.md)** - Import graph data
- **[06 - Vector Search (Movies)](06_vector_search_recommendations.md)** - Movie recommendations

## Source Code

All example source code is available in the [`examples/`]({{ config.repo_url }}/tree/{{ config.extra.version_tag }}/bindings/python/examples) directory of the repository.

## Additional Resources

- **[Quick Start Guide](../getting-started/quickstart.md)** - Installation and setup
- **[API Reference](../api/database.md)** - Complete API documentation
- **[User Guide](../guide/core/database.md)** - In-depth guides
