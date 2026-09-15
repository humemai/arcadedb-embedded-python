# Reading the Output

A row is not a result. It becomes one by surviving an admission filter, a freeze, an export,
and four gates, and several of its fields mean something other than what their names
suggest. This page covers the path from a written row to a published cell, and the fields
that have actually misled people.

The single rule everything else follows from:

> **The tracker is history. The artifact is state.**
>
> Task notes, issue titles, and old summaries describe what was true when they were written,
> and they are not refreshed when the thing is fixed. Read the data before repeating what a
> note says about it.

## From a Row to a Cell

| Stage | Artifact | What it is |
|---|---|---|
| A campaign runs | `results/runs_<lane>_<pin>.jsonl` | The campaign's own rows. Until they are merged, this file is the only copy of its data. |
| Merge | `results/runs.jsonl` | The merged canonical store, append-only. Merging appends and never replaces, and refuses if it would shrink the canonical cell count. |
| Freeze | `results/runs_paper.csv` | The frozen rows every table is generated from. Regenerated from the store, never hand-edited. |
| Export | `results/web_benchmarks.json` | The page payload: every table, row, column, and condition the site renders. |
| Publish | The project page | Copied to the site, gated, and verified byte-identical to the file the gates read. |

Order matters, and it is not optional: a campaign file archived before it is merged is a
deleted campaign. A few tables also read **overlay directories** of per-cell files directly
rather than going through the store, and those directories are all-or-nothing: a partial
directory refuses the publish instead of quietly printing whichever subset of engines
happens to exist.

Most of `results/` is untracked by design. A developer checkout does not have the bench
host's tree, and a path being absent from yours is expected rather than lost.

## What May Reach a Table

The admission filter runs **before** the dedupe, so a bad row can never shadow a good one by
being newer. A row is dropped, not warned about, when:

- it did not exit cleanly;
- its size is not one of the sizes that lane publishes, so retired and exploratory tiers
  cannot reach a cell;
- its CPU set is partial, which is what a parallel exploration shard looks like after the
  fact;
- its engine version is a development or snapshot string on a line that publishes releases;
- a served row names no version and carries no image digest, because a bare `latest` is not
  a version and the pre-release guard cannot see through it;
- a witness field, such as the heap read back from the container, is absent **or** unequal,
  because bare equality would pass by matching one absence against another;
- a lane's mandatory evidence is missing, such as a sparse row with no recall number, which
  is the only thing distinguishing the real corpus from a generated one at some sizes.

What survives is deduped on the cell's identity with the newest timestamp winning, so a
re-measured cell supersedes the old one at merge.

!!! warning "An exit code is not evidence"
    Zero means a process finished, not that it measured what you asked for. Two defects of
    exactly that shape got through: a lane left on its generated fallback corpus produced
    rows across three sizes, every one clean, distinguishable from the real corpus only by
    the absent ground truth; and a heap that cells reported, stages reported, and the
    artifact asserted, which the engine never had. Acceptance compares the **data** against
    the specification, never the return code.

## Fields That Trap People

**A served row's disk is not the row's disk field.** The row keeps server plus client for
the record; the page prints the server container's growth alone, because the client is only
the driver. The row is in megabytes and the page is in gibibytes, so a value that looks a
thousand times too large under a gibibyte header is a skipped division, not a real
footprint. On-disk size is also a post-run reading taken after the queries, sampled until
two readings agree, and a cell that never converged says so rather than printing a bare
number.

**A digest is of the canonical answer, not of the raw rows.** It is taken after the answer is
put into canonical form: sorted unless the query defines an order, floats rounded, and
driver-specific row wrappers and column ordering removed. Two engines whose digests match
did not return identical result objects. Hashing what a driver handed back instead would
disagree on every engine pair for reasons that are not about the answer. See
[Answer Checking](equivalence.md).

**"Unexpressible" is a declaration, not a failure.** An engine whose adapter declares an
operation absent has said so deliberately, with its reason on the row. It is not a crashed
cell, not a timeout, not a gap to be filled, and not evidence that the engine is slow. A
silently missing answer is the failure, and telling the two apart is what the gate exists
for.

**The thermal fields are conditions, not diagnostics.** Every row records the package
temperature and the kernel's throttle counters at the start and end of the cell. The bench
host is a mobile-class part that bounces off its thermal ceiling under a long build, the
power mode is left as the machine ships by decision, and rows from different stages are
compared with those fields **read** rather than assumed equal. They are on the row so that a
hot cell is a number instead of a suspicion.

**`instrument` names the query set, the timers, and the durability rule the row ran under.**
Rows from two instruments never share a table, and the freeze and the exporter both refuse
one that does. The same column name can mean a different quantity under a different
instrument, which is exactly why the field exists.

**`durability` is what the engine ran at commit, read out of the engine** where it can be
read. The engines that have no setting carry a string naming them as the exception, and an
engine whose behaviour at commit could not be established says that instead of claiming a
class.

**A version field can be deliberately empty.** On one lane the ArcadeDB-stamped engine
version is right for the ArcadeDB row and wrong for every comparator, so the lane asks each
backend for its own version and leaves the shared field null. A wrong version that passes a
provenance audit is worse than none.

**An arm is selected by flag, not by filename.** Several files hold multiple arms of one
experiment, distinguished by a boolean on the row. Assert the flags rather than globbing the
directory.

**A timed-out row records where it died.** The client disk and memory at the timeout are
written on the timeout path, and the cell log carries the lane's phase markers. Read them
before recording a did-not-finish.

## Traps in the Other Direction

**An absent row makes a claim.** If comparators appear at a size and we do not, a reader
concludes we could not do that size. The exporter publishes only sizes where our engine also
has a row, and prints what it withheld and why.

**Real numbers can compose a false impression.** A table can be accurate in every cell and
wrong as a whole. Ask what a reader concludes, not only whether each figure is right.

**A negative number can be the finding.** One decomposition goes negative at the smallest
sizes, which is the term sitting below the design's resolution, and that is the evidence for
the claim it supports. It is published with the explanation rather than clamped to zero, and
the count of negative sizes is pinned so it cannot be quietly tidied away.

## How the Page Is Generated and Gated

Publishing is one command rather than a checklist, because a checklist has a step someone
skips. It regenerates the tables and figures from the frozen rows, exports the payload, runs
the gates, shows the diff, and only then builds, commits, and pushes.

The invariant it enforces: **every page table and figure is generated from frozen rows,
listed in the page manifest, pinned by a gate, and carries a source link to a tracked
artifact.**

Four gates run, and they answer different questions:

| Gate | Asks |
|---|---|
| `provenance_check` | Does every published cell trace back to a run, under conditions that were recorded rather than asserted? |
| `fairness_check` | Were the rows in one table given the same thing? F1 to F12. |
| `page_check` | Does every cell and every typed number on the page still agree with the generated tables? |
| `equivalence_check` | Did the engines of a table give the same answers? |

Some specifics that matter if you ever compare the page against the data yourself:

- **The page may show fewer numbers than the generated tables, never a different one.** A
  page cell covering a claimed measurement must agree within that claim's tolerance; a stale
  mapping fails, and an absent cell fails.
- **Tolerance is the number's own printed rounding**, half a unit in the last digit, so a
  wider window cannot pass a number the table no longer prints.
- **Every typed number in the page's prose is pinned to a named table column**, including the
  numbers in captions. A reworded sentence fails the gate rather than passing silently,
  which is deliberate: five caption ratios once stood stale on the live page after a re-pin
  because nothing pinned them.
- **A count is pinned alongside every zero.** "No torn results" is what a broken reader also
  produces, so the trial count is asserted beside it.
- **Conditions are generated, not typed.** Repetition and operation counts per table, and the
  durability note naming each table's engines, are computed from the rows that table shows.
- **After the copy, the served file is verified byte-identical** to the one the gates read.

!!! info "Where the rules live"
    [`READING-RESULTS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/READING-RESULTS.md)
    is the source for this page,
    [`RESULTS-MAP.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/RESULTS-MAP.md)
    says what every file under `results/` is and who reads it, and
    [`PAGE-SPEC.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PAGE-SPEC.md)
    is the contract for what the page contains and what a cell must satisfy to be printed.

## Checking the Tables Without Running Anything

The frozen rows and the page payload are published as a release asset with their pins. That
is the verification most readers want: you can recompute any table on the
[project page](https://humem.ai/projects/arcadedb) from the rows behind it, check a cell
against its own row, and see which cells were withheld and why, without a machine, a corpus,
or a container.
