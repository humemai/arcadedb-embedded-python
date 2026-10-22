# arcadedb-embedded-native (PREVIEW)

> **Preview, alpha quality.** This is an experiment, not a release. The API follows `arcadedb-embedded`, but the engine runs as a
> GraalVM native-image shared library, a different runtime with its own bugs. Do not use it for data you cannot lose. Versions are
> pre-releases (`26.10.2.dev0`): `pip install --pre arcadedb-embedded-native`. Report problems at
> <https://github.com/humemai/arcadedb-embedded-python/issues> and say that you use the native wheel.

ArcadeDB (SQL, openCypher, document, graph, vector, time series) embedded in your Python process **without a JVM and without JPype**.
The engine is compiled ahead of time with GraalVM Community Edition to `libarcadedb.so`; Python loads it with `ctypes`.

## Install

```bash
pip install --pre arcadedb-embedded-native        # or: uv add --prerelease allow arcadedb-embedded-native
```

It installs **beside** `arcadedb-embedded` (distinct distribution name, distinct import name `arcadedb_native`, no shared files).
Extras for the columnar helpers: `[numpy]`, `[arrow]`, `[pandas]`, `[polars]`.

## Use

The public API is the one of `arcadedb_embedded`. Switch with one line:

```python
import arcadedb_native as arcadedb      # was: import arcadedb_embedded as arcadedb

with arcadedb.create_database("/tmp/demo") as db:
    db.schema.create_vertex_type("Person")   # schema objects work; see "Not supported yet" for the Java-object corners
    with db.transaction():
        db.command("sql", "CREATE VERTEX Person SET name = ?", "Ada")
    print(db.query("sql", "SELECT FROM Person").to_list())
```

`arcadedb_native.ENGINE_VERSION`, `.NATIVE_IMAGE` and `.SOURCE_COMMIT` tell which engine and which build you have.

## Platforms

Linux x86-64 only, CPython 3.11 to 3.14, glibc 2.34 or newer (wheel tag `py3-none-manylinux_2_34_x86_64`; one wheel serves every
Python version because the library is loaded with `ctypes`, not compiled against CPython). The image is built for baseline x86-64
(`-march=compatibility`), so it runs on any x86-64 CPU. macOS, Windows and Linux arm64 wheels do not exist yet.

## Not supported yet

Each of these raises `NotOnNativeYet` (a `NotImplementedError`) instead of misbehaving:

- **JVM-only APIs**: `get_java_database()`, `start_jvm()`, `jvm_kwargs`, JVM settings, `jar_fingerprint()`, direct Java class access.
- **Java-object returns of schema methods** (for example `getClass`, `newLightEdge`), `VectorIndex.get_stats`, and
  `VectorIndex.find_nearest_approximate` over PRODUCT quantization (PQ accessors).
- **Async `transaction()`** helpers that depend on Java threads.
- Engine modules left out of the image: gRPC, MongoDB wire, Raft/HA, Gremlin (the in-process server, the
  HTTP API, Postgres, Redis and Bolt wire protocols are in).
- Free-threaded Python builds are untested.

The parity suite (the bindings' own tests run against the installed wheel) passes with 0 failures; the remaining tests are the
"not yet" items above or JVM-only by nature. Numbers are in the project notes, not here.

## Licence

Apache-2.0 for ArcadeDB and these bindings. The library also contains the GraalVM Community Edition runtime and JDK class
library code, licensed GPLv2 **with the Classpath Exception**, plus the Apache/BSD/MIT/UPL/EPL third-party Java libraries
listed in `THIRD_PARTY_NOTICES.md`. All texts and the source locations are in the wheel's `*.dist-info/licenses/`.
