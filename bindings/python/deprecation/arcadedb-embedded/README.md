# arcadedb-embedded has moved to arcadedb

**This package is deprecated. 26.11.1 is its last release.** The ArcadeDB Python bindings now live in the ArcadeData organization, under a new package name. The package is now [`arcadedb`](https://pypi.org/project/arcadedb/), which is the **native build**: the engine runs as a native library, without a JVM. If you need the JVM build, install [`arcadedb-jvm`](https://pypi.org/project/arcadedb-jvm/) instead.

| | Old | New |
|---|---|---|
| PyPI package | `arcadedb-embedded` | [`arcadedb`](https://pypi.org/project/arcadedb/) (native build) or [`arcadedb-jvm`](https://pypi.org/project/arcadedb-jvm/) (JVM build) |
| Import | `import arcadedb_embedded` | `import arcadedb` |
| Source and issues | `humemai/arcadedb-embedded-python` (archived) | [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python) |
| Documentation | `docs.humem.ai/arcadedb` | [docs.arcadedb.com/arcadedb-python](https://docs.arcadedb.com/arcadedb-python/) |

## What to do

```bash
pip uninstall arcadedb-embedded
pip install arcadedb
```

Then change `import arcadedb_embedded` to `import arcadedb` (and `from arcadedb_embedded import X` to `from arcadedb import X`).

`arcadedb-embedded` was the JVM build, so `arcadedb` is a different runtime. If your code needs the JVM build, for example because it uses Java classes through JPype or a long-running load that suits the JVM, install it instead:

```bash
pip uninstall arcadedb-embedded
pip install arcadedb-jvm
```

[Which package?](https://docs.arcadedb.com/arcadedb-python/which-package.html) explains the difference. `arcadedb` and `arcadedb-jvm` both provide the module `arcadedb`: install one of them in an environment, not both.

## What this release does

It is a shim. It installs `arcadedb==26.11.1`, and `import arcadedb_embedded` emits one `FutureWarning` and then gives you the `arcadedb` module, submodules included, so existing code keeps running. It is pinned to `arcadedb==26.11.1` and gets no updates: to receive newer ArcadeDB versions, switch to `arcadedb` (or `arcadedb-jvm`).

The extras `vector`, `arrow`, `pandas` and `polars` are forwarded to `arcadedb`. The old `vector` extra (numpy) maps to the `numpy` extra of `arcadedb`.

Older `arcadedb-embedded` releases stay on PyPI for pinned installs. For the full old-to-new table, see the [migration guide](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/deprecation/MIGRATION.md).
