# Testing Guide

Comprehensive testing documentation for ArcadeDB Python bindings.

!!! success "Test Coverage"
    Current bindings suite

    - **Current package**: 351 passed
    - All embedded ArcadeDB features working (SQL, OpenCypher, vectors, graphs)

## Quick Navigation

<div class="grid cards" markdown>

-   :material-flask: **[Overview](testing/overview.md)**

    ---

    Quick start, statistics, and how to run tests

-   :material-database: **[Core Tests](testing/test-core.md)**

    ---

    CRUD, transactions, queries, graph operations (13 tests)

-   :material-lock: **[Concurrency Tests](testing/test-concurrency.md)**

    ---

    File locking, thread safety, multi-process

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

Nothing to install — test dependencies come from the repo-root uv project and
are synced automatically by `uv run`.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific category
uv run pytest tests/test_core.py -v
uv run pytest tests/test_concurrency.py -v

# Run with coverage
uv run pytest --cov=arcadedb_embedded --cov-report=html
```

## Test Coverage Summary

| Category | What's Tested |
|----------|---------------|
| **Core Operations** | CRUD, transactions, queries, graph operations, vector search |
| **Concurrency** | File locking, thread safety, multi-process limitations |
| **Data Import** | SQL import workflows, type inference, batch commits |
| **Query Languages** | SQL, OpenCypher |
| **Advanced Features** | Unicode support, schema introspection, geospatial SQL, timeseries SQL, graph algorithms, materialized views, HASH indexes |

## Key Concepts

### Concurrency Model

!!! question "Can multiple Python instances access the same database?"

    - ❌ Multiple **processes** cannot (file lock prevents it)
    - ✅ Multiple **threads** can (thread-safe within same process)
    - ✅ For true multi-process access, run the official standalone ArcadeDB server

See [Concurrency Tests](testing/test-concurrency.md) for details.

## Common Testing Workflows

### Development

```bash
# Run tests matching keyword
pytest -k "transaction" -v
pytest -k "import" -v

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show skipped test reasons
pytest -v -rs
```

## Test Organization

This is the current live test tree under `bindings/python/tests`. Exact test counts evolve, so this section lists files and responsibilities rather than hardcoding per-file totals.

```bash
tests/
├── conftest.py                         # Shared fixtures
├── test_async_executor.py             # Async execution tests
├── test_concurrency.py                # Concurrency tests
├── test_core.py                       # Core operations
├── test_cypher.py                     # OpenCypher tests
├── test_database_utils.py             # Database utility tests
├── test_docs_examples.py              # Runnable docs example tests
├── test_exporter.py                   # Exporter tests
├── test_geo_predicate_sql.py          # Geospatial SQL predicate tests
├── test_graph_algorithms_sql.py       # shortestPath / dijkstra / astar
├── test_graph_api.py                  # Graph API tests
├── test_graph_batch.py                # Bulk graph ingest helper
├── test_hash_index_schema.py          # HASH index schema tests
├── test_import_database.py            # SQL import workflow tests
├── test_importer_api.py               # Import helper wrapper tests
├── test_jvm_args.py                   # JVM argument tests
├── test_logging_helper.py             # Internal logging helper tests
├── test_materialized_view_sql.py      # Materialized view lifecycle
├── test_numpy_support.py              # NumPy integration tests
├── test_resultset.py                  # Result handling tests
├── test_schema.py                     # Schema tests
├── test_timeseries_sql.py             # Timeseries SQL coverage
├── test_transaction_config.py         # Transaction config tests
├── test_type_conversion.py            # Type conversion tests
├── test_vector.py                     # Vector API tests
├── test_vector_params_verification.py # Vector parameter validation tests
├── test_vector_sql.py                 # Vector SQL tests
└── test_wheel_platform_tag.py         # Wheel platform tag tests
```

## Next Steps

**New to testing?** Start with [Overview](testing/overview.md)

**Working with databases?** See [Core Tests](testing/test-core.md)

**Need multi-process access?** Read [Concurrency Tests](testing/test-concurrency.md)

**Importing data?** See [Data Import Tests](testing/test-importer.md)

**Checking docs examples?** See [Docs Example Tests](testing/test-docs-examples.md)

**Want best practices?** Read [Best Practices Summary](testing/best-practices.md)
