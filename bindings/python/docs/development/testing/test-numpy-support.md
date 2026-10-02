# NumPy Support Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_numpy_support.py){ .md-button }

These tests cover automatic conversion of NumPy arrays passed into `db.command()`, `db.query()`, and regular transactions. Each test is guarded by `@pytest.mark.skipif(not HAS_NUMPY, ...)`.

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

- Inserting a `np.float32` array as the single bound `?` parameter, then asserting the stored vector is close to `[0.1, 0.2, 0.3]` (`np.allclose`)
- Passing the same array as a bound `?` parameter in a `WHERE` clause; this part asserts only that the call does not raise, not what it returns

**Pattern:**

```python
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO VectorData SET vector = ?",
        np.array([0.1, 0.2, 0.3], dtype=np.float32),
    )

vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
db.query("sql", "SELECT FROM VectorData WHERE vector = ?", vec)
```

The insert binds a NumPy array on purpose: a bare Python list as the only argument
is the positional-parameter array itself, so `[0.1, 0.2, 0.3]` would bind
`vector = 0.1`.

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
from arcadedb_embedded import to_java_float_array

embedding = np.random.rand(384).astype(np.float32)

vertex = db.new_vertex("Document")
vertex.set("embedding", to_java_float_array(embedding))
vertex.save()
```

!!! warning "Do not call `.tolist()` here"

    `.tolist()` crosses the JVM boundary one element at a time, so its cost
    grows with the dimension of every vector you store;
    `to_java_float_array()` crosses once, and it accepts a NumPy array
    directly.

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

# Pass the NumPy array straight through; db.query() converts it
results = db.query(
    "sql",
    "SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) ORDER BY distance",
    "Document[embedding]", query, 10, 100,
)
```

!!! note "`.tolist()` is not the conversion step here either"

    `db.query()` and `db.command()` accept a NumPy array as a bound parameter
    directly: `test_numpy_array_conversion_in_command` binds one in
    `db.command()` and reads the stored vector back;
    `test_numpy_array_conversion_in_query` does the same insert, then binds
    one in `db.query()` and asserts only that the call does not raise. A
    Python list is
    not a drop-in for it, and it raises no error either. When the list is the
    only argument, it is the positional-parameter array itself, one element
    per `?` (`test_single_list_arg_is_positional_param_array` in
    `test_core.py`): `db.command("sql", "INSERT INTO VectorData SET vector = ?",
    [0.1, 0.2, 0.3])` stores the scalar `0.1`, not the vector. Among several
    arguments, as in the query above, a list is one collection parameter, but
    it crosses into the JVM element by element.

    `to_java_float_array()` is accepted here too; the binding passes a NumPy
    argument through it automatically.

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
from arcadedb_embedded import to_java_float_array

model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embedding
text = "Hello world"
embedding = model.encode(text)  # Returns NumPy array

# Store in ArcadeDB
vertex = db.new_vertex("Document")
vertex.set("text", text)
vertex.set("embedding", to_java_float_array(embedding))
vertex.save()
```

### OpenAI Embeddings

```python
import numpy as np
from openai import OpenAI

# Get embedding from OpenAI (openai>=1.0 client)
client = OpenAI()
response = client.embeddings.create(
    input="Hello world",
    model="text-embedding-3-small"
)

embedding = np.array(response.data[0].embedding, dtype=np.float32)

# Store
vertex.set("embedding", to_java_float_array(embedding))
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
    vertex.set("vector", to_java_float_array(vec))
    vertex.save()
```

## Performance Tips

1. **Use float32** - Faster and smaller than float64
2. **Batch inserts** - Use chunked transactions for many vectors
3. **Never `.tolist()` a vector you are storing** - it crosses the JVM
   boundary one element at a time, so its cost grows with the dimension.
   `to_java_float_array()` crosses once and accepts NumPy directly
4. **Numpy for math** - Use NumPy for vector operations
5. **`LSM_VECTOR` (JVector) for search** - Enable similarity search

## Key Takeaways

1. **Convert with `to_java_float_array()`** - before storing, never `.tolist()`
2. **Convert back** - Use `np.array()` after retrieving
3. **Prefer float32** - Best for embeddings
4. **Use `LSM_VECTOR` (JVector)** - Enable fast similarity search
5. **Works with ML libs** - Direct integration

## See Also

- **[Vector API](../../api/vector.md)** - Vector operations
- **[Vector Tests](test-vector.md)** - Core vector functionality
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** - Real-world usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** - NumPy integration
