# Contributing to ArcadeDB Python Bindings

Thank you for your interest in contributing to ArcadeDB Python bindings! This guide will help you get started with development.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/humemai/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python

# Build the package (requires Docker) — also refreshes the uv env at the repo root
./scripts/build.sh

# Run tests
uv run pytest
```

## Development Environment

### Requirements

**Required:**

- Python 3.10–3.14 (dev baseline 3.12)
- Java 25+ (JDK or JRE)
- Docker (for building distributions)
- Git

**Optional:**

- pytest (testing)
- black (code formatting)
- mypy (type checking)
- mkdocs (documentation)

### Setup

1. **Clone Repository**

```bash
git clone https://github.com/humemai/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python
```

2. **Build the Wheel**

The package only works as a built wheel (it bundles the ArcadeDB JARs and a
JRE), so there is no editable install. Building also refreshes the uv dev
environment at the repo root:

```bash
./scripts/build.sh
```

3. **Verify Setup**

The dev environment is a uv project at the repo root (`pyproject.toml`); it
installs the built wheel from `dist/` plus all test/dev dependencies. There is
no virtualenv to activate — run everything through `uv run`, from anywhere in
the repo:

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
│   └── arcadedb_embedded/        # Main package
│       ├── __init__.py            # Package initialization
│       ├── _logging.py            # Internal logging helpers
│       ├── async_executor.py      # Async command/query execution
│       ├── citation.py            # Citation DOI helpers
│       ├── core.py                # Database, DatabaseFactory
│       ├── exceptions.py          # Exception classes
│       ├── exporter.py            # Data export (JSONL, GraphML, etc.)
│       ├── graph.py               # Graph wrappers
│       ├── graph_batch.py         # Bulk graph ingest helper
│       ├── importer.py            # Import helpers
│       ├── jvm.py                 # JVM startup logic
│       ├── results.py             # Query result handling
│       ├── schema.py              # Schema management
│       ├── server.py              # ArcadeDBServer
│       ├── transactions.py        # Transaction management
│       ├── type_conversion.py     # Python-Java type conversion
│       └── vector.py              # Vector search support
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── README.md                  # Testing documentation
│   ├── test_async_executor.py     # Async execution tests
│   ├── test_concurrency.py        # Concurrency tests
│   ├── test_core.py               # Core tests
│   ├── test_cypher.py             # OpenCypher tests
│   ├── test_database_utils.py     # Database utilities tests
│   ├── test_docs_examples.py      # Docs example tests
│   ├── test_exporter.py           # Exporter tests
│   ├── test_geo_predicate_sql.py  # Geospatial SQL tests
│   ├── test_graph_algorithms_sql.py # Graph algorithm SQL tests
│   ├── test_graph_api.py          # Graph API tests
│   ├── test_graph_batch.py        # GraphBatch tests
│   ├── test_hash_index_schema.py  # HASH index schema tests
│   ├── test_import_database.py    # Import database tests
│   ├── test_importer_api.py       # Import helper tests
│   ├── test_jvm_args.py           # JVM argument tests
│   ├── test_logging_helper.py     # Logging helper tests
│   ├── test_materialized_view_sql.py # Materialized view SQL tests
│   ├── test_numpy_support.py      # NumPy integration tests
│   ├── test_resultset.py          # Result handling tests
│   ├── test_schema.py             # Schema tests
│   ├── test_server.py             # Server tests
│   ├── test_server_patterns.py    # Server pattern tests
│   ├── test_timeseries_sql.py     # Timeseries SQL tests
│   ├── test_transaction_config.py # Transaction tests
│   ├── test_type_conversion.py    # Type conversion tests
│   ├── test_vector.py             # Vector search tests
│   ├── test_vector_sql.py         # Vector SQL tests
│   ├── test_vector_params_verification.py # Vector parameter validation tests
│   └── test_wheel_platform_tag.py # Wheel platform tag tests
├── docs/                          # MkDocs documentation
│   ├── getting-started/
│   ├── guide/
│   ├── api/
│   ├── examples/
│   └── development/
├── examples/                      # Example scripts
│   ├── 01_simple_document_store.py
│   ├── 02_social_network_graph.py
│   ├── 03_vector_search.py
│   ├── 04_csv_import_documents.py
│   ├── 05_csv_import_graph.py
│   ├── 06_vector_search_recommendations.py
│   ├── download_data.py           # Data download helper
│   ├── data/                      # Example datasets
│   └── scripts/                   # Example helper scripts
├── pyproject.toml                 # Package configuration
├── setup.py                       # Setup configuration
├── scripts/                       # Build and maintenance helpers
│   ├── build.sh                   # Main build entrypoint
│   ├── build-native.sh            # Native build script
│   ├── build_and_install_locally.sh # Local build + install helper
│   ├── ensure-build-tools.sh      # Build tools setup
│   ├── extract_version.py         # Version extraction
│   ├── fix_markdown.py            # Docs formatter
│   ├── jar_exclusions.txt         # JAR optimization list
│   ├── list_image_jars_by_size.sh # Image JAR inspection helper
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

1. Extracts ArcadeDB version from parent `pom.xml`
2. Downloads appropriate JAR files with custom filtering
3. Creates a bundled platform-specific JRE and stages optimized JARs (see `scripts/jar_exclusions.txt`)
4. Runs tests in isolated Docker environment
5. Creates wheel file in `dist/`

### Local Build

```bash
# Build for the current platform
./scripts/build.sh

# Or target a specific supported platform on matching native hardware
./scripts/build.sh darwin/arm64 3.12
./scripts/build.sh windows/amd64 3.12

# No install step needed — build.sh refreshes the repo-root uv env automatically
```

### Development Install

There is no editable install: the package only works as a built wheel (it
bundles the ArcadeDB JARs and a JRE that a source install lacks). After
changing Python code in `src/`, rebuild:

```bash
./scripts/build.sh   # rebuilds the wheel and refreshes the uv env
uv run pytest
```

## Running Tests

### All Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=arcadedb_embedded --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Specific Test Files

```bash
# Core functionality
pytest tests/test_core.py

# Server mode
pytest tests/test_server.py

# Import database coverage
pytest tests/test_import_database.py

# Documentation examples coverage
pytest tests/test_docs_examples.py

# OpenCypher tests
pytest tests/test_cypher.py -k cypher
```

### Test Markers

```bash
# Skip server tests
pytest -m "not server"

# Only OpenCypher tests
pytest -k cypher
```

### Writing Tests

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

- Line length: 100 characters (not 79)
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
# Format with black
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/
```

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

```bash
# Docs tooling lives in the `docs` dependency group of the repo-root uv project

# Serve locally (hot reload)
uv run --group docs mkdocs serve

# Build static site
mkdocs build

# Output: site/
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
    def query(self, language: str, command: str, params: Optional[dict] = None) -> ResultSet:
        """
        Execute a query and return results.

        Args:
            language: Query language (sql, opencypher, mongo, graphql, etc.)
            command: Query command string
            params: Optional query parameters

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
db.query(language: str, command: str, params: Optional[dict] = None) -> ResultSet
```

Execute a query and return results.

**Parameters:**

- `language` (str): Query language (sql, opencypher, mongodb, graphql)
- `command` (str): Query command string
- `params` (Optional[dict]): Query parameters for parameterized queries

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

# Add upstream
git remote add upstream https://github.com/humemai/arcadedb-embedded-python.git
```

### 2. Create Branch

```bash
# Update main
git checkout main
git pull upstream main

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
pytest

# Format code
black src/ tests/
isort src/ tests/

# Type check
mypy src/

# Build documentation
mkdocs build
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

### 7. PR Template

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

### Version Numbering

We follow ArcadeDB core version:

- Version extracted from parent `pom.xml`
- Format: `MAJOR.MINOR.PATCH`
- Example: `24.11.1`

### Creating a Release

1. **Update Version**

```bash
# Version automatically extracted during build
python scripts/extract_version.py
```

2. **Build Package**

```bash
# Build the package
./scripts/build.sh

# Verify wheels
ls -lh dist/
```

3. **Test Installation**

```bash
# Test the wheel in a throwaway env (doesn't touch the dev env)
uv run --isolated --no-project --with dist/arcadedb_embedded-*.whl \
    python -c "import arcadedb_embedded; print('✅ Package OK')"
```

4. **Publish to PyPI**

```bash
# Upload to Test PyPI first (twine runs via uvx, no install needed)
uvx twine upload --repository testpypi dist/*

# Test install from Test PyPI in a throwaway env
uv run --isolated --no-project --index https://test.pypi.org/simple/ \
    --with arcadedb-embedded python -c "import arcadedb_embedded"

# Upload to production PyPI
uvx twine upload dist/*
```

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
3. Test locally: `mkdocs serve`
4. Submit PR

### Updating Dependencies

```bash
# Upgrade the dev environment to the latest allowed versions
uv lock --upgrade && uv sync

# Runtime deps of the package itself (e.g. jpype1) are declared in
# bindings/python/pyproject.toml [project.dependencies] — edit by hand

# Update in pyproject.toml
[project]
dependencies = [
    "jpype1>=1.5.0",  # Update version
]
```

## Troubleshooting

### JVM Errors

```bash
# Check Java version
java -version  # Must be 25+

# Set JAVA_HOME
export JAVA_HOME=/path/to/jdk-25
```

### Build Errors

```bash
# Clean build artifacts
rm -rf dist/ build/ *.egg-info

# Remove cached JARs and JRE
rm -rf src/arcadedb_embedded/jars/
rm -rf src/arcadedb_embedded/jre/

# Rebuild
./scripts/build.sh
```

### Test Failures

```bash
# Run specific test with verbose output
pytest tests/test_core.py::test_create_database -vv

# Run with debugging
pytest --pdb tests/test_core.py

# Check test coverage
pytest --cov=arcadedb_embedded --cov-report=term-missing
```

### Docker Issues

```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker build --no-cache -f scripts/Dockerfile.build ../..
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
