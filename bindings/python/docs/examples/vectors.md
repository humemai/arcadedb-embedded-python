# Vector Search Examples

This page covers examples for implementing AI-powered semantic search using vector embeddings in ArcadeDB.

## Vector Search Examples

### Basic Vector Search

**[Example 03 - Vector Search: Product Discovery](03_vector_search.md)**

Learn the fundamentals of vector search:

- Creating vector indexes with SQL
- Generating embeddings
- Performing similarity searches
- Understanding JVector parameters

### Movie Recommendations

**[Example 06 - Vector Search: Movie Recommendations](06_vector_search_recommendations.md)**

Build a recommendation system:

- Movie embeddings from titles/genres
- Semantic similarity search
- Personalized recommendations
- Real-world MovieLens data

## Quick Start: Vector Search

### Create Vector Index

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    # Create vertex type with vector property (schema ops are auto-transactional)
    db.command("sql", "CREATE VERTEX TYPE Product")
    db.command("sql", "CREATE PROPERTY Product.name STRING")
    db.command("sql", "CREATE PROPERTY Product.description STRING")
    db.command("sql", "CREATE PROPERTY Product.embedding ARRAY_OF_FLOATS")

    # Preferred: create the vector index in SQL
    db.command(
        "sql",
        """
        CREATE INDEX ON Product (embedding)
        LSM_VECTOR
        METADATA {
            "dimensions": 384,
            "similarity": "COSINE"
        }
        """,
    )

    # SQL builds the graph immediately by default.
    # Add "buildGraphNow": false only if you intentionally want lazy preparation.
```

### Insert Vectors

```python
import numpy as np
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Generate or load embeddings (example with random vectors)
    def get_embedding(text: str) -> list:
        # In production, use OpenAI, Sentence Transformers, etc.
        return np.random.rand(384).tolist()

    # Insert products with embeddings
    products = [
        ("Laptop", "High-performance computing device"),
        ("Mouse", "Wireless ergonomic mouse"),
        ("Keyboard", "Mechanical keyboard with RGB")
    ]

    with db.transaction():
        for name, description in products:
            embedding = get_embedding(f"{name}: {description}")
            db.command(
                "sql",
                "INSERT INTO Product SET name = ?, description = ?, embedding = ?",
                name,
                description,
                arcadedb.to_java_float_array(embedding),
            )
```

### Search Similar Items

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Query for similar products (reads don't require a transaction)
    def get_embedding(text: str) -> list:
        # In production, use real embedding service
        import numpy as np
        return np.random.rand(384).tolist()

    search_text = "computer accessories"
    query_embedding = get_embedding(search_text)

    results = db.query(
        "sql",
        """
        SELECT name, description,
               vectorL2Distance(embedding, ?) as distance
        FROM Product
        ORDER BY distance ASC
        LIMIT 5
        """,
        query_embedding,
    )

    for record in results:
        print(f"{record.get('name')}: {record.get('distance'):.4f}")
```

#### SQL nearest-neighbor (preferred for query-first code):

```python
import arcadedb_embedded as arcadedb
import numpy as np

with arcadedb.open_database("./vector_demo") as db:
    query_embedding = np.random.rand(384).tolist()
    qvec_literal = "[" + ", ".join(str(float(x)) for x in query_embedding) + "]"
    rows = db.query(
        "sql",
        f"SELECT vectorNeighbors('Product[embedding]', {qvec_literal}, 5) as res",
    ).to_list()
    for hit in rows[0].get("res", []):
        record = hit.get("record")
        distance = hit.get("distance")
        if record is not None:
            print(f"{record.get('name')}: {distance:.4f}")
```

#### SQL filtered search with score shaping:

```python
rows = db.query(
    "sql",
    (
        "SELECT name, description, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors('Product[embedding]', "
        f"{qvec_literal}, 20))) WHERE name <> ? ORDER BY distance LIMIT 5"
    ),
    "Laptop",
).to_list()
```

## Vector Functions

ArcadeDB provides several vector functions:

### Distance Metrics

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 384  # Example embedding

    # Raw cosine similarity (-1 to 1, higher = more similar)
    results = db.query(
        "sql",
        """
        SELECT vectorCosineSimilarity(embedding, ?) as score
        FROM Product
        """,
        query_vector,
    )

    # Euclidean distance (L2)
    results = db.query(
        "sql",
        """
        SELECT vectorL2Distance(embedding, ?) as score
        FROM Product
        """,
        query_vector,
    )

    # Dot product
    results = db.query(
        "sql",
        """
        SELECT vectorDotProduct(embedding, ?) as score
        FROM Product
        """,
        query_vector,
    )
```

### Nearest Neighbors

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 384  # Example embedding

    # Find k-nearest neighbors (read-only, no transaction needed)
    results = db.query(
        "sql",
        """
        SELECT name,
               vectorL2Distance(embedding, ?) as distance
        FROM Product
        ORDER BY distance ASC
        LIMIT 10
        """,
        query_vector,
    )
```

## JVector Index Configuration

Tune vector index performance with JVector parameters:

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    # Create vertex type
    db.command("sql", "CREATE VERTEX TYPE Product")
    db.command("sql", "CREATE PROPERTY Product.embedding ARRAY_OF_FLOATS")

    # Preferred: configure the index directly in SQL metadata
    db.command(
        "sql",
        """
        CREATE INDEX ON Product (embedding)
        LSM_VECTOR
        METADATA {
            "dimensions": 384,
            "similarity": "COSINE",
            "maxConnections": 16,
            "beamWidth": 100
        }
        """
    )
```

**Index Configuration Parameters:**

- **max_connections**: 8-32 (higher = better accuracy, more memory/slower build)
- **beam_width**: 64-200 (higher = better search accuracy, slower queries)
    - 64: Fast search, lower accuracy
    - 100: Balanced (default)
    - 200: High accuracy, slower search
- **buildGraphNow**: `true` by default in SQL metadata. Set it to `false` only when you
  intentionally want lazy graph preparation.
- **ef_search**: Exact-search beam width override (optional)
    - Leave unset to use ArcadeDB's default/adaptive behavior
    - Smaller values are faster with lower recall
    - Larger values are slower with better recall

## Embedding Providers

### OpenAI Embeddings

```python
from openai import OpenAI

client = OpenAI(api_key="your-key")

def get_embedding(text: str) -> list:
    response = client.embeddings.create(
        model="text-embedding-3-small",  # 1536 dimensions
        input=text
    )
    return response.data[0].embedding
```

### Sentence Transformers

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions

def get_embedding(text: str) -> list:
    return model.encode(text).tolist()
```

### Hugging Face

```python
from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
model = AutoModel.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')

def get_embedding(text: str) -> list:
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1)
    return embeddings[0].tolist()
```

## Performance Optimization

### Batch Embeddings

Generate embeddings in batches for better performance:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Batch embedding generation
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')

    texts = ["product 1", "product 2", "product 3"]
    embeddings = model.encode(texts, batch_size=32)

    # Batch insert with transaction
    with db.transaction():
        for text, embedding in zip(texts, embeddings):
            db.command(
                "sql",
                "INSERT INTO Product SET description = ?, embedding = ?",
                text,
                arcadedb.to_java_float_array(embedding),
            )
```

## Complete Examples

See full implementations:

- **[Example 03: Product Vector Search](03_vector_search.md)** - Complete vector search implementation
- **[Example 06: Movie Recommendations](06_vector_search_recommendations.md)** - Recommendation system

## Additional Resources

- **[Vector API Documentation](../api/vector.md)** - Complete API reference
- **[Vector Search Guide](../guide/vectors.md)** - In-depth vector search strategies
- **[HNSW Paper](https://arxiv.org/abs/1603.09320)** - Understanding the algorithm

## Source Code

View the complete vector search example source code:

- [`examples/03_vector_search.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/03_vector_search.py)
- [`examples/06_vector_search_recommendations.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/06_vector_search_recommendations.py)
