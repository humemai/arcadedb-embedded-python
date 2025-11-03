## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ./run_benchmark_04_csv_import_documents.sh small p4_b5000 --export'
💾 Export enabled: Databases will be exported to JSONL after import

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


✅ Import complete in 19257.756s
⏱️  Rate: 1,887 records/sec

🔍 Verifying record counts...
  ✅ Movie: 86,537 records
  ✅ Rating: 33,832,162 records
  ✅ Link: 86,537 records
  ✅ Tag: 2,328,315 records

========================================================================
TOTAL SCRIPT RUN TIME: 332m 58s
========================================================================

✅ All benchmarks completed successfully!
bash -c   21459.56s user 116.73s system 108% cpu 5:32:57.29 total


## time bash -c 'ARCADEDB_JVM_MAX_HEAP="8g" ./run_benchmark_05_csv_import_graph.sh small 5000 4 all_6 --export'


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
  Step 7 (Roundtrip):            ✅ PASS

[java_noasync]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7 (Roundtrip):            ✅ PASS

[java_noindex]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7 (Roundtrip):            ✅ PASS

[java_noindex_noasync]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7 (Roundtrip):            ✅ PASS

[sql]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7 (Roundtrip):            ✅ PASS

[sql_noindex]
    Users:  610
    Movies: 9,742
    RATED:  98,734
    TAGGED: 3,494
    Ratings: 223
  ✅ Basic Validation PASSED

  Step 5 (Validation & Queries): ✅ PASS
  Step 6 (Export):               ✅ PASS
  Step 7 (Roundtrip):            ✅ PASS

------------------------------------------------------------------------

MEMORY USAGE SUMMARY:
------------------------------------------------------------------------

[java]
  Peak RSS:  1961.19 MB (actual memory) | Peak VSZ: 17270.48 MB (virtual) | Peak CPU:  394.0%
  Avg  RSS:  1257.64 MB                | Avg  VSZ: 15879.40 MB

[java_noasync]
  Peak RSS:  1907.35 MB (actual memory) | Peak VSZ: 16433.76 MB (virtual) | Peak CPU:  357.0%
  Avg  RSS:  1248.46 MB                | Avg  VSZ: 15179.60 MB

[java_noindex]
  Peak RSS:  1646.19 MB (actual memory) | Peak VSZ: 17077.23 MB (virtual) | Peak CPU:  377.0%
  Avg  RSS:   862.60 MB                | Avg  VSZ: 14898.50 MB

[java_noindex_noasync]
  Peak RSS:  1789.42 MB (actual memory) | Peak VSZ: 16539.32 MB (virtual) | Peak CPU:  431.0%
  Avg  RSS:  1008.38 MB                | Avg  VSZ: 15400.20 MB

[sql]
  Peak RSS:  1705.63 MB (actual memory) | Peak VSZ: 15198.64 MB (virtual) | Peak CPU:  374.0%
  Avg  RSS:  1252.60 MB                | Avg  VSZ: 14157.90 MB

[sql_noindex]
  Peak RSS:  1484.02 MB (actual memory) | Peak VSZ: 15197.51 MB (virtual) | Peak CPU:  369.0%
  Avg  RSS:  1097.83 MB                | Avg  VSZ: 14158.90 MB

------------------------------------------------------------------------

PERFORMANCE SUMMARY:
------------------------------------------------------------------------

[java]
  Vertices: 10,352 in 1.79s
    → 5771 vertices/sec
  Edges: 102,228 in 17.55s
    → 5826 edges/sec
  Creation time: 19.34s (vertices + edges only)

  Export time: 0.68s
  Roundtrip import time: 2.55s
  Total roundtrip time: 3.23s

  Total script time: 28.16s (includes schema, loading, validation)

[java_noasync]
  Vertices: 10,352 in 2.08s
    → 4972 vertices/sec
  Edges: 102,228 in 18.05s
    → 5663 edges/sec
  Creation time: 20.13s (vertices + edges only)

  Export time: 0.72s
  Roundtrip import time: 2.37s
  Total roundtrip time: 3.09s

  Total script time: 29.16s (includes schema, loading, validation)

[java_noindex]
  Vertices: 10,352 in 1.77s
    → 5851 vertices/sec
  Edges: 102,228 in 22.88s
    → 4467 edges/sec
  Creation time: 24.65s (vertices + edges only)

  Export time: 0.50s
  Roundtrip import time: 1.47s
  Total roundtrip time: 1.97s

  Total script time: 32.07s (includes schema, loading, validation)

[java_noindex_noasync]
  Vertices: 10,352 in 1.99s
    → 5208 vertices/sec
  Edges: 102,228 in 22.90s
    → 4464 edges/sec
  Creation time: 24.89s (vertices + edges only)

  Export time: 0.50s
  Roundtrip import time: 1.68s
  Total roundtrip time: 2.17s

  Total script time: 32.28s (includes schema, loading, validation)

[sql]
  Vertices: 10,352 in 1.75s
    → 5915 vertices/sec
  Edges: 102,228 in 19.09s
    → 5356 edges/sec
  Creation time: 20.84s (vertices + edges only)

  Export time: 0.77s
  Roundtrip import time: 2.35s
  Total roundtrip time: 3.11s

  Total script time: 29.57s (includes schema, loading, validation)

[sql_noindex]
  Vertices: 10,352 in 1.69s
    → 6108 vertices/sec
  Edges: 102,228 in 18.32s
    → 5580 edges/sec
  Creation time: 20.02s (vertices + edges only)

  Export time: 0.74s
  Roundtrip import time: 2.23s
  Total roundtrip time: 2.97s

  Total script time: 28.46s (includes schema, loading, validation)

------------------------------------------------------------------------

Full logs saved in: ./benchmark_logs/graph_small_20251103_111331

EXPORTED GRAPH DATABASES:
------------------------------------------------------------------------

  [java] ./benchmark_logs/graph_small_20251103_111331/benchmark_java_db.jsonl.tgz
    Size: 2.11 MB

  [java_noindex] ./benchmark_logs/graph_small_20251103_111331/benchmark_java_noindex_db.jsonl.tgz
    Size: 2.11 MB

  [sql_noindex] ./benchmark_logs/graph_small_20251103_111331/benchmark_sql_noindex_db.jsonl.tgz
    Size: 2.11 MB

  [java_noasync] ./benchmark_logs/graph_small_20251103_111331/benchmark_java_noasync_db.jsonl.tgz
    Size: 2.11 MB

  [java_noindex_noasync] ./benchmark_logs/graph_small_20251103_111331/benchmark_java_noindex_noasync_db.jsonl.tgz
    Size: 2.11 MB

  [sql] ./benchmark_logs/graph_small_20251103_111331/benchmark_sql_db.jsonl.tgz
    Size: 2.11 MB

  Total: 6 export(s), 12.71 MB

  💡 These exports can be used to:
     • Import with: python 05_csv_import_graph.py --import-jsonl <file>
     • Skip CSV import step in future benchmarks
     • Share reproducible benchmark databases

------------------------------------------------------------------------
