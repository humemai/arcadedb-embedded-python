# What is in `results/`, and who reads it

Written 2026-08-30 because `provenance_check.py` listed **20 result directories
as "dead overlay, or an unaudited input"** and eleven of them turned out to be
live inputs to the published page. A warning that fires on live data teaches
people to ignore the warning, so the classification lives here.

**Rule: nothing in `results/` is deleted. Superseded material moves to
`archive-<date>/` and keeps its name.** Quarantine markers
(`QUARANTINE_`, `REFUSED_`, `SUPERSEDED_`, `NONCOMPARABLE_`) are evidence of a
decision and are never tidied away.

## Canonical data

| path | what | read by |
|---|---|---|
| `runs.jsonl` | the merged canonical row store. Append-only. | `make_paper_tables`, `export_web`, everything downstream |
| `runs_page_<pin>.jsonl` | current campaign, page lanes | `merge_campaign` -> `runs.jsonl` |
| `runs_l4_<pin>.jsonl` | current campaign, time-series lane | as above |
| `runs_lifecycle_<pin>.jsonl` | current campaign, lifecycle lane | as above |
| `runs_lifecycle_gav_<pin>.jsonl` | lifecycle `graph_gav` situation, run separately | as above |
| `runs_remeasure_1b04483bf.jsonl` | the #5467 re-measure posted upstream | evidence; do not merge |
| `raw/` | one JSON per cell, 788 files | `provenance_check`, `claims_check`, `page_check`, `make_paper_figures` |
| `manifest-*.json` | per-invocation image digests, cpuset, heap, reps | `provenance_check`, `runner`, `backfill*` |
| `runs-*.csv` | per-invocation summary written by `runner.py` | `runner` only |

## Overlays: directories a table reads directly

These are NOT dead. They feed published cells and are the reason the
"unmapped" warning is noisy.

| dir | feeds | pin era |
|---|---|---|
| `sparse_mp/` | `l3smp` multipass table (`export_web`) | 2026-08 overlay |
| `sparse_mp_<pin>/` | same table when COMPLETE; see the all-or-nothing rule below | current pin, **partial** |
| `e4decomp/`, `e4decomp_2681/` | `e4` deployment table (`export_web`) | 2026-08 overlay |
| `e4_decomp/` | `claims_check` only | 2026-08 |
| `dense_mp_2681/` | `make_paper_tables`, `make_paper_figures` | 2026-08 |
| `lifecycle/` | `export_web`, `make_paper_tables` | 2026-08 |
| `probe/` | `export_web`, `make_paper_tables`, `claims_check` | 2026-08 |
| `summary/` | `make_paper_figures`, `make_paper_tables`, `page_check`, `claims_check` | 2026-08 |
| `e3_q17/`, `ingest_ab/`, `tentag/` | `claims_check` | 2026-08 |

**All-or-nothing.** `_pinned_dir(name, expected=...)` uses
`results/<name>_<pin>` only when every expected file is present. A partial
pinned directory does not make a table visibly short -- callers skip missing
files, so it publishes whichever subset exists. `sparse_mp_b7c6c800d` held 1 of
12 files, and that one is an ArcadeDB arm, so a pinned export would have shipped
the six-engine comparison as a single ArcadeDB row. Fixed 2026-08-30; the
fallback now prints what was missing.

## Evidence and quarantine, kept deliberately

| path | why it exists |
|---|---|
| `NONCOMPARABLE_e4decomp_<pin>/` | host-side e4 run: cpuset 0-19 not 0-11, 9 reps not 15, 2 arms of 3. Exited 0 and looked plausible. |
| `QUARANTINE_wrong_engine_image.jsonl` | server rows stamped with a pin while running stock 26.8.1 |
| `REFUSED_l2_corpus_guard.jsonl` | rows the corpus-count guard rejected |
| `SUPERSEDED_prepin_d7940d79e.jsonl` | pre-pin rows kept for comparison |
| `*.WINDOWED-QLAST-*`, `*.SUPERSEDED-*`, `*.prequarantine` | the file as it stood before a known defect was fixed |
| `profile_5467_*_d7940d79e/` | async-profiler output behind the #5467 report |
| `delta_scan_<pin>/` | #6797 evidence for upstream. Not a page input. |

## No reader at all

Verified by grepping `export_web`, `make_paper_tables`, `make_paper_figures`,
`claims_check`, `page_check`:

- `l4_retime/` (2026-08-22)
- `profiles/` (2026-08-15, 5 MB)

Candidates for `archive-<date>/`. They are not deleted, because a directory with
no reader today is often the evidence behind a claim someone made in prose.

## When adding a result directory

Add it to `FEEDS`/`FEEDS_FILES` in `provenance_check.py` **or** to this file's
"no reader" list. The audit exists to catch an unaudited input to a published
cell; every entry it prints that is actually fine makes the next real one
easier to miss.
