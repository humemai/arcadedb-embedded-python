# Re-measuring paper cells on a wheels-only post1

The procedure for rerunning the paper's ArcadeDB embedded cells on `26.11.1.post1`, the wheels-only release whose engine is byte-identical to 26.11.1 (DECISIONS #297). The plan and the open question of which cells qualify are CAMPAIGN section 7 row 93 (issue #581). This file is the how. Nothing in it runs by itself, and nothing in it touches the live pass: the rerun writes its own rows file and its own rep state, from its own worktrees.

## What was built

| piece | file | what it does |
|---|---|---|
| build-only mode | `runner.py --build-only`, a hook in `l1_tpc.py`, `l2_graph.py`, `e2_hybrid.py`, `l3d_dense.py`, `post1_rows.py` | A cell stops right after `build()` (load and index, before any timed work) and writes a row with `row_kind = "build_only"`. The runner refuses the flag unless the results file is named `runs_page_<pin>_2611_post<N>.jsonl`, so such a row cannot land in the pass's own rows file. |
| wheel label | `post1_rows.stamp_row`, called by the runner | A stage that exports `BENCH_WHEEL_LABEL`, `BENCH_WHEEL_NAME` and `BENCH_WHEEL_SHA256` gets `wheel_label`, `wheel_name` and `wheel_sha256` on every row. A row without them is labelled by its `engine_version`. The build is `engine_backend` (`native` or `jvm`), as before. |
| the choice of one wheel per cell | `post1_rows.resolve`, used by `land_stage.py --post1-reps N` | Per in-process ArcadeDB cell, the rows of ONE wheel: the newest wheel that has rows for the cell, only when it is complete at N repetitions. A cell that would mix wheels, or whose newer wheel is short, is a problem and the landing exits nonzero before anything is merged. |
| stage generator | `make_post1_rerun_stages.py` | Writes the wheel stage and the lane stages of the rerun, embedded arms only, on top of `make_2611_stages.stage_script` (so the TEMP GATE, the guards, the cap rule and the rep gate are the live chain's own), plus `ORDER.txt` and the sequential driver `run_post1.sh`. |
| tests | `test_post1_rerun.py` | Pure Python, no docker, no timing. `uv run --no-project python test_post1_rerun.py`. |

## What a build-only row may replace

Only these fields of the same cell and repetition, and only when the glue change does not touch a query path (DECISIONS #299: the ingest changes #318, #324 and #325; not the read-path changes #321 and #323, which need a `full` cell):

`build_s`, `ingest_s`, `index_s`, `index_before_load`, `setup_s`, `gav_build_s`, and the load-transport facts `lineitem_buckets`, `async_writers`, `async_sync`, `load_call_rows`, `columnar_insert`.

Every timed workload figure of the cell stays at its 26.11.1 value. The memory, disk and cpu figures of the build window are carried beside the full row's own as `build_window_*` and never over them, because the full row's figures cover the whole container life. The merged row says where each half came from: `timed_wheel`, `timed_ts_utc`, `build_figures_wheel`, `build_figures_wheel_sha256`, `build_figures_run_id`, `build_figures_ts_utc`, `build_figures_replaced`. Its `ts_utc` is the newer of the two, because the freeze keeps the newest row per cell key.

A cell list entry has one of three modes: `build-only`, `full` (a whole cell, with its overlay) or `skip`. The default list is every embedded cell of the paper profile (22 jobs per pass per chain): lane cells `build-only`, the two multipass overlays `skip` (an overlay times queries, there is nothing to stop after).

## The order of the real rerun

1. **Preconditions.** The live n=3 pass and the PG-wire catch-up have ended; `bench/arcadedb-import-26111` (the four-arm generator, PR #554) is merged, because the native chain needs it (`make_post1_rerun_stages.py` refuses a native chain without it); the post1 wheels are released (tag and PyPI) and the byte-identity guard of DECISIONS #297 passed; the user said go. Nobody syncs the mini during the live pass: a dirty or moved tree aborts its queues.
2. **Pin check.** The engine commit is the pass's (`ENGINE_COMMIT` of the pins file), the wheel label is `26.11.1.post1`, and each wheel's file name carries that version. The stage reads the version out of the built image and refuses on a difference, so a wheel whose metadata says another version cannot run (the candidate JVM wheel of the glue A/B is one: its metadata says 26.11.1). `engine_pin.jar_pin` makes the engine-jar check accept the `X.Y.Z` jar under an `X.Y.Z.postN` pin.
3. **Cell list.** `python3 make_post1_rerun_stages.py --write-cells post1_cells.tsv`, then edit the mode column from the measured A/B (never by judgment, DECISIONS #298).
4. **Dry run, laptop.** `python3 make_post1_rerun_stages.py --dry-run --cells post1_cells.tsv --hours HOURS.tsv --reps 3` prints the stage list and an ESTIMATE per chain. Generate the scripts with the real pins, `bash -n` is part of the selftest. Run ONE build-only cell on the laptop with a synced wheel into a scratch results file (`runner.py --lanes l1tpc --workloads oltp --scale tpch1 --backends arcadedb_embedded --build-only --results-file runs_page_dry_2611_post1.jsonl`) and read the row back: `row_kind`, `wheel_sha256`, `build_s`, and no timed figure. The laptop verifies, the mini measures.
5. **Mini, only on the go.** Worktrees at the harness commit, one per chain (`git worktree add --detach ~/post1-wt/<chain> <sha>`, `results` linked as `fourarm/run.sh` does), the generated folder copied to `~/stages-2611c/post1/`, then `touch ~/POST1.go` and `setsid nohup bash run_post1.sh`. One timed job at a time, `ORDER.txt` is the order, removing the go file stops it at the next stage boundary.
6. **Landing.** `land_stage.py --pin <commit> --post1-reps 3 --dry-run`, read the per-cell decisions, then `--apply`. A build-only row anywhere else is refused.
7. **Rows and state of the live pass are never touched.** The rerun writes `runs_page_<pin>_2611_post1.jsonl` and `rep-state-2026-11-<pin>[-<build>]-post1.tsv`.

## What the paper may say

For a rerun cell, only the post1 figures of the fields above, labelled with the wheel (`26.11.1.post1`, sha256 in the artifact), and the 26.11.1 figures for everything else of the cell, labelled as 26.11.1. The 26.11.1 rows of a rerun cell stay in the raw logs and are not printed (DECISIONS #298). A cell that was not rerun keeps its 26.11.1 rows. The served arms never change (they do not use the wheels).

## n and repetitions

DECISIONS #240: a speed claim needs 3 runs per arm at 2x or more, 5 or more at 1.3x to 2x, 10 or more below 1.3x, pre-registered in the README and the brief. The landing's `--post1-reps N` is that n: a cell with fewer post1 repetitions than N is refused, never filled from 26.11.1. The paper's n=3 is `--post1-reps 3`; a pass 4 or 5 of the live chain would need the same number of post1 repetitions.

## Rollback

`uv run --no-project python post1_rows.py strip --label 26.11.1.post1 results/runs.jsonl` deletes every row that carries the wheel label (a full post1 row, or a cell merged from build-only rows), then `land_stage.py` without `--post1-reps` lands the live rows file again, which restores the replaced 26.11.1 rows, and the page is rebuilt by the landing.

## Not verified here

Nothing was run on the mini or in docker. The freeze's handling of the added columns (`row_kind`, `wheel_*`, `build_*`, `timed_*`, `build_window_*`) and of two `engine_version` strings in one freeze (the one-version gate of the four-arm freeze) is checked on the landing's dry run, not before. `verify_pair_c25.sh` may compare the wheel version with the engine jar version and has not been read for `.postN`.
