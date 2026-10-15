# AGENTS.md

This repository is a fork of ArcadeDB. The `CLAUDE.md` files in `engine/`, `ha-raft/` and `studio/` are upstream's and describe the Java engine; do not edit them here. Upstream's root `CLAUDE.md` is not kept in this fork.

Our work is in two places, each with its own rules:

- `bindings/python/`: the Python bindings. Read `bindings/python/AGENTS.md` before changing anything there.
- `benchmarks/`: the benchmark harness and its published results. Read `benchmarks/AGENTS.md` (and its `README.md`) before changing anything there.

The Java engine under `engine/` and the per-language `e2e-*` suites belong to upstream. Report a cause there instead of changing it here: file an issue, and send a pull request only for a low-hanging fix (`bindings/python/docs/development/upstream-issues.md`). The periodic `bindings/python` update to upstream is a separate routine (`bindings/python/docs/development/upstream-bindings-pr.md`).

Planned changes, not final and not yet public: the Python bindings may move to their own repository and PyPI project, and the benchmarks to `humemai/dbbench`, after the October benchmark campaign and the paper. Until then do not rename or move this repository, and do not change the release or upstream-sync routines without asking. The record is `.notes/bench/DECISIONS.md` #182.
