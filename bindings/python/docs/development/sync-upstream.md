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
- Keeps removed upstream workflows from being reintroduced:
  `.github/workflows/mvn-test.yml`, `.github/workflows/mvn-deploy.yml`,
  `.github/workflows/mvn-release.yml`, `.github/workflows/license-compliance.yml`, and
  `.github/workflows/meterian.yml`, and `.github/workflows/studio-security-audit.yml`

## After sync

```bash
cd bindings/python
./scripts/build.sh linux/amd64
pytest tests/ -v
git push origin main
```
