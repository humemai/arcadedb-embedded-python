# Data Import Examples

This page covers the current import examples for the Python bindings.

Before running any example, download the datasets using **[Dataset Downloader](download_data.md)**.

## CSV Import Examples

### Import Tabular Data as Documents

**[Example 04 - CSV Import: Documents](04_csv_import_documents.md)**

Learn how to:

- create a target document type with SQL
- import CSV data through `IMPORT DATABASE`
- validate NULL handling and inferred types
- benchmark query performance before and after indexes

### Import Graph Data

**[Example 05 - CSV Import: Graph Database](05_csv_import_graph.md)**

Learn how to:

- import vertices from CSV
- import edges from CSV using matching IDs
- create graph schema up front
- bulk-load graph data with SQL import commands

## SQL Import Workflow

The current bindings expose SQL `IMPORT DATABASE` plus a narrow
`db.import_documents(...)` helper for document-file loads.

For very large Python-side bulk ingest workloads in this repository, do not treat
importer-based paths as the default choice.

- For bulk table/document ingest, prefer async SQL insert with one async worker.
- Do not rely on multi-threaded async SQL insert for this path in the current Python
    examples.
- For bulk graph ingest, prefer `GraphBatch`.

More broadly, this repository does not currently encourage `IMPORT DATABASE` as the main
Python-side ingest recommendation. It remains available for the supported file-driven
workflows and may become a stronger recommendation later if behavior improves.

### Basic CSV Import

```python
from pathlib import Path

import arcadedb_embedded as arcadedb


def file_url(path: str) -> str:
    return Path(path).resolve().as_uri()


with arcadedb.create_database("./import_demo") as db:
    db.command("sql", "CREATE DOCUMENT TYPE MyType")
    db.command(
        "sql",
        f"IMPORT DATABASE {file_url('./data.csv')} WITH documentType = 'MyType', commitEvery = 5000",
    )
```

### Import with Predefined Schema

```python
with arcadedb.create_database("./import_demo") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Product")
    db.command("sql", "CREATE PROPERTY Product.id INTEGER")
    db.command("sql", "CREATE PROPERTY Product.name STRING")
    db.command("sql", "CREATE PROPERTY Product.price DOUBLE")

    db.command(
        "sql",
        f"IMPORT DATABASE {file_url('./products.csv')} WITH documentType = 'Product', commitEvery = 5000",
    )
```

### Import Graph Vertices and Edges

```python
with arcadedb.create_database("./graph_import_demo") as db:
    db.command("sql", "CREATE VERTEX TYPE User")
    db.command("sql", "CREATE EDGE TYPE Follows UNIDIRECTIONAL")

    db.command(
        "sql",
        (
            "IMPORT DATABASE WITH "
            f"vertices = '{file_url('./users.csv')}', "
            "vertexType = 'User', "
            "typeIdProperty = 'userId', "
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
            "typeIdProperty = 'userId', "
            "typeIdType = 'Long', "
            "edgeFromField = 'follower_id', "
            "edgeToField = 'following_id'"
        ),
    )
```

## Performance Tips

1. Pre-create critical schema and unique indexes.
2. Use a larger `commitEvery` value when you intentionally choose the SQL import path.
3. Drop expensive secondary indexes before a one-shot import and recreate them afterward.
4. Validate source files before starting long-running jobs.
5. For bulk table/document ingest, prefer single-worker async SQL instead of importer-based paths.
6. For bulk graph ingest, prefer `GraphBatch` instead of importer-based graph loading.

## Additional Resources

- **[Import Workflow Reference](../api/importer.md)** - Supported SQL import surface
- **[Import Guide](../guide/import.md)** - Import strategies and patterns
- **[Performance Guide](../guide/operations.md)** - JVM and bulk-load tuning

## Source Code

View the complete example source code:

- [`examples/04_csv_import_documents.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/04_csv_import_documents.py)
- [`examples/05_csv_import_graph.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/05_csv_import_graph.py)
