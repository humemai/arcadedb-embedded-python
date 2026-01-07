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
- Use Gremlin queries for high-performance graph traversal
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
    db.schema.create_document_type("Product")

    # Insert document
    with db.transaction():
        product = db.new_document("Product")
        product.set("name", "Laptop").set("price", 999.99).set("inStock", True)
        product.save()

    # Query documents (reads don't need transaction)
    results = db.query("sql", "SELECT FROM Product WHERE price < 1000")
    for record in results:
        print(record.get("name"), record.get("price"))
```

### Basic Graph Operations

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    # Create vertex types (schema ops are auto-transactional)
    db.schema.create_vertex_type("Person")
    db.schema.create_edge_type("Knows")

    # Create vertices and edges
    with db.transaction():
        alice = db.new_vertex("Person")
        alice.set("name", "Alice").save()

        bob = db.new_vertex("Person")
        bob.set("name", "Bob").save()

        edge = alice.new_edge("Knows", bob)
        edge.save()

    # Traverse graph (reads don't need transaction)
    results = db.query("gremlin", """
        g.V().hasLabel('Person')
         .out('Knows')
         .values('name')
    """)

    for record in results:
        print(record)
```

## More Examples

Browse all examples:

- **[Examples Overview](index.md)** - Complete list of examples
- **[01 - Simple Document Store](01_simple_document_store.md)** - Document database basics
- **[02 - Social Network Graph](02_social_network_graph.md)** - Graph database basics
- **[03 - Vector Search](03_vector_search.md)** - AI-powered semantic search
- **[04 - CSV Import (Tables)](04_csv_import_documents.md)** - Import tabular data
- **[05 - CSV Import (Graph)](05_csv_import_graph.md)** - Import graph data
- **[06 - Vector Search (Movies)](06_vector_search_recommendations.md)** - Movie recommendations
- **[07 - StackOverflow (Multi-Model)](07_stackoverflow_multimodel.md)** - Multi-model database
- **[08 - Server Mode](08_server_mode_rest_api.md)** - HTTP server & Studio UI

## Source Code

All example source code is available in the [`examples/`](https://github.com/humemai/arcadedb-embedded-python/tree/main/bindings/python/examples) directory of the repository.

## Additional Resources

- **[Quick Start Guide](../getting-started/quickstart.md)** - Installation and setup
- **[API Reference](../api/database.md)** - Complete API documentation
- **[User Guide](../guide/core/database.md)** - In-depth guides
