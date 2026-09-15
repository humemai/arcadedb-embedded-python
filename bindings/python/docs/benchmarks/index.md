# Benchmarks

ArcadeDB is measured against the engines you would otherwise reach for: PostgreSQL and
DuckDB for documents, Neo4j for graphs, Qdrant and Milvus for vectors, QuestDB and
TimescaleDB for time series, and the other multi-model engines that claim the same ground.
This section documents how those numbers are produced, so you can decide whether they mean
anything before you rely on them.

!!! tip "The results live on the project page"
    Every table, every figure, and every measured number is published at
    **[humem.ai/projects/arcadedb](https://humem.ai/projects/arcadedb)**.
    These documentation pages carry the method only, and no results.

    There is one copy of the numbers on purpose. Each table is generated from one frozen
    payload and pinned by gates that fail a publish when a cell moves. A second copy in
    the documentation would either drift the first time a campaign re-measured something,
    or it would need the same gates on a second site for no gain.

## What the Suite Is

Two benchmark suites live in the repository, and they answer different questions.

| Suite | Question | Documented in |
|---|---|---|
| [`benchmarks/experiments/`](https://github.com/humemai/arcadedb-embedded-python/tree/main/benchmarks/experiments) | Engine against engine. How does ArcadeDB compare with specialist and embedded databases on the same corpus, the same machine, and the same operation? | These pages |
| [`benchmarks/python-bindings/`](https://github.com/humemai/arcadedb-embedded-python/tree/main/benchmarks/python-bindings) | Binding against binding. What does reaching the same engine through Python cost against calling it from Java? | [Performance: Python Bindings vs Java](../guide/performance.md) |

The rest of this section is about the first suite. It runs every engine in Docker, one
cell at a time, with pinned image digests, an identical CPU set and memory envelope per
cell, and five repetitions reported as the median with its spread. Every timed query's
answer is canonicalised and compared across the engines of its table before any latency is
published, which is the part that separates it from a stopwatch.

## The Lanes

A **lane** is one workload script that puts every engine through the same operations
against the same corpus. Each lane feeds one or two tables on the project page.

| Lane | Workload | Corpus | Table |
|---|---|---|---|
| Document OLTP | TPC-C new-order and payment, plus one record inserted, read by key, updated, and deleted | TPC-H at scale factor 1 | [Documents](https://humem.ai/projects/arcadedb#documents) |
| Document OLAP | TPC-H Q1 and Q6, top parts by revenue, count by ship mode, and revenue by month | TPC-H at scale factor 1 | [Documents](https://humem.ai/projects/arcadedb#documents) |
| Graph OLTP | Point lookup, one hop, two hops, three hops with a property filter, insert, update, and delete | LDBC-SNB at SF1 and SF10 | [Graph](https://humem.ai/projects/arcadedb#graph) |
| Graph OLAP | Average friend age, friendships within a city, most friends, degree distribution, and triangle count, with and without ArcadeDB's Graph Analytical View | LDBC-SNB at SF1 and SF10 | [Graph](https://humem.ai/projects/arcadedb#graph) |
| Dense vectors | Nearest-neighbour search at k=10, plus an insert into a built index and a delete from one | SIFT1M and DEEP-10M | [Vectors](https://humem.ai/projects/arcadedb#vectors) |
| Sparse vectors | Learned-sparse retrieval at k=10 | Big-ANN 2023 sparse track | [Vectors](https://humem.ai/projects/arcadedb#vectors) |
| Time series | Newest reading, a twelve-hour aggregate, a double group-by, a high-usage filter, and a group-by with ordering and a limit | TSBS cpu-only | [Time series](https://humem.ai/projects/arcadedb#timeseries) |
| Cross-model | One transaction that writes a document, a graph edge, and a vector together; the same transaction interrupted; a retrieval path; and a graph-filtered vector search | Generated product set | [Cross-model](https://humem.ai/projects/arcadedb#crossmodel) |
| Session lifecycle | Open, one query, one write, and close, across what a database contains | Each model at four sizes | [Python](https://humem.ai/projects/arcadedb#embedded) |
| Deployment split | The same work in-process, over in-process HTTP, and against a separate container | Result sizes from one document to a hundred thousand | [Python](https://humem.ai/projects/arcadedb#embedded) |
| Python materialization | The same result taken through each Python materialization API, against the Java baseline | One scan and one vector search | [Python](https://humem.ai/projects/arcadedb#embedded) |

The query set is fixed at forty operations and closed to additions for the current
campaign. Eighteen of the forty come from a published benchmark rather than from us.

## The Corpora

No lane that reaches a table runs on a generated corpus where a published one exists. Each
lane reads real data from a mount, and a lane that cannot find its corpus is refused rather
than allowed to fall back to a synthetic generator.

- **TPC-H** at scale factor 1, generated with DuckDB's `dbgen` and staged as Parquet. The
  document lanes read the line-item tables as documents. The transactional operations are
  TPC-C inspired rather than an audited TPC-C run, and the page says so.
- **LDBC-SNB Interactive v1**, the Linked Data Benchmark Council's social network, at SF1
  and SF10, projected onto persons and their `KNOWS` edges.
- **SIFT1M** and **DEEP-10M** for dense vectors, from the ann-benchmarks distributions,
  with the exact ground truth each ships so recall is measured rather than assumed.
- **Big-ANN 2023 sparse track**: a SPLADE encoding of MS MARCO passages at three sizes,
  with the challenge's own top-k ground truth.
- **TSBS**, the Time Series Benchmark Suite's cpu-only data set, generated from a recipe
  in the repository so the corpus can be rebuilt rather than merely copied.
- A generated product set for the cross-model lane, where each product carries a document,
  an edge, and an embedding, because no published benchmark writes all three in one
  transaction.

## The Engines

ArcadeDB runs **both deployments on every table**: embedded in the Python process, and as a
server reached over HTTP, built from one upstream commit and running one JVM on both sides,
so the axis between them is transport and nothing else.

The comparators are pinned by image digest, and each one is the engine a reader would
actually reach for on that workload.

| Where they run | Engines |
|---|---|
| Documents and analytics | PostgreSQL (at its image defaults and tuned), DuckDB, SQLite, MongoDB, SurrealDB, ArangoDB |
| Graph | Neo4j, LadybugDB, SurrealDB, ArangoDB |
| Dense vectors | Qdrant, Milvus, Chroma, LanceDB, sqlite-vec, DuckDB VSS, pgvector, Neo4j's vector index, SurrealDB, ArangoDB |
| Sparse vectors | Elasticsearch, Milvus, Qdrant, pgvector |
| Time series | QuestDB, TimescaleDB, DuckDB, SQLite, MongoDB |
| Cross-model | PostgreSQL with pgvector and Apache AGE, Neo4j's vector index, SurrealDB, ArangoDB, and a composed Qdrant plus Neo4j stack |

Engines that offer both an embedded and a served form get a row for each, which is why
SurrealDB appears twice. Every comparator version is the latest self-hosted stable release
at measurement time, re-surveyed at each campaign, and restated at the freeze.

## What Each Table Argues

A table is worth printing only if it answers a question a reader actually has.

- **[Documents](https://humem.ai/projects/arcadedb#documents)**: whether an engine that
  stores documents can serve the transactional and analytical workloads people usually
  reach for a relational database to run. This is the workload ArcadeDB loses by the widest
  margin, and it is on the page for that reason.
- **[Graph](https://humem.ai/projects/arcadedb#graph)**: whether traversals and graph
  analytics hold up against a dedicated graph database, and what ArcadeDB's Graph
  Analytical View buys, measured with the view both on and off so the accelerator is priced
  rather than assumed.
- **[Vectors](https://humem.ai/projects/arcadedb#vectors)**: whether a multi-model engine
  can search embeddings at a recall a specialist vector store would accept. Latency without
  recall is not a comparison, so both are always printed, at matched operating points.
- **[Time series](https://humem.ai/projects/arcadedb#timeseries)**: whether the native
  time-series type is worth using against engines built for nothing else.
- **[Cross-model](https://humem.ai/projects/arcadedb#crossmodel)**: the page's central
  claim. One transaction writes a document, an edge, and a vector, and the same transaction
  is interrupted to see what survives. A composed stack of two specialist systems cannot
  offer that, and the table shows the difference as torn results rather than as an opinion.
- **[Python](https://humem.ai/projects/arcadedb#embedded)**: what the embedded package
  costs. Session cost from open to close, what the client and server split costs, and what
  each Python materialization API costs against Java on the same JARs.

## What the Suite Does Not Measure

Stated here because an absent number is a claim too.

- **Concurrency and load.** It needs a load generator that is not Python; our own harness
  is censored by GIL queueing above a handful of clients, and a bad concurrency table is
  worse than a disclosed absence.
- **Import, export, and backup**, and replication beyond one failover trial.
- **Durability outside the one matched relaxed class** on reads. The timed writes run at
  both settings; everything else runs at one.
- **Anything across a real network.** Served engines run in a sibling container on the same
  host.
- **Dense dimensionality above 128, and k other than 10.**

## Where to Go Next

<div class="grid cards" markdown>

-   :material-ruler-square:{ .lg .middle } [**Protocol**](protocol.md)

    One machine, one job at a time, fixed limits, five repetitions, and the fairness
    invariants a comparison has to satisfy

-   :material-equal:{ .lg .middle } [**Answer Checking**](equivalence.md)

    Every timed query's answer is canonicalised and compared across engines, which is why
    this is a benchmark and not a stopwatch

-   :material-play-circle:{ .lg .middle } [**Running a Lane**](running.md)

    The pinned images, the corpora, and one lane end to end on your own machine

-   :material-table-search:{ .lg .middle } [**Reading the Output**](results.md)

    The frozen file, the fields that trap people, and how the project page is generated
    and gated

</div>
