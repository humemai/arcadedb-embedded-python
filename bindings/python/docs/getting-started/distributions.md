# Package Options

ArcadeDB Python provides **embedded** packages that run the database directly in your Python process via JPype. We currently offer one main package with an optional JRE variant coming soon.

## Quick Comparison

| Package | Size | Java Required | Studio UI | Query Languages | Status |
|---------|------|---------------|-----------|----------------|--------|
| **arcadedb-embedded** | ~123MB | Java 21+ | ✅ | SQL, Cypher, Gremlin, MongoDB | ✅ Available |
| **arcadedb-embedded-jre** | ~170MB | ❌ | ✅ | SQL, Cypher, Gremlin, MongoDB | ⏳ Coming Soon |

## Main Package

**Best for:** Most use cases - development and production

```bash
pip install arcadedb-embedded
```

### What's Included

- **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- **Query Languages**: SQL, Cypher, Gremlin, MongoDB
- **Studio Web UI**: Visual database explorer and query editor
- **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- **Vector Search**: HNSW indexing for embeddings
- **Data Import**: CSV, JSON, Neo4j importers

### What's NOT Included

- ❌ **gRPC Wire Protocol**: Excluded to keep package size manageable

We don't need gRPC at this moment, and we might add it in future versions if needed.

### Test Results

**43 out of 43 tests pass** (0 tests skipped):

- ✅ All core database operations work
- ✅ SQL, Cypher, and Gremlin queries work
- ✅ HTTP server and Studio UI work
- ✅ Vector search and import operations work
- ✅ All features available except gRPC

### Use Cases

- Production Python applications
- Development and debugging
- Multi-model database needs
- Graph, document, and vector applications
- Any scenario requiring SQL, Cypher, or Gremlin

### Accessing Studio UI

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

## JRE Package (Coming Soon)

**Best for:** Simplified deployment, no Java setup required

```bash
pip install arcadedb-embedded-jre
```

### Key Features

- **Same functionality** as the main package
- **Bundled JRE**: No Java installation required
- **Larger size**: ~170MB (includes ~50MB minimal JRE)
- **Platform-specific**: Separate wheels per platform (Linux, macOS, Windows)

### Use Cases

- Cloud deployments without Java dependencies
- Docker containers for minimal setup
- Desktop applications for non-developers
- Any scenario where Java setup is challenging

## Same Import for All

Regardless of package, the import is always:

```python
import arcadedb_embedded as arcadedb
```

This means you can:

- **Develop** with the main package (includes Studio UI)
- **Deploy** with either variant based on Java availability
- **Switch** between packages without code changes

## Which Package Should You Choose?

**Start with the main package:**

- Production-ready and tested
- All features included (~123MB)
- Only requires Java 21+ installed
- Available now on PyPI

**Upgrade to JRE package when available:**

- If Java installation is challenging
- For simplified Docker deployments
- Coming soon with cross-platform support

## Size Breakdown

### Main Package (~123MB)

- Core Database: ~60 MB
- Query Engines (SQL/Cypher/Gremlin): ~25 MB
- Studio UI: ~3 MB
- Wire Protocols: ~15 MB
- Dependencies: ~20 MB

### JRE Package (~170MB)

- Everything in Main Package: ~123 MB
- Bundled Minimal JRE: ~47 MB

**Note**: gRPC wire protocol (~38MB) is excluded from both packages to keep size manageable.

## Installation Tips

### Switch Packages

Uninstall the current package first:

```bash
pip uninstall arcadedb-embedded arcadedb-embedded-headless arcadedb-embedded-minimal arcadedb-embedded

# Install the new package
pip install arcadedb-embedded
```

### Check Installed Package

```python
import arcadedb_embedded as arcadedb
print(f"Version: {arcadedb.__version__}")

# Check which features are available
with arcadedb.create_database("/tmp/test") as db:
    # All query engines should be available
    result = db.query("sql", "SELECT 1")
    print("Database working correctly")
```

## Next Steps

- [Installation Guide](installation.md) - Detailed install instructions
- [Quick Start](quickstart.md) - Get started in 5 minutes
- [Server Mode](../guide/server.md) - Using the HTTP server with Studio UI
- [Query Languages](../guide/queries.md) - SQL, Cypher, and Gremlin examples
