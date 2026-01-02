# Vector Search - Semantic Similarity

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/03_vector_search.py){ .md-button }

## Overview

This example demonstrates semantic similarity search using vector embeddings and JVector
indexing. It covers:

- Storing 384-dimensional vector embeddings (mimicking sentence-transformers)
- Creating and populating JVector indexes
- Performing nearest-neighbor searches
- Understanding indexing performance and architecture
- Best practices for filtering and production deployment

## Implementation Status

### Current: JVector

ArcadeDB uses [JVector](https://github.com/datastax/jvector), a state-of-the-art vector search engine.

**Characteristics:**
- ✅ **High Performance**: Native Java implementation with efficient graph traversal.
- ✅ **Disk-Based**: Uses DiskANN-inspired graph structure to minimize RAM usage.
- ✅ **Multi-Threaded**: Supports concurrent indexing and search.
- ✅ **Flexible**: Supports multiple distance functions (Cosine, Euclidean, Dot Product).

## Key Concepts

### Vector Embeddings

Vector embeddings represent text, images, or other data as points in high-dimensional space.

```python
# Example with sentence-transformers
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions
embedding = model.encode("This is a sample document")
# embedding is now a 384D numpy array
```

**Common dimensions:**
- **384D**: sentence-transformers/all-MiniLM-L6-v2 (fast, good quality)
- **768D**: sentence-transformers/all-mpnet-base-v2 (higher quality)
- **1536D**: OpenAI text-embedding-3-small (best quality, paid)

### JVector Index

JVector uses a graph-based index (HNSW + DiskANN) to enable fast approximate nearest-neighbor search.

```python
index = db.create_vector_index(
    vertex_type="Article",
    vector_property="embedding",
    dimensions=384,
    distance_function="cosine",  # or "euclidean", "inner_product"
    max_connections=32,          # connections per node (default: 32)
    beam_width=256               # search quality (default: 256)
)
```

**Parameters explained:**

- **dimensions**: Must match your embedding model.
- **distance_function**:
  - `cosine`: Best for normalized vectors (text embeddings).
  - `euclidean`: Straight-line distance (image features).
  - `inner_product`: Dot product (when magnitude matters).
- **max_connections**: Connections per node (default: 32). Higher = better accuracy, more memory.
- **beam_width**: Search beam width (default: 256). Higher = better recall, slower search.

## Architecture & Performance

### Lazy Index Building

The vector index is built lazily. The actual construction of the index happens when the
first query is executed, not when the index is created or when data is added. This means
the first search query might take longer than subsequent queries as it triggers the
index build process ("warm up").

### Index Structure

When you create and populate a vector index, ArcadeDB stores the graph and metadata in specific files.

**Files created** (for 10K documents, 384D, max_connections=32):
```
Article_...v1.umtidx                        256 KB   (updatable memory table index)
Article_...v0.lsmvecidx                     256 KB   (LSM index metadata)
Article_...v0.vecgraph                       16 MB   (vector graph structure)
Article_0.1.65536.v0.bucket                  23 MB   (vertices + embeddings)
Article_0_in_edges...bucket                   0 B    (unused)
Article_0_out_edges...bucket                  0 B    (unused)
─────────────────────────────────────────────────
Total:                                      ~40 MB
```

**Key insight**: The vector graph is stored in a dedicated `.vecgraph` file (16MB), separate from the standard graph edges. The vertices and embeddings are stored in the standard bucket (23MB). The `.umtidx` and `.lsmvecidx` files store metadata and in-memory structures.

### Indexing Performance

**Batch indexing** (10,000 documents):
- **Total time**: ~15 seconds (including database creation and insertion)
- **Per document**: ~1.5ms
- **Peak Memory**: ~1.34 GB (Total process memory including JVM overhead and Python runtime)

**What happens:**
1.  JVector algorithm runs in RAM and storage (graph construction).
2.  Each document connects to `max_connections` neighbors.
3.  Graph structure is updated in the `.vecgraph` file.
4.  Transaction commits write to disk.

### Search Performance

**Query characteristics** (k=5 nearest neighbors):
- **Speed**: Logarithmic time complexity (does not scan all documents).
- **Memory**: Working set scales with `beam_width` and `max_connections`, not dataset size.
- **Caching**: Hot vertices are cached by ArcadeDB's page cache.

## Production Best Practices

### 1. Incremental Indexing

ArcadeDB's LSM (Log-Structured Merge) tree architecture handles indexing automatically.

**✅ Recommended Approach**:
```python
# Index is updated automatically as you insert
with db.transaction():
    for doc in documents:
        vertex = db.new_vertex("Article")
        vertex.set("embedding", embedding)
        vertex.save()
        # No manual index.add_vertex() needed!
```

### 2. Filtering Strategies

JVector supports **native filtering** by passing a set of allowed Record IDs (RIDs) to the search method. This allows you to combine SQL's powerful filtering with vector search.

**Native Filtering (Recommended)**:

```python
def search_with_filters(db, index, query_embedding, k=5, filters=None):
    """
    Search with metadata filters using native JVector filtering.
    """
    allowed_rids = None

    if filters:
        # 1. Find RIDs matching the filter using SQL
        conditions = []
        params = {}
        for i, (prop, value) in enumerate(filters.items()):
            param_name = f"p{i}"
            conditions.append(f"{prop} = :{param_name}")
            params[param_name] = value

        where_clause = " AND ".join(conditions)
        query = f"SELECT FROM Article WHERE {where_clause}"

        # Get RIDs of matching documents
        result_set = db.query("sql", query, params)
        allowed_rids = [record.get_rid() for record in result_set]

        if not allowed_rids:
            return [] # No documents match the filter

    # 2. Pass allowed_rids to find_nearest
    return index.find_nearest(query_embedding, k=k, allowed_rids=allowed_rids)
```

**Pros:**
- Accurate results (no approximation).
- Efficient (JVector skips disallowed nodes).
- Leverages SQL for complex metadata queries.

### 3. Memory Considerations

**RAM usage formula:**
```
RAM ≈ 4 bytes × dimensions × num_vectors × (1 + M/2)
```

**Examples:**
- 10K vectors, 384D: ~50 MB (Graph memory)
- 100K vectors, 384D: ~500 MB (Graph memory)
- 1M vectors, 384D: ~5 GB (Graph memory)

**Note:** ArcadeDB uses page caching, so hot data stays in RAM while cold data is read from disk on-demand.

## Example Output

```
======================================================================
🔍 ArcadeDB Python - Example 03: Vector Search (JVector)
======================================================================

Step 1: Creating database...
   ✅ Database created at: ./my_test_databases/vector_search_db
   💡 Using embedded mode - no server needed!
   ⏱️  Time: 0.234s

Step 2: Defining schema...
   ✅ Schema created: Article vertex type
   💡 Vector property type: ARRAY_OF_FLOATS
   ⏱️  Time: 0.012s

Step 3: Generating mock data...
   ✅ Generated 10000 mock documents
   💡 Embedding dimensions: 384
   ⏱️  Time: 1.347s

Step 4: Inserting data...
      Inserted 1000/10000 documents...
      ...
      Inserted 10000/10000 documents...
   ✅ Inserted 10000 documents
   ⏱️  Time: 12.543s

Step 5: Creating vector index...
   💡 JVector Parameters:
      • dimensions: 384 (matches embedding size)
      • distance_function: cosine (best for normalized vectors)
      • max_connections: 32 (connections per node, higher = more accurate but slower)
      • beam_width: 256 (search quality, higher = more accurate)
   ✅ Created JVector vector index
   💡 LSM index automatically indexes existing records upon creation.
   ✅ Indexing handled by ArcadeDB engine.
   ⏱️  Time: 0.163s

Step 6: Performing semantic similarity searches...
   Running 10 queries on randomly sampled categories...

   🔍 Query 1: Find documents similar to Category 42
      Top 5 MOST similar documents (smallest distance):
      1. Article 67 about category_42
         Category: category_42, Distance: 0.7634
      2. Article 12 about category_42
         Category: category_42, Distance: 0.7698
      ...

   ⏱️  All queries time: 0.521s

======================================================================
✅ Vector search example completed successfully!
======================================================================
```

## Related Documentation

- [Database API](../api/database.md) - Core database operations
- [Transactions](../api/transactions.md) - Transaction management
- [Query Guide](../guide/core/queries.md) - SQL and Cypher queries
- [ArcadeDB Vector Search](https://docs.arcadedb.com/) - Official documentation
