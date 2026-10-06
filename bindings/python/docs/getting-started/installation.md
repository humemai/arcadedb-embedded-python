# Installation

## Quick Installation

The `arcadedb-embedded` package is **self-contained** with a bundled JRE - **no Java installation required!**

```bash
pip install arcadedb-embedded
```

**Requirements:**

- **Python 3.10 to 3.14** (CI runs all five on every supported platform). No Java installation required!
- **Supported Platforms**: Prebuilt wheels for **4 platforms**
    - Linux: x86_64, ARM64
    - macOS: Apple Silicon (ARM64)
    - Windows: x86_64

## What's Included

The `arcadedb-embedded` package includes everything you need. The Linux x86_64 wheel of
26.10.1 is 69.4 MiB to download and 96.9 MiB unpacked (measured on the file on PyPI);
other platforms are in the same range:

| Platform | Wheel tag (Python 3.12) | Download |
|---|---|---|
| Linux x86_64 | `manylinux_2_34_x86_64` | 69.4 MiB |
| Linux ARM64 | `manylinux_2_34_aarch64` | 68.3 MiB |
| macOS Apple Silicon | `macosx_11_0_arm64` | 64.8 MiB |
| Windows x86_64 | `win_amd64` | 66.1 MiB |

Every wheel is platform-specific, built on a native runner of its platform, and carries a
JRE for that platform, so pip needs no hint to pick the right one. Unpacked, the Linux
x86_64 wheel holds:

- **ArcadeDB JARs**: ~34 MiB across 64 JARs, including the optional server and Studio stack
  ([Server Mode](../guide/server.md#what-it-costs-you) lists it; `arcadedb.jar_fingerprint()`
  counts and hashes the installed JARs)
- **Bundled JRE**: ~63 MiB (Java 25 runtime trimmed with jlink to 20 modules)

Engine modules the bindings do not use are left out to keep the wheel small: the gRPC and
MongoDB wire protocols, Raft HA, and Gremlin among them (`scripts/jar_exclusions.txt` in the
repository has the full list). The optional server is in-process, so its lifetime is your
Python process's, and it bundles the Postgres, Redis, and Bolt wire protocols (opt-in); see
[Access Methods](../api-access-methods.md).

**Features Included:**

- ✅ **No Java Installation Required**: Bundled platform-specific JRE
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL and OpenCypher
- ✅ **Vector Search**: Graph-based indexing for embeddings
- ✅ **Data Import**: CSV, XML, and ArcadeDB JSONL import
- ✅ **Server Mode**: Optional in-process HTTP server
- ✅ **Studio Web UI**: Visual database explorer and query editor

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
└── arcadedb_embedded-X.Y.Z-cp<pyver>-cp<pyver>-<platform>.whl
```

For example, a Linux x86_64 build on Python 3.12 now looks like:

```text
arcadedb_embedded-X.Y.Z-cp312-cp312-manylinux_2_34_x86_64.whl
```

Install locally:

```bash
pip install dist/arcadedb_embedded-*.whl
```

## JVM Configuration

Prefer configuring the bundled JVM **inside Python** before the first database is created:

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
    - `-Darcadedb.vectorIndex.graphBuildCacheSize=<count>`: build-cache override (default automatic; leave unset)
    - `-Darcadedb.vectorIndex.mutationsBeforeRebuild=<count>`: FLOOR for the rebuild threshold, which scales with the index (see the vector index guide); the effective value is `max(floor, min(graphSize x 0.2, 50000))` at the defaults

**Automatically injected flags** (always set unless you pass your own value):

| Flag | Purpose |
|------|---------|
| `-Xmx4g` | Default heap ceiling (`heap_size="4g"`); an `-Xmx` in `jvm_args` or `ARCADEDB_JVM_ARGS` wins unless you pass a different `heap_size` |
| `-XX:ErrorFile=./log/hs_err_pid%p.log` | JVM crash log location (`ARCADEDB_JVM_ERROR_FILE` overrides it) |
| `-Djdk.xml.maxGeneralEntitySizeLimit=0`, `-Djdk.xml.entityExpansionLimit=0`, `-Djdk.xml.totalEntitySizeLimit=0` | Lift the JDK's XML entity limits for large XML imports; this applies to the whole process. Pass `start_jvm(disable_xml_limits=False)` to keep the JDK limits |
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
    JVM options are locked after the JVM starts. Set `start_jvm(...)` or pass `jvm_kwargs` **before** the first database is created. To change JVM settings, start a new Python process.

!!! tip "Environment variable (optional)"
    If you must configure JVM flags externally (CI, shell scripts), set `ARCADEDB_JVM_ARGS`. It is always read, and `jvm_args` passed in code are appended after it. In-code configuration is preferred.

For detailed configuration and memory tuning, see [Troubleshooting - Memory Configuration](../development/troubleshooting.md#memory-configuration).

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [User Guide](../guide/core/database.md) - Learn all features
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
