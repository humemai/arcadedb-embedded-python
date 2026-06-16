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
db.command("sql", "CREATE VERTEX TYPE Article")
db.command("sql", "CREATE PROPERTY Article.title STRING")
db.command("sql", "CREATE PROPERTY Article.content STRING")
db.command("sql", "CREATE PROPERTY Article.category STRING")
db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
db.command("sql", "CREATE PROPERTY Article.id STRING")
db.command("sql", "CREATE INDEX ON Article (id) UNIQUE_HASH")
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
        db.command(
            "sql",
            """
            INSERT INTO Article SET
                id = :id,
                title = :title,
                content = :content,
                category = :category,
                embedding = :embedding
            """,
            {
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
                "category": doc["category"],
                "embedding": arcadedb.to_java_float_array(doc["embedding"]),
            },
        )
```

Inserts are committed in batches (every 1,000 documents).

### 4. Creating Vector Index

Create the JVector index for similarity search in SQL. This is the cleaner and
recommended path:

```python
db.command(
    "sql",
    """
    CREATE INDEX ON Article (embedding)
    LSM_VECTOR
    METADATA {
        "dimensions": 384,
        "similarity": "COSINE"
    }
    """
)
```

**Metadata:**
- `dimensions`: Must match embedding model size
- `similarity`: `COSINE` (best for normalized vectors)

The index is `LSM_VECTOR` (JVector / HNSW-style graph). The LSM index automatically
indexes the existing records when it is created.

### 5. Semantic Search

Find the k most similar documents to a query embedding with SQL nearest-neighbor
queries. The index name, the query embedding, and `k` are passed as positional query
parameters to `vectorNeighbors(?, ?, ?)`:

```python
index_name = "Article[embedding]"
query_embedding = create_mock_embedding(category, f"query{query_num}")
most_similar = db.query(
    "sql",
    (
        "SELECT title, category, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors(?, ?, ?))) ORDER BY distance"
    ),
    index_name,
    query_embedding,
    5,
).to_list()

for hit in most_similar:
    print(f"{hit.get('title')}: {hit.get('distance'):.4f}")
```

The example also shows a filtered query in the same category (it retrieves 50
neighbors, then filters by category and limits to 5):

```python
filtered_hits = db.query(
    "sql",
    (
        "SELECT title, category, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors(?, ?, ?))) "
        "WHERE category = ? ORDER BY distance LIMIT 5"
    ),
    index_name,
    query_embedding,
    50,
    category,
).to_list()
```

The example then demonstrates two more workloads: an INT8-encoded dense-vector index
(an `LSM_VECTOR` index with `"encoding": "INT8"` on a `BINARY` property) and a
sparse-vector index (`LSM_SPARSE_VECTOR` on token/weight arrays, queried with
`` `vector.sparseNeighbors` ``). Both are wrapped in `try`/`except` and skipped if the
runtime does not support them.

## Example Output

```
Step 5: Creating vector index...
   💡 JVector Parameters:
      • dimensions: 384 (matches embedding size)
      • distance_function: cosine (best for normalized vectors)
      • max_connections: 32 (connections per node, higher = more accurate but slower)
      • beam_width: 256 (search quality, higher = more accurate)
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
