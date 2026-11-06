# ArcadeDB Embedded for Python

> **Moved: the Python bindings now live in [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python).** Install `arcadedb` (the native build, the default) or `arcadedb-jvm` (the JVM build); both use `import arcadedb`. [Which package?](https://github.com/ArcadeData/arcadedb-python/blob/main/docs/modules/ROOT/pages/which-package.adoc) explains the choice. Both packages are released as 26.11.1 (`uv add arcadedb`). `arcadedb-embedded` and `import arcadedb_embedded` are deprecated: the last release of `arcadedb-embedded`, 26.11.1, installs `arcadedb`. Report bindings issues and send bindings pull requests to the new repository. This repository will be archived once the benchmark tooling moves to [humemai/dbbench](https://github.com/humemai/dbbench) (planned for mid-November 2026, after the last measuring pass); until then the tooling stays here.

[![PyPI](https://img.shields.io/pypi/v/arcadedb)](https://pypi.org/project/arcadedb/)
[![Docs](https://img.shields.io/badge/docs-arcadedb.com-892122)](https://docs.arcadedb.com/arcadedb-python/)

---

## What is in this repository

- `benchmarks/`: the benchmark harness for ArcadeDB and its comparators, and the published results. Start with [benchmarks/README.md](benchmarks/README.md).
- `bindings/python/`: the source of the `arcadedb-embedded` releases up to 26.10.2.post1. It is kept for history and for the benchmark harness, and new work on the bindings goes to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python).
- The rest is a fork of the ArcadeDB Java project, which this repository does not change.

## Use the Python bindings

Install the package and read the documentation from the new repository:

```bash
uv add arcadedb   # native build, the default
uv add arcadedb-jvm   # JVM build, only if you need it
```

- Documentation: [https://docs.arcadedb.com/arcadedb-python/](https://docs.arcadedb.com/arcadedb-python/)
- Repository, issues and pull requests: [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python)
- PyPI: [arcadedb](https://pypi.org/project/arcadedb/) and [arcadedb-jvm](https://pypi.org/project/arcadedb-jvm/)

## Upstream ArcadeDB (Java)

This repository is a fork of ArcadeDB Java. For the server, the Java API, and the core database documentation:

- Upstream repository: [https://github.com/ArcadeData/arcadedb](https://github.com/ArcadeData/arcadedb)
- Documentation: [https://docs.arcadedb.com](https://docs.arcadedb.com)
- ArcadeDB Discord: [https://discord.gg/w2Npx2B7hZ](https://discord.gg/w2Npx2B7hZ)

## Support

- Benchmark issues: [https://github.com/humemai/arcadedb-embedded-python/issues](https://github.com/humemai/arcadedb-embedded-python/issues)
- Bindings issues: [https://github.com/ArcadeData/arcadedb-python/issues](https://github.com/ArcadeData/arcadedb-python/issues)

## License

Both upstream ArcadeDB (Java) and the Python bindings are licensed under Apache 2.0, fully open and free for everyone, including commercial use.

Arcade Data, the company behind ArcadeDB, has [committed in writing](https://arcadedb.com/blog/open-source-forever-why-arcadedb-will-never-change-its-license/) to keeping the engine Apache 2.0, and HumemAI makes the same commitment for the Python bindings.
