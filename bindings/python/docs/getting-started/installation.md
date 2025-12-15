# Installation

## Quick Installation

The `arcadedb-embedded` package is **self-contained** with a bundled JRE - **no Java installation required!**

```bash
# Temporarily install from GitHub Pages (awaiting PyPI size limit approval)
pip install arcadedb-embedded \
  --index-url https://humemai.github.io/arcadedb-embedded-python/simple/ \
  --extra-index-url https://pypi.org/simple/
```

!!! note "Temporary GitHub Pages Installation"
    We're temporarily hosting wheels on GitHub Pages while awaiting PyPI size limit approval (our wheels are ~160MB, default limit is 100MB).

    - `--index-url`: Primary index (GitHub Pages for arcadedb-embedded)
    - `--extra-index-url`: Secondary index (PyPI for dependencies like JPype1)

    Once PyPI approves our size limit request, installation will be simpler:
    ```bash
    pip install arcadedb-embedded
    ```

**Requirements:**

- **Python 3.8+ only** - No Java installation required!
- **Supported Platforms**: Prebuilt wheels for **6 platforms**
  - Linux: x86_64, ARM64
  - macOS: Intel (x86_64), Apple Silicon (ARM64)
  - Windows: x86_64, ARM64

## What's Included

The `arcadedb-embedded` package (~155-161MB wheel, ~215-230MB installed) includes everything you need:

- **ArcadeDB JARs**: 167.4MB (identical across all platforms)
- **Bundled JRE**: 47-63MB (platform-specific Java 21 runtime via jlink)
- **Python Package**: ~5MB

**Platform Details:**

| Platform | Wheel Size | JRE Size | Installed Size |
|----------|-----------|----------|----------------|
| Windows ARM64 | 155.1M | 47.3M | ~215M |
| macOS ARM64 | 156.7M | 53.9M | ~221M |
| macOS Intel | 157.8M | 55.3M | ~223M |
| Windows x64 | 157.4M | 51.5M | ~219M |
| Linux ARM64 | 159.9M | 61.8M | ~229M |
| Linux x64 | 160.9M | 62.7M | ~230M |

**Features Included:**

- ✅ **No Java Installation Required**: Bundled platform-specific JRE
- ✅ **Core Database**: All models (Graph, Document, Key/Value, Vector, Time Series)
- ✅ **Query Languages**: SQL, Cypher, Gremlin, MongoDB
- ✅ **Studio Web UI**: Visual database explorer and query editor
- ✅ **Wire Protocols**: HTTP REST, PostgreSQL, MongoDB, Redis
- ✅ **Vector Search**: HNSW indexing for embeddings
- ✅ **Data Import**: CSV, JSON, Neo4j importers

!!! tip "Platform Selection"
    pip automatically selects the correct platform-specific wheel for your system. You don't need to specify the platform manually.

## Python Version

- **Supported**: Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Recommended**: Python 3.10 or higher

## Dependencies

All Python dependencies are automatically installed:

- **JPype1** >= 1.5.0 (Java-Python bridge)
- **typing-extensions** (for Python < 3.10)

## Verify Installation

After installation, verify everything works:

```python
import arcadedb_embedded as arcadedb
print(f"ArcadeDB Python bindings version: {arcadedb.__version__}")

# Test database creation
with arcadedb.create_database("/tmp/test") as db:
    result = db.query("sql", "SELECT 1 as test")
    print(f"Database working: {result[0].get_property('test') == 1}")
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

# Or build with Docker for Linux
docker-compose up arcadedb-python-build
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

## Troubleshooting

### Installation Fails with "No matching distribution"

If pip can't find the package:

1. Make sure you're using the correct installation command with both index URLs:
   ```bash
   pip install arcadedb-embedded \
     --index-url https://humemai.github.io/arcadedb-embedded-python/simple/ \
     --extra-index-url https://pypi.org/simple/
   ```

2. Check your platform is supported:
   ```bash
   python -c "import platform; print(platform.machine(), platform.system())"
   ```
   Supported: x86_64/amd64/AMD64, aarch64/arm64/ARM64 on Linux, macOS, Windows

3. Check your Python version:
   ```bash
   python --version  # Should be 3.8 or higher
   ```

### Import Errors

If `import arcadedb_embedded` fails:

```bash
# Uninstall first
pip uninstall arcadedb-embedded

# Reinstall
pip install arcadedb-embedded \
  --index-url https://humemai.github.io/arcadedb-embedded-python/simple/ \
  --extra-index-url https://pypi.org/simple/
```

### Version Conflicts

If you see version conflicts with JPype:

```bash
# Upgrade JPype
pip install --upgrade JPype1

# Reinstall ArcadeDB
pip install --force-reinstall arcadedb-embedded \
  --index-url https://humemai.github.io/arcadedb-embedded-python/simple/ \
  --extra-index-url https://pypi.org/simple/
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [Package Overview](distributions.md) - Detailed package information
- [User Guide](../guide/core/database.md) - Learn all features
- [Build Architecture](../development/build-architecture.md) - How platform-specific wheels are built
