# ArcadeDB benchmarks: harnesses and results

Two suites, split by what they compare. Both run on one otherwise idle host,
report N=5 as median [min-max], and publish the rows their numbers are
computed from.

- `experiments/` — **engine vs engine.** ArcadeDB's multi-model engine against
  specialist and embedded systems (Kim, Franchini, Himpe, Garulli): docker,
  pinned image digests, identical cpuset and memory caps per cell. Every
  number that reaches the paper comes from a serial re-run.
- `python-bindings/` — **binding vs binding, and Python vs Java.** The same
  engine reached through the Python package: graph, vector and tabular lanes
  against SQLite, DuckDB, LadybugDB and Chroma, plus `jpype_overhead/`, which
  times the binding against Java-native execution on identical JARs to show
  what crossing the CPython-JVM boundary costs.
- `design-docs/` — reference copies of engine design docs restored from git
  history (`40bc98c843`), kept verbatim as source material.

**What is tracked.** Append logs and regenerable inputs (corpora, databases,
per-run time-series) are gitignored; the frozen rows the papers' numbers are
computed from, and the generated tables, are committed. The rules live in the
repository-root `.gitignore` for both suites rather than in per-directory
files, so one suite's `results/` convention cannot silently govern the other.

Thesis (evidence-audited): multi-model unification over one page/WAL/MVCC
transaction pipeline — documents, graph, KV, time series, and vectors, with
every index type committing in the same transaction and Raft replicating
model-agnostic WAL page diffs. No individual mechanism is claimed as novel.

Read `experiments/FAIRNESS.md` before adding a lane or trusting a number. It
lists the invariants a comparison has to satisfy to be worth reporting, and the
overrides we apply deliberately, and disclose, to put engines at matched
operating points.

The paper source and submission notes are kept outside this repository.
