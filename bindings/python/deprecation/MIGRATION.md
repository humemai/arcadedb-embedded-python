# Migrating from arcadedb-embedded and arcadedb-embedded-native

The ArcadeDB Python bindings moved from `humemai/arcadedb-embedded-python` to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python), under new PyPI names: `arcadedb-embedded` (the JVM package) becomes `arcadedb-jvm`, and `arcadedb-embedded-native` (the native package) becomes `arcadedb`. This repository is archived after the move. Documentation: [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/).

## Install and import

| Before | After |
|---|---|
| `pip install arcadedb-embedded` | `pip install arcadedb-jvm` |
| `pip install arcadedb-embedded-native` (preview) | `pip install arcadedb` |
| `pip install 'arcadedb-embedded[arrow,pandas]'` | `pip install 'arcadedb-jvm[arrow,pandas]'` |
| `uv add arcadedb-embedded` | `uv add arcadedb-jvm` |
| `import arcadedb_embedded` | `import arcadedb` |
| `import arcadedb_native` (from `arcadedb-embedded-native`) | `import arcadedb` |
| `from arcadedb_embedded import open_database` | `from arcadedb import open_database` |
| `arcadedb_embedded.core`, `arcadedb_embedded.jvm`, ... (and `arcadedb_native.core`, ...) | `arcadedb.core`, `arcadedb.jvm`, ... |

`arcadedb-jvm` is the same JVM build as `arcadedb-embedded`, so moving to it changes nothing at run time. `pip install arcadedb` gives the native build instead (no JVM), a different runtime: take it on purpose, from the documentation, not because the name looks like the successor of `arcadedb-embedded`.

Both new packages provide the module `arcadedb`, so an environment holds `arcadedb-jvm` or `arcadedb`, not both. Uninstall the old package first: `pip uninstall arcadedb-embedded` (or `arcadedb-embedded-native`).

## Version mapping

From 26.11.1 the package version is the ArcadeDB engine version, as before.

| Old | Last release | New |
|---|---|---|
| `arcadedb-embedded` (JVM, bundled JRE) | 26.10.2.post1 on PyPI, then the shim 26.11.1 | `arcadedb-jvm` 26.11.1 and later |
| `arcadedb-embedded-native` (preview) | 26.10.2.dev1, then the shim 26.11.1 | `arcadedb` 26.11.1 and later |

The 26.11.1 releases of the old names are shims and the last ones. The `arcadedb-embedded` shim installs `arcadedb-jvm` at exactly 26.11.1, and the `arcadedb-embedded-native` shim installs `arcadedb` at exactly 26.11.1; importing `arcadedb_embedded` (or `arcadedb_native`, for the native shim) then emits one `FutureWarning` and re-exports `arcadedb`, submodules included, so unchanged code keeps running until you edit the import. A shim never upgrades: for newer versions install `arcadedb-jvm` or `arcadedb`. Older releases of the old names stay on PyPI for pinned installs.

## What stays the same

- The Python API: the module is renamed, its classes and functions are the ones of the 26.11.1 bindings. The runtime of each old package stays the same when you follow the table: JVM to `arcadedb-jvm`, native to `arcadedb`.
- Python 3.11 to 3.14, and the Apache-2.0 license.
- The extras `vector`, `arrow`, `pandas` and `polars`, under the same names.
- Where to look: the user guide and API reference move with the code to the new docs site, and the old `docs.humem.ai/arcadedb` pages redirect there.

## What changes

- The distribution and import names, as above.
- Issues and pull requests go to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python/issues). Benchmarks stay with HumemAI, in [humemai/dbbench](https://github.com/humemai/dbbench).
- Engine changes between 26.10.2 and 26.11.1: read the 26.11.1 release notes, as for any upgrade.
