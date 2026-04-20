# ArcadeDB Python Bindings Profiler

This profiler measures Python-side overhead after query execution in Java.

It focuses on the binding paths that matter most in practice:

- SQL result consumption
- OpenCypher result consumption
- async callback streaming
- CSV export
- SQL vector result handling

## Current Baseline

The canonical report in this directory is:

- `profile-report-20260420-140105.json`

Main takeaways from that run:

- `sql_projected_to_list` improved from about `8.55s` to `6.98s`
- `sql_full_records_to_list` improved from about `76.71s` to `27.51s`
- `export_to_csv` improved from about `24.79s` to `17.42s`
- lazy scan paths stayed roughly flat
- retained eager materialization is still the expensive memory-heavy case

Required fixes are done. Any further work is optional tuning.

## Run

From `bindings/python`:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py --preset full --runs 3 --records 5000 --person-count 2000 --vector-records 1500 --vector-k 10 --query-runs 100 --heap-size 4g
```

## Read The Report

- `wall_total` is isolated scenario runtime
- `rss_*_delta_bytes` shows process memory growth across phases
- `python_peak_*_delta_bytes` shows Python allocation growth from `tracemalloc`

In practice:

- if lazy scan is cheap but `to_list()` is expensive, Python materialization is the problem
- if wrapper scan is cheap but full rows are expensive, dict/list construction is the problem
- if retained materialization spikes memory, live Python ownership is the problem

## Files Here

- `profile_bindings.py`: profiler entry point
- `profile-report-20260420-140105.json`: current baseline artifact
- `results.md`: short benchmark summary
