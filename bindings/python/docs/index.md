# ArcadeDB Python Bindings

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Production Ready**

    ---

    Native Python bindings for ArcadeDB with full test coverage

    - **Status**: ✅ Production Ready
    - **Tests**: ✅ 252 + 7 Examples Passing

-   :fontawesome-brands-python:{ .lg .middle } **Pure Python API**

    ---

    Pythonic interface to ArcadeDB's multi-model database

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-graph:{ .lg .middle } **Multi-Model Database**

    ---

    Graph, Document, Key/Value, Vector, Time Series in one database

    [:octicons-arrow-right-24: Learn More](guide/core/database.md)

-   :material-lightning-bolt:{ .lg .middle } **High Performance**

    ---

    Direct JVM integration via JPype for maximum speed

    [:octicons-arrow-right-24: Architecture](development/architecture.md)

</div>

## What is ArcadeDB?

ArcadeDB is a next-generation multi-model database that supports:

- **Graph**: Native property graphs with vertices and edges
- **Document**: Schema-less JSON documents
- **Key/Value**: Fast key-value pairs
- **Vector**: Embeddings with HNSW (JVector) similarity search
- **Time Series**: Temporal data with efficient indexing
- **Search Engine**: Full-text search with Lucene

## Why Python Bindings?

These bindings provide native Python access to ArcadeDB's full capabilities with **two
access methods**:

### Java API (Embedded Mode)

- **Direct JVM Integration**: Run database directly in your Python process via JPype
- **Best Performance**: No network overhead, direct method calls
- **Use Cases**: Single-process applications, high-performance scenarios
- **Example**:
  ```python
  with db.transaction():
      vertex = db.new_vertex("Person")
      vertex.set("name", "Alice")
      vertex.save()
  ```

### HTTP API (Server Mode)

- **Remote Access**: HTTP REST endpoints when server is running
- **Multi-Language**: Any language can connect via HTTP
- **Use Cases**: Multi-process applications, web services, remote access
- **Example**:
  ```python
  import requests
  from requests.auth import HTTPBasicAuth

  requests.post(
      "http://localhost:2480/api/v1/command/mydb",
      json={"language": "sql", "command": "SELECT FROM Person"},
            auth=HTTPBasicAuth("root", "password"),
            timeout=30,
  )
  ```

Both APIs can be used **simultaneously** on the same server instance.

## Additional Features

- **Multiple Query Languages**: SQL, OpenCypher, MongoDB syntax
- **ACID Transactions**: Full transactional guarantees
- **Type Safety**: Pythonic API with proper error handling

## Features

<div class="grid" markdown>

!!! success "Core Features"
    - 🚀 **Embedded Mode** - Direct database access in Python process
    - 🌐 **Server Mode** - Optional HTTP server with Studio UI
    - 📦 **Self-contained** - All JARs and JRE bundled
    - 🔄 **Multi-model** - Graph, Document, Key/Value, Vector
    - 🔍 **Multiple languages** - SQL, OpenCypher, MongoDB

!!! success "Advanced Features"
    - ⚡ **High performance** - Direct JVM integration via JPype
    - 🔒 **ACID transactions** - Full transaction support
    - 🎯 **Vector storage** - HNSW (JVector) indexing for embeddings
    - 📥 **Data import** - CSV and ArcadeDB JSONL
    - 🔎 **Full-text search** - Lucene integration

</div>

## Quick Example

```python
import arcadedb_embedded as arcadedb

# Create database (context manager for automatic open and close)
with arcadedb.create_database("./mydb") as db:
    # Create schema (auto-transactional)
    db.schema.create_document_type("Person")

    # Insert data (requires transaction)
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice")
        person.set("age", 30)
        person.save()

    # Query data
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")

    # db.drop()  # Permanently deletes the database
```

!!! tip "Resource Management"
    Always use context managers (`with` statements) for automatic resource cleanup!

## Package Coverage

These bindings provide **comprehensive coverage** of ArcadeDB's Java API, focusing on
features most relevant to Python developers:

| Module | Coverage | Description |
|--------|----------|-------------|
| Core Operations | ✅ 100% | Database, queries, transactions |
| Schema Management | ✅ 100% | Types, properties, indexes |
| Server Mode | ✅ 90% | HTTP server, Studio UI, database management |
| Vector Search | ✅ 100% | HNSW (JVector) indexing, similarity search |
| Data Import | ⚠️ 70% | CSV and ArcadeDB JSONL (XML support limited, not recommended) |
| Data Export | ✅ 100% | JSONL, GraphML, GraphSON, CSV |
| Graph API | ✅ 85% | Full support via SQL and OpenCypher |

See [Java API Coverage](java-api-coverage.md) for detailed comparison.

## Distribution

We provide a **single, self-contained package** that works on all major platforms:

| Platform | Package Name | Size | What's Included |
|----------|-------------|------|-----------------|
| **All Platforms** | `arcadedb-embedded` | ~209-215MB | Full ArcadeDB + Bundled JRE + Studio UI |

The package uses the standard import:

```python
import arcadedb_embedded as arcadedb
```

!!! success "No Java Installation Required!"
    The package includes a bundled Java 21 Runtime Environment (JRE) optimized for ArcadeDB.
    You do **not** need to install Java separately on your system.

## Getting Started

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } [**Install**](getting-started/installation.md)

    Installation instructions

-   :material-run-fast:{ .lg .middle } [**Quick Start**](getting-started/quickstart.md)

    Get up and running in 5 minutes

-   :material-book-open-variant:{ .lg .middle } [**User Guide**](guide/core/database.md)

    Comprehensive guide to all features

-   :material-api:{ .lg .middle } [**API Reference**](api/database.md)

    Detailed API documentation

</div>

## Requirements

- **Python**: 3.10–3.14 (packaged; primary testing on 3.12)
- **OS**: Linux, macOS, or Windows (x86_64 or ARM64)

!!! note "Self-Contained"
    Everything needed to run ArcadeDB is included in the wheel: **Bundled JRE**
    (Platform-specific Java 21 runtime, ~63MB), **ArcadeDB JARs** (Core database engine,
    ~226MB), **JPype** (Bridge between Python and the bundled JVM).

## Community & Support

- **PyPI**: [arcadedb-embedded](https://pypi.org/project/arcadedb-embedded/)
- **GitHub**: [humemai/arcadedb-embedded-python](https://github.com/humemai/arcadedb-embedded-python)
- **Issues**: [Report bugs](https://github.com/humemai/arcadedb-embedded-python/issues)
- **ArcadeDB Docs**: [docs.arcadedb.com](https://docs.arcadedb.com)

## License

Apache License 2.0 - see [LICENSE](https://github.com/humemai/arcadedb-embedded-python/blob/main/LICENSE)
