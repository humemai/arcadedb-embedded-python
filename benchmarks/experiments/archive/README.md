# Campaign script archive

The 175 loose launcher scripts and logs that had accumulated in mini's home
directory, archived here on 2026-08-15 before that directory was cleared.

**This is provenance, not backup.** Sixteen of these scripts are the only
record of how cells the papers currently print were produced: `sparse_2681`,
`dense_mp5_2681`, `e4decomp_2681`, `srv109`, `q17` and the profile runs feed
Tables IV and V and four project-page tables, and the bespoke drivers that
produced them take their configuration from these scripts rather than from
anything in the repo. Delete this and those cells become unreproducible.

It is also the evidence for two defects found the same day:

- The campaign's dataset switches (`BENCH_GRAPH_SOURCE`, `BENCH_SPARSE_SOURCE`
  and friends) lived only in these scripts, so a newly written launcher
  omitted all of them. One lane validated its scale name and crashed; the
  others would have run to completion against synthetic corpora. The forward
  fix is `../campaign_env.sh`, which is in the repo beside the runner.
- Costing the 8.84M sparse tier had to fall back to four unlabelled log lines,
  because per-cell wall clock was never recorded anywhere else. The forward fix
  is the phase timers in `../l3_sparse.py`.

Nothing here should be run again. New work uses the lane scripts through
`runner.py`; see `../campaign_env.sh` for the environment they need.
