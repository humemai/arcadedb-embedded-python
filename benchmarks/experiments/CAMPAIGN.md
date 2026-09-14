# Running a campaign

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
2. **Small.** One tier up, N=5, real corpora, every metric recorded. This is where the gates run for the first time: `provenance_check`, `fairness_check`, and `page_check`.
3. **Big.** The published tiers.

A stage that produces rows no gate admits has failed even if every cell exited 0.

## 3. What every cell records

Beyond the lane's own metrics:

- **Memory.** `peak_anon_mib_sum`, `peak_shmem_mib_sum`, `peak_owned_mib_sum` (anon + shmem), summed across every container in the cell. Anon alone misses a POSIX-shmem buffer pool entirely.
- **Disk.** `SizeRw` plus `du` over the daemon-reported volume mounts, with a settle loop requiring two readings within 1%. A volume in an image with no `du` is sized from a helper container (BUGS.md F38).
- **IO.** Cumulative `rbytes`/`wbytes` from `io.stat`.
- **Phases.** `build_s`, settle, query generation, ground-truth load, search wall, recall computation, and `phases_accounted_s` so unexplained time is visible rather than absorbed. The dense and sparse lanes also split `ingest_s` from `index_s` where the engine has the boundary. Every lane prints `PHASE` markers as it goes, so a cell killed by its timeout still says which phase it was in.
- **Cold and warm**, separately, in every lane that has a repeat pass.
- **Envelope.** cpuset, memory cap, heap, observed server heap and page cache, `mem_split`, image digest, engine version, engine commit.

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

## 6. The live chain

The September chain on mini, each script waiting on its predecessor and gated on `verify_pair_c25.sh`, at pin `8d6af9475`:

`qDO` (running, its dense stage) -> `qDP` -> `qDQ` -> `qDR` -> `qDS` -> `qDT` -> `qDU` -> `qDV` -> `qDW` -> `qDX`, ending about 19 September.

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
| qDX | one phase-marked re-run of the embedded SurrealDB 1M dense cell, expected to time out again, for the phase it dies in (BUGS.md F41) |

Finished scripts move to `~/queue_archive` on mini. The chain holds its pin start to finish; an upstream fix landing mid-run becomes a candidate for the next re-pin, never a restart. October's campaign is DECISIONS #74 as amended by #81 to #86, and starts with the comparators.
