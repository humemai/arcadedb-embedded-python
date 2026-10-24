# Migrating from arcadedb-embedded to arcadedb

The ArcadeDB Python bindings moved from `humemai/arcadedb-embedded-python` to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python), under new PyPI names. This repository is archived after the move. Documentation: [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/).

## Install and import

| Before | After |
|---|---|
| `pip install arcadedb-embedded` | `pip install arcadedb` |
| `pip install arcadedb-embedded-native` (preview) | `pip install arcadedb-native` |
| `pip install 'arcadedb-embedded[arrow,pandas]'` | `pip install 'arcadedb[arrow,pandas]'` |
| `uv add arcadedb-embedded` | `uv add arcadedb` |
| `import arcadedb_embedded` | `import arcadedb` |
| `from arcadedb_embedded import open_database` | `from arcadedb import open_database` |
| `arcadedb_embedded.core`, `arcadedb_embedded.jvm`, ... | `arcadedb.core`, `arcadedb.jvm`, ... |

Both new packages provide the module `arcadedb`, so an environment holds `arcadedb` or `arcadedb-native`, not both. Uninstall the old package first: `pip uninstall arcadedb-embedded`.

## Version mapping

From 26.11.1 the package version is the ArcadeDB engine version, as before.

| Old | Last release | New |
|---|---|---|
| `arcadedb-embedded` (JVM, bundled JRE) | 26.10.2.post1 on PyPI, then the shim 26.11.1 | `arcadedb` 26.11.1 and later |
| `arcadedb-embedded-native` (preview) | 26.10.2.dev1, then the shim 26.11.1 | `arcadedb-native` 26.11.1 and later |

The 26.11.1 releases of the old names are shims and the last ones. Each installs the new package at exactly 26.11.1; importing `arcadedb_embedded` then emits one `FutureWarning` and re-exports `arcadedb`, submodules included, so unchanged code keeps running until you edit the import. A shim never upgrades: for newer versions install `arcadedb` or `arcadedb-native`. Older releases of the old names stay on PyPI for pinned installs.

## What stays the same

- The Python API: the module is renamed, its classes and functions are the ones of the 26.11.1 bindings.
- Python 3.11 to 3.14, and the Apache-2.0 license.
- The extras `vector`, `arrow`, `pandas` and `polars`, under the same names.
- Where to look: the user guide and API reference move with the code to the new docs site, and the old `docs.humem.ai/arcadedb` pages redirect there.

## What changes

- The distribution and import names, as above.
- Issues and pull requests go to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python/issues). Benchmarks stay with HumemAI, in [humemai/dbbench](https://github.com/humemai/dbbench).
- Engine changes between 26.10.2 and 26.11.1: read the 26.11.1 release notes, as for any upgrade.
