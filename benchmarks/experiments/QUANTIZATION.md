# What each vector engine ships, and what the page runs

The quantization survey of DECISIONS #131 item 8 (CAMPAIGN.md section 7 row 42), taken 2026-10-02 against the pins the 26.10.1 measurement starts from. For every dense and sparse comparator: the representations its pinned image ships, what our DDL builds today, and whether it gets an int8 arm. The rule is DECISIONS #53, extended to the sparse table by #131: an engine that ships an int8 (or int8-class) mode gets an int8 arm beside its full-precision one, at the same operating point, and each row records the representation it ran as `quantization`.

**Source column.** "image" means checked on the pinned image or client package on 2026-10-02 (the probe is named); "docs" means the engine's documentation for the pinned version, not yet run here; "adapter" means what our own DDL issues.

## Dense

| engine (pin) | ships | our arm today | int8 arm | source |
|---|---|---|---|---|
| ArcadeDB (26.10.1 at the re-pin) | `LSM_VECTOR` quantization `NONE`, `INT8`, `BINARY`, `PRODUCT` | fp32 and INT8, embedded and served | exists | adapter (`l3d_dense._QUANT_DDL`, the engine's own error text for anything else) |
| Qdrant v1.19.1 | scalar (int8), product, binary, turbo | fp32 and scalar int8 (quantile 0.99, always_ram, rescore at search) | exists | image: `qdrant_client.models` in `dbbench:client` lists `ScalarQuantization` (`int8`), `ProductQuantization`, `BinaryQuantization`, `TurboQuantization` |
| Milvus v3.0.1 | HNSW (fp32), `HNSW_SQ` (`sq_type` SQ8 and others), `HNSW_PQ`, `HNSW_PRQ`, IVF variants | HNSW fp32 and `HNSW_SQ` SQ8 | exists | adapter (both arms build on the image); docs for the rest |
| sqlite-vec 0.1.9 | `float32`, `int8`, `bit` column types, `vec_quantize_int8()` | fp32 and int8 | exists | image: `dbbench:dense` |
| LanceDB 0.39.0 | `IVF_HNSW_FLAT` (unquantized HNSW in IVF partitions), `IVF_HNSW_SQ`, `IVF_HNSW_PQ`, `IVF_FLAT`, `IVF_SQ`, `IVF_PQ`, `IVF_RQ` | `IVF_HNSW_SQ`, recorded INT8, on the stated ground that it is LanceDB's only HNSW offering | **the premise is stale**: 0.39.0 builds `IVF_HNSW_FLAT`, so LanceDB can run an fp32 arm matched to the others, and today's `IVF_HNSW_SQ` arm becomes its int8 arm | image: each type passed to `create_index` on a 3,000-row table in `dbbench:dense`; `HNSW_FLAT` and `HNSW_SQ` (without IVF) are refused |
| Chroma 1.5.9 | hnswlib, fp32 only | fp32 | none shipped | adapter (only `hnsw:*` collection metadata exists); docs |
| DuckDB VSS (duckdb 1.5.4) | HNSW over `FLOAT[]` arrays; no quantization setting | fp32 | none shipped | image: `duckdb_settings()` in `dbbench:duckdb` lists only `hnsw_ef_search` and `hnsw_enable_experimental_persistence` |
| pgvector 0.8.6 | `vector` (fp32), `halfvec` (fp16), `bit` (binary, by an expression index over `binary_quantize`), `sparsevec` | fp32 | no int8 type; fp16 and binary exist but are not int8, so no arm under #53 | docs |
| Neo4j 2026.08.1 | `vector.quantization.type` `NONE`, `SCALAR`, `BINARY`; **unset means `BINARY`**, with `vector.default_search_expansion_factor` 3.0 | **recorded fp32, ran BINARY**: `neo4j_dense` and `neo4j_e2` create their index without the key | add the fp32 arm by setting `NONE` (or `vector.quantization.enabled: false`, which reads back `NONE`), and the int8-class arm as `SCALAR` | image: `SHOW VECTOR INDEXES` on an index created with exactly our options reports provider `vector-2026.08` and `vector.quantization.type: "BINARY"`; `INT8` and `FLOAT32` are syntax errors |
| MongoDB 8.2.12 + mongot-community 1.70.4 | `vectorSearch` index `quantization`: `none`, `scalar`, `binary` | `none`, read back as `mongot_quantization` | `scalar` | adapter (sets `"quantization": "none"` and reads it back); docs for the others |
| SurrealDB (core 2.3.10 embedded, 3.2.4 served) | HNSW `TYPE` F64, F32, I64, I32, I16: element types of the stored array, not quantization of float vectors | `TYPE F32` | none shipped | adapter; docs |
| ArangoDB 3.12.11 | FAISS IVF vector index; a custom FAISS `factory` string (SQ8, PQ) | IVF flat, fp32 (`nLists`, `nProbe` calibrated) | possible through `factory` (SQ8) if the pinned server accepts it: **verify before deciding** | docs, not yet run here |
| Elasticsearch 9.5.4 (joins dense, row 37) | `hnsw`, `int8_hnsw`, `int4_hnsw`, `bbq_hnsw`, `bbq_disk`, `int8_flat` (all accepted); **default `int8_hnsw` at 96 and 128 dimensions** (m 16, ef_construction 100), `bbq_hnsw` with 3x oversampling from 384 | not built yet | fp32 `hnsw` and int8 `int8_hnsw`, as row 37 says; the default is the int8 arm, so the fp32 arm must set `hnsw` explicitly | image: dense_vector mappings on the pinned server, defaults read through `_mapping/field?include_defaults=true` |
| Memgraph 3.13.1 (joins dense, row 38) | `scalar_kind` f64, f32, f16, bf16, i8 (`b1` refused) | not built yet | f32 and i8 | image: `CREATE VECTOR INDEX ... scalar_kind` on the pinned server, `SHOW VECTOR INDEX INFO` |
| FalkorDB (6.0.1 at the re-pin, row 38) | vector index over float32 | not built yet | none documented | docs, not yet run here |
| LadybugDB 0.20.4 (row 38) | the official `vector` extension, HNSW over float arrays | not built yet | none documented | docs, not yet run here |

## Sparse

| engine (pin) | ships | our arm today | int8 arm | source |
|---|---|---|---|---|
| ArcadeDB | `LSM_SPARSE_VECTOR` `weightQuantization` INT8 (the default), FP16, FP32 | INT8 (default) and FP32 | exists | adapter (`l3_sparse.ArcadeEmbedded.quant`, engine #5143) |
| Qdrant v1.19.1 | sparse `datatype` `float32` (default), `float16`, `uint8`, `turbo4` | float32 | **`uint8`**: an int8-class arm under #131 | image: `qdrant_client.models.Datatype` in `dbbench:client` |
| Milvus v3.0.1 | `SPARSE_FLOAT_VECTOR` with `SPARSE_INVERTED_INDEX` | float32 weights | none documented | adapter; docs |
| Elasticsearch 9.5.4 | `sparse_vector`; weights kept at reduced precision by the engine, no setting | the default | none to choose | docs |
| pgvector 0.8.6 | `sparsevec`, fp32 | fp32 | none shipped | docs |

## What follows

New int8 arms owed for the 26.10.1 measurement: Neo4j `SCALAR` (with its fp32 arm corrected to `NONE`, on the dense and cross-model lanes), MongoDB `scalar`, Elasticsearch `int8_hnsw` (row 37), Memgraph `i8` (row 38), LanceDB's fp32 `IVF_HNSW_FLAT` beside its existing SQ arm, and Qdrant sparse `uint8`. ArangoDB's `factory` SQ8 is to be tried on the pinned server first. The dense lane's other forks build the dense arms; the Qdrant sparse arm belongs to the sparse lane.
