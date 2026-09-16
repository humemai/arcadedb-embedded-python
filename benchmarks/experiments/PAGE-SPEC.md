# Project page spec: what the page contains and what each cell must satisfy

The page at `humem.ai/projects/arcadedb` is the PRIMARY artifact. There is no paper; "page material" is the only kind. This file is the contract: what tables exist, what rows and columns they carry, which figures are published, and what a cell must satisfy to be printed.

`PROTOCOL.md` says how a number is produced. `FAIRNESS.md` says when two numbers may be compared. This file says what gets shown. If they disagree, PROTOCOL wins on production and FAIRNESS wins on comparison; this file never licenses a cell those two would refuse.

---

## 0. The rules every published cell obeys

1. **Serial, full cpuset.** Every published latency, throughput, percentile, and memory cell runs one at a time on mini's `cpuset 0-11` (the 12 P-core THREADS on 6 physical P-cores; see 0a), `workers=1`, `tier=paper`. Parallel shards exist for sweeps and exploration only and may never reach the page. Enforced: `runner.py` refuses `workers != 1` at paper tier; `load_canonical` drops partial cpusets.
2. **N=5, median [min-max].** Five repetitions per cell. Any table with a cell below n=5 states its n in a condition, and no page sentence may assert an n that a cell it covers does not meet. Per-table operation and repetition counts are generated conditions (`export_web._counts_note`), never typed.
3. **One engine commit per table.** Every ArcadeDB row in one table comes from the same upstream commit, stamped as `engine_commit`. Comparators are digest-pinned images. See section 1. Enforced at production time: `runner.py` refuses a paper-tier ArcadeDB run when `ARCADEDB_ENGINE_COMMIT` is unset, before any cell starts, and `bench_common.run_conditions()` reads it so bespoke probes carry it too. A rule the page depends on may not be a printed reminder to a human.
4. **One corpus per table.** Every row in a table describes the same dataset at the same size. A table whose rows disagree on `n_docs` (or the lane's size field) is a defect, not a comparison. The fingerprint must come from the corpus the lane loaded, not from a module constant (`l2_graph.py` and `l3_sparse.py` point it at the loaded data; BUGS.md F6 is the sparse lane running the synthetic corpus under a paper label).
5. **A knob the campaign sets must reach the cell, be honoured by the lane, and resolve inside the container.** `runner.py`'s env passthrough is a CLOSED tuple: a knob absent from it silently runs the in-script default. Three checks, each of which has failed once: DELIVERED (diff every lane's `environ.get("UPPER_CASE")` against what the runner passes), HONOURED (an unknown mode is a hard error, not a silent fallback to a literal default), and RESOLVED where the process runs (the mount is printed in the preamble and a missing corpus is refused on the host). Run the delivery diff whenever a lane gains a knob.
6. **The config PROFILE is recorded on every row.** ArcadeDB ships profiles that rewrite defaults wholesale: one sets `VECTOR_INDEX_GRAPH_BUILD_CACHE_SIZE=-1` with both cache heap percentages at 50, another pins both caches to a flat 10,000, against a default of `graphBuildCacheSize=0` (auto) and `graphBuildCacheMaxHeapPercent=25`. The profile can move a build by 4.7x on its own (10% against 25% at deep10m: 10,786 s against 2,274 s), so two rows under different profiles are not comparable. The percentage applies only on the AUTO path; quoting it for a run that pinned an absolute cache size is wrong.
7. **A probe must measure the thing its column is named after, and a bespoke stage must not hardcode a condition the lane derives.** A read that costs about as much as an empty query did not reach the structure, and a write whose index-entry count does not move did not land; assert both in the lane rather than trusting the query text (the `graph_gav` read once ran in SQL, which cannot reach a Graph Analytical View, and the sparse read was a `count(*)` that never touched the index: 1.6 ms against 234 ms on the same fixture). A stage that sets by hand any condition the lane computes (heap, cpuset, tier) has to say so on the row, and a comparison spanning stages has to check that the conditions match. Consequence today: the lifecycle `graph_gav` situation is withheld (`export_web.LIFECYCLE_WITHHELD`) because its corrected read changed scope from 100 seeds to an unbounded whole-graph 2-hop; it needs a bounded seed set and a per-cycle assertion that the view was used before it can print.

---

## 0a. The machine

Every published number is measured on **mini**. The laptop is a development host: it compiles, it runs probes, and nothing it produces reaches the page.

| | mini (bench host) | laptop (dev only) |
|---|---|---|
| CPU | 12th Gen Intel Core i9-12900HK | Intel Core Ultra X9 388H |
| topology | 1 socket, 14 cores, 20 threads: 6 P-cores with SMT (12 threads) + 8 E-cores | 16 cores, 16 threads, no SMT |
| `cpuset 0-11` | the 12 P-core threads, verified by max frequency: cpu0-11 report 4900 MHz, cpu12-19 report 3800 MHz | **NOT the P-cores here.** The kernel reports `cpu_core = 0-3`, `cpu_atom = 4-15`, and max frequency agrees: cpu0-3 at 5100-5200 MHz, cpu4-11 at 4000, cpu12-15 at 3700. `0-11` on this machine is 4 P + 8 E, mixed. Laptop probes pin `0-3`. |
| RAM | 64 GiB installed (61.3 GiB usable) | 30 GiB |
| storage | Samsung SSD 980 PRO 2 TB NVMe (root, `/home`, `/var/tmp`, all bench data) | Samsung MZVL22T0HDLB 1.9 TB NVMe |
| OS / kernel | Ubuntu 26.04 LTS, 7.0.0-30-generic | Ubuntu 26.04 LTS, 7.0.0-29-generic |
| Docker | 29.7.2 | |

Four things about that table are load-bearing and must be said on the page, not just recorded here.

**`cpuset 0-11` is 12 THREADS on 6 PHYSICAL CORES, not 12 cores.** SMT is on (`/sys/devices/system/cpu/smt/control` = `on`). A reader who assumes 12 physical cores will over-estimate what a parallel build had available, and every "12-core" phrasing in our own prose is wrong.

**`cpuset 0-11` means something DIFFERENT on the two machines.** On mini it is the P-core threads. On the laptop the kernel says `cpu_core = 0-3` and `cpu_atom = 4-15`, so the same string selects 4 P-cores plus 8 E-cores. Laptop probes pin `0-3`; anything published re-runs on mini anyway, so the two never need to mean the same thing, only to be stated.

**Frequency is not pinned.** The governor is `powersave` and turbo is ENABLED (`intel_pstate/no_turbo` = 0), so a long build and a short query do not see the same clock. This is a mobile-class part in a small chassis, so sustained all-core work throttles in a way a server part would not. It is why every published number runs SERIAL: co-scheduling on this host does not merely add noise, it changes the clock the other cell sees.

Measured on 2026-09-14 (BUGS.md F45): under a long build the package bounces off its thermal ceiling at 89 to 90 C while the busy cores hold 4.3 GHz, and the kernel counted 23.7 s of throttling in a 90 s window. The power mode stays as the machine ships, because pinning the clock would lower every absolute number on the page, and every row instead records `host_temp_c_start` and `_end`, `host_throttle_count_start` and `_end`, and `host_throttled_ms` as the evidence. No protocol change is pending on this.

**The 7.3 TB disk is not the bench disk.** `/dev/sda` is rotational and mounted at `/mnt/hdd8tb` for backups. Everything measured lives on the NVMe. A reader seeing a spinning disk in a machine listing would reasonably discount every I/O number, so the split has to be explicit.

The page's setup section is this block, read from `lscpu` and `lsblk`, not derived from a row. The payload's `hosts_recorded` list is container ids annotated "(host unknown)" on every lane except sparse and dense, because a row records a container, not a host; it is not rendered. From the 2026-10 instrument every row records `bench_host`, which the runner refuses to leave unset at paper tier (DECISIONS #74).

## 1. Engine identity: commit, not version

ArcadeDB is pinned by **upstream commit SHA**, not by a release number. The build line reads `26.9.1.dev0` for every commit, so a version string cannot identify what ran, and printing one while claiming the page ships the upstream engine unmodified is a contradiction.

- Every row carries `engine_commit` (short SHA of the upstream commit the wheel and server image were both built from).
- The page prints it as the engine identity, linked to the commit on GitHub. Every ArcadeDB row is named from its own engine string and commit (`arcadedb 26.9.1-dev · 8d6af9475`), never from an image tag; served rows carry the row's `server_image_ref` (BUGS.md F16, F32). The page header lists the identities actually present.
- Embedded and server arms in one table are built from the SAME commit, paired, and run the same JVM (DECISIONS #54).
- A campaign FREEZES one commit and holds it start to finish. Upstream landing a fix mid-run does not restart the campaign; it becomes a dated changelog entry and a candidate for the next re-pin.
- Re-pinning is a deliberate, dated act recorded in the changelog with what moved. No table falls back to an older pin, anywhere (DECISIONS #62).

Comparators are pinned by image digest and carry a version name, recorded per row from the image they ran on. A comparator row with `version_name: null` is not publishable. Embedded comparators name the engine core, not the SDK (BUGS.md F39).

---

## 2. Tables

The generated block "Published tables" at the end of this file is the list of tables, rows, sizes, and columns on the page; `refresh_web_page.py` rewrites it from the payload on every publish. The hand-written tables below say what each table is for and which arms are still to land. Every table needs: an id, a title, a dataset line, explicit columns, explicit rows, a source link to a tracked artifact, and its conditions, which include the generated per-table operation and repetition counts beside the typed ones.

The columns below are the 2026-10 instrument's, which carries the forty operations of PROTOCOL.md section 2 (documents 6 OLTP and 5 OLAP, graph 7 OLTP and 5 OLAP, dense 3, sparse 1, time series 5, cross-model 4, and lifecycle 4) and the one measurement set of DECISIONS #89: cold and warm latency at p50 and p99, throughput where the operation has a rate, recall where the index is approximate, peak memory, on-disk size after the workload, and ingest and index build as separate columns on the vector tables. A table that omits one of those states why in its conditions, which `page_check` enforces. An operation an engine cannot express is a declared absence (DECISIONS #88): the cell is a dash and the condition names the engine and the operation, so it cannot be read as a slow engine or as a gap still to be filled. SurrealDB server rows on every table that has them re-run for their disk reading in qDW (BUGS.md F38); the new rows supersede the old at merge. The queue chain that lands the arms named below is CAMPAIGN.md section 6. Tables planned and not built: `l3d_params` (matched operating points; waits on a renderer for text cells), `l4_tentag` (one-tag against ten-tag, ratios only), `pyingest` (the write side of the Python cost), `pysweep` (where the Python tax comes from), `ops_recovery`, `ops_failover`, and `ops_start` (measured, never published). Retired and not coming back: `l3smp` (folded into `l3s` as warm columns), `l1`, `l1olap`, `l1tpc` (the synthetic document set is no longer run, DECISIONS #67 and #72), `l3s_nocompact` (the settle-step ablation is operator material, not page material, DECISIONS #71), `ops_build` and `ops_disk` (realised as the ingest pair and the disk column on every table).

### Vector

| id | title | rows | columns |
|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB embedded and server, each int8 and fp32, Elasticsearch, Milvus, Qdrant (all published) | search cold p50 and p99, warm p50 and p99, gain, recall@10, ingest vectors/s, ingest s and index s where the engine has the boundary and the total where it does not, peak memory GiB, disk GiB |
| `l3d` | Dense vector search | ArcadeDB embedded and server, each fp32 and int8, Chroma, DuckDB-VSS, LanceDB, Milvus (fp32, int8), Qdrant (fp32, int8), sqlite-vec (fp32, int8), Neo4j (fp32), SurrealDB server (fp32) (all published; the SurrealDB embedded 1M cell exceeded its budget, is named on the table, and re-runs phase-marked in qDX for the phase it dies in, BUGS.md F41); pgvector queued (qDS); ArangoDB queued (qDV) | search cold p50 and p99, warm p50 and p99, insert into a built index then search, and delete from a built index then search, each p50 and p99 at the 1M tier only, recall@10, ingest vectors/s, ingest s and index s where the engine has the boundary and the total where it does not, peak memory GiB, disk GiB |

Scales: `l3s` 100k / 1M / 8.84M; `l3d` 1M / 9.99M. Both dense sizes read one protocol: `_dense_overlay_entries(scale)` reads `dense_mp5_<pin>` for 10M and `dense_mp5_small_<pin>` for 1M, and a partial directory refuses. No single-pass dense row is on the page; the single-pass campaign rows feed no page table.

`l3d_params`, when built, exists to make the maxConnections-32-against-M-16 argument checkable rather than assertable, and to disclose that sqlite-vec is `exact_scan_no_ann`, brute force rather than an ANN index.

**Dense build cache.** The page's dense table reads the multipass overlays, where the fp32 arms are pinned to the corpus (`graphBuildCacheSize=9,990,000` at 9.99M on both deployments) and the INT8 arms run the engine default of 100,000 (DECISIONS #56; the percent knob is unread for inline quantization). The condition line must say: "ArcadeDB fp32 build cache pinned to the corpus size (9,990,000); INT8 at the engine default; comparators have no equivalent setting; see #7146 for the default's cost." The reason: at the engine default (`graphBuildCacheSize=0`, 25% of available heap at build start) the served fp32 arm at deep10m sized its cache to 3.67M of 9.99M and built in 190-198 min where the same jars embedded sized to the whole corpus and built in 38-42; at a matched capacity the two are within 10%, so the gap is the cache sizer, not the transport. The single-pass campaign rows run the default and stay frozen. The cache ablation (`results/ablation_cache_8d6af9475.jsonl`, 21 cells) is operator and upstream material, never a page table (DECISIONS #55). Operator recommendation to record: set `graphBuildCacheSize` to the corpus size when `N * (4*dims + 64)` bytes fits in about half the free heap; otherwise `graphBuildCacheMaxHeapPercent=75`; for int8 only `graphBuildCacheSize` moves anything.

### Graph

| id | title | rows | columns |
|---|---|---|---|
| `l2` | Graph OLTP | ArcadeDB embedded and server, LadybugDB, Neo4j, SurrealDB embedded and server (all published); ArangoDB queued (qDV) | point, 1-hop, 2-hop, 3-hop with a property filter, insert, update, and delete, each p50 and p99, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph analytics with and without the view | ArcadeDB embedded, embedded GAV, server, server GAV, LadybugDB, Neo4j, SurrealDB embedded and server (all published; the SurrealDB embedded SF10 cell exceeded its budget and is named on the table); ArangoDB queued (qDV) | the five queries (average friend age, friendships within a city, most friends, degree distribution, and triangle count), each cold and warm p50 and p99, view build s, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |

Scales: `l2` SF1 + SF10; `l2olap` SF1 + SF10 (SF10 alone cannot show whether the view's benefit scales).

`l2` carries p99 on every latency (DECISIONS #63), and no cold and warm split: each of its operations runs against a warm database by construction, and the condition says so rather than leaving the columns blank (DECISIONS #89).

The triangle count is the cell most likely to exceed its budget at SF10. A named censored cell with its budget stated is a result and not a gap, printed the way the embedded SurrealDB cells already are (DECISIONS #82b). Both new analytics queries return a small deterministic answer, a histogram and a single integer, so they are the strongest equivalence checks on the page: two engines that disagree about how many triangles one graph holds are caught before anybody reads a latency.

### Documents and time series

The page's document tables are TPC only (DECISIONS #67): `docs_oltp` and `docs_olap`, with PostgreSQL beside the default arm.

ArcadeDB has no row on `docs_olap` since 2026-09-14 (BUGS F42 and F43): answer checking found that its two queries were not the questions the comparators answered, our Q1 text computed four of the five aggregates, and its Q6 lost the boundary discount to the engine's decimal-literal comparison. Both errors made its numbers faster than the truth, so the cells came down. A table may lose its ArcadeDB row only by declaring it in a condition a reader sees, naming ArcadeDB and giving the reason; `page_check` passes a declared withdrawal and still fails a silent one. October re-measures the table with every engine's answer compared.

The decimal-literal defect is upstream #7609, filed 2026-09-15, and the same day's #7611 is the one that decides how this table is read at scale: an indexed lower bound loses part of a run of equal entries, so the revenue query disagreed only at the size where the loss landed on a qualifying row. That is why the revenue total and the revenue by month now count the rows they aggregate and compare the count exactly (DECISIONS #94): the count is part of the answer and not a page column, and without it a lost row sits inside the sums' rounding at the campaign's largest tier.

| id | title | rows | columns |
|---|---|---|---|
| `docs_oltp` | Document OLTP | ArcadeDB embedded and server, DuckDB, MongoDB, PostgreSQL, SQLite, SurrealDB server (all published); SurrealDB embedded queued (qDU, after BUGS.md F37); ArangoDB queued (qDV) | new-order and payment, and one order line inserted, read by key, updated, and deleted, each p50 and p99, OLTP ops/s over new-order and payment, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `docs_olap` | Document OLAP | same rows as `docs_oltp` | Q1, Q6, top ten parts by revenue, count by ship mode, and revenue by month, each cold and warm p50 and p99, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `l4` | Time series | ArcadeDB embedded and server, each native time series and document path, DuckDB, QuestDB, SQLite, MongoDB, TimescaleDB (all published) | newest reading, 12h aggregate, double group-by, high-usage filter, and group-by with ordering and limit, each cold and warm p50 and p99, ingest points/s, ingest total s, peak memory GiB, disk GiB |

`l4`'s double group-by has no served native time-series cell: over HTTP the engine prints the bucket as a date, so every bucket inside one calendar day collapses to one value while the embedded arm on the same build and five comparators return the full grouping (upstream #7610, BUGS.md F44). The cell is withheld rather than published as a latency for a different answer, the table's condition names the arm and the query, and the gate prints it as a known disagreement until the re-pin that carries the fix.

Every document table publishes ingest rate beside OLTP ops/s: publishing the win without the loss is selective.

Both transactional tables carry the four single-record operations, because nothing else on the page times the simplest thing anyone does to a database, and one record created, read, updated, and deleted is the operation every engine expresses without a dialect argument (DECISIONS #82a). Each of the four records its answer digest, so a create that wrote nothing or a delete that deleted nothing fails the equivalence gate instead of printing a fast number.

### Cross-model, deployment, embedded

| id | title | rows | columns |
|---|---|---|---|
| `e2` | Cross-model transaction | ArcadeDB embedded and server, Qdrant + Neo4j, SurrealDB embedded and server, PostgreSQL + pgvector + AGE, Neo4j vector index (all published; the composed Qdrant + Neo4j row still carries the retired Neo4j 5-community pin and its Qdrant half still runs in memory until qDT re-runs it); ArangoDB queued (qDV) | the composed write, the same write interrupted, the retrieval path, and the graph-filtered vector search, each p50 and p99, recall on the two read paths, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `e2atom` | what survives a crash | same as `e2` | trials, torn results |
| `e4` | What the client/server split costs | 1 to 100,000 documents | in-process, in-process HTTP, separate container |
| `pycost` | What Python costs | Java, Python, to_columns, to_json_list, to_list | time ms (p50, column 7 of `mini_results.csv`; column 6 is the mean and is never printed), vs Java |

`e2atom` is the page's strongest claim: 40/40 torn for the composed stack against 0/40 for every single-engine row on the table, pinned over all six single-engine labels.

The two read paths keep `e2` from being only a write argument (DECISIONS #82c). The retrieval path is a vector top-k, a one-hop expansion, and a projection of the documents found, which is the multi-model read a reader recognises from their own application; the graph-filtered search is a top-k restricted to the neighbourhood of a start node, which is where one engine pushes the filter into the index while a composed stack moves a candidate set between two systems and has to choose between filtering before or after the search. Both carry recall, measured against a brute-force answer over the same filtered candidate set, because an engine that filters after the search shows it there and not in latency.

`e4` runs as a runner lane (`e4_decomp.py`) at the pin. The two derived deployment-cost columns, CPU time, crashes raised, and the scratch write left the page under DECISIONS #73.

### Operating it

| id | title | rows | columns |
|---|---|---|---|
| `lifecycle` | session cost, open to close | doc, doc_idx10, empty, graph, sparse, ts, vector, each embedded and server; 10k, 100k, 1M, and 10M for doc, ts, and vector (graph_gav withheld, rule 7) | JVM start ms, first open ms, cold process ms, open and close, one query, one write, and write-then-query session ms, peak memory GiB |

`lifecycle` is both a page table and a regression gate; see section 4. It carries no cold and warm split, because it is itself the cold measurement, and no throughput or recall, because it runs no rated or approximate operation; the conditions say so rather than leaving the columns blank (DECISIONS #89). Server rows are labelled `<situation> (server)`: `open database` / action / `close database` over HTTP; JVM-start, first-open, and cold-process columns are null because a server is already a process. Embedded rows print no disk because the embedded database sits on a host bind mount the disk reading cannot see; those cells are blank with a condition (DECISIONS #71).

**The scenarios.** A database is not only opened and closed; it is built, read, written to, and reopened after someone else wrote. Those states cost different amounts and the difference is the finding, so each is its own column.

| scenario | what it asks |
|---|---|
| `build` | create, load, create the index/view, close. The session that OWNS the build, and where a close-time rebuild doubles it (#6489). |
| `clean` | reopen, touch nothing, close. The case #6583/#6632 argued about. |
| `read` | reopen, run one query, close. |
| `write` | reopen, commit one row into a scratch type, close. Held CONSTANT across situations, so it prices "what does committing anything cost". Measured, not on the page (DECISIONS #73). |
| `write_own` | reopen, commit into the situation's OWN structure, close. The constant write leaves a vector index clean; only this dirties it. |
| `write_own_read` | write then read in one session. Neither half alone shows the cost (#6641). |
| `stale` / `stale_read` | reopen a database a PREVIOUS session wrote to, so a persisted derived structure is invalid on arrival. |
| `drop` | reopen, drop the accelerator, close. Single cycle, never a median: the second cycle would find nothing to drop and quietly average in a no-op. |

**Time the actions, not just the ends.** Timing `open` and `close` and discarding the middle misses exactly where a query-triggered rebuild lands (it once reported ~5 ms open and ~300 ms close for a session that cost 4.3 s). Every scenario reports `open + action + close = session`, and the page quotes the session.

**Cold start is four numbers, not one.** Measured in a fresh subprocess, per situation: `import_ms` (interpreter + module import), `jvm_start_ms` (`start_jvm()` alone, no database), `first_open_ms` (first `open_database()`, JVM already up), and `cold_process_ms` (what a CLI actually waits for). A bare JVM is ~115 ms and adding all 65 jars to the classpath costs ~15 ms, so most of the cold process is the BINDING path, not the JVM and not the classpath. A page that quotes a millisecond warm open without this is off by two orders of magnitude for anything CLI-shaped, and embedded use is mostly CLI-shaped.

### Rendering rules, every table

- **One row order, one column pass.** `export_web._finish_table()` runs last over every table: tier, ArcadeDB first, then comparators alphabetically; embedded before server; int8 before fp32; stable inside a group. Every metric a row carries becomes a column. A builder owns its numbers, not its layout (BUGS.md F25).
- **Column order and ingest names.** The workload's own columns in spec order, then `recall@10`, then the ingest pair (rate, then total), then peak memory, then disk. Ingest rates name the type: `ingest documents/s` (documents, TPC), `ingest vertices+edges/s` (graph), `ingest points/s` (time series), `ingest+index vectors/s` (both vector tables), `ingest+index vertices+edges/s` (the cross-model set, whose load includes the vector index). The word "records" does not appear as a column name.
- **Ingest is a column pair, not a table.** Every table whose rows loaded something shows `ingest <unit>/s` and `ingest total s`. On the vector tables the 2026-10 instrument prints `ingest s` and `index s` as separate columns for the engines that have the boundary (ArcadeDB, pgvector, Neo4j, Milvus, and LanceDB), and the engines that index while ingesting keep the total with that as the stated reason (DECISIONS #74 item 2, #89); the cross-model timer still includes the index build and the note says so. Derived rates use `_rate(count_fields, seconds_field)` in the spec, aggregated per row like any field.
- **p50 and p99 on every latency column, cold and warm.** The first iteration after the database is opened is the cold number and the remaining iterations are the warm one, so the split costs nothing and answers what the first query of a session costs against the hundredth (DECISIONS #89). Analytical queries run 100 iterations per query per rep and record `*_p50_ms` and `*_p99_ms` (DECISIONS #63). A table with no split states why. p95 is not shown anywhere.
- **The same measurement set on every table** (DECISIONS #89): the latencies above, throughput where the operation has a natural rate, recall where the index is approximate, peak memory, and on-disk size after the workload, on every table rather than on some. An omission is a stated reason in the conditions, never a blank column, and `page_check` fails one that carries no reason.
- **The durability condition is generated, not typed.** Each table's note comes from the engines that table shows (`export_web._durability_note`): the matched relaxed class, then any engine on that table that waits for the disk at every commit, then any engine whose behaviour at commit could not be established (FAIRNESS.md F10, DECISIONS #81).
- **Peak memory and disk on the multipass-fed tables come from the campaign cell of the same arm** (same build, same envelope); the served arm's multipass file sees only the client container.
- **Disk on every table.** A blank disk cell is a row measured before the instrument (2026-08-14), an engine with no disk at all (the E2 spec's `in_memory`), or a served row with no server reading (BUGS.md F38); the note under the table says which. A served row's disk is the server container's growth alone, the client is only the driver. Neo4j's value includes its preallocated 256 MiB log files and the note says so (BUGS.md F27). Units are GiB (BUGS.md F40).
- **Rendering.** Integers print as integers (0, not 0.00; 40, not 40.0); values below 0.1 print with two significant digits; a missing value is a dash. Every table carries a Size column and direction arrows, and the best value per column within a size is bold.
- **Vocabulary.** Documents, not tables; one word per concept (Python package, embedded/server, comparator, size, cold/warm, trial). The page never says tabular or relational.
- **Both deployments wherever the engine has a served form** (DECISIONS #61): ArcadeDB runs embedded and server on every table, and a comparator that offers both runs both (SurrealDB). Quantization: fp32 and int8 only; fp16 is not run.
- **Before calling a page complete**, scan the exported JSON per column for blank cells and per row for a missing version (BUGS.md F26 has the one-liner). The freeze counts rows; the reader sees cells.

---

## 3. Figures

Six maximum. A figure per table is a gallery, not an argument.

| stem | status | contents |
|---|---|---|
| `f4_one_vs_n` | published | ArcadeDB against the best specialist at equal recall, log ratio. Exhaustive two-panel per DECISIONS #64: one row per published metric family, first pass and repeat pass. |
| `f7_e2_hybrid` | published | cross-model transaction latency |
| `f8_deployment` | published | embedded against server across result sizes; refuses to draw across two pins |
| `f6_memory_ceiling` | generated (`results/generated/figures`), not on the page | peak anon at DEEP-10M, ArcadeDB bars at the 24g heap |
| `f3_sparse_perquery` | not built | per-query latency against summed posting length (Spearman 0.95 on the pre-pin rows); needs a per-query run stamped at the pin so the figure and the tables describe the same engine |
| `f9_build_cost` | not built | build seconds per engine per lane, log scale. The largest ArcadeDB deficit on the page and currently only trailing columns. |
| `f10_lifecycle` | candidate, not built | close ms against rows, per situation, log-log. Only if `lifecycle` shows the O(stored) shape; if close is flat everywhere the table suffices. |

Deleted and NOT to be resurrected: `f5_sparse_scaling`; it captioned a real 8.84M measurement as a synthetic corpus.

---

## 4. Close cost is a bug, not a table column

Close and open cost get a page table AND an invariant, because a slow close is a defect class (DECISIONS #50) and this engine has produced several (#5747, #6489, #5872, #6067, #6722, #7183).

**The invariant (DECISIONS #50):**

> Close should be **O(what was written), not O(what is stored)**, and on the order of **100 ms**.

Grounded twice: close should not cost more than getting started, and it should sit under the ~100 ms at which a script stops feeling instant.

**"Getting started" is two numbers, not one.** A Java process reaches its first engine call in ~219 ms (`RuntimeMXBean.getUptime()`); a Python process in ~1,000 ms on the laptop (import ~105 + `start_jvm()` ~470 + first `open_database()` ~400). On mini, the machine the page publishes, `start_jvm()` alone is 176-196 ms, flat in workload and scale, and the whole cold Python process is 420-540 ms for every workload except vector. Mini is 2.6x faster than the laptop on `start_jvm()`, so no JVM figure may be quoted without its host; the page uses the mini column. The page's story is embedded PYTHON, so the Python row is the one its close budget answers to.

**Quote JVM startup next to every session number.** At these magnitudes it is the larger figure: a 5 ms `open()` inside a process that took 219 ms to reach its first database call is not a 5 ms cost to anyone launching a CLI, and printing the `open()` alone flatters every embedded number on the page.

`lifecycle` runs as a gate, not just a report. It FAILS when:
- a situation's close time grows with row count while nothing was written (that is the O(stored) shape and it is always a bug), or
- any clean close exceeds 100 ms at any tested size.

Situations that pass (documents, all four index types, geo, sparse, time series) are stated positively: the multi-model substrate closes cheaply. The vector index is the situation that does not, and the table's condition says what is known at this engine build: a no-op close grows with the index (8 ms at 10k, 98 ms at 1M, 1.4 s at 10M), and a session that writes and then searches pays a full asynchronous graph rebuild that `close()` waits on (#7183, fixed upstream in #7191 for 26.10.1; the October re-pin re-measures it, DECISIONS #74). The earlier halves of the vector cost (#6067 close-time deferral via #6724, #6722 eager location scan via #6731) are fixed upstream and are not open defects on the page.

The Graph Analytical View is no longer rebuilt on every open (#6583 via #6588, #6632 via #6633: +0.77 ms at open against +1,027 ms before, at 10M vertices / 40M edges), and an invalidating commit no longer stalls the next query (#6641 via #6642: 3.0 ms against 5,613 ms). The page must not say the view's speedup is paid with a per-session scan; it is not. What the view still costs per session is in section 4b.

Still open and worth pursuing as an upstream issue, not a caveat: 0.40 ms per index on close, independent of index content, vanishing on tmpfs, so it is I/O, and 30 indexes is not an unusual schema.

Cold open is measurable: `pagecache.evict()` drops a database's files with `posix_fadvise(DONTNEED)` and verifies with `mincore` that they left. No root, and it evicts only the named files, so the rest of the host stays warm and the number means "this database is cold" rather than "the machine is cold".

---

## 4a. When on-disk size is measured

On-disk size is not fixed at the moment a database closes, and a number that depends on when we looked is the same class of defect as the memory column. It drifts three ways: delayed block allocation (down-counts what is still dirty), background compaction retiring obsolete segments (drifts DOWN, sometimes minutes later), and WAL truncation after checkpoint.

**What the page prints today.** `disk GiB` is a column on every table that has it (DECISIONS #61), not the separate table once planned. `disk_data_mb` = the engine's writable layer plus its volumes after the cell, minus the same engine's empty footprint; for a served row, the server container alone. It is a POST-RUN reading, taken after the queries, and every table that prints it says so in its conditions. `container_disk()` syncs first, samples until two consecutive readings agree within 1%, measures the writable layer AND the volumes (PostgreSQL reported `SizeRw` unchanged from empty while 1,017.5 MiB sat in its volume), reads volume destinations from the daemon rather than a guessed path table, and returns `settled=False` with both readings rather than a bare number. The embedded arm takes one sample (`tries=1`) against a stopped container: defensible, since a dead process cannot compact, and stated on the row rather than left looking like a settled reading.

**The build-point protocol, the October target.** What the stricter reading requires:

1. **Measure at the point the build timer stops**, immediately after the engine's own documented settle step (forcemerge / flush / green-wait / `COMPACT INDEX` / `CHECKPOINT`), the same step the build is already timed to. That is the one moment every engine is in a defined, documented, reproducible state. Measuring "size at time T after close" makes the number a function of each engine's compaction schedule rather than of the data.
2. **A post-query reading is a second column, not the headline.** It answers a different question (does querying grow it?) and must not be compared against another engine's post-build number.
3. **`settled=False` blocks publication.** A cell that never converged is not a measurement.
4. **The settle budget must exceed a compaction cycle.** `tries=3, settle_s=3.0` is a 9-second window against a process that can land minutes later, so two readings can agree inside a compaction pause and record a false settle. Raise the budget and record how long convergence took.

**Land it deliberately, before a campaign, never between reps of a running one.** An adversarial review of a first design found that a barrier-and-watcher approach deadlocks every cell in every lane, that removing `tries` from the signature TypeErrors at four call sites, and that giving the dense lane an ArcadeDB settle step via `idx.compact()` is a SILENT NO-OP, because `LSMVectorIndex.compact()` returns false unless a compaction was already scheduled and nothing schedules one. Measuring at a slightly wrong point costs far less than breaking every cell.

## 4b. GAV is measured with the view ON and OFF, everywhere

The Graph Analytical View is an ArcadeDB-only accelerator, so an unablated number is a claim about a configuration rather than about the engine. Every graph OLAP cell runs BOTH arms:

    {embedded, server} x {SF1, SF10} x {BENCH_GAV=1, BENCH_GAV=0}   = 8 cells

All eight cells are on `l2olap`. The view's build cost is charged to the arm that builds it and published as a column (`view build s`, absent on rows without the view).

Labelling: `l2_graph.main()` stamps `out["gav"]` as a real boolean and sets `backend_arm="nogav"` for the off arm. `BENCH_GAV` is in the runner's env allowlist; it was once missing, which would have built the view anyway and written rows labelled as the ablation, rc=0, indistinguishable from a real one (rule 5).

**The ablation must use the lane's real query set, not a stand-in.** On a 100k-vertex, 400k-edge synthetic graph an openCypher two-hop count is 7% SLOWER with the view than without, stable across session lengths. The published speedup (the pinned top-degree ratio, 6.9x at 8d6af9475, which is one query's number; the benefit varies by query and grows with the graph, which is why `l2olap` shows both scales) comes from the lane's property-aggregation queries over neighbourhoods, a different access pattern. The view's benefit is query-shape dependent, and a probe that substitutes a convenient query measures nothing about the view the page publishes.

What belongs beside the pinned ratio: the view's cost per session is real. Its build is charged once (about 2.0 s at SF10, the `view build s` column), and a session that never queries the view pays +0.77 ms at open since #6633 (section 4). The pinned ratio is a within-session property.

---

## 6. Gates

`refresh_web_page.py`'s invariant: *every page table and figure is generated from frozen rows, listed in the page manifest, pinned by `page_check`, and carries a source link to a tracked artifact.* `page_check.PROSE` pins every typed number in `arcadedb.ts`, including page-only tables through `lambda P:` references over the exported JSON; a reworded sentence fails ABSENT. `page_check` also fails if any table loses its ArcadeDB row against the live page. `land_stage.py` is the publish-after-a-stage procedure: merge, regenerate, gates, then the diff, and with `--apply` the build, the commit in both repositories, and the push. Both scripts take `--preview` to publish to the hidden October route instead of the live page (DECISIONS #83), and `refresh_web_page.py --skeleton` fills that route from the laptop placeholder freeze, refusing any row from the bench host or at paper tier, stamping every table's conditions as placeholders, and waiving F1 and F3 by name because both describe the bench host (DECISIONS #86); PUBLISHING.md holds all three. After a re-pin, the SERVED page is grepped for the previous pin's strings in every field, not just the labels (BUGS.md F16).

| gate | fails when |
|---|---|
| mixed corpus | rows in one table disagree on `n_docs` while sharing a `scale_label` |
| sweep tier | a published cell carries `tier != paper` |
| unexplained column | a rendered column is named by no condition and no methodology entry |
| false protocol sentence | a page sentence asserts an n that any cell it covers does not meet |
| unpinned literal | a numeric literal appears in page prose outside a pinned entry or a generated cell |
| labels | a corpus name, size, or dimension on the page disagrees with the artifact constant |
| close cost | a clean close exceeds 100 ms, or grows with rows while nothing was written |
| mixed instrument | one table holds rows measured under two instruments |
| durability class | a table's engines committed under different rules, or a row carries no `durability` |
| disagreeing answers | two engines of one table answer the same query differently at one scale, or an engine skipped an operation without declaring it unexpressible |
| missing measurement | a table omits one of the standard measurements and states no reason |

---

## 7. Methodology the page must carry

Once, at the end, linked from every table: the global conditions; the environment table (`cpuset`, `mem_cap`, `server_mem_cap`, `mem_split`, `heap`, `server_heap`); the machine block from 0a, stating that the cpuset is 12 threads on 6 physical cores, that the governor is `powersave` with turbo enabled so frequency is not pinned, that the package throttles under sustained load with the power mode left as it ships and every row recording its temperature and the kernel's throttle counters (BUGS.md F45), and that the bench disk is NVMe while the same machine holds a rotational disk used only for backups; the overrides table from `PROTOCOL.md` section 7 with a column saying **which way each override moves the number**; the durability note (DECISIONS #65, #70, #81); engine identity per section 1; the query set, forty operations by table, eighteen of them from a published benchmark (DECISIONS #82d); repetition counts per table (generated, not typed); how equivalence is checked, that every timed query's answer is digested and compared across the engines of its table, and which operations an engine declared it cannot express (DECISIONS #88); ground truth (how recall@10 is computed and against which truth); outcome accounting; a dated changelog; and "Reproducing this", linking PROTOCOL, FAIRNESS, CAMPAIGN, READING-RESULTS, PUBLISHING, and the frozen artifacts.

Beside every peak-memory column that compares ArcadeDB variants: `-Xms=-Xmx` commits the heap, so the column measures reservation, not demand. This never clears; it is stated, not fixed.

And a closing list of what the page does NOT measure: concurrency and load (it needs a non-Python load generator; our own harness is censored above ~4 clients by GIL queueing, and a bad concurrency table is worse than a disclosed absence); import, export, and backup; replication beyond the failover trial; durability outside the one matched relaxed class, whose strict end is priced in the maintainers' memo and not on the page (DECISIONS #81); updates against a live vector index, where the 2026-10 dense table times an insert and a delete into a built index at the 1M tier and nothing above it (DECISIONS #82d); dense dimensionality above 128; anything across a real network; k other than 10.

---

## Published tables (generated by refresh_web_page.py from results/web_benchmarks.json on every publish; do not edit by hand)

Every table carries a Size column and direction arrows; the best value per column within a size is bold on the page; ingest is a pair of columns where the lane records it. Rows: ArcadeDB first, comparators alphabetical, embedded before server, int8 before fp32.

| id | title | rows | sizes | columns |
|---|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Elasticsearch, Milvus, Qdrant, pgvector | 100k vectors, 1M vectors, 8.84M vectors | recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB, cold p50 ms, cold p99 ms, warm p50 ms, warm p99 ms, gain |
| `l3d` | Dense vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Chroma (fp32), DuckDB VSS (fp32), LanceDB (int8), Milvus (fp32), Milvus (int8), Neo4j (fp32), Qdrant (fp32), Qdrant (int8), SurrealDB (server, fp32), pgvector (fp32), sqlite-vec (fp32), sqlite-vec (int8) | 1M vectors, 9.99M vectors | cold p50 ms, cold p99 ms, warm p50 ms, warm p99 ms, recall@10, ingest+index total s, ingest+index vectors/s, peak memory GiB, disk GiB |
| `l2` | Graph OLTP | ArcadeDB (embedded), ArcadeDB (server), LadybugDB, Neo4j, SurrealDB (embedded), SurrealDB (server) | SF1 (11k people), SF10 (73k people) | point p50 ms, point p99 ms, 1-hop p50 ms, 1-hop p99 ms, 2-hop p50 ms, 2-hop p99 ms, write p50 ms, write p99 ms, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph OLAP | ArcadeDB (embedded), ArcadeDB (embedded, GAV), ArcadeDB (server), ArcadeDB (server, GAV), LadybugDB, Neo4j, SurrealDB (embedded), SurrealDB (server) | SF1 (11k people), SF10 (73k people) | ingest vertices+edges/s, ingest total s, average friend age p50 ms, average friend age p99 ms, friends in same city p50 ms, friends in same city p99 ms, most friends p50 ms, most friends p99 ms, peak memory GiB, disk GiB |
| `e2atom` | Cross-model transaction: what survives a crash | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Neo4j (vector index), PostgreSQL + pgvector + AGE, Qdrant + Neo4j (no shared transaction), SurrealDB (embedded), SurrealDB (server) | 50k products | trials, torn results |
| `e2` | Cross-model transaction | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Neo4j (vector index), PostgreSQL + pgvector + AGE, Qdrant + Neo4j (no shared transaction), SurrealDB (embedded), SurrealDB (server) | 50k products | p50 ms, p99 ms, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `l4` | Time series | ArcadeDB (embedded, document path), ArcadeDB (embedded, native time series), ArcadeDB (server, document path), ArcadeDB (server, native time series), DuckDB, MongoDB, QuestDB, SQLite, TimescaleDB | 2.59M points | ingest points/s, ingest total s, newest reading p50 ms, newest reading p99 ms, 12h aggregate p50 ms, 12h aggregate p99 ms, peak memory GiB, disk GiB |
| `lifecycle` | Session cost, open to close | Dense vectors (embedded), Dense vectors (server), Documents (embedded), Documents (server), Documents, ten indexes (embedded), Documents, ten indexes (server), Empty database (embedded), Empty database (server), Graph (embedded), Graph (server), Sparse vectors (embedded), Sparse vectors (server), Time series (embedded), Time series (server) | 10k, 100k, 1M, 10M | JVM start ms, first open ms, cold process ms, open and close ms, one query ms, one write ms, write, then query ms, peak memory GiB |
| `e4` | What the client/server split costs | 1 documents, 1,000 documents, 10 documents, 10,000 documents, 100 documents, 100,000 documents | 1, 10, 100, 1,000, 10,000, 100,000 | in-process ms, in-process server, HTTP ms, separate container, HTTP ms |
| `pycost` | What Python costs | Java, in process, Python, Python, to_columns, Python, to_json_list, Python, to_list | 100k-document scan, vector search | time ms, vs Java |
| `docs_oltp` | Document OLTP | ArcadeDB (embedded), ArcadeDB (server), DuckDB, MongoDB, PostgreSQL, SQLite, SurrealDB (embedded), SurrealDB (server) | TPC-H SF1 (6.0M line items) | new-order p50 ms, new-order p99 ms, OLTP ops/s, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `docs_olap` | Document OLAP | DuckDB, MongoDB, PostgreSQL, SQLite, SurrealDB (embedded), SurrealDB (server) | TPC-H SF1 (6.0M line items) | Q1 p50 ms, Q1 p99 ms, Q6 p50 ms, Q6 p99 ms, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
