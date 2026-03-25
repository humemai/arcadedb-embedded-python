# VLDB 2025 Accepted Papers — Summaries

## Cost-Effective, Low Latency Vector Search with Azure Cosmos DB (2505.05885v2)

- Problem: Operational databases need native vector search without data duplication into specialized vector DBs.
- Approach: Deeply integrate DiskANN into Cosmos DB’s Bw-Tree, storing quantized vectors and adjacency lists as index terms and keeping one vector index per partition in sync with document data.
- Key techniques: Rewritten DiskANN with decoupled storage layout and async providers; quantized-space search with reranking; filter-aware and paginated graph search; sharded DiskANN for multi-tenant and label-based filtering.
- Datasets: Wiki-Cohere (35M Wikipedia embeddings, 768D), MS Turing (1B query embeddings, 100D), YFCC (1M CLIP 192D with metadata). Runbooks for update stability: expiration-time and clustered distribution-shift scenarios.
- Experiments: Up to 10M vectors per partition and 1B total vectors; latency/recall/cost vs search depth; filter-aware vs post-filtering; ingestion throughput and CPU breakdown; sharded vs non-sharded indexing; recall stability under updates.
- Comparisons: Cost comparisons against Pinecone, Zilliz, and DataStax serverless offerings using published pricing. Qualitative comparisons to SingleStore-V, Elastic, JVector/DataStax, pgvector/pgvectorscale.
- Results: ~20 ms query latency on 10M vectors; cost roughly 12× to 43× lower than Zilliz/Pinecone serverless enterprise tiers (10M, 768D). Stable recall under updates and scalable to billions of vectors via partitioning.

## TuskFlow: An Efficient Graph Database for Long-Running Transactions (p4777-theodorakis)

- Problem: “Mammoth” graph transactions (long-running, large read-write sets) block or abort short-lived transactions under 2PL/MVCC.
- Approach: Deterministic protocol based on Aria that reorders short-lived transactions around mammoths within epochs; mammoths are split into budgeted tasks and tracked with visited/pending states.
- Key techniques: Graph tagging to narrow mammoth conflict regions; workload-aware graph partitioning (RPatternM); parallel mammoth execution; transaction reordering to reduce aborts.
- Datasets: LDBC SNB (SF10), DBpedia, USRoad; additional mention of WikiTalk in setup comparisons. Mammoth queries based on LDBC BI variants (balanced/unbalanced) and graph maintenance tasks.
- Experiments: Tail latency/throughput under mammoths; partitioning impact under skewed workloads; optimization breakdown for tagging/partitioning/parallelism; epoch and budget tuning; scalability with increasing tx/s.
- Comparisons: Baselines include 2PL (Neo4j’s Forseti) and Postgres MVCC. Aria discussed qualitatively; experiments focus on 2PL and Postgres.
- Results: Order-of-magnitude improvements in tail latency and throughput vs 2PL/MVCC; mammoths complete without blocking short-lived work.

## Towards Principled, Practical Document Database Design (p4804-carey)

- Problem: Document DB schema design is often ad hoc and application-first, leading to brittle or inefficient designs.
- Approach: A data-first, ER-driven methodology for JSON schema design that mirrors relational conceptual/logical design and preserves data independence.
- Key guidance: Map ER entities to collections, composite attributes to nested objects, multivalued attributes/weak entities to arrays, and inheritance to a unified collection with subtype indicators.
- Anti-patterns: Unbounded nesting, data-as-metadata, arrays-as-fields, non-uniform nesting, scalar heterogeneity, mixed anti-patterns, and failure to embrace diversity; each with cures.
- Experiments: Primarily a methodology paper; includes a small empirical timing example comparing query latency with/without redundancy on a synthetic workload (100K products, 500K customers, 1M orders) to illustrate trade-offs. No broad system benchmarks or ablations.

## Cloudy With a Chance of JSON (p4938-carey)

- Problem: Analytics over JSON data across operational DBs, RDBMSs, and object storage often requires heavy ETL and rigid schemas.
- Approach: Couchbase Capella Columnar—a cloud-native, columnar JSON analytics service using SQL++ with storage/compute separation and MPP execution.
- Key features: Native JSON analytics; streaming/shadowed ingestion from Couchbase and non-Couchbase sources; external object store queries; cost-based optimization; SQL++ UDFs and Python UDFs; support for BI tools.
- Experiments: System/experience paper with examples and architecture walkthrough; no explicit benchmark datasets or ablation studies.

## GaussDB-Vector: A Large-Scale Persistent Real-Time Vector Database for LLM Applications (p4951-sun)

- Problem: Existing vector databases struggle with real-time updates, disk-based performance, and large-scale distributed search.
- Approach: Persistent, real-time vector DB with page-based storage, IVF and Vamana graph indexes, PQ, and hardware acceleration.
- Key techniques: Two-layer IVF clustering with contiguous data pages; graph index layouts tuned for I/O locality; neighbor pruning; caching of PQ tables/codes; vacuum for deleted vectors; SIMD/NPUs/GPUs and parallelism.
- Datasets: SIFT (10M, 128D), GIST (1M, 960D), HUAWEINet (15M, 1024D), hybrid variants with scalar columns, and SIFT-10B for scaling.
- Experiments: Vector search performance and hybrid search; distributed scalability on SIFT-10B; hardware acceleration (NPUs/SIMD). Cluster of 40 machines (72 cores, 64GB RAM, 2TB disk; one node with 8 NPUs).
- Comparisons: Baselines include ElasticSearch, Milvus, and PGVector (all using HNSW in their evaluation). GaussDB-Vector uses graph index for vector-only and hybrid index for multi-column queries.
- Results: Reported 1–5× performance improvements over baselines; supports hybrid scalar-vector queries and distributed scaling.

## GalaxyWeaver: Autonomous Table-to-Graph Conversion and Schema Optimization with LLMs (p5100-tong)

- Problem: Table-to-graph conversion is error-prone and often produces suboptimal schemas for query workloads.
- Approach: LLM-guided framework that automates conversion and iteratively optimizes graph schemas with query awareness and domain knowledge.
- Key techniques: Rule-based conversion from PK/FK to vertices/edges; optimization strategies (convert vertices to edges, move properties to edges, extract properties into vertices, remove redundancy, adjust edge directions); prompt-guided Advisor + Executor + optional human Adjuster.
- Datasets: 4DBInfer corpora — AVS (349,967,371 rows), AB (24,291,489), SE (5,399,818), MAG (21,847,396). Reported graph sizes for basic vs optimized graphs.
- Experiments: Compare three representations per dataset: relational tables (MySQL), basic graph (Galaxybase), optimized graph (GalaxyWeaver). Each query run 10 times; normalized performance with optimized graph as baseline. LLM generation statistics over 10 runs per dataset using GPT-4o.
- Comparisons: Baselines are relational tables and basic graph conversion (PK/FK only). No comparisons to external graph conversion tools.
- Results: Optimized graphs reduce hop counts and execution time for join-heavy workloads; schema optimization rates 74–100% on correct schemas.
