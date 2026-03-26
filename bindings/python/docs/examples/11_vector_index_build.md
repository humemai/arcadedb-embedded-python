# Example 11: Vector Index Build

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/11_vector_index_build.py){ .md-button }

This example benchmarks vector ingest and index-build time across several vector
backends.

## Overview

Example 11 is the build-only vector benchmark.

- It resolves either MSMARCO or Stack Overflow vector shards.
- It ingests vectors into the chosen backend.
- It builds an HNSW-style index, or the nearest equivalent supported by that backend.
- It reports ingest time, index-build time, disk usage, and peak RSS.

## Supported Backends

- `arcadedb_sql`
- `pgvector`
- `qdrant`
- `milvus`
- `faiss`
- `lancedb`

## Datasets

- `MSMARCO-*`
- `stackoverflow-*`

## Run

From `bindings/python/examples`:

```bash
python 11_vector_index_build.py \
  --backend arcadedb_sql \
  --dataset stackoverflow-tiny \
  --max-connections 16 \
  --beam-width 100 \
  --batch-size 10000 \
  --mem-limit 4g
```

## Shared Build Parameters

The example normalizes build settings around two knobs:

- `max_connections`: HNSW `m`-style connectivity
- `beam_width`: HNSW `ef_construction`-style build breadth

The exact backend call differs, but these two values are threaded through the build in
every engine that supports them.

## Exact Build Operations By Backend

### ArcadeDB

The ArcadeDB path explicitly creates schema and ingests vectors with SQL.

#### Schema DDL

```sql
CREATE VERTEX TYPE VectorData
CREATE PROPERTY VectorData.id INTEGER
CREATE PROPERTY VectorData.vector ARRAY_OF_FLOATS
```

#### ArcadeDB Ingest Statement

```sql
INSERT INTO VectorData SET id = ?, vector = ?
```

#### ArcadeDB Index Build Call

```sql
CREATE INDEX ON VectorData (vector)
LSM_VECTOR
METADATA {
  "dimensions": <dim>,
  "similarity": "COSINE",
  "maxConnections": <max_connections>,
  "beamWidth": <beam_width>,
  "quantization": <quant>,
  "storeVectorsInGraph": <store_vectors_in_graph>,
  "addHierarchy": <add_hierarchy>
}
```

This is the exact Example 11 build path for ArcadeDB. The Python object helper exists,
but the benchmark and the recommended docs path use SQL.

### FAISS

FAISS uses `IndexHNSWFlat` wrapped in `IndexIDMap2`.

#### Index Construction

```python
index_hnsw = faiss.IndexHNSWFlat(
    int(dim),
    int(max_connections),
    faiss.METRIC_INNER_PRODUCT,
)
index_hnsw.hnsw.efConstruction = int(beam_width)
index = faiss.IndexIDMap2(index_hnsw)
```

#### FAISS Ingest Call

```python
faiss.normalize_L2(vectors)
index.add_with_ids(vectors, ids)
```

### LanceDB

LanceDB first creates a table of `{id, vector}` rows, then tries HNSW-like index modes.

#### Table Creation

The first batch creates the table with:

```python
table = db.create_table(table_name, rows, mode="overwrite")
```

Later batches append via:

```python
table.add(rows)
```

#### Index Creation Attempts

The exact code tries these index types in order:

1. `HNSW`
2. `IVF_HNSW_SQ` with `num_partitions=1`

The build call is:

```python
table.create_index(
    index_type=index_type,
    metric="cosine",
    vector_column_name="vector",
    m=int(max_connections),
    ef_construction=int(beam_width),
    **extra_kwargs,
)
```

### pgvector

The PostgreSQL vector path uses the `vector` extension and an HNSW index.

#### Schema Setup

```sql
CREATE EXTENSION IF NOT EXISTS vector
DROP TABLE IF EXISTS vectordata
CREATE TABLE vectordata(id INTEGER PRIMARY KEY, vector vector({dim}))
```

#### Ingest Statement

```sql
INSERT INTO vectordata(id, vector) VALUES (%s, %s::vector)
```

#### Index Build Statement

```sql
CREATE INDEX vectordata_vector_hnsw ON vectordata USING hnsw (vector vector_cosine_ops) WITH (m = {m_val}, ef_construction = {ef_val})
```

The build finishes with:

```sql
ANALYZE vectordata
```

### Qdrant

Qdrant recreates the collection with cosine distance and HNSW config.

#### Collection Definition

```python
client.recreate_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(
    size=int(dim),
    distance=models.Distance.COSINE,
    ),
    hnsw_config=models.HnswConfigDiff(
    m=int(max_connections),
    ef_construct=int(beam_width),
    ),
)
```

#### Ingest Objects

```python
models.PointStruct(id=int(idx), vector=vec.tolist())
```

These points are sent in upsert batches.

### Milvus

Milvus creates an explicit collection schema before building an HNSW index.

#### Collection Schema

```python
schema = CollectionSchema(
    fields=[
    FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
        auto_id=False,
    ),
    FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=dim,
    ),
    ],
    description="Vector benchmark collection",
)
```

#### Milvus Index Build Call

```python
index_params = {
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {
    "M": int(max_connections),
    "efConstruction": int(beam_width),
    },
}
collection.create_index(field_name="vector", index_params=index_params)
```

#### Milvus Ingest Call

```python
collection.insert([ids, vectors])
collection.flush()
```

## Notes

- Client-server backends report combined client and server RSS.
- ArcadeDB exposes extra build knobs such as `quantization`, `store_vectors_in_graph`,
  and `add_hierarchy`.
- LanceDB may fall back from `HNSW` to `IVF_HNSW_SQ` depending on what the installed
  version supports.
