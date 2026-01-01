# Vector Search Tests

The `test_vector.py` file contains **1 test class** with multiple tests covering vector similarity search with HNSW indexes.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/python-embedded/bindings/python/tests/test_vector.py){ .md-button }

## Overview

Vector search tests cover:

- ✅ **HNSW Index Creation** - Vector similarity index setup
- ✅ **Vector Storage** - Storing embeddings as float arrays
- ✅ **Similarity Search** - Finding nearest neighbors
- ✅ **Index Configuration** - M, efConstruction, ef parameters
- ✅ **Multiple Dimensions** - 128, 384, 1536 dimensions
- ✅ **Cosine Similarity** - Distance metric
- ✅ **Top-K Retrieval** - Getting N nearest neighbors

## Test Coverage

### test_vector_index_creation
Tests creating HNSW vector indexes.

**What it tests:**
- Creating HNSW index on embedding property
- Setting index parameters (M, efConstruction, ef, dimension)
- Index exists after creation

**Pattern:**
```python
# Create schema
db.schema.create_vertex_type("Document")
db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")

# Create vector index
index = db.create_vector_index("Document", "embedding", dimensions=384)
```

---

### test_vector_storage_and_retrieval
Tests storing and retrieving vector embeddings.

**What it tests:**
- Storing float arrays as embeddings
- Retrieving embeddings
- Embedding value preservation

**Pattern:**
```python
# Store embedding
embedding = [0.1, 0.2, 0.3, 0.4] * 96  # 384 dimensions

vertex = db.new_vertex("Document")
vertex.set("docId", 1)
vertex.set("text", "Hello world")
vertex.set("embedding", embedding)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Document WHERE docId = 1").first()
retrieved_embedding = result.get_property("embedding")

assert len(retrieved_embedding) == 384
assert retrieved_embedding[0] == 0.1
```

---

### test_vector_similarity_search
Tests finding nearest neighbors.

**What it tests:**
- Querying with vector using `~` operator
- Getting top-K nearest neighbors
- Results ordered by similarity
- Similarity scores returned

**Pattern:**
```python
# Insert documents with embeddings
embeddings = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.9, 0.1, 0.0, 0.0],  # Similar to first
]

with db.transaction():
    for i, emb in enumerate(embeddings):
        vertex = db.new_vertex("Document")
        vertex.set("docId", i)
        vertex.set("embedding", emb)
        vertex.save()

# Query: find similar to [1.0, 0.0, 0.0, 0.0]
query_vector = [1.0, 0.0, 0.0, 0.0]

results = db.query(
    "sql",
    "SELECT *, $similarity as score FROM Document WHERE embedding ~ ? LIMIT 3",
    query_vector
)

# Most similar should be docId=0 and docId=3
top_results = list(results)
assert top_results[0].get_property("docId") == 0  # Exact match
assert top_results[1].get_property("docId") == 3  # Close match
```

---

### test_vector_search_with_filters
Tests combining vector search with filters.

**What it tests:**
- Vector search + WHERE clause
- Filtering by properties
- Maintaining similarity ordering

**Pattern:**
```python
# Query: find similar vectors where category = "tech"
results = db.query(
    "sql",
    """
    SELECT *, $similarity as score
    FROM Document
    WHERE embedding ~ ? AND category = 'tech'
    ORDER BY $similarity DESC
    LIMIT 5
    """,
    query_vector
)

for result in results:
    assert result.get_property("category") == "tech"
    score = result.get_property("score")
    print(f"DocId: {result.get_property('docId')}, Score: {score}")
```

---

### test_hnsw_parameter_tuning
Tests different HNSW configurations.

**What it tests:**
- M parameter (connections per node)
- efConstruction (build quality)
- ef (search quality)
- Performance vs accuracy tradeoff

**Pattern:**
```python
# High accuracy configuration
db.create_vector_index(
    "Document",
    "embedding",
    dimensions=384,
    max_connections=32,
    beam_width=400
)

# Fast configuration
db.create_vector_index(
    "Document",
    "embedding",
    dimensions=384,
    max_connections=8,
    beam_width=100
)
```

---

### test_vector_dimensions
Tests various embedding dimensions.

**What it tests:**
- 128-dimensional embeddings (small)
- 384-dimensional embeddings (medium)
- 768-dimensional embeddings (large)
- 1536-dimensional embeddings (OpenAI)

**Pattern:**
```python
# Test different dimensions
dimensions = [128, 384, 768, 1536]

for dim in dimensions:
    # Create type
    type_name = f"Doc{dim}d"
    schema.create_vertex_type(type_name)

    # Create HNSW index
    db.create_vector_index(type_name, "embedding", dimensions=dim)

    # Insert vector
    embedding = [0.1] * dim
    vertex = db.new_vertex(type_name)
    vertex.set("embedding", embedding)
    vertex.save()
```

---

### test_batch_vector_insertion
Tests bulk vector insertion performance.

**What it tests:**
- Inserting thousands of vectors
- Using BatchContext for speed
- Index building during insert

**Pattern:**
```python
import random

# Create 10K vectors
with db.batch_context(batch_size=1000, parallel=4) as batch:
    for i in range(10000):
        # Generate random embedding
        embedding = [random.random() for _ in range(384)]

        batch.create_vertex(
            "Document",
            docId=i,
            embedding=embedding
        )

# Search is fast even with 10K vectors
query = [random.random() for _ in range(384)]
results = db.query(
    "sql",
    "SELECT *, $similarity as score FROM Document WHERE embedding ~ ? LIMIT 10",
    query
)
```

## Test Patterns

### Create HNSW Index
```python
# Create index
db.create_vector_index("Document", "embedding", dimensions=384)

# Configure
index.setProperty(HnswVectorIndexRAM.M_PARAMETER, 16)
index.setProperty(HnswVectorIndexRAM.EF_CONSTRUCTION_PARAMETER, 200)
index.setProperty(HnswVectorIndexRAM.EF_PARAMETER, 100)
index.setProperty(HnswVectorIndexRAM.DIMENSION_PARAMETER, 384)
```

### Store Vector
```python
embedding = [0.1, 0.2, 0.3, ...]  # 384 floats

vertex = db.new_vertex("Document")
vertex.set("embedding", embedding)
vertex.save()
```

### Search Vectors
```python
query_vector = [0.1, 0.2, 0.3, ...]

results = db.query(
    "sql",
    "SELECT *, $similarity as score FROM Document WHERE embedding ~ ? LIMIT 10",
    query_vector
)

for result in results:
    doc_id = result.get_property("docId")
    score = result.get_property("score")
    print(f"Match: {doc_id}, Similarity: {score}")
```

## Common Assertions

```python
# Index created
assert schema.get_type("Document").get_indexes() is not None

# Embedding stored
result = db.query("sql", "SELECT FROM Document").first()
embedding = result.get_property("embedding")
assert len(embedding) == 384
assert isinstance(embedding, list)

# Search results
results = list(db.query("sql", "SELECT FROM Document WHERE embedding ~ ?", query))
assert len(results) > 0

# Similarity scores
result = results[0]
score = result.get_property("score")
assert 0 <= score <= 1  # Cosine similarity
```

## HNSW Parameters Guide

| Parameter | Range | Default | Impact |
|-----------|-------|---------|--------|
| **M** | 2-48 | 16 | Connections per node. Higher = better accuracy, more memory |
| **efConstruction** | 100-500 | 200 | Build quality. Higher = better index, slower build |
| **ef** | 50-200 | 100 | Search quality. Higher = better recall, slower search |
| **dimension** | Any | Required | Vector size (must match embeddings) |

### Recommended Configurations

**High Accuracy:**
- M = 32
- efConstruction = 400
- ef = 200

**Balanced:**
- M = 16 (default)
- efConstruction = 200 (default)
- ef = 100 (default)

**High Speed:**
- M = 8
- efConstruction = 100
- ef = 50

## Key Takeaways

1. **Configure HNSW** - Set M, efConstruction, ef, dimension
2. **Match dimensions** - All vectors must be same size
3. **Use BatchContext** - For bulk vector insertion
4. **Tune for workload** - Balance accuracy vs speed
5. **Filter with WHERE** - Combine vector + property filters

## See Also

- **[Vector API](../../api/vector.md)** - Full API reference
- **[NumPy Tests](test-numpy-support.md)** - NumPy integration
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** - Real-world usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** - Advanced patterns
- **[Vector Guide](../../guide/vectors.md)** - Vector search concepts
