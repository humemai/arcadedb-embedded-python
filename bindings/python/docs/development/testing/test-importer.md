# Data Import Tests

[View `test_import_database.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_import_database.py){ .md-button }
[View `test_importer_api.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_importer_api.py){ .md-button }

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

`test_import_database.py`:

- **test_import_database_csv_documents**: `IMPORT DATABASE file://...csv` stores 3 `Document` records.
- **test_import_database_csv_documents_with_quoted_parallel_setting**: the same CSV through ``IMPORT DATABASE WITH documents = ..., documentsFileType = 'csv', documentType = 'Document', `parallel` = 1`` (a quoted `parallel` setting) stores 3 records.
- **test_import_database_csv_graph_vertices_and_edges**: the vertex and edge CSV fixtures import at least 6 vertices and 3 edges (skips if the fixtures are missing).
- **test_import_database_csv_graph_vertices_and_edges_with_quoted_parallel**: the same with a quoted `parallel` setting.
- **test_import_database_xml_vertices**: an XML file imported with `entityType = 'VERTEX'` stores 2 `v_user` vertices (skips on the Windows runtime, where the engine-side XML path fails).
- **test_import_database_neo4j_fixture**: a Neo4j export imports and leaves at least one type in the schema.
- **test_import_database_word2vec_vectors**: a Word2Vec file imports at least 10 `Word` records.
- **test_import_database_rdf_fixture**: an RDF fixture imports, and `schema:types` is non-empty afterwards (it counts types, not records); it skips without an RDF importer and on the Windows parse failure.
- **test_import_database_into_timeseries_type**: `IMPORT DATABASE ... WITH documentType = 'Telemetry'` into a TIMESERIES type raises an `ArcadeDBError` mentioning "importing database", and the type still has 0 rows. The importer cannot place a document in a TIMESERIES type, so this pins the failure rather than an import path.
- **test_import_database_with_missing_file_fails**: a missing file raises `ArcadeDBError`.

The Neo4j, Word2Vec, and RDF tests skip when their fixture is missing or the runtime lacks that importer. The fixtures come from `integration/src/test/resources/` in the repository checkout (`importer-vertices.csv`, `importer-edges.csv`, `neo4j-export-mini.jsonl`, `importer-word2vec.txt`, and `importer-rdf.xml`). `test_import_database_into_timeseries_type` skips if `CREATE TIMESERIES TYPE` is rejected.

`test_importer_api.py`:

- **test_import_documents_imports_csv_from_path**: `db.import_documents(path, document_type="Person")` returns `result == "OK"`, `operation == "import documents"`, the source as a `file://` URI, and a statistics dict; 3 `Person` rows are stored and Alice's `city` is `"New York"`.
- **test_import_documents_accepts_explicit_importer_settings**: explicit `file_type`, `commit_every`, `parallel`, `wal`, and `extra_settings` still return `"OK"` and 3 rows.
- **test_import_documents_applies_and_restores_runtime_settings**: after an import with its own settings, the database's read-your-writes and the async executor's parallel level, commit interval, and WAL flag are back to their earlier values.
- **test_set_commit_every_rejects_below_one**: `async_executor().set_commit_every(0)` and `(-5)` raise `ValueError`.
- **test_import_documents_missing_file_raises_arcadedb_error**: a missing file raises `ArcadeDBError`.
- **test_import_documents_restores_runtime_settings_after_failure**: the same runtime settings are restored when the import fails.
- **test_import_documents_on_row_error** and **test_import_documents_rejects_unknown_on_row_error**: see below.

### `on_row_error`

`test_import_documents_on_row_error` imports a three-row CSV whose middle row repeats a
`UNIQUE`-indexed key, across three arms: the default, an explicit `"abort"`,
and `"skip"`. Measured behaviour is `abort` leaving 0 rows and raising, against
`skip` leaving `['A-1', 'B-2']` and not raising, with the engine logging
`Error on importing document at line 2, skipping it`. The test asserts that the
default and `"abort"` both raise and do not leave the full good set, and that
`"skip"` does not raise and leaves exactly `['A-1', 'B-2']`; because the default
and `"abort"` carry the same assertions, a change to the engine default cannot pass
silently.

`test_import_documents_rejects_unknown_on_row_error` checks that an unknown mode raises `ValueError`. That validation is
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
# Run the import database test file (from the repository root)
uv run pytest bindings/python/tests/test_import_database.py -v

# Run the import_documents API tests
uv run pytest bindings/python/tests/test_importer_api.py -v

# Run with output
uv run pytest bindings/python/tests/test_import_database.py -v -s
```

## Notes

- For full database restores, the recommended Python surface is still SQL `IMPORT DATABASE`.
- `db.import_documents(...)` is intentionally documented as a narrow wrapper rather than a new recommended default ingest workflow.

## Related Documentation

- [Import Workflow Reference](../../api/importer.md)
- [Data Import Guide](../../guide/import.md)
- [Import Examples](../../examples/import.md)
