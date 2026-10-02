# Testing Guide

Comprehensive testing documentation for ArcadeDB Python bindings.

## Quick Navigation

<div class="grid cards" markdown>

-   :material-flask: **[Overview](testing/overview.md)**

    ---

    Quick start, markers, skips, and how to run tests

-   :material-database: **[Core Tests](testing/test-core.md)**

    ---

    CRUD, transactions, queries, graph operations

-   :material-server: **[Server Tests](testing/test-server.md)**

    ---

    Server lifecycle, configuration, and Studio URL

-   :material-lock: **[Concurrency Tests](testing/test-concurrency.md)**

    ---

    File locking, thread safety, multi-process

-   :material-swap-horizontal: **[Server Patterns](testing/test-server-patterns.md)**

    ---

    Embedded + HTTP best practices

-   :material-import: **[Data Import Tests](testing/test-importer.md)**

    ---

    SQL `IMPORT DATABASE` workflows and format coverage

-   :material-file-document-multiple: **[Docs Example Tests](testing/test-docs-examples.md)**

    ---

    Executable coverage for representative Python snippets in the MkDocs docs tree

-   :material-source-branch: **[GraphBatch Tests](testing/test-graph-batch.md)**

    ---

    Engine-backed bulk graph ingest helper coverage

-   :material-map-marker-radius: **[Geo Predicate SQL Tests](testing/test-geo-predicate-sql.md)**

    ---

    SQL `geo.within` and `geo.intersects` semantics

-   :material-chart-timeline-variant: **[Timeseries SQL Tests](testing/test-timeseries-sql.md)**

    ---

    SQL-first timeseries type creation, range queries, and bucketing

-   :material-table-search: **[Materialized View SQL Tests](testing/test-materialized-view-sql.md)**

    ---

    Materialized view lifecycle, refresh, and metadata coverage

-   :material-backup-restore: **[RESTORE SQL Tests](testing/test-restore-sql.md)**

    ---

    RESTORE DOCUMENT/VERTEX: record count agrees with a full scan, and the record comes back intact

-   :material-map-search: **[Graph Algorithms SQL Tests](testing/test-graph-algorithms-sql.md)**

    ---

    `shortestPath`, `dijkstra`, and `astar` runtime coverage

-   :material-pound-box: **[Hash Index Schema Tests](testing/test-hash-index-schema.md)**

    ---

    HASH index creation, discovery, and drop coverage

-   :material-graph: **[OpenCypher Tests](testing/test-opencypher.md)**

    ---

    Graph traversal language

-   :material-check-all: **[Best Practices](testing/best-practices.md)**

    ---

    Summary of recommended patterns and practices

</div>

## Quick Start

### Installation

1. Build the wheel: `cd bindings/python && ./scripts/build.sh` (Docker on Linux,
   Python 3.12 by default). It writes the wheel to `bindings/python/dist/` and,
   outside CI, refreshes the repo-root uv environment.
2. From the repository root (or `bindings/python`), run `uv run pytest`. The
   repo-root `pyproject.toml` is the test environment, pinned to Python 3.12, so it
   needs a cp312 wheel. To leave out the heavy example packages (torch,
   sentence-transformers), pass `--no-group examples` to `uv sync` and `uv run`.

Other Python versions and platforms are covered by CI (see [CI/CD Setup](ci-setup.md)).
CI does not use the uv environment: it installs the built wheel and a hand-maintained
list of test dependencies, then runs `pytest tests/` from `bindings/python` (see
[CI Gates](ci-setup.md#ci-gates)).

### Running Tests

```bash
# Run all tests (from the repository root or bindings/python; from any other
# directory a bare run collects only that directory)
uv run pytest

# Run specific category (paths are relative to the repository root)
uv run pytest bindings/python/tests/test_core.py -v
uv run pytest bindings/python/tests/test_concurrency.py -v

# Run with coverage
uv run pytest --cov=arcadedb_embedded --cov-report=html
```

## Test Coverage Summary

| Category | What's Tested |
|----------|---------------|
| **Core Operations** | CRUD, transactions, queries, graph operations, vector search |
| **Server Mode** | Server lifecycle and configuration, HTTP API, bundled wire protocols, packaging |
| **Concurrency** | File locking, thread safety, multi-process limitations |
| **Server Patterns** | Embedded+HTTP combinations, lock management |
| **Data Import** | SQL `IMPORT DATABASE` across formats, the `import_documents()` wrapper, `on_row_error` |
| **Query Languages** | SQL, OpenCypher |
| **Advanced Features** | Unicode support, schema introspection, geospatial SQL, timeseries SQL, graph algorithms, materialized views, HASH indexes |

## Key Concepts

### Concurrency Model

!!! question "Can multiple Python instances access the same database?"

    - ❌ Multiple **processes** cannot (file lock prevents it)
    - ✅ Multiple **threads** can (thread-safe within same process)
    - ✅ Use **server mode** for true multi-process access

See [Concurrency Tests](testing/test-concurrency.md) for details.

### Server Access Patterns

Two ways to combine embedded + HTTP access:

1. **Pattern 1**: Embedded First → Server (requires manual `close()`)
2. **Pattern 2**: Server First → Create (recommended, simpler)

See [Server Patterns](testing/test-server-patterns.md) for detailed comparison.

### Performance Insight

!!! tip "No HTTP Overhead"
    Embedded access through a server is a direct JVM call, not HTTP: the Python
    process that started the server pays no network overhead. The server-patterns
    comparison prints both timings but does not assert that they are equal.

## Common Testing Workflows

### Development

```bash
# Run tests matching keyword
uv run pytest -k "transaction" -v
uv run pytest -k "import" -v

# Stop on first failure
uv run pytest -x

# Drop into debugger on failure
uv run pytest --pdb

# Show skipped test reasons
uv run pytest -v -rs
```

## Test Organization

This is the current live test tree under `bindings/python/tests`. Exact test counts evolve, so this section lists files and responsibilities rather than hardcoding per-file totals.

```bash
tests/
├── conftest.py                         # Shared fixtures
├── test_async_executor.py              # Async execution tests
├── test_bulk_insert.py                 # insert_many / create_record bulk ingest tests
├── test_concurrency.py                 # Concurrency tests
├── test_core.py                        # Core operations
├── test_cross_model_atomicity.py       # Search, hop, and update in one transaction
├── test_cypher.py                      # OpenCypher tests
├── test_database_utils.py              # Database utility tests
├── test_docs_examples.py               # Runnable docs example tests
├── test_example11_degree_matching.py   # Example 11 backend degree matching
├── test_exporter.py                    # Exporter tests
├── test_geo_predicate_sql.py           # Geospatial SQL predicate tests
├── test_graph.py                       # GraphBatch new_edges / create_vertices bulk tests
├── test_graph_algorithms_sql.py        # shortestPath / dijkstra / astar
├── test_graph_api.py                   # Graph API tests
├── test_graph_batch.py                 # Bulk graph ingest helper
├── test_hash_index_schema.py           # HASH index schema tests, plus a named-list IN parameter on an LSM_TREE index
├── test_import_database.py             # SQL import workflow tests
├── test_importer_api.py                # Import helper wrapper tests
├── test_jar_provenance.py              # Engine provenance carried by the wheel
├── test_java_package_shadowing.py      # java/ or com/ folders on the path
├── test_jvm.py                         # start_jvm() re-entry, close and reopen in one process, and exit with an unclosed database
├── test_jvm_args.py                    # JVM argument tests
├── test_jvm_payload.py                 # No Python list crosses into the JVM
├── test_logging_helper.py              # Internal logging helper tests
├── test_materialized_view_sql.py       # Materialized view lifecycle
├── test_numpy_support.py               # NumPy integration tests
├── test_restore_sql.py                 # RESTORE DOCUMENT / VERTEX tests
├── test_resultset.py                   # Result handling tests
├── test_resultset_arrow.py             # ResultSet.to_arrow() tests
├── test_runtime_cache.py               # Dev-mode runtime cache tests
├── test_schema.py                      # Schema tests
├── test_schema_batching.py             # Schema statements apply at once; many batch in one transaction
├── test_server.py                      # Server tests
├── test_server_http_endpoints.py       # Server HTTP features the bindings do not wrap
├── test_server_packaging.py            # Server stack bundled in the wheel
├── test_server_patterns.py             # Embedded/server access patterns
├── test_server_wire_protocols.py       # Bundled wire protocols
├── test_sparse_quantization_compact.py # Sparse precision, settle step, dense beam
├── test_timeseries_sql.py              # Timeseries SQL coverage
├── test_transaction_config.py          # Transaction config tests
├── test_type_conversion.py             # Type conversion tests
├── test_vector.py                      # Vector API tests
├── test_vector_delta_visibility.py     # Vectors searchable before a rebuild
├── test_vector_params_verification.py  # Vector parameter validation tests
├── test_vector_second_pass.py          # Repeated query sets return the same neighbours
├── test_vector_sql.py                  # Vector SQL tests
└── test_wheel_platform_tag.py          # Wheel platform tag tests, and __version__ equals the installed distribution version
```

## Next Steps

**New to testing?** Start with [Overview](testing/overview.md)

**Working with databases?** See [Core Tests](testing/test-core.md)

**Need multi-process access?** Read [Concurrency Tests](testing/test-concurrency.md)

**Setting up a server?** Check [Server Patterns](testing/test-server-patterns.md)

**Importing data?** See [Data Import Tests](testing/test-importer.md)

**Checking docs examples?** See [Docs Example Tests](testing/test-docs-examples.md)

**Want best practices?** Read [Best Practices Summary](testing/best-practices.md)
