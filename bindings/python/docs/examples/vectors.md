# Vector Search Examples

This page points to the examples that use vector search in ArcadeDB from Python. The
[Vector Search Guide](../guide/vectors.md) holds the index options, the SQL functions,
and the code patterns, and the [Vector API](../api/vector.md) documents the helpers
such as `arcadedb.to_java_float_array(...)`.

## Which Example Covers What

**[Example 03 - Vector Search](03_vector_search.md)**

- semantic search over 10,000 mock `Article` documents grouped by category
- an `ARRAY_OF_FLOATS` property, an `LSM_VECTOR` (JVector) index created in SQL, and
  top-k queries with `vectorNeighbors(...)` and bound parameters
- INT8-encoded dense vectors and a sparse-vector index, plus a first-pass versus
  second-pass timing of the same queries

**[Example 06 - Vector Search: Movie Recommendations](06_vector_search_recommendations.md)**

- real embeddings of MovieLens titles and genres from two sentence-transformers models
- "more like this" recommendations by vector similarity, compared side by side with
  graph-based collaborative filtering on the rating data

**[Example 11 - Vector Index Build](11_vector_index_build.md)** and
**[Example 12 - Vector Search Benchmark](12_vector_search.md)**

- build-only and search-only benchmarks across ArcadeDB and other vector backends, on
  MSMARCO and Stack Overflow embeddings; Example 12 reuses Example 11's databases

**[Example 13 - Stack Overflow Hybrid Queries](13_stackoverflow_hybrid_queries.md)**

- one workflow that combines documents, graph edges, and embeddings in hybrid queries

**[Example 25 - Sparse Vectors, Weight Precision, and Compaction](25_sparse_quantization_and_compact.md)**

- `LSM_SPARSE_VECTOR` with INT8 versus FP32 posting weights, and `COMPACT INDEX` after a
  bulk load

**[Example 26 - Cross-Model Transaction Atomicity](26_cross_model_transaction_atomicity.md)**

- a vector search, a graph hop, and a document update in one transaction

## Binding the Query Vector

Pass the query vector as a bound parameter rather than pasting it into the SQL text:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_embedding = [0.1] * 384  # from your embedding model
    rows = db.query(
        "sql",
        "SELECT vectorNeighbors('Product[embedding]', ?, 5) as res",
        arcadedb.to_java_float_array(query_embedding),
    ).to_list()
```

The [Vector Search Guide](../guide/vectors.md) covers index creation, filtered search,
and the tuning parameters.

## Source Code

View the vector search example source code:

- [`examples/03_vector_search.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/03_vector_search.py)
- [`examples/06_vector_search_recommendations.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/06_vector_search_recommendations.py)
