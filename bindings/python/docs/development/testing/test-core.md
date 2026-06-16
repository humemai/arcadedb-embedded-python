# Core Database Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_core.py){ .md-button }

There are **25 tests** covering fundamental database operations.

## Overview

Tests validate:

- Database creation and context managers
- CRUD operations (Create, Read, Update, Delete)
- Transaction management and ACID behavior
- Graph operations (vertex/edge creation and traversal)
- Query result handling and iteration
- Error handling
- OpenCypher queries (when available)
- SQL aggregate behavior on empty types
- Full-text search (`SEARCH_INDEX`, `$score`, wildcards)
- SQLScript, `UPDATE`/`DELETE` `BATCH`, `UPDATE ... CONTENT`, `TRUNCATE BUCKET`, `FIND REFERENCES`
- Unicode/international character support
- Schema introspection and metadata
- Large result sets (1000+ records)
- Type conversions (Python ↔ Java)
- RID lookup via `lookup_by_rid()`

## Test Cases

### Database Management

- **test_database_creation**: Creates a new database via `arcadedb.create_database()` and verifies `is_open()` before and after `close()`
- **test_database_operations**: Uses a `with` context manager to create a `TestDoc` type, insert in a transaction, and query it back

### CRUD Operations

- **test_rich_data_types**: Defines a `Task` type with STRING/BOOLEAN/INTEGER/FLOAT/DECIMAL/DATE/DATETIME properties, uses built-in functions (`uuid()`, `date()`, `sysdate()`), then exercises insert, aggregation, filtering, UPDATE, and DELETE
- **test_arcadedb_sql_features**: Tests built-in SQL functions and JSON-like embedded document properties on `TestEntity` (metadata returns a Java map-like object)
- **test_transactions**: Tests successful commit and automatic rollback on exception
- **test_result_methods**: Tests `Result` methods: `has_property()`, `get()`, `get_property_names()`, `to_dict()`, `to_json()`
- **test_property_type_conversions**: Tests Python ↔ Java type mapping (str, int, long, float, double, bool, None, date)

### Full-text Search

- **test_fulltext_search_with_score**: Creates a `FULL_TEXT` index on `Article.content` and verifies `SEARCH_INDEX(...)` results expose `$score`
- **test_fulltext_search_preserves_wildcards**: Verifies wildcard queries (`Hel*`) reach the full-text index unchanged

### SQL Statement Coverage

- **test_sql_count_on_empty_type_returns_zero**: `count(*)` on an empty type returns a row with `0`
- **test_sqlscript_returns_last_command_result**: `sqlscript` returns the last command's result when no explicit `RETURN` is used
- **test_update_with_json_array_content**: `UPDATE ... CONTENT [...]` supports JSON arrays for multi-document updates with `RETURN AFTER`
- **test_truncate_bucket**: `TRUNCATE BUCKET` removes all records in a bucket (uses `count_type()`)
- **test_update_batch_clause**: `UPDATE ... BATCH` executes through the Python SQL pass-through
- **test_delete_batch_clause**: `DELETE ... BATCH` executes through the Python SQL pass-through
- **test_find_references_returns_referring_record**: `FIND REFERENCES` returns the record pointing to a target RID

### Graph Operations

- **test_graph_operations**: Creates `Person` vertices and a `Knows` edge via SQL, then traverses with `out('Knows')`
- **test_create_edge_with_content_object_preserves_properties**: `CREATE EDGE ... CONTENT {...}` keeps object-form properties
- **test_complex_graph_traversal**: Multi-hop traversal across `Follows`/`Likes` edges on a small social graph
- **test_lookup_by_rid**: Creates a vertex with `db.new_vertex(...)`/`save()`, then resolves it with `db.lookup_by_rid()`; invalid RID raises `ArcadeDBError`

### Query Languages

- **test_opencypher_queries**: Tests OpenCypher `CREATE` and `MATCH` queries (skips if the opencypher engine is unavailable)

### Other Features

- **test_error_handling**: `arcadedb.open_database()` on an invalid path raises `ArcadeDBError`
- **test_unicode_support**: Tests UTF-8 international characters (Spanish, Chinese, Japanese, Arabic) and emoji
- **test_schema_queries**: Tests schema metadata via `SELECT FROM schema:types`, `schema:indexes`, and `schema:database`
- **test_large_result_set_handling**: Bulk-inserts 1000 records and tests ordered iteration, filtering, and aggregation

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
knows_edges = vertex.get_out_edges("Knows")  # outgoing "Knows" edges
friends = [edge.get_in() for edge in knows_edges]  # neighbor vertices
```

## Related Documentation

- [Database API Reference](../../api/database.md)
- [Transactions API Reference](../../api/transactions.md)
- [Results API Reference](../../api/results.md)
- [Database Guide](../../guide/core/database.md)
