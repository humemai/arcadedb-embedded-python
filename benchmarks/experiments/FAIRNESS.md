# The fairness contract

Every number on the page compares systems. A comparison is only worth printing if both sides were given the same thing. This file says what "the same thing" means, what is allowed to differ, and what is checked mechanically rather than remembered.

`fairness_check.py` is one of the gates `refresh_web_page.py` runs (`equivalence_check`, `resource_check`, `provenance_check`, `fairness_check`, `page_check`, `version_consistency_check`, `version_pin_check`). It fails loudly rather than warning quietly.

The failure mode this contract exists to close is **a correct number measured under conditions the row beside it did not get**. `claims_check` and `provenance_check` cannot see it: both verify a number against its own artifact, and such a number is correct about its own run.

## Invariants (must hold; checked)

**F1. Same cpuset.** Every container in a published cell gets the full `0-11` (the 12 P-threads on 6 physical P-cores). Client and server topologies share that cpuset deliberately, so CPU competition stays inside the deployment under test rather than being hidden by giving the server its own cores.

**F2. Serial only.** Published cells run one at a time. `runner.py` forces `workers=1` on the paper tier and errors otherwise; queue scripts pass `--tier paper --workers 1` explicitly. The parallel sweep tier (disjoint cpuset shards, shuffled order) exists for exploration and must never reach a table. A published row from a sweep is detectable after the fact as a partial cpuset such as `0-5`, and `load_canonical` drops it.

**F3. Same memory envelope per (lane, scale).** Every backend at a tier gets the same `--memory`/`--memory-swap` cap and, for JVM engines, the same heap (the same `-Xmx`; the ArcadeDB arms, embedded and served, leave `-Xms` unset, as the bindings document and ArcadeDB's maintainers advise for a fixed memory budget, while each other server engine keeps the initial heap its own documentation recommends: PROTOCOL.md section 7, "JVM initial heap"). Two JVM processes are exceptions and run at their own default heap: QuestDB, whose rows record the tier heap although no heap reaches its server, and mongot inside the MongoDB Search image (CAMPAIGN.md section 7, row 30). One ArcadeDB arm is a declared exception on purpose (F3b): the served arm at the vendor image's own JVM settings, on the documents transaction workload only (CAMPAIGN.md section 7, row 69). It gets the same memory cap as every other arm and a different heap and collector; its row records no tier heap, stamps `server_jvm_defaults`, and carries the JVM's own report of what it ran (`server_jvm_*`, read from the process). `fairness_check.JVM_DEFAULTS_ARMS` names it and what it differs in, and the gate fails a `jvm_defaults` arm that is not declared and a declared arm that is not marked, so the one arm that runs other settings than its siblings says so and shows it.

A served backend gets the **full tier cap** and the client its own `BENCH_CLIENT_MEM` budget on top, stamped `mem_split="full+client"`, so a served engine sees exactly the cap an embedded engine of the same tier sees. Every frozen served row carries that stamp. `BENCH_SERVER_MEM_FRACTION` restores the older `server = 0.75 * total` split for a reproduction. Compare a served topology by `srv_cap / mem_split`, never by adding client and server: addition reads 1.75x the envelope.

**The edge this rule has on a lane whose DRIVER is memory-hungry.** The rule gives the engine the full cap on both deployments, which is right. But a served cell runs the driver in its OWN container, while an EMBEDDED cell is one process, so on that side the driver competes with the engine for the one cap. It is invisible on most lanes because the driver is small; on `l4` the lane parses line protocol in Python inside every cell, and at `ts1000` that parser peaked at 7.6 GiB in the served arm's client container (BUGS F66). Any sentence comparing the two deployments' MEMORY on this lane must say which side was carrying the parser, and a claim that one deployment accumulates and the other does not needs more than the two peaks to stand up. The parsed corpus is now held at about a third of that and freed after ingest (CAMPAIGN section 7 row 18); the earlier rows keep the larger figure.

**"Same heap" means the heap the engine RAN, not the heap the cell asked for.** A row stamps `heap` from the request, so a hardcoded server heap is invisible in the artifact (Elasticsearch once ran 4g at three tiers while stamped `heap=16g`). `observe_server()` closes it by reading the container's real `-Xmx` back out of `docker inspect` into `server_heap` and failing any cell where the two disagree. Rows without that witness are dropped from published tables by `load_canonical`, so a tier shows a gap rather than an unfair number.

**F3d. Neo4j, Elasticsearch and CrateDB run their vendors' memory rules, so their heap is not the tier heap (DECISIONS #202).** F3 says every JVM engine gets the same `-Xmx`; the harness runs every engine as its vendor recommends, and for these (two, and CrateDB since 2026-10-23) the vendor gives a rule that differs from half the cap. Neo4j takes the heap and page cache that `neo4j-admin server memory-recommendation --memory=<cap>` prints, run from the pinned image for each tier cap (`vendor_memory.NEO4J_MEMORY`, held equal to the committed tool output `neo4j_memory_recommendation.json` by `test_vendor_memory.py`), with the initial heap equal to the maximum. Elasticsearch takes the tier heap capped at 50% of the cap and at 26 GiB (Elastic: "no more than 50% of the total memory available to each Elasticsearch node", "26GB is safe on most systems"), `-Xms` = `-Xmx`; only deep10m moves, from 24g to 18g. The memory cap stays the same for every engine, and `fairness_check.check_envelope` judges the cap with everyone else and these two arms' heap against the vendor table. The heap each engine ran is still read back from the container (`server_heap`) and the running JVM. CrateDB: "a good starting point for the heap space is 25% of the system memory", between 1 GB and 30.5 GB (https://cratedb.com/docs/guide/admin/memory.html), set with `CRATE_HEAP_SIZE` from `vendor_memory.cratedb_heap`; the node's own heap maximum is read back from `sys.nodes` (`cratedb_heap_max_mib`).

The check is honest about its own limit: it reads the container's ENV, which is what we passed in, not the JVM's live heap. It proves the plumbing, not the obedience. The stronger form is to ask the engine (Elasticsearch reports `jvm.mem.heap_max_in_bytes` from `/_nodes/jvm`); it is owed, and CAMPAIGN.md section 7, item 20 carries it.

**A resource raised for one engine obliges a re-measure of every engine at that tier.** This is the sharpest rule here, and the one that has been broken: the dense envelope went 28g/16g to 36g/24g for a legitimate reason and only ArcadeDB was re-measured, which turned a fix into a 29% memory advantage.

Note the scope. The rule is about *resources*. Upgrading one engine's version is not a resource change: the comparators keep the same cpuset, envelope, protocol and degree, so F1 to F8 still hold and their rows may be carried forward under F9.

**F4. Same protocol.** Reps per build, warmup count, settle step and query set are properties of the LANE, not of whoever wrote the driver. If ArcadeDB gets five passes over one build, so does every comparator. If one engine gets a post-ingest settle, all of them do.

*One engine, two versions, two spellings.* The two SurrealDB deployments run different text for the triangle count, because the faster form inverts between their versions (the record-link form is 5.2x faster on the embedded core 2.3.10 and the arrow form 4.2x faster on the served 3.2.4), so one shared text would hand whichever arm it suits less a penalty that measures our spelling rather than either engine (DECISIONS #93). Both texts and both measurements stay in the adapter, and the answer digests prove the two forms compute the same number.

**F5. Same engine line within a table.** A row measured on a different release than the row beside it compares versions while appearing to compare configurations.

**F6. Thread pools are fitted to the cpuset, not to the host.** F1 pins the cpuset, which bounds which CPUs a process may run on. It does not bound how many threads the process starts, and several runtimes size their pools from the host core count regardless of the mask. An engine running 20 threads on 12 CPUs pays context switching its 12-thread neighbour does not.

The call that sees the restriction is `sched_getaffinity`. **`os.cpu_count()`, `nproc --all` and `/proc/cpuinfo` report the host and ignore the mask**, so any of them in an adapter is this bug. Plain `nproc` does respect affinity, verified rather than assumed: under `taskset -c 0-11` on a 16-CPU box, `nproc`=12 while `nproc --all`=16 and `/proc/cpuinfo`=16.

Fitting the pool is resource fitting, the first of the four sanctioned override categories, so it is applied rather than merely disclosed. What each fit sets, and the row field that reads it back, is in PROTOCOL.md section 7; the pins are in COMPARATORS.md. This table is the audit: what each runtime does under a cpuset, and the verdict.

| runtime | evidence | verdict |
|---|---|---|
| DuckDB | default `threads`=20 under a 12-CPU cpuset in the real bench image; every lane sets `PRAGMA threads` from `sched_getaffinity` (`duckdb_threads`, `duckpgq_threads` on the graph arm) | host default; fitted |
| Qdrant | `actix-rt` runtime 11 threads, update pool ~11, from `/proc/<pid>/task` | cpuset |
| Elasticsearch | `_nodes/os` reports `available_processors: 12`, `allocated_processors: 12` | cpuset |
| Neo4j | 10 `GC Thread#N`; G1 derives `8 + (N-8)*5/8` above 8, so 12 CPUs gives 10 | cpuset |
| ArcadeDB (JVM) | `availableProcessors()` reads the cgroup on Java 11+ | cpuset |
| Chroma, LanceDB, sqlite-vec | embedded in the driver, no separate server pool. Their Rust runtimes and the Python process's own threads follow the cpuset, each measured against a run with no cpuset; SQLite is single-threaded. Their caches are fixed or unbounded, not host-sized | cpuset; the lifecycle arms record `lc_threads_after_open` |
| Milvus | `go_sched_gomaxprocs_threads 12`; Go sizes from `sched_getaffinity` | cpuset |
| Memgraph | `SHOW CONFIG` under a 12-CPU cpuset on a 16-CPU laptop: `bolt_num_workers` and `storage_snapshot_thread_count` both 16, documented as "the number of processing units available on the machine"; its memory limit is host-sized the same way | **host**; fitted (`memgraph_bolt_workers`, `memgraph_snapshot_threads`, `memgraph_memory_limit_mib`; the cross-model arm too) |
| FalkorDB | 4.20.6: the startup log says "using 16 threads" for the query pool (host) and "set to 12" for OpenMP (the GraphBLAS pool reads the mask). 6.0.1 sizes the query pool from the cpuset and keeps the explicit setting | **host** for the 4.20.6 query pool, cpuset for OpenMP; fitted (`falkordb_thread_count`, `falkordb_omp_threads`) |
| LadybugDB (BUGS F160) | `CALL current_setting("threads")` reads the host's CPU count under a cpuset (LadybugDB/ladybug#1070), and the buffer pool defaults to 0.8 of physical RAM, above the cell cap. A laptop A/B on the lane's own adapter at 20 against 12 threads put its reads 12-28% slow and its writes 12% fast | **host**; fitted (`ladybug_threads`, `ladybug_buffer_pool_mib`; the cross-model arm too) |
| CrateDB | `sys.nodes`: `os_info['available_processors']` reads the `processors` setting, which defaults to the host's CPU count (the vendor's `node.rst`: "by default ... the available processors on the system"); with `-Cprocessors={ncpu}` a 12-CPU cell reports 12 (probed 2026-10-23: 6 under a 6-CPU cpuset) | **host default**; fitted (`cratedb_processors`; heap `cratedb_heap_max_mib`, F3d) |
| PostgreSQL (every arm: AGE, `postgres_tuned`, `timescaledb`, `pgvector_dense`, `pgvector_sparse`, `postgres_ts`) | `SHOW` under an 8-CPU cpuset and a 16 GiB cap: `max_parallel_workers_per_gather` 2 and `work_mem` 4MB, fixed defaults rather than host-sized ones, so not F6's bug as stated; but every other engine's pools reach the cell's cores and cap, and these reach 3 of 12 cores and spill rather than use the cap. Same-run A/B, defaults against fitted (`BENCH_PG_FIT=off`), answers identical in every pair: LSQB q2 on AGE 1.8x faster fitted, TPC-H Q1 on `postgres_tuned` 1.47x, `work_mem` fitted from the cap cut temp-file spill from 42 GB to 0.7 GB per analytics pass; TimescaleDB and pgvector search unchanged within run noise | **fixed default**; fitted through `runner.PG_FIT_CMD` on every PostgreSQL arm except `postgres`, the defaults arm by design (`pg_*` fields, or `server_cmd` on the cross-model rows). `BENCH_PG_FIT=off` exists for the A/B only |

The comparators this audit did not cover (MongoDB, QuestDB, SurrealDB, SQLite, and ArangoDB) are not yet audited, and memory pools have been checked for a host-sized default only where one was found (Memgraph's memory limit and LadybugDB's buffer pool, BUGS F160); CAMPAIGN.md section 7, item 20 carries both.

Two ways to get this audit wrong, both nearly recorded. Total OS thread count is not pool sizing: a JVM server runs dozens of threads irrespective of cpuset, so the question for a JVM is `availableProcessors()` and the named pool settings. And running `nproc` inside a container answers about the container, not about the engine: ask the engine's own metrics.

The DuckDB bias runs **against** DuckDB, which wins that lane regardless, so nothing self-serving rests on it.

**F7. Same effective base-layer degree across dense backends per scale.** Engines spell graph degree differently: one takes the per-layer `maxConnections`, another the base-layer degree, and the same integer therefore builds two different graphs. Recorded per row as `degree_param` plus `degree_family` so the check reads the number in the unit its own engine meant. A row recording no degree FAILS.

*The other construction knob, and why it is NOT matched.* ArcadeDB builds through jvector, which also exposes `neighborOverflowFactor` (engine default 1.2). Raising it cuts graph-unreachable nodes at no measurable cost, and it stays at the default anyway: cheap is not the test, "is there a matched value on the other side" is, and there is none, because no hnswlib-family comparator has this knob. Setting it would move our graph alone, in our favour, which is what separates it from the `maxConnections` 32-against-16 correction: that one converts units between two engines that mean different things by the same integer (DECISIONS.md #45).

*An index whose degree is fixed and equals the match.* CrateDB 6.4.6 exposes no HNSW parameter. Its graph is Lucene 10.4.0's default format: `Lucene99HnswVectorsFormat` DEFAULT_MAX_CONN 16 (doubled at layer 0, hnswlib's M 16) and DEFAULT_BEAM_WIDTH 100, read from the class constants of the jars in the pinned image, with `CrateCodec` only wrapping the delegate's format (2026-10-23). The row records the value it builds (`degree_param` 16, family `hnswlib_m_doubled_at_base`, `cratedb_lucene_max_conn`, `cratedb_lucene_beam_width`), as Memgraph's does; the adapter refuses to build at any other `BENCH_DENSE_COMPARATOR_M`, because then F7 could not be met. The search beam is `knn_match`'s k, per shard, and the table has one shard, so k = ef_search; the lane's matched-recall sweep turns it as it turns every ef.

*An index with no degree is matched by effect.* ArangoDB's vector index is FAISS IVF, so F7's degree has no counterpart. Its operating point is chosen to land on the same recall instead: `nLists` is FAISS's own guideline `round(4*sqrt(n))`; `nProbe` is calibrated inside the cell, after the build and before any timed pass, by binary search on a held-out slice the timed pass never sees, for the smallest value whose recall@10 reaches the target; and the target is the median recall@10 of ArcadeDB's own embedded fp32 arm at the same scale, read from the frozen CSV. Matching our own arm is the neutral choice: a higher target slows them and flatters us, a lower one speeds them and flatters them. The row records `ivf_nlists`, `ivf_nprobe`, `ivf_recall_target`, `ivf_recall_target_source`, `ivf_calibration_recall`, `ivf_calibration_queries`, and `ivf_calibration_slice`; `degree_family` says `ivf_flat_no_degree`, and `fairness_check.py` accepts that family only when the target is present and the calibration recall is within 0.01 of it. The lane and the multipass driver call the same hook in `arango_common.py`, so the two cannot drift.

*The #131 dense arms, degree in each engine's own unit.* Elasticsearch's `index_options.m` and FalkorDB's `M` are hnswlib's M (doubled at layer 0), given COMPARATOR_M. LadybugDB's HNSW has two layers, so it is given ml = 2 x COMPARATOR_M and mu = COMPARATOR_M and records `ladybug_ml_base_degree`. Memgraph cannot be given a degree at all (it ignores any other config key; recall was identical at connectivity 2, 16, and 64), so it matches by the engine's own value and the row records that value rather than ours; its fixed build expansion and its search count are disclosed on the row (`memgraph_vector_expansion_add`, `memgraph_search_count`). Whether each engine honours its parameters was checked by effect, not read off its documentation. Elasticsearch's are read back from the index mapping onto the row (`es_index_options`). The per-engine settings are in COMPARATORS.md.

The same arms' pools carry the fits their engines already have on other lanes (F6 above), and Elasticsearch's heap is the tier heap with `-Xms` = `-Xmx`, read back from `_nodes` as `es_heap_max_mib` beside `es_allocated_processors`.

**F8. The cpuset must equalise USE, not only the resource.** F1 gives every engine the same 12 threads. That is not the same as every engine *taking* the same amount: one that spreads a single query over 12 threads and one that answers on a single thread are both "given 12 CPUs", and comparing their p50s compares scheduling policy as much as engine speed. Measured on mini, dense `tiny` (100k vectors), the same cell at cpuset `0` and at `0-11`, three reps each, median [min-max]:

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

**F10. Same durability class per table, and one instrument.** A commit that waits for the disk and one that does not are different operations, and a write latency compares them only if every engine in the table waited the same way. Since DECISIONS #81 the matched class is *relaxed*: a commit returns without waiting for the disk and the log is flushed by the engine's own background policy.

**Every default below was read out of the engine, not assumed.** The evidence for each is in `bench_common.py` above the `DURABILITY_*` strings, which are defined once there so two lanes cannot describe one engine differently. In the relaxed class: ArcadeDB at `txWalFlush=0` (`GlobalConfiguration.TX_WAL_FLUSH`); SQLite and sqlite-vec under WAL with `synchronous=NORMAL` (`PRAGMA`, confirmed by `strace`); PostgreSQL, pgvector, PG+AGE, and TimescaleDB, whose adapters run `SHOW synchronous_commit` on connect and record the server's own answer; MongoDB's timed writes at `w=1, j=false` against a server reporting `journalCommitInterval` 100 ms; ArangoDB's default (`database.wait-for-sync` false, `rocksdb.use-fsync` false, `rocksdb.sync-interval` 100 ms); QuestDB's default (`cairo.commit.mode` `nosync`); Memgraph's default (`storage_wal_file_flush_every_n_tx` 100000, so the WAL is fsynced every 100,000 transactions rather than at commit); FalkorDB's default (`appendonly` no, RDB snapshots only, so nothing is synced at commit); and SurrealDB embedded, where an A/B under `strace` shows 6 `fsync` calls at both 50 and 250 commits with `SURREAL_SYNC_DATA` unset against 56 and 256 with it set.

Three engines cannot be relaxed and are the named exceptions on their tables. Neo4j: `SHOW SETTINGS` offers no durability or sync setting at all, and forcing the log at commit is its documented behaviour. LadybugDB: `strace` counts 56 `fdatasync` calls for 50 auto-commit writes, and `Database()` takes no sync option. DuckDB: `strace` counts 55 `fsync` calls for 50 commits, and `duckdb_settings()` exposes only checkpoint and WAL-autocheckpoint thresholds, no commit-sync knob.

Two engines on the lifecycle table only have no setting either way. Chroma syncs at every write (`strace` counts 8 `fsync` calls per `add()`, its SQLite reads back `journal_mode=delete`, and its Settings offer no sync option), so it cannot be relaxed and is named with the three above. LanceDB never syncs at commit (`strace` counts no sync call of any kind over 250 `add()` calls, with no option on the connection or the table), so it cannot be made strict (`fairness_check.RELAXED_ONLY_ALLOWED`). Each prints one number, as the engines above do.

**SurrealDB served has the knob, on its storage path (BUGS F165).** It takes `sync=never|every|<interval>` as a query parameter on the RocksDB path and prints the mode at INFO when it starts; its default is a sync at every transaction commit. The relaxed class passes `sync=never`, the strict class `sync=every`, and the runner reads `Sync mode:` back from the startup log before the client starts and refuses the cell on a mismatch (`surreal_sync_mode` on the row). The `unverified` class stays in `bench_common.durability_class` and `fairness_check`, with no backend allowed in it.

Every row records what it ran as `durability`; `fairness_check.check_durability` refuses a row with none, a row whose engine reports a class other than the one its cell asked for in `durability_class` (DECISIONS #90), a row that declares no setting or carries an unverified string on an engine not named above, or a PostgreSQL row whose server answered anything but its class's setting (`off` relaxed, `on` strict). The same check refuses two `instrument` values in one table (rows before 2026-10 carry none and are the September instrument), and it refuses a time-series table whose engines disagree on the row counts of the two data-dependent queries (`q_groupby_rows`, `q_high_rows`), because a query that returned a different number of rows measured a different question.

**F10c. What a clean stop syncs, by trace (the server-restart table, DECISIONS #139 item 2, 2026-10-02).** The restart table times each server's own clean stop after a batch of committed writes, at the durability its own table runs it at, so what the stop has to flush depends on that setting. COMPARATORS.md describes the table and its engines; this is the trace COMPARATORS.md does not hold. A sidecar in the server's PID namespace (`l6_restart.py` with `BENCH_RS_TRACE=1`) logs every `fsync`, `fdatasync`, `sync_file_range`, `msync`, `syncfs`, and `sync` of every process during the stop; micro corpora, 200 committed writes before the stop; counts only, the times are not measurements: ArcadeDB 2 to 5 `fdatasync` (all four models); SurrealDB 7; ArangoDB 8; MongoDB 34, and 104 with mongot; PostgreSQL 22; Neo4j 279 (its checkpoint); Memgraph 18; FalkorDB 2 (its RDB snapshot); Qdrant 84 (36 `fsync`, 48 `msync`); Milvus 36; Elasticsearch 17; QuestDB 0 (`cairo.commit.mode=nosync`: its stop syncs nothing, and the batch still read back after the restart, from the page cache the host kept). Every batch read back after every restart on every engine. Milvus exits 134 (SIGABRT, a goroutine dump) on every stop while losing nothing.

**F10b. Both durability classes on every timed write (DECISIONS #90, superseding the single-setting half of #81).** F10 fixes the class within a table; #90 adds the second table. Every timed write operation runs twice, once at each setting: the six document operations, the three graph writes, and the cross-model transaction. Bulk ingest stays at one setting, because an fsync per batch at ten million vectors is hours and teaches nothing the write cells do not, and every read path is untouched.

Most engines cannot switch this per operation (ArcadeDB's `txWalFlush` is per database, SurrealDB's and QuestDB's are server flags), so the class is a property of the CELL. `runner.py --durability strict` sets the flags that live on a server and puts the class in the container's environment for the ones that live on the client; `bench_common` holds one strict string per engine beside its relaxed one; the row records `durability` (what the engine reports), `durability_class` (what the cell asked for), `durability_no_setting`, and `durability_server_flags`. The class is part of the canonical key, so a strict cell cannot shadow the relaxed one beside it.

**Read back, not asserted, on both sides.** ArcadeDB's value comes from `GlobalConfiguration.TX_WAL_FLUSH` after the database is open; SQLite's from `PRAGMA journal_mode` and `PRAGMA synchronous`; ArangoDB's from the collection's own `properties()["sync"]`; the PostgreSQL family's from `SHOW synchronous_commit`. `fairness_check` fails a row whose engine reports a different class from the one the cell asked for, which is what a flag that did not take looks like.

The three engines with no knob (named under F10) run once and declare `durability_no_setting`. The page prints their one number in both columns, which puts them on an equal footing instead of comparing their strict numbers against everyone else's relaxed ones.

**The answer must not change with the class.** A strict commit changes when a write becomes durable, not what it wrote, so the #88 digests of one engine must match across its two classes; `equivalence_check` E2 fails a backend that gives two answers across its own repetitions and classes.

What each engine pays for the strict class is measured on the bench host and printed by the durability table.

**F11. Equivalent queries must return equivalent answers.** A benchmark that never checks the answer measures how fast an engine can be wrong: an adapter that dropped a filter, a group or a join condition would print a lead rather than a bug (DECISIONS #88). Recall against ground truth on the two vector lanes and the torn-state comparison in the cross-model trial are the only other cross-engine correctness checks.

Every timed query whose answer is deterministic records a canonical digest of that answer, a row count, and a short readable sample, written by `bench_common.result_digest`. Three rules make the check mean something:

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
  neighbours at SF0.01 and disagrees at SF1 on the same correct answer. Counts stay
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

The cold number is one per CELL, not one per query, because the cold question is about the session: `cold_first_query_ms` and `cold_first_query_name`, from the first query the cell ran after the database opened (on the two vector lanes a WARMUP query, which is why it is the cold one). The rows also keep `cold_<q>_ms`, `warm_<q>_p50_ms` and `warm_<q>_p99_ms` per query under one naming convention across every lane.

Where a measurement genuinely does not apply the row carries a stated reason in
`cold_warm_na` rather than a blank cell, and the strings are defined once in
`bench_common` so two lanes cannot phrase one exemption differently: a
transactional cell has no cold and warm split because every operation runs
against an already-warm database by construction; the lifecycle lane is itself
the cold measurement; the two vector lanes warm on a held-out slice before they
time anything, and their cold and warm columns come from the multipass driver.

**F13. Close cost is an invariant, not a column.** Close should be O(what was written), not O(what is stored), and on the order of 100 ms; the reasoning, the situations, and the numbers are PAGE-SPEC.md section 4 (DECISIONS #50). Checked by `fairness_check.check_close_cost`, which prints under this number; `test_fairness_headers.py` holds the numbering against this file.

**F14. Equivalent queries get equivalent index support, and the support is chosen by MEASUREMENT (DECISIONS #112, BUGS F98).** Every engine reaches a query through some access path, and which path it gets is a choice this harness makes on its behalf. That choice was once made by reasoning about what ought to help, and it was wrong in both directions at once: an index worth **6.1x** to ArcadeDB on Q6 was withheld from PostgreSQL, which gains **2.5x** from it, and given to SQLite, which it costs **20%**.

The rule is NOT "every engine gets the same index". That is the obvious repair and it is wrong: the same Q6 index costs ArangoDB 29% and SQLite 20%, because at 14% selectivity an index lookup plus row fetches is dearer than the scan it replaces, and how dear depends on the engine. It is the rule F7 already uses for ArangoDB's IVF vector index, which has no degree to match: **matched by effect**. Each engine gets the configuration that is genuinely best for it, the decision is a measurement rather than an argument, the row records what was built, and the build time is published rather than folded into ingest so the cost of the choice is visible. The per-engine decisions are in PROTOCOL.md section 7 and the measurements in BUGS F98, per engine, as ratios within one engine and not a comparison between engines.

**The composed embedded stack (2026-10-25) declares all of this per store.** SQLite, LanceDB and LadybugDB each get the access path that is best for them on the lane's `pid IN` reads, and the declaration is in `fairness_check.INDEX_DECISIONS["e2"]` (SQLite's rowid, LadybugDB's primary key, LanceDB's BTREE with its measured ratio); the vector index is fp32 `IVF_HNSW_FLAT` at the table's HNSW settings (F7; no quantized arm, the paper's rule); durability is SQLite's class plus two named engines with no setting (F10); parallelism is LadybugDB's fitted threads and pool, SQLite single-threaded and LanceDB's own (F6). What the arm cannot guarantee is written in COMPARATORS.md ("The composed embedded stack"): no transaction spans the stores, which is the point of the arm.

What makes this checkable rather than a good intention:

* **A new arm must declare its index decision.** `fairness_check` fails a lane backend that declares nothing. Silence is the state this invariant exists to remove.
* **The declaration is checked against the rows, not trusted (F14b).** `index_s` on an arm's rows is the evidence for its declaration. The gate fails an arm whose declaration cites a measured with/without ratio and whose every row records `index_s=0`, and fails one that declares `NONE` and records a build. Only those two directions are asserted: a declaration with no build step to time is reported as not asserted rather than pattern-matched into an expectation. The count of arms checked, not asserted, and predating the ingest/index split is printed every run.
* **Where one arm times the two phases, every arm does (F14c).** A new `build()` that does not split leaves a blank in a column the other arms fill, and a blank in a benchmark reads as a result. Three states pass: the arm splits, or it declares `index_before_load` (the index is defined before the first row lands, as SurrealDB's is on the document and time-series lanes), or no arm on that lane splits at all. The finding is the fourth: a lane where some arms split, one does not, and it says nothing. On the dense lane the two phases are independent timers inside `build_s`, so those rows also carry `setup_s` for the remainder (BUGS F101).
* **ArcadeDB's id indexes follow the vendor's rule for the index kind (ArcadeData/arcadedb#9169, PROTOCOL.md section 7).** An id a workload only looks up by equality is `UNIQUE_HASH`; a key also ranged over or ordered stays `UNIQUE`. Each comparator keeps the primary-key or default index its own maintainers give it, so this is the same footing and not a knob only ArcadeDB gets. It moves both ways, and the table says so in a generated sentence. `fairness_check.ARCADEDB_HASH_ID_INDEXES` is the one registry of which ids those are, and `test_index_kinds.py` holds it equal to the `CREATE INDEX` text in each lane. The registry is the claim and the row is the evidence (F14d): each ArcadeDB arm on those lanes records `index_kinds`, the engine's own `SELECT FROM schema:indexes` answer, a stamped row with another kind is a failure, and a row without the stamp is a failure since the 26.10.1 measurement started (`INDEX_KINDS_GATE_FAILS`, now `True`). The page sentence is built only from rows that carry the stamp.
* **The decision names its evidence.** "No index" is a finding when it is measured (ArangoDB, DuckDB on the document lane) and a defect when it is an omission.
* **Index build time is its own column** wherever the engine has a boundary to time, because folding it into ingest hides both the cost and the asymmetry: SurrealDB's document arm must build its index BEFORE the load, so about 5.3 s of index work sits inside an ingest number every other engine pays without any.

**F15. A setting this benchmark overrides is on the row and under the table (CAMPAIGN.md section 7, item 21).** PROTOCOL.md section 7 lists every default that is overridden. Each override a table shows is registered in `override_registry.py` (the arms that run it, the row field their adapter reads back from the engine, the value the sentence claims, and the generated sentence), and three checks hold it: `fairness_check` F15 fails a 2026-10 row of such an arm that lacks the field or carries another value, `page_check` fails a table that shows such an arm and prints no sentence saying so, and `test_overrides.py` fails when a PROTOCOL.md section 7 row says NOWHERE or cites a registration that does not exist. The registry and test docstrings carry the mechanics. Two limits: the served ArcadeDB's `addHierarchy` has no read-back at this pin, so its field records the request and says so; and the registry shows that an override can be found, not that it is justified. No sentence says which way an override moves a number.

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

## Memory and disk per phase are read the same way for every engine

The question a memory column answers is "what did this engine hold, at the end of this phase", and the answer has to come from something every engine has and none can change. That is the cgroup of the container the engine runs in: `anon` plus `shmem` at the end of the phase, summed over the cell's containers (the server's and the client's for a served engine, the client's alone for an embedded one), read by the runner from the host. The headline column is that number and nothing else. Page cache is context and stays out for every engine alike. Disk and IO follow the same rule: the headline is the bytes of the container that holds the engine's data, less its empty start, and the bytes that container's cgroup read and wrote since the previous phase, both from the host and both defined for every engine whatever its storage layout. The write-ahead log is found by file name and is context only, because naming it is a per-engine table.

What a runtime exposes beyond that is recorded and never ranked across runtimes. A JVM engine gets its heap at the end of each phase (used, committed, direct buffers where visible), after a forced full GC only at the end of the last timed phase and in idle, never right before a timed phase, so no JVM engine starts a timed phase on a freshly collected heap that a native engine does not get (the row's `jvm_forced_gc_phases` says which phases were collected, and a heap read without a GC is named `jvm_<phase>_used_mib`, not after-GC); an embedded engine gets its own process's anonymous pages and resident set. Nothing is done for a native engine that is not done for a JVM one before a timed phase. The GC is an extra reading about the JVM, taken after the timed work so that its working set can be told from the heap it was given; the headline reading of a JVM engine at `queries` follows it, as a native engine's follows its own allocator's state at the same moment. A native allocator that keeps freed pages (glibc arenas, jemalloc) stays as it is: the harness does not trim it, and that difference is a property of the engines.

A pinned heap (`-Xms` equal to `-Xmx`) is a resource decision that moves the kernel's reading to the cap, whatever the workload. It is why the memory column of a pinned JVM arm reads its pin. The ArcadeDB arms, embedded and served, are not pinned, so their headline is what the engine grew to; the other served engines start with the heap their vendors' documentation gives, and the row says which. Any engine's row can be read without the JVM numbers, and no JVM-only number is ever the headline.

**GATE** `test_memory_probe.py` (parsers on synthetic cgroup, smaps and `jcmd` input; the lane and host handshake; a row stamped by an earlier instrument has no new field).

## Allowed to differ (must be DISCLOSED, per PROTOCOL.md section 7)

- **Vendor settle steps** that have no equivalent elsewhere (Elasticsearch forcemerge, Milvus seal+index wait+compaction+load, Qdrant green-wait, ArcadeDB `COMPACT INDEX`). Each engine gets *its own*; none goes unmatched by the others having theirs. The one settle step this harness defines rather than a vendor is the SurrealDB server's HNSW wait on the dense and cross-model lanes, a latency probe recorded as `settle_s` (BUGS F134, DECISIONS #117), and PROTOCOL.md section 7 lists it as such.
- **Operating points deliberately not matched**, such as the dense fp32 arms with the build cache pinned to the corpus against INT8 at the engine default (DECISIONS #56), stated in the l3d condition.
- **Quality and precision differences** (int8 against fp32 postings, ES pruning). Report recall next to latency, always. The 2026-11 paper queue (profile `paper-2611`, 2026-10-25) stages the dense lane at fp32 for every engine and no int8 or PQ arm: quantized arms are not like-for-like across engines (each engine's scalar, product or binary code is its own setting), quantization is out of the paper's scope, and ArcadeDB's own INT8 and BINARY are out by the owner's rule (jvector PQ, BQ and NVQ are studied after the paper). The second list (sparse, time series, lifecycle) is not staged either. `make_2611_stages.py --check` lists what is dropped and proves none of it is scheduled.
- **Product quantization arms (2026-11 instrument, `BENCH_DENSE_PQ=1`).** One PQ setting per engine family (32 subspaces of 256 centroids on 128-d), matched as closely as each engine allows and stamped on the row (`pq_subspaces`, `pq_clusters`, `pq_rerank`); the re-rank is each engine's own (ArcadeDB's default, Qdrant `oversampling`, Milvus `refine_k`, none for ArangoDB's FAISS factory), so recall sits next to latency and size in their own row family. An ArcadeDB PQ arm runs only on a build whose SQL accepts `rerank`; on any other it refuses (QUANTIZATION.md). The paper queue (`paper-2611`) stages no PQ arm even with the variable set.
- **Intra-query parallelism at each engine's default.** ArcadeDB's SQL scans a type's buckets in parallel (`arcadedb.queryParallelScan`, on by default) only when the type has at least two buckets, and `arcadedb.typeDefaultBuckets` is 1. Every ArcadeDB type in this benchmark is created with the default except the document lane's `LineItem`, which gets `cores - 1` buckets to match its async load workers (CAMPAIGN.md section 7, row 10; the value is on the rows as `lineitem_buckets`). From 26.10.1 (PR #8524) one bucket is split into page ranges across the workers, so a scan outside a transaction runs in parallel at the engine default. Not tuned: the bucket count is a knob that moves only ArcadeDB, so the default stands until a campaign decides otherwise (CAMPAIGN.md section 7, item 10). A served ArcadeDB read through `POST /api/v1/command` runs inside an auto-commit transaction, where a scan never runs in parallel (ArcadeData/arcadedb#8775); the served reads go through `POST /api/v1/query` (CAMPAIGN.md section 7, row 25, BUGS F163).
- **Matched recall is the fair dense headline.** At one beam setting two engines sit at different recalls, and the cheaper answer reads as the faster engine; the beam is also the one knob every engine has under a different name and a different scale. ANN-benchmarks practice is to fix the recall and compare latency, so the dense table's headline is the lowest p50 among the sweep passes that reach recall@10 0.95 (0.90 and 0.99 beside it), with the beam that reached it printed, and the full recall-latency curve kept in the rows. Nothing is tuned per engine except that beam, over the same list for every HNSW engine; an engine that cannot reach the target is marked, not shown at a lower recall. Engines with no beam setting run once and say so (PROTOCOL.md section 2).

Anything else that differs is a defect, not an override.

## Bespoke drivers investigate, lane scripts publish

Both fairness violations ever found in a published table were rows a bespoke driver produced rather than the lane script: a driver is written to answer a narrow question and carries whatever protocol its author needed at the time, and is then promoted to a cell. Every clean lane puts each backend through one script, so warmup and settle are decided once and apply to everyone. L3d and L3s's warm columns are the two places that still publish overlay-driver rows (`dense_multipass_driver.py` and `sparse_multipass_driver.py`, run through the runner). If a driver's output must become a cell, diff its protocol against the lane's first.

## A CPU percentage is a fact about a container, not about an engine

ArcadeDB's sparse build runs at roughly 2 of the 12 allocated cores, and that is a harness property rather than an engine property: `ArcadeEmbedded.build` in `l3_sparse.py` is a serial Python loop calling `newDocument`/`save` per document, so about one core is a single producer thread and the rest is engine background work. The engine was never asked for more.

Nor is it an unfairness. Qdrant, Milvus and Elasticsearch drive ingest from the *same* serial `gen_docs` loop, batching into `upsert`, a bulk-import file writer (Milvus, since 2026-10-22: Parquet through `RemoteBulkWriter` into its MinIO, then one import job, the vendor's documented path) and `bulk`. The producer is symmetric; what differs after the handover is architectural (in-process per-document JNI against one client call per batch to a server that parallelises internally), which is the deployment axis the page already reports. What survives is narrow and ours: embedded pays N JNI crossings per batch where a client pays one, and upstream #5577 bounds the dense cost at roughly 7% of insertion.

Attributing a CPU percentage requires knowing who was asking for the work.

## An exit code is not evidence

`rc == 0` means a process finished, not that it measured what you asked for. Two defects of that shape: a queue script that set only `BENCH_DATA` left `l3_sparse.py` on its synthetic fallback generator and produced 94 rows across three tiers, every one `rc=0`, distinguishable from the real corpus only by the absent ground truth; and the F3 heap, where cells produced rows, stages reported OK, and the artifact asserted a heap the engine never had.

Acceptance has to compare the DATA against the specification, because every one of these produced output that looked exactly like success:

- A **container-side preflight** asserts, from inside the container, that the lane sees the corpus it was told to use and accepts the scales it will be passed. Checking the host path is a different check: a run once lost 20 cells to a directory that existed on the host and not at the mount point.
- Every sparse stage is **verified against the data it produced**, recall present and `n_docs == 8_841_823` at medium, not against its return code.
- `load_canonical` drops any sparse row without a recall number, before the dedupe, so an unpublishable row cannot shadow a publishable one.

Prefer the loud failure. The same script that wrote those 94 quiet rows also crashed the graph lane outright, and that failure cost 80 cells and was worth far less than it looked, because it was loud.

## Still open

Whether any engine's disk IO scheduling differs under the same cap (CAMPAIGN.md section 7, item 20).

- **Multi-container deployments share the cell's cap (Milvus compose, 2026-10-22).** Every engine's server side gets exactly the cell's memory cap. Milvus's three containers split it (etcd 512m and MinIO 1g out of the cap, the rest to Milvus), and the memory, CPU, I/O and disk figures on its row cover all three, so neither the budget nor the measurement flatters or handicaps the deployment. `test_milvus_compose.py` asserts server + sidecars == cap for every backend with sidecars.
