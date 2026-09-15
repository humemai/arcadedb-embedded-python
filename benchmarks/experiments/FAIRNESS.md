# The fairness contract

Every number on the page compares systems. A comparison is only worth printing if both sides were given the same thing. This file says what "the same thing" means, what is allowed to differ, and what is checked mechanically rather than remembered.

`fairness_check.py` is one of the four gates `refresh_web_page.py` runs. It fails loudly rather than warning quietly.

The failure mode this contract exists to close is **a correct number measured under conditions the row beside it did not get**. `claims_check` and `provenance_check` cannot see it: both verify a number against its own artifact, and such a number is correct about its own run.

## Invariants (must hold; checked)

**F1. Same cpuset.** Every container in a published cell gets the full `0-11` (the 12 P-threads on 6 physical P-cores). Client and server topologies share that cpuset deliberately, so CPU competition stays inside the deployment under test rather than being hidden by giving the server its own cores.

**F2. Serial only.** Published cells run one at a time. `runner.py` forces `workers=1` on the paper tier and errors otherwise; queue scripts enforce it again with `guard()`. The parallel sweep tier (disjoint cpuset shards, shuffled order) exists for exploration and must never reach a table. A published row from a sweep is detectable after the fact as a partial cpuset such as `0-5`, and `load_canonical` drops it.

**F3. Same memory envelope per (lane, scale).** Every backend at a tier gets the same `--memory`/`--memory-swap` cap and, for JVM engines, the same heap.

A served backend gets the **full tier cap** and the client its own `BENCH_CLIENT_MEM` budget on top, stamped `mem_split="full+client"`, so a served engine sees exactly the cap an embedded engine of the same tier sees. Every frozen served row carries that stamp. `BENCH_SERVER_MEM_FRACTION` restores the older `server = 0.75 * total` split for a reproduction. Compare a served topology by `srv_cap / mem_split`, never by adding client and server: addition reads 1.75x the envelope.

**"Same heap" means the heap the engine RAN, not the heap the cell asked for.** A row stamps `heap` from the request, so a hardcoded server heap is invisible in the artifact; Elasticsearch ran 4g at three tiers while its comparators scaled 4g, 8g, 16g, stamped `heap=16g` throughout. `observe_server()` closes it by reading the container's real `-Xmx` back out of `docker inspect` into `server_heap` and failing any cell where the two disagree. Rows without that witness are dropped from published tables by `load_canonical`, so a tier shows a gap rather than an unfair number.

The check is honest about its own limit: it reads the container's ENV, which is what we passed in, not the JVM's live heap. It proves the plumbing, not the obedience. The stronger form is to ask the engine (Elasticsearch reports `jvm.mem.heap_max_in_bytes` from `/_nodes/jvm`) and is still owed.

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
| **DuckDB** | default `threads`=20 under a 12-CPU cpuset in the real bench image | **HOST-DERIVED.** Fixed in `l1_tabular.py` only; l1_tpc, l3d and l4 still run oversubscribed |
| Qdrant | `actix-rt` runtime 11 threads, update pool ~11, from `/proc/<pid>/task` | cpuset |
| Elasticsearch | `_nodes/os` reports `available_processors: 12`, `allocated_processors: 12` | cpuset |
| Neo4j | 10 `GC Thread#N`; G1 derives `8 + (N-8)*5/8` above 8, so 12 CPUs gives 10 | cpuset |
| ArcadeDB (JVM) | `availableProcessors()` reads the cgroup on Java 11+ | cpuset |
| Chroma, LanceDB, sqlite-vec | embedded in the driver, no separate server pool | n/a |
| Milvus | `go_sched_gomaxprocs_threads 12`; Go sizes from `sched_getaffinity` | cpuset |

Not yet audited: every comparator added since (MongoDB, TimescaleDB, pgvector, PG+AGE, SurrealDB, SQLite, and ArangoDB).

Two ways to get this audit wrong, both nearly recorded. Total OS thread count is not pool sizing: a JVM server runs dozens of threads irrespective of cpuset, so the question for a JVM is `availableProcessors()` and the named pool settings. And running `nproc` inside a container answers about the container, not about the engine: ask the engine's own metrics.

The DuckDB bias runs **against** DuckDB, which wins that lane regardless, so nothing self-serving rests on it; the tabular rows are re-measured at each freeze rather than carried over.

**F7. Same effective base-layer degree across dense backends per scale.** Engines spell graph degree differently: one takes the per-layer `maxConnections`, another the base-layer degree, and the same integer therefore builds two different graphs. Recorded per row as `degree_param` plus `degree_family` so the check reads the number in the unit its own engine meant. A row recording no degree FAILS.

*The other construction knob, and why it is NOT matched.* ArcadeDB builds through jvector, which also exposes `neighborOverflowFactor` (engine default 1.2): how far above `maxConnections` a neighbour list may grow during construction before pruning. Raising it to 2.0 cuts graph-unreachable nodes 3.5x at no measurable cost (50k x 128, `maxConnections=32`: 299 orphans at 1.2, 85 at 2.0, build time, peak RSS and recall flat). It stays at the default anyway. Cheap is not the test; "is there a matched value on the other side" is, and there is none, because no hnswlib-family comparator has this knob. Setting it would move our graph alone, in our favour, which is what separates it from the `maxConnections` 32-against-16 correction: that one converts units between two engines that mean different things by the same integer. Recorded as DECISIONS.md #45.

*An index with no degree is matched by effect.* ArangoDB's vector index is FAISS IVF (inverted lists over trained centroids), so F7's degree has no counterpart and a nominal match is impossible. Its operating point is chosen to land on the same recall instead: `nLists` is FAISS's own guideline for 1M to 10M vectors, `round(4*sqrt(n))`; `nProbe` is calibrated inside the cell, after the index is built and before any timed pass, by binary search on a held-out slice (fixture queries 1000:1200 with their ground truth; both fixtures ship 10,000 and the lane times the first 1,000, so the timed pass never sees them and the cold pass stays cold) for the smallest value whose recall@10 reaches the target; and the target is read from the frozen CSV, the median recall@10 of ArcadeDB's own embedded fp32 arm at the same scale. Matching our own arm is the neutral choice: a higher target slows them and flatters us, a lower one speeds them and flatters them. The row records `ivf_nlists`, `ivf_nprobe`, `ivf_recall_target`, `ivf_recall_target_source`, `ivf_calibration_recall`, `ivf_calibration_queries`, and `ivf_calibration_slice`; `degree_family` says `ivf_flat_no_degree`, and `fairness_check.py` accepts that family only when the target is present and the calibration recall is within 0.01 of it. The lane and the multipass driver call the same hook in `arango_common.py`, so the two cannot drift. The cross-model lane measures no recall and keeps the uncalibrated starting fraction, recorded on its row as well.

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

**F9. A kept row needs a control, because the host is not an invariant.** F1 to F8 and F10 to F12 constrain a cell's *configuration*; none constrains *when* it ran. A row printed tonight beside one measured five weeks ago is fully compliant and still potentially wrong, because the kernel, the docker version and the machine's thermal history all moved and, apart from the thermal fields every row has carried since the queue scripts pulled them on 2026-09-14 (BUGS.md F45), none of that is recorded as a run condition.

So when a campaign re-measures one engine and carries the others forward, **re-run one untouched comparator as a control and show it reproduces its kept numbers within run-to-run spread.** One extra cell buys evidence for every row that was not re-run. If the control does not reproduce, the carried-forward rows are not usable and the whole tier is re-measured. Record the control's old-against-new delta next to the table it licenses, so a reader can see the carry-forward was checked rather than assumed.

**F10. Same durability class per table, and one instrument.** A commit that waits for the disk and one that does not are different operations, so a write latency is a comparison only if every engine in the table committed the same way. From the 2026-10 instrument (DECISIONS #81) the matched class is **relaxed**: a commit returns without waiting for the disk and the log is flushed by the engine's own background policy, which loses the last committed transactions on a power cut but does not corrupt the store. That is ArcadeDB's own default at `txWalFlush=0`, so the comparators are matched to it rather than it to them: SQLite and sqlite-vec run WAL with `synchronous=NORMAL`, the PostgreSQL family runs `synchronous_commit=off`, MongoDB's timed writes run at `w=1, j=false`, and ArangoDB, QuestDB, and SurrealDB embedded run their own defaults, which are already in this class. Every one of those settings is read out of the engine rather than assumed, and each row records what it ran as `durability`.

**Neo4j is the exception the decision names**: it flushes its log at every commit, has no setting to relax it, so it runs as it is and its graph and cross-model tables say it is the one engine waiting for the disk, rather than leaving it silently advantaged or disadvantaged. The same read-out-of-the-engine check put LadybugDB and DuckDB in the strict class too, and each table's durability condition is generated from the engines that table shows. SurrealDB served 3.2.4 exposes no durability setting at all, so it is in neither class and its row says so instead of claiming one.

`fairness_check.check_durability` refuses a 2026-10 row carrying no `durability`, a strict string on an engine that has the knob, an unverified string on an engine not named above, and two `instrument` values in one table. The relaxed setting is a real deployment mode every one of these engines documents, it is matched on every engine that has the knob, and the one that cannot match is named: that is the whole fairness argument, and it is not re-litigated per table.

Since DECISIONS #90 every timed write runs at both settings and the page carries both classes rather than choosing one, so the invariant is that a table's engines share a class and not that only the relaxed one is measured; ingest stays at a single setting on every lane (#90a).

**F11. Close cost is an invariant, not a column.** Close should be O(what was written), not O(what is stored), and on the order of 100 ms; the reasoning, the situations, and the numbers are PAGE-SPEC.md section 4 (DECISIONS #50). Checked by `fairness_check.check_close_cost`, which prints under this number.

**F12. Equivalent queries must return equivalent answers.** A benchmark that never checks the answer measures how fast an engine can be wrong, and an adapter that silently drops a filter, a join condition, or a group reads as a lead rather than as a bug. So every timed query with a deterministic answer records a canonical digest of it (order-insensitive unless the query defines an order, floats rounded before hashing, a readable sample kept beside the digest), and `equivalence_check` refuses a table whose engines disagree at one scale. A query an engine cannot express is declared absent in its adapter and named by the gate, never skipped. The vector lanes keep recall against ground truth, which is the stronger check for an approximate index, and the cross-model lane keeps its torn-state comparison; its two read paths are checked by recall against a brute-force answer over the same filtered candidate set, with the graph and document halves digest-compared exactly (DECISIONS #82c, #88).

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

- **Vendor settle steps** that have no equivalent elsewhere (Elasticsearch forcemerge, Milvus flush+load, Qdrant green-wait, ArcadeDB `COMPACT INDEX`). Each engine gets *its own*; none goes unmatched by the others having theirs.
- **Operating points deliberately not matched**, such as the dense fp32 arms with the build cache pinned to the corpus against INT8 at the engine default (DECISIONS #56), stated in the l3d condition.
- **Quality and precision differences** (int8 against fp32 postings, ES pruning). Report recall next to latency, always.

Anything else that differs is a defect, not an override.

## Bespoke drivers investigate, lane scripts publish

Both fairness violations ever found in a published table were rows a bespoke driver produced rather than the lane script: a driver is written to answer a narrow question and carries whatever protocol its author needed at the time, and is then promoted to a cell. Every clean lane puts each backend through one script, so warmup and settle are decided once and apply to everyone. L3d is the last lane that still publishes an overlay-driver row (`dense_multipass_driver.py`, run through the runner). If a driver's output must become a cell, diff its protocol against the lane's first.

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

Whether any engine's disk IO scheduling differs under the same cap.
