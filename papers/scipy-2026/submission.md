# SciPy 2026 Submission Draft

## Title

**From Transactions to Vectors: Embedded Multi-Model Data Workflows in Scientific Python**

---

## Session Type

- Talk (30 minutes)

## Track

- Data-Driven Discovery, Machine Learning and Artificial Intelligence

---

## Abstract (≤100 words)

Scientific Python workflows often combine transactional updates, graph queries, and
vector retrieval, but these capabilities are usually split across multiple systems. This
talk presents an **embedded, OLTP-first, multi-model** approach using a Java engine with
Python bindings, enabling in-process workflows without separate database infrastructure.
We show how SQL (dialect), Cypher, and HNSW vector indexing/search can coexist in one
local runtime for research and applied ML tasks. Attendees will learn practical design
patterns, tradeoffs, and reproducibility practices for building open, end-to-end data
pipelines with **Apache 2.0** software.

---

## Description (~500 words)

Scientific Python projects increasingly combine transactional updates, graph
relationships, and vector retrieval in one workflow. In practice, these needs are often
split across multiple systems (for example, an OLTP database plus separate analytics or
retrieval components). That split adds operational complexity and makes reproducible
local experimentation harder.

This talk presents an alternative pattern: an **embedded, OLTP-first, multi-model**
engine with Python bindings, enabling documents, graphs, and vectors in one in-process
runtime.

We will explicitly map data patterns to query/index choices: SQL for tabular and
record-oriented analysis, Cypher for property-graph traversal and relationship-centric
questions, and HNSW indexes for approximate nearest-neighbor vector search.

The session is aimed at Python users building data-intensive scientific or applied ML
workflows who want lower infrastructure overhead while keeping strong data integrity.
The target audience includes researchers, data scientists, and engineers who currently
move data across multiple services for ingestion, relationship modeling, and semantic
search. No database internals background is required.

We will walk through a concrete workflow using Python bindings over an embedded Java
engine. The session covers:

- Creating and evolving schema from Python
- Performing transactional writes (**OLTP** core)
- Querying record-style datasets with SQL (dialect)
- Querying relationship-heavy datasets with Cypher (property graph)
- Building and querying HNSW vector indexes for retrieval and recommendation tasks
- Structuring local workflows so they remain analytics-friendly without abandoning
  transactional guarantees

Rather than positioning this approach as a replacement for dedicated data warehouses, we
focus on where it is most useful: local workflows and larger-scale use cases where
single-node embedded performance is a good fit, reproducible experiments, and
applications where low-latency in-process access matters. We discuss tradeoffs
explicitly, including operational simplicity versus distributed scale, and when an
embedded approach is the right fit.

Attendees will leave with practical guidance on:

- Deciding when an OLTP-first embedded architecture is appropriate for scientific Python
- Designing data models that mix records, relationships, and vectors in one system
- Building reproducible, open workflows that are easy to share and run
- Avoiding common pitfalls when combining transactional and analytical-style access
  patterns

The session also highlights open-source and reproducibility considerations important to
the SciPy community. The project is **Apache 2.0** licensed and free to use, with public
code, documentation, and runnable examples.

Supplementary materials:

- Repository: https://github.com/humemai/arcadedb-embedded-python
- Documentation: https://docs.humem.ai/arcadedb/

By the end of the talk, participants will have a clear mental model and implementation
path for building end-to-end Python data workflows that start with reliable
transactional foundations and extend naturally to graph and vector-driven analysis.

---

## Notes to Organizers (Optional)

Thank you for reviewing this submission. I am currently planning for in-person
attendance, but travel funding is not yet fully confirmed. If needed, I would be glad to
present this work as a virtual poster. I am also happy to provide additional technical
details, repository pointers, or demo materials to support review.
