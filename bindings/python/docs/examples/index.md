# Examples Overview

Hands-on examples demonstrating ArcadeDB Python bindings in real-world scenarios. Each example is self-contained, well-documented, and ready to run.

## Available Examples

### 🏁 Getting Started

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
Production graph creation from MovieLens dataset. Comprehensive performance analysis comparing Java API vs SQL, synchronous vs async, with/without indexes. 6 benchmark configurations, 10 validation queries, export/import roundtrip testing. Learn when to use Java API (bulk operations: 5,071 edges/sec) vs SQL (complex queries).

**[06 - Vector Search - Movie Recommendations](06_vector_search_recommendations.md)**
Production-ready vector embeddings and HNSW (JVector) indexing for semantic movie search.

**[07 - Multi-Model: Stack Overflow Q&A](07_stackoverflow_multimodel.md)**
Documents (questions/answers), graph (user relationships, tags), and vectors (duplicate detection) in one comprehensive system. Demonstrates all three models working together with rich Stack Exchange dataset. Features RID-based pagination patterns and index-based vertex lookups for high performance.

**[08 - Server Mode & HTTP API](08_server_mode_rest_api.md)**
Embedded server with Studio UI and REST API. Demonstrates hybrid access pattern (embedded Python + HTTP API), concurrent load testing with multiple clients, polyglot querying (SQL + OpenCypher), and visual database exploration using ArcadeDB Studio.

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
7. **Multi-Model Stack Overflow** (07) - Documents + Graph + Vectors
8. **Server Mode** (08) - Production deployment and Studio UI

---

*Start with [Simple Document Store](01_simple_document_store.md)!*
