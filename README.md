# ArcadeDB Embedded for Python

Native Python bindings for ArcadeDB (forked from the official Java project).

[![PyPI](https://img.shields.io/pypi/v/arcadedb-embedded)](https://pypi.org/project/arcadedb-embedded/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arcadedb-embedded)](https://pypi.org/project/arcadedb-embedded/)
[![Docs](https://img.shields.io/badge/docs-humem.ai-blue)](https://docs.humem.ai/arcadedb/latest/)
[![Test Python Bindings](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-bindings.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-bindings.yml)
[![Test Python Examples](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-examples.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/test-python-examples.yml)
[![Release to PyPI](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/release-python-packages.yml/badge.svg)](https://github.com/humemai/arcadedb-embedded-python/actions/workflows/release-python-packages.yml)

---

## ✨ What this repo provides

<p align="center">
	<a href="https://github.com/arcadedata/arcadedb"><img height="25" src="studio/src/main/resources/static/images/social/github.svg" alt="Github"></a>
	&nbsp;
  <a href="https://www.linkedin.com/company/arcadedb/"><img height="25" src="studio/src/main/resources/static/images/social/linkedin.svg" alt="LinkedIn"></a>
  &nbsp;
  <a href="https://bsky.app/profile/arcadedb.bsky.social"><img height="25" src="studio/src/main/resources/static/images/social/bluesky.svg" alt="Bluesky"></a>
  &nbsp;
  <a href="https://twitter.com/arcade_db"><img height="25" src="studio/src/main/resources/static/images/social/twitter.svg" alt="Twitter"></a>
  &nbsp;
  <a href="https://www.youtube.com/@ArcadeDB"><img height="25" src="studio/src/main/resources/static/images/social/youtube.svg" alt="Youtube"></a>
  &nbsp;
  <a href="https://discord.gg/w2Npx2B7hZ"><img height="25" src="studio/src/main/resources/static/images/social/discord.svg" alt="Discord"></a>
  &nbsp;
  <a href="https://stackoverflow.com/questions/tagged/arcadedb"><img height="25" src="studio/src/main/resources/static/images/social/stack-overflow.svg" alt="StackOverflow"></a>
	&nbsp;
	<a href="https://arcadedb.com/blog/"><img height="25" src="studio/src/main/resources/static/images/social/blog.svg" alt="Blog"></a>
</p>

The Python bindings and packaging live under bindings/python. The upstream Java project remains the source of the core database.

## 🧱 What’s inside

- bindings/python: Python package source, build scripts, tests, and examples.
- docs site: https://docs.humem.ai/arcadedb/
- CI: Build/test workflows for bindings and examples (badges above).

- [Graph Database](https://docs.arcadedb.com#graph-model) (compatible with Neo4j Cypher, Apache Tinkerpop Gremlin and OrientDB SQL)
- [Document Database](https://docs.arcadedb.com#document-model) (compatible with the MongoDB driver + MongoDB queries and OrientDB
  SQL)
- [Key/Value](https://docs.arcadedb.com#keyvalue-model) (compatible with the Redis driver)
- [Search Engine](https://docs.arcadedb.com/#searchengine-model)
- [Time Series](https://docs.arcadedb.com/#timeseries-model) (with InfluxDB Line Protocol, Prometheus remote_write/read, and PromQL support)
- [Vector Embedding](https://docs.arcadedb.com/#vector-model)
- [Geospatial](https://docs.arcadedb.com/#geospatial-model)

- Local embedded analytics without a separate server process.
- Vector search and graph workloads from Python.
- Running ArcadeDB in-process for testing or tooling.

## 🧠 ArcadeDB at a glance

ArcadeDB key capabilities:

- **70+ Built-in Graph Algorithms** — Pathfinding, centrality, community detection, link prediction, graph embeddings, and more — all available out of the box
- **Parallel Query Execution** — SQL queries leverage multiple CPU cores for faster execution on large datasets
- **Materialized Views** — Pre-computed query results stored and automatically maintained
- **MCP Server** — Built-in [Model Context Protocol](https://docs.arcadedb.com/#mcp) server for AI assistant and LLM integration
- **AI Assistant** — Integrated AI assistant in Studio (Beta) for query help and database management
- **Geospatial Indexing** — Native spatial queries and proximity searches with `geo.*` SQL functions
- **TimeSeries** — Columnar storage with Gorilla/Delta-of-Delta compression, InfluxDB/Prometheus ingestion, PromQL queries, Grafana integration
- **Hash Indexes** — Extendible hashing for faster exact-match lookups alongside LSM-Tree indexes

ArcadeDB can be used as:

- Embedded from any language on top of the Java Virtual Machine
- Embedded from Python via bindings: [arcadedb-embedded-python](https://github.com/humemai/arcadedb-embedded-python)
- Remotely by using [HTTP/JSON](https://docs.arcadedb.com#http-json-api)
- Remotely by using a [Postgres driver](https://docs.arcadedb.com#postgres-driver) (ArcadeDB implements Postgres Wire protocol)
- Remotely by using a [Redis driver](https://docs.arcadedb.com#redis-query-language) (only a subset of the operations are implemented)
- Remotely by using a [MongoDB driver](https://docs.arcadedb.com#mongodb-query-language) (only a subset of the operations are implemented)
- By AI assistants via the built-in [MCP Server](https://docs.arcadedb.com/#mcp) (Model Context Protocol)

- Lightweight Java 25 runtime (jlink) bundled per platform.
- ArcadeDB JARs required for the embedded engine.
- Python bindings and source modules.

### Use Cases

Explore real-world examples in the [arcadedb-usecases](https://github.com/ArcadeData/arcadedb-usecases) repository — self-contained projects with Docker Compose, SQL schemas, and runnable demos covering:

- **Recommendation Engine** — graph traversal + vector similarity + time-series
- **Knowledge Graphs** — co-authorship and citation networks with full-text search
- **Graph RAG** — retrieval-augmented generation with LangChain4j and Neo4j Bolt
- **Fraud Detection** — graph, vector, and time-series signals with Cypher
- **Real-time Analytics** — IoT and service monitoring with time-series
- **Social Network Analytics** — materialized view dashboards with polyglot queries
- **Supply Chain** — multi-tier visibility with PostgreSQL protocol and JavaScript

### Getting started in 5 minutes

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

There are four variants of (about monthly) releases:

- `full` - this is the complete package including all modules
- `minimal` - this package excludes the `gremlin`, `redisw`, `mongodbw`, `graphql` modules
- `headless` - this package excludes the `gremlin`, `redisw`, `mongodbw`, `graphql`, `studio` modules
- `base` - core engine, server, and network only — excludes all optional modules (`console`, `gremlin`, `studio`, `redisw`, `mongodbw`, `postgresw`, `grpcw`, `graphql`, `metrics`)

- Issues (Python bindings): https://github.com/humemai/arcadedb-embedded-python/issues
- ArcadeDB Discord: https://discord.gg/w2Npx2B7hZ

You can also build a **custom distribution** with only the modules you need using the [Custom Package Builder](https://docs.arcadedb.com/#custom-package-builder):

```bash
curl -fsSL https://github.com/ArcadeData/arcadedb/releases/download/26.3.1/arcadedb-builder.sh | \
  bash -s -- --version=26.3.1 --modules=gremlin,studio
```

Available optional modules: `console`, `gremlin`, `studio`, `redisw`, `mongodbw`, `postgresw`, `grpcw`, `graphql`, `metrics`. The builder supports interactive mode, Docker image generation, and offline builds from local Maven repositories.

### Java Versions

Both upstream ArcadeDB (Java) and this ArcadeDB Embedded Python project are licensed under Apache 2.0, which is fully open and free for everyone, including commercial use.

Java 21 packages are available on [Maven central](https://repo.maven.apache.org/maven2/com/arcadedb/) and docker images on [Docker Hub](https://hub.docker.com/r/arcadedata/arcadedb).

We also support Java 17 on a separate branch `java17` for those who cannot upgrade to Java 21 yet through GitHub packages.

To use Java 17 inside your project, add the repository to your `pom.xml` and reference dependencies as follows:

```xml
    <repositories>
        <repository>
            <name>github</name>
            <id>github</id>
            <url>https://maven.pkg.github.com/ArcadeData/arcadedb</url>
        </repository>
    </repositories>
    <dependencies>
      <dependency>
          <groupId>com.arcadedb</groupId>
          <artifactId>arcadedb-engine</artifactId>
          <version>26.3.1-java17</version>
      </dependency>
    </dependencies>
```

Docker images are available on ghcr.io too:

```shell
docker pull ghcr.io/arcadedata/arcadedb:26.3.1-java17
```

### Community

Join our growing community around the world, for ideas, discussions and help regarding ArcadeDB.

- Chat live with us on [Discord](https://discord.gg/w2Npx2B7hZ)
- Follow us on [Twitter](https://twitter.com/arcade_db)
- or on [Bluesky](https://bsky.app/profile/arcadedb.bsky.social)
- Connect with us on [LinkedIn](https://www.linkedin.com/products/arcadedb)
- or on [Facebook](https://www.facebook.com/arcadedb)
- Questions tagged `#arcadedb` on [Stack Overflow](https://stackoverflow.com/questions/tagged/arcadedb)
- View our official [Blog](https://arcadedb.com/blog/)

### Security

For security issues kindly email us at support@arcadedb.com instead of posting a public issue on GitHub.

### License and Attribution

ArcadeDB is Free for any usage and licensed under the liberal [Open Source Apache 2 license](LICENSE). We are committed to remaining **Open Source Forever** — see our [Governance](GOVERNANCE.md) for the structural guarantees that make this more than a promise. If you need commercial support, or you need to have an issue fixed ASAP, check our [pricing page](https://arcadedb.com/pricing.html).

For third-party attributions and copyright notices, see:
- [NOTICE](NOTICE) - Required legal attributions
- [ATTRIBUTIONS.md](ATTRIBUTIONS.md) - Detailed third-party acknowledgments
- [LICENSE](LICENSE) - Full license text
- [GOVERNANCE.md](GOVERNANCE.md) - License guarantee and project governance

### Thanks To

<a href="https://www.yourkit.com"><img src="https://www.yourkit.com/images/yklogo.png"></a> for providing YourKit Profiler to our committers.

### Contributing

We would love for you to get involved with ArcadeDB project.
If you wish to help, you can learn more about how you can contribute to this project in the [contribution guide](CONTRIBUTING.md).

Have fun with data!

The ArcadeDB Team

## Stargazers over time
[![Stargazers over time](https://starchart.cc/ArcadeData/arcadedb.svg?variant=adaptive)](https://starchart.cc/ArcadeData/arcadedb)
