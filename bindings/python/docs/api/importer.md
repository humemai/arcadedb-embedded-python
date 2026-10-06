# Import Workflow Reference

This page documents the import surface of the Python bindings: SQL `IMPORT DATABASE`
plus the narrow `db.import_documents(...)` wrapper for document-shaped file imports.

Both are covered by tests, but they are not the recommended path for large Python-side
ingest. For that, use `db.insert_many(...)` for documents and `db.graph_batch(...)` for
graphs; see the [Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation).

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
- ArcadeDB JSONL exports for full restore flows

A TIMESERIES type is not an import target: it owns no document buckets, so
`IMPORT DATABASE ... documentType = '<timeseries type>'` raises `ArcadeDBError`. Load
time series with `db.async_executor().append_samples(...)` instead.

## Current Recommendation

The ingest guidance (`insert_many`, its parallel mode and bucket rule, `GraphBatch`, and
why the async executor's `command(...)` is not an ingest path) lives in one place: the
[Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation). For this
page's two entry points:

- Treat `db.import_documents(...)` as a narrow convenience wrapper, not as the default
    ingest story for Python.
- Use SQL `IMPORT DATABASE` mainly when you specifically need one of the supported file
    import formats or a full ArcadeDB export/restore path.
- To compare the paths on your own data, use Example 15 and 16 style comparisons across
    transactional SQL, the batch helpers, and SQL import rather than assuming one winner.

## `db.import_documents(...)`

```python
db.import_documents(
    source: str | os.PathLike,
    document_type: str = "Document",
    *,
    file_type: str | None = None,
    delimiter: str | None = None,
    header: str | None = None,
    skip_entries: int | None = None,
    properties_include: str | None = None,
    commit_every: int | None = None,
    parallel: int | None = None,
    wal: bool | None = None,
    verbose_level: int | None = None,
    probe_only: bool | None = None,
    force_database_create: bool | None = None,
    trim_text: bool | None = None,
    on_row_error: str | None = None,
    extra_settings: Mapping[str, Any] | None = None,
) -> ImportResult
```

Runs ArcadeDB's Java importer on one source into one document type. A parameter left
at `None` is not passed, so the importer's own default applies. The engine setting each
one sets is in parentheses.

**Parameters:**

- `source`: a local path (`str` or `os.PathLike`) or an importer URL. A path with no URL
  scheme, a relative one included, is resolved to an absolute `file://` URI, which
  `ImportResult.source_url` reports. The path is not percent-encoded, so a directory or file
  name with a space or another special character works as it is.
- `document_type`: the target document type (`documentType`).
- `file_type`: the importer format, such as `"csv"` (`documentsFileType`).
- `delimiter`: the field delimiter of a delimited format (`documentsDelimiter`).
- `header`: the column names, separated by the delimiter (`"id,name,city"`), for a file
  that has no header line (`documentsHeader`). With it, no line is skipped as a header.
- `skip_entries`: lines to skip at the start of the file, the header line included
  (`documentsSkipEntries`). Without it, a file read without `header` skips its header
  line only.
- `properties_include`: comma-separated names of the properties to import
  (`documentPropertiesInclude`); the importer's default `"*"` imports all of them.
- `commit_every`, `parallel`, `wal`: the transaction split interval, the worker count,
  and WAL use during the import (`commitEvery`, `parallel`, `wal`; see the side effects
  below).
- `verbose_level`: the importer's log level (`verboseLevel`, 2 by default).
- `probe_only`: analyze the source without writing records (`probeOnly`).
- `force_database_create`: delete and recreate the database when the importer opens a
  database of its own (`forceDatabaseCreate`). It has no effect on the open database
  this method runs on.
- `trim_text`: trim text values (`trimText`, on by default); the XML format reads it.
- `on_row_error`: `"abort"` (the default) or `"skip"`; see [`on_row_error`](#on_row_error).
- `extra_settings`: any other importer setting by its engine name; each value is passed
  as a string, and `None` values are dropped.

**While it runs**, the call turns read-your-writes off on the database and applies any
`parallel`, `commit_every`, and `wal` you pass to the database's async executor. When
the import ends, with or without an error, it waits for the executor and restores all
four settings.

**Returns:** an `ImportResult` with

- `result`: `"OK"`, or `"PROBE_ONLY"` with `probe_only=True` (then `statistics` is empty)
- `operation`: `"import documents"`
- `source_url`: the URL the importer read
- `statistics`: the importer's counters as a dict, such as `createdDocuments`,
  `parsedRecords`, and `skippedRecords`
- `get(key, default=None)`: one counter from `statistics`
- `to_dict()`: the counters plus `result`, `operation`, and `source_url` in one dict

**Raises:** `ArcadeDBError` if the import fails, and `ValueError` for an `on_row_error`
other than `"abort"` or `"skip"`.

```python
result = db.import_documents(
    "movies.csv", document_type="Movie", file_type="csv", commit_every=5000
)
print(result.source_url, result.get("createdDocuments"))
```

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
db.command("sql", "CREATE EDGE TYPE Follows")
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
- `onRowError` (`db.import_documents(..., on_row_error=...)`)

### `on_row_error`

`"abort"` (the default) fails the whole job on the first malformed or
out-of-range row. `"skip"` logs that row and keeps going, so a single bad
record cannot discard the good ones.

`"skip"` is not free, and the cost is not just the failing row:

- It commits **per row** for the whole run, rather than one transaction for the
  file (documents) or `commitEvery`-sized async batches (vertices). A duplicate
  key only fails at index time, when a bucket write already exists, so undoing
  just that row needs the row to own its transaction.
- For vertex imports it also drops `database.async()` entirely, making the
  import synchronous and single-threaded. `commit_every` and `parallel` are
  silently inapplicable there while it is enabled.
- It requires **exclusive control of the transaction** and raises if one is
  already active, for example inside a caller-managed `with db.transaction():`
  or a server HTTP command running with the default `autoCommit`.

Any value other than `"abort"` or `"skip"` raises `ValueError`. The engine
tests this setting with `"skip".equalsIgnoreCase(value)`, so an unvalidated
typo would silently run the import in `abort` mode instead.

## Recommended Workflow

1. Create the target schema with SQL DDL when you need strict typing or indexes.
1. Run `IMPORT DATABASE` with a file URL and the relevant options.
1. Validate imported counts and representative records.
1. Recreate or add heavy secondary indexes after large bulk loads if throughput matters.

## See Also

- [Data Import Guide](../guide/import.md) - Import strategy and tradeoffs
- [Database API](database.md) - Database operations
- [Graph Operations Guide](../guide/graphs.md) - Working with graph data
- [Example 04: CSV Import (Tables)](../examples/04_csv_import_documents.md) - A worked CSV import
