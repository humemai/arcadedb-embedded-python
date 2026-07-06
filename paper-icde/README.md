# ArcadeDB DB-engine paper (ICDE 2027 Industry & Applications track)

Working branch `icde-2027` — **never merged to `main`**. Holds the paper LaTeX,
the benchmark harness, and committed result summaries for the ArcadeDB
multi-model engine paper (Kim, Franchini, Himpe, Garulli).

- `latex/` — IEEEtran source; build with `latexmk -pdf paper.tex`.
- `experiments/` — DB-vs-DB benchmark harness (docker, pinned digests,
  identical cpuset/memory caps, N=5 mean±std; every reported number from
  serial re-runs). Raw results are gitignored; summaries are committed.
- `design-docs/` — reference copies of engine design docs restored from git
  history (`40bc98c843`), kept verbatim as paper source material.
- Paper strategy / venue notes / rebuttals live OUTSIDE this repo (private).

Thesis (evidence-audited): multi-model unification over one page/WAL/MVCC
transaction pipeline — documents, graph, KV, time series, and vectors, with
every index type committing in the same transaction and Raft replicating
model-agnostic WAL page diffs. No individual mechanism is claimed as novel.
