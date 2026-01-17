# Plan to Update Python Bindings for LSM Vector Index Enhancements (COMPLETED)

We have updated the Python bindings to support the new features introduced in the ArcadeDB engine: **LSM Vector Index Graph Storage** (`storeVectorsInGraph`) and **Quantization**.

## 1. Update Python Bindings (`src/arcadedb_embedded`)

### `bindings/python/src/arcadedb_embedded/jvm.py` (DONE)
-   Added `--add-modules=jdk.incubator.vector` to the default JVM arguments to enable SIMD optimizations.
-   **Note**: Correct syntax for the module flag was verified.

### `bindings/python/src/arcadedb_embedded/core.py` (DONE)
-   Updated `create_vector_index` signature to accept `quantization` and `store_vectors_in_graph`.
-   **Implementation Detail**: Used `JSONObject` metadata to pass `storeVectorsInGraph` to avoid JPype ambiguity with `TypeLSMVectorIndexBuilder`.
    ```python
    json_cfg = JSONObject('{ "storeVectorsInGraph": true }')
    builder.withMetadata(json_cfg)
    ```

## 2. Update Tests (`tests`) (DONE)

### `bindings/python/tests/test_vector.py`
-   Added `test_create_vector_index_with_graph_storage` (PASSED).
-   Added `test_graph_storage_with_quantization` (PASSED).
-   Refactored quantization tests into `test_lsm_vector_quantization_int8_comprehensive` and `test_lsm_vector_quantization_binary_comprehensive` (PASSED).
-   Fixed DELETE/SEARCH consistency issues in `test_lsm_vector_delete_and_search_others` (PASSED).

### `bindings/python/tests/test_vector_sql.py`
-   Updated SQL tests to support quantization syntax.
-   Fixed and enabled BINARY quantization tests (removed `xfail`).

## 3. Update Examples (DONE)

The vector benchmark scripts and other examples have been updated.

### `bindings/python/examples`
-   `benchmark-vector/benchmark_vector_params.py`: Added CLI args (`--quantization`, `--store-vectors-in-graph`).
-   `03_vector_search.py`, `06_vector_search_recommendations.py`, `07_stackoverflow_multimodel.py`: Updated comments and calls.

## 4. Documentation (DONE)

-   Updated `bindings/python/README.md`.
-   Updated docstrings in `core.py`.

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
- [ ] Engine: INT8 quantization footprint regression — db size grows vs FP32 and RSS stays high; re-evaluate after graph duplication fix.
- [x] Engine: Expose a public “build vector graph now” API (no search trigger), e.g., `buildVectorGraphNow()` on `LSMVectorIndex`. this is easier than I thought. I should also make changes to the examples to include this. it's cleaner this way.
- [x] Python: expose PQ/approximate search (wrap `findNeighborsFromVectorApproximate`) in `VectorIndex`, and surface PQ knobs in `create_vector_index` metadata without JPype ambiguity.
- [x] Python: expose the four parameters used for PQ
        pq_subspaces: Optional[int] = None,
        pq_clusters: Optional[int] = None,
        pq_center_globally: Optional[bool] = None,
        pq_training_limit: Optional[int] = None,
- [x] Tests: add PQ/approx search coverage (params pass-through, k results, overquery handling, persistence after reopen, invalid PQ config errors).
- [ ] Benchmarks/examples: extend vector examples and MSMARCO bench scripts to include PQ/approx runs and note recall trade-offs for random vs real embeddings.
- [ ] Docs: update Python examples and mkdocs, once all the vector stuff is done.

## **Plan: Issue #3162 (codes-first / drop floats)**

- **Goal:** shrink disk/RSS when quantization is on.
- **Step 1 (drop floats opt-in):**
    - Add `storeRawVectors` (default true). If false and quantization != NONE, do not store float payloads in the bucket; keep only RID→index-id. `lsmvecidx` (and `.vecpq` for PQ) remains the source of quantized vectors.
    - Persist `payloadType` (FLOATS vs codes) so reopen/search know what’s stored; reject rebuild/retune that needs floats when payloadType is codes.
    - Guardrails: refuse `storeRawVectors=false` if quantization=NONE; clear error messaging for rebuild attempts without floats.
