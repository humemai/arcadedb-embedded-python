# Syncing Upstream

This fork tracks `ArcadeData/arcadedb` through the local `upstream-main` branch.

## Commands

```bash
./sync-upstream.sh --status
./sync-upstream.sh --dry-run
./sync-upstream.sh
```

## What it does

- Updates `upstream-main` to match `upstream/main`
- Merges `upstream-main` into `main`
- Preserves this fork's root `README.md` and `CLAUDE.md`

## After sync

```bash
cd bindings/python
./build.sh linux/amd64
pytest tests/ -v
git push origin main
```
