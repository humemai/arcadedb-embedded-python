# Example 06: Vector Search Movie Recommendations

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/06_vector_search_recommendations.py){ .md-button }

**Production-ready vector embeddings and HNSW (JVector) indexing for semantic movie search**

## Overview

This example demonstrates creating vector embeddings for movies and using HNSW (JVector)
indexing for fast semantic similarity search. You'll learn:

- **Real embeddings** - Using sentence-transformers for 384-dimensional vectors
- **HNSW (JVector) vector indexing** - Fast approximate nearest neighbor search (cosine similarity)
- **Graph vs Vector** - Compare collaborative filtering with semantic similarity
- **Multi-model comparison** - Two embedding models with different semantic characteristics
- **Performance optimization** - Graph query sampling for 150-300× speedup

## What You'll Learn

- Generate embeddings using sentence-transformers (all-MiniLM-L6-v2, paraphrase-MiniLM-L6-v2)
- Create and populate HNSW (JVector) vector indexes with custom edge types
- Graph-based collaborative filtering (full vs sampled modes)
- Vector-based semantic similarity search
- Performance comparison: 4 recommendation methods
- Handling vector metadata persistence and property versioning
- Known limitations: JSONL export/import for vectors, NOTUNIQUE index bugs

## Prerequisites

**1. Install dependencies:**

```bash
uv pip install arcadedb-embedded sentence-transformers numpy
```

**2. Source database:**

This example requires a graph database from Example 05:

```bash
# Option A: Use existing database
python 05_csv_import_graph.py --dataset movielens-small --method java

# Option B: Import from JSONL export
python 05_csv_import_graph.py --dataset movielens-small --import-jsonl ./exports/movielens_graph_small_db.jsonl.tgz
```

**Two dataset sizes available:**

- **movielens-small**: 9,742 movies, ~100K ratings - Quick testing (9 min total)
- **movielens-large**: 86,537 movies, ~33M ratings - Production testing (51 min total)

## Usage

```bash
# Recommended: Import from JSONL export (fastest setup)
python 06_vector_search_recommendations.py \
    --source-db my_test_databases/movielens_graph_small_db \
    --db-path my_test_databases/movielens_graph_small_db_vectors

# Use existing graph database
python 06_vector_search_recommendations.py \
    --source-db my_test_databases/movielens_graph_small_db \
    --db-path my_test_databases/movielens_graph_small_db_vectors

# Import from JSONL
python 06_vector_search_recommendations.py \
    --import-jsonl ./exports/movielens_graph_small_db.jsonl.tgz \
    --source-db my_test_databases/movielens_graph_small_db \
    --db-path my_test_databases/movielens_graph_small_db_vectors

# Force re-generation of embeddings
python 06_vector_search_recommendations.py \
    --source-db my_test_databases/movielens_graph_small_db \
    --db-path my_test_databases/movielens_graph_small_db_vectors \
    --force-embed

# See all options
python 06_vector_search_recommendations.py --help
```

**Key options:**

- `--source-db SOURCE_DB` - Source graph database path (required)
- `--db-path DB_PATH` - Working database path for vectors (required)
- `--import-jsonl IMPORT_JSONL` - Import from JSONL file (optional)
- `--heap-size SIZE` - JVM max heap size (e.g. `8g`, `4096m`)
- `--force-embed` - Force re-generation of embeddings (optional)

**Recommendations:**

- **Setup:** Use fresh copy or import from JSONL to avoid conflicts
- **Memory:** 8GB JVM heap for large dataset (`--heap-size 8g`)
- **Embeddings:** Cached automatically, use `--force-embed` to regenerate
- **Models:** Both models included for comparison

## Vector Embedding Models

### Model 1: all-MiniLM-L6-v2

- **Dimensions:** 384
- **Best for:** General-purpose semantic similarity
- **Performance (small):** 72 movies/sec encoding, 135.6s total
- **Performance (large):** 167 movies/sec encoding, 517.1s total
- **Index creation (small):** 59.6s for 9,742 movies
- **Index creation (large):** 1,050.8s for 86,537 movies

### Model 2: paraphrase-MiniLM-L6-v2

- **Dimensions:** 384
- **Best for:** Paraphrase detection and semantic similarity
- **Performance (small):** ~800 movies/sec encoding, ~90s total
- **Performance (large):** 943 movies/sec encoding, 91.7s total
- **Index creation (small):** 58.2s for 9,742 movies
- **Index creation (large):** 1,123.9s for 86,537 movies

**Encoding speedup:** Model 2 is ~5-10× faster due to model optimizations

## Recommendation Methods

### 1. Graph-Based Full (Collaborative Filtering - Comprehensive)

**How it works:**

- Finds users who rated the query movie highly (≥4.0 stars)
- Analyzes ALL movies those users also rated highly
- Aggregates ratings and recommends top movies

**Performance:**

- **Small dataset:** 0.119-0.307s per query
- **Large dataset:** 37.6-62.2s per query
- **Best for:** Offline batch recommendations

**Pros:**

- Most thorough analysis
- High-quality recommendations based on user behavior

**Cons:**

- Slow on large datasets (processes 100K+ intermediate results)
- Cold start problem (new movies without ratings)

### 2. Graph-Based Fast (Collaborative Filtering - Sampled)

**How it works:**

- Same as full mode, but limits intermediate results to 25K
- Samples ~50 users' worth of ratings
- Uses nested SELECT with LIMIT before GROUP BY aggregation

**Performance:**

- **Small dataset:** 0.149-0.243s per query
- **Large dataset:** 0.206-0.242s per query
- **Speedup:** 150-300× faster than full mode

**Pros:**

- Real-time recommendation speed
- Still produces high-quality results
- No cold start problem for existing movies

**Cons:**

- Slightly less comprehensive than full mode
- Still requires some ratings history

### 3. Vector (all-MiniLM-L6-v2)

**How it works:**

- Encodes movie titles and genres into 384-dimensional vectors
- Uses HNSW (JVector) index for fast approximate nearest neighbor search
- Finds movies with similar semantic meaning

**Performance:**

- **Small dataset:** 0.012-0.145s per query
- **Large dataset:** 0.024-0.041s per query

**Pros:**

- Very fast (~0.02-0.04s)
- No cold start problem (works for new movies)
- Finds semantically similar content

**Cons:**

- Different recommendations than collaborative filtering
- Requires embedding generation and indexing

### 4. Vector (paraphrase-MiniLM-L6-v2)

**How it works:**

- Same as Vector method 1, but with different embedding model
- Optimized for paraphrase detection

**Performance:**

- **Small dataset:** 0.009-0.023s per query
- **Large dataset:** 0.016-0.038s per query
- **Fastest method:** Often 2-3× faster than other models

**Pros:**

- Extremely fast (0.01-0.03s)
- Different semantic characteristics than Model 1
- Best for real-time search

**Cons:**

- May find different movies than collaborative filtering
- Embedding quality depends on model training

## Example Results

### Query: "Toy Story (1995)"

#### Small Dataset

```
Graph-Based Full:
1. Five Easy Pieces (1970) (4.9★, 5 users)
2. Thin Red Line, The (1998) (4.8★, 5 users)
⏱️  0.307s

Graph-Based Fast:
1. Five Easy Pieces (1970) (4.9★, 5 users)
2. Thin Red Line, The (1998) (4.8★, 5 users)
⏱️  0.169s (1.8× faster)

Vector (all-MiniLM-L6-v2):
1. Ice Guardians (2016) (distance: 0.1365)
2. Ordinary Decent Criminal (2000) (distance: 0.2077)
⏱️  0.145s

Vector (paraphrase-MiniLM-L6-v2):
1. Ice Guardians (2016) (distance: 0.0306)
2. Death and the Maiden (1994) (distance: 0.0887)
⏱️  0.009s (16× faster than full graph)
```

#### Large Dataset

```
Graph-Based Full:
1. O Pátio das Cantigas (1942) (5.0★, 11 users)
2. Farmer & Chase (1997) (5.0★, 7 users)
⏱️  43.694s

Graph-Based Fast:
1. Local Hero (1983) (5.0★, 5 users)
2. Little Shop of Horrors (1986) (5.0★, 5 users)
⏱️  0.242s (180× faster!)

Vector (all-MiniLM-L6-v2):
1. Arranged (2007) (distance: 0.1365)
2. Banyo (2005) (distance: 0.1388)
⏱️  0.041s

Vector (paraphrase-MiniLM-L6-v2):
1. Arranged (2007) (distance: 0.0306)
2. Banyo (2005) (distance: 0.0719)
⏱️  0.029s (1,500× faster than full graph!)
```

## Performance Summary

### Small Dataset (9,742 movies)

| Phase | Time | Notes |
|-------|------|-------|
| Setup (copy database) | ~1s | Fresh working copy |
| Model 1 encoding | 135.6s | 72 movies/sec |
| Model 1 indexing | 59.6s | JVector index creation |
| Model 2 encoding | ~90s | 5× faster encoding |
| Model 2 indexing | 58.2s | JVector index creation |
| **Total** | **~548s (9.1 min)** | End-to-end |

**Query Performance:**

- Graph Full: 0.119-0.307s
- Graph Fast: 0.149-0.243s (1.3-1.8× speedup)
- Vector Model 1: 0.012-0.145s
- Vector Model 2: 0.009-0.023s (fastest)

### Large Dataset (86,537 movies)

| Phase | Time | Notes |
|-------|------|-------|
| Setup (copy database) | ~5s | 119 MB database |
| Model 1 encoding | 517.1s | 167 movies/sec |
| Model 1 indexing | 1,050.8s | JVector index creation |
| Model 2 encoding | 91.7s | 943 movies/sec |
| Model 2 indexing | 1,123.9s | JVector index creation |
| **Total** | **~3,075s (51.3 min)** | End-to-end |

**Query Performance:**

- Graph Full: 37.6-62.2s (comprehensive but slow)
- Graph Fast: 0.206-0.242s (150-300× speedup!)
- Vector Model 1: 0.024-0.041s
- Vector Model 2: 0.016-0.038s (fastest, 1,500-2,000× vs full graph)

**Memory usage:**

- Small: ~7.2 GB RSS
- Large: ~11.2 GB RSS

## JVector Index Configuration

```python
index = db.create_vector_index(
    vertex_type="Movie",
    vector_property="embedding_v1",  # or "embedding_v2"
    dimensions=384,
    distance_function="cosine",
)
```

**Key parameters:**

- **vertex_type:** The vertex type to index (e.g., "Movie")
- **vector_property:** Property containing the embedding vectors
- **dimensions:** Vector dimensionality (384 for sentence-transformers models)
- **distance_function:** "cosine" for normalized similarity (0-1 range)
- **build_graph_now:** `True` by default (eager graph preparation). Set `False` to defer graph preparation to first query.

## Output

The script outputs:

1. **Dependency check** - Verifies sentence-transformers and numpy
2. **Database setup** - Copy or import source database
3. **Embedding generation** - Progress bars for both models
4. **Index creation** - JVector index building with timing
5. **Recommendation comparison** - 4 methods × 5 query movies
6. **Summary** - Method characteristics and use cases
7. **Overall timing** - Total execution time

**Total execution time:**

- Small dataset: ~548s (9.1 min)
- Large dataset: ~3,075s (51.3 min)

## See Also

- [Example 04: CSV Import - Documents](04_csv_import_documents.md) - Source data import
- [Example 05: CSV Import - Graph](05_csv_import_graph.md) - Graph database creation
- [sentence-transformers documentation](https://www.sbert.net/) - Embedding models
- [JVector GitHub](https://github.com/datastax/jvector) - Vector index implementation
