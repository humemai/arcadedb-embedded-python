# ArcadeDB Python Bindings

Native Python bindings for ArcadeDB - the multi-model database that supports Graph, Document, Key/Value, Search Engine, Time Series, and Vector models.

**Status**: ✅ Production Ready | **Tests**: 43/43 Passing (100%)

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
# Install arcadedb-embedded with bundled JRE - No Java installation required!
pip install arcadedb-embedded

# Development version (latest features, may be unstable)
pip install --pre arcadedb-embedded
```

**Requirements:**

- **Python 3.8+ only** - No Java installation required!
- **Development version**: Use `--pre` flag to install `.devN` versions

!!! tip "Development Releases"
    We publish development versions (`X.Y.Z.devN`) for every push to main when `pom.xml` contains a SNAPSHOT version. These are great for testing new features but may be unstable. [Learn more](DEV_RELEASE_STRATEGY.md)

### 5-Minute Example

```python
import arcadedb_embedded as arcadedb

# Create database (context manager for automatic cleanup)
with arcadedb.create_database("/tmp/mydb") as db:
    # Create schema
    db.command("sql", "CREATE DOCUMENT TYPE Person")

    # Insert data (requires transaction)
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")

    # Query data
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get_property('name')}")
```

**[👉 See full tutorial](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/quickstart/)**

---

## ✨ Features

- ☕ **No Java Installation Required**: Bundled JRE (~39MB compressed) included
- 🚀 **Embedded Mode**: Direct database access in Python process (no network)
- 🌐 **Server Mode**: Optional HTTP server with Studio web interface
- 📦 **Self-contained**: All dependencies bundled (162MB wheel: 123MB JARs + 39MB JRE)
- 🔄 **Multi-model**: Graph, Document, Key/Value, Vector, Time Series
- 🔍 **Multiple query languages**: SQL, Cypher, Gremlin, MongoDB
- ⚡ **High performance**: Direct JVM integration via JPype
- 🔒 **ACID transactions**: Full transaction support
- 🎯 **Vector storage**: Store and query vector embeddings with HNSW indexing
- 📥 **Data import**: Built-in CSV, JSON, Neo4j importers

---

## 📦 What's Inside

The `arcadedb-embedded` package (162MB wheel, ~240MB installed) includes everything you need:

- **ArcadeDB JARs** (~123MB): Core database engine with all features
- **Bundled JRE** (~39MB): Custom Java 21 runtime (jlink, 21 modules)
- **Total:** 162MB compressed wheel, ~240MB when installed

**Note**: Some JARs are excluded to optimize package size. See `jar_exclusions.txt` for details.

Import: `import arcadedb_embedded as arcadedb`

---

## 🧪 Testing

**Status**: 43/43 tests passing (100%)

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_core.py -v
```

See [tests/README.md](tests/README.md) for detailed test documentation.

---

## 🔧 Building from Source

**Docker required** - it handles all dependencies (Java, Maven, Python build tools):

```bash
cd bindings/python/

# Build for your current platform (auto-detected)
./build.sh

# Build for specific platform
./build.sh linux/amd64
./build.sh darwin/arm64
# etc.
```

Built wheels will be in `dist/`. **[Build instructions](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#building-from-source)**

Supported platforms: `linux/amd64`, `linux/arm64`, `darwin/amd64`, `darwin/arm64`, `windows/amd64`

> **Note:** `linux/arm64` uses QEMU emulation for builds. Additional platforms like `windows/arm64` may be added in future releases if demand justifies it.

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
├── vector.py            # Vector search and HNSW indexing
├── importer.py          # Data import (CSV, JSON, Neo4j)
├── exceptions.py        # ArcadeDBError exception
└── jvm.py              # JVM lifecycle management
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
