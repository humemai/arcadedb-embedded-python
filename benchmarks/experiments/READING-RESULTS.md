# Reading the results without misreading them

PROTOCOL.md says how a run is produced. FAIRNESS.md says what makes a
comparison legitimate. This file says how to read what came out, and exists
because every trap below was hit for real, most of them on 2026-08-11 while
building the humem.ai project page, and several of them produced a confident
wrong conclusion that survived until someone looked at the artifact again.

The single rule, from which most of the rest follows:

> **The tracker is history. The artifact is state.**
>
> Task notes, issue titles and old summaries describe what was true when they
> were written. They are not refreshed when the thing is fixed. Read the data
> before repeating what a note says about it.

On 2026-08-11 that rule was broken four times about one lane (L4), producing:
a claim it "records almost nothing" (it records most of the run envelope), a
claim its settle step favoured us (`settle_s` is 0.0 for all three engines and
the paper says so), a claim its comparator builds were missing (they are
recorded, and QuestDB's carries a commit hash), and a claim it was not
publication-ready (it is). One of those was published on a public page and had
to be corrected twice. Every time the data was actually read, the data
disagreed with the note and the earlier work turned out to be right.

## Before believing any number you did not just measure

1. **Open the file.** Not the task, not the summary, not last week's message.
2. **Print the whole record**, not the fields you expect. `settle_s: 0.0` is
   the evidence that no engine settled; a filter that drops falsy values hides
   it and makes symmetry look like absence.
3. **Check which arm you have.** Several files hold multiple arms of the same
   experiment, distinguished by flags rather than by name.
4. **Check which file you have.** Several lanes split one comparison across
   two files.
5. **If it contradicts the paper, suspect yourself first.** `claims_check`
   pins the paper's prose against the data and passes 79/79. A disagreement is
   far more likely to be a misread field than a wrong paper.

## Field traps, specifically

**The 12-hour aggregation is `q_global_ms`, not `q_range_ms`.** `q_global_ms`
returns 12 rows, one per hour, and medians ~25.0 ms on the native path.
`q_range_ms` is a 60-row range query and medians ~4.4 ms. Both look like
plausible "aggregation" numbers. Reading the second as the first makes the
paper appear wrong by 5.7x, and it is not.

**Last-point has two variants, and only on one source.** The native probe
records `q_last_unbounded_ms` (0.720) and `q_last_ms` (0.860, recency
windowed). The other engines record one number as `q_last_ms`. The paper
quotes the unbounded one because it is the faster of the two measured. Reading
only `q_last_unbounded_ms` blanks three of four rows.

**ArcadeDB has two time-series arms, in two different files.** The native
`TIMESERIES` type is in `results/ts_2681/nosettle_r*.json` at ~1.86M pts/s.
The general-purpose document path is in `results/l4_tsbs.jsonl` at ~40.1k,
alongside QuestDB and DuckDB. A table built from the second file alone shows
our slowest arm against everyone else's best and reads as a 46x loss. The
papers report both arms precisely so that ratio is read as what the
specialized layout buys.

**`engine_version` is deliberately null for non-ArcadeDB rows in L4.** Use
`backend_version`. `run_conditions()` stamps `engine_version` from the
installed wheel, which is right for the ArcadeDB row and wrong for DuckDB and
QuestDB, so `l4_tsbs.py` asks each backend for its own version instead. A
wrong version that passes a provenance audit is worse than none. See the
comment in that file.

**Arms are selected by flag, not by filename.** `claims_check.ts_arm()` takes
`primitive=` and `numpy_cols=` because the published row is one specific arm.
Its docstring is explicit that pooling them "would report a number the paper
never claims". Assert the flags rather than globbing the directory.

**The main lanes' `engine_version` column is not publishable.** `qdrant_dense`
records `?`; sparse Qdrant and Milvus record only `"qdrant"` and `"milvus"`;
`l1 arcadedb_server` records `"server:latest"` while running a pinned digest.
The authoritative source is `runner.py`'s `BACKENDS`, which pins every
comparator by sha256. `build_images.sh` does NOT answer this: those are client
libraries (`qdrant-client==1.18.0`), not servers (Qdrant v1.18.2).

**`host` is recorded on two lanes of seven.** Sparse and dense have it; the
rest record the container but not the machine. Do not imply a uniform
environment from rows that cannot prove one.

## Publishing traps

**An absent row makes a claim.** If comparators appear at a tier and we do
not, a reader concludes we could not do that tier. The dense lane nearly
shipped that way: our 10M rows exist but ran on `26.8.1.dev3`, and
releases-only correctly excludes them. `export_web.py` now publishes only
scales where our engine also has a row, and names what it withheld.

**Real numbers can compose a false impression.** The document-path table above
would have been accurate in every cell and wrong as a whole. Ask what a reader
concludes, not only whether each figure is right.

**Negative numbers can be the finding.** E4's process-boundary term goes
negative at the four smallest sizes. That is the boundary sitting below the
design's resolution, which is the evidence for "co-locating costs nothing
measurable". Publish it with the explanation rather than clamping to zero;
`claims_check` pins the count of negative sizes at 4 so it cannot be quietly
tidied away.

## Gates

Four, and they answer different questions. Run all of them after touching
results, tables or the page:

    BENCH_PAPER_DIR=<dir with paper.tex> python provenance_check.py   # does a cell trace to a run
    BENCH_PAPER_DIR=<...>                python fairness_check.py     # F1-F9
    BENCH_PAPER_DIR=<...>                python claims_check.py       # paper prose vs data
    BENCH_PAPER_DIR=<...>                python page_check.py         # page vs paper

`page_check.py` is not circular even though both artifacts derive from the
same rows: it compares the page against the paper's hand-transcribed
constants, which is the part that can drift. It catches the `q_range_ms`
mistake mechanically.
