# Installation

## Quick Installation

The `arcadedb-embedded` package is **self-contained** with a bundled JRE - **no Java installation required!**

```bash
uv pip install arcadedb-embedded
```

**Requirements:**

- **Python 3.10–3.14** (packaged; primary testing on 3.12) - No Java installation required!
- **Supported Platforms**: Prebuilt wheels for **4 platforms**
    - Linux: x86_64, ARM64
    - macOS: Apple Silicon (ARM64)
    - Windows: x86_64

## What's Included

The `arcadedb-embedded` package includes everything you need. Current Linux x86_64 dev
builds are about 73MB as a wheel and about 102MB installed, with some variation by
platform and version:

- **ArcadeDB JARs**: ~31.7MB (uncompressed)
- **Bundled JRE**: ~60MB (uncompressed, platform-specific Java 25 runtime via jlink)

**Features Included:**

- ✅ **No Java Installation Required**: Bundled platform-specific JRE
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher, MongoDB
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, XML, and ArcadeDB JSONL import

!!! tip "Platform Selection"
    uv pip automatically selects the correct platform-specific wheel for your system. You don't need to specify the platform manually.

## Python Version

- **Supported**: Python 3.10, 3.11, 3.12, 3.13, 3.14 (packaged classifiers)
- **Recommended**: Python 3.12 or higher

## Dependencies

All Python dependencies are automatically installed:

- **JPype1** >= 1.5.0 (Java-Python bridge)

## Verify Installation

After installation, verify everything works:

```python
import arcadedb_embedded as arcadedb
print(f"ArcadeDB Python bindings version: {arcadedb.__version__}")

# Test database creation
with arcadedb.create_database("./test") as db:
    result = db.query("sql", "SELECT 1 as test")
    print(f"Database working: {result.first().get('test') == 1}")
```

Expected output (version will match what you installed):

```text
ArcadeDB Python bindings version: X.Y.Z
Database working: True
```

## Building from Source

If you want to build the wheels yourself, see [Build Architecture Documentation](../development/build-architecture.md) for comprehensive instructions.

Quick build:

```bash
cd bindings/python/

# Build for your current platform (auto-detected)
./scripts/build.sh
```

Built wheels will be in `dist/`:

```text
dist/
└── arcadedb_embedded-X.Y.Z-py3-none-<platform>.whl
```

Install locally:

```bash
uv pip install dist/arcadedb_embedded-*.whl
```

## JVM Configuration

Prefer configuring the bundled JVM **inside Python** before the first database or server is created:

```python
from arcadedb_embedded.jvm import start_jvm

# Configure JVM explicitly once per process
start_jvm(heap_size="8g", jvm_args="-XX:MaxDirectMemorySize=8g")
```

Or pass JVM options when creating/opening the database:

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./db", jvm_kwargs={"heap_size": "8g"}) as db:
    pass
```

**Common Options:**

JVM arguments use two flag types:

- **`-X` flags**: JVM runtime options (heap, GC, etc.)
    - `-Xmx<size>`: Maximum heap memory (e.g., `-Xmx8g` for 8GB)
    - `-Xms<size>`: Initial heap size (recommended: same as `-Xmx`)
    - `-XX:MaxDirectMemorySize=<size>`: Limit off-heap buffers

- **`-D` flags**: System properties for ArcadeDB configuration
    - `-Darcadedb.vectorIndex.locationCacheSize=<count>`: Vector location cache limit
    - `-Darcadedb.vectorIndex.graphBuildCacheSize=<count>`: JVector build cache limit
    - `-Darcadedb.vectorIndex.mutationsBeforeRebuild=<count>`: Mutations threshold before rebuilding JVector

**Automatically injected flags** (always set, override only if needed):

| Flag | Purpose |
|------|---------|
| `--add-modules=jdk.incubator.vector` | Enable JVector SIMD acceleration |
| `--enable-native-access=ALL-UNNAMED` | Required for off-heap / Panama access |
| `-Dfile.encoding=UTF8` | Force UTF-8 regardless of OS locale |
| `--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED` | Reflection into atomic internals used by the engine |
| `--add-opens=java.base/java.nio.channels.spi=ALL-UNNAMED` | Reflection into NIO channel SPI for memory-mapped I/O |
| `--add-opens=java.base/java.lang=ALL-UNNAMED` | Reflection into core `java.lang` for engine bootstrap |
| `-Dpolyglot.engine.WarnInterpreterOnly=false` | Silence Truffle/GraalVM warning on standard HotSpot JDKs |
| `-XX:+UseCompactObjectHeaders` | Reduce per-object header overhead to lower heap usage |
| `-Djava.awt.headless=true` | Suppress AWT/display initialisation |

!!! warning "One JVM configuration per process"
    JVM options are locked after the JVM starts. Set `start_jvm(...)` or pass `jvm_kwargs` **before** the first database or server is created. To change JVM settings, start a new Python process.

!!! tip "Environment fallback (optional)"
    If you must configure JVM flags externally (CI, shell scripts), `ARCADEDB_JVM_ARGS` is still supported, but in-code configuration is preferred.

For detailed configuration and memory tuning, see [Troubleshooting - Memory Configuration](../development/troubleshooting.md#memory-configuration).

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [Package Overview](distributions.md) - Detailed package information
- [User Guide](../guide/core/database.md) - Learn all features
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
