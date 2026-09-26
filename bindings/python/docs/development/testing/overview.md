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
- ✅ **Server mode** - HTTP API, multi-client access
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
pytest -k "server"
pytest -k "concurrency"

# Run with output (see print statements)
pytest -v -s
```

## Test Files Overview

Test counts evolve over time. For the latest per-file counts, run `pytest -v -rs`.

| Test File | Description |
| --------- | ----------- |
| [`test_async_executor.py`](test-async-executor.md) | Async command/query execution, callback behavior, and exact command-path counts at parallel levels 1 and 4 |
| [`test_bulk_insert.py`](test-bulk-insert.md) | Recommended bulk paths land every row, plus `Database.insert_many`, `AsyncExecutor.create_record`, vector columns, and numpy `append_samples` bulk ingest |
| [`test_core.py`](test-core.md) | Core database operations, CRUD, transactions, queries |
| [`test_database_utils.py`](test-database-utils.md) | Database utility helpers and initialization behavior |
| [`test_docs_examples.py`](test-docs-examples.md) | Executes representative Python snippets from the documentation site |
| [`test_exporter.py`](test-exporter.md) | Database export formats and CSV result export helpers |
| [`test_graph_api.py`](test-graph-api.md) | Graph wrapper behavior for vertices, edges, and traversal helpers |
| [`test_importer_api.py`](test-importer.md) | Narrow `db.import_documents(...)` wrapper coverage |
| [`test_logging_helper.py`](test-logging-helper.md) | Internal `_logging` helper configuration behavior |
| [`test_numpy_support.py`](test-numpy-support.md) | NumPy integration and array conversion behavior |
| [`test_resultset.py`](test-resultset.md) | Result and ResultSet iteration, accessors, and export helpers |
| [`test_schema.py`](test-schema.md) | Schema, property, and index management behavior |
| [`test_server.py`](test-server.md) | Server mode, HTTP API, configuration |
| [`test_concurrency.py`](test-concurrency.md) | File locking, thread safety, multi-process behavior |
| [`test_server_patterns.py`](test-server-patterns.md) | Best practices for embedded + server mode |
| [`test_import_database.py`](test-importer.md) | SQL `IMPORT DATABASE` scenarios and format coverage |
| [`test_cypher.py`](test-opencypher.md) | OpenCypher query language |
| [`test_graph_batch.py`](test-graph-batch.md) | Bulk graph-ingest helper coverage |
| [`test_graph.py`](test-graph.md) | `GraphBatch.new_edges` and `create_vertices` bulk path coverage |
| [`test_geo_predicate_sql.py`](test-geo-predicate-sql.md) | Geospatial SQL predicate semantics |
| [`test_timeseries_sql.py`](test-timeseries-sql.md) | Time-series SQL type creation, range filters, and bucketing |
| [`test_materialized_view_sql.py`](test-materialized-view-sql.md) | Materialized view lifecycle and refresh behavior |
| [`test_restore_sql.py`](test-restore-sql.md) | RESTORE DOCUMENT/VERTEX record-count and record integrity |
| [`test_graph_algorithms_sql.py`](test-graph-algorithms-sql.md) | SQL graph algorithm runtime coverage |
| [`test_hash_index_schema.py`](test-hash-index-schema.md) | HASH index schema API behavior |
| [`test_jvm_args.py`](test-jvm-args.md) | JVM args handling |
| [`test_transaction_config.py`](test-transaction-config.md) | Transaction configuration and rollback semantics |
| [`test_type_conversion.py`](test-type-conversion.md) | Python/Java type conversion coverage |
| [`test_vector.py`](test-vector.md) | Vector API and nearest-neighbor search behavior |
| [`test_vector_params_verification.py`](test-vector-params-verification.md) | Vector param validation |
| [`test_vector_sql.py`](test-vector-sql.md) | SQL vector functions, index creation, and search flows |
| [`test_cross_model_atomicity.py`](test-cross-model-atomicity.md) | Search, hop, and update in one transaction survive an interruption between the writes with nothing torn; without a transaction they are torn every time |
| [`test_example11_degree_matching.py`](test-example11-degree-matching.md) | Example 11 compares ArcadeDB against hnswlib-derived vector backends. |
| [`test_jar_provenance.py`](test-jar-provenance.md) | The wheel can say which engine it carries, not just which version it is. |
| [`test_java_package_shadowing.py`](test-java-package-shadowing.md) | A folder named `java/` or `com/` must not change what a query returns |
| [`test_jvm.py`](test-jvm.md) | Tests for start_jvm() re-entry behavior once the JVM is running. |
| [`test_jvm_payload.py`](test-jvm-payload.md) | A Python list must never be what crosses into the JVM |
| [`test_resultset_arrow.py`](test-resultset-arrow.md) | Tests for ResultSet.to_arrow(). |
| [`test_runtime_cache.py`](test-runtime-cache.md) | The dev-mode runtime cache must follow the wheel it was extracted from |
| [`test_server_http_endpoints.py`](test-server-http-endpoints.md) | The three server HTTP features the bindings document but do not wrap: multi-request transactions, server database commands, and line-protocol time-series writes |
| [`test_server_packaging.py`](test-server-packaging.md) | The server stack is actually IN the wheel, and the API is reachable. |
| [`test_server_wire_protocols.py`](test-server-wire-protocols.md) | The wire protocols the wheel bundles are actually reachable. |
| [`test_sparse_quantization_compact.py`](test-sparse-quantization-compact.md) | Sparse index weight precision and the settle step, plus the dense search beam argument |
| [`test_vector_delta_visibility.py`](test-vector-delta-visibility.md) | Vectors written after an index build are searchable, exactly, before any rebuild |
| [`test_vector_second_pass.py`](test-vector-second-pass.md) | A repeated query set returns the same neighbours as its first pass |
| [`test_wheel_platform_tag.py`](test-wheel-platform-tag.md) | Built wheel manylinux platform tag verification (regression tests for issue #4037) |

## Common Testing Workflows

### Development Workflow

```bash
# Run only failed tests from last run
pytest --lf
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

The markers are registered in `bindings/python/pyproject.toml` (`server`, `server_wire`, and
`integration`) and in `tests/conftest.py` (`server` and `graph_export`). These are the ones the
suite uses:

| Marker | Tests |
| ------ | ----- |
| `server` | The four server tests in `test_server.py`, `test_server_starts_and_serves_http` in `test_server_packaging.py`, and `test_docs_api_access_examples` in `test_docs_examples.py` |
| `server_wire` | Every test in `test_server_wire_protocols.py` (module-level `pytestmark`) |
| `graph_export` | `test_export_graphml` and `test_export_graphson` in `test_exporter.py` |

`integration` is registered, but no test uses it.

```bash
# Run only the tests marked server
pytest -m server

# Run only OpenCypher tests (a keyword match, not a marker)
pytest -k cypher

# Run all except the tests marked server
pytest -m "not server"
```

`-m "not server"` skips only the tests marked `server`. Other tests that start a server still
run: `test_server_patterns.py`, `test_server_http_endpoints.py`, and `test_server_wire_protocols.py`
(marked `server_wire`, not `server`). To leave out every server-starting test:

```bash
pytest -m "not server and not server_wire" \
  --ignore=tests/test_server_patterns.py \
  --ignore=tests/test_server_http_endpoints.py
```

## Expected Output

When the current bindings test suite passes, you should see a clean all-green summary.

```text
======================== passed ========================
```

## Next Steps

- **New to testing?** Start with [Core Tests](test-core.md)
- **Using server mode?** See [Server Tests](test-server.md) and [Server Patterns](test-server-patterns.md)
- **Confused about concurrency?** Read [Concurrency Tests](test-concurrency.md)
- **Importing data?** Check [Data Import Tests](test-importer.md)
- **Using OpenCypher?** See [OpenCypher Tests](test-opencypher.md)

## Related Documentation

- [API Reference](../../api/database.md) - Database API documentation
- [User Guide](../../guide/core/database.md) - Database usage guide
- [Contributing](../contributing.md) - How to contribute to the project
- [Best Practices](best-practices.md) - Testing best practices
