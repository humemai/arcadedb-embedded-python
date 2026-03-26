# Materialized View SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_materialized_view_sql.py){ .md-button }

These tests cover the SQL lifecycle for materialized views.

## Covered Behavior

### 1) end-to-end lifecycle

Creates a materialized view, inspects `schema:materializedViews`, refreshes it after new source rows arrive, and drops it cleanly.

### 2) refresh mode changes

Alters a view to `REFRESH MANUAL`, verifies the metadata change, and confirms that rows only update after explicit refresh.

### 3) idempotent drop

Checks that `DROP MATERIALIZED VIEW IF EXISTS` is safely repeatable.
