# Transactions

Prefer the Pythonic wrappers (`new_vertex`, `new_document`, `new_edge`, `modify`,
`batch_context`) over raw SQL. When you see `temp_db_path`, substitute your own path if
you are not in the test harness.

## Basic commit and rollback

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    db.schema.create_document_type("TransactionTest")

    # Commit on success
    with db.transaction():
        db.command("sql", "INSERT INTO TransactionTest SET id = 1")
        db.command("sql", "INSERT INTO TransactionTest SET id = 2")

    result = db.query("sql", "SELECT count(*) as count FROM TransactionTest")
    count = list(result)[0].get("count")
    assert count == 2

    # Rollback on exception
    try:
        with db.transaction():
            db.command("sql", "INSERT INTO TransactionTest SET id = 3")
            raise Exception("Intentional error")
    except Exception:
        pass

    result = db.query("sql", "SELECT count(*) as count FROM TransactionTest")
    count = list(result)[0].get("count")
    assert count == 2
```

## Schema is auto-transactional

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    # Schema changes do not need an explicit transaction
    db.schema.create_document_type("TestDoc")

    # Data writes do
    with db.transaction():
        db.command("sql", "INSERT INTO TestDoc SET name = 'test', value = 42")

    result = db.query("sql", "SELECT FROM TestDoc WHERE name = 'test'")
    record = list(result)[0]
    assert record.get("value") == 42
```

## Pythonic vertex/document creation in a transaction

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.graph import Document, Vertex

with arcadedb.create_database(temp_db_path) as db:
    db.schema.create_vertex_type("Person")
    db.schema.create_document_type("Task")

    with db.transaction():
        alice = db.new_vertex("Person")
        assert isinstance(alice, Vertex)
        alice.set("name", "Alice").set("age", 30).save()

        task = db.new_document("Task")
        assert isinstance(task, Document)
        task.set("title", "Test Task")
        task.set("priority", 5)
        task.save()
```

## Pythonic edge creation with properties

```python
with arcadedb.create_database(temp_db_path) as db:
    db.schema.create_vertex_type("Person")
    db.schema.create_edge_type("Knows")

    with db.transaction():
        alice = db.new_vertex("Person").set("name", "Alice").save()
        bob = db.new_vertex("Person").set("name", "Bob").save()

        edge = alice.new_edge("Knows", bob, since="2020", strength=0.8)
        edge.save()
```

## Update after querying (immutables -> modify())

```python
with arcadedb.create_database(temp_db_path) as db:
    db.schema.create_vertex_type("City")

    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO City SET name = 'New York', population = 8000000",
        )

    result = db.query("sql", "SELECT FROM City WHERE name = 'New York'")
    city = list(result)[0].get_vertex()

    with db.transaction():
        mutable_city = city.modify()
        mutable_city.set("country", "USA")
        mutable_city.save()

    updated = list(db.query("sql", "SELECT FROM City WHERE name = 'New York'"))[0]
    assert updated.get("country") == "USA"
```

## Batch context: edge creation must be inside a transaction

```python
with db.transaction():
    with db.batch_context(batch_size=10) as batch:
        batch.create_edge(alice, bob, "KNOWS", since=2020)
        batch.create_edge(bob, charlie, "KNOWS", since=2021)
        batch.create_edge(charlie, alice, "KNOWS", since=2022)
```

## Batch updates with `modify()` + `batch_context`

```python
counters = list(db.query("sql", "SELECT FROM Counter"))

with db.transaction():
    with db.batch_context(batch_size=50) as batch:
        for counter in counters:
            vertex = counter.get_vertex()
            mutable_vertex = vertex.modify()
            mutable_vertex.set("value", counter.get("value") * 2)
            batch.update_record(mutable_vertex._java_document)
```

## Chunked bulk inserts with manual commit/renew

```python
import arcadedb_embedded as arcadedb

BATCH_SIZE = 1000
with db.transaction():
    total_inserted = 0
    for i, doc in enumerate(documents):
        vertex = db.new_vertex("Article")
        vertex.set("id", doc["id"])
        vertex.set("title", doc["title"])
        vertex.set("content", doc["content"])
        vertex.set("category", doc["category"])
        vertex.set("embedding", arcadedb.to_java_float_array(doc["embedding"]))
        vertex.save()

        total_inserted += 1
        if total_inserted % BATCH_SIZE == 0:
            db.commit()
            db.begin()
```

## SQL updates inside transactions

```python
with db.transaction():
    db.command(
        "sql",
        """UPDATE Task SET
           completed = true,
           cost = 127.50
           WHERE title = 'Buy groceries'""",
    )

with db.transaction():
    db.command(
        "sql",
        """UPDATE Task SET
           cost = NULL,
           estimated_hours = NULL
           WHERE title = 'Call dentist'""",
    )
```
