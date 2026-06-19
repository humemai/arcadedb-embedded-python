# SciPy 2026 — paper + experiments hub

Durable, committed overview of the SciPy 2026 work. Last updated: 2026-06-19.

## Where things live

- **The paper itself is NOT in this repo.** It lives in the SciPy proceedings fork:
  `/home/tk/repos/scipy_proceedings/papers/taewoon_kim/` (`main.md`, `myst.yml`, `mybib.bib`),
  submitted as a PR to **`scipy-conference/scipy_proceedings`** branch `2026`
  (PR title must start with `Paper:`).
- **Experiments live HERE:** `papers/scipy-2026/experiments/` (the benchmark harness).
- **Detailed working docs** (PLAN, EVIDENCE, TODO, LITERATURE, REQUIREMENTS) live next to the
  paper in `scipy_proceedings/papers/taewoon_kim/` and are **local-only** (git-excluded there,
  not pushed). This README is the durable, committed summary of their current state.
- `submission.md` — the original pretalx proposal (historical reference).
- `cfp.md` — the SciPy 2026 call for proposals (reference).

## Paper at a glance

- **Title:** "ArcadeDB in Python: An In-Process Multi-Model Database"
  (proposal title was "From Transactions to Vectors: Embedded Multi-Model Data Workflows in
  Scientific Python"; revisable through late Aug).
- **Author:** Taewoon Kim (solo). ORCID 0000-0003-2892-0194. Affiliation HumemAI.
- **Deadlines:** first-draft PR **2026-06-20** (revisable to late Aug); poster (separate,
  Google Form) 2026-06-29.
- **Scope:** this is a **Python-enablement** paper, NOT a DB-engine paper. Contribution =
  `arcadedb-embedded` (the JPype/in-process Python bindings) + the scientific-Python workflows
  it unlocks. ArcadeDB the engine is credited/cited, not claimed.
- **Companion paper:** a typical DB-engine paper (industry track, with the ArcadeDB authors) is
  separate; keep the two disjoint (engine internals/DB-vs-DB perf there; Python enablement here).
- Package names: PyPI `arcadedb-embedded`, import `arcadedb_embedded`, repo `arcadedb-embedded-python`.

## Experiments (this folder)

DB-to-DB comparison, all **embedded / in-process from Python**. Full OLTP×OLAP crossing per
data-model lane (libraries are NOT competitors — only an exact-search recall baseline).

| Lane | Systems | Workloads |
|---|---|---|
| Tabular (relational) | SQLite, DuckDB, **ArcadeDB** | OLTP × OLAP |
| Graph | Kùzu, **ArcadeDB** | OLTP × OLAP |
| Vector (HNSW) | Chroma + exact baseline, **ArcadeDB** | build + search (recall@k) |

- Dropped: LanceDB (no pure HNSW), Neo4j (server-only from Python), server vector DBs
  (Milvus/Qdrant/pgvector). Neo4j/FalkorDBLite mentioned only in prose.
- Honesty: don't claim ArcadeDB is the *only* embedded multi-model DB (Kùzu has vector+FTS too).
  Claim = uniquely combines OLTP docs + SQL + graph + vectors with full ACID, in-process from Python.

### Protocol (new runs)

- Latest versions, **pinned (version + image digest)**; Docker, **one experiment at a time**,
  identical CPU/mem limits.
- Each comparator as an **embedded lib in one Python process** (not a server).
- **5 reps → mean ± std**; discard warm-up for query/throughput; measure **cold JVM startup**
  separately (it's part of the story).
- Idiomatic index per system; **vector recall@k vs exact (Faiss/bruteforce) baseline**.
- **Scaled down for SciPy:** drop the LARGE tier; use small/medium; report one representative size.
- Kept experiments (from `bindings/python/examples`, re-implemented here, do NOT modify examples):
  lifecycle/startup, tabular OLTP+OLAP, graph OLTP+OLAP (+GAV), vector build+search, hybrid example.

### Benchmark machine

- **`tk@mini`** — Intel i9-12900HK (20 threads), 61 GiB RAM, 1.8 TB disk, Docker 29.5.3
  (no sudo), Ubuntu, system Python 3.14. Runs launched over SSH in the background.

## Reproducibility split

- **Heavy harness** → here (`experiments/`), cited from the paper (URL + pinned commit; Zenodo DOI ideal).
- **Light analysis** → in the PR as supplementary: results CSVs + a small plotting script/notebook
  that builds the paper figures. Keeps the PR clean while figures stay reproducible from data.

## Status / outstanding

- [x] Plan, scope, title, comparison design, protocol — settled.
- [x] Bibliography: embedded-DB landscape + sci-Python stack in `mybib.bib`.
- [ ] Implement the harness here (`experiments/`): add Chroma + Kùzu, recall@k vs exact,
      5-rep/Docker runner, small-scale datasets.
- [ ] Run on `tk@mini`; collect results CSVs.
- [ ] Draft `main.md` sections; build figures from results.
