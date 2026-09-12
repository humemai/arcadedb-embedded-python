# Project page spec — what the page contains and what each cell must satisfy

The page at `humem.ai/projects/arcadedb` is the PRIMARY artifact. The paper draws
from it. This file is the contract: what tables exist, what rows and columns they
carry, which figures are published, and what a cell must satisfy to be printed.

`PROTOCOL.md` says how a number is produced. `FAIRNESS.md` says when two numbers
may be compared. This file says what gets shown. If they disagree, PROTOCOL wins
on production and FAIRNESS wins on comparison; this file never licenses a cell
those two would refuse.

---

## 0. The rules every published cell obeys

1. **Serial, full cpuset.** Every published latency, throughput, percentile and
   memory cell runs one at a time on mini's `cpuset 0-11` (the 12 P-core THREADS
   on 6 physical P-cores; see 0a), `workers=1`, `tier=paper`. Parallel shards exist for sweeps and exploration only and may
   never reach the page. Enforced: `runner.py` refuses `workers != 1` at paper
   tier; `load_canonical` drops partial cpusets.
2. **N=5, median [min-max].** Five repetitions per cell. Any table with a cell
   below n=5 states its n in a condition, and no page sentence may assert an n
   that a cell it covers does not meet.
3. **One engine commit per table.** Every ArcadeDB row in one table comes from the
   same upstream commit, stamped as `engine_commit`. Comparators are digest-pinned
   images. See §1.
   **ENFORCED at production time since 2026-08-25**, because it was not before and
   that cost a day. `build_engine_pair.sh` ended by PRINTING "stamp rows with
   ARCADEDB_ENGINE_COMMIT=<sha>" -- an instruction to a human -- and four separate
   runs came back rc=0 with `engine_commit=None` on every row: 118 lifecycle rows
   worth ~18 h of bench time, 20 l4 rows, and 1,000 sparse_cliff rows that were
   themselves a re-run whose only purpose was to add that field. `runner.py` now
   REFUSES a paper-tier ArcadeDB run when the variable is unset, before any cell
   starts, and `bench_common.run_conditions()` reads it so bespoke probes carry it
   too. A rule the page depends on may not be a reminder.
4. **One corpus per table.** Every row in a table describes the same dataset at
   the same size. A table whose rows disagree on `n_docs` (or the lane's size
   field) is a defect, not a comparison.
5. **A knob the campaign sets must reach the cell, and this is checked.**
   `runner.py`'s env passthrough is a CLOSED tuple, and its own comment says what
   happens to anything missing: "a knob absent here silently runs the in-script
   default." On 2026-08-24 that cost us the entire lifecycle table.
   `BENCH_LC_ITERS` and `BENCH_LC_WARMUP` were absent, so every cell ran the
   lane's defaults of 3 and 1 while the campaign exported 5 and 2 and every
   report said n=5. `BENCH_LC_MODES` was dropped the same way, so a 10M cell
   asked for two cheap scenarios ran all five.
   The check is mechanical and takes a second: diff every lane's
   `environ.get("UPPER_CASE")` against what the runner delivers. Run it when a
   lane gains a knob. The audit that followed found six more undelivered knobs,
   including `BENCH_DENSE_QUANT`, which selects int8 against fp32, and
   `BENCH_DUCKDB_THREADS`, which is a fairness knob. None had been set by a
   campaign, so no published row was wrong, but they were latent in exactly the
   way `BENCH_LC_ITERS` was latent until someone used it.

   **DELIVERY IS ONLY THE FIRST OF THREE.** 2026-08-25 found the other two, both
   in knobs that rule 5 had already certified as delivered.
   *(a) HONOURED.* `BENCH_LC_MODES` reached the cell and the cell ignored it:
   `l5_lifecycle.py` looped a literal tuple of all six modes and read `MODES`
   only for the stale block. No row was wrong, but a 10M vector cell ran 10.6 h
   instead of ~53 min and the stage could not finish inside its timeout. Fixed in
   `ae5257093`; an unknown mode is now a hard error, and the default is the old
   tuple verbatim so earlier rows stay reproducible.
   *(b) RESOLVED WHERE THE PROCESS RUNS.* `BENCH_DATA` was never exported by any
   launcher, so `runner.py` mounted the in-repo `experiments/data` as `/data` and
   every corpus lane was pointed at the wrong directory. l4 was the only victim
   (20 cells, each dead in under a second), and an earlier instance had been
   "fixed" by passing a HOST path into a container, which cannot resolve. Fixed
   in `bfe88ea28`: the mount is printed in the preamble and a lane whose corpus
   is missing is refused on the host.
   So the rule is: a knob must be DELIVERED to the cell, HONOURED by the lane,
   and RESOLVE to something that exists inside the container. Checking only the
   first has now failed twice.
7. **A probe must measure the thing its column is named after, and a bespoke
   stage must not hardcode a condition the lane derives.** Two failures on
   2026-08-26, both of which produced plausible numbers and exit 0.

   *The probe measured something else.* `graph_gav`'s read was issued in SQL,
   and a Graph Analytical View is consumed only by the openCypher executor, so
   every graph_gav session had the accelerator present and never consulted it.
   Same fixture, same data: 1.6 ms in SQL, 234 ms in cypher. `sparse`'s read was
   `SELECT count(*)`, which plans to CountFromTypeStep and never touches the
   index, and its write set neither tokens nor weights, so the index discarded
   it and write_own was byte-identical to the control write it exists not to be.
   `doc_idx10` wrote one of its ten indexed properties. The check is cheap and
   mechanical: a read that costs about as much as an empty query did not reach
   the structure, and a write whose index-entry count does not move did not
   land. Assert both in the lane rather than trusting the query text.

   *The bespoke stage hardcoded a condition.* The #5467 profiling stage set
   `ARCADEDB_HEAP=16g` by hand while the lane derives heap from the tier (4g at
   tiny, 8g at small). Both ran on the same host under the same cpuset, so the
   two profiles were comparable to each other, but a cross-date comparison
   against a profile taken at 8g was not, and it was posted upstream before the
   difference was noticed. A stage that sets by hand any condition the lane
   computes has to say so on the row, and any comparison spanning stages has to
   check the conditions match rather than assume the host is enough.

6. **The config PROFILE is recorded on every row.** ArcadeDB ships profiles that
   rewrite defaults wholesale: one sets `VECTOR_INDEX_GRAPH_BUILD_CACHE_SIZE=-1`
   with both cache heap percentages at 50, another pins both caches to a flat
   10,000, against a default of `graphBuildCacheSize=0` (auto) and
   `graphBuildCacheMaxHeapPercent=25`. Heap and cpuset are already recorded; the
   profile is not, and it can move a build by 4.7x on its own (10% vs 25% at
   deep10m: 10,786 s vs 2,274 s). Two rows under different profiles are not
   comparable and nothing in the row currently says so. Also: the percentage only
   applies on the AUTO path, so quoting it for a run that pinned an absolute
   cache size is wrong.

---

## 0a. The machine

Every published number is measured on **mini**. The laptop is a development
host: it compiles, it runs probes, and nothing it produces reaches the page.

| | mini (bench host) | laptop (dev only) |
|---|---|---|
| CPU | 12th Gen Intel Core i9-12900HK | Intel Core Ultra X9 388H |
| topology | 1 socket, 14 cores, 20 threads: 6 P-cores with SMT (12 threads) + 8 E-cores | 16 cores, 16 threads, no SMT |
| `cpuset 0-11` | the 12 P-core threads, verified by max frequency: cpu0-11 report 4900 MHz, cpu12-19 report 3800 MHz | **NOT the P-cores here.** The kernel reports `cpu_core = 0-3`, `cpu_atom = 4-15`, and max frequency agrees: cpu0-3 at 5100-5200 MHz, cpu4-11 at 4000, cpu12-15 at 3700. `0-11` on this machine is 4 P + 8 E, mixed. Laptop probes pin `0-3`. |
| RAM | 64 GiB installed (61.3 GiB usable) | 30 GiB |
| storage | Samsung SSD 980 PRO 2 TB NVMe (root, `/home`, `/var/tmp`, all bench data) | Samsung MZVL22T0HDLB 1.9 TB NVMe |
| OS / kernel | Ubuntu 26.04 LTS, 7.0.0-30-generic | Ubuntu 26.04 LTS, 7.0.0-29-generic |
| Docker | 29.7.2 | |

Three things about that table are load-bearing and must be said on the page,
not just recorded here:

**`cpuset 0-11` is 12 THREADS on 6 PHYSICAL CORES, not 12 cores.** SMT is on
(`/sys/devices/system/cpu/smt/control` = `on`). A reader who assumes 12 physical
cores will over-estimate what a parallel build had available, and every
"12-core" phrasing in our own prose is wrong.

**`cpuset 0-11` means something DIFFERENT on the two machines, which is a trap
we walked into.** On mini it is the P-core threads. On the laptop the kernel
says `cpu_core = 0-3` and `cpu_atom = 4-15`, so the same string selects 4 P-cores
plus 8 E-cores. Laptop probes that used `0-11` "for consistency with mini" were
measuring a heterogeneous set, which is fine for a ratio and misleading for a
latency. Laptop probes pin `0-3`; anything published re-runs on mini anyway, so
the two never need to mean the same thing, only to be stated.

**Frequency is not pinned.** The governor is `powersave` and turbo is ENABLED
(`intel_pstate/no_turbo` = 0), so a long build and a short query do not see the
same clock. This is a mobile-class part in a small chassis, so sustained
all-core work throttles in a way a server part would not. It is why every
published number runs SERIAL: co-scheduling on this host does not merely add
noise, it changes the clock the other cell sees.

**The 7.3 TB disk is not the bench disk.** `/dev/sda` is rotational and mounted
at `/mnt/hdd8tb` for backups. Everything measured lives on the NVMe. A reader
seeing a spinning disk in a machine listing would reasonably discount every I/O
number, so the split has to be explicit.

## 1. Engine identity: commit, not version

ArcadeDB is pinned by **upstream commit SHA**, not by a release number. The
build line reads `26.9.1.dev0` for every commit, so a version string cannot
identify what ran, and printing one while claiming the page ships the upstream
engine unmodified is a contradiction.

- Every row carries `engine_commit` (short SHA of the upstream commit the wheel
  and server image were both built from).
- The page prints it as the engine identity, linked to the commit on GitHub.
- Embedded and server arms in one table are built from the SAME commit, paired.
- A campaign FREEZES one commit and holds it start to finish. Upstream landing a
  fix mid-run does not restart the campaign; it becomes a dated changelog entry
  and a candidate for the next re-pin.
- Re-pinning is a deliberate, dated act recorded in the changelog with what moved.

Comparators are pinned by image digest and carry a version name. A comparator
row with `version_name: null` is not publishable.

---

## 2. Tables

Twelve on the page today (the generated block at the end of this file is the
list). Plan tables still unbuilt: `l3s_nocompact`, `l3d_params`, `l4_tentag`,
`pyingest`, `pysweep`, `ops_recovery/failover/start`. Every table needs: an id, a
title, a dataset line, explicit columns, explicit rows, a source link to a
tracked artifact, and its conditions.

### Vector

| id | title | rows | columns |
|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB emb int8 / emb fp32 / srv int8 / srv fp32, Elasticsearch, Milvus, Qdrant (pgvector queued, qDK) | cold p50, cold p99, warm p50, warm p99, gain, recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB |
| `l3smp` (retired 2026-09-11, folded into `l3s` as warm columns) | Sparse: what a second pass buys | same six | cold p50, warm p50, gain, **recall@10** |
| `l3s_nocompact` | **NEW** — what the settle step buys | ArcadeDB emb int8 with/without COMPACT | p50 at 100k / 1M / 8.84M, ratio |
| `l3d` | Dense vector search | ArcadeDB emb fp32 / srv fp32 / emb int8 / srv int8, Chroma, DuckDB-VSS, LanceDB, Milvus (fp32, int8), Qdrant (fp32, int8), sqlite-vec (fp32, int8) (pgvector, Neo4j, SurrealDB embedded and server queued, qDK and qDO) | cold p50, cold p99, warm p50, warm p99, recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB |
| `l3d_params` | **NEW** — matched operating points | every dense arm | ef_construction, ef_search, degree_param, degree_family, quantization, index kind |

Scales: `l3s` 100k / 1M / 8.84M; `l3d` 1M / 9.99M.

`l3d_params` exists to make the maxConnections-32-vs-M-16 argument checkable
rather than assertable, and to disclose that sqlite-vec is `exact_scan_no_ann` —
brute force, not an ANN index.

#### Dense build cache: what the four ArcadeDB arms run, and why served fp32 is slow (2026-09-03)

The single-pass campaign rows run the engine default; the page's dense table
reads the multipass overlays, where the fp32 arms at 9.99M are pinned to the
corpus and INT8 runs 100,000 (paragraph below). The default, `graphBuildCacheSize=0`,
sizes the HNSW build cache as 25% of *available* heap at build start
(`graphBuildCacheMaxHeapPercent=25`, since #6513). The cache ablation at
`8d6af9475` (`results/ablation_cache_8d6af9475.jsonl`, 21 cells, deep10m, heap
24g both sides) shows that one default lands the two deployments in different
places:

| arm | cache the default chose | build (min) | at whole corpus (9,990,000) |
|---|---|---|---|
| embedded fp32 | whole corpus (driver holds vectors in numpy; JVM near empty at sizing) | 38-42 | 38-42 |
| served fp32 | **3,674,697** (ingest put ~17 GB on-heap first) | 190-198 | 55-56 |
| embedded int8 | 100,000 (`DEFAULT_CACHE_SIZE`; the percent knob is unread for inline quantization) | 59-63 | not measured (3.67M: 53) |
| served int8 | 100,000 | 78-80 | not measured (3.67M: 69-70) |

At a matched capacity the served and embedded arms are within 6-10% of each
other at every point measured, so the served/embedded build gap on the page is
the cache sizer, not the transport. Figure:
`.notes/bench/figs/deep10m_build_vs_cache.png`. Full analysis in
`.notes/bench/FINDINGS-20260830.md` sections 2, 6 and 7.

**How the page handles it.** The `l3d` table publishes the default-policy rows
as they are, since that is what a user gets, and the caption must say that the
served fp32 build is on the wrong side of the cache knee at the engine default
and that the same jars embedded are not. The ablation is not a page table; it is
the evidence for the upstream report. Recommendation to record for operators:
set `graphBuildCacheSize` to the corpus size when `N * (4*dims + 64)` bytes
fits in about half the free heap; otherwise `graphBuildCacheMaxHeapPercent=75`.
For int8 only `graphBuildCacheSize` moves anything.

**The multipass table (2026-09-04, DECISIONS #56).** T5's dense block and the
page's 10M dense table are re-measured at this pin by qCJ with the fp32 build
cache **pinned to the corpus** (`graphBuildCacheSize=9,990,000` on
`arcadedb_dense_embedded` and `arcadedb_dense_server`) and the INT8 arms at the
**engine default** (100,000). User decision, on time. The caption of that table
and the page's condition line must say: "ArcadeDB fp32 build cache pinned to
the corpus size (9,990,000); INT8 at the engine default; comparators have no
equivalent setting; see #7146 for the default's cost." No single-pass dense row
is on the page; the single-pass campaign rows feed the paper checks only.

### Graph

| id | title | rows | columns |
|---|---|---|---|
| `l2` | Graph OLTP | ArcadeDB emb / srv, LadybugDB, Neo4j (SurrealDB embedded and server queued, qDO) | point, 1-hop, 2-hop, and write, each p50 and p99, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph analytics ± the view | ArcadeDB embedded, embedded GAV, server, server GAV, LadybugDB, Neo4j | the three queries, each p50 and p99, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |

Scales: `l2` SF1 + SF10; `l2olap` **SF1 + SF10** (SF10-only cannot show whether
the view's benefit scales; 20 SF1 rows are already frozen).

`l2` carries p99 on every latency (DECISIONS #63); the 2-hop SF10 reversal that
motivated it (20.28 vs 10.10 at b7c6c800d) is gone at 8d6af9475 (1.67 vs 4.79).

### Documents and time series (the synthetic `l1`, `l1olap`, `l1tpc` blocks are retired from the page since 2026-09-11, DECISIONS #67; the paper keeps them. TPC now renders as `docs_oltp` and `docs_olap` with PostgreSQL (tuned) beside the default arm; SQLite, MongoDB, and SurrealDB are queued)

| id | title | rows | columns |
|---|---|---|---|
| `l1` | Tabular OLTP and OLAP | ArcadeDB emb / srv, DuckDB, PostgreSQL | read p50, insert p50, **update p50**, OLTP ops/s, **ingest rows/s**, OLAP total, peak mem |
| `l1olap` | **NEW** — OLAP breakdown | same four | the five analytical queries, one column each |
| `l1tpc` | TPC-H / TPC-C | same four | Q1, Q6, new-order p50, OLTP ops/s, peak mem |
| `l4` | Time series | ArcadeDB embedded and server, each native time series and document path, DuckDB, QuestDB (SQLite, MongoDB, and TimescaleDB queued, qDI, qDJ, qDM) | newest reading p50 and p99, 12h aggregate p50 and p99, ingest points/s, ingest total s, peak memory GiB, disk GiB |
| `l4_tentag` | **NEW** — schema fidelity | same four | one-tag vs ten-tag, ratios only |

`l1` must publish ingest rate beside OLTP ops/s: publishing the win without the
loss is selective. `l1olap` turns one unexplained 70,807 ms cell into a
structural row-store-vs-column-store story.

### Cross-model, deployment, embedded

| id | title | rows | columns |
|---|---|---|---|
| `e2` | Cross-model transaction | ArcadeDB embedded and server, Qdrant + Neo4j, SurrealDB embedded (PG+pgvector+AGE, Neo4j vector index, and SurrealDB server queued, qDN) | p50 ms, p99 ms, CPU s, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `e2atom` | what survives a crash | same as `e2` | trials, crashes raised, torn results |
| `e4` | What the client/server split costs | 1 … 100,000 rows | in-process, in-process HTTP, separate container, packing cost, separate process |
| `pycost` | What Python costs | Java, Python, to_columns, to_json_list, to_list | **p50** (not mean), vs Java |
| `pyingest` | **NEW** — the write side | serial SQL, async parallel, insert_many, insert_many parallel | rows/s |
| `pysweep` | **NEW** — where the tax comes from | one-column vs group-by | ratio at 1k / 10k / 100k |

`e2atom` is the page's strongest claim: 40/40 torn for the composed stack against 0/40 for ArcadeDB and
SurrealDB, and 235 of 1,500 products left disagreeing.

`pycost` currently prints column 6 of `mini_results.csv`, which is the **mean**;
p50 sits unused in column 7. It is the only "ms" column on the page that is not
a p50.

### Operating it — NEW SECTION

| id | title | rows | columns |
|---|---|---|---|
| `lifecycle` | session cost, open to close | doc, doc_idx10, empty, graph, sparse, ts, vector, each embedded and server; 10k, 100k, 1M, and 10M for doc, ts, and vector (graph_gav withheld) | JVM start ms, first open ms, cold process ms, clean, read, write, write_own, and write_own_read session ms, peak memory GiB, disk GiB |
| `ops_build` | load and build cost | realised as columns (the ingest pair, the disk column); see the addenda | ingest rate, ingest total s |
| `ops_recovery` | **NEW** — crash recovery | ArcadeDB, 2 WAL settings | trials, contiguous, duplicates, recovery s |
| `ops_failover` | **NEW** — Raft failover | 3-node ArcadeDB | trials, acked writes present, ambiguous, election s, failover s |
| `ops_start` | **NEW** — cold start | ArcadeDB emb / srv, LadybugDB, Qdrant, sqlite-vec | create+DDL s, reopen ms, connect s |
| `ops_disk` | on-disk footprint | realised as columns (the ingest pair, the disk column); see the addenda | disk GiB |

`lifecycle` is both a page table and a regression gate — see §4.

**Status 2026-08-25: the lane has produced its first paper-candidate sweep.**
107 cells on mini through the wheel at engine pin `5010b306c9`, eight situations
across 10k / 100k / 1M and four across 10M. Full matrix in
`.notes/bench/lifecycle-open-close.md`, section "2026-08-25". The
headline shape: everything is flat across a 1000x range except the vector index,
which is the only situation that scales in BOTH directions — 1,378.8 ms to open
at 10M ([#6722](https://github.com/ArcadeData/arcadedb/issues/6722)) and
2,465,487 ms to close after one insert
([#6067](https://github.com/ArcadeData/arcadedb/issues/6067)). A GAV under the
identical trigger is 21.6 ms.
**RETRACTED 2026-08-26: not an identical trigger.** The graph_gav read was
issued in SQL, which cannot reach a Graph Analytical View at all, so that arm
never consulted the accelerator while the vector arm hit its index. Same
fixture at lc10k: 1.6 ms in SQL, 234 ms in cypher. The vector figures are
unaffected; the GAV comparison is withdrawn pending qAH.
**SUPERSEDED THE SAME DAY.** #6067's close-time deferral reached main at 09:58
UTC on 08-25 via [#6724](https://github.com/ArcadeData/arcadedb/pull/6724), so
the 41-minute figure describes an engine that stopped shipping that morning. At
the new pin, 1M vectors: open-insert-one-close is **99.5 ms** against 135,988 ms.
The cost is not gone, it is conditional - the same session with a SEARCH in it is
128,543 ms against 139,248 ms, i.e. 8% - so the page must quote the SESSION, not
the close. See `lifecycle-open-close.md`, section "2026-08-25 evening".
`n` caveat the table must carry: 10M is n=1 for `vector`'s write-own column and
n=3 for its cheap columns. Everything at 1M and below is n=3 or n=5.
`ops_disk` needs `runner.container_disk` wired; it is implemented and carried by
zero frozen rows.

> **2026-09-11 currency note:** superseded 2026-09-07: disk GiB is on every page table.

**The seven scenarios, because "open and close cost" was too few questions.**
A database is not only opened and closed; it is built, read, written to, and
reopened after someone else wrote. Those states cost wildly different amounts
and the difference is the whole finding, so each is its own row:

| scenario | what it asks |
|---|---|
| `build` | create, load, create the index/view, close. The session that OWNS the build, and where a close-time rebuild doubles it (#6489). |
| `clean` | reopen, touch nothing, close. The case #6583/#6632 argued about. |
| `read` | reopen, run one query, close. |
| `write` | reopen, commit one row into a scratch type, close. Held CONSTANT across situations, so it prices "what does committing anything cost". |
| `write_own` | reopen, commit into the situation's OWN structure, close. The constant write leaves a vector index clean; only this dirties it. |
| `write_own_read` | write then read in one session. Neither half alone shows the cost (#6641). |
| `stale` / `stale_read` | reopen a database a PREVIOUS session wrote to, so a persisted derived structure is invalid on arrival. |
| `drop` | reopen, drop the accelerator, close. Single cycle, never a median: the second cycle would find nothing to drop and quietly average in a no-op. |

**Time the actions, not just the ends.** An earlier version of this lane timed
`open` and `close` and discarded the middle, which is exactly where a
query-triggered rebuild lands: it reported ~5 ms open and ~300 ms close for a
session that actually cost 4.3 s. Every scenario reports
`open + action + close = session`, and the page quotes the session.

**Cold start is four numbers, not one.** "JVM startup" was being used for three
different quantities. Measured in a fresh subprocess, per situation:

| column | this machine | what it is |
|---|---|---|
| `import_ms` | ~105 ms | interpreter + module import |
| `jvm_start_ms` | ~470 ms | `start_jvm()` alone, no database |
| `first_open_ms` | ~400 ms | first `open_database()`, JVM already up |
| `cold_process_ms` | ~1,000 ms | what a CLI actually waits for |

For scale, a bare JVM here is **~115 ms** and adding all 65 jars to the
classpath costs **~15 ms**. So roughly 900 ms of the cold second is the BINDING
path, not the JVM and not the classpath. A page that quotes a 4 ms warm open
without this is off by two orders of magnitude for anything CLI-shaped, and
embedded use is mostly CLI-shaped.

---

## 3. Figures

Six maximum. A figure per table is a gallery, not an argument.

| stem | status | contents |
|---|---|---|
| `f4_one_vs_n` | published | ArcadeDB vs best specialist at equal recall, log ratio. Exhaustive two-panel per DECISIONS #64, synthetic document rows dropped per #67. |
| `f7_e2_hybrid` | published | cross-model transaction latency |
| `f8_deployment` | published | embedded vs server across result sizes |
| `f3_sparse_perquery` | blocked on data | per-query latency vs summed posting length, Spearman 0.95. `engine_commit` now lands (2026-08-25, 1,000 rows at `5010b306c9`, checked by reading the rows back rather than trusting rc=0). Re-running once at the new pin so the figure and the lifecycle table describe the same engine. |
| `f6_memory_ceiling` | published (ArcadeDB bars at the 24g heap; comparators cleared 2026-09-03) | peak anon at DEEP-10M. |
| `f9_build_cost` | **NEW** (unbuilt as of 2026-09-11) | build seconds per engine per lane, log scale. The largest ArcadeDB deficit on the page and currently only trailing columns. |
| `f10_lifecycle` | **NEW, candidate** (unbuilt as of 2026-09-11) | close ms vs rows, per situation, log-log. Only if `lifecycle` shows the O(stored) shape after the current fixes; if close is flat everywhere the table suffices. |

Deleted and NOT to be resurrected: `f5_sparse_scaling` — it captioned a real
8.84M measurement as a synthetic corpus.

---

## 4. Close cost is a bug, not a table column

Close and open cost get a page table AND an invariant, because a slow close is a
defect and this engine has produced three of them (#5747, #6489, #5872).

**The invariant, from `lifecycle-open-close.md`:**

> Close should be **O(what was written), not O(what is stored)**, and on the
> order of **100 ms**.

Grounded twice: close should not cost more than getting started, and it should
sit under the ~100 ms at which a script stops feeling instant.

**"Getting started" is two numbers, not one**, and older notes quoting a single
~160 ms conflated them (that figure is also unsourced and was not taken on mini;
see the annotation in `.notes/bench/lifecycle-open-close.md`).
Measured 2026-08-24 on an idle laptop, `26.9.1.dev0`, n=5:

| path | to its first engine call |
|---|---|
| Java process | **~219 ms** (`RuntimeMXBean.getUptime()` before the first call) |
| Python process | **~1,000 ms** = import ~105 + `start_jvm()` ~470 + first `open_database()` ~400 |

**And on MINI, which is the machine the page publishes.** Measured 2026-08-25 in
the lifecycle lane, `start_jvm()` in a fresh subprocess, n=107 cells:

| path | on mini |
|---|---|
| `start_jvm()` alone, no database | **175.8-196.2 ms**, flat in workload and scale |
| whole cold Python process | **420-540 ms** for every workload except vector |
| whole cold Python process, vector at 10M | **2,202 ms** |

Mini is 2.6x faster than the laptop on `start_jvm()` (~180 vs ~470 ms), so no JVM
figure may be quoted without its host. The page uses the mini column.

Compare a bare `java -version` on the same machine: **~115 ms**. The page's story
is embedded PYTHON, so the second row is the one its close budget answers to.

**Quote JVM startup next to every session number.** At these magnitudes it is
the larger figure: a 5 ms `open()` inside a process that took 219 ms to reach
its first database call is not a 5 ms cost to anyone launching a CLI, and
printing the `open()` alone flatters every embedded number on the page.

`lifecycle` runs as a gate, not just a report. It FAILS when:
- a situation's close time grows with row count while nothing was written
  (that is the O(stored) shape and it is always a bug), or
- any clean close exceeds 100 ms at any tested size.

Situations that already pass — documents, all four index types, geo, sparse,
time series — are stated positively: the multi-model substrate closes cheaply.
Two optional accelerators did not.

**Fixed since the last matrix ran, and therefore unmeasured:** #5747 (our PR
#5787), #6489 (our PR #6490), #6503 (Luca's #6513), #6518. The q75 matrix ran on
`26.8.1.dev23` and its `vector` clean close reads **8,223 ms** at 100k and
**34,504 ms** at 1M.

> **2026-09-11 currency note:** SUPERSEDED 2026-09-03: measured at 8d6af9475, the page's lifecycle table.

**Still open and worth pursuing** (each is a candidate upstream issue, not a
caveat to write around):
- 0.40 ms per index on close, independent of index content, vanishing on tmpfs
  → it is I/O, and 30 indexes is not an unusual schema.
- ~~The Graph Analytical View is REBUILT on every open~~ **CLOSED 2026-08-23,
  both halves of the fix we asked for shipped the same day.** [#6583](https://github.com/ArcadeData/arcadedb/issues/6583)
  (ours) → Luca's [#6588](https://github.com/ArcadeData/arcadedb/pull/6588)
  persists the CSR with a freshness certificate; his
  [#6632](https://github.com/ArcadeData/arcadedb/issues/6632) → [#6633](https://github.com/ArcadeData/arcadedb/pull/6633)
  then made the read lazy-on-first-use, unconditionally. Measured on the merged
  commit at 10M vertices / 40M edges, a session that never queries the view now
  pays **+0.77 ms** at open against **+1027.46 ms** before. The page must stop
  saying the speedup is paid with a per-session scan; it is not.
- ~~**The cost moved rather than vanished**~~ **CLOSED 2026-08-24.**
  [#6641](https://github.com/ArcadeData/arcadedb/issues/6641) (ours) → Luca's
  [#6642](https://github.com/ArcadeData/arcadedb/pull/6642), merged the same day,
  and the fix is the direction we proposed: kick the check off in the background
  and let the triggering query fall back to OLTP immediately. Verified on main,
  n=5: the first query after an invalidating commit is **3.0 ms** (range
  2.7-308.7) against 5,613 ms unfixed, and the view reports `status=BUILDING` in
  all five, so the rebuild genuinely went to the background. The 10M sweep
  ~~confirms it holds at scale: a GAV's write-own close is 21.6 ms at 10M
  vertices, flat against 9.5 ms at 10k.~~ **WITHDRAWN 2026-08-26**: that flatness
  is an artefact of a read that could not reach the view (SQL, not cypher), so it
  is not evidence about the view at all.
- **NEW 2026-08-25, and it is the OPEN half of the vector cost.**
  [#6722](https://github.com/ArcadeData/arcadedb/issues/6722) (ours). Every
  database open parses every page of every `LSM_VECTOR` index and rebuilds the
  in-memory location map one entry at a time, for a session that may never
  search. Warm open at 10M is **1,378.8 ms** against 1.1-1.3 ms for documents and
  for a graph with a view. The diagnostic that identifies it is cold-vs-warm:
  every other workload gets 40-55% back from the page cache and the vector index
  gets 3-8%, so the cost is parse and map population, not I/O. The line
  immediately below the call defers the GRAPH on purpose, which is what makes the
  eager location scan a choice. Java repro reproduced on upstream `e215d61c1` at
  0.25-0.39 us/vector.
  **FIXED the same day** by his [#6731](https://github.com/ArcadeData/arcadedb/pull/6731).
  Verified n=7 idle: open goes 8/14/47 -> 6/3/3 ms at 2k/50k/200k, flat in corpus
  size, and at 1M on mini 90.3 -> 1.9 ms. #6067's close-time deferral landed the
  same morning via #6724, so BOTH halves of the vector lifecycle cost are fixed
  upstream and neither belongs on the page as an open defect.
  What remains, and what the page should carry instead: a session that writes and
  then searches still pays the rebuild, 128,543 ms at 1M, and the identical work
  costs 2,032 ms if the session did not write. Filed as #7183, fixed upstream in
  #7191 for 26.10.1; the October re-pin re-measures it.
- Cold open is now measurable: `pagecache.evict()` drops a database's files with
  `posix_fadvise(DONTNEED)` and verifies with `mincore` that they left. No root,
  and it evicts only the named files, so the rest of the host stays warm and the
  number means "this database is cold" rather than "the machine is cold".

---

## 4a. When on-disk size is measured

On-disk size is not fixed at the moment a database closes, and a number that
depends on when we looked is the same class of defect as the memory column. It
drifts three ways: delayed block allocation (down-counts what is still dirty),
background compaction retiring obsolete segments (drifts DOWN, sometimes minutes
later), and WAL truncation after checkpoint.

`container_disk()` already handles most of this — it syncs first, samples until
two consecutive readings agree within 1%, measures the writable layer AND the
volumes (PostgreSQL reported `SizeRw` unchanged from empty while 1,017.5 MiB sat
in its volume), reads volume destinations from the daemon rather than a guessed
path table, and returns `settled=False` with both readings rather than a bare
number. What remains:

1. **Measure at the point the build timer stops**, immediately after the engine's
   own documented settle step (forcemerge / flush / green-wait / `COMPACT INDEX`
   / `CHECKPOINT`) — the same step the build is already timed to. That is the one
   moment every engine is in a defined, documented, reproducible state. Measuring
   "size at time T after close" makes the number a function of each engine's
   compaction schedule rather than of the data, so an engine that compacts eagerly
   prints a smaller index than one that defers, at identical content.
2. **A post-query reading is a second column, not the headline.** It answers a
   different question — does querying grow it? — and must not be compared against
   another engine's post-build number.
3. **`settled=False` blocks publication.** Today it is a note. A cell that never
   converged is not a measurement.
4. **The settle budget must exceed a compaction cycle.** `tries=3, settle_s=3.0`
   is a 9-second window against a process the docstring says can land "minutes
   later", so two readings can agree inside a compaction pause and record a false
   settle. Raise the budget and record how long convergence took.
5. **The embedded arm currently takes one sample** (`tries=1`) against a stopped
   container. Defensible — a dead process cannot compact, and `inspect --size`
   works on a stopped container — but it must be stated on the row rather than
   left looking like a settled reading, since `disk_settled` stays null.

**This change is bigger than it looks and must not be rushed into a live
campaign.** An adversarial review of a first design (2026-08-21) found that a
barrier-and-watcher approach deadlocks every cell in every lane; that removing
`tries` from the signature TypeErrors at four call sites; that declaring the
anchor dict beside the thread start NameErrors on the three early-return paths
runner.py:1113-1116 already documents against; and, worst, that giving the dense
lane an ArcadeDB settle step via `idx.compact()` would be a SILENT NO-OP,
because `LSMVectorIndex.compact()` returns false unless a compaction was
already scheduled and nothing schedules one. That item would have shipped as
"ArcadeDB now takes its settle step" while doing nothing at all.

So land it deliberately, before the full multi-lane campaign, never between
reps of a running one. Disk is a published post-run column (addendum
2026-09-07); the build-point reading is the October target, and measuring it
at a slightly wrong point costs far less than breaking every cell.

## 4b. GAV is measured with the view ON and OFF, everywhere

The Graph Analytical View is an ArcadeDB-only accelerator, so an unablated number
is a claim about a configuration rather than about the engine. Every graph OLAP
cell runs BOTH arms:

    {embedded, server} x {SF1, SF10} x {BENCH_GAV=1, BENCH_GAV=0}   = 8 cells

All eight cells are frozen at 8d6af9475 and `l2olap` shows them. The view's
build cost is charged to the arm that builds it, and published as a column.

Labelling: `l2_graph.main()` stamps `out["gav"]` as a real boolean and sets
`backend_arm="nogav"` for the off arm, which is correct. Fixed: every frozen
graph OLAP row stamps a real boolean.

`BENCH_GAV` is in the runner's env allowlist. It was once missing, which would
have built the view anyway and written rows labelled as the ablation, rc=0,
indistinguishable from a real one.

**The ablation must use the lane's real query set, not a stand-in.** Measured
2026-08-21 on a 100k-vertex, 400k-edge synthetic graph at engine `3ec4f07e0`:
an openCypher two-hop count (`MATCH (a:P)-[:E]->(b:P)-[:E]->(c:P) RETURN
count(*)`) is **7% SLOWER** with the view than without, stable across session
lengths 1, 2, 3 and 5 (1.08x, 1.06x, 1.07x, 1.07x). The published speedup, the pinned top-degree ratio (6.9x at 8d6af9475),
comes from the lane's property-aggregation queries over neighbourhoods, which
is a different access pattern. So the view's benefit is query-shape dependent,
and a probe that substitutes a convenient query measures nothing about the
view the page publishes.

What the same measurement DOES establish, and what belongs beside the pinned top-degree ratio (6.9x at 8d6af9475): the
view's fixed cost per session is real and large. A session that opens and closes
without querying at all costs **414.6 ms with the view against 11.5 ms without,
36x**, because the CSR is rebuilt by a full graph scan on every open
(`CSRBuilder: 100000 nodes, 400000 edges, 4.2 MB, 384-622 ms` on every open).
The pinned top-degree ratio (6.9x at 8d6af9475) is a within-session property
that each open re-pays.

---

## 4c. Lane readiness, 2026-08-27

What a reader of this file most needs is which lanes can be published now. An
adversarial audit on 08-26 confirmed 23 defects, 14 blocking publication; 18 are
fixed. This is the residue.

> **SUPERSEDED 2026-08-28: the pin moved to `b7c6c800d`.** The table below
> describes rows measured at `d7940d79e`, which are now quarantined as
> `results/SUPERSEDED_prepin_d7940d79e.jsonl` and reach no table. That pin
> predated `1b04483bf`, the #6743 sparse fix, so its sparse numbers understate
> ArcadeDB by roughly 4x (1M p50 ~37 ms against 11.26 ms re-measured); it also
> predated 20 `graph/olap` commits including four GAV **correctness** fixes
> (#6769 masks all parallel edges when one is deleted), #6857 and #6858. The
> campaign is re-running every lane at the new pin. Kept as written because it
> records what the audit found, not what is currently published.

| lane | rows at pin `d7940d79e` (SUPERSEDED) | status |
|---|---|---|
| `l1` | 50 | READY |
| `l1tpc` | 50 | READY |
| `e2` | yes | READY |
| `l4` | 20, re-run 08-27 | READY for ingest and the aggregates. `q_last` needed a second fix: our native arm asked a WINDOWED question in the column three unbounded arms share. Fixed, needs one more 11-minute re-run |
| `lifecycle` | 104 | READY except `graph_gav` |
| `l3s` | 35 | measurements sound; `n_docs` still comes from a module constant so rule 4's corpus fingerprint checks a constant |
| `l2` | none | never run at this pin |
| `l3d` | none | never run at paper tier |

> **2026-09-03, pin `8d6af9475`:** every lane above is READY at n=5 per cell
> (97 cells, 505 clean rows across `runs_page`, `runs_l4`, `runs_lifecycle`):
> `l1`, `l1tpc`, `l2` sf1/sf10, `l3s` tiny/small/medium, `l3d` deep10m at paper
> tier with all four ArcadeDB arms and nine comparators, `l4`, `lifecycle`
> lc10k/lc100k/lc1m all seven workloads, `e2`. `l3d` small is re-running (qCH)
> after 20 cells failed on a wrong `BENCH_DENSE_DATA`. Comparator rows carry
> `engine_commit=b7c6c800d` by design (carried forward; they do not run
> ArcadeDB), except Milvus, re-measured after the build-time fix.
>
> **2026-09-07:** `l3s` is READY at the pin (qCI, paper corpus, 45 rows; T4 reads them). Milvus dense rows are being re-measured (qCO, sealed segments). **Earlier correction 2026-09-04:** `l3s` at this pin was NOT ready. All 45 ArcadeDB
> sparse cells ran the synthetic 10M/30,000 corpus (BUGS F6); the freeze
> dropped them and T4 stays at 26.8.1 until qCI (paper corpus, ~9 h) lands.
> `l3d` small re-ran clean (qCH, 20 rows). `l3d` deep10m ArcadeDB rows are at
> the pin in `runs_paper.csv`, but T5 and the page's 10M dense table read the
> `dense_mp5_2681` multipass overlay, which nothing re-ran; f8 refuses to draw
> across the two pins. Open decision: re-run the dense multipass at the pin
> (ArcadeDB arms ~31 h at today's served-fp32 default, plus Milvus) or drop the
> warm column and read T5 from the campaign rows.

**Two of the defects flattered us**, which is why they were worth finding: the l4
native arm slept 5 s that no other arm got, and its `q_last` was windowed where
the others were unbounded. Both were invisible in the row because the field name
did not say what had been done.

**`graph_gav` is not ready and the reason is ours.** The audit found the read was
issued in SQL, which cannot reach a Graph Analytical View at all. Fixing that
made it reach the view (1.6 ms -> 234 ms at lc10k, which is the proof), but the
same edit changed the SCOPE: the old read was 100 seeds, the replacement is an
unbounded whole-graph 2-hop, so 16,087 ms at 1M measures the query written, not
the view. Rule 7 half-applied. It needs a bounded seed set AND a per-cycle
assertion that the view was used.

**Still withheld:** lifecycle `graph_gav` (`export_web` LIFECYCLE_WITHHELD).

---

## 5. Blocked cells — what may not be published today

| what | why | clears when |
|---|---|---|
| ~~`l3s` medium, Milvus + Qdrant~~ | ~~pools two corpora~~ | **CLEARED 2026-08-21**: `PAPER_CORPUS` in `load_canonical` admits only the corpus each tier publishes, fingerprinted on `(n_docs, dims)`. Rows still need re-publishing |
| ~~`l3d` deep10m, all comparators~~ | ~~`tier=sweep`, envelope 28g/16g, `version_name: null`~~ | **CLEARED 2026-09-03**: 5 clean paper-tier rows per comparator at the matched 36g/24g envelope in `runs_page_8d6af9475.jsonl` (Milvus re-measured after `df807f112`, the rest carried forward from `b7c6c800d`) |
| ~~`f6_memory_ceiling`~~ | ~~draws no ArcadeDB bar~~ | **CLEARED 2026-09-03**: ArcadeDB deep10m memory rows exist and the figure draws them |
| ~~`l4` ratios~~ | ~~QuestDB's WAL-apply poll was inside its timed ingest. Code fixed 2026-08-22 (`QuestTS.settle()` runs outside the timer); the published rows still carried the old timing~~ | **CLEARED 2026-09-03**: re-run at the pin, every row stamped |
| ~~`l4` ArcadeDB native TIMESERIES row~~ | ~~came from `l4_native_probe.py`, a bespoke probe, not the lane script, and ran two opt-in fast paths (`TS_PRIMITIVE=1`, `TS_NUMPY=1`) that no comparator got~~ | **CLEARED 2026-09-08**: lane row through `_l4_canonical` |
| any peak-memory comparison across ArcadeDB variants | `-Xms=-Xmx` commits the heap, so the column measures reservation, not demand | never — state it beside every such column |
| ~~`postgres_tuned`~~ | ~~has never run: 0 rows, display name only~~ | **CLEARED**: 20 rows; "PostgreSQL (tuned)" on `docs_oltp` and `docs_olap` |
| `hosts_recorded` | 382 container IDs (payload `setup.hosts`) annotated "(host unknown)"; a row records a container id, not a host | do not render it. Publish the 0a machine block instead, which is read from `lscpu`/`lsblk` rather than derived from a row |

---

## 5a. What still needs measuring

Ordered by whether a published cell depends on it.

**Blocking a cell that is on the page today:**

| measurement | cost | why |
|---|---|---|
| DONE 2026-09-03: l4 re-run with the corrected ingest timer | ~2 h | the code is fixed; the rows are not |
| DONE 2026-09-08: native TIMESERIES promoted to the lane, then re-run | ~4 h | a probe number cannot sit in a lane table (F6b) |
| DONE 2026-09-03: dense comparators at deep10m, paper tier, matched envelope, pinned versions | ~2-3 d | three independent disqualifiers on the current rows |
| `f3` sparse per-query re-run with `engine_commit` stamped | ~4 h | unblocks the best unbuilt figure |

**New tables the page does not have yet:**

| measurement | cost | status |
|---|---|---|
| DONE (published): lifecycle: cold/warm open, close x3 modes, 8 situations, 2 sizes | ~3 h | lane BUILT and smoke-tested; needs a campaign run on the frozen pair |
| DONE (published): on-disk footprint | free | lands automatically now; qO rows already carry `disk_data_mb` |
| crash recovery, Raft failover, cold start | free | measured, never published |
| **import / export** | ~1 d, lane to build | **The largest blind spot on the page.** Nothing here measures `IMPORT DATABASE` / `EXPORT DATABASE` or backup+restore, and for an embedded engine those are lifecycle operations a user hits as often as open and close. Examples 15 and 16 already contrast import-database against transactional ingest, so the shape exists; it is not a lane and produces no rows. GATED, though: upstream #6471 (JSONL export silently skips un-serializable records with no aggregate error) and #6460 (JSONL import does not remap LINK-typed values, fix in flight as #6654) are open CORRECTNESS bugs. Benchmarking a path that silently drops records would produce a throughput number for the wrong work. Build the lane, but publish only once those two land |
| DONE (published as the ingest pair): load and build cost table | free | in frozen rows already |
| DONE (published as `e2atom`): atomicity table (torn counts) | free | in frozen rows already |
| DONE (`l2olap` SF1 published): ingest A/B, jpype size sweep, nocompact ablation, l2olap SF1 | free | in frozen rows already |

**Ablations, worth running but blocking nothing:**

| measurement | cost | why |
|---|---|---|
| ~~`graphBuildCacheMaxHeapPercent` sweep~~ | done | **ANSWERED 2026-08-23.** 25% is the right default and the page can now say so with evidence instead of publishing it as "whatever the engine does". At deep10m: 10% costs **10,786 s** against 25%'s **2,274 s**, a 4.7x penalty, while 40% and 60% are slightly WORSE than 25% (2,421 and 2,423) because the extra cache takes heap the build needs. Query p50 and recall are flat throughout (7.4-8.4 ms, 0.952-0.955), so the knob touches build only. NOTE the staging lesson: the same sweep at `small` looked FLAT across all four percentages, because auto-sizing granted the whole 1,000,000-vector corpus at every one of them. A tier that cannot exercise a knob reports a plateau that says nothing. |
| ~~GAV on/off at the missing 7 of 8 cells~~ | done | **MEASURED 2026-08-23**, all 8 cells at N=5. The view is worth 2.50x to 6.55x at SF10 depending on the query and 1.50x to 3.70x at SF1, so the benefit GROWS with the graph and the single pinned top-degree ratio (6.9x at 8d6af9475) the page prints is one query's number out of a range. View build is 2.06 s at SF10 against 1,771 ms saved per pass of the three queries, so it amortises in about one pass. |
| int8 disk overhead (#3143 revisit) | ~1 h | our own issue, closed COMPLETED in May, yet int8 measures 13% MORE disk than fp32 at deep10m (8773.8 vs 7744.6 MB) |
| pgvector arm | adapters landed 2026-09-11, queued qDK / qDN | the most conspicuous absence |
| single-engine E2 alternative (Neo4j native vector index) | adapters landed 2026-09-11, queued qDK / qDN | tests the "any other pair" claim |

**Deliberately not measured:** concurrency. It needs a non-Python load generator,
our own harness is censored above ~4 clients by GIL queueing, and a bad
concurrency table is worse than a disclosed absence.

---

## 6. Gates

Existing gates stay. `refresh_web_page.py`'s invariant is re-pointed from "the
page may only show what the papers show" to: *every page table and figure is
generated from frozen rows, listed in the page manifest, pinned by `page_check`,
and carries a source link to a tracked artifact.*

New gates, each closing a failure found in the 2026-08-21 review:

| gate | fails when |
|---|---|
| mixed corpus | rows in one table disagree on `n_docs` while sharing a `scale_label` |
| sweep tier | a published cell carries `tier != paper` |
| unexplained column | a rendered column is named by no condition and no methodology entry |
| false protocol sentence | a page sentence asserts an n that any cell it covers does not meet |
| unpinned literal | a numeric literal appears in page prose outside a pinned entry or a generated cell |
| labels | a corpus name, size or dimension on the page disagrees with the artifact constant |
| close cost | a clean close exceeds 100 ms, or grows with rows while nothing was written |

---

## 7. Methodology the page must carry

Once, at the end, linked from every table: the global conditions; the
environment table (`cpuset`, `mem_cap`, `server_mem_cap`, `mem_split`, `heap`,
`server_heap`); the machine block from 0a, stating that the cpuset is 12 threads
on 6 physical cores, that the governor is `powersave` with turbo enabled so
frequency is not pinned, and that the bench disk is NVMe while the same machine
holds a rotational disk used only for backups; the overrides table from
`PROTOCOL.md` §7 with
a column saying **which way each override moves the number**; engine identity
per §1; repetition counts per table; ground truth (how recall@10 is computed and
against which truth); outcome accounting; a dated changelog; and "Reproducing
this", linking PROTOCOL, FAIRNESS, CAMPAIGN, READING-RESULTS, PUBLISHING and the
frozen artifacts.

And a closing list of what the page does NOT measure: concurrency and load;
replication beyond the failover trial; durability at non-default settings;
updates and deletes against a live vector index; dense dimensionality above 128;
anything across a real network; k other than 10.

---

## Addendum 2026-09-07: what the page shows after the 8d6af9475 re-pin and the user's audit

Amends §2 (tables), §4a (disk) and the arm lists above. DECISIONS #58, #60, #61 in the private notes carry the reasoning; this is the spec-level record.

**Tables now on the page (13):** `l3s`, `l3smp`, `l3d`, `l2`, `l2olap`, `l1`, `l1olap` (NEW: the five analytical queries, one column each), `l1tpc`, `l4`, `e2`, `e2atom` (NEW: trials, crashes raised, torn results), `lifecycle`, `e4`, `pycost`. `l3d_params` waits on a renderer for text cells; `l3s_nocompact`, `l4_tentag`, `pyingest`, `pysweep`, `ops_build/recovery/failover/start` are still unbuilt.

> **2026-09-11 currency note:** SUPERSEDED 2026-09-11 by the generated block below (12 tables; `l3smp`, `l1`, `l1olap`, `l1tpc` retired).

**Columns added from fields the rows already carried:** `p95`/`p99` (l3s; p95 removed 2026-09-10), `cold p99` (l3d), `point p99` and `2-hop p99` (l2), `view build s` (l2olap, absent on rows without the view), `update p50` and `ingest rows/s` (l1), `CPU s` (e2), `peak memory GiB` on the multipass-fed tables (from the campaign cell of the same arm; the served arm's multipass file sees only the client container), and **`disk GiB` on every table that has it**.

**`ops_disk` is realised as a column, not a table.** `disk_data_mb` = the engine's writable layer plus its volumes after the cell, minus the same engine's empty footprint. It is a post-run reading, not the build-point reading §4a asks for, and every table that prints it says so in its conditions. Blank where the engine's containers were not sampled (Milvus's sparse stack) or the row predates the wiring (dense comparators at 1M). §4a's stricter protocol stays the October target.

**Arms: both deployments wherever the engine has a served form.** Added: `arcadedb_sparse_server_fp32` (l3s, l3smp), the server arm without the view (l2olap, SF1 and SF10; l2olap now shows both scales), `arcadedb_e2_server` (e2, e2atom; one HTTP session transaction), `arcadedb_ts_doc_server` and `arcadedb_ts_native_server` (l4; the native arm writes InfluxDB line protocol to `/api/v1/ts/{db}/write` and declares `ts_path=native_timeseries_http_line_protocol`), and `arcadedb_server` on `lifecycle` (rows labelled `<situation> (server)`: `open database` / action / `close database` over HTTP; JVM-start, first-open and cold-process columns are null, a server is already a process; tiers lc10k/lc100k/lc1m). E4 runs as a runner lane (`e4_decomp.py`) at the pin instead of the August hand launch. Quantization: fp32 and int8 only; fp16 is not run.

**Every typed number in `arcadedb.ts` is pinned** by `page_check.PROSE`, including page-only tables through `lambda P:` references over the exported JSON; a reworded sentence fails ABSENT. `page_check` also fails if any table loses its ArcadeDB row against the live page.

**Identity:** every ArcadeDB row is named from its own engine string and commit (`arcadedb 26.9.1-dev · 8d6af9475`), never from an image tag. The page header lists the identities actually present.

## 2026-09-10 addendum: cells, not rows

The 8d6af9475 page was complete by rows and had blank cells. The rules that came out of the audit:

- **One row order, one column pass.** `export_web._finish_table()` runs last over every table: tier, ArcadeDB first, then comparators alphabetically; embedded before server; int8 before fp32; stable inside a group. Every metric a row carries becomes a column, peak memory and disk last. A builder owns its numbers, not its layout.
- **p50 and p99 on every latency column**, cold and warm where a second pass exists. Transactional lanes had the samples already; the analytical lanes (graph OLAP, document OLAP, TPC-H Q1/Q6, time-series queries) now run 100 iterations per query per rep and record `*_p50_ms` and `*_p99_ms` beside the mean/median fields they always had (DECISIONS #63). p95 is not shown anywhere.
- **Disk on every table.** A blank disk cell is a row measured before the instrument (2026-08-14) or an engine with no disk at all; the E2 spec's `in_memory` names the latter and the note under the table says so. Neo4j runs with a 5 s checkpoint interval only; its disk value includes the preallocated 256 MiB log files and DISK_NOTE says so (BUGS F27).
- **Both dense sizes read one protocol.** `_dense_overlay_entries(scale)` reads `dense_mp5_<pin>` for 10M and `dense_mp5_small_<pin>` for 1M; a partial directory refuses.
- **Rendering.** Integers print as integers (0, not 0.00; 40, not 40.0); values below 0.1 print with two significant digits; a missing value is a dash.
- **Vocabulary.** Documents, not tables; one word per concept (Python package, embedded/server, comparator, size, cold/warm, trial). The page never says tabular or relational.
- **Before calling a page complete**, scan the exported JSON per column for blank cells and per row for a missing version (BUGS F26 has the one-liner). The freeze counts rows; the reader sees cells.
- **Ingest is a column pair, not a table (2026-09-11).** Every table whose rows loaded something shows `ingest <unit>/s` and `ingest total s`: records/s on documents, TPC (line items plus parts over load seconds), graph (persons plus edges) and the cross-model set (products plus edges); pts/s on time series; vectors/s on the sparse and dense tables (labelled ingest+index, one timer), where the total includes the index build and the note says so. Derived rates use `_rate(count_fields, seconds_field)` in the spec, aggregated per row like any field. A separate side-by-side table was built and dropped the same day at the user's request.
- **Column order and ingest names (2026-09-11).** `_finish_table` orders every table the same way: the workload's own columns in spec order, then `recall@10`, then the ingest pair (rate, then total), then peak memory, then disk. Ingest rates name the type: `ingest documents/s` (documents, TPC), `ingest vertices+edges/s` (graph), `ingest points/s` (time series), `ingest+index vectors/s` (both vector tables), `ingest+index vertices+edges/s` (the cross-model set, whose load includes the vector index). The word "records" does not appear as a column name.

## Published tables (generated by refresh_web_page.py from results/web_benchmarks.json on every publish; do not edit by hand)

Every table carries a Size column and direction arrows; the best value per column within a size is bold on the page; ingest is a pair of columns where the lane records it. Rows: ArcadeDB first, comparators alphabetical, embedded before server, int8 before fp32.

| id | title | rows | sizes | columns |
|---|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Elasticsearch, Milvus, Qdrant | 100k vectors, 1M vectors, 8.84M vectors | recall@10, ingest+index vectors/s, ingest+index total s, peak memory GiB, disk GiB, cold p50 ms, cold p99 ms |
| `l3d` | Dense vector search | ArcadeDB (embedded, fp32), ArcadeDB (embedded, int8), ArcadeDB (server, fp32), ArcadeDB (server, int8), Chroma (fp32), DuckDB VSS (fp32), LanceDB (int8), Milvus (fp32), Milvus (int8), Qdrant (fp32), Qdrant (int8), sqlite-vec (fp32), sqlite-vec (int8) | 1M vectors, 9.99M vectors | cold p50 ms, cold p99 ms, warm p50 ms, warm p99 ms, recall@10, ingest+index total s, ingest+index vectors/s, peak memory GiB, disk GiB |
| `l2` | Graph OLTP | ArcadeDB (embedded), ArcadeDB (server), LadybugDB, Neo4j | SF1 (11k people), SF10 (73k people) | point p50 ms, point p99 ms, 1-hop p50 ms, 1-hop p99 ms, 2-hop p50 ms, 2-hop p99 ms, write p50 ms, write p99 ms, ingest vertices+edges/s, ingest total s, peak memory GiB, disk GiB |
| `l2olap` | Graph OLAP, with and without the Graph Analytical View | ArcadeDB (embedded), ArcadeDB (embedded, GAV), ArcadeDB (server), ArcadeDB (server, GAV), LadybugDB, Neo4j | SF1 (11k people), SF10 (73k people) | ingest vertices+edges/s, ingest total s, average friend age p50 ms, average friend age p99 ms, friends in same city p50 ms, friends in same city p99 ms, most friends p50 ms, most friends p99 ms, peak memory GiB, disk GiB |
| `e2atom` | Cross-model transaction: what survives a crash | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Qdrant + Neo4j (no shared transaction), SurrealDB (embedded) | 50k products | trials, crashes raised, torn results |
| `e2` | Cross-model transaction | ArcadeDB (one transaction), ArcadeDB (server, one transaction), Qdrant + Neo4j (no shared transaction), SurrealDB (embedded) | 50k products | p50 ms, p99 ms, CPU time s, ingest+index vertices+edges/s, ingest+index total s, peak memory GiB, disk GiB |
| `l4` | Time series | ArcadeDB (embedded, document path), ArcadeDB (embedded, native time series), ArcadeDB (server, document path), ArcadeDB (server, native time series), DuckDB, QuestDB, SQLite | 2.59M points | ingest points/s, ingest total s, newest reading p50 ms, newest reading p99 ms, 12h aggregate p50 ms, 12h aggregate p99 ms, peak memory GiB, disk GiB |
| `lifecycle` | Session cost, open to close | Dense vectors (embedded), Dense vectors (server), Documents (embedded), Documents (server), Documents, ten indexes (embedded), Documents, ten indexes (server), Empty database (embedded), Empty database (server), Graph (embedded), Graph (server), Sparse vectors (embedded), Sparse vectors (server), Time series (embedded), Time series (server) | 10k, 100k, 1M, 10M | JVM start ms, first open ms, cold process ms, open and close ms, one query ms, one write ms, write into the structure ms, write, then query ms, peak memory GiB |
| `e4` | What the client/server split costs | 1 documents, 1,000 documents, 10 documents, 10,000 documents, 100 documents, 100,000 documents | 1, 10, 100, 1,000, 10,000, 100,000 | in-process ms, in-process server, HTTP ms, separate container, HTTP ms, packing cost ms, separate process ms |
| `pycost` | What Python costs | Java, in process, Python, Python, to_columns, Python, to_json_list, Python, to_list | 100k-document scan, vector search | time ms, vs Java |
| `docs_oltp` | Document OLTP | ArcadeDB (embedded), ArcadeDB (server), DuckDB, PostgreSQL, PostgreSQL (tuned), SQLite | TPC-H SF1 (6.0M line items) | new-order p50 ms, new-order p99 ms, OLTP ops/s, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
| `docs_olap` | Document OLAP | ArcadeDB (embedded), ArcadeDB (server), DuckDB, PostgreSQL, PostgreSQL (tuned), SQLite | TPC-H SF1 (6.0M line items) | Q1 p50 ms, Q1 p99 ms, Q6 p50 ms, Q6 p99 ms, ingest documents/s, ingest total s, peak memory GiB, disk GiB |
