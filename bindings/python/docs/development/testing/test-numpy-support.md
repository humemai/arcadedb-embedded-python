# NumPy Support Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_numpy_support.py){ .md-button }

These notes mirror the Python tests in [test_numpy_support.py]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_numpy_support.py). There are 3 tests covering NumPy array storage, retrieval, and vector search integration. See [test_numpy_support.py]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_numpy_support.py) for implementations.

## Coverage

- Array storage (float32, float64) as vector properties
- Array retrieval and conversion to NumPy
- HNSW similarity search with NumPy vectors

### test_store_and_retrieve_numpy_array
Tests storing and retrieving NumPy arrays.

**What it tests:**
- Storing NumPy array as vector property
- Array type preservation
- Round-trip conversion

**Pattern:**
```python
# Create NumPy array
embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

# Store in database
vertex = db.new_vertex("Document")
vertex.set("embedding", embedding.tolist())
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Document").first()
stored_embedding = result.get("embedding")

# Verify
np.testing.assert_array_almost_equal(embedding, stored_embedding)
```

---

### test_numpy_vector_search
Tests vector similarity search with NumPy arrays.

**What it tests:**
- Creating HNSW (JVector) index on vector property
- Inserting NumPy-generated embeddings
- Performing similarity search
- Retrieving nearest neighbors

**Pattern:**
```python
import numpy as np

# Create schema with HNSW (JVector) index
db.schema.create_vertex_type("Document")
db.schema.create_property("Document", "embedding", "ARRAY_OF_FLOATS")

db.create_vector_index("Document", "embedding", dimensions=128)

# Insert vectors
for i in range(100):
    embedding = np.random.rand(128).astype(np.float32)

    vertex = db.new_vertex("Document")
    vertex.set("docId", i)
    vertex.set("embedding", embedding.tolist())
    vertex.save()

# Search for similar vectors
query_vector = np.random.rand(128).astype(np.float32)

results = db.query(
    "sql",
    "SELECT FROM Document WHERE embedding ~ ?",
    query_vector.tolist()
)

for result in results:
    print(result.get("docId"))
```

---

### test_numpy_dtype_conversion
Tests NumPy dtype handling.

**What it tests:**
- float32 → Java float[] conversion
- float64 → Java double[] conversion
- int32 → Java int[] conversion
- Type preservation during round-trip

**Pattern:**
```python
import numpy as np

# Test float32
vec_f32 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
vertex.set("vec_f32", vec_f32.tolist())

# Test float64
vec_f64 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
vertex.set("vec_f64", vec_f64.tolist())

# Test int32
vec_int = np.array([1, 2, 3], dtype=np.int32)
vertex.set("vec_int", vec_int.tolist())

vertex.save()

# Retrieve and verify types
result = db.query("sql", "SELECT FROM Document").first()
assert isinstance(result.get("vec_f32"), list)
```

## Test Patterns

### Store NumPy Array
```python
import numpy as np

embedding = np.random.rand(384).astype(np.float32)

vertex = db.new_vertex("Document")
vertex.set("embedding", embedding.tolist())  # Convert to list
vertex.save()
```

### Retrieve as NumPy
```python
result = db.query("sql", "SELECT FROM Document").first()
embedding_list = result.get("embedding")

# Convert back to NumPy
embedding = np.array(embedding_list, dtype=np.float32)
```

### Vector Search with NumPy
```python
import numpy as np

# Generate query vector
query = np.random.rand(384).astype(np.float32)

# Search (convert to list for query)
results = db.query(
    "sql",
    "SELECT FROM Document WHERE embedding ~ ?",
    query.tolist()
)
```

## Common Assertions

```python
import numpy as np

# Array equality
np.testing.assert_array_almost_equal(expected, actual)

# Array shape
assert embedding.shape == (384,)

# Array dtype
assert embedding.dtype == np.float32

# List to array conversion
embedding_list = result.get("embedding")
embedding = np.array(embedding_list, dtype=np.float32)
assert isinstance(embedding, np.ndarray)
```

## Integration with ML Libraries

### Sentence Transformers
```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embedding
text = "Hello world"
embedding = model.encode(text)  # Returns NumPy array

# Store in ArcadeDB
vertex = db.new_vertex("Document")
vertex.set("text", text)
vertex.set("embedding", embedding.tolist())
vertex.save()
```

### OpenAI Embeddings
```python
import openai
import numpy as np

# Get embedding from OpenAI
response = openai.Embedding.create(
    input="Hello world",
    model="text-embedding-ada-002"
)

embedding = np.array(response['data'][0]['embedding'], dtype=np.float32)

# Store
vertex.set("embedding", embedding.tolist())
```

### scikit-learn
```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

vectorizer = TfidfVectorizer()
vectors = vectorizer.fit_transform(documents)

# Convert sparse to dense NumPy
dense_vectors = vectors.toarray()

# Store each vector
for i, vec in enumerate(dense_vectors):
    vertex = db.new_vertex("Document")
    vertex.set("vector", vec.tolist())
    vertex.save()
```

## Performance Tips

1. **Use float32** - Faster and smaller than float64
2. **Batch inserts** - Use BatchContext for many vectors
3. **Convert once** - `.tolist()` only when storing
4. **Numpy for math** - Use NumPy for vector operations
5. **HNSW (JVector) for search** - Enable similarity search

## Key Takeaways

1. **Convert to list** - Use `.tolist()` before storing
2. **Convert back** - Use `np.array()` after retrieving
3. **Prefer float32** - Best for embeddings
4. **Use HNSW (JVector)** - Enable fast similarity search
5. **Works with ML libs** - Direct integration

## See Also

- **[Vector API](../../api/vector.md)** - Vector operations
- **[Vector Tests](test-vector.md)** - Core vector functionality
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** - Real-world usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** - NumPy integration
