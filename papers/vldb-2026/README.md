# ArcadeDB: Executing Hybrid Vector, Relational, and Graph Queries in an Embedded Database

## 0. Paper at a glance

**Thesis:** A single embedded multi-model DB can support **SQL-style relational queries**, **graph traversals**, **vector similarity search**, and **hybrid combinations** on a realistic dataset (Stack Overflow), with measurable trade-offs vs **PostgreSQL + pgvector**.

**Industrial-track positioning:** Experience report + evaluation + lessons learned (not algorithm novelty).

---

## 1. Abstract (150–200 words)

- **Context:** Hybrid retrieval workloads increasingly combine vectors + filters + relationships; polyglot stacks add complexity and consistency issues.
- **System:** ArcadeDB supports documents/relational-like types, graph (vertices/edges), and ANN vector indexes in one engine; evaluated in **embedded mode**.
- **Workload:** Stack Overflow dataset (`stackoverflow-medium`, ~5.6M records), mapped to relational types + graph edges + embeddings.
- **Evaluation plan:** ingestion throughput, index build time/size, query latency (p50/p95), update costs; compare to PostgreSQL + pgvector baseline.
- **Expected findings (placeholder):** [2–3 headline results once measured].
- **Takeaways:** practical lessons on pagination, indexing, batching, and embedded execution.

---

## 2. Introduction

### 2.1 Problem

- Modern “retrieval-centric” applications require:
  - vector top-k
  - structured predicates (score/time/tags)
  - relationship-based context (threads, citations, authorship)

- Typical implementation: **polyglot** (RDBMS + vector store + optional graph DB).
- Costs:
  - duplicated data and IDs
  - cross-system consistency logic
  - operational overhead
  - harder reproducibility

### 2.2 Why embedded multi-model

- Embedded eliminates network hop and reduces measurement variability.
- One engine → one transaction boundary and one ID space.

### 2.3 What this paper contributes (state as “experience + findings”)

1. A practical account of executing **relational + graph + vector** queries in one embedded engine on a realistic dataset.
2. An evaluation (planned) of ingestion, index build, and hybrid query performance; comparison with PostgreSQL + pgvector.
3. Transferable lessons (pagination, filter ordering, index lookups, batching, transaction sizing, embedded tuning).

### 2.4 Non-goals (explicit)

- No new ANN algorithms / embeddings
- No distributed/multi-node evaluation
- No claim of universal superiority over PostgreSQL
- RAG is motivation, not a contribution

---

## 3. System Background: ArcadeDB Embedded Multi-Model Engine

### 3.1 Data model and storage primitives

- Records: **Document**, **Vertex**, **Edge**
- Types ≈ tables; schema optional
- Buckets as physical storage partitions (mention for ingestion parallelism if relevant)

### 3.2 Query interfaces

- SQL dialect for documents/relational-style queries
- OpenCypher for graph traversal
- Embedded Java API (and how Python calls it, if relevant)

### 3.3 Vector indexing and search

- ANN index type (HNSW via JVector)
- Core parameters to report later:
  - `M`, `efConstruction`, `efSearch`, distance metric

- Index lifecycle:
  - build, persist, load, update behavior (state what is supported/assumed)

### 3.4 Embedded execution model

- Single-process JVM runtime
- Resource considerations:
  - heap sizing
  - GC
  - file system + caching assumptions

---

## 4. Dataset and Multi-Model Mapping

### 4.1 Dataset: Stack Overflow (medium)

State:

- source (StackExchange dump), snapshot date
- scale: use your expected counts (~5.56M total)

### 4.2 Relational/document schema (Types)

Describe main types and key fields:

- User, Post, Comment, Tag, Vote, PostLink, PostHistory, Badge

Include:

- primary keys
- core foreign keys used for edges (OwnerUserId, PostId, ParentId, etc.)

### 4.3 Graph construction

Define vertices/edges used:

- Vertices: User, Post, Tag (or Post as Vertex and others as Documents—state choice)
- Edges:
  - User→Post ASKED/ANSWERED
  - Post→Post ANSWER_TO
  - Post→Tag HAS_TAG
  - User→Post COMMENTED/VOTED
  - (Optional) Post→Post LINKED (from PostLink)

### 4.4 Vector embeddings

Define:

- embedding targets (Post Title+Body, TagName)
- embedding dimensionality
- model (name + version)
- how vectors are stored and indexed (per-type vector index)

### 4.5 Representative hybrid query patterns

Provide 3 “canonical” query patterns you will evaluate:

1. vector-only similarity search
2. vector + structured filters
3. vector + graph predicate / traversal expansion (optional)

---

## 5. Workloads (What we measure)

Keep to **3–5 workloads**, each with clear input/output.

### W1: Ingestion (Documents/Types)

- streaming parse (XML)
- batch insertion
- measure throughput and peak memory

### W2: Graph materialization

- edge creation between types
- measure edges/s, total time, memory

### W3: Vector index build

- build index for Post vectors (and Tag vectors if included)
- measure build time, index size, memory footprint

### W4: Query latency (Vector + Hybrid)

Define query families:

- Q1 vector-only: top-k similar posts
- Q2 vector + filters: score/time/tag constraints
- Q3 vector → graph: retrieve seed posts then traverse to answers/users/tags

### W5: Updates (optional but valuable)

- re-embed X% of posts
- metadata updates
- measure update throughput + effect on index

---

## 6. Experimental Setup

### 6.1 Hardware/software

Single table (to fill later):

- CPU, RAM, NVMe
- OS/kernel
- JVM distribution + version
- ArcadeDB version
- Postgres + pgvector versions
- Python version (if measurement harness is Python)

### 6.2 Compared systems

**C1: ArcadeDB embedded**

- heap size (e.g., 32GB)
- vector index params (M, ef\*)
- caching config

**C2: PostgreSQL + pgvector**

- deployment: local server + local client connections
- index method: HNSW or IVFFlat (pick one, justify)
- analogous parameter choices
- tuning budget statement (“comparable effort budget”)

### 6.3 Metrics

**Ingestion/update**

- rows/s
- edges/s
- time-to-index
- update ops/s

**Latency**

- p50/p95
- QPS under controlled concurrency (optional)

**Footprint**

- index size on disk
- peak RSS / heap
- optional CPU utilization

**Correctness / quality (optional)**

- If you evaluate recall@k, define ground truth procedure; otherwise omit.

---

## 7. Evaluation (mocked now; fill with results later)

Each subsection ends with a short “takeaway”.

### 7.1 Ingestion performance (W1)

Report:

- per-table import time
- overall throughput
- effect of batch size and transaction boundaries

Figures/tables:

- Table: import times by type
- Figure: throughput vs batch size (optional)

### 7.2 Graph materialization performance (W2)

Report:

- time to create edges
- compare strategies:
  - index-based lookup vs join/IN queries

- show effect of RID pagination

Figures/tables:

- Table: edges created and rate
- Figure: edge creation throughput over time (optional)

### 7.3 Vector index build (W3)

Report:

- build time
- index size
- memory peak
- sensitivity to `M`, `efConstruction`

Figures/tables:

- Table: index params vs build time/size
- Figure: build time vs dataset size (small→medium) (optional)

### 7.4 Query latency: vector-only (Q1)

Report:

- p50/p95 for k=10/50/100
- effect of efSearch
- compare ArcadeDB vs Postgres+pgvector

Figures:

- p95 latency vs k
- p95 latency vs efSearch

### 7.5 Query latency: vector + structured filters (Q2)

Report:

- latency under different filter selectivities
- explain whether filtering happens pre/post candidate generation (system behavior)

Figures:

- p95 latency vs selectivity bucket

### 7.6 Query latency: vector + graph constraints (Q3) (optional)

If included:

- traversal depth 1/2
- number of expansions
- impact on latency

### 7.7 Update costs (W5)

Report:

- re-embedding X% posts
- delete/update throughput
- index maintenance behavior (incremental vs rebuild if applicable)

### 7.8 Summary comparison

One summary table of headline metrics:

- ingestion, build, p95 latencies, index size, update throughput

**Important framing:** present as _trade-offs_, not “better”.

---

## 8. Lessons Learned (core industrial section)

Write 5–7 lessons, each with:

- **Problem**
- **What we tried**
- **What worked**
- **Why it generalizes**

Suggested lessons based on your existing work:

1. RID-based pagination beats OFFSET/LIMIT at scale
2. Nested scan+filter avoids sparse-match skipping
3. Index-based vertex resolution dominates join-based approaches
4. Batch sizing and transaction boundaries dominate throughput
5. Embedded mode reduces variability but increases sensitivity to heap/GC tuning
6. Hybrid query planning requires explicit attention to filter selectivity and candidate set size
7. Multi-model unification simplifies consistency and IDs, but introduces shared-resource contention trade-offs

---

## 9. Related Work

Organize tightly:

- Vector search in DBs (extensions + native)
- Multi-model DBs (document+graph; unified engines)
- Embedded DB systems
- Hybrid retrieval pipelines / polyglot architectures

Keep it short and relevant.

---

## 10. Limitations and Future Work

### Limitations

- Single-node evaluation
- One dataset
- Embedded mode focus (server mode not evaluated)
- Limited parameter tuning budget

### Future work

- scaling study (medium→large) once feasible
- additional datasets (optional)
- deeper study of incremental vector updates
- server deployment evaluation

---

## 11. Conclusion

Restate:

- feasibility of hybrid queries in one embedded engine
- what performance/operational trade-offs were observed
- practical guidance for practitioners

---

## Appendix (optional but useful)

### A. Query templates

- Provide example SQL, Cypher, and hybrid query patterns (short)

### B. Reproducibility checklist

- dataset hash, commit hash, configs, scripts

---

## “Mock now” guidance (what to fill later)

To make this skeleton “real”, you only need to produce **~10 numbers**:

- import throughput + total time
- edge creation time
- vector index build time + size
- p95 vector latency (k=10) for ArcadeDB + Postgres
- p95 hybrid latency for ArcadeDB + Postgres
- update throughput (optional)

Once you have those, the paper becomes credible.

If you want, next I can output this as an **Overleaf-ready LaTeX outline** (`\section{}` + bullet placeholders) so you can paste directly.
