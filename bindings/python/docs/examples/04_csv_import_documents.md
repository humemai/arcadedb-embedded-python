# Example 04: CSV Import - Tables (Documents)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/04_csv_import_documents.py){ .md-button }

**Bulk CSV import with explicit schema mapping, WAL-off ingest, NULL handling, and index
optimization**

## Overview

This example demonstrates importing real-world CSV data from the MovieLens dataset into
ArcadeDB documents. You'll learn production-ready patterns for:

- **Explicit schema mapping** - Each document type's columns are mapped to fixed
  ArcadeDB types (LONG, DOUBLE, STRING)
- **Bulk INSERT ingest** - Python parses the CSV and runs batched `INSERT INTO ... SET`
- **WAL-off ingest** - WAL is disabled during the bulk load, then re-enabled
- **NULL value handling** - Import and query missing data across all types
- **Batch processing** - Optimize import performance with commit batching
- **Index optimization** - Create indexes AFTER import for maximum throughput
- **Performance analysis** - Measure query speedup with statistical validation
- **Result validation** - Verify indexes return identical results with actual data samples
- **Optional export/roundtrip** - Export to JSONL and re-import to validate integrity

## What You'll Learn

- Explicit per-type schema mapping (LONG, DOUBLE, STRING)
- Bulk INSERT ingest from Python via `csv.DictReader` + batched `db.command("sql", ...)`
- NULL value import from empty CSV cells
- Query performance measurement (10 runs with statistics)
- Index creation timing (before vs after import)
- Full-text (Lucene) indexing on the genres field
- **Result validation with actual data samples**
- Optional JSONL export and `IMPORT DATABASE` roundtrip validation

## Prerequisites

**1. Install ArcadeDB Python bindings:**

```bash
uv pip install arcadedb-embedded
```

**2. Dataset download (automatic):**

The example automatically downloads the dataset if it doesn't exist. You can also
download it manually:

```bash
cd bindings/python/examples
python download_data.py movielens-large # movielens large dataset
python download_data.py movielens-small # movielens small dataset
```

**Note:** You must download the dataset before running this example if the auto-download is disabled or blocked by your environment.

**Two dataset sizes available:**

- **movielens-large**: ~86,000 movies, ~33M ratings (~265 MB) - Realistic performance testing
- **movielens-small**: ~9,700 movies, ~100,000 ratings (~1 MB) - Quick testing

Empty cells in the CSV files are imported as SQL NULL. After each file is loaded the
example counts NULLs in the columns that can be empty:

- `movies.csv`: NULL `genres`
- `ratings.csv`: NULL `timestamp`
- `links.csv`: NULL `imdbId`, NULL `tmdbId`
- `tags.csv`: NULL `tag`

## Dataset Structure

Each dataset has 4 CSV files imported into 4 document types:

| File | Columns | Document type |
|------|---------|---------------|
| `movies.csv` | movieId, title, genres | `Movie` |
| `ratings.csv` | userId, movieId, rating, timestamp | `Rating` |
| `links.csv` | movieId, imdbId, tmdbId | `Link` |
| `tags.csv` | userId, movieId, tag, timestamp | `Tag` |

**movielens-large**: ~86K movies, ~33M ratings (~265 MB).
**movielens-small**: ~9K movies, ~100K ratings (~1 MB).

For quick testing, use: `python download_data.py movielens-small`

## Usage

```bash
# Basic usage (large dataset by default)
python 04_csv_import_documents.py

# Use small dataset for quick testing
python 04_csv_import_documents.py --dataset movielens-small

# Configure parallel threads and batch size
python 04_csv_import_documents.py --parallel 8 --batch-size 10000

# Export database for reproducibility
python 04_csv_import_documents.py --export

# See all options
python 04_csv_import_documents.py --help
```

**Key options:**

- `--dataset {movielens-small,movielens-large}` - Dataset size (default: movielens-large)
- `--parallel PARALLEL` - Number of parallel import threads (default: auto-detect)
- `--batch-size BATCH_SIZE` - Records per commit batch (default: 5000)
- `--export` - Export database to JSONL after import
- `--db-name DB_NAME` - Custom database name (default: movielens_{size}_db)

**Recommendations:**

- Parallel threads: 4-8 for best performance (auto-detected by default)
- Batch size: 5000-50000 (larger = faster imports, more memory)
- Export: Use `--export` to create reproducible benchmark databases

## Explicit Schema Mapping

The example defines an **explicit schema** for each document type before ingest. Columns
are mapped to fixed ArcadeDB types in `import_csv_documents_via_sql()`:

### Schema mapping (`schema_by_type`)

```
📋 Movie (movies.csv):
   • movieId: LONG
   • title: STRING
   • genres: STRING

📋 Rating (ratings.csv):
   • userId: LONG
   • movieId: LONG
   • rating: DOUBLE
   • timestamp: LONG

📋 Link (links.csv):
   • movieId: LONG
   • imdbId: LONG
   • tmdbId: LONG

📋 Tag (tags.csv):
   • userId: LONG
   • movieId: LONG
   • tag: STRING
   • timestamp: LONG
```

The script creates each document type with `CREATE DOCUMENT TYPE`, then issues one
`CREATE PROPERTY` per column with these types. During parsing, empty cells become
`None` (SQL NULL), LONG columns are parsed with `int()`, and DOUBLE columns with
`float()`.

## Code Walkthrough

### Step 0: Check Dataset Availability (auto-download)

```python
data_dir = Path(__file__).parent / "data" / args.dataset
if not check_dataset_exists(data_dir):
    print(f"❌ Dataset not found at: {data_dir}")
    download_dataset(args.dataset)  # runs download_data.py as a subprocess
```

`check_dataset_exists()` verifies that `movies.csv`, `ratings.csv`, `links.csv`, and
`tags.csv` are all present; if not, the script downloads the dataset automatically.

### Enable WAL-off ingest mode

Before importing, the script puts the database into a faster bulk-load mode and disables
WAL on the async executor:

```python
db.set_read_your_writes(False)
async_exec = db.async_executor()
async_exec.set_commit_every(args.batch_size)
async_exec.set_transaction_use_wal(False)
```

WAL is re-enabled after the ratings import (`set_transaction_use_wal(True)` and
`set_read_your_writes(True)`).

### Import CSV files with bulk INSERT

`import_csv_documents_via_sql(database, csv_path, doc_type)` creates the document type
and its properties from the explicit schema, then parses the CSV with `csv.DictReader`
and runs batched `INSERT INTO ... SET ... = ?` statements inside transactions
(flushing every `args.batch_size` rows):

```python
stats = import_csv_documents_via_sql(db, movies_csv, "Movie")

# Check for NULL values (using .first() for efficiency)
null_genres = (
    db.query("sql", "SELECT count(*) as c FROM Movie WHERE genres IS NULL")
    .first()
    .get("c")
)

if null_genres > 0:
    print(f"   🔍 NULL values detected:")
    print(f"      • genres: {null_genres:,} NULL values ({null_genres/stats['documents']*100:.1f}%)")
    print("   💡 Empty CSV cells correctly imported as SQL NULL")
```

The function returns a dict with `documents` (row count via `SELECT count(*)`),
`errors`, and `duration_ms`; the script then prints the records/sec rate for each file.

### Step 8: Query Performance WITHOUT Indexes

```python
TEST_QUERIES = [
    ("Find movie by ID", "SELECT FROM Movie WHERE movieId = 500"),
    ("Find user's ratings", "SELECT FROM Rating WHERE userId = 414 ORDER BY movieId, rating LIMIT 10"),
    ("Find movie ratings", "SELECT FROM Rating WHERE movieId = 500 ORDER BY userId, rating LIMIT 10"),
    ("Count user's ratings", "SELECT count(*) as count FROM Rating WHERE userId = 414"),
    ("Find movies by genre (LIKE with LIMIT)", "SELECT FROM Movie WHERE genres LIKE '%Action%' ORDER BY movieId LIMIT 10"),
    ("Count ALL Action movies (LIKE, no LIMIT)", "SELECT count(*) as count FROM Movie WHERE genres LIKE '%Action%'"),
]

# Run each query 10 times for statistical reliability
for query_name, query in test_queries:
    run_times = []
    for _ in range(10):
        query_start = time.time()
        result = list(db.query("sql", query))
        run_times.append(time.time() - query_start)

    avg_time = statistics.mean(run_times)
    std_time = statistics.stdev(run_times)
    print(f"   📊 {query_name}:")
    print(f"      Average: {avg_time*1000:.2f}ms ± {std_time*1000:.2f}ms")
```

### Step 9: Create Indexes (AFTER Import)

The script first calls `wait_for_compaction()`, then creates these indexes via the
`create_indexes()` helper (which retries on compaction/index conflicts):

```python
indexes = [
    ("Movie", "movieId", "UNIQUE"),
    ("Movie", "genres", "FULL_TEXT"),   # Lucene full-text search on genres
    ("Rating", "userId", "NOTUNIQUE"),
    ("Rating", "movieId", "NOTUNIQUE"),
    ("Link", "movieId", "UNIQUE"),
    ("Tag", "movieId", "NOTUNIQUE"),
]
success_count, failed_indexes = create_indexes(db, indexes)
```

After creation the script queries `schema:indexes` and validates that every expected
index exists, raising `RuntimeError` if any are missing.

**Why create indexes AFTER import?**

- 2-3x faster total time
- Indexes built in one pass
- Fully compacted from start
- Production best practice

### Step 10: Query Performance WITH Indexes

Same queries, now with indexes active. Results show dramatic speedup!

## Performance Results

### Query Speedup Summary

```
🚀 Performance Improvement Summary:
======================================================================
Query                          Before (s)      After (s)       Speedup
======================================================================
Find movie by ID               0.039±0.008     0.001±0.002     58.1x
      (98.3% time saved)
...
======================================================================
```

The exact numbers vary by machine and dataset. Each query's average and standard
deviation are printed in seconds (formatted as `avg±std`), along with the speedup and
percent time saved. Times are measured over 10 runs per query (`num_runs=10`).

**Key findings:**

- ✅ Single-column and `NOTUNIQUE` indexes can yield large lookup/count speedups
- ✅ Standard deviation shows **query stability**
- ✅ `LIKE` scans without a LIMIT (e.g. counting all Action movies) may not speed up

## NULL Value Handling

The example demonstrates NULL handling: empty CSV cells are imported as SQL NULL, and
after each file the script counts NULLs in columns that can be empty (`genres`,
`timestamp`, `imdbId`, `tmdbId`, `tag`).

### Import Results (illustrative format)

```
Step 2: Importing movies.csv → Movie documents...
   ✅ Imported <N> movies
   💡 Errors: 0
   🔍 NULL values detected:
      • genres: <count> NULL values (<pct>%)
   💡 Empty CSV cells correctly imported as SQL NULL
```

Each import step prints the imported count, the error count, the elapsed time, and the
records/sec rate; NULL detection is printed only when the relevant column has NULLs.

### NULL Values in Aggregations

In Step 12, NULL `tag` or `genres` values surface as `'None'` in the
`GROUP BY` aggregation output (because Python `str(None)` is `'None'`); NULL `rating`
values are printed on a dedicated `NULL` line in the rating distribution.

## Index Architecture

ArcadeDB exposes multiple index engines (LSM_TREE, HASH, FULL_TEXT, VECTOR). The
default `UNIQUE` / `NOTUNIQUE` indexes use the **LSM-Tree (Log-Structured Merge Tree)**
backend, while the `genres` index in this example uses the Lucene-backed `FULL_TEXT`
engine.

### How LSM-Tree Works

**Architecture:**
```
LSMTreeIndex
├── Mutable Buffer (in-memory)
│   └── Recent writes, fast inserts
│
└── Compacted Storage (disk)
    └── Sorted, immutable data
```

**Key advantages:**

- **Write-optimized**: Sequential writes to memory buffer (perfect for bulk imports)
- **Type-agnostic**: Same structure for all types, type-aware comparison during lookups
- **Auto-compaction**: Background merging keeps data sorted and compact
- **Transaction-friendly**: Buffers writes until commit

### Type Performance & Storage

**Binary serialization per type:**

| Type | Storage Size | Comparison Speed | Best For |
|------|--------------|------------------|----------|
| BYTE | 1 byte | ⚡ Very fast | Flags, small counts (0-255) |
| SHORT | 2 bytes | ⚡ Very fast | Medium numbers (-32K to 32K) |
| INTEGER | 4 bytes | ⚡ Very fast | IDs, standard numbers (up to 2B) |
| LONG | 8 bytes | ⚡ Very fast | Large IDs, timestamps |
| FLOAT | 4 bytes | ⚡ Fast | Small decimals (7-digit precision) |
| DOUBLE | 8 bytes | ⚡ Fast | Standard decimals (15-digit precision) |
| DATE/DATETIME | 8 bytes (as LONG) | ⚡ Fast | Timestamps, dates |
| STRING | Variable | 🐌 Slower | Text, byte-by-byte comparison |
| DECIMAL | Variable | 🐌 Slowest | Exact precision (e.g., money) |

**Index space example** (100K records):

- BYTE: 100KB | SHORT: 200KB | **INTEGER: 400KB** (best balance) | LONG: 800KB | STRING(20): 2MB+

**Why this matters:**

- Smaller types = more keys per page = better cache performance
- Fixed-size types = faster comparison = better query speed
- Choose INTEGER for most IDs (handles 2 billion values, compact, fast)

## Analysis Queries

The example includes comprehensive data analysis:

### Record Counts

```python
SELECT count(*) as count FROM Movie
SELECT count(*) as count FROM Rating
SELECT count(*) as count FROM Link
SELECT count(*) as count FROM Tag
```

### Rating Statistics

```python
SELECT
    count(*) as total_ratings,
    avg(rating) as avg_rating,
    min(rating) as min_rating,
    max(rating) as max_rating
FROM Rating
```

### Rating Distribution

```python
SELECT rating, count(*) as count
FROM Rating
GROUP BY rating
ORDER BY rating
```

### Top Genres

```python
SELECT genres, count(*) as count
FROM Movie
WHERE genres <> '(no genres listed)'
GROUP BY genres
ORDER BY count DESC
LIMIT 10
```

### Most Active Users

```python
SELECT userId, count(*) as rating_count
FROM Rating
GROUP BY userId
ORDER BY rating_count DESC
LIMIT 10
```

Step 12 also prints sample movies, the top 10 most-tagged movies (with titles looked
up by `movieId`), and the top 10 most common tags.

## Best Practices Demonstrated

### ✅ Explicit Schema Mapping

- Each document type's columns are mapped to fixed types in `schema_by_type`
- LONG for integer-like columns, DOUBLE for decimals, STRING for text
- Schema is created with `CREATE DOCUMENT TYPE` + `CREATE PROPERTY` before ingest

### ✅ Schema Definition

- Define schema BEFORE import (validation + optimization)
- Use explicit property types (no guessing)
- Choose appropriate types for data ranges

### ✅ Import Optimization

- Bulk `INSERT INTO ... SET` with batched commits (every `args.batch_size` rows)
- WAL disabled during ingest (`set_transaction_use_wal(False)`), re-enabled afterward
- Larger batches = faster imports (balance with memory); `--batch-size` defaults to 5000

### ✅ Index Strategy

- **CREATE INDEXES AFTER IMPORT** (avoids per-insert index maintenance)
- Wait for background compaction first (`wait_for_compaction()`)
- Use `UNIQUE` / `NOTUNIQUE` (LSM-tree) indexes and a `FULL_TEXT` index on `genres`
- Retry index creation on compaction/index conflicts (`create_indexes()` helper)

### ✅ Performance Measurement

- Run queries 10 times for statistical reliability
- Calculate average, standard deviation, min, max
- Compare before/after index performance
- Measure speedup percentages

### ✅ NULL Handling

- Empty CSV cells → SQL NULL automatically
- Check NULL counts after import
- NULL values appear in aggregations (as 'None' string)
- Support NULL across all types (STRING, INTEGER, etc.)

## Running the Example

```bash
cd bindings/python/examples

# Use default (large) dataset - downloads automatically if needed
python 04_csv_import_documents.py

# Use small dataset for quick testing - downloads automatically if needed
python 04_csv_import_documents.py --dataset movielens-small

# Use large dataset explicitly
python 04_csv_import_documents.py --dataset movielens-large

# With custom JVM heap for large datasets
python 04_csv_import_documents.py --dataset movielens-large --heap-size 8g
```

**Command-line options:**

- `--dataset {movielens-small,movielens-large}` - Dataset size to use (default: movielens-large)
- `--heap-size SIZE` - JVM max heap size (e.g. `8g`, `4096m`)
- The script automatically downloads the dataset if it doesn't exist

**Expected output:**

- Automatic dataset download if needed
- Step-by-step import progress (Steps 0-14)
- NULL value detection for all 4 files
- Performance statistics (before/after indexes, 10 runs each)
- Index creation and validation against `schema:indexes`
- Data analysis queries with results
- Full-text search demonstration on `genres`
- Optional JSONL export and roundtrip validation (with `--export`)
- Total script run time printed at the end (varies by machine/dataset)

**Database location:**

- Small dataset: `./my_test_databases/movielens_small_db/`
- Large dataset: `./my_test_databases/movielens_large_db/`
- Custom: `./my_test_databases/{--db-name}/`

The database is preserved for inspection after the example completes.

⚠️ **Note**: The database directory is larger than the source CSVs due to:

- Index structures (LSM-tree and Lucene full-text)
- Transaction logs and metadata
- Internal data structures for document storage
- WAL (Write-Ahead Log) files for durability

## Key Takeaways

1. ✅ **Explicit schema mapping** assigns LONG/DOUBLE/STRING per column before ingest
2. ✅ **Bulk INSERT ingest** with WAL disabled during the load (re-enabled afterward)
3. ✅ **NULL value handling** works across types - empty CSV cells become SQL NULL
4. ✅ **Batch processing** (`--batch-size` / `commitEvery`) improves import performance
5. ✅ **Create indexes AFTER import** - avoids per-insert index maintenance
6. ✅ **Indexes** provide large speedups for lookups and counts. For exact-match
   lookups, prefer `UNIQUE_HASH` / `NOTUNIQUE_HASH`; for ranges and ordered scans,
   prefer `UNIQUE` / `NOTUNIQUE` (`LSM_TREE`).
7. ✅ **Statistical validation** (10 runs) ensures reliable performance measurements
8. ✅ **Result validation** compares actual data values against an embedded baseline
9. ✅ **Optional export/import roundtrip** (`--export`) verifies data integrity
10. ✅ **Database persistence** - reopen and query immediately, no rebuild needed!

## Next Steps

- **Try Example 05**: Graph import (MovieLens as vertices and edges)
- **Experiment**: Modify `--batch-size` to see performance impact
- **Add queries**: Try your own analysis queries on the dataset
- **Index tuning**: Create different index combinations and measure speedup
- **Export/roundtrip**: Run with `--export` to validate export → import integrity

## Related Examples

- [Example 01 - Simple Document Store](01_simple_document_store.md) - Document basics and CRUD
- [Example 02 - Social Network Graph](02_social_network_graph.md) - Graph modeling with NULL handling
- [Example 03 - Vector Search](03_vector_search.md) - Semantic similarity search

---

**Dataset License**: MovieLens data is provided by GroupLens Research and is free to use
for educational purposes. See
[https://grouplens.org/datasets/movielens/](https://grouplens.org/datasets/movielens/)
for details.
