# Data Import Examples

This page points to the examples that load data into ArcadeDB from Python. The
[Data Import Guide](../guide/import.md) holds the recommendations, the import formats,
and the code patterns; the examples below show them at scale.

Before running the MovieLens and Stack Overflow examples, download their datasets with
the **[Dataset Downloader](download_data.md)**.

## Which Example Covers What

**[Example 04 - CSV Import: Documents](04_csv_import_documents.md)**

- parses the MovieLens CSV files in Python and loads them into document types with
  batched, parameterized `INSERT` statements
- defines the schema explicitly (integer-like columns to LONG, decimals to DOUBLE,
  text to STRING) and imports empty cells as NULL
- benchmarks queries before and after indexes
- with `--export`, exports the database to JSONL and re-imports it with
  `IMPORT DATABASE` as a round trip

**[Example 05 - CSV Import: Graph](05_csv_import_graph.md)**

- reads Example 04's document database (or an Example 04 JSONL export) and builds a
  graph from it: users and movies as vertices, ratings and tags as edges
- builds vertices with SQL, `db.graph_batch(...)`, or synchronous transactions, and
  edges with SQL `CREATE EDGE`
- creates the indexes before the edges (unless `--no-index`), and validates the graph
  with queries

**[Example 15 - Table Ingest Comparison](15_import_database_vs_transactional_table_ingest.md)**
and **[Example 16 - Graph Ingest Comparison](16_import_database_vs_transactional_graph_ingest.md)**

- compare transactional SQL, the async SQL path, SQL `IMPORT DATABASE`, and
  `db.import_documents(...)` (tables) or `GraphBatch` (graphs) on the same generated data,
  with count checks before any timing is trusted

**[Example 22 - numpy Bulk I/O](22_numpy_bulk_io.md)**

- bulk document ingest with `db.insert_many(...)`, transactional and with
  `parallel=True` on a type created with one bucket per async writer
- time-series ingest from numpy arrays with `AsyncExecutor.append_samples(...)`

## The Short Version

- For bulk document ingest, use `db.insert_many(...)`. With `parallel=True` it raises
  `ArcadeDBError` if the async writers reject any record.
- For bulk graph ingest, use `db.graph_batch(...)`.
- Keep SQL `IMPORT DATABASE` for its supported file formats and for restoring exports.
- Do not use `db.async_executor().command(...)` for bulk writes. Before 26.10.1 it could
  silently drop records above parallel level 1 (`ArcadeData/arcadedb#7615`, fixed in
  #7625); see [Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation).

## Additional Resources

- **[Data Import Guide](../guide/import.md)** - Recommendations, formats, and code patterns
- **[Import Workflow Reference](../api/importer.md)** - Supported SQL import surface
- **[Database API: insert_many](../api/database.md#insert_many)** - Bulk document ingest
- **[GraphBatch API](../api/graph_batch.md)** - Bulk graph ingest

## Source Code

View the complete example source code:

- [`examples/04_csv_import_documents.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/04_csv_import_documents.py)
- [`examples/05_csv_import_graph.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/05_csv_import_graph.py)
