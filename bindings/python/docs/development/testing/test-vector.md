# Vector Search Tests (JVector / LSM)

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_vector.py){ .md-button }

The `test_vector.py` suite exercises the current Java-native JVector + LSM vector index
used by ArcadeDB (no Python hnswlib dependency). All tests run through the Python
bindings.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_vector.py){ .md-button }

## Overview

What the tests cover:

- ✅ **HNSW (JVector)/LSM index creation** via `create_vector_index`
- ✅ **Nearest-neighbor search** with `find_nearest`
- ✅ **RID filtering** using `allowed_rids`
- ✅ **Overquery factor** tuning (`overquery_factor`)
- ✅ **Distance functions** (cosine default, euclidean variants)
- ✅ **Persistence & size checks** (index files survive reopen)
- ✅ **Distance sanity checks** for orthogonal, parallel, opposite, and 45° vectors

## Test Coverage (high level)

- `test_create_vector_index` – creates HNSW (JVector)/LSM index and verifies schema listing
- `test_lsm_vector_search` – basic nearest-neighbor search
- `test_lsm_vector_search_with_filter` – `allowed_rids` filtering
- `test_lsm_vector_delete_and_search_others` – deletes vertices, ensures others are still found
- `test_lsm_vector_search_overquery` – adjusts `overquery_factor`
- `test_get_vector_index_lsm` – fetches index metadata
- `test_lsm_index_size` – asserts index file presence/size
- `test_lsm_persistence` – reopen DB and reuse the index
- Distance suites – cosine/euclidean correctness for orthogonal/parallel/opposite/high-dim vectors

## SQL Vector Functions Tests

SQL vector operations are tested separately in `test_vector_sql.py`, including vector math functions, distance calculations, aggregations, quantization (with known limitations), and SQL-based index creation and search.

## Common Pattern (mirrors `test_lsm_vector_search`)

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./test_db") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index("Doc", "embedding", dimensions=3)

    with db.transaction():
        v = db.new_vertex("Doc")
        v.set("embedding", arcadedb.to_java_float_array([1.0, 0.0, 0.0]))
        v.save()

    results = index.find_nearest([0.9, 0.1, 0.0], k=1)
    vertex, distance = results[0]
    emb = arcadedb.to_python_array(vertex.get("embedding"))
    assert abs(emb[0] - 1.0) < 0.001
```

### Filtering with `allowed_rids` (from `test_lsm_vector_search_with_filter`)
```python
allowed = [str(v.get_identity()) for v in inserted_vertices]
results = index.find_nearest([1.0, 0.0, 0.0], k=2, allowed_rids=allowed)
```

### Overquery factor (from `test_lsm_vector_search_overquery`)
```python
results = index.find_nearest(query, k=2, overquery_factor=2)
```

### Persistence check (from `test_lsm_persistence`)
```python
with arcadedb.create_database(path) as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")
    db.create_vector_index("Doc", "embedding", dimensions=3)
    with db.transaction():
        v = db.new_vertex("Doc")
        v.set("embedding", arcadedb.to_java_float_array([1.0, 0.0, 0.0]))
        v.save()

with arcadedb.open_database(path) as db:
    index = db.schema.get_vector_index("Doc", "embedding")
    assert index.get_size() == 1
```

## Key Takeaways

1. Tests exercise JVector/LSM indexes end-to-end via the Python bindings (no hnswlib path).
2. `find_nearest` returns `(vertex, score)`; cosine distance follows JVector's `(1 - cosθ)/2` convention.
3. `allowed_rids` and `overquery_factor` are covered for filtering and recall tuning.
4. Persistence and size checks verify indexes survive reopen and report counts correctly.

## See Also

- **[Vector API](../../api/vector.md)** – Full Python API reference
- **[NumPy Tests](test-numpy-support.md)** – NumPy integration
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** – End-to-end usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** – Vector-powered recommender
- **[Vector Guide](../../guide/vectors.md)** – Concepts and tuning
