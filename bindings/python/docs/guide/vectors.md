# Vector Search Guide

Bring your own embeddings (OpenAI, HF, local models). This guide focuses on how the
Python bindings build and query vector indexes (JVector) in embedded mode.

## Quick Start (Embedded, Minimal)

```bash
pip install arcadedb-embedded numpy
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
        max_connections=32,          # Corresponds to M in HNSW
        beam_width=256               # Corresponds to efConstruction in HNSW
        # quantization="PRODUCT",   # enable PQ
        # pq_subspaces=2,            # M
        # pq_clusters=256,           # K
        # pq_center_globally=True,
        # pq_training_limit=128_000,
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
- `create_vector_index(vertex_type, vector_property, dimensions, distance_function="cosine", max_connections=32, beam_width=256, quantization=None, store_vectors_in_graph=False, add_hierarchy=None, pq_subspaces=None, pq_clusters=None, pq_center_globally=None, pq_training_limit=None)`
- `find_nearest(query_vector, k=10, overquery_factor=16, allowed_rids=None)`
  - `overquery_factor` multiplies `k` during search to improve recall.
  - `allowed_rids` filters candidates server-side (useful for metadata-prefilter).

## Distance Functions (scoring behavior)

- `cosine` (default): returns distance in [0,1]; lower is better.
- `euclidean`: returns similarity score $1 / (1 + d^2)$; higher is better.
- `inner_product`: returns negative dot product; lower is better.

## Tuning Knobs

- `dimensions`: must match your embedding length.
- `max_connections` (HNSW M): higher → better recall, more memory/slow build.
- `beam_width` (ef/efConstruction): higher → better recall, slower search/build.
- `overquery_factor` (runtime only): higher → better recall, slower search.
    - Note: JVector doesn’t expose HNSW’s `efSearch`; `overquery_factor` is the Python-side
        oversampling knob we added to compensate—set it higher when you need recall.

Suggested presets from tests/examples:

- Fast/dev: `max_connections=16`, `beam_width=128`, `overquery_factor=8`.
- Balanced default: `max_connections=32`, `beam_width=256`, `overquery_factor=16`.
- High recall: `max_connections=64`, `beam_width=512`, `overquery_factor=32`.

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

## Quantization (Experimental)

- `quantization` accepts `"INT8"`, `"BINARY"`, or `"PRODUCT"` (PQ).
- PQ tunables (require `quantization="PRODUCT"`): `pq_subspaces` (M), `pq_clusters` (K), `pq_center_globally`, `pq_training_limit`.
- INT8/BINARY have shown instability on larger inserts; PQ is the recommended quantization path for recall/latency trade-offs.

## SQL Helpers (Optional)

- Prefer Schema API for embedded: `db.schema.create_index("Doc", ["embedding"], index_type="LSM_VECTOR")`
- SQL is also available (useful for remote servers): `CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {"dimensions": 128, "distanceFunction": "COSINE"}`
- Search via SQL:
    - `SELECT vectorNeighbors('Doc[embedding]', [0.1,0.2], 5) AS res`
    - Or with type/property signature: `SELECT vectorNeighbors('Doc', 'embedding', [0.1,0.2], 5)`
- Math/distance helpers: `vectorCosineSimilarity`, `vectorL2Distance`, `vectorDotProduct`, `vectorNormalize`, `vectorAdd`, `vectorSum`, etc.
- Quantization via SQL: `METADATA {"quantization": "INT8"}` works for tiny datasets; larger inserts still unstable (see tests).

## Examples & References

- **[Example 03: Vector Search – Semantic Similarity](../examples/03_vector_search.md)**
- **[Example 06: Vector Search Movie Recommendations](../examples/06_vector_search_recommendations.md)**
- **[Vector API Reference](../api/vector.md)**
