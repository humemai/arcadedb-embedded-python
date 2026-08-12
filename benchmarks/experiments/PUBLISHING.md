# Republishing the project page

PROTOCOL.md says how a run is produced. FAIRNESS.md says what makes a
comparison legitimate. READING-RESULTS.md says how to read what came out.
This one says how the numbers get from the frozen rows onto
humem.ai/projects/arcadedb without going wrong on the way.

## The command

```
BENCH_PAPER_DIR=<dir with paper.tex> python refresh_web_page.py
```

That is the whole routine. It regenerates the tables and figures, exports the
page data, runs all four gates, syncs the JSON and the figures the page
references, builds the site, and prints the diff for you to read. It does not
commit: reading the diff before publishing is the point, not an afterthought.

Run it after **any** re-measure, after any change to the tables or figures,
and after any change to the page's own table list.

Flags: `--site <path>` if humem.ai is not a sibling checkout, `--no-build` to
skip the Next.js build (don't, normally: the build is what catches the page
referencing an asset that was never written).

## The one rule

> **The page shows what the papers show.**
>
> Adapting a presentation is fine. Inventing a result is not, or the papers
> stop being the thing that was reviewed.

Concretely, every table on the page should correspond to one in a paper:

| Paper | Tables |
|---|---|
| ICDE | `t2_tabular`, `t3_graph`, `t4_sparse`, `t5_dense_ts` |
| SciPy | `tbl-capability`, `tbl-tabular`, `tbl-graph`, `tbl-vector`, `tbl-latency`, `tbl-transport` |

The page's "What Python costs" is the one deliberate adaptation: it merges
SciPy's `tbl-latency` and `tbl-transport` into the question a reader actually
arrives with. The numbers are unchanged. That is the line — reshaping how a
result is presented, not producing a result nobody reviewed.

Two page tables were removed on 2026-08-12 for failing this rule: an E2 table
and an E4 table. Both experiments are real and both are in the ICDE paper, but
as **figures plus prose**, with no table behind either. The tables had been
built for the page alone.

## Why it is a script and not a checklist

Every step here was once done by hand, and on 2026-08-11/12 the hand-done ones
were where the mistakes were:

- **A figure the paper had deleted got republished.** `f5_sparse_scaling` was
  dropped from the paper in `366f4c1` as superseded once the 8.84M tier
  landed. Nobody deleted the generator function, so it kept writing a PDF into
  `figures/`, and that directory was later read as if it were the list of "the
  papers' figures". It is not. It is output. **The `.tex` files are the
  manifest.** The orphan then rotted unnoticed, because a figure no paper
  renders is a figure nobody proofreads: it drew ArcadeDB's real 8.84M
  measurement, captioned it as a synthetic corpus, and placed it at 1e7.
- **Copying figures one by one has no step that removes one.** That is why the
  script derives the SVG set from the page source and **deletes** any SVG the
  page no longer references. On its first run it swept `f6_memory_ceiling.svg`,
  converted weeks earlier and never placed.
- **A stale PDF from a retired generator sat in `figures/` since July.**
  `l3_sparse_scale_sweep.pdf`, written by `plot_figures.py`, which
  `make_paper_figures.py` superseded. Nobody had ever noticed.
- **The page JSON was copied by hand**, so nothing forced it to match what
  `export_web.py` would produce today.

## What blocks a bad publish

Four gates, then two structural checks. All of them fail the run rather than
warn:

| Check | Asks |
|---|---|
| `provenance_check` | does every cell trace to a run |
| `fairness_check` | F1–F9 comparison invariants |
| `claims_check` | does the paper's hand-typed prose match the data |
| `page_check` | does the page agree with the paper |
| `_check_no_orphan_figures` | is every generated figure cited by a `.tex` |
| refresh step 5 | is every figure the page references a generated one |

The last two compose into the property that matters: a figure on the page must
be a figure in a paper. `WEB_ONLY_FIGURES` is the escape hatch and is
deliberately empty — earn a line in it, do not assume one.

## Adding a table to the page

1. Confirm it exists in a paper (table above). If it does not, stop.
2. Add it to `export_web.py` if the data is not already exported.
3. Reference it from `arcadedb.ts`.
4. Add its headline cells to `page_check.MAPPING`, so the page and the paper
   are pinned to each other. A table nothing pins can drift silently, which is
   exactly what happened to f5.
5. Run the command above.

## Adding a figure to the page

1. Confirm a `.tex` does `\includegraphics` it. If not, it does not go on the
   page.
2. Reference it from `arcadedb.ts` as `/images/projects/arcadedb/<stem>.svg`.
3. Run the command above; it converts and syncs it.
