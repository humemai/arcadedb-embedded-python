# Exporter API

The exporter module provides two complementary utilities:
- `export_database` for full database exports (JSONL/GraphML/GraphSON)
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
    format: str = "jsonl",
    overwrite: bool = False,
    include_types: Optional[List[str]] = None,
    exclude_types: Optional[List[str]] = None,
    verbose: int = 1,
) -> Dict[str, Any]
```

Export the full database using ArcadeDB's Java exporter. Supported formats are
`jsonl`, `graphml`, and `graphson`.

**Parameters:**

- `db`: Database instance
- `file_path`: Output file path (non-absolute paths are stored under exports/)
- `format`: Export format (`"jsonl"`, `"graphml"`, `"graphson"`)
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

# GraphML export (requires GraphML module in the packaged jars)
export_database(db, "graph.graphml.tgz", format="graphml", overwrite=True)

db.close()
```

!!! note "GraphML and GraphSON"
    GraphML/GraphSON formats require the corresponding Java modules to be present
    in the packaged jars. If missing, `export_database` raises a clear error.

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
