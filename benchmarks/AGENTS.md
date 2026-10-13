# AGENTS.md: benchmarks

Start with `README.md` here: `benchmarks/experiments/` is the live harness whose rows feed the published benchmark pages, and `benchmarks/python-bindings/` is the frozen artifact of the SciPy 2026 paper (not extended). The general rules of `bindings/python/AGENTS.md` apply here too.

Paths in this file are relative to the repository root (the directory that contains `.git`), whatever your working directory is.

## Read first, by task

| You are | Read |
|---|---|
| running a lane | `bindings/python/docs/benchmarks/running.md` |
| changing how a number is produced, adding an engine, or judging fairness, durability, pins or censored cells | `bindings/python/docs/benchmarks/protocol.md` |
| adding or changing a query, or checking that engines answered the same question | `bindings/python/docs/benchmarks/equivalence.md` |
| reading or publishing results | `bindings/python/docs/benchmarks/results.md`, `bindings/python/docs/benchmarks/index.md` |
| running or staging a campaign, or the re-pin checklist | `benchmarks/experiments/CAMPAIGN.md` (its first section is the whole routine; start at `benchmarks/README.md`) |
| landing a stage, freezing rows, or publishing to the page | `benchmarks/experiments/PUBLISHING.md`, `benchmarks/experiments/RESULTS-MAP.md` (what is in `results/` and who reads it) |
| how a row is produced and what enforces each rule | `benchmarks/experiments/PROTOCOL.md` |
| adding or changing a comparator, its pin or its settings, or judging whether two numbers may be compared | `benchmarks/experiments/COMPARATORS.md`, `benchmarks/experiments/FAIRNESS.md` |
| changing what the page shows | `benchmarks/experiments/PAGE-SPEC.md` |
| reading a row's fields without misreading them | `benchmarks/experiments/READING-RESULTS.md` |
| dense or sparse quantization | `benchmarks/experiments/QUANTIZATION.md` |

## Rules for agents

- Never type a number into a page, doc or comment: generate it from the result rows, or check it with a script.
- Change a harness, stage or protocol file in its own pull request, and say what it does to rows that already exist. Do not edit published rows.
- A temporary file says when it goes (`REMOVE WHEN:`). When the code moves to the standalone benchmark repository, this file moves with it.
