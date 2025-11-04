## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ./run_benchmark_04_csv_import_documents.sh small p4_b5000 --export'

========================================================================
CSV Import Benchmarks - 1 Configuration(s)
========================================================================
Dataset: small
Configurations: p4_b5000
Log directory: ./benchmark_logs/csv_import_small_20251103_004240

Dataset directory: ./data/ml-small
  Size: 3.2M

Starting 1 parallel run(s)...

  [1] p4_b5000 (parallel=4, batch=5000) -> p4_b5000.log

All processes started. Waiting for completion...

  ✓ p4_b5000 completed (exit code: 0)

========================================================================
All benchmarks completed!
========================================================================

MEMORY USAGE SUMMARY:
------------------------------------------------------------------------

[p4_b5000]
  Peak RSS:   935.45 MB (actual memory) | Peak VSZ: 14443.56 MB (virtual) | Peak CPU:  308.0%
  Avg  RSS:   479.66 MB                | Avg  VSZ:  9639.78 MB

------------------------------------------------------------------------

PERFORMANCE SUMMARY:
------------------------------------------------------------------------

[p4_b5000]
========================================================================
  Total Python Script Runtime: 0m 5s (5s)
  --------------------------------------------------------------------

  Import Performance:
  --------------------------------------------------------------------
    Movies:      9,742 records in  0.092s →    105,891 records/sec
    Ratings:   100,836 records in  0.208s →    484,788 records/sec
    Links:       9,742 records in  0.026s →    374,692 records/sec
    Tags:        3,683 records in  0.022s →    167,409 records/sec
    TOTAL:     124,003 records in   .348s →    356,330 records/sec (avg)

  Index Creation:
  --------------------------------------------------------------------
    Total time: 0.3s

  Query Performance (WITHOUT indexes):
  --------------------------------------------------------------------
    Find movie by ID:                  0.007s
    Find user's ratings:               0.056s
    Find movie ratings:                0.044s
    Count user's ratings:              0.044s
    Find movies by genre (LIKE):       0.010s
    Count ALL Action movies:           0.007s

  Query Performance (WITH indexes):
  --------------------------------------------------------------------
    Find movie by ID:                  0.000s
    Find user's ratings:               0.005s
    Find movie ratings:                0.000s
    Count user's ratings:              0.003s
    Find movies by genre (LIKE):       0.001s
    Count ALL Action movies:           0.008s

  Baseline Validation:
  --------------------------------------------------------------------
    Step  8 (BEFORE indexes):  ✅ PASS - All results match baseline
    Step 10 (AFTER indexes):   ✅ PASS - All results match baseline
    Step 14 (AFTER roundtrip): ✅ PASS - All results match baseline

    FINAL VALIDATION:          ✅ SUCCESS - All query runs consistent

========================================================================

------------------------------------------------------------------------

Full logs saved in: ./benchmark_logs/csv_import_small_20251103_004240

EXPORTED DATABASES:
------------------------------------------------------------------------

  [p4_b5000] ./benchmark_logs/csv_import_small_20251103_004240/p4_b5000.jsonl.tgz (1.61 MB)

------------------------------------------------------------------------


========================================================================
TOTAL SCRIPT RUN TIME: 0m 5s
========================================================================

Moving exports to log directory...

✅ All benchmarks completed successfully!
bash -c   14.54s user 1.30s system 296% cpu 5.346 total


## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ./run_benchmark_04_csv_import_documents.sh large p4_b50000 --export'

========================================================================
CSV Import Benchmarks - 1 Configuration(s)
========================================================================
Dataset: large
Configurations: p4_b50000
Log directory: ./benchmark_logs/csv_import_large_20251103_005914

Dataset directory: ./data/ml-large
  Size: 971M

Starting 1 parallel run(s)...

  [1] p4_b50000 (parallel=4, batch=50000) -> p4_b50000.log

All processes started. Waiting for completion...

  ✓ p4_b50000 completed (exit code: 0)

========================================================================
All benchmarks completed!
========================================================================

MEMORY USAGE SUMMARY:
------------------------------------------------------------------------

[p4_b50000]
  Peak RSS: 10416.48 MB (actual memory) | Peak VSZ: 17359.83 MB (virtual) | Peak CPU:  320.0%
  Avg  RSS:  8880.80 MB                | Avg  VSZ: 16779.40 MB

------------------------------------------------------------------------

PERFORMANCE SUMMARY:
------------------------------------------------------------------------

[p4_b50000]
========================================================================
  Total Python Script Runtime: 332m 56s (19976s)
  --------------------------------------------------------------------

  Import Performance:
  --------------------------------------------------------------------
    Movies:     86,537 records in  0.300s →    288,457 records/sec
    Ratings:  33,832,162 records in 37.226s →    908,832 records/sec
    Links:      86,537 records in  0.124s →    697,879 records/sec
    Tags:     2,328,315 records in  3.150s →    739,148 records/sec
    TOTAL:    36,333,551 records in 40.800s →    890,528 records/sec (avg)

  Index Creation:
  --------------------------------------------------------------------
    Total time: 53.1s

  Query Performance (WITHOUT indexes):
  --------------------------------------------------------------------
    Find movie by ID:                  0.041s
    Find user's ratings:              15.008s
    Find movie ratings:               15.330s
    Count user's ratings:             14.872s
    Find movies by genre (LIKE):       0.063s
    Count ALL Action movies:           0.061s

  Query Performance (WITH indexes):
  --------------------------------------------------------------------
    Find movie by ID:                  0.000s
    Find user's ratings:               0.001s
    Find movie ratings:                0.060s
    Count user's ratings:              0.000s
    Find movies by genre (LIKE):       0.001s
    Count ALL Action movies:           0.059s

  Index Speedup Summary:
  --------------------------------------------------------------------

  Baseline Validation:
  --------------------------------------------------------------------
    Step  8 (BEFORE indexes):  ✅ PASS - All results match baseline
    Step 10 (AFTER indexes):   ✅ PASS - All results match baseline
    Step 14 (AFTER roundtrip): ✅ PASS - All results match baseline

    FINAL VALIDATION:          ✅ SUCCESS - All query runs consistent

========================================================================

✅ Export complete!
  • Total records: 36,333,551
  • Vertices: 0
  • Edges: 0
  • Documents: 36,333,551
⏱️  Time: 78.707s
📦 File size: 458.53 MB


✅ Import complete in 19257.756s (320m)
⏱️  Rate: 1,887 records/sec

🔍 Verifying record counts...
  ✅ Movie: 86,537 records
  ✅ Rating: 33,832,162 records
  ✅ Link: 86,537 records
  ✅ Tag: 2,328,315 records

========================================================================
TOTAL SCRIPT RUN TIME: 332m 58s (most of it is from importing)
========================================================================

✅ All benchmarks completed successfully!
bash -c   21459.56s user 116.73s system 108% cpu 5:32:57.29 total


## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ARCADEDB_JVM_ARGS="-Xms8g" ./run_benchmark_05_csv_import_graph.sh small 5000 4 all_6 --export'


========================================================================
Graph Creation Benchmarks - 6 Method(s)
========================================================================
Dataset: small
Batch size: 5000
Parallel level: 4
Methods: java java_noindex sql_noindex java_noasync java_noindex_noasync sql
Log directory: ./benchmark_logs/graph_small_20251103_201213

Source database: ./my_test_databases/ml_small_db
  Size: 13M

Cleaning up any existing database copies...
Creating temporary database copies for parallel runs...
  (this may take a few minutes for large datasets)

  ✓ Created copy 1
  ✓ Created copy 2
  ✓ Created copy 3
  ✓ Created copy 4
  ✓ Created copy 5
  ✓ Created copy 6

Starting 6 parallel run(s)...

  [1] java (Java API + async)        (PID: 2677179) -> java.log
  [2] java_noasync (Java API, sync)  (PID: 2677187) -> java_noasync.log
  [3] sql (SQL, always sync)         (PID: 2677195) -> sql.log
  [4] java_noindex (no idx + async)  (PID: 2677203) -> java_noindex.log
  [5] java_noindex_noasync (no idx, sync) (PID: 2677211) -> java_noindex_noasync.log
  [6] sql_noindex (no idx, sync)     (PID: 2677219) -> sql_noindex.log

All processes started. Waiting for completion...

  ✓ java completed (exit code: 0)
  ✓ java_noindex completed (exit code: 0)
  ✓ sql_noindex completed (exit code: 0)
  ✓ java_noasync completed (exit code: 0)
  ✓ java_noindex_noasync completed (exit code: 0)
  ✓ sql completed (exit code: 0)

========================================================================
All benchmarks completed!
========================================================================

VALIDATION RESULTS:
------------------------------------------------------------------------

[java]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

[java_noasync]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

[java_noindex]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

[java_noindex_noasync]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

[sql]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

[sql_noindex]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7a (Roundtrip Import):    ✅ PASS
  Step 7b (Roundtrip V&Q):       ✅ PASS

------------------------------------------------------------------------

MEMORY USAGE SUMMARY:
------------------------------------------------------------------------

[java]
  Peak RSS:  5729.23 MB (actual memory) | Peak VSZ: 16762.43 MB (virtual) | Peak CPU:  347.0%
  Avg  RSS:  4043.02 MB                | Avg  VSZ: 15395.20 MB

[java_noasync]
  Peak RSS:  5674.36 MB (actual memory) | Peak VSZ: 15266.72 MB (virtual) | Peak CPU:  378.0%
  Avg  RSS:  3806.48 MB                | Avg  VSZ: 12588.10 MB

[java_noindex]
  Peak RSS:  5089.56 MB (actual memory) | Peak VSZ: 16825.78 MB (virtual) | Peak CPU:  420.0%
  Avg  RSS:  3213.14 MB                | Avg  VSZ: 15463.40 MB

[java_noindex_noasync]
  Peak RSS:  5663.47 MB (actual memory) | Peak VSZ: 15202.89 MB (virtual) | Peak CPU:  403.0%
  Avg  RSS:  3344.81 MB                | Avg  VSZ: 13812.80 MB

[sql]
  Peak RSS:  5617.58 MB (actual memory) | Peak VSZ: 15136.93 MB (virtual) | Peak CPU:  424.0%
  Avg  RSS:  4154.10 MB                | Avg  VSZ: 13842.70 MB

[sql_noindex]
  Peak RSS:  5718.95 MB (actual memory) | Peak VSZ: 15266.94 MB (virtual) | Peak CPU:  381.0%
  Avg  RSS:  3990.13 MB                | Avg  VSZ: 13953.20 MB

------------------------------------------------------------------------

PERFORMANCE SUMMARY:
------------------------------------------------------------------------

[java]
  Vertices: 10,352 in 2.32s
    → 4453 vertices/sec
  Edges: 102,228 in 15.69s
    → 6516 edges/sec
  Creation time: 18.01s (vertices + edges only)

  Export time: 0.66s
  Roundtrip import time: 1.78s
  Total roundtrip time: 2.44s

  Total script time: 26.76s (includes schema, loading, validation)

[java_noasync]
  Vertices: 10,352 in 0.90s
    → 11528 vertices/sec
  Edges: 102,228 in 14.76s
    → 6927 edges/sec
  Creation time: 15.65s (vertices + edges only)

  Export time: 0.62s
  Roundtrip import time: 1.79s
  Total roundtrip time: 2.41s

  Total script time: 24.14s (includes schema, loading, validation)

[java_noindex]
  Vertices: 10,352 in 2.43s
    → 4255 vertices/sec
  Edges: 102,228 in 16.64s
    → 6143 edges/sec
  Creation time: 19.07s (vertices + edges only)

  Export time: 0.63s
  Roundtrip import time: 1.62s
  Total roundtrip time: 2.25s

  Total script time: 27.05s (includes schema, loading, validation)

[java_noindex_noasync]
  Vertices: 10,352 in 0.83s
    → 12514 vertices/sec
  Edges: 102,228 in 15.11s
    → 6766 edges/sec
  Creation time: 15.94s (vertices + edges only)

  Export time: 0.61s
  Roundtrip import time: 1.81s
  Total roundtrip time: 2.42s

  Total script time: 24.46s (includes schema, loading, validation)

[sql]
  Vertices: 10,352 in 2.12s
    → 4882 vertices/sec
  Edges: 102,228 in 20.63s
    → 4956 edges/sec
  Creation time: 22.75s (vertices + edges only)

  Export time: 0.47s
  Roundtrip import time: 1.47s
  Total roundtrip time: 1.94s

  Total script time: 29.71s (includes schema, loading, validation)

[sql_noindex]
  Vertices: 10,352 in 1.92s
    → 5383 vertices/sec
  Edges: 102,228 in 19.57s
    → 5225 edges/sec
  Creation time: 21.49s (vertices + edges only)

  Export time: 0.50s
  Roundtrip import time: 1.63s
  Total roundtrip time: 2.14s

  Total script time: 29.14s (includes schema, loading, validation)

------------------------------------------------------------------------

Full logs saved in: ./benchmark_logs/graph_small_20251103_201213

========================================================================
TOTAL SCRIPT RUN TIME: 0m 31s
========================================================================

Moving exports from working directories...
  ✓ Moved benchmark_java_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/
  ✓ Moved benchmark_java_noindex_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/
  ✓ Moved benchmark_sql_noindex_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/
  ✓ Moved benchmark_java_noasync_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/
  ✓ Moved benchmark_java_noindex_noasync_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/
  ✓ Moved benchmark_sql_db.jsonl.tgz to ./benchmark_logs/graph_small_20251103_201213/

EXPORTED GRAPH DATABASES:
------------------------------------------------------------------------

  [java] ./benchmark_logs/graph_small_20251103_201213/benchmark_java_db.jsonl.tgz
    Size: 2.11 MB

  [java_noindex] ./benchmark_logs/graph_small_20251103_201213/benchmark_java_noindex_db.jsonl.tgz
    Size: 2.11 MB

  [sql_noindex] ./benchmark_logs/graph_small_20251103_201213/benchmark_sql_noindex_db.jsonl.tgz
    Size: 2.11 MB

  [java_noasync] ./benchmark_logs/graph_small_20251103_201213/benchmark_java_noasync_db.jsonl.tgz
    Size: 2.11 MB

  [java_noindex_noasync] ./benchmark_logs/graph_small_20251103_201213/benchmark_java_noindex_noasync_db.jsonl.tgz
    Size: 2.11 MB

  [sql] ./benchmark_logs/graph_small_20251103_201213/benchmark_sql_db.jsonl.tgz
    Size: 2.11 MB

  Total: 6 export(s), 12.71 MB

  💡 These exports can be used to:
     • Import with: python 05_csv_import_graph.py --import-jsonl <file>
     • Skip CSV import step in future benchmarks
     • Share reproducible benchmark databases

------------------------------------------------------------------------

Cleaning up temporary databases...
  ✓ Removed ml_small_db_copy1
  ✓ Removed ml_small_db_copy2
  ✓ Removed ml_small_db_copy3
  ✓ Removed ml_small_db_copy4
  ✓ Removed ml_small_db_copy5
  ✓ Removed ml_small_db_copy6
  ✓ Removed ./benchmark_work
✓ Cleanup complete

✅ All benchmarks completed successfully!
bash -c   343.31s user 24.21s system 1205% cpu 30.489 total

## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ARCADEDB_JVM_ARGS="-Xms8g" ./run_benchmark_05_csv_import_graph.sh large 50000 4 all_6 --export'

========================================================================
All benchmarks completed!
========================================================================

MEMORY USAGE SUMMARY:
------------------------------------------------------------------------

[java]
  Peak RSS: 18876.22 MB (actual memory) | Peak VSZ: 26961.45 MB (virtual) | Peak CPU:  360.0%
  Avg  RSS: 14685.70 MB                | Avg  VSZ: 22050.20 MB

[java_noasync]
  Peak RSS: 16363.84 MB (actual memory) | Peak VSZ: 24492.47 MB (virtual) | Peak CPU:  361.0%
  Avg  RSS: 13512.80 MB                | Avg  VSZ: 21583.10 MB

[java_noindex]
  Peak RSS: 18695.65 MB (actual memory) | Peak VSZ: 25860.61 MB (virtual) | Peak CPU:  368.0%
  Avg  RSS: 14520.20 MB                | Avg  VSZ: 21822.30 MB

[java_noindex_noasync]
  Peak RSS: 16027.85 MB (actual memory) | Peak VSZ: 22382.91 MB (virtual) | Peak CPU:  324.0%
  Avg  RSS: 12356.00 MB                | Avg  VSZ: 18787.60 MB

[sql]
  Peak RSS: 16332.41 MB (actual memory) | Peak VSZ: 24492.21 MB (virtual) | Peak CPU:  369.0%
  Avg  RSS: 13192.10 MB                | Avg  VSZ: 21472.40 MB

[sql_noindex]
  Peak RSS: 15991.26 MB (actual memory) | Peak VSZ: 22474.84 MB (virtual) | Peak CPU:  362.0%
  Avg  RSS: 12311.20 MB                | Avg  VSZ: 18657.50 MB

------------------------------------------------------------------------

PERFORMANCE SUMMARY:
------------------------------------------------------------------------

[java]
  Vertices: 417,512 in 169.07s
    → 2469 vertices/sec
  Edges: 35,367,522 in 17388.65s
    → 2034 edges/sec
  Creation time: 17557.72s (vertices + edges only)

  Export time: 122.53s
  Roundtrip import time: 1365.41s
  Total roundtrip time: 1487.94s

  Total script time: 19543.22s (includes schema, loading, validation)

[java_noasync]
  Vertices: 417,512 in 33.83s
    → 12341 vertices/sec
  Edges: 35,367,522 in 6974.16s
    → 5071 edges/sec
  Creation time: 7007.99s (vertices + edges only)

  Export time: 134.73s
  Roundtrip import time: 3050.36s
  Total roundtrip time: 3185.09s

  Total script time: 10735.51s (includes schema, loading, validation)

[java_noindex]
  Vertices: 417,512 in 156.85s
    → 2662 vertices/sec
  Edges: 35,367,522 in 43149.06s
    → 820 edges/sec
  Creation time: 43305.91s (vertices + edges only)

  Export time: 120.06s
  Roundtrip import time: 1079.20s
  Total roundtrip time: 1199.26s

  Total script time: 44954.12s (includes schema, loading, validation)

[java_noindex_noasync]
  Vertices: 417,512 in 32.03s
    → 13036 vertices/sec
  Edges: 35,367,522 in 19232.25s
    → 1839 edges/sec
  Creation time: 19264.28s (vertices + edges only)

  Export time: 115.93s
  Roundtrip import time: 1575.77s
  Total roundtrip time: 1691.71s

  Total script time: 21394.38s (includes schema, loading, validation)

[sql]
  Vertices: 417,512 in 47.80s
    → 8734 vertices/sec
  Edges: 35,367,522 in 9335.14sS
    → 3789 edges/sec
  Creation time: 9382.94s (vertices + edges only)

  Export time: 187.54s
  Roundtrip import time: 1783.64s
  Total roundtrip time: 1971.18s

  Total script time: 11916.97s (includes schema, loading, validation)

[sql_noindex]
  Vertices: 417,512 in 46.90s
    → 8902 vertices/sec
  Edges: 35,367,522 in 19950.98s
    → 1773 edges/sec
  Creation time: 19997.88s (vertices + edges only)

  Export time: 124.27s
  Roundtrip import time: 1549.20s
  Total roundtrip time: 1673.46s

  Total script time: 22089.37s (includes schema, loading, validation)

EXPORTED GRAPH DATABASES:
------------------------------------------------------------------------

  [java] ./benchmark_logs/graph_large_20251103_201537/benchmark_java_db.jsonl.tgz
    Size: 670.26 MB

  [java_noindex] ./benchmark_logs/graph_large_20251103_201537/benchmark_java_noindex_db.jsonl.tgz
    Size: 670.26 MB

  [sql_noindex] ./benchmark_logs/graph_large_20251103_201537/benchmark_sql_noindex_db.jsonl.tgz
    Size: 670.26 MB

  [java_noasync] ./benchmark_logs/graph_large_20251103_201537/benchmark_java_noasync_db.jsonl.tgz
    Size: 670.26 MB

  [java_noindex_noasync] ./benchmark_logs/graph_large_20251103_201537/benchmark_java_noindex_noasync_db.jsonl.tgz
    Size: 670.26 MB

  [sql] ./benchmark_logs/graph_large_20251103_201537/benchmark_sql_db.jsonl.tgz
    Size: 670.26 MB
