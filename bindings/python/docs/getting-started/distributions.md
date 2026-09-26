# Package Overview

ArcadeDB Python provides a **self-contained embedded** package that runs the database directly in your Python process with a bundled JRE - **no Java installation required!**

## The Package

| Package | Wheel Size | Installed Size | Java Required | Studio UI | Query Languages |
|---------|-----------|------------------------------|---------------|----------------|
| **arcadedb-embedded** | ~69 MiB | ~96 MiB | ❌ No | ✅ | SQL, OpenCypher |

**Installation:**

```bash
pip install arcadedb-embedded
```

**Requirements:** Python 3.10–3.14 (packaged; primary testing on 3.12) - No Java installation needed!

## What's Inside

The package includes everything you need:

- **ArcadeDB JARs** (~33 MiB, uncompressed): Core database plus the optional server/Studio stack
- **Bundled JRE** (~63 MiB, uncompressed): Platform-specific Java 25 runtime (via jlink)

**Current Linux x86_64 package info:** ~69 MiB compressed wheel, ~63 MiB JRE, ~33 MiB JARs, and ~96 MiB installed (26.10.1 development wheel, measured 2026-09-27).

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

- ✅ **No Java Installation Required**: Platform-specific JRE bundled (~63 MiB uncompressed)
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher (all included)
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, XML, and ArcadeDB JSONL import
- ✅ **Server Mode**: Optional in-process HTTP server
- ✅ **Studio Web UI**: Visual database explorer and query editor

**Optimized:**

- Some components are excluded to optimize package size (e.g., the gRPC wire
  protocol). See `scripts/jar_exclusions.txt` in the repository for the full
  list.
- The bundled server is in-process, so its lifetime is your Python process's.
  It bundles the Postgres, Redis, and Bolt wire protocols (opt-in). For a
  standalone server, HA/replication, TLS, or the Mongo wire protocol, run the
  official [ArcadeDB server](https://docs.arcadedb.com/#Server) — see
  [Access Methods](../api-access-methods.md).

## Use Cases

Perfect for:

- Production Python applications
- Cloud deployments (no Java setup needed!)
- Docker containers
- Desktop applications
- Multi-model database needs (Graph, Document, Vector, Time Series)
- Any scenario requiring SQL or OpenCypher queries
- Development and debugging (with Studio UI)

## Accessing Studio UI

```python
from arcadedb_embedded import create_server

# Start HTTP server with Studio UI
server = create_server("./databases", root_password="password123")
server.start()

# Studio UI available at the URL below (port 2480 by default)
print(server.get_studio_url())

# When done
server.stop()
```

!!! tip "Studio in Browser"
    Once the server starts, open the printed URL to reach the Studio UI. Studio
    ships as static assets with no executable code, so it costs disk and nothing
    else until a browser actually requests it.

## Import Statement

The import is always:

```python
import arcadedb_embedded as arcadedb
```

Simple and consistent across all platforms!

## Size Breakdown

Current sizes are ballpark values and can move with ArcadeDB, the bundled JRE, the
target platform, and filesystem overhead after installation:

- **Wheel (compressed)**: ~69 MiB
- **Installed package**: ~96 MiB

**Components (uncompressed):**

- **ArcadeDB JARs**: ~33 MiB (64 JARs, including the optional server stack; [Server Mode](../guide/server.md#what-it-costs-you) breaks down its cost as measured on 26.8.1)
- **Bundled JRE**: ~63 MiB (platform-specific Java 25 runtime via jlink, 20 modules)

**Optimizations:**

- The gRPC wire protocol is excluded; server and Studio are included
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
- [Server Mode](../guide/server.md) - Using the HTTP server with Studio UI
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
- [Query Languages](../guide/core/queries.md) - SQL and OpenCypher examples
