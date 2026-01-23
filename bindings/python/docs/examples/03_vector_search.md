# Vector Search - Semantic Similarity

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/03_vector_search.py){ .md-button }

## Overview

This example demonstrates semantic similarity search using vector embeddings and HNSW
(JVector) indexing. It covers:

- Storing 384-dimensional vector embeddings
- Creating HNSW (JVector) indexes for fast nearest-neighbor search
- Performing semantic similarity searches
- Understanding vector index parameters

## Key Steps

### 1. Schema Definition

Create a vertex type with an embedding property:

```python
db.schema.create_vertex_type("Article")
db.schema.create_property("Article", "title", "STRING")
db.schema.create_property("Article", "embedding", "ARRAY_OF_FLOATS")
db.schema.create_index("Article", ["id"], unique=True)
```

Vector properties must use the `ARRAY_OF_FLOATS` type.

### 2. Generating Embeddings

The example generates 10,000 mock documents with 384-dimensional embeddings:

```python
# Mock embedding generation (in production, use real models)
def create_mock_embedding(category_seed, doc_seed):
    rng = np.random.RandomState(hash(category_seed + doc_seed) % 2**32)
    category_vector = ...
    embedding = (category_vector + noise) / np.linalg.norm(...)
    return embedding.astype(np.float32)
```

Documents in the same category have embeddings that are closer together.

### 3. Inserting Data

Insert documents with embeddings in transactions:

```python
with db.transaction():
    for doc in documents:
        vertex = db.new_vertex("Article")
        vertex.set("title", doc["title"])
        vertex.set("embedding", arcadedb.to_java_float_array(doc["embedding"]))
        vertex.save()
```

### 4. Creating Vector Index

Create a JVector index for similarity search:

```python
index = db.create_vector_index(
    vertex_type="Article",
    vector_property="embedding",
    dimensions=384,
    distance_function="cosine"
)
```

**Parameters:**
- `dimensions`: Must match embedding model size
- `distance_function`: `cosine` (for normalized vectors), `euclidean`, or `inner_product`

### 5. Semantic Search

Find the k most similar documents to a query embedding:

```python
query_embedding = create_mock_embedding(category, "query")
most_similar = index.find_nearest(query_embedding, k=5)

for vertex, distance in most_similar:
    title = vertex.get("title")
    category = vertex.get("category")
    print(f"{title}: {distance:.4f}")
```

The `find_nearest()` method returns (vertex, distance) pairs sorted by distance.

## Example Output

```
Step 5: Creating vector index...
   💡 JVector Parameters:
      • dimensions: 384 (matches embedding size)
      • distance_function: cosine (best for normalized vectors)
      • max_connections: 16 (connections per node, higher = more accurate but slower)
      • beam_width: 100 (search quality, higher = more accurate)
   ✅ Created JVector vector index

Step 6: Performing semantic similarity searches...
   Running 10 queries on randomly sampled categories...

   🔍 Query 1: Find documents similar to Category 42
      Top 5 MOST similar documents (smallest distance):
      1. Article 67 about category_42
         Category: category_42, Distance: 0.7634
      2. Article 12 about category_42
         Category: category_42, Distance: 0.7698
```

## Running the Example

```bash
cd bindings/python/examples
python 03_vector_search.py
```

Database files will be created in `./my_test_databases/vector_search_db/`
