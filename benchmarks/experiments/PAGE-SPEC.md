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

**The 7.3 TB disk is not the bench disk.** `/dev/sda` is rotational and mounted at `/mnt/hdd8tb` for backups. Everything measured lives on the NVMe. A reader seeing a spinning disk in a machine listing would reasonably discount every I/O number, so the split has to be explicit.

The page's setup section is this block, read from `lscpu` and `lsblk`, not derived from a row. The payload's `hosts_recorded` list is container ids annotated "(host unknown)" on every lane except sparse and dense, because a row records a container, not a host; it is not rendered. Recording `BENCH_HOST` on every row is on the October checklist (DECISIONS #74).

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

The generated block "Published tables" at the end of this file is the list of tables, rows, sizes, and columns on the LIVE page; `refresh_web_page.py` rewrites it from the live payload on every live publish, and a preview publish writes the same inventory for the October route to `results/generated/preview-tables.md` instead of touching this file. The hand-written tables below describe the October instrument (DECISIONS #74 as amended through #104b) as the assembled skeleton payload shows it: every row label, column, and size named here is read from that payload, and when the payload and this prose disagree the payload is right and this prose is corrected (#102). Every table needs: an id, a title, a dataset line, explicit columns, explicit rows, a source link to a tracked artifact, and its conditions, which on an October payload are generated or registered sentences only (section "What the October page may say"). Tables planned and not built: `l3d_params` (matched operating points; waits on a renderer for text cells), `l4_tentag` (one-tag against ten-tag, ratios only), `pyingest` (the write side of the Python cost), `pysweep` (where the Python tax comes from), `ops_recovery`, `ops_failover`, and `ops_start` (measured, never published). Retired and not coming back: `l3smp` (folded into `l3s` as warm columns), `l1`, `l1olap`, `l1tpc` (the synthetic document set is no longer run, DECISIONS #67 and #72), `l3s_nocompact` (the settle-step ablation is operator material, not page material, DECISIONS #71), `ops_build` and `ops_disk` (realised as the ingest pair and the disk column on every table). Two tables are fed by bench-host artifacts rather than by a lane the skeleton runs, and the skeleton payload names them as absent: `e4` (its own overlay) and `pycost` (the binding suite's frozen file). Both return when their artifacts are re-measured at the October pin.

**Sizes (DECISIONS #103b, #103c).** One size per table by default, and a second only where the table exists to show how an engine scales. A raised size replaces that size's rows; no table accumulates two generations of one size and no new table is made for a size. The skeleton runs every lane at its smallest laptop corpus with the size column naming that corpus (`export_web.SKELETON_SCALE_LABELS`), so the sizes named below are the campaign's, and the skeleton's labels say "skeleton" so the two cannot be confused.

**Per-query budgets (DECISIONS #82b, #100, #100a).** Three lanes censor per query rather than per cell, at a budget that is a property of the lane and identical for every engine on its table: graph analytics (`graph_common.OLAP_BUDGET_S`), time series (`l4_tsbs.QUERY_BUDGET_S`), and document analytics (`l1_tpc.OLAP_BUDGET_S`). The page prints each budget from the constant, never from prose. A censored query keeps its cold pass and its answer digest, its p50 and p99 are over the iterations it reached, and the table names it beside its counts note with the iteration count and the time. No other lane has a per-query budget: the transactional, vector, cross-model, and lifecycle cells run under the cell timeout alone.

### Vector

| id | title | rows | columns |
|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB embedded and server, each int8 and fp32; Elasticsearch, Milvus, pgvector, Qdrant. ArangoDB, MongoDB, and SurrealDB have no row and are declared under the table (cannot express: none has a sparse index type, each with its own documentation cited, DECISIONS #95b), which is what the coverage table reads | p50 ms, p99 ms, recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB. The cold and warm columns with their gain come from the sparse multipass driver on the bench host (DECISIONS #89) and are absent from the skeleton |
| `l3d` | Dense vector search | ArcadeDB embedded and server, each int8 and fp32; ArangoDB (fp32), Chroma (fp32), DuckDB VSS (fp32, DuckDB 1.5.4), LanceDB (int8), Milvus (int8 and fp32), MongoDB (fp32, through MongoDB Search in the same container), Neo4j (fp32), pgvector (fp32), Qdrant (int8 and fp32), sqlite-vec (int8 and fp32), SurrealDB embedded and server (fp32) | cold p50 ms, cold p99 ms, after insert p50 ms, after delete p50 ms, insert into index ms/vector, recall@10 after insert, delete from index ms/vector, recall@10 after delete, index s, recall@10, ingest+index vectors/s, ingest s, ingest+index total s, peak memory GiB, disk GiB. Warm columns come from the dense multipass driver on the bench host and are absent from the skeleton |

Sizes: `l3s` three, 100k / 1M / 8.84M, the whole Big-ANN sparse track; `l3d` two, 1M and 10M (SIFT1M and DEEP-10M), both kept because the vector tables exist to show scaling (#103c). The sparse table has one ingest timer because every engine on it builds the index as it ingests; the dense table records `ingest s` and `index s` separately where the engine has the boundary, beside the single pair (#74). The two dense mutation operations, insert into a built index and delete from one, each followed by a search and its recall, run at the 1M tier only (#82d) and are forced on at the skeleton's micro size.

Both dense sizes read one protocol: `_dense_overlay_entries(scale)` reads `dense_mp5_<pin>` for 10M and `dense_mp5_small_<pin>` for 1M, and a partial directory refuses. No single-pass dense row is on the page; the single-pass campaign rows feed no page table.

`l3d_params`, when built, exists to make the maxConnections-32-against-M-16 argument checkable rather than assertable, and to disclose that sqlite-vec is `exact_scan_no_ann`, brute force rather than an ANN index.

**Dense build cache.** The page's dense table reads the multipass overlays, where the fp32 arms are pinned to the corpus (`graphBuildCacheSize=9,990,000` at 9.99M on both deployments) and the INT8 arms run the engine default (DECISIONS #56; the percent knob is unread for inline quantization). The condition line must say: "ArcadeDB fp32 build cache pinned to the corpus size (9,990,000); INT8 at the engine default; comparators have no equivalent setting; see #7146 for the default's cost." The reason, with its measurements, is DECISIONS #55 and #56: at the engine default the served fp32 build sizes its cache to a fraction of the corpus and the embedded build to the whole of it, so the gap is the cache sizer and not the transport. The single-pass campaign rows run the default and stay frozen. The cache ablation (`results/ablation_cache_8d6af9475.jsonl`) is operator and upstream material, never a page table (DECISIONS #55), and the operator recommendation lives with it.

### Graph

| id | title | rows | columns |
|---|---|---|---|
| `l2` | Graph OLTP | ArcadeDB embedded and server; ArangoDB, DuckPGQ (DuckDB 1.5.4 with the community DuckPGQ extension, SQL/PGQ), FalkorDB, LadybugDB, Memgraph, MongoDB, Neo4j, SurrealDB embedded and server | point p50 ms, point p99 ms, 1-hop p50 ms, 2-hop p50 ms, 3-hop filtered p50 ms, insert p50 ms, update p50 ms, delete p50 ms, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph OLAP | ArcadeDB embedded and server with the view built (labelled GAV), beside the view-off arms of section 4b in the campaign (the skeleton ran the view-on arms only); ArangoDB, DuckPGQ, FalkorDB, LadybugDB, Memgraph, MongoDB, Neo4j, SurrealDB embedded and server. Neo4j has no row in the skeleton payload: its analytics cell was frozen at the synthetic micro size while every other engine's is the LDBC slice, so it is a skeleton gap to close, not an absence; #104b proved its fourteen digests on the slice | average friend age p50 ms, average friend age p99 ms, friends in same city p50 ms, most friends p50 ms, degree distribution p50 ms, triangle count p50 ms, LSQB Q1 p50 ms through LSQB Q9 p50 ms, cold first query ms, view build s, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |

Interactive (`l2`): seven operations, point lookup, one hop, two hops, three hops filtered on the far end, insert, update, and delete, every read against a fresh seed set per repetition and the three writes 1,000 each per repetition. The writes run in both durability classes (#90). The table declares no cold/warm split: every operation runs against a built, warm database by construction. Every engine traverses the same persons-and-KNOWS projection with edges stored in both directions.

Analytics (`l2olap`): fourteen query columns (DECISIONS #104), each asked of the whole graph and run 100 times per repetition under the graph lane's per-query budget. Five are hand-written: average friend age by city, friendships within a city, most friends, degree distribution, and the triangle count; two of them aggregate a property along the edges, which LSQB never does, so they stay. Nine are LSQB's pattern-matching counts, taken nearly verbatim from the published Cypher (undirected KNOWS, exactly as LSQB writes it) and translated into AQL, MongoDB aggregation, SurrealQL, and SQL/PGQ, with every digest agreeing on the slice across all nine graph engines and nothing declared unexpressible (#104a, #104b). What each LSQB query counts, in the words the page uses:

- Q1: the eight-label chain: a country, a city in it, a person living there, a forum that person belongs to, a post in that forum, a comment replying to the post, the comment's tag, and the tag's class, every match counted.
- Q2: pairs of friends where one wrote a comment replying to a post the other wrote.
- Q3: three people who all live in the same country and are all friends with one another, each ordering counted.
- Q4: a tagged message with its creator, a person who liked it, and a comment replying to it, every combination counted.
- Q5: a tagged message and a reply to it carrying a different tag.
- Q6: a friend of a friend and that far person's tag interests, the two ends being different people.
- Q7: the fourth with the liker and the reply optional, so a tagged message with neither still counts once per creator.
- Q8: the fifth where the reply does not also carry the message's own tag.
- Q9: the sixth where the two people at the ends are not themselves friends.

The friends-of-friends pair (Q6 and Q9) is the one expected to be censored widely at full scale; a censored cell carries its cold-pass digest and is a result, not a hole (#104a). The p99 is on the headline query only (average friend age); the cold column is the first query of the session, most friends, timed once on a freshly opened database. The view build is charged to the arm that builds it and printed as `view build s`, blank on rows without the view.

Sizes: `l2` two, SF1 and SF10 of the persons-and-KNOWS projection, since per-seed reads never touch the message half and the full network at SF10 is not feasible; `l2olap` one, the full social network at SF1, which LSQB's queries need (#103b). The skeleton's analytics rows read a capped LDBC SF1 slice and are labelled as such.

### Documents and time series

The page's document tables are TPC only (DECISIONS #67): `docs_oltp` and `docs_olap`, split by `_restructure_tables` from one lane. The tuned PostgreSQL arm (`postgres_tuned`) runs on the lane as an ablation of one image's defaults and is kept off both document tables and the durability table, because it reads as a second engine (DECISIONS #76).

| id | title | rows | columns |
|---|---|---|---|
| `docs_oltp` | Document OLTP | ArcadeDB embedded and server; ArangoDB, DuckDB (1.5.4), MongoDB, PostgreSQL, SQLite, SurrealDB embedded and server | new-order p50 ms, new-order p99 ms, payment p50 ms, insert p50 ms, read p50 ms, update p50 ms, delete p50 ms, OLTP ops/s, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `docs_olap` | Document OLAP | same rows as `docs_oltp` | Q1 p50 ms, Q1 p99 ms, Q6 p50 ms, top parts p50 ms, ship mode p50 ms, by month p50 ms, cold first query ms, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `l4` | Time series | ArcadeDB embedded and server, each native time series and document path; ArangoDB, DuckDB (1.5.4), MongoDB, QuestDB, SQLite, SurrealDB embedded and server, TimescaleDB | newest reading p50 ms, newest reading p99 ms, 12h aggregate p50 ms, per-host hourly p50 ms, high-usage p50 ms, grouped, ordered, limited p50 ms, cold first query ms, ingest points/s, ingest total s, peak memory GiB, disk GiB |

Document OLTP: six operations, TPC-C new-order and payment and the four single-record operations (insert, read, update, delete by key), 1,000 of each per repetition, with OLTP ops/s the rate of the two transactions together; the p99 is on new-order only; every write runs in both durability classes; no cold/warm split, declared on the rows. Document OLAP: five analytical queries over the whole line-item table, TPC-H Q1 and Q6 plus the top ten parts by revenue, the count by ship mode, and revenue by month, 100 iterations each under the document analytics budget (#100a; the one cell it is expected to censor, the SurrealDB server's Q1, is named there); the cold column is Q1, the first query of the session.

Time series: six TSBS queries, all 100 iterations per repetition under the time-series budget (#100): the newest reading per host (TSBS last-point, asked unbounded), the same bounded to the past hour (measured and kept on the row, not printed), the twelve-hour aggregate, per-host hourly (a double group-by), the high-usage filter, and the grouped, ordered, limited query. The cold column is the newest reading. ArangoDB and SurrealDB run it on a plain table with a composite (host, ts) index, SQLite's footing (#100). One cell is withheld and declared: the served native arm's per-host hourly, whose answer differs from every other engine's on the server's SQL path (`export_web.L4_WITHHELD_HOURLY`).

Sizes: `docs_oltp` one, TPC-H SF1, since transactions do not get more interesting with more rows; `docs_olap` one, TPC-H SF10, where scanning and grouping separate planners; `l4` one, TSBS cpu-only at 1,000 hosts, the smallest configuration TSBS defines (#103, #103b). The skeleton runs SF0.01 and the 100-host corpus.

Every document table publishes ingest rate beside OLTP ops/s: publishing the win without the loss is selective.

### Cross-model, deployment, embedded

| id | title | rows | columns |
|---|---|---|---|
| `e2` | Cross-model transaction | ArcadeDB (one transaction), embedded and server; ArangoDB, MongoDB (its vector hit runs outside the transaction because the engine refuses it inside one, recorded as `txn_scope`, #98), Neo4j (vector index), PostgreSQL + pgvector + AGE, Qdrant + Neo4j (no shared transaction; its Qdrant half in memory, disclosed), SurrealDB embedded and server | transaction p50 ms, transaction p99 ms, retrieval p50 ms, graph-filtered search p50 ms, retrieval recall@10, filtered recall@10, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `e2atom` | Cross-model transaction: what survives a crash | same as `e2` | trials, torn results |
| `e4` | What the client/server split costs | 1 to 100,000 documents | in-process, in-process HTTP, separate container |
| `pycost` | What Python costs | Java, Python, to_columns, to_json_list, to_list | time ms (p50, column 7 of `mini_results.csv`; column 6 is the mean and is never printed), vs Java |

Four cross-model operations (#82c): the composed transaction (a vector hit, a graph traversal, and a document update in one transaction, 300 per repetition, both durability classes), the same transaction interrupted (`e2atom`, which kills the process between the writes and reopens), a retrieval path, and a graph-filtered vector search, the two read paths with recall for the vector half and digests for the rest. `e2atom` is the page's central claim, all-or-nothing across three models against a composed stack that cannot promise it; the trial count and the torn count are pinned by `page_check` against the artifact, and what they say is written at the freeze, not here (#102).

`e4` runs as a runner lane (`e4_decomp.py`) at the pin. The two derived deployment-cost columns, CPU time, crashes raised, and the scratch write left the page under DECISIONS #73.

Sizes: `e2` and `e2atom` one, 500k products, so retrieval recall is measured on more than a toy (#103); the skeleton runs 50k. `e4` keeps its six result sizes; `pycost` its two workloads.

### Operating it

| id | title | rows | columns |
|---|---|---|---|
| `lifecycle` | Session cost, open to close | seven situations, empty database, documents, documents with ten indexes, graph, sparse vectors, dense vectors, and time series, each ArcadeDB embedded and server; SurrealDB embedded on the six it can express (empty, documents, ten indexes, graph, dense vectors, time series on a plain table), with sparse vectors and the analytical view declared with the parse error (#95b). Graph with the analytical view withheld for ArcadeDB (rule 7). 10k, 100k, 1M, and 10M for documents, time series, and dense vectors; the skeleton runs 10k | JVM start ms, first open ms, cold process ms, open and close ms, one query ms, one write ms, write, then query ms, peak memory GiB |
| `durability` | What waiting for the disk costs | one row per engine and operation, from the write cells of `docs_oltp`, `l2`, and `e2` run in both classes (#90); the Size column names the operation: TPC-C new-order, TPC-C payment, one record inserted, read (the control, which commits nothing), updated, deleted; one person and an edge inserted, a property updated, a person and its edges deleted; one transaction across three models | no wait ms, waits for the disk ms, cost of waiting |
| `multimodel` | What the four multi-model engines cover | ArcadeDB, ArangoDB, MongoDB, SurrealDB, every arm of one engine folded into one row | one column per table on the page (eleven), each cell measured, declared (with the reason printed under that table), or no arm |

`lifecycle` is both a page table and a regression gate; see section 4. Server rows are labelled `<situation> (server)`: `open database` / action / `close database` over HTTP; JVM-start, first-open, and cold-process columns are null because a server is already a process. SurrealDB rows carry no JVM start either, since its core is a compiled extension the import loads, and the table says so. Embedded rows print no disk because the embedded database sits on a host bind mount the disk reading cannot see; those cells are blank with a condition (DECISIONS #71).

`durability` has no lane of its own. Engines with no setting to relax (DuckDB and its DuckPGQ arm, LadybugDB, Neo4j and the arms built on it) print one number in the waiting column and say so; the SurrealDB server's class could not be established from the engine and prints in the waiting column with the sentence that says why. The read row is the control. The ratio column is what waiting costs that engine on that operation and is not a claim about any other write.

`multimodel` is derived by the exporter from the other tables in the payload and re-derived by `page_check` at every publish (#95a); the roster of four is the one typed thing. It carries no number.

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

**Time the actions, not just the ends.** Timing `open` and `close` and discarding the middle misses exactly where a query-triggered rebuild lands (it once reported a millisecond open and a sub-second close for a session that cost seconds). Every scenario reports `open + action + close = session`, and the page quotes the session.

**Cold start is four numbers, not one.** Measured in a fresh subprocess, per situation: `import_ms` (interpreter + module import), `jvm_start_ms` (`start_jvm()` alone, no database), `first_open_ms` (first `open_database()`, JVM already up), and `cold_process_ms` (what a CLI actually waits for). The split exists so the page can say where a cold process goes, the JVM, the classpath, or the binding path, from the table rather than from an estimate. A page that quotes a warm open without the cold process beside it is off by orders of magnitude for anything CLI-shaped, and embedded use is mostly CLI-shaped.

### Rendering rules, every table

- **One row order, one column pass.** `export_web._finish_table()` runs last over every table: tier, ArcadeDB first, then comparators alphabetically; embedded before server; int8 before fp32; stable inside a group. Every metric a row carries becomes a column. A builder owns its numbers, not its layout (BUGS.md F25).
- **Column set and ingest names.** Under the October instrument a lane's columns are `export_web.OCT_TABLE_METRICS`, which REPLACES the September list: one warm median per query, a ninety-ninth percentile for the table's headline query only (the first in the list), one cold column for the first query after the database opens where the lane has one (a transactional cell declares in `cold_warm_na` that it does not), throughput where the operation has a rate, recall where the index is approximate, peak memory, disk, and on the dense table ingest and index build as separate timers. Ingest rates name the type: `ingest documents/s` (documents, TPC), `ingest vertices+edges/s` (graph), `ingest points/s` (time series), `ingest+index vectors/s` (both vector tables), `ingest+index vertices+edges/s` (the cross-model set, whose load includes the vector index). The word "records" does not appear as a column name.
- **Ingest is a column pair, not a table.** Every table whose rows loaded something shows `ingest <unit>/s` and `ingest total s`; on the vector and cross-model tables the timer includes the index build and the note says so. The dense table adds `ingest s` and `index s` where the engine has the boundary (DECISIONS #74 item 2); the sparse table states that no engine on it has one. Derived rates use `_rate(count_fields, seconds_field)` in the spec, aggregated per row like any field.
- **Latency columns.** p50 on every query; p99 on the headline query of each table (DECISIONS #89 as amended); analytical queries run 100 iterations per query per repetition and record `*_p50_ms` and `*_p99_ms` on the row whether or not the page prints both. p95 is not shown anywhere. No per-table aggregate is published.
- **Peak memory and disk on the multipass-fed tables come from the campaign cell of the same arm** (same build, same envelope); the served arm's multipass file sees only the client container.
- **Disk on every table.** A blank disk cell is a row measured before the instrument (2026-08-14), an engine with no disk at all (the E2 spec's `in_memory`), or a served row with no server reading (BUGS.md F38); the note under the table says which. A served row's disk is the server container's growth alone, the client is only the driver. Neo4j's value includes its preallocated 256 MiB log files and the note says so (BUGS.md F27). Units are GiB (BUGS.md F40).
- **Rendering.** Integers print as integers (0, not 0.00; 40, not 40.0); values below 0.1 print with two significant digits; a missing value is a dash. Every table carries a Size column and direction arrows, and the best value per column within a size is bold.
- **Vocabulary.** Documents, not tables; one word per concept (Python package, embedded/server, comparator, size, cold/warm, trial). The page never says tabular or relational.
- **Both deployments wherever the engine has a served form** (DECISIONS #61): ArcadeDB runs embedded and server on every table, and a comparator that offers both runs both (SurrealDB). Quantization: fp32 and int8 only; fp16 is not run.
- **Absences are declared, never blank** (DECISIONS #92, #95b). An engine is left off a table only when its documentation and an exact error show the query cannot be expressed, and then the sentence under the table says so with the citation; a censored or withheld cell is named with its reason. The coverage table reads those declarations.
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

`refresh_web_page.py`'s invariant: *every page table and figure is generated from frozen rows, listed in the page manifest, pinned by `page_check`, and carries a source link to a tracked artifact.* `page_check.PROSE` pins every typed number in `arcadedb.ts`, including page-only tables through `lambda P:` references over the exported JSON; a reworded sentence fails ABSENT. `page_check` also fails if any table loses its ArcadeDB row against the live page. `land_stage.py` is the publish-after-a-stage procedure: merge, regenerate, gates, then the diff, and with `--apply` the build, the commit in both repositories, and the push. Both scripts take `--preview` to publish to the hidden October route instead of the live page (DECISIONS #83); PUBLISHING.md holds both. After a re-pin, the SERVED page is grepped for the previous pin's strings in every field, not just the labels (BUGS.md F16).

| gate | fails when |
|---|---|
| mixed corpus | rows in one table disagree on `n_docs` while sharing a `scale_label` |
| sweep tier | a published cell carries `tier != paper` |
| unexplained column | a rendered column is named by no condition and no methodology entry |
| false protocol sentence | a page sentence asserts an n that any cell it covers does not meet |
| unpinned literal | a numeric literal appears in page prose outside a pinned entry or a generated cell |

## What the October page may say while the campaign runs (DECISIONS #102)

Three kinds of text exist on the page, and only two are allowed before the freeze.

- **Generated**: cells, counts, budgets, censored and withheld cells, declared absences, the durability setting each row ran, the disk definition. Derived from the frozen rows or from constants imported from the code that ran, by a registered generator. Cannot go stale.
- **Instrument prose**: what a table measures, what its columns are, how to read them, the fairness setup, the licence table. Typed, carries no number that is not pinned, and describes the protocol rather than the outcome. Lives in the October prose file for the page body and in the exporter's October prose registry for the sentences under a table.
- **Interpretation**: which engine moves between passes, which benefit is uneven, how far the comparators sit from one another, what the ratios say. Not written while the campaign runs. Written once at the freeze, when every row is in, each sentence with a pin, so a later re-measure that changes the number fails the publish.

A condition sentence on an October payload that is neither generated nor registered fails `page_check`. No sentence that serves the September page is reused for October, whatever its content; the September sentences are deleted from the exporter at the switch.
| labels | a corpus name, size, or dimension on the page disagrees with the artifact constant |
| close cost | a clean close exceeds 100 ms, or grows with rows while nothing was written |

---

## 7. Methodology the page must carry

Once, at the end, linked from every table: the global conditions; the environment table (`cpuset`, `mem_cap`, `server_mem_cap`, `mem_split`, `heap`, `server_heap`); the machine block from 0a, stating that the cpuset is 12 threads on 6 physical cores, that the governor is `powersave` with turbo enabled so frequency is not pinned, and that the bench disk is NVMe while the same machine holds a rotational disk used only for backups; the overrides table from `PROTOCOL.md` section 7 with a column saying **which way each override moves the number**; the durability note (DECISIONS #65, #70, #81); engine identity per section 1; repetition counts per table (generated, not typed); ground truth (how recall@10 is computed and against which truth); outcome accounting; a dated changelog; and "Reproducing this", linking PROTOCOL, FAIRNESS, CAMPAIGN, READING-RESULTS, PUBLISHING, and the frozen artifacts.

Beside every peak-memory column that compares ArcadeDB variants: `-Xms=-Xmx` commits the heap, so the column measures reservation, not demand. This never clears; it is stated, not fixed.

And a closing list of what the page does NOT measure: concurrency and load (it needs a non-Python load generator; our own harness is censored above ~4 clients by GIL queueing, and a bad concurrency table is worse than a disclosed absence); import, export, and backup; replication beyond the failover trial; durability at non-default settings; updates and deletes against a live vector index; dense dimensionality above 128; anything across a real network; k other than 10.

---

## Published tables (generated by refresh_web_page.py from results/web_benchmarks.json on every publish; do not edit by hand)

Every table carries a Size column and direction arrows; the best value per column within a size is bold on the page; ingest is a pair of columns where the lane records it. Rows: ArcadeDB first, comparators alphabetical, embedded before server, int8 before fp32.

| id | title | rows | sizes | columns |
|---|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Elasticsearch, Milvus, Qdrant | 100k vectors, 1M vectors, 8.84M vectors | recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB, cold p50 ms, cold p99 ms |
| `l3d` | Dense vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Chroma (fp32), DuckDB VSS (fp32), LanceDB (int8), Milvus (fp32), Milvus (int8), Neo4j (fp32), Qdrant (fp32), Qdrant (int8), SurrealDB (server, fp32), sqlite-vec (fp32), sqlite-vec (int8) | 1M vectors, 9.99M vectors | cold p50 ms, cold p99 ms, warm p50 ms, warm p99 ms, recall@10, ingest+index total s, ingest+index vectors/s, peak memory GiB, disk GiB |
| `l2` | Graph OLTP | ArcadeDB (embedded), ArcadeDB (server), LadybugDB, Neo4j, SurrealDB (embedded), SurrealDB (server) | SF1 (11k people), SF10 (73k people) | point p50 ms, point p99 ms, 1-hop p50 ms, 1-hop p99 ms, 2-hop p50 ms, 2-hop p99 ms, write p50 ms, write p99 ms, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph OLAP | ArcadeDB (embedded), ArcadeDB (embedded, GAV), ArcadeDB (server), ArcadeDB (server, GAV), LadybugDB, Neo4j, SurrealDB (embedded), SurrealDB (server) | SF1 (11k people), SF10 (73k people) | ingest vertices+edges/s, ingest total s, average friend age p50 ms, average friend age p99 ms, friends in same city p50 ms, friends in same city p99 ms, most friends p50 ms, most friends p99 ms, peak memory GiB, disk GiB |
| `e2atom` | Cross-model transaction: what survives a crash | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Neo4j (vector index), PostgreSQL + pgvector + AGE, Qdrant + Neo4j (no shared transaction), SurrealDB (embedded), SurrealDB (server) | 50k products | trials, torn results |
| `e2` | Cross-model transaction | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Neo4j (vector index), PostgreSQL + pgvector + AGE, Qdrant + Neo4j (no shared transaction), SurrealDB (embedded), SurrealDB (server) | 50k products | p50 ms, p99 ms, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `l4` | Time series | ArcadeDB (embedded, document path), ArcadeDB (embedded, native time series), ArcadeDB (server, document path), ArcadeDB (server, native time series), DuckDB, MongoDB, QuestDB, SQLite, TimescaleDB | 2.59M points | ingest points/s, ingest total s, newest reading p50 ms, newest reading p99 ms, 12h aggregate p50 ms, 12h aggregate p99 ms, peak memory GiB, disk GiB |
| `lifecycle` | Session cost, open to close | Dense vectors (embedded), Dense vectors (server), Documents (embedded), Documents (server), Documents, ten indexes (embedded), Documents, ten indexes (server), Empty database (embedded), Empty database (server), Graph (embedded), Graph (server), Sparse vectors (embedded), Sparse vectors (server), Time series (embedded), Time series (server) | 10k, 100k, 1M, 10M | JVM start ms, first open ms, cold process ms, open and close ms, one query ms, one write ms, write, then query ms, peak memory GiB |
| `e4` | What the client/server split costs | 1 documents, 1,000 documents, 10 documents, 10,000 documents, 100 documents, 100,000 documents | 1, 10, 100, 1,000, 10,000, 100,000 | in-process ms, in-process server, HTTP ms, separate container, HTTP ms |
| `pycost` | What Python costs | Java, in process, Python, Python, to_columns, Python, to_json_list, Python, to_list | 100k-document scan, vector search | time ms, vs Java |
| `docs_oltp` | Document OLTP | ArcadeDB (embedded), ArcadeDB (server), DuckDB, MongoDB, PostgreSQL, SQLite, SurrealDB (server) | TPC-H SF1 (6.0M line items) | new-order p50 ms, new-order p99 ms, OLTP ops/s, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `docs_olap` | Document OLAP | ArcadeDB (embedded), ArcadeDB (server), DuckDB, MongoDB, PostgreSQL, SQLite, SurrealDB (server) | TPC-H SF1 (6.0M line items) | Q1 p50 ms, Q1 p99 ms, Q6 p50 ms, Q6 p99 ms, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
