# Benchmark protocol (decided 2026-07-06)

## Resource envelope — parent-cgroup equality

Every cell runs under ONE parent cgroup (`docker run --cgroup-parent=<slice>`)
carrying the cell's TOTAL budget: cpuset = P-core threads only (0-11 on the
i9-12900HK bench host), `--memory` + `--memory-swap` caps, same JVM-heap policy
per scale tier.

- Embedded topology: 1 container under the parent (engine + workload in-process).
- Client-server topology: server container + client container under the SAME
  parent — they compete for the same total; no manual client/server split
  (removes the split-ratio tunable as a bias vector; mirrors a real single-host
  deployment). One sensitivity cell per family uses an explicit 80/20 split to
  show conclusions don't depend on arbitration.
- HA topology (E3): 3 server containers + client under one parent with a bigger,
  stated budget (the co-running IS the experiment).

## Accounting — always sum both sides

- Memory: parent cgroup `memory.peak` (= client + server summed, comparable to
  embedded's single-process number, which inherently includes client-side work).
  Per-container peaks also recorded for breakdown figures.
- CPU: parent cgroup usage (user+sys), plus per-container.
- Cross-check parent numbers against `docker stats` samples (the RSS-confound
  lesson from the cypherglot harness).

## Measurement rules

- Metrics per cell: latency p50/p95/p99 + mean, sustained QPS, bulk-load /
  index-build time, recall@10 vs exact ground truth, peak + post-load RSS,
  on-disk size, cold-start where relevant.
- N=5 repeats -> mean±std; warmups discarded and counted.
- Two-tier parallelism: shuffled parallel sweep (2-3 workers, disjoint cpusets)
  for exploration only; EVERY number reported in the paper comes from serial
  re-runs (one cell at a time, full budget). Manifests record the tier.
- Images pinned by digest on first run; engine versions in every manifest.
