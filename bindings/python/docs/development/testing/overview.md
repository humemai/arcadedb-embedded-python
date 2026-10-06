# Testing Overview

The ArcadeDB Python bindings have a comprehensive test suite covering all major functionality.

## What's Tested

The test suite covers:

- ✅ **Core database operations** - CRUD, transactions, queries
- ✅ **Server mode** - HTTP API, multi-client access
- ✅ **Concurrency patterns** - File locking, thread safety, multi-process
- ✅ **Graph operations** - Vertices, edges, traversals
- ✅ **Query languages** - SQL, OpenCypher
- ✅ **Vector search** - JVector-based `LSM_VECTOR` indexes, similarity search
- ✅ **Data import** - SQL `IMPORT DATABASE` across CSV, XML, Neo4j, Word2Vec, and RDF, plus the `import_documents()` wrapper
- ✅ **Graph ingest helper** - `GraphBatch` buffering and flush behavior
- ✅ **Geospatial SQL** - `geo.within`, `geo.intersects`, null input returns null; a boundary point returns a boolean (which one is not asserted)
- ✅ **Time series SQL** - `CREATE TIMESERIES TYPE`, range queries, bucketing
- ✅ **Materialized views** - create, refresh, alter, drop lifecycle
- ✅ **Graph algorithms** - `shortestPath`, `dijkstra`, `astar`
- ✅ **HASH schema indexes** - create, discover, idempotent `get_or_create_index`, force drop, and the `UNIQUE_HASH` id path
- ✅ **Unicode support** - International characters, emoji
- ✅ **Schema introspection** - Querying database metadata
- ✅ **Type conversions** - Python/Java type mapping
- ✅ **Large result sets** - Result sets of 1,000 records: ordered iteration, filtered and aggregate queries (no timing is asserted)
- ✅ **Async executor** - `async_executor()` commands, queries, callbacks, and exact command-path counts at parallel levels 1 and 4
- ✅ **Bulk ingest** - `insert_many`, `AsyncExecutor.create_record`, and numpy `append_samples`
- ✅ **Export** - JSONL database export, CSV result export, and the error GraphML and GraphSON raise without arcadedb-gremlin
- ✅ **ResultSet API** - `to_list`, `to_json_list`, `to_dataframe`, `to_arrow`, and release of the engine cursor
- ✅ **JVM** - startup, arguments, and lifecycle (re-entry, reopen in one process, exit with an unclosed database)
- ✅ **Bundled wire protocols** - PostgreSQL (including Arrow ADBC), Bolt, and the Redis port setting; a default server opens none of their ports
- ✅ **Packaging and provenance** - server JARs in the wheel, `jar_fingerprint()`, the wheel platform tag, the dev-mode runtime cache, and `__version__`
- ✅ **Sparse vectors** - `LSM_SPARSE_VECTOR` weight precision, the settle step (`COMPACT INDEX`), and INT8 rescoring
- ✅ **Cross-model atomicity** - search, hop, and update in one transaction survive an interruption
- ✅ **RESTORE** - `RESTORE DOCUMENT` and `RESTORE VERTEX` record counts and record integrity
- ✅ **Schema batching** - schema statements apply at once; many batch in one transaction
- ✅ **Docs snippets** - selected Python blocks from the documentation run as code
- ✅ **JVM payload check** - a static check that no Python list crosses into the JVM

## Quick Start

### Install Test Dependencies

1. Build the wheel: `cd bindings/python && ./scripts/build.sh` (Docker on Linux,
   Python 3.12 by default). It writes the wheel to `bindings/python/dist/` and,
   outside CI, refreshes the repo-root uv environment.
2. From the repository root (or `bindings/python`), run `uv run pytest`. The
   repo-root `pyproject.toml` is the test environment, pinned to Python 3.12, so it
   needs a cp312 wheel. To leave out the heavy example packages (torch,
   sentence-transformers), pass `--no-group examples` to `uv sync` and `uv run`.

Other Python versions and platforms are covered by CI (see [CI/CD Setup](../ci-setup.md)).
CI does not use the uv environment: it installs the built wheel and a hand-maintained
list of test dependencies, then runs `pytest tests/` from `bindings/python` (see
[CI Gates](../ci-setup.md#ci-gates)).

### Run All Tests

```bash
# From the repository root or bindings/python (from any other directory a bare
# run collects only that directory)
uv run pytest

# With verbose output
uv run pytest -v

# With coverage report
uv run pytest --cov=arcadedb_embedded --cov-report=html
```

On Windows, run with `--capture=sys`: pytest's default fd capture can leave the JVM writing
its log lines to a handle that no longer belongs to it, and the test then hangs in that
write (issue #10).

### Run Specific Tests

```bash
# Run a specific test file (paths are relative to the repository root)
uv run pytest bindings/python/tests/test_core.py

# Run a specific test function
uv run pytest bindings/python/tests/test_core.py::test_database_creation

# Run tests matching a keyword
uv run pytest -k "transaction"
uv run pytest -k "server"
uv run pytest -k "concurrency"

# Run with output (see print statements)
uv run pytest -v -s
```

## Test Files Overview

Test counts evolve over time. For the latest per-file counts, run `uv run pytest -v -rs`.

| Test File | Description |
| --------- | ----------- |
| [`test_async_executor.py`](test-async-executor.md) | Async command/query execution, callback behavior, and exact command-path counts at parallel levels 1 and 4 |
| [`test_bulk_insert.py`](test-bulk-insert.md) | Recommended bulk paths land every row, plus `Database.insert_many`, `AsyncExecutor.create_record`, vector columns, and numpy `append_samples` bulk ingest |
| [`test_core.py`](test-core.md) | Core database operations, CRUD, transactions, queries |
| [`test_database_utils.py`](test-database-utils.md) | `count_type`, `is_transaction_active`, and `drop`, plus error handling on a closed database |
| [`test_docs_examples.py`](test-docs-examples.md) | Executes representative Python snippets from the documentation site |
| [`test_exporter.py`](test-exporter.md) | Database export formats and CSV result export helpers |
| [`test_graph_api.py`](test-graph-api.md) | Graph wrapper behavior for vertices, edges, and traversal helpers |
| [`test_importer_api.py`](test-importer.md) | Narrow `db.import_documents(...)` wrapper coverage |
| [`test_logging_helper.py`](test-logging-helper.md) | Internal `_logging` helper configuration behavior |
| [`test_numpy_support.py`](test-numpy-support.md) | NumPy integration and array conversion behavior |
| [`test_resultset.py`](test-resultset.md) | Result and ResultSet iteration, accessors, and export helpers |
| [`test_schema.py`](test-schema.md) | Schema, property, and index management behavior |
| [`test_schema_batching.py`](test-schema-batching.md) | Schema statements apply immediately, a rollback does not undo them, and many batch in one transaction |
| [`test_server.py`](test-server.md) | Server lifecycle, configuration, and databases through the Java API (no HTTP calls) |
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
| [`test_hash_index_schema.py`](test-hash-index-schema.md) | HASH index schema API behavior, the `UNIQUE_HASH` id path end to end, plus a named-list IN parameter on an LSM_TREE index |
| [`test_jvm_args.py`](test-jvm-args.md) | JVM args handling |
| [`test_transaction_config.py`](test-transaction-config.md) | WAL flush, read-your-writes, and auto-transaction settings |
| [`test_type_conversion.py`](test-type-conversion.md) | Python/Java type conversion coverage |
| [`test_vector.py`](test-vector.md) | Vector API and nearest-neighbor search behavior |
| [`test_vector_params_verification.py`](test-vector-params-verification.md) | Vector param validation |
| [`test_vector_sql.py`](test-vector-sql.md) | SQL vector functions, index creation, and search flows |
| [`test_cross_model_atomicity.py`](test-cross-model-atomicity.md) | Search, hop, and update in one transaction survive an interruption between the writes with nothing torn; with one transaction per write they are torn every time |
| [`test_example11_degree_matching.py`](test-example11-degree-matching.md) | `hnsw_m_from_max_connections()` halves maxConnections for hnswlib-derived backends, never below 1, and accepts a string; skips if examples/11 is absent |
| [`test_jar_provenance.py`](test-jar-provenance.md) | The wheel can say which engine it carries, not just which version it is. |
| [`test_java_package_shadowing.py`](test-java-package-shadowing.md) | A folder named `java/` or `com/` must not change what a query returns |
| [`test_jvm.py`](test-jvm.md) | `start_jvm()` re-entry once the JVM is running, close and reopen in one process, and interpreter exit with an unclosed database |
| [`test_sigint.py`](test-jvm.md#ctrl-c-test_sigintpy) | Ctrl-C raises `KeyboardInterrupt` and runs cleanup once the JVM is started; `interrupt=True` keeps JPype's default |
| [`test_jvm_payload.py`](test-jvm-payload.md) | A Python list must never be what crosses into the JVM |
| [`test_resultset_arrow.py`](test-resultset-arrow.md) | Tests for ResultSet.to_arrow(). |
| [`test_columnar_readers.py`](test-resultset-arrow.md#schemaless-and-decimal-data-test_columnar_readerspy) | `to_columns`, `to_dataframe`, and `to_arrow` on schemaless and DECIMAL data, at several batch sizes. |
| [`test_runtime_cache.py`](test-runtime-cache.md) | The dev-mode runtime cache must follow the wheel it was extracted from |
| [`test_server_http_endpoints.py`](test-server-http-endpoints.md) | The three server HTTP features the bindings document but do not wrap (multi-request transactions, server database commands, and line-protocol time-series writes), plus a projection read over HTTP |
| [`test_server_packaging.py`](test-server-packaging.md) | The server stack is actually IN the wheel, and the API is reachable. |
| [`test_server_wire_protocols.py`](test-server-wire-protocols.md) | The wire protocols the wheel bundles are actually reachable. |
| [`test_sparse_quantization_compact.py`](test-sparse-quantization-compact.md) | Sparse index weight precision and the settle step, the dense search beam argument, and INT8 sparse rescoring |
| [`test_vector_delta_visibility.py`](test-vector-delta-visibility.md) | Vectors written after an index build are searchable, exactly, before any rebuild |
| [`test_vector_second_pass.py`](test-vector-second-pass.md) | A repeated query set returns the same neighbours as its first pass |
| [`test_wheel_platform_tag.py`](test-wheel-platform-tag.md) | Built wheel manylinux platform tag verification (regression tests for `ArcadeData/arcadedb#4037`), and `__version__` equals the installed distribution version |

## Common Testing Workflows

### Development Workflow

```bash
# Run only failed tests from last run
uv run pytest --lf
```

### Debugging Tests

```bash
# Stop on first failure
uv run pytest -x

# Drop into debugger on failure
uv run pytest --pdb

# Show local variables on failure
uv run pytest -l

# Verbose with full output
uv run pytest -vv -s
```

## Test Markers

The markers are registered in `bindings/python/pyproject.toml` (`server`, `server_wire`,
and `integration`); the repo-root `pyproject.toml` mirrors that block. These are
the ones the suite uses:

| Marker | Tests |
| ------ | ----- |
| `server` | `test_server_creation`, `test_server_database_operations`, `test_server_custom_config`, and `test_server_context_manager` in `test_server.py`, `test_server_starts_and_serves_http` in `test_server_packaging.py`, and `test_docs_api_access_examples` in `test_docs_examples.py` |
| `server_wire` | Every test in `test_server_wire_protocols.py` (module-level `pytestmark`) |

`integration` is registered, but no test uses it.

```bash
# Run only the tests marked server
uv run pytest -m server

# Run only OpenCypher tests (a keyword match, not a marker)
uv run pytest -k cypher

# Run all except the tests marked server
uv run pytest -m "not server"
```

`-m "not server"` skips only the tests marked `server`. Other tests that start a server still
run: `test_server_patterns.py`, `test_server_http_endpoints.py`, and `test_server_wire_protocols.py`
(marked `server_wire`, not `server`). To leave out every server-starting test:

```bash
uv run pytest -m "not server and not server_wire" \
  --ignore=bindings/python/tests/test_server_patterns.py \
  --ignore=bindings/python/tests/test_server_http_endpoints.py
```

## Expected Output

A passing run ends with a summary of the form `N passed, M skipped, K xfailed`, with no
failures or errors. The strict xfails are the engine bugs listed on the Known Engine Issues
page; on Linux and macOS nothing skips. Run with `-rs` to see why a test skipped.

## Skips

A skip is a test that did not run, so the suite keeps them to what cannot run:

- **The platform**: on Windows, `test_importer_api.py` skips a file name with a question mark and
  `test_sigint.py` skips its child-process interrupts.
- **The upstream pull request branch has no `docs/`**: `test_docs_examples.py` skips there.
- **An optional Python package**: numpy, pandas, pyarrow, requests, psycopg,
  adbc-driver-postgresql, or neo4j, through `pytest.importorskip`, so a missing one is
  visible to the CI gate below.

A test never skips because the engine or the wheel lacks a feature it ships (OpenCypher,
geo and graph-algorithm SQL functions, time series, the HASH index, vector encodings, the
importers, the server stack): that is a failure. Earlier versions of these tests skipped on
the engine's error or on an empty answer, which let a wrong empty answer pass as a skip.

CI enforces this: the `test` job runs `scripts/check_test_skips.py` over the JUnit XML and
fails on any skip whose reason is not on its short list (`tests/test_check_test_skips.py`
tests the gate). See [CI Gates](../ci-setup.md#ci-gates).

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
