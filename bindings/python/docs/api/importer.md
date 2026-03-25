# Import Workflow Reference

This page documents the currently available import surface in the Python bindings.

The old broad Python importer DSL is still gone. The current import surface is limited
to SQL `IMPORT DATABASE` plus the narrow `db.import_documents(...)` wrapper for
document-shaped file imports.

That path exists and is covered by tests, but it is not currently something this
repository encourages people to rely on heavily from Python. In practice, behavior has
been inconsistent enough that the preferred guidance for large Python-side ingest is
still transactional or async SQL instead. This may improve in the future.

## Available Entry Points

Use `Database.command()` with SQL:

```python
db.command("sql", "IMPORT DATABASE ...")
```

Or use the narrow Python wrapper when you specifically want a document-file import from
Python code:

```python
db.import_documents("./movies.csv", document_type="Movie", file_type="csv")
```

Formats exercised by the bindings include:

- CSV documents
- CSV graph vertices and edges
- XML
- Neo4j
- Word2Vec
- RDF
- timeseries targets
- ArcadeDB JSONL exports for full restore flows

## Current Recommendation

The bindings expose both SQL `IMPORT DATABASE` and `db.import_documents(...)`, but the
current guidance in this repository is not to encourage the importer-based paths as the
default Python-side ingest path right now.

- For focused ingest benchmarks, use Example 15 and 16 style comparisons across
    transactional SQL, async SQL, and SQL import rather than assuming one winner.
- Async SQL remains the safest default recommendation for Python-managed ingest
    experiments, but measured results are workload-dependent.
- Treat `db.import_documents(...)` as a narrow convenience wrapper, not as the default
    ingest story for Python.
- For bulk table/document ingest from Python, prefer async SQL insert with a single
    async worker.
- Do not rely on multi-threaded async SQL insert for that path in the current Python
    examples. It has not been safe or reliable in testing.
- For bulk graph ingest, prefer `GraphBatch` rather than importer-based graph loading.
- Use SQL `IMPORT DATABASE` mainly when you specifically need one of the supported file
    import formats or a full ArcadeDB export/restore path.
- Treat this guidance as current, not permanent. The recommendation can change if the
    Python-side behavior improves.

## Common Patterns

### Import a CSV File into a Document Type

```python
from pathlib import Path


def file_url(path: str) -> str:
    return Path(path).resolve().as_uri()


db.command("sql", "CREATE DOCUMENT TYPE Movie")
db.command(
    "sql",
    f"IMPORT DATABASE {file_url('./movies.csv')} WITH documentType = 'Movie', commitEvery = 5000",
)
```

### Import Graph Vertices

```python
db.command("sql", "CREATE VERTEX TYPE Person")
db.command(
    "sql",
    (
        "IMPORT DATABASE WITH "
        "vertices = 'file:///data/people.csv', "
        "vertexType = 'Person', "
        "typeIdProperty = 'id', "
        "typeIdType = 'Long', "
        "typeIdUnique = true"
    ),
)
```

### Import Graph Edges

```python
db.command("sql", "CREATE EDGE TYPE Follows UNIDIRECTIONAL")
db.command(
    "sql",
    (
        "IMPORT DATABASE WITH "
        "edges = 'file:///data/follows.csv', "
        "edgeType = 'Follows', "
        "typeIdProperty = 'id', "
        "typeIdType = 'Long', "
        "edgeFromField = 'from', "
        "edgeToField = 'to'"
    ),
)
```

### Import XML as Vertices

```python
db.command(
    "sql",
    "IMPORT DATABASE file:///data/sample.xml WITH objectNestLevel = 1, entityType = 'VERTEX'",
)
```

### Restore an ArcadeDB Export

```python
db.command(
    "sql",
    "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000",
)
```

## Important Options

The exact option set depends on the source format, but the commonly used ones in the
bindings are:

- `documentType`
- `vertexType`
- `edgeType`
- `typeIdProperty`
- `typeIdType`
- `typeIdUnique`
- `edgeFromField`
- `edgeToField`
- `commitEvery`
- `objectNestLevel`
- `entityType`

## Recommended Workflow

1. Create the target schema with SQL DDL when you need strict typing or indexes.
1. Run `IMPORT DATABASE` with a file URL and the relevant options.
1. Validate imported counts and representative records.
1. Recreate or add heavy secondary indexes after large bulk loads if throughput matters.

## Compatibility Note

If you see old references to a broad Python `Importer`, `import_csv()`, or `import_xml()`
surface in older fork history or stale docs, treat them as obsolete. The current Python
surface is intentionally small: SQL `IMPORT DATABASE` plus `db.import_documents(...)`,
and both importer-based paths should still be treated cautiously from Python.

## See Also

- [Data Import Guide](../guide/import.md) - Import strategy and tradeoffs
- [Database API](database.md) - Database operations
- [Graph Operations Guide](../guide/graphs.md) - Working with graph data
- [Import Examples](../examples/import.md) - Practical examples
