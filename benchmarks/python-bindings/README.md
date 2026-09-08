# Benchmark suite for "ArcadeDB in Python: An In-Process Multi-Model Database" (SciPy 2026)

Compares `arcadedb-embedded` with embedded Python specialists on one corpus, the Cross
Validated (`stats.stackexchange.com`) Stack Exchange dump: SQLite and DuckDB for documents,
LadybugDB for the graph, Chroma for vectors, plus a Faiss exact baseline for recall. Every
backend runs in-process from Python, inside its own Docker container under the same CPU and
memory caps, five repetitions per cell. It is separate from `bindings/python/examples`.

## Versions behind the paper tables

Every ArcadeDB row in `results/runs_paper.csv` records `lib_version` 26.8.1, the PyPI wheel.
Comparators (`python:3.12-slim`, x86_64):

| Backend | Package | Version | Role |
|---|---|---|---|
| arcadedb-embedded | `arcadedb-embedded` | 26.8.1 | documents + graph + vectors |
| SQLite | stdlib `sqlite3` | 3.46.1 | documents, transactional |
| DuckDB | `duckdb` | 1.5.4 | documents, analytical |
| LadybugDB | `ladybug` | 0.18.1 | graph (see `docs/ladybug-package.md`) |
| Chroma | `chromadb` | 1.5.9 | vectors (HNSW) |
| Faiss | `faiss-cpu` | 1.14.3 | exact recall baseline |

## Environments and isolation

Nothing is installed into the reader's Python. Two mechanisms are used:

- **Benchmark tables: Docker.** `build_images.sh` builds one image per backend from
  `python:3.12-slim` with that backend pinned at the versions in the table above (the pins
  are in the script). `run.py` starts a fresh container for every repetition, so no state
  carries over between runs or backends. Docker and `uv` are the only host requirements.
- **Hybrid workflow: throwaway uv environments.** `reproduce_hybrid.sh` runs each step with
  `uv run --no-project`, pulling `arcadedb-embedded==26.8.1` and its companions from PyPI
  into a cached, disposable environment. It does not use this repository's development
  setup. `ARCADEDB_VERSION=26.9.1 ./benchmarks/python-bindings/reproduce_hybrid.sh` runs the
  same workflow on another release.

## Reproduce the hybrid workflow (paper section "Documents, graph, and vectors in one process")

One command, from anywhere in the repository. It needs only `uv`, not Docker:

```bash
./benchmarks/python-bindings/reproduce_hybrid.sh                     # paper corpus
./benchmarks/python-bindings/reproduce_hybrid.sh stackoverflow-tiny  # quick check, under a minute
```

It downloads the dump and computes the 384-d `all-MiniLM-L6-v2` embeddings if missing (the
slow step), converts the XML to Parquet if missing, then runs `hybrid_showcase.py`, which
prints a `RESULT {json}` line with the per-step timings and a walkthrough of one query.

## Reproduce the benchmark tables

From the repository root (the uv project must be run from there):

```bash
./benchmarks/python-bindings/build_images.sh                                   # one pinned image per backend
uv run python benchmarks/python-bindings/run.py --datasets medium --reps 5     # all three models
uv run --with pandas python benchmarks/python-bindings/make_tables.py          # -> results/tables.md
uv run --with matplotlib --with pandas python benchmarks/python-bindings/make_figures.py
```

`run.py` runs one container at a time, every backend under the same CPU and memory caps,
and records each container's peak memory. It appends every run to `results/runs.jsonl`;
the frozen selection behind the paper is `results/runs_paper.csv`, which the two
generators read. Set `BENCH_DATA` if the datasets are not under
`bindings/python/examples/data`. Ablations (`BENCH_GAV=0`, `BENCH_ARCADE_WAL_FLUSH=2`)
must write to their own `BENCH_RESULTS_DIR`. The result-transport measurement is
`transport_lane.py`; the JPype overhead study is in `jpype_overhead/`.

## Layout

```
benchmarks/python-bindings/
├── README.md
├── reproduce_hybrid.sh        one command: download, embed, prepare, run the hybrid workflow
├── run.py                     orchestrator: containers, caps, repetitions, memory sampling
├── bench_common.py            shared helpers for the three model benchmarks
├── tabular_bench.py           documents: SQLite, DuckDB, ArcadeDB; OLTP and OLAP
├── graph_bench.py             graph: LadybugDB, ArcadeDB; OLTP and OLAP (+ GAV)
├── vector_bench.py            vectors: Chroma, ArcadeDB; build, query latency, recall@10
├── transport_lane.py          result transport into Python: iter_dicts, json, columns, arrow
├── hybrid_showcase.py         vector -> SQL -> Cypher workflow (wrapped by reproduce_hybrid.sh)
├── make_tables.py             results/runs_paper.csv -> results/tables.md
├── make_figures.py            results/runs_paper.csv -> figures/fig_*.png
├── build_images.sh            one pinned Docker image per backend
├── run_smoke_all.sh           build each image and run its smoke test
├── smoke_{arcadedb,chroma,duckdb,faiss,ladybug,sqlite}.py
├── datasets/
│   └── prepare.py             Stack Exchange XML -> Parquet
├── docker/
│   ├── Dockerfile             parameterized per backend
│   └── wheels/                local arcadedb-embedded wheel, if not using PyPI
├── figures/                   architecture and hybrid-workflow diagrams (.dot/.svg/.png), fig_*.png
├── jpype_overhead/            JPype overhead study: Java probes, Python benches, REPORT.md
├── results/
│   ├── runs.jsonl             append log of every run (untracked)
│   ├── runs_paper.csv         frozen selection behind the paper tables (tracked)
│   ├── tables.md              generated by make_tables.py (tracked)
│   ├── lat/                   per-run latency summaries (tracked)
│   ├── mem/                   per-run memory time series (untracked)
│   └── results_abl_*/         ablation campaigns (GAV off, strict durability)
└── docs/
    ├── dev-log-2026-06.md     development log, June to August 2026
    └── ladybug-package.md     LadybugDB package and version note
```

## What is and is not committed

- Raw and prepared datasets are not committed; `reproduce_hybrid.sh` or `datasets/prepare.py`
  rebuild them.
- `results/runs_paper.csv`, `results/tables.md`, and the per-run latency summaries are
  tracked. The append log and memory time series are not (rules in the root `.gitignore`).
