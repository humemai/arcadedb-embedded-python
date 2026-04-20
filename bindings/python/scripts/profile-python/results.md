# Results

This directory keeps one current benchmark artifact and one short summary.

## Canonical Report

- `profile-report-20260420-140105.json`

Run used to produce it:

```bash
cd /mnt/ssd2/repos/arcadedb-embedded-python/bindings/python && /mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py --preset full --runs 3 --records 5000 --person-count 2000 --vector-records 1500 --vector-k 10 --query-runs 100 --heap-size 4g
```

## Current Numbers

- `sql_projected_lazy_scan`: mean `2.68s`
- `sql_projected_to_list`: mean `6.98s`
- `sql_full_records_to_list`: mean `27.51s`
- `sql_full_records_to_list_no_convert`: mean `30.62s`
- `sql_full_records_wrapper_scan`: mean `4.83s`
- `sql_full_records_to_list_retained`: mean `24.64s`
- `sql_aggregate_first`: mean `0.55s`
- `sql_aggregate_one`: mean `0.50s`
- `opencypher_lazy_scan`: mean `0.30s`
- `export_to_csv`: mean `17.42s`

Peak Python allocation deltas:

- `sql_full_records_wrapper_scan`: about `60.77 KiB`
- `sql_full_records_to_list`: about `20.52 MiB`
- `sql_full_records_to_list_retained`: about `305.63 MiB`

## Comparison To The Earlier Full Baseline

Historical comparison numbers from the pre-refactor full run:

- `sql_projected_to_list`: `8.55s` -> `6.98s` (about `18%` faster)
- `sql_full_records_to_list`: `76.71s` -> `27.51s` (about `64%` faster)
- `export_to_csv`: `24.79s` -> `17.42s` (about `30%` faster)
- lazy scan paths stayed effectively flat

## Read

- eager materialization got much cheaper
- wrapper traversal is not the main cost center
- retained full-row ownership is still the expensive memory case
- required fixes are done; any further work is optional tuning
