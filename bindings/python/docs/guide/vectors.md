# Vector Search Guide

Bring your own embeddings (OpenAI, HF, local models). This guide focuses on how the
Python bindings build and query vector indexes (JVector) in embedded mode.

## Quick Start (Embedded, Minimal)

```bash
uv pip install arcadedb-embedded numpy
```

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array

texts = ["python database", "graph queries", "vector search"]

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "text", "STRING")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=3,                # must match your embedding size
        distance_function="cosine",  # default: cosine
        max_connections=16,          # Corresponds to M in HNSW (default)
        beam_width=100               # Corresponds to efConstruction in HNSW (default)
    )

    with db.transaction():
        for i, t in enumerate(texts):
            embedding = [float(i == j) for j in range(3)]  # toy vectors
            v = db.new_vertex("Doc")
            v.set("text", t)
            v.set("embedding", to_java_float_array(embedding))
            v.save()

    results = index.find_nearest([0.9, 0.1, 0.0], k=2)
    for vertex, score in results:
        print(vertex.get("text"), score)
```

## API Essentials

- Vector property type must be `ARRAY_OF_FLOATS`.
- `create_vector_index(vertex_type, vector_property, dimensions, distance_function="cosine", max_connections=16, beam_width=100, quantization="INT8", location_cache_size=None, graph_build_cache_size=None, mutations_before_rebuild=None, store_vectors_in_graph=False, add_hierarchy=True, pq_subspaces=None, pq_clusters=None, pq_center_globally=None, pq_training_limit=None)`
- `find_nearest(query_vector, k=10, overquery_factor=4, allowed_rids=None)`
    - `overquery_factor` multiplies `k` during search to improve recall.
    - `allowed_rids` filters candidates server-side (useful for metadata-prefilter).

## Distance Functions (scoring behavior)

- `cosine` (default): returns distance in [0,1]; lower is better.
- `euclidean`: returns similarity score $1 / (1 + d^2)$; higher is better.
- `inner_product`: returns negative dot product; lower is better.

## Tuning Knobs

- `dimensions`: must match your embedding length.
- `max_connections` (HNSW M): higher → better recall, more memory/slow build (default: 16).
- `beam_width` (ef/efConstruction): higher → better recall, slower search/build (default: 100).
- `overquery_factor` (runtime only): higher → better recall, slower search.
    - Note: JVector doesn’t expose HNSW’s `efSearch`; `overquery_factor` is the Python-side
        oversampling knob we added to compensate—set it higher when you need recall.

Suggested presets from tests/examples (k=10):

- Min: `max_connections=12`, `beam_width=64`, `overquery_factor=2`.
- Normal (default): `max_connections=16`, `beam_width=100`, `overquery_factor=4`.
- Max: `max_connections=32`, `beam_width=200`, `overquery_factor=8`.

## Memory & Heap Requirements (1024-dim vectors)

Vector index build is the most memory-hungry step. For 1024-dimensional vectors:

**Build (heap):**

- 1M vectors: at least 4G
- 2M vectors: at least 8G
- 4M vectors: at least 16G
- 8M vectors: at least 32G

**Search (heap):**

- 1M vectors: 1G works, at least 1G recommended
- 2M vectors: 1G works, at least 2G recommended
- 4M vectors: 1G works, at least 2G recommended
- 8M vectors: 1G OOM, 2G works, at least 4G recommended

If you reduce vector dimensions (e.g., 384-dim), you can substantially lower heap requirements.

## Generating Embeddings (example)

Use any model you like; the bindings only need a Python list/NumPy array of floats. A
typical text workflow uses a Transformer-based embedding model, e.g.,
sentence-transformers with normalized outputs for cosine:

```python
from sentence_transformers import SentenceTransformer
from arcadedb_embedded import to_java_float_array

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dims

doc_text = "retrieval augmented generation"
vec = model.encode(doc_text, normalize_embeddings=True)

with arcadedb.create_database("./vector_demo") as db:
    db.schema.create_vertex_type("Doc")
    db.schema.create_property("Doc", "text", "STRING")
    db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=len(vec),
        distance_function="cosine",
    )

    with db.transaction():
        v = db.new_vertex("Doc")
        v.set("text", doc_text)
        v.set("embedding", to_java_float_array(vec))
        v.save()

    hits = index.find_nearest(vec, k=1)
```

Notes:

- `to_java_float_array` accepts NumPy arrays directly.
- For cosine, pass `normalize_embeddings=True` (as above) to your model.
- For euclidean or inner_product, skip normalization if magnitude should matter.

## Filtering by RID (prefilter)

```python
rids = [row.get_rid() for row in db.query("sql", "SELECT @rid FROM Doc WHERE topic = 'ai'")]
results = index.find_nearest(query_vec, k=5, allowed_rids=rids)
```

## Quantization

- `quantization` accepts `"INT8"`, `"BINARY"`, `"PRODUCT"` (PQ), or `None` (full precision).
- Default and recommended setting is `"INT8"`.
- Use `quantization=None` only when you explicitly need full-precision vectors and can accept higher memory usage.
- PQ tunables (require `quantization="PRODUCT"`): `pq_subspaces` (M), `pq_clusters` (K), `pq_center_globally`, `pq_training_limit`.
- `"PRODUCT"`/PQ is currently not recommended for production workloads in these bindings.

## SQL Helpers (Optional)

- Prefer Schema API for embedded: `db.schema.create_index("Doc", ["embedding"], index_type="LSM_VECTOR")`
- SQL is also available (useful for remote servers): `CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {"dimensions": 128, "distanceFunction": "COSINE"}`
- Search via SQL:
    - `SELECT vectorNeighbors('Doc[embedding]', [0.1,0.2], 5) AS res`
    - Or with type/property signature: `SELECT vectorNeighbors('Doc', 'embedding', [0.1,0.2], 5)`
- Math/distance helpers: `vectorCosineSimilarity`, `vectorL2Distance`, `vectorDotProduct`, `vectorNormalize`, `vectorAdd`, `vectorSum`, etc.
- Quantization via SQL: `METADATA {"quantization": "INT8"}` is the recommended path for embedded usage.

## Examples & References

- **[Example 03: Vector Search – Semantic Similarity](../examples/03_vector_search.md)**
- **[Example 06: Vector Search Movie Recommendations](../examples/06_vector_search_recommendations.md)**
- **[Vector API Reference](../api/vector.md)**
