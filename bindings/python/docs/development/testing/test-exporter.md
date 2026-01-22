# Exporter Tests

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py){ .md-button }

These notes mirror the Python tests in [test_exporter.py](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py). There are 5 test classes with 12+ tests covering JSONL (with type/edge filters), GraphML/GraphSON (skipped if GraphSON support is unavailable), CSV, round-trip (export→import), bulk insert (chunked transactions), and all data types.

## Test Classes & Cases

### TestDatabaseExport

Fixture `sample_db` creates 20 users, 15 movies, 10 actors, 50 Rated edges, 30 ActedIn edges, 15 Follows edges, 10 LogEntry docs, 5 Config docs (155 total records).

- **export_jsonl_basic**: Exports entire database; asserts `totalRecords == 155`, `vertices == 45` (20+15+10), `edges == 95` (50+30+15), `documents == 15` (10+5). File in `exports/` dir. See [test_exporter.py#L226-L247](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L226-L247).

- **export_jsonl_with_include_types**: Exports only `User` type; asserts `vertices == 20`, edges/docs zero. See [test_exporter.py#L249-L265](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L249-L265).

- **export_jsonl_with_exclude_types**: Excludes `LogEntry`; asserts `documents == 5` (only Config, logs excluded). See [test_exporter.py#L267-L282](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L267-L282).

- **export_overwrite_protection**: First export succeeds; second with `overwrite=False` raises `ArcadeDBError` mentioning "already exists" or "overwrite". See [test_exporter.py#L284-L304](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L284-L304).

- **export_invalid_format**: Passes `format="invalid_format"`; asserts raises `ArcadeDBError` with "invalid" or "format". See [test_exporter.py#L306-L312](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L306-L312).

- **export_graphml/export_graphson**: Both attempt export; if GraphSON support is missing, skip with `pytest.skip(...)`. See [test_exporter.py#L314-L357](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L314-L357).

- **export_verbose_levels**: Tests `verbose` parameter (0, 1, 2); asserts `"totalRecords"` in stats for each. See [test_exporter.py#L359-L373](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L359-L373).

- **export_empty_database**: Empty database exports with `totalRecords == 0`, `vertices/edges/documents == 0`. File still created. See [test_exporter.py#L375-L396](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L375-L396).

### TestCSVExport

- **export_to_csv_basic**: Queries 20 User records; asserts CSV has 20 rows with columns `userId, name, age, email, premium`. See [test_exporter.py#L400-L426](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L400-L426).

- **export_to_csv_with_fieldnames**: Exports Movie query with custom fieldnames `["movieId", "title"]`; asserts header and column count. See [test_exporter.py#L428-L451](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L428-L451).

- **export_to_csv_empty_results**: Query with no hits; asserts CSV exists and is mostly empty (headers only or zero rows). See [test_exporter.py#L453-L464](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L453-L464).

- **export_to_csv_with_resultset**: Uses `export_to_csv(results, path)` on `SELECT rating FROM Rated WHERE rating > 0`; asserts 50 rows (all Rated edges). See [test_exporter.py#L466-L481](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L466-L481).

- **export_to_csv_with_list_of_dicts**: Passes list of 3 dicts to `export_to_csv()`, verifies CSV written and matches. See [test_exporter.py#L483-L506](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L483-L506).

### TestRoundTripExport

- **jsonl_export_import_roundtrip**: Exports sample_db to JSONL, closes original, creates new DB, imports via `IMPORT DATABASE file://...`, then verifies counts (User 20, Movie 15, Actor 10, LogEntry 10, Config 5) and data integrity (first user name is "User0"). See [test_exporter.py#L508-L567](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L508-L567).

### TestExportWithBulkInsert

- **export_after_chunked_insert**: Uses chunked transactions (no `batch_context`) to create 500 Product vertices, exports to JSONL, asserts `vertices == 500`. See [test_exporter.py#L567-L605](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py#L567-L605).

### TestAllDataTypes

Test class exists (last line ~876) but content not shown in excerpt. Likely tests STRING, INTEGER, BOOLEAN, LIST, MAP, DATETIME, BINARY preservation.

## Quick Patterns

```python
# Full database JSONL
stats = db.export_database("export.jsonl.tgz", format="jsonl", overwrite=True)

# Filter by type
stats = db.export_database("users.jsonl.tgz", format="jsonl",
                            include_types=["User"], overwrite=True)

# CSV from query
db.export_to_csv("SELECT * FROM User", "users.csv")

# CSV with fieldnames
db.export_to_csv("SELECT movieId, title FROM Movie", "movies.csv",
                  fieldnames=["movieId", "title"])

# Import roundtrip
db.command("sql", "IMPORT DATABASE file:///path/to/export.jsonl.tgz")
```

## Key Observations

- Export paths use `exports/` subdirectory relative to cwd
- Stats keys: `totalRecords`, `vertices`, `edges`, `documents`, `elapsedInSecs`, some include `"_rev"` metadata
- GraphML/GraphSON skip gracefully if GraphSON support is unavailable; others raise on bad format
- CSV export supports custom fieldnames and header row
- Round-trip: file path must use `file://` URL format and forward slashes (Windows compat)
