# Example 05: CSV Import - Graph

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/05_csv_import_graph.py){ .md-button }

**Production-ready graph creation from MovieLens dataset with comprehensive performance analysis**

## Overview

This example demonstrates creating a graph database from the MovieLens dataset,
transforming documents into vertices and edges. You'll learn production-ready patterns
for:

- **Graph modeling** - Users and Movies as vertices, ratings and tags as edges
- **SQL pipeline** - End-to-end graph creation with SQL DDL/DML
- **Async vs Sync** - Compare async vs sync modes in embedded mode
- **Index optimization** - Create indexes BEFORE bulk edge creation for 2-3× speedup
- **Export & roundtrip validation** - Verify data integrity through complete cycle
- **Performance benchmarking** - Measure and compare 6 different configurations
- **Query validation** - 10 graph queries with result verification
- **Directed graph semantics** - Traversals should be interpreted as directional

## What You'll Learn

- Graph schema design (vertex types, edge types, properties)
- Foreign key resolution (userId → User vertex, movieId → Movie vertex)
- **Synchronous is faster than async in embedded mode** (no network I/O to parallelize)
- **Indexes provide 2-3× speedup** for edge creation
- Export/import performance and compression ratios (50-80×)
- Graph query patterns (MATCH, collaborative filtering, recommendations)
- Production import patterns for large-scale graphs

## Prerequisites

**1. Install ArcadeDB Python bindings:**

```bash
uv pip install arcadedb-embedded
```

**2. Dataset download (automatic):**

The example automatically downloads the dataset if it doesn't exist. You can also use a
pre-existing document database from Example 04.

**Two dataset sizes available:**

- **movielens-large**: ~330K users, ~86K movies, ~33M edges (~971 MB CSV) - Realistic performance testing
- **movielens-small**: ~610 users, ~9,700 movies, ~100K edges (~3.2 MB CSV) - Quick testing

## Usage

```bash
# Recommended SQL configuration (synchronous)
python 05_csv_import_graph.py --dataset movielens-small --method sql --no-async

# Run with export for roundtrip validation
python 05_csv_import_graph.py --dataset movielens-small --batch-size 5000 --method java --no-async --export

# Comprehensive benchmark (all 6 configurations in parallel)
./run_benchmark_05_csv_import_graph.sh movielens-small 5000 4 all_6 --export

# See all options
python 05_csv_import_graph.py --help
```

**Key options:**

- `--dataset {movielens-small,movielens-large}` - Dataset size (default: movielens-small)
- `--method {java,sql}` - Creation method (DSL-first recommendation: `sql`)
- `--no-async` - Use synchronous transactions (FASTER for embedded mode)
- `--no-index` - Skip creating indexes (slower, for comparison)
- `--batch-size BATCH_SIZE` - Batch size for operations (default: 5000)
- `--parallel PARALLEL` - Async executor threads (default: 4, not recommended)
- `--export` - Export graph database to JSONL after creation
- `--export-path EXPORT_PATH` - Export filename (default: `{db_name}.jsonl.tgz`)
- `--db-name DB_NAME` - Database name (default derived from dataset, e.g. `movielens_graph_small_db`)
- `--source-db SOURCE_DB` - Custom source database path
- `--import-jsonl IMPORT_JSONL` - Import from JSONL export instead of using the source document DB

**Recommendations:**

- **Method:** Use `sql` for consistency with DSL-first examples and guides
- **Async:** Use `--no-async` for best performance (2.5× faster in embedded mode)
- **Indexes:** Keep enabled (2-3× speedup for edge creation)
- **Batch size:** 5000 for small, 50000 for large datasets
- **Export:** Use `--export` to validate data integrity via roundtrip

## Graph Schema

### Vertex Types

**User**

- Properties: `userId` (INTEGER, indexed)
- Count: 610 (small) / 330,000 (large)

**Movie**

- Properties: `movieId` (INTEGER, indexed), `title` (STRING), `genres` (STRING), `imdbId` (STRING), `tmdbId` (INTEGER)
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

### 4. 🎯 **DSL-First: Use SQL for Ingestion and Queries**

**Use SQL For:**

- ✅ **Bulk edge/vertex creation** with one consistent DSL across examples
- ✅ **Complex graph queries** (MATCH patterns, multi-hop traversals)
- ✅ Aggregations (GROUP BY, COUNT, AVG)
- ✅ Ad-hoc analysis and prototyping
- ✅ When readability and portability matter
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

The example includes 10 comprehensive graph queries (8 SQL + 2 OpenCypher), run by
`run_and_validate_queries()` and validated against the per-dataset baselines in
`EXPECTED_RESULTS`:

### Query 1: Movies rated by User #1 (SQL - Basic Traversal)

```sql
SELECT expand(out('RATED')) FROM User WHERE userId = 1
```

### Query 2: Movies rated 5.0 by User #1 (SQL - Edge Property Filter)

```sql
SELECT expand(outE('RATED')[rating = 5.0].inV())
FROM User WHERE userId = 1
```

### Query 3: Rating statistics for top 5 active users (SQL - Aggregations)

```sql
SELECT u.userId as userId,
       COUNT(e) as num_ratings,
       AVG(e.rating) as avg_rating,
       MIN(e.rating) as min_rating,
       MAX(e.rating) as max_rating
FROM (
  MATCH {type: User, as: u}.outE('RATED'){as: e} RETURN u,e
)
GROUP BY u.userId
ORDER BY num_ratings DESC
LIMIT 5
```

### Query 4: Top 10 most rated movies (SQL - Aggregations)

```sql
SELECT m.movieId as movieId, m.title as title,
       COUNT(e) as num_ratings, AVG(e.rating) as avg_rating
FROM (
  MATCH {type: Movie, as: m}.inE('RATED'){as: e} RETURN m, e
)
GROUP BY m.movieId, m.title
ORDER BY num_ratings DESC
LIMIT 10
```

### Query 5: Top 10 most tagged movies (SQL - Aggregations)

```sql
SELECT m.movieId as movieId, m.title as title, COUNT(e) as num_tags
FROM (
  MATCH {type: Movie, as: m}.inE('TAGGED'){as: e} RETURN m, e
)
GROUP BY m.movieId, m.title
ORDER BY num_tags DESC
LIMIT 10
```

### Query 6: Users who rated same movies as User #1 (SQL - MATCH Pattern)

```sql
SELECT friend.userId as other_user, movie.title as common_movie,
       a.rating as my_rating, b.rating as their_rating
FROM (
  MATCH {type: User, where: (userId = 1), as: me}
        .outE('RATED'){as: a}
        .inV(){as: movie}
        .inE('RATED'){as: b}
        .outV(){as: friend, where: (userId != 1)}
  RETURN me, friend, movie, a, b
)
```

### Query 7: Users with similar taste to User #1 (SQL - MATCH + Aggregation)

Same as Query 6 but filters both edges to `rating >= 4.5` and aggregates
`count(*) as shared_high_ratings` grouped by `friend.userId`.

### Query 8: Rating distribution across all ratings (SQL - Aggregation)

```sql
SELECT rating, count(*) as frequency
FROM RATED
WHERE rating IS NOT NULL
GROUP BY rating
ORDER BY rating
```

### Query 9: User #1's top-rated movies (OpenCypher - Basic Pattern)

```cypher
MATCH (u:User {userId: 1})-[r:RATED]->(m:Movie)
WHERE r.rating >= 4.0
RETURN m.title as title, r.rating as rating
ORDER BY rating DESC
```

### Query 10: Users who rated same movies as User #1 (OpenCypher - Pattern)

```cypher
MATCH (u:User {userId: 1})-[:RATED]->(m:Movie)<-[:RATED]-(other:User)
WHERE other.userId <> 1
RETURN other.userId as other_user, count(*) as shared_movies
ORDER BY shared_movies DESC
```

**Note:** Queries 1-8 use SQL (including SQL `MATCH` patterns); Queries 9-10 use
OpenCypher as an alternative pattern syntax.

## Code Walkthrough

### Step 1: Create Graph Schema

```python
# create_schema() runs each DDL statement wrapped in try/except so the
# schema build is idempotent (re-running a CREATE is a no-op):
schema_commands = [
    "CREATE VERTEX TYPE User",
    "CREATE VERTEX TYPE Movie",
    "CREATE EDGE TYPE RATED",
    "CREATE EDGE TYPE TAGGED",
    "CREATE PROPERTY User.userId INTEGER",
    "CREATE PROPERTY Movie.movieId INTEGER",
    "CREATE PROPERTY Movie.title STRING",
    "CREATE PROPERTY Movie.genres STRING",
    "CREATE PROPERTY Movie.imdbId STRING",
    "CREATE PROPERTY Movie.tmdbId INTEGER",
    "CREATE PROPERTY RATED.rating FLOAT",
    "CREATE PROPERTY RATED.timestamp LONG",
    "CREATE PROPERTY TAGGED.tag STRING",
    "CREATE PROPERTY TAGGED.timestamp LONG",
]
for command in schema_commands:
    try:
        db.command("sql", command)
    except Exception:
        pass

# Indexes (unless --no-index): created BEFORE bulk edge creation
db.command("sql", "CREATE INDEX ON User (userId) UNIQUE_HASH")
db.command("sql", "CREATE INDEX ON Movie (movieId) UNIQUE_HASH")
```

Because the graph is directed, user-to-movie traversals should normally be expressed as
outgoing traversals from `User` to `Movie`. If you need incoming traversals, express
that explicitly in SQL MATCH or OpenCypher.

### Step 2: Create Vertices (SQL)

```python
# The example uses a VertexCreator class for batch creation. Users come from
# the distinct userIds in the source Rating type. The synchronous SQL path
# inserts user vertices in batched transactions:
class VertexCreator:
    def _create_users(self, total_users: int):
        """Create User vertices from distinct Rating.userId values."""
        with arcadedb.open_database(str(source_db_path)) as source_db:
            query = (
                "SELECT userId FROM (SELECT DISTINCT userId FROM Rating) "
                "ORDER BY userId"
            )
            batch_user_ids = []
            for record in source_db.query("sql", query):
                batch_user_ids.append(record.get("userId"))
                if len(batch_user_ids) >= self.batch_size:
                    with self.db.transaction():
                        for uid in batch_user_ids:
                            self.db.command(
                                "sql", "INSERT INTO User SET userId = ?", uid
                            )
                    batch_user_ids = []
            # ... handle remaining batch ...

# See full implementation in the Python file for the Java-API and async paths.
```

### Step 3: Create Edges with Foreign Key Resolution

```python
# EdgeCreator paginates the source Rating type (database-level streaming),
# resolves User/Movie RIDs once per batch via a cache (IN [...] lookups that
# use the userId/movieId indexes), then creates edges directly between RIDs.
class EdgeCreator:
    def _create_rated_edges(self, total_ratings: int):
        """Create RATED edges from Rating records."""
        last_rid = "#-1:-1"
        while True:
            query = f"""
                SELECT *, @rid as rid FROM Rating
                WHERE timestamp IS NOT NULL AND @rid > {last_rid}
                LIMIT {self.batch_size}
            """
            chunk = list(source_db.query("sql", query))
            if not chunk:
                break

            with self.db.transaction():
                # Build {userId: rid} and {movieId: rid} caches for this batch
                user_cache, movie_cache = self._build_vertex_cache(chunk)
                for record in chunk:
                    user_rid = user_cache.get(record.get("userId"))
                    movie_rid = movie_cache.get(record.get("movieId"))
                    if user_rid and movie_rid:
                        self.db.command(
                            "sql",
                            f"CREATE EDGE RATED FROM {user_rid} TO {movie_rid} "
                            f"SET rating = {record.get('rating')}, "
                            f"timestamp = {record.get('timestamp')}",
                        )

            last_rid = chunk[-1].get("rid")

# See full implementation in the Python file (Java-API and SQL variants).
```

### Step 4: Run Validation Queries

```python
# Verify vertex counts (validate_counts_and_samples)
user_count = list(db.query("sql", "SELECT count(*) as count FROM User"))[0].get("count")
movie_count = list(db.query("sql", "SELECT count(*) as count FROM Movie"))[0].get("count")

# Verify edge counts
rated_count = list(db.query("sql", "SELECT count(*) as count FROM RATED"))[0].get("count")
tagged_count = list(db.query("sql", "SELECT count(*) as count FROM TAGGED"))[0].get("count")

print(f"  Users:  {user_count:,}")
print(f"  Movies: {movie_count:,}")
print(f"  RATED:  {rated_count:,}")
print(f"  TAGGED: {tagged_count:,}")
```

## Running the Benchmark

### Single Configuration

```bash
# Fastest configuration (recommended)
python 05_csv_import_graph.py --dataset movielens-small --method java --no-async

# Compare with SQL
python 05_csv_import_graph.py --dataset movielens-small --method sql

# With export for roundtrip validation
python 05_csv_import_graph.py --dataset movielens-small --batch-size 5000 --method java --no-async --export
```

### Comprehensive Benchmark (All 6 Configurations)

```bash
# Run all 6 methods in parallel
./run_benchmark_05_csv_import_graph.sh movielens-small 5000 4 all_6

# With export and roundtrip validation
./run_benchmark_05_csv_import_graph.sh movielens-small 5000 4 all_6 --export

# Large dataset (takes several hours)
./run_benchmark_05_csv_import_graph.sh movielens-large 50000 4 all_6 --export
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

Prefer configuring heap inside the script before it creates the first database:

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.jvm import start_jvm

start_jvm(heap_size="8g", jvm_args="-Xms8g")
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
--parallel 4         # Async executor parallel level (1-16, default 4)
```

**Note:** This only affects the Java-API async path. Parallel async does NOT help for
graph creation in embedded mode (and has no effect in `--method sql`, which is always
synchronous). Use synchronous Java API (`--no-async`) for best performance.

## Next Steps

**[Example 06 - Vector Search: Movie Recommendations](06_vector_search_recommendations.md)**

Semantic similarity search with MovieLens data:

- Generate embeddings from movie titles/genres
- Build HNSW (JVector) index for nearest-neighbor search
- Find similar movies using cosine distance
- Combine vector similarity with rating data
- Query: "Movies similar to X that users also liked"
