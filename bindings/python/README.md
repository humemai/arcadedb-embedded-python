# ArcadeDB Python Bindings

Native Python bindings for ArcadeDB - the multi-model database that supports Graph, Document, Key/Value, Search Engine, Time Series, and Vector models.

**Status**: ✅ Production Ready | **Tests**: 43/43 Passing (100%)

---

## 📚 Documentation

**[📖 Read the Full Documentation →](https://humemai.github.io/arcadedb-embedded-python/latest)**

Quick links:
- [Installation Guide](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/)
- [Quick Start Tutorial](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/quickstart/)
- [Package Variants](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/packages/)
- [User Guide](https://humemai.github.io/arcadedb-embedded-python/latest/guide/core/database/)
- [API Reference](https://humemai.github.io/arcadedb-embedded-python/latest/api/database/)
- [Examples](https://humemai.github.io/arcadedb-embedded-python/latest/examples/)

---

## 🚀 Quick Start

### Installation

Choose based on your needs:

```bash
# Main package (requires Java 21+) - Includes Studio UI and all features
pip install arcadedb-embedded

# JRE package (no Java required) - Same features with bundled JRE (coming soon)
pip install arcadedb-embedded-jre
```

**Requirements:**

- **Main package**: Java 21+ must be installed ([details](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#java-runtime-environment-jre))
- **JRE package**: No external dependencies (coming soon)

!!! tip "Eliminate JVMCI Warnings"
    See warnings about "JVMCI is not enabled"? Install [GraalVM](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#eliminate-polyglot-warnings-optional) to fix them.

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

- 🚀 **Embedded Mode**: Direct database access in Python process (no network)
- 🌐 **Server Mode**: Optional HTTP server with Studio web interface
- 📦 **Self-contained**: All dependencies bundled (~123MB, gRPC excluded)
- 🔄 **Multi-model**: Graph, Document, Key/Value, Vector, Time Series
- 🔍 **Multiple query languages**: SQL, Cypher, Gremlin, MongoDB
- ⚡ **High performance**: Direct JVM integration via JPype
- 🔒 **ACID transactions**: Full transaction support
- 🎯 **Vector storage**: Store and query vector embeddings with HNSW indexing
- 📥 **Data import**: Built-in CSV, JSON, Neo4j importers

---

## 📦 Package Options

ArcadeDB Python provides an **embedded** package that runs the database in your Python process:

| Package | Size | Java Required | Studio UI | Query Languages | Status |
|---------|------|---------------|-----------|----------------|--------|
| **arcadedb-embedded** | ~123MB | Java 21+ | ✅ | SQL, Cypher, Gremlin, MongoDB | ✅ Available |
| **arcadedb-embedded-jre** | ~170MB | ❌ | ✅ | SQL, Cypher, Gremlin, MongoDB | ⏳ Coming Soon |

Both packages include the same features. The only difference is Java runtime dependency.

**Note**: gRPC wire protocol is excluded to keep package size manageable. We may add it in future versions if needed.

All use the same import: `import arcadedb_embedded as arcadedb`

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

# Build main package
./build-all.sh base     # ~123 MB (default)

# Build with bundled JRE (coming soon)
./build-all.sh jre      # ~170 MB
```

Built wheels will be in `dist/`. **[Build instructions](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#building-from-source)**

!!! note "Package Contents"
    The package includes all ArcadeDB features except gRPC wire protocol. We don't need gRPC at this moment, and we might add it in future versions if needed.

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
- **PyPI (Main)**: <https://pypi.org/project/arcadedb-embedded/>
- **PyPI (JRE)**: <https://pypi.org/project/arcadedb-embedded-jre/> (coming soon)
- **GitHub**: <https://github.com/humemai/arcadedb-embedded-python>
- **ArcadeDB Main Docs**: <https://docs.arcadedb.com>
- **Issues**: <https://github.com/humemai/arcadedb-embedded-python/issues>

---

## Community

Made with ❤️ by the ArcadeDB community
