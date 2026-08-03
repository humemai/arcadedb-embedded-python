# F8: query-time parallelism

Raw artifacts for the F8 invariant in `../../FAIRNESS.md`.

Measured 2026-08-03 on mini. The same dense `tiny` cell (100k vectors, k=10)
run at `--cpuset-cpus 0` and at `--cpuset-cpus 0-11`, three reps each, five
embedded backends. `p50(1cpu)/p50(12cpu)` is the per-query parallel speedup.

`r<rep>_<backend>_<cpuset>.json`, where cpuset `0` is one CPU and `011` is
`0-11`. Reproduce with `~/f8_reps.sh` on mini.

Answer: no embedded engine parallelises a single query (four of five within 2%
of 1.0). LanceDB is reproducibly *slower* on 12 CPUs than on 1 (0.84x, ranges
disjoint across reps), so the shared cpuset costs a comparator rather than
favouring us.

Scope: one tier, one query in flight, embedded only. Says nothing about
concurrent load or about the server-topology engines.
