# The fairness contract

Every number on the page compares systems. A comparison is only worth printing if both sides were given the same thing. This file says what "the same thing" means, what is allowed to differ, and what is checked mechanically rather than remembered.

`fairness_check.py` is one of the gates `refresh_web_page.py` runs (`equivalence_check`, `provenance_check`, `fairness_check`, `page_check`, `version_consistency_check`, `version_pin_check`). It fails loudly rather than warning quietly.

The failure mode this contract exists to close is **a correct number measured under conditions the row beside it did not get**. `claims_check` and `provenance_check` cannot see it: both verify a number against its own artifact, and such a number is correct about its own run.

## Invariants (must hold; checked)

**F1. Same cpuset.** Every container in a published cell gets the full `0-11` (the 12 P-threads on 6 physical P-cores). Client and server topologies share that cpuset deliberately, so CPU competition stays inside the deployment under test rather than being hidden by giving the server its own cores.

**F2. Serial only.** Published cells run one at a time. `runner.py` forces `workers=1` on the paper tier and errors otherwise; queue scripts pass `--tier paper --workers 1` explicitly. The parallel sweep tier (disjoint cpuset shards, shuffled order) exists for exploration and must never reach a table. A published row from a sweep is detectable after the fact as a partial cpuset such as `0-5`, and `load_canonical` drops it.

**F3. Same memory envelope per (lane, scale).** Every backend at a tier gets the same `--memory`/`--memory-swap` cap and, for JVM engines, the same heap. Two JVM processes are exceptions and run at their own default heap: QuestDB, whose rows record the tier heap although no heap reaches its server, and mongot inside the MongoDB Search image (CAMPAIGN.md section 7, row 30). One ArcadeDB arm is a declared exception on purpose (F3b): the served arm at the vendor image's own JVM settings, on the documents transaction workload only (CAMPAIGN.md section 7, row 69). It gets the same memory cap as every other arm and a different heap, collector, and initial heap size, because it is started without the two variables every other served ArcadeDB arm sets; its row records no tier heap, stamps `server_jvm_defaults`, and carries the JVM's own report of what it ran (`server_jvm_*`, read from the process). `fairness_check.JVM_DEFAULTS_ARMS` names it and what it differs in, the gate fails a `jvm_defaults` arm that is not declared and a declared arm that is not marked, and its rows are held to the JVM's report (a heap of 75% of the cap, generational ZGC, no `-Xms` or `-Xmx` on the command line), so the one arm that runs other settings than its siblings says so and shows it.

A served backend gets the **full tier cap** and the client its own `BENCH_CLIENT_MEM` budget on top, stamped `mem_split="full+client"`, so a served engine sees exactly the cap an embedded engine of the same tier sees. Every frozen served row carries that stamp. `BENCH_SERVER_MEM_FRACTION` restores the older `server = 0.75 * total` split for a reproduction. Compare a served topology by `srv_cap / mem_split`, never by adding client and server: addition reads 1.75x the envelope.

**The edge this rule has on a lane whose DRIVER is memory-hungry, found 2026-09-21.** The rule gives the engine the full cap on both deployments, which is right. But a served cell runs the driver in its OWN container, while an EMBEDDED cell is one process, so on that side the driver competes with the engine for the one cap. It is invisible on most lanes because the driver is small. On `l4` it is not: the lane parses line protocol in Python inside every cell, and at `ts1000` that parser peaked at 7.6 GiB in the served arm's client container. So the embedded engine had roughly 24 GiB of headroom against the served engine's 32, under one stamped `32g` cap. SurrealDB embedded was OOM-killed there and its served arm completed at 27.5 GiB total (BUGS F66). The kill is not explained by this -- that arm was past 24 GiB long before the end -- but any sentence comparing the two deployments' MEMORY on this lane must say which side was carrying the parser, and a claim that one deployment accumulates and the other does not needs more than the two peaks to stand up. **Re-pin (2026-10-03, CAMPAIGN section 7 row 18):** the parsed corpus is now held at about a third of that (89 bytes a point against 281) and freed after ingest, so the parser's share at ts1000 is about 2.2 GiB held until ingest ends, not 7.6 GiB for the whole cell; October's 7.6 GiB stands for the rows measured then, and the 26.10.1 measurement's `ts1000` rows carry the smaller figure.

**"Same heap" means the heap the engine RAN, not the heap the cell asked for.** A row stamps `heap` from the request, so a hardcoded server heap is invisible in the artifact; Elasticsearch ran 4g at three tiers while its comparators scaled 4g, 8g, 16g, stamped `heap=16g` throughout. `observe_server()` closes it by reading the container's real `-Xmx` back out of `docker inspect` into `server_heap` and failing any cell where the two disagree. Rows without that witness are dropped from published tables by `load_canonical`, so a tier shows a gap rather than an unfair number.

The check is honest about its own limit: it reads the container's ENV, which is what we passed in, not the JVM's live heap. It proves the plumbing, not the obedience. The stronger form is to ask the engine (Elasticsearch reports `jvm.mem.heap_max_in_bytes` from `/_nodes/jvm`); it is owed, and CAMPAIGN.md section 7, item 20 carries it.

**A resource raised for one engine obliges a re-measure of every engine at that tier.** This is the sharpest rule here, and the one that has been broken: the dense envelope went 28g/16g to 36g/24g for a legitimate reason and only ArcadeDB was re-measured, which turned a fix into a 29% memory advantage.

Note the scope. The rule is about *resources*. Upgrading one engine's version is not a resource change: the comparators keep the same cpuset, envelope, protocol and degree, so F1 to F8 still hold and their rows may be carried forward under F9.

**F4. Same protocol.** Reps per build, warmup count, settle step and query set are properties of the LANE, not of whoever wrote the driver. If ArcadeDB gets five passes over one build, so does every comparator. If one engine gets a post-ingest settle, all of them do.

*One engine, two versions, two spellings.* The two SurrealDB deployments run different text for the triangle count, because the faster form inverts between their versions: the record-link form is 5.2x faster on the embedded core 2.3.10 and the arrow form is 4.2x faster on the served 3.2.4, both measured, so one shared text would hand whichever arm it suits less a four to five times penalty that measures our spelling rather than either engine (DECISIONS #93). Both texts and both measurements stay in the adapter so the choice is checkable, and the answer digests prove the two forms compute the same number.

**F5. Same engine line within a table.** A row measured on a different release than the row beside it compares versions while appearing to compare configurations.

**F6. Thread pools are fitted to the cpuset, not to the host.** F1 pins the cpuset, which bounds which CPUs a process may run on. It does not bound how many threads the process starts, and several runtimes size their pools from the host core count regardless of the mask. An engine running 20 threads on 12 CPUs pays context switching its 12-thread neighbour does not.

The call that sees the restriction is `sched_getaffinity`. **`os.cpu_count()`, `nproc --all` and `/proc/cpuinfo` report the host and ignore the mask**, so any of them in an adapter is this bug. Plain `nproc` does respect affinity, verified rather than assumed: under `taskset -c 0-11` on a 16-CPU box, `nproc`=12 while `nproc --all`=16 and `/proc/cpuinfo`=16.

Fitting the pool is resource fitting, the first of the four sanctioned override categories, so it is applied rather than merely disclosed.

*Audit, 2026-08-01, seven comparator runtimes:*

| runtime | evidence | verdict |
|---|---|---|
| DuckDB | default `threads`=20 under a 12-CPU cpuset in the real bench image; every lane now sets `PRAGMA threads` from `sched_getaffinity` (l1_tabular first, then l1_tpc, l3d, and l4 on the October instrument, 2026-09-15; the l2 DuckPGQ graph arm carries the same fix, 2026-09-17, and records it as `duckpgq_threads`; the e2 cross-model arm from the 26.10.1 measurement too, as `duckdb_threads`, beside the cgroup-derived `duckdb_memory_limit`) | cpuset |
| Qdrant | `actix-rt` runtime 11 threads, update pool ~11, from `/proc/<pid>/task` | cpuset |
| Elasticsearch | `_nodes/os` reports `available_processors: 12`, `allocated_processors: 12` | cpuset |
| Neo4j | 10 `GC Thread#N`; G1 derives `8 + (N-8)*5/8` above 8, so 12 CPUs gives 10 | cpuset |
| ArcadeDB (JVM) | `availableProcessors()` reads the cgroup on Java 11+ | cpuset |
| Chroma, LanceDB, sqlite-vec | embedded in the driver, no separate server pool. Their Rust runtimes follow the cpuset (laptop, 2026-10-02, after one open: Chroma 1.5.9's `tokio-rt-worker` threads 5 under `--cpuset-cpus 4-7` against 17 with no cpuset on the 16-CPU laptop, LanceDB 0.39.0's `lancedb-tokio` 5 against 17), as do the threads the Python process starts (4 against 16 beside Chroma, 5 against 17 beside LanceDB); SQLite is single-threaded. Their caches are fixed or unbounded, not host-sized | cpuset; the lifecycle arms record the threads the process holds after its first open (`lc_threads_after_open`) |
| Milvus | `go_sched_gomaxprocs_threads 12`; Go sizes from `sched_getaffinity` | cpuset |
| Memgraph 3.13.1 (2026-09-17) | `SHOW CONFIG` under `--cpuset-cpus 0-11` on a 16-CPU laptop: `bolt_num_workers` 16 and `storage_snapshot_thread_count` 16, both documented as "the number of processing units available on the machine"; 51 tasks in `/proc/1/task` at idle. Its memory limit is host-sized the same way (`memory_limit` 0 reported as 30.35 GiB inside an 8g container) | **host**; fitted: runner passes `--bolt-num-workers={ncpu}`, `--storage-snapshot-thread-count={ncpu}` and `--memory-limit` at 90% of the cap, and the adapter reads all three back onto the row (`memgraph_bolt_workers`, `memgraph_snapshot_threads`, `memgraph_memory_limit_mib`; 12, 12, 7372 on the laptop smoke at an 8g cap) The cross-model arm (`memgraph_e2`, from the 26.10.1 measurement) gets the same flags and reads the same settings back. |
| FalkorDB 4.20.6 (2026-09-17; 6.0.1 from 2026-10-02 sizes the query pool from the cpuset, `THREAD_COUNT` 4 under a 4-CPU cpuset, and keeps the explicit setting) | startup log under the same cpuset: "Thread pool created, using 16 threads" and "Maximum number of OpenMP threads set to 12"; `GRAPH.CONFIG GET THREAD_COUNT` 16, `OMP_THREAD_COUNT` 12. The query pool reads the host's logical cores, the GraphBLAS pool reads the affinity mask | **host** for the query pool, cpuset for OpenMP; fitted: runner passes `THREAD_COUNT {ncpu}` in `FALKORDB_ARGS`, the log then reads "using 12 threads" and the adapter records `falkordb_thread_count` and `falkordb_omp_threads` from `GRAPH.CONFIG GET` (12 and 12 on the laptop smoke) |
| LadybugDB 0.20.4 (2026-09-29, BUGS F160) | not audited on 2026-08-01 nor listed as owed; found from LadybugDB/ladybug#1070: `CALL current_setting("threads")` reads the host's CPU count under a cpuset (16 under `--cpuset-cpus 4-7` on the 16-CPU laptop, affinity 4), which is 20 on mini's 12-CPU cells, and the buffer pool defaults to 0.8 of physical RAM, about 49 GB against the 24 GB cell cap. A laptop A/B on the lane's own adapter at 20 against 12 threads put its reads 12-28% slow and its writes 12% fast | **host**; fitted 2026-09-29: the adapter passes `max_num_threads` from `sched_getaffinity` and `buffer_pool_size` at 0.8 of the cgroup `memory.max`, reads the thread count back, and records `ladybug_threads` and `ladybug_buffer_pool_mib` (4 and 3276 in a 4-CPU, 4 GB container); its rows are re-run in the 26.10.1 measurement. The cross-model arm (`ladybug_e2`, from the 26.10.1 measurement) opens through the same fit and records `ladybug_threads` and `ladybug_buffer_pool_mib`. |
| PostgreSQL + AGE 1.8.0 on PostgreSQL 18.6 (2026-10-02, both AGE arms) | `SHOW` under an 8-CPU cpuset and a 16 GiB cap: `max_parallel_workers_per_gather` 2 and `work_mem` 4MB, PostgreSQL's fixed defaults rather than host-sized ones, so not F6's bug as stated; but every other engine's pools reach the cell's cores and cap, and these reach 3 of 12 cores and spill rather than use the cap. Measured on the full SF1 network (`repros/age-dialect/resource_fit_probe.py`): workers fitted to the cpuset made LSQB q2 1.8x faster and q4, q5, q7 1.1-1.25x; `work_mem` fitted from the cap cut temp-file spill from 42 GB to 0.7 GB per analytics pass at no net time cost, with no OOM kill; four times that bought nothing | **fixed default**; fitted: the runner passes `max_parallel_workers_per_gather` and `max_parallel_maintenance_workers` = cpuset - 1, `max_parallel_workers` = cpuset, and `work_mem` = (cap x 0.75) / (cpuset x 16), and the graph adapter reads every one back onto the row (`pg_*`); the cross-model rows carry them in `server_cmd` |
| PostgreSQL 18.6 arms: `postgres_tuned`, `timescaledb`, `pgvector_dense`, `pgvector_sparse`, and the new `postgres_ts` (2026-10-02) | the same fixed defaults as AGE's (2 workers per query, a pool of 8, `work_mem` 4MB; `postgres_tuned` carried a constant 64MB). Same-run A/B on the laptop, defaults against fitted (`BENCH_PG_FIT=off`), answers identical in every pair, no OOM kill: TPC-H Q1 at SF1 on `postgres_tuned` 1.47x faster fitted, Q6 1.13x; the plain-table time series' per-host hourly aggregate 1.35x, its other queries unchanged, and q_last on the same plan either way (EXPLAIN, interleaved in one session); TimescaleDB unchanged within run noise; pgvector dense and sparse search unchanged and recall equal (0.997 and 0.94 both ways), the HNSW build a little faster with more maintenance workers | **fixed default**; fitted with AGE's rule through `runner.PG_FIT_CMD` on every PostgreSQL arm except `postgres`, the defaults arm by design; the time-series arms read every setting back onto the row (`pg_*`), the others carry them in `server_cmd`. `BENCH_PG_FIT=off` exists for the A/B only |

The comparators this audit did not cover (MongoDB, QuestDB, SurrealDB, SQLite, and ArangoDB) are not yet audited, and memory pools have been checked for a host-sized default only where one was found (Memgraph's memory limit and LadybugDB's buffer pool, BUGS F160); CAMPAIGN.md section 7, item 20 carries both.

Two ways to get this audit wrong, both nearly recorded. Total OS thread count is not pool sizing: a JVM server runs dozens of threads irrespective of cpuset, so the question for a JVM is `availableProcessors()` and the named pool settings. And running `nproc` inside a container answers about the container, not about the engine: ask the engine's own metrics.

The DuckDB bias runs **against** DuckDB, which wins that lane regardless, so nothing self-serving rests on it.

**F7. Same effective base-layer degree across dense backends per scale.** Engines spell graph degree differently: one takes the per-layer `maxConnections`, another the base-layer degree, and the same integer therefore builds two different graphs. Recorded per row as `degree_param` plus `degree_family` so the check reads the number in the unit its own engine meant. A row recording no degree FAILS.

*The other construction knob, and why it is NOT matched.* ArcadeDB builds through jvector, which also exposes `neighborOverflowFactor` (engine default 1.2): how far above `maxConnections` a neighbour list may grow during construction before pruning. Raising it to 2.0 cuts graph-unreachable nodes 3.5x at no measurable cost (50k x 128, `maxConnections=32`: 299 orphans at 1.2, 85 at 2.0, build time, peak RSS and recall flat). It stays at the default anyway. Cheap is not the test; "is there a matched value on the other side" is, and there is none, because no hnswlib-family comparator has this knob. Setting it would move our graph alone, in our favour, which is what separates it from the `maxConnections` 32-against-16 correction: that one converts units between two engines that mean different things by the same integer. Recorded as DECISIONS.md #45.

*An index with no degree is matched by effect.* ArangoDB's vector index is FAISS IVF (inverted lists over trained centroids), so F7's degree has no counterpart and a nominal match is impossible. Its operating point is chosen to land on the same recall instead: `nLists` is FAISS's own guideline for 1M to 10M vectors, `round(4*sqrt(n))`; `nProbe` is calibrated inside the cell, after the index is built and before any timed pass, by binary search on a held-out slice (fixture queries 1000:1200 with their ground truth; both fixtures ship 10,000 and the lane times the first 1,000, so the timed pass never sees them and the cold pass stays cold) for the smallest value whose recall@10 reaches the target; and the target is read from the frozen CSV, the median recall@10 of ArcadeDB's own embedded fp32 arm at the same scale. Matching our own arm is the neutral choice: a higher target slows them and flatters us, a lower one speeds them and flatters them. The row records `ivf_nlists`, `ivf_nprobe`, `ivf_recall_target`, `ivf_recall_target_source`, `ivf_calibration_recall`, `ivf_calibration_queries`, and `ivf_calibration_slice`; `degree_family` says `ivf_flat_no_degree`, and `fairness_check.py` accepts that family only when the target is present and the calibration recall is within 0.01 of it. The lane and the multipass driver call the same hook in `arango_common.py`, so the two cannot drift. The cross-model lane measures no recall and keeps the uncalibrated starting fraction, recorded on its row as well.

*The #131 dense arms (2026-10-02), degree in each engine's own unit.* Elasticsearch's `index_options.m` and FalkorDB's `M` are hnswlib's M (doubled at layer 0), given COMPARATOR_M. LadybugDB's HNSW has two layers, `ml` the base layer's degree and `mu` the upper's, so it is given ml = 2 x COMPARATOR_M and mu = COMPARATOR_M and records `ladybug_ml_base_degree`. Memgraph 3.13.1 cannot be given a degree at all: it builds every vector index from a default USearch 2.21.4 config and ignores any other config key (recall was identical at connectivity 2, 16, and 64), and that default is connectivity 16, doubled at the base, so it matches by the engine's own value and the row records that value rather than ours. Its build expansion is fixed at 128 against the lane's ef_construction of 100, disclosed on the row (`memgraph_vector_expansion_add`); its search is matched by asking for 100 results and keeping 10 (`memgraph_search_count`), as the Neo4j arm's is. Whether each engine honours its parameters was checked by effect on the laptop (20k SIFT vectors), not read off its documentation: recall moved from about 0.04 to 1.0 between a crippled and a generous setting for FalkorDB and LadybugDB, and did not move at all for Memgraph. Elasticsearch's are read back from the index mapping onto the row (`es_index_options`), so an override would show there.

The same arms' pools carry the fits their engines already have on other lanes (F6 above): Memgraph's Bolt workers, snapshot threads, and memory limit; FalkorDB's THREAD_COUNT; LadybugDB's threads and buffer pool (F160); Elasticsearch's heap at the tier heap with `-Xms` = `-Xmx`, read back from `_nodes` as `es_heap_max_mib` beside `es_allocated_processors`.

**F8. The cpuset must equalise USE, not only the resource.** F1 gives every engine the same 12 threads. That is not the same as every engine *taking* the same amount: one that spreads a single query over 12 threads and one that answers on a single thread are both "given 12 CPUs", and comparing their p50s compares scheduling policy as much as engine speed. Measured 2026-08-03 on mini, dense `tiny` (100k vectors), the same cell at cpuset `0` and at `0-11`, three reps each, median [min-max]:

| backend | p50 @ 1 CPU | p50 @ 12 CPU | speedup |
|---|---|---|---|
| arcadedb_dense_embedded | 0.727 [0.69-0.73] | 0.677 [0.67-0.69] | 1.07x |
| chroma_dense | 0.508 [0.51-0.52] | 0.511 [0.51-0.53] | 0.99x |
| duckdb_vss_dense | 1.379 [1.38-1.38] | 1.374 [1.37-1.38] | 1.00x |
| lancedb_dense | 1.166 [1.17-1.17] | 1.396 [1.39-1.44] | **0.84x** |
| sqlite_vec_dense | 13.061 [12.81-13.23] | 13.266 [13.07-13.30] | 0.98x |

**No embedded engine parallelises a single query.** Four of five sit within 2% of 1.0, so the twelve threads are idle during a k=10 search and the p50 comparison is a comparison of engines, not of thread counts.

**LanceDB is reproducibly slower with more CPUs.** 0.84x is not noise: the three-rep ranges are disjoint. Giving it the full cpuset costs it roughly 20% on this workload. The bias runs against a comparator rather than for us, and it is disclosed rather than quietly enjoyed: LanceDB's published dense latency is a slight overstatement of what the engine can do on one core.

Scope, and it is narrow. One tier, k=10, one query in flight at a time, embedded backends only. It says nothing about concurrent query load, and nothing about Qdrant or Milvus, which run as servers and are the ones most likely to hold per-query pools. Re-measure before extending the claim.

**F9. A kept row needs a control, because the host is not an invariant.** F1 to F8 and F10 constrain a cell's *configuration*; none constrains *when* it ran. A row printed tonight beside one measured five weeks ago is fully compliant and still potentially wrong, because the kernel, the docker version and the machine's thermal history all moved and none of that is recorded as a run condition.

So when a campaign re-measures one engine and carries the others forward, **re-run one untouched comparator as a control and show it reproduces its kept numbers within run-to-run spread.** One extra cell buys evidence for every row that was not re-run. If the control does not reproduce, the carried-forward rows are not usable and the whole tier is re-measured. Record the control's old-against-new delta next to the table it licenses, so a reader can see the carry-forward was checked rather than assumed.

**F10. Same durability class per table, and one instrument.** A commit that
waits for the disk and one that does not are different operations, and a write
latency compares them only if every engine in the table waited the same way.
Since the 2026-10 instrument (DECISIONS #81) the matched class is *relaxed*: a
commit returns without waiting for the disk and the log is flushed by the
engine's own background policy.

**Every default below was read out of the engine, not assumed** (laptop,
2026-09-14, and 2026-09-17 for Memgraph and FalkorDB; the evidence for each is in `bench_common.py` above the
`DURABILITY_*` strings, which are defined once there so two lanes cannot
describe one engine differently). In the relaxed class: ArcadeDB at
`txWalFlush=0`, which `GlobalConfiguration.TX_WAL_FLUSH` reports as its default
and current value; SQLite and sqlite-vec under WAL with `synchronous=NORMAL`,
read back by `PRAGMA` and confirmed by `strace` (50 commits, 8 `fsync`);
PostgreSQL, pgvector, PG+AGE, and TimescaleDB, whose adapters run
`SHOW synchronous_commit` on connect and record the server's own answer;
MongoDB's timed writes at `w=1, j=false` against a server reporting
`journalCommitInterval` 100 ms; ArangoDB's default, with the 3.12.11 server
answering `database.wait-for-sync` false, `rocksdb.use-fsync` false, and
`rocksdb.sync-interval` 100 ms; QuestDB's default, with the server
answering `cairo.commit.mode` `nosync` from `SHOW PARAMETERS`; Memgraph's
default, with `SHOW CONFIG` answering `storage_wal_enabled` true and
`storage_wal_file_flush_every_n_tx` 100000, so the WAL is fsynced every
100,000 transactions rather than at commit (`strace`: 1 `fsync` over a build
and 3,009 commits); FalkorDB's default, with `CONFIG GET` answering
`appendonly` no and RDB snapshots only, so nothing is synced at commit
(`strace`: 0 `fsync` over a build and 3,011 writes); and SurrealDB
embedded, where an A/B under `strace` shows 6 `fsync` calls at both 50 and 250
commits with `SURREAL_SYNC_DATA` unset against 56 and 256 with it set.

Three engines cannot be relaxed and are the named exceptions on their tables.
Neo4j: `SHOW SETTINGS` offers no durability or sync setting at all
(its `tx_log` settings cover buffer, preallocation, and rotation), and forcing
the log at commit is its documented behaviour. LadybugDB: `strace` counts 56
`fdatasync` calls for 50 auto-commit writes, and `ladybug` 0.20.4's `Database()`
takes no sync option. DuckDB: `strace` counts 55 `fsync` calls for 50 commits,
and `duckdb_settings()` at 1.5.4 (the pin since DECISIONS #103d) exposes only
checkpoint and WAL-autocheckpoint thresholds, no commit-sync knob.

Two engines on the lifecycle table only (2026-10-02, DECISIONS #131 item 5)
have no setting either way. Chroma 1.5.9 syncs at every write: `strace` counts
8 `fsync` calls per `add()` (436 at 50 adds, 2,036 at 250), its SQLite reads
back `journal_mode=delete`, and its Settings offer no sync option, so it cannot
be relaxed and is named with the three above. LanceDB 0.39.0 never syncs at
commit: each `add()` writes a new table version and `strace` counts no sync
call of any kind over 250 of them, with no option on the connection or the
table, so it cannot be made strict (`fairness_check.RELAXED_ONLY_ALLOWED`).
Each prints one number, as the engines above do. LadybugDB was re-measured at
0.21.2 when the client image moved to it: one `fdatasync` per commit, as at
0.20.4.

**SurrealDB served has the knob, on its storage path (BUGS F165, 2026-10-02).**
SurrealDB 3.2.4 takes `sync=never|every|<interval>` as a query parameter on the
RocksDB path (`rocksdb:/tmp/surreal/db?sync=never`) and prints the mode at INFO
when it starts. Its default is `Sync mode: every transaction commit`: strace on
the laptop counts one `fdatasync` per commit, 5.3 ms each wall clock, and none at
`sync=never`, where single-record writes fall from about 7.5 ms to under 1.2 ms.
Until this date the harness held that 3.2.4 had no sync setting, because the
search covered only its `SURREAL_*` variable names, and every served row carried
"behaviour at commit is not verified" while every serverlog we kept carried the
default's line: the October campaign ran this engine at a sync per commit in both
classes. The relaxed class now passes `sync=never`, the strict class `sync=every`,
and the runner reads `Sync mode:` back from the startup log before the client
starts and refuses the cell on a mismatch (`surreal_sync_mode` on the row). The
`unverified` class stays in `bench_common.durability_class` and
`fairness_check`, with no backend allowed in it.

Every row records what it ran as `durability`; `fairness_check.check_durability`
refuses a 2026-10 row with none, a row whose engine reports a class other than
the one its cell asked for in `durability_class` (DECISIONS #90), a row that
declares no setting or carries an unverified string on an engine not named
above, or a PostgreSQL row whose server answered anything but its class's
setting (`off` relaxed, `on` strict). The same check refuses two `instrument`
values in one table (rows before 2026-10 carry none and are the September
instrument), and it refuses a time-series table whose engines disagree on the
row counts of the two data-dependent queries (`q_groupby_rows`, `q_high_rows`),
because a query that returned a different number of rows measured a different
question.

**F10c. What a clean stop syncs, by trace (the server-restart table, DECISIONS #139 item 2, 2026-10-02).** The
restart table times each server's own clean stop after a batch of committed writes, at the durability its own
table runs it at, so what the stop has to flush depends on that setting. Traced on the development machine
(`l6_restart.py` with `BENCH_RS_TRACE=1`: a sidecar in the server's PID namespace logs every `fsync`,
`fdatasync`, `sync_file_range`, `msync`, `syncfs`, and `sync` of every process during the stop; micro corpora,
200 committed writes before the stop; counts only, the times are not measurements): ArcadeDB 2 to 5
`fdatasync` (all four models); SurrealDB 7; ArangoDB 8; MongoDB 34, and 104 with mongot; PostgreSQL 22;
Neo4j 279 (its checkpoint); Memgraph 18; FalkorDB 2 (its RDB snapshot); Qdrant 84 (36 `fsync`, 48 `msync`);
Milvus 36; Elasticsearch 17; QuestDB 0 (`cairo.commit.mode=nosync`: its stop syncs nothing, and the batch
still read back after the restart, from the page cache the host kept). Every batch read back after every
restart on every engine. Two stops were not clean in the exit-code sense while losing nothing: Milvus exits
134 (SIGABRT, a goroutine dump) on every stop, and before 2026-10-02 the `dbbench:mongo-search` entrypoint
ignored the stop signal (bash as PID 1 traps nothing), which would have been a kill after the grace.

**F10b. Both durability classes on every timed write (DECISIONS #90,
superseding the single-setting half of #81).** F10 fixes the class within a
table; #90 adds the second table. Every timed write operation runs twice, once
at each setting: the six document operations, the three graph writes, and the
cross-model transaction. Bulk ingest stays at one setting, because an fsync per
batch at ten million vectors is hours and teaches nothing the write cells do
not, and every read path is untouched.

Most engines cannot switch this per operation -- ArcadeDB's `txWalFlush` is per
database, SurrealDB's and QuestDB's are server flags -- so the class is a
property of the CELL. `runner.py --durability strict` sets the flags that live
on a server and puts the class in the container's environment for the ones that
live on the client; `bench_common` holds one strict string per engine beside
its relaxed one; the row records `durability` (what the engine reports),
`durability_class` (what the cell asked for), `durability_no_setting`, and
`durability_server_flags`. The class is part of the canonical key, so a strict
cell cannot shadow the relaxed one beside it.

**Read back, not asserted, on both sides.** ArcadeDB's value comes from
`GlobalConfiguration.TX_WAL_FLUSH` after the database is open; SQLite's from
`PRAGMA journal_mode` and `PRAGMA synchronous`; ArangoDB's from the collection's
own `properties()["sync"]`; the PostgreSQL family's from `SHOW
synchronous_commit`. `fairness_check` fails a row whose engine reports a
different class from the one the cell asked for, which is what a flag that did
not take looks like.

**Three engines have no knob** and are the named exceptions: DuckDB and
LadybugDB, each straced rather than assumed, and Neo4j, whose settings offer
none and whose documentation says it forces the log at commit (not traced
here); the SurrealDB 3.2.4 server stood here as a fourth until BUGS F165 found
its setting. They run once, declare
`durability_no_setting`, and the page prints their one number in both columns,
which puts them on an equal footing instead of comparing their strict numbers
against everyone else's relaxed ones.

**The answer must not change with the class.** A strict commit changes when a
write becomes durable, not what it wrote, so the #88 digests of one engine must
match across its two classes; `equivalence_check` E2 fails a backend that gives
two answers across its own repetitions and classes.

What each engine pays for the strict class is measured on the bench host and printed by the durability table; laptop ratios were a smoke and are not repeated here.

**F11. Equivalent queries must return equivalent answers.** A benchmark that
never checks the answer measures how fast an engine can be wrong, and until
2026-09-14 this one never checked: recall against ground truth on the two
vector lanes and the torn-state comparison in the cross-model trial were the
only cross-engine correctness anywhere, so an adapter that dropped a filter, a
group or a join condition would have printed a lead rather than a bug
(DECISIONS #88).

Every timed query whose answer is deterministic now records a canonical digest
of that answer, a row count, and a short readable sample, written by
`bench_common.result_digest`. Three rules make the check mean something:

* The digest is computed from the object the **timed call returned**, outside
  the timed section. Re-running the query to digest it would digest a second
  execution against a different cache state, and on a lane with writes a
  different database.
* An engine that cannot express a query records
  `unexpressible: <reason>`, never a blank, because silence is
  indistinguishable from agreement.
* Normalisation is identical for every engine and is declared once per query,
  never per engine: the column order is the query's, alternative column names
  cover the dialects (`_id`, `_id.f`, an AQL `RETURN` name, a positional SQL
  tuple), integers print exactly, floats to six significant digits, strings are
  stripped, dates are ISO, aware datetimes land in UTC, and a column that holds
  an instant, a month or a MEASURE is declared as such so epoch seconds, epoch
  milliseconds, a datetime and a truncated date are one value, and so are an
  integral sum and the same sum as a double.
* A column that holds a **measure** is declared `num`; a column that holds a
  **count or an identifier** is not. The two spellings of a whole number --
  exact for an int, six significant digits for a double -- coincide only below
  a million, so an engine whose `SUM` returns an integer agrees with its
  neighbours at SF0.01 and disagrees at SF1 on the same correct answer. That
  happened, seven engines to one (2026-09-14, TPC-H Q1, ArangoDB). Counts stay
  exact in the other direction: rounding a count to six significant digits
  would let 1,234,567 and 1,234,568 agree.

A write has no answer to digest, so what is digested is the state it left: the
whole CRUD table read back after each phase, the orders after the new-order and
payment loops, the persons the graph writes created. An insert that wrote
nothing, an update that matched nothing and a delete that deleted nothing each
fail the gate instead of printing a fast number.

`equivalence_check.py` groups the digests by lane, scale, workload and query
and refuses a publish when two engines disagree, printing both samples. A group
with one engine is reported as UNCHECKED and never counted as a pass; a backend
that ran the cell and recorded neither a digest nor a declared absence fails; a
lane that recorded nothing at all fails unless it is declared as checked
otherwise, which the two vector lanes are, by recall.

**F12. Every table reports the same measurement set, or says why not.** One
warm median per query, a ninety-ninth percentile for the table's headline
query, ONE cold column per table, throughput where the operation has a natural
rate, recall where the index is approximate, peak memory, on-disk size after
the workload, and for the vector tables ingest and index build as separate
timers (DECISIONS #89, as amended). About nine columns on the widest table
rather than twenty-one, and **no aggregated per-table statistic**: no mean, no
median, and no geometric mean across query types. An arithmetic mean across
queries whose times span five orders of magnitude is the slowest query in
disguise, a median across them moves when a query is added, and the summary
figure already carries the cross-table ratio view.

The cold number is one per CELL, not one per query, because the cold question
is about the session: `cold_first_query_ms` and `cold_first_query_name`, from
the first query the cell ran after the database opened. On the two vector lanes
that is a WARMUP query rather than the first timed one, which is exactly why it
is the cold one. The rows also keep `cold_<q>_ms`, `warm_<q>_p50_ms` and
`warm_<q>_p99_ms` per query under one naming convention across every lane -- a
row carrying more than the page prints is useful, and it is what lets a table
ask every lane the same question without knowing which lane it is asking.

Where a measurement genuinely does not apply the row carries a stated reason in
`cold_warm_na` rather than a blank cell, and the strings are defined once in
`bench_common` so two lanes cannot phrase one exemption differently: a
transactional cell has no cold and warm split because every operation runs
against an already-warm database by construction; the lifecycle lane is itself
the cold measurement; the two vector lanes warm on a held-out slice before they
time anything, and their cold and warm columns come from the multipass driver.

**F13. Close cost is an invariant, not a column.** Close should be O(what was written), not O(what is stored), and on the order of 100 ms; the reasoning, the situations, and the numbers are PAGE-SPEC.md section 4 (DECISIONS #50). Checked by `fairness_check.check_close_cost`, which prints under this number. Renumbered from F11 here because F11 and F12 are the October instrument's two rules above; `fairness_check.check_close_cost` prints F13 too (it printed F11 until CAMPAIGN.md section 7, row 31, and `test_fairness_headers.py` holds the numbering against this file).

**F14. Equivalent queries get equivalent index support, and the support is chosen by MEASUREMENT (DECISIONS #112, BUGS F98).** Every engine reaches a query through some access path, and which path it gets is a choice this harness makes on its behalf. Until 2026-09-22 that choice was made by reasoning about what ought to help, and it was wrong in both directions at once: the document lane gave ArcadeDB an `l_shipdate` index worth **6.1x** on Q6 and gave PostgreSQL, which gains **2.5x** from the same index, none; it gave SQLite one that costs it **20%**; and the time-series lane gave every engine a `(host, ts)` path except DuckDB, which wants one.

The rule is NOT "every engine gets the same index". That is the obvious repair and it is wrong: the same Q6 index costs ArangoDB 29% and SQLite 20%, because at 14% selectivity an index lookup plus row fetches is dearer than the scan it replaces, and how dear depends on the engine. It is the rule F7 already uses for ArangoDB's IVF vector index, which has no degree to match: **matched by effect**. Each engine gets the configuration that is genuinely best for it, the decision is a measurement rather than an argument, the row records what was built, and the build time is published rather than folded into ingest so the cost of the choice is visible.

Three things follow, and they are what make this checkable rather than a good intention:

* **A new arm must declare its index decision.** `fairness_check` fails a lane backend that declares nothing, the way the capability table refuses a kind its legend cannot define. Silence is the state this invariant exists to remove.
* **And the declaration is checked against the rows, not trusted (F14b).** A map saying an arm builds an index is a claim; `index_s` on that arm's rows is the evidence. The gate fails an arm whose declaration cites a measured with/without ratio and whose every row records `index_s=0`, and fails one that declares `NONE` and records a build -- an index removed for costing that engine coming back. Only those two directions are asserted: a declaration like "record id carries pid" or "native TIMESERIES type" describes an index with no build step to time, and those arms are reported as not asserted rather than pattern-matched into an expectation. The count of arms checked, arms not asserted, and arms whose rows predate the ingest/index split is printed every run, so the coverage is visible rather than implied.
* **And where one arm times the two phases, every arm does (F14c).** The ingest/index split turns "this engine took 40 s to build the corpus" into "12 s writing, 28 s indexing", and it arrives per adapter -- so it is exactly the kind of thing that stops arriving when someone adds the next engine to a lane and writes a `build()` without knowing its neighbours time two phases inside theirs. The cost is not a missing number but an unfair TABLE: the column exists because the other arms fill it, so the new arm prints a blank where everyone else prints a figure, and a blank in a benchmark reads as a result. Three states pass -- the arm splits, or it declares `index_before_load` (the index is defined before the first row lands and its work is spread through the load, as SurrealDB does on the document and time-series lanes), or no arm on that lane splits at all (on the sparse lane every engine but pgvector builds its index as it ingests, and pgvector's index build follows its load inside the same single timer; on the graph lane every engine creates its index in the schema before loading). The finding is the fourth: a lane where some arms split, one does not, and it says nothing. On the dense lane the two phases are independent timers inside `build_s` rather than a division of it, so those rows also carry `setup_s` for the remainder, and the three add up (BUGS F101).
* **ArcadeDB's id indexes follow the vendor's rule for the index kind, and the page says which are which.** ArcadeDB's maintainers answered (ArcadeData/arcadedb#9169) that an id a workload only reads, updates, and deletes by equality takes `UNIQUE_HASH`, and that a key also ranged over or ordered stays `UNIQUE` (a sorted LSM tree). The documents lane's `Part(p_partkey)`, `OrderNew(okey)`, and `Crud(ckey)`, the tabular lane's `orders(id)`, the cross-model lane's `Product(pid)`, and the graph lane's LDBC message-half ids are hash indexes from the 26.10.1 re-pin; `Person(id)` stays sorted because the graph lane's untimed `person_scan` ranges over it, and `l_shipdate`, `customer_id`, the time-series `Point(host, ts)`, and the lifecycle and recovery indexes are not equality-only ids. Each comparator keeps the primary-key or default index its own maintainers give it, so this is the same footing and not a knob only ArcadeDB gets. It moves both ways: hash lookups are faster and the hash build is slower than the sorted build when ids arrive in ascending order, as every loader here sends them, so the ingest and index columns carry a cost and the transaction columns a gain, and the table says so in a generated sentence. `fairness_check.ARCADEDB_HASH_ID_INDEXES` is the one registry of which ids those are, and `test_index_kinds.py` holds it equal to the `CREATE INDEX` text in each lane. The registry is the claim and the row is the evidence (F14d): each ArcadeDB arm on those lanes records `index_kinds`, the engine's own `SELECT FROM schema:indexes` answer after the schema is built, a stamped row with another kind is a failure from the first day, and a row without the stamp is a failure since the 26.10.1 measurement started (one constant, `INDEX_KINDS_GATE_FAILS`, flipped in the commit that started it and now `True`), and the page sentence is built only from rows that carry the stamp, so a page regenerated over rows measured before the stamp existed claims nothing.
* **The decision names its evidence.** "No index" is a finding when it is measured (ArangoDB, DuckDB on the document lane) and a defect when it is an omission (PostgreSQL on the document lane, DuckDB on the time-series lane, both until 2026-09-22).
* **Index build time is its own column** wherever the engine has a boundary to time. The dense vector table has always separated `ingest s` from `index s`; the rest folded index build into ingest, which hides both the cost and the asymmetry -- SurrealDB's document arm must build its index BEFORE the load, so about 5.3 s of index work sits inside an ingest number every other engine pays without any.

The measurements behind this are in BUGS F98, per engine, with the row counts they were taken at. They are ratios within one engine and not a comparison between engines.

**F15. A setting this benchmark overrides is on the row and under the table (CAMPAIGN.md section 7, item 21).** PROTOCOL.md section 7 lists every default that is overridden, and for nine of them its last column said NOWHERE: the inventory was the only record, so a reader of a table could not learn that Elasticsearch ran with security off, that DuckDB's pool was fitted to the cpuset, or that the ArcadeDB server ran a different query-memory limit from the embedded package. `overrides.py` registers each override a table shows: the arms that run it, the row field their adapter reads back from the engine (Elasticsearch's `_xpack` and index settings, DuckDB's `current_setting`, Neo4j's `SHOW SETTINGS`, the ArcadeDB index's own metadata, the served ArcadeDB's `schema:database`, which the runner asks over HTTP, and its request-body limit from `GET /api/v1/server?mode=default`), the value the sentence claims, and the generated sentence. Three checks hold it. `fairness_check` F15 fails a 2026-10 row of such an arm that lacks the field or carries another value: DuckDB's thread count is held to the size of the row's own cpuset, so a `PRAGMA` that did not take fails, and Neo4j's page cache is held to what the cell passed. `page_check` fails a table that shows such an arm and prints no sentence saying so. `test_overrides.py` reads PROTOCOL.md section 7 and fails when a row still says NOWHERE or cites a registration that does not exist. Two limits, stated: the served ArcadeDB's `addHierarchy` has no read-back at this pin (its HTTP API returns no index metadata), so its field records the request and says so; and the registry shows that an override can be found, not that it is justified. No sentence says which way an override moves a number.

## Parallelism policy: maximise it, but never inside a published absolute

The standing direction is to use the machine. But "run more at once" and "report this latency" are not compatible everywhere, so the rule has to say where the line falls.

Randomly permuting run order is worth doing and we do it, but it buys one thing: it stops co-run noise from landing preferentially on one configuration, so an A-against-B **ratio** stays honest. It does not remove the noise. Two jobs sharing an L3 and a memory controller both run slower and both show fatter tails, and permutation cannot restore an absolute level or a p95 that never happened. Our headline claims are single-node absolutes and percentiles, which is exactly the quantity permutation cannot repair.

So the split is by **what the number is**, not by how long the job takes:

| may run in parallel, freely | must be serial on the full cpuset |
|---|---|
| dataset download, decompression, ground-truth generation | every latency cell whose number reaches a table |
| docker image builds, wheel builds | every throughput/QPS cell |
| exploration sweeps and parameter scans | anything reporting p95/p99 |
| A/B probes whose answer is a **ratio** measured in the same run | memory working-set cells |
| any run whose output is a decision, not a table cell | scale-ceiling and RAM-bound cells (serial anyway) |

Two consequences:

1. **A parallel run cannot be promoted later.** If a cell was measured two-at-once, it is exploration forever; wanting the number afterwards does not make it eligible. F2 makes that enforceable rather than aspirational.
2. **Disclose the shape, not a co-run penalty per engine.** Say which classes of work were parallel and that every reported number was re-measured serially. A per-engine perturbation table is detail nobody can check, and it invites the reader to treat the exploration tier as if it were data.

**Sharding, when parallel is allowed.** Disjoint cpuset shards, never overlapping, never crossing an SMT sibling pair, and the same shard width for every arm of a comparison. Three 4-thread shards over `0-11`, not "whatever is free". An arm given a wider shard than its neighbour is F1 violated with extra steps.

## Allowed to differ (must be DISCLOSED, per PROTOCOL.md section 7)

- **Vendor settle steps** that have no equivalent elsewhere (Elasticsearch forcemerge, Milvus flush+load, Qdrant green-wait, ArcadeDB `COMPACT INDEX`). Each engine gets *its own*; none goes unmatched by the others having theirs. The one settle step this harness defines rather than a vendor is the SurrealDB server's HNSW wait on the dense and cross-model lanes, a latency probe recorded as `settle_s` (BUGS F134, DECISIONS #117), and PROTOCOL.md section 7 lists it as such.
- **Operating points deliberately not matched**, such as the dense fp32 arms with the build cache pinned to the corpus against INT8 at the engine default (DECISIONS #56), stated in the l3d condition.
- **Quality and precision differences** (int8 against fp32 postings, ES pruning). Report recall next to latency, always.
- **Intra-query parallelism at each engine's default.** ArcadeDB's SQL scans a type's buckets in parallel (`arcadedb.queryParallelScan`, on by default) only when the type has at least two buckets, and `arcadedb.typeDefaultBuckets` is 1. Every ArcadeDB type in this benchmark is created with the default. At the October pin that meant its full scans ran on one thread, as SQLite's and MongoDB's do, while DuckDB uses the whole cpuset; from 26.10.1 (PR #8524) one bucket is split into page ranges across the workers, so a scan outside a transaction runs in parallel at the engine default. Not tuned: the bucket count is a knob that moves only ArcadeDB, so the default stands until a campaign decides otherwise (decided 2026-09-23; CAMPAIGN.md section 7, item 10). A served ArcadeDB read through `POST /api/v1/command` runs inside an auto-commit transaction, where a scan never runs in parallel (ArcadeData/arcadedb#8775); the served reads go through `POST /api/v1/query`, which runs an idempotent statement without one (CAMPAIGN.md section 7, row 25, BUGS F163). The per-record cost that makes a single-threaded scan slow is engine code, filed as ArcadeData/arcadedb#8260.

Anything else that differs is a defect, not an override.

## Bespoke drivers investigate, lane scripts publish

Both fairness violations ever found in a published table were rows a bespoke driver produced rather than the lane script: a driver is written to answer a narrow question and carries whatever protocol its author needed at the time, and is then promoted to a cell. Every clean lane puts each backend through one script, so warmup and settle are decided once and apply to everyone. L3d and L3s's warm columns are the two places that still publish overlay-driver rows (`dense_multipass_driver.py` and `sparse_multipass_driver.py`, run through the runner). If a driver's output must become a cell, diff its protocol against the lane's first.

## A CPU percentage is a fact about a container, not about an engine

ArcadeDB's sparse build runs at roughly 2 of the 12 allocated cores, and that is a harness property rather than an engine property: `ArcadeEmbedded.build` in `l3_sparse.py` is a serial Python loop calling `newDocument`/`save` per document, so about one core is a single producer thread and the rest is engine background work. The engine was never asked for more.

Nor is it an unfairness. Qdrant, Milvus and Elasticsearch drive ingest from the *same* serial `gen_docs` loop, batching into `upsert`, `insert` and `bulk`. The producer is symmetric; what differs after the handover is architectural (in-process per-document JNI against one client call per batch to a server that parallelises internally), which is the deployment axis the page already reports. What survives is narrow and ours: embedded pays N JNI crossings per batch where a client pays one, and upstream #5577 bounds the dense cost at roughly 7% of insertion.

Attributing a CPU percentage requires knowing who was asking for the work.

## An exit code is not evidence

`rc == 0` means a process finished, not that it measured what you asked for. Two defects of exactly that shape: a queue script that set only `BENCH_DATA` left `l3_sparse.py` on its synthetic fallback generator and produced 94 rows across three tiers, every one `rc=0`, under stages that logged OK, distinguishable from the real corpus only by the absent ground truth; and the F3 heap, where cells produced rows, stages reported OK, and the artifact asserted a heap the engine never had.

Acceptance has to compare the DATA against the specification, because every one of these produced output that looked exactly like success:

- A **container-side preflight** asserts, from inside the container, that the lane sees the corpus it was told to use and accepts the scales it will be passed. Checking the host path is a different check: a run once lost 20 cells to a directory that existed on the host and not at the mount point.
- Every sparse stage is **verified against the data it produced**, recall present and `n_docs == 8_841_823` at medium, not against its return code.
- `load_canonical` drops any sparse row without a recall number, before the dedupe, so an unpublishable row cannot shadow a publishable one.

Prefer the loud failure. The same script that wrote those 94 quiet rows also crashed the graph lane outright, and that failure cost 80 cells and was worth far less than it looked, because it was loud.

## Still open

Whether any engine's disk IO scheduling differs under the same cap (CAMPAIGN.md section 7, item 20).
