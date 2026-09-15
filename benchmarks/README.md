# ArcadeDB benchmarks: harnesses and results

Two suites, split by what they compare. Both run every backend in Docker under
the same CPU and memory caps, report five repetitions per cell, and publish
the rows their numbers are computed from.

- `experiments/` is **engine versus engine**: ArcadeDB's multi-model engine
  against specialist and multi-model systems, each pinned by image digest, on
  documents, graph, dense and sparse vectors, time series, and cross-model
  queries. Its results are the project page at
  <https://humem.ai/projects/arcadedb>. There is no paper; the page is the
  only artifact, and every number on it is generated from the frozen rows by
  the exporter and checked by gates before it can be published.
- `python-bindings/` is **binding versus binding, and Python versus Java**:
  the same engine reached through the Python package against SQLite, DuckDB,
  LadybugDB, and Chroma, plus `jpype_overhead/`, which times the binding
  against Java-native execution on identical jars. This is the suite behind
  the SciPy 2026 paper, and its own README carries the versions and layout.

## Where to start in `experiments/`

`CAMPAIGN.md` is the operating manual. Its first section is the whole routine
end to end, from settling the instrument to switching the page and pruning
what a campaign made obsolete, and every step names the document that holds
its detail. Read it first; the rest are the references it points to.

| Document | What it settles |
|---|---|
| `CAMPAIGN.md` | The routine: how a campaign is staged, queued, landed, frozen, and switched onto the page |
| `PROTOCOL.md` | How a row is produced, and what enforces each rule (a gate, a check, or a person) |
| `FAIRNESS.md` | When two numbers may be compared: the invariants and the disclosed overrides |
| `COMPARATORS.md` | What every comparator is pinned to, and why it runs the way it does |
| `PAGE-SPEC.md` | What the page contains: tables, rows, columns, and what each cell must satisfy |
| `PUBLISHING.md` | How the numbers get from the frozen rows onto the page, the preview route, and the results asset |
| `READING-RESULTS.md` | How to read what came out without misreading it |
| `RESULTS-MAP.md` | What is in `results/` on the bench host, and which script reads each file |

If two of them disagree, PROTOCOL wins on how a number is produced, FAIRNESS
wins on whether it may be compared, and PAGE-SPEC wins on what is shown.

The Python package's own documentation has a benchmarks section that explains
the method without repeating any number, and links to the page for the
numbers: `bindings/python/docs/benchmarks/`.

## What is tracked

Append logs and regenerable inputs (corpora, databases, per-run time series)
are gitignored; the frozen rows the page is computed from and the generated
tables are committed. The rules live in the repository-root `.gitignore` for
both suites rather than in per-directory files, so one suite's `results/`
convention cannot silently govern the other. `RESULTS-MAP.md` says which files
exist only on the bench host.
