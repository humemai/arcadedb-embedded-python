# Gremlin Tests

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_gremlin.py){ .md-button }

These notes mirror the Python tests in [test_gremlin.py](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_gremlin.py). There are 2 tests validating Gremlin query language support. See [test_gremlin.py](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_gremlin.py) for details.

## Gremlin

[Apache Gremlin](https://tinkerpop.apache.org/gremlin.html) is a graph traversal language from TinkerPop for querying graph structures.
        db.command("gremlin", """
            g.addV('Person').property('name', 'Alice').property('age', 30)
             .addV('Person').property('name', 'Bob').property('age', 25)
             .next()
        """)

    # Query with Gremlin
    result = db.query("gremlin", """
        g.V().hasLabel('Person').values('name')
    """)

    names = [r for r in result]
    assert 'Alice' in names
    assert 'Bob' in names
```

## Gremlin Examples

### Graph Traversal

```python
# Create vertices and edges
with db.transaction():
    db.command("gremlin", """
        alice = g.addV('Person').property('name', 'Alice').next()
        bob = g.addV('Person').property('name', 'Bob').next()
        charlie = g.addV('Person').property('name', 'Charlie').next()

        g.addE('Knows').from(alice).to(bob).property('since', 2020).next()
        g.addE('Knows').from(bob).to(charlie).property('since', 2021).next()
    """)
```

## Gremlin Examples

### Friends of Friends

```python
# Find friends of friends
result = db.query("gremlin", """
    g.V().has('name', 'Alice')
     .out('Knows')
     .out('Knows')
     .values('name')
""")

# Should find Charlie (friend of friend)
assert 'Charlie' in list(result)
```

### Filtering and Projection

```python
# Find people older than 25
result = db.query("gremlin", """
    g.V().hasLabel('Person')
     .has('age', gt(25))
     .values('name')
""")

names = list(result)
assert 'Alice' in names  # age 30
assert 'Bob' not in names  # age 25
```

## Running This Test

```bash
# Run Gremlin test
pytest tests/test_gremlin.py -v

# Will be skipped if Gremlin not available
pytest tests/test_gremlin.py -v
# ======================== 1 skipped =========================
```

## Gremlin vs SQL

| Feature | SQL | Gremlin |
|---------|-----|---------|
| **Style** | Declarative | Imperative |
| **Focus** | Set operations | Step-by-step traversal |
| **Learning curve** | Easier (if you know SQL) | Steeper |
| **Graph traversal** | Limited | Excellent |
| **Use case** | General queries | Complex graph patterns |

### Example Comparison

**SQL:**
```sql
SELECT name FROM Person WHERE age > 25
```

**Gremlin:**
```groovy
g.V().hasLabel('Person').has('age', gt(25)).values('name')
```

**SQL (graph traversal):**
```sql
SELECT name, out('Knows').name as friends FROM Person WHERE name = 'Alice'
```

**Gremlin (graph traversal):**
```groovy
g.V().has('name', 'Alice').out('Knows').values('name')
```

## When to Use Gremlin

**Use Gremlin when:**

- ✅ Complex graph traversals (multi-hop, conditional paths)
- ✅ Graph algorithms (PageRank, shortest path, etc.)
- ✅ Pattern matching in graphs
- ✅ You're already familiar with TinkerPop

**Use SQL when:**

- ✅ Simple CRUD operations
- ✅ Set-based queries
- ✅ Standard reporting
- ✅ Your team knows SQL

## Related Documentation

- [Gremlin Guide](../../guide/graphs.md#gremlin-queries)
- [Graph Operations Guide](../../guide/graphs.md)
- [Apache TinkerPop Docs](https://tinkerpop.apache.org/docs/current/)
