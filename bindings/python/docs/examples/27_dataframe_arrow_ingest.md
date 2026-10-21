# 27 - DataFrame And Arrow Ingest

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/27_dataframe_arrow_ingest.py){ .md-button }

A pandas or Polars DataFrame, or an Arrow table, loads straight into a type, and a
result set comes back out as a Polars DataFrame. There is no row loop and no CSV in
between.

It covers:

- a pandas DataFrame into a document type with `Database.insert_dataframe()`: a
  timestamp column, a column with nulls (a pandas `NaN` is a null), and a list column,
  loaded in batches of 10,000 rows. See [`insert_dataframe`](../api/database.md#insert_dataframe)
- a Polars DataFrame into a vertex type, then edges between those vertices through
  `graph_batch().new_edges()`. An edge type is not a target of `insert_dataframe()`: an
  edge needs the RIDs of both ends
- an Arrow table into a type that declares some of its properties with
  `Database.insert_arrow()`: the `int64` column converts to the declared `INTEGER`, the
  timestamp to `DATETIME_MICROS`, and an undeclared `float32` column is stored as
  `DOUBLE`. A column that would lose data (a float into an `INTEGER`) is refused with
  `TypeError` before a row is written. The mapping tables are on
  [`insert_arrow`](../api/database.md#insert_arrow)
- the result back out with `ResultSet.to_polars()`, which reads through `to_arrow()`

Needs pandas, polars and pyarrow (`pip install 'arcadedb-embedded[pandas,polars]'`).

## Run

From `bindings/python/examples`:

```bash
python 27_dataframe_arrow_ingest.py
# reduced scale:
python 27_dataframe_arrow_ingest.py --rows 10000
```

The database is created under `./my_test_databases/dataframe_ingest_db` (`--db-path`).
