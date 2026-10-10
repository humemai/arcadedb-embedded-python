# AGENTS.md: benchmarks

Read `README.md` here first. `experiments/` is the live harness whose rows feed the published benchmark pages, and `python-bindings/` is the frozen artifact of the SciPy 2026 paper (not extended; new work goes in `experiments/`). The general rules of `bindings/python/AGENTS.md` apply here too (one change keeps everything current, git and GitHub conventions, no secrets).

## Rules specific to measurements

- Every published number comes from the frozen result rows through the exporter and passes the gates before it appears on a page. Never type a number into a page, a doc or a comment; generate it, or check it with a script.
- Every claim names the exact engine build or version, image and settings it was measured on. Re-measure on the current build before saying a bug is fixed or still present.
- Compare engines under the same CPU and memory caps and the same data, and give every engine the setup its own documentation recommends. A comparator's settings are disclosed on the engine's page, and a correction from its maintainers is re-run and added; the old result stays in the history.
- A timing claim quotes an interval from interleaved runs on the same cores, never one percentage from two single runs. A cell that did not finish is a censored measurement and is printed as such, not dropped.
- Change a harness, stage or protocol file in its own pull request and say what it does to existing rows; do not edit rows that were already published.
- Do not run benchmark compute on the bench host outside the queue that owns it.
- A temporary file says when it goes (`REMOVE WHEN:`). When code moves to the standalone benchmark repository, this file moves with it.
