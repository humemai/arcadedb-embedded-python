# Data Import Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_import_database.py){ .md-button }

The import-focused test coverage is split across:

- `test_import_database.py` for SQL `IMPORT DATABASE` behavior and format coverage
- `test_importer_api.py` for the narrow `db.import_documents(...)` wrapper

## Quick Start

### SQL `IMPORT DATABASE`

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    db.command(
        "sql",
        "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000",
    )
```

### `db.import_documents(...)`

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    db.import_documents("./movies.csv", document_type="Movie", file_type="csv")
```

### Covered Scenarios

```python
The file covers:

- CSV document imports
- CSV graph vertex/edge imports
- XML imports
- Neo4j imports
- Word2Vec vector imports
- RDF imports
- Timeseries target imports
- SQL `IMPORT DATABASE` usage where full-database restore semantics matter
- `on_row_error` skip-vs-abort, and rejection of unknown modes
```

### `on_row_error`

Two tests. The first imports a three-row CSV whose middle row repeats a
`UNIQUE`-indexed key, across three arms: the default, an explicit `"abort"`,
and `"skip"`. Measured behaviour is `abort` leaving 0 rows and raising, against
`skip` leaving `['A-1', 'B-2']` and not raising, with the engine logging
`Error on importing document at line 2, skipping it`. The default and `"abort"`
are asserted to match, so a change to the engine default cannot pass silently.

The second checks that an unknown mode raises `ValueError`. That validation is
Python-side on purpose: the engine tests `"skip".equalsIgnoreCase(value)`, so
`"ignore"` or `"SKIPP"` would otherwise run the import in exactly the opposite
mode from the one requested, with nothing logged. `"SKIP"` is accepted, mirroring
the engine's case-insensitivity.

## Test Shape

These tests are intentionally conservative in their guidance:

- schema is prepared with SQL DDL where needed
- full database restores use `db.command("sql", "IMPORT DATABASE ...")`
- assertions verify imported counts and representative records rather than broad importer DSL wiring
- the wrapper tests confirm `db.import_documents(...)` exists and behaves correctly, not
    that it is the preferred ingest path for large Python workloads

## Running These Tests

```bash
# Run the import database test file
pytest tests/test_import_database.py -v

# Run the import_documents API tests
pytest tests/test_importer_api.py -v

# Run with output
pytest tests/test_import_database.py -v -s
```

## Notes

- For full database restores, the recommended Python surface is still SQL `IMPORT DATABASE`.
- `db.import_documents(...)` is intentionally documented as a narrow wrapper rather than a new recommended default ingest workflow.
- The maintained regression coverage for imports now lives in `test_import_database.py` and `test_importer_api.py`.

## Related Documentation

- [Import Workflow Reference](../../api/importer.md)
- [Data Import Guide](../../guide/import.md)
- [Import Examples](../../examples/import.md)
