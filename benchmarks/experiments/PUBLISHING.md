# Republishing the project page

PROTOCOL.md says how a run is produced. FAIRNESS.md says what makes a comparison legitimate. READING-RESULTS.md says how to read what came out. This one says how the numbers get from the frozen rows onto humem.ai/projects/arcadedb without going wrong on the way.

## The command

```
BENCH_ENGINE_COMMIT=<pin> python refresh_web_page.py
```

That is the whole routine. It regenerates the tables and figures into `results/generated`, exports the page data, runs the three gates, syncs the JSON and the figures the page references, rewrites PAGE-SPEC.md's generated table inventory, builds the site, and prints the diff. It does not commit: reading the diff before publishing is the point, not an afterthought.

Run it after **any** re-measure, after any change to the tables or figures, and after any change to the page's own table list.

Flags: `--site <path>` if humem.ai is not a sibling checkout; `--no-build` to skip the Next.js build (do not, normally: the build is what catches the page referencing an asset that was never written); `--preview` for the preview target below.

## The preview target (DECISIONS #83)

`refresh_web_page.py --preview` and `land_stage.py --preview` publish to `/projects/arcadedb/next`, the campaign page watched while it fills in: the same exporter, gates, and figures, written to `src/data/arcadedb-benchmarks-next.json` and `public/images/projects/arcadedb-next/`, and checked against the prose in `src/lib/projects/items/arcadedb-next.ts`. The table inventory goes to `results/generated/preview-tables.md` and PAGE-SPEC.md is not rewritten. The route is noindex and not in the project index, and its banner names the pin from the payload.

A preview publish never writes the live payload, the live images, or `arcadedb.ts`. The switch, when the campaign freeze is complete and every gate is green, is one commit that copies the preview payload, images, and prose over the live ones and deletes the route.

## The one rule

> **Every page table is generated from frozen rows, listed in the manifest, pinned by `page_check`, and links its source.**
>
> Adapting a presentation is fine. A cell that traces to no frozen row is not.

This is PAGE-SPEC.md section 6.

## Why it is a script and not a checklist

Every step was once done by hand, and the hand-done ones were where the mistakes were. A figure deleted from its source kept being generated and republished, captioning a real 8.84M measurement as a synthetic corpus. Copying figures one by one has no step that removes one, so the script derives the SVG set from the page source and **deletes** any SVG the page no longer references. The page JSON was copied by hand, so nothing forced it to match what `export_web.py` would produce today; now the exporter's output is the file the site gets.

## What blocks a bad publish

Three gate scripts (`page_check` has two sections), then two structural checks. All of them fail the run rather than warn:

| Check | Asks |
|---|---|
| `provenance_check` | does every cell trace to a run |
| `fairness_check` | F1 to F9 comparison invariants |
| `page_check.MAPPING` | do the page's table cells agree with the generated tables |
| `page_check.PROSE` | do the page's hand-typed prose numbers agree with the tables and the page-derived pins |
| `_check_no_orphan_figures` | is every generated figure cited |
| refresh step 5 | is every figure the page references a generated one |

`MAPPING` and `PROSE` split the page because the two surfaces fail differently. Cells are written by the exporter straight from the frozen results, so a wrong one is nearly impossible. Prose is typed by hand, so a wrong one is nearly inevitable: a caption once gave one engine's dense latency from the canonical CSV and the other's from the matched overlay, inside one sentence, with no published cell wrong and nothing invented.

`WEB_ONLY_FIGURES` is the escape hatch for a figure the page shows and nothing else cites. It is deliberately empty; earn a line in it, do not assume one.

## Adding a table to the page

1. Confirm it is generated from frozen rows and add it to `export_web.LANES` or a builder.
2. Add it to `export_web.py` if the data is not already exported.
3. Reference it from `arcadedb.ts`.
4. Add its headline cells to `page_check.MAPPING`, so the page and the generated tables are pinned to each other. A table nothing pins can drift silently.
5. If the prose around it quotes any number, add each one to `page_check.PROSE` with a regex that captures the digits as printed. Quoting a number in a sentence is making a claim; a claim nothing pins is one nothing checks.
6. Run the command above.

## Adding a figure to the page

1. Confirm something cites it. If nothing does, it does not go on the page.
2. Reference it from `arcadedb.ts` as `/images/projects/arcadedb/<stem>.svg`.
3. Run the command above; it converts and syncs it.

## Landing a finished queue stage

One command, the same order every time, refuses by default:

```
.venv/bin/python benchmarks/experiments/land_stage.py \
    --exclude-backends <backends still running on mini, comma list> \
    [--overlay neo4jvec] [--exclude-since 2026-09-12T12:00] [--preview] \
    --message "<one line: what joined>" [--apply]
```

It pulls `runs_page_<pin>.jsonl` (and, with `--overlay`, an arm's dense multipass files at both sizes), drops the rows of the backends named as still running so a stage in progress never reaches the freeze, merges, publishes through the gates, and prints which page tables changed. Without `--apply` it stops there and restores the site's payload; with `--apply` it builds the site, commits both repositories, and pushes. The merge into `runs.jsonl` is idempotent, so a dry run followed by `--apply` is the normal sequence.

Never `git add` a raw directory (`results/runs.jsonl`, `dense_mp5_*`, `sparse_mp_*`): the bench host writes them, and a tracked copy makes its `git pull --ff-only` refuse, which aborts every queued script. They are ignored by `.gitignore`; keep it that way.
