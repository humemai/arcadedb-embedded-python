# The fairness contract

Every number in the paper compares systems. A comparison is only worth
printing if both sides were given the same thing. This file says what "the
same thing" means, what is allowed to differ, and what is checked
mechanically rather than remembered.

Run `python3 fairness_check.py` before regenerating tables and at the freeze.
It fails loudly rather than warning quietly.

## Why this file exists

Three violations were found on 2026-07-31, in one afternoon, by asking a
question no check asked: not "is this number right" but "was the row next to
it given the same resources and the same treatment". All three favoured
ArcadeDB. None was caught by claims_check or provenance_check, because both
of those verify a number against its own artifact, and every number here was
correct about its own run.

That is the failure mode this contract exists to close: **a correct number
measured under conditions the row beside it did not get.**

## Invariants (must hold; checked)

**F1. Same cpuset.** Every container in a published cell gets the full
`0-11` (the 12 P-threads). Client and server topologies share that cpuset
deliberately, so CPU competition stays inside the deployment under test
rather than being hidden by giving the server its own cores.

**F2. Serial only.** Published cells run one at a time. `runner.py` forces
`workers=1` on the paper tier and errors otherwise; queue scripts enforce it
again with `guard()`. The parallel sweep tier (disjoint cpuset shards,
shuffled order) exists for exploration and must never reach a table. Sweeps
did run, at `l2 sf1`, `l2 sf10` and `l3s micro` — a published row from one is
detectable as a partial cpuset such as `0-5`.

**F3. Same memory envelope per (lane, scale).** Every backend at a tier gets
the same `--memory`/`--memory-swap` cap and, for JVM engines, the same heap.
A client/server backend gets the envelope **split**, not doubled:
`server = 0.75 * total`, `client = total - server`, so the pair sums to what
an embedded cell gets in one container.

**F4. Same protocol.** Reps per build, warmup count, settle step and query
set are properties of the LANE, not of whoever wrote the driver. If ArcadeDB
gets five passes over one build, so does every comparator. If one engine gets
a post-ingest settle, all of them do.

**F5. Same engine line within a table.** A row measured on a different
release than the row beside it compares versions while appearing to compare
configurations. This is what made T5's server build cell wrong.

**F6. Thread pools are fitted to the cpuset, not to the host.** F1 pins the
cpuset, which bounds which CPUs a process may run on. It does not bound how
many threads the process decides to start, and several runtimes size their
pools from the host core count regardless of the mask they were given. That
is not equal treatment: an engine running 20 threads on 12 CPUs pays context
switching its 12-thread neighbour does not.

The call that sees the restriction is `sched_getaffinity`. **`os.cpu_count()`,
`nproc --all` and `/proc/cpuinfo` report the host and ignore the mask**, so any
of them appearing in an adapter is this bug.

Plain `nproc` is the exception and **does** respect affinity — verified, not
assumed: under `taskset -c 0-11` on a 16-CPU box, `nproc`=12 while
`nproc --all`=16 and `/proc/cpuinfo`=16. An earlier version of this section
said `nproc` ignored cpuset, copied from queue64's own interpretation line,
which is wrong. Corrected here because a fairness document asserting a false
fact about the measuring tool is worse than saying nothing.

Fitting the pool is the first of the four enumerated fairness overrides
(resource fitting) in the config policy, the same one that sets JVM heap per
tier, so it is applied rather than merely disclosed.

*Measured 2026-08-01 (queue64 on mini, and confirmed locally under `taskset`):*

| runtime | evidence | verdict |
|---|---|---|
| **DuckDB** | default `threads`=20 under a 12-CPU cpuset, in the real bench image; `taskset -c 0-11` on a 16-CPU box still yields 16 | **HOST-DERIVED.** Fixed: `l1_tabular.py` sets `PRAGMA threads` from `sched_getaffinity` |
| Qdrant | `actix-rt` runtime 11 threads, update pool ~11, from `/proc/<pid>/task` | cpuset |
| Elasticsearch | `_nodes/os` reports `available_processors: 12`, `allocated_processors: 12` | cpuset |
| Neo4j | 10 `GC Thread#N`; G1 derives `8 + (N-8)*5/8` above 8, so 12 CPUs gives 10 and 20 would give 15 | cpuset |
| ArcadeDB (JVM) | `availableProcessors()` reads the cgroup on Java 11+ | cpuset |
| Chroma, LanceDB, sqlite-vec | embedded in the driver, no separate server pool | n/a |
| Milvus | its own metrics report `go_sched_gomaxprocs_threads 12`; Go sizes from `sched_getaffinity` | cpuset |

**Measured 2026-08-01. Audit complete across all seven comparator runtimes: DuckDB is the only offender.**

Two corrections worth keeping, because the wrong answers were nearly recorded:

*Total OS threads is not pool sizing.* A first sweep counted threads per server
and flagged anything above `cpuset+4`. Elasticsearch came back 88 and Neo4j 83,
both reported as host-derived. Both are wrong: a JVM server runs dozens of
threads (GC, JIT, JMX, acceptors, per-index pools) irrespective of cpuset. The
question for a JVM is `availableProcessors()` and the named pool settings, and
by that measure both fit the cpuset exactly.

*"What qdrant sees" saw the container.* The original queue64 line ran `nproc`
and `/proc/cpuinfo` inside the container and labelled both `qdrant sees:`. They
disagree because `nproc` respects affinity and `/proc/cpuinfo` does not, and
neither asks Qdrant anything. Its real pools are cpuset-shaped.

Consequence for published numbers: every DuckDB cell measured before this fix
ran oversubscribed. The bias runs **against** DuckDB, which wins that lane
regardless, so nothing self-serving rests on it — but the tabular rows must be
re-measured at the freeze rather than carried over.

**F7. Same effective base-layer degree across dense backends per scale.**
Enforced by `fairness_check.py`. Engines spell graph degree differently: one
takes the per-layer `maxConnections`, another takes the base-layer degree,
and the same integer therefore builds two different graphs. Comparing them at
one nominal `M` compares an accident of naming. Recorded per row as
`degree_param` plus `degree_family` so the check reads the number in the unit
its own engine meant.

## Parallelism policy: maximise it, but never inside a published absolute

The standing direction is to use the machine, and it is the right one: mini
sits idle far more than it runs, and serialising work that does not need to be
serial buys nothing. But "run more at once" and "report this latency" are not
compatible everywhere, so the rule has to say exactly where the line falls.

**What parallelism does and does not fix.** Randomly permuting run order is
worth doing and we do it, but it buys one specific thing: it stops co-run noise
from landing preferentially on one configuration, so an A-vs-B **ratio** stays
honest. It does not remove the noise. Two jobs sharing an L3 and a memory
controller both run slower and both show fatter tails, and permutation cannot
restore an absolute level or a p95 that never happened. Our headline claims are
single-node absolutes and percentiles, which is exactly the quantity permutation
cannot repair.

So the split is by **what the number is**, not by how long the job takes:

| may run in parallel, freely | must be serial on the full cpuset |
|---|---|
| dataset download, decompression, ground-truth generation | every latency cell whose number reaches a table |
| docker image builds, wheel builds | every throughput/QPS cell |
| exploration sweeps and parameter scans | anything reporting p95/p99 |
| A/B probes whose answer is a **ratio** measured in the same run | memory working-set cells |
| any run whose output is a decision, not a table cell | scale-ceiling and RAM-bound cells (serial anyway) |

Two consequences worth stating plainly, because both have bitten:

1. **A parallel run cannot be promoted later.** If a cell was measured
   two-at-once, it is exploration forever; wanting the number afterwards does
   not make it eligible. `runner.py` forces `workers=1` on the paper tier and a
   sweep row is detectable after the fact by its partial cpuset (`0-5` rather
   than `0-11`), which is the audit trail that makes this enforceable rather
   than aspirational.
2. **Disclose the shape, not a co-run penalty per engine.** The paper says
   which classes of work were parallel and that every reported number was
   re-measured serially. It does not owe a per-engine perturbation table; that
   is detail nobody can check and it invites the reader to treat the
   exploration tier as if it were data.

**Sharding, when parallel is allowed.** Disjoint cpuset shards, never
overlapping, never crossing an SMT sibling pair, and the same shard width for
every arm of a comparison. Three 4-thread shards over `0-11`, not "whatever is
free". An arm given a wider shard than its neighbour is F1 violated with extra
steps.

**The open question.** F1 equalises the *resource*. It does not establish that
each engine *uses* the same amount of it: an engine that spreads one query over
12 threads and one that answers on a single thread are both "given 12 CPUs".
Nothing here checks that yet, which makes it the one axis where we cannot say
which way the bias runs. Being measured now (`~/f8_probe.sh`); when it lands it
becomes F8 with a number attached.

## Allowed to differ (must be DISCLOSED, per the config policy)

- **Vendor settle steps** that have no equivalent elsewhere (Elasticsearch
  forcemerge, Milvus flush+load, Qdrant green-wait, ArcadeDB `COMPACT INDEX`).
  Each engine gets *its own*; none goes unmatched by the others having theirs.
- **Operating points deliberately not matched**, e.g. the int8 dense row at
  16 GiB heap against fp32 at 24 GiB. Both appear in the table with the heap
  named in the row label.
- **Quality/precision differences** (int8 vs fp32 postings, ES pruning).
  Report recall next to latency, always.

Anything else that differs is a defect, not an override.

## Known violations and their status

| # | where | what differed | worth | status |
|---|---|---|---|---|
| 1 | T5 dense (F4) | ArcadeDB 1 build + 5 passes, table uses 2--5; comparators 5 builds + 1 pass each | 4.0--6.1x | disclosed in caption; queue61 re-measures comparators |
| 2 | T5 dense (F3) | envelope raised 28g/16g -> 36g/24g on 2026-07-20 and only ArcadeDB re-measured | 29% more memory | queue61 gives comparators 36g |
| 3 | T5 time series (F4) | ArcadeDB probe has a 30 s settle; `l4_tsbs` comparators have none | 2.23x one way, 2.5x the other | resolved: table prints the unsettled arm |

Violation 2 is the sharpest lesson. The envelope was raised for a good reason
(the fp32 build needed it) and the change was applied to the engine being
fixed. Nobody re-ran the six comparators, so a legitimate fix became an
advantage. **Raising a resource for one engine creates an obligation to
re-measure every engine at that tier.**

## The structural cause

Violations 1 and 3 are both rows produced by a *bespoke driver* rather than
the lane script. Protocol audit of every lane, completed 2026-07-31:

| lane | where timing lives | verdict |
|---|---|---|
| L1 tabular | shared loop, `WARMUP_OLTP=200` / `WARMUP_OLAP=1` for all | clean |
| L1 TPC | shared loop in `main()`, backend is a parameter | clean |
| L2 graph | shared loop, each backend implements its own `post_build` settle | clean |
| L3s sparse | one lane script for all seven backends | clean |
| E2 hybrid | shared loop in `main()`, `WARMUP=20` for all three | clean |
| L3d dense | comparators via the lane script, **ArcadeDB via overlay drivers** | violation 1 |
| L4 time series | comparators via `l4_tsbs`, **ArcadeDB via `l4_native_probe`** | violation 3 |

Every clean lane puts each backend through one script, so warmup and settle
are decided once and apply to everyone. Both violations are the two lanes
where an ArcadeDB row comes from somewhere else. Every bespoke driver was written to answer a narrow question (close
out an issue, verify a fix) and was later promoted to a published cell,
carrying whatever protocol its author needed at the time.

**Rule: bespoke drivers investigate, lane scripts publish.** If a driver's
output must become a cell, diff its protocol against the lane's first.

## Not yet verified

Equal *allocation* is not equal *honouring*. **Ran 2026-08-01 as queue64; see
F6 for the results and the fix.** The suspicion was half right and pointed at
the wrong engine: Milvus and Qdrant's clients read the cpuset correctly, and
the runtime that ignored it was **DuckDB**, which we had not suspected because
it is embedded rather than a Go/Rust server.

Qdrant and Elasticsearch are now answered in F6 (both cpuset). Still open:

- whether any engine's *disk* IO scheduling differs under the same cap.

## Corrected here, because this file asserted it wrongly for an hour

An earlier version of this section said ArcadeDB's sparse build "runs at
roughly 2 of the 12 allocated cores. That is a real engine property, not a
harness defect." **It is a harness property.** `ArcadeEmbedded.build` in
`l3_sparse.py` is a serial Python loop calling `newDocument`/`save` per
document, so about one core is a single producer thread and the rest is
engine background work. The engine was never asked for more, and the
measurement (214% against DuckDB-VSS's 1203% on the same cpuset) says nothing
about its parallelism.

Nor is it an unfairness: Qdrant, Milvus and Elasticsearch drive ingest from
the *same* serial `gen_docs` loop, batching into `upsert`, `insert` and
`bulk`. The producer is symmetric across all four; what differs after the
handover is architectural (in-process per-document JNI against one client
call per batch to a server that parallelises internally), which is the
deployment axis the paper already reports.

What survives is narrow and ours: embedded pays N JNI crossings per batch
where a client pays one. Sparse build time is not a published column, and
#5577 bounds the dense one at roughly 7% insertion, so no paper number moves.

The general rule this yields: **a CPU percentage is a fact about a container,
not about an engine.** Attributing one requires knowing who was asking for
the work.
