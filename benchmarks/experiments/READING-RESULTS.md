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

**An envelope failure is not a timeout.** A cell with `rc=137` and `oom_killed` true was killed by the kernel at the tier's memory cap; it did not run out of time, and the `error` string is not `timeout_after_*`. Read it as "this engine did not fit the envelope every engine on this tier was given", which is a fact about the engine's memory behaviour at that size and evidence for nothing about its latency. The exporter words it differently from a censored cell for that reason. Two on the record, both SurrealDB embedded at the 32 GiB tier envelope on 2026-09-18/19: TPC-H SF10 on the document analytics lane, and the full SF1 network on the graph analytics lane. `rc=137` WITHOUT `oom_killed` is a third thing, a container that exited on a signal for some other reason, and it is investigated before it is recorded (see the rule above this one).

**A censored note names the phase the cap interrupted, when the row can say.** "Exceeded its budget" alone cannot tell an engine that spent its whole budget ingesting from one that reached the queries and stalled on the ninth. `runner.py` records the cell's last PHASE markers in `timeout_phase_hint`, and `export_web._timeout_phase` reads the last one into a phrase: a query phase names its query ("query lsqb_q9"), a build, ingest, connect or close phase names itself. October's two censored cells are the two ends of that range -- SurrealDB at 500k was still in the index build at 7,046 s and never ran a query, while ArcadeDB's analytics cell was starting lsqb_q9 after lsqb_q8 returned a p50 of 77,857 ms. When the hint cannot be read (a container that printed nothing) the clause is omitted rather than guessed, so its absence means "we do not know", never "no phase".

**An outcome note may name a size the table does not print.** `export_web._censored_notes` reads `runs.jsonl`, not the frozen CSV, so it writes a note for every cell that failed at any size the lane ran, including a raised tier whose rows never reached the table. A raised tier replaces a table's rows only when every engine on that table has landed there (DECISIONS #103b), so a half-finished raise leaves notes about the larger size under rows at the smaller one. That is the state of `docs_olap` (notes about TPC-H SF10 over SF1 rows) and `l2olap` (a note about the full SF1 network over the projection rows) since 2026-09-19. The notes are true; what they omit is that other engines did measure at the larger size, so do not read "there is no row" as "nobody got a number there". **That describes the SEPTEMBER page.** October does not reach that state: under #108 a table carries both sizes, the large one as a row group, and an engine absent from it is a declared outcome (#103g) rather than a reason to withhold every other engine's rows.

**`host` is recorded on two lanes of seven; `bench_host` on every row since 2026-10.** Sparse and dense have `host`; the rest record the container but not the machine. Rows measured under the 2026-10 instrument carry `bench_host`, written by the runner and refused at paper tier when unset (DECISIONS #74). Do not imply a uniform environment from rows that cannot prove one.

**`instrument` names the query set, timers, and durability rule a row ran under.** Rows before 2026-10 carry none and are the September instrument; `load_canonical` and `export_web` refuse two values in one table. Read a 2026-10 document OLTP row's `oltp_ops_per_s` as new-order and payment together (`oltp_ops` says how many), where a September row's is new-order alone.

**`durability` is what the engine ran at commit, read from the engine where it can be read.** PostgreSQL-family rows carry the server's own `SHOW synchronous_commit` answer; a value ending "(NOT the #81 setting)" means the server was not started with the flag and the row fails F10. Strings starting "fsync at commit" are the named exceptions (Neo4j, LadybugDB, DuckDB), and "unverified" is SurrealDB served, which has no setting to read.

**A digest is of the canonical answer, not of the raw rows.** The digest is taken after the answer is put in canonical form: sorted unless the query defines an order, floats rounded to a fixed precision, engine-specific row wrappers and column ordering gone. Two engines whose digests match did not return identical result objects, and hashing what a driver handed back instead will disagree on every engine pair for reasons that are not about the answer.

**A measure is compared as a number; a count and an identifier are compared exactly.** A summed or averaged column is declared numeric once per query, so an engine returning an integer and one returning a double agree: ArangoDB's `SUM` returns 37,734,107 where the others return 37,734,107.0, which split the pricing summary seven engines to one at SF1 while both sides held the same number. A count is never declared that way, because the float side rounds to six significant digits and 1,234,567 would agree with 1,234,568.

**The revenue total and the revenue by month carry a row count in the answer.** It is compared exactly and is not a page column (DECISIONS #94): at the campaign's largest tier a single lost row moves either sum by less than the digest's rounding, detected 10.8 and 36.5 per cent of the time, and F46 is an engine that loses exactly one row to an index bound.

**A withheld cell is not a missing measurement.** A disagreement that has been reproduced and filed upstream prints as KNOWN and its cell is withheld (`equivalence_check.KNOWN_DISAGREEMENTS`, `export_web.WITHHELD_CELLS`); today that is the served native time-series group-by, upstream #7610, and the entry goes at the re-pin that carries the fix.

**Every row since 2026-09-14 says how hot the machine was.** `host_temp_c_start` and `_end`, `host_throttle_count_start` and `_end`, and `host_throttled_ms` (BUGS.md F45). mini throttles under sustained load while the busy cores hold 4.3 GHz, the power mode is unchanged by decision, and rows from different stages are compared with those fields read rather than assumed equal.

**"Unexpressible" is a declaration, not a failure.** An engine whose adapter declares an operation absent has said so deliberately (DECISIONS #88); `equivalence_check` names it and the table prints a dash with the reason in its condition. It is not a crashed cell, a timeout, or a gap to be filled, and it is not evidence that the engine is slow. A silently missing answer is the failure, and that is what the gate exists to tell apart from this.

**`ingest_s` and `index_s` are present only where the engine has the boundary** (ArcadeDB, pgvector, Neo4j, Milvus, LanceDB); `build_s` is still the whole timer and the two do not sum to it exactly (schema creation and Milvus's compaction sit outside them). Milvus's `index_s` is its post-build wait, flush through load.

**The graph write pass now has a partner.** `delete_p50_ms` and `delete_p99_ms` come from deleting, in order, the persons the write pass created (with their edge), one transaction each; `hop3f_*` is the 3-hop read filtered on the far end. Neither exists on September rows.

**`q_groupby_rows` and `q_high_rows` are data-dependent shapes.** The time-series lane records them instead of asserting them, and F10 refuses a table whose engines disagree; the other three queries keep their asserted shapes (1, 60, 12 rows).

**A row says two things about durability, and they can disagree.** `durability`
is what the ENGINE reported, read back out of it wherever it can be asked;
`durability_class` is what the CELL asked for (DECISIONS #90). They agree on a
healthy row. A row where they differ is a flag that did not take -- an
environment variable the server ignores, a JVM property that never reached the
JVM -- and `fairness_check` fails it rather than publishing the asserted value.
`durability_no_setting` marks the four engines with no knob (Neo4j, DuckDB,
LadybugDB, the SurrealDB 3.2.4 server); they run once and the page prints that
one number in both columns. `durability_server_flags` says what the runner
changed on a server container for the class, and is blank for an embedded arm.

**A strict cell is a different cell, not a different column.** The strict arm of
a write cell carries the same lane, scale, workload, backend and rep as the
relaxed one and is told apart only by `durability_class`, which is why that
field is part of the canonical key and why the run_id carries a `_dstrict`
suffix. Reads and bulk ingests exist in the relaxed class only.

**`res_<query>_digest` is the ANSWER, not a checksum of the row.** Every timed query whose answer is deterministic carries three fields: `res_<q>_digest` (sixteen hex characters over the canonical answer), `res_<q>_sample` (the first few canonical rows, readable), and `res_<q>_n` (the row count). A digest that reads `unexpressible: <reason>` means the engine cannot ask that question and the reason is the adapter's own (DECISIONS #88). Two engines with the same digest gave the same answer; two with different digests did not, and the samples say how. Do not compare digests across scales or across queries: the declared column names and the ordering flags are hashed with the rows, so a digest identifies an answer to one question at one size.

**A write's digest is the state it left, not what it returned.** `res_crud_insert_*`, `res_crud_update_*` and `res_crud_delete_*` are untimed read-backs of the whole CRUD table after each phase; `res_neworder_*` and `res_payment_*` are the orders table after each loop; `res_graph_insert/update/delete_*` are the persons the graph writes created. `res_crud_read_*` is the only one of the set that digests what the timed calls actually returned.

**The two vector lanes record no digests, on purpose.** Their answers come from an approximate index, where two correct engines legitimately differ; they are checked by recall against exact ground truth instead, and `equivalence_check` lists them as declared. The cross-model read paths use both: `recall_retrieval` and `recall_filtered` judge the vector half, `res_retrieval_docs_*` and `res_filtered_candidates_*` the graph and document halves.

**`recall_filtered` near zero is a capability, not a bug.** `filtered_mode` says how the arm ran the graph-filtered vector search. An arm that pre-filters ranks the candidate set directly and should reach 1.0; an arm that post-filters searches globally to `filtered_overfetch` and then drops non-neighbours, and its recall is bounded by how many of the candidates fall in that global top-N. Both ArcadeDB arms post-filter, because ArcadeDB SQL at 26.8.1 has no scalar vector-distance function to rank a candidate set with. Read `filtered_candset_match` first: it is the fraction of queries where the engine's own traversal found the same candidate set the harness derives from the generated edges, and a recall means nothing if that is not 1.0.

**`mutate_*` exists only where the mutation phase ran.** `mutate_ran` and `mutate_reason` are on every dense row and say which of the three cases applied: the one-million tier, forced on by `BENCH_DENSE_MUTATE=1`, or not this tier. `mutate_deleted_hits` must be zero; a non-zero value is an index still returning records the engine said it deleted, which is a correctness failure and not a latency one.

**The page's cold column is `cold_first_query_ms`, one per cell.** It is the
first query the cell ran after the database opened, named by
`cold_first_query_name`, and on the two vector lanes that is a warmup query
rather than the first timed one -- which is why it is the cold one (#89 as
amended). The per-query `cold_<q>_ms` fields are still on the row and are still
true; they are simply more than the page prints. `cold_first_query_na` carries
the reason where the cell times no query at all.

**No table prints an aggregate across its queries.** No mean, no median, no
geometric mean: the per-query columns are the report (#89 as amended). A row
that looks like it should have one does not.

**`cold_<q>_ms` / `warm_<q>_p50_ms` / `warm_<q>_p99_ms` are the same three questions in every lane.** The cold number is the first iteration after the database was opened; the warm numbers are the rest. A lane's own older field names still exist and still mean what they did: `q1_ms` on the document lane pools cold and warm, and the graph lane's unprefixed read fields ARE the cold pass, with `cold_point_p50_ms` and friends added as aliases so a table need not know which lane it is reading. `cold_warm_na` carries the reason where the split does not apply, and a blank there means nobody has said why.

**ArcadeDB's Q6 before 2026-10 summed two of three discount buckets.** `Q6_ARCADE` was written with `l_discount >= 0.05 AND l_discount <= 0.07`, and ArcadeDB SQL parses a decimal literal in a comparison at single precision, so `>= 0.05` behaves as `> 0.05` and the 0.05 bucket is dropped; the same query through `BETWEEN` or through bound parameters returns all three. Measured on the laptop at SF0.01: 10,761 rows against 16,323, revenue 842,572.68 against 1,193,053.23, while every comparator computed the 1,193,053.23 answer. September's ArcadeDB Q6 cells are therefore a smaller query than the one beside them. Fixed in the 2026-10 instrument; the engine defect is upstream's.

**ArcadeDB's Q1 before 2026-10 computed four aggregates where every comparator computed five.** `sum(l_extendedprice * (1 - l_discount))` was never written into `Q1_ARCADE`. Same shape as the Q6 finding and the same consequence: both ArcadeDB arms ran a cheaper query than the engines printed beside them.


## Publishing traps

**An absent row makes a claim.** If comparators appear at a tier and we do not, a reader concludes we could not do that tier. `export_web.py` publishes only scales where our engine also has a row, and names what it withheld.

**Real numbers can compose a false impression.** A table can be accurate in every cell and wrong as a whole. Ask what a reader concludes, not only whether each figure is right.

**Negative numbers can be the finding.** E4's process-boundary term goes negative at the four smallest sizes. That is the boundary sitting below the design's resolution, which is the evidence for "co-locating costs nothing measurable". Publish it with the explanation rather than clamping to zero; `claims_check` pins the count of negative sizes at 4 so it cannot be quietly tidied away.

## Gates

Four, and they answer different questions. `refresh_web_page.py` runs all of them; run them by hand after touching results or tables:

    BENCH_ENGINE_COMMIT=<pin> python provenance_check.py    # does a cell trace to a run
    BENCH_ENGINE_COMMIT=<pin> python fairness_check.py      # F1 to F12
    BENCH_ENGINE_COMMIT=<pin> python page_check.py          # page cells vs generated tables, prose vs pins
    BENCH_ENGINE_COMMIT=<pin> python equivalence_check.py   # do the engines of a table agree on the answer

`equivalence_check.py` lands with the 2026-10 instrument, and the October campaign does not start until it exists and every lane records its digests (DECISIONS #88); it has nothing to say about a September row, which carries none.

`structure_check.py` (2026-09-21) is the list counterpart to `prose_check`: where that one asks whether a NUMBER in prose traces to a pinned claim, this asks whether a LIST a document spells out is the list the code holds -- the gates PAGE-SPEC names against `refresh_web_page.GATES`, and the stage chain CAMPAIGN.md draws against `make_october_stages.STAGES`. It is not a publish gate on purpose: a typo in a campaign document does not make the page wrong, and a publish gate that blocks on one only teaches people to switch it off. `make_october_stages.py` runs the chain half itself and warns, because regenerating is exactly when the documented chain goes stale (BUGS F92). Run the whole thing by hand before campaign prep; it is instant and has no known false findings.

`claims_check.py` is a helper library `page_check` imports, not a gate. Running it by hand is still the only thing that checks the claims in PROTOCOL.md section 4. `prose_check.py` and `comparator_pins_check.py` are hand-run too. **Read `comparator_pins_check` output with BUGS F91 in hand**: it maps each backend to "the pypi package whose pin governs it", which is true of an embedded engine and false of a served one, so `neo4j_graph` compares a SERVER version against a DRIVER pin and reports STALE on every run whatever was measured; Qdrant and Milvus agree only while those projects version client and server in lockstep. Its map is 14 entries against 69 backends, and `pg_age_e2` is not one of them -- so it would not have caught the defect that motivated looking at it (F76). What guards that now is `version_pin_check --runtime`, which reads the versions back out of the built images before cell 1 rather than after the campaign.

Publishing to humem.ai is one command; PUBLISHING.md says which one and why it is a command rather than a checklist.
