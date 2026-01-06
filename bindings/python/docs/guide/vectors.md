# Vector Search Guide

Vector search enables semantic similarity search using embeddings from machine learning
models. This guide covers strategies, best practices, and patterns for implementing
vector search with ArcadeDB.

## Overview

Vector search transforms your data into high-dimensional vectors (embeddings) and finds
similar items using distance metrics. Perfect for:

- **Semantic Search**: Find documents by meaning, not just keywords
- **Recommendation Systems**: Find similar products, users, or content
- **Image Search**: Find similar images using visual embeddings
- **Question Answering**: Match questions to relevant answers
- **Anomaly Detection**: Find outliers in vector space

**How It Works:**

1. Generate embeddings using ML models (Sentence Transformers, OpenAI, etc.)
2. Store vectors in ArcadeDB with HNSW (JVector) indexing
3. Query with new vectors to find nearest neighbors
4. Get results ranked by similarity

## Quick Start

### 1. Install Dependencies

```bash
pip install arcadedb-embedded sentence-transformers
```

### 2. Create Vector Index

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
from sentence_transformers import SentenceTransformer

documents = [
    "Python is a programming language",
    "ArcadeDB is a graph database",
    "Machine learning uses neural networks"
]

query = "What is Python?"
model = SentenceTransformer('all-MiniLM-L6-v2')

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Document")
    db.schema.create_property("Document", "text", "STRING")
    db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Document",
        vector_property="embedding",
        dimensions=384,  # Match your model
        distance_function="cosine"
    )

    # Index documents
    with db.transaction():
        for doc_text in documents:
            embedding = model.encode(doc_text)

            vertex = db.new_vertex("Document")
            vertex.set("text", doc_text)
            vertex.set("embedding", to_java_float_array(embedding))
            vertex.save()

    # Search
    query_embedding = model.encode(query)
    results = index.find_nearest(query_embedding, k=3)

    for vertex, distance in results:
        text = vertex.get("text")
        similarity = 1 - distance  # Convert distance to similarity
        print(f"[{similarity:.3f}] {text}")
```

## Embedding Models

### Sentence Transformers

Best for text similarity:

```python
from sentence_transformers import SentenceTransformer

# All-purpose (384 dimensions)
model = SentenceTransformer('all-MiniLM-L6-v2')

# High quality (768 dimensions)
model = SentenceTransformer('all-mpnet-base-v2')

# Multilingual (768 dimensions)
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

# Generate embedding
embedding = model.encode("Your text here")
print(embedding.shape)  # (384,) or (768,)
```

**Installation:**
```bash
pip install sentence-transformers
```

---

### OpenAI Embeddings

Commercial API with high quality:

```python
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

def get_embedding(text, model="text-embedding-3-small"):
    response = client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding

# text-embedding-3-small: 1536 dimensions
# text-embedding-3-large: 3072 dimensions
embedding = get_embedding("Your text here")
```

**Installation:**
```bash
pip install openai
```

---

### Hugging Face Transformers

For custom models:

```python
from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
model = AutoModel.from_pretrained('bert-base-uncased')

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    # Use [CLS] token embedding
    embedding = outputs.last_hidden_state[0][0].numpy()
    return embedding

embedding = get_embedding("Your text here")
```

---

### CLIP (Images + Text)

For multimodal search:

```python
from transformers import CLIPProcessor, CLIPModel
from PIL import Image

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Image embedding
image = Image.open("photo.jpg")
inputs = processor(images=image, return_tensors="pt")
image_embedding = model.get_image_features(**inputs)[0].detach().numpy()

# Text embedding
inputs = processor(text=["a photo of a cat"], return_tensors="pt")
text_embedding = model.get_text_features(**inputs)[0].detach().numpy()
```

## Distance Functions

### Cosine Distance

**Best for:** Text embeddings, normalized vectors

**Formula:** `1 - (A · B) / (||A|| * ||B||)`

**Range:** [0, 2], lower is more similar

**Usage:**
```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Document")
    db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Document",
        vector_property="embedding",
        dimensions=384,
        distance_function="cosine"  # Default
    )
```

**When to Use:**
- Text embeddings (Sentence Transformers, OpenAI)
- When direction matters more than magnitude
- Most common choice for semantic search

---

### Euclidean Distance

**Best for:** Image embeddings, spatial data

**Formula:** `sqrt(Σ(Ai - Bi)²)`

**Range:** [0, ∞), lower is more similar

**Usage:**
```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Image")
    db.schema.create_property("Image", "features", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Image",
        vector_property="features",
        dimensions=512,
        distance_function="euclidean"
    )
```

**When to Use:**
- Image embeddings (ResNet, VGG)
- When absolute distance matters
- Spatial or geometric data

---

### Inner Product

**Best for:** Collaborative filtering, recommendations

**Formula:** `-(A · B)`

**Range:** (-∞, ∞), **higher** is more similar (note: inverted!)

**Usage:**
```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "preferences", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="User",
        vector_property="preferences",
        dimensions=128,
        distance_function="inner_product"
    )
```

**When to Use:**
- Recommendation systems
- When vectors aren't normalized
- When magnitude carries information

## Index Parameters

### Max Connections

Controls connections per node in the graph. Maps to `maxConnections` in JVector.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=384,
        max_connections=32  # Number of connections (default: 32)
    )
```

**Trade-offs:**

| Max Connections | Recall | Memory | Build Speed | Search Speed |
|-----------------|--------|--------|-------------|--------------|
| 16              | Good   | Low    | Fast        | Fast         |
| 32 (Default)    | Decent | Medium | Medium      | Medium       |
| 64              | High   | High   | Slow        | Slow         |

**Recommendations:**
- **Small datasets (<100K)**: max_connections=16
- **Medium datasets (100K-1M)**: max_connections=32 (default)
- **Large datasets (>1M)**: max_connections=64

---

### Beam Width (ef)

Controls search quality vs speed. Maps to `beamWidth` in JVector.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=384,
        beam_width=256  # Search candidate list size (default: 256)
    )
```

**Trade-offs:**

| Beam Width | Recall | Search Speed |
|------------|--------|--------------|
| <256       | Good   | Fast         |
| 256 (Def)  | Medium | Medium       |
| >256       | High   | Slow         |

**Recommendations:**
- **Fast search**: beam_width=128
- **Balanced**: beam_width=256 (default)
- **High accuracy**: beam_width=512

---

### Overquery Factor

Controls search-time accuracy by exploring more candidates than requested.

```python
# Actual search will explore k * overquery_factor candidates
results = index.find_nearest(
    query_embedding,
    k=10,
    overquery_factor=16  # Default: 16
)
```

**Trade-offs:**

| Factor | Recall | Search Speed |
|--------|--------|--------------|
| <16    | Low    | Fast         |
| 16     | Decent | Medium       |
| >16    | High   | Slow         |


**Recommendations:**
- **Fast search**: overquery_factor=8
- **Balanced**: overquery_factor=16 (default)
- **High accuracy**: overquery_factor=32

## Schema Design

### Basic Schema

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Document")
    db.schema.create_property("Document", "id", "STRING")
    db.schema.create_property("Document", "text", "STRING")
    db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")
    db.schema.create_index("Document", ["id"], unique=True)

    index = db.create_vector_index(
        vertex_type="Document",
        vector_property="embedding",
        dimensions=384
    )
```

---

### With Metadata

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Article")
    db.schema.create_property("Article", "id", "STRING")
    db.schema.create_property("Article", "title", "STRING")
    db.schema.create_property("Article", "content", "STRING")
    db.schema.create_property("Article", "category", "STRING")
    db.schema.create_property("Article", "created_at", "DATETIME")
    db.schema.create_property("Article", "embedding", "ARRAY_OF_FLOATS")

    db.schema.create_index("Article", ["id"], unique=True)
    db.schema.create_index("Article", ["category"], unique=False)

    index = db.create_vector_index(
        vertex_type="Article",
        vector_property="embedding",
        dimensions=384
    )
```

---

### Multiple Vector Types

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Product")
    db.schema.create_property("Product", "name", "STRING")
    db.schema.create_property("Product", "description", "STRING")
    db.schema.create_property("Product", "text_embedding", "ARRAY_OF_FLOATS")
    db.schema.create_property("Product", "image_embedding", "ARRAY_OF_FLOATS")

    text_index = db.create_vector_index(
        vertex_type="Product",
        vector_property="text_embedding",
        dimensions=384,
        distance_function="cosine"
    )

    image_index = db.create_vector_index(
        vertex_type="Product",
        vector_property="image_embedding",
        dimensions=512,
        distance_function="euclidean"
    )
```

## Search Patterns

### Basic Similarity Search

```python
query_embedding = model.encode("machine learning")
results = index.find_nearest(query_embedding, k=10)

for vertex, distance in results:
    text = vertex.get("text")
    print(f"{text} (distance: {distance:.4f})")
```

---

### Hybrid Search (Vector + Filters)

Combine vector similarity with metadata filters.

**Option 1: Pre-filtering (Recommended)**

Filter candidates *before* vector search using `allowed_rids`. This is more efficient as
it ensures you get `k` results that match your criteria.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    # Assume schema and vector index are already created on Article.embedding

    # 1. Query for matching RIDs using SQL or index lookup
    rs = db.query("sql", "SELECT @rid FROM Article WHERE category = 'Programming'")
    allowed_rids = [doc.get_rid() for doc in rs]

    # 2. Perform vector search restricted to those RIDs
    query_embedding = model.encode("python tutorial")
    results = index.find_nearest(query_embedding, k=10, allowed_rids=allowed_rids)

    for vertex, distance in results:
        print(f"{vertex.get('title')} (distance: {distance:.4f})")
```

**Option 2: Post-filtering**

Filter candidates *after* vector search. This is simpler but may return fewer than `k`
results if many top candidates are filtered out.

```python
# Get candidates from vector search (oversample with larger k)
query_embedding = model.encode("python tutorial")
candidates = index.find_nearest(query_embedding, k=100)

# Filter by metadata
filtered_results = []
for vertex, distance in candidates:
    category = vertex.get("category")
    created_at = vertex.get("created_at")

    # Apply filters
    if category == "Programming" and distance < 0.5:
        filtered_results.append((vertex, distance))

    if len(filtered_results) >= 10:
        break

# Display results
for vertex, distance in filtered_results:
    title = vertex.get("title")
    print(f"{title} - {distance:.4f}")
```

---

### Re-ranking with Multiple Embeddings

```python
# First pass: Text search
text_query = "red sports car"
text_embedding = text_model.encode(text_query)
text_results = text_index.find_nearest(text_embedding, k=50)

# Second pass: Image search
image_embedding = image_model.encode(query_image)
image_results = image_index.find_nearest(image_embedding, k=50)

# Combine scores
combined_scores = {}
for vertex, distance in text_results:
    rid = vertex.get("@rid")
    combined_scores[rid] = {"vertex": vertex, "text_dist": distance, "image_dist": None}

for vertex, distance in image_results:
    rid = vertex.get("@rid")
    if rid in combined_scores:
        combined_scores[rid]["image_dist"] = distance
    else:
        combined_scores[rid] = {"vertex": vertex, "text_dist": None, "image_dist": distance}

# Weighted combination
final_results = []
for rid, data in combined_scores.items():
    text_dist = data["text_dist"] or 1.0
    image_dist = data["image_dist"] or 1.0

    # Weighted average
    combined_dist = 0.6 * text_dist + 0.4 * image_dist
    final_results.append((data["vertex"], combined_dist))

# Sort by combined score
final_results.sort(key=lambda x: x[1])

for vertex, score in final_results[:10]:
    name = vertex.get("name")
    print(f"{name} - combined score: {score:.4f}")
```

---

### Pagination

```python
def paginated_search(query_embedding, page_size=10, page=0):
    """Search with pagination."""
    # Get more results than needed
    k = (page + 1) * page_size + 10
    results = index.find_nearest(query_embedding, k=k)

    # Slice for current page
    start = page * page_size
    end = start + page_size

    page_results = list(results)[start:end]
    return page_results

# Page 0
page1 = paginated_search(query_embedding, page_size=10, page=0)

# Page 1
page2 = paginated_search(query_embedding, page_size=10, page=1)
```

## Performance Optimization

### Lazy Index Building

The vector index is built lazily. The actual construction of the index happens when the
first query is executed, not when the index is created or when data is added.

This means the first search query might take longer than subsequent queries as it
triggers the index build process ("warm up").

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=384,
        distance_function="cosine"
    )

    # Add data (fast)
    with db.transaction():
        vertex = db.new_vertex("Doc")
        vertex.set("embedding", to_java_float_array(model.encode("warmup")))
        vertex.save()

    # First query (slower - triggers index build)
    print("Warming up index...")
    index.find_nearest(model.encode("warmup"), k=1)

    # Subsequent queries (fast)
    results = index.find_nearest(model.encode("example query"), k=10)
```

### Batch Indexing

```python
# Efficient: Batch in single transaction
batch_size = 1000
documents = load_documents()  # Your data source

with db.transaction():
    for i, doc in enumerate(documents):
        embedding = model.encode(doc['text'])

        vertex = db.new_vertex("Document")
        vertex.set("text", doc['text'])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

        # Commit every batch_size records
        if (i + 1) % batch_size == 0:
            db.commit()
            db.begin()

    # Commit remaining
    db.commit()
```

---

### Embedding Caching

```python
import pickle
from pathlib import Path

class EmbeddingCache:
    def __init__(self, cache_dir="./embedding_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_path(self, text):
        import hashlib
        key = hashlib.md5(text.encode()).hexdigest()
        return self.cache_dir / f"{key}.pkl"

    def get(self, text):
        cache_path = self.get_cache_path(text)
        if cache_path.exists():
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        return None

    def set(self, text, embedding):
        cache_path = self.get_cache_path(text)
        with open(cache_path, 'wb') as f:
            pickle.dump(embedding, f)

# Usage
cache = EmbeddingCache()

def get_embedding_cached(text, model):
    embedding = cache.get(text)
    if embedding is None:
        embedding = model.encode(text)
        cache.set(text, embedding)
    return embedding

# Much faster on repeated queries
embedding = get_embedding_cached("python tutorial", model)
```

---

### Incremental Updates

```python
def add_document(db, index, model, doc_data):
    """Add single document efficiently."""
    with db.transaction():
        # Generate embedding
        embedding = model.encode(doc_data['text'])

        # Create vertex
        vertex = db.new_vertex("Document")
        vertex.set("id", doc_data['id'])
        vertex.set("text", doc_data['text'])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

    return vertex

def update_document(db, index, model, doc_id, new_text):
    """Update document and re-index."""
    with db.transaction():
        # Find existing
        result = db.query("sql", f"SELECT FROM Document WHERE id = '{doc_id}'")
        if not result.has_next():
            raise ValueError(f"Document {doc_id} not found")

        vertex = result.next()

        # Update
        new_embedding = model.encode(new_text)
        vertex.set("text", new_text)
        vertex.set("embedding", to_java_float_array(new_embedding))
        vertex.save()
```

---

### Memory Management

```python
# For large datasets, process in chunks
def index_large_dataset(db, index, model, data_source, chunk_size=1000):
    """Index large dataset with memory management."""
    import gc

    chunk_count = 0

    for chunk in data_source.iter_chunks(chunk_size):
        # Generate embeddings for chunk
        texts = [item['text'] for item in chunk]
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)

        # Index chunk
        with db.transaction():
            for item, embedding in zip(chunk, embeddings):
                vertex = db.new_vertex("Document")
                vertex.set("text", item['text'])
                vertex.set("embedding", to_java_float_array(embedding))
                vertex.save()

        chunk_count += 1
        print(f"Indexed chunk {chunk_count} ({chunk_size} items)")

        # Force garbage collection
        gc.collect()
```

## Production Patterns

### Configuration Management

```python
import os
from dataclasses import dataclass

@dataclass
class VectorSearchConfig:
    model_name: str = "all-MiniLM-L6-v2"
    dimensions: int = 384
    distance_function: str = "cosine"
    max_connections: int = 32
    beam_width: int = 256
    max_items: int = 1000000

# Load from environment
config = VectorSearchConfig(
    model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    dimensions=int(os.getenv("VECTOR_DIMENSIONS", "384")),
    max_connections=int(os.getenv("JVECTOR_MAX_CONNECTIONS", "32")),
    beam_width=int(os.getenv("JVECTOR_BEAM_WIDTH", "256"))
)

# Use config
from sentence_transformers import SentenceTransformer
model = SentenceTransformer(config.model_name)

index = db.create_vector_index(
    vertex_type="Document",
    vector_property="embedding",
    dimensions=config.dimensions,
    distance_function=config.distance_function,
    max_connections=config.m,
    beam_width=config.ef
)
```

---

### Monitoring and Logging

```python
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorSearchMetrics:
    def __init__(self):
        self.search_times = []
        self.index_times = []

    def log_search(self, query, results, elapsed):
        self.search_times.append(elapsed)
        avg_time = sum(self.search_times) / len(self.search_times)

        logger.info(
            f"Search: {len(results)} results in {elapsed:.3f}s "
            f"(avg: {avg_time:.3f}s)"
        )

    def log_index(self, count, elapsed):
        self.index_times.append(elapsed)
        rate = count / elapsed if elapsed > 0 else 0

        logger.info(
            f"Indexed: {count} items in {elapsed:.2f}s "
            f"({rate:.0f} items/sec)"
        )

# Usage
metrics = VectorSearchMetrics()

# Search with timing
start = time.time()
results = index.find_nearest(query_embedding, k=10)
elapsed = time.time() - start
metrics.log_search("user query", results, elapsed)

# Indexing with timing
start = time.time()
# ... index documents ...
elapsed = time.time() - start
metrics.log_index(100, elapsed)
```

---

### Error Handling

```python
from arcadedb_embedded import ArcadeDBError

def safe_vector_search(index, query_embedding, k=10, retries=3):
    """Vector search with retry logic."""
    for attempt in range(retries):
        try:
            results = index.find_nearest(query_embedding, k=k)
            return results

        except ArcadeDBError as e:
            if attempt < retries - 1:
                logger.warning(f"Search failed (attempt {attempt + 1}): {e}")
                time.sleep(0.1 * (attempt + 1))
                continue
            else:
                logger.error(f"Search failed after {retries} attempts: {e}")
                return []

    return []

def safe_vector_index(db, index, model, document):
    """Index with error handling."""
    try:
        with db.transaction():
            embedding = model.encode(document['text'])

            vertex = db.new_vertex("Document")
            vertex.set("text", document['text'])
            vertex.set("embedding", to_java_float_array(embedding))
            vertex.save()

            return True

    except ArcadeDBError as e:
        logger.error(f"Indexing failed for document {document.get('id')}: {e}")
        return False
```

## Common Use Cases

### Semantic Document Search

```python
# Index documents
documents = [
    {"id": "doc1", "title": "Python Tutorial", "content": "Learn Python..."},
    {"id": "doc2", "title": "ML Guide", "content": "Machine learning..."},
]

for doc in documents:
    # Combine title and content for embedding
    text = f"{doc['title']}. {doc['content']}"
    embedding = model.encode(text)

    with db.transaction():
        vertex = db.new_vertex("Document")
        vertex.set("id", doc['id'])
        vertex.set("title", doc['title'])
        vertex.set("content", doc['content'])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

# Search
query = "How do I learn programming?"
query_embedding = model.encode(query)
results = index.find_nearest(query_embedding, k=5)

for vertex, distance in results:
    print(f"[{1-distance:.2f}] {vertex.get('title')}")
```

---

### Question Answering

```python
# Index Q&A pairs
qa_pairs = [
    {"q": "What is Python?", "a": "Python is a programming language..."},
    {"q": "How to install Python?", "a": "Download from python.org..."},
]

for qa in qa_pairs:
    # Embed the question
    embedding = model.encode(qa['q'])

    with db.transaction():
        vertex = db.new_vertex("QA")
        vertex.set("question", qa['q'])
        vertex.set("answer", qa['a'])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

# Find answer for new question
new_question = "Where can I get Python?"
query_embedding = model.encode(new_question)
results = index.find_nearest(query_embedding, k=1)

if results:
    vertex, distance = results[0]
    print(f"Q: {vertex.get('question')}")
    print(f"A: {vertex.get('answer')}")
    print(f"Confidence: {1-distance:.2%}")
```

---

### Product Recommendations

```python
# Index products with description embeddings
products = [
    {"sku": "PROD1", "name": "Laptop", "desc": "High performance laptop"},
    {"sku": "PROD2", "name": "Mouse", "desc": "Wireless mouse"},
]

for prod in products:
    embedding = model.encode(prod['desc'])

    with db.transaction():
        vertex = db.new_vertex("Product")
        vertex.set("sku", prod['sku'])
        vertex.set("name", prod['name'])
        vertex.set("description", prod['desc'])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

# Find similar products
target_product_desc = "portable computer"
query_embedding = model.encode(target_product_desc)
similar = index.find_nearest(query_embedding, k=5)

print("Similar products:")
for vertex, distance in similar:
    print(f"  {vertex.get('name')} - {1-distance:.2%} match")
```

## See Also

- [Vector API Reference](../api/vector.md) - Complete API documentation
- [Vector Examples](../examples/vectors.md) - Practical code examples
- [Database API](../api/database.md) - Database operations
- [JVector GitHub](https://github.com/datastax/jvector) - JVector java library
