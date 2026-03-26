# 18 - Geo Predicates With WKT Points And Polygons

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/18_geo_predicates_wkt.py){ .md-button }

This example demonstrates the current SQL-first geospatial surface in the Python
bindings. It deliberately uses WKT stored in `STRING` properties and exercises the same
`geo.*` predicates already covered by the Java engine tests:

- creating a `GEOSPATIAL` index on point coordinates
- storing depots as WKT `POINT` values
- storing service areas as WKT `POLYGON` values
- running direct `geo.within(...)` and `geo.intersects(...)` sanity checks
- querying indexed point records with polygon filters
- querying stored polygon records for overlap
- reopening the database to verify persisted geospatial index metadata
- dropping the index and rerunning the same filter to show full-scan fallback

## Run

From `bindings/python/examples`:

```bash
python3 18_geo_predicates_wkt.py
```

With a custom database path:

```bash
python3 18_geo_predicates_wkt.py --db-path ./my_test_databases/geo_demo
```

## Notes

- The example stays SQL-first on purpose. There is no separate Python geometry object
  API.
- Geospatial values are stored as WKT strings and interpreted in queries via `geo.*`.
- `GEOSPATIAL` indexes are for spatial predicates, not uniqueness constraints.
- The example includes both the indexed path and the post-`DROP INDEX` fallback path so
  the script shows that the index changes performance characteristics, not result
  correctness.
- If the packaged runtime does not include geospatial SQL functions or `GEOSPATIAL`
  index support, the script prints a short explanation and exits.

## Why This Example Exists

The Java engine already has focused geospatial coverage for:

- `CREATE INDEX ... GEOSPATIAL`
- indexed `geo.within(...)` queries over stored WKT points
- indexed `geo.intersects(...)` queries
- fallback evaluation when the index is absent
- persistence across reopen

This Python example mirrors those behaviors with the public bindings API so the examples
set includes a dedicated geospatial workflow without introducing a new Python-side DSL.
