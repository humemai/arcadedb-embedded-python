# Plan to Update Python Bindings for LSM Vector Index Enhancements (COMPLETED)

We have updated the Python bindings to support the new features introduced in the ArcadeDB engine: **LSM Vector Index Graph Storage** (`storeVectorsInGraph`) and **Quantization**.

## 1. Update Python Bindings (`src/arcadedb_embedded`)

### `bindings/python/src/arcadedb_embedded/jvm.py` (DONE)

- Added `--add-modules=jdk.incubator.vector` to the default JVM arguments to enable SIMD optimizations.
- **Note**: Correct syntax for the module flag was verified.
- JVM args now focus on JVM-wide concerns only (heap, headless, native access, vector module); per-index vector params moved to `core.py`.

### `bindings/python/src/arcadedb_embedded/core.py` (DONE)

- Updated `create_vector_index` signature to accept `quantization`, `store_vectors_in_graph`, PQ knobs, and per-index vector cache/rebuild overrides (`location_cache_size`, `graph_build_cache_size`, `mutations_before_rebuild`).
- Per-index overrides are passed via metadata (e.g., `locationCacheSize`, `graphBuildCacheSize`, `mutationsBeforeRebuild`), making configuration Pythonic instead of JVM-wide.
- **Implementation Detail**: Used `JSONObject` metadata to avoid JPype overload ambiguity with `TypeLSMVectorIndexBuilder`.

## 2. Update Tests (`tests`) (DONE)

### `bindings/python/tests/test_vector.py`

- Added `test_create_vector_index_with_graph_storage` (PASSED).
- Added `test_graph_storage_with_quantization` (PASSED).
- Refactored quantization tests into `test_lsm_vector_quantization_int8_comprehensive` and `test_lsm_vector_quantization_binary_comprehensive` (PASSED).
- Fixed DELETE/SEARCH consistency issues in `test_lsm_vector_delete_and_search_others` (PASSED).

### `bindings/python/tests/test_vector_sql.py`

- Updated SQL tests to support quantization syntax.
- Fixed and enabled BINARY quantization tests (removed `xfail`).

## 3. Update Examples (DONE)

The vector benchmark scripts and other examples have been updated.

### `bindings/python/examples`

- `benchmark-vector/benchmark_vector_params.py`: Added CLI args (`--quantization`, `--store-vectors-in-graph`).
- `03_vector_search.py`, `06_vector_search_recommendations.py`, `07_stackoverflow_multimodel.py`: Updated comments and calls.

## 4. Documentation (DONE)

- Updated `bindings/python/README.md`.
- Updated docstrings in `core.py`.

---

## Action Plan (COMPLETED)

1.  [x] Modify `bindings/python/src/arcadedb_embedded/jvm.py`.
2.  [x] Modify `bindings/python/src/arcadedb_embedded/core.py` (handling JPype ambiguity).
3.  [x] Create and run tests in `bindings/python/tests/test_vector.py`.
4.  [x] Modify `bindings/python/examples/benchmark-vector/benchmark_vector_params.py`.
5.  [x] Modify other examples (`03`, `06`, `07`).
6.  [x] Update `bindings/python/README.md` and docstrings.

## TOODs

- [x] `addHierarchy` has been added to the vector java code base. expose this to python
- [x] fix the WAL issue for vector building
- [x] Engine: `storeVectorsInGraph=false` ignored (vecgraph still inlines vectors) — fix to avoid duplicate storage and high RSS/disk.
- [x] Engine: Expose a public “build vector graph now” API (no search trigger), e.g., `buildVectorGraphNow()` on `LSMVectorIndex`. this is easier than I thought. I should also make changes to the examples to include this. it's cleaner this way.
- [x] Python: expose PQ/approximate search (wrap `findNeighborsFromVectorApproximate`) in `VectorIndex`, and surface PQ knobs in `create_vector_index` metadata without JPype ambiguity.
- [x] Python: expose the four parameters used for PQ
      pq_subspaces: Optional[int] = None,
      pq_clusters: Optional[int] = None,
      pq_center_globally: Optional[bool] = None,
      pq_training_limit: Optional[int] = None,
- [x] Tests: add PQ/approx search coverage (params pass-through, k results, overquery handling, persistence after reopen, invalid PQ config errors).
- [ ] Run 1M, 2M, 4M, 8M, and 16M MSMARCO vector build and search.
- [ ] Docs: update Python examples and mkdocs, once all the vector stuff is done. Now we know the best practice. For example, default should be

  ```python
  def create_vector_index(
        self,
        vertex_type: str,
        vector_property: str,
        dimensions: int,
        distance_function: str = "cosine",
        max_connections: int = 16,
        beam_width: int = 100,
        quantization: str = "INT8",
        location_cache_size: Optional[int] = None,
        graph_build_cache_size: Optional[int] = None,
        mutations_before_rebuild: Optional[int] = None,
        store_vectors_in_graph: bool = False,
        add_hierarchy: Optional[bool] = True,
        pq_subspaces: Optional[int] = None,
        pq_clusters: Optional[int] = None,
        pq_center_globally: Optional[bool] = None,
        pq_training_limit: Optional[int] = None
  )
  ```

  also we've learned that memory consumption is quite big. For example, for 1024 dimensional vectors with INT8 quantization, for vector index building we need at least:
  - 1M vectors need at least 4G heap
  - 2M vectors need at least 8G heap
  - 4M vectors need at least 16G heap
  - 8M vectors need at least 32G heap

  and for vector search we need:
  - 1M: 1g works, at least 1g recommended
  - 2M: 1g works, at least 2g recommended
  - 4M: 1g works, at least 2g recommended
  - 8M: 1g doesn't work (OoM), 2g works, at least 4g recommended

  ofc, we can reduce the heap requirements potentailly by reducing the vector dimensions and other `create_vector_index` parameters. we advise people to build the vector index in a bigger and more powerful machine, which has more RAM, and then move the database files & indexes to the production machine.

# Plan to remove Gremlin completely and replace it with OpenCypher

- now we can finally remove `108.9 MB     arcadedb-gremlin-26.1.1-SNAPSHOT-shaded.jar` since we have opencypher implemented already.
- We have to remove the Gremlin stuff in python binding tests, examples, and documentation. Ideally they should be replaced with OpenCypher examples and tests. Would be nice if we can make direct translation. OpenCypher is in `3.5 MB     arcadedb-engine-26.1.1-SNAPSHOT.jar`, which is amazing.

## TODOs

- [x] Fix the `*.py` examples in `/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/examples`. We have some Gremlin queries and they should be replaced with OpenCypher queries.
- [x] Now that we fixed the `*.py` examples, we should fix the documents of the examples in `/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/docs/examples` that mention Gremlin.
- [x] Fix the documents that talk about Gremlin (`/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/docs`). Gremlin is not supported anymore. we support opencypher. we should remove that.
- [x] Fix the remaining `*.py` and `*.md` in general (`/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python`) that "encourages" Gremlin. now we should encourage (open) cypher
