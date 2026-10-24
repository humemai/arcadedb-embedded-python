# arcadedb-embedded has moved to arcadedb

**This package is deprecated. 26.11.1 is its last release.** The ArcadeDB Python bindings now live in the ArcadeData organization, under a new package name:

| | Old | New |
|---|---|---|
| PyPI package | `arcadedb-embedded` | [`arcadedb`](https://pypi.org/project/arcadedb/) |
| Import | `import arcadedb_embedded` | `import arcadedb` |
| Source and issues | `humemai/arcadedb-embedded-python` (archived) | [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python) |
| Documentation | `docs.humem.ai/arcadedb` | [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/) |

## What to do

```bash
pip uninstall arcadedb-embedded
pip install arcadedb
```

Then change `import arcadedb_embedded` to `import arcadedb` (and `from arcadedb_embedded import X` to `from arcadedb import X`). The new package is the same bindings, published under the new name. `arcadedb` 26.11.1 has the same version number as this release.

## What this release does

It is a shim. It installs `arcadedb==26.11.1`, and `import arcadedb_embedded` emits one `FutureWarning` and then gives you the `arcadedb` module, submodules included, so existing code keeps running. It is pinned to `arcadedb==26.11.1` and gets no updates: to receive newer ArcadeDB versions, switch to `arcadedb`.

The extras `vector`, `arrow`, `pandas` and `polars` are forwarded to the same extras of `arcadedb`.

Older `arcadedb-embedded` releases stay on PyPI for pinned installs. For the full old-to-new table, see the [migration guide](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/deprecation/MIGRATION.md).
