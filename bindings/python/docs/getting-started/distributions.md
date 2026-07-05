# Package Overview

ArcadeDB Python provides a **self-contained embedded** package that runs the database directly in your Python process with a bundled JRE - **no Java installation required!**

## The Package

| Package | Wheel Size | Installed Size | Java Required | Query Languages |
|---------|-----------|------------------------------|---------------|----------------|
| **arcadedb-embedded** | ~64MB | ~89MB | ❌ No | SQL, OpenCypher |

**Installation:**

```bash
pip install arcadedb-embedded
```

**Requirements:** Python 3.10–3.14 (packaged; primary testing on 3.12) - No Java installation needed!

## What's Inside

The package includes everything you need:

- **ArcadeDB JARs** (~24MB, uncompressed): Core database with the embedded feature set
- **Bundled JRE** (~65MB, uncompressed): Platform-specific Java 25 runtime (via jlink)

**Current Linux x86_64 package info:** ~64MB compressed wheel, ~65MB JRE, ~24MB JARs, and ~89MB installed.

These numbers are measured from the built wheel file and the extracted
`site-packages/arcadedb_embedded/` directory, and they vary by platform and version.

## Platform Support

Pre-built **platform-specific** wheels are available for **4 platforms**. Sizes stay in the same ballpark across platforms, but vary slightly by platform and version (see size breakdown below).

**Key Features:**

- ✅ All platforms use **platform-specific wheels** (not universal)
- ✅ pip automatically selects the correct wheel for your system
- ✅ Each platform has its own bundled JRE optimized for that architecture
- ✅ Full bindings suite passes on every platform build
- ✅ Built on native runners (no emulation) for optimal performance

## What's Included

**Core Features:**

- ✅ **No Java Installation Required**: Platform-specific JRE bundled (~65MB uncompressed)
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher (all included)
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, XML, and ArcadeDB JSONL import

**Optimized (embedded-only):**

- The package is embedded-only: the HTTP server, Studio web UI, and wire
  protocols are not bundled. For client-server deployments, run the official
  [ArcadeDB server](https://docs.arcadedb.com/#Server) alongside — see
  [Access Methods](../api-access-methods.md).
- Additional components are excluded to optimize package size (e.g., gRPC
  wire protocol). See `scripts/jar_exclusions.txt` in the repository for the
  full list.

## Use Cases

Perfect for:

- Production Python applications
- Cloud deployments (no Java setup needed!)
- Docker containers
- Desktop applications
- Multi-model database needs (Graph, Document, Vector, Time Series)
- Any scenario requiring SQL or OpenCypher queries

## Import Statement

The import is always:

```python
import arcadedb_embedded as arcadedb
```

Simple and consistent across all platforms!

## Size Breakdown

Current sizes are ballpark values and can move with ArcadeDB, the bundled JRE, the
target platform, and filesystem overhead after installation:

- **Wheel (compressed)**: ~64MB
- **Installed package**: ~89MB

**Components (uncompressed):**

- **ArcadeDB JARs**: ~24MB (51 JARs)
- **Bundled JRE**: ~65MB (platform-specific Java 25 runtime via jlink)

**Optimizations:**

- Embedded-only: server/Studio/wire-protocol JARs excluded
- See `scripts/jar_exclusions.txt` in repository for details

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
# On Linux x64 for Python 3.12, installs: arcadedb_embedded-X.Y.Z-cp312-cp312-manylinux_2_34_x86_64.whl
# On macOS ARM64 for Python 3.12, installs: arcadedb_embedded-X.Y.Z-cp312-cp312-macosx_11_0_arm64.whl
# On Windows x86_64 for Python 3.12, installs: arcadedb_embedded-X.Y.Z-cp312-cp312-win_amd64.whl
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
- [Query Languages](../guide/core/queries.md) - SQL and OpenCypher examples
