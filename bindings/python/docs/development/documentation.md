# Documentation Development

This guide explains how to work with the MkDocs Material documentation for ArcadeDB Python bindings.

## Documentation Structure

```text
bindings/python/
├── docs/              # Documentation source
│   ├── index.md       # Homepage
│   ├── api-access-methods.md
│   ├── java-api-coverage.md
│   ├── getting-started/
│   ├── guide/
│   ├── api/
│   ├── examples/
│   ├── benchmarks/
│   ├── development/
│   ├── brand/         # Logo and brand assets
│   └── stylesheets/   # extra.css
├── mkdocs.yml         # MkDocs configuration
└── site/              # Built documentation (gitignored)
```

## Local Development

### Preview Documentation

Run a local development server with live reload:

```bash
# Normalize Markdown formatting for proper MkDocs rendering (from bindings/python)
uv run python scripts/fix_markdown.py
```

```bash
# from the repository root, where the uv project and its .venv live
uv run mkdocs serve -f bindings/python/mkdocs.yml
```

Then open: <http://127.0.0.1:8000/arcadedb/>

Any changes to `.md` files will automatically refresh in your browser!

### Build Documentation

Build the static site to verify there are no errors:

```bash
uv run mkdocs build --strict -f bindings/python/mkdocs.yml
```

The built site will be in `site/` directory. `--strict` turns warnings into errors, so a link to
a page that does not exist fails the build. It does not check `#anchors`: MkDocs reports
a link to a missing heading only at `info` level (`validation.links.anchors`), so follow a
link with an anchor in the built site, or build once with a temporary config that sets
`validation: {links: {anchors: warn}}`.

## Versioned Documentation

Documentation is versioned using [mike](https://github.com/jimporter/mike) and automatically deployed when you push a version tag.

### How It Works

1. **Push a version tag** (`X.Y.Z`, `X.Y.Z.devN`, or `X.Y.Z.postN`) as described in
   [Release Workflow](release.md)
2. **GitHub Actions** (`deploy-python-docs.yml`) automatically:
    - Builds documentation with MkDocs
    - Deploys version `X.Y.Z` under `arcadedb/` on the `main` branch of
      [humemai/humemai-docs](https://github.com/humemai/humemai-docs), which serves docs.humem.ai
    - Sets it as the `latest` version (every tag push does, dev tags included)
    - Updates version selector

    It does not wait for the PyPI release, so a tag whose release fails still deploys its
    docs as `latest`.

3. **Users can view**:
    - Latest stable docs: <https://docs.humem.ai/arcadedb/>
    - Specific version: `https://docs.humem.ai/arcadedb/X.Y.Z/` (replace `X.Y.Z` with the release)
    - Version selector in top-right corner

### Deployment Workflow

**Automatic deployment** (recommended): follow [Release Workflow](release.md). The
annotated tag it pushes triggers both the PyPI release and the docs deploy. Do not let
`gh release create` create the tag for you: it makes a lightweight tag at whatever the
target branch points to, which skips the checks in the release procedure.

```text
# Docs deploy to:
# https://docs.humem.ai/arcadedb/X.Y.Z/ (versioned)
# https://docs.humem.ai/arcadedb/ (redirects to latest)
```

**Manual deployment** (for testing):

You can manually trigger deployment from GitHub Actions:

1. Go to **Actions** → **Deploy MkDocs to GitHub Pages**
2. Click **Run workflow**
3. Choose:
    - **Version**: `dev` (or any version name)
    - **Set as latest**: `false` (to keep as separate version)

This creates a test deployment without affecting the stable docs.

### Version Management

The deploy workflow (`.github/workflows/deploy-python-docs.yml`) does not use a `gh-pages` branch.
It checks out `humemai/humemai-docs` (branch `main`) into `humemai-docs/` at the repo root and runs
mike from there with `--deploy-prefix arcadedb --branch main`. Use the same layout and flags by hand
(push access to `humemai/humemai-docs` is required for `--push`):

```bash
# From the repo root
git clone -b main https://github.com/humemai/humemai-docs.git humemai-docs
cd humemai-docs
```

List all deployed versions:

```bash
uv run --project .. --group docs mike list \
  --deploy-prefix arcadedb \
  --branch main \
  --config-file ../bindings/python/mkdocs.yml
```

Delete a version:

```bash
# Replace X.Y.Z with version to delete
uv run --project .. --group docs mike delete \
  --deploy-prefix arcadedb \
  --branch main \
  --push \
  --config-file ../bindings/python/mkdocs.yml \
  X.Y.Z
```

Point `latest` at a different version (the workflow sets the default to the `latest` alias, so
moving the alias is enough):

```bash
# Replace X.Y.Z with the version that should become latest
uv run --project .. --group docs mike alias --update-aliases \
  --deploy-prefix arcadedb \
  --branch main \
  --push \
  --config-file ../bindings/python/mkdocs.yml \
  X.Y.Z latest
```

### Version Alignment

Documentation versions **match PyPI package versions**:

| Release Tag | Docs Version | PyPI Packages |
|-------------|--------------|---------------|
| `X.Y.Z` | `X.Y.Z` | `arcadedb-embedded==X.Y.Z` |
| Example: `26.9.1` | `26.9.1` | `arcadedb-embedded==26.9.1` |

This ensures users always see documentation matching their installed package version.

## Writing Documentation

### Style Guide

**Tone:**

- Friendly and approachable
- Use "you" to address the reader
- Keep sentences concise
- Use active voice

**Code Examples:**

- Show complete, runnable examples
- Include imports and setup
- Add comments for complex logic
- Use realistic variable names

**Organization:**

- Start with simple concepts
- Build to more complex topics
- Use clear headings
- Add navigation hints

### Markdown Features

#### Admonitions (Callouts)

```markdown
!!! note "Title (optional)"
    This is a note with a custom title.

!!! tip
    This is a helpful tip.

!!! warning
    This is a warning.

!!! danger
    This is a critical warning.

!!! info
    This is informational.

!!! success
    This indicates success.
```

#### Code Blocks with Tabs

```markdown
=== "Python"

    ```python
    import arcadedb_embedded as arcadedb
    ```

=== "SQL"

    ```sql
    SELECT * FROM User;
    ```
```

#### Code Block Highlighting

```python
import arcadedb_embedded as arcadedb
db = arcadedb.create_database("./mydb")  # (1)!
db.close()
```

1. Creates a new database in the current directory

#### Internal Links

```markdown
See [Installation Guide](../getting-started/installation.md) for details.

Link to a specific section: [Testing](testing.md#running-the-tests)
```

### API Documentation

An entry in `docs/api/` is a `###` heading with the method name, the signature in a
`python` block, a short description, and then **Parameters:**, **Returns:**, **Raises:**, and
**Example:** in that order, as in [Database API](../api/database.md). Keep it in step with the
signature and docstring in `src/arcadedb_embedded/`.

## Testing Documentation

### Verify All Links Work

Run the strict build above, then follow the links you added or changed in `mkdocs serve`.

### Check Mobile Responsiveness

The Material theme is mobile-responsive by default. Test by:

1. Run `uv run mkdocs serve -f bindings/python/mkdocs.yml` (from the repository root)
2. Open in browser
3. Use browser DevTools responsive mode (F12 → Toggle device toolbar)
4. Test navigation, search, code blocks on mobile sizes

### Test Search

1. Run `uv run mkdocs serve -f bindings/python/mkdocs.yml` (from the repository root)
2. Click search icon (or press `/`)
3. Search for key terms
4. Verify results are relevant

## Continuous Integration

No workflow builds the documentation on a push or a pull request.
`deploy-python-docs.yml` runs only on a version tag or a manual dispatch, and it runs
`mike deploy`, not a strict build. Run the strict build locally before you push a docs
change; it fails on warnings and on links to pages that do not exist (not on missing `#anchors`, see above):

```bash
uv run mkdocs build --strict -f bindings/python/mkdocs.yml
```

The deploy does not use the locked `docs` group of the repo-root project: it installs the
latest `mkdocs-material`, `mkdocs-git-revision-date-localized-plugin`, `mkdocs-macros-plugin`,
and `mike` with `uv pip install --system`. A page that builds locally can still differ in the
deployed build.

`tests/test_docs_examples.py`, part of the test suite, executes a selection of the
Python snippets in these pages (see [Documentation Example Tests](testing.md#documentation-example-tests)).

## Troubleshooting

### "Config file not found"

Run from the repository root:

```bash
uv run mkdocs serve -f bindings/python/mkdocs.yml
```

### "Module not found" error

Install dependencies (docs tooling lives in the `docs` dependency group of the
repo-root uv project):

```bash
uv sync --group docs
```

### Changes not appearing

1. Check file is saved
2. Check terminal for build errors
3. Hard refresh browser (Ctrl+Shift+R)
4. Restart `mkdocs serve`

### Version selector not showing

The version selector appears after deploying at least 2 versions with mike. The deploy workflow
runs these from its `humemai-docs/` checkout (see [Version Management](#version-management)):

```bash
# A release, set as latest
mike deploy --update-aliases \
  --deploy-prefix arcadedb \
  --branch main \
  --push \
  --config-file ../bindings/python/mkdocs.yml \
  X.Y.Z latest \
  --title "X.Y.Z"
mike set-default \
  --deploy-prefix arcadedb \
  --branch main \
  --push \
  --config-file ../bindings/python/mkdocs.yml \
  latest

# A version that is not latest (for example a manual `dev` run)
mike deploy \
  --deploy-prefix arcadedb \
  --branch main \
  --push \
  --config-file ../bindings/python/mkdocs.yml \
  dev \
  --title "dev"
```

## Next Steps

- [Contributing Guide](contributing.md) - How to contribute
- [Testing Guide](testing.md) - Running tests
- [MkDocs Material Reference](https://squidfunk.github.io/mkdocs-material/) - Full documentation
- [mike Documentation](https://github.com/jimporter/mike) - Versioning tool
