# 19 - Hash Index Exact-Match Lookup Workflow

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/19_hash_index_exact_match.py){ .md-button }

This example demonstrates a fuller HASH index workflow that mirrors several of the
behaviors already covered by the Java engine tests:

- creating a unique HASH index with `UNIQUE_HASH`
- creating non-unique HASH indexes with `NOTUNIQUE_HASH`
- creating composite HASH indexes for multi-column exact matches
- inserting deterministic product and warehouse inventory records
- running equality lookups against single-property and composite HASH indexes
- inspecting HASH index metadata from the Python schema API
- verifying missing-key behavior
- updating indexed values and verifying HASH index maintenance
- showing duplicate-key rejection plus rollback semantics
- closing and reopening the database to verify index persistence

## Run

From `bindings/python/examples`:

```bash
python3 19_hash_index_exact_match.py
```

With a custom database path:

```bash
python3 19_hash_index_exact_match.py --db-path ./my_test_databases/hash_index_demo
```

## Notes

- The example is intentionally SQL-first.
- HASH indexes are the right fit for exact-match predicates such as `sku = ?`, `category
  = ?`, or `(warehouse = ? AND sku = ?)`.
- For range predicates or ordered scans, prefer `UNIQUE` / `NOTUNIQUE` `LSM_TREE`
  indexes instead.
- If the packaged runtime does not include HASH index support, the script prints a short
  explanation and exits.
- The example intentionally includes a reopen phase so persisted HASH index metadata and
  exact-match lookups are exercised in a fresh database session.

## Why This Example Exists

The Java engine already has focused HASH index coverage for:

- SQL creation via `UNIQUE_HASH` and `NOTUNIQUE_HASH`
- unique and non-unique lookup behavior
- composite HASH keys
- missing-key behavior
- duplicate-key rejection
- persistence across reopen

This Python example mirrors that behavior with the public bindings API so the examples
set includes a dedicated exact-match index workflow.
