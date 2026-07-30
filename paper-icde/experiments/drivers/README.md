# Drivers behind published cells

These produced numbers that appear in the paper. They lived only in
`tk@mini:~/profiling/` and were untracked, while their same-named copies under
`experiments/` were 0-byte and root-owned (a container write that created the
file and never filled it). A published cell whose driver exists on exactly one
machine, in a home directory, is not reproducible, so they are tracked here.

| driver | produced | feeds |
|---|---|---|
| `fp32_dev20_driver.py` | `verify5412b/fp32_dev20_rep*.json` | T5 ArcadeDB (emb) fp32 row |
| `int8_dev20_driver.py` | `verify5412b/int8_dev20_rep*.json` | T5 ArcadeDB (emb, int8, 16 GiB) row |
| `int8_dev20h24_driver.py` | `verify5412b/int8_dev20h24_rep*.json` | matched-24 GiB int8 ablation (prose) |
| `srv5413_driver.py` | `verify5413/srv5413_rep*.json` | T5 ArcadeDB (srv) row |
| `fp32_dev22_driver.py` | `queue34` dev22 dense | not published (see open-improvements item 10) |
| `int8_dev16_driver.py` | superseded dev16 overlay | nothing |
| `fp32_5412_driver.py` | `verify5412` (superseded by `verify5412b`) | nothing |
| `floor_driver.py` | build-memory floor re-check | prose |

`fp32_dev22_driver.py` is `fp32_dev20_driver.py` with the version label
substituted; `queue34` asserted that by diffing the two under label
substitution before running, and the assertion re-verifies here.

## One number worth knowing before reading T5

`fp32_dev20_driver.py`'s docstring records the #5412 close-out baseline as
**"warm query p50 0.81ms / p99 1.22ms at 0.950 recall (must not regress)"**.
Across sessions the same measurement has read:

| when | p50 |
|---|---|
| #5412 close-out baseline | 0.81 ms |
| `verify5412b` (**what T5 publishes**) | 0.723 ms |
| `queue34`, dev22 | 0.835 ms |

So the published value sits at the good end of a band the measurement has
occupied all along, and the dev22 reading is ordinary rather than a
regression. `queue41` runs both arms back to back on one machine state to
settle it; whichever way it lands, T5's dense p50 should be reported as
typical rather than best-observed.
