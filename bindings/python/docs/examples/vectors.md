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

with arcadedb.create_database("vector_demo") as db:
    # Create vertex type with vector property (schema ops are auto-transactional)
    db.schema.create_vertex_type("Product")
    db.schema.create_property("Product", "name", "STRING")
    db.schema.create_property("Product", "description", "STRING")
    db.schema.create_property("Product", "embedding", "ARRAY_OF_FLOATS")

    # Create vector index (1536 dimensions for OpenAI embeddings)
    db.create_vector_index("Product", "embedding", dimensions=1536)
```

### Insert Vectors

```python
import numpy as np
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Generate or load embeddings (example with random vectors)
    def get_embedding(text: str) -> list:
        # In production, use OpenAI, Sentence Transformers, etc.
        return np.random.rand(1536).tolist()

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
            product.set("embedding", embedding)
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
        return np.random.rand(1536).tolist()

    search_text = "computer accessories"
    query_embedding = get_embedding(search_text)

    results = db.query("""
        SELECT name, description,
               vectorL2Distance(embedding, ?) as distance
        FROM Product
        ORDER BY distance ASC
        LIMIT 5
    """, (query_embedding,))

    for record in results:
        print(f"{record.get('name')}: {record.get('distance'):.4f}")
```

## Vector Functions

ArcadeDB provides several vector functions:

### Distance Metrics

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 1536  # Example embedding

    # Cosine similarity (0-2, lower = more similar)
    results = db.query("""
        SELECT vectorCosineSimilarity(embedding, ?) as score
        FROM Product
    """, (query_vector,))

    # Euclidean distance (L2)
    results = db.query("""
        SELECT vectorL2Distance(embedding, ?) as score
        FROM Product
    """, (query_vector,))

    # Dot product
    results = db.query("""
        SELECT vectorDotProduct(embedding, ?) as score
        FROM Product
    """, (query_vector,))
```

### Nearest Neighbors

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 1536  # Example embedding

    # Find k-nearest neighbors (read-only, no transaction needed)
    results = db.query("""
        SELECT name,
               vectorL2Distance(embedding, ?) as distance
        FROM Product
        ORDER BY distance ASC
        LIMIT 10
    """, (query_vector,))
```

## Advanced Patterns

### Hybrid Search (Vectors + Filters)

Combine semantic search with traditional filtering:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_embedding = [0.5] * 1536  # Example embedding

    # Read-only query, no transaction needed
    results = db.query("""
        SELECT name, price, category,
               vectorL2Distance(embedding, ?) as similarity
        FROM Product
        WHERE category = 'Electronics'
          AND price < 1000
          AND inStock = true
        ORDER BY similarity ASC
        LIMIT 10
    """, (query_embedding,))
```

### Multi-Vector Search

Search across multiple vector properties:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Insert product with multiple embeddings
    with db.transaction():
        product = db.new_vertex("Product")
        product.set("name", "Laptop")
        product.set("title_embedding", [0.5] * 1536)
        product.set("description_embedding", [0.3] * 1536)
        product.set("image_embedding", [0.7] * 1536)
        product.save()

    # Search combining multiple vectors (read-only, no transaction)
    query_title = [0.5] * 1536
    query_desc = [0.3] * 1536
    query_image = [0.7] * 1536

    results = db.query("""
        SELECT name,
               (vectorL2Distance(title_embedding, ?) * 0.5 +
                vectorL2Distance(description_embedding, ?) * 0.3 +
                vectorL2Distance(image_embedding, ?) * 0.2) as score
        FROM Product
        ORDER BY score ASC
        LIMIT 10
    """, (query_title, query_desc, query_image))
```

### Graph + Vectors

Combine graph traversal with vector similarity:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    query_vector = [0.5] * 1536  # Example embedding

    # Find similar products bought by friends (read-only, no transaction)
    results = db.query("""
        SELECT product.name,
               vectorL2Distance(product.embedding, ?) as similarity
        FROM (
            SELECT expand(purchased)
            FROM (
                SELECT expand(friendOf)
                FROM User
                WHERE id = ?
            )
        ) purchased,
        Product product
        WHERE purchased.@rid = product.@rid
          AND vectorL2Distance(product.embedding, ?) < 0.5
        ORDER BY similarity ASC
        LIMIT 10
    """, (query_vector, 123, query_vector))
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
                          dimensions=1536,
                          max_connections=32,     # Connections per node (default: 32)
                          beam_width=256)         # Search beam width (default: 256)
```

**Parameter Guidelines:**
- **max_connections**: 8-64 (higher = better accuracy, more memory/slower build)
- **beam_width**: 128-512 (higher = better search accuracy, slower queries)
  - 128: Fast search, lower accuracy
  - 256: Balanced (default)
  - 512: High accuracy, slower search

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
            product.set("embedding", embedding.tolist())
            product.save()
```

### Index Warming

Pre-load vector index into memory:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./vector_demo") as db:
    # Warm up the index (read-only, no transaction needed)
    dummy_vector = [0.0] * 1536
    results = db.query("""
        SELECT FROM Product
        WHERE vectorL2Distance(embedding, ?) < 999
        LIMIT 1
    """, (dummy_vector,))
```

## Complete Examples

See full implementations:

- **[Example 03: Product Vector Search](03_vector_search.md)** - Complete vector search implementation
- **[Example 06: Movie Recommendations](06_vector_search_recommendations.md)** - Recommendation system
- **[Example 07: StackOverflow Multi-Model](07_stackoverflow_multimodel.md)** - Vectors + Graph + Documents

## Additional Resources

- **[Vector API Documentation](../api/vector.md)** - Complete API reference
- **[Vector Search Guide](../guide/vectors.md)** - In-depth vector search strategies
- **[ArcadeDB Vector Documentation](https://docs.arcadedb.com/#Vector-Search)** - Official vector search docs
- **[HNSW Paper](https://arxiv.org/abs/1603.09320)** - Understanding the algorithm

## Source Code

View the complete vector search example source code:
- [`examples/03_vector_search.py`](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/03_vector_search.py)
- [`examples/06_vector_search_recommendations.py`](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/06_vector_search_recommendations.py)
