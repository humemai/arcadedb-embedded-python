# Vector SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_sql.py){ .md-button }

There are 29 tests covering SQL vector functions for math, aggregations, distance metrics, normalization, quantization, native INT8 encoding, sparse vectors, and `LSM_VECTOR` index creation and search.

## Overview

Tests validate:

- Vector math functions: element-wise add, multiply, scale, and scalar broadcast
- Vector aggregations (`vectorSum`, `vectorAvg`, `vectorMin`, `vectorMax`) across multiple rows
- Distance functions: cosine similarity, L2 (Euclidean), dot product, Manhattan/L1
- Vector normalization, magnitude/L2-norm aliases, clamping, and null detection
- Score-shaping helpers: `vector.scoreTransform`, `vector.multiScore`, `vector.sparsity`
- Vector quantization (`INT8`, `BINARY`) and native `INT8` encoding via `LSM_VECTOR`
- `LSM_VECTOR` / `LSM_SPARSE_VECTOR` index creation with rich metadata
- `vectorNeighbors` / `vector.neighbors` / `vector.sparseNeighbors` top-K retrieval (by vector, by key, grouped, parameterized, and over OpenCypher)

## Test Cases

### Vector Math

- **test_vector_math_functions**: Tests `vectorAdd([1,2],[3,4])`, `vectorMultiply` (element-wise), and `vectorScale(v, scalar)`.
- **test_vector_add_subtract_scalar_broadcast**: `vectorAdd` / `vectorSubtract` broadcast a scalar operand across the vector (and `vectorAdd` is commutative for scalar + vector).

### Vector Aggregations

- **test_vector_aggregations**: Tests `vectorSum`, `vectorAvg`, `vectorMin`, `vectorMax` element-wise across rows of an `ARRAY_OF_FLOATS` property.

### Distance Metrics

- **test_vector_distance_functions**: `vectorCosineSimilarity`, `vectorL2Distance`, and `vectorDotProduct` on orthogonal vectors.
- **test_vector_manhattan_distance**: `vectorManhattanDistance` / `vectorL1Distance` (and the dotted `vector.manhattanDistance` / `vector.l1Distance` aliases) compute the L1 distance.

### Normalization & Helpers

- **test_vector_normalization**: `vectorNormalize([3,4])` returns the unit vector `[0.6, 0.8]`.
- **test_vector_l2_norm_aliases**: `vectorL2Norm` / `vector.l2Norm` are aliases of `vectorMagnitude`.
- **test_vector_clamp**: `vectorClamp` / `vector.clamp` limit each element to a `[min, max]` range.
- **test_vector_has_null**: `vectorHasNull` / `vector.hasNull` detect NaN/null elements (e.g. `sqrt(-1.0)`).

### Score Shaping

- **test_vector_score_transform_modes**: `vector.scoreTransform` supports `LN` (== `LOG`) and `TANH` modes.
- **test_vector_multi_score_fusion**: `vector.multiScore` fuses a list of scores; `MAX` returns the largest.
- **test_vector_sparsity_modes**: `vector.sparsity` reports a default sparsity ratio plus `L0` and `GMEAN` modes.

### Quantization & Encoding

- **test_vector_quantization_functions**: `vectorQuantizeInt8(v)` runs and returns a non-null result.
- **test_int8_quantization_boundary_condition_sql**: INT8 quantized `LSM_VECTOR` index (Dim=16, N=10) builds and is searchable via `vectorNeighbors`.
- **test_create_index_with_quantization_int8_sql**: Creates an `INT8` quantized `LSM_VECTOR` index, inserts N=50 vectors, and verifies `vectorNeighbors` search succeeds.
- **test_create_index_with_quantization_binary_sql**: Creates a `BINARY` quantized `LSM_VECTOR` index (Dim=128) with `storeVectorsInGraph` and verifies search.
- **test_create_index_with_native_int8_encoding_sql**: Creates an `LSM_VECTOR` index on a `BINARY` property with `"quantization": "NONE", "encoding": "INT8"` and verifies the metadata (skips if the build does not expose `encoding`).
- **test_vector_neighbors_on_native_int8_storage_sql**: Verifies `vectorNeighbors` works against native INT8-encoded storage ingested as byte arrays (skips if unsupported).

### Index Creation & Metadata

- **test_sql_create_index_builds_vector_graph_immediately_by_default**: A `LSM_VECTOR` index created via SQL is queryable immediately with `vectorNeighbors`.
- **test_create_index_with_rich_metadata_sql**: `LSM_VECTOR` creation supports `dimensions`, `similarity`, `quantization`, `idPropertyName`, `storeVectorsInGraph`, `addHierarchy`, `locationCacheSize`, `graphBuildCacheSize`, and `mutationsBeforeRebuild`; verifies the resulting Java metadata.

### Neighbor Search

- **test_vector_neighbors**: `vectorNeighbors(indexName, vector, k)` on a basic `LSM_VECTOR` index.
- **test_vector_neighbors_accepts_parameterized_index_and_vector**: `vectorNeighbors(?, ?, ?)` accepts bound index name, vector, and k parameters.
- **test_vector_neighbors_by_key_sql**: `vectorNeighbors('Word[vector]', 'docA', 3)` searches from an existing record key.
- **test_vector_neighbors_by_key_opencypher**: OpenCypher exposes `CALL vector.neighbors(...)` with key-based lookup (skips if OpenCypher is unavailable).
- **test_vector_neighbors_group_by_sql**: `vector.neighbors` supports `{ groupBy, groupSize }` options.
- **test_sparse_vector_neighbors_sql**: `LSM_SPARSE_VECTOR` index plus `vector.sparseNeighbors` top-K retrieval (skips if `LSM_SPARSE_VECTOR` is unsupported).

### End-to-End Search

- **test_vector_delete_and_search_others_sql**: Inserts 100 random vectors, deletes every 10th, and verifies nearest-match search with `vectorL2Distance` and `ORDER BY`.
- **test_document_vector_search_sql**: KNN search on a `DOCUMENT` type using `vectorL2Distance` and `ORDER BY ... LIMIT`.

## Pattern

```python
# Create vector property and LSM_VECTOR index
db.command("sql", "CREATE VERTEX TYPE Movie")
db.command("sql", "CREATE PROPERTY Movie.embedding ARRAY_OF_FLOATS")
db.command(
    "sql",
    """
    CREATE INDEX ON Movie (embedding)
    LSM_VECTOR
    METADATA { "dimensions": 4, "similarity": "COSINE" }
    """,
)

# Insert vectors
with db.transaction():
    db.command("sql", "INSERT INTO Movie SET embedding = [1.0, 0.0, 0.0, 0.0]")

# Top-K search
rows = db.query(
    "sql",
    "SELECT expand(vectorNeighbors('Movie[embedding]', [1.0, 0.0, 0.0, 0.0], 2))",
).to_list()
```

## Key Functions

- **Math**: `vectorAdd()`, `vectorSubtract()`, `vectorMultiply()`, `vectorScale()`
- **Aggregation**: `vectorSum()`, `vectorAvg()`, `vectorMin()`, `vectorMax()`
- **Distance**: `vectorCosineSimilarity()`, `vectorL2Distance()`, `vectorDotProduct()`, `vectorManhattanDistance()` / `vectorL1Distance()`
- **Helpers**: `vectorNormalize()`, `vectorMagnitude()` / `vectorL2Norm()`, `vectorClamp()`, `vectorHasNull()`
- **Score shaping**: `vector.scoreTransform()`, `vector.multiScore()`, `vector.sparsity()`
- **Quantization/encoding**: `vectorQuantizeInt8()`; `LSM_VECTOR` `quantization` (`INT8`, `BINARY`, `NONE`) and `encoding` (`INT8`) metadata
- **Schema**: `ARRAY_OF_FLOATS` (dense), `ARRAY_OF_INTEGERS` + `ARRAY_OF_FLOATS` (sparse), `BINARY` (native-encoded) properties
- **Indexes**: `LSM_VECTOR`, `LSM_SPARSE_VECTOR`
- **Search**: `vectorNeighbors()`, `vector.neighbors()`, `vector.sparseNeighbors()`
```
