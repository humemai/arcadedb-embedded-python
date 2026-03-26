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
db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
db.command("sql", "CREATE PROPERTY Article.id INTEGER")
db.command("sql", "CREATE INDEX ON Article (id) UNIQUE")
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
         "INSERT INTO Article SET title = ?, embedding = ?",
         doc["title"],
         arcadedb.to_java_float_array(doc["embedding"]),
      )
```

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

**Parameters:**
- `dimensions`: Must match embedding model size
- `distance_function`: `cosine` (for normalized vectors), `euclidean`, or `inner_product`
- `buildGraphNow`: Defaults to `true` in SQL metadata. Set it to `false` only if you
   intentionally want to defer preparation to the first query.

### 5. Semantic Search

Find the k most similar documents to a query embedding with SQL nearest-neighbor
queries. This keeps search in the query layer, where filtering and score shaping are
easy to express.

```python
query_embedding = create_mock_embedding(category, "query")
qvec_literal = "[" + ", ".join(str(float(x)) for x in query_embedding.tolist()) + "]"
rows = db.query(
   "sql",
   (
      "SELECT title, category, distance, (1 - distance) AS score "
      "FROM (SELECT expand(vectorNeighbors('Article[embedding]', "
      f"{qvec_literal}, 5))) ORDER BY distance"
   ),
).to_list()

for hit in rows:
   print(f"{hit.get('title')}: {hit.get('distance'):.4f}")
```

The example also shows a filtered query in the same category:

```python
filtered_rows = db.query(
   "sql",
   (
      "SELECT title, category, distance, (1 - distance) AS score "
      "FROM (SELECT expand(vectorNeighbors('Article[embedding]', "
      f"{qvec_literal}, 50))) WHERE category = ? ORDER BY distance LIMIT 5"
   ),
   category,
).to_list()
```

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
