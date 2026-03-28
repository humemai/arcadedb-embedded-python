# 22 - Graph Analytical View SQL Workflow

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/22_graph_analytical_view_sql.py){ .md-button }

This example shows the intended Python posture for Graph Analytical Views: keep the
binding surface thin and drive the entire lifecycle with SQL, even for a much larger
synthetic transport graph. The default run now starts at six-figure scale.

It covers:

- generating a synthetic graph with 100,000 base `City` vertices by default and a denser
  multi-region `ROAD` topology
- creating a named Graph Analytical View with `VERTEX TYPES`, `EDGE TYPES`,
  `PROPERTIES`, and `EDGE PROPERTIES`
- polling `schema:graphAnalyticalViews` until the initial async build becomes `READY`
- inspecting metadata such as `status`, `nodeCount`, `edgeCount`, `compactionThreshold`,
  and `memoryUsageBytes`
- running normal SQL `MATCH` traversals and aggregate queries without a Python-native
  GAV wrapper
- showing how `UPDATE MODE OFF` becomes `STALE` after a large growth wave
- rebuilding explicitly with `REBUILD GRAPH ANALYTICAL VIEW ...`
- altering the view with `ALTER GRAPH ANALYTICAL VIEW ...`
- switching to `UPDATE MODE SYNCHRONOUS` and verifying live count changes on another
  growth wave
- reopening the database to confirm persisted GAV restoration

## Run

From `bindings/python/examples`:

```bash
python3 22_graph_analytical_view_sql.py
```

With a custom database path:

```bash
python3 22_graph_analytical_view_sql.py --db-path ./my_test_databases/gav_demo
```

The default run is 100,000 base cities, 25,000 stale-growth cities, and 10,000
synchronous-growth cities.

For a smaller smoke-sized run:

```bash
python3 22_graph_analytical_view_sql.py --base-cities 1200 --stale-growth-cities 300 --sync-growth-cities 200 --regions 12 --batch-size 300
```

## Notes

- The example is deliberately SQL-first. It uses `db.command("sql", ...)` and
  `db.query("sql", ...)` only.
- `CREATE GRAPH ANALYTICAL VIEW ...` starts with an async build, so checking
  `schema:graphAnalyticalViews` is part of the expected workflow.
- The script demonstrates both manual refresh (`UPDATE MODE OFF` + `REBUILD`) and live
  refresh (`UPDATE MODE SYNCHRONOUS`).
- The database is left on disk so you can reopen it and inspect the persisted GAV.

## Why This Example Exists

The Java codebase already exposes Graph Analytical Views through SQL DDL and schema
metadata. The Python binding therefore does not need a dedicated Graph Analytical
View object API just to manage the feature. This example documents that decision in
executable form at a more realistic scale, so users can see both the operational
lifecycle and the tradeoff of keeping the Python surface thin.
