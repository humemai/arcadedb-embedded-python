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
- ✅ **Batch inserts** through `BatchContext`

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
- `test_lsm_vector_search_comprehensive` – end-to-end search path

## SQL Vector Functions Tests

SQL vector operations are tested separately in `test_vector_sql.py`, including vector math functions, distance calculations, aggregations, quantization (with known limitations), and SQL-based index creation and search.

## Common Patterns

### Create JVector (LSM-backed) index
```python
with arcadedb.create_database("./test_db") as db:
    # Schema operations are auto-transactional
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        "Doc",
        "embedding",
        dimensions=384,
        distance_function="cosine",   # default
        max_connections=32,            # graph degree
        beam_width=256                 # search/construction beam
    )
```

### Search with filters and overquery factor
```python
with arcadedb.create_database("./test_db") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        "Doc",
        "embedding",
        dimensions=3,
    )

    # Insert test vertices with embeddings
    with db.transaction():
        doc1 = db.new_vertex("Doc", docId=1, embedding=[1.0, 0.0, 0.0])
        doc1.save()
        doc2 = db.new_vertex("Doc", docId=2, embedding=[0.0, 1.0, 0.0])
        doc2.save()

    # Search with filters
    query = [1.0, 0.0, 0.0]
    results = index.find_nearest(
        query,
        k=2,
        allowed_rids=[doc1.get_rid(), doc2.get_rid()],
        overquery_factor=16,
    )
```

### Batch insert vectors
```python
with arcadedb.create_database("./test_db") as db:
    # Schema operations are auto-transactional
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "docId", "INTEGER")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    # Batch insert (auto-transactional)
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    with db.batch_context(batch_size=1000, parallel=4) as batch:
        for i, vec in enumerate(vectors):
            batch.create_vertex("Doc", docId=i, embedding=vec)
```

## Key Takeaways

1. JVector is fully Java-native and LSM-backed; no legacy hnswlib path remains.
2. Use `allowed_rids` for pre-filtered searches and `overquery_factor` for recall/speed trade-offs.
3. `max_connections` and `beam_width` map to JVector graph degree and search beam; tune per workload.
4. All tests run through the Python bindings to ensure parity with the Java engine.

## See Also

- **[Vector API](../../api/vector.md)** – Full Python API reference
- **[NumPy Tests](test-numpy-support.md)** – NumPy integration
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** – End-to-end usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** – Vector-powered recommender
- **[Vector Guide](../../guide/vectors.md)** – Concepts and tuning
