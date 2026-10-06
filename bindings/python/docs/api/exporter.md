# Exporter API

The exporter module provides two complementary utilities:

- `export_database` for full database exports (JSONL)
- `export_to_csv` for exporting query results or in-memory data to CSV

!!! tip "Context Managers"
    Prefer context managers for automatic cleanup:

    ```python
    with arcadedb.open_database("./mydb") as db:
        export_database(db, "backup.jsonl.tgz", overwrite=True)
    ```

## export_database

```python
from arcadedb_embedded.exporter import export_database

export_database(
    db,
    file_path: str,
    export_format: str = "jsonl",
    overwrite: bool = False,
    include_types: Optional[List[str]] = None,
    exclude_types: Optional[List[str]] = None,
    verbose: int = 1,
) -> Dict[str, Any]
```

Export the full database using ArcadeDB's Java exporter. The wheel exports `jsonl`.
`graphml` and `graphson` are accepted names, but their exporters come from the
optional `arcadedb-gremlin` module, which the wheel does not bundle, so they raise
`ArcadeDBError` (see the note below).

**Parameters:**

- `db`: Database instance
- `file_path`: Output file path (non-absolute paths are stored under exports/)
- `export_format`: Export format. `"jsonl"` is the one the wheel supports; `"graphml"`
  and `"graphson"` raise `ArcadeDBError` without `arcadedb-gremlin`
- `overwrite`: Overwrite output if it already exists
- `include_types`: Export only specific types
- `exclude_types`: Exclude specific types
- `verbose`: Verbosity level (0-2)

**Returns:**

Dictionary with export statistics (keys depend on the Java exporter), commonly:

- `totalRecords`
- `documents`, `vertices`, `edges`
- `elapsedInSecs`

**Examples:**

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Full JSONL backup (recommended)
stats = export_database(db, "backup.jsonl.tgz", overwrite=True)
print(stats)

# Export only selected types
export_database(
    db,
    "users.jsonl.tgz",
    include_types=["User", "Admin"],
    overwrite=True,
)

# Exclude types
export_database(
    db,
    "no_logs.jsonl.tgz",
    exclude_types=["AuditLog", "Event"],
    overwrite=True,
)

db.close()
```

!!! note "GraphML and GraphSON"
    The GraphML and GraphSON exporters are provided by the optional `arcadedb-gremlin`
    module, which the wheel excludes to keep its size down (`scripts/jar_exclusions.txt`).
    With the wheel as shipped, `export_format="graphml"` or `"graphson"` raises
    `ArcadeDBError` naming that module. Use `jsonl`.

## export_to_csv

```python
from arcadedb_embedded.exporter import export_to_csv

export_to_csv(
    results: Union[ResultSet, List[Dict]],
    file_path: str,
    fieldnames: Optional[List[str]] = None,
)
```

Export query results (or a list of dictionaries) to CSV. This is a Python-side
helper and does not use the Java exporter.

Without `fieldnames` the header is the keys of every row, in order of first appearance
(for a `ResultSet`, of its first batch of 10,000 rows): a property the first row lacks
is a column, empty where a row lacks it. A column that first appears after the first
batch cannot be added to a header already written, so the export raises `ArcadeDBError`
naming it and leaves the part written; pass `fieldnames` naming every column the query
can return.

`fieldnames` sets the header and the column order; it cannot rename columns. It must
name every key of every row (a name a row lacks is written empty): a missing one raises
`ArcadeDBError` ("dict contains fields not in fieldnames"), and for a `ResultSet` the
header is already written by then, which leaves a header-only file. To rename, alias
the columns in the query. A `ResultSet` is read through `iter_json_batches()`, so
`DATE` and `DATETIME` values are written as epoch-millisecond integers.

**Examples (ResultSet):**

```python
results = db.query("sql", "SELECT userId, name, email FROM User")
export_to_csv(results, "users.csv")
```

**Examples (list of dicts):**

```python
data = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
]
export_to_csv(data, "users.csv", fieldnames=["id", "name"])
```

**Convenience helper on `Database`:**

```python
db.export_to_csv("SELECT * FROM User", "users.csv")
```
