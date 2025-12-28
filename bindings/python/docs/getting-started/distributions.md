# Package Overview

ArcadeDB Python provides a **self-contained embedded** package that runs the database directly in your Python process with a bundled JRE - **no Java installation required!**

## The Package

| Package | Wheel Size | Installed Size | Java Required | Studio UI | Query Languages |
|---------|-----------|----------------|---------------|-----------|----------------|
| **arcadedb-embedded** | 155-161MB | ~215-230MB | ❌ No | ✅ | SQL, Cypher, Gremlin, MongoDB |

**Installation:**

```bash
# Temporarily install from GitHub Pages (awaiting PyPI size limit approval)
pip install arcadedb-embedded \
  --index-url https://humemai.github.io/arcadedb-embedded-python/simple/ \
  --extra-index-url https://pypi.org/simple/
```

**Requirements:** Python 3.8+ only - No Java installation needed!

## What's Inside

The package includes everything you need:

- **ArcadeDB JARs** (167.4MB): Core database with all features
- **Bundled JRE** (47-63MB): Platform-specific Java 21 runtime (via jlink)
- **Python Package** (~5MB): Python wrapper and utilities

**Total:** 155-161MB compressed wheel (varies by platform), ~215-230MB when installed

## Platform Support

Pre-built **platform-specific** wheels are available for **6 platforms**:

| Platform | Wheel Size | JRE Size | Installed Size | Tests |
|----------|-----------|----------|----------------|-------|
| Windows ARM64 | 155.1M | 47.3M | ~215M | 205/205 ✅ |
| macOS ARM64 (Apple Silicon) | 156.7M | 53.9M | ~221M | 205/205 ✅ |
| macOS Intel (x86_64) | 157.8M | 55.3M | ~223M | 205/205 ✅ |
| Windows x64 | 157.4M | 51.5M | ~219M | 205/205 ✅ |
| Linux ARM64 | 159.9M | 61.8M | ~229M | 205/205 ✅ |
| Linux x64 | 160.9M | 62.7M | ~230M | 205/205 ✅ |

**Key Features:**

- ✅ All platforms use **platform-specific wheels** (not universal)
- ✅ pip automatically selects the correct wheel for your system
- ✅ Each platform has its own bundled JRE optimized for that architecture
- ✅ All 6 platforms tested and verified (205/205 tests passing)
- ✅ Built on native runners (no emulation) for optimal performance

## What's Included

## What's Included

**Core Features:**

- ✅ **No Java Installation Required**: Platform-specific JRE bundled (~47-63MB)
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, Cypher, Gremlin, MongoDB (all included)
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, JSON, Neo4j importers

**Optimized:**

- Some components are excluded to optimize package size (e.g., gRPC wire protocol)
- See `jar_exclusions.txt` in the repository for details

## Test Results

**205 out of 205 tests pass** on all platforms (100% success rate):

- ✅ All core database operations
- ✅ SQL, Cypher, and Gremlin queries
- ✅ HTTP server and Studio UI
- ✅ Vector search and import operations
- ✅ All platforms validated

## Use Cases

Perfect for:

- Production Python applications
- Development and debugging (with Studio UI)
- Cloud deployments (no Java setup needed!)
- Docker containers
- Desktop applications
- Multi-model database needs (Graph, Document, Vector, Time Series)
- Any scenario requiring SQL, Cypher, or Gremlin queries

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

Total package size varies by platform: **155-161MB wheel, ~215-230MB installed**

**Common components (identical across platforms):**

- **ArcadeDB JARs**: 167.4 MB (83 files - core database, query engines, Studio UI, protocols)

**Platform-specific components:**

- **Bundled JRE**: 47-63 MB (varies by platform, see table above)
- **Python package**: ~5 MB

**Why sizes vary by platform:**

- JRE binaries differ by platform (different native code)
- ARM platforms tend to have slightly smaller JREs
- All platforms use the same JAR files (167.4MB)

**Optimizations:**

- Some components excluded for size (e.g., gRPC wire protocol ~38MB)
- See `jar_exclusions.txt` in repository for details

## Installation Tips

### Check Installed Package

```python
import arcadedb_embedded as arcadedb
print(f"Version: {arcadedb.__version__}")

# Verify database works
with arcadedb.create_database("/tmp/test") as db:
    result = db.query("sql", "SELECT 1 as test")
    print(f"Database working: {result[0].get_property('test') == 1}")
```

### Platform Detection

pip automatically selects the correct platform-specific wheel:

```bash
# On Linux x64, installs: arcadedb_embedded-X.Y.Z-py3-none-manylinux_2_17_x86_64.whl
# On macOS ARM64, installs: arcadedb_embedded-X.Y.Z-py3-none-macosx_11_0_arm64.whl
# On Windows x64, installs: arcadedb_embedded-X.Y.Z-py3-none-win_amd64.whl
# etc.
```

You can verify which platform you're on:

```python
import platform
print(f"System: {platform.system()}")
print(f"Machine: {platform.machine()}")
print(f"Python: {platform.python_version()}")
```

## Next Steps

- [Installation Guide](installation.md) - Detailed install instructions
- [Quick Start](quickstart.md) - Get started in 5 minutes
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
- [Server Mode](../guide/server.md) - Using the HTTP server with Studio UI
- [Query Languages](../guide/core/queries.md) - SQL, Cypher, and Gremlin examples
