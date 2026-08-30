# What is in `results/`, and who reads it

> **WHICH HOST.** This describes `results/` **on the bench host (mini)**, where
> the campaigns actually write. A developer checkout does NOT have the same
> tree: most of `results/` is gitignored (`runs.jsonl` at `.gitignore:578`,
> engine logs at `:390`), so overlays, manifests and quarantine files exist on
> mini as UNTRACKED paths and simply are not here. Counts below are mini's.
>
> Two consequences, both of which have bitten:
>
> 1. A path listed here may be absent from your checkout. That is expected, not
>    a missing file. Check on mini before concluding anything is lost.
> 2. **Committing a path that exists untracked on mini makes mini's `git pull`
>    fail**, and every queue script opens with `git pull --ff-only`, so it
>    aborts the waiting stage. This is not the tracked-modification case in
>    [[dirty-tree-on-mini-is-an-outage]]; it is the untracked-collision case,
>    and it takes the chain down the same way. Before committing anything under
>    `results/`, check the incoming paths against mini's untracked files.

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

## The 8d6af9475 re-pin (2026-08-30)

The engine moved from `b7c6c800d` to upstream's published snapshot
`8d6af9475`, and the served arm moved from Temurin 21 / musl / ZGC to
Corretto 25 / glibc / G1 with compact object headers. See DECISIONS #54.

| path | what |
|---|---|
| `runs_page_8d6af9475.jsonl` | the new campaign. Started by carrying 220 clean COMPARATOR rows forward from `runs_page_b7c6c800d.jsonl`; each carries `carried_forward_from` and `carried_forward_reason`. 197 ArcadeDB rows were NOT carried. |
| `runs_lifecycle_8d6af9475.jsonl` | lifecycle on the matched pair (qCC). Carries the #6798 counters owed upstream. |
| `results_jdk21_control.jsonl` | **a control, not a published lane.** One served deep10m rep on upstream's stock image (Temurin 21 / musl), identical jars and flags. Exists only to price the JVM major before deciding whether to report it upstream. Never merge into `runs.jsonl`. |
| `runs_page_b7c6c800d.jsonl` | previous campaign. Its comparator rows live on in the new file; its ArcadeDB rows are superseded. |

**Every ArcadeDB row measured before 2026-08-30 is superseded**, embedded as
well as served: the jars moved 84 commits. Counted, not estimated: 60 of the
481 frozen rows in `runs_paper.csv` are ArcadeDB SERVER rows, over l1/medium,
l1tpc/tpch1, l2/sf1, l2/sf10, l3d/small, l3s/tiny, l3s/small, l3s/medium.

`runs_paper.csv` is regenerated from `runs.jsonl` by the freeze step, and the
canonical store keys on (lane, scale, n_docs, workload, backend, gav, rep) with
the latest `ts_utc` winning -- so the re-measured rows supersede the old ones on
merge. **Do not hand-edit the frozen CSV**; re-freeze after the campaign.

### Queue scripts

`queue-archive-20260830/` on the bench host holds the 15 retired `qB*` scripts.
They pin `b7c6c800d` and verify the pair with `build_engine_pair.sh`, which
checks a locally COMPILED pair -- the wrong claim for a pair assembled from
upstream's published jars. Live scripts are `qCA` -> `qCB` -> `qCC` -> `qCD`,
each gated on `verify_pair_c25.sh`.
