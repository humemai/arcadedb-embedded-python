# What is in `results/`, and who reads it

> **WHICH HOST.** This describes `results/` **on the bench host (mini)**, where the campaigns write. A developer checkout does not have the same tree: nearly all of `results/` is gitignored (`runs.jsonl` and every `runs_*.jsonl` at `.gitignore:580` and `:599`, `raw/` at `:601`), so overlays and campaign files exist on mini as untracked paths and simply are not in your checkout.
>
> Two consequences, both of which have bitten:
>
> 1. A path listed here may be absent from your checkout. That is expected, not a missing file. Check on mini before concluding anything is lost.
> 2. **Committing a path that exists untracked on mini makes mini's `git pull` fail**, and every queue script opens with `git pull --ff-only`, so it aborts the waiting stage. Before committing anything under `results/`, check the incoming paths against mini's untracked files.

**Rule: an output nothing reads may be deleted; superseded material that a decision still cites moves to `archive-<date>/` and keeps its name.** Quarantine markers (`QUARANTINE_`, `REFUSED_`, `SUPERSEDED_`, `NONCOMPARABLE_`) are evidence of a decision and are never tidied away.

## Order of operations, and it is not optional

A `runs_*_<pin>.jsonl` is the only copy of its data until it is merged. Archiving one before the merge deletes the campaign.

1. `merge_campaign.py`: campaign files into `runs.jsonl`
2. freeze: `runs.jsonl` into `runs_paper.csv`
3. `export_web.py`: into `web_benchmarks.json`
4. only then archive the campaign files, and only after confirming their rows are in `runs.jsonl` by `engine_commit`

A campaign file reports "no reader" when you grep the publishing scripts. That is what step 1 not having run yet looks like, not a dead file.

`runs_paper.csv` is regenerated from `runs.jsonl` by the freeze step, and the canonical store keys on `(lane, scale, n_docs, workload, backend, gav, rep)` with the latest `ts_utc` winning, so a re-measured row supersedes the old one on merge. **Do not hand-edit the frozen CSV**; re-freeze after the campaign.

## Canonical data

| path | what | read by |
|---|---|---|
| `runs.jsonl` | the merged canonical row store. Append-only. | `make_paper_tables`, `export_web`, everything downstream |
| `runs_page_<pin>.jsonl` | current campaign, page lanes | `merge_campaign` into `runs.jsonl` |
| `runs_l4_<pin>.jsonl` | current campaign, time-series lane | as above |
| `runs_lifecycle_<pin>.jsonl` | current campaign, lifecycle lane | as above |
| `runs_paper.csv` | the frozen rows every table is generated from | `make_paper_tables`, `export_web`, `page_check` |
| `web_benchmarks.json` | the page payload | the site, `page_check` |
| `raw/` | one server and client log per cell, written by the runner. Untracked. | nothing on the page; read by hand when a cell needs explaining |
| `manifest-*.json` | per-invocation image digests, cpuset, heap, reps; every row names its manifest by timestamp | nothing opens them; kept as provenance by reference |
| `runs-*.csv` | per-invocation summary written by `runner.py` | nothing. Delete them when they pile up; the writer stays. Swept 2026-09-19: 103 files, all 106 rows `tier=sweep` and 88 of them `bench_host=laptop`, zero paper-tier rows, so none could ever reach a page. Check that before deleting, not after |
| `runs.jsonl.before-merge-<stamp>` | `merge_campaign.py`'s rollback copy of the canonical file | nothing reads them. ONE is kept, the copy of the most recent merge; the script now prunes the rest itself. Eleven had reached 73 MB by 2026-09-19 before this. Verify containment line by line before deleting any: `runs.jsonl` has lost rows once, to a git checkout during a live campaign |
| `mp_rows_<pin>.jsonl`, `mp_rows_small_<pin>.jsonl`, `mp_rows_sparse_<pin>.jsonl` | the per-cell multipass rows behind the overlay directories below | nothing on the page; the per-cell record |
| `runs_skeleton_laptop.csv` | the laptop micro-scale placeholder freeze behind a skeleton publish, one repetition, sweep tier, `bench_host` of the laptop (DECISIONS #86) | `refresh_web_page.py --skeleton`, which refuses a row from the bench host or at paper tier. Never merged into `runs.jsonl` |
| `runs_CALIBRATION_<tier>_<pin>.jsonl` | a calibration pass: one repetition per engine at a tier nothing has measured yet, run to turn that tier's query budgets from projections into measurements (DECISIONS #106). Not publishable at n=1 | nothing. `merge_campaign.py` takes an explicit `--remote` path and no glob, so it cannot pick one up by accident; `derive_budgets.py` reads the frozen CSV, so a calibration tier reaches the budget table only when someone re-freezes with its rows |

The answer digest and its readable sample, the `durability` string, and the thermal fields (BUGS.md F45) are row fields rather than files, so nothing under `results/` holds them separately and a question about any of the three is answered by printing the row.

`equivalence_check.py` reads the frozen set like the other gates and takes `--rows <file>` for a campaign file, a smoke file, or the skeleton freeze, reducing to the newest row per cell before it compares, so a re-run cell does not read as one backend giving two answers.

## Overlays: directories a table reads directly

| dir | feeds |
|---|---|
| `dense_mp5_<pin>/` | the page's 9.99M dense table, T5, and f4/f8's dense bars |
| `dense_mp5_small_<pin>/` | the same table at 1M |
| `sparse_mp_<pin>/` | the warm columns on the page's `l3s` table (`export_web`) |

Every other directory under `results/` is evidence, quarantine, or output; nothing generated reads it.

**All-or-nothing.** `make_paper_tables.dense_mp_dir()` is the ONE resolver for the dense overlays: it returns `results/dense_mp5_<BENCH_ENGINE_COMMIT>` only when every one of the 13 mandatory arms (`fp32 int8 arcsrv arcsrv_int8 milvus milvus_int8 qdrant qdrant_int8 chroma duckvss lancedb sqlitevec sqlitevec_int8`) has all five `mp_<arm>_b<n>.json` files, else it refuses. `neo4jvec`, `pgvector`, `surreal`, `surrealsrv`, and `arango` are optional arms (`MP_ARMS_OPTIONAL`) that join the table when all five of their files exist, are absent with none, and refuse the publish with some, so a partial arm never prints as a row. `dense_mp5_small_<pin>` feeds the 1M tier with `MP_ARMS_SMALL`. T5, f4/f8's dense bars, the page's dense table, F4 in `fairness_check` and `provenance_check`'s `FEEDS` all call the one resolver, so they cannot disagree.

The rule exists because a partial pinned directory does not make a table visibly short: callers skip missing files, so it publishes whichever subset exists. One such directory held 1 of 12 files, and that one was an ArcadeDB arm, so a pinned export would have shipped a six-engine comparison as a single ArcadeDB row.

Cache policy for the dense overlays: DECISIONS #56, disclosed in PROTOCOL.md section 7.

## Evidence and quarantine, kept deliberately

A quarantine marker in a filename says a human decided the rows are unpublishable and why. Keep the file, keep the name.

| pattern | why it exists |
|---|---|
| `NONCOMPARABLE_*` | a run whose conditions do not match the tier it looks like it belongs to |
| `QUARANTINE_*` | rows stamped with conditions they did not run under |
| `REFUSED_*` | rows a lane guard rejected |
| `SUPERSEDED_*`, `*.SUPERSEDED-*`, `*.prequarantine` | the file as it stood before a known defect was fixed |
| `delta_scan_<pin>/`, `ablation_cache_<pin>.jsonl`, `verify_<sha>/` | upstream evidence. Not page inputs; `ablation_cache` is read only by `dense_matrix.py`, the operator table, and is never merged into `runs.jsonl` |

## When adding a result directory

Add it to `FEEDS`/`FEEDS_FILES` in `provenance_check.py` **or** to this file. The audit exists to catch an unaudited input to a published cell; every entry it prints that is actually fine makes the next real one easier to miss.

## `evidence/`: tracked copies of what an upstream report cites

`results/` is untracked by design, but an upstream issue needs a stable URL. `evidence/` holds verbatim copies of finished files a filed report links to, under a path that exists nowhere on mini. Copy, never move; `results/` stays the working store.

## Queue scripts

The live chain, what each script runs, and where finished scripts go: CAMPAIGN.md section 6. Every script gates on `verify_pair_c25.sh`, which is in this directory alongside `build_matched_pair.sh` and `build_c25_wheel.sh`, the pair recipe. Retired `qB*` scripts pinned to `b7c6c800d` live in `queue-archive-20260830/` on the bench host; they verify a locally compiled pair, which is the wrong claim for a pair assembled from upstream's published jars.

## The 8d6af9475 pin

The engine is pinned to upstream's published snapshot `8d6af9475`, and the served arm runs Corretto 25 / glibc / G1 with compact object headers, matched to the embedded arm (DECISIONS #54).

Every ArcadeDB row measured before that re-pin is superseded, embedded as well as served: the jars moved 84 commits. The campaign started by carrying clean COMPARATOR rows forward from the previous pin's file, each stamped `carried_forward_from` and `carried_forward_reason`; no ArcadeDB row was carried.

The live page stays on this pin for the whole October campaign (DECISIONS #83). October rows accumulate in their own `runs_*_<pin>.jsonl` under the new pin, are frozen and exported separately, and reach the site only through the preview target, whose payload is `arcadedb-benchmarks-next.json` and whose table inventory is `results/generated/preview-tables.md`. A row of one instrument is never merged into the freeze of the other: `instrument` on the row says which it is, and the freeze and the exporter refuse a lane that holds both.
