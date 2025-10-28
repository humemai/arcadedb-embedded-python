# Package Overview

ArcadeDB Python provides an **embedded** package that runs the database directly in your Python process via JPype with a bundled JRE - **no Java installation required!**

## The Package

| Package | Size | Java Required | Studio UI | Query Languages |
|---------|------|---------------|-----------|----------------|
| **arcadedb-embedded** | 162MB wheel (~240MB installed) | ❌ No | ✅ | SQL, Cypher, Gremlin, MongoDB |

**Installation:**

```bash
pip install arcadedb-embedded
```

**Requirements:** Python 3.8+ only - No Java installation needed!

## What's Inside

The package (162MB wheel, ~240MB installed) includes everything you need:

- **ArcadeDB JARs** (~123MB): Core database with all features
- **Bundled JRE** (~39MB): Custom Java 21 runtime (jlink, 21 modules)
- **Total:** 162MB compressed wheel, ~240MB when installed

## Platform Support

Pre-built wheels are currently available for 4 platforms:

- **Linux**: x86-64
- **macOS**: x86-64 (Intel), ARM64 (Apple Silicon)
- **Windows**: x86-64

> **Future Platforms:** `linux/arm64` and `windows/arm64` may be added in future releases if demand justifies the additional CI infrastructure.

All platforms include a platform-specific bundled JRE - no external Java required!

## Features

## Features

**Included:**

- ✅ **No Java Installation Required**: Bundled JRE (~63MB) included
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, Cypher, Gremlin, MongoDB
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: HNSW indexing for embeddings
- ✅ **Data Import**: CSV, JSON, Neo4j importers

**Not Included:**

- ❌ **gRPC Wire Protocol**: Excluded to keep package size manageable

We don't need gRPC at this moment, and we might add it in future versions if needed.

## Test Results

**43 out of 43 tests pass** (100% success rate):

- ✅ All core database operations work
- ✅ SQL, Cypher, and Gremlin queries work
- ✅ HTTP server and Studio UI work
- ✅ Vector search and import operations work
- ✅ All features available except gRPC

## Use Cases

## Use Cases

Perfect for:

- Production Python applications
- Development and debugging
- Cloud deployments (no Java setup needed!)
- Docker containers
- Desktop applications
- Multi-model database needs
- Graph, document, and vector applications
- Any scenario requiring SQL, Cypher, or Gremlin

## Accessing Studio UI

```python
from arcadedb_embedded import create_server

# Start HTTP server with Studio UI
server = create_server("./databases")
server.start()

# Studio UI available at: http://localhost:2480
# Create databases, run queries, visualize data

# When done
server.stop()
```

!!! tip "Studio in Browser"
    Once the server starts, open your browser to `http://localhost:2480` to access the Studio UI.

## Import Statement

The import is always:

```python
import arcadedb_embedded as arcadedb
```

Simple and consistent across all platforms!

## Size Breakdown

Total package size: **162MB wheel (~240MB installed)**

- **ArcadeDB JARs**: ~123 MB (core database, query engines, Studio UI, protocols)
- **Bundled JRE**: ~39 MB (custom Java 21 runtime via jlink, 21 modules)
- **Compressed wheel**: 162 MB
- **Installed size**: ~240 MB

**Note**: gRPC wire protocol is excluded to keep package size manageable.

## Installation Tips

### Check Installed Package

```python
import arcadedb_embedded as arcadedb
print(f"Version: {arcadedb.__version__}")

# Verify database works
with arcadedb.create_database("/tmp/test") as db:
    result = db.query("sql", "SELECT 1")
    print("Database working correctly!")
```

## Next Steps

- [Installation Guide](installation.md) - Detailed install instructions
- [Quick Start](quickstart.md) - Get started in 5 minutes
- [Server Mode](../guide/server.md) - Using the HTTP server with Studio UI
- [Query Languages](../guide/queries.md) - SQL, Cypher, and Gremlin examples
