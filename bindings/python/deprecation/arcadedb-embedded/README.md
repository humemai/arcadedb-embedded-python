# arcadedb-embedded has moved to arcadedb-jvm

**This package is deprecated. 26.11.1 is its last release.** The ArcadeDB Python bindings now live in the ArcadeData organization, under a new package name. `arcadedb-jvm` is the same JVM build as `arcadedb-embedded` (JPype and a bundled JRE), so moving to it changes nothing at run time:

| | Old | New |
|---|---|---|
| PyPI package | `arcadedb-embedded` | [`arcadedb-jvm`](https://pypi.org/project/arcadedb-jvm/) |
| Import | `import arcadedb_embedded` | `import arcadedb` |
| Source and issues | `humemai/arcadedb-embedded-python` (archived) | [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python) |
| Documentation | `docs.humem.ai/arcadedb` | [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/) |

## What to do

```bash
pip uninstall arcadedb-embedded
pip install arcadedb-jvm
```

Then change `import arcadedb_embedded` to `import arcadedb` (and `from arcadedb_embedded import X` to `from arcadedb import X`). The new package is the same bindings and the same JVM build, published under the new name. `arcadedb-jvm` 26.11.1 has the same version number as this release.

Do not install `arcadedb` instead: it is the native build (no JVM), a different runtime. Choose it on purpose, from the documentation, not by following the old name. `arcadedb` and `arcadedb-jvm` both provide the module `arcadedb`: install one of them in an environment, not both.

## What this release does

It is a shim. It installs `arcadedb-jvm==26.11.1`, and `import arcadedb_embedded` emits one `FutureWarning` and then gives you the `arcadedb` module of `arcadedb-jvm`, submodules included, so existing code keeps running. It is pinned to `arcadedb-jvm==26.11.1` and gets no updates: to receive newer ArcadeDB versions, switch to `arcadedb-jvm`.

The extras `vector`, `arrow`, `pandas` and `polars` are forwarded to the same extras of `arcadedb-jvm`.

Older `arcadedb-embedded` releases stay on PyPI for pinned installs. For the full old-to-new table, see the [migration guide](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/deprecation/MIGRATION.md).
