# Example 12: Vector Search

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/12_vector_search.py){ .md-button }

This example benchmarks search performance over the vector indexes produced by
Example 11.

## Overview

Example 12 is the search-only vector benchmark.

- It reuses the backend output produced by Example 11.
- It loads query ids and full top-k ground truth from the benchmark dataset.
- It sweeps explicit `ef_search` values across the exact-search backends.
- It reports recall and latency for each backend.

## Supported Backends

- `arcadedb_sql`
- `faiss`
- `lancedb`
- `bruteforce`
- `pgvector`
- `qdrant`
- `milvus`

## Run

From `bindings/python/examples`:

```bash
python 12_vector_search.py \
  --backend arcadedb_sql \
  --dataset stackoverflow-tiny \
  --db-path ./my_test_databases/stackoverflow_tiny_vector_index_arcadedb_sql \
  --k 50 \
  --query-limit 1000 \
  --ef-search-values 50,75,100,150,200 \
  --mem-limit 4g
```

## Shared Evaluation Logic

The example reads the evaluation set with two helpers.

### Query IDs

```python
qids.append(int(obj["query_id"]))
```

### Ground Truth

```python
ground_truth[qid] = [int(entry["doc_id"]) for entry in obj.get("topk", [])]
```

### ef_search Sweep

The benchmark now sweeps explicit `ef_search` values instead of normalizing an
intermediate factor.

## Exact Search Operations By Backend

### ArcadeDB

The ArcadeDB path has two execution branches.

#### SQL `vectorNeighbors()` branch

When the loaded index handle is a metadata dict, the benchmark issues:

```sql
SELECT vectorNeighbors('{index_name}', [q1, q2, ...], {k}) as res
```

where `[q1, q2, ...]` is the literal query vector.

#### Embedded index API branch

If the loaded handle is an embedded index object:

- product quantization uses:

```python
index.find_nearest_approximate(qvec, k=k)
```

- non-product paths use:

```python
index.find_nearest(qvec, k=k, ef_search=ef_search)
```

ArcadeDB exact search now exposes `ef_search` directly. The current PQ approximate API
still only exposes `k`, so the `ef_search` sweep affects ArcadeDB's exact path but not
its PQ approximate path.

The CLI exposes this sweep as `--ef-search-values`.

### FAISS

FAISS normalizes the query vector and then runs:

```python
_dist, ids = index.search(qvec, int(k))
```

Before searching, the benchmark sets:

```python
hnsw.efSearch = int(ef_search)
```

when the HNSW structure is exposed.

### LanceDB

The LanceDB search call starts from:

```python
search = table.search(queries[q_idx].tolist()).metric("cosine").limit(int(k))
```

It then conditionally applies:

```python
search = search.ef(int(ef_search))
```

or:

```python
search = search.ef_search(int(ef_search))
```

and, for IVF-backed modes, possibly:

```python
search = search.nprobes(int(nprobes))
```

The search is executed with:

```python
rows = search.to_list()
```

### Bruteforce

The exact-search baseline normalizes all corpus and query vectors and computes cosine
similarity directly:

```python
scores = corpus_vectors_normalized @ queries_normalized[q_idx]
```

It then ranks results with either:

```python
ranked_idx = np.argsort(scores)[::-1][:topk]
```

or the partial-top-k path:

```python
candidate_idx = np.argpartition(scores, -topk)[-topk:]
ranked_idx = candidate_idx[np.argsort(scores[candidate_idx])[::-1]]
```

### pgvector

The PostgreSQL vector path executes two SQL statements per query.

#### Search Parameter Setup

```sql
SET LOCAL hnsw.ef_search = {ef_search}
```

#### Search Query

```sql
SELECT id FROM vectordata ORDER BY vector <=> %s::vector LIMIT %s
```

The query vector is serialized through `vector_to_pg_literal()`.

### Qdrant

Qdrant uses `query_points()` with explicit HNSW search parameters:

```python
client.query_points(
    collection_name=collection_name,
    query=queries[q_idx].tolist(),
    limit=int(k),
    search_params=models.SearchParams(hnsw_ef=int(ef_search)),
    with_payload=False,
    with_vectors=False,
)
```

### Milvus

Milvus searches with cosine distance and an HNSW `ef` parameter:

```python
search_params = {
    "metric_type": "COSINE",
    "params": {"ef": int(ef_search)},
}
```

and then:

```python
collection.search(
    data=[queries[q_idx].tolist()],
    anns_field="vector",
    param=search_params,
    limit=int(k),
    output_fields=["id"],
)
```

The source retries transient Milvus search errors before failing the run.

## Result Format

Every backend returns the same result fields:

- `queries`
- `recall_mean`
- `latency_ms_mean`
- `latency_ms_p95`
- `recall_count`

Some backends also report normalized runtime knobs such as:

- `effective_ef_search`
- `effective_nprobes`

## Notes

- Example 12 now sweeps explicit `ef_search` values for the backends that expose them.
- Client-server backends report combined client and server RSS.
- The `bruteforce` backend exists to provide an exact-search reference path inside the benchmark harness.
