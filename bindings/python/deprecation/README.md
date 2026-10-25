# Deprecation shim for the old PyPI name arcadedb-embedded

The Python bindings move to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python) as `arcadedb` (the native build) and `arcadedb-jvm` (the JVM build), both importing as `arcadedb`. This folder holds the last release of the old name `arcadedb-embedded`: a pure-Python shim that depends on `arcadedb` at the same version, warns once, and re-exports it. The old JVM package therefore moves to the native build, on purpose (decided 2026-10-25). The warning and the README say so in plain words, name `arcadedb-jvm` as the way to keep the JVM build, and link the Which package? page of the new documentation. Users: see [MIGRATION.md](MIGRATION.md).

`arcadedb-embedded-native` (the native preview package) gets no shim. Its PyPI project has no files and is archived, so there is nothing to redirect.

| Folder | PyPI project | Depends on | Version |
|---|---|---|---|
| `arcadedb-embedded/` | `arcadedb-embedded` (old JVM package) | `arcadedb==26.11.1` (the native build) | 26.11.1 |

The shim module is `arcadedb_embedded`. The mapping above lives in one place, `TARGETS` in `build_shims.py`, together with the one assumption behind it: `arcadedb` provides the import name `arcadedb` (the layout says so, but it has no real release yet). `EXTRAS` there maps the extras of the old package to the extras of `arcadedb` (`vector`, the numpy extra, becomes `numpy`; `arcadedb` has no `vector`). `build_shims.py` refuses to build when the shim's `pyproject.toml` (name, description, dependencies, extras, `Replaced by` URL) or its `_NEW_DIST` and `_NEW_MODULE` constants disagree with `TARGETS`. The real package in `bindings/python/src` is not changed and does not warn: the benchmark harness imports it until the split.

**This shim publishes only after the native `arcadedb` 26.11.1 FINAL exists.** It pins `arcadedb==26.11.1`, and a `26.11.1.devN` release does not satisfy that pin. Until the final release is out, do not publish this shim: `pip install arcadedb-embedded` would fail to resolve.

## Build and test (never uploads)

```bash
python3 bindings/python/deprecation/build_shims.py --out /tmp/shims        # uv build, wheel + sdist
taskset -c 0-3 uv run pytest bindings/python/tests/test_deprecation_shims.py   # needs the real wheel installed, like the rest of the suite
```

`build_shims.py` checks each version with `scripts/check_version.py` first; add `--check-pypi` on cutover day to check it is the next version on PyPI (it fails once that version is published).

## Cutover day

1. Release the native `arcadedb` 26.11.1 FINAL from ArcadeData/arcadedb-python first (and `arcadedb-jvm` 26.11.1, which the warning names). Check `pip download --no-deps arcadedb==26.11.1` works: the shim pins this exact version. If the first final `arcadedb` is not out (only `26.11.1.devN`), do not publish the shim.
2. Never push a `26.11.1` tag in this repository: `release-python-packages.yml` would build and publish the real wheels under `arcadedb-embedded`.
3. Build and check: `python3 bindings/python/deprecation/build_shims.py --out dist --check-pypi && uvx twine check dist/*`.
4. Publish the shim. Trusted publishing works only from a workflow, so either (a) register a trusted publisher on the PyPI project `arcadedb-embedded` (repository `humemai/arcadedb-embedded-python`, workflow `publish-deprecation-shims.yml`, environment `pypi`), add the workflow below to `.github/workflows/` (and to `FORK_GITHUB_ALLOWLIST` in `sync-upstream.sh` if another sync will still run), and dispatch it with `publish` on; or (b) upload from a laptop with `uvx twine upload dist/*` and a project-scoped API token.
5. In a clean environment: `pip install arcadedb-embedded==26.11.1` installs `arcadedb` (the native build, not `arcadedb-jvm`: check `pip list`), and `python -W default -c "import arcadedb_embedded"` shows one FutureWarning that names `arcadedb-jvm` for the JVM build.

```yaml
name: Publish deprecation shims
on:
  workflow_dispatch:
    inputs:
      publish:
        description: "Upload to PyPI (off: build and check only)"
        type: boolean
        default: false
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - name: Setup UV package manager
        run: |
          installer="$(mktemp)"
          curl -LsSf --retry 5 --retry-all-errors --retry-delay 5 -o "$installer" https://astral.sh/uv/0.12.0/install.sh
          sh "$installer"
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
      - run: python3 bindings/python/deprecation/build_shims.py --out dist --check-pypi
      - run: uvx twine check dist/*.whl dist/*.tar.gz
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: shims
          path: dist/
  publish:
    needs: build
    if: inputs.publish
    runs-on: ubuntu-24.04
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: shims
          path: dist/
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
        with:
          packages-dir: dist/
```
