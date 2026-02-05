# Testing Overview

The ArcadeDB Python bindings have a comprehensive test suite covering all major functionality.

## Quick Statistics

!!! success "Test Results"
    - **Current package**: ✅ 260 passed, 6 skipped (260 collected)
    - All features available (SQL, OpenCypher, Studio UI, Vector search)

## What's Tested

The test suite covers:

- ✅ **Core database operations** - CRUD, transactions, queries
- ✅ **Server mode** - HTTP API, multi-client access
- ✅ **Concurrency patterns** - File locking, thread safety, multi-process
- ✅ **Graph operations** - Vertices, edges, traversals
- ✅ **Query languages** - SQL, OpenCypher
- ✅ **Vector search** - HNSW (JVector) based Vector indexes, similarity search
- ✅ **Data import** - CSV with batch commits and type inference
- ✅ **Unicode support** - International characters, emoji
- ✅ **Schema introspection** - Querying database metadata
- ✅ **Type conversions** - Python/Java type mapping
- ✅ **Large datasets** - Handling 1000+ records efficiently

## Quick Start

### Install Test Dependencies

```bash
uv pip install pytest pytest-cov
```

### Run All Tests

```bash
# From the bindings/python directory
pytest

# With verbose output
pytest -v

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
|-----------|-------------|
| [`test_core.py`](test-core.md) | Core database operations, CRUD, transactions, queries |
| [`test_server.py`](test-server.md) | Server mode, HTTP API, configuration |
| [`test_concurrency.py`](test-concurrency.md) | File locking, thread safety, multi-process behavior |
| [`test_server_patterns.py`](test-server-patterns.md) | Best practices for embedded + server mode |
| [`test_importer.py`](test-importer.md) | CSV import with type inference |
| [`test_cypher.py`](test-opencypher.md) | OpenCypher query language |
| [`test_jvm_args.py`](test-jvm-args.md) | JVM args handling |
| [`test_vector_params_verification.py`](test-vector-params-verification.md) | Vector param validation |

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

Tests are organized with pytest markers:

```bash
# Run only server tests
pytest -m server

# Run only OpenCypher tests
pytest -k cypher

# Run all except slow tests
pytest -m "not slow"
```

## Expected Output

When all tests pass, you should see:

```
======================== 260 passed in 9.67s =========================
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
