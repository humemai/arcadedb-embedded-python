# Hash Index Schema Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_hash_index_schema.py){ .md-button }

These tests cover HASH index creation and discovery through the Python schema API.

## Covered Behavior

### 1) create, discover, and query

Creates a HASH index through `schema.create_index(...)`, verifies it is discoverable through schema metadata, and confirms equality queries still return the expected record.

### 2) get-or-create and force drop

Verifies idempotent HASH index creation through `get_or_create_index(...)` and cleanup through `drop_index(..., force=True)`.

## Runtime Guard

If the current packaged runtime does not support `IndexType.HASH`, these tests skip instead of failing spuriously.
