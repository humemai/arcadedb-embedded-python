# Core Database Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_core.py){ .md-button }

The tests cover fundamental database operations.

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
- Result sets of 1,000 records (no timing is asserted)
- Type conversions (Python ↔ Java)
- RID lookup via `lookup_by_rid()`
- `run_in_transaction()` commit and rollback on any exception, including `BaseException`
- Bulk materialization (`to_json_list()`, `to_columns()`, `to_dataframe()`)

## Test Cases

### Database Management

- **test_database_creation**: Creates a new database via `arcadedb.create_database()` and verifies `is_open()` before and after `close()`
- **test_database_operations**: Uses a `with` context manager to create a `TestDoc` type, insert in a transaction, and query it back

### CRUD Operations

- **test_rich_data_types**: Defines a `Task` type with STRING/BOOLEAN/INTEGER/FLOAT/DECIMAL/DATE/DATETIME properties, uses built-in functions (`uuid()`, `date()`, `sysdate()`), then exercises insert, aggregation, filtering, UPDATE, and DELETE
- **test_arcadedb_sql_features**: Tests built-in SQL functions and JSON-like embedded document properties on `TestEntity` (metadata returns a Java map-like object)
- **test_transactions**: Tests successful commit and automatic rollback on exception
- **test_run_in_transaction_commits_and_returns**: `run_in_transaction()` runs `fn` transactionally and hands back its return value; a non-retryable `ArcadeDBError` from `fn` propagates and its insert is rolled back
- **test_run_in_transaction_rolls_back_on_non_arcadedb_error**: A plain `KeyError` from `fn` still rolls back and leaves no open transaction (regression test for #7108)
- **test_run_in_transaction_rolls_back_on_base_exception**: `SystemExit` is a `BaseException`, so `except Exception` let it skip the rollback; the test raises `SystemExit` from `fn` and asserts no transaction is left open and nothing was stored
- **test_result_methods**: Tests `Result` methods: `has_property()`, `get()`, `get_property_names()`, `to_dict()`, `to_json()`
- **test_property_type_conversions**: Tests Python ↔ Java type mapping (str, int, long, float, double, bool, None, date); `date` is only checked to be non-null
- **test_single_list_arg_is_positional_param_array**: A single list argument binds one element per `?` placeholder, the idiom example 04's CSV ingest uses; a list among several arguments stays one parameter (`vectorCosineSimilarity(?, ?)` returns 1.0)

### Full-text Search

- **test_fulltext_search_with_score**: Creates a `FULL_TEXT` index on `Article.content` and verifies `SEARCH_INDEX(...)` results expose `$score`
- **test_fulltext_search_preserves_wildcards**: Verifies wildcard queries (`Hel*`) reach the full-text index unchanged
- **test_fulltext_search_bm25_term_boosts**: BM25 scoring honours per-term caret boosts (`term^weight`) in the query string

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

### Result Materialization

- **test_to_json_list_bulk_materialization**: `to_json_list(batch_size=10)` returns all 25 rows across several Java batches, with JSON-native values; the `n` column matches `to_list()`
- **test_to_json_list_empty_result**: `to_json_list()` on an empty result is an empty list
- **test_to_columns_typed_bulk_materialization**: `to_columns()` returns typed numpy columns with pandas-convention nulls
- **test_to_columns_survives_json_metacharacters_in_aliases**: A projection alias is arbitrary text, so the columnar header has to be real JSON (#6758): aliases containing a quote and a semicolon come back as the column names, with their values, across batches of 2 rows
- **test_to_dataframe_fast_path**: `to_dataframe()` returns 50 rows with an integer dtype for `n` and the expected `name` in row 3 (skips without pandas). The test does not check which path built it
- **test_resultset_close_and_context_manager**: `ResultSet` supports `close()` and the context-manager protocol

### Parameter Binding (`test_parameter_binding.py`)

`query()`, `command()`, and the async executor hand the engine one typed argument: an `Object[]` for positional parameters and a `java.util.Map` for named ones (humemai/arcadedb-embedded-python#172). Before, `command()` with a lone `None` raised `Ambiguous overloads`.

- **a lone null binds**: `None`, `[None]`, and `(None,)` on `command()` insert and update a property to null, select records in an `UPDATE ... WHERE v <=> ?`, and on `query()` select the record whose `v` is null
- **null then a value**: `(None, 1)` on both binds both
- **named parameters**: a dict on both binds `:v` (null) and `:w`; a list holding one dict is still the named map, in SQL and in openCypher
- **async**: `args=[None]`, `(None,)`, and `[None, 1]` store a null without an error
- **one Java overload per shape**: a JPype proxy of the `Database` interface, and of `DatabaseAsyncExecutor`, records the argument each shape arrives as
- **scalar parameters take the short path** (`TestScalarParametersTakeTheShortPath`): a dict of `str` keys with `int`, `float`, `str`, `bool`, or `None` values, and positional scalars, are bound without `convert_python_to_java` (a spy on it sees no call); the answers equal the general path's, for every scalar type including a 2**40 integer and a null. A `Decimal`, a list value, a subclass of `int`, and a numpy scalar still take the general path

### Other Features

- **test_error_handling**: `arcadedb.open_database()` on an invalid path raises `ArcadeDBError`
- **test_failed_open_does_not_hang_process_exit**: A failed `open_database()` must leave the process able to exit: a child process that fails an open exits 0 within 60 s (regression test for a leaked non-daemon AsyncFlush thread)
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
