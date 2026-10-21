# 27 - Python Functions And Record Events

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/27_python_functions_and_record_events.py)

Two things no query language can express, which `sqlite3` and DuckDB also offer from Python:

- **A Python function called from a statement.** `db.register_function("slugify", fn)`, then
  `SELECT slugify(name) FROM Person` and `WHERE slugify(name) = '...'`. From openCypher the
  function needs a namespaced name (`py.slugify`). An exception in the function arrives as an
  `ArcadeDBError` that names the function and the Python exception.
- **A Python callback on a record change.** `db.on("after_create", fn, "Account")` runs
  `fn(record)` for each new record. A `before_create` callback that returns `False` refuses
  the write. `handle.remove()` stops a callback.

The example also measures what one Python call costs against the same expression in SQL.

## Run

From `bindings/python/examples`:

```bash
python 27_python_functions_and_record_events.py --rows 20000
```

The database is created under `./my_test_databases/python_functions_events` (`--db-path`).

## Notes

- Synthetic data, no download; a few seconds end to end.
- The per-call cost is one round trip between the engine and Python, about 5 to 10
  microseconds on a laptop core. It is why a SQL expression is better where one can do the
  work.
- See [`register_function`](../api/database.md#register_function) and
  [`on`](../api/database.md#on) for threading, scope, and error rules.
