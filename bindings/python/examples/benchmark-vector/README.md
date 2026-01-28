# Benchmarking Arcadedb's Vector Index Build and Search (LSM + JVector) Performance

## MSMARCO Dataset

- Data prepared with [convert-msmacro-parquet-to-shards.py](./convert-msmacro-parquet-to-shards.py). [Download Cohere MSMARCO v2.1](https://huggingface.co/datasets/Cohere/msmarco-v2.1-embed-english-v3) parquet shards, normalize to float32, write flat f32 shards, and build exact GT for 1K queries (top-50).
- Benchmarks here use the 1M subset. For production/RAG we should target 10M+ vectors; GT and shards are already computed—ask if you want the bundle to rerun.

## Benchmark Setup

- **Hardware:** AMD Ryzen 9 7950X (16 cores), 128GB DDR5 (4x32GB), Samsung SSD 970 EVO Plus 2TB.
- Take the duration with a grain of salt, since there are other processes running on the machine. RSS and DB size are more stable. 4 threads were allocated per task, but there aren't always the same number of tasks runing in parallel, so effective CPU usage may vary.
- If not mentioned, `MAX_CONNECTIONS` is fixed as 12, `BEAM_WIDTHS` as 64, and `OVERQUERY_FACTORS` as 1

### Tests Run on 22-Jan-2026

We ran the same 1024-dimensional MSMARCO vectors with `INT8` quantization. Config (all runs): `store_vectors_in_graph=False`, `add_hierarchy=True`, `max_connections=16`, `beam_width=100`, `batch_size=10000`. These runs include both index build and search timings.

**Index build (INT8, 1000 queries, Recall@50):**

#### MSMARCO-1M

| heap | ingest_s | peak_rss_mb | db_size_mb | total_duration |
| :--- | -------: | ----------: | ---------: | :------------- |
| 4g   |   66.278 |     4460.43 |    6753.94 | 31m 49.438s    |

#### MSMARCO-2M

| heap | ingest_s | peak_rss_mb | db_size_mb | total_duration |
| :--- | -------: | ----------: | ---------: | :------------- |
| 8g   |  130.745 |     8624.22 |    13507.5 | 1h 0m 51.475s  |

#### MSMARCO-4M

| heap | ingest_s | peak_rss_mb | db_size_mb | total_duration |
| :--- | -------: | ----------: | ---------: | :------------- |
| 16g  |  298.401 |     16956.9 |    27014.9 | 2h 23m 31.456s |

#### MSMARCO-8M

| heap | ingest_s | peak_rss_mb | db_size_mb | total_duration |
| :--- | -------: | ----------: | ---------: | :------------- |
| 32g  |  620.635 |     33592.9 |    54024.1 | 5h 42m 31.988s |

**Lessons learned:**

- 1M: at least 4G
- 2M: at least 8G
- 4M: at least 16G
- 8M: at least 32G

These are near bare minimums; lower heaps may work if vector dimensions are reduced.

**Search study (INT8, 1000 queries, Recall@50):**

#### MSMARCO-1M

| heap | overquery_factor | recall@50 | latency_ms_mean | latency_ms_p95 | search_s | peak_rss_mb | db_size_mb | total_duration (s) |
| :--- | ---------------: | --------: | --------------: | -------------: | -------: | ----------: | ---------: | -----------------: |
| 1g   |               16 |     0.993 |             387 |            713 |      387 |        1300 |       6753 |                393 |
| 1g   |                8 |     0.990 |             216 |            391 |      217 |        1274 |       6753 |                223 |
| 1g   |                4 |     0.985 |             131 |            239 |      132 |        1259 |       6753 |                137 |
| 1g   |                2 |     0.973 |              86 |            172 |       86 |        1249 |       6753 |                 92 |
| 1g   |                1 |     0.942 |              60 |            141 |       61 |        1236 |       6753 |                 68 |
| 2g   |               16 |     0.993 |             216 |            384 |      216 |        2337 |       6753 |                221 |
| 2g   |                8 |     0.990 |             133 |            252 |      133 |        2303 |       6753 |                139 |
| 2g   |                4 |     0.985 |              82 |            173 |       83 |        2284 |       6753 |                 88 |
| 2g   |                2 |     0.973 |              53 |            119 |       53 |        2269 |       6753 |                 58 |
| 2g   |                1 |     0.942 |              34 |             80 |       35 |        2252 |       6753 |                 43 |
| 4g   |               16 |     0.993 |              90 |            169 |       90 |        4400 |       6753 |                 95 |
| 4g   |                8 |     0.990 |              53 |            117 |       54 |        4369 |       6753 |                 59 |
| 4g   |                4 |     0.985 |              31 |             80 |       31 |        4348 |       6753 |                 36 |
| 4g   |                2 |     0.973 |              19 |             61 |        2 |        4330 |       6753 |                 25 |
| 4g   |                1 |     0.942 |              12 |             42 |       13 |        4312 |       6753 |                 19 |
| 8g   |               16 |     0.993 |              32 |             48 |       32 |        8570 |       6753 |                 37 |
| 8g   |                8 |     0.990 |              17 |             25 |       17 |        8540 |       6753 |                 21 |
| 8g   |                4 |     0.985 |               9 |             13 |        9 |        8522 |       6753 |                 14 |
| 8g   |                2 |     0.973 |               5 |              6 |        5 |        8510 |       6753 |                  9 |
| 8g   |                1 |     0.942 |               3 |              6 |        3 |        8456 |       6753 |                 10 |

#### MSMARCO-2M

| heap | overquery_factor | recall@50 | latency_ms_mean | latency_ms_p95 | search_s | peak_rss_mb | db_size_mb | total_duration (s) |
| :--- | ---------------: | --------: | --------------: | -------------: | -------: | ----------: | ---------: | -----------------: |
| 1g   |               16 |     0.991 |             897 |           1577 |      898 |        1215 |      13507 |                916 |
| 1g   |                8 |     0.987 |             464 |            827 |      465 |        1278 |      13507 |                483 |
| 1g   |                4 |     0.982 |             277 |            490 |      278 |        1277 |      13507 |                296 |
| 1g   |                2 |     0.971 |             167 |            342 |      167 |        1265 |      13507 |                180 |
| 1g   |                1 |     0.940 |               9 |            229 |       96 |        1255 |      13507 |                109 |
| 2g   |               16 |     0.991 |             511 |            849 |      511 |        2355 |      13507 |                528 |
| 2g   |                8 |     0.987 |             280 |            492 |      280 |        2325 |      13507 |                298 |
| 2g   |                4 |     0.982 |             167 |            336 |      167 |        2305 |      13507 |                184 |
| 2g   |                2 |     0.971 |             101 |            234 |      101 |        2286 |      13507 |                119 |
| 2g   |                1 |     0.940 |              69 |            204 |       69 |        2267 |      13507 |                 94 |
| 4g   |               16 |     0.991 |             319 |            551 |      319 |        4407 |      13507 |                339 |
| 4g   |                8 |     0.987 |             181 |            321 |      181 |        4377 |      13507 |                200 |
| 4g   |                4 |     0.982 |             118 |            228 |      119 |        4357 |      13507 |                138 |
| 4g   |                2 |     0.971 |              71 |            148 |       72 |        4338 |      13507 |                 90 |
| 4g   |                1 |     0.940 |              43 |            114 |       43 |        4323 |      13507 |                 65 |
| 8g   |               16 |     0.991 |             135 |            263 |      135 |        8561 |      13507 |                151 |
| 8g   |                8 |     0.987 |              80 |            184 |       81 |        8530 |      13507 |                 98 |
| 8g   |                4 |     0.982 |              46 |            126 |       47 |        8511 |      13507 |                 64 |
| 8g   |                2 |     0.971 |              27 |             56 |       28 |        8498 |      13507 |                 45 |
| 8g   |                1 |     0.940 |              15 |             30 |       16 |        8488 |      13507 |                 38 |

#### MSMARCO-4M

| heap | overquery_factor | recall@50 | latency_ms_mean | latency_ms_p95 | search_s | peak_rss_mb | db_size_mb | total_duration (s) |
| :--- | ---------------: | --------: | --------------: | -------------: | -------: | ----------: | ---------: | -----------------: |
| 1g   |               16 |      0.99 |            2084 |           3747 |     2084 |        1214 |      27014 |               2135 |
| 1g   |                8 |     0.985 |            1276 |           2195 |     1277 |        1193 |      27014 |               1322 |
| 1g   |                4 |     0.976 |             686 |           1206 |      686 |        1192 |      27014 |                734 |
| 1g   |                2 |     0.963 |             443 |            824 |      443 |        1237 |      27014 |                488 |
| 1g   |                1 |     0.938 |             269 |            495 |      270 |        1233 |      27014 |                312 |
| 2g   |               16 |      0.99 |             534 |            910 |      535 |        2373 |      27014 |                566 |
| 2g   |                8 |     0.985 |             297 |            505 |      298 |        2346 |      27014 |                330 |
| 2g   |                4 |     0.976 |             179 |            358 |      179 |        2331 |      27014 |                207 |
| 2g   |                2 |     0.963 |             106 |            275 |      107 |        2320 |      27014 |                131 |
| 2g   |                1 |     0.938 |              66 |            222 |       67 |        2308 |      27014 |                103 |
| 4g   |               16 |      0.99 |             385 |            681 |      385 |        4453 |      27014 |                411 |
| 4g   |                8 |     0.985 |             208 |            422 |      209 |        4423 |      27014 |                235 |
| 4g   |                4 |     0.976 |             129 |            320 |      129 |        4403 |      27014 |                156 |
| 4g   |                2 |     0.963 |              78 |            160 |       78 |        4385 |      27014 |                106 |
| 4g   |                1 |     0.938 |              49 |            109 |       49 |        4363 |      27014 |                 85 |
| 8g   |               16 |      0.99 |             279 |            446 |      280 |        8603 |      27014 |                307 |
| 8g   |                8 |     0.985 |             166 |            285 |      166 |        8572 |      27014 |                193 |
| 8g   |                4 |     0.976 |             101 |            204 |      102 |        8549 |      27014 |                127 |
| 8g   |                2 |     0.963 |              62 |            148 |       63 |        8530 |      27014 |                 89 |
| 8g   |                1 |     0.938 |              37 |            103 |       37 |        8514 |      27014 |                 71 |

#### MSMARCO-8M

| heap | overquery_factor | recall@50 | latency_ms_mean | latency_ms_p95 | search_s | peak_rss_mb | db_size_mb | total_duration (s) |
| :--- | ---------------: | --------: | --------------: | -------------: | -------: | ----------: | ---------: | -----------------: |
| 2g   |               16 |     0.980 |            1210 |           1975 |     1211 |        2385 |      54024 |               1270 |
| 2g   |                8 |     0.974 |             716 |           1172 |      716 |        2343 |      54024 |                834 |
| 2g   |                4 |     0.966 |             435 |            744 |      436 |        2317 |      54024 |                491 |
| 2g   |                2 |     0.947 |             272 |            428 |      272 |        2305 |      54024 |                327 |
| 2g   |                1 |     0.911 |             173 |            372 |      173 |        2296 |      54024 |                242 |
| 4g   |               16 |     0.980 |             359 |            625 |      359 |        4491 |      54024 |                406 |
| 4g   |                8 |     0.974 |             201 |            435 |      202 |        4465 |      54024 |                246 |
| 4g   |                4 |     0.966 |             123 |            352 |      123 |        4442 |      54024 |                169 |
| 4g   |                2 |     0.947 |              74 |            294 |       75 |        4422 |      54024 |                133 |
| 4g   |                1 |     0.911 |              47 |            247 |       47 |        4411 |      54024 |                112 |
| 8g   |               16 |     0.980 |             267 |            558 |      267 |        8650 |      54024 |                309 |
| 8g   |                8 |     0.974 |             140 |            311 |      140 |        8621 |      54024 |                180 |
| 8g   |                4 |     0.966 |              85 |            183 |       85 |        8600 |      54024 |                127 |
| 8g   |                2 |     0.947 |              54 |            137 |       54 |        8582 |      54024 |                 96 |
| 8g   |                1 |     0.911 |              34 |            100 |       35 |        8548 |      54024 |                 79 |

**Lesson learned:**

- Vector search needs less heap than index build.
- 1M: 1G works; at least 1G recommended.
- 2M: 1G works; at least 2G recommended.
- 4M: 1G works; at least 2G recommended.
- 8M: 1G OOM; 2G works; at least 4G recommended.
- Build on a more powerful machine; search deployment can run on less powerful hardware.

### Commit/Date: main @ 6ef8858 (Thu Jan 15 16:40:51 2026 -0500)

- This commit adds Product Quantization (PQ) support to JVector index.
- The below four tasks vary quantization mode (`NONE`, `INT8`, `PRODUCT`, `BINARY`).
- `store_vectors_in_graph=False`, `add_hierarchy=True`, `max_connections=12`, `beam_width=64`, `overquery_factor=1`, `batch_size=10000` for all four runs.
- This time every task was allocated with one thread.
- As for PQ, there are four params we can tune, and we just used the defaults in ArcadeDB:
  - `pq_subspaces`
  - `pq_clusters`
  - `pq_center_globally`
  - `pq_training_limit`

#### MSMARCO-1M (1000 queries, Recall@50)

| quantization | ingest_s | ingest_rss_mb | create_index_s | create_index_rss_mb | build_graph_now_s | build_graph_now_rss_mb | search_s | search_rss_mb | recall@50_before_close | open_db_s | open_db_rss_mb | warmup_after_reopen_s | warmup_after_reopen_rss_mb | search_after_reopen_s | search_after_reopen_rss_mb | recall@50_after_reopen | peak_rss_mb | db_size_mb | total_duration |
| :----------- | -------: | ------------: | -------------: | ------------------: | ----------------: | ---------------------: | -------: | ------------: | ---------------------: | --------: | -------------: | --------------------: | -------------------------: | --------------------: | -------------------------: | ---------------------: | ----------: | ---------: | :------------- |
| NONE         |   60.599 |       7518.07 |         13.073 |             552.203 |            4859.9 |                313.852 |   11.132 |         6.773 |                 0.9099 |     4.066 |          5.902 |                 8.522 |                      0.125 |                 7.676 |                      4.117 |                 0.9099 |     8816.13 |    5750.44 | 1h 22m         |
| INT8         |   60.978 |       7405.65 |         18.888 |              877.16 |           3099.27 |                124.875 |   18.011 |        16.293 |                 0.9051 |    11.855 |         13.812 |                 4.302 |                      0.488 |                15.587 |                      7.176 |                 0.9039 |     8855.47 |    6738.94 | 53m            |
| PRODUCT      |   61.418 |       7978.64 |         13.127 |             211.594 |           5024.72 |                241.484 |    2.571 |         8.305 |                 0.8524 |     2.645 |          4.219 |                 7.266 |                      0.113 |                 1.401 |                      8.926 |                 0.8525 |     8862.87 |    5996.45 | 1h 25m         |
| BINARY       |   60.754 |       7734.86 |         25.235 |             452.316 |           3841.34 |                197.668 |   11.857 |        20.723 |                 0.2861 |     5.973 |          14.68 |                 4.298 |                      1.539 |                 5.865 |                      5.824 |                 0.2861 |     8837.07 |    5879.94 | 1h 5m          |

#### Disk Usage Breakdown

##### `quantization=none`

```bash
5.6G    VectorData_0.1.65536.v0.bucket
10M     VectorData_0_2748779662794320.4.262144.v0.lsmvecidx
59M     VectorData_0_2748779662794320_vecgraph.5.262144.v0.vecgraph
```

##### `quantization=int8`

```bash
5.6G    VectorData_0.1.65536.v0.bucket
999M    VectorData_0_2748780028226180.4.262144.v0.lsmvecidx
59M     VectorData_0_2748780028226180_vecgraph.5.262144.v0.vecgraph
```

##### `quantization=PQ`

```bash
5.6G    VectorData_0.1.65536.v0.bucket
11M     VectorData_0_2748780503246723.4.262144.v0.lsmvecidx
247M    VectorData_0_2748780503246723.4.262144.v0.lsmvecidx.vecpq
59M     VectorData_0_2748780503246723_vecgraph.5.262144.v0.vecgraph
```

##### `quantization=binary`

```bash
5.6G    VectorData_0.1.65536.v0.bucket
140M    VectorData_0_2748779801023527.4.262144.v0.lsmvecidx
59M     VectorData_0_2748779801023527_vecgraph.5.262144.v0.vecgraph
```

#### Findings

- **Recall:** `NONE` and `INT8` stay high (~0.91). `PRODUCT` drops (~0.85) under these PQ defaults (M/K not tuned). `BINARY` is much worse (~0.29).
- **Search speed:** PQ is fastest in-query (≈2.6s vs 7–18s) once built, but recall loss is noticeable. `NONE` and `INT8` are slower than PQ but similar to each other.
- **Index/graph build:** `INT8` builds the graph much faster (~3.1k s) than `NONE`/`PRODUCT` (~5k s). PQ build adds PQ codebook/encoding time but was still slower overall than `INT8`.
- **Memory (RSS):** Peaks are all high (~8.8 GB) and similar across modes; quantization didn’t reduce peak RSS in this run.
- **Disk usage:**
  - Bucket (f32) stays ~5.6 GB for all modes.
  - `NONE` index is tiny (~10–11 MB).
  - `INT8` index is large (~999 MB).
  - `PQ` adds a `.vecpq` file (~247 MB) plus small index (~11 MB).
  - `BINARY` index is moderate (~140 MB).
- **Reopen:** Recall and timings after reopen track pre-close numbers; PQ remains lower recall, `NONE`/`INT8` remain high.
- **Recommendation:** For quality, prefer `NONE` or `INT8`; use PQ only if you need the lowest query latency and can accept lower recall, and consider tuning PQ (M/K) to recover recall. Avoid `BINARY` here given the large recall drop.
- All four of them saved the vectors in the db like `db.schema.get_or_create_property("VectorData", "vector", "ARRAY_OF_FLOATS")`.
- Maybe we should do this differently when quantization is enabled?

#### MSMARCO-1M (1000 queries, Recall@50) with heap size capped at 4GB

- For 1M dataset, I've been doing 8GB heap so far. This time I capped it at 4GB to see how it affects performance.

| quantization | ingest_s | ingest_rss_mb | create_index_s | create_index_rss_mb | build_graph_now_s | build_graph_now_rss_mb | search_s | recall@50_before_close | search_after_reopen_s | search_after_reopen_rss_mb | recall@50_after_reopen | peak_rss_mb | db_size_mb | total_duration |
| :----------- | -------: | ------------: | -------------: | ------------------: | ----------------: | ---------------------: | -------: | ---------------------: | --------------------: | -------------------------: | ---------------------: | ----------: | ---------: | :------------- |
| NONE         |   62.175 |       4004.79 |          16.29 |             122.816 |           6773.81 |                153.227 |   10.238 |                 0.9013 |                  9.87 |                      3.176 |                 0.9013 |     4701.89 |    5750.44 | 1h 54m         |
| INT8         |   62.319 |       3974.97 |         21.722 |              95.438 |            3313.5 |                108.125 |   35.718 |                 0.9083 |                33.318 |                      3.188 |                 0.9066 |     4603.35 |    6738.94 | 58m            |
| PRODUCT      |   61.694 |       3974.34 |         16.053 |             116.758 |           6923.63 |                199.758 |    1.657 |                 0.8608 |                 1.383 |                      5.992 |                 0.8612 |     4723.02 |    5996.45 | 1h 56m         |
| BINARY       |   62.904 |       4014.12 |          27.06 |              87.609 |           4267.63 |                 89.707 |   21.314 |                 0.2923 |                14.683 |                     14.125 |                 0.2923 |     4619.88 |    5879.94 | 1h 13m         |

### Commit/Date: main @ 91a86e3 (Thu Jan 15 10:32:50 2026 -0500)

- Now we have `build_graph_now`, with which we can build the graph index without warmup. This is cleaner than relying on the first search to trigger the build.
- `store_vectors_in_graph` is set to False for all four below tasks. Also `add_hierarchy` is set to True for all four tasks.
- We also varied `batch_size`, which adds vectors in chunks to the database.

#### MSMARCO-1M (1000 queries, Recall@50)

| quantization | batch_size | load_corpus_s | load_corpus_rss_mb | ingest_rss_mb | create_index_s | create_index_rss_mb | build_graph_now_s | build_graph_now_rss_mb | warmup_s | warmup_rss_mb | search_s | search_rss_mb | recall@50_before_close | open_db_s | open_db_rss_mb | warmup_after_reopen_s | warmup_after_reopen_rss_mb | search_after_reopen_s | search_after_reopen_rss_mb | recall@50_after_reopen | peak_rss_mb | db_size_mb | total_duration |
| :----------- | ---------: | ------------: | -----------------: | ------------: | -------------: | ------------------: | ----------------: | ---------------------: | -------: | ------------: | -------: | ------------: | ---------------------: | --------: | -------------: | --------------------: | -------------------------: | --------------------: | -------------------------: | ---------------------: | ----------: | ---------: | :------------- |
| NONE         |     100000 |             0 |                  0 |       8617.99 |         16.339 |                  22 |           4833.32 |                182.383 |    0.045 |         0.605 |   12.037 |        12.238 |                 0.9117 |     3.466 |         13.805 |                10.615 |                      0.145 |                 8.177 |                      8.902 |                 0.9117 |     9335.16 |    5750.44 | 1h 22m         |
| NONE         |      10000 |             0 |                  0 |       7476.79 |         16.505 |             553.051 |           4861.65 |                293.746 |     0.04 |         0.766 |    9.038 |         8.281 |                 0.9076 |     2.305 |          6.645 |                 7.153 |                      2.512 |                 6.775 |                     18.473 |                 0.9076 |     8839.89 |    5750.44 | 1h 22m         |
| INT8         |     100000 |             0 |                  0 |       8583.21 |         21.401 |              74.676 |           2665.78 |                 85.578 |    0.111 |         3.875 |   18.321 |        19.668 |                 0.9015 |    11.946 |         -0.152 |                 4.002 |                      4.363 |                15.725 |                      3.137 |                 0.9015 |     9252.09 |    6738.94 | 46m            |
| INT8         |      10000 |             0 |                  0 |       7554.18 |         22.836 |             138.258 |           2756.29 |                528.305 |     0.17 |         1.504 |   16.344 |        16.941 |                  0.914 |    11.713 |         21.402 |                 4.134 |                       2.91 |                 7.601 |                     11.586 |                 0.9125 |     8763.66 |    6738.94 | 48m            |

#### Findings

- Recall: NONE vs INT8 are within noise (~0.90–0.91), so quantization didn’t change quality much.
- Memory (RSS): Peak RSS tracks batch size (100k lower than 10k); switching NONE↔INT8 didn’t materially reduce peak RSS.
- Disk: INT8 still inflates DB size (e.g., ~6.7GB vs ~5.7GB for NONE; graph/index structures add ~1GB).
- Performance: INT8 builds the graph much faster (minutes vs ~1h+), but costs more on search/open (higher warmup/search times after build/reopen).

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
320K    dictionary.0.327680.v0.dict
59M     VectorData_0_2689535159251959_vecgraph.5.262144.v0.vecgraph
999M    VectorData_0_2689535159251959.4.262144.v0.lsmvecidx
5.6G    VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=True and quantization=INT8

```bash
320K    dictionary.0.327680.v0.dict
999M    VectorData_0_2689534677234566.4.262144.v0.lsmvecidx
3.9G    VectorData_0_2689534677234566_vecgraph.5.262144.v0.vecgraph
5.6G    VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=False and quantization=None

```bash
320K    dictionary.0.327680.v0.dict
11M     VectorData_0_2689535353426837.4.262144.v0.lsmvecidx
59M     VectorData_0_2689535353426837_vecgraph.5.262144.v0.vecgraph
5.6G    VectorData_0.1.65536.v0.bucket
```

##### store_vectors_in_graph=True and quantization=None

```bash
320K    dictionary.0.327680.v0.dict
11M     VectorData_0_2689535105029551.4.262144.v0.lsmvecidx
3.9G    VectorData_0_2689535105029551_vecgraph.5.262144.v0.vecgraph
5.6G    VectorData_0_1.65536.v0.bucket
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
