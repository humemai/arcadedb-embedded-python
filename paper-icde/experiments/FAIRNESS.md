# The fairness contract

Every number in the ICDE paper compares systems. A comparison is only worth
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

Equal *allocation* is not equal *honouring*. A JVM on Java 11+ reads the
cpuset for `availableProcessors()`, so ArcadeDB sizes its pools to 12. Go and
Rust runtimes have historically read the host's full core count (20 here). If
Milvus or Qdrant sizes pools to 20 while pinned to 12, they oversubscribe and
pay scheduling we do not. Tracked as task #120; the check is seconds per
image but must wait for the box to be free.

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
