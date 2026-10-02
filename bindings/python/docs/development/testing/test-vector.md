# Vector Search Tests (JVector / LSM)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector.py){ .md-button }

The test suite exercises the current Java-native JVector + LSM vector index
used by ArcadeDB (no Python hnswlib dependency). All tests run through the Python
bindings.

The array-helper tests are module-level functions; the rest are in
`TestLSMVectorIndex`.

## Overview

What the tests cover:

- ✅ **Array helpers**: `to_java_byte_array`, `to_java_float_array`, and `to_java_int_array`
- ✅ **JVector `LSM_VECTOR` index creation** through `db.create_vector_index()`, including PQ, id-property, and graph-storage options
- ✅ **Nearest-neighbor search** with `find_nearest`, `find_nearest_by_key`, and `find_nearest_approximate`
- ✅ **RID filtering** using `allowed_rids`
- ✅ **Search beam tuning** (`ef_search`)
- ✅ **Distance functions** (cosine default, euclidean variants)
- ✅ **Quantization** (`INT8`, `BINARY`, `PRODUCT`)
- ✅ **Persistence, size, and stats** (the index survives reopen)

## Test Cases

### Array helpers (module level)

- **test_to_java_byte_array_accepts_bytes_like_fast_paths**: `bytes`, `bytearray`, and NumPy `int8`/`uint8` arrays convert to Java `byte[]` with signed values (`255` becomes `-1`).
- **test_to_java_float_array_accepts_numpy_directly**: NumPy `float32` and `float64` arrays convert to `[1.0, 2.0, 3.0]`.
- **test_to_java_int_array**: lists, tuples, `range`, an empty list, and values up to `2147483647` convert unchanged.
- **test_to_java_int_array_accepts_numpy_directly**: NumPy arrays of each integer dtype convert to `[1, 2, 3]`.
- **test_to_java_int_array_round_trips_through_a_sparse_vector**: tokens stored from a NumPy array read back as `[7, 91, 4096]`, and the weights as `[0.5, 0.25, 0.125]`.

### Index creation

- **test_create_vector_index_build_graph_now_default_true**: `create_vector_index()` calls `VectorIndex.build_graph_now()` once by default.
- **test_create_vector_index_build_graph_now_can_be_disabled**: with `build_graph_now=False` it is not called.
- **test_create_vector_index**: returns a `VectorIndex`, and `schema:indexes` lists an index on `Doc` whose name starts with `Doc`.
- **test_create_vector_index_with_pq_params**: with `quantization="PRODUCT"`, the PQ arguments reach the metadata (`pqSubspaces == 4`, `pqClusters == 128`, `pqCenterGlobally` false, `pqTrainingLimit == 5000`).
- **test_create_vector_index_with_custom_id_property**: `id_property="slug"` reaches the metadata as `idPropertyName`.
- **test_create_vector_index_with_graph_storage**: `store_vectors_in_graph=True` creates an index.
- **test_graph_storage_with_quantization**: graph storage plus `BINARY` quantization creates an index whose `get_quantization()` is `BINARY`.
- **test_get_vector_index_lsm**: `SELECT name FROM schema:indexes WHERE typeName = 'Doc'` lists an index on `Doc`.
- **test_lsm_vector_metadata**: `get_metadata()` returns the index and bucket names, type, property, dimensions, similarity, id property, quantization, cache settings, and flags as given, and has no `location_cache_size` key.

### Search

- **test_lsm_vector_search**: `find_nearest(k=1)` returns one result, the vector closest to the query.
- **test_lsm_vector_search_by_key**: `find_nearest_by_key("doc-a", k=2)` returns `doc-a` first and `doc-b` second.
- **test_lsm_vector_search_by_key_missing_record_raises**: a key with no record raises `ArcadeDBError` ("No record found").
- **test_lsm_vector_search_with_filter**: with `allowed_rids`, results come only from the allowed records, in distance order, for four different allow-lists.
- **test_lsm_vector_search_uses_database_lookup_by_rid**: the two results are materialized through the `Database` RID lookup (called twice).
- **test_lsm_vector_search_uses_database_rid_conversion**: the `allowed_rids` strings are converted through the `Database` wrapper, in order.
- **test_lsm_vector_search_ef_search**: `find_nearest(k=2, ef_search=32)` returns 2 results with the closest vector first.
- **test_lsm_vector_search_rejects_invalid_ef_search**: `ef_search=0` raises `ArcadeDBError` mentioning `ef_search`.
- **test_lsm_vector_build_graph_now**: after `build_graph_now()`, a search returns the closest vector.
- **test_lsm_vector_delete_and_search_others**: of 100 random vectors, every tenth is deleted; each deleted vector is absent from its own search and each remaining one is found.
- **test_lsm_vector_search_comprehensive**: on small word embeddings, the neighbours of `king` include `queen` and `man` or `woman` but not `cat` or `dog`, and the neighbours of `cat` include `dog` but not `king`.
- **test_document_vector_search**: search on a document type returns `apple` and `banana` (not `car`) for one query and `car` and `truck` (not `apple`) for another; results are `MyDoc` records with 4-dimensional embeddings.

### Approximate search (PRODUCT quantization)

- **test_lsm_vector_search_approximate_product**: on a `PRODUCT` index (a `TypeIndex` wrapper), `find_nearest_approximate(k=1)` returns the closest vector.
- **test_lsm_vector_search_approximate_typeindex**: the same through the `TypeIndex` wrapper path; skips if the build does not return one.
- **test_lsm_vector_search_approximate_fallback**: on an index without `PRODUCT` quantization, `find_nearest_approximate()` raises `ArcadeDBError` (despite the test name, it asserts the error).
- **test_lsm_vector_search_approximate_product_requires_enough_vectors**: a `PRODUCT` index on too few vectors raises `ArcadeDBError` mentioning `pq_clusters`.
- **test_lsm_vector_search_approximate_returns_k**: with 261 vectors (5 hand-picked plus 256 fillers), `find_nearest_approximate(k=2)` returns exactly 2 results, each with a record and a distance.
- **test_lsm_vector_search_approximate_persistence**: after closing and reopening, `vectorNeighbors(...)` returns one neighbour with a record and a distance (it polls up to 50 times while the graph loads).

### Size, stats, and persistence

- **test_lsm_index_size**: `get_size()` is 0 before inserts and 2 after two inserts.
- **test_lsm_index_stats**: `get_stats()` is a non-empty dict of scalar values; `totalVectors` is 0 before inserts and 2 after.
- **test_lsm_persistence**: after a reopen, the type still has one record and `vectorNeighbors` returns one neighbour.

### Distance functions

- **test_lsm_cosine_distance_orthogonal_vectors**: orthogonal vectors are at cosine distance 1.0.
- **test_lsm_cosine_distance_parallel_vectors**: parallel vectors are at distance below 0.01.
- **test_lsm_cosine_distance_opposite_vectors**: opposite vectors are at distance 2.0.
- **test_lsm_cosine_distance_45_degree_vectors**: vectors 45° apart are at the expected cosine distance.
- **test_lsm_cosine_distance_3d_orthogonal_vectors**: orthogonal 3-D vectors are at distance 1.0.
- **test_lsm_cosine_distance_3d_parallel_and_opposite**: parallel 3-D vectors are at distance below 0.01, opposite ones at 2.0.
- **test_lsm_cosine_distance_high_dimensional**: in 128 dimensions, parallel, opposite, and near-orthogonal vectors are at about 0, 2.0, and 1.0 (each check runs only for a vector that comes back; orthogonal tolerance 0.1; skips without NumPy).
- **test_lsm_euclidean_distance**: with `EUCLIDEAN`, the reported distances are 0.0 for the origin and 25.0 for the point (3, 4) (the squared Euclidean distance from the origin), and the origin comes back first.

### Quantization

- **test_int8_quantization_boundary_condition**: an `INT8` index with 10 vectors of dimension 16 returns one result for `k=1`.
- **test_lsm_vector_quantization_int8_comprehensive**: an `INT8` index reports `get_quantization() == "INT8"`, and the top result's first component is above 0.9 at a distance below 0.2.
- **test_lsm_vector_quantization_binary_comprehensive**: a `BINARY` index reports `get_quantization() == "BINARY"` and returns one result with a full-length vector and a distance.

## SQL Vector Functions Tests

SQL vector operations are tested separately in `test_vector_sql.py`, including vector math functions, distance calculations, aggregations, quantization (the INT8 SQL test does not check the returned vector's values), and SQL-based index creation and search.

## Common Patterns

### Create JVector (LSM-backed) index

```python
with arcadedb.create_database("./test_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

    db.command(
        "sql",
        '''
        CREATE INDEX ON Doc (embedding)
        LSM_VECTOR
        METADATA {
            "dimensions": 384,
            "similarity": "COSINE",
            "maxConnections": 32,
            "beamWidth": 100
        }
        ''',
    )
```

### Search with filters and ef_search

```python
with arcadedb.create_database("./test_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.docId INTEGER")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    db.command(
        "sql",
        'CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {"dimensions": 3}',
    )

    # Insert test vertices with embeddings
    with db.transaction():
        doc1 = db.new_vertex("Doc")
        doc1.set("docId", 1)
        doc1.set("embedding", arcadedb.to_java_float_array([1.0, 0.0, 0.0]))
        doc1.save()
        doc2 = db.new_vertex("Doc")
        doc2.set("docId", 2)
        doc2.set("embedding", arcadedb.to_java_float_array([0.0, 1.0, 0.0]))
        doc2.save()

    # Search with filters (the WHERE goes on an outer query over the expanded
    # neighbours; on the expand() query itself it matches nothing)
    query = [1.0, 0.0, 0.0]
    allowed_rids_sql = f"['{doc1.get_rid()}', '{doc2.get_rid()}']"
    query_literal = "[" + ", ".join(str(float(v)) for v in query) + "]"
    results = db.query(
        "sql",
        (
            "SELECT FROM (SELECT expand(vectorNeighbors('Doc[embedding]', "
            f"{query_literal}, 2, 100))) WHERE @rid IN {allowed_rids_sql}"
        ),
    ).to_list()
```

### Chunked insert vectors (preferred)

```python
import numpy as np

with arcadedb.create_database("./test_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.docId INTEGER")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

    # Prefer chunked transactions for embedded (avoids batch_context overhead)
    vectors = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    chunk_size = 100
    for start in range(0, len(vectors), chunk_size):
        with db.transaction():
            for idx, vec in enumerate(vectors[start : start + chunk_size]):
                doc = db.new_vertex("Doc")
                doc.set("docId", start + idx)
                # One JVM crossing per vector; a Python list crosses element by element
                doc.set("embedding", arcadedb.to_java_float_array(vec))
                doc.save()
```

## Key Takeaways

1. JVector is fully Java-native and LSM-backed; no legacy hnswlib path remains.
2. `max_connections` and `beam_width` map to JVector graph degree and search beam; tune
   per workload.
3. Prefer chunked `db.transaction()` inserts for embedded workloads rather than a
   separate batching abstraction.

## See Also

- **[Vector API](../../api/vector.md)** – Full Python API reference
- **[NumPy Tests](test-numpy-support.md)** – NumPy integration
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** – End-to-end usage
- **[Example 06: Movie Recommendations](../../examples/06_vector_search_recommendations.md)** – Vector-powered recommender
- **[Vector Guide](../../guide/vectors.md)** – Concepts and tuning
