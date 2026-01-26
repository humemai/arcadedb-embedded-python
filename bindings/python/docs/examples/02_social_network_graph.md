# Social Network Graph Example

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/02_social_network_graph.py){ .md-button }

## Overview

This example demonstrates how to use ArcadeDB as a graph database to model and query social networks. It showcases the power of graph databases for representing and traversing complex relationships between entities.

**What You'll Learn:**

- Creating vertex and edge types (schema definition)
- Modeling entities (Person) and relationships (FRIEND_OF) with properties
- NULL value handling for optional vertex properties (email, phone, reputation)
- Graph traversal patterns (friends, friends-of-friends, mutual connections)
- **Comparing SQL MATCH vs OpenCypher query languages**
- **Performance characteristics of each query language**
- Variable-length path queries (`*1..3` syntax in OpenCypher)
- Working with relationship properties and bidirectional edges
- Filtering by NULL values (finding people without email/phone)
- Proper transaction handling and property access patterns
- Real-world graph database implementation techniques

## ⚡ SQL MATCH vs OpenCypher

This example compares SQL MATCH and OpenCypher for expressing the same graph traversals.

### Guidance

- **SQL MATCH** is a good choice for SQL developers and reporting-style queries.
- **OpenCypher** is expressive for path-based traversals and graph patterns.
- Choose the language that best matches your team's familiarity and your query style.

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
    person = db.new_vertex("Person")
    person.set("name", "Alice Johnson")
    person.set("age", 28)
    person.set("city", "New York")
    person.save()
```

### Edges (Relationships)
Connect vertices with optional properties:
```python
# Bidirectional friendship with relationship metadata
with db.transaction():
    alice = list(db.query("sql", "SELECT FROM Person WHERE name = 'Alice Johnson'"))[0].get_vertex()
    bob = list(db.query("sql", "SELECT FROM Person WHERE name = 'Bob Smith'"))[0].get_vertex()

    edge = alice.new_edge("FRIEND_OF", bob)
    edge.set("since", "2020-05-15")
    edge.set("closeness", "close")
    edge.save()
```

### Schema Definition
Define types and properties upfront for consistency:
```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./social_network_db") as db:
    # Create vertex type with properties (schema ops are auto-transactional)
    db.schema.create_vertex_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")
    db.schema.create_property("Person", "city", "STRING")
    db.schema.create_property("Person", "joined_date", "DATE")
    db.schema.create_property("Person", "email", "STRING")      # Optional (can be NULL)
    db.schema.create_property("Person", "phone", "STRING")      # Optional (can be NULL)
    db.schema.create_property("Person", "verified", "BOOLEAN")
    db.schema.create_property("Person", "reputation", "FLOAT")  # Optional (can be NULL)

    # Create edge type with properties
    db.schema.create_edge_type("FRIEND_OF")
    db.schema.create_property("FRIEND_OF", "since", "DATE")
    db.schema.create_property("FRIEND_OF", "closeness", "STRING")

    # Create indexes for performance
    db.schema.create_index("Person", ["name"], unique=False)
```

## Query Examples

The example demonstrates 6 queries in each of three languages:

### SQL MATCH Queries

```sql
-- 1. Find all friends of Alice
MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
      -FRIEND_OF->
      {type: Person, as: friend}
RETURN friend.name as name, friend.city as city
ORDER BY friend.name
```

```sql
-- 2. Find friends of friends of Alice
MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
      -FRIEND_OF->
      {type: Person, as: friend}
      -FRIEND_OF->
      {type: Person, as: friend_of_friend, where: (name <> 'Alice Johnson')}
RETURN DISTINCT friend_of_friend.name as name, friend.name as through_friend
ORDER BY friend_of_friend.name
```

```sql
-- 3. Find mutual friends between Alice and Bob
MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
      -FRIEND_OF->
      {type: Person, as: mutual}
      <-FRIEND_OF-
      {type: Person, as: bob, where: (name = 'Bob Smith')}
RETURN mutual.name as mutual_friend
ORDER BY mutual.name
```

```sql
-- 4. Friendship statistics by city (SQL aggregation)
SELECT city, COUNT(*) as person_count,
       AVG(age) as avg_age
FROM Person
GROUP BY city
ORDER BY person_count DESC, city
```

```sql
-- 5. Find people without email (SQL NULL check)
SELECT name, phone, verified
FROM Person
WHERE email IS NULL
```

```sql
-- 6. Verified people with reputation (exclude NULLs)
SELECT name, reputation, city
FROM Person
WHERE verified = true AND reputation IS NOT NULL
ORDER BY reputation DESC
```

### OpenCypher Queries

```cypher
-- 1. Find all friends of Alice
MATCH (alice:Person {name: 'Alice Johnson'})-[:FRIEND_OF]->(friend:Person)
RETURN friend.name as name, friend.city as city
ORDER BY friend.name
```

```cypher
-- 2. Find friends of friends of Alice
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF]->(friend:Person)
      -[:FRIEND_OF]->(fof:Person)
WHERE fof.name <> 'Alice Johnson'
RETURN DISTINCT fof.name as name, friend.name as through_friend
ORDER BY fof.name
```

```cypher
-- 3. Find mutual friends between Alice and Bob
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF]->(mutual:Person)
      <-[:FRIEND_OF]-(bob:Person {name: 'Bob Smith'})
RETURN mutual.name as mutual_friend
ORDER BY mutual.name
```

```cypher
-- 4. Find close friendships (Cypher)
MATCH (p1:Person)-[f:FRIEND_OF {closeness: 'close'}]->(p2:Person)
RETURN p1.name as person1, p2.name as person2, f.since as since
ORDER BY f.since
```

```cypher
-- 5. Count friends per person (Cypher aggregation)
MATCH (p:Person)
OPTIONAL MATCH (p)-[:FRIEND_OF]->(friend:Person)
RETURN p.name as name, COUNT(friend) as friend_count
ORDER BY friend_count DESC, name
```

```cypher
-- 6. Find connections within 3 steps from Alice (Cypher)
MATCH (alice:Person {name: 'Alice Johnson'})
      -[:FRIEND_OF*1..3]-(connected:Person)
WHERE connected.name <> 'Alice Johnson'
RETURN DISTINCT connected.name as name, connected.city as city
ORDER BY connected.name
```

## NULL Value Handling in Graphs

Graph vertices can have optional properties with NULL values:

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./social_network_db") as db:
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

    # Querying for NULL Values - Find vertices with missing optional properties
    # Find people without email addresses (reads don't need transaction)
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

## Performance Considerations

### Indexing
Create indexes on frequently queried properties:
```python
# Index on person names for fast lookups
db.schema.create_index("Person", ["name"], unique=False)

# For unique identifiers
db.schema.create_index("Person", ["person_id"], unique=True)
```

### Batch Operations
For large datasets, use batch operations:
```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./social_network_db") as db:
    # Batch vertex creation (all inside single transaction)
    large_dataset = [{"name": "Person1"}, {"name": "Person2"}]  # Example data

    with db.transaction():
        for person_data in large_dataset:
            db.command("sql", f"CREATE VERTEX Person SET name = '{person_data['name']}'")
            # Transaction automatically commits at end of 'with' block
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
# Always use .get() for query results
for row in result:
    name = row.get('name')  # ✅ Correct
    city = row.get('city')  # ✅ Correct
    # name = row['name']    # ❌ Wrong - will fail
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

## Related Examples

- [**01 - Simple Document Store**](01_simple_document_store.md) - Foundation example with document types and CRUD operations
- [**03 - Vector Search**](03_vector_search.md) - Semantic similarity search with HNSW indexing
- [**05 - CSV Import (Graph)**](05_csv_import_graph.md) - Creating graph structures from CSV data
- [**06 - Vector Search Recommendations**](06_vector_search_recommendations.md) - Semantic search and movie recommendations
- [**07 - Multi-Model Stack Overflow**](07_stackoverflow_multimodel.md) - Combining graph, documents, and vectors

## Next Steps

- Learn about [Vector Search](03_vector_search.md) for AI-powered semantic search
- Explore [CSV Import (Graph)](05_csv_import_graph.md) for importing graph data from files
- See [Multi-Model Stack Overflow](07_stackoverflow_multimodel.md) for combining graph with documents and vectors
- Check out [Server Mode & HTTP API](08_server_mode_rest_api.md) for production deployment
