# Graph Operations

ArcadeDB is a native multi-model database with first-class support for property graphs.
This guide covers working with vertices, edges, and graph traversals using the Python
bindings.

## Overview

ArcadeDB's graph model consists of:

- **Vertices (Nodes)**: Entities in your graph with properties
- **Edges (Relationships)**: Connections between vertices with optional properties
- **Types**: Schema definitions for vertices and edges

## Creating Graph Schema (SQL)

Define vertex and edge types with SQL statements:

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./social") as db:
    # Create vertex types
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE VERTEX TYPE Company")

    # Create edge types
    db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")
    db.command("sql", "CREATE EDGE TYPE WorksFor UNIDIRECTIONAL")

    # Add properties to vertices
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")
    db.command("sql", "CREATE PROPERTY Person.email STRING")

    # Add properties to edges
    db.command("sql", "CREATE PROPERTY Knows.since DATE")
    db.command("sql", "CREATE PROPERTY WorksFor.role STRING")

    print("✅ Graph schema created")
```

!!! info "DSL-first guidance"
    Prefer SQL/OpenCypher for schema and CRUD examples in all app-facing docs.

## Creating Vertices

### Using SQL (recommended)

Create vertices declaratively with SQL:

```python
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Person SET name = ?, age = ?, email = ?",
        "Charlie",
        35,
        "charlie@example.com",
    )

    print("✅ Created vertex")
```

!!! tip "When to Use Each Approach"
    - **SQL/OpenCypher (default)**: Consistent across embedded and server modes

## Creating Edges

**Important**: In ArcadeDB, edges are created **from vertices**, not from the database
directly. This is the proper graph model - edges represent connections between existing
vertices.

### Why create edges via SQL `CREATE EDGE`?

`CREATE EDGE ... FROM (...) TO (...)` is the recommended graph-write pattern in docs:

- Clear source/destination semantics
- Works consistently in embedded and server modes
- Avoids wrapper-level coupling in examples

### Creating Edges with SQL (recommended)

To create edges declaratively, identify source and destination vertices in subqueries:

```python
with db.transaction():
    db.command("sql", "INSERT INTO Person SET id = 1, name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET id = 2, name = 'Bob'")
    db.command("sql", """
        CREATE EDGE Knows
        FROM (SELECT FROM Person WHERE id = 1)
        TO (SELECT FROM Person WHERE id = 2)
        SET since = date('2020-01-15')
    """)

    print("✅ Created edge: Alice -> Bob")
```

### Creating Edges with Retrieved Vertices (SQL pattern)

```python
with db.transaction():
    db.command(
        "sql",
        """
        CREATE EDGE Knows
        FROM (SELECT FROM Person WHERE name = 'Alice')
        TO (SELECT FROM Person WHERE name = 'Bob')
        SET since = date('2020-01-15')
        """,
    )
```

!!! warning "Vertex must exist before edge creation"
    `CREATE EDGE ... FROM (...) TO (...)` requires both endpoint subqueries to return
    persisted vertices. If either side matches no record, the edge creation fails.

### Listing Edges from a Vertex

Use SQL/OpenCypher traversals for edge listing:

```python
out_edges = db.query(
    "sql",
    "SELECT expand(outE('Knows')) FROM Person WHERE name = 'Alice'",
).to_list()
```

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
        db.command("sql", "CREATE VERTEX TYPE Person")
        db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")
        db.command("sql", "CREATE PROPERTY Person.name STRING")
        db.command("sql", "CREATE PROPERTY Person.age INTEGER")
        db.command("sql", "CREATE PROPERTY Knows.since INTEGER")

        # 2. Create vertices and edges
        print("Creating graph data...")
        with db.transaction():
            db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")
            db.command("sql", "INSERT INTO Person SET name = 'Bob', age = 25")
            db.command("sql", "INSERT INTO Person SET name = 'Charlie', age = 35")

            db.command(
                "sql",
                "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Alice') TO (SELECT FROM Person WHERE name='Bob') SET since = 2020",
            )
            db.command(
                "sql",
                "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Bob') TO (SELECT FROM Person WHERE name='Charlie') SET since = 2019",
            )
            db.command(
                "sql",
                "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Charlie') TO (SELECT FROM Person WHERE name='Alice') SET since = 2021",
            )

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
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")

# ❌ Bad - will fail
db.command("sql", "INSERT INTO Person SET name = 'Alice'")  # Error: No transaction!
```

### 2. Create Indexes for Frequent Lookups

```python
# Index properties used in WHERE clauses
db.command("sql", "CREATE INDEX ON Person (name, email) NOTUNIQUE")
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

### 4. Ensure Vertices Exist Before Creating Edges

```python
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET name = 'Bob'")
    db.command(
        "sql",
        "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Alice') TO (SELECT FROM Person WHERE name='Bob')",
    )
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

#### 2. Prefer SQL DELETE for all deletion paths

Use `DELETE FROM ...` for consistency in docs and production code.

### Cascade Behavior

#### Vertex Deletion

When you delete a vertex, **all connected edges are automatically deleted**:

```python
with db.transaction():
    # Create test data
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET name = 'Bob'")
    db.command(
        "sql",
        "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Alice') TO (SELECT FROM Person WHERE name='Bob')",
    )

# Verify setup
vertices_before = list(db.query("sql", "SELECT FROM Person"))
edges_before = list(db.query("sql", "SELECT FROM Knows"))
print(f"Before: {len(vertices_before)} vertices, {len(edges_before)} edges")

# Delete vertex
with db.transaction():
    db.command("sql", "DELETE FROM Person WHERE name = 'Alice'")

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
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    db.command("sql", "INSERT INTO Person SET name = 'Bob'")
    db.command(
        "sql",
        "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Alice') TO (SELECT FROM Person WHERE name='Bob')",
    )

# Delete edge
with db.transaction():
    db.command("sql", "DELETE FROM Knows")

# Check results - vertices still exist
vertices = list(db.query("sql", "SELECT FROM Person"))
edges = list(db.query("sql", "SELECT FROM Knows"))
print(f"Vertices: {len(vertices)}")  # Output: 2
print(f"Edges: {len(edges)}")        # Output: 0
```

### Best Practices for Deletion

| Scenario | Recommended Approach | Why |
|----------|----------------------|-----|
| Delete from query results | SQL DELETE | Works predictably |
| Delete single record by RID | SQL DELETE | Consistent style |
| Delete with complex WHERE clause | SQL DELETE | Readable and powerful |
| Delete in loop | SQL DELETE with WHERE clause | Faster than per-record calls |
| Interactive/programmatic delete | SQL DELETE | Same behavior across modes |

**Summary: Use SQL DELETE by default**, except for immediate interactive deletion where you need to delete an object you just fetched.

## OpenCypher Queries

ArcadeDB supports OpenCypher for declarative graph pattern matching.

### Using OpenCypher

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./graph_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")

    # Insert data and query via OpenCypher
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")
        db.command("sql", "INSERT INTO Person SET name = 'Bob', age = 25")
        db.command(
            "sql",
            "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name='Alice') TO (SELECT FROM Person WHERE name='Bob')",
        )

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
