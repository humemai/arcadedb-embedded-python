# Schema Batching Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_schema_batching.py)

Schema statements apply immediately, and many of them batch in one transaction (ArcadeData/arcadedb#8635).

A schema statement is not transactional: it takes effect at once, and a rollback does not undo it. Running many inside one transaction is the recommended way to create many types, because the schema is written to disk once when the transaction ends (ArcadeData/arcadedb#8635).

## Test Cases

### 1) many schema statements in one transaction all take effect

Twelve types, each with a property and a unique index, created inside one `with db.transaction():` all exist after it and after a reopen, and the unique index refuses a duplicate id.

### 2) a rollback does not undo a schema statement

A type created inside a transaction that raises is still there afterwards and after a reopen, while the insert made in the same block is rolled back.
