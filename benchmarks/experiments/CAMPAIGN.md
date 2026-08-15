# Running a campaign

How a full re-measure is executed on mini. `PROTOCOL.md` holds the rules a row
must satisfy; this file holds the procedure that produces the rows. If the two
disagree, PROTOCOL wins and this file is wrong.

The July 2026 campaign record that used to live here was deleted rather than
kept: every number in it came from `26.8.1.dev0`-`dev3` wheels, several have
since been corrected, and a stale summary in the working tree is a number
somebody quotes. It is in git history if it is ever needed.

## 1. The shape: parallel where nothing is measured, serial where it is

**Phase A, parallel.** Image builds, corpus generation and conversion,
ground-truth computation, checksums, dataset staging. None of it produces a
published number, none of it is timed, and it is the only place concurrency is
free. Run it as wide as the box allows.

**Phase B, serial.** The measured cell, whole and undivided: build, settle,
query, close. One at a time, full cpuset `0-11`, nothing else on the machine.
This is `PROTOCOL.md` §2 and it did not change.

### Why Phase B is not parallel, with the numbers

The question is fair and the idle is real: a running cell burns **1.37 CPU-
seconds per wall second** on a 12-thread cpuset, 11.4% of the cpuset and 6.9%
of the machine. Every lane is a closed-loop single-client Python for-loop, so
one core is genuinely the whole critical path. Four things stop that idle from
being usable:

1. **Memory binds before CPU does.** mini has 61.3 GiB. Measured `peak_mib_sum`
   at l3s medium is 30475 MiB per cell, so two of them is 59.5 GiB with nothing
   left for page cache, on a host with `swappiness=10` and 1.6 GiB of swap
   already in use. `runner.py` already refuses this. The tiers where the time
   actually goes — l3s medium, l1 medium, l3d deep10m — admit a concurrency of
   exactly **1**. 16g tiers admit 3, 8g tiers 5-7.

2. **Residency is worth 9-18x to us and 0-7% to every comparator.** Cold vs
   warm p50 at deep10m: `arcadedb_dense_server` 18.26x, `arcadedb_dense_embedded`
   8.97x, and then milvus 1.07x, chroma 1.02x, duckdb-vss 1.01x, sqlite-vec
   1.00x, lancedb 0.99x, qdrant 0.97x. ArcadeDB is lazy; the others are resident
   from load. There is one page cache on the host, so a neighbour cell touching
   a different corpus evicts yours — and it moves one column of the table and
   not the other. This is why permutation does not rescue it: permutation
   protects a ratio, and this is not a level shift applied evenly.

3. **One 24 MiB L3 for the whole package**, shared with the 8 E-cores outside
   the cpuset, against working sets of 0.2-1.3 GiB. Magnitude unmeasured.

4. **Turbo.** At 1.37 busy cores a cell sits near single-core turbo on a mobile
   i9-12900HK. A second cell lowers the clock for both rows.

**And the prize is small.** Perfect intra-lane parallelism at current caps
saves **15-24 hours out of ~153, so 10-16%** — and the 153 h figure is itself
roughly 2.5x too high: it rests on the mean of four logged l3s medium cells,
while the 70 logged cells at that tier and corpus put the full N=5 build at
~15 h rather than 92. A corrected pass is **50-60 hours**, which makes the
saving smaller still and every saved hour a published cell measured under a
condition its neighbours in the table did not get.

**Two things save more and cost nothing.** Parallelise Phase A, which is free.
Then attack the build rather than the concurrency: **86-99% of every expensive
cell is `build_s`** (deep10m 99%, l3s medium 98%, tpch10 91%) and none of it
produces a published latency. Dropping l3s medium from N=5 to N=3 saves ~6 h
against a 29% wider interval, disclosed the way PROTOCOL already requires.
That is larger, auditable and reversible.

### Why the build/query phase split is not adopted either

The proposal was to build every cell in parallel, stop the engine, then reopen
it for an exclusive serial query pass. `lifecycle_probe.py` measured what that
would cost before anything was built around it. Measured on mini, 26.8.1,
embedded arms, N=1 per cell, at four tiers:

| backend | scale | `build_s` | `close_s` | disk pre → post | released | `reopen_s` | cold after build → reopen | drift |
|---|---|---|---|---|---|---|---|---|
| arcadedb l2 | sf1 | 2.67 | 0.028 | 102.8 → 16.1 MB | -84.3% | 0.010 | 0.645 → 0.520 ms | -19.4% |
| arcadedb l2 | sf10 | 19.44 | 0.055 | 146.5 → 109.1 MB | -25.5% | 0.011 | 0.647 → 0.516 ms | -20.2% |
| ladybug l2 | sf1 | 0.44 | 0.030 | 5.0 → 5.0 MB | 0.0% | 0.026 | 0.193 → 0.181 ms | -6.2% |
| ladybug l2 | sf10 | 2.23 | 0.034 | 27.5 → 27.5 MB | 0.0% | 0.027 | 0.192 → 0.194 ms | +1.0% |
| arcadedb l3s | tiny | 8.93 | 0.098 | 191.5 → 156.0 MB | -18.5% | 0.009 | 6.660 → 4.724 ms | -29.1% |
| arcadedb l3s | small | 93.36 | 0.171 | 1540.4 → 1510.3 MB | **-2.0%** | 0.008 | 10.623 → 10.930 ms | **+2.9%** |

**Reopening is cheap and flat: 8-27 ms at every tier, against builds of 0.4 s
to 93 s.** Closing is 28-171 ms. Neither is an obstacle, and both are now
measured rather than assumed (#154, #155).

**The cold-drift hazard is a small-tier artifact, and the last row is the one
that matters.** At sf1/sf10/tiny the reopened pass is 19-29% *faster* than the
post-build pass on ArcadeDB against 1-6% on LadybugDB, which is what a lazy
engine looks like when the whole corpus sits in a page cache that a close does
not flush. At l3s small — 1.5 GB on disk, the first tier where that stops being
free — the drift is **+2.9%**, essentially neutral. The apparent asymmetry
shrinks as the data grows.

So the split is not disqualified, but it is **not yet licensed either**: every
number above is N=1, and no tier here comes close to the ones that dominate the
cost (l3s medium is 8.84M docs and ~30 GiB). A single measurement at a tier
whose working set exceeds the page cache decides it. Until then the split stays
unadopted, because the failure mode is silent: it would move our own rows and
not the comparators', in the direction that flatters us.

Two findings fall out of the same table and stand on their own:

- **What a clean close releases is roughly fixed, not proportional**: 30-87 MB
  at every tier measured, which is 84% of a toy database and 2.0% of a 1.5 GB
  one. LadybugDB releases nothing at either scale because it is already
  settled. A disk column measured pre-close therefore compares our
  WAL-inflated state against a comparator's settled one — real, and bounded at
  tens of MB rather than the fraction the smallest tier suggested. #149/#155.
- `connect_empty_s` is 0.515-0.575 s against an 8-11 ms reopen: creating a
  database and issuing DDL costs ~50x what opening a built one does.

## 2. Staging: smoke, then small, then big

Every campaign runs in three stages and does not advance until the previous one
is green. The reason is arithmetic: a defect found at stage 3 costs a full pass.

1. **Smoke.** Cheapest tier of each lane, N=1. Proves the images, the corpora,
   the adapters and the recorded schema. Rows go to a scratch results file, not
   to `runs.jsonl`.
2. **Small.** One tier up, N=5, real corpora, every metric recorded. This is
   where the gates run for the first time: `fairness_check`,
   `provenance_check`, `claims_check`, `page_check`.
3. **Big.** The published tiers.

Between stages, run the gates and read the monitor's SUSPECT section. A stage
that produces rows no gate admits has failed even if every cell exited 0.

## 3. What every cell records

Beyond the lane's own metrics:

- **Memory.** `peak_anon_mib_sum`, `peak_shmem_mib_sum`, `peak_owned_mib_sum`
  (= anon + shmem), summed across every container in the cell. Anon alone
  misses a POSIX-shmem buffer pool entirely, which is how a PostgreSQL
  comparison came to be 88% our own Python driver.
- **Disk.** `SizeRw` plus `du` over the daemon-reported volume mounts, with a
  settle loop requiring two readings within 1%. `SizeRw` alone reads 20 KB for
  an engine with 1 GiB in a VOLUME.
- **IO.** cumulative `rbytes`/`wbytes` from `io.stat`.
- **Phases.** `build_s`, settle, query generation, ground-truth load, search
  wall, recall computation, and `phases_accounted_s` so unexplained time is
  visible rather than absorbed.
- **Cold and warm**, separately, in every lane that has a repeat pass. Reporting
  one number and not saying which hid a 9.4x second-pass gain on a comparator
  we claim to beat.
- **Envelope.** cpuset, memory cap, heap, observed server heap and page cache,
  `mem_split`, image digest, engine version.

## 4. Monitoring

`monitoring/campaign_watch.py` reads the rows and reports what looks wrong;
`monitoring/campaign_monitor.sh` polls mini and forwards only the SUSPECT
section. Every check exists because this project shipped or nearly shipped that
exact defect. It is not a liveness check: a monitor that only greps for progress
markers is silent through a crash, and silence looks like "still running".

## 5. Launching

```sh
bash build_images.sh                 # Phase A; refuses a pre-release pin
source campaign_env.sh               # the six BENCH_* dataset switches
campaign_env_check                   # asserts every corpus is present
python3 -u runner.py --lanes ... --scale ... --reps 5
```

Rules that have each cost a run:

- Never sync the repo mid-campaign. A `git checkout` reverted a tracked
  `runs.jsonl` and lost rows; a mid-campaign merge split one lane's rows across
  two schemas. Sync between stages, never inside one.
- Archive `runs.jsonl` before anything that could touch it.
- Wait loops read the **last** marker line. `STATUS.txt` is append-only, so a
  bare grep finds this morning's ABORT and acts on it.
- Kill the process group, not the script: `kill -- -PGID`, then verify with
  `docker ps` and `pgrep`.
