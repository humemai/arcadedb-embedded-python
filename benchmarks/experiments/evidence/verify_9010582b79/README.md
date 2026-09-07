# Verification of #7146/#7147 and #7184/#7191 at DEEP-10M on upstream main 9010582b79

Embedded engine from a wheel built at 9010582b79, mini, 24 GB heap, cpuset 0-11, 2026-09-07 (queue qCQ for the cache builds, qCU for the delta probe).

- `cache_default_10m.jsonl`, `cache_lines.txt`: no cache settings; both precisions chose the full 9,990,000-vector cache (#7147 holds at this scale).
- `delta_10000000_bounded.jsonl`: the #7184 probe with the harness waiting for the admitted rebuild. The first rebuild is admitted at 100k buffered and completes (10,100,000 graph nodes); the next, for the 2.4M mutations that accumulated meanwhile, is deferred for memory again.
- `delta_probe.engine-lines.txt`: the engine's Deferring / Starting async / build lines from stderr.
