# Republishing the project page

PROTOCOL.md says how a run is produced. FAIRNESS.md says what makes a comparison legitimate. READING-RESULTS.md says how to read what came out. This one says how the numbers get from the frozen rows onto humem.ai/research/arcadedb without going wrong on the way.

## Where this fits

This file is the publish half of the routine, and the map of `results/` the publish reads from ("What is in `results/` and who reads it", below). The routine in order, both loops, is at the top of CAMPAIGN.md; read that first if you are new to it or returning after a campaign.

## The command

```
BENCH_ENGINE_COMMIT=<pin> python refresh_web_page.py
```

That is the whole routine. It regenerates the tables and figures into `results/generated`, exports the page data, runs the gates, syncs the JSON and the figures the page references, rewrites PAGE-SPEC.md's generated table inventory, builds the site, and prints the diff. It does not commit: reading the diff before publishing is the point, not an afterthought.

Run it after **any** re-measure, after any change to the tables or figures, and after any change to the page's own table list.

Flags: `--site <path>` if humem.ai is not a sibling checkout; `--no-build` to skip the Next.js build (do not, normally: the build is what catches the page referencing an asset that was never written); `--preview` for the preview target below; `--skeleton` for the laptop placeholder publish.

## The Engines documentation page

The Engines page of the documentation site (humemai/dbbench, `docs/engines.md`) is generated, never edited: `uv run python benchmarks/experiments/gen_engines_doc.py <path to docs/engines.md>` from the repo root. It reads the October rows (`make_paper_tables.load_canonical`), the arm names (`export_web.py`) and the override sentences (`override_registry.py`), so nothing on it is typed. Regenerate it at every landing and commit the result in humemai/dbbench; `--check <path>` exits 1 when it is out of date. Lanes and arms without rows yet are on its gap list.

## The preview target (DECISIONS #83)

`refresh_web_page.py --preview` and `land_stage.py --preview` publish to `/projects/arcadedb/next`, the campaign page watched while it fills in: the same exporter, gates, and figures, written to `src/data/arcadedb-benchmarks-next.json` and `public/images/projects/arcadedb-next/`, and checked against the prose in `src/lib/projects/items/arcadedb-next.ts`. The table inventory goes to `results/generated/preview-tables.md` and PAGE-SPEC.md is not rewritten. The route is noindex and not in the project index, and its banner names the pin from the payload.

A preview publish never writes the live payload, the live images, or `arcadedb.ts`. Its tables, figures, `GATE_STATUS.txt` and `withheld_recall.json` go to `results/generated_oct/`, not to `results/generated/`, which is the published set `page_check` pins the live page against; `BENCH_SKELETON=1` writes to the untracked `results/generated_skeleton/`. A row of one instrument is never merged into the freeze of the other: `instrument` on the row says which it is, and the freeze and the exporter refuse a lane that holds both. Every ArcadeDB row measured under another pin is superseded, embedded as well as served; no ArcadeDB row is carried forward, and a comparator row carried forward is stamped `carried_forward_from` and `carried_forward_reason`. The switch, when the campaign freeze is complete and every gate is green, is one commit that copies the preview payload, images, and prose over the live ones and deletes the route.

`--skeleton` (DECISIONS #86) publishes the laptop micro-scale placeholder run to that route so the page's shape can be read before mini measures anything. It implies `--preview`, reads the skeleton freeze, and refuses any row that carries no `bench_host`, names the bench host, or is not at sweep tier. It stamps the payload and every table's conditions as placeholders, waives F1 and F3 by name because both describe the bench host, and runs every other gate. A live publish refuses a payload stamped skeleton.

## The one rule

> **Every page table is generated from frozen rows, listed in the manifest, pinned by `page_check`, and links its source.**
>
> Adapting a presentation is fine. A cell that traces to no frozen row is not.

This is PAGE-SPEC.md section 6.

## Why it is a script and not a checklist

Every step was once done by hand, and the hand-done ones were where the mistakes were. A figure deleted from its source kept being republished, with a caption for a corpus it no longer showed. Copying figures one by one has no step that removes one, so the script derives the SVG set from the page source and **deletes** any SVG the page no longer references. The exporter's output is the file the site gets, so the page JSON cannot drift from what `export_web.py` produces today.

## What blocks a bad publish

The gate scripts (`refresh_web_page.GATES`), then three structural checks. All of them fail the run rather than warn:

| Check | Asks |
|---|---|
| `resource_check` | is any disk or memory value one that cannot be right: far below the other engines of its group, a negative disk growth, or a disk reading taken after a failed pre-disk step (issue #349). Rows of the 2026-10 instrument only; the count of rows not checked is printed |
| `provenance_check` | does every cell trace to a run |
| `fairness_check` | F1 to F15 comparison invariants, durability class, instrument, and the stamps of the overrides a table discloses included |
| `equivalence_check` | do the engines of a table agree on the answer, and is every operation an engine cannot express declared (DECISIONS #88) |
| `page_check` | does the page agree with its own sources: its 9.99M dense cells with the generated table, the atomicity counts with the artifact, every operation of the query set a column with every engine answering or declared, no table losing its ArcadeDB row, and every number under a table traced to a source |
| `page_check.PROSE` | do the page's hand-typed prose numbers agree with the tables and the page-derived pins |
| `version_consistency_check` | does one engine wear two version strings across the page's tables, or a comparator an ArcadeDB release number |
| `version_pin_check` | do `runner.py`, `build_images.sh`, the three Dockerfiles, and COMPARATORS.md agree on every image digest and package pin (it reads no rows) |
| `_check_no_orphan_figures` | is every generated figure cited |
| refresh step 3, `tableId` coverage | does every table the page's prose names by `tableId` exist in the payload, and does every table in the payload have a section on the page to render it; a scoped landing declares the tables it lacks in `pending_tables` instead of being refused |
| refresh step 5 | is every figure the page references a generated one |

`PROSE` is its own check because the page's two surfaces fail differently. Cells are written by the exporter straight from the frozen results. Prose is typed by hand, so a wrong number in it is nearly inevitable: a caption once gave one engine's dense latency from the canonical CSV and the other's from the matched overlay, with no published cell wrong.

A disagreement that has been reproduced, understood, and filed upstream prints as KNOWN rather than FAIL and its cell is withheld from the page instead of being published beside an answer it does not match (`equivalence_check.KNOWN_DISAGREEMENTS`, `export_web.WITHHELD_CELLS`); nothing is withheld today (`WITHHELD_CELLS` is empty). `KNOWN_DISAGREEMENTS` holds PostgreSQL + AGE's CRUD read-backs (apache/age#2587), whose cells publish with a note and are not withheld (DECISIONS #134). An entry is deleted at the re-pin that carries the fix, which re-arms the gate for that query, because a gate that cannot pass until an upstream release lands is a gate somebody deletes.

`WEB_ONLY_FIGURES` is the escape hatch for a figure the page shows and nothing else cites. It is deliberately empty; earn a line in it, do not assume one.

## Adding a table to the page

1. Confirm it is generated from frozen rows and add it to `export_web.LANES` or a builder in `export_web.py`.
2. Reference it from `arcadedb.ts`.
3. If it reports operations of the query set, add them to `page_check.OPERATION_MANIFEST`, so every operation is a column with every engine answering or declared. A table nothing checks can drift silently.
4. If the prose around it quotes any number, add each one to `page_check.PROSE` with a regex that captures the digits as printed. Quoting a number in a sentence is making a claim; a claim nothing pins is one nothing checks.
5. State in the table's conditions any measurement from the standard set it does not carry (PROTOCOL.md section 2, DECISIONS #89). `page_check` fails an omission that carries no reason.
6. Run the command above.

## Adding a figure to the page

1. Confirm something cites it. If nothing does, it does not go on the page.
2. Reference it from `arcadedb.ts` as `/images/projects/arcadedb/<stem>.svg`.
3. Run the command above; it converts and syncs it.

## What is in `results/` and who reads it

> **Which host.** This describes `results/` **on the bench host (mini)**, where the campaigns write. A developer checkout does not have the same tree: everything under `results/` is ignored by the allowlist at the end of the repo-root `.gitignore` (from `benchmarks/experiments/results/**`), which names the tracked artifacts one by one. Two consequences:
>
> 1. A path listed here may be absent from your checkout. That is expected, not a missing file. Check on mini before concluding anything is lost.
> 2. **Committing a path that exists untracked on mini makes mini's `git pull` fail.** Every queue script opens with `git pull -q --ff-only || abort` and has no clean-tree check, so the pull aborts the waiting stage. A modified tracked file does the same. An untracked file aborts the pull only once a commit adds that same path (git refuses to overwrite it); an ignored file at that path does not refuse, which is why the allowlist exists. Before committing anything under `results/`, check the incoming paths against mini's untracked files. A new tracked artifact needs `git add -f` and a line in the allowlist. Never `git add` a raw directory (`results/runs.jsonl`, `dense_mp5_*`, `sparse_mp_*`) and never `git add -A`: sweeping raw results into a commit is the other failure the allowlist closes.

**Rule: an output nothing reads may be deleted; superseded material that a decision still cites moves to `archive-<date>/` and keeps its name.** Quarantine markers (`QUARANTINE_`, `REFUSED_`, `SUPERSEDED_`, `NONCOMPARABLE_`) are evidence of a decision and are never tidied away.

### Order of operations, and it is not optional

A `runs_*_<pin>.jsonl` is the only copy of its data until it is merged. Archiving one before the merge deletes the campaign.

1. `merge_campaign.py`: campaign files into `runs.jsonl`
2. freeze: `runs.jsonl` into `runs_paper.csv`
3. `export_web.py`: into `web_benchmarks.json`
4. only then archive the campaign files, and only after confirming their rows are in `runs.jsonl` by `engine_commit`

`land_stage.py` performs steps 1 to 3 in one run (see "Landing a finished queue stage"); archive only after it reports LANDED. A campaign file that shows "no reader" when you grep the publishing scripts is a file whose step 1 has not run yet, not a dead file.

The canonical store keys on `(lane, scale, n_docs, workload, backend, gav, rep, durability_class)` with the latest `ts_utc` winning, so a re-measured row supersedes the old one on merge. **Do not hand-edit the frozen CSV**; re-freeze after the campaign.

### Canonical data

| path | what | read by |
|---|---|---|
| `runs.jsonl` | the merged canonical row store. Append-only. | `make_paper_tables`, `export_web`, everything downstream |
| `runs_page_<pin>.jsonl` | the campaign's rows for the page lanes (an older campaign also wrote `runs_l4_<pin>.jsonl` and `runs_lifecycle_<pin>.jsonl`) | `merge_campaign` into `runs.jsonl` |
| `runs_paper.csv` | the frozen rows every table is generated from | `make_paper_tables`, `export_web`, `page_check` |
| `web_benchmarks.json` | the page payload | the site, `page_check` |
| `raw/` | one server and client log per cell, written by the runner. Untracked. | nothing on the page; read by hand when a cell needs explaining |

### Tracked artifacts, and what made each one

The allowlist says WHICH files are tracked; this says why, and what to re-run to rebuild them. A one-shot probe's script looks unreferenced to a "who calls this?" sweep, so the link is written here. Do not delete a producer because nothing calls it.

| tracked artifact | produced by | read by |
|---|---|---|
| `runs_paper.csv` | `make_paper_tables.py` (the freeze) | every gate, the exporter, the release asset |
| `web_benchmarks.json` | `export_web.py` | `page_check`, `version_consistency_check`, `refresh_web_page` |
| `runs_paper_oct.csv`, `generated_oct/**` | `make_paper_tables.py` under `BENCH_INSTRUMENT=2026-10` (DECISIONS #84) | the gates and the exporter under the same switch, `land_stage.py --preview` |
| `web_benchmarks_next.json` | `export_web.py` under `BENCH_INSTRUMENT=2026-10` | the preview route, `page_check --preview`, `version_consistency_check --preview`, `refresh_web_page --preview` |
| `generated/tables/*`, `withheld_recall.json` | `make_paper_tables.py` | `page_check`, `provenance_check`, the exporter's withheld-cell notes |
| `generated/preview-tables.md`, `generated/memo_bottlenecks.html` | `refresh_web_page.py --preview`; `memo_bottlenecks.py` | a reader of the preview's inventory; the maintainers' memo, not the page |
| `sparse_cliff.jsonl` | `sparse_cliff_probe.py`, one shot | `make_paper_figures.f3_sparse_perquery`; f3 is not built (PAGE-SPEC.md section 3) |
| `e3_q17/*.json`, `ingest_ab/ab_r*.json`, `tentag/tentag_ab.json` | `e3_recovery.py`, `async_ingest_probe.py`, `ts_stride_probe.py`, one shot each | `claims_check.py` (the recovery table is planned, not built) |
| `manifest-*.json` | per-invocation image digests, cpuset, heap, reps; every row names its manifest by timestamp | nothing opens them; kept as provenance by reference |
| `runs-*.csv` | per-invocation summary written by `runner.py` | nothing. Delete them when they pile up; the writer stays. Check first that none holds a paper-tier or bench-host row |
| `runs.jsonl.before-merge-<stamp>` | `merge_campaign.py`'s rollback copy of the canonical file | nothing. ONE is kept, the copy of the most recent merge; the script prunes the rest. Verify containment line by line before deleting any: `runs.jsonl` has lost rows once, to a git checkout during a live campaign |
| `mp_rows_*_<pin>.jsonl` | the per-cell multipass rows behind the overlay directories below | nothing on the page; the per-cell record |
| `web_benchmarks_skeleton.json`, `runs_skeleton_laptop.csv` (tracked); `generated_skeleton/**`, `runs_oct_smoke_laptop.jsonl` (untracked) | `export_web.py` and `make_paper_tables.py` under `refresh_web_page.py --skeleton` (DECISIONS #86); the CSV is the laptop placeholder freeze, never merged into `runs.jsonl` | `version_consistency_check.py` reads the JSON; the skeleton publish reads the rest; nothing reads the smoke file |
| `runs_CALIBRATION_<tier>_<pin>.jsonl` | a calibration pass: one repetition per engine at an unmeasured tier, to turn its query budgets from projections into measurements (DECISIONS #106). Not publishable at n=1 | nothing. `merge_campaign.py` takes an explicit `--remote` path and no glob; `derive_budgets.py` reads the frozen CSV |

### The libraries the lanes import

No stage runs these directly, so a sweep for entry points finds no caller; each is imported, and none is dead (`grep` the module name for its importers): `bench_common.py` (statistics, run conditions, durability strings, answer digest), `graph_common.py` and `ldbc_snb.py`, `sparse_common.py` and `bigann_sparse.py` (the synthetic corpora and their real-data drop-ins), `budget_lookup.py` and `budgets.py` (query budgets; the table `derive_budgets.py` generates, never hand-edited), `arango_common.py`, `mongo_common.py` and `surreal_common.py` (per-engine connection and settings), `pagecache.py` (evicts a database from the page cache for a cold open), `l5_lifecycle_server.py` and `l5_lifecycle_surreal.py` (arms of `l5_lifecycle.py`), `lean_http.py` (the HTTP session every ArcadeDB served arm uses, CAMPAIGN.md section 7, row 72), `override_registry.py` (every override a table shows, PROTOCOL.md section 7), and `gen_engines_doc.py` (the Engines page, above).

The answer digest, the `durability` string, the thermal fields (BUGS.md F45), the idle-state stamps (`cpu_dma_latency_*`), `sparse_warmup_queries`, `dense_id_index` and `arcadedb_ts_result_format` are row fields, not files; print the row to answer a question about one.

`equivalence_check.py` and `resource_check.py` read the frozen set like the other gates and take `--rows <file>` for a campaign file, a smoke file or the skeleton freeze. `equivalence_check` reduces to the newest row per cell first, so a re-run cell does not read as one backend giving two answers.

### Overlays: directories a table reads directly

| dir | feeds |
|---|---|
| `dense_mp5_<pin>/` | the page's 9.99M dense table, T5, and f4/f8's dense bars |
| `dense_mp5_small_<pin>/` | the same table at 1M |
| `sparse_mp_<pin>/` | the warm columns on the page's `l3s` table (`export_web`) |
| `e4decomp_<pin>/` | the E4 decomposition table: `export_web.py` (`E4_DIR`; it stops without the directory unless it is a skeleton run) and `make_paper_tables.py`. `land_stage.py` copies the `decomp3m_*.json` files into it, so a landing is blocked until the e4 lane has run at that pin |

Every other directory under `results/` is evidence, quarantine, or output; nothing generated reads it. Cache policy for the dense overlays: DECISIONS #56, disclosed in PROTOCOL.md section 7.

**All-or-nothing.** `make_paper_tables.dense_mp_dir()` is the ONE resolver for the dense overlays: it returns `results/dense_mp5_<BENCH_ENGINE_COMMIT>` only when every one of the 13 mandatory arms (`fp32 int8 arcsrv arcsrv_int8 milvus milvus_int8 qdrant qdrant_int8 chroma duckvss lancedb sqlitevec sqlitevec_int8`) has all five `mp_<arm>_b<n>.json` files, else it refuses. `neo4jvec`, `pgvector`, `surreal`, `surrealsrv`, `arango` and `mongo` are optional arms (`MP_ARMS_OPTIONAL`) that join the table when all five of their files exist, are absent with none, and refuse the publish with some. `dense_mp5_small_<pin>` feeds the 1M tier with `MP_ARMS_SMALL`. T5, f4/f8's dense bars, the page's dense table, F4 in `fairness_check` and `provenance_check`'s `FEEDS` all call the one resolver, so they cannot disagree. A partial directory does not make a table visibly short (callers skip missing files), so without the rule a pinned export could ship a six-engine comparison as a single ArcadeDB row.

### Evidence and quarantine, kept deliberately

| pattern | why it exists |
|---|---|
| `NONCOMPARABLE_*` | a run whose conditions do not match the tier it looks like it belongs to |
| `QUARANTINE_*` | rows stamped with conditions they did not run under |
| `REFUSED_*` | rows a lane guard rejected |
| `SUPERSEDED_*`, `*.SUPERSEDED-*`, `*.prequarantine` | the file as it stood before a known defect was fixed |
| `delta_scan_<pin>/`, `ablation_cache_<pin>.jsonl`, `verify_<sha>/` | upstream evidence. Not page inputs; `ablation_cache` is read only by `dense_matrix.py`, the operator table, and is never merged into `runs.jsonl` |

**When adding a result directory,** add it to `FEEDS`/`FEEDS_FILES` in `provenance_check.py` **or** to this section. The audit exists to catch an unaudited input to a published cell; every entry it prints that is actually fine makes the next real one easier to miss.

**`evidence/`** holds tracked copies of what an upstream report cites: `results/` is untracked by design, but an upstream issue needs a stable URL. Copy, never move; `results/` stays the working store.

**Queue scripts.** The live chain and where finished scripts go: CAMPAIGN.md section 6; what each stage runs: `make_october_stages.STAGES` for the October chain and `make_2610_stages.py` for the 26.10.1 measurement. Every script gates on `verify_pair_c25.sh`, which sits here beside `build_matched_pair.sh` and `build_c25_wheel.sh`, the pair recipe.

## Landing a finished queue stage

One command, the same order every time, refuses by default:

```
.venv/bin/python benchmarks/experiments/land_stage.py \
    --only-lanes <lanes the stage measured, comma list> \
    --exclude-backends <backends still running on mini, comma list> \
    [--overlay neo4jvec] [--exclude-since 2026-09-12T12:00] [--preview --pin <commit>] \
    [--drop-unless arcadedb_graph_server:l2:oltp:server_http_body_max_bytes=68719476736] \
    --message "<one line: what joined>" [--dry-run | --apply]
```

It pulls `runs_page_<pin>.jsonl` (and, with `--overlay`, an arm's dense multipass files at both sizes, always the sparse second-pass files `sparse_mp_<pin>/` when the sparse lane lands (BUGS F148), and always the deployment decomposition's `e4decomp_<pin>/` files, since the `e4` table is a directory of artifacts rather than rows in the log and the export stops without it), drops the rows of the backends named as still running so a stage in progress never reaches the freeze, merges, publishes through the gates, and prints which page tables changed.

**`--drop-unless` drops the rows a repair stage replaced.** `BACKEND:LANE:WORKLOAD:FIELD=VALUE` drops that cell's rows whose FIELD is not VALUE (absent counts as not VALUE), so the old rows go and the repair's rows, which carry the stamp, stay; repeat it for several cells. Example: ArcadeDB's served graph OLTP was first measured at the engine's default bulk-load body limit, which broke the sf10 load, and the repair stage re-ran the cell with the raise stamped as `server_http_body_max_bytes` (DECISIONS #172). A malformed spec ends the run instead of dropping nothing.

**`--only-lanes` scopes a staged landing, and the scope is cumulative.** Rows of every lane not named stay on the host for a later landing, because the gates read the whole freeze and would fail a landing on lanes it was not publishing; empty lands everything. The scope is the lanes named PLUS every lane already on the page, read from the published payload, so a landing adds to the page rather than rebuilding it (BUGS F111; PAGE-SPEC.md section 2). A landing that would make any table on the page disappear is REFUSED and the site's payload restored. After the merge it also WARNS, without refusing, when a landed lane's rows were measured before a later commit to that lane's own script, and lists the commits (BUGS F98: an l4 landing once passed every gate with DuckDB rows that predated the index every other arm had). Without `--apply` it stops there and restores the site's payload; with `--apply` it builds the site, commits both repositories, and pushes. The merge into `runs.jsonl` is idempotent, so a run without `--apply` followed by one with it is the normal sequence.

**`--apply` governs the PUBLISH, not the merge, and `--dry-run` is the flag that writes nothing.** A run without `--apply` still performs steps 2 and 3, and step 3 merges. `--dry-run` pulls, filters, and stops: it prints how many rows WOULD merge and which of them carry errors, and leaves `runs.jsonl` byte-identical. It is also the mode a pre-campaign rehearsal wants.

**`--pin` defaults to the live page's commit**, which is wrong for every preview landing, since step 1 pulls `runs_page_<pin>.jsonl` by exact name. A preview landing without an explicit `--pin` (or `BENCH_ENGINE_COMMIT`) is REFUSED rather than guessed: a wrong pin fetches the other campaign's rows and fails much later, with the merge already done.

Never `git add` a raw directory under `results/` (see the first note of the results section above).

## The data behind the page, as a release asset

`publish_results_asset.py --tag <tag>` bundles `results/runs_paper.csv` and `results/web_benchmarks.json` with a manifest naming the engine pin, the tables, the row count, the file checksums, and the gate status, and attaches it to a GitHub release with `--publish`. Without `--publish` it writes the bundle and prints what it would upload, the same dry-run-then-apply shape `land_stage.py` uses. Most readers who doubt a benchmark want the rows rather than a way to rerun it (DECISIONS #97). Run it after a campaign is frozen, not after every stage.

## Switching the page to a new campaign

A switch is the one moment the whole page changes at once: a new engine pin, a re-pinned comparator set, new columns, new prose, and a documentation site that describes all of it (DECISIONS #83).

Run `campaign_switch_check.py --new-pin <pin>` first. It reports three things and changes nothing: whether the preconditions hold, which tracked files still name the old pin, and which documentation lines name a version, a date, an issue number, or an instrument label, since those are prose no generator keeps current.

Then, in order: land the final stage and freeze; run every gate on the new payload, including the manifest coverage check; copy the preview payload, images, and prose over the live ones in one commit; publish the results asset (it bundles what the LIVE page serves, so before the switch it would package the previous campaign); delete the preview route so nothing stale is reachable; update the files the check listed that are not historical mentions; update the documentation lines it listed that the new campaign changes; and rebuild both sites, checking that the page's link to the docs and the docs' links to the page still resolve.

Pruning comes before the documentation pass, and the documentation pass is not optional: removing a rule leaves sentences elsewhere that referred to it, and a document describing something that no longer exists is worse than no document. The check reports what should go as well as what should change. It is a report rather than a gate on purpose: a file naming the old pin may be recording history rather than describing the present, and a tool that decided that for you would be wrong in both directions.
