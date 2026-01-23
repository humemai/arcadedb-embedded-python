# ArcadeDB Python Bindings

Native Python bindings for ArcadeDB - the multi-model database that supports Graph, Document, Key/Value, Search Engine, Time Series, and Vector models.

**Status**: ✅ Production Ready | **Tests**: 252 Passing | **Platforms**: 6 Supported

---

## 📚 Documentation

**[📖 Read the Full Documentation →](https://humemai.github.io/arcadedb-embedded-python/latest)**

Quick links:

- [Installation Guide](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/)
- [Quick Start Tutorial](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/quickstart/)
- [User Guide](https://humemai.github.io/arcadedb-embedded-python/latest/guide/core/database/)
- [API Reference](https://humemai.github.io/arcadedb-embedded-python/latest/api/database/)
- [Examples](https://humemai.github.io/arcadedb-embedded-python/latest/examples/)

---

## 🚀 Quick Start

### Installation

```bash
uv pip install arcadedb-embedded
```

**Requirements:**

- **Python 3.10–3.14** (packaged/tested on CPython 3.12) - No Java installation required!
- **Supported Platforms**: Prebuilt wheels for **6 platforms**
  - Linux: x86_64, ARM64
  - macOS: Intel (x86_64), Apple Silicon (ARM64)
  - Windows: x86_64, ARM64
- **Development version**: Use `--pre` flag to install `.devN` versions

!!! tip "Development Releases"
We publish development versions (`X.Y.Z.devN`) for every push to main when `pom.xml` contains a SNAPSHOT version. These are great for testing new features but may be unstable. [Learn more](DEV_RELEASE_STRATEGY.md)

### 5-Minute Example

```python
import arcadedb_embedded as arcadedb

# Create database (context manager for automatic open and close)
with arcadedb.create_database("./mydb") as db:
  # Create schema (schema ops are auto-transactional)
  db.schema.create_document_type("Person")
  db.schema.create_property("Person", "name", "STRING")
  db.schema.create_property("Person", "age", "INTEGER")

    # Insert data (requires transaction)
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")

    # Query data
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")

  # SQL also works (useful when talking to a remote server),
  # but the embedded API above is preferred for local use.
```

**[👉 See full tutorial](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/quickstart/)**

---

## ✨ Features

- ☕ **No Java Installation Required**: Bundled JRE (~249MB uncompressed)
- 🌍 **6 Platforms Supported**: Linux, macOS, Windows (x86_64 + ARM64)
- 🚀 **Embedded Mode**: Direct database access in Python process (no network)
- 🌐 **Server Mode**: Optional HTTP server with Studio web interface
- 📦 **Self-contained**: All dependencies bundled (~116MB wheel)
- 🔄 **Multi-model**: Graph, Document, Key/Value, Vector, Time Series
- 🔍 **Multiple query languages**: SQL, OpenCypher, MongoDB
- ⚡ **High performance**: Direct JVM integration via JPype
- 🔒 **ACID transactions**: Full transaction support
- 🎯 **Vector storage**: Store and query vector embeddings with HNSW (JVector) indexing
- 📥 **Data import**: Built-in CSV and ArcadeDB JSONL import

---

## 📦 What's Inside

The `arcadedb-embedded` package is platform-specific and self-contained:

**Package Contents (all platforms, ballpark):**

- **Wheel size (compressed)**: ~116MB
- **ArcadeDB JARs (uncompressed)**: ~32MB
- **Bundled JRE (uncompressed)**: ~249MB (platform-specific Java 25 runtime via jlink)
- **Total uncompressed size**: ~281MB

**Note**: Some JARs are excluded to optimize package size (e.g., gRPC wire protocol). See `jar_exclusions.txt` for details.

Import: `import arcadedb_embedded as arcadedb`

---

## 🧪 Testing

**Status**: 252 tests + 7 example scripts passing on all 6 platforms

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_core.py -v
```

See [tests/README.md](tests/README.md) for detailed test documentation.

---

## 🔧 Building from Source

**Requirements vary by platform:**

- **Linux**: Docker (handles all dependencies)
- **macOS/Windows**: Java 25+ JDK with jlink (to build the bundled JRE)

### Setup Virtual Environment

First, create and activate a Python virtual environment:

```bash
cd bindings/python/

# Create virtual environment
python3 -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Install build and test dependencies
uv pip install build
uv pip install -e ".[test]"
```

### Build the Package

```bash
# Build for your current platform (auto-detected)
./build.sh

# Build for specific platform
./build.sh linux/amd64    # Requires Docker
./build.sh darwin/arm64   # Requires Java JDK (native build)
./build.sh windows/arm64  # Requires Java JDK (native build)
# etc.
```

### Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_core.py -v
```

Built wheels will be in `dist/`. **[Build instructions](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#building-from-source)**

**Supported platforms:**

- `linux/amd64` (Docker build on native x64 runner)
- `linux/arm64` (Docker build on native ARM64 runner)
- `darwin/amd64` (Native build on macOS Intel)
- `darwin/arm64` (Native build on macOS Apple Silicon)
- `windows/amd64` (Native build on Windows x64)
- `windows/arm64` (Native build on Windows ARM64)

> **Developer Note:** See [docs/development/build-architecture.md](docs/development/build-architecture.md) for comprehensive documentation of the multi-platform build architecture, including how we achieve platform-specific JRE bundling across all 6 platforms on GitHub Actions.

## Development

!!! note "Package Contents"
The package includes optimized ArcadeDB JARs. Some components are excluded for size optimization - see `jar_exclusions.txt` for details.

!!! note "Versioning"
Versions are automatically extracted from the main ArcadeDB `pom.xml`. See [versioning strategy](https://humemai.github.io/arcadedb-embedded-python/latest/development/release/#python-versioning-strategy) for details on development vs release mode handling.

---

## 📋 Package Structure

```text
arcadedb_embedded/
├── __init__.py          # Public API exports
├── core.py              # Database and DatabaseFactory
├── server.py            # ArcadeDBServer for HTTP mode
├── results.py           # ResultSet and Result wrappers
├── transactions.py      # TransactionContext manager
├── schema.py            # Schema management API
├── vector.py            # Vector search and HNSW (JVector) indexing
├── importer.py          # Data import (CSV, JSONL)
├── exporter.py          # Data export (JSONL, GraphML, GraphSON, CSV)
├── batch.py             # Batch operations context
├── async_executor.py    # Asynchronous query execution
├── type_conversion.py   # Python-Java type conversion utilities
├── exceptions.py        # ArcadeDBError exception
├── jvm.py               # JVM lifecycle management
└── _version.py          # Package version info
```

**[Architecture details](https://humemai.github.io/arcadedb-embedded-python/latest/development/architecture/)**

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) and our [development guide](https://humemai.github.io/arcadedb-embedded-python/latest/development/contributing/).

---

## 📄 License

Apache License 2.0 - see [LICENSE](../../LICENSE)

---

## 🔗 Links

- **Documentation**: <https://humemai.github.io/arcadedb-embedded-python/latest/>
- **PyPI**: <https://pypi.org/project/arcadedb-embedded/>
- **GitHub**: <https://github.com/humemai/arcadedb-embedded-python>
- **ArcadeDB Main Docs**: <https://docs.arcadedb.com>
- **Issues**: <https://github.com/humemai/arcadedb-embedded-python/issues>

---

## Community

Made with ❤️ by the ArcadeDB community
