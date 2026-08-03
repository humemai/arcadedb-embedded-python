# ArcadeDB multi-model engine: benchmark harness and results

The DB-vs-DB benchmark harness behind our paper on the ArcadeDB multi-model
engine (Kim, Franchini, Himpe, Garulli), plus the committed result summaries.

- `experiments/` — the harness: docker, pinned image digests, identical cpuset
  and memory caps per cell, N=5 reported as median [min–max]. Every number that
  reaches the paper comes from a serial re-run on one otherwise idle host. Raw
  results are gitignored; summaries are committed.
- `design-docs/` — reference copies of engine design docs restored from git
  history (`40bc98c843`), kept verbatim as source material.

Thesis (evidence-audited): multi-model unification over one page/WAL/MVCC
transaction pipeline — documents, graph, KV, time series, and vectors, with
every index type committing in the same transaction and Raft replicating
model-agnostic WAL page diffs. No individual mechanism is claimed as novel.

Read `experiments/FAIRNESS.md` before adding a lane or trusting a number. It
lists the invariants a comparison has to satisfy to be worth reporting, and the
overrides we apply deliberately, and disclose, to put engines at matched
operating points.

The paper source and submission notes are kept outside this repository.
