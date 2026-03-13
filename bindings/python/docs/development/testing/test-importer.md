# Data Import Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_import_database.py){ .md-button }

The current import-focused test file validates SQL-first `IMPORT DATABASE` behavior and
format coverage rather than the removed legacy importer test surface.

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
```

## Test Shape

These tests are intentionally SQL-first:

- schema is prepared with SQL DDL where needed
- full database restores use `db.command("sql", "IMPORT DATABASE ...")`
- assertions verify imported counts and representative records rather than importer DSL wiring

## Running These Tests

## Running These Tests

```bash
# Run the import database test file
pytest tests/test_import_database.py -v

# Run with output
pytest tests/test_import_database.py -v -s
```

## Notes

- For full database restores, the recommended Python surface is SQL `IMPORT DATABASE`, not a separate high-level Python importer DSL.
- The maintained regression coverage for imports now lives in `test_import_database.py`.

## Related Documentation

- [Import Workflow Reference](../../api/importer.md)
- [Data Import Guide](../../guide/import.md)
- [Import Examples](../../examples/import.md)
