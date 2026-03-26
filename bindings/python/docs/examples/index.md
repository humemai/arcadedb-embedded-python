# Examples Overview

Hands-on examples demonstrating ArcadeDB Python bindings in real-world scenarios. Each example is self-contained, well-documented, and ready to run.

!!! note "DSL-first examples"
    Current examples and docs use SQL/OpenCypher as the default approach for schema, CRUD, and graph operations.

## Available Examples

### 🏁 Getting Started

**[Dataset Downloader](download_data.md)**
Download and prepare datasets used by the examples (MovieLens, Stack Exchange, MSMARCO).

**[01 - Simple Document Store](01_simple_document_store.md)**
Foundation example covering document types, CRUD operations, comprehensive data types (DATE, DATETIME, DECIMAL, FLOAT, INTEGER, STRING, BOOLEAN, LIST OF STRING), and NULL value handling (INSERT NULL, UPDATE to NULL, IS NULL queries).

**[02 - Social Network Graph](02_social_network_graph.md)**
Complete graph modeling with vertices, edges, NULL handling, and dual query languages (SQL MATCH vs Cypher). Demonstrates 8 people with optional fields, 24 bidirectional edges, graph traversal, and comprehensive queries.

**[03 - Vector Search](03_vector_search.md)**
Semantic similarity search with HNSW (JVector) indexing. Demonstrates vector storage, index
creation, and nearest neighbor search.

**[04 - CSV Import - Documents](04_csv_import_documents.md)**
Production CSV import with automatic type inference by Java, NULL handling, and index optimization. Imports MovieLens dataset (36M+ records) with comprehensive performance analysis and result validation with actual data samples.

**[05 - CSV Import - Graph](05_csv_import_graph.md)**
Production graph creation from MovieLens dataset. Comprehensive performance analysis of SQL pipelines, synchronous vs async, and index effects. Includes benchmark configurations, validation queries, and export/import roundtrip testing.

**[06 - Vector Search - Movie Recommendations](06_vector_search_recommendations.md)**
Production-ready vector embeddings and HNSW (JVector) indexing for semantic movie search.

**[07 - Stack Overflow Tables (OLTP)](07_stackoverflow_tables_oltp.md)**
Table-oriented OLTP benchmark with mixed CRUD operations and deterministic single-thread verification.

**[08 - Stack Overflow Tables (OLAP)](08_stackoverflow_tables_olap.md)**
Table-oriented OLAP benchmark with fixed analytical queries, load/index timing, and repeated query runs.

**[09 - Stack Overflow Graph (OLTP)](09_stackoverflow_graph_oltp.md)**
Graph OLTP benchmark with directed-edge semantics, result verification notes, and cross-backend workload comparison.

**[10 - Stack Overflow Graph (OLAP)](10_stackoverflow_graph_olap.md)**
Graph OLAP benchmark using a fixed OpenCypher query suite across multiple backends.

**[11 - Vector Index Build](11_vector_index_build.md)**
Build-only vector benchmark comparing ArcadeDB, pgvector, Qdrant, Milvus, FAISS, and LanceDB.

**[12 - Vector Search](12_vector_search.md)**
Search-only vector benchmark that reuses Example 11 output and sweeps backend-specific search parameters.

**[13 - Stack Overflow Hybrid Queries](13_stackoverflow_hybrid_queries.md)**
Standalone SQL + graph + vector workflow over Stack Overflow data.

**[14 - Lifecycle Timing](14_lifecycle_timing.md)**
Embedded lifecycle benchmark covering JVM startup, load, query, close, and reopen timing.

**[15 - Import Database vs Transactional Table Ingest](15_import_database_vs_transactional_table_ingest.md)**
Four-way table-ingest comparison. Repository guidance from these experiments is to prefer single-worker async SQL for bulk table/document ingest.

**[16 - Import Database vs Transactional Graph Ingest](16_import_database_vs_transactional_graph_ingest.md)**
Four-way graph-ingest comparison. Repository guidance from these experiments is to prefer `GraphBatch` for bulk graph ingest.

**[17 - Time Series End-to-End](17_timeseries_end_to_end.md)**
SQL-first time-series workflow covering type creation, tagged inserts, range queries, and hourly bucket aggregation.

## Quick Start

**⚠️ Important: Always run examples from the `examples/` directory.**

```bash
cd bindings/python/examples/
python 01_simple_document_store.py
```

## Learning Path

1. **Document Store** (01) - Learn fundamentals
2. **Graph Operations** (02) - Understand relationships
3. **Vector Search** (03) - AI/ML integration
4. **CSV Import - Documents** (04) - ETL to documents with MovieLens
5. **CSV Import - Graph** (05) - Same data as graph with performance benchmarks
6. **Vector Search - Movies** (06) - Semantic search and recommendations
7. **Stack Overflow Tables (OLTP/OLAP)** (07/08) - Table benchmarks and fairness conventions
8. **Stack Overflow Graph (OLTP/OLAP)** (09/10) - Directed graph benchmarks and query suites
9. **Vector Benchmarks** (11/12) - Index build and search benchmarking across vector backends
10. **Hybrid Queries** (13) - Combined SQL, graph, and vector workflow
11. **Lifecycle And Ingest Benchmarks** (14/15/16) - Embedded lifecycle timing and ingest comparisons
12. **Time Series SQL Workflow** (17) - Tagged samples, range queries, and bucket aggregation from Python

---

*Start with [Simple Document Store](01_simple_document_store.md)!*
