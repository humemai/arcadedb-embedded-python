# OpenCypher Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cypher.py){ .md-button }

These notes mirror the Python tests in [test_cypher.py]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cypher.py). The tests validate OpenCypher query support and common graph patterns.

## OpenCypher

OpenCypher is a declarative graph query language for pattern matching and traversal.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./opencypher_test_db") as db:
    db.schema.create_vertex_type("Person")
    db.schema.create_edge_type("Knows")

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
