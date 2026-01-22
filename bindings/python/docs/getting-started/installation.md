# Installation

## Quick Installation

The `arcadedb-embedded` package is **self-contained** with a bundled JRE - **no Java installation required!**

```bash
pip install arcadedb-embedded
```

**Requirements:**

- **Python 3.10–3.14** (packaged; primary testing on 3.12) - No Java installation required!
- **Supported Platforms**: Prebuilt wheels for **6 platforms**
  - Linux: x86_64, ARM64
  - macOS: Intel (x86_64), Apple Silicon (ARM64)
  - Windows: x86_64, ARM64

## What's Included

The `arcadedb-embedded` package (~209-215MB wheel, ~274-289MB installed) includes everything you need:

- **ArcadeDB JARs**: 226.0MB (identical across all platforms)
- **Bundled JRE**: 47-63MB (platform-specific Java 21 runtime via jlink)
- **Python Package**: ~5MB

**Platform Details:**

| Platform | Wheel Size | JRE Size | Installed Size |
|----------|-----------|----------|----------------|
| Windows ARM64 | 209.4M | 47.6M | ~274M |
| macOS ARM64 | 210.8M | 53.9M | ~280M |
| macOS Intel | 211.9M | 55.3M | ~281M |
| Windows x64 | 211.6M | 51.6M | ~278M |
| Linux ARM64 | 214.1M | 61.8M | ~288M |
| Linux x64 | 215.0M | 62.7M | ~289M |

**Features Included:**

- ✅ **No Java Installation Required**: Bundled platform-specific JRE
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, OpenCypher, MongoDB
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV and ArcadeDB JSONL import (XML supported but has limitations)

!!! tip "Platform Selection"
    pip automatically selects the correct platform-specific wheel for your system. You don't need to specify the platform manually.

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
./build.sh
```

Built wheels will be in `dist/`:

```text
dist/
└── arcadedb_embedded-X.Y.Z-py3-none-<platform>.whl
```

Install locally:

```bash
pip install dist/arcadedb_embedded-*.whl
```

## JVM Configuration

The bundled JVM can be configured via the `ARCADEDB_JVM_ARGS` environment variable **before** importing `arcadedb_embedded`:

```bash
# Default (4GB heap)
python your_script.py

# Custom memory for large datasets
export ARCADEDB_JVM_ARGS="-Xmx8g -Xms8g"
python your_script.py
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

!!! warning "Set Before Import"
    `ARCADEDB_JVM_ARGS` must be set **before** the first `import arcadedb_embedded` in your Python process. The JVM can only be configured once.

For detailed configuration and memory tuning, see [Troubleshooting - Memory Configuration](../development/troubleshooting.md#memory-configuration).

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [Package Overview](distributions.md) - Detailed package information
- [User Guide](../guide/core/database.md) - Learn all features
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
