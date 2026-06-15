# NumPy Support Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_numpy_support.py){ .md-button }

There are 3 tests covering automatic conversion of NumPy arrays passed into `db.command()`, `db.query()`, and regular transactions. Each test is guarded by `@pytest.mark.skipif(not HAS_NUMPY, ...)`.

## Coverage

- Automatic NumPy array conversion when used as a `db.command()` parameter
- Automatic NumPy array conversion when used as a `db.query()` parameter
- NumPy array conversion in regular transactions (no batch context), including `arcadedb.to_java_float_array()`

### test_numpy_array_conversion_in_command

Tests automatic conversion of NumPy arrays in `db.command()`.

**What it tests:**

- Inserting a `np.float32` array directly as a bound `?` parameter
- Round-trip retrieval against an `ARRAY_OF_FLOATS` property
- Approximate float equality of the stored values

**Pattern:**

```python
db.command("sql", "CREATE VERTEX TYPE VectorData")
db.command("sql", "CREATE PROPERTY VectorData.vector ARRAY_OF_FLOATS")

vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)

with db.transaction():
    db.command("sql", "INSERT INTO VectorData SET vector = ?", vec)

result = db.query("sql", "SELECT FROM VectorData").first()
stored_vec = result.get("vector")
assert len(stored_vec) == 3
assert abs(stored_vec[0] - 0.1) < 0.0001
```

---

### test_numpy_array_conversion_in_query

Tests automatic conversion of NumPy arrays in `db.query()`.

**What it tests:**

- Passing a `np.float32` array as a bound `?` parameter in a `WHERE` clause
- That the call succeeds without raising

**Pattern:**

```python
with db.transaction():
    db.command("sql", "INSERT INTO VectorData SET vector = ?", [0.1, 0.2, 0.3])

vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
db.query("sql", "SELECT FROM VectorData WHERE vector = ?", vec)
```

---

### test_numpy_array_conversion_in_transaction

Tests NumPy array conversion in regular transactions (no batch context).

**What it tests:**

- Converting `np.float32` arrays via `arcadedb.to_java_float_array()`
- Inserting into both a vertex type (`VectorData`) and a document type (`DocData`) within one transaction
- Round-trip retrieval of both `ARRAY_OF_FLOATS` properties

**Pattern:**

```python
vec1_java = arcadedb.to_java_float_array(np.array([0.1, 0.2, 0.3], dtype=np.float32))
vec2_java = arcadedb.to_java_float_array(np.array([0.4, 0.5, 0.6], dtype=np.float32))

with db.transaction():
    db.command("sql", "INSERT INTO VectorData SET vector = ?", vec1_java)
    db.command("sql", "INSERT INTO DocData SET embedding = ?", vec2_java)
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
2. **Batch inserts** - Use chunked transactions for many vectors
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
