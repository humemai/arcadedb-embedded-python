# ArcadeDB Python Bindings

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Production Ready__

    ---

    Native Python bindings for ArcadeDB with full test coverage

    **Status**: ✅ Production Ready | **Tests**: 205/205 Passing (100%)

-   :fontawesome-brands-python:{ .lg .middle } __Pure Python API__

    ---

    Pythonic interface to ArcadeDB's multi-model database

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-graph:{ .lg .middle } __Multi-Model Database__

    ---

    Graph, Document, Key/Value, Vector, Time Series in one database

    [:octicons-arrow-right-24: Learn More](guide/core/database.md)

-   :material-lightning-bolt:{ .lg .middle } __High Performance__

    ---

    Direct JVM integration via JPype for maximum speed

    [:octicons-arrow-right-24: Architecture](development/architecture.md)

</div>

## What is ArcadeDB?

ArcadeDB is a next-generation multi-model database that supports:

- **Graph**: Native property graphs with vertices and edges
- **Document**: Schema-less JSON documents
- **Key/Value**: Fast key-value pairs
- **Vector**: Embeddings with JVector similarity search
- **Time Series**: Temporal data with efficient indexing
- **Search Engine**: Full-text search with Lucene

## Why Python Bindings?

These bindings provide native Python access to ArcadeDB's full capabilities with __two access methods__:

### Java API (Embedded Mode)

- __Direct JVM Integration__: Run database directly in your Python process via JPype
- __Best Performance__: No network overhead, direct method calls
- __Use Cases__: Single-process applications, high-performance scenarios
- __Example__: `db.command("sql", "SELECT * FROM MyType")`

### HTTP API (Server Mode)

- __Remote Access__: HTTP REST endpoints when server is running
- __Multi-Language__: Any language can connect via HTTP
- __Use Cases__: Multi-process applications, web services, remote access
- __Example__: `requests.post("http://localhost:2480/api/v1/query/mydb")`

Both APIs can be used __simultaneously__ on the same server instance.

## Additional Features

- __Multiple Query Languages__: SQL, Cypher, Gremlin (full distribution), MongoDB syntax
- __ACID Transactions__: Full transactional guarantees
- __Type Safety__: Pythonic API with proper error handling

## Features

<div class="grid" markdown>

!!! success "Core Features"
    - 🚀 **Embedded Mode** - Direct database access in Python process
    - 🌐 **Server Mode** - Optional HTTP server with Studio UI
    - 📦 **Self-contained** - All JARs bundled, just needs JRE
    - 🔄 **Multi-model** - Graph, Document, Key/Value, Vector
    - 🔍 **Multiple languages** - SQL, Cypher, Gremlin, MongoDB

!!! success "Advanced Features"
    - ⚡ **High performance** - Direct JVM integration via JPype
    - 🔒 **ACID transactions** - Full transaction support
    - 🎯 **Vector storage** - JVector indexing for embeddings
    - 📥 **Data import** - CSV, JSON, Neo4j importers
    - 🔎 **Full-text search** - Lucene integration
    - 🗺️ **Geospatial** - JTS for spatial queries

</div>

## Quick Example

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

!!! tip "Resource Management"
    Always use context managers (`with` statements) for automatic resource cleanup!

## Package Coverage

These bindings provide **~85% coverage** of ArcadeDB's Java API, focusing on features most relevant to Python developers:

| Module | Coverage | Description |
|--------|----------|-------------|
| Core Operations | ✅ 100% | Database, queries, transactions |
| Server Mode | ✅ 100% | HTTP server, Studio UI |
| Vector Search | ✅ 100% | JVector indexing, similarity search |
| Data Import | ✅ 100% | CSV, JSON, Neo4j |
| Graph API | ⚠️ 60% | Basic graph operations (Python-relevant subset) |
| Gremlin | ⚠️ 70% | Query execution (full dist only) |

See [Java API Coverage](java-api-coverage.md) for detailed comparison.

## Distribution

We provide a **single, self-contained package** that works on all major platforms:

| Platform | Package Name | Size | What's Included |
|----------|-------------|------|-----------------|
| **All Platforms** | `arcadedb-embedded` | ~160MB | Full ArcadeDB + Bundled JRE + Studio UI + Gremlin |

All distributions use the same import:

```python
import arcadedb_embedded as arcadedb
```

!!! success "No Java Installation Required!"
    The package includes a bundled Java 21 Runtime Environment (JRE) optimized for ArcadeDB.
    You do **not** need to install Java separately on your system.

## Getting Started

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } [__Install__](getting-started/installation.md)

    Installation instructions for all three distributions

-   :material-run-fast:{ .lg .middle } [__Quick Start__](getting-started/quickstart.md)

    Get up and running in 5 minutes

-   :material-book-open-variant:{ .lg .middle } [__User Guide__](guide/core/database.md)

    Comprehensive guide to all features

-   :material-api:{ .lg .middle } [__API Reference__](api/database.md)

    Detailed API documentation

</div>

## Requirements

- **Python**: 3.8 - 3.12
- **OS**: Linux, macOS, or Windows (x86_64 or ARM64)

!!! note "Self-Contained"
    Everything needed to run ArcadeDB is included in the wheel.
    - **Bundled JRE**: Platform-specific Java 21 runtime (~50-60MB)
    - **ArcadeDB JARs**: Core database engine (~160MB)
    - **JPype**: Bridge between Python and the bundled JVM

## Community & Support

- **PyPI**: [arcadedb-embedded](https://pypi.org/project/arcadedb-embedded/)
- **GitHub**: [humemai/arcadedb-embedded-python](https://github.com/humemai/arcadedb-embedded-python)
- **Issues**: [Report bugs](https://github.com/humemai/arcadedb-embedded-python/issues)
- **ArcadeDB Docs**: [docs.arcadedb.com](https://docs.arcadedb.com)

## License

Apache License 2.0 - see [LICENSE](https://github.com/humemai/arcadedb-embedded-python/blob/main/LICENSE)
