# Testing Guide

Comprehensive testing documentation for ArcadeDB Python bindings.

!!! success "Test Coverage"
    **262 tests** across 20 test files, 100% passing

    - **Current package**: 262 passed
    - All ArcadeDB features working (SQL, OpenCypher, Studio)

## Quick Navigation

<div class="grid cards" markdown>

-   :material-flask: **[Overview](testing/overview.md)**

    ---

    Quick start, statistics, and how to run tests

-   :material-database: **[Core Tests](testing/test-core.md)**

    ---

    CRUD, transactions, queries, graph operations (13 tests)

-   :material-server: **[Server Tests](testing/test-server.md)**

    ---

    HTTP API, Studio, configuration (6 tests)

-   :material-lock: **[Concurrency Tests](testing/test-concurrency.md)**

    ---

    File locking, thread safety, multi-process (4 tests)

-   :material-swap-horizontal: **[Server Patterns](testing/test-server-patterns.md)**

    ---

    Embedded + HTTP best practices (4 tests)

-   :material-import: **[Data Import Tests](testing/test-importer.md)**

    ---

    CSV import with type inference (16 tests)

-   :material-graph: **[OpenCypher Tests](testing/test-opencypher.md)**

    ---

    Graph traversal language (1 test)

-   :material-check-all: **[Best Practices](testing/best-practices.md)**

    ---

    Summary of recommended patterns and practices

</div>

## Quick Start

### Installation

```bash
# Install test dependencies
uv pip install pytest pytest-cov
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific category
pytest tests/test_core.py -v
pytest tests/test_concurrency.py -v

# Run with coverage
pytest --cov=arcadedb_embedded --cov-report=html
```

## Test Coverage Summary

| Category | What's Tested |
|----------|---------------|
| **Core Operations** | CRUD, transactions, queries, graph operations, vector search |
| **Server Mode** | HTTP API, Studio UI, configuration, multiple databases |
| **Concurrency** | File locking, thread safety, multi-process limitations |
| **Server Patterns** | Embedded+HTTP combinations, lock management |
| **Data Import** | CSV with type inference, batch commits |
| **Query Languages** | SQL, OpenCypher |
| **Advanced Features** | Unicode support, schema introspection, large datasets |

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
    Embedded access through server is **just as fast** as standalone embedded mode!

    It's a direct JVM call, not HTTP. Same Python process = zero network overhead.

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

```bash
tests/
├── test_core.py              # Core operations (13 tests)
├── test_server.py            # Server mode (6 tests)
├── test_concurrency.py       # Concurrency (4 tests)
├── test_server_patterns.py   # Patterns (4 tests)
├── test_importer.py          # Import (13 tests)
├── test_cypher.py            # OpenCypher (tests)
└── conftest.py               # Shared fixtures
```

## Next Steps

**New to testing?** Start with [Overview](testing/overview.md)

**Working with databases?** See [Core Tests](testing/test-core.md)

**Need multi-process access?** Read [Concurrency Tests](testing/test-concurrency.md)

**Setting up a server?** Check [Server Patterns](testing/test-server-patterns.md)

**Importing data?** See [Data Import Tests](testing/test-importer.md)

**Want best practices?** Read [Best Practices Summary](testing/best-practices.md)
