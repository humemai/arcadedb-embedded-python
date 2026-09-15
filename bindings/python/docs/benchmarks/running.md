# Running a Lane Yourself

Everything the published numbers come from is in the repository: the runner, the lane
scripts, every adapter, the image pins, the corpus recipes, and the gates. This page walks
one lane end to end and says what to expect if you run it somewhere other than the bench
host.

!!! warning "This is not a `pip install` benchmark"
    The harness drives Docker directly. It starts a client container and, for a served
    engine, a sibling server container on a cell network, gives both the same CPU set,
    reads their cgroups back, and sizes their disks from the daemon. It needs Docker, a
    checkout, and the corpora on local disk. The corpora alone are tens of gigabytes.

## What You Need

| | |
|---|---|
| **Docker** | Every engine runs in a container, including ArcadeDB. Images are pinned by digest. |
| **The repository** | [`benchmarks/experiments/`](https://github.com/humemai/arcadedb-embedded-python/tree/main/benchmarks/experiments) holds the runner, the lanes, and the gates. |
| **The corpora** | Staged under one host directory, bind-mounted read-only into every container at `/data`. |
| **Disk and memory** | The published tiers assume a machine with 64 GiB. The small tiers do not. |

There is deliberately **no Docker image of the whole harness**. The corpora cannot ship
inside an image, the runner starts comparator servers as sibling containers so such an image
would need the host's Docker socket, and an image pinned to twenty engine digests is stale
at the next re-pin, which means a stranger would run it and get numbers that do not match
the page. The frozen rows and the page payload are published as a release asset instead, so
the tables can be checked against the data without running anything, which is the
verification most readers actually want.

## The Pins

**ArcadeDB** is built as a matched pair from one upstream commit: the wheel that goes into
the client image and the server image, on one JVM. `build_matched_pair.sh` and
`build_c25_wheel.sh` produce it and `verify_pair_c25.sh` verifies that both sides carry the
same JARs and the same JVM major version. At the publishing tier the runner refuses to start
an ArcadeDB run when the engine commit is unset, before any cell runs, because a row that
cannot name its engine cannot reach a table.

**Comparators** are pinned by immutable amd64 manifest digest, listed in the runner's
backend table and recorded on every row. **Client libraries** are pinned by exact version in
`build_images.sh`, which also refuses to bake a pre-release ArcadeDB wheel unless you ask for
one explicitly. The engine versions and digests currently in the harness, and the reason
each engine runs the way it does, are in
[`COMPARATORS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/COMPARATORS.md).

## The Corpora

Each lane reads a real corpus and refuses to fall back to a generated one. Every source is
either public or reproducible from a script in the repository.

| Corpus | Where it comes from |
|---|---|
| TPC-H at scale factor 1 | Generated with DuckDB's `dbgen` and staged as Parquet under `$BENCH_DATA/tpch` |
| LDBC-SNB Interactive v1, SF1 and SF10 | The LDBC council's pre-generated tarballs, extracted under `$BENCH_DATA/ldbc` |
| SIFT1M and DEEP-10M | The ann-benchmarks HDF5 distributions, converted to `.npy` once on the host by `gen_dense_npy.py` so the containers need only numpy |
| Big-ANN 2023 sparse track | The challenge's CSR files and its own top-k ground truth, staged under `$BENCH_DATA/bigann` |
| TSBS cpu-only | `gen_tsbs_corpus.sh`, which records the host count, window, and interval so the corpus can be rebuilt rather than merely copied |

`campaign_env.sh` holds the switch and the mount path for each of them, and
`campaign_env_check` asserts that every corpus is actually present. Setting a path is not
the same claim as the data being there: a lane handed a path with no corpus behind it once
ran green for hours on generated data, and a row records the size it was **asked** for, not
the corpus it read.

## One Lane, End to End

The graph lane at SF1 is the cheapest published tier, so it is the one to try first.

```bash
cd benchmarks/experiments

# Phase A: build the per-backend images. Parallel, nothing is measured here.
bash build_images.sh

# The dataset switches, from the repository rather than from someone's shell history.
source campaign_env.sh
campaign_env_check            # refuses if any corpus is missing

# Phase B: the measured cells, one at a time, on the full CPU set.
python3 -u runner.py --lanes l2 --scale sf1 --reps 5
```

Useful flags while you are finding your feet:

```bash
# One repetition, into a scratch file, to prove the images and the adapters.
python3 -u runner.py --lanes l2 --scale sf1 --reps 1 \
    --results-file runs_smoke.jsonl

# A subset of the lane's engines.
python3 -u runner.py --lanes l2 --scale sf1 --reps 5 \
    --backends arcadedb_graph_embedded,neo4j_graph

# One workload of the lane.
python3 -u runner.py --lanes l2 --scale sf1 --reps 5 --workloads oltp
```

A campaign runs in three stages and does not advance until the previous one is green:
**smoke** (the cheapest tier of each lane, one repetition, into a scratch file, proving the
images, corpora, adapters, and recorded schema), **small** (one tier up, five repetitions,
real corpora, where the gates run for the first time), and **big** (the published tiers). A
defect found at the third stage costs a full pass, and a stage that produces rows no gate
admits has failed even if every cell exited zero.

!!! note "One runner per host"
    The runner takes an exclusive lock. Its orphan sweep would destroy a live campaign's
    in-flight containers, so never co-run a second runner or rebuild a bench image while
    cells are running.

## What Comes Out

One invocation writes:

| Path | What |
|---|---|
| `results/runs.jsonl` | One JSON row per cell, appended. This is the store everything downstream reads. |
| `results/raw/<run_id>.json` | The lane's own output for that cell. |
| `results/raw/<run_id>.clientlog`, `.serverlog` | The container logs, written even for a failed cell. |
| `results/manifest-<timestamp>.json` | Image digests, CPU set, memory caps, heap, tier, and repetition count for the invocation. |
| `results/runs-<timestamp>.csv` | A per-invocation summary, convenient and read by nothing. |

A row carries far more than its timings, because the conditions are read from the container
rather than asserted by the launcher:

- **Identity**: `lane`, `backend`, `workload`, `scale`, `rep`, `tier`, `run_id`, `ts_utc`,
  `instrument`, `bench_host`.
- **Engine**: `engine_version`, `engine_commit` for ArcadeDB, `server_image` and
  `server_image_ref` for a served comparator.
- **Envelope**: `cpuset`, `mem_cap`, `heap`, `server_heap` as observed, `mem_split`,
  `topology`.
- **Outcome**: `rc`, `oom_killed`, `n_rows`, the lane's latency and throughput fields at the
  median and the ninety-ninth percentile, `recall_at_10` where the index is approximate.
- **Footprint**: peak anonymous, shared, and owned memory summed across every container in
  the cell, plus disk for the writable layer and every declared volume, with a settle loop
  and a flag saying whether it converged.
- **Phases**: `ingest_s`, `index_s` where the engine has that boundary, `build_s`, settle,
  query, and an accounted-phases total so unexplained time is visible rather than absorbed.
- **Answers**: a canonical digest, a readable sample, and a row count per timed query.
- **Conditions**: `durability` read back out of the engine, and the package temperature and
  kernel throttle counters at the start and end of the cell.

Then the gates, which you can run by hand after touching results or tables:

```bash
BENCH_ENGINE_COMMIT=<pin> python3 provenance_check.py    # does a cell trace to a run
BENCH_ENGINE_COMMIT=<pin> python3 fairness_check.py      # F1 to F12
BENCH_ENGINE_COMMIT=<pin> python3 page_check.py          # page cells against generated tables
BENCH_ENGINE_COMMIT=<pin> python3 equivalence_check.py   # do the engines of a table agree
```

`equivalence_check.py` takes `--rows <file>` so you can point it at a smoke file rather than
the frozen set. It reduces to the newest row per cell before comparing, so a re-run does not
read as one engine giving two answers.

## On a Machine That Is Not the Bench Host

The harness will run. The numbers will not be comparable with the page, and several things
will behave differently.

**The CPU set string does not mean the same thing.** On the bench host `0-11` is the twelve
hardware threads of six performance cores. On another machine the kernel may lay out
performance and efficiency cores differently, so the same string selects a mix. Set
`BENCH_CPUSET` to whatever the performance cores actually are on your machine, and expect a
different answer from a machine with a different topology, cache, or memory bandwidth.

**The memory caps assume a large machine.** The published tiers step up to tens of gibibytes
per cell, with the JVM heap at half the cap. On a smaller machine, run the `micro` or `tiny`
scales, or pass `--mem` and `--heap` explicitly and accept that you have changed the
envelope for every engine in the comparison, which is a protocol change and not a
convenience.

**Thermal behaviour is part of the result.** A laptop under a long build throttles, and the
throttle counters on the row are the evidence. Two cells measured hours apart on a hot
machine were not necessarily measured at the same clock.

**Your rows are marked as yours.** Every row records the host it ran on, and the runner
refuses to run at the publishing tier with it unset. Rows from a development machine are for
harness development and smoke only, by rule, and nothing produced off the bench host reaches
the page.

**Expect the long tiers to be long.** On the expensive cells the overwhelming majority of the
wall clock is the build, not the queries, and a vector build at the largest tier runs for
hours per cell before a single latency is recorded. Start at a small scale, with one
repetition, on one backend.

!!! tip "If a cell fails, read it before recording it"
    An exit code of zero means a process finished, not that it measured what you asked for.
    Every lane prints phase markers as it runs and the runner records the phase, client
    disk, and memory at a timeout, so a cell that dies inside its budget still says what it
    was doing. Read the cell log and the phase breakdown before calling anything a timeout,
    a failure, or an engine limit. That standard applies to comparators exactly as it
    applies to ArcadeDB.

## Further Reading

The operational documents in the repository go deeper than these pages do:

- [`PROTOCOL.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/PROTOCOL.md): every rule with the tag that says what enforces it.
- [`FAIRNESS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/FAIRNESS.md): the invariants, with the audits behind them.
- [`CAMPAIGN.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/CAMPAIGN.md): how a full re-measure is staged and launched.
- [`COMPARATORS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/COMPARATORS.md): what each comparator is pinned to, and why it runs the way it does.
- [`READING-RESULTS.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/experiments/READING-RESULTS.md): summarised on the next page, [Reading the Output](results.md).
