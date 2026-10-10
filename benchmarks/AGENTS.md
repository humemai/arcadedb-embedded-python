# AGENTS.md: benchmarks

Start with `README.md` here: `benchmarks/experiments/` is the live harness whose rows feed the published benchmark pages, and `benchmarks/python-bindings/` is the frozen artifact of the SciPy 2026 paper (not extended). The general rules of `bindings/python/AGENTS.md` apply here too.

## Read first, by task

| You are | Read |
|---|---|
| running a lane | `bindings/python/docs/benchmarks/running.md` |
| changing how a number is produced, adding an engine, or judging fairness, durability, pins or censored cells | `bindings/python/docs/benchmarks/protocol.md` |
| adding or changing a query, or checking that engines answered the same question | `bindings/python/docs/benchmarks/equivalence.md` |
| reading or publishing results | `bindings/python/docs/benchmarks/results.md`, `bindings/python/docs/benchmarks/index.md` |

## Rules for agents

- Never type a number into a page, doc or comment: generate it from the result rows, or check it with a script.
- Change a harness, stage or protocol file in its own pull request, and say what it does to rows that already exist. Do not edit published rows.
- Do not run benchmark compute on the bench host outside the queue that owns it.
- A temporary file says when it goes (`REMOVE WHEN:`). When the code moves to the standalone benchmark repository, this file moves with it.
