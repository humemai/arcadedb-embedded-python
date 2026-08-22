# Project page spec — what the page contains and what each cell must satisfy

The page at `humem.ai/projects/arcadedb` is the PRIMARY artifact. The paper draws
from it. This file is the contract: what tables exist, what rows and columns they
carry, which figures are published, and what a cell must satisfy to be printed.

`PROTOCOL.md` says how a number is produced. `FAIRNESS.md` says when two numbers
may be compared. This file says what gets shown. If they disagree, PROTOCOL wins
on production and FAIRNESS wins on comparison; this file never licenses a cell
those two would refuse.

---

## 0. The four rules every published cell obeys

1. **Serial, full cpuset.** Every published latency, throughput, percentile and
   memory cell runs one at a time on mini's `cpuset 0-11` (the 12 P-core THREADS
   on 6 physical P-cores; see 0a), `workers=1`, `tier=paper`. Parallel shards exist for sweeps and exploration only and may
   never reach the page. Enforced: `runner.py` refuses `workers != 1` at paper
   tier; `load_canonical` drops partial cpusets.
   *Known violation to clear: the 30 dense `deep10m` comparator rows are
   `tier=sweep`. They must be re-run at paper tier before the dense 10M table is
   published again.*
2. **N=5, median [min-max].** Five repetitions per cell. Any table with a cell
   below n=5 states its n in a condition, and no page sentence may assert an n
   that a cell it covers does not meet.
3. **One engine commit per table.** Every ArcadeDB row in one table comes from the
   same upstream commit, stamped as `engine_commit`. Comparators are digest-pinned
   images. See §1.
4. **One corpus per table.** Every row in a table describes the same dataset at
   the same size. A table whose rows disagree on `n_docs` (or the lane's size
   field) is a defect, not a comparison.

---

## 0a. The machine

Every published number is measured on **mini**. The laptop is a development
host: it compiles, it runs probes, and nothing it produces reaches the page.

| | mini (bench host) | laptop (dev only) |
|---|---|---|
| CPU | 12th Gen Intel Core i9-12900HK | Intel Core Ultra X9 388H |
| topology | 1 socket, 14 cores, 20 threads: 6 P-cores with SMT (12 threads) + 8 E-cores | 16 cores, 16 threads, no SMT |
| `cpuset 0-11` | the 12 P-core threads, verified by max frequency: cpu0-11 report 4900 MHz, cpu12-19 report 3800 MHz | n/a |
| RAM | 61 GiB | 30 GiB |
| storage | Samsung SSD 980 PRO 2 TB NVMe (root, `/home`, `/var/tmp`, all bench data) | Samsung MZVL22T0HDLB 1.9 TB NVMe |
| OS / kernel | Ubuntu 26.04 LTS, 7.0.0-30-generic | Ubuntu 26.04 LTS, 7.0.0-29-generic |
| Docker | 29.7.2 | |

Three things about that table are load-bearing and must be said on the page,
not just recorded here:

**`cpuset 0-11` is 12 THREADS on 6 PHYSICAL CORES, not 12 cores.** SMT is on
(`/sys/devices/system/cpu/smt/control` = `on`). A reader who assumes 12 physical
cores will over-estimate what a parallel build had available, and every
"12-core" phrasing in our own prose is wrong.

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

Eleven today, plus five added by the current plan. Every table needs: an id, a
title, a dataset line, explicit columns, explicit rows, a source link to a
tracked artifact, and its conditions.

### Vector

| id | title | rows | columns |
|---|---|---|---|
| `l3s` | Sparse vector search | ArcadeDB emb int8 / emb fp32 / srv int8, Elasticsearch, Milvus, Qdrant | p50, **p95**, **p99**, recall@10, build s, peak mem |
| `l3smp` | Sparse: what a second pass buys | same six | cold p50, warm p50, gain, **recall@10** |
| `l3s_nocompact` | **NEW** — what the settle step buys | ArcadeDB emb int8 with/without COMPACT | p50 at 100k / 1M / 8.84M, ratio |
| `l3d` | Dense vector search | ArcadeDB emb fp32 / srv fp32 / emb int8, Chroma, DuckDB-VSS, LanceDB, Milvus, Qdrant, sqlite-vec | cold p50, **cold p95/p99**, warm p50, recall@10, build s |
| `l3d_params` | **NEW** — matched operating points | every dense arm | ef_construction, ef_search, degree_param, degree_family, quantization, index kind |

Scales: `l3s` 100k / 1M / 8.84M; `l3d` 1M / 9.99M.

`l3d_params` exists to make the maxConnections-32-vs-M-16 argument checkable
rather than assertable, and to disclose that sqlite-vec is `exact_scan_no_ann` —
brute force, not an ANN index.

### Graph

| id | title | rows | columns |
|---|---|---|---|
| `l2` | Graph traversal | ArcadeDB emb / srv, LadybugDB, Neo4j | point p50, 1-hop p50, 2-hop p50, **2-hop p99**, **point p99**, write p50, peak mem |
| `l2olap` | Graph analytics ± the view | ArcadeDB emb GAV / emb / srv GAV, LadybugDB, Neo4j | three query times, **view build s**, peak mem *(annotated or dropped, see §4)* |

Scales: `l2` SF1 + SF10; `l2olap` **SF1 + SF10** (SF10-only cannot show whether
the view's benefit scales; 20 SF1 rows are already frozen).

`l2` needs p99 because the p50 headline reverses there: 2-hop SF10 is 20.28 ms
against Neo4j's 10.10.

### Tabular and time series

| id | title | rows | columns |
|---|---|---|---|
| `l1` | Tabular OLTP and OLAP | ArcadeDB emb / srv, DuckDB, PostgreSQL | read p50, insert p50, **update p50**, OLTP ops/s, **ingest rows/s**, OLAP total, peak mem |
| `l1olap` | **NEW** — OLAP breakdown | same four | the five analytical queries, one column each |
| `l1tpc` | TPC-H / TPC-C | same four | Q1, Q6, new-order p50, OLTP ops/s, peak mem |
| `l4` | Time series | ArcadeDB native TS / doc path, QuestDB, DuckDB | ingest pts/s, newest reading, 12h aggregate |
| `l4_tentag` | **NEW** — schema fidelity | same four | one-tag vs ten-tag, ratios only |

`l1` must publish ingest rate beside OLTP ops/s: publishing the win without the
loss is selective. `l1olap` turns one unexplained 70,807 ms cell into a
structural row-store-vs-column-store story.

`l4` is BLOCKED until QuestDB's WAL-apply poll moves outside its timed ingest
region (see §5).

### Cross-model, deployment, embedded

| id | title | rows | columns |
|---|---|---|---|
| `e2` | Cross-model transaction | ArcadeDB, Qdrant+Neo4j, SurrealDB | p50, p99, peak mem, **CPU s** |
| `e2_atomicity` | **NEW** — what survives a crash | same three | trials, crash raised, torn count, disagreeing products |
| `e4` | What the client/server split costs | 1 … 100,000 rows | in-process, in-process HTTP, separate container, packing cost, separate process, **p95/p99** |
| `pycost` | What Python costs | Java, Python, to_columns, to_json_list, to_list | **p50** (not mean), vs Java |
| `pyingest` | **NEW** — the write side | serial SQL, async parallel, insert_many, insert_many parallel | rows/s |
| `pysweep` | **NEW** — where the tax comes from | one-column vs group-by | ratio at 1k / 10k / 100k |

`e2_atomicity` is the page's strongest claim and currently the only major one
with no table: 40/40 torn for the composed stack against 0/40 for ArcadeDB and
SurrealDB, and 235 of 1,500 products left disagreeing.

`pycost` currently prints column 6 of `mini_results.csv`, which is the **mean**;
p50 sits unused in column 7. It is the only "ms" column on the page that is not
a p50.

### Operating it — NEW SECTION

| id | title | rows | columns |
|---|---|---|---|
| `lifecycle` | **NEW** — open and close cost | empty, doc, doc_idx{1,10,30}, hash, fulltext, geo, sparse, ts, graph, graph_gav, vector, vector2, mixed | **cold open ms**, warm open ms, close ms clean / read / write, at 10k and 100k |
| `ops_build` | **NEW** — load and build cost | every engine, every lane | build s, rows/s |
| `ops_recovery` | **NEW** — crash recovery | ArcadeDB, 2 WAL settings | trials, contiguous, duplicates, recovery s |
| `ops_failover` | **NEW** — Raft failover | 3-node ArcadeDB | trials, acked writes present, ambiguous, election s, failover s |
| `ops_start` | **NEW** — cold start | ArcadeDB emb / srv, LadybugDB, Qdrant, sqlite-vec | create+DDL s, reopen ms, connect s |
| `ops_disk` | **NEW** — on-disk footprint | every engine, every lane | bytes after the engine's own settle step (see §4a) |

`lifecycle` is both a page table and a regression gate — see §4.
`ops_disk` needs `runner.container_disk` wired; it is implemented and carried by
zero frozen rows.

---

## 3. Figures

Six maximum. A figure per table is a gallery, not an argument.

| stem | status | contents |
|---|---|---|
| `f4_one_vs_n` | published, needs fix | ArcadeDB vs best specialist at equal recall, log ratio. MUST include the two worst rows (graph analytics 0.11x, tabular OLAP 0.0015x) or stop calling itself the whole evaluation. |
| `f7_e2_hybrid` | published | cross-model transaction latency |
| `f8_deployment` | published | embedded vs server across result sizes |
| `f3_sparse_perquery` | blocked on data | per-query latency vs summed posting length, Spearman 0.95. Unblocks when sparse_cliff rows carry `engine_commit`. |
| `f6_memory_ceiling` | BLOCKED | peak anon at DEEP-10M. Draws NO ArcadeDB bar today. Needs ArcadeDB `peak_anon_mib_sum` at deep10m AND comparators re-run at matched envelope. |
| `f9_build_cost` | **NEW** | build seconds per engine per lane, log scale. The largest ArcadeDB deficit on the page and currently only trailing columns. |
| `f10_lifecycle` | **NEW, candidate** | close ms vs rows, per situation, log-log. Only if `lifecycle` shows the O(stored) shape after the current fixes; if close is flat everywhere the table suffices. |

Deleted and NOT to be resurrected: `f5_sparse_scaling` — it captioned a real
8.84M measurement as a synthetic corpus.

---

## 4. Close cost is a bug, not a table column

Close and open cost get a page table AND an invariant, because a slow close is a
defect and this engine has produced three of them (#5747, #6489, #5872).

**The invariant, from `lifecycle-open-close.md`:**

> Close should be **O(what was written), not O(what is stored)**, and on the
> order of **100 ms**.

Grounded twice: close should not cost more than getting started (JVM startup is
~160 ms here), and it should sit under the ~100 ms at which a script stops
feeling instant.

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
**34,504 ms** at 1M. Re-running it on the frozen commit is a before/after of our
own fixes and the first honest answer to "what does it cost to close".

**Still open and worth pursuing** (each is a candidate upstream issue, not a
caveat to write around):
- 0.40 ms per index on close, independent of index content, vanishing on tmpfs
  → it is I/O, and 30 indexes is not an unusual schema.
- The Graph Analytical View is REBUILT on every open, not loaded: only the
  definition is persisted and the CSR is re-derived by scanning the graph. So
  the 5.9x traversal speedup is paid with a full graph scan per session, which
  wins over a long session and loses over a short one. That belongs beside the
  5.9x, and the fix (lazy-on-first-use, or persist the CSR) is upstream work.
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
reps of a running one. Disk is not a published column today, and measuring it
at a slightly wrong point costs far less than breaking every cell.

## 4b. GAV is measured with the view ON and OFF, everywhere

The Graph Analytical View is an ArcadeDB-only accelerator, so an unablated number
is a claim about a configuration rather than about the engine. Every graph OLAP
cell runs BOTH arms:

    {embedded, server} x {SF1, SF10} x {BENCH_GAV=1, BENCH_GAV=0}   = 8 cells

Frozen data covers **one** of those eight (embedded SF10, `gav=False`). The view's
build cost is charged to the arm that builds it, and published as a column.

Labelling: `l2_graph.main()` stamps `out["gav"]` as a real boolean and sets
`backend_arm="nogav"` for the off arm, which is correct. But every GAV-ON row in
the frozen set carries `gav=''` because it predates that stamping, and `''` is
also what every non-graph lane carries — so an empty string means both "view on"
and "view irrelevant here". The next campaign fixes this by construction; until
then the two arms are told apart by an absence.

`BENCH_GAV` is in the runner's env allowlist. It was once missing, which would
have built the view anyway and written rows labelled as the ablation, rc=0,
indistinguishable from a real one.

**The ablation must use the lane's real query set, not a stand-in.** Measured
2026-08-21 on a 100k-vertex, 400k-edge synthetic graph at engine `3ec4f07e0`:
an openCypher two-hop count (`MATCH (a:P)-[:E]->(b:P)-[:E]->(c:P) RETURN
count(*)`) is **7% SLOWER** with the view than without, stable across session
lengths 1, 2, 3 and 5 (1.08x, 1.06x, 1.07x, 1.07x). The published 5.9x speedup
comes from the lane's property-aggregation queries over neighbourhoods, which
is a different access pattern. So the view's benefit is query-shape dependent,
and a probe that substitutes a convenient query measures nothing about the
view the page publishes.

What the same measurement DOES establish, and what belongs beside the 5.9x: the
view's fixed cost per session is real and large. A session that opens and closes
without querying at all costs **414.6 ms with the view against 11.5 ms without,
36x**, because the CSR is rebuilt by a full graph scan on every open
(`CSRBuilder: 100000 nodes, 400000 edges, 4.2 MB, 384-622 ms` on every open).
The 5.9x is a within-session property that each open re-pays.

---

## 5. Blocked cells — what may not be published today

| what | why | clears when |
|---|---|---|
| ~~`l3s` medium, Milvus + Qdrant~~ | ~~pools two corpora~~ | **CLEARED 2026-08-21**: `PAPER_CORPUS` in `load_canonical` admits only the corpus each tier publishes, fingerprinted on `(n_docs, dims)`. Rows still need re-publishing |
| `l3d` deep10m, all comparators | `tier=sweep`, envelope 28g/16g against ArcadeDB's 36g/24g, `version_name: null` | re-run at paper tier, matched envelope, pinned versions |
| `f6_memory_ceiling` | draws no ArcadeDB bar | ArcadeDB deep10m memory rows exist |
| `l4` ratios | QuestDB's WAL-apply poll was inside its timed ingest. **Code fixed 2026-08-22** (`QuestTS.settle()` runs outside the timer); the published rows still carry the old timing | l4 is re-run |
| `l4` ArcadeDB native TIMESERIES row | comes from `l4_native_probe.py`, a BESPOKE PROBE, not the lane script, and runs two opt-in fast paths (`TS_PRIMITIVE=1`, `TS_NUMPY=1`) that no comparator gets. FAIRNESS F6b is precisely "bespoke drivers investigate, lane scripts publish". The 1.86M pts/s headline is a probe number sitting in a table of lane numbers | the native arm is promoted into `l4_tsbs.py` as a fourth backend and re-run, or the row is withdrawn |
| any peak-memory comparison across ArcadeDB variants | `-Xms=-Xmx` commits the heap, so the column measures reservation, not demand | never — state it beside every such column |
| `postgres_tuned` | has never run: 0 rows, display name only | it runs |
| `hosts_recorded` | 100 container IDs annotated "(host unknown)"; a row records a container id, not a host | do not render it. Publish the 0a machine block instead, which is read from `lscpu`/`lsblk` rather than derived from a row |

---

## 5a. What still needs measuring

Ordered by whether a published cell depends on it.

**Blocking a cell that is on the page today:**

| measurement | cost | why |
|---|---|---|
| l4 re-run with the corrected ingest timer | ~2 h | the code is fixed; the rows are not |
| native TIMESERIES promoted to the lane, then re-run | ~4 h | a probe number cannot sit in a lane table (F6b) |
| dense comparators at deep10m, paper tier, matched envelope, pinned versions | ~2-3 d | three independent disqualifiers on the current rows |
| `f3` sparse per-query re-run with `engine_commit` stamped | ~4 h | unblocks the best unbuilt figure |

**New tables the page does not have yet:**

| measurement | cost | status |
|---|---|---|
| lifecycle: cold/warm open, close x3 modes, 8 situations, 2 sizes | ~3 h | lane BUILT and smoke-tested; needs a campaign run on the frozen pair |
| on-disk footprint | free | lands automatically now; qO rows already carry `disk_data_mb` |
| crash recovery, Raft failover, cold start | free | measured, never published |
| load and build cost table | free | in frozen rows already |
| atomicity table (torn counts) | free | in frozen rows already |
| ingest A/B, jpype size sweep, nocompact ablation, l2olap SF1 | free | in frozen rows already |

**Ablations, worth running but blocking nothing:**

| measurement | cost | why |
|---|---|---|
| `graphBuildCacheMaxHeapPercent` sweep at `small` (10/25/40/60, both quantizations, N=3) | ~2 h | we publish the engine default with no evidence it is good. Stage 1 only; escalate to deep10m only if the curve has shape |
| GAV on/off at the missing 7 of 8 cells | ~4 h | an ArcadeDB-only accelerator with one ablation cell is a configuration claim |
| int8 disk overhead (#3143 revisit) | ~1 h | our own issue, closed COMPLETED in May, yet int8 measures 13% MORE disk than fp32 at deep10m (8773.8 vs 7744.6 MB) |
| pgvector arm | ~2-3 d | the most conspicuous absence |
| single-engine E2 alternative (Neo4j native vector index) | ~2-3 d | tests the "any other pair" claim |

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
