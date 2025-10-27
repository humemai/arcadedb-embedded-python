# ArcadeDB Python Bindings

> **Python bindings for [ArcadeDB](https://github.com/ArcadeData/arcadedb)** - A multi-model database supporting Graph, Document, Key/Value, Vector, and Time Series models with extreme performance.

[![PyPI - Base](https://img.shields.io/badge/PyPI-arcadedb--embedded-blue)](https://pypi.org/project/arcadedb-embedded/)
[![PyPI - JRE](https://img.shields.io/badge/PyPI-arcadedb--embedded--jre-blue)](https://pypi.org/project/arcadedb-embedded-jre/)
[![Tests](https://img.shields.io/badge/tests-43%2F43%20passing-brightgreen)](https://github.com/humemai/arcadedb-embedded-python/actions)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

**📖 [Documentation](https://humemai.github.io/arcadedb-embedded-python/) | 🐛 [Issues](https://github.com/humemai/arcadedb-embedded-python/issues)**

---

## Quick Start

### Installation

```bash
pip install arcadedb-embedded        # Requires Java 21+
pip install arcadedb-embedded-jre  # With bundled JRE (coming soon)

**Requirements:**

- **Main package:** Python 3.8+ and [Java 21+](https://adoptium.net/) (JRE)
- **JRE package:** Python 3.8+ only (JRE bundled)

**💡 Tip:** See "JVMCI is not enabled" warnings? Install [GraalVM](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/installation/#eliminate-polyglot-warnings-optional) to fix them

**Technology:** Uses [JPype](https://jpype.readthedocs.io/) to bridge Python and Java, providing direct access to ArcadeDB's embedded engine with minimal overhead.

### Basic Usage (CRUD)

```python
import arcadedb_embedded as arcadedb

# Create database
with arcadedb.create_database("/tmp/mydb") as db:

    # CREATE: Define schema
    db.command("sql", "CREATE DOCUMENT TYPE Person")

    # CREATE: Insert data (requires transaction)
    with db.transaction():
        db.command("sql", """
            INSERT INTO Person SET name = 'Alice', age = 30, city = 'NYC'
        """)
        db.command("sql", """
            INSERT INTO Person SET name = 'Bob', age = 25, city = 'LA'
        """)

    # READ: Query data
    result = db.query("sql", "SELECT FROM Person WHERE age > 20")
    for record in result:
        print(f"{record.get_property('name')} - {record.get_property('age')}")

    # UPDATE: Modify records
    with db.transaction():
        db.command("sql", "UPDATE Person SET age = 31 WHERE name = 'Alice'")

    # DELETE: Remove records
    with db.transaction():
        db.command("sql", "DELETE FROM Person WHERE name = 'Bob'")
```

### Graph Example

```python
# Create graph schema
db.command("sql", "CREATE VERTEX TYPE User")
db.command("sql", "CREATE EDGE TYPE Follows")

# Insert vertices and edges
with db.transaction():
    db.command("sql", "CREATE VERTEX User SET name = 'Alice'")
    db.command("sql", "CREATE VERTEX User SET name = 'Bob'")
    db.command("sql", """
        CREATE EDGE Follows
        FROM (SELECT FROM User WHERE name = 'Alice')
        TO (SELECT FROM User WHERE name = 'Bob')
    """)

# Query graph
result = db.query("sql", """
    SELECT expand(out('Follows')) FROM User WHERE name = 'Alice'
""")
```

### Vector Search Example

```python
# Create vector index
db.command("sql", "CREATE VERTEX TYPE Document")
db.command("sql", """
    CREATE PROPERTY Document.embedding ARRAY OF DOUBLE
""")
db.command("sql", """
    CREATE VECTOR INDEX Document_embedding
    ON Document(embedding)
    HNSW M 16, EF_CONSTRUCTION 128
""")

# Insert vectors
with db.transaction():
    db.command("sql", """
        CREATE VERTEX Document
        SET text = 'Hello world', embedding = [0.1, 0.2, 0.3]
    """)

# Search by vector similarity
result = db.query("sql", """
    SELECT FROM Document
    ORDER BY embedding <-> [0.1, 0.2, 0.4]
    LIMIT 5
""")
```

**📚 [More Examples](https://humemai.github.io/arcadedb-embedded-python/latest/examples/) | [Full Tutorial](https://humemai.github.io/arcadedb-embedded-python/latest/getting-started/quickstart/)**

---

## Features

✅ **Embedded Mode** - Runs in your Python process (no server needed)
✅ **Multi-Model** - Graph, Document, Key/Value, Vector, Time Series
✅ **Query Languages** - SQL, Cypher, Gremlin, MongoDB (all included)
✅ **ACID Transactions** - Full transactional support
✅ **Vector Search** - HNSW indexing for embeddings
✅ **Studio UI** - Web-based database browser (included)
✅ **Self-Contained** - All dependencies bundled (123MB, gRPC excluded)
✅ **Production Ready** - 43/43 tests passing, actively maintained

---

## Package Variants

| Package | Size | Java Required | Studio UI | Use Case |
|---------|------|---------------|-----------|----------|
| **arcadedb-embedded** | ~123MB | Java 21+ | ❌ | Optimized deployment |
| **arcadedb-embedded-jre** | ~170MB | None | ✅ | Simplified deployment |

Both packages include the same features: SQL, Cypher, Gremlin, Studio UI, and all core functionality except gRPC wire protocol.
The only difference is Java runtime dependency.

All packages use the same import: `import arcadedb_embedded as arcadedb`

---

## About ArcadeDB

**[ArcadeDB](https://github.com/ArcadeData/arcadedb)** is a high-performance multi-model database that supports:

- **Data Models:** Graph, Document, Key/Value, Vector, Time Series
- **Query Languages:** SQL, Cypher, Gremlin, MongoDB, GraphQL
- **Architecture:** ACID transactions, native graph engine, full-text search
- **Performance:** Millions of records/second with minimal resources

This fork provides **embedded Python bindings** using JPype to bridge Python and the Java-based ArcadeDB engine.

**Main ArcadeDB Resources:**

- 📖 [Official Documentation](https://docs.arcadedb.com)
- 🐳 [Docker Images](https://hub.docker.com/r/arcadedata/arcadedb)
- 💬 [Community Discord](https://discord.gg/w2Npx2B7hZ)
- 🔧 [Upstream Repository](https://github.com/ArcadeData/arcadedb)

---

## Contributing

**Python Bindings:** Issues and PRs welcome at [this repository](https://github.com/humemai/arcadedb-embedded-python/issues)
**Main ArcadeDB:** Contribute to the [upstream project](https://github.com/ArcadeData/arcadedb)

---

## License

Apache License 2.0 - See [LICENSE](LICENSE)

Built on [ArcadeDB](https://arcadedb.com) | Python bindings by [HumemAI](https://humem.ai)
