# Reading the results without misreading them

PROTOCOL.md says how a run is produced. FAIRNESS.md says what makes a comparison legitimate. This file says how to read what came out.

The single rule, from which most of the rest follows:

> **The tracker is history. The artifact is state.**
>
> Task notes, issue titles and old summaries describe what was true when they were written. They are not refreshed when the thing is fixed. Read the data before repeating what a note says about it.

## Before believing any number you did not just measure

1. **Open the file.** Not the task, not the summary, not last week's message.
2. **Print the whole record**, not the fields you expect. `settle_s: 0.0` is the evidence that no engine settled; a filter that drops falsy values hides it and makes symmetry look like absence.
3. **Check which arm you have.** Several files hold multiple arms of the same experiment, distinguished by flags rather than by name.
4. **Check which file you have.** Several lanes split one comparison across two files.
5. **If it contradicts the generated tables or the page, suspect yourself first.** A disagreement is far more likely to be a misread field than a wrong table.

## Field traps, specifically

**The 12-hour aggregation is `q_global_ms`, not `q_range_ms`.** `q_global_ms` returns 12 rows, one per hour, and medians about 25.0 ms on the native path. `q_range_ms` is a 60-row range query and medians about 4.4 ms. Both look like plausible "aggregation" numbers, and reading the second as the first makes the page appear wrong by 5.7x.

**Last-point is one field.** Every l4 lane row records `q_last_ms` (unbounded); `q_last_unbounded_ms` exists only in the retired probe files.

**ArcadeDB has two time-series arms, both lane rows.** Embedded and served, backends `arcadedb_ts_native`, `arcadedb_ts_doc`, and their `_server` twins; the page prints all four.

**`engine_version` is deliberately null for non-ArcadeDB rows in L4.** Use `backend_version`. `run_conditions()` stamps `engine_version` from the installed wheel, which is right for the ArcadeDB row and wrong for DuckDB and QuestDB, so `l4_tsbs.py` asks each backend for its own version instead. A wrong version that passes a provenance audit is worse than none.

**Arms are selected by flag, not by filename.** `claims_check.ts_arm()` takes `primitive=` and `numpy_cols=` because the published row is one specific arm. Assert the flags rather than globbing the directory.

**A comparator row's version and digest are read from the row** (`server_image`, `engine_version`); `runner.BACKENDS` describes future rows only (BUGS.md F32).

**An ArangoDB dense row's `recall_at_10` is a calibrated operating point, not a knob.** The IVF `nProbe` is chosen in the cell (`ivf_nprobe`, with `ivf_nlists` = `round(4*sqrt(n))`) as the smallest value whose held-out recall reaches the frozen ArcadeDB fp32 median: `ivf_calibration_recall` is that held-out estimate, on `ivf_calibration_queries` queries from `ivf_calibration_slice`, never the timed set, and `ivf_recall_target` with `ivf_recall_target_source` say what it was matched to. Read the timed `recall_at_10` as the outcome of that match (FAIRNESS.md F7).

**Legacy embedded SurrealDB rows say `surrealdb-embedded:2.0.0`; the page says core 2.3.10.** Both are right (BUGS.md F39): 2.0.0 is the Python SDK, which stamped itself as the engine, and the core it compiles in is surrealdb-core 2.3.10. Rows frozen before the fix keep the SDK string, and the exporter resolves that stamp to the core version at load through the pinned wheel, so the file string and the page differ by design. Newer rows carry `surrealdb-embedded:2.3.10 (sdk 2.0.0)`.

**`disk_data_mb` and `server_disk_mb` are megabytes on the row and gibibytes on the page.** The exporter divides at load (`_UNIT_DIVISOR`, through `unit_field` when the metric is a callable, BUGS.md F40); a value that looks a thousand times too large under a "disk GiB" header is the divisor being skipped, not a real footprint. `page_check` bounds every disk median at 200 GiB for that reason.

**A served row's page disk value is the server container alone.** `disk_data_mb` on the row still holds server plus client; `export_web._disk_data` subtracts the client for the page (BUGS.md F38).

**A timed-out row records where it died.** `timeout_client_disk_mb` and `timeout_cpu_mem` are written on the timeout path, and the cell log carries the lane's `PHASE` markers (BUGS.md F41). Read them before recording a DNF.

**`host` is recorded on two lanes of seven.** Sparse and dense have it; the rest record the container but not the machine. Do not imply a uniform environment from rows that cannot prove one. Recording `BENCH_HOST` on every row is on the October checklist (DECISIONS #74).

## Publishing traps

**An absent row makes a claim.** If comparators appear at a tier and we do not, a reader concludes we could not do that tier. `export_web.py` publishes only scales where our engine also has a row, and names what it withheld.

**Real numbers can compose a false impression.** A table can be accurate in every cell and wrong as a whole. Ask what a reader concludes, not only whether each figure is right.

**Negative numbers can be the finding.** E4's process-boundary term goes negative at the four smallest sizes. That is the boundary sitting below the design's resolution, which is the evidence for "co-locating costs nothing measurable". Publish it with the explanation rather than clamping to zero; `claims_check` pins the count of negative sizes at 4 so it cannot be quietly tidied away.

## Gates

Three, and they answer different questions. `refresh_web_page.py` runs all of them; run them by hand after touching results or tables:

    BENCH_ENGINE_COMMIT=<pin> python provenance_check.py   # does a cell trace to a run
    BENCH_ENGINE_COMMIT=<pin> python fairness_check.py     # F1 to F9
    BENCH_ENGINE_COMMIT=<pin> python page_check.py         # page cells vs generated tables, prose vs pins

`claims_check.py` is a helper library `page_check` imports, not a gate. Running it by hand is still the only thing that checks the claims in PROTOCOL.md section 4. `prose_check.py` and `comparator_pins_check.py` are hand-run too.

Publishing to humem.ai is one command; PUBLISHING.md says which one and why it is a command rather than a checklist.
