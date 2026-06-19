# SciPy 2026 experiments (benchmark harness)

Standalone benchmark harness for the SciPy 2026 paper ("ArcadeDB in Python: An In-Process
Multi-Model Database"). The paper lives in `scipy_proceedings/papers/taewoon_kim/`; see
`../README.md` for the full plan. This harness is **separate from** `bindings/python/examples`
(do not modify those) and is the citable reproducibility artifact for the paper.

> Status: **all 6 backends smoke-passing in Docker** (`python:3.12-slim`, one image per backend).
> See `docker/Dockerfile`, `smoke_*.py`, `run_smoke_all.sh`.

### Verified backends + pinned versions (2026-06-19, x86_64, python:3.12-slim)

| Backend | pip | Version | Role |
|---|---|---|---|
| arcadedb-embedded | `arcadedb-embedded==26.6.1` | 26.6.1 | our system (tabular+graph+vector) |
| SQLite | stdlib | 3.46.1 | tabular OLTP |
| DuckDB | `duckdb` | 1.5.4 | tabular OLAP |
| Kùzu | `kuzu` | 0.11.3 | graph |
| Chroma | `chromadb` | 1.5.9 | vector (HNSW) |
| Faiss | `faiss-cpu` | 1.14.3 | exact recall baseline |

Cross-check: ArcadeDB and Chroma returned identical cosine distances on seeded data → recall@k
methodology is sound. Faiss smoke used L2; the real exact baseline must use the **cosine** space
(normalize + `IndexFlatIP`).

### Dataset prep — working

`datasets/prepare.py <site>` downloads a Stack Exchange dump
(`https://archive.org/download/stackexchange/<site>.7z`, CC BY-SA) and writes one normalized
multi-model dataset to `datasets/prepared/<site>/`: `posts`, `users`, `edges_posted`,
`edges_answers` (Parquet). `posts.text` = title + de-HTML'd body (for embeddings).
Validated on `coffee.stackexchange.com` (4.5k posts, 11.6k users) in ~6s.

- **Site choice for the paper:** pick a thematically-fitting *small* site (candidates:
  `cs.stackexchange.com` — the established choice; or `datascience`/`ai.stackexchange.com`
  for ML relevance). `coffee` is only the pipeline smoke test.
- Snapshot note: archive.org serves the latest dump; record access date for repro.

### Reuse from existing work (do NOT redo)

The package repo already contains most of what we need under `bindings/python/examples/`:

- **Data downloaded:** `examples/data/stackoverflow-tiny/` (~100K records, cs.stackexchange-derived,
  full XML) and `stackoverflow-small/` (cs.stackexchange, 1.41M). No re-download.
- **Embeddings + recall ground-truth precomputed:** `stackoverflow-tiny/vectors/` —
  `all-MiniLM-L6-v2`, **384-d**, 19,591 vectors (Q/A/comments) + `*.gt.jsonl`
  (**1,000 queries × top-50 exact NN**). Reuse as the vector data AND the recall@k baseline.
- **Workload logic + SQLite/DuckDB/Faiss adapters:** examples 07–12. Harness/adapt.
- **Docker matrix orchestration:** `examples/scripts/run_*_matrix.sh`, `summarize_*`. Reuse pattern.

**Chosen small dataset = `stackoverflow-tiny`** (real, laptop-scale, already has vectors + gt).
`prepare.py`'s download path is redundant; keep it only as an optional local-XML normalizer.

### Vector lane — validated (unlimited, tiny)

`vector_bench.py --backend {arcadedb,chroma}` loads the precomputed shards, builds the index,
runs the 1000 gt queries, computes **recall@k vs the exact cosine gt**. Validated on full `tiny`
(19,591 vec, 1000 q): ArcadeDB build 1.76s / q 2.68ms / recall@10 0.995; Chroma build 1.56s /
q 0.95ms / recall@10 0.998. (Unlimited resources — validation, not official numbers.)
IDs are `vector_id` (post_id is NOT unique in the 'all' corpus); gt is in vector_id space.

### Orchestrator `run.py` — validated (laptop)

`run.py --datasets tiny,small,medium --backends arcadedb,chroma --reps 5` runs each backend
container **one-at-a-time** under identical caps (**`--cpuset-cpus=0-7` + `--memory` 8g/16g**),
with a host-side **memory sidecar** (samples cgroup `memory.current`/`anon` every 0.25s →
time series; reads exact kernel `memory.peak`). Outputs: `results/runs.csv` (per-rep: timings,
recall@k, peak+anon MiB, limits, image digest), `results/mem/*.csv` (memory-over-time),
`results/ENV.md` (host + image digests). Validated: vector lane, tiny, 2 reps, both backends.

Standard caps: **cpuset 0-7 (8 P-cores), mem 8g (16g medium)** — same on laptop & mini.

### Tabular lane — validated (tiny)

`tabular_bench.py --backend {sqlite,duckdb,arcadedb} --workload {oltp,olap}` on normalized
`posts.parquet`. Idiomatic bulk load per engine (DuckDB native ingest, not row-by-row).
tiny result: ArcadeDB OLTP 4402 ops/s (vs sqlite 297, duckdb 375); OLAP duckdb 2.7ms /
sqlite 4.1ms / arcadedb 81ms. On-thesis: OLTP-first vs analytics-oriented.
`datasets/prepare.py <stackoverflow-tiny|...>` normalizes local XML → parquet (no re-download).

### Graph lane — validated (tiny)

`graph_bench.py --backend {kuzu,arcadedb} --workload {oltp,olap}`. Graph:
(User)-[:POSTED]->(Post), (Post)-[:ANSWERS]->(Post); edges filtered to existing endpoints.
Shared Cypher (ints embedded). Kùzu loads via COPY (idiomatic bulk); ArcadeDB via transactional
CREATE. tiny: ArcadeDB OLTP 3827 ops/s (vs kuzu 1006), write 0.29ms vs 5.3ms; Kùzu OLAP 8.5ms
vs arcadedb 59ms + faster bulk load. On-thesis (OLTP-first vs OLAP-optimized).

### All three lanes validated (laptop, tiny) — coherent story

ArcadeDB: competitive vector recall; **wins OLTP** (tabular ~12×, graph ~4×); loses OLAP to the
specialists (DuckDB/SQLite ~25×, Kùzu 7×). Honest, no cherry-picking.

### Full suite orchestrated — validated (laptop, tiny, 2 reps)

`run.py --datasets tiny --reps 2 --lanes vector,tabular,graph` ran all 12 cells × 2 reps = 24
runs clean, capped (cpuset 0-7, 8g) with memory tracking → `runs.csv` (24 rows), `manifest.json`,
`ENV.md`, 24 `mem/*.csv`. Memory tradeoff quantified: ArcadeDB (JVM) ~440-700 MiB vs
SQLite ~63 / DuckDB ~107 / Kùzu ~210 / Chroma ~560 MiB.

**Harness complete.** Remaining = (1) `prepare.py` for small + medium (tabular/graph need their
`prepared/` parquet; vector already has all three), (2) move to mini: clone repo, build images,
rsync data, run official `--reps 5 --datasets tiny,small,medium`.

### Real remaining work (everything else is reuse)

- **Chroma** vector adapter (load the existing `.f32` vectors; recall@k vs `gt.jsonl`).
- **Kùzu** graph adapter + graph workload.
- **Clean, trimmed runner** for our 4 lanes × small scale × 5 reps (drop server backends + the
  sprawling matrix) — this is the "fit SciPy" repackaging.
- Wire recall@k to the existing `gt.jsonl`; quiet JVM INFO logs.

## What it does

DB-to-DB comparison, all **embedded / in-process from Python**, full OLTP×OLAP crossing per
data-model lane, plus vector build/search with honest recall@k.

| Lane | Systems | Workloads |
|---|---|---|
| Tabular | SQLite, DuckDB, ArcadeDB | OLTP × OLAP |
| Graph | Kùzu, ArcadeDB | OLTP × OLAP |
| Vector (HNSW) | Chroma, ArcadeDB (+ Faiss/bruteforce exact baseline) | build + search, recall@k |

## Protocol

- Latest versions, **pinned** (record version + Docker image digest).
- **Docker, one experiment at a time**, identical CPU/memory limits across containers.
- Each comparator runs as an **embedded library inside one Python process** (not a server).
- **5 repetitions** per cell → report **mean ± std** (min/max ok).
- Discard a warm-up for query/throughput; measure **cold JVM startup** separately.
- Idiomatic index per system; **vector recall@k vs exact** (Faiss/bruteforce) ground truth.
- **Scaled down:** small/medium dataset only (no LARGE tier); one representative size in-paper.
- Dataset: Stack Overflow (same data for all systems); cite the dump source.

## Planned layout (to build)

```
experiments/
  README.md            # this file
  datasets/            # download + prep scripts (small/medium)
  backends/            # one adapter per system: arcadedb, sqlite, duckdb, kuzu, chroma, exact
  workloads/           # tabular_oltp, tabular_olap, graph_oltp, graph_olap, vector
  docker/              # per-backend Dockerfiles / pinned images
  run.py               # orchestrator: 5 reps, isolation, env capture → results/*.csv
  results/             # output CSVs (mean/std) — feed the paper's plotting
  ENV.md               # captured environment (CPU/RAM/OS/Docker/versions/digests)
```

## Running (target: tk@mini)

- Sync this repo to `tk@mini`, run the orchestrator in the background (tmux/nohup) over SSH.
- Collect `results/*.csv`; copy the light plotting + CSVs into the PR as supplementary.
- Record environment to `ENV.md` for the paper's reproducibility section.
