# Examples Overview

Hands-on examples demonstrating ArcadeDB Python bindings in real-world scenarios. Each example is self-contained, well-documented, and ready to run.

## Available Examples

### 🏁 Getting Started

**[01 - Simple Document Store](01_simple_document_store.md)**
Foundation example covering document types, CRUD operations, comprehensive data types (DATE, DATETIME, DECIMAL, FLOAT, INTEGER, STRING, BOOLEAN, LIST OF STRING), and NULL value handling (INSERT NULL, UPDATE to NULL, IS NULL queries).

**[02 - Social Network Graph](02_social_network_graph.md)** ✅
Complete graph modeling with vertices, edges, NULL handling, and dual query languages (SQL MATCH vs Cypher). Demonstrates 8 people with optional fields, 24 bidirectional edges, graph traversal, and comprehensive queries.

**[03 - Vector Search](03_vector_search.md)** ⚠️ **EXPERIMENTAL**
Semantic similarity search with HNSW indexing. Demonstrates API but not production-ready yet.

**[04 - CSV Import - Documents](04_csv_import_documents.md)** ✅
Production CSV import with automatic type inference by Java, NULL handling, and index optimization. Imports MovieLens dataset (36M+ records) with comprehensive performance analysis and result validation with actual data samples.

**[05 - CSV Import - Graph](05_csv_import_graph.md)** 🚧 **COMING SOON**
Import MovieLens dataset as graph structures. Users and Movies become vertices, ratings and tags become edges. Demonstrates foreign key resolution and graph traversal patterns on familiar data.

**[06 - Vector Search - Movie Recommendations](06_vector_search_movies.md)** 🚧 **COMING SOON**
Semantic similarity search with MovieLens data. Generate embeddings from movie titles/genres, find similar movies using HNSW index, combine with rating data for recommendations.

### 🔍 Coming Soon

**07 - Multi-Model: Stack Overflow Q&A** 🚧
Documents (questions/answers), graph (user relationships, tags), and vectors (duplicate detection) in one comprehensive system. Demonstrates all three models working together with rich Stack Exchange dataset.

**08 - Server Mode & HTTP API** 🚧
Embedded server with Studio UI and REST API. Production deployment patterns with remote access.

## Quick Start

**⚠️ Important: Always run examples from the `examples/` directory.**

```bash
cd bindings/python/examples/
python 01_simple_document_store.py
```

## Learning Path

1. **Document Store** (01) - Learn fundamentals
2. **Graph Operations** (02) - Understand relationships
3. **Vector Search** (03) ⚠️ - AI/ML integration (experimental)
4. **CSV Import - Documents** (04) - ETL to documents with MovieLens
5. **CSV Import - Graph** (05) 🚧 - Same data as graph (coming soon)
6. **Vector Search - Movies** (06) 🚧 - Semantic search on MovieLens (coming soon)
7. **Multi-Model Stack Overflow** (07) 🚧 - Documents + Graph + Vectors (coming soon)
8. **Server Mode** (08) 🚧 - Production deployment (coming soon)

## Support

- [GitHub Issues](https://github.com/humemai/arcadedb-embedded-python/issues)
- [Documentation](https://docs.arcadedb.com/)
- [Community Forum](https://github.com/humemai/arcadedb-embedded-python/discussions)

---

*Start with [Simple Document Store](01_simple_document_store.md)!*
