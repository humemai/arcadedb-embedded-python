# Contributing to ArcadeDB Python Bindings

Thank you for your interest in contributing to ArcadeDB Python bindings! This guide will help you get started with development.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/humemai/arcadedb-embedded-python.git
cd arcadedb-embedded-python/bindings/python

# Build the package (requires Docker)
./build.sh base

# Install in development mode
pip install -e .

# Run tests
pytest tests/
```

## Development Environment

### Requirements

**Required:**

- Python 3.10–3.14 (dev baseline 3.11)
- Java 21+ (JDK or JRE)
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

2. **Create Virtual Environment**

```bash
# Create venv
python -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

3. **Install Development Dependencies**

```bash
# Install package in editable mode
pip install -e ".[dev,vector]"

# Or manually install dependencies
pip install pytest pytest-cov black isort mypy numpy
```

4. **Verify Setup**

```bash
# Check Python
python --version  # Should be within 3.10–3.14

# Check Java
java -version     # Should be 21+

# Run quick test
python -c "import arcadedb_embedded; print('✅ Setup successful!')"
```

## Project Structure

```
arcadedb/bindings/python/
├── src/
│   └── arcadedb_embedded/        # Main package
│       ├── __init__.py            # Package initialization
│       ├── core.py                # Database, DatabaseFactory
│       ├── server.py              # ArcadeDBServer
│       ├── schema.py              # Schema management
│       ├── results.py             # Query result handling
│       ├── transactions.py        # Transaction management
│       ├── vector.py              # Vector search support
│       ├── importer.py            # Data import (CSV, XML)
│       ├── exporter.py            # Data export (JSONL, GraphML, etc.)
│       ├── batch.py               # Batch operations
│       ├── async_executor.py      # Async query execution
│       ├── type_conversion.py     # Python-Java type conversion
│       ├── exceptions.py          # Exception classes
│       ├── jvm.py                 # JVM startup logic
│       ├── _version.py            # Version info
│       └── jars/                  # JAR files (bundled/downloaded)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── README.md                  # Testing documentation
│   ├── test_core.py               # Core tests
│   ├── test_server.py             # Server tests
│   ├── test_schema.py             # Schema tests
│   ├── test_resultset.py          # Result handling tests
│   ├── test_importer.py           # Importer tests
│   ├── test_exporter.py           # Exporter tests
│   ├── test_vector.py             # Vector search tests
│   ├── test_vector_sql.py         # Vector SQL tests
│   ├── test_gremlin.py            # Gremlin tests
│   ├── test_batch_context.py      # Batch operations tests
│   ├── test_async_executor.py     # Async execution tests
│   ├── test_type_conversion.py    # Type conversion tests
│   ├── test_transaction_config.py # Transaction tests
│   ├── test_concurrency.py        # Concurrency tests
│   ├── test_database_utils.py     # Database utilities tests
│   ├── test_numpy_support.py      # NumPy integration tests
│   └── test_server_patterns.py    # Server pattern tests
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
│   ├── 07_stackoverflow_multimodel.py
│   ├── 08_server_mode_rest_api.py
│   ├── download_data.py           # Data download helper
│   ├── data/                      # Example datasets
│   └── benchmark-vector/          # Vector benchmark suite
├── pyproject.toml                 # Package configuration
├── setup.py                       # Setup configuration
├── setup_jars.py                  # JAR download script
├── extract_version.py             # Version extraction
├── write_version.py               # Version writing
├── jar_exclusions.txt             # JAR optimization list
├── build.sh                       # Build script
├── build-native.sh                # Native build script
├── ensure-build-tools.sh          # Build tools setup
├── Dockerfile.build               # Build container
└── mkdocs.yml                     # Documentation config
```

## Building from Source

### Docker Build (Recommended)

```bash
# Build the current package
./build.sh base

# Output: dist/*.whl
```

**What the build does:**

1. Extracts ArcadeDB version from parent `pom.xml`
2. Downloads appropriate JAR files with custom filtering
3. Packages Python code with optimized JARs (see `jar_exclusions.txt`)
4. Runs tests in isolated Docker environment
5. Creates wheel file in `dist/`

### Local Build

```bash
# Download JARs with custom filtering
python setup_jars.py

# Build wheel
python -m build

# Install locally
pip install dist/*.whl
```

### Development Install

```bash
# Install in editable mode (no wheel needed)
pip install -e .

# Changes to Python code take effect immediately
# No reinstall needed
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

# Importer
pytest tests/test_importer.py

# Gremlin tests
pytest tests/test_gremlin.py -m gremlin
```

### Test Markers

```bash
# Skip server tests
pytest -m "not server"

# Only Gremlin tests
pytest -m gremlin

# Skip Gremlin tests
pytest -m "not gremlin"
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
        with db.transaction():
            db.command("sql", "CREATE VERTEX TYPE User")

        # Verify
        result = db.query("sql", "SELECT FROM schema:types WHERE name = 'User'")
        assert result.has_next()
    finally:
        db.close()

def test_transaction_rollback(tmp_path):
    """Test transaction rollback."""
    db_path = tmp_path / "test.db"
    db = arcadedb.create_database(str(db_path))

    try:
        with db.transaction():
            db.command("sql", "CREATE VERTEX TYPE User")

        # Should rollback
        with pytest.raises(Exception):
            with db.transaction():
                db.command("sql", "INSERT INTO User SET name = 'Alice'")
                raise Exception("Force rollback")

        # Verify rollback
        result = db.query("sql", "SELECT FROM User")
        assert not result.has_next()
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
        user = db.new_vertex("User")
        user.set("name", name)
        user.set("email", email)
        user.save()

    return {
        "name": name,
        "email": email,
    }

# Bad
def create_user(db,name,email):
    user=db.new_vertex('User')  # No spaces, single quotes
    user.set('name',name)
    return user
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
def import_csv(
    db: Database,
    file_path: str,
    type_name: str,
    batch_size: int = 1000
) -> int:
    """
    Import CSV file into database.

    Args:
        db: Database instance
        file_path: Path to CSV file
        type_name: Vertex or document type name
        batch_size: Records per transaction (default: 1000)

    Returns:
        Number of records imported

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ArcadeDBError: If import fails

    Example:
        >>> db = arcadedb.open_database("./mydb")
        >>> count = import_csv(db, "users.csv", "User", batch_size=5000)
        >>> print(f"Imported {count} users")
    """
    # Implementation
    pass
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

def get_importer(self) -> Importer:
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
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve locally (hot reload)
mkdocs serve

# Build static site
mkdocs build

# Output: site/
```

### Writing Documentation

Documentation uses **Markdown** with **MkDocs Material** theme:

```markdown
# Page Title

Brief introduction to the topic.

## Section

Content here with examples.

### Code Examples

\```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")
\```

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
```

### API Documentation

Keep API reference in sync with code:

```python
# src/arcadedb_embedded/core.py
class Database:
    def query(self, language: str, command: str, params: Optional[dict] = None) -> ResultSet:
        """
        Execute a query and return results.

        Args:
            language: Query language (sql, cypher, gremlin, etc.)
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

\```python
db.query(language: str, command: str, params: Optional[dict] = None) -> ResultSet
\```

Execute a query and return results.

**Parameters:**

- `language` (str): Query language (sql, cypher, gremlin, mongodb, graphql)
- `command` (str): Query command string
- `params` (Optional[dict]): Query parameters for parameterized queries

**Returns:**

- `ResultSet`: Iterable query results

**Raises:**

- `ArcadeDBError`: If query execution fails

**Example:**

\```python
# Basic query
result = db.query("sql", "SELECT FROM User")
for user in result:
    print(user.get("name"))

# Parameterized query
result = db.query("sql",
    "SELECT FROM User WHERE age > :min_age",
    {"min_age": 18}
)
\```
````

## Pull Request Process

### 1. Fork and Clone

```bash
# Fork on GitHub first
git clone https://github.com/YOUR_USERNAME/arcadedb.git
cd arcadedb/bindings/python

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
git commit -m "Add vector search distance function parameter

- Added distance_function parameter to create_vector_index()
- Supports cosine, euclidean, and inner_product
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
python extract_version.py
```

2. **Build Package**

```bash
# Build the package
./build.sh base

# Verify wheels
ls -lh dist/
```

3. **Test Installation**

```bash
# Test the wheel
pip install dist/arcadedb_embed-*.whl
python -c "import arcadedb_embedded; print('✅ Package OK')"
```

4. **Publish to PyPI**

```bash
# Install twine
pip install twine

# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Test install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ arcadedb-embedded

# Upload to production PyPI
twine upload dist/*
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
# Update JPype
pip install --upgrade jpype1

# Update dev dependencies
pip install --upgrade pytest black mypy

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
java -version  # Must be 21+

# Set JAVA_HOME
export JAVA_HOME=/path/to/jdk-21
```

### Build Errors

```bash
# Clean build artifacts
rm -rf dist/ build/ *.egg-info

# Remove cached JARs and JRE
rm -rf src/arcadedb_embedded/jars/
rm -rf src/arcadedb_embedded/jre/

# Rebuild
./build.sh
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
docker build --no-cache -f Dockerfile.build ../..
```

## Getting Help

- **Documentation**: [https://docs.arcadedb.com](https://docs.arcadedb.com)
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
