# AGENTS.md

This repository is a fork of ArcadeDB. The root `CLAUDE.md` and the ones in `engine/`, `ha-raft/` and `studio/` are upstream's and describe the Java engine; do not edit them here.

Our work is in two places, each with its own rules:

- `bindings/python/`: the Python bindings. Read `bindings/python/AGENTS.md` before changing anything there.
- `benchmarks/`: the benchmark harness and its published results. Read `benchmarks/AGENTS.md` (and its `README.md`) before changing anything there.

The Java engine under `engine/` and the per-language `e2e-*` suites belong to upstream. Report a cause there instead of changing it here, and send engine fixes upstream as issues and pull requests (`bindings/python/docs/development/upstream-pr.md`).
