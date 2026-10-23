# arcadedb-embedded-native (PREVIEW)

> **Preview, alpha quality.** This is an experiment, not a release. The API follows `arcadedb-embedded`, but the engine runs as a
> GraalVM native-image shared library, a different runtime with its own bugs. Do not use it for data you cannot lose. Versions are
> pre-releases (`26.10.2.dev1`): `pip install --pre arcadedb-embedded-native`. Report problems at
> <https://github.com/humemai/arcadedb-embedded-python/issues> and say that you use the native wheel.

ArcadeDB (SQL, openCypher, document, graph, vector, time series) embedded in your Python process **without a JVM and without JPype**.
The engine is compiled ahead of time with GraalVM Community Edition to a shared library (`libarcadedb.so`, `.dylib` or `.dll`); Python loads it with `ctypes`.

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

CPython 3.11 to 3.14; one wheel per platform serves every Python version because the library is loaded with `ctypes`, not compiled against
CPython. Images are built for the baseline CPU of the platform (`-march=compatibility`).

| Platform | Wheel tag | Status |
| --- | --- | --- |
| Linux x86-64, glibc 2.34+ | `manylinux_2_34_x86_64` | published |
| Linux arm64, glibc 2.34+ | `manylinux_2_34_aarch64` | built in CI, not published until its parity run is green |
| macOS arm64 | `macosx_<minos>_arm64` | built in CI, not published until its parity run is green |
| Windows x64 | `win_amd64` | built in CI, not published until its parity run is green |

Intel macOS and Windows arm64 are not built.

## CPU requirements

The wheels are built with `-march=compatibility`, the baseline of each platform: any x86-64 CPU (no AVX2 needed), and generic armv8-a on arm64. They run on a Celeron or Pentium N/J (for example J4125, N5105), on a Proxmox VM with the default CPU type (`x86-64-v2-AES`, `kvm64`), under QEMU's default model, on a Raspberry Pi 4 (Cortex-A72, ARMv8.0) and on AWS Graviton1. Apple Silicon is always fine.

GraalVM CE's own default is higher: x86-64-v3 on x86-64 (AVX, AVX2, BMI1, BMI2, FMA, F16C, LZCNT, MOVBE) and armv8.1-a on arm64 (LSE atomics). An image built that way (`MARCH=x86-64-v3 preview-build.sh`, or a local build with GraalVM's default) dies with `Illegal instruction` and no message on an older CPU. The loader therefore checks the CPU before it loads such an image, and raises `ArcadeDBError` that names the missing features and the baseline:

| Platform | Where the features are read |
| --- | --- |
| Linux x86-64 | the `flags` line of `/proc/cpuinfo` (LZCNT is `lzcnt` or `abm`) |
| Linux arm64 | the `Features` line of `/proc/cpuinfo` (`atomics` is LSE) |
| Windows x86-64 | `IsProcessorFeaturePresent(PF_AVX2_INSTRUCTIONS_AVAILABLE)` |
| macOS | not checked (Apple Silicon only) |

If the CPU cannot be read, the check does not block. Set `ARCADEDB_NATIVE_SKIP_CPU_CHECK=1` to skip it. The fallback on a CPU below the baseline is the JVM package, `pip install arcadedb-embedded`, which runs on any x86-64 CPU. The check is in `arcadedb_embedded/_native/cpu.py`.

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
library code, licensed GPLv2 **with the Classpath Exception**, plus the Apache/BSD/MIT/UPL/EDL third-party Java libraries
listed in `THIRD_PARTY_NOTICES.md`. All texts and the source locations are in the wheel's `*.dist-info/licenses/`.
