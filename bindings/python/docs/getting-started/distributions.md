# Package Overview

ArcadeDB Python provides a **self-contained embedded** package that runs the database directly in your Python process with a bundled JRE - **no Java installation required!**

## The Package

| Package | Wheel Size | Installed Size | Java Required | Studio UI | Query Languages |
|---------|-----------|----------------|---------------|-----------|----------------|
| **arcadedb-embedded** | ~209-215MB | ~274-289MB | ❌ No | ✅ | SQL, OpenCypher, MongoDB |

**Installation:**

```bash
pip install arcadedb-embedded
```

**Requirements:** Python 3.10–3.14 (packaged; primary testing on 3.12) - No Java installation needed!

## What's Inside

The package includes everything you need:

- **ArcadeDB JARs** (226.0MB): Core database with all features
- **Bundled JRE** (47-63MB): Platform-specific Java 21 runtime (via jlink)
- **Python Package** (~5MB): Python wrapper and utilities

**Total:** ~209-215MB compressed wheel (varies by platform), ~274-289MB when installed

## Platform Support

Pre-built **platform-specific** wheels are available for **6 platforms**:

| Platform | Wheel Size | JRE Size | Installed Size | Tests |
|----------|-----------|----------|----------------|-------|
| Windows ARM64 | 209.4M | 47.6M | ~274M | 222 passed ✅ |
| macOS ARM64 (Apple Silicon) | 210.8M | 53.9M | ~280M | 222 passed ✅ |
| macOS Intel (x86_64) | 211.9M | 55.3M | ~281M | 222 passed ✅ |
| Windows x64 | 211.6M | 51.6M | ~278M | 222 passed ✅ |
| Linux ARM64 | 214.1M | 61.8M | ~288M | 222 passed ✅ |
| Linux x64 | 215.0M | 62.7M | ~289M | 222 passed ✅ |

**Key Features:**

- ✅ All platforms use **platform-specific wheels** (not universal)
- ✅ pip automatically selects the correct wheel for your system
- ✅ Each platform has its own bundled JRE optimized for that architecture
- ✅ All 6 platforms tested and verified (222/222 tests passing)
- ✅ Built on native runners (no emulation) for optimal performance

## What's Included

**Core Features:**

- ✅ **No Java Installation Required**: Platform-specific JRE bundled (~47-63MB)
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher, MongoDB (all included)
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV and ArcadeDB JSONL import (XML supported but has limitations)

**Optimized:**

- Some components are excluded to optimize package size (e.g., gRPC wire protocol)
- See `jar_exclusions.txt` in the repository for details

## Test Results

**222 out of 222 tests pass** on all platforms (100% success rate):

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

Total package size varies by platform: **209-215MB wheel, ~274-289MB installed**

**Common components (identical across platforms):**

- **ArcadeDB JARs**: 226.0 MB (core database, query engines, Studio UI, protocols)

**Platform-specific components:**

- **Bundled JRE**: 47-63 MB (varies by platform, see table above)
- **Python package**: ~5 MB

**Why sizes vary by platform:**

- JRE binaries differ by platform (different native code)
- ARM platforms tend to have slightly smaller JREs (~48MB)
- Intel/x64 platforms have slightly larger JREs (~52-63MB)
- All platforms use the same JAR files (226.0MB)

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
- [Query Languages](../guide/core/queries.md) - SQL and OpenCypher examples
