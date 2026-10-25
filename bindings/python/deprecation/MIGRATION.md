# Migrating from arcadedb-embedded

The ArcadeDB Python bindings moved from `humemai/arcadedb-embedded-python` to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python), under new PyPI names: `arcadedb` (the native build) and `arcadedb-jvm` (the JVM build). `arcadedb-embedded` was the JVM package. Its last release is a shim that installs `arcadedb`, the native build. If you need the JVM build, install `arcadedb-jvm` yourself. This repository is archived after the move. Documentation: [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/). To decide between the two packages, read [Which package?](https://docs.arcadedb.com/arcadedb-python/which-package.html).

`arcadedb-embedded-native` (the native preview package) has no shim and no new release. Its PyPI project has no files and is archived. If you used a preview of it from another source, install `arcadedb`.

## Install and import

| Before | After (native build) | After (JVM build) |
|---|---|---|
| `pip install arcadedb-embedded` | `pip install arcadedb` | `pip install arcadedb-jvm` |
| `pip install 'arcadedb-embedded[arrow,pandas]'` | `pip install 'arcadedb[arrow,pandas]'` | `pip install 'arcadedb-jvm[arrow,pandas]'` |
| `uv add arcadedb-embedded` | `uv add arcadedb` | `uv add arcadedb-jvm` |
| `import arcadedb_embedded` | `import arcadedb` | `import arcadedb` |
| `from arcadedb_embedded import open_database` | `from arcadedb import open_database` | `from arcadedb import open_database` |
| `arcadedb_embedded.core`, `arcadedb_embedded.jvm`, ... | `arcadedb.core`, ... | `arcadedb.core`, `arcadedb.jvm`, ... |

The package for `arcadedb-embedded` users is now `arcadedb`, which is the native build: the engine runs as a native library, without a JVM. It is a different runtime from the one you had. If your code needs the JVM build, for example because it uses Java classes through JPype, install `arcadedb-jvm`: it is the same JVM build as `arcadedb-embedded`, so nothing changes at run time. The extra `vector` of `arcadedb-embedded` (numpy) is the extra `numpy` of `arcadedb`; `arrow`, `pandas` and `polars` keep their names.

Both new packages provide the module `arcadedb`, so an environment holds `arcadedb` or `arcadedb-jvm`, not both. Uninstall the old package first: `pip uninstall arcadedb-embedded`.

## Version mapping

From 26.11.1 the package version is the ArcadeDB engine version, as before.

| Old | Last release | New |
|---|---|---|
| `arcadedb-embedded` (JVM, bundled JRE) | 26.10.2.post1 on PyPI, then the shim 26.11.1 | `arcadedb` 26.11.1 and later (native), or `arcadedb-jvm` 26.11.1 and later (JVM) |
| `arcadedb-embedded-native` (preview) | 26.10.2.dev1 (no files on PyPI), no shim | `arcadedb` 26.11.1 and later |

The 26.11.1 release of `arcadedb-embedded` is a shim and the last one. It installs `arcadedb` at exactly 26.11.1. Importing `arcadedb_embedded` then emits one `FutureWarning` and re-exports `arcadedb`, submodules included, so unchanged code keeps running until you edit the import. The warning says that the package is now `arcadedb`, that this is the native build, and that `arcadedb-jvm` is the JVM build. The shim never upgrades: for newer versions install `arcadedb` or `arcadedb-jvm`. Older releases of the old name stay on PyPI for pinned installs. The shim is published only after the native `arcadedb` 26.11.1 final release exists.

## What stays the same

- The Python API: the module is renamed, its classes and functions are the ones of the 26.11.1 bindings. A few features can differ between the two builds; Which package? lists them.
- Python 3.11 to 3.14, and the Apache-2.0 license.
- The extras `arrow`, `pandas` and `polars`, under the same names.
- Where to look: the user guide and API reference move with the code to the new docs site, and the old `docs.humem.ai/arcadedb` pages redirect there.

## What changes

- The distribution and import names, as above.
- The default runtime: `pip install arcadedb` is the native build, not the JVM build.
- Issues and pull requests go to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python/issues). Benchmarks stay with HumemAI, in [humemai/dbbench](https://github.com/humemai/dbbench).
- Engine changes between 26.10.2 and 26.11.1: read the 26.11.1 release notes, as for any upgrade.
