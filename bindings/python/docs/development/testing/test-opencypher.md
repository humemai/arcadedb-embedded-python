# OpenCypher Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cypher.py){ .md-button }

The tests validate OpenCypher query support, common graph patterns, and recent path-mode
semantics.

They also include regression coverage for planner behavior that matters to the
Python bindings, such as `UNWIND` variables being usable inside `WHERE`
predicates.

## OpenCypher

OpenCypher is a declarative graph query language for pattern matching and traversal.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./opencypher_test_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")

    with db.transaction():
        alice = db.new_vertex("Person")
        alice.set("name", "Alice").save()

        bob = db.new_vertex("Person")
        bob.set("name", "Bob").save()

        edge = alice.new_edge("Knows", bob)
        edge.save()

    result = db.query("opencypher", """
        MATCH (p:Person)-[:Knows]->(friend:Person)
        RETURN friend.name as name
    """)

    names = [r.get("name") for r in result]
    assert "Bob" in names
```

## Running This Test

```bash
pytest tests/test_cypher.py -v
```

## Notable Regression Coverage

- Path modes: default `TRAIL`, explicit `ACYCLIC`, and `WALK`
- `WALK` requires an explicit hop bound on cyclic traversals
- `UNWIND` variables can be referenced from `WHERE` clauses during `MATCH`
- Aggregations on missing labels still return a single row with `0`
- Result property order remains stable for projected OpenCypher values

## Path Mode Example

```cypher
MATCH ACYCLIC (a:Node {name: 'A'})-[:LINK*1..5]->(b)
RETURN b.name AS name
```

This coverage is intentionally test-focused: Python already reaches these features
through `db.query("opencypher", ...)`, so the bindings need semantic verification more
than a dedicated wrapper API.

## OpenCypher vs SQL MATCH

| Feature | SQL MATCH | OpenCypher |
|---------|-----------|------------|
| **Style** | SQL-like | Declarative graph patterns |
| **Focus** | Set operations + graph patterns | Pattern matching + paths |
| **Learning curve** | Easier if you know SQL | Easier if you know Cypher |
| **Graph traversal** | Strong | Strong |

### Example Comparison

**SQL MATCH:**
```sql
MATCH {type: Person, as: p}-Knows->{type: Person, as: friend}
RETURN friend.name
```

**OpenCypher:**
```cypher
MATCH (p:Person)-[:Knows]->(friend:Person)
RETURN friend.name
```

## Related Documentation

- [Query Languages](../../guide/core/queries.md)
- [Graph Operations Guide](../../guide/graphs.md)
