# Vector Search Guide

Bring your own embeddings (OpenAI, HF, local models). This guide focuses on the
recommended SQL-first way to build and query vector indexes (JVector) in embedded mode.

## Quick Start (Embedded, Minimal)

```bash
pip install arcadedb-embedded numpy
```

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import to_java_float_array

texts = ["python database", "graph queries", "vector search"]

with arcadedb.create_database("./vector_demo") as db:
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.text STRING")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")

    db.command(
        "sql",
        """
        CREATE INDEX ON Doc (embedding)
        LSM_VECTOR
        METADATA {
        "dimensions": 3,
        "similarity": "COSINE"
        }
        """,
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

- Use SQL `CREATE INDEX ... LSM_VECTOR METADATA {...}` for vector index creation.
- Prefer SQL or Cypher for vector retrieval/search, because search composes naturally
  with filters, projections, and graph traversal.
- Keep the secondary Python helper APIs in mind only for manual or maintenance cases;
  they are not the recommended application-facing workflow.

- Vector property type is usually `ARRAY_OF_FLOATS`.
- Use `BINARY` only when you are storing pre-quantized INT8 bytes with
  `encoding="INT8"`.
- `CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {...}` is the preferred creation
  path.
    - SQL builds the vector graph immediately by default.
    - Add `"buildGraphNow": false` only if you intentionally want lazy preparation.
- Use `vectorNeighbors(..., k, ef_search)` as the default SQL nearest-neighbor surface.
- `get_metadata()` remains available on the loaded vector index when you need to inspect
  index configuration from Python.

## Distance Functions (scoring behavior)

- `cosine` (default): returns cosine distance in [0,2]; lower is better.
- `euclidean`: returns similarity score $1 / (1 + d^2)$; higher is better.
- `inner_product`: returns negative dot product; lower is better.

Important:

- Vector-index search exposes cosine as distance: $1 - \cos(\theta)$.
- SQL `vectorCosineSimilarity(...)` exposes raw cosine similarity, so its values follow
  cosine similarity semantics rather than vector-index distance semantics.

## Tuning Knobs

- `dimensions`: must match your embedding length.
- `max_connections` (Vamana per-layer degree; use 2*M to match an hnswlib M): higher → better recall, more memory/slower build (default: 32).
- `beam_width` (ef/efConstruction): higher → better recall, slower search/build (default: 100).
- `ef_search` (runtime, exact search only): higher → better recall, slower search.
    - Leave it unset to use the Java engine's default/adaptive behavior.

Suggested presets from tests/examples (k=10):

- Min: `max_connections=12`, `beam_width=64`, `ef_search=32`.
- Normal (default/adaptive): `max_connections=32`, `beam_width=100`, `ef_search=None`.
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

{% raw %}

```python
import json
import arcadedb_embedded as arcadedb
from sentence_transformers import SentenceTransformer
from arcadedb_embedded import to_java_float_array

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dims

doc_text = "retrieval augmented generation"
vec = model.encode(doc_text, normalize_embeddings=True)

with arcadedb.create_database("./vector_demo") as db:
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.text STRING")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    metadata_json = json.dumps({"dimensions": len(vec), "similarity": "COSINE"})

    db.command(
        "sql",
        "CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA " + metadata_json,
    )

    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO Doc SET text = ?, embedding = ?",
            doc_text,
            to_java_float_array(vec),
        )

    hits = db.query(
        "sql",
        f"SELECT vectorNeighbors('Doc[embedding]', {list(map(float, vec))}, 1) as res",
    ).to_list()
```

{% endraw %}

Notes:

- `to_java_float_array` accepts NumPy arrays directly.
- For cosine, pass `normalize_embeddings=True` (as above) to your model.
- For euclidean or inner_product, skip normalization if magnitude should matter.

## Preferred Search Surface: SQL / Cypher

For new code, prefer query APIs for search.

### SQL filtered vector search with score shaping

```python
qvec_literal = "[" + ", ".join(str(float(x)) for x in query_vec) + "]"

rows = db.query(
    "sql",
    (
    "SELECT title, category, distance, (1 - distance) AS score "
    "FROM (SELECT expand(vectorNeighbors('Article[embedding]', "
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
    "FROM (SELECT expand(vectorNeighbors('Movie[embedding]', "
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
- SQL quantization helpers: `vector.quantizeInt8` / `vector.dequantizeInt8` and
  `vector.quantizeBinary` / `vector.dequantizeBinary(v[, low, high])`. Binary
  quantization keeps only the sign of each element; dequantize reconstructs it as
  `low`/`high` (default `-1.0`/`1.0`).

## SQL Helpers

- Preferred path: `CREATE INDEX ON Doc (embedding)
  LSM_VECTOR METADATA {"dimensions": 128, "distanceFunction": "COSINE"}`
- Search via SQL:
    - `SELECT vectorNeighbors('Doc[embedding]', [0.1,0.2], 5) AS res`
- Math/distance helpers: `vectorCosineSimilarity`, `vectorL2Distance`,
  `vectorDotProduct`, `vectorNormalize`, `vectorAdd`, `vectorSum`, etc.
- Every `vector.xxx` function is also reachable as a camelCase alias (`vector.l2Norm`
  ⇔ `vectorL2Norm`), so both spellings resolve to the same function.
- Distance: `vectorL2Distance` (Euclidean), `vectorManhattanDistance` /
  `vectorL1Distance` (L1, sum of absolute differences).
- Norms: `vectorL2Norm` / `vectorMagnitude` (Euclidean length), `vectorLInfNorm`
  (max absolute element).
- Element-wise math: `vectorAdd`, `vectorSubtract`, `vectorMultiply`, `vectorScale`,
  and `vectorClamp(v, min, max)` to bound each element to a range. `vectorAdd` and
  `vectorSubtract` also broadcast a scalar operand (e.g. `vectorAdd([1,2,3], 4)`).
- Quality checks: `vectorHasNull(v)` returns `true` when a vector contains a
  NaN/null element (useful for guarding embeddings before indexing).
- Stats: `vectorStdDev`, `vectorVariance`, and `vector.sparsity(v[, threshold, mode])`
  where `mode` is the default ratio, `L0` (count of significant elements), or `GMEAN`.
- Score shaping: `vector.scoreTransform(score, mode)` with modes such as `LN`/`LOG`
  and `TANH`, and `vector.multiScore(scores, fusion)` (e.g. `MAX`) to fuse score lists.
- Conversions: `.asString(format)` renders a vector as text — formats are `COMPACT`
  (default), `PRETTY`, `PYTHON`, `JULIA`, `MATLAB`, `MATLAB_COLUMN`, and `NUMPY`,
  where `NUMPY` emits a bare comma-separated list ready for
  `np.array(s.split(','), dtype=np.float32)`. `.asVector()` is the inverse and parses
  any of those layouts (or a number/list) back into a vector, e.g.
  `SELECT [1.0, 2.5].asString('NUMPY').asVector()`. `.asSparse([threshold])` converts
  a dense vector to a sparse one (see Sparse Vectors).
- Quantization via SQL: `METADATA {"quantization": "INT8"}` is the recommended path for
  embedded usage.

## Native INT8 Storage

If your application already has INT8 vectors, store them in a `BINARY` property and
set `encoding="INT8"` on the vector index metadata.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./vector_demo_int8") as db:
    db.command("sql", "CREATE VERTEX TYPE ByteDoc")
    db.command("sql", "CREATE PROPERTY ByteDoc.id STRING")
    db.command("sql", "CREATE PROPERTY ByteDoc.embedding BINARY")

    db.command(
    "sql",
    """
    CREATE INDEX ON ByteDoc (embedding)
    LSM_VECTOR
    METADATA {
        "dimensions": 4,
        "similarity": "COSINE",
        "quantization": "NONE",
        "encoding": "INT8"
    }
    """,
    )

    with db.transaction():
    db.command(
        "sql",
        "INSERT INTO ByteDoc SET id = ?, embedding = ?",
        "doc_a",
        arcadedb.to_java_byte_array([127, 0, 0, 0]),
    )
```

Use `encoding="INT8"` only with `quantization="NONE"`. Combining INT8 storage encoding
with INT8 quantization would quantize the same vector twice.

## Sparse Vectors

ArcadeDB also supports sparse top-K retrieval through `LSM_SPARSE_VECTOR` and
`vector.sparseNeighbors(...)`. To convert between representations in SQL, use
`.asSparse([threshold])` (dense → sparse, keeping elements above the threshold)
and `vector.sparseToDense(sv)` (sparse → dense), e.g.
`SELECT [0.0, 5.0, 0.0].asSparse()`.

```python
import arcadedb_embedded as arcadedb
import jpype.types as jtypes

with arcadedb.create_database("./sparse_demo") as db:
    db.command("sql", "CREATE DOCUMENT TYPE SparseDoc")
    db.command("sql", "CREATE PROPERTY SparseDoc.tokens ARRAY_OF_INTEGERS")
    db.command("sql", "CREATE PROPERTY SparseDoc.weights ARRAY_OF_FLOATS")

    db.command(
    "sql",
    """
    CREATE INDEX ON SparseDoc (tokens, weights)
    LSM_SPARSE_VECTOR
    METADATA {"dimensions": 128}
    """,
    )

    rows = db.query(
    "sql",
    "SELECT expand(`vector.sparseNeighbors`('SparseDoc[tokens,weights]', ?, ?, 5))",
    jtypes.JArray(jtypes.JInt)([5]),
    arcadedb.to_java_float_array([1.0]),
    ).to_list()
```

## Grouped Search

Recent engine builds support `groupBy` / `groupSize` options on `vector.neighbors`.
This is useful when you want diversity across a field such as source file, tenant, or
document family.

```python
rows = db.query(
    "sql",
    (
    "SELECT source_file, distance FROM "
    "(SELECT expand(`vector.neighbors`(?, ?, ?, { groupBy: 'source_file', groupSize: 1 }))) "
    "ORDER BY distance"
    ),
    "GroupedDoc[embedding]",
    arcadedb.to_java_float_array([1.0, 0.0, 0.0, 0.0]),
    3,
).to_list()
```

## Examples & References

- **[Example 03: Vector Search – Semantic Similarity](../examples/03_vector_search.md)**
- **[Example 06: Vector Search Movie Recommendations](../examples/06_vector_search_recommendations.md)**
- **[Vector API Reference](../api/vector.md)**
