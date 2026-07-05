# Testing Overview

The ArcadeDB Python bindings have a comprehensive test suite covering all major functionality.

## Quick Statistics

!!! success "Test Results"
    - **Current package**: the full suite passes cleanly
    - Test counts evolve over time; run `pytest -v -rs` for the latest totals
    - Environment-specific skips may vary depending on optional components

## What's Tested

The test suite covers:

- ✅ **Core database operations** - CRUD, transactions, queries
- ✅ **Concurrency patterns** - File locking, thread safety, multi-process
- ✅ **Graph operations** - Vertices, edges, traversals
- ✅ **Query languages** - SQL, OpenCypher
- ✅ **Vector search** - HNSW (JVector) based Vector indexes, similarity search
- ✅ **Data import** - CSV with batch commits and type inference
- ✅ **Graph ingest helper** - `GraphBatch` buffering and flush behavior
- ✅ **Geospatial SQL** - `geo.within`, `geo.intersects`, null/boundary semantics
- ✅ **Time series SQL** - `CREATE TIMESERIES TYPE`, range queries, bucketing
- ✅ **Materialized views** - create, refresh, alter, drop lifecycle
- ✅ **Graph algorithms** - `shortestPath`, `dijkstra`, `astar`
- ✅ **HASH schema indexes** - create, discover, idempotent drop behavior
- ✅ **Unicode support** - International characters, emoji
- ✅ **Schema introspection** - Querying database metadata
- ✅ **Type conversions** - Python/Java type mapping
- ✅ **Large datasets** - Handling 1000+ records efficiently

## Quick Start

### Install Test Dependencies

Nothing to install — test dependencies come from the repo-root uv project and
are synced automatically by `uv run`.

### Run All Tests

```bash
# From anywhere in the repo
uv run pytest

# With verbose output
uv run pytest -v

# With coverage report
pytest --cov=arcadedb_embedded --cov-report=html
```

### Run Specific Tests

```bash
# Run a specific test file
pytest tests/test_core.py

# Run a specific test function
pytest tests/test_core.py::test_database_creation

# Run tests matching a keyword
pytest -k "transaction"
pytest -k "concurrency"

# Run with output (see print statements)
pytest -v -s
```

## Test Files Overview

Test counts evolve over time. For the latest per-file counts, run `pytest -v -rs`.

| Test File | Description |
| --------- | ----------- |
| [`test_async_executor.py`](test-async-executor.md) | Async command/query execution and callback behavior |
| [`test_core.py`](test-core.md) | Core database operations, CRUD, transactions, queries |
| [`test_database_utils.py`](test-database-utils.md) | Database utility helpers and initialization behavior |
| [`test_docs_examples.py`](test-docs-examples.md) | Executes representative Python snippets from the documentation site |
| [`test_exporter.py`](test-exporter.md) | Database export formats and CSV result export helpers |
| [`test_graph_api.py`](test-graph-api.md) | Graph wrapper behavior for vertices, edges, and traversal helpers |
| [`test_importer_api.py`](test-importer.md) | Narrow `db.import_documents(...)` wrapper coverage |
| `test_logging_helper.py` | Logging helper configuration behavior |
| [`test_numpy_support.py`](test-numpy-support.md) | NumPy integration and array conversion behavior |
| [`test_resultset.py`](test-resultset.md) | Result and ResultSet iteration, accessors, and export helpers |
| [`test_schema.py`](test-schema.md) | Schema, property, and index management behavior |
| [`test_concurrency.py`](test-concurrency.md) | File locking, thread safety, multi-process behavior |
| [`test_import_database.py`](test-importer.md) | SQL `IMPORT DATABASE` scenarios and format coverage |
| [`test_cypher.py`](test-opencypher.md) | OpenCypher query language |
| [`test_graph_batch.py`](test-graph-batch.md) | Bulk graph-ingest helper coverage |
| [`test_geo_predicate_sql.py`](test-geo-predicate-sql.md) | Geospatial SQL predicate semantics |
| [`test_timeseries_sql.py`](test-timeseries-sql.md) | Time-series SQL type creation, range filters, and bucketing |
| [`test_materialized_view_sql.py`](test-materialized-view-sql.md) | Materialized view lifecycle and refresh behavior |
| [`test_graph_algorithms_sql.py`](test-graph-algorithms-sql.md) | SQL graph algorithm runtime coverage |
| [`test_hash_index_schema.py`](test-hash-index-schema.md) | HASH index schema API behavior |
| [`test_jvm_args.py`](test-jvm-args.md) | JVM args handling |
| [`test_transaction_config.py`](test-transaction-config.md) | Transaction configuration and rollback semantics |
| [`test_type_conversion.py`](test-type-conversion.md) | Python/Java type conversion coverage |
| [`test_vector.py`](test-vector.md) | Vector API and nearest-neighbor search behavior |
| [`test_vector_params_verification.py`](test-vector-params-verification.md) | Vector param validation |
| [`test_vector_sql.py`](test-vector-sql.md) | SQL vector functions, index creation, and search flows |
| `test_wheel_platform_tag.py` | Built wheel platform tag verification |

## Common Testing Workflows

### Development Workflow

```bash
# Watch mode - rerun tests on file changes
pytest --watch

# Run only failed tests from last run
pytest --lf

# Run tests in parallel (faster)
pytest -n auto
```

### Debugging Tests

```bash
# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Verbose with full output
pytest -vv -s
```

## Test Markers

Tests are organized with pytest markers (`integration`, `graph_export`):

```bash
# Run only OpenCypher tests
pytest -k cypher

# Run all except server tests
pytest -m "not server"
```

## Expected Output

When the current bindings test suite passes, you should see a clean all-green summary.

```text
======================== passed ========================
```

## Next Steps

- **New to testing?** Start with [Core Tests](test-core.md)
- **Confused about concurrency?** Read [Concurrency Tests](test-concurrency.md)
- **Importing data?** Check [Data Import Tests](test-importer.md)
- **Using OpenCypher?** See [OpenCypher Tests](test-opencypher.md)

## Related Documentation

- [API Reference](../../api/database.md) - Database API documentation
- [User Guide](../../guide/core/database.md) - Database usage guide
- [Contributing](../contributing.md) - How to contribute to the project
- [Best Practices](best-practices.md) - Testing best practices
