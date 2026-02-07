# Package Overview

ArcadeDB Python provides a **self-contained embedded** package that runs the database directly in your Python process with a bundled JRE - **no Java installation required!**

## The Package

| Package | Wheel Size | Installed Size (uncompressed) | Java Required | Studio UI | Query Languages |
|---------|-----------|------------------------------|---------------|-----------|----------------|
| **arcadedb-embedded** | ~68MB | ~95MB | ❌ No | ✅ | SQL, OpenCypher, MongoDB |

**Installation:**

```bash
uv pip install arcadedb-embedded
```

**Requirements:** Python 3.10–3.14 (packaged; primary testing on 3.12) - No Java installation needed!

## What's Inside

The package includes everything you need:

- **ArcadeDB JARs** (~32MB, uncompressed): Core database with all features
- **Bundled JRE** (~60MB, uncompressed): Platform-specific Java 25 runtime (via jlink)

**Total:** ~68MB compressed wheel, ~95MB uncompressed installed size (similar across platforms)

## Platform Support

Pre-built **platform-specific** wheels are available for **4 platforms**. Sizes are consistent across platforms (see size breakdown below).

**Key Features:**

- ✅ All platforms use **platform-specific wheels** (not universal)
- ✅ uv pip automatically selects the correct wheel for your system
- ✅ Each platform has its own bundled JRE optimized for that architecture
- ✅ All supported platforms tested and verified (262/262 tests passing)
- ✅ Built on native runners (no emulation) for optimal performance

## What's Included

**Core Features:**

- ✅ **No Java Installation Required**: Platform-specific JRE bundled (~60MB uncompressed)
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher, MongoDB (all included)
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, XML, and ArcadeDB JSONL import

**Optimized:**

- Some components are excluded to optimize package size (e.g., gRPC wire protocol)
- See `jar_exclusions.txt` in the repository for details

## Test Results

**262 out of 262 tests pass** on all platforms (100% success rate):

- ✅ All core database operations
- ✅ SQL and OpenCypher queries
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
- Any scenario requiring SQL or OpenCypher queries

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

Current sizes are consistent across platforms (ballpark):

- **Wheel (compressed)**: ~68MB
- **Installed (uncompressed)**: ~95MB

**Components (uncompressed):**

- **ArcadeDB JARs**: ~31.7MB
- **Bundled JRE**: ~60MB (platform-specific Java 25 runtime via jlink)

**Optimizations:**

- Some components excluded for size (e.g., gRPC wire protocol)
- See `jar_exclusions.txt` in repository for details

## Installation Tips

### Check Installed Package

```python
import arcadedb_embedded as arcadedb
print(f"Version: {arcadedb.__version__}")

# Verify database works
with arcadedb.create_database("./test") as db:
    result = db.query("sql", "SELECT 1 as test")
    print(f"Database working: {result.first().get('test') == 1}")
```

### Platform Detection

uv pip automatically selects the correct platform-specific wheel:

```bash
# On Linux x64, installs: arcadedb_embedded-X.Y.Z-py3-none-manylinux_2_17_x86_64.whl
# On macOS ARM64, installs: arcadedb_embedded-X.Y.Z-py3-none-macosx_11_0_arm64.whl
# On Windows x86_64, installs: arcadedb_embedded-X.Y.Z-py3-none-win_amd64.whl
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
- [Query Languages](../guide/core/queries.md) - SQL and OpenCypher examples
