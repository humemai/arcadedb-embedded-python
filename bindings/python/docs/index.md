# ArcadeDB Python Bindings

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Production Ready**

    ---

    Native Python bindings for ArcadeDB with comprehensive embedded/server coverage

    - **Status**: ✅ Production Ready
    - **Tests**: ✅ Full suite green on every platform build

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

### Embedded Engine (DSL-first)

- **Direct JVM Integration**: Run database directly in your Python process via JPype
- **Best Performance**: No network overhead, direct method calls
- **Use Cases**: Single-process applications, high-performance scenarios
- **Recommended style**: SQL/OpenCypher via `db.command(...)` and `db.query(...)`
- **Example**:
    ```python
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice'")
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
        "http://localhost:2480/api/v1/query/mydb",
        json={"language": "sql", "command": "SELECT FROM Person"},
        auth=HTTPBasicAuth("root", "password"),
        timeout=30,
    )
    ```
    For many small calls, or large results, the client library and the protocol matter:
    see [Choosing a Protocol from Python](guide/server.md#choosing-a-protocol-from-python).

Both APIs can be used **simultaneously** on the same server instance; see
[Access Methods](api-access-methods.md) and [Server Mode](guide/server.md).

!!! info "When to run the official server distribution instead"
    In-process server mode ties the server's lifetime to your Python process.
    For a database that outlives any one client, or for HA/replication and TLS,
    run the standalone [ArcadeDB server](https://docs.arcadedb.com/#Server).

## Current Ingest Guidance

The bindings are SQL/Cypher-first, but the recommended ingest path depends on what you
are doing.

- For normal application code, prefer SQL/OpenCypher through `db.command(...)` and
    `db.query(...)`.
- For file-driven imports or restore flows, use SQL `IMPORT DATABASE` or the narrow
    `db.import_documents(...)` wrapper when you specifically need document-file import.
- For bulk document ingest from Python, prefer `db.insert_many(...)` for rows and
    `db.insert_columns(...)` for data that already lives in columns. They cross the FFI
    boundary once per batch and once per column.
- For bulk graph ingest from Python, prefer `GraphBatch`.
- Do not use the async executor's SQL command path (`async_executor().command(...)`) for
    bulk writes.

The measurements and the reasons are in the
[Bulk Ingest Recommendation](guide/import.md#bulk-ingest-recommendation).

## Features

<div class="grid" markdown>

!!! success "Core Features"
    - 🚀 **Embedded Mode** - Direct database access in Python process
    - 🌐 **Server Mode** - Optional in-process HTTP server with Studio UI
    - 📦 **Self-contained** - All JARs and JRE bundled
    - 🔄 **Multi-model** - Graph, Document, Key/Value, Vector, Time Series
    - 🔍 **Multiple languages** - SQL and OpenCypher

!!! success "Advanced Features"
    - ⚡ **High performance** - Direct JVM integration via JPype
    - 🔒 **ACID transactions** - durable to a process crash by default, to a power cut with `arcadedb.txWalFlush=1` (see [Durability](guide/core/transactions.md#durability-what-a-commit-survives))
    - 🎯 **Vector storage** - HNSW (JVector) indexing for embeddings
    - 📥 **Data import** - CSV, XML, and ArcadeDB JSONL
    - 🔎 **Full-text search** - Lucene integration

</div>

## Quick Example

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")

    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)

    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")
```

!!! tip "Resource Management"
    Always use context managers (`with` statements) for automatic resource cleanup!

## Package Coverage

These bindings cover the parts of ArcadeDB's Java API most relevant to Python
developers:

| Module | Status | Description |
|--------|--------|-------------|
| Core Operations | ✅ Supported | Database, queries, transactions |
| Schema Management | ✅ Supported | Types, properties, indexes |
| Server Mode | ✅ Supported | HTTP server, Studio UI, database management |
| Vector Search | ✅ Supported | HNSW (JVector) indexing, similarity search |
| Data Import | ✅ Supported | CSV, XML, and ArcadeDB JSONL |
| Data Export | ✅ Supported | JSONL; CSV for query results |
| Graph API | ✅ Supported | SQL and OpenCypher, plus record wrappers |

See [Java API Coverage](java-api-coverage.md) for detailed comparison.

## Benchmarks

ArcadeDB is measured against the engines you would otherwise reach for, on one machine, one
job at a time, with every timed query's answer compared across engines before any latency is
published. The results live on the
[project page](https://humem.ai/projects/arcadedb); the
[Benchmarks](benchmarks/index.md) section documents the protocol, the answer checking, how
to run a lane yourself, and how to read the output.

## Distribution

We provide a **single, self-contained package** that works on all major platforms:

| Platforms | Package Name | Size | What's Included |
|----------|-------------|------|-----------------|
| linux/amd64, linux/arm64, darwin/arm64, windows/amd64 | `arcadedb-embedded` | ~69 MiB wheel, ~97 MiB installed | Full ArcadeDB + Bundled JRE + Studio UI |

The package uses the standard import:

```python
import arcadedb_embedded as arcadedb
```

!!! success "No Java Installation Required!"
    The package includes a bundled Java 25 Runtime Environment (JRE) optimized for ArcadeDB.
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

- **Python**: 3.10 to 3.14 (CI runs all five on every supported platform)
- **OS**: Linux (x86_64, ARM64), macOS (Apple Silicon), or Windows (x86_64)

## Community & Support

- **PyPI**: [arcadedb-embedded](https://pypi.org/project/arcadedb-embedded/)
- **GitHub**: [humemai/arcadedb-embedded-python](https://github.com/humemai/arcadedb-embedded-python)
- **Issues**: [Report bugs](https://github.com/humemai/arcadedb-embedded-python/issues)
- **ArcadeDB Docs**: [docs.arcadedb.com](https://docs.arcadedb.com)

## License

Both upstream ArcadeDB (Java) and this ArcadeDB Embedded Python project are licensed under Apache 2.0, fully open and free for everyone, including commercial use.
