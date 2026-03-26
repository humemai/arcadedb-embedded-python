# Geo Predicate SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_geo_predicate_sql.py){ .md-button }

These tests cover the SQL geospatial predicate helpers used from Python.

## Covered Behavior

### 1) `geo.within` and `geo.intersects`

Checks boolean semantics for inside/outside points, overlapping/disjoint polygons, and `NULL` propagation.

### 2) boundary and repeatability

Re-runs representative queries to verify stable results and acceptable boundary-point semantics.

## Runtime Guard

If the packaged runtime does not include the geo SQL functions, these tests skip cleanly.
