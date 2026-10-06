# Contributing to ArcadeDB Python Bindings

Thank you for your interest in contributing to ArcadeDB Python bindings! This guide will help you get started with development.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/humemai/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python

# Build the package (requires Docker); this also refreshes the uv env at the repo root
./scripts/build.sh

# Run tests
uv run pytest
```

## Development Environment

### Requirements

**Required:**

- Python: the package supports 3.10–3.14; the dev environment is 3.12 only
- [uv](https://docs.astral.sh/uv/) (runs the dev environment)
- Docker (for building the Linux wheels)
- Git

**Only for native macOS and Windows builds:**

- A JDK 25 or later with `jlink` and `javac`, and `JAVA_HOME` set (`scripts/build-native.sh`
  checks the version and `jlink`, and reads the JDK's modules from `JAVA_HOME`)
- A Python with a working `build` module: the script takes the first of `python3.13`,
  `python3.12`, `python3.11`, `python3`, and `python` that has one, and the version argument
  does not choose it
- Docker, to pull the JARs from the `arcadedata/arcadedb` image, unless
  `src/arcadedb_embedded/jars/` already holds JARs. An existing JAR directory is reused
  whatever its version, so delete it after a version change.

A native build rewrites the `version`, `name`, and `description` lines of the tracked
`bindings/python/pyproject.toml` in place, and deletes every wheel in `dist/` before it builds.
Revert `pyproject.toml` before committing.

The wheel bundles its own JRE, so running the tests or using the package needs no
Java installation, and the Linux build runs inside Docker.

**Installed by the repo-root uv project** (no separate install):

- pytest (testing)
- black and isort (code formatting)
- mypy (type checking)
- bandit (security lint)
- mkdocs and its plugins (documentation)

### Setup

1. **Clone Repository**

```bash
git clone https://github.com/humemai/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python
```

2. **Build the Wheel**

The JARs and JRE come from a built wheel, so there is no editable install.
Outside CI, and when uv is on `PATH`, building also refreshes the uv dev
environment at the repo root:

```bash
./scripts/build.sh
```

3. **Verify Setup**

The dev environment is a uv project at the repo root (`pyproject.toml`); it
installs the built wheel from `dist/` plus all test/dev dependencies. It is
pinned to Python 3.12, so it needs a cp312 wheel. There is no virtualenv to
activate: run everything through `uv run`, from the repository root or
`bindings/python` (from any other directory, a bare `uv run pytest` collects
only that directory):

```bash
# Run quick test
uv run python -c "import arcadedb_embedded; print('✅ Setup successful!')"

# Run the test suite
uv run pytest
```

## Project Structure

```
arcadedb-embedded-python/bindings/python/
├── src/
│   ├── arcadedb_embedded/        # Main package
│   │   ├── __init__.py            # Package initialization
│   │   ├── _logging.py            # Internal logging helpers
│   │   ├── async_executor.py      # Async command/query execution
│   │   ├── core.py                # Database, DatabaseFactory
│   │   ├── exceptions.py          # Exception classes
│   │   ├── exporter.py            # JSONL database export, CSV result export
│   │   ├── graph.py               # Graph wrappers
│   │   ├── graph_batch.py         # Bulk graph ingest helper
│   │   ├── importer.py            # Import helpers
│   │   ├── jvm.py                 # JVM startup logic
│   │   ├── results.py             # Query result handling
│   │   ├── schema.py              # Schema management
│   │   ├── server.py              # ArcadeDBServer
│   │   ├── transactions.py        # Transaction management
│   │   ├── type_conversion.py     # Python-Java type conversion
│   │   └── vector.py              # Vector search support
│   └── java/com/arcadedb/python/  # Bridge JAR sources (batched row transport)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         # Shared fixtures
│   ├── README.md                           # Testing documentation
│   ├── test_async_executor.py              # Async execution tests
│   ├── test_bulk_insert.py                 # insert_many / create_record bulk ingest tests
│   ├── test_concurrency.py                 # Concurrency tests
│   ├── test_core.py                        # Core operations
│   ├── test_cross_model_atomicity.py       # Search, hop, and update in one transaction
│   ├── test_cypher.py                      # OpenCypher tests
│   ├── test_database_utils.py              # Database utility tests
│   ├── test_docs_examples.py               # Runnable docs example tests
│   ├── test_example11_degree_matching.py   # Example 11 backend degree matching
│   ├── test_exporter.py                    # Exporter tests
│   ├── test_geo_predicate_sql.py           # Geospatial SQL predicate tests
│   ├── test_graph.py                       # GraphBatch new_edges / create_vertices bulk tests
│   ├── test_graph_algorithms_sql.py        # shortestPath / dijkstra / astar
│   ├── test_graph_api.py                   # Graph API tests
│   ├── test_graph_batch.py                 # Bulk graph ingest helper
│   ├── test_hash_index_schema.py           # HASH index schema tests, plus a named-list IN parameter on an LSM_TREE index
│   ├── test_import_database.py             # SQL import workflow tests
│   ├── test_importer_api.py                # Import helper wrapper tests
│   ├── test_jar_provenance.py              # Engine provenance carried by the wheel
│   ├── test_java_package_shadowing.py      # java/ or com/ folders on the path
│   ├── test_jvm.py                         # start_jvm() re-entry, close and reopen in one process, and exit with an unclosed database
│   ├── test_jvm_args.py                    # JVM argument tests
│   ├── test_jvm_payload.py                 # No Python list crosses into the JVM
│   ├── test_logging_helper.py              # Internal logging helper tests
│   ├── test_materialized_view_sql.py       # Materialized view lifecycle
│   ├── test_numpy_support.py               # NumPy integration tests
│   ├── test_restore_sql.py                 # RESTORE DOCUMENT / VERTEX tests
│   ├── test_resultset.py                   # Result handling tests
│   ├── test_resultset_arrow.py             # ResultSet.to_arrow() tests
│   ├── test_runtime_cache.py               # Dev-mode runtime cache tests
│   ├── test_schema.py                      # Schema tests
│   ├── test_schema_batching.py             # Schema statements apply at once; many batch in one transaction
│   ├── test_server.py                      # Server tests
│   ├── test_server_http_endpoints.py       # Server HTTP features the bindings do not wrap
│   ├── test_server_packaging.py            # Server stack bundled in the wheel
│   ├── test_server_patterns.py             # Embedded/server access patterns
│   ├── test_server_wire_protocols.py       # Bundled wire protocols
│   ├── test_sparse_quantization_compact.py # Sparse precision, settle step, dense beam
│   ├── test_timeseries_sql.py              # Timeseries SQL coverage
│   ├── test_transaction_config.py          # Transaction config tests
│   ├── test_type_conversion.py             # Type conversion tests
│   ├── test_vector.py                      # Vector API tests
│   ├── test_vector_delta_visibility.py     # Vectors searchable before a rebuild
│   ├── test_vector_params_verification.py  # Vector parameter validation tests
│   ├── test_vector_second_pass.py          # Repeated query sets return the same neighbours
│   ├── test_vector_sql.py                  # Vector SQL tests
│   └── test_wheel_platform_tag.py          # Wheel platform tag tests, and __version__ equals the installed distribution version
├── docs/                          # MkDocs documentation
│   ├── getting-started/
│   ├── guide/
│   ├── api/
│   ├── examples/
│   └── development/
├── examples/                      # Example scripts
│   ├── 01_simple_document_store.py
│   ├── 02_social_network_graph.py
│   ├── ...                        # the other numbered examples
│   ├── 26_cross_model_transaction_atomicity.py
│   ├── download_data.py           # Data download helper
│   ├── data/                      # Example datasets
│   └── scripts/                   # Example helper scripts
├── local-jars/                    # Engine JARs staged by build.sh (gitignored)
├── .runtime-cache/                # JARs and JRE extracted for source-tree imports (gitignored)
├── pyproject.toml                 # Package configuration
├── setup.py                       # Setup configuration
├── scripts/                       # Build and maintenance helpers
│   ├── arrow_transport_probe.py   # to_arrow() measurement script
│   ├── build.sh                   # Main build entrypoint
│   ├── build-native.sh            # Native build script
│   ├── build_and_install_locally.sh # Engine build + wheel from the headless assembly (no Studio, Bolt, Redis, or GraphQL)
│   ├── ensure-build-tools.sh      # Build tools setup
│   ├── extract_version.py         # Version extraction
│   ├── fix_markdown.py            # Docs formatter
│   ├── jar_exclusions.txt         # JAR optimization list
│   ├── list_image_jars_by_size.sh # Image JAR inspection helper
│   ├── profile-python/            # Result-consumption profiler
│   ├── setup_jars.py              # JAR staging script
│   ├── verify_wheel_platform_tag.py # Wheel platform tag verifier
│   ├── write_version.py           # Version writing
│   └── Dockerfile.build           # Build container
└── mkdocs.yml                     # Documentation config
```

## Building from Source

### Docker Build (Recommended)

```bash
# Build the current package
./scripts/build.sh

# Output: dist/*.whl
```

**What the build does:**

1. Reads the ArcadeDB version from the parent `pom.xml` (`scripts/extract_version.py`)
2. Takes the JARs from the `arcadedata/arcadedb:<version>` image or, on Linux, from the
   directory passed as the third argument, and removes those listed in
   `scripts/jar_exclusions.txt`; a native build reuses `src/arcadedb_embedded/jars/` when it
   already holds JARs
3. Compiles the bridge JAR (`arcadedb-python-bridge.jar`) from `src/java/`
4. Builds the bundled JRE with `jlink`
5. Builds the wheel; on Linux, `scripts/verify_wheel_platform_tag.py` checks the manylinux tag
   against the highest GLIBC version the JRE needs
6. On Linux only, installs the wheel in a clean image and runs a smoke script that creates a
   database, inserts one document, and queries it (the test suite does not run during the build)
7. Deletes older wheels with the same tag from `dist/`
8. Outside CI, with uv on `PATH`, refreshes the repo-root uv environment:
   `uv lock --upgrade-package arcadedb-embedded`, then
   `uv sync --reinstall-package arcadedb-embedded`

### Local Build

```bash
# Build for the current platform
./scripts/build.sh

# Or target a specific supported platform on matching native hardware
# (the Python version argument applies to Linux (Docker) builds only)
./scripts/build.sh darwin/arm64
./scripts/build.sh windows/amd64

# No install step needed: build.sh refreshes the repo-root uv env automatically

# Embed engine JARs you built yourself instead of the image's (third argument;
# Linux builds only, a native build ignores it)
./scripts/build.sh linux/amd64 3.12 ../../package/target/arcadedb-<version>.dir/arcadedb-<version>/lib
```

A wheel built from a JAR directory carries only the JARs in that directory (less those in
`scripts/jar_exclusions.txt`). Use the full assembly's `lib` directory, as above. The
headless assembly, which `scripts/build_and_install_locally.sh` stages, omits Studio, Bolt,
Redis, and GraphQL, and its wheel fails `test_server_packaging.py`. To test a change to the
bindings, build against the image's JARs; use a JAR directory to test an engine change.

### Development Install

There is no editable install. The JARs and JRE come from a built wheel: the uv
environment installs it, and an import from the source tree extracts them from the
newest wheel in `dist/` into `.runtime-cache/`. After changing Python code in
`src/`, rebuild:

```bash
./scripts/build.sh   # rebuilds the wheel and refreshes the uv env
uv run pytest
```

## Running Tests

### All Tests

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=arcadedb_embedded --cov-report=html

# View coverage report
open htmlcov/index.html
```

The tests use fixed ports: 2480 (the server default, which most server tests use) and 8080
(`test_server_custom_config`), and `test_plugins_are_opt_in` asserts that 5432, 6379, and 7687
refuse connections. A local PostgreSQL, Redis, Neo4j, or ArcadeDB server listening on one of
those ports fails the suite. On Windows, run pytest with `--capture=sys`.

### Specific Test Files

```bash
# Paths are relative to the repository root

# Core functionality
uv run pytest bindings/python/tests/test_core.py

# Server mode
uv run pytest bindings/python/tests/test_server.py

# Import database coverage
uv run pytest bindings/python/tests/test_import_database.py

# Documentation examples coverage
uv run pytest bindings/python/tests/test_docs_examples.py

# OpenCypher tests
uv run pytest bindings/python/tests/test_cypher.py
```

### Test Markers

```bash
# Skip the tests marked server (other server-starting tests still run)
uv run pytest -m "not server"

# Only OpenCypher tests (a keyword match, not a marker)
uv run pytest -k cypher
```

The markers in use are `server` and `server_wire`; `integration` is registered
but unused. See [Test Markers](testing/overview.md#test-markers) for which tests each one covers
and how to leave out every server-starting test.

### Writing Tests

Use the shared fixtures in `tests/conftest.py` rather than your own temporary directories. A
server test carries `@pytest.mark.server` and does not skip. One JVM serves the whole session,
and engine-wide settings carry from one test to the next, so run the full suite after adding a
test. The fixtures, what may skip, optional dependencies, hang diagnostics, and the Bandit rule
are in [Writing a Test for This Suite](testing/best-practices.md#writing-a-test-for-this-suite).

```python
# tests/test_example.py
import pytest
import arcadedb_embedded as arcadedb

def test_create_database(tmp_path):
    """Test database creation."""
    db_path = tmp_path / "test.db"

    # Create database
    db = arcadedb.create_database(str(db_path))

    try:
        # Test operations
        db.command("sql", "CREATE VERTEX TYPE User")

        # Verify
        result = db.query("sql", "SELECT FROM schema:types WHERE name = 'User'")
        assert result.first() is not None
    finally:
        db.close()

def test_transaction_rollback(tmp_path):
    """Test transaction rollback."""
    db_path = tmp_path / "test.db"
    db = arcadedb.create_database(str(db_path))

    try:
        db.command("sql", "CREATE VERTEX TYPE User")

        # Should rollback
        with pytest.raises(Exception):
            with db.transaction():
                db.command("sql", "INSERT INTO User SET name = ?", "Alice")
                raise Exception("Force rollback")

        # Verify rollback
        result = db.query("sql", "SELECT FROM User")
        assert result.first() is None
    finally:
        db.close()
```

## Coding Standards

### Python Style

We follow **PEP 8** with some modifications:

- Line length: 88 characters (black's default; no override is configured)
- Use double quotes for strings
- Use trailing commas in multi-line structures

```python
# Good
def create_user(db, name: str, email: str) -> dict:
    """
    Create a new user vertex.

    Args:
        db: Database instance
        name: User's full name
        email: User's email address

    Returns:
        User vertex as dict
    """
    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO User SET name = ?, email = ?",
            name,
            email,
        )

    return {
        "name": name,
        "email": email,
    }

# Bad
def create_user(db,name,email):
    db.command('sql',f"INSERT INTO User SET name = '{name}', email = '{email}'")
    return {"name": name, "email": email}
```

### Formatting Tools

```bash
# From the repository root: the hooks CI runs (black, isort, shfmt, pretty-format-yaml,
# prettier on src/java, and the whitespace and end-of-file fixers)
uvx pre-commit run --files $(git ls-files 'bindings/python/**')

# Type checking, from bindings/python (advisory: no CI job runs mypy)
uv run mypy src/
```

Running black or isort by hand does not reproduce the gate: pre-commit pins its own tool
versions, which can differ from the uv environment's, and it also covers `examples/` and
`scripts/`.

CI also runs Bandit, a dependency-floor audit, and the pre-commit hooks; see
[CI Gates](ci-setup.md#ci-gates) for what they check and how to run them locally.

### Type Hints

Use type hints for all public APIs:

```python
from typing import Optional, List, Dict, Any

def query_users(
    db: Database,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query users with optional filters."""
    # Implementation
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def import_database(
    db: Database,
    source_url: str,
    options: str = ""
) -> None:
    """
    Import data into the database through SQL.

    Args:
        db: Database instance
        source_url: File URL to import from
        options: Additional SQL import options fragment

    Returns:
        None

    Example:
        >>> db = arcadedb.open_database("./mydb")
        >>> import_database(db, "file:///tmp/users.csv", "WITH documentType = 'User'")
    """
    db.command("sql", f"IMPORT DATABASE {source_url} {options}".strip())
```

### Error Handling

Always provide clear error messages:

```python
# Good
try:
    db = arcadedb.open_database(path)
except Exception as e:
    raise ArcadeDBError(
        f"Failed to open database at '{path}': {e}"
    ) from e

# Bad
try:
    db = arcadedb.open_database(path)
except:
    raise Exception("Error")  # Not informative!
```

### Naming Conventions

```python
# Classes: PascalCase
class DatabaseFactory:
    pass

class VectorIndex:
    pass

# Functions/methods: snake_case
def create_database(path: str) -> Database:
    pass

def import_data(self, path: str) -> None:
    pass

# Constants: UPPER_SNAKE_CASE
DEFAULT_BATCH_SIZE = 1000
MAX_RETRIES = 3

# Private: leading underscore
def _internal_helper():
    pass

class Database:
    def _check_not_closed(self):
        pass
```

## Documentation

### Building Documentation

See [Documentation Development](documentation.md). In short, from the repository root:

```bash
# Serve locally (hot reload)
uv run mkdocs serve -f bindings/python/mkdocs.yml

# Build with strict checks (fails on warnings and broken links)
uv run mkdocs build --strict -f bindings/python/mkdocs.yml
```

### Writing Documentation

Documentation uses **Markdown** with **MkDocs Material** theme:

````markdown
# Page Title

Brief introduction to the topic.

## Section

Content here with examples.

### Code Examples

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")
```

### Admonitions

!!! note "Important Note"
    This is important information.

!!! warning "Warning"
    Be careful with this!

!!! tip "Pro Tip"
    This will make your life easier.

### Links

- [Internal link](../api/database.md)
- [External link](https://arcadedb.com)
````

### API Documentation

Keep API reference in sync with code:

```python
# src/arcadedb_embedded/core.py
class Database:
    def query(self, language: str, command: str, *args) -> ResultSet:
        """
        Execute a query and return results.

        Args:
            language: Query language (sql, opencypher, graphql)
            command: Query command string
            *args: Positional parameters, or one dict of named parameters

        Returns:
            ResultSet: Iterable query results

        Raises:
            ArcadeDBError: If query execution fails

        Example:
            >>> result = db.query("sql", "SELECT FROM User WHERE age > :min_age", {"min_age": 18})
            >>> for user in result:
            ...     print(user.get("name"))
        """
```

Corresponding documentation in `docs/api/database.md`:

````markdown
### query

```python
db.query(language: str, command: str, *args) -> ResultSet
```

Execute a query and return results.

**Parameters:**

- `language` (str): Query language (sql, opencypher, graphql)
- `command` (str): Query command string
- `*args`: Positional parameters for `?` placeholders, or one dict of named parameters

**Returns:**

- `ResultSet`: Iterable query results

**Raises:**

- `ArcadeDBError`: If query execution fails

**Example:**

```python
# Basic query
result = db.query("sql", "SELECT FROM User")
for user in result:
    print(user.get("name"))

# Parameterized query
result = db.query("sql",
    "SELECT FROM User WHERE age > :min_age",
    {"min_age": 18}
)
```
````

## Pull Request Process

### 1. Fork and Clone

```bash
# Fork on GitHub first
git clone https://github.com/YOUR_USERNAME/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python

# Track this repository. Do not call the remote "upstream": this repository's own
# scripts (sync-upstream.sh) use that name for ArcadeData/arcadedb.
git remote add humemai https://github.com/humemai/arcadedb-embedded-python.git
```

### 2. Create Branch

```bash
# Update main
git checkout main
git pull humemai main

# Create feature branch
git checkout -b feature/my-new-feature

# Or bug fix branch
git checkout -b fix/issue-123
```

### 3. Make Changes

```bash
# Edit files
vim src/arcadedb_embedded/core.py

# Add tests
vim tests/test_core.py

# Update documentation
vim docs/api/database.md
```

### 4. Test Changes

```bash
# Run tests
uv run pytest

# Format and lint (from the repository root; the hooks CI runs)
uvx pre-commit run --files $(git ls-files 'bindings/python/**')

# Type check (advisory; from bindings/python)
uv run mypy src/

# Build documentation (from the repository root)
uv run mkdocs build --strict -f bindings/python/mkdocs.yml
```

### 5. Commit Changes

```bash
# Stage changes
git add src/ tests/ docs/

# Commit with clear message
git commit -m "Refine vector search docs and tests

- Clarified SQL-first vector index workflow
- Updated vector docs and tests
- Added tests for all distance functions
- Updated API documentation

Fixes #123"
```

**Commit Message Guidelines:**

- First line: Brief summary (50 chars max)
- Blank line
- Detailed description
- Reference issues: `Fixes #123` or `Closes #456`

### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/my-new-feature

# Go to GitHub and create Pull Request
```

### 7. Suggested PR Description

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] All tests pass
- [ ] Added new tests for changes
- [ ] Updated documentation
- [ ] Tested manually

## Checklist
- [ ] Code follows project style guide
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Related Issues
Fixes #123
Closes #456
```

## Release Process

Releases are cut by pushing a version tag; the release workflow builds, tests, and
publishes the wheels through PyPI trusted publishing. Do not upload wheels by hand.
The full procedure, including how the version reaches `pom.xml` and the checks to run
on the tag before pushing it, is in [Release Workflow](release.md).

## Common Tasks

### Adding a New Feature

1. Create feature branch
2. Implement feature in `src/arcadedb_embedded/`
3. Add tests in `tests/`
4. Update documentation in `docs/`
5. Add example in `examples/` (if applicable)
6. Submit PR

### Fixing a Bug

1. Write failing test that reproduces bug
2. Fix bug in source code
3. Verify test now passes
4. Update documentation if needed
5. Submit PR with test + fix

### Adding Documentation

1. Create/update Markdown files in `docs/`
2. Add to `mkdocs.yml` navigation
3. Test locally: `uv run mkdocs serve -f bindings/python/mkdocs.yml` (from the repository root)
4. Submit PR

### Updating Dependencies

```bash
# Upgrade the dev environment to the latest allowed versions
uv lock --upgrade && uv sync

# Runtime deps of the package itself (e.g. jpype1) are declared in
# bindings/python/pyproject.toml [project.dependencies]; edit by hand

# Update in pyproject.toml
[project]
dependencies = [
    "jpype1>=1.5.0",  # Update version
]
```

A test dependency goes in three places: the `test` extra in `bindings/python/pyproject.toml`,
the install step in `.github/workflows/test-python-bindings.yml`, and the dependencies of the
repo-root `pyproject.toml`. The `dependency-floors` CI job resolves the declared floors with
`--resolution lowest-direct` for every Python version in the classifiers and runs `pip-audit`
on the result, so a floor that admits a vulnerable release fails it.

## Troubleshooting

### JVM Errors

The package always starts its bundled JRE (`jvm.py` loads the JVM library from the
wheel's `jre/` directory), so the system `java` and `JAVA_HOME` play no part at
runtime. If the JVM fails to start:

- Rebuild or reinstall the wheel, in case the bundled JRE is incomplete
- Check the options passed to `start_jvm()`, `jvm_kwargs`, or `ARCADEDB_JVM_ARGS`
- Remember that JVM options are fixed once the JVM is running; start a new process
  to change them

A JDK 25 or later is only needed to build native macOS and Windows wheels.

### Build Errors

```bash
# Clean build artifacts (from bindings/python)
rm -rf dist/ build/ src/*.egg-info local-jars/ .runtime-cache/

# Remove cached JARs and JRE (a native build reuses an existing jars/ directory,
# whatever its version)
rm -rf src/arcadedb_embedded/jars/
rm -rf src/arcadedb_embedded/jre/

# Rebuild
./scripts/build.sh
```

After deleting `dist/`, rebuild before the next `uv run` or `uv sync`: the repo-root
environment installs the package from there.

### Test Failures

```bash
# Run specific test with verbose output (from the repository root)
uv run pytest bindings/python/tests/test_core.py::test_database_creation -vv

# Run with debugging
uv run pytest --pdb bindings/python/tests/test_core.py

# Check test coverage
uv run pytest --cov=arcadedb_embedded --cov-report=term-missing
```

### Docker Issues

```bash
# Clear Docker's build cache (unlike `docker system prune -a`, this keeps your images)
docker builder prune

# Rebuild
./scripts/build.sh
```

## Getting Help

- **Documentation**: [https://docs.humem.ai/arcadedb/](https://docs.humem.ai/arcadedb/)
- **GitHub Issues**: [https://github.com/humemai/arcadedb-embedded-python/issues](https://github.com/humemai/arcadedb-embedded-python/issues)

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## See Also

- [Architecture](architecture.md) - System architecture
- [Troubleshooting](troubleshooting.md) - Common issues
- [API Reference](../api/database.md) - API documentation
