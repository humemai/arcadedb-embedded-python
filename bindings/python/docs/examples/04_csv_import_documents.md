# Example 04: CSV Import - Tables (Documents)

**Production-ready CSV import with automatic type inference, NULL handling, and index optimization**

## Overview

This example demonstrates importing real-world CSV data from the MovieLens dataset into ArcadeDB documents. You'll learn production-ready patterns for:

- **Automatic type inference** - Java analyzes CSV and infers optimal ArcadeDB types
- **Schema-on-write** - Database creates schema automatically during import
- **NULL value handling** - Import and query missing data across all types
- **Batch processing** - Optimize import performance with commit batching
- **Index optimization** - Create indexes AFTER import for maximum throughput
- **Performance analysis** - Measure query speedup with statistical validation
- **Result validation** - Verify indexes return identical results with actual data samples

## What You'll Learn

- Automatic type inference by Java CSV importer (LONG, DOUBLE, STRING)
- Schema-on-write during import (no manual schema creation needed)
- NULL value import from empty CSV cells
- Query performance measurement (10 runs with statistics)
- Index creation timing (before vs after import)
- Composite indexes for multi-column queries
- **Result validation with actual data samples**
- Production import patterns for large datasets
- **FULL_TEXT index limitations with LIKE queries** (⚠️ Known Issue)

## Prerequisites

**1. Install ArcadeDB Python bindings:**

```bash
pip install arcadedb-embedded
```

**2. Dataset download (automatic):**

The example automatically downloads the dataset if it doesn't exist. You can also download it manually:

```bash
cd bindings/python/examples
python download_data.py movielens-large # movielens large dataset
python download_data.py movielens-small # movielens small dataset
```

**Two dataset sizes available:**
- **movielens-large**: ~86,000 movies, ~33M ratings (~265 MB) - Realistic performance testing
- **movielens-small**: ~9,700 movies, ~100,000 ratings (~1 MB) - Quick testing

Both datasets include intentional NULL values for testing:
- `movies.csv`: ~3% NULL genres
- `ratings.csv`: ~2% NULL timestamps
- `links.csv`: ~10% NULL imdbId, ~15% NULL tmdbId
- `tags.csv`: ~5% NULL tags

## Dataset Structure

**MovieLens Large** - 4 CSV files:

| File | Records | Columns | Description |
|------|---------|---------|-------------|
| `movies.csv` | 86,537 | movieId, title, genres | Movie metadata |
| `ratings.csv` | 33,832,162 | userId, movieId, rating, timestamp | User ratings |
| `links.csv` | 86,537 | movieId, imdbId, tmdbId | External IDs (with NULLs) |
| `tags.csv` | 2,328,315 | userId, movieId, tag, timestamp | User tags (with NULLs) |

**Total records**: 36,333,551 documents

For quick testing with the smaller dataset (124,003 records), use: `python download_data.py movielens-small`

## Usage

```bash
# Basic usage (large dataset by default)
python 04_csv_import_documents.py

# Use small dataset for quick testing
python 04_csv_import_documents.py --size small

# Configure parallel threads and batch size
python 04_csv_import_documents.py --parallel 8 --batch-size 10000

# Export database for reproducibility
python 04_csv_import_documents.py --export

# See all options
python 04_csv_import_documents.py --help
```

**Key options:**
- `--size {small,large}` - Dataset size (default: large)
- `--parallel PARALLEL` - Number of parallel import threads (default: auto-detect)
- `--batch-size BATCH_SIZE` - Records per commit batch (default: 5000)
- `--export` - Export database to JSONL after import
- `--db-name DB_NAME` - Custom database name (default: movielens_{size}_db)

**Recommendations:**
- Parallel threads: 4-8 for best performance (auto-detected by default)
- Batch size: 5000-50000 (larger = faster imports, more memory)
- Export: Use `--export` to create reproducible benchmark databases

## Type Inference by Java

The example uses **automatic type inference** by the Java CSV importer, which analyzes the data and selects optimal ArcadeDB types:

### Example Inference Results (movielens-large)

```
📋 Movie (movies.csv):
   • movieId: LONG (e.g., '1')
   • title: STRING (e.g., 'Toy Story (1995)')
   • genres: STRING (e.g., 'Adventure|Animation|Children|Comedy|Fantasy')

📋 Rating (ratings.csv):
   • userId: LONG (e.g., '1')
   • movieId: LONG (e.g., '1')
   • rating: DOUBLE (e.g., '4.0')
   • timestamp: LONG (e.g., '964982703')

📋 Link (links.csv):
   • movieId: LONG (e.g., '1')
   • imdbId: LONG (e.g., '')         ← NULL value
   • tmdbId: LONG (e.g., '862')

📋 Tag (tags.csv):
   • userId: LONG (e.g., '2')
   • movieId: LONG (e.g., '60756')
   • tag: STRING (e.g., 'funny')
   • timestamp: LONG (e.g., '1445714994')
```

## Code Walkthrough

### Step 1: Check Dataset Availability

```python
data_dir = Path(__file__).parent / "data" / "ml-latest-small"
if not data_dir.exists():
    print("❌ MovieLens dataset not found!")
    print("💡 Please download the dataset first:")
    print("   python download_data.py")
    exit(1)
```

### Step 2: Let Java Infer Types Automatically

The Java CSV importer automatically analyzes the CSV data and infers optimal ArcadeDB types (LONG, DOUBLE, STRING). No manual type inference code is needed - the importer handles this intelligently based on the actual data values.

The schema is created automatically during import (schema-on-write), eliminating the need for explicit schema definition before import.

### Step 3: Import CSV Files Directly

```python
# Import with batch commits for performance
stats = arcadedb.import_csv(
    db,
    movies_csv,
    "Movie",
    commit_every=1000  # Commit every 1000 records
)

# Check for NULL values
null_genres = list(db.query(
    "sql", "SELECT count(*) as c FROM Movie WHERE genres IS NULL"
))[0].get_property("c")

if null_genres > 0:
    print(f"   🔍 NULL values detected:")
    print(f"      • genres: {null_genres:,} NULL values ({null_genres/stats['documents']*100:.1f}%)")
    print("   💡 Empty CSV cells correctly imported as SQL NULL")
```

**Performance results (small dataset):**
- Movies: 105,891 records/sec
- Ratings: 484,788 records/sec (largest file, highly optimized)
- Links: 374,692 records/sec
- Tags: 167,409 records/sec
- **Total: 356,330 records/sec average**

**Performance results (large dataset):**
- Movies: 288,457 records/sec
- Ratings: 908,832 records/sec (largest file, highly optimized)
- Links: 697,879 records/sec
- Tags: 739,148 records/sec
- **Total: 890,528 records/sec average**

**Key insight:** Larger datasets show better performance due to more efficient batch processing and reduced per-record overhead.

### Step 8: Query Performance WITHOUT Indexes

```python
test_queries = [
    ("Find movie by ID", "SELECT FROM Movie WHERE movieId = 500"),
    ("Find user's ratings", "SELECT FROM Rating WHERE userId = 414 LIMIT 10"),
    ("Find movie ratings", "SELECT FROM Rating WHERE movieId = 500"),
    ("Count user's ratings", "SELECT count(*) FROM Rating WHERE userId = 414"),
    ("Find movies by genre", "SELECT FROM Movie WHERE genres LIKE '%Action%' LIMIT 10"),
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

```python
with db.transaction():
    db.command("sql", "CREATE INDEX ON Movie (movieId) UNIQUE")
    db.command("sql", "CREATE INDEX ON Rating (userId, movieId) NOTUNIQUE")  # Composite!
    db.command("sql", "CREATE INDEX ON Link (movieId) UNIQUE")
    db.command("sql", "CREATE INDEX ON Tag (movieId) NOTUNIQUE")
```

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
Query                          Before (ms)     After (ms)      Speedup
======================================================================
Find movie by ID               39.1±7.6        0.7±1.9         58.1x
                                     (98.3% time saved)
Find user's ratings            16003.9±79.4    1.1±0.4         14,836x
                                     (100.0% time saved)
Find movie ratings             16524.8±124.2   153.1±22.2      107.9x
                                     (99.1% time saved)
Count user's ratings           16004.3±138.3   0.8±1.4         19,604x
                                     (100.0% time saved)
Find movies by genre           1.0±1.0         0.8±0.3         1.3x
                                     (23.7% time saved)
Count ALL Action movies        58.7±8.4        65.1±18.0       0.9x
                                     (-10.8% time saved)
======================================================================
```

**Key findings:**
- ✅ Composite indexes show **massive gains** (up to 19,604x speedup!)
- ✅ Single column lookups are **very fast** (58.1x speedup)
- ✅ Standard deviation shows **query stability**
- ⚠️ FULL_TEXT index on genres shows slight regression with LIKE queries (see Known Issue)

## NULL Value Handling

The example demonstrates comprehensive NULL handling:

### Import Results

```
Step 2: Importing movies.csv → Movie documents...
   ✅ Imported 86,537 movies
   🔍 NULL values detected:
      • genres: 2,584 NULL values (3.0%)
   💡 Empty CSV cells correctly imported as SQL NULL

Step 4: Importing ratings.csv → Rating documents...
   ✅ Imported 33,832,162 ratings
   🔍 NULL values detected:
      • timestamp: 675,782 NULL values (2.0%)
   💡 Empty CSV cells correctly imported as SQL NULL

Step 5: Importing links.csv → Link documents...
   ✅ Imported 86,537 links
   🔍 NULL values detected:
      • imdbId: 8,628 NULL values (10.0%)
      • tmdbId: 13,026 NULL values (15.1%)
   💡 Empty CSV cells correctly imported as SQL NULL

Step 6: Importing tags.csv → Tag documents...
   ✅ Imported 2,328,315 tags
   🔍 NULL values detected:
      • tag: 116,644 NULL values (5.0%)
   💡 Empty CSV cells correctly imported as SQL NULL
```

### NULL Values in Aggregations

```
💬 Top 10 most common tags:
    1. 'None' (116,644 uses)          ← NULL tags appear as 'None'
    2. 'sci-fi' (13,612 uses)
    ...

🎭 Top 10 genres by movie count:
    1. Drama (11,857 movies)
    ...
    6. None (2,584 movies)          ← NULL genres appear as 'None'
```

**Total NULL values**: ~799,638 across all fields (LONG and STRING types)

## Index Architecture

ArcadeDB uses **LSM-Tree (Log-Structured Merge Tree)** for all indexes - a single unified backend that handles all data types efficiently.

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
SELECT count(*) as count FROM Movie     # 9,742 movies
SELECT count(*) as count FROM Rating    # 100,836 ratings
SELECT count(*) as count FROM Link      # 9,742 links
SELECT count(*) as count FROM Tag       # 3,683 tags
```

### Rating Statistics

```python
SELECT
    count(*) as total_ratings,
    avg(rating) as avg_rating,
    min(rating) as min_rating,
    max(rating) as max_rating
FROM Rating

# Results: 100,836 ratings, avg 3.50 ★, range 0.5-5.0
```

### Rating Distribution

```python
SELECT rating, count(*) as count
FROM Rating
GROUP BY rating
ORDER BY rating

# Results:
# 0.5 ★ : 1,370
# 1.0 ★ : 2,811
# ...
# 4.0 ★ : 26,818  (most common)
# 5.0 ★ : 13,211
```

### Top Genres

```python
SELECT genres, count(*) as count
FROM Movie
WHERE genres <> '(no genres listed)'
GROUP BY genres
ORDER BY count DESC
LIMIT 10

# Results: Drama (1,022), Comedy (922), Comedy|Drama (429), ...
```

### Most Active Users

```python
SELECT userId, count(*) as rating_count
FROM Rating
GROUP BY userId
ORDER BY rating_count DESC
LIMIT 10

# Results: User 414 (2,698 ratings), User 599 (2,478), ...
```

## Best Practices Demonstrated

### ✅ Type Inference by Java
- Java CSV importer automatically analyzes data and selects optimal types
- Handles LONG, DOUBLE, STRING intelligently based on actual values
- No manual type inference code needed
- Schema-on-write simplifies development

### ✅ Schema Definition
- Define schema BEFORE import (validation + optimization)
- Use explicit property types (no guessing)
- Choose appropriate types for data ranges

### ✅ Import Optimization
- Use `commit_every` parameter for batching
- Larger batches = faster imports (balance with memory)
- Movies: commit_every=1000 (smaller batches)
- Ratings: commit_every=5000 (larger dataset, bigger batches)

### ✅ Index Strategy
- **CREATE INDEXES AFTER IMPORT** (2-3x faster total time)
- Use composite indexes for multi-column queries
- Order matters: most selective column first
- Index creation timing: ~0.2 seconds for 124K records

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
python 04_csv_import_documents.py --size small

# Use large dataset explicitly
python 04_csv_import_documents.py --size large

# With custom JVM heap for large datasets
ARCADEDB_JVM_ARGS="-Xmx8g -Xms8g" python 04_csv_import_documents.py --size large
```

**Command-line options:**
- `--size {small,large}` - Dataset size to use (default: large)
- The script automatically downloads the dataset if it doesn't exist

**Expected output:**
- Automatic dataset download if needed
- Step-by-step import progress
- NULL value detection for all 4 files
- Performance statistics (before/after indexes)
- Data analysis queries with results
- Total time: ~2-3 minutes (movielens-large) or ~5 seconds (movielens-small)

**Database location:**
- Small dataset: `./my_test_databases/movielens_small_db/`
- Large dataset: `./my_test_databases/movielens_large_db/`

The database is preserved for inspection after the example completes.

**Database size:**

- **movielens-large**: ~2.0 GB database from ~971 MB CSV files (~2.1x expansion)
- **movielens-small**: ~27 MB database from ~3.2 MB CSV files (~8.4x expansion)

⚠️ **Note**: Database files are larger than source CSVs due to:

- Index structures (LSM-Tree buffers and sorted data)
- Transaction logs and metadata
- Internal data structures for document storage
- WAL (Write-Ahead Log) files for durability

## Expected Output

```text
======================================================================
🎬 ArcadeDB Python - Example 04: CSV Import - Documents
======================================================================

📊 Dataset size: large

Step 0: Checking for MovieLens dataset...
✅ Large dataset found!
   Location: .../data/movielens-large

# Or if dataset doesn't exist, you'll see:
# ❌ Large dataset not found at: .../data/movielens-large
# 📥 Downloading large dataset...
# ✅ Dataset downloaded successfully!

Step 1: Creating database...
   ✅ Database created at: ./my_test_databases/movielens_large_db
   ⏱️  Time: 0.597s

Step 2: Inspecting CSV files and inferring types...
   📋 Movie (movies.csv):
      • movieId: INTEGER
      • title: STRING
      • genres: STRING
   ⏱️  Time: 0.019s

Step 3: Creating schema with explicit property types...
   ✅ Created Movie document type
   ✅ Created Rating document type
   ✅ Created Link document type
   ✅ Created Tag document type
   ⏱️  Time: 0.051s

Step 4: Importing movies.csv → Movie documents...
   ✅ Imported 86,537 movies
   🔍 NULL values detected:
      • genres: 2,584 NULL values (3.0%)

Step 5: Importing ratings.csv → Rating documents...
   ✅ Imported 33,832,162 ratings
   🔍 NULL values detected:
      • timestamp: 675,782 NULL values (2.0%)

Step 6: Importing links.csv → Link documents...
   ✅ Imported 86,537 links
   🔍 NULL values detected:
      • imdbId: 8,628 NULL values (10.0%)
      • tmdbId: 13,026 NULL values (15.1%)

Step 7: Importing tags.csv → Tag documents...
   ✅ Imported 2,328,315 tags
   🔍 NULL values detected:
      • tag: 116,644 NULL values (5.0%)

Step 8: Testing query performance WITHOUT indexes...
   📊 Find movie by ID: 8.67ms ± 5.67ms

Step 9: Creating indexes for query performance...
   ✅ Created indexes on key columns
   ⏱️  Time: 0.238s

Step 10: Testing query performance WITH indexes...
   📊 Find movie by ID: 0.51ms ± 1.41ms

   🚀 Performance Improvement Summary:
   Find movie by ID: 17.0x speedup (94.1% time saved)
   Find user's ratings: 49.4x speedup (98.0% time saved)

Step 11: Verifying schema and property definitions...
   📋 Movie schema (formally defined):
      • movieId: INTEGER
      • title: STRING
      • genres: STRING

Step 12: Querying and analyzing imported data...
   📊 Total records imported: 124,003
   ⭐ Rating statistics: 100,836 ratings, avg 3.50
   🎭 Top genres: Drama (1,022), Comedy (922)
   👥 Most active user: User 414 (2,698 ratings)

✅ Data Import Example Complete!
```

## ⚠️ Known Issue: FULL_TEXT Index Performance with LIKE Queries

### Issue Summary

The example creates a `FULL_TEXT` index on the `Movie.genres` field, but testing reveals that **FULL_TEXT indexes do NOT improve performance for `LIKE '%term%'` pattern matching queries**, and may actually cause performance regression.

### Performance Results (movielens-large dataset with 86,537 movies)

**Query: `SELECT count(*) FROM Movie WHERE genres LIKE '%Action%'`**

- **Without FULL_TEXT index**: 58.7ms ± 8.4ms
- **With FULL_TEXT index**: 65.1ms ± 18.0ms
- **Result**: 0.9x speedup **(10.8% SLOWER)**

**Query: `SELECT FROM Movie WHERE genres LIKE '%Action%' LIMIT 10`**

- **Without index**: 1.0ms ± 1.0ms
- **With FULL_TEXT index**: 0.8ms ± 0.3ms
- **Result**: 1.3x speedup (marginal improvement)

### Why This Happens

1. **Tokenization Mismatch**: FULL_TEXT indexes tokenize text (e.g., `"Action|Comedy|Sci-Fi"` → `["Action", "Comedy", "Sci-Fi"]`)
2. **Pattern Matching**: `LIKE '%Action%'` is substring search, not token search
3. **Index Overhead**: The query planner may attempt to use the index inefficiently, adding overhead without benefit

### Comparison with Working Indexes

For comparison, LSM_TREE indexes on the same dataset show massive improvements:

- `Rating(userId)`: **14,836x speedup** ✅
- `Rating(movieId)`: **107.9x speedup** ✅
- `Movie(movieId)`: **58.1x speedup** ✅

### Current Status

**Reported to ArcadeDB team**: [Issue #2703](https://github.com/ArcadeData/arcadedb/issues/2703)

Awaiting clarification on:

1. Whether `LIKE` queries should use FULL_TEXT indexes
2. Alternative syntax (e.g., `SEARCH()` function) for proper full-text search
3. Whether this is a query optimizer issue

### Recommendation

**For now**: The example keeps the FULL_TEXT index for demonstration purposes, but be aware:

- ✅ LSM_TREE indexes (on movieId, userId) work excellently
- ⚠️ FULL_TEXT index on genres provides minimal/negative benefit with LIKE
- 🔍 Future ArcadeDB releases may improve this behavior

**Alternative**: If you need text search, consider:

- Using separate tokens in dedicated fields
- Implementing application-level text filtering after retrieval
- Waiting for ArcadeDB team guidance on proper full-text search syntax

### Documentation Note

This limitation is documented here for future reference. The example code includes:

- Performance validation that detects the issue
- Detailed comments explaining FULL_TEXT index behavior
- Result consistency validation (shows queries return identical data regardless of indexes)

## Database Files on Disk

After running the example, the database directory contains several types of files that reflect ArcadeDB's multi-bucket architecture:

### Directory Structure

Example for large dataset (`movielens_large_db`):

```bash
my_test_databases/movielens_large_db/
├── configuration.json          # Database configuration
├── schema.json                 # Current schema (authoritative)
├── schema.prev.json           # Previous schema version (for rollback)
├── statistics.json            # Database statistics
├── dictionary.0.327680.v0.dict  # String compression dictionary
├── Movie_0.bucket ... Movie_14.bucket    # 15 data buckets for Movie type
├── Rating_0.bucket ... Rating_14.bucket  # 15 data buckets for Rating type
├── Link_0.bucket ... Link_14.bucket      # 15 data buckets for Link type
├── Tag_0.bucket ... Tag_14.bucket        # 15 data buckets for Tag type
├── Movie_0_*.umtidx ... Movie_14_*.umtidx     # Movie.movieId index files (UNIQUE)
├── Movie_0_*.numtidx ... Movie_14_*.numtidx   # Movie.genres index files (FULL_TEXT)
├── Rating_0_*.nuctidx ... Rating_14_*.nuctidx # Rating.userId index files (NOTUNIQUE)
├── Rating_0_*.numtidx ... Rating_14_*.numtidx # Rating.movieId index files (NOTUNIQUE)
├── Link_0_*.umtidx ... Link_14_*.umtidx       # Link.movieId index files (UNIQUE)
└── Tag_0_*.numtidx ... Tag_14_*.numtidx       # Tag.movieId index files (NOTUNIQUE)

Total: ~185 files (60 buckets + 120 index files + 5 metadata files)
```

**File naming pattern**: `Type_BucketNum_Timestamp.FileID.Size.Version.Extension`

Example: `Movie_0_258729020513975.61.262144.v1.umtidx`

- Type: Movie
- Bucket: 0
- Timestamp: 258729020513975
- File ID: 61
- Size: 262144 bytes
- Version: v1
- Extension: umtidx (Unique Mutable Tree Index)

### Multi-Bucket Architecture

**ArcadeDB creates 15 buckets per type by default** to enable parallel operations:

```text
Movie type → 15 buckets (Movie_0 through Movie_14)
Rating type → 15 buckets (Rating_0 through Rating_14)
Link type → 15 buckets (Link_0 through Link_14)
Tag type → 15 buckets (Tag_0 through Tag_14)
```

**When you create an index, ArcadeDB creates one index file per bucket:**

```text
CREATE INDEX ON Movie (movieId) UNIQUE
→ Creates 15 index files: Movie_0_*.umtidx through Movie_14_*.umtidx

CREATE INDEX ON Rating (userId) NOTUNIQUE
→ Creates 15 index files: Rating_0_*.nuctidx through Rating_14_*.nuctidx
```

**Total index files = buckets × indexed properties:**

- Movie: 15 buckets × 2 properties (movieId + genres) = 30 index files
- Rating: 15 buckets × 2 properties (userId + movieId) = 30 index files
- Link: 15 buckets × 1 property (movieId) = 15 index files
- Tag: 15 buckets × 1 property (movieId) = 15 index files
- **Total: 90 active index files**

### Schema Metadata (schema.json)

The `schema.json` file is the **authoritative source** for database structure. It contains:

**Example schema excerpt:**

```json
{
  "schemaVersion": 62,
  "types": {
    "Movie": {
      "type": "d",
      "buckets": ["Movie_0", "Movie_1", ..., "Movie_14"],
      "properties": {
        "movieId": { "type": "LONG" },
        "title": { "type": "STRING" },
        "genres": { "type": "STRING" }
      },
      "indexes": {
        "Movie_0_258729020513975": {
          "type": "LSM_TREE",
          "bucket": "Movie_0",
          "properties": ["movieId"],
          "unique": true
        },
        "Movie_0_258729481567523": {
          "type": "FULL_TEXT",
          "bucket": "Movie_0",
          "properties": ["genres"],
          "unique": false
        },
        ... // 13 more buckets with same indexes
      }
    },
    "Rating": {
      "buckets": ["Rating_0", ..., "Rating_14"],
      "indexes": {
        // 30 indexes: 15 for userId + 15 for movieId
      }
    }
  }
}
```

**Key insights from schema:**

- ✅ **15 buckets per type** - confirms multi-bucket architecture
- ✅ **1 index per bucket per property** - explains why 6 CREATE INDEX commands create 90 index files
- ✅ **3 index types**: LSM_TREE (general), FULL_TEXT (text), JVECTOR (vectors)
- ✅ **Properties track type inference** - shows Java-inferred LONG/DOUBLE/STRING types

### Why So Many Files?

**This is expected behavior** - not a bug! ArcadeDB's multi-bucket design enables:

1. **Parallel writes** - Multiple threads can write to different buckets simultaneously
2. **Parallel index updates** - Each bucket's index can be updated independently
3. **Better scalability** - Distributes data and indexes across multiple files
4. **Compaction efficiency** - Smaller files compact faster than monolithic structures

**File count reference:**

- GitHub issue [#2701](https://github.com/ArcadeData/arcadedb/issues/2701): User reported "80 indexes instead of 5 expected"
- **Resolution**: Working as designed - 1 index per bucket is intentional for parallelism

### Cleanup Note

Some index files may appear duplicated with different timestamps due to LSMTree compaction creating new versions. Old files are automatically cleaned up during subsequent compaction cycles. The `schema.json` metadata always reflects the currently active indexes.

## Database Persistence

**The imported database is fully persistent** - you can reopen it in future sessions and all data, schema, and indexes will be preserved exactly as they were.

### Reopening an Existing Database

```python
# Open existing database (no creation needed)
# Use movielens_small_db or movielens_large_db depending on which dataset you imported
db = arcadedb.create_arcadedb("./my_test_databases/movielens_large_db")

# Schema is automatically loaded (4 types: Movie, Rating, Link, Tag)
types = db.get_schema().get_types()

# All indexes are automatically active (96 index entries)
movie_schema = db.get_schema().get_type("Movie")
indexed_props = movie_schema.get_indexed_properties()

# All 36.3M records are intact
movie_count = list(db.query("sql", "SELECT count(*) as c FROM Movie"))[0].get_property("c")
rating_count = list(db.query("sql", "SELECT count(*) as c FROM Rating"))[0].get_property("c")

# Query performance is identical to original import
result = db.query("sql", "SELECT FROM Movie WHERE movieId = 500")  # Fast indexed lookup!
```

**What gets preserved:**

✅ **All 36.3M records** (86K movies, 33.8M ratings, 2.3M tags, 86K links)
✅ **Schema definitions** (all 4 types with correct property definitions)
✅ **All indexes** (96 index entries across 16 buckets per type)
✅ **Query performance** (same indexed query speedup as original import)
✅ **NULL values** (all NULL data preserved correctly)

### Persistence Best Practices

```python
# 1. Always close database properly
db.close()  # Ensures all data is flushed to disk

# 2. Reopen existing database (don't recreate!)
db_path = "./my_test_databases/movielens_large_db"  # or movielens_small_db
if os.path.exists(db_path):
    db = arcadedb.create_arcadedb(db_path)
    # All data, schema, indexes automatically available
else:
    # First time: create and import
    db = arcadedb.create_arcadedb(db_path)
    # ... import CSV files ...

# 3. Schema and indexes are durable
# No need to recreate schema or rebuild indexes on reload
```

**Database files on disk**:

Small dataset: `./my_test_databases/movielens_small_db/` (~27 MB, 155 files)
Large dataset: `./my_test_databases/movielens_large_db/` (~2.0 GB, more files due to data volume)

Contents:

- `schema.json` - Authoritative schema definition (types, properties, indexes)
- `configuration.json` - Database configuration
- `*.bucket` - Data files (15 buckets per type, 60 total)
- `*.umtidx`, `*.numtidx` - Index files (90 index files for 6 indexes across 15 buckets each)
- Metadata files: `dictionary`, `schema.prev.json`, `statistics.json`
- Total: 155 files (small dataset), more for large dataset

The database is **production-ready** after import - restart your application, reopen the database, and query immediately with full index performance!

## Key Takeaways

1. ✅ **Automatic type inference** by Java provides intelligent LONG/DOUBLE/STRING selection
2. ✅ **Schema-on-write** simplifies development (no manual schema creation needed)
3. ✅ **NULL value handling** works seamlessly across all data types (STRING, INTEGER, etc.)
4. ✅ **Batch processing** (`commit_every`) dramatically improves import performance
5. ✅ **Create indexes AFTER import** - 2-3x faster than indexing during import
6. ✅ **LSM_TREE indexes** provide massive performance gains (up to 14,836x speedup!)
7. ✅ **Statistical validation** (10 runs) ensures reliable performance measurements
8. ✅ **Result validation** compares actual data values, not just row counts
9. ⚠️ **FULL_TEXT indexes** don't help `LIKE` queries (known issue, reported)
10. ✅ **Multi-bucket architecture** creates 15 buckets per type, 1 index file per bucket per property
11. ✅ **Database persistence** - reopen and query immediately, no rebuild needed!

## Next Steps

- **Try Example 05**: Graph import (MovieLens as vertices and edges)
- **Experiment**: Modify `commit_every` values to see performance impact
- **Add queries**: Try your own analysis queries on the dataset
- **Index tuning**: Create different index combinations and measure speedup
- **Type testing**: Change type inference rules and observe import behavior

## Related Examples

- [Example 01 - Simple Document Store](01_simple_document_store.md) - Document basics and CRUD
- [Example 02 - Social Network Graph](02_social_network_graph.md) - Graph modeling with NULL handling
- [Example 03 - Vector Search](03_vector_search.md) - Semantic similarity search

---

**Dataset License**: MovieLens data is provided by GroupLens Research and is free to use for educational purposes. See [https://grouplens.org/datasets/movielens/](https://grouplens.org/datasets/movielens/) for details.
