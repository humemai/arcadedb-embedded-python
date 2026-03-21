# Data Import Guide

This guide covers the currently available import workflows in the Python bindings.

The current bindings are SQL-first. The old broad Python `Importer`, `import_csv()`,
and `import_xml()` surface is intentionally not part of the current public API. The
remaining import surface is SQL `IMPORT DATABASE` plus the narrow
`db.import_documents(...)` helper for document-file loads, but this repository still
does not encourage leaning on importer-based paths heavily from Python.

Use it when you need its supported file-import behavior or a full
`EXPORT DATABASE` + `IMPORT DATABASE` restore flow. For large Python-side table/document
ingest, prefer async SQL with a single async worker.

## Overview

The currently exposed importer paths are ArcadeDB's native SQL importer plus a narrow
Python wrapper for document imports.

+ CSV document imports
+ CSV graph imports for vertices and edges
+ XML imports
+ Neo4j imports
+ Word2Vec imports for vector workflows
+ RDF imports
+ Timeseries imports
+ Full ArcadeDB JSONL restore

All of these are exercised through `db.command("sql", "IMPORT DATABASE ...")` in
the current test suite, but test coverage should not be read as a recommendation to make
this your default Python ingest path.

`db.import_documents(...)` is also covered by dedicated API tests, but it should be read
the same way: supported, not currently encouraged as the default Python ingest path.

## Bulk Ingest Recommendation

`IMPORT DATABASE` is available, but it is not the recommended path for very large
Python-side bulk ingest workloads in this repository right now, and more broadly it is
not something we currently encourage as the default Python import story.

+ Example 15 plus the larger table examples are the basis for the current repository
    guidance.
+ For bulk table/document ingest, async SQL with `--async-parallel 1` is the
    recommended default.
+ Do not rely on multi-threaded async SQL insert for this path in the current Python
    examples. It has not been safe or reliable in testing.
+ `db.import_documents(...)` exists for document-shaped file import convenience, but in
    current Python testing it has also shown reliability problems under heavier loads.
+ Reserve `IMPORT DATABASE` for supported import formats, restore flows, and cases where
    you explicitly need that importer behavior from Python.
+ For bulk graph ingest, use `GraphBatch` instead; see Example 16 and the graph
    examples.

## Example 15 and 16 Benchmark Structure

Example 15 and 16 are the repository's focused ingest comparison harnesses.

+ Example 15 includes the `db.import_documents(...)` wrapper in addition to the main
    SQL-based ingestion paths.
+ Example 15 targets multi-table/document ingest.
+ Example 16 targets graph ingest with vertices plus edges.
+ Both examples enforce parity checks on the final loaded data so timing comparisons are
    only accepted when the result counts match the expected shape.
+ Example 15 is useful for comparison, but the repository recommendation for bulk
    table/document ingest is still single-worker async SQL.

## Quick Start

### Import CSV as Documents

```python
from pathlib import Path

import arcadedb_embedded as arcadedb


def file_url(path: str) -> str:
    return Path(path).resolve().as_uri()


with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Movie")
    db.command(
        "sql",
        f"IMPORT DATABASE {file_url('./movies.csv')} WITH documentType = 'Movie', commitEvery = 5000",
    )
```

### Import CSV as Vertices and Edges

```python
from pathlib import Path

import arcadedb_embedded as arcadedb


def file_url(path: str) -> str:
    return Path(path).resolve().as_uri()


with arcadedb.create_database("./graphdb") as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Follows UNIDIRECTIONAL")

    db.command(
        "sql",
        (
            "IMPORT DATABASE WITH "
            f"vertices = '{file_url('./people.csv')}', "
            "vertexType = 'Person', "
            "typeIdProperty = 'id', "
            "typeIdType = 'Long', "
            "typeIdUnique = true"
        ),
    )

    db.command(
        "sql",
        (
            "IMPORT DATABASE WITH "
            f"edges = '{file_url('./follows.csv')}', "
            "edgeType = 'Follows', "
            "typeIdProperty = 'id', "
            "typeIdType = 'Long', "
            "edgeFromField = 'from', "
            "edgeToField = 'to'"
        ),
    )
```

### Restore an ArcadeDB Export

```python
with arcadedb.create_database("./restored") as db:
    db.command(
        "sql",
        "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000",
    )
```

## Choosing the Right Import Mode

### CSV

Use CSV imports for flat tabular data, graph vertex/edge feeds, and time-series style
ingestion.

Best fit:

+ spreadsheet-style datasets
+ relational exports
+ graph nodes and edges split across files
+ moderate-size file imports and format-driven imports

### ArcadeDB JSONL Export

Use JSONL exports when you want a full database restore with schema and data intact.

Best fit:

+ environment-to-environment migration
+ backups and restore drills
+ reproducible benchmark datasets

### XML, RDF, Neo4j, Word2Vec

These formats are also driven through SQL `IMPORT DATABASE`. See the import tests for
working examples of the exact option sets used in the bindings.

## Schema Strategy

### Recommended: Pre-create the Schema

Create types, properties, and indexes before importing when you care about data types,
constraints, and predictable query plans.

```python
with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE User")
    db.command("sql", "CREATE PROPERTY User.id LONG")
    db.command("sql", "CREATE PROPERTY User.email STRING")
    db.command("sql", "CREATE INDEX ON User (id) UNIQUE")
    db.command("sql", "CREATE INDEX ON User (email) UNIQUE")

    db.command(
        "sql",
        "IMPORT DATABASE file:///data/users.csv WITH documentType = 'User', commitEvery = 10000",
    )
```

### Fast Start: Let the Import Create the Target Type

For exploratory work, you can import into a new type with minimal setup. This is quick,
but you give up explicit control over schema shape and validation.

## Performance Guidance

### Tune `commitEvery`

Use larger commit batches for throughput and smaller ones for lower memory pressure when
you do choose the SQL import path.

| Dataset Size | Recommended `commitEvery` |
| --- | --- |
| < 100K rows | 1,000 to 10,000 |
| 100K to 1M rows | 10,000 to 50,000 |
| > 1M rows | 50,000 to 100,000 |

### Drop Heavy Indexes Before Bulk Loads

For large one-shot imports, remove expensive indexes first and recreate them afterward.
For the largest Python benchmark ingest paths in this repo, prefer async SQL with a
single async worker instead of leaning on `IMPORT DATABASE`.

```python
db.command("sql", "DROP INDEX `User[email]`")

db.command(
    "sql",
    "IMPORT DATABASE file:///data/users.csv WITH documentType = 'User', commitEvery = 50000",
)

db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
```

### Validate the Input Up Front

Check required columns and data cleanliness before starting a long import run. The SQL
importer will fail fast on malformed configurations, but it is still cheaper to catch
obvious CSV issues before JVM work starts.

## Relationship Mapping

For graph imports, load vertices first, then edges, and use matching ID fields.

```python
db.command(
    "sql",
    (
        "IMPORT DATABASE WITH "
        "vertices = 'file:///data/users.csv', "
        "vertexType = 'User', "
        "typeIdProperty = 'id', "
        "typeIdType = 'Long', "
        "typeIdUnique = true"
    ),
)

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

## See Also

+ [Import Workflow Reference](../api/importer.md) - Supported SQL import surface
+ [Import Examples](../examples/import.md) - Practical examples
+ [Database API](../api/database.md) - Database operations
+ [Transactions](../api/transactions.md) - Transaction management
