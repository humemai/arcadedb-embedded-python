# Protocol: How a Number Is Produced

Every published number is one cell: one engine, one workload, one corpus size, repeated
five times on one machine with nothing else running. This page summarizes what a cell is
given, what it records, and what a comparison has to satisfy before two cells may be
printed beside each other.

This page is the reader-facing summary. The rules themselves live in
[`PROTOCOL.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PROTOCOL.md)
and [`FAIRNESS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/FAIRNESS.md),
where each rule carries a tag saying what enforces it: a gate that refuses, a check that
runs only when someone runs it, or nothing at all. If you change how a number is produced,
read those two files, not this page.

## One Machine, One Job at a Time

Every published number is measured on one host, a mobile-class Intel Core i9-12900HK with
64 GiB of memory and an NVMe disk. The full environment table is in the
[setup section](https://humem.ai/research/dbbench) of the DBBench page. Development
machines compile, run probes, and smoke new adapters, and nothing they produce reaches the
page.

- **`cpuset 0-11` is twelve hardware threads on six physical cores.** SMT is on. The same
  string selects different cores on another machine, so a number measured elsewhere is not
  comparable with one on the page.
- **Frequency is not pinned.** The power mode is left as the machine ships, because pinning
  the clock would lower every absolute number. Every row records the package temperature
  and the kernel's throttle counters at the start and end of the cell, so a hot cell is a
  number rather than a suspicion.

Concurrency is free exactly where nothing is being measured (downloads, image builds,
exploration sweeps) and nowhere else. Every latency, throughput, percentile, and memory cell
that reaches a table runs serial on the full `cpuset`, and the runner refuses more than one
worker at the publishing tier. A cell measured two-at-once is exploration forever.

## The Envelope

- **One CPU set, shared.** Every container in a published cell gets the full `cpuset`, and a
  client and server pair shares it.
- **One memory cap per lane and size, identical for every engine.** A served engine sees
  exactly the cap an embedded engine of the same tier sees, and its client gets a separate
  budget on top.
- **One JVM heap per tier, identical for every JVM engine.** The heap a row records is the
  heap the engine **ran**, read back out of the container, not the heap the cell asked for.
  The cap on the heap (`-Xmx`) is the same for every JVM engine; the initial heap follows each
  engine's own documentation. Embedded ArcadeDB leaves `-Xms` unset, as the Python bindings
  document, and the server engines keep the initial heap their vendors recommend.
- **Raising a resource for one engine obliges a re-measure of every engine at that tier.**
- **Neo4j and Elasticsearch run their vendors' memory rules.** Neo4j takes the heap and page cache
  that its own `neo4j-admin server memory-recommendation` prints for the cell's memory cap, and
  Elasticsearch a heap of at most half the cap and under the compressed-oops threshold (26 GiB).
  Both keep the initial heap equal to the maximum, as their documentation recommends, and every
  engine still gets the same memory cap.

!!! note "The memory contract cuts against ArcadeDB, and is kept anyway"
    The JVM heap lives inside the container cap, so ArcadeDB's heap leaves the rest of the
    cap for JVM overhead and page cache while a non-JVM comparator has the whole cap for
    its own use. Equal caps are what can be enforced, so equal caps are what is enforced.

## What the Instrument Does

The harness measures one instrument, `2026-11`, and every row is stamped with it. These
choices are part of it, the same for every cell:

- **A warm-up before the sparse search.** Every sparse engine runs 1,000 untimed searches on
  queries that are not in the timed set, so a query or result cache cannot flatter an engine.
- **The CPU idle state is held for each timed cell**, at the lowest latency target, so a
  single-client time under a millisecond does not include a core waking up. A cell that
  cannot take the hold still runs, and the row says so.
- **The dense lane indexes the vector id** on every engine that would otherwise scan for the
  record it deletes, so the delete column compares indexed lookups.
- **The served ArcadeDB arms use the vendor's official Python driver as the headline**, and
  the same cell runs again on the lean HTTP client of this harness as a labelled sensitivity
  row. Bulk loads and transactions stay on the lean client.
- **Large results are read on each engine's documented bulk path** (Arrow for ArcadeDB
  embedded and DuckDB), with the plain-Python read timed beside it. Small results do not
  move.

## Repetitions, and What a Cell Prints

**Five repetitions per cell, reported as the median with the minimum and maximum.** Not the
mean: the spread is the part that says whether the median is worth anything. Operation
counts per repetition are properties of the lane, fixed before a driver is written, and the
page prints them as generated conditions.

**Cold and warm are the same run.** The first iteration after the database opens is the cold
number and the remaining iterations are the warm one.

**Three things stop work, and each is a property of the work, not of the engine.** A query
has a time budget, derived from the bench host's own rows and never chosen per engine; a
query that exceeds it stops at the iteration it reached, and the table says so. A whole cell
has a time cap, identical for every engine at that size; an engine that cannot finish inside
it is published as censored with the cap named, not as a gap. A query whose budget cannot
buy a median is abandoned after its first pass, with the reason on the row.

**Every table reports the same measurement set**, or states why not: a warm median per
query, a ninety-ninth percentile for the headline query, one cold column, throughput and
recall where they apply, peak memory, on-disk size, and ingest and index build as separate
timers where the engine has that boundary. There is deliberately **no per-table aggregate**:
a mean across queries whose times span orders of magnitude is the slowest query in
disguise, so each query gets its own column.

## Matched Operating Points

Every engine runs as shipped, and a default is overridden only in four sanctioned cases:
resource fitting to the cell's CPU set and memory envelope; each engine's own documented
bulk-load settle step, timed inside the build; moving engines onto one quality-against-latency
point (for vectors, the same effective base-layer degree, or a recall calibrated against our
own frozen rows), because a latency comparison at unequal recall compares nothing; and a
documented escape hatch for a demonstrably pathological default. Per-system expert tuning
beyond vendor guidance never happens, and neither does tuning ArcadeDB with insider
knowledge that is not applied to the comparators.

!!! warning "An override nobody can find is a defect, whichever way it moves the number"
    Every override is stamped on the row where a field exists, and the full inventory, with
    a column saying which way each one moves the number, is published in the methodology
    section of the DBBench page. Several of them run against us.

## Durability

A commit that waits for the disk and one that does not are different operations, so a write
latency is a comparison only if every engine in the table committed the same way.

The matched class is **relaxed**: a commit returns without waiting for the disk, and the log
is flushed by the engine's own background policy. That is ArcadeDB's own default, and each
comparator is set to its own documented production mode for the same class. Every setting
is **read back out of the engine** rather than assumed, and the row records what it ran.

**Every timed write runs twice, once at each setting**, and the page prints both with the
ratio between them. Engines with no setting to relax are named on their own tables and
print one number in both columns. Bulk ingest runs at a single setting on every lane.

!!! note "The framing cuts both ways"
    The strict setting is a fixed per-commit tax set by the device, so engines converge when
    they all wait. A published relaxed write measures how well an engine avoids the disk as
    much as how fast it writes.

## The Fairness Invariants

`fairness_check.py` is one of the gates that runs before a publish. It exists to close one
failure mode the other checks cannot see: **a correct number measured under conditions the
row beside it did not get**. The invariants, in short (the full list with its enforcement
tags is in
[`FAIRNESS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/FAIRNESS.md)):

- **Same resources.** Same CPU set (F1), same memory envelope and verified heap (F3), thread
  pools fitted to the CPU set and not to the host (F6), and a CPU set that equalizes use,
  not only the resource (F8).
- **Serial only (F2).** A parallel shard shows up afterwards as a partial CPU set and is
  dropped.
- **Same protocol (F4).** Repetitions, warmup, settle step, and query set belong to the lane,
  not to whoever wrote the driver.
- **Same engine line within a table (F5)**, and a control when only one engine is
  re-measured (F9).
- **Same operating point.** Same effective base-layer degree across dense backends (F7), and
  equivalent index support chosen by measurement (F14).
- **Same durability class per table, on one instrument (F10)**, with both classes on every
  timed write (F10b).
- **Same answer (F11).** Equivalent queries must return equivalent answers; see
  [Answer Checking](equivalence.md).
- **Same measurement set and no aggregate (F12)**, and a clean close that stays proportional
  to what was written (F13).

## Engine Identity and Pins

ArcadeDB is pinned by **upstream commit**, not by a release number, because the build line
reads the same development version for every commit. Every row carries the short commit that
both the wheel and the server image were made from, and the page prints it as the engine
identity. Embedded and server arms in one table are built from the same commit and run the
same JVM, verified by a script, so the axis between them is transport and nothing else.

Comparators are pinned by immutable image digest, and the version a row publishes is what the
engine reported at connect time, never the image tag. A campaign freezes one pin and holds it
start to finish; a fix that lands mid-campaign becomes a candidate for the next re-pin.

## What Happens Next

- [Answer Checking](equivalence.md) covers the invariant that a latency is only worth
  printing if the engines agreed on the answer.
- [Running a Lane](running.md) walks one lane end to end.
- [Reading the Output](results.md) covers the frozen rows and the gates that stand between
  them and the page.
