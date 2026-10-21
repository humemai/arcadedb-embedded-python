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
        "similarity": "COSINE",
        "quantization": "INT8",
        "addHierarchy": true
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
        "SELECT vectorNeighbors('Doc[embedding]', ?, 2) as res",
        # bind the query vector; a bare Python list as the only argument would be
        # read as the parameter array and bind ? to 0.9
        to_java_float_array([0.9, 0.1, 0.0]),
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
- `get_stats()` returns live counters (cache hits and misses, where vectors were read
  from, graph state) for sizing caches and diagnosing build cost. See
  [Vector Caches](../api/vector.md#vector-caches).
- After a database is opened, an index loads its graph on the first search, and that
  search pays for it. A service that restarts can call `warm_up()` on the loaded index
  right after opening.
  See [`VectorIndex.warm_up()`](../api/vector.md#vectorindexwarm_up).

## Distance Functions (scoring behavior)

- `cosine` (default): returns cosine distance in [0,2]; lower is better.
- `euclidean`: returns squared Euclidean distance (d²); lower is better.
- `dot_product`: returns `-(1 + A·B) / 2`; lower is better. It expects unit-length
  vectors, and the engine logs a warning when sampled vectors are not.

Important:

- Vector-index search exposes cosine as distance: 1 - cos(θ).
- SQL `vectorCosineSimilarity(...)` exposes raw cosine similarity, so its values follow
  cosine similarity semantics rather than vector-index distance semantics.

## Tuning Knobs

- `dimensions`: must match your embedding length.
- `max_connections` (Vamana per-layer degree; use 2*M to match an hnswlib M): higher → better recall, more memory/slower build (default: 32).
- `beam_width` (ef/efConstruction): higher → better recall, slower search/build (default: 100).
- `ef_search` (runtime, exact search only): higher → better recall, slower search.
    - Unset, the engine picks the beam: 100 below 10,000 vectors, and `max(2k, 20)` from
      there up. On 20,000 random 32-dimension vectors that default found 80% of the true
      top 10, where a beam of 100 found 99.7%. Set it for the recall you need.

### The search beam in SQL

`vectorNeighbors(index, vector, k)` takes an optional fourth argument, the search
beam (`efSearch`): how many candidates the graph walk keeps before returning
`k`. Higher finds more of the true neighbours and costs time; the engine's
default is adaptive and small on larger graphs (see above). Pass it explicitly
when you compare recall across settings or engines, so the number you quote is
the number that ran:

```sql
SELECT expand(vectorNeighbors('Doc[embedding]', :q, 10, 100))
```

### Searches while the graph rebuilds

Deletes and updates collect as pending changes, and once they reach a fifth of
the graph (`arcadedb.vectorIndex.rebuildGraphRatio`, 0.2), and sometimes
earlier, the engine rebuilds the graph in the background while searches keep
running. On 26.9.1 and earlier, ArcadeDB
[#8862](https://github.com/ArcadeData/arcadedb/issues/8862) makes those searches
return noticeably worse neighbours for as long as the rebuild runs: on 20,000
vectors, recall@10 at a beam of 100 fell from 0.99 to between 0.14 and 0.31 for
the four seconds of the rebuild. **Fixed in 26.10.1** (PR #8864, verified on its
merge): the same run keeps recall@10 between 0.985 and 1.000 through the
rebuild. On an older release, run bulk deletes and updates at a quiet time; a
rebuild takes about as long as building the index, and the engine logs
`Built graph for index` when the new graph is in place.

At about 10M vectors with sustained inserts while a rebuild runs, the next
rebuild can be deferred indefinitely, and every search then pays a growing scan
of the vectors not yet in the graph (ArcadeDB
[#7260](https://github.com/ArcadeData/arcadedb/issues/7260)). Upstream fixed it
in [#9289](https://github.com/ArcadeData/arcadedb/pull/9289), merged on
2026-10-06 and released in ArcadeDB 26.10.2; the 26.10.1 wheel still has it. On 26.10.1, a
heap of about twice the graph, a lower `mutations_before_rebuild`, or rebuilding in a quiet window
avoids it. Read-mostly use, and loading first and
serving after, never meet it.

<!-- ab-table: rebuild-threshold -->
<!-- /ab-table -->

### Build-time cache: use the default

Building the graph for millions of vectors is dominated by reading the vectors
back, so the engine caches them while it builds. The default sizing is
automatic and is the right setting: it reads the heap the engine actually has
free and caches the whole corpus when it fits, inside a share of the heap
(`arcadedb.vectorIndex.graphBuildCacheMaxHeapPercent`, 25%). Give the JVM the
heap and leave `graphBuildCacheSize` alone; set an absolute count only to bound
a build on a deliberately small heap. Nothing in the bindings' tests or
examples sets it. See the
[Memory & Heap](#memory-heap-requirements-1024-dim-vectors) section for the
heap side.

### Graph build settings in SQL

The index metadata takes the graph build settings that the tuning list above names, and two
more that the Python helper does not expose: `neighborOverflowFactor` and
`alphaDiversityRelaxation`. Both are at least 1.0 and default to 1.2 in the engine. They
set how many extra candidate neighbours the build considers (`neighborOverflowFactor`) and
how far the build trades distance accuracy for diversity (`alphaDiversityRelaxation`). The
engine documents 1.0 to 1.5 as the typical range. A higher value costs build time. Leave them
at their defaults unless you measure a recall gain.

```python
db.command(
    "sql",
    """
    CREATE INDEX ON Doc (embedding) LSM_VECTOR
    METADATA {
        "dimensions": 384,
        "similarity": "COSINE",
        "maxConnections": 32,
        "beamWidth": 100,
        "neighborOverflowFactor": 1.2,
        "alphaDiversityRelaxation": 1.2,
        "addHierarchy": false
    }
    """,
)
```

`addHierarchy` has two defaults, on purpose. A SQL `CREATE INDEX` without the key follows the
engine, which builds a flat graph (`false`). `Database.create_vector_index()` passes
`add_hierarchy=True` unless you say otherwise, so an index made from Python has the HNSW
hierarchy layers. The two paths therefore build different graphs from the same
settings. State the value in both when you compare results, or when you need the same
index from either path. `VectorIndex.get_metadata()["add_hierarchy"]` shows what an index
has.

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
        "SELECT vectorNeighbors('Doc[embedding]', ?, 1) as res",
        to_java_float_array(vec),
    ).to_list()
```

{% endraw %}

Notes:

- `to_java_float_array` accepts NumPy arrays directly.
- For cosine, pass `normalize_embeddings=True` (as above) to your model.
- For euclidean, skip normalization if magnitude should matter. For dot_product,
  normalize: the engine expects unit-length vectors.

## Preferred Search Surface: SQL / Cypher

For new code, prefer query APIs for search. Bind the query vector as a parameter
(`to_java_float_array(query_vec)`) rather than pasting it into the SQL text: a pasted
vector makes every query a new statement to parse (see
[Parameters](core/queries.md#parameters)).

### SQL filtered vector search with score shaping

```python
from arcadedb_embedded import to_java_float_array

rows = db.query(
    "sql",
    (
        "SELECT title, category, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors('Article[embedding]', ?, 50))) "
        "WHERE category = ? ORDER BY distance LIMIT 5"
    ),
    to_java_float_array(query_vec),
    "category_42",
).to_list()
```

### SQL self-exclusion

```python
rows = db.query(
    "sql",
    (
        "SELECT title, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors('Movie[embedding]', ?, 20))) "
        "WHERE title <> ? ORDER BY distance LIMIT 10"
    ),
    to_java_float_array(query_vec),
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
- The default depends on the path that creates the index:
    - `Database.create_vector_index()` passes `quantization="INT8"` and `add_hierarchy=True`
      unless you say otherwise. This is a deliberate choice of these bindings.
    - SQL `CREATE INDEX ... LSM_VECTOR` follows the engine: no quantization (`NONE`, full
      precision) and no hierarchy (`addHierarchy` false) unless the `METADATA` sets them.
      The quick start above sets both, so it builds the same index as the helper.
- INT8 is the recommended setting. To get it from SQL, put `"quantization": "INT8"` in the
  `METADATA`.
- Use `quantization=None` only when you explicitly need full-precision vectors and can
  accept higher memory usage.
- PQ tunables (require `quantization="PRODUCT"`): `pq_subspaces` (M), `pq_clusters` (K),
  `pq_center_globally`, `pq_training_limit`.
- In current ArcadeDB engine builds, PRODUCT/PQ also needs enough indexed vectors per
  bucket for training. For very small corpora, set `pq_clusters` to a value no larger
  than the number of indexed vectors in that bucket, or use `INT8`, `BINARY`, or `None`.
- `"PRODUCT"`/PQ is not recommended in these bindings: current engine builds score SQL search
  (`vectorNeighbors`) candidates with the full-precision vectors, so PQ gives no search speedup,
  and the index files are larger than with `None` because PQ codes are written that nothing reads
  ([ArcadeDB #10514](https://github.com/ArcadeData/arcadedb/issues/10514)).
- SQL quantization helpers: `vector.quantizeInt8` / `vector.dequantizeInt8` and
  `vector.quantizeBinary` / `vector.dequantizeBinary(v[, low, high])`. Binary
  quantization keeps only the sign of each element; dequantize reconstructs it as
  `low`/`high` (default `-1.0`/`1.0`).

## SQL Helpers

- Preferred path for embedded and server modes: `CREATE INDEX ON Doc (embedding)
  LSM_VECTOR METADATA {"dimensions": 128, "similarity": "COSINE"}`
  (the key is `similarity`; `distanceFunction` is rejected by the index, though
  it remains the spelling `IMPORT DATABASE ... WITH distanceFunction = cosine`
  uses on that separate surface)
- Search via SQL:
    - `SELECT vectorNeighbors('Doc[embedding]', ?, 5) AS res`, with the query vector
      bound (`to_java_float_array(vec)`)
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
- Conversions: `.asString(format)` renders a vector as text. Formats are `COMPACT`
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

### Weight precision: INT8 by default, FP32 on request

The sparse index stores posting weights quantized to 8 bits by default, which
is what a search engine does and costs a small amount of recall. To keep exact
32-bit weights, say so in the index metadata:

```sql
CREATE INDEX ON SparseDoc (tokens, weights) LSM_SPARSE_VECTOR
METADATA {"dimensions": 30000, "weightQuantization": "FP32"}
```

Both forms answer `vector.sparseNeighbors` the same way. The INT8 index
only picks the candidates: it fetches `k × rescoreOversample` of them and ranks them by
the exact score computed from the records' own weights (`ArcadeData/arcadedb#8576`).
`rescoreOversample` is an index metadata key, 2 by default for INT8 and FP16 and off for
FP32; `0` turns it off. On 100,000 BigANN SPLADE documents that took INT8 recall@10 from
0.9948 to 1.0000, the same as FP32, and made the top-10 lists identical whatever the
commit size the index was loaded with, for about 16% more scorer time on Temurin 25
(43% on Temurin 21, laptop, 4 cores). So the choice is on disk (FP32 about 20% larger
for a SPLADE-style corpus) and speed, not on the answers.

Leave the scorer's own settings at their defaults (posting block size 128,
`arcadedb.sparseVectorScoringMaxPartitions=0`); upstream has no other setting to
recommend (`ArcadeData/arcadedb#8553`).

### Sparse search options

`vector.sparseNeighbors(index, indices, values, k[, options])` takes the query as two
arrays of the same length, token ids and weights. Its options map has `filter`, `where`,
`groupBy` and `groupSize`, which work as in [Search Options in SQL](#search-options-in-sql)
(`where` needs 26.11.1 or later), and `minScore`, which drops hits scoring below it. A sparse
score is a similarity, so higher is better. Unlike the dense function, the row exposes
`score`, not `distance`.

```python
rows = db.query(
    "sql",
    "SELECT id, score FROM "
    "(SELECT expand(`vector.sparseNeighbors`('SparseDoc[tokens,weights]', ?, ?, 5, "
    "{ minScore: 0.5 })))",
    jtypes.JArray(jtypes.JInt)([5]),
    arcadedb.to_java_float_array([1.0]),
).to_list()
```

From Python, `db.schema.create_index("SparseDoc", ["tokens", "weights"],
index_type=IndexType.LSM_SPARSE_VECTOR)` creates the index with the engine defaults. Use
the SQL form above when you need `dimensions`, `weightQuantization` or `rescoreOversample`.

### The settle step: compact before you time queries

An LSM sparse index answers from every segment it has written until those
segments are merged, and a freshly loaded index has many. Queries get faster
once it is compacted, so compact after bulk loads and before benchmarks, the
way you would force-merge a search engine:

```sql
COMPACT INDEX `SparseDoc[tokens,weights]`
```

The statement is synchronous and works embedded and over the server's HTTP
API alike. In-process there is also the Java handle,
`db.get_java_database().getSchema().getIndexByName(...).compact()`, which is
what the SQL form calls. At one million documents the compaction took about
two seconds and moved query p50 from 9.5 ms to 7.0 ms. It also flushes the in-memory
postings, so afterwards the whole index is one segment (`ArcadeData/arcadedb#8576`).

## Grouped Search

`vector.neighbors` accepts `groupBy` / `groupSize` options.
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

## Search Options in SQL

The fourth argument of `vectorNeighbors(index, vector, k, options)` (the dotted name
`vector.neighbors` is the same function) is either the search beam as a number or a map of
options. All keys are optional:

| Key | Meaning |
| --- | --- |
| `efSearch` | Search beam width, as in [The search beam in SQL](#the-search-beam-in-sql) |
| `filter` | List of RIDs to restrict the search to |
| `where` | Predicate on the candidate records: a map of property to value, or a SQL condition string. Needs ArcadeDB 26.11.1 or later |
| `groupBy` | Property to group the hits by; `k` then counts groups |
| `groupSize` | Hits kept per group (default 1) |
| `maxDistance` | Drop hits farther than this distance |

An unknown key raises an error that lists the allowed ones. `where` raises that error on an
engine older than 26.11.1, and the 26.10.x wheels carry one.

### Filter by RID and by predicate

`filter` takes a list of RIDs you computed before the search. `where` tests a condition on
each candidate as the search reaches it, so you do not list every RID in scope first. Give a
map (every property must be equal) or a SQL condition string. A condition cannot use
positional `?` parameters, so bind values by name or put them in a map.

```python
# Needs ArcadeDB 26.11.1 or later
rows = db.query(
    "sql",
    "SELECT title, distance FROM "
    "(SELECT expand(vectorNeighbors('Doc[embedding]', ?, 5, "
    "{ where: \"lang = 'en' AND year > 2020\" })))",
    to_java_float_array(query_vec),
).to_list()

rows = db.query(
    "sql",
    "SELECT title, distance FROM "
    "(SELECT expand(vectorNeighbors('Doc[embedding]', ?, 5, { where: { lang: 'en' } })))",
    to_java_float_array(query_vec),
).to_list()
```

`where` and `filter` combine: a hit has to pass both. On an older engine, build the RID
list with a query and pass it as `filter`.

### Distance cut-off

`maxDistance` drops hits whose distance is above the value. It is applied to the `k`
neighbours the index found, so a tight cut-off returns fewer than `k` rows and does not
search further to fill them. Set `k` to the most rows you want.

```python
rows = db.query(
    "sql",
    "SELECT title, distance FROM "
    "(SELECT expand(vectorNeighbors('Doc[embedding]', ?, 50, { maxDistance: 0.25 })))",
    to_java_float_array(query_vec),
).to_list()
```

Options combine, for example `{ efSearch: 100, filter: [...], maxDistance: 0.25 }`.
[Grouped Search](#grouped-search) shows `groupBy` and `groupSize`.

## Examples & References

- **[Example 03: Vector Search – Semantic Similarity](../examples/03_vector_search.md)**
- **[Example 06: Vector Search Movie Recommendations](../examples/06_vector_search_recommendations.md)**
- **[Vector API Reference](../api/vector.md)**
