# Core Database Tests

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_core.py){ .md-button }

These notes mirror the Python tests in [test_core.py](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_core.py). There are **15 tests** covering fundamental database operations.

## Overview

Tests validate:

- Database creation/opening and context managers
- CRUD operations (Create, Read, Update, Delete)
- Transaction management and ACID behavior
- Graph operations (vertex/edge creation and traversal)
- Query result handling and iteration
- Error handling
- OpenCypher queries (when available)
- Vector search with HNSW indexes
- Unicode/international character support
- Schema introspection and metadata
- Large result sets (1000+ records)
- Type conversions (Python ↔ Java)

## Test Cases

### Database Management

- **database_creation**: Creates new database via `arcadedb.create_database()`, verifies initialization and cleanup
- **database_open**: Opens existing database via `arcadedb.open_database()`, tests persistence and multiple cycles
- **context_manager**: Tests `with` statement for automatic resource cleanup, exception handling

### CRUD Operations

- **crud_operations**: Tests Create (insert), Read (query), Update (modify), Delete operations; validates transaction boundaries
- **transactions**: Tests ACID behavior, automatic commit on success, automatic rollback on exception

### Graph Operations

- **graph_operations**: Tests vertex/edge type creation, vertex creation, edge linking with properties, graph traversal queries
- **graph_traversal**: Tests `.out()`, `.in()`, `.both()` methods for graph navigation
- **complex_graph**: Multi-step graph construction with multiple vertices, edges, traversals, and modifications

### Query Results

- **result_set**: Tests ResultSet iteration, Result property access via `.get()`, order preservation, multiple result handling

### Query Languages

- **cypher_queries**: Tests OpenCypher CREATE statements, MATCH queries, property access (when OpenCypher available)
- **sql_queries**: Tests SQL queries, aggregation, filtering, joins

### Advanced Features

- **vector_search**: Tests vector index creation, vector insertion, cosine similarity search, result ranking
- **unicode_support**: Tests UTF-8 encoding, international characters (Spanish, Chinese, Japanese, Arabic), emoji
- **schema_queries**: Tests schema metadata via `SELECT FROM schema:types`, type introspection
- **large_result_sets**: Tests bulk inserts (1000+ records) in transactions, iteration efficiency, memory handling
- **type_conversions**: Tests Python ↔ Java type mapping (str, int, float, bool, None, datetime)

## Key Patterns

```python
# Database lifecycle
with arcadedb.create_database("./test_db") as db:
    # Use database
    pass  # Auto-closes

# Transaction pattern
with db.transaction():
    rec = db.new_document("Type")
    rec.set("key", "value").save()
    # Auto-commits on success, auto-rollback on error

# Query and iterate
result_set = db.query("sql", "SELECT FROM Type")
for result in result_set:
    value = result.get("field")
    # Process...

# Graph traversal
vertex = db.new_vertex("Person")
vertex.set("name", "Alice").save()
friends = vertex.out("Knows")  # Traverse edges
```

## Related Documentation

- [Database API Reference](../../api/database.md)
- [Transactions API Reference](../../api/transactions.md)
- [Results API Reference](../../api/results.md)
- [Database Guide](../../guide/core/database.md)
