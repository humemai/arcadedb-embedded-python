# Vector API

Vector search capabilities in ArcadeDB use JVector (a graph-based index combining HNSW
and DiskANN concepts) for fast approximate nearest neighbor search. Perfect for semantic
search, recommendation systems, and similarity-based queries.

## Overview

ArcadeDB's vector support enables:

- **Semantic Search**: Find similar documents, images, or any embedded content
- **Recommendation Systems**: Find similar items based on feature vectors
- **Clustering**: Group similar vectors together
- **Anomaly Detection**: Find outliers in vector space

**Key Features:**

- Graph-based indexing for O(log N) search performance
- Multiple distance metrics (cosine, euclidean, inner product)
- Native NumPy integration (optional)
- Configurable precision/performance trade-offs

## Module Functions

Utility functions for converting between Python and Java vector representations:

### `to_java_float_array(vector)`

Convert a Python array-like object to a Java float array compatible with ArcadeDB's
vector indexing.

**Parameters:**

- `vector`: Array-like object containing float values
    - Python list: `[0.1, 0.2, 0.3]`
    - NumPy array: `np.array([0.1, 0.2, 0.3])`
    - Any iterable: `(0.1, 0.2, 0.3)`

**Returns:**

- Java float array (`JArray<JFloat>`)

**Example:**

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
import numpy as np

# From Python list
vec_list = [0.1, 0.2, 0.3, 0.4]
java_vec = to_java_float_array(vec_list)

# From NumPy array (if NumPy installed)
vec_np = np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32)
java_vec = to_java_float_array(vec_np)

# Use with vertex
vertex = db.new_vertex("Document")
vertex.set("embedding", java_vec)
vertex.save()
```

---

### `to_python_array(java_vector, use_numpy=True)`

Convert a Java array or ArrayList to a Python array.

**Parameters:**

- `java_vector`: Java array or ArrayList of floats
- `use_numpy` (bool): Return NumPy array if available (default: `True`)
    - If `True` and NumPy is installed: returns `np.ndarray`
    - If `False` or NumPy unavailable: returns Python `list`

**Returns:**

- `np.ndarray` (if `use_numpy=True` and NumPy available)
- `list` (otherwise)

**Example:**

```python
from arcadedb_embedded import to_python_array

# Get vector from vertex
vertex = result_set.next()
java_vec = vertex.get("embedding")

# Convert to NumPy array
np_vec = to_python_array(java_vec, use_numpy=True)
print(type(np_vec))  # <class 'numpy.ndarray'>

# Convert to Python list
py_list = to_python_array(java_vec, use_numpy=False)
print(type(py_list))  # <class 'list'>
```

---

## VectorIndex Class

Wrapper for ArcadeDB's vector index, providing similarity search capabilities.

### Creation via Database

Vector indexes are created using the `Database.create_vector_index()` method:

**Signature:**

```python
db.create_vector_index(
    vertex_type: str,
    vector_property: str,
    dimensions: int,
    distance_function: str = "cosine",
    max_connections: int = 16,
    beam_width: int = 100,
    quantization: str = "INT8",
    location_cache_size: int | None = None,
    graph_build_cache_size: int | None = None,
    mutations_before_rebuild: int | None = None,
    store_vectors_in_graph: bool = False,
    add_hierarchy: bool | None = True,
    pq_subspaces: int | None = None,
    pq_clusters: int | None = None,
    pq_center_globally: bool | None = None,
    pq_training_limit: int | None = None,
    build_graph_now: bool = True,
) -> VectorIndex
```

**Parameters:**

- `vertex_type` (str): Vertex type containing vectors
- `vector_property` (str): Property name storing vector arrays
- `dimensions` (int): Vector dimensionality (must match your embeddings)
- `distance_function` (str): Distance metric (default: `"cosine"`)
    - `"cosine"`: Cosine distance (1 - cosine similarity)
    - `"euclidean"`: Euclidean distance (L2 norm)
    - `"inner_product"`: Negative inner product
- `max_connections` (int): Max connections per node (default: 16)
    - Maps to `maxConnections` in JVector
    - Higher = better recall, more memory
        - Typical range: 8-64
- `beam_width` (int): Beam width for search/construction (default: 100)
    - Maps to `beamWidth` in JVector
    - Higher = better recall, slower search
        - Typical range: 50-500
- `quantization` (str | None): `"INT8"` (recommended), `"BINARY"`, `"PRODUCT"`, or `None` (default: `"INT8"`)
    - Prefer `"INT8"` for current production usage in these bindings.
    - `"PRODUCT"`/PQ is available but currently not recommended for production workloads.
- `build_graph_now` (bool): If `True` (default), eagerly prepares the vector graph during index creation.
    Set to `False` to defer graph preparation until first query.

**Returns:**

- `VectorIndex`: Index object for searching

**Example:**

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
import numpy as np

# Create database and schema
db = arcadedb.create_database("./vector_db")

db.schema.create_vertex_type("Document")
db.schema.create_property("Document", "id", "STRING")
db.schema.create_property("Document", "text", "STRING")
db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")
db.schema.create_index("Document", ["id"], unique=True)

# Create vector index
index = db.create_vector_index(
    vertex_type="Document",
    vector_property="embedding",
    dimensions=384,  # Match your embedding model
    distance_function="cosine",
    max_connections=16,
    beam_width=100
)

print(f"Created vector index: {index}")
```

---

### `VectorIndex.find_nearest(query_vector, k=10, overquery_factor=4, allowed_rids=None)`

Find k-nearest neighbors to the query vector.

**Note:** With default settings (`build_graph_now=True` in `create_vector_index`), graph
preparation runs during index creation. If you set `build_graph_now=False`, the first call
to `find_nearest` may perform lazy graph preparation and therefore take longer.

**Parameters:**

- `query_vector`: Query vector as:
    - Python list: `[0.1, 0.2, ...]`
    - NumPy array: `np.array([0.1, 0.2, ...])`
    - Any array-like iterable
- `k` (int): Number of neighbors to return (default: 10)
- `overquery_factor` (int): Multiplier for search-time over-querying (implicit efSearch)
    (default: 4)
- `allowed_rids` (List[str]): Optional list of RID strings (e.g. `["#1:0", "#2:5"]`) to
  restrict search (default: `None`)

**Returns:**

- `List[Tuple[record, float]]`: List of `(record, distance)` tuples
    - `record`: Matched ArcadeDB record object (Vertex, Document, or Edge)
    - `distance`: Similarity score (float)
        - Cosine: lower = more similar
        - Euclidean: higher = more similar
        - Inner product: lower = more similar (negative dot product)
    - Range depends on `distance_function`

**Example:**

```python
# Generate query vector (in practice, from your embedding model)
query_text = "machine learning tutorial"
query_vector = generate_embedding(query_text)  # Your embedding function

# Search for 5 most similar documents
neighbors = index.find_nearest(query_vector, k=5)

# Search with RID filtering
allowed_rids = ["#10:5", "#10:8", "#10:12"]
filtered_neighbors = index.find_nearest(query_vector, k=5, allowed_rids=allowed_rids)

for record, distance in neighbors:
    doc_id = record.get("id")
    text = record.get("text")
    print(f"Distance: {distance:.4f} | ID: {doc_id}")
    print(f"  Text: {text[:100]}...")
```

**Distance Interpretation:**

| Function | Range | Similarity direction |
|----------|-------|----------------------|
| cosine | [0, 2] | lower is better (0 = identical) |
| euclidean | (0, 1] | higher is better (1 = identical) |
| inner_product | (-∞, ∞) | lower is better (negative dot product) |

- Vertex must have the vector property populated
- Vector dimensionality must match index dimensions
- Call within a transaction for consistency

---

### `VectorIndex.build_graph_now()`

Force an immediate rebuild/preparation of the vector graph.

Use this when you want to control when rebuild cost is paid, for example:

- after bulk inserts,
- after bulk deletes/removals,
- before opening traffic after large vector mutations.

This is especially useful if you created the index with `build_graph_now=False` and want
to avoid rebuild work on the first query.

**Returns:**

- `None`

**Example:**

```python
# After large vector changes, force rebuild now
index.build_graph_now()
```

---

## Complete Examples

### Semantic Search with Sentence Transformers

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
from sentence_transformers import SentenceTransformer
import numpy as np

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions

# Create database and schema
db = arcadedb.create_database("./semantic_search")

db.schema.create_vertex_type("Document")
db.schema.create_property("Document", "id", "STRING")
db.schema.create_property("Document", "title", "STRING")
db.schema.create_property("Document", "content", "STRING")
db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")
db.schema.create_index("Document", ["id"], unique=True)

# Create vector index (384 dimensions for all-MiniLM-L6-v2)
index = db.create_vector_index(
    vertex_type="Document",
    vector_property="embedding",
    dimensions=384,
    distance_function="cosine",
    max_connections=16,
    beam_width=100  # Default beam width
)

# Sample documents
documents = [
    {"id": "doc1", "title": "Python Tutorial",
     "content": "Learn Python programming basics"},
    {"id": "doc2", "title": "Machine Learning Guide",
     "content": "Introduction to ML algorithms"},
    {"id": "doc3", "title": "Database Systems",
     "content": "Understanding relational databases"},
]

# Index documents
print("Indexing documents...")
with db.transaction():
    for doc in documents:
        # Generate embedding
        text = f"{doc['title']} {doc['content']}"
        embedding = model.encode(text)

        # Create vertex
        vertex = db.new_vertex("Document")
        vertex.set("id", doc["id"])
        vertex.set("title", doc["title"])
        vertex.set("content", doc["content"])
        vertex.set("embedding", to_java_float_array(embedding))
        vertex.save()

print(f"Indexed {len(documents)} documents")

# Search
query = "How to learn programming"
query_embedding = model.encode(query)

print(f"\nQuery: '{query}'")
results = index.find_nearest(query_embedding, k=3)

for vertex, distance in results:
    print(f"\nDistance: {distance:.4f}")
    print(f"Title: {vertex.get('title')}")
    print(f"Content: {vertex.get('content')}")

db.close()
```

---

### Hybrid Search (Vector + Filters)

Combine vector similarity with property filters using SQL:

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
import numpy as np

db = arcadedb.open_database("./products_db")

# Create schema
db.schema.create_vertex_type("Product")
db.schema.create_property("Product", "id", "STRING")
db.schema.create_property("Product", "name", "STRING")
db.schema.create_property("Product", "category", "STRING")
db.schema.create_property("Product", "price", "DECIMAL")
db.schema.create_property("Product", "features", "ARRAY_OF_FLOATS")
db.schema.create_index("Product", ["category"], unique=False)

# Create vector index
index = db.create_vector_index(
    vertex_type="Product",
    vector_property="features",
    dimensions=128
)

# Add products with feature vectors
products = [
    {"id": "p1", "name": "Laptop", "category": "Electronics",
     "price": 999.99, "features": np.random.rand(128)},
    {"id": "p2", "name": "Mouse", "category": "Electronics",
     "price": 29.99, "features": np.random.rand(128)},
    {"id": "p3", "name": "Desk", "category": "Furniture",
     "price": 299.99, "features": np.random.rand(128)},
]

with db.transaction():
    for prod in products:
        v = db.new_vertex("Product")
        v.set("id", prod["id"])
        v.set("name", prod["name"])
        v.set("category", prod["category"])
        v.set("price", prod["price"])
        v.set("features", to_java_float_array(prod["features"]))
        v.save()
        # Note: LSM vector index automatically indexes new records

# Hybrid search: vector similarity + filters
query_features = np.random.rand(128)
candidates = index.find_nearest(query_features, k=100)  # Get many candidates

# Filter by category and price
filtered_results = []
for vertex, distance in candidates:
    category = vertex.get("category")
    price = float(vertex.get("price"))

    if category == "Electronics" and price < 500:
        filtered_results.append((vertex, distance))

    if len(filtered_results) >= 5:  # Want top 5 after filtering
        break

print("Filtered Results:")
for vertex, distance in filtered_results:
    print(f"{vertex.get('name')} - ${vertex.get('price')} - {distance:.4f}")

db.close()
```

---

### Image Similarity Search

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array
from PIL import Image
import numpy as np

# Assuming you have a function to generate image embeddings
def get_image_embedding(image_path):
    """
    Generate embedding for image using your model
    (e.g., ResNet, CLIP, etc.)
    """
    # Placeholder - use your actual embedding model
    return np.random.rand(512)  # Example: 512-dim embedding

db = arcadedb.create_database("./image_search")

# Schema
db.schema.create_vertex_type("Image")
db.schema.create_property("Image", "id", "STRING")
db.schema.create_property("Image", "filename", "STRING")
db.schema.create_property("Image", "path", "STRING")
db.schema.create_property("Image", "embedding", "ARRAY_OF_FLOATS")

# Create index
index = db.create_vector_index(
    vertex_type="Image",
    vector_property="embedding",
    dimensions=512,
    distance_function="cosine",
    max_connections=24,  # Higher for image search
    beam_width=200
)

# Index images
image_files = ["img1.jpg", "img2.jpg", "img3.jpg"]

with db.transaction():
    for idx, img_file in enumerate(image_files):
        embedding = get_image_embedding(img_file)

        v = db.new_vertex("Image")
        v.set("id", f"img_{idx}")
        v.set("filename", img_file)
        v.set("path", f"/images/{img_file}")
        v.set("embedding", to_java_float_array(embedding))
        v.save()

        # Note: LSM vector index automatically indexes new records

# Search for similar images
query_image = "query.jpg"
query_embedding = get_image_embedding(query_image)

similar_images = index.find_nearest(query_embedding, k=5)

print(f"Similar images to {query_image}:")
for vertex, distance in similar_images:
    print(f"  {vertex.get('filename')} - similarity: {1 - distance:.4f}")

db.close()
```

---

## Performance Tuning

### Vector Index Parameters

**max_connections (connections per node):**

- **Lower (12)**: Faster build, less memory, lower recall
- **Medium (16)**: Balanced (default)
- **Higher (32)**: Better recall, more memory, slower build

**overquery_factor (search size):**

- **Lower (2)**: Faster search, lower recall
- **Medium (4)**: Balanced (default)
- **Higher (8)**: Better recall, slower search

**beam_width:**

- **Lower (64)**: Faster build, lower quality
- **Medium (100)**: Balanced (default)
- **Higher (200)**: Better quality, slower build

### Distance Functions

**Cosine Distance:**

- Best for: Text embeddings, normalized vectors
- Range: [0, 2], lower is better
- Use when: Direction matters more than magnitude

**Euclidean Distance:**

- Best for: Image embeddings, spatial data
- Range: [0, ∞), lower is better
- Use when: Absolute distance matters

**Inner Product:**

- Best for: Collaborative filtering, when vectors aren't normalized
- Range: (-∞, ∞), higher is better (note: inverted!)
- Use when: Magnitude information is important

### Memory Considerations

Approximate memory per vertex:

```
memory_per_vertex = dimensions * 4 bytes + max_connections * 8 bytes + overhead
```

Example for 384-dim vectors with max_connections=16:

```
384 * 4 + 16 * 8 + ~100 bytes ≈ 1.8 KB per vertex
```

For 1 million vectors: ~1.8 GB RAM

---

## Error Handling

```python
from arcadedb_embedded import ArcadeDBError, to_java_float_array
import numpy as np

try:
    # Dimension mismatch
    index = db.create_vector_index("Doc", "emb", dimensions=384)

    v = db.new_vertex("Doc")
    v.set("emb", to_java_float_array(np.random.rand(512)))  # Wrong size!
    v.save()
    # Indexing happens automatically and may fail asynchronously or on next access

except ArcadeDBError as e:
    print(f"Error: {e}")
    # Handle dimension mismatch

try:
    # Missing vector property
    v = db.new_vertex("Doc")
    v.set("id", "doc1")
    # Forgot to set embedding!
    v.save()
    # Indexing happens automatically

except ArcadeDBError as e:
    print(f"Error: {e}")
    # Handle missing property
```

---

## See Also

- [Vector Search Guide](../guide/vectors.md) - Comprehensive vector search strategies
- [Vector Examples](../examples/vectors.md) - More practical examples
- [Database API](database.md) - Database operations
- [Query Guide](../guide/core/queries.md) - Combining vectors with queries
