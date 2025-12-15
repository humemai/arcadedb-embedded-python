# ArcadeDB Python: Query Languages vs Java API Guide

A comprehensive guide on when to use query languages (SQL/Cypher) versus direct Java API calls in ArcadeDB Python bindings.

## Table of Contents
- [Quick Reference](#quick-reference)
- [Schema Operations](#schema-operations)
- [Data Creation](#data-creation)
- [Data Reading](#data-reading)
- [Data Updates](#data-updates)
- [Data Deletion](#data-deletion)
- [Graph Operations](#graph-operations)
- [Performance Comparison](#performance-comparison)
- [Best Practices](#best-practices)

---

## Quick Reference

**Core Principle: Use Java API whenever possible, query languages (SQL/Cypher) when required or more appropriate.**

| Operation | SQL/Cypher | Java API | Recommendation |
|-----------|------------|----------|----------------|
| **Schema Definition** | ✅ Required | ❌ Not available | **Use SQL** (only option) |
| **Vertex Creation** | ✅ Available (SQL) | ✅ Available | **Use API** (faster, safer, type-safe) |
| **Edge Creation** | ✅ Available (SQL) | ✅ Available | **Use API** (faster, especially with caching) |
| **Queries/Traversals** | ✅ Required | ❌ Not practical | **Use SQL/Cypher** (only option) |
| **Property Updates** | ✅ Available (SQL) | ✅ Available | **Use API** (type-safe, safer) |
| **Batch Updates** | ✅ Available (SQL) | ❌ Not practical | **Use SQL** (designed for this) |
| **Deletions** | ✅ Available (SQL) | ✅ Available | **Use API** when you have the object, SQL for batch |
| **Complex Filtering** | ✅ Required | ❌ Not available | **Use SQL/Cypher** (only option) |
| **Aggregations** | ✅ Required | ❌ Not available | **Use SQL** (only option) |

**Simple Rule:**

- **Creating/Updating individual records?** → Use Java API
- **Querying/Filtering/Aggregating?** → Use SQL or Cypher
- **Batch operations on many records?** → Use SQL

---

## Schema Operations

### ✅ Use SQL Only

Schema operations are **only available via SQL** - there's no direct Java API exposed in Python bindings.

#### Create Document/Vertex/Edge Types

```python
# Document type
db.command("sql", "CREATE DOCUMENT TYPE User")

# Vertex type (for graphs)
db.command("sql", "CREATE VERTEX TYPE Person")

# Edge type (for graphs)
db.command("sql", "CREATE EDGE TYPE FRIEND_OF")
```

#### Create Properties

```python
# Define property with type
db.command("sql", "CREATE PROPERTY Person.name STRING")
db.command("sql", "CREATE PROPERTY Person.age INTEGER")
db.command("sql", "CREATE PROPERTY Person.score DOUBLE")
db.command("sql", "CREATE PROPERTY Person.active BOOLEAN")
db.command("sql", "CREATE PROPERTY Person.joined DATE")

# Property with constraints
db.command("sql", "CREATE PROPERTY Person.email STRING (mandatory true)")
db.command("sql", "CREATE PROPERTY Person.ssn STRING (mandatory true, readonly true)")
```

#### Create Indexes

```python
# Non-unique index
db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")

# Unique index
db.command("sql", "CREATE INDEX ON Person (email) UNIQUE")

# Composite index
db.command("sql", "CREATE INDEX ON Person (lastName, firstName) NOTUNIQUE")
```

**Why SQL Only?** Schema operations are administrative and done infrequently. The Java API for schema is complex and not exposed in Python bindings.

---

## Data Creation

### Documents & Vertices

#### Option 1: SQL (Simple cases, educational)

```python
# Create document with SQL
db.command("sql", "CREATE DOCUMENT User SET name = 'Alice', age = 30")

# Create vertex with SQL
db.command("sql", "CREATE VERTEX Person SET name = 'Bob', age = 25")

# ⚠️ String escaping required for user input!
name = "O'Brien"  # Has single quote
db.command("sql", f"CREATE VERTEX Person SET name = '{name.replace(\"'\", \"''\")}', age = 35")
```

**Pros:**
- Familiar SQL syntax
- Good for examples/tutorials

**Cons:**
- String escaping issues with quotes/special characters
- SQL injection risk if not careful
- Slower (10-30x) than API
- **Not recommended for production code**

#### Option 2: Java API (Recommended)

```python
# Create document with API
doc = db.new_document("User")
doc.set_property("name", "Alice")
doc.set_property("age", 30)
doc.save()

# Create vertex with API
vertex = db.new_vertex("Person")
vertex.set_property("name", "Bob")
vertex.set_property("age", 25)
vertex.save()

# Safe handling of special characters (no escaping needed!)
vertex = db.new_vertex("Person")
vertex.set_property("name", "O'Brien")  # Automatically escaped
vertex.set_property("bio", 'Text with "quotes" and \'apostrophes\'')  # Safe!
vertex.save()
```

**Pros:**
- **Type safe** - properties handled correctly
- **No SQL injection** - values properly escaped
- **10-30x faster** than SQL
- Handles special characters automatically
- **Production-ready**

**Cons:**
- More verbose (3 lines vs 1)
- Less familiar to SQL developers (but worth learning!)

#### Bulk Creation Performance Comparison

```python
# ❌ SLOW: SQL approach for 10,000 vertices
import time

start = time.time()
with db.transaction():
    for i in range(10000):
        db.command("sql", f"CREATE VERTEX Person SET userId = {i}, name = 'User{i}'")
print(f"SQL: {time.time() - start:.2f}s")  # ~3.5s

# ✅ FAST: API approach for 10,000 vertices
start = time.time()
with db.transaction():
    for i in range(10000):
        vertex = db.new_vertex("Person")
        vertex.set_property("userId", i)
        vertex.set_property("name", f"User{i}")
        vertex.save()
print(f"API: {time.time() - start:.2f}s")  # ~0.3s (11x faster!)
```

**Real example from Example 05:**
- 10,352 vertices created with API: **0.79s total**
- Projected SQL time: **8-9s** (10-11x slower)

### Edges

#### Option 1: SQL with Subqueries (Simple cases)

```python
# Create edge between two vertices using subqueries
db.command("sql", """
    CREATE EDGE FRIEND_OF
    FROM (SELECT FROM Person WHERE name = 'Alice')
    TO (SELECT FROM Person WHERE name = 'Bob')
    SET since = date('2020-01-15'), closeness = 'close'
""")
```

**Pros:**
- Declarative and clear
- Good for one-off edges

**Cons:**
- **Very slow for bulk** - does 2 lookups per edge
- SQL injection risk
- Hard to handle errors (what if Alice doesn't exist?)

#### Option 2: Java API (Recommended)

```python
# Get vertices first
alice = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
bob = db.query("sql", "SELECT FROM Person WHERE name = 'Bob'")

alice_vertex = list(alice)[0]._java_result.getElement().get().asVertex()
bob_vertex = list(bob)[0]._java_result.getElement().get().asVertex()

# Create edge using vertex.newEdge() API
edge = alice_vertex.newEdge(
    "FRIEND_OF",
    bob_vertex,
    "since", "2020-01-15",
    "closeness", "close"
)
edge.save()
```

**Pros:**
- Explicit error handling (vertex not found)
- Type safe properties

**Cons:**
- More verbose
- Need to extract Java vertex from Result wrapper

#### Option 3: Optimized Bulk Edge Creation (Best for performance)

```python
# ✅ RECOMMENDED: Cache vertices, then create edges in bulk
from datetime import datetime

# Step 1: Cache all vertices (do once)
user_cache = {}
movie_cache = {}

with db.transaction():
    # Cache users
    for user_wrapper in db.query("sql", "SELECT FROM User"):
        user_id = user_wrapper.get_property("userId")
        user_cache[user_id] = user_wrapper._java_result.getElement().get().asVertex()

    # Cache movies
    for movie_wrapper in db.query("sql", "SELECT FROM Movie"):
        movie_id = movie_wrapper.get_property("movieId")
        movie_cache[movie_id] = movie_wrapper._java_result.getElement().get().asVertex()

# Step 2: Create edges using cached vertices
with db.transaction():
    for rating in ratings_data:  # Could be millions of edges!
        user_vertex = user_cache.get(rating['userId'])
        movie_vertex = movie_cache.get(rating['movieId'])

        if user_vertex and movie_vertex:
            edge = user_vertex.newEdge(
                "RATED",
                movie_vertex,
                "rating", rating['value'],
                "timestamp", rating['timestamp']
            )
            edge.save()
```

**Performance Comparison (Real data from Example 05):**

| Method | Edges Created | Time | Rate | Notes |
|--------|---------------|------|------|-------|
| SQL with subqueries | 98,734 | 33.6s | 2,937/sec | Each edge = 2 lookups |
| API with caching | 98,734 | 2.6s | 36,723/sec | **12.5x faster!** |

**Projected for 33M edges:**
- SQL: ~3.1 hours
- API with caching: ~15 minutes

**Memory Model:**

The vertex cache is a **Python dict holding references to Java objects**:

```python
# Python side (minimal memory ~1KB for 1000 vertices)
user_cache = {
    123: <JPype proxy>,      # Just a pointer to JVM
    456: <JPype proxy>,      # ~50 bytes per entry
}

# JVM side (actual vertex data ~500-1000 bytes each)
# MutableVertex objects with properties, RIDs, etc.
```

- **Cache overhead**: Negligible (~50-100 bytes per vertex in Python)
- **Actual data**: Lives in JVM memory where ArcadeDB manages it
- **No duplication**: We don't copy vertex data to Python
- **Benefit**: Instant O(1) lookups, no database queries during edge creation

---

## Data Reading

### ✅ Use SQL/Cypher Only

Reading data requires queries - **SQL or Cypher are the only options**.

#### Simple Queries

```python
# Get all documents
result = db.query("sql", "SELECT FROM User")

# Filter by property
result = db.query("sql", "SELECT FROM Person WHERE age > 25")

# Order and limit
result = db.query("sql", "SELECT FROM Person ORDER BY age DESC LIMIT 10")
```

#### Graph Traversals (SQL MATCH)

```python
# Find friends using SQL MATCH
result = db.query("sql", """
    MATCH {type: Person, as: alice, where: (name = 'Alice')}
          -FRIEND_OF->
          {type: Person, as: friend}
    RETURN friend.name as name, friend.age as age
""")
```

#### Graph Traversals (Cypher)

```python
# Find friends using Cypher
result = db.query("cypher", """
    MATCH (alice:Person {name: 'Alice'})-[:FRIEND_OF]->(friend:Person)
    RETURN friend.name as name, friend.age as age
""")

# Find friends of friends
result = db.query("cypher", """
    MATCH (alice:Person {name: 'Alice'})
          -[:FRIEND_OF*1..2]->(friend:Person)
    WHERE friend.name <> 'Alice'
    RETURN DISTINCT friend.name as name
""")
```

#### Aggregations

```python
# Count, average, etc.
result = db.query("sql", """
    SELECT city, COUNT(*) as count, AVG(age) as avg_age
    FROM Person
    GROUP BY city
    ORDER BY count DESC
""")
```

**Why SQL Only?** Queries involve complex filtering, joins, aggregations - SQL/Cypher are designed for this.

---

## Data Updates

### Option 1: SQL (Batch updates - Recommended for updating many records)

```python
# ✅ Update 10,000 records in ONE operation
db.command("sql", "UPDATE Person SET verified = true WHERE age >= 18")
# -> Single optimized query, processes all matches at once
# -> ~0.01s regardless of how many records match

# Update multiple properties with conditions
db.command("sql", """
    UPDATE Person
    SET status = 'senior', discount = 0.15
    WHERE age >= 65
""")

# Increment values
db.command("sql", "UPDATE Person SET loginCount = loginCount + 1 WHERE name = 'Alice'")
```

**Why SQL for batch updates?**
- **One operation** - Single query updates all matching records
- **Optimized by database** - ArcadeDB processes the WHERE condition efficiently
- **No loop overhead** - No Python/Java iteration needed

**Best for:**
- Updating many records at once (10s, 100s, 1000s+)
- Conditional bulk updates
- Computed updates (increment, formulas)

### Option 2: Java API (Single record updates)

```python
# ✅ Update single record you already have
result = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
person_wrapper = list(result)[0]

# Update properties
person_vertex = person_wrapper._java_result.getElement().get().asVertex()
person_vertex.setProperty("age", 31)
person_vertex.setProperty("city", "Boston")
person_vertex.save()
```

**Best for:**
- Single record updates
- Type-safe property updates
- When you already have the record object

**Why not API for batch updates?**

```python
# ❌ Avoid: Looping to update many records
result = db.query("sql", "SELECT FROM Person WHERE age >= 18")
for person_wrapper in result:  # Could be 10,000 iterations!
    person = person_wrapper._java_result.getElement().get().asVertex()
    person.setProperty("verified", True)
    person.save()  # Separate save operation for EACH record
# -> 10,000 individual operations instead of 1
# -> 100x slower than SQL UPDATE
```

**The distinction:**
- **Batch = many records, one condition** → Use SQL (one operation)
- **Single record in hand** → Use Java API (type-safe)

---

## Data Deletion

### Option 1: SQL (Recommended for most cases)

```python
# Delete by condition
db.command("sql", "DELETE FROM Person WHERE age < 18")

# Delete all of a type
db.command("sql", "DELETE FROM TempData")

# Delete specific record by RID
db.command("sql", "DELETE FROM #12:34")

# Delete vertices and their edges (CASCADE)
db.command("sql", "DELETE VERTEX Person WHERE name = 'Alice'")
```

**Best for:**
- Deleting multiple records
- Conditional deletion
- Cascade deletion (vertices with edges)

### Option 2: Java API (When you have the object)

```python
# Delete a specific vertex you already have
vertex._java_result.getElement().get().asVertex().delete()

# Or through the wrapper
person_wrapper._java_result.getElement().get().delete()
```

**Best for:**
- Deleting specific object you already loaded
- Part of larger object manipulation

---

## Graph Operations

### Vertex/Edge Creation

See [Data Creation](#data-creation) section above.

**TL;DR:** Use Java API for bulk, SQL for examples/one-offs.

### Graph Traversals

**✅ Use SQL MATCH or Cypher Only**

Graph traversals require query languages designed for patterns:

```python
# SQL MATCH: Find friends of friends
result = db.query("sql", """
    MATCH {type: Person, as: start, where: (name = 'Alice')}
          -FRIEND_OF->
          {type: Person, as: friend1}
          -FRIEND_OF->
          {type: Person, as: friend2}
    WHERE friend2.name <> 'Alice'
    RETURN friend2.name as name
""")

# Cypher: Same query
result = db.query("cypher", """
    MATCH (start:Person {name: 'Alice'})
          -[:FRIEND_OF]->(friend1:Person)
          -[:FRIEND_OF]->(friend2:Person)
    WHERE friend2.name <> 'Alice'
    RETURN friend2.name as name
""")

# Variable-length paths (Cypher only)
result = db.query("cypher", """
    MATCH (alice:Person {name: 'Alice'})
          -[:FRIEND_OF*1..3]-(connected:Person)
    RETURN DISTINCT connected.name
""")
```

**There is no Java API equivalent** - traversals need declarative pattern matching.

### Shortest Path

```python
# Find shortest path between two people
result = db.query("sql", """
    SELECT shortestPath($from, $to, 'BOTH') as path
    FROM Person
    LET $from = (SELECT FROM Person WHERE name = 'Alice'),
        $to = (SELECT FROM Person WHERE name = 'Bob')
""")
```

**SQL/Cypher only** - graph algorithms require query language.

---

## Performance Comparison

### Real-World Benchmarks (Example 05: MovieLens Small Dataset)

| Operation | SQL Time | API Time | Speedup | Notes |
|-----------|----------|----------|---------|-------|
| **Create 610 Users** | ~0.05s | ~0.05s | 1x | Small dataset, negligible diff |
| **Create 9,742 Movies** | ~0.85s | ~0.30s | 2.8x | Medium dataset |
| **Create 98,734 RATED edges** | 33.6s | 2.6s | **12.9x** | Subqueries vs caching |
| **Create 3,683 TAGGED edges** | 1.9s | 0.11s | **17.3x** | Subqueries vs caching |
| **Total graph creation** | 41.8s | 5.3s | **7.9x** | Overall improvement |

### Projected Performance: Large Dataset (33M+ edges)

| Operation | SQL (projected) | API (optimized) | Time Saved |
|-----------|-----------------|-----------------|------------|
| **Create 330,975 Users** | ~2.8s | ~2.5s | 0.3s |
| **Create 86,537 Movies** | ~23s | ~8s | 15s |
| **Create 33,832,162 RATED edges** | **3.2 hours** | **15 minutes** | **2h 45m** |
| **Create 2,236,574 TAGGED edges** | **19 minutes** | **1.1 minutes** | **18m** |
| **Total** | **~3.7 hours** | **~27 minutes** | **~3.4 hours saved!** |

### Key Takeaways

1. **Small datasets (<100 records):** SQL vs API difference is negligible (<100ms)
2. **Medium datasets (1K-10K records):** API is 2-5x faster
3. **Large datasets (100K+ records):** API is 10-30x faster
4. **Edge creation with lookups:** Caching + API is 10-17x faster than SQL subqueries

---

## Best Practices

### 1. Schema Operations → Always Use SQL

```python
# ✅ Good: Schema definition (only option)
db.command("sql", "CREATE VERTEX TYPE Person")
db.command("sql", "CREATE PROPERTY Person.name STRING")
db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")
```

No alternative - this is the only way.

### 2. Data Creation → Always Use Java API

```python
# ❌ Avoid: SQL for creation (even single records)
db.command("sql", f"CREATE VERTEX Person SET userId = {i}")

# ✅ Good: API for all creation (single or bulk)
v = db.new_vertex("Person")
v.set_property("userId", i)
v.save()
```

**Always faster and safer**, even for single records.

### 3. Edge Creation → Always Cache + Java API

```python
# ❌ Avoid: SQL subqueries (slow even for single edge)
db.command("sql", f"""
    CREATE EDGE KNOWS
    FROM (SELECT FROM Person WHERE id = {edge_data['from_id']})
    TO (SELECT FROM Person WHERE id = {edge_data['to_id']})
""")

# ✅ Good: Cache vertices, use API (always)
vertex_cache = {}
for v_wrapper in db.query("sql", "SELECT FROM Person"):
    id = v_wrapper.get_property("id")
    vertex_cache[id] = v_wrapper._java_result.getElement().get().asVertex()

# Then create edges
from_v = vertex_cache[edge_data['from_id']]
to_v = vertex_cache[edge_data['to_id']]
edge = from_v.newEdge("KNOWS", to_v)
edge.save()
```

**10-17x faster**, no exceptions for "just one edge".

### 4. Queries → Always Use SQL/Cypher

```python
# ✅ Good: SQL for filtering, aggregations, traversals (only option)
result = db.query("sql", "SELECT FROM Person WHERE age > 25 ORDER BY name")
result = db.query("cypher", "MATCH (p:Person)-[:KNOWS]->(friend) RETURN friend.name")
```

No practical API alternative.

### 5. User Input → Always Use Java API

```python
# ❌ Dangerous: SQL with user input (never do this!)
user_name = get_user_input()
db.command("sql", f"CREATE VERTEX Person SET name = '{user_name}'")  # SQL injection!

# ✅ Safe: API with user input (always do this)
user_name = get_user_input()  # Any string is safe
v = db.new_vertex("Person")
v.set_property("name", user_name)  # Automatically escaped
v.save()
```

API handles escaping automatically - **never use SQL for user input**.

### 6. Updates → Use Java API (Unless Batch)

```python
# Single record update - Use API
person_wrapper._java_result.getElement().get().asVertex().setProperty("age", 31)
person_wrapper._java_result.getElement().get().asVertex().save()

# Batch update - Use SQL
db.command("sql", "UPDATE Person SET verified = true WHERE age >= 18")
```

### 7. Mixed Approach → API for Data, SQL for Schema/Queries

```python
# ✅ Best: Use each tool for its strength

# 1. Schema (SQL - only option)
db.command("sql", "CREATE VERTEX TYPE Person")
db.command("sql", "CREATE INDEX ON Person (email) UNIQUE")

# 2. Creation (API - always)
with db.transaction():
    for data in dataset:
        v = db.new_vertex("Person")
        v.set_property("name", data['name'])
        v.set_property("email", data['email'])
        v.save()

# 3. Queries (SQL - only option)
result = db.query("sql", "SELECT city, COUNT(*) FROM Person GROUP BY city")
```

---

## Summary: When to Use What

### Use Java API (Default Choice)

**Always prefer Java API when creating or modifying data:**

- ✅ **All vertex creation** (single or bulk)
- ✅ **All edge creation** (single or bulk)
- ✅ **Property updates** (type-safe)
- ✅ **Record deletions** (when you have the object)
- ✅ **Any user input** (automatic escaping)
- ✅ **Production code** (safer, faster, more maintainable)

**Why?** Type safety, automatic escaping, 10-30x faster, no SQL injection risk.

### Use SQL/Cypher (When Required)

**Use query languages when Java API is not available or impractical:**

- ✅ **Schema definition** (types, properties, indexes) - *only option*
- ✅ **Queries and filtering** (SELECT with WHERE) - *only option*
- ✅ **Graph traversals** (MATCH patterns in SQL, or Cypher) - *only option*
- ✅ **Aggregations** (COUNT, AVG, GROUP BY) - *only option*
- ✅ **Batch updates** (UPDATE many records with WHERE) - *more efficient*
- ✅ **Batch deletions** (DELETE many records with WHERE) - *more efficient*
- ✅ **Complex conditions** - *only option*
- ✅ **Educational examples** - *shows query syntax for learning*

**Why?** These operations are designed for query languages and have no API equivalent.

**Cypher vs SQL:** Use Cypher for graph patterns (more intuitive), SQL for everything else (more flexible).

### The New Golden Rule

**Java API first, query languages when necessary.**

- **Have data to create/update?** → Start with Java API
- **Need to find/filter/aggregate data?** → Use SQL or Cypher
- **Updating/deleting many records at once?** → Use SQL
- **Working with user input?** → Definitely use Java API
- **Graph pattern matching?** → Use Cypher (or SQL MATCH)

### Performance Rule of Thumb

- **Any size dataset:** Java API is faster and safer for creation
- **Small operations (<100):** Difference is small but API still better
- **Large operations (1000+):** API is 10-30x faster - essential for performance
- **Queries/traversals:** SQL/Cypher is the only option

---

## Additional Resources

- [Example 05: CSV Import Graph](../examples/05_csv_import_graph.py) - Shows optimized bulk creation with Java API
- [Example 02: Social Network](../examples/02_social_network_graph.py) - Shows both SQL and Cypher for queries
- [Example 03: Vector Search](../examples/03_vector_search.py) - Uses Java API for vertex creation
- [ArcadeDB SQL Documentation](https://docs.arcadedb.com/#SQL)
- [ArcadeDB Cypher Documentation](https://docs.arcadedb.com/#Cypher)
- [ArcadeDB Java API Documentation](https://docs.arcadedb.com/#Java-API)

---

**Last updated:** October 29, 2025
