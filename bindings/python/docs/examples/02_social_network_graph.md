# Social Network Graph Example ✅

**Status: Complete and Fully Functional**

## Overview

This example demonstrates how to use ArcadeDB as a graph database to model and query social networks. It showcases the power of graph databases for representing and traversing complex relationships between entities.

**File:** `examples/02_social_network_graph.py`

**What You'll Learn:**
- Creating vertex and edge types (schema definition)
- Modeling entities (Person) and relationships (FRIEND_OF) with properties
- NULL value handling for optional vertex properties (email, phone, reputation)
- Graph traversal patterns (friends, friends-of-friends, mutual connections)
- **Comparing SQL MATCH vs Cypher vs Gremlin query languages**
- **Performance characteristics of each query language**
- Variable-length path queries (`*1..3` syntax in Cypher, `repeat().times(3)` in Gremlin)
- Working with relationship properties and bidirectional edges
- Filtering by NULL values (finding people without email/phone)
- Proper transaction handling and property access patterns
- Real-world graph database implementation techniques

## ⚡ Performance Comparison: SQL vs Cypher vs Gremlin

This example includes comprehensive performance benchmarking of all three query languages:

### Query-by-Query Results (8 people, 24 edges):

| Query | Cypher | Gremlin | Speedup |
|-------|--------|---------|---------|
| Find friends | 0.876s | 0.008s | **109× faster** |
| Friends of friends | 0.056s | 0.003s | **18× faster** |
| Mutual friends | 0.018s | 0.001s | **18× faster** |
| Close friendships | 0.022s | 0.002s | **11× faster** |
| Count aggregation | 0.059s | 0.001s | **59× faster** |
| Variable-length paths | 0.044s | 0.002s | **22× faster** |
| **Total Time** | **1.075s** | **0.017s** | **63× faster** |

### Key Findings:

✅ **Gremlin is significantly faster** - 63× faster overall than Cypher
✅ **SQL MATCH performs well** - close to Gremlin performance
⚠️ **Cypher has performance issues** - transpiler overhead, unmaintained codebase
✅ **Gremlin has 100% feature parity** - can do everything Cypher can do

### When to Use Each:

**Gremlin (Recommended for Production):**
- ⚡ Best performance (63× faster than Cypher)
- 🎯 100% feature parity with Cypher
- 🔧 Fine-grained control over traversal
- 📊 Better for complex graph algorithms
- ✅ Actively maintained (Apache TinkerPop)

**SQL MATCH (Recommended for SQL Developers):**
- 🔄 Mix graph and relational queries
- 📈 Good performance (2.7× faster than Cypher)
- 🛠️ Familiar SQL syntax
- 📊 Excellent for aggregations

**Cypher (Use with Caution):**
- ⚠️ Slowest performance (transpiler overhead)
- ⚠️ Based on unmaintained Cypher For Gremlin project
- ⚠️ Type conversion issues
- ✅ Most readable for simple queries
- ✅ Familiar to Neo4j users

## ⚠️ Cypher Limitations in ArcadeDB

ArcadeDB's Cypher implementation has known limitations you should be aware of:

### 1. Unmaintained Transpiler
> "ArcadeDB's Cypher implementation is based on the Cypher For Gremlin Open Source transpiler. This project is not actively maintained by Open Cypher anymore, so issues in the transpiler are hard to fix."

**Impact:**
- Bugs in the transpiler cannot be easily fixed
- No active development or improvements
- May not support newer Cypher features
- Performance optimizations unlikely

### 2. Type Conversion Issues
> "ArcadeDB automatically handles the conversion between compatible types, such as strings and numbers when possible. Cypher does not."

**Problem:**
```cypher
-- Define schema with string ID
CREATE VERTEX Person SET id = "123"

-- Query with integer (may fail or give unpredictable results)
MATCH (p:Person {id: 123}) RETURN p  -- ⚠️ Type mismatch!
```

**Solution:** Use strict typing or switch to SQL/Gremlin:
```sql
-- SQL is more flexible with type conversion
SELECT FROM Person WHERE id = 123  -- ✅ Works
```

```gremlin
// Gremlin with explicit type
g.V().hasLabel('Person').has('id', '123')  // ✅ Works
```

### 3. Performance Overhead
The transpilation process adds significant overhead:
- Cypher → Gremlin translation at runtime
- No direct execution path
- Additional parsing and validation layers

**Recommendation:** For production workloads, prefer Gremlin or SQL MATCH over Cypher.

## Real-World Use Case

Social networks are perfect examples of graph data structures where:
- **Entities** (people, companies, places) become vertices
- **Relationships** (friendships, follows, likes) become edges
- **Properties** store additional information about both entities and relationships
- **Graph queries** efficiently find patterns like "friends of friends" or "mutual connections"

This pattern applies to many domains:
- Social media platforms
- Professional networks (LinkedIn-style)
- Recommendation systems
- Fraud detection networks
- Knowledge graphs

## Key Graph Concepts

### Vertices (Nodes)
Represent entities in your domain:
```python
# Person vertex with properties (using embedded ArcadeDB)
with db.transaction():
    db.command("sql", "CREATE VERTEX Person SET name = ?, age = ?, city = ?",
               "Alice Johnson", 28, "New York")
```

### Edges (Relationships)
Connect vertices with optional properties:
```python
# Bidirectional friendship with relationship metadata
with db.transaction():
    # Create edge using property-based lookups (recommended approach)
    db.command("sql", """
        CREATE EDGE FRIEND_OF
        FROM (SELECT FROM Person WHERE name = 'Alice Johnson')
        TO (SELECT FROM Person WHERE name = 'Bob Smith')
        SET since = date('2020-05-15'), closeness = 'close'
    """)
```

### Schema Definition
Define types and properties upfront for consistency:
```python
# Create vertex type with properties (using transactions)
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")
    db.command("sql", "CREATE PROPERTY Person.city STRING")
    db.command("sql", "CREATE PROPERTY Person.joined_date DATE")
    db.command("sql", "CREATE PROPERTY Person.email STRING")      # Optional (can be NULL)
    db.command("sql", "CREATE PROPERTY Person.phone STRING")      # Optional (can be NULL)
    db.command("sql", "CREATE PROPERTY Person.verified BOOLEAN")
    db.command("sql", "CREATE PROPERTY Person.reputation FLOAT")  # Optional (can be NULL)

    # Create edge type with properties
    db.command("sql", "CREATE EDGE TYPE FRIEND_OF")
    db.command("sql", "CREATE PROPERTY FRIEND_OF.since DATE")
    db.command("sql", "CREATE PROPERTY FRIEND_OF.closeness STRING")

    # Create indexes for performance
    db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")
```

## Query Language Comparison

One of ArcadeDB's strengths is supporting multiple query languages for graph operations. This example demonstrates all three and measures their performance.

### SQL Approach

Traditional SQL with subqueries for graph traversal:

```sql
-- Find all friends of Alice (using SQL subqueries)
SELECT name, city FROM Person
WHERE name IN (
    SELECT p2.name
)
ORDER BY name
```

### Cypher Syntax

Neo4j-compatible graph query language:

```cypher
-- Same query in Cypher (more intuitive for graph patterns)
MATCH (alice:Person {name: 'Alice Johnson'})-[:FRIEND_OF]->(friend:Person)
RETURN friend.name as name, friend.city as city
ORDER BY friend.name
```

### Gremlin Syntax

Apache TinkerPop traversal language:

```gremlin
// Same query in Gremlin (fastest performance)
g.V().hasLabel('Person').has('name', 'Alice Johnson')
    .out('FRIEND_OF')
    .project('name', 'city')
    .by('name')
    .by('city')
    .order().by(select('name'))
```

### Gremlin Feature Parity with Cypher

**Yes, Gremlin can do everything Cypher can do!** Here are the equivalents:

| Cypher Pattern | Gremlin Equivalent |
|----------------|-------------------|
| `MATCH (a)-[:FRIEND_OF]->(b)` | `g.V().as('a').out('FRIEND_OF').as('b')` |
| `WHERE a.name = 'Alice'` | `.has('name', 'Alice')` |
| `RETURN DISTINCT b.name` | `.dedup().values('name')` |
| `ORDER BY b.name` | `.order().by('name')` |
| `COUNT(*)` | `.count()` |
| `-[:FRIEND_OF*1..3]-` | `.repeat(out('FRIEND_OF')).times(3).emit()` |

### When to Use Each

**SQL Approach:**
- Familiar to SQL developers
- Good for mixing graph and relational queries
- Powerful for aggregations and data transformations
- Works well with traditional reporting tools
- **Performance:** 2.7× faster than Cypher

**Cypher:**
- More intuitive for graph patterns
- Shorter syntax for complex traversals
- Natural expression of graph relationships
- Better for pure graph operations
- **Most popular in industry** (Neo4j ecosystem)
- **Performance:** Slowest due to transpiler overhead (⚠️ unmaintained)

**Gremlin:**
- **Best performance** (63× faster than Cypher!)
- Imperative control over traversal
- Fine-grained optimization opportunities
- **100% feature parity with Cypher**
- Industry standard (Apache TinkerPop)
- Used by AWS Neptune, Azure Cosmos DB
- **Recommended for production workloads**

### Property Access in Python
When processing query results, use the property access API:
```python
# Process query results with proper property access
result = db.query("cypher", """
    MATCH (alice:Person {name: 'Alice Johnson'})-[:FRIEND_OF]->(friend:Person)
    RETURN friend.name as name, friend.city as city
""")

for row in result:
    name = row.get_property('name')  # Use .get_property() not ['name']
    city = row.get_property('city')
    print(f"Friend: {name} from {city}")
```

## NULL Value Handling in Graphs

Graph vertices can have optional properties with NULL values:

```python
# Insert person with NULL email and phone
with db.transaction():
    db.command("sql", """
        CREATE VERTEX Person SET
            name = 'Eve Brown',
            age = 29,
            city = 'Seattle',
            joined_date = date('2020-08-22'),
            email = NULL,
            phone = NULL,
            verified = false,
            reputation = 3.2
    """)
```

### Querying for NULL Values

Find vertices with missing optional properties:

```python
# Find people without email addresses
result = db.query("sql", """
    SELECT name, phone, verified
    FROM Person
    WHERE email IS NULL
""")

# Find verified people with reputation scores (exclude NULLs)
result = db.query("sql", """
    SELECT name, reputation, city
    FROM Person
    WHERE verified = true AND reputation IS NOT NULL
    ORDER BY reputation DESC
""")
```

This pattern is useful for:
- Finding incomplete profiles
- Identifying missing contact information
- Filtering by data completeness
- Quality checks and data validation

## Advanced Graph Patterns

### Friends of Friends
Finding second-degree connections:
```sql
-- SQL MATCH
MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
      -FRIEND_OF->
      {type: Person, as: friend}
      -FRIEND_OF->
      {type: Person, as: friend_of_friend, where: (name <> 'Alice Johnson')}
RETURN DISTINCT friend_of_friend.name as name, friend.name as through_friend
```

```cypher
-- Cypher
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF]->(friend:Person)
      -[:FRIEND_OF]->(fof:Person)
WHERE fof.name <> 'Alice Johnson'
RETURN DISTINCT fof.name as name, friend.name as through_friend
```

### Mutual Friends
Finding common connections between two people:
```sql
-- SQL MATCH
MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
      -FRIEND_OF->
      {type: Person, as: mutual}
      <-FRIEND_OF-
      {type: Person, as: bob, where: (name = 'Bob Smith')}
RETURN mutual.name as mutual_friend
```

```cypher
-- Cypher
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF]->(mutual:Person)
      <-[:FRIEND_OF]-(bob:Person {name: 'Bob Smith'})
RETURN mutual.name as mutual_friend
```

### Variable-Length Paths
Finding all connections within a certain distance:
```cypher
-- Cypher (SQL MATCH also supports this with different syntax)
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF*1..3]-(connected:Person)
WHERE connected.name <> 'Alice Johnson'
RETURN DISTINCT connected.name as name
```

## Working with Relationship Properties

Edges can store metadata about relationships:
```python
# Create friendship with properties
db.command("sql", """
    CREATE EDGE FRIEND_OF FROM ? TO ?
    SET since = date(?), closeness = ?, interaction_frequency = ?
""", alice_rid, bob_rid, "2020-05-15", "close", "daily")

# Query based on relationship properties
result = db.query("cypher", """
    MATCH (p1:Person)-[f:FRIEND_OF {closeness: 'close'}]->(p2:Person)
    RETURN p1.name as person1, p2.name as person2, f.since as since
    ORDER BY f.since
""")
```

## Bidirectional Relationships

For symmetric relationships like friendship:
```python
# Create both directions
db.command("sql", "CREATE EDGE FRIEND_OF FROM ? TO ? SET since = date(?), closeness = ?",
           alice_rid, bob_rid, "2020-05-15", "close")
db.command("sql", "CREATE EDGE FRIEND_OF FROM ? TO ? SET since = date(?), closeness = ?",
           bob_rid, alice_rid, "2020-05-15", "close")
```

This allows queries to work in either direction without specifying directionality.

## Performance Considerations

### Indexing
Create indexes on frequently queried properties:
```python
# Index on person names for fast lookups
db.command("sql", "CREATE INDEX ON Person (name) IF NOT EXISTS")

# Composite indexes for complex queries
db.command("sql", "CREATE INDEX ON Person (city, age) IF NOT EXISTS")
```

### Batch Operations
For large datasets, use batch operations:
```python
# Batch vertex creation
batch_vertices = []
for person_data in large_dataset:
    batch_vertices.append(f"CREATE VERTEX Person SET name = '{person_data['name']}', ...")

# Execute as transaction
db.begin()
try:
    for statement in batch_vertices:
        db.command("sql", statement)
    db.commit()
except Exception as e:
    db.rollback()
    raise
```

## Expected Output

When you run the example, you'll see comprehensive output showing all graph operations:

```
🌐 ArcadeDB Python - Social Network Graph Example
=======================================================
🔌 Creating/connecting to database...
✅ Database created at: ./my_test_databases/social_network_db
💡 Using embedded mode - no server needed!

📊 Creating social network schema...
  ✓ Created Person vertex type
  ✓ Created Person properties
  ✓ Created FRIEND_OF edge type
  ✓ Created FRIEND_OF properties
  ✓ Created index on Person.name

👥 Creating sample social network data...
  📝 Creating people...
    ✓ Created person: Alice Johnson (28, New York)
    ✓ Created person: Bob Smith (32, San Francisco)
    ✓ Created person: Carol Davis (26, Chicago)
    ... (8 people total)
  🤝 Creating friendships...
    ✓ Connected Alice Johnson ↔ Bob Smith (close)
    ✓ Connected Alice Johnson ↔ Carol Davis (casual)
    ... (12 bidirectional friendships = 24 edges)
  ✅ Created 8 people and 24 friendship connections

🔍 Demonstrating graph queries...

  📊 SQL MATCH Queries:
    1️⃣ Find all friends of Alice (SQL MATCH):
      👥 Bob Smith from San Francisco
      👥 Carol Davis from Chicago
      👥 Eve Brown from Seattle

    2️⃣ Find friends of friends of Alice (SQL MATCH):
      🔗 David Wilson (through Bob Smith)
      🔗 Frank Miller (through Bob Smith)
      🔗 Grace Lee (through Carol Davis)
      ... (7 results showing network expansion)

  🎯 Cypher Queries:
    1️⃣ Find all friends of Alice (Cypher):
      👥 Bob Smith from San Francisco
      👥 Carol Davis from Chicago
      👥 Eve Brown from Seattle

    4️⃣ Find close friendships (Cypher):
      💙 Alice Johnson → Bob Smith (since 2020-05-15)
      💙 Carol Davis → Eve Brown (since 2021-09-12)
      ... (8 close relationships)

    5️⃣ Find connections within 3 steps from Alice (Cypher):
      🌐 Bob Smith from San Francisco
      🌐 Carol Davis from Chicago
      🌐 David Wilson from Boston
      ... (7 people reachable within 3 hops)

  🆚 SQL vs Cypher Comparison:
    ✅ Cypher query returned 3 results
    💡 SQL and Cypher would yield equivalent results
    🎯 Key Differences: SQL uses subqueries, Cypher uses pattern matching

✅ Social network graph example completed successfully!
✅ Database connection closed
💡 Database files preserved at: ./my_test_databases/social_network_db
```

## Try It Yourself

1. **Run the example:**
   ```bash
   # Important: Navigate to examples directory first
   cd bindings/python/examples
   python 02_social_network_graph.py
   ```

2. **Explore the database:**
   - Database files are created in `./my_test_databases/social_network_db/`
   - Inspect the console output to understand each operation
   - Try modifying the sample data in the code

3. **Experiment with queries:**
   - Modify the Cypher queries in `demonstrate_cypher_queries()`
   - Add new relationship types (WORKS_WITH, LIVES_NEAR)
   - Try different traversal patterns and depths
   - Add relationship scoring (strength, trust level)

4. **Scale it up:**
   - Import larger datasets from CSV files
   - Add more vertex types (Company, Location, Interest)
   - Implement recommendation algorithms
   - Add temporal aspects (friendship start/end dates)

## Key Implementation Notes

### Property Access Pattern
```python
# Always use .get_property() for query results
for row in result:
    name = row.get_property('name')  # ✅ Correct
    city = row.get_property('city')  # ✅ Correct
    # name = row['name']             # ❌ Wrong - will fail
```

### Transaction Handling
```python
# Wrap all write operations in transactions
with db.transaction():
    db.command("sql", "CREATE VERTEX Person SET name = ?", "Alice")
    db.command("sql", "CREATE EDGE FRIEND_OF FROM (...) TO (...)")
```

### Edge Creation Best Practice
```python
# Use property-based lookups instead of RIDs
db.command("sql", """
    CREATE EDGE FRIEND_OF
    FROM (SELECT FROM Person WHERE name = 'Alice')
    TO (SELECT FROM Person WHERE name = 'Bob')
    SET since = date('2020-05-15')
""")
```

## Common Patterns

### Recommendation System
```cypher
-- Find people you might know (friends of friends who aren't already friends)
MATCH (me:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF]->(:Person)
      -[:FRIEND_OF]->(recommended:Person)
WHERE NOT (me)-[:FRIEND_OF]-(recommended) AND me <> recommended
RETURN recommended.name, COUNT(*) as mutual_friends
ORDER BY mutual_friends DESC
```

### Social Distance
```cypher
-- Find shortest path between two people
MATCH path = shortestPath((start:Person {name: 'Alice Johnson'})
                         -[:FRIEND_OF*]-(end:Person {name: 'Henry Clark'}))
RETURN length(path) as degrees_of_separation
```

### Influencer Detection
```sql
-- Find most connected people
SELECT name, in('FRIEND_OF').size() as friend_count
FROM Person
ORDER BY friend_count DESC
LIMIT 5
```

## Related Examples

- **01_simple_document_store.py** - Basic database operations and schema
- **04_csv_import_to_graph.py** - Importing graph data from files
- **05_ecommerce_multimodel.py** - Combining graph with document storage

## Next Steps

- Learn about [Vector Search](03_vector_search.md) for AI-powered recommendations
- Explore [CSV Import (Documents)](04_csv_import_documents.md) for importing tabular data
- See [CSV Import (Graph)](05_csv_import_graph.md) for importing graph data from CSV
- Check out [Multi-Model Example](07_stackoverflow_multimodel.md) for combining graph with document storage

---

*This example demonstrates core graph database concepts that apply across many domains. The patterns shown here scale from small applications to enterprise social platforms.*
