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
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.text STRING")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

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
            db.command(
                "sql",
                "INSERT INTO Doc SET text = ?, embedding = ?",
                t,
                to_java_float_array(embedding),
            )

    rows = db.query(
        "sql",
        "SELECT vectorNeighbors('Doc[embedding]', [0.9, 0.1, 0.0], 2) as res",
    ).to_list()
    for hit in rows[0].get("res", []):
        record = hit.get("record")
        if record is not None:
            print(record.get("text"), hit.get("distance"))
```

## API Essentials

Preferred split:

- Use Python object API for vector index creation and configuration.
- Prefer SQL or Cypher for vector retrieval/search, because search composes naturally
  with filters, projections, and graph traversal.
- Treat `find_nearest()` and `find_nearest_by_key()` as convenience wrappers for
  simple embedded-mode workflows.

- Vector property type must be `ARRAY_OF_FLOATS`.
- `create_vector_index(vertex_type, vector_property, dimensions,
  id_property=None, distance_function="cosine", max_connections=16,
  beam_width=100, quantization="INT8",
  location_cache_size=None, graph_build_cache_size=None, mutations_before_rebuild=None,
  store_vectors_in_graph=False, add_hierarchy=True, pq_subspaces=None, pq_clusters=None,
  pq_center_globally=None, pq_training_limit=None, build_graph_now=True)`
    - `build_graph_now=True` eagerly prepares the graph at creation time.
    - Set `build_graph_now=False` to defer graph preparation until first query.
- `build_graph_now()` on the returned index can be called later to force
  rebuild/preparation, e.g. after bulk vector inserts or removals/deletes.
- `find_nearest(query_vector, k=10, ef_search=None, allowed_rids=None)`
    - `ef_search` optionally overrides the exact-search beam width.
    - Leave it as `None` to use ArcadeDB's default/adaptive behavior.
    - `allowed_rids` filters candidates server-side (useful for metadata-prefilter).
- `find_nearest_by_key(key, k=10, ef_search=None, allowed_rids=None)`
    - Looks up the source vector by the index `id_property` and then runs the same
      Python search path as `find_nearest()`.
- `get_metadata()` returns stable index metadata such as dimensions, similarity
  function, configured `id_property`, quantization, and cache/build settings.

## Distance Functions (scoring behavior)

- `cosine` (default): returns cosine distance in [0,2]; lower is better.
- `euclidean`: returns similarity score $1 / (1 + d^2)$; higher is better.
- `inner_product`: returns negative dot product; lower is better.

Important:

- `find_nearest()` / vector-index search exposes cosine as distance: $1 - \cos(\theta)$.
- SQL `vectorCosineSimilarity(...)` exposes raw cosine similarity, so its values follow
  cosine similarity semantics rather than vector-index distance semantics.

## Tuning Knobs

- `dimensions`: must match your embedding length.
- `max_connections` (HNSW M): higher → better recall, more memory/slow build (default: 16).
- `beam_width` (ef/efConstruction): higher → better recall, slower search/build (default: 100).
- `ef_search` (runtime, exact search only): higher → better recall, slower search.
    - `None` uses the Java engine's default/adaptive behavior.
    - PQ approximate search currently does not expose per-query `ef_search`; it only
      accepts `k` and optional RID filters.

Suggested presets from tests/examples (k=10):

- Min: `max_connections=12`, `beam_width=64`, `ef_search=32`.
- Normal (default/adaptive): `max_connections=16`, `beam_width=100`, `ef_search=None`.
- Max: `max_connections=32`, `beam_width=200`, `ef_search=200`.

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

If you reduce vector dimensions (e.g., 384-dim), you can substantially lower heap
requirements.

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
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.text STRING")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

    index = db.create_vector_index(
        vertex_type="Doc",
        vector_property="embedding",
        dimensions=len(vec),
        distance_function="cosine",
    )

    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO Doc SET text = ?, embedding = ?",
            doc_text,
            to_java_float_array(vec),
        )

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

## Preferred Search Surface: SQL / Cypher

For new code, prefer query APIs for search.

### SQL filtered vector search with score shaping

```python
qvec_literal = "[" + ", ".join(str(float(x)) for x in query_vec) + "]"

rows = db.query(
  "sql",
  (
    "SELECT title, category, distance, (1 - distance) AS score "
    "FROM (SELECT expand(`vector.neighbors`('Article[embedding]', "
    f"{qvec_literal}, 50))) WHERE category = ? ORDER BY distance LIMIT 5"
  ),
  "category_42",
).to_list()
```

### SQL self-exclusion

```python
rows = db.query(
  "sql",
  (
    "SELECT title, distance, (1 - distance) AS score "
    "FROM (SELECT expand(`vector.neighbors`('Movie[embedding]', "
    f"{qvec_literal}, 20))) WHERE title <> ? ORDER BY distance LIMIT 10"
  ),
  movie_title,
).to_list()
```

### Cypher search with score shaping

```python
rows = db.query(
  "opencypher",
  (
    "CALL vector.neighbors('Doc[embedding]', $vec, $k) "
    "YIELD name, distance RETURN name, (1 - distance) AS score ORDER BY score DESC"
  ),
  {"vec": query_vec, "k": 5},
).to_list()
```

## Search from an Existing Record

```python
with arcadedb.create_database("./vector_demo") as db:
  db.command("sql", "CREATE VERTEX TYPE Doc")
  db.command("sql", "CREATE PROPERTY Doc.slug STRING")
  db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

  index = db.create_vector_index(
    vertex_type="Doc",
    vector_property="embedding",
    dimensions=3,
    id_property="slug",
  )

  with db.transaction():
    db.command(
      "sql",
      "INSERT INTO Doc SET slug = ?, embedding = ?",
      "doc-a",
      to_java_float_array([1.0, 0.0, 0.0]),
    )
    db.command(
      "sql",
      "INSERT INTO Doc SET slug = ?, embedding = ?",
      "doc-b",
      to_java_float_array([0.9, 0.1, 0.0]),
    )

  neighbors = index.find_nearest_by_key("doc-a", k=2)
  metadata = index.get_metadata()

  print(metadata["dimensions"], metadata["id_property"])
  for record, distance in neighbors:
    print(record.get("slug"), distance)
```

Use this helper when you want a small embedded-mode shortcut. For richer filtering,
projection, self-exclusion, or score shaping, prefer SQL/Cypher queries.

## Quantization

- `quantization` accepts `"INT8"`, `"BINARY"`, `"PRODUCT"` (PQ), or `None` (full precision).
- Default and recommended setting is `"INT8"`.
- Use `quantization=None` only when you explicitly need full-precision vectors and can
  accept higher memory usage.
- PQ tunables (require `quantization="PRODUCT"`): `pq_subspaces` (M), `pq_clusters` (K),
  `pq_center_globally`, `pq_training_limit`.
- In current ArcadeDB engine builds, PRODUCT/PQ also needs enough indexed vectors per
  bucket for training. For very small corpora, set `pq_clusters` to a value no larger
  than the number of indexed vectors in that bucket, or use `INT8`, `BINARY`, or `None`.
- `"PRODUCT"`/PQ is currently not recommended for production workloads in these bindings.

## SQL Helpers

- Preferred path for embedded and server modes: `CREATE INDEX ON Doc (embedding)
  LSM_VECTOR METADATA {"dimensions": 128, "distanceFunction": "COSINE"}`
- Search via SQL:
    - `SELECT vectorNeighbors('Doc[embedding]', [0.1,0.2], 5) AS res`
- Math/distance helpers: `vectorCosineSimilarity`, `vectorL2Distance`,
  `vectorDotProduct`, `vectorNormalize`, `vectorAdd`, `vectorSum`, etc.
- Quantization via SQL: `METADATA {"quantization": "INT8"}` is the recommended path for
  embedded usage.

## Examples & References

- **[Example 03: Vector Search – Semantic Similarity](../examples/03_vector_search.md)**
- **[Example 06: Vector Search Movie Recommendations](../examples/06_vector_search_recommendations.md)**
- **[Vector API Reference](../api/vector.md)**
