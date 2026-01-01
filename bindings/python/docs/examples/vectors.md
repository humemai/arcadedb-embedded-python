# Vector Search Examples

This page covers examples for implementing AI-powered semantic search using vector embeddings in ArcadeDB.

## Vector Search Examples

### Basic Vector Search

**[Example 03 - Vector Search: Product Discovery](03_vector_search.md)**

Learn the fundamentals of vector search:
- Creating vector indexes
- Generating embeddings
- Performing similarity searches
- Understanding HNSW parameters

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

db = arcadedb.create_database("vector_demo", create_if_not_exists=True)

# Create vertex type with vector property
with db.transaction() as tx:
    db.command("sql", """
        CREATE VERTEX TYPE Product
        IF NOT EXISTS
    """)

    # Create vector index (1536 dimensions for OpenAI embeddings)
    db.command("sql", """
        CREATE INDEX IF NOT EXISTS
        ON Product (embedding)
        VECTOR 1536
    """)
```

### Insert Vectors

```python
import numpy as np

# Generate or load embeddings (example with random vectors)
def get_embedding(text: str) -> list:
    # In production, use OpenAI, Sentence Transformers, etc.
    return np.random.rand(1536).tolist()

# Insert products with embeddings
with db.transaction() as tx:
    products = [
        ("Laptop", "High-performance computing device"),
        ("Mouse", "Wireless ergonomic mouse"),
        ("Keyboard", "Mechanical keyboard with RGB")
    ]

    for name, description in products:
        embedding = get_embedding(f"{name}: {description}")

        db.command("sql", """
            CREATE VERTEX Product
            SET name = ?,
                description = ?,
                embedding = ?
        """, name, description, embedding)
```

### Search Similar Items

```python
# Query for similar products
search_text = "computer accessories"
query_embedding = get_embedding(search_text)

with db.transaction() as tx:
    results = db.query("sql", """
        SELECT name, description,
               vectorDistance(embedding, ?, 'COSINE') as distance
        FROM Product
        ORDER BY distance ASC
        LIMIT 5
    """, query_embedding)

    for record in results:
        print(f"{record.get('name')}: {record.get('distance'):.4f}")
```

## Vector Functions

ArcadeDB provides several vector functions:

### Distance Metrics

```python
# Cosine similarity (0-2, lower = more similar)
db.query("sql", """
    SELECT vectorDistance(embedding, ?, 'COSINE') as score
    FROM Product
""", query_vector)

# Euclidean distance
db.query("sql", """
    SELECT vectorDistance(embedding, ?, 'EUCLIDEAN') as score
    FROM Product
""", query_vector)

# Dot product
db.query("sql", """
    SELECT vectorDistance(embedding, ?, 'DOT') as score
    FROM Product
""", query_vector)
```

### Nearest Neighbors

```python
# Find k-nearest neighbors
with db.transaction() as tx:
    results = db.query("sql", """
        SELECT name,
               vectorNearest(embedding, ?, 10) as neighbors
        FROM Product
        WHERE @rid = #12:0
    """, query_vector)
```

## Advanced Patterns

### Hybrid Search (Vectors + Filters)

Combine semantic search with traditional filtering:

```python
with db.transaction() as tx:
    results = db.query("sql", """
        SELECT name, price, category,
               vectorDistance(embedding, ?, 'COSINE') as similarity
        FROM Product
        WHERE category = 'Electronics'
          AND price < 1000
          AND inStock = true
        ORDER BY similarity ASC
        LIMIT 10
    """, query_embedding)
```

### Multi-Vector Search

Search across multiple vector properties:

```python
# Create product with multiple embeddings
with db.transaction() as tx:
    db.command("sql", """
        CREATE VERTEX Product
        SET name = 'Laptop',
            title_embedding = ?,
            description_embedding = ?,
            image_embedding = ?
    """, title_vec, desc_vec, image_vec)

# Search combining multiple vectors
with db.transaction() as tx:
    results = db.query("sql", """
        SELECT name,
               (vectorDistance(title_embedding, ?, 'COSINE') * 0.5 +
                vectorDistance(description_embedding, ?, 'COSINE') * 0.3 +
                vectorDistance(image_embedding, ?, 'COSINE') * 0.2) as score
        FROM Product
        ORDER BY score ASC
        LIMIT 10
    """, query_title, query_desc, query_image)
```

### Graph + Vectors

Combine graph traversal with vector similarity:

```python
# Find similar products bought by friends
with db.transaction() as tx:
    results = db.query("cypher", """
        MATCH (user:User {id: $userId})-[:FRIEND]->(friend:User)
             ,(friend)-[:PURCHASED]->(product:Product)
        WHERE vectorDistance(product.embedding, $queryVector, 'COSINE') < 0.5
        RETURN DISTINCT product.name,
               vectorDistance(product.embedding, $queryVector, 'COSINE') as similarity
        ORDER BY similarity ASC
        LIMIT 10
    """, {'userId': 123, 'queryVector': query_vector})
```

## HNSW Index Configuration

Tune vector index performance:

```python
# Create index with custom parameters
with db.transaction() as tx:
    db.command("sql", """
        CREATE VERTEX INDEX ON Product (embedding)
        VECTOR 1536
        HNSW {
            m: 16,              -- Max connections per node
            efConstruction: 200, -- Construction quality
            ef: 100             -- Search quality
        }
    """)
```

**Parameter Guidelines:**
- **m**: 8-64 (higher = better accuracy, more memory)
- **efConstruction**: 100-500 (higher = better index quality, slower build)
- **ef**: 50-500 (higher = better search accuracy, slower queries)

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
# Batch embedding generation
texts = ["product 1", "product 2", "product 3", ...]
embeddings = model.encode(texts, batch_size=32)

# Batch insert
with db.transaction() as tx:
    for text, embedding in zip(texts, embeddings):
        db.command("sql", """
            CREATE VERTEX Product
            SET description = ?,
                embedding = ?
        """, text, embedding.tolist())
```

### Index Warming

Pre-load vector index into memory:

```python
# Warm up the index
with db.transaction() as tx:
    dummy_vector = [0.0] * 1536
    db.query("sql", """
        SELECT FROM Product
        WHERE vectorDistance(embedding, ?, 'COSINE') < 999
        LIMIT 1
    """, dummy_vector)
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
