# ArcadeDB Embedded for Python

Native Python bindings for ArcadeDB (forked from the official Java project).

[![PyPI](https://img.shields.io/pypi/v/arcadedb-embedded)](https://pypi.org/project/arcadedb-embedded/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arcadedb-embedded)](https://pypi.org/project/arcadedb-embedded/)
[![Docs](https://img.shields.io/badge/docs-humem.ai-blue)](https://docs.humem.ai/arcadedb/latest/)
[![Test Python Bindings](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-bindings.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-bindings.yml)
[![Test Python Examples](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-examples.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-examples.yml)
[![Release to PyPI](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/release-python-packages.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/release-python-packages.yml)

<p align="center">
  <a href="https://github.com/ArcadeData/arcadedb/actions/workflows/mvn-deploy.yml"><img src="https://github.com/ArcadeData/arcadedb/actions/workflows/mvn-deploy.yml/badge.svg"></a>
  &nbsp;
  <a href="https://codecov.io/github/ArcadeData/arcadedb" >
   <img src="https://codecov.io/github/ArcadeData/arcadedb/graph/badge.svg?token=0690JAJHIO"/></a>

[//]: # (  <a href="https://www.codacy.com/gh/ArcadeData/arcadedb/dashboard?utm_source=github.com&utm_medium=referral&utm_content=ArcadeData/arcadedb&utm_campaign=Badge_Coverage"><img src="https://app.codacy.com/project/badge/Coverage/1f971260db1e46638bd3fd91e3ebf668"></a>)

[//]: # (  &nbsp;)
  <a href="https://app.codacy.com/gh/ArcadeData/arcadedb?utm_source=github.com&utm_medium=referral&utm_content=ArcadeData/arcadedb&utm_campaign=Badge_Grade_Settings"><img src="https://api.codacy.com/project/badge/Grade/d40cc721f39b49eb81408307960f145b"></a>
  &nbsp;
  <a href="https://www.meterian.io/report/gh/ArcadeData/arcadedb"><img src="https://www.meterian.io/badge/gh/ArcadeData/arcadedb/security?branch=main"></a>
  &nbsp;
  <a href="https://www.meterian.io/report/gh/ArcadeData/arcadedb"><img src="https://www.meterian.io/badge/gh/ArcadeData/arcadedb/stability?branch=main"></a>
</p>

## ✨ What this repo provides

- Native Python bindings for ArcadeDB with a bundled JRE (no local Java required).
- Wheels for Linux x86_64, Linux ARM64, and macOS Apple Silicon.
- Embedded usage (in-process) with optional server mode.
- Tests and examples validated in CI across supported platforms.

The Python bindings and packaging live under bindings/python. The upstream Java project remains the source of the core database.

## 🧱 What’s inside

- bindings/python: Python package source, build scripts, tests, and examples.
- docs site: https://docs.humem.ai/arcadedb/
- CI: Build/test workflows for bindings and examples (badges above).

## ✅ Typical use cases

- Local embedded analytics without a separate server process.
- Vector search and graph workloads from Python.
- Running ArcadeDB in-process for testing or tooling.

## 🧠 ArcadeDB at a glance

- Multi-model database built for performance.
- Document + Graph + Key/Value + Vector + Time Series in one engine.
- Supports SQL, OpenCypher, and MongoDB query language.

- Embedded from any language on top of the Java Virtual Machine
- Embedded from Python via bindings: [arcadedb-embedded-python](https://github.com/humemai/arcadedb-embedded-python)
- Remotely by using [HTTP/JSON](https://docs.arcadedb.com#HTTP-API)
- Remotely by using a [Postgres driver](https://docs.arcadedb.com#Postgres-Driver) (ArcadeDB implements Postgres Wire protocol)
- Remotely by using a [Redis driver](https://docs.arcadedb.com#Redis-API) (only a subset of the operations are implemented)
- Remotely by using a [MongoDB driver](https://docs.arcadedb.com#MongoDB-API) (only a subset of the operations are implemented)

- Lightweight Java 25 runtime (jlink) bundled per platform.
- ArcadeDB JARs required for the embedded engine.
- Python bindings and source modules.

## ✨ ArcadeDB capabilities (via Python)

- Multi-model: Graph, Document, Key/Value, Vector, Time Series.
- Query languages: SQL, OpenCypher, MongoDB.
- ACID transactions and high performance.

## 🚀 Quick start (Python)

```bash
uv pip install arcadedb-embedded
```

See [the Python README](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/README.md) for usage, examples, and build details.

## 🔗 Quick Links

- Python README: https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/README.md
- PyPI: https://pypi.org/project/arcadedb-embedded/

## 🧭 Upstream ArcadeDB (Java)

This repo is a fork of ArcadeDB Java. For the server, Java API, and core database docs:

- Upstream repo: https://github.com/ArcadeData/arcadedb
- Docs: https://docs.arcadedb.com

## 💬 Support & community

- Issues (Python bindings): https://github.com/humemai/arcadedb-embedded-python/issues
- ArcadeDB Discord: https://discord.gg/w2Npx2B7hZ

## 📄 License

Both upstream ArcadeDB (Java) and this ArcadeDB Embedded Python project are licensed under Apache 2.0, which is fully open and free for everyone, including commercial use.

Apache License 2.0 – see https://github.com/humemai/arcadedb-embedded-python/blob/main/LICENSE
