# Benchmarks

ArcadeDB is measured against the engines you would otherwise reach for: PostgreSQL and
DuckDB for documents, Neo4j for graphs, Qdrant and Milvus for vectors, QuestDB and
TimescaleDB for time series, and the other multi-model engines that claim the same ground.
This section documents how those numbers are produced, so you can decide whether they mean
anything before you rely on them.

!!! tip "The results live on the DBBench page"
    Every table, every figure, and every measured number is published at
    **[humem.ai/research/dbbench](https://humem.ai/research/dbbench)**.
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

These pages describe the 2026-11 instrument, settled before its first cell so that nothing
changes under the rows (a mid-campaign change splits them). The page publishes 2026-11 rows
only, and a table appears on it when its rows are frozen, so where a corpus size or an engine
list here is ahead of what the page prints, that is the gap between the instrument and the
rows it has produced so far, and the page's own notes say which sizes it carries.

The rest of this section is about the first suite. It runs every engine in Docker, one
cell at a time, with pinned image digests, an identical CPU set and memory envelope per
cell, and five repetitions reported as the median with its spread. Every timed query's
answer is canonicalised and compared across the engines of its table before any latency is
published, which is the part that separates it from a stopwatch.

## The Lanes, Corpora, and Engines

A **lane** is one workload script that puts every engine through the same operations
against the same corpus, and each lane feeds one or two tables on the DBBench page. No
lane that reaches a table runs on a generated corpus where a published one exists, and a
lane that cannot find its corpus is refused rather than allowed to fall back to a
synthetic generator.

- **Documents**: TPC-C inspired transactions (not an audited TPC-C run) and TPC-H analytics,
  on TPC-H at scale factors 1 and 10. Engines: PostgreSQL, DuckDB, SQLite, MongoDB,
  SurrealDB, ArangoDB.
- **Graph**: point lookups, hops, writes, and fourteen whole-graph analytical queries,
  nine of them LSQB's, on LDBC-SNB. Engines: Neo4j, Memgraph, FalkorDB, LadybugDB, DuckDB
  with DuckPGQ, SurrealDB, ArangoDB, MongoDB.
- **Dense and sparse vectors**: nearest-neighbour and learned-sparse retrieval at k=10, on
  SIFT1M, DEEP-10M, and the Big-ANN 2023 sparse track, with the exact ground truth each
  ships. Engines include Qdrant, Milvus, Chroma, LanceDB, pgvector, and Elasticsearch.
- **Time series**: TSBS cpu-only at 100 and 1,000 hosts. Engines: QuestDB, TimescaleDB,
  DuckDB, SQLite, MongoDB, SurrealDB, ArangoDB.
- **Cross-model**: one transaction that writes a document, a graph edge, and a vector
  together, and the same transaction interrupted, on a generated product set because no
  published benchmark writes all three at once. Engines: PostgreSQL with pgvector and
  Apache AGE, Neo4j, SurrealDB, ArangoDB, MongoDB, and a composed Qdrant plus Neo4j stack.
- **Python**: session lifecycle, the deployment split (in-process, in-process HTTP, separate
  container), and Python materialization against the Java baseline.

The query set is fixed for the current campaign and twenty-seven of its operations come from
a published benchmark rather than from us. The exact lane list, the queries, and what each
LSQB query counts are in
[`PAGE-SPEC.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PAGE-SPEC.md),
and the engine list, versions, and pins are in
[`COMPARATORS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/COMPARATORS.md).

ArcadeDB runs **both deployments on every table**: embedded in the Python process, and as a
server reached over HTTP, built from one upstream commit and running one JVM on both sides,
so the axis between them is transport and nothing else. Engines that offer both forms get a
row for each. An engine with no native type for a workload still runs it the way its own
users would, and a comparator is left off a table only when its documentation and an exact
error show the query cannot be expressed.

## What Each Table Argues

A table is worth printing only if it answers a question a reader actually has.

- **[Documents](https://humem.ai/research/dbbench/tables)**: whether an engine that
  stores documents can serve the transactional and analytical workloads people usually
  reach for a relational database to run. This is the workload ArcadeDB loses by the widest
  margin, and it is on the page for that reason.
- **[Graph](https://humem.ai/research/dbbench/graphs)**: whether traversals and graph
  analytics hold up against a dedicated graph database, and what ArcadeDB's Graph
  Analytical View buys, measured with the view both on and off so the accelerator is priced
  rather than assumed.
- **[Vectors](https://humem.ai/research/dbbench/vectors)**: whether a multi-model engine
  can search embeddings at a recall a specialist vector store would accept. Latency without
  recall is not a comparison, so both are always printed, at matched operating points.
- **[Time series](https://humem.ai/research/dbbench/time-series)**: whether the native
  time-series type is worth using against engines built for nothing else.
- **[Cross-model](https://humem.ai/research/dbbench/cross-model)**: the page's central
  claim. One transaction writes a document, an edge, and a vector, and the same transaction
  is interrupted to see what survives. A composed stack of two specialist systems cannot
  offer that, and the table shows the difference as torn results rather than as an opinion.
- **[Python](https://humem.ai/research/dbbench/lifecycle)**: what the embedded package
  costs. Session cost from open to close, what the client and server split costs, and what
  each Python materialization API costs against Java on the same JARs.

## What the Suite Does Not Measure

Stated here because an absent number is a claim too.

- **Concurrency and load.** It needs a load generator that is not Python; our own harness
  is censored by GIL queueing above a handful of clients, and a bad concurrency table is
  worse than a disclosed absence.
- **Import, export, and backup**, and replication beyond one failover trial.
- **Durability outside the matched relaxed class.** The timed writes are the exception and
  run at both settings; ingest and everything else run at one.
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

    The frozen file, the fields that trap people, and how the DBBench page is generated
    and gated

</div>
