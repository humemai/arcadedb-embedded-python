# Sending the Bindings Upstream (retired)

!!! danger "Retired on 2026-10-25. Do not run `make-upstream-pr-branch.sh`."
    ArcadeData/arcadedb deleted `bindings/python` in [#10615](https://github.com/ArcadeData/arcadedb/pull/10615) (commit `1e0507a522`, 2026-10-23, 143 files). There is no upstream tree left to update, so the periodic pull request has nothing to carry, and the sync it was built on is retired too ([Syncing Upstream](sync-upstream.md)). The script now exits with an error and a message that names the decision ("Stop syncing", 2026-10-25).

The Python bindings continue in [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python). Send bindings changes there.

Engine bugs and low-hanging engine fixes still go to ArcadeData/arcadedb, by a different route that does not touch this repository's tree: [Upstream Issues and Fixes](upstream-issues.md).

## What the routine was (record)

Changes made here reached ArcadeData/arcadedb through one branch, `python-bindings`, regenerated from `main` on top of the `upstream-main` mirror by `make-upstream-pr-branch.sh`, after `sync-upstream.sh` and a reconcile of the bindings with whatever the sync brought. It carried upstream's existing `bindings/python` tree with our file contents, plus the two test workflows, and nothing else. The earlier pull requests were ArcadeData/arcadedb#5807, #6889 and #10120 (the 26.10.2 update). The script keeps the full rules in its comments and its git history.
