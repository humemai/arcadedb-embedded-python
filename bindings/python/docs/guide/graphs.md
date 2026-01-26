# Graph Operations

ArcadeDB is a native multi-model database with first-class support for property graphs.
This guide covers working with vertices, edges, and graph traversals using the Python
bindings.

## Overview

ArcadeDB's graph model consists of:

- **Vertices (Nodes)**: Entities in your graph with properties
- **Edges (Relationships)**: Connections between vertices with optional properties
- **Types**: Schema definitions for vertices and edges

## Creating Graph Schema (Python API)

Define vertex and edge types with the embedded API (no SQL needed):

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./social") as db:
    # Create vertex types
    db.schema.create_vertex_type("Person")
    db.schema.create_vertex_type("Company")

    # Create edge types
    db.schema.create_edge_type("Knows")
    db.schema.create_edge_type("WorksFor")

    # Add properties to vertices
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")
    db.schema.create_property("Person", "email", "STRING")

    # Add properties to edges
    db.schema.create_property("Knows", "since", "DATE")
    db.schema.create_property("WorksFor", "role", "STRING")

    print("✅ Graph schema created")
```

!!! info "Prefer the embedded API"
    SQL still works, but the Python API is safer (no string quoting issues) and keeps your code Python-first.

## Creating Vertices

### Using the API (recommended)

Create vertices programmatically with `new_vertex()`:

```python
with db.transaction():
    # Create a vertex using the API
    vertex = db.new_vertex("Person")
    vertex.set("name", "Charlie")
    vertex.set("age", 35)
    vertex.set("email", "charlie@example.com")
    vertex.save()

    print(f"✅ Created vertex with RID: {vertex.get_rid()}")
```

### Using SQL

SQL is still available if you prefer declarative inserts:

```python
with db.transaction():
    db.command("sql", """
        CREATE VERTEX Person
        SET name = 'Alice', age = 30, email = 'alice@example.com'
    """)
```

!!! tip "When to Use Each Approach"
    - **API (default)**: Programmatic control, safer than string-building
    - **SQL**: When you’re talking to a remote/server instance (HTTP/Binary)

## Creating Edges

**Important**: In ArcadeDB, edges are created **from vertices**, not from the database
directly. This is the proper graph model - edges represent connections between existing
vertices.

### Why No `db.new_edge()` Method?

Unlike `db.new_vertex()` and `db.new_document()`, there is no `db.new_edge()` method. This is by design in ArcadeDB's API:

- Edges conceptually **belong to vertices** - they represent relationships
- You must have both vertices before creating a connection
- Edges are created by calling `vertex.new_edge(edgeType, toVertex, **properties)`

### Creating Edges with the Python Graph API (recommended)

To create edges programmatically, you must:

1. Create or retrieve both vertices
2. Call `new_edge()` on the source vertex
3. Save the edge

```python
with db.transaction():
    # Create vertices
    alice = db.new_vertex("Person")
    alice.set("name", "Alice")
    alice.set("id", 1)
    alice.save()

    bob = db.new_vertex("Person")
    bob.set("name", "Bob")
    bob.set("id", 2)
    bob.save()

    # Create edge FROM alice TO bob
    # Note: Called on the vertex, not the database!
    edge = alice.new_edge("Knows", bob)
    edge.set("since", "2020-01-15")
    edge.save()

    print(f"✅ Created edge: {alice.get('name')} -> {bob.get('name')}")
```

### Creating Edges with SQL

You can also create edges declaratively:

```python
with db.transaction():
    db.command("sql", """
        CREATE EDGE Knows
        FROM (SELECT FROM Person WHERE id = 1)
        TO (SELECT FROM Person WHERE id = 2)
        SET since = date('2020-01-15')
    """)
```

### Creating Edges with Retrieved Vertices

Often you'll create edges between existing vertices:

```python
# Query for existing vertices
result_alice = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
result_bob = db.query("sql", "SELECT FROM Person WHERE name = 'Bob'")

if result_alice.has_next() and result_bob.has_next():
    alice = result_alice.next().get_vertex()
    bob = result_bob.next().get_vertex()

    with db.transaction():
        # Create edge between existing vertices
        edge = alice.new_edge("Knows", bob)
        edge.set("since", "2020-01-15")
        edge.save()
```

!!! warning "Vertex Must Be Saved First"
    Before creating an edge, both vertices must be saved (have a valid RID).
    Attempting to create an edge with unsaved vertices will raise an error:
    ```
    IllegalArgumentException: Current vertex is not persistent. Call save() first
    ```

### Listing Edges from a Vertex

The graph wrappers provide directional helpers with optional label filters:

```python
# Outgoing edges (optionally filter by label)
out_edges = alice.get_out_edges()           # all labels
knows_out = alice.get_out_edges("Knows")    # only Knows edges

# Incoming edges
in_edges = alice.get_in_edges()

# Both directions
both_edges = alice.get_both_edges()
```

Each item is an `Edge` wrapper; use edge.get_out() / edge.get_in() to reach the connected vertices.

### Creating Edges with OpenCypher

OpenCypher provides clear graph patterns for creating edges:

```python
with db.transaction():
    # Create vertices and edge using OpenCypher
    db.command("opencypher", """
        CREATE (alice:Person {name: 'Alice', age: 30})
        CREATE (bob:Person {name: 'Bob', age: 25})
        CREATE (alice)-[:Knows {since: 2020}]->(bob)
    """)
```

Or connect existing vertices:

```python
with db.transaction():
    db.command("opencypher", """
        MATCH (alice:Person {name: 'Alice'}), (bob:Person {name: 'Bob'})
        CREATE (alice)-[:Knows {since: 2020}]->(bob)
    """)
```

## Complete Example: Social Network

Here's a complete example building a small social network:

```python
import arcadedb_embedded as arcadedb

def create_social_network():
    with arcadedb.create_database("./social_network") as db:
        # 1. Create schema
        print("Creating schema...")
        db.schema.create_vertex_type("Person")
        db.schema.create_edge_type("Knows")
        db.schema.create_property("Person", "name", "STRING")
        db.schema.create_property("Person", "age", "INTEGER")
        db.schema.create_property("Knows", "since", "INTEGER")

        # 2. Create vertices and edges
        print("Creating graph data...")
        with db.transaction():
            # Create people
            alice = db.new_vertex("Person")
            alice.set("name", "Alice")
            alice.set("age", 30)
            alice.save()

            bob = db.new_vertex("Person")
            bob.set("name", "Bob")
            bob.set("age", 25)
            bob.save()

            charlie = db.new_vertex("Person")
            charlie.set("name", "Charlie")
            charlie.set("age", 35)
            charlie.save()

            # Create relationships
            edge1 = alice.new_edge("Knows", bob)
            edge1.set("since", 2020)
            edge1.save()

            edge2 = bob.new_edge("Knows", charlie)
            edge2.set("since", 2019)
            edge2.save()

            edge3 = charlie.new_edge("Knows", alice)
            edge3.set("since", 2021)
            edge3.save()

        print("✅ Graph created\n")

        # 3. Query the graph with OpenCypher
        print("Finding Alice's friends:")
        result = db.query("opencypher", """
            MATCH (p:Person {name: 'Alice'})-[:Knows]->(friend:Person)
            RETURN friend.name as name, friend.age as age
            ORDER BY name
        """)

        for record in result:
            name = record.get('name')
            age = record.get('age')
            print(f"  - {name}, age {age}")

        print("\nFinding friends of friends:")
        result = db.query("opencypher", """
            MATCH (p:Person {name: 'Alice'})-[:Knows]->(:Person)-[:Knows]->(fof:Person)
            WHERE fof.name <> 'Alice'
            RETURN DISTINCT fof.name as name
            ORDER BY name
        """)

        for record in result:
            print(f"  - {record.get('name')}")

if __name__ == "__main__":
    create_social_network()
```

## Best Practices

### 1. Always Use Transactions for Writes

```python
# ✅ Good - wrapped in transaction
with db.transaction():
    vertex = db.new_vertex("Person")
    vertex.set("name", "Alice")
    vertex.save()

# ❌ Bad - will fail
vertex = db.new_vertex("Person")  # Error: No transaction!
```

### 2. Create Indexes for Frequent Lookups

```python
# Index properties used in WHERE clauses (Python schema API)
db.schema.create_index("Person", ["name", "email"], unique=False)
```

### 3. Use OpenCypher for Graph Queries

OpenCypher provides expressive graph patterns and path queries.

```python
result = db.query("opencypher", """
    MATCH (p:Person {name: 'Alice'})-[:Knows]->(friend:Person)
    RETURN friend.name as name
    ORDER BY name
""")
```

### 4. Save Vertices Before Creating Edges

```python
with db.transaction():
    v1 = db.new_vertex("Person")
    v1.set("name", "Alice")
    v1.save()  # ✅ Must save first!

    v2 = db.new_vertex("Person")
    v2.set("name", "Bob")
    v2.save()  # ✅ Must save first!

    # Now can create edge
    edge = v1.new_edge("Knows", v2)
    edge.save()
```

## Deleting Records

Deleting vertices, edges, and documents requires understanding cascade behavior and the
different deletion approaches available.

### Deletion Approaches

#### 1. SQL DELETE (Recommended for reliability)

Use SQL `DELETE` for reliable deletion in all scenarios:

```python
with db.transaction():
    # Delete vertex by RID
    db.command("sql", "DELETE FROM Person WHERE @rid = #1:0")

    # Delete by property
    db.command("sql", "DELETE FROM Person WHERE name = 'Alice'")

    # Delete edges
    db.command("sql", "DELETE FROM Knows WHERE @rid = #2:0")
```

**Advantages:**

- ✅ Works reliably in all situations
- ✅ Supports complex WHERE clauses
- ✅ Batch delete multiple records
- ✅ Best for query results

#### 2. Wrapper `.delete()` Method

Use the `.delete()` method on fresh lookups:

```python
with db.transaction():
    # Works on objects from lookup_by_rid()
    vertex = db.lookup_by_rid("#1:0")
    vertex.delete()

    # Works on newly created objects
    new_vertex = db.new_vertex("Person")
    new_vertex.set("name", "Bob")
    new_vertex.save()
    new_vertex.delete()
```

**⚠️ Important Limitation:**

- ❌ Does NOT work on query results
- ✅ Works on fresh lookups via `lookup_by_rid()`
- ✅ Works on newly created objects

```python
# ❌ DON'T DO THIS - delete() won't work on query results
results = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
for record in results:
    record.delete()  # This is a no-op!

# ✅ DO THIS INSTEAD - use SQL DELETE
with db.transaction():
    db.command("sql", "DELETE FROM Person WHERE name = 'Alice'")
```

### Cascade Behavior

#### Vertex Deletion

When you delete a vertex, **all connected edges are automatically deleted**:

```python
with db.transaction():
    # Create test data
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()
    edge = alice.new_edge("Knows", bob).save()

    alice_id = str(alice.get_identity())

# Verify setup
vertices_before = list(db.query("sql", "SELECT FROM Person"))
edges_before = list(db.query("sql", "SELECT FROM Knows"))
print(f"Before: {len(vertices_before)} vertices, {len(edges_before)} edges")

# Delete vertex
with db.transaction():
    alice = db.lookup_by_rid(alice_id)
    alice.delete()

# Check results
vertices_after = list(db.query("sql", "SELECT FROM Person"))
edges_after = list(db.query("sql", "SELECT FROM Knows"))
print(f"After: {len(vertices_after)} vertices, {len(edges_after)} edges")
# Output: After: 1 vertices, 0 edges (edge cascaded!)
```

#### Edge Deletion

When you delete an edge, **vertices remain intact**:

```python
with db.transaction():
    # Create test data
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()
    edge = alice.new_edge("Knows", bob).save()

    edge_id = str(edge.get_identity())

# Delete edge
with db.transaction():
    edge = db.lookup_by_rid(edge_id)
    edge.delete()

# Check results - vertices still exist
vertices = list(db.query("sql", "SELECT FROM Person"))
edges = list(db.query("sql", "SELECT FROM Knows"))
print(f"Vertices: {len(vertices)}")  # Output: 2
print(f"Edges: {len(edges)}")        # Output: 0
```

### Best Practices for Deletion

| Scenario | Recommended Approach | Why |
|----------|----------------------|-----|
| Delete from query results | SQL DELETE | `.delete()` doesn't work on query results |
| Delete single record by RID | SQL DELETE or `.delete()` | Both work, SQL is more flexible |
| Delete with complex WHERE clause | SQL DELETE | Much more readable and powerful |
| Delete in loop | SQL DELETE with WHERE clause | Single operation is faster than loop |
| Interactive/programmatic delete | `.delete()` on fresh lookup | Immediate feedback on same object |

**Summary: Use SQL DELETE by default**, except for immediate interactive deletion where you need to delete an object you just fetched.

## OpenCypher Queries

ArcadeDB supports OpenCypher for declarative graph pattern matching.

### Using OpenCypher

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./graph_db") as db:
    # Create schema (auto-transactional)
    db.schema.create_vertex_type("Person")
    db.schema.create_edge_type("Knows")

    # Insert data with Python API and query via OpenCypher
    with db.transaction():
        alice = db.new_vertex("Person").set("name", "Alice").set("age", 30)
        bob = db.new_vertex("Person").set("name", "Bob").set("age", 25)
        alice.save()
        bob.save()
        alice.new_edge("Knows", bob).save()

    # Query with OpenCypher
    results = db.query("opencypher", """
        MATCH (p:Person)
        WHERE p.age > 25
        RETURN p.name as name
    """)

    for record in results:
        print(record.get("name"))  # Outputs: Alice
```

### OpenCypher vs SQL

| Feature | OpenCypher | SQL |
|---------|-----------|-----|
| **Style** | Declarative graph patterns | Declarative |
| **Graph Traversal** | ✅ Excellent | ⚠️ Limited |
| **Readability** | High | High |
| **Standards Body** | openCypher | ANSI SQL |
| **Best For** | Graph patterns and paths | Relational queries |

### Common OpenCypher Patterns

```python
# Find all vertices
results = db.query("opencypher", "MATCH (n) RETURN n")

# Find vertices by label
results = db.query("opencypher", "MATCH (p:Person) RETURN p")

# Find vertices by property
results = db.query("opencypher", "MATCH (p:Person {name: 'Alice'}) RETURN p")

# Traverse outgoing edges
results = db.query("opencypher", """
    MATCH (p:Person {name: 'Alice'})-[:Knows]->(friend:Person)
    RETURN friend.name as name
""")

# Multi-hop traversal
results = db.query("opencypher", """
    MATCH (p:Person {name: 'Alice'})-[:Knows*2]->(fof:Person)
    RETURN DISTINCT fof.name as name
""")
```

### When to Use OpenCypher

- **Pattern matching**: Express graph structures declaratively
- **Multi-hop traversals**: Variable-length paths
- **Readable queries**: Clear syntax for graph relationships

For more details, see [OpenCypher Tests](../development/testing/test-opencypher.md).

## Next Steps

- **[Vector Search](vectors.md)**: Add vector embeddings to vertices for similarity search
- **[Data Import](import.md)**: Import graph data from CSV or ArcadeDB JSONL exports
- **[Server Mode](server.md)**: Visualize your graph in Studio UI
