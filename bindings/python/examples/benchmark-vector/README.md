# Benchmarking Arcadedb's Vector Index Build and Search (LSM + JVector) Performance

## MSMARCO Dataset

- Data prepared with [convert-msmacro-parquet-to-shards.py](./convert-msmacro-parquet-to-shards.py). [Download Cohere MSMARCO v2.1](https://huggingface.co/datasets/Cohere/msmarco-v2.1-embed-english-v3) parquet shards, normalize to float32, write flat f32 shards, and build exact GT for 1K queries (top-50).
- Benchmarks here use the 1M subset. For production/RAG we should target 10M+ vectors; GT and shards are already computed—ask if you want the bundle to rerun.

## Benchmark Setup

- **Hardware:** AMD Ryzen 9 7950X (16 cores), 128GB DDR5 (4x32GB), Samsung SSD 970 EVO Plus 2TB.
- Take the duration with a grain of salt, since there are other processes running on the machine. RSS and DB size are more stable. 4 threads were allocated per task, but there aren't always the same number of tasks runing in parallel, so effective CPU usage may vary.
- If not mentioned, `MAX_CONNECTIONS` is fixed as 12, `BEAM_WIDTHS` as 64, and `OVERQUERY_FACTORS` as 1

### Commit/Date: main @ da5e70d (Thu Jan 15 09:44:44 2026 -0500)

- This commit fixes the store_vectors_in_graph issue.
- The below two runs were run with `add_hierarchy=True`

#### MSMARCO-1M (1000 queries, Recall@50)

| quantization | store_vectors_in_graph | ingest_rss_mb | build_rss_mb | warmup_s | warmup_rss_mb | search_s | search_rss_mb | recall@50_before_close | warmup_after_reopen_s | search_after_reopen_s | search_after_reopen_rss_mb | recall@50_after_reopen | peak_rss_mb | db_size_mb | total_duration |
| :----------- | :--------------------- | ------------: | -----------: | -------: | ------------: | -------: | ------------: | ---------------------: | --------------------: | --------------------: | -------------------------: | ---------------------: | ----------: | ---------: | :------------- |
| NONE         | True                   |       8608.92 |       77.746 |  6001.45 |        157.16 |     6.26 |        13.098 |                 0.9198 |                  6.91 |                20.835 |                     11.656 |                 0.9197 |     9348.51 |    9650.44 | 1h 41m         |
| NONE         | False                  |       8650.15 |       40.016 |  5974.64 |        139.84 |    9.871 |         4.977 |                  0.916 |                 7.873 |                 6.724 |                     11.609 |                 0.9157 |     9329.95 |    5750.44 | 1h 41m         |
| INT8         | True                   |       8392.88 |      420.625 |  3416.91 |        95.156 |   13.134 |        10.457 |                 0.9149 |                 4.313 |                  67.3 |                     10.047 |                 0.9072 |     9408.62 |    10638.9 | 59m            |
| INT8         | False                  |       8284.59 |      518.801 |  3404.88 |       112.254 |    9.147 |        13.809 |                 0.9146 |                 4.457 |                 9.165 |                     31.578 |                 0.9146 |     9437.81 |    6738.94 | 58m            |

#### Disk Usage Breakdown

##### store_vectors_in_graph=False and quantization=INT8

```bash
du -sh arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=off_hier=on_batch=100000_seed=42/* | sort -h
320K    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=off_hier=on_batch=100000_seed=42/dictionary.0.327680.v0.dict
59M     arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=off_hier=on_batch=100000_seed=42/VectorData_0_2689535159251959_vecgraph.5.262144.v0.vecgraph
999M    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=off_hier=on_batch=100000_seed=42/VectorData_0_2689535159251959.4.262144.v0.lsmvecidx
5.6G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=off_hier=on_batch=100000_seed=42/VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=True and quantization=INT8

```bash
du -sh arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=on_hier=on_batch=100000_seed=42/* | sort -h
320K    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=on_hier=on_batch=100000_seed=42/dictionary.0.327680.v0.dict
999M    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=on_hier=on_batch=100000_seed=42/VectorData_0_2689534677234566.4.262144.v0.lsmvecidx
3.9G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=on_hier=on_batch=100000_seed=42/VectorData_0_2689534677234566_vecgraph.5.262144.v0.vecgraph
5.6G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=int8_store=on_hier=on_batch=100000_seed=42/VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=False and quantization=None

```bash
du -sh arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=off_hier=on_batch=100000_seed=42/* | sort -h
320K    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=off_hier=on_batch=100000_seed=42/dictionary.0.327680.v0.dict
11M     arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=off_hier=on_batch=100000_seed=42/VectorData_0_2689535353426837.4.262144.v0.lsmvecidx
59M     arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=off_hier=on_batch=100000_seed=42/VectorData_0_2689535353426837_vecgraph.5.262144.v0.vecgraph
5.6G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=off_hier=on_batch=100000_seed=42/VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=True and quantization=None

```bash
du -sh arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=on_hier=on_batch=100000_seed=42/* | sort -h
320K    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=on_hier=on_batch=100000_seed=42/dictionary.0.327680.v0.dict
11M     arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=on_hier=on_batch=100000_seed=42/VectorData_0_2689535105029551.4.262144.v0.lsmvecidx
3.9G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=on_hier=on_batch=100000_seed=42/VectorData_0_2689535105029551_vecgraph.5.262144.v0.vecgraph
5.6G    arcadedb_runs/dataset=MSMARCO-1M_label=1000000_maxconn=12_beam=64_oq=1_quant=none_store=on_hier=on_batch=100000_seed=42/VectorData_0_1.65536.v0.bucket
```

#### Findings

- **Disk Usage:** With `storeVectorsInGraph=False`, the vector graph file (`*.vecgraph`) size drops drastically from ~3.9GB to ~59MB. The total DB size is reduced by ~40% (6.7-5.7GB vs 10.6-9.6GB) by avoiding vector duplication. Note that in INT8 mode (`quant=int8`), there is an additional ~1GB overhead from the `*.lsmvecidx` file compared to `quant=none` (~11MB) because the quantized index structure itself consumes space, even though the bucket size (~5.6GB) remains constant across all runs (since it stores original f32 vectors).
- **Search Performance:** While initial search times are comparable, using `storeVectorsInGraph=True` results in significantly worse search performance after reopening the database.
- **Conclusion:** `storeVectorsInGraph=True` adds no tangible benefits; it increases disk usage and degrades search performance after a restart. Keeping it disabled (`False`) is recommended.

### Commit/Date: main @ d8098d7 (Wed Jan 14 15:20:25 2026 -0500)

#### MSMARCO-1M (1000 queries, Recall@50)

| quantization | store_vectors_in_graph | add_hierarchy | ingest_s | ingest_rss_mb | warmup_s | warmup_rss_mb | search_s | search_rss_mb | recall@50_before_close | open_db_s | warmup_after_reopen_s | search_after_reopen_s | recall@50_after_reopen | peak_rss_mb | db_size_mb | total_duration |
| :----------- | :--------------------- | :------------ | -------: | ------------: | -------: | ------------: | -------: | ------------: | ---------------------: | --------: | --------------------: | --------------------: | ---------------------: | ----------: | ---------: | :------------- |
| NONE         | False                  | True          |       70 |          8708 |  7139.74 |           152 |        6 |            17 |                 0.9101 |         1 |                     7 |                     9 |                 0.9101 |        9354 |       9650 | 2h 0m          |
| INT8         | False                  | False         |       71 |          8825 |   3865.7 |           140 |       27 |            10 |                 0.9072 |        15 |                     5 |                    65 |                 0.9072 |        9458 |      10633 | 1h 7m          |
| NONE         | True                   | False         |       67 |          8699 |  6561.28 |           147 |       16 |            10 |                 0.9085 |         4 |                    13 |                    58 |                 0.9049 |        9352 |       9645 | 1h 52m         |
| NONE         | False                  | False         |       66 |          8707 |  6590.55 |           171 |       13 |            16 |                 0.8994 |         3 |                    13 |                    23 |                 0.8994 |        9380 |       9645 | 1h 51m         |

#### Findings

- Memory: JVM heap capped at 8GB, yet RSS (Resident Set Size) peaks 9.3–9.5GB in all runs; forcing 4GB causes OOM. Even a 1M dataset pushes outside heap, suggesting off-heap/native graph build and mmap traffic dominate.
- Storage: Each run writes ~1.0GB `*.lsmvecidx` + ~5.6GB bucket + ~3.9GB `*.vecgraph`; vectors are effectively stored twice (bucket + graph) because `store_vectors_in_graph=False` is ignored—LSMVectorIndexGraphFile still serializes inline vectors. This doubles disk and keeps RSS high when mapping the graph file.
- Lazy build + rebuild: Graph is built only after the first search, so the first query does all construction (long warmup). Post-ingest mutations set `graphState=MUTABLE`, and the search path currently rebuilds on the very next query since it only checks `mutationsSinceSerialize>0`; the configured threshold (GlobalConfiguration default 100) is bypassed. Pure queries do not increment the counter, so 1,000 searches alone never trigger rebuilds.
- Persistence: Close/reopen shows no rebuild because the Jan 14, 2026 engine fix now persists and reloads the graph successfully. The reopen warmup is mostly graph load, not rebuild.
- Hierarchy: `add_hierarchy` raises build time modestly (~+9m: 2h00 vs. 1h51) but improves recall (0.9101 vs. 0.8994) and cuts search time materially (6s vs. 13–16s across 1K queries); likely fewer hops during graph search.
- Quantization (int8): Ingest time drops sharply (1h07 vs. ~1h51–2h00) with comparable recall (0.9072 vs. 0.8994 baseline). However RSS does not improve and db size increases (10.6GB vs. 9.6GB), likely because vectors are duplicated in the graph and/or stored as float alongside the int8 quantized form.
- JVector knobs: `MAX_CONNECTIONS=12` and `BEAM_WIDTH=64` held constant; higher will improve recall at higher build cost. JVector lacks `efSearch`, so overquery (>k then rerank) is the lever; overquery factor was 1 here to simplify results.
- Next steps: The ArcadeDB team is looking into the vector duplication and rebuild-threshold issues. Once fixes land, we will rerun on the 1M set for verification and then move to the 10M benchmark.
