# 14 - Lifecycle Timing Benchmark

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/14_lifecycle_timing.py){ .md-button }

This example measures the embedded ArcadeDB lifecycle from Python with a mixed workload.

It reports timings for:

- JVM startup
- database create + schema setup
- database open
- transaction load (table + graph + vectors)
- query phase
- close
- reopen
- reopen query phase
- reopen close
- server mode: `close database` and `open database` on a running bundled server, timed
  over HTTP (three rounds, averaged)

## Run

From `bindings/python/examples`:

```bash
python3 14_lifecycle_timing.py
```

With custom workload:

```bash
python3 14_lifecycle_timing.py \
  --runs 5 \
  --table-records 50000 \
  --graph-vertices 10000 \
  --vector-records 10000 \
  --vector-dimensions 64 \
  --query-runs 100 \
  --jvm-heap 2g
```

## Notes

- The benchmark uses a random database path under the system temp directory by default;
  `--db-path` sets it instead.
- The path is removed at the end (cleanup is always on). The server step uses the same
  path with a `_server` suffix and removes it too.
- The script is intended for benchmarking in `examples`, not deterministic CI assertions.

## Expected Output (Desktop Baseline)

After the per-run lines, the server step prints its two averages (values vary):

```text
Server mode, the same database closed and reopened on a running server:
  close database: <seconds>s avg over 3
  open database:  <seconds>s avg over 3
```

On a normal desktop CPU, this is a representative summary shape you can expect:

```text
Averages
  jvm start:   0.242371s
  create:      0.065687s
  schema:      0.036061s
  open:        0.003828s
  transaction: 1.217344s
  load:        1.217346s
  query:       5.025231s
  close:       0.002140s
  reopen:      0.011762s
  reopen query:2.343519s
  reopen close:0.001561s
```

Actual timings vary with CPU, storage, memory, Python/JVM versions, and current system load.
