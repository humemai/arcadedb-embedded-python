# Vector SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_vector_sql.py){ .md-button }

These notes mirror the Python tests in [test_vector_sql.py]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_vector_sql.py). There are 12 tests covering SQL vector functions for math, aggregations, distance metrics, normalization, and quantization.

## Overview

Tests validate:

- Vector math functions: addition, multiplication, scalar scaling
- Vector aggregations (SUM, AVG, MIN, MAX) across multiple rows
- Distance functions: cosine similarity, L2 (Euclidean), dot product
- Vector normalization to unit length
- Vector quantization (INT8) with proper scaling/unscaling
- Handling edge cases: boundary conditions, nested vectors, metadata
- Vector indexes and column type definitions in schema
- SQL query support for vector operations

## Test Cases

### Vector Math

- **vector_math_functions**: Tests SQL functions `vector_add(v1, v2)`, `vector_multiply_scalar(v, scalar)`, `vector_scale()` on float arrays; verifies expected results

### Vector Aggregations

- **vector_aggregations**: Tests SQL aggregate functions `SUM(vectors)`, `AVG(vectors)`, `MIN(vectors)`, `MAX(vectors)` on vector columns across multiple rows; validates proper element-wise aggregation

### Distance Metrics

- **vector_distance_functions**: Tests distance functions:
  - `vector_distance_cosine(v1, v2)`: cosine similarity (0 to 1)
  - `vector_distance_l2(v1, v2)`: Euclidean distance
  - `vector_distance_dot(v1, v2)`: dot product
  - Validates values for orthogonal, parallel, and arbitrary vectors

### Normalization

- **vector_normalization**: Tests `vector_normalize(v)` to unit length (magnitude 1); validates magnitude of result

### Quantization

- **vector_quantization_functions**: Tests `vector_quantize_int8(v)` and `vector_unquantize_int8(v_quantized, scale)` for compression; validates reversibility

- **int8_quantization_boundary_condition_sql**: Tests INT8 quantization at min/max boundaries (-128, 127) and zero edge cases; validates no overflow

- **quantization_with_scale_factors_sql**: Tests quantization with explicit scale factors; validates proper scaling math

### Advanced

- **nested_vector_objects_sql**: Tests queries on nested/nested vector data structures; validates accessor syntax and iteration

- **vector_metadata_parsing**: Tests SQL queries with vector metadata (dimension, type, quantization_type); validates extraction and type correctness

- **vector_indexes_sql**: Creates vector indexes on columns and validates query execution; tests index creation syntax and HNSW/IVF options if available

- **vector_column_types_in_schema**: Tests schema definition with VECTOR type, dimension constraints, quantization config; validates type enforcement in insert/update

## Pattern

```python
# Create vector columns
db.execute("sql", """
  CREATE TYPE VectorData
  PROPERTIES (
    embedding VECTOR(DIMENSION=3, QUANTIZATION_TYPE=INT8),
    name STRING
  )
""")

# Insert vectors
db.execute("sql", """
  INSERT INTO VectorData SET
    embedding = [1.0, 2.0, 3.0],
    name = 'sample'
""")

# Query with vector functions
results = db.query("sql", """
  SELECT
    vector_normalize(embedding) as normalized,
    vector_distance_cosine(embedding, [1, 0, 0]) as distance
  FROM VectorData
""")

# Quantize for storage
compressed = db.execute("sql",
  "SELECT vector_quantize_int8([1.5, 2.5, 3.5]) as q")
```

## Key Functions

- **Math**: `vector_add()`, `vector_multiply_scalar()`, `vector_scale()`
- **Aggregation**: `SUM()`, `AVG()`, `MIN()`, `MAX()`
- **Distance**: `vector_distance_cosine()`, `vector_distance_l2()`, `vector_distance_dot()`
- **Normalization**: `vector_normalize()`
- **Quantization**: `vector_quantize_int8()`, `vector_unquantize_int8()`
- **Schema**: `VECTOR(DIMENSION=n, QUANTIZATION_TYPE=INT8)`
- **Indexes**: Vector indexes (HNSW, IVF)
