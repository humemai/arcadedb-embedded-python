# Protocol: How a Number Is Produced

Every published number is one cell: one engine, one workload, one corpus size, repeated
five times on one machine with nothing else running. This page says what a cell is given,
what it must record, and what a comparison has to satisfy before two cells may be printed
beside each other.

The rules themselves live in
[`PROTOCOL.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PROTOCOL.md)
and [`FAIRNESS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/FAIRNESS.md),
where each rule carries a tag saying what enforces it: a gate that refuses, a check that
runs only when someone runs it, or nothing at all. A rule the page depends on is not left
as a reminder to a human where it can be made a gate instead.

## One Machine

Every published number is measured on one host. Development machines compile, run probes,
and smoke new adapters, and nothing they produce reaches the page.

The bench host is a mobile-class Intel Core i9-12900HK with six performance cores and eight
efficiency cores, 64 GiB of memory, an NVMe system disk, Ubuntu, and Docker. The full
environment table is published in the
[setup section](https://humem.ai/projects/arcadedb#setup) of the project page.

Four properties of that machine are load-bearing enough to state rather than record:

- **`cpuset 0-11` is twelve hardware threads on six physical cores**, not twelve cores. SMT
  is on. Anyone who reads it as twelve cores will over-estimate what a parallel build had.
- **The same `cpuset` string means something different on another machine.** On a host whose
  kernel reports performance and efficiency cores in a different order, `0-11` selects a
  mix. This is one of the reasons a number measured elsewhere is not comparable with a
  number on the page.
- **Frequency is not pinned.** The governor is `powersave` and turbo is enabled, so a long
  build and a short query do not see the same clock, and sustained all-core work on a
  mobile part in a small chassis throttles in a way a server part would not. The power mode
  is left as the machine ships, because pinning the clock would lower every absolute number
  on the page. Instead, every row records the package temperature and the kernel's throttle
  counters at the start and end of the cell, so a hot cell is a number rather than a
  suspicion.
- **The bench disk is the NVMe.** The same machine holds a rotational disk, which is used
  for backups and holds nothing that is measured.

## One Job at a Time

Concurrency is free exactly where nothing is being measured, and nowhere else.

| Runs in parallel, freely | Must run serial on the full `cpuset` |
|---|---|
| Dataset download, decompression, and ground-truth generation | Every latency cell that reaches a table |
| Docker image builds and wheel builds | Every throughput cell |
| Exploration sweeps and parameter scans | Anything reporting a percentile |
| A/B probes whose answer is a ratio measured in one run | Memory working-set cells |

Permuting run order is worth doing and the harness does it, but it buys one thing: it stops
co-run noise from landing preferentially on one configuration, so an A-against-B **ratio**
stays honest. It cannot restore an absolute level or a tail that never happened, and the
published claims are single-node absolutes and percentiles.

Four things make the serial rule concrete on this host rather than merely principled. Peak
memory at the larger tiers means two cells leave nothing for page cache. Page-cache
residency is worth a great deal to a lazily loading engine and almost nothing to engines
that are resident from load, so a neighbour cell touching a different corpus moves one
column of the table and not the other. The package has one shared L3. And at the load one
cell puts on the machine, a second cell lowers the clock for both.

A cell measured two-at-once is exploration forever. Wanting the number afterwards does not
make it eligible, and the runner refuses more than one worker at the publishing tier so
that this is enforced rather than remembered.

## The Envelope

**One CPU set, shared.** Every container in a published cell gets the full `cpuset`. A
client and server pair shares that one set rather than each getting its own cores, so CPU
competition stays inside the deployment under test instead of being hidden by giving the
server cores of its own.

**One memory cap per lane and size, identical for every engine.** A cap is a ceiling rather
than a reservation, so an engine that needs less is not affected by a generous tier. A
served engine gets the full tier cap and its client gets a separate budget on top, so a
served engine sees exactly the cap an embedded engine of the same tier sees. Comparing a
served topology by adding client and server together reads as a much larger envelope than
the engine had.

**One JVM heap per tier, identical for every JVM engine.** The heap is half the cap, with
the largest dense tier the single stated exception at two thirds, and the runner prints the
policy at startup and marks any deviation. The heap a row records is the heap the engine
**ran**, read back out of the container, not the heap the cell asked for: a hardcoded server
heap is otherwise invisible in the artifact, and that has happened.

**Raising a resource for one engine obliges a re-measure of every engine at that tier.**
This is the sharpest rule here and the one that has been broken, when a dense envelope grew
for a legitimate reason and only ArcadeDB was re-measured, which turned a fix into a memory
advantage.

!!! note "The memory contract cuts against ArcadeDB, and is kept anyway"
    The JVM heap lives inside the container cap, so ArcadeDB's heap leaves the rest of the
    cap for JVM overhead and page cache while a non-JVM comparator has the whole cap for
    its own use. Equal caps are what can be enforced, so equal caps are what is enforced,
    and the consequence is stated rather than quietly enjoyed.

## Repetitions, and What a Cell Prints

**Five repetitions per cell, reported as the median with the minimum and maximum.** Not the
mean: a mean over five repetitions hides which one was slow, and the spread is the part
that says whether the median is worth anything. A table whose cell falls short of five
repetitions states its shortfall in a condition a reader sees, and the disclosure is deleted
when the shortfall is fixed.

Per repetition:

| Operation class | Count per repetition |
|---|---|
| Transactional operations | 1,000 |
| Each analytical query | 100 |
| Vector queries per pass | 1,000 |

Those counts are properties of the lane, fixed before a driver is written, and they are
printed on the page as generated conditions rather than typed into prose.

**Cold and warm are the same run.** The first iteration after the database is opened is the
cold number and the remaining iterations are the warm one, which costs nothing because
those iterations already run, and it answers the question a reader actually has: what does
the first query of a session cost against the hundredth. Where the split genuinely does not
apply, the table says so in a clause instead of leaving a blank. A transactional cell runs
against a warm database by construction, and the session-cost table is itself the cold
measurement.

**A query has a budget, and the cell does not die with it.** On the graph analytics and
time-series tables each query gets the same time budget on every engine. A query that
exceeds it stops at the iteration it reached, its numbers are over those iterations, the
table says so in a sentence naming the budget and the count, and the cell's other queries
keep theirs. Without this a slow scan on one engine took the whole cell past the timeout
and left nothing, which is the worse outcome: a censored cell is a measurement, an absent
one is a story.

**Every table reports the same measurement set**: cold and warm latency at the median and
the ninety-ninth percentile, throughput where the operation has a natural rate, recall where
the index is approximate, peak memory, on-disk size after the workload, and, on the vector
tables, ingest and index build as separate timers wherever the engine has that boundary. A
table that omits one of these carries a stated reason, which a gate enforces the way it
enforces every other page invariant.

There is deliberately **no per-table aggregate**. An arithmetic mean across queries whose
times span orders of magnitude is the slowest query in disguise, a median across them moves
when a query is added, and the only defensible summary is one people would quote without
its caveats. One column per query instead, with the cross-table ratio view left to the
[summary figure](https://humem.ai/projects/arcadedb#summary).

## Matched Operating Points

Every engine runs as shipped, and a default is overridden only where leaving it would make
the comparison meaningless. Four categories are sanctioned, and nothing else is:

1. **Resource fitting.** Heap, thread pools, and memory settings fitted to the cell's CPU
   set and memory envelope. Envelope equality, not tuning.
2. **Vendor settle step.** Each engine's own documented bulk-load-then-query preparation,
   timed inside the build so the build is timed to a queryable index. Every engine gets its
   own, and none is skipped.
3. **Operating-point matching.** Where defaults put engines at different points of a
   quality against latency tradeoff, they are moved onto one point, because a latency
   comparison at unequal recall compares nothing.
4. **Documented escape hatch.** A default that is demonstrably pathological, tuned to the
   vendor's own recommendation, with the same care applied to every backend in the lane.

What never happens: per-system expert tuning beyond vendor guidance, or tuning ArcadeDB
with insider knowledge that is not applied to the comparators.

Two examples of category three, because they are the ones that decide a vector table. Graph
degree is spelled differently by different engines, and the same integer therefore builds
graphs of different degree, so the lane matches **effective base-layer degree** and records
the number in each engine's own unit. An index that has no degree at all, such as an
inverted-list index over trained centroids, cannot be matched that way, so its operating
point is calibrated inside the cell to land on the same recall, against a target read from
our own frozen rows rather than chosen by hand.

!!! warning "An override nobody can find is a defect, whichever way it moves the number"
    Every override is stamped on the row where a field exists and named in reader-facing
    text, and the full inventory, with a column saying which way each one moves the number,
    is published in the methodology section of the project page. Several of them run
    against us, including an index the comparators do not get and a SQLite setting that
    makes SQLite faster on exactly the rows we would rather win.

## Durability

A commit that waits for the disk and one that does not are different operations, so a write
latency is a comparison only if every engine in the table committed the same way.

The matched class is **relaxed**: a commit returns without waiting for the disk, and the log
is flushed by the engine's own background policy, which loses the last committed
transactions on a power cut but does not corrupt the store. That is ArcadeDB's own default,
so the comparators are matched to us rather than the other way round, and each engine's
setting is a documented production mode: write-ahead logging with a relaxed synchronous
level for the SQLite family, asynchronous commit for the PostgreSQL family, an unjournaled
acknowledged write for MongoDB, and their own defaults for the engines already in this
class. Every one of those settings is **read back out of the engine** rather than assumed,
and the row records what it ran.

**Every timed write runs twice, once at each setting**, and the page prints both with the
ratio between them. The main tables keep the relaxed number as the headline, because it is
the matched class and the common deployment, and a small table beside them settles the size
of the effect. Engines with no setting to relax, which are named on their own tables, print
one number in the strict column and say so, which also puts them on an equal footing rather
than comparing their strict numbers against everyone else's relaxed ones.

Bulk ingest runs at a single setting on every lane. A bulk load commits in batches, so the
flush is amortised and a second build buys nothing; whether the loaders really do commit per
batch rather than per row is settled once by a check off the campaign rather than by a
column on every table.

!!! note "The framing cuts both ways"
    The strict setting is a fixed per-commit tax set by the device, so engines converge when
    they all wait, and the ratio between the two settings is inversely proportional to how
    fast an engine's relaxed path is. It follows that a published relaxed write measures how
    well an engine avoids the disk as much as how fast it writes. ArcadeDB embedded's fast
    relaxed document insert is what makes its own multiple one of the largest on that table.

## The Fairness Invariants

`fairness_check.py` is one of the gates that runs before a publish. It exists to close one
failure mode the other checks cannot see: **a correct number measured under conditions the
row beside it did not get**. Such a number is correct about its own run, so verifying it
against its own artifact proves nothing.

| | Invariant |
|---|---|
| **F1** | Same CPU set. Every container in a published cell gets the full set, and a client and server pair shares it. |
| **F2** | Serial only. Published cells run one at a time; a parallel shard is detectable afterwards as a partial CPU set and is dropped. |
| **F3** | Same memory envelope per lane and size, and the same heap for every JVM engine, verified as the heap that ran. |
| **F4** | Same protocol. Repetitions per build, warmup count, settle step, and query set are properties of the lane, not of whoever wrote the driver. |
| **F5** | Same engine line within a table. A row measured on a different release than the row beside it compares versions while appearing to compare configurations. |
| **F6** | Thread pools fitted to the CPU set, not to the host. Several runtimes size their pools from the host core count regardless of the mask, and an engine running twenty threads on twelve CPUs pays context switching its neighbour does not. |
| **F7** | Same effective base-layer degree across dense backends, read in each engine's own unit; an index with no degree is matched by effect instead. |
| **F8** | The CPU set must equalise **use**, not only the resource. Measured: no embedded engine parallelises a single nearest-neighbour query, so the comparison is of engines and not of thread counts. |
| **F9** | A kept row needs a control. When a campaign re-measures one engine and carries the others forward, one untouched comparator is re-run and its old-against-new delta is recorded beside the table it licenses. |
| **F10** | Same durability class per table, and one instrument. Rows measured under two instruments never share a table. |
| **F11** | Close cost is an invariant, not a column: close should be proportional to what was written and not to what is stored, and a clean close that exceeds the stated budget fails the gate. |
| **F12** | Equivalent queries must return equivalent answers. This one has its own page: [Answer Checking](equivalence.md). |

## Engine Identity and Pins

ArcadeDB is pinned by **upstream commit**, not by a release number, because the build line
reads the same development version for every commit and a version string therefore cannot
identify what ran. Every row carries the short commit of the upstream build that both the
wheel and the server image were made from, and the page prints it as the engine identity,
linked to the commit.

Embedded and server arms in one table are built from the **same commit and run the same
JVM**, verified by a script rather than asserted, so the axis between them is transport and
not JVM major version, collector, or object layout.

Comparators are pinned by immutable image digest, and the version a row publishes is what
the engine reported at connect time, never the image tag. Client libraries are pinned by
exact version, because an unpinned dependency is a comparator that changes when nobody is
looking, and that has happened.

**A campaign freezes one pin and holds it start to finish.** Upstream landing a fix
mid-campaign does not restart it; the fix becomes a dated changelog entry and a candidate
for the next re-pin. No table falls back to an older pin, anywhere.

## What Happens Next

- [Answer Checking](equivalence.md) covers the invariant that a latency is only worth
  printing if the engines agreed on the answer.
- [Running a Lane](running.md) walks one lane end to end.
- [Reading the Output](results.md) covers the frozen rows and the gates that stand between
  them and the page.
