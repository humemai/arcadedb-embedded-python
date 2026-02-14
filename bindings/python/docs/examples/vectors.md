# Vector Search Examples

This page covers examples for implementing AI-powered semantic search using vector embeddings in ArcadeDB.

## Vector Search Examples

### Basic Vector Search

**[Example 03 - Vector Search: Product Discovery](03_vector_search.md)**

Learn the fundamentals of vector search:

- Creating vector indexes
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
    db.schema.create_vertex_type("Product")
    db.schema.create_property("Product", "name", "STRING")
    db.schema.create_property("Product", "description", "STRING")
    db.schema.create_property("Product", "embedding", "ARRAY_OF_FLOATS")

    # Create vector index (384 dims to mirror Example 03)
    db.create_vector_index(
        "Product",
        "embedding",
        dimensions=384,
        distance_function="cosine",
    )

    # By default, create_vector_index(..., build_graph_now=True) eagerly
    # prepares the vector graph. Set build_graph_now=False to defer until
    # first query.
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
            product = db.new_vertex("Product")
            product.set("name", name)
            product.set("description", description)
            # Convert to Java float[]
            product.set("embedding", arcadedb.to_java_float_array(embedding))
            product.save()
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

#### Pythonic nearest-neighbor (preferred for code):

```python
import arcadedb_embedded as arcadedb
import numpy as np

with arcadedb.open_database("./vector_demo") as db:
    index = db.schema.get_vector_index("Product", "embedding")
    query_embedding = np.random.rand(384).tolist()

    results = index.find_nearest(query_embedding, k=5)
    for vertex, distance in results:
        print(f"{vertex.get('name')}: {distance:.4f}")
```

## Vector Functions

ArcadeDB provides several vector functions:

### Distance Metrics

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 384  # Example embedding

    # Cosine similarity (0-2, lower = more similar)
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
    db.schema.create_vertex_type("Product")
    db.schema.create_property("Product", "embedding", "ARRAY_OF_FLOATS")

    # Create index with JVector parameters (schema operations are auto-transactional)
    db.create_vector_index("Product", "embedding",
                          dimensions=384,         # Match Example 03 defaults
                          max_connections=16,     # Connections per node (default: 16)
                          beam_width=100)         # Search beam width (default: 100)
```

**Index Configuration Parameters:**

- **max_connections**: 8-32 (higher = better accuracy, more memory/slower build)
- **beam_width**: 64-200 (higher = better search accuracy, slower queries)
    - 64: Fast search, lower accuracy
    - 100: Balanced (default)
    - 200: High accuracy, slower search
- **build_graph_now**: `True` by default (eager graph preparation). Set `False` to defer graph preparation to first query.
- **overquery_factor**: Search-time tuning (default: 4)
    - Multiplies k internally; 16 means searches ~160 candidates for k=10
    - Smaller (4-8) = faster, lower recall
    - Larger (32-64) = slower, better recall

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
            product = db.new_vertex("Product")
            product.set("description", text)
            product.set("embedding", arcadedb.to_java_float_array(embedding))
            product.save()
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
