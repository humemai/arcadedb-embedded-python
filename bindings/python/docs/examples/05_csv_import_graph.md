# Example 05: CSV Import - Graph

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/examples/05_csv_import_graph.py){ .md-button }

**Production-ready graph creation from MovieLens dataset with comprehensive performance analysis**

## Overview

This example demonstrates creating a graph database from the MovieLens dataset,
transforming documents into vertices and edges. You'll learn production-ready patterns
for:

- **Graph modeling** - Users and Movies as vertices, ratings and tags as edges
- **Java API vs SQL** - Compare both approaches for bulk graph creation
- **Async vs Sync** - Understand when parallelism helps (and when it hurts)
- **Index optimization** - Create indexes AFTER bulk operations for 2-3× speedup
- **Export & roundtrip validation** - Verify data integrity through complete cycle
- **Performance benchmarking** - Measure and compare 6 different configurations
- **Query validation** - 10 graph queries with result verification

## What You'll Learn

- Graph schema design (vertex types, edge types, properties)
- Foreign key resolution (userId → User vertex, movieId → Movie vertex)
- **Java API is faster than SQL for bulk edge creation** (5,071 vs 3,789 edges/sec)
- **Synchronous is faster than async in embedded mode** (no network I/O to parallelize)
- **Indexes provide 2-3× speedup** for edge creation
- Export/import performance and compression ratios (50-80×)
- Graph query patterns (MATCH, collaborative filtering, recommendations)
- Production import patterns for large-scale graphs

## Prerequisites

**1. Install ArcadeDB Python bindings:**

```bash
pip install arcadedb-embedded
```

**2. Dataset download (automatic):**

The example automatically downloads the dataset if it doesn't exist. You can also use a
pre-existing document database from Example 04.

**Two dataset sizes available:**

- **movielens-large**: ~330K users, ~86K movies, ~33M edges (~971 MB CSV) - Realistic performance testing
- **movielens-small**: ~610 users, ~9,700 movies, ~100K edges (~3.2 MB CSV) - Quick testing

## Usage

```bash
# Recommended: Fastest configuration (Java API, synchronous)
python 05_csv_import_graph.py --size small --method java --no-async

# Compare with SQL
python 05_csv_import_graph.py --size small --method sql

# Run with export for roundtrip validation
python 05_csv_import_graph.py --size small --method java --no-async --export

# Comprehensive benchmark (all 6 configurations in parallel)
./run_benchmark_05_csv_import_graph.sh small 5000 4 all_6 --export

# See all options
python 05_csv_import_graph.py --help
```

**Key options:**

- `--size {small,large}` - Dataset size (default: small)
- `--method {java,sql}` - Creation method: 'java' (recommended) or 'sql'
- `--no-async` - Use synchronous transactions (FASTER for embedded mode)
- `--no-index` - Skip creating indexes (slower, for comparison)
- `--batch-size BATCH_SIZE` - Batch size for operations (default: 5000)
- `--parallel PARALLEL` - Async executor threads (default: 4, not recommended)
- `--export` - Export graph database to JSONL after creation
- `--source-db SOURCE_DB` - Custom source database path
- `--import-jsonl IMPORT_JSONL` - Import from JSONL export instead of CSV

**Recommendations:**

- **Method:** Use `java` (faster than SQL for bulk operations)
- **Async:** Use `--no-async` for best performance (2.5× faster in embedded mode)
- **Indexes:** Keep enabled (2-3× speedup for edge creation)
- **Batch size:** 5000 for small, 50000 for large datasets
- **Export:** Use `--export` to validate data integrity via roundtrip

## Graph Schema

### Vertex Types

**User**

- Properties: `userId` (LONG, indexed), `name` (STRING)
- Count: 610 (small) / 330,000 (large)

**Movie**

- Properties: `movieId` (LONG, indexed), `title` (STRING), `genres` (STRING), `imdbId` (STRING), `tmdbId` (STRING)
- Count: 9,742 (small) / 86,537 (large)

### Edge Types

**RATED** (User → Movie)

- Properties: `rating` (FLOAT), `timestamp` (LONG)
- Count: 98,734 (small) / 33,155,309 (large)

**TAGGED** (User → Movie)

- Properties: `tag` (STRING), `timestamp` (LONG)
- Count: 3,494 (small) / 2,212,213 (large)

## Performance Results

### Small Dataset (610 users, 9,742 movies, 102,228 edges)

| Method | Vertices | Edges | Creation Time | Memory (Peak) |
|--------|----------|-------|---------------|---------------|
| **java_noasync** ⚡ | **11,528/s** | **6,927/s** | **15.65s** | 5.5 GB |
| java_noindex_noasync | 12,514/s | 6,766/s | 15.94s | 5.5 GB |
| java (async) | 4,453/s | 6,516/s | 18.01s | 5.6 GB |
| java_noindex (async) | 4,255/s | 6,143/s | 19.07s | 5.0 GB |
| sql_noindex | 5,383/s | 5,225/s | 21.49s | 5.6 GB |
| sql | 4,882/s | 4,956/s | 22.75s | 5.5 GB |

### Large Dataset (330K users, 86K movies, 35.4M edges)

| Method | Vertices | Edges | Creation Time | Memory (Peak) |
|--------|----------|-------|---------------|---------------|
| **java_noasync** ⚡ | **12,341/s** | **5,071/s** | **1h 57m** | 16.0 GB |
| sql | 8,734/s | 3,789/s | 2h 36m | 16.0 GB |
| java (async) | 2,469/s | 2,034/s | 4h 52m | 18.4 GB |
| java_noindex_noasync | 13,036/s | 1,839/s | 5h 21m | 15.7 GB |
| sql_noindex | 8,902/s | 1,773/s | 5h 33m | 15.6 GB |
| java_noindex (async) | 2,662/s | 820/s | 12h 1m | 18.3 GB |

## Key Performance Insights

### 1. 🚀 **Synchronous Java API is FASTEST for Bulk Edge Creation**

**Winner: `java_noasync` (5,071 edges/sec)**

```
Large Dataset Edge Creation:
✅ java_noasync:           5,071 edges/sec  ← FASTEST (sync Java API)
✅ sql:                    3,789 edges/sec  (25% slower)
❌ java (async):           2,034 edges/sec  (60% slower)
```

**Why?** In embedded mode, there's no network I/O to parallelize. Async machinery (futures, thread coordination) adds overhead without benefits. Direct synchronous Java API calls are the fastest path.

### 2. 📊 **Indexes Provide 2-3× Speedup**

```
Java API Edge Creation (Large Dataset):
✅ WITH indexes (java_noasync):     5,071 edges/sec  ← 2.8× faster
❌ WITHOUT indexes:                 1,839 edges/sec

SQL Edge Creation (Large Dataset):
✅ WITH indexes (sql):              3,789 edges/sec  ← 2.1× faster
❌ WITHOUT indexes:                 1,773 edges/sec
```

**Best Practice:** Create indexes BEFORE bulk edge creation (unlike documents where indexes come after).

### 3. ⚡ **Async Hurts Performance in Embedded Mode**

```
Java API with Indexes (Large Dataset):
✅ Synchronous (java_noasync):     5,071 edges/sec  ← 2.5× faster
❌ Async (java):                   2,034 edges/sec

Vertex Creation:
✅ Synchronous:                   12,341 vertices/sec  ← 5× faster
❌ Async:                          2,469 vertices/sec
```

**Why?** Async is designed for I/O-bound operations (network, disk). In embedded mode, all operations are in-memory JVM calls. Async overhead (thread pools, futures, synchronization) wastes CPU cycles.

### 4. 🎯 **Java API vs SQL: Use Case Matters**

**Use Java API For:**

- ✅ **Bulk edge/vertex creation** (java_noasync: 5,071 edges/sec vs sql: 3,789 edges/sec)
- ✅ Simple CRUD operations (cleaner, type-safe)
- ✅ Batch operations via transactions
- ✅ When raw performance matters most

**Use SQL For:**

- ✅ **Complex graph queries** (MATCH patterns, multi-hop traversals)
- ✅ Aggregations (GROUP BY, COUNT, AVG)
- ✅ Ad-hoc analysis and prototyping
- ✅ When readability > raw speed
- ✅ Cypher compatibility (Neo4j migration path)

### 5. 💾 **Memory Usage: Heap vs Total Process Memory**

```
Large Dataset Memory (8GB JVM Heap):
Peak RSS (actual memory):  15.6 - 18.8 GB  ← Total process memory
JVM Heap (-Xmx):           8.0 GB           ← Just the heap portion

Total = Heap + Non-Heap (metaspace, page cache, thread stacks, direct buffers)
```

**Insight:** JVM heap setting (`-Xmx`) only limits heap memory. Total process memory
includes metaspace, page cache, thread stacks, and direct buffers. Plan for 1.5-2× your
heap size in actual RAM.

## Export & Roundtrip Validation

### Export Performance

```
Large Dataset Export (35.4M edges):
✅ java_noasync:    122.53s  (288,815 records/sec)
✅ sql:             187.54s  (188,682 records/sec)

Compression Ratio: 50-80× (JSONL → gzip)
File Size: 670 MB compressed (from ~33 GB uncompressed)
```

### Roundtrip Import Performance

```
Large Dataset Import from JSONL:
✅ java_noasync:    1,365.41s  (25,906 records/sec)
✅ sql:             1,783.64s  (19,843 records/sec)

Total Roundtrip (Export + Import):
✅ java_noasync:    1,487.94s  (24.8 min)
✅ sql:             1,971.18s  (32.9 min)
```

**Validation:** All roundtrip imports passed 10 query validations, confirming data integrity.

## Graph Queries

The example includes 10 comprehensive graph queries (8 SQL + 2 OpenCypher):

### Query 1: Count Vertices by Type

```sql
SELECT labels()[0] as type, count(*) as count
FROM V
GROUP BY type
ORDER BY count DESC
```

### Query 2: Count Edges by Type

```sql
SELECT labels()[0] as type, count(*) as count
FROM E
GROUP BY type
ORDER BY count DESC
```

### Query 3: Sample User Ratings

```sql
MATCH {type: User, where: (userId = 1)}-RATED->{type: Movie}
RETURN $patternPathEdges
LIMIT 5
```

### Query 4: Sample User Tags

```sql
MATCH {type: User, where: (userId = 2)}-TAGGED->{type: Movie}
RETURN $patternPathEdges
LIMIT 5
```

### Query 5: High-Rated Movies

```sql
MATCH {type: User}-RATED->{type: Movie, as: m}
RETURN m.title, m.movieId, m.genres
ORDER BY m.movieId
LIMIT 10
```

### Query 6: Collaborative Filtering (Most Complex)

```sql
MATCH {type: User, where: (userId = 1)}-RATED->{type: Movie}<-RATED-{type: User, as: otherUser}
RETURN otherUser.userId, count(*) as shared_movies
GROUP BY otherUser.userId
ORDER BY shared_movies DESC
LIMIT 10
```

### Query 7-8: Additional SQL Patterns

- Query 7: Users with similar taste (SQL MATCH + aggregation)
- Query 8: Rating distribution (SQL aggregation, filters NULL ratings)

### Query 9-10: OpenCypher Patterns

- Query 9: User's top-rated movies (OpenCypher traversal with filtering)
- Query 10: Collaborative filtering (OpenCypher aggregation)

**Note:** These queries use OpenCypher patterns as an alternative to SQL MATCH syntax.

## Code Walkthrough

### Step 1: Create Graph Schema

```python
# Create vertex types (Schema API preferred for embedded)
db.schema.get_or_create_vertex_type("User")
db.schema.get_or_create_property("User", "userId", "LONG")
db.schema.get_or_create_property("User", "name", "STRING")
db.schema.get_or_create_index("User", ["userId"], unique=True)

db.schema.get_or_create_vertex_type("Movie")
db.schema.get_or_create_property("Movie", "movieId", "LONG")
db.schema.get_or_create_property("Movie", "title", "STRING")
db.schema.get_or_create_index("Movie", ["movieId"], unique=True)

# Create edge types
db.schema.get_or_create_edge_type("RATED")
db.schema.get_or_create_property("RATED", "rating", "FLOAT")
db.schema.get_or_create_property("RATED", "timestamp", "LONG")

db.schema.get_or_create_edge_type("TAGGED")
db.schema.get_or_create_property("TAGGED", "tag", "STRING")
db.schema.get_or_create_property("TAGGED", "timestamp", "LONG")

# SQL DDL remains available (e.g., for remote servers), but the Schema API above is recommended for embedded runs.
```

### Step 2: Create Vertices (Java API - Recommended)

```python
# The example uses VertexCreator class for efficient batch creation
class VertexCreator:
    def _create_users(self, total_users: int):
        """Create User vertices from Rating data."""
        # Use paginated query to avoid memory issues
        last_rid = None
        while True:
            query = f"""SELECT DISTINCT userId FROM Rating
                        WHERE @rid > {last_rid} LIMIT {batch_size}"""
            users = list(db.query("sql", query))
            if not users:
                break

            for record in users:
                user_id = record.get("userId")
                vertex = db.new_vertex("User")
                vertex.set("userId", user_id)
                vertex.set("name", f"User {user_id}")
                vertex.save()

            last_rid = users[-1].get_identity()

# See full implementation in Python file for production-ready patterns
```

### Step 3: Create Edges with Foreign Key Resolution

```python
# Create RATED edges with efficient index lookups
class EdgeCreator:
    def _create_rated_edges(self, total_ratings: int):
        """Create RATED edges from Rating documents."""
        last_rid = None
        while True:
            # Paginated query
            query = f"""SELECT * FROM Rating
                        WHERE @rid > {last_rid} LIMIT {batch_size}"""
            ratings = list(db.query("sql", query))
            if not ratings:
                break

            for rating_doc in ratings:
                user_id = rating_doc.get("userId")
                movie_id = rating_doc.get("movieId")

                # Use index lookups (O(1)) instead of SQL queries
                user_vertex = db.lookup_by_key("User", ["userId"], [user_id])[0]
                movie_vertex = db.lookup_by_key("Movie", ["movieId"], [movie_id])[0]

                edge = user_vertex.new_edge("RATED", movie_vertex, True, "User", "Movie")
                edge.set("rating", rating_doc.get("rating"))
                edge.set("timestamp", rating_doc.get("timestamp"))
                edge.save()

            last_rid = ratings[-1].get_identity()

# See full implementation in Python file with batch processing
```

### Step 4: Run Validation Queries

```python
# Verify vertex counts
user_count = db.query("sql", "SELECT count(*) as c FROM User").first().get("c")
movie_count = db.query("sql", "SELECT count(*) as c FROM Movie").first().get("c")

# Verify edge counts
rated_count = db.query("sql", "SELECT count(*) as c FROM RATED").first().get("c")
tagged_count = db.query("sql", "SELECT count(*) as c FROM TAGGED").first().get("c")

print(f"✅ Users:  {user_count:,}")
print(f"✅ Movies: {movie_count:,}")
print(f"✅ RATED:  {rated_count:,}")
print(f"✅ TAGGED: {tagged_count:,}")
```

## Running the Benchmark

### Single Configuration

```bash
# Fastest configuration (recommended)
python 05_csv_import_graph.py --size small --method java --no-async

# Compare with SQL
python 05_csv_import_graph.py --size small --method sql

# With export for roundtrip validation
python 05_csv_import_graph.py --size small --method java --no-async --export
```

### Comprehensive Benchmark (All 6 Configurations)

```bash
# Run all 6 methods in parallel
./run_benchmark_05_csv_import_graph.sh small 5000 4 all_6

# With export and roundtrip validation
./run_benchmark_05_csv_import_graph.sh small 5000 4 all_6 --export

# Large dataset (takes several hours)
./run_benchmark_05_csv_import_graph.sh large 50000 4 all_6 --export
```

**6 Configurations:**

1. `java` - Java API with async and indexes
2. `java_noasync` - Java API synchronous with indexes ⚡ **FASTEST**
3. `java_noindex` - Java API with async, no indexes
4. `java_noindex_noasync` - Java API synchronous, no indexes
5. `sql` - SQL with indexes (always synchronous)
6. `sql_noindex` - SQL without indexes (always synchronous)

## Benchmark Configuration

### JVM Settings

```bash
export ARCADEDB_JVM_ARGS="-Xmx8g -Xms8g"
export ARCADEDB_JVM_ARGS="-Xms8g"
```

**Memory Planning:**

- Heap size: 8 GB (`-Xmx8g`)
- Total process memory: 15-19 GB (heap + non-heap)
- Plan for 2× heap size in actual RAM

### Batch Sizes

```bash
--batch-size 5000    # Small dataset (default)
--batch-size 50000   # Large dataset (recommended)
```

**Larger batches = fewer commits = faster imports**

### Parallel Processing

```bash
--parallel 4         # CSV import parallelism (Example 04)
```

**Note:** Parallel async does NOT help for graph creation in embedded mode. Use synchronous Java API (`--no-async`) for best performance.

## Next Steps

**[Example 06 - Vector Search: Movie Recommendations](06_vector_search_recommendations.md)**

Semantic similarity search with MovieLens data:
- Generate embeddings from movie titles/genres
- Build HNSW (JVector) index for nearest-neighbor search
- Find similar movies using cosine distance
- Combine vector similarity with rating data
- Query: "Movies similar to X that users also liked"
