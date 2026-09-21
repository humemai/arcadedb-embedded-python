# Running a campaign

## The routine, end to end

Two loops, one inside the other. This is the whole procedure in order; each step names where its detail lives, and nothing below contradicts it.

Per campaign, once:

1. Settle the instrument before any cell runs: the query set, the measurement set, the durability rule, the fairness invariants, and the answer checking. A change mid-campaign splits the rows, so this is the only free moment (DECISIONS #82d, #88, #89, #90; PROTOCOL.md). The method pages in the package documentation (`bindings/python/docs/benchmarks/`) describe the same instrument without numbers, so they change in this step too, never later.
2. Smoke every adapter, one cell per engine per lane, and keep the evidence table (section 2 below). Smoke wherever a machine is free: nothing in the fairness contract touches a smoke, and the bench host is reserved only while a published cell runs, so a smoke on the real corpora there is both faster and a better test than a capped slice on the laptop. One runner per host, always: `runner.py` sweeps every `dbbench=1` container on the machine at startup, so a second invocation from another checkout silently destroys the first's cell (BUGS F58).
3. Pin ArcadeDB: sync upstream to the release the campaign runs and build the wheel by the routine in `bindings/python/docs/development/upstream-pr.md`, run our Java reproductions on the built engine to confirm every fix it should carry is intact, and record the engine commit inside that wheel as the campaign's pin (the pin is the commit, not the version string, DECISIONS #49). The served arm's matched pair is built from the same image by `build_matched_pair.sh` (HANDOFF.md). One wheel, one pin, held start to finish.
4. Re-pin every comparator to its latest stable release, smoking the risky jumps on their own (COMPARATORS.md, DECISIONS #87).
5. Publish a skeleton to the preview route from laptop data, so the page's shape can be reviewed before the numbers exist (DECISIONS #86, PUBLISHING.md). The skeleton is written from nothing: its tables and the sentences under them are generated from the rows, and its prose describes the instrument only. Nothing is copied from the previous page, because a sentence that was true on last campaign's rows is the one that goes stale unnoticed (DECISIONS #102, PAGE-SPEC.md "What the October page may say").
6. Run the campaign, landing each stage to the preview rather than to the live page (section 6 below).
7. Regenerate the query budgets from the campaign's own rows (`python3 derive_budgets.py > budgets.py`) so the next campaign's caps are measurements at the corpora it will run rather than projections, and commit the table with the freeze (DECISIONS #106).
8. Freeze, run every gate including the manifest coverage check, and publish the results asset (`publish_results_asset.py`, PUBLISHING.md). Only now is interpretation written, which engine moves between passes, which benefit is uneven, what a ratio says: once, from the frozen rows, each sentence with a pin, so a later re-measure that changes the number fails the publish instead of leaving a sentence that used to be true.
9. Switch: copy the preview payload, images, and prose over the live ones in one commit, and delete the preview route (`campaign_switch_check.py`, PUBLISHING.md).
10. Prune what the campaign made obsolete: superseded decisions, bugs that retired with it, retired markers, any withheld cell whose upstream issue has closed, and the previous page's typed sentences in the exporter, which are deleted rather than kept for a page that no longer exists (step 4 of the switch check).
11. Re-read every document the pruning touched, then rebuild both sites, the project page and the package documentation, and check the links between them resolve in both directions (`uv run mkdocs build --strict -f bindings/python/mkdocs.yml` from the repository root).

Per stage, repeated inside step 6:

1. Write the queue script, lint it with `queue_lint.py`, and chain it behind the previous one (section 5 below).
2. Let it run. The session watches STATUS.txt and docker; investigate any failure before recording it, because a recorded failure is a published claim.
3. Land it with `land_stage.py`: pull the rows, exclude the backends still running, merge, run the gates, read the table diff, then apply, which commits the data and publishes the page. `--exclude-backends` matches by prefix, so a family name catches its served twin (`surrealdb_dense` also drops `surrealdb_dense_server`); when the next stage re-runs one arm of a family, exclude by time instead, `--exclude-since` set to the finished stage's ALL-DONE timestamp, and read the `dropped` line the script prints before applying. The script refuses LANDED unless the bindings commit moved HEAD and the push reached origin (a pre-commit hook that rewrites a staged file aborts the commit; the script retries once).
4. Regenerate anything derived from the rows that changed, such as the bottleneck memo. Do not write interpretation of the new rows on the page; that waits for the freeze (step 6 above).


How a full re-measure is executed on mini. `PROTOCOL.md` holds the rules a row must satisfy; this file holds the procedure that produces the rows. If the two disagree, PROTOCOL wins and this file is wrong.

## 1. The shape: parallel where nothing is measured, serial where it is

**Phase A, parallel.** Image builds, corpus generation and conversion, ground-truth computation, checksums, dataset staging. None of it produces a published number, none of it is timed, and it is the only place concurrency is free. Run it as wide as the box allows.

**Phase B, serial.** The measured cell, whole and undivided: build, settle, query, close. One at a time, full cpuset `0-11`, nothing else on the machine. This is `PROTOCOL.md` section 2.

### Why Phase B is not parallel

The idle is real: a running cell burns 1.37 CPU-seconds per wall second on a 12-thread cpuset. Four things stop it from being usable.

1. **Memory binds before CPU does.** mini has 61.3 GiB. Peak memory at l3s medium is about 30 GiB per cell, so two of them leave nothing for page cache. `runner.py` already refuses it. The tiers where the time actually goes (l3s medium, l1 medium, l3d deep10m) admit a concurrency of exactly 1.
2. **Residency is worth 9-18x to us and 0-7% to every comparator.** ArcadeDB is lazy; the others are resident from load. There is one page cache on the host, so a neighbour cell touching a different corpus evicts yours, and it moves one column of the table and not the other. Permutation protects a ratio; this is not a level shift applied evenly.
3. **One 24 MiB L3 for the whole package**, shared with the 8 E-cores outside the cpuset, against working sets of 0.2-1.3 GiB. Magnitude unmeasured.
4. **Turbo.** At 1.37 busy cores a cell sits near single-core turbo on a mobile i9-12900HK. A second cell lowers the clock for both rows.

And the prize is small: perfect intra-lane parallelism at current caps saves 10-16% of a pass. Two things save more and cost nothing. Parallelise Phase A, which is free. Then attack the build rather than the concurrency: 86-99% of every expensive cell is `build_s` (deep10m 99%, l3s medium 98%, tpch10 91%) and none of it produces a published latency. Dropping a tier from N=5 to N=3 is larger, auditable, reversible, and disclosed the way PROTOCOL already requires.

### Why the build/query phase split is not adopted

The proposal was to build every cell in parallel, stop the engine, then reopen it for an exclusive serial query pass. Measured on mini at four tiers, N=1: reopening is cheap and flat (8-27 ms against builds of 0.4 s to 93 s) and closing is 28-171 ms, so neither is an obstacle. The split is still **not licensed**, for two reasons.

Every number behind it is N=1, and no tier measured comes close to the ones that dominate the cost (l3s medium is 8.84M docs and about 30 GiB). At the small tiers the reopened pass is 19-29% *faster* than the post-build pass on ArcadeDB against 1-6% on LadybugDB, which is what a lazy engine looks like when the whole corpus sits in a page cache a close does not flush; by l3s small the drift is +2.9% and essentially neutral. A single measurement at a tier whose working set exceeds the page cache decides it. Until then the split stays unadopted, because the failure mode is silent: it would move our own rows and not the comparators', in the direction that flatters us.

The second reason is arithmetic and engine-version dependent. The split closes each cell inside the parallel phase, and before upstream #6490 a dense close was a full second graph build (#6489: a build that leaves any node graph-unreachable merges those orphans into the pending-mutation list, so `graphState` stays MUTABLE and `flush()`, which `close()` calls, rebuilds). At deep10m that is a 24g heap and hours of CPU running beside a neighbour cell. A release carrying #6490 removes that objection but not the N=1 one. `l3d_dense.py` records the mechanism beside its `BENCH_SKIP_CLOSE` switch.

Two findings from the same measurement stand on their own:

- **What a clean close releases is roughly fixed, not proportional**: 30-87 MB at every tier measured, which is 84% of a toy database and 2.0% of a 1.5 GB one. A disk column measured pre-close compares our WAL-inflated state against a comparator's settled one, real and bounded at tens of MB.
- `connect_empty_s` is 0.515-0.575 s against an 8-11 ms reopen: creating a database and issuing DDL costs about 50x what opening a built one does.

## 2. Staging: smoke, then small, then big

Every campaign runs in three stages and does not advance until the previous one is green. A defect found at stage 3 costs a full pass.

1. **Smoke.** Cheapest tier of each lane, N=1. Proves the images, the corpora, the adapters and the recorded schema. Rows go to a scratch results file, not to `runs.jsonl`.
2. **Small.** One tier up, N=5, real corpora, every metric recorded. This is where the gates run for the first time: `provenance_check`, `fairness_check`, `page_check`, and `equivalence_check`.
3. **Big.** The published tiers.

A stage that produces rows no gate admits has failed even if every cell exited 0.

## 3. What every cell records

Beyond the lane's own metrics:

- **Memory.** `peak_anon_mib_sum`, `peak_shmem_mib_sum`, `peak_owned_mib_sum` (anon + shmem), summed across every container in the cell. Anon alone misses a POSIX-shmem buffer pool entirely.
- **Disk.** `SizeRw` plus `du` over the daemon-reported volume mounts, with a settle loop requiring two readings within 1%. A volume in an image with no `du` is sized from a helper container (BUGS.md F38).
- **IO.** Cumulative `rbytes`/`wbytes` from `io.stat`.
- **Phases.** `build_s`, settle, query generation, ground-truth load, search wall, recall computation, and `phases_accounted_s` so unexplained time is visible rather than absorbed. The dense and sparse lanes also split `ingest_s` from `index_s` where the engine has the boundary. Every lane prints `PHASE` markers as it goes, so a cell killed by its timeout still says which phase it was in.
- **Cold and warm**, separately: the first iteration after the database is opened is the cold number and the remaining iterations are the warm one, on every timed query from the 2026-10 instrument (DECISIONS #89). A lane where the split does not apply says so instead of leaving a blank.
- **Envelope.** cpuset, memory cap, heap, observed server heap and page cache, `mem_split`, image digest, engine version, engine commit.
- **Thermal.** `host_temp_c_start` and `_end` from the package sensor, `host_throttle_count_start` and `_end` and `host_throttled_ms` from the kernel, on every row since the queue scripts pulled the fix on 2026-09-14 (BUGS.md F45). mini bounces off its thermal ceiling under a long build while the busy cores hold 4.3 GHz, so the power mode stays as the machine ships and each row carries the temperature and the counters as evidence; no protocol change follows.
- **Instrument.** `instrument`, `bench_host`, the per-engine `durability` string read out of the engine, and the canonical answer digest with its readable sample for every deterministic query (PROTOCOL.md section 2).

## 4. Heap and memory caps

**One cap per tier, identical for every engine.** A cap is a ceiling rather than a reservation, so an engine that needs less is unaffected by a tier whose cap is generous. A per-backend cap would be the unfairness the caps exist to prevent.

**One heap per tier, identical for every JVM engine.** ArcadeDB embedded, ArcadeDB server, Neo4j and Elasticsearch all receive the same `{heap}` from one table (`-Xmx`, `NEO4J_server_memory_heap_max__size`, `ES_JAVA_OPTS` respectively). Non-JVM comparators have no equivalent knob, which is why heap sizing is a documented resource-fitting override rather than a per-engine advantage.

**heap = 0.50 x cap, and deep10m is the one exception at 0.67** (24g in 36g). The runner prints this table at startup and marks any deviation.

0.50 is a deliberate split between heap and page cache, not a default nobody revisited. At every tier except deep10m, `peak_anon` sits BELOW the committed heap (4g heap against 2.7 GiB touched at tiny; 8g against 6.1-6.5 GiB at small), so the JVM never needed the heap it already had and raising the ratio would change nothing measurable. The other half of the cap is not idle: it holds the OS page cache for the engine's own files, which the cold/warm split prices at 9-18x for ArcadeDB against 1.0x for engines resident from load.

deep10m sits at 0.67 because a single fp32 dense build peaks well above the 18g that 0.50 would give. The answer was deliberately NOT to grow the envelope until the engine's own build-cache default fitted: no comparator caches its corpus during an index build, so accepting that default means ArcadeDB takes GiB that Qdrant, Milvus, Chroma and LanceDB do not, and then the envelope grows so that it fits, room only one engine gets. The campaign runs the engine's default cache and the tier keeps the 36g/24g envelope it has always had (DECISIONS #52; #56 pins the fp32 multipass arms to the corpus and is disclosed as an override in PROTOCOL.md section 7). The cache policy is recorded on every row as `graph_build_cache_size` and `graph_build_cache_policy`.

## 5. Launching

```sh
bash build_images.sh                 # Phase A; refuses a pre-release pin
source campaign_env.sh               # the BENCH_* dataset switches (the October queue scripts source it; the September scripts set them inline)
campaign_env_check                   # asserts every corpus is present
python3 -u runner.py --lanes ... --scale ... --reps 5
```

**The write workloads run twice, once per durability class (DECISIONS #90).**
The class is a property of the cell, not a second measurement inside one, so a
queue script asks for the same cell twice:

```sh
python3 -u runner.py --lanes l1tpc --workloads oltp --scale tpch1 --reps 5                      # relaxed
python3 -u runner.py --lanes l1tpc --workloads oltp --scale tpch1 --reps 5 --durability strict  # strict
```

The same pair for `--lanes l2 --workloads oltp` and `--lanes e2 --workloads
hybrid`. Everything else -- every read workload, every analytics workload, both
vector lanes' ingests, and the lifecycle lane -- runs once, at the relaxed
default. The strict cell writes its own `run_id` (a `_dstrict` suffix), its own
raw artifact, and its own canonical key, so the two never shadow each other;
`fairness_check` F10b fails a write cell that exists in only one class, and the
four engines with no knob (Neo4j, DuckDB, LadybugDB, the SurrealDB 3.2.4
server) are exempt because they run once and declare it.

Rules that have each cost a run:

- Never sync the repo mid-campaign. A `git checkout` reverted a tracked `runs.jsonl` and lost rows; a mid-campaign merge split one lane's rows across two schemas. Sync between stages, never inside one.
- Archive `runs.jsonl` before anything that could touch it.
- Wait loops read the **last** marker line. `STATUS.txt` is append-only, so a bare grep finds this morning's ABORT and acts on it.
- Kill the process group, not the script: `kill -- -PGID`, then verify with `docker ps` and `pgrep`.
- Never edit a queue script that is running. Bash reads by byte offset, so a mid-run edit resumes mid-token.
- Monitoring is the session's own watch on `STATUS.txt` and `docker ps` on the bench host. There are no monitoring scripts.

## 5a. The laptop skeleton (DECISIONS #86)

The whole instrument, on the development laptop, at the smallest size each lane runs, one repetition, both durability classes on the writes, into its own results file, published to the preview route as placeholders so the October page's shape can be read and edited before mini measures anything. It is not a campaign: every row it produces is refused by a live publish, and nothing it produces is merged into `runs.jsonl`.

```sh
export BENCH_ALLOW_DEV=1 BENCH_DATA="$HOME/bench-data" BENCH_HOST=laptop BENCH_CPUSET=0-11
export BENCH_TPC_SF=0.01                      # the laptop corpus is SF0.01, not the campaign's SF1
export BENCH_ARCADEDB_NO_COMPACT_HEADERS=1    # see below
# no BENCH_GRAPH_SOURCE and no BENCH_SPARSE_SOURCE: neither LDBC-SNB nor the
# Big-ANN corpus is staged here, so both lanes run their own micro generators
python3 -u runner.py --lanes <lane> --workloads <wl> --scale <micro|e2|ts100|lc10k> \
    --reps 1 --tier sweep --workers 1 --results-file runs_skeleton_laptop.jsonl
```

One stage per (lane, workload), and the write workloads twice, once with `--durability strict`, exactly as the campaign does: `l1tpc` oltp x2 and olap, `l2` oltp x2 and olap, `e2` hybrid x2 and atomicity, `l3d`, `l3s`, `l4`, `lifecycle`. Then:

```sh
BENCH_RUNS_JSONL=runs_skeleton_laptop.jsonl \
    python3 refresh_web_page.py --skeleton --site <humem.ai checkout>
```

Four things the first two attempts got wrong, each of which cost a stage:

- **`--workers 1`, not the sweep tier's default of 2.** At two workers every row records the shard it ran on (`0-5` or `6-11`) instead of the cpuset, so the page's setup paragraph has two cpusets to choose between, and the lifecycle lane times an open and a close beside a neighbour cell.
- **`BENCH_ARCADEDB_NO_COMPACT_HEADERS=1`.** The served arms here run the stock published image, whose JDK 21 answers `Unrecognized VM option 'UseCompactObjectHeaders'` and refuses to boot. Every ArcadeDB server cell died on it. The flag is settable only on the matched pair, which the laptop does not build.
- **Ground truth for the sparse lane.** `l3_sparse.py` on the synthetic generator ships none, `recall_at_10` is then null, and `load_canonical` drops every such row before the page sees it, so the sparse table silently does not exist. Generate it once with `gen_sparse_gt.py --scale micro` and copy the `gt.npy` to `$BENCH_DATA/sparse/micro/`.
- **`BENCH_RUNS_JSONL` on the publish.** The freeze, the exporter and the atomicity check all read it; without it they read `runs.jsonl`, which on a laptop is either absent or somebody else's rows.


## 6. The live chain

The September chain on mini, each script waiting on its predecessor and gated on `verify_pair_c25.sh`, at pin `8d6af9475`:

`qDO` -> `qDP` -> `qDQ` -> `qDR` -> `qDS` -> `qDT` -> `qDU` -> `qDV` -> `qDW` -> `qDX`. Complete: qDX ended 2026-09-18 02:20Z and every stage has landed.

| script | what it runs |
|---|---|
| qDO | SurrealDB on the single-model tables: documents (TPC), graph, and dense, embedded and served |
| qDP | the sparse second pass at 100k, the one tier whose warm columns were blank |
| qDQ | the embedded native time-series arm again, after BUGS.md F33 |
| qDR | SQLite on the time-series lane again, at four-decimal latencies |
| qDS | pgvector again, after BUGS.md F34: dense and sparse, lane and multipass |
| qDT | the composed Qdrant + Neo4j cross-model arm |
| qDU | SurrealDB embedded on the TPC tables again, after BUGS.md F37 |
| qDV | ArangoDB 3.12.11, served only, on documents, graph, dense, and cross-model (DECISIONS #78) |
| qDW | SurrealDB served again on the cells whose disk reading was blank (BUGS.md F38) |
| qDX | one phase-marked re-run of the embedded SurrealDB 1M dense cell. It timed out again at four hours, which was the point: the record gained the phase, `build-running`, the index build (BUGS.md F41) |

Finished scripts move to `~/queue_archive` on mini. The chain holds its pin start to finish; an upstream fix landing mid-run becomes a candidate for the next re-pin, never a restart.

**The September extension (DECISIONS #103a to #103e), after qDX, same pin, same instrument.** Installed as `qEA` to `qEE` on 2026-09-18. It ran two stages and was then stopped; the three that did not run are cancelled, and their raises happen in October instead. `qDY` is not part of it: it is the one-cell BUGS F55 diagnostic for ArangoDB's IVF at deep10m.

| script | what it runs | outcome |
|---|---|---|
| qEA | documents analytics at TPC-H SF10 (`tpch10`), every engine, olap only; the ArcadeDB arms opt in with `WITH_ARCADEDB_OLAP=1`, since their September Q1/Q6 text is the one BUGS F42/F43 withdrew | ran 2026-09-18 04:42Z to 16:52Z; DuckDB and both PostgreSQL arms measured, ArangoDB, MongoDB and SQLite censored at the tier's cap, SurrealDB served failed inside its budget on a closed connection, SurrealDB embedded killed by the kernel at the tier's memory envelope. The tier did not switch; see below |
| qEB | graph analytics on the full SF1 network (`sf1full`), every engine, the olap workload only, with and without the view for ArcadeDB; then Memgraph, FalkorDB and DuckPGQ on the interactive table at SF1 and SF10 | ran 2026-09-18 17:47Z to 2026-09-19 00:00Z. The three new engines LANDED on the interactive table at both sizes. On the analytics table SurrealDB embedded was killed by the kernel at the tier's memory envelope, so that tier did not switch either |
| qEC | time series at 1,000 hosts (`ts1000`) | **cancelled**, moved to October |
| qED | cross-model at 500k products (`e2_500k`) | **cancelled**, moved to October |
| qEE | DuckDB re-measured at 1.5.4 on its September tiers | **cancelled**, moved to October. Consequence on the live page: DuckPGQ landed at DuckDB 1.5.4 while the documents, time-series and dense-VSS arms still read 1.5.5, so September carries two DuckDB versions until October re-measures them (COMPARATORS.md) |

A raised size replaced a tier under #103b: the page table switched to the new tier only when every engine on it had landed there (`make_paper_tables.PAPER_SCALES` and, for graph analytics, `export_web` `l2olap` `only_scales`). Neither raise met that bar, so `docs_olap` still prints TPC-H SF1 and `l2olap` still prints the SF1 and SF10 projections. **That rule is retired for October by #108**: a table carries two sizes, the large one is a row group rather than a replacement, and an engine absent from it is a declared outcome (#103g) rather than a reason to withhold the engines that did measure. Those rows do NOT carry over: this extension measured them at September's pin, and rule 3 of PAGE-SPEC gives one engine commit per table, so October re-measures every one of them at October's pin. What #108 changes is that October's large sizes publish whatever engines reach them, instead of the whole size waiting on the slowest. What the reader sees of the attempt is outcome accounting: the exporter reads every failed cell out of `runs.jsonl` and writes a note naming the engine, the raised size, and what it reported, under a table whose rows are still the old size (READING-RESULTS.md, "an outcome note may name a size the table does not print").

**Sizes, every campaign (#108).** Each table carries two sizes wherever a second one is affordable and informative: graph interactive SF1 and SF10, documents transactional and analytical TPC-H SF1 and SF10, time series 100 and 1,000 hosts, cross-model 50k and 500k products, dense 1M and 9.99M, sparse 100k / 1M / 8.84M. Graph analytics is the single exception at one size, the full SF1 network, because the full network at SF10 is not feasible. Plan the matrix at two sizes from the start; if it does not fit, the transactional documents table's SF10 is the first size to drop, and dropping it is recorded rather than done silently.

**qOB (graph analytics) was STOPPED 2026-09-19 14:52Z and is re-queued.** Its first cell -- our own embedded arm --
was censored at the 7,200 s cap, and projecting every engine's skeleton numbers through the measured 98x
slice-to-full-network blow-up said most of the other ten would follow: ~20 h for a near-empty table. Stopped rather
than run, on the user's standing rule that tail runs must not dominate. `lsqb_q6` and `lsqb_q9` are now excluded at
`sf1full` (#109), which brings eight of eleven engines inside the cap; the other three are censored with the cap
named. The five stages after it were released to run in the meantime, since none depends on the analytics question.

**qOB (graph analytics) was STOPPED 2026-09-19 14:52Z and is re-queued.** Its first cell -- our own embedded arm -- was censored at the 7,200 s cap, and projecting every engine's skeleton numbers through the measured 98x slice-to-full-network blow-up said most of the other ten would follow: about 20 h for a near-empty table. Stopped rather than run, on the standing rule that tail runs must not dominate. `lsqb_q6` and `lsqb_q9` are now excluded at `sf1full` (#109), which brings eight of eleven engines inside the cap; the other three are censored with the cap named. The five stages after it were released to run meanwhile, since none depends on the analytics question.

**THE OCTOBER CAMPAIGN STARTED 2026-09-19 05:17Z** with `qOA`, and `qOB` to `qOH` are queued behind it,
each waiting on its predecessor's `ALL-DONE` marker. Generated by `make_october_stages.py`; installed in the
bench host's home, not the repo. The pair was built first from upstream's published snapshot
`arcadedata/arcadedb@sha256:ccb0ad1f6e...`, whose jars read `buildNumber 417314c18da782620463bc7c09ac6bd34ac6fbda`
(read out of the image, not taken from a plan), giving `arcadedb-c25:417314c18` and a 26.10.1.dev0 wheel over the
same 86 jars. The September wheel was deleted at that point rather than left beside it.

The first stage's preflight is the record of what "ready" means here: it rebuilt `dbbench:arcadedb` with the
pinned wheel, read the version back OUT of the rebuilt image, and only then ran the pair check, which reported
`jars=image+wheel+embedded-image` where the same check reported `jars=both` an hour earlier and was wrong. The
first rows confirm it end to end: `instrument 2026-10`, `engine_commit 417314c18`, and BOTH ArcadeDB arms on one
engine line (embedded `26.10.1.dev0`, served `server:26.10.1-SNAPSHOT (build 417314c18...)`), which is the
defect of BUGS F69 verified fixed on real data rather than in principle.

**`qCAL`, the calibration pass, finished 2026-09-19 03:11Z.** Time series at 1,000 hosts, one repetition per engine, written to `results/runs_CALIBRATION_ts1000_<pin>.jsonl`, which `merge_campaign.py` never reads and which published nothing. Eight of nine engines left a row; the served native time-series arm was refused by the #88 shape guard, which is under diagnosis. Its output is `budgets.py` at 17 measured entries (DECISIONS #106). Two entries were WITHHELD rather than generated, and the rule that withheld them is now part of the generator: an entry whose engine count is under half the widest roster answering that query anywhere is survivorship, not a budget. At TPC-H SF10 only three engines of ten left a row, and their median would have handed a ten-times-larger corpus a four-times-SMALLER budget than SF1's, then censored every engine outside the set it was derived from. The lane's constant applies there until October's instrument can censor per query and still leave a p50 behind.

**The October chain on mini, at pin `417314c18`.** Fifteen stages generated by `make_october_stages.py` from one table, each waiting on its predecessor's `<id> ALL-DONE` marker in `~/STATUS.txt`:

`qOA` -> `qOA2` -> `qOB` -> `qOC` -> `qOD` -> `qOI` -> `qOD2` -> `qOA3` -> `qOD3` -> `qOA4` -> `qOE` -> `qOF` -> `qOG` -> `qOH` -> `qOB2`.

`qOAR` ran between `qOA` and `qOA2` and is not in that list because it was made by hand rather than generated. **Read this order off `make_october_stages.STAGES`, not off this sentence:** the prose here stated `qOD2` before `qOI` and omitted `qOA4` until 2026-09-21, while the generator and the eleven scripts actually running on mini both had `qOD -> qOI -> qOD2`. The difference is not cosmetic -- `qOI` is the only producer of the `e4` table (F84), so where it sits decides when the first landing becomes possible.

**Every page table needs a stage that produces it, and E4 did not have one.** The live page carries the deployment decomposition and `export_web` refuses to build a page without `e4decomp_<pin>`, but no October stage ran the `e4` lane and no archived script ever had -- September's artifact was made by hand. `qOI` is that stage. Before a campaign, walk the payload's table list and name the stage that feeds each one (BUGS F84).

**Every stage checks that its images carry their pins before it runs (BUGS F90, F76).** The build step and the existence check that follows it both passed for nine days while `dbbench:pg-age` sat on PostgreSQL 17.11 under an instrument pinned to 18.6: "images present" is true of an image built a week before the pin moved. It was not a labelling problem. AGE 1.8.0 builds edges about 65x faster than 1.7.0, so the cross-model cell at `e2_500k` spent its entire 7,200 s cap on edge creation, never reached the HNSW build, and was recorded as a censoring that reads like an engine limit. The ArcadeDB arm has been verified by content since August -- `verify_pair_c25.sh` reads the jar's own build number -- and `version_pin_check --runtime` now gives every comparator the same treatment, running each `dbbench:*` image and reading its versions back out before cell 1. An image that is absent, or that cannot state its versions, is a failure and not a pass; pins it cannot resolve (`PKGS[arcadedb]` is a shell variable) are reported rather than skipped silently.

**Every stage checks that its whole cell fits before it runs (BUGS F74, #109).** The budget sum above bounds what ITERATIONS may cost; it cannot see a query's FIRST TOUCH, which #82b makes always complete. That is the gap that censored October's first analytics cell at its 7,200 s cap while its budgets summed to 48% of it, because one query spent 1,384 s on its first touch alone. Each stage now runs `cell_cost_check` for every tier it will use -- ingest plus measured first touches plus the budget ceiling, against the cap -- and aborts only on a SCORED projection over the cap. A tier whose query roster has no rows yet is reported and not blocked, because the tool refuses to score what it cannot see rather than guessing (it once scored 5 of 14 queries and reported ok).

**Every stage with a timed write runs it twice, once at each durability class (#90, FAIRNESS F10b).** `make_october_stages.STRICT_WORKLOADS` names the four (lane, workload) pairs that get the second pass: documents and graph `oltp`, cross-model `hybrid` and `atomicity`. Reads are untouched and bulk ingest stays at one setting (#90a). THE CLASS IS A CLI FLAG, NOT AN ENVIRONMENT VARIABLE: `runner.py` assigns `os.environ["BENCH_DURABILITY"]` from `--durability`, default `relaxed`, so exporting the variable is overwritten before any lane reads it and the cell runs relaxed while claiming nothing (BUGS F81). qOA3 and qOD3 add the pass for the two stages that ran before this landed; they are queued early because fairness_check F10 blocks the landing of the tables they feed.

**A repair runs after the stage it repairs.** qOD2 was first queued at the tail, behind five stages and roughly two weeks of bench time, which would have left the cross-model table unlandable for all of it -- its MongoDB arm has no rows and its PostgreSQL+AGE arm has ten at the wrong engine version. Placing it directly after qOD costs qOE two to three hours and makes the table landable the same day. It also matches the ordering rule the stage table already follows: the campaign is sequenced by uncertainty, and an arm known to be broken is the most certain thing on the board to fix.

The repairs in that line are `qOA2` (DuckPGQ, after a duplicate class shadowed the working one, BUGS F73), `qOB2` (graph analytics re-run under #109's tier exclusions) and `qOD2` (the two cross-model arms that ran against images nobody was rebuilding, BUGS F76). A repair is a new stage at the tail, never an edit to a running one: bash reads a script by byte offset, so a mid-run edit resumes mid-token, and a stage waiting in its marker loop can be replaced only by killing its process group and relaunching it.

**A stage builds the images its backends name (#110).** `_images_for()` reads `image` and `server_image` off each backend in `runner.BACKENDS`, so a new arm brings its image with it; the stage then verifies each one exists before the first cell. The typed list this replaced had gone stale in three places at once -- `dbbench:mongo-search` never built, `pg-age` and `dense` predating the re-pin -- and none of the three announced itself as a missing image. MongoDB's arm reported `server_not_ready`, which reads like a slow engine.

## 7. October: the skeleton, then the comparators, then one switch

October's campaign is DECISIONS #74 as amended through #108, and it starts with the comparator re-pin survey. The instrument is final before the first October cell: the forty-operation query set (PROTOCOL.md section 2), the matched durability class (FAIRNESS.md F10), the answer digests (F12), the ingest and index timers, and `bench_host` on every row. Rows measured under two instruments cannot share a table, so the preparation happens while the September chain is still running and the user's go turns into cells the same day (DECISIONS #84).

**Skeleton first, on the laptop.** Once the instrument branch is verified arm by arm, the whole of it runs on the laptop at micro and sweep scales, one repetition, every lane and every backend, into its own results file, and publishes to the preview route as the October page's shape: every table, every column, every condition, and every prose slot, with placeholder numbers, weeks before mini measures anything (DECISIONS #86). `refresh_web_page.py --skeleton` implies `--preview`, refuses any row from the bench host or at paper tier, stamps the payload and every table's conditions as placeholders, waives F1 and F3 by name in the payload because both describe the bench host, and runs every other gate exactly as October will. A live publish refuses a payload stamped skeleton. Nothing from the skeleton is merged into the campaign's results, and the first real stage overwrites the preview payload.

**Comparators next, before 26.10.1 ships.** On the user's go, every comparator is checked against its own release feed, re-pinned where it moved, and smoked where the jump needs it (COMPARATORS.md, October re-pins), and the comparator stages run first. When the user reports 26.10.1, the pair is built and verified and every ArcadeDB arm is queued behind the running comparator stages (DECISIONS #84).

**ONE LINE OF DEVELOPMENT, and this is why.** The instrument is developed on `main`. Between 2026-09-14 and 2026-09-19 it was developed on two branches at once, and on 2026-09-19 neither could run the campaign: `october-instrument` had the per-query budgets, the abandonment rule and the expanded query sets but none of the raised tiers in `TIMEOUT_BY_SCALE`; `main` had the raised tiers, the publish verification and the coverage rules but no budget mechanism at all. Each half looked finished from inside itself. Assembling them took a 23-file, ~75-hunk merge that had to be redone three times as `main` moved underneath it, and the merge itself introduced two duplicate dict keys and a duplicate module-level binding that silently killed four declarations (BUGS F65).

A long-lived branch is what made "the instrument is ready" true of two trees and false of both. `october-instrument` is fully merged as of `631450fb3f` (0 commits outside `main`; its tip was `3bc6a353c5`) and is to be deleted rather than kept. If a change genuinely cannot land on `main`, it is small enough to land behind a flag or it waits.

**The stage order and what it costs, measured rather than planned.** From mini's own STATUS.txt, 3,202 timed cells, plus the query uplift October adds (graph analytics fourteen columns against five, documents five OLAP queries against two, time series six against three). The one PROJECTION is cross-model at 500k, which has never run and is taken at ten times the 50k tier; every other figure is measured.

| stage | table | sizes | hours | cumulative |
|---|---|---|---|---|
| qOA | graph interactive | SF1 + SF10 | ~7.8 (was 17.9, see below) | 0.3 d |
| qOB | graph analytics | full SF1 | 18.8 | 1.5 d |
| qOC | time series | 100 + 1,000 hosts | 18.0 | 2.3 d |
| qOD | cross-model | 50k + 500k | 20.7 | 3.1 d |
| qOE | documents, both tables | SF1 + SF10 | 103.1 | 7.4 d |
| qOF | sparse vector | three sizes | 31.2 | 8.7 d |
| qOG | lifecycle | four sizes | 15.9 | 9.4 d |
| qOH | dense vector | 1M + 9.99M | 122.3 | 14.5 d |

**The uplift factors above were ASSUMPTIONS, and the first stage measured one of them.** I gave graph
interactive a 1.0x uplift on the reasoning that October adds analytics queries rather than interactive ones.
That is wrong: October's interactive workload measures SEVEN operations where September measured four, adding a
three-hop traversal, an update and a delete. Measured per arm on `sf1`, October against September:

| arm | September | October | x |
|---|---|---|---|
| ArcadeDB (embedded) | 6.2 s | 29.0 s | 4.7 |
| ArcadeDB (server) | 26.2 s | 52.8 s | 2.0 |
| LadybugDB | 7.7 s | 44.3 s | 5.8 |
| Neo4j | 34.4 s | 64.6 s | 1.9 |
| SurrealDB (embedded) | 48.0 s | 747.5 s | 15.6 |

**It is not a regression, checked before recording it as one.** The per-operation latencies are September's to
within noise (point 0.044 against 0.044 ms, hop1 0.751 against 0.699, hop2 15.266 against 15.126); the cell is
longer because it measures more. SurrealDB's 15.6x is the new three-hop traversal on the engine that was already
slowest at two hops, at ~184 ms cold per operation.

The qOA row above was ALSO wrong in composition, in the other direction: its 17.9 h came from September cells
that included the `olap` arms, which qOA does not run -- those are qOB's, at `sf1full`. So qOA is oltp only,
about 7.8 h with the measured uplift applied, and the two errors partly cancelled. Every other stage's uplift in
this table is still an assumption, and each will be corrected the same way as its stage measures it.

The order is by UNCERTAINTY, not by size. qOD runs fourth because 500k products has never been measured and its figure is the only projection on the board: if it is wrong, it is wrong on day three rather than day thirteen. qOC runs third because its large size is the one an open diagnosis can block, and a stage that cannot run should discover that early. The three long stages are back-loaded because each is well characterised and none can teach us anything that changes the plan.

Dense last is deliberate. It is 35% of the campaign alone, and the page is otherwise complete at day 8.4; a table may publish at the previous pin with a generated sentence naming what it was measured at, which disappears when the pinned artifact arrives (BUGS F17). The one designated trim, documents transactional at SF10 (#108), brings the whole campaign to 13.5 days.

**What the budgets do and do not bound.** The per-query budgets (#106) cover graph, documents, and time series, which is 45% of the campaign. Dense, sparse, and lifecycle have no budget mechanism and are 49%. Dense is the wrong SHAPE for a query budget in any case: about four fifths of a dense cell is the index build, and #106 budgets queries. At `deep10m` the only thing bounding it is the whole-cell cap, which at 8 h against a healthy 40-62 min build bounds a hang rather than a tail.

And within the three lanes that DO have budgets, most of October's queries will run on the lane's flat constant rather than a measured one. Resolved 2026-09-19 against the merged instrument, asking for every (lane, tier, query) the three lanes will actually request: **17 resolve to a measured budget and 47 fall back**, because LSQB's nine and the other queries October adds have never been measured anywhere. That is by design and not a gap to close before launching: the row records which of the two applied, so a projection can never be read as a measurement, and step 7 of the per-campaign list regenerates the table from October's own rows for the campaign after it. The check that matters before launching is that the KEYS match, since a name mismatch would silently fall back on every query: zero entries in `budgets.py` name a (lane, tier, query) no lane asks for.

**Checked before the first cell, 2026-09-19.** Every corpus October needs is already on mini (LDBC SF1 and SF10, TPC-H SF1 and SF10, TSBS 100 and 1,000 hosts, deep10m, bigann, dense), so no generation time is hidden in the figures above; cross-model needs no corpus file, as `e2_hybrid` generates its catalogue from a fixed seed. The `e2_500k` tier is wired: `PRODUCTS` reads an env var the runner does NOT forward, which is the shape of several past latent-knob defects, but `runner.py` passes `--scale` to every lane and `e2_hybrid.main()` sets the size from it, recording `n_products` on the row so a mismatch is visible rather than silent.

**One switch at the end.** The live page stays on the September freeze at pin `8d6af9475`, untouched, for the whole campaign; October rows accumulate in their own per-pin file and land table by table on the preview route through `land_stage.py --preview`; when the freeze is complete and every gate is green, one commit copies the preview payload, images, and prose over the live ones and deletes the route (DECISIONS #83). The new columns have no September counterpart, so a partial landing on the live page would seat them beside old rows and the gates would refuse it. The route and the flag are exercised on real October stages, not written on switch day.
