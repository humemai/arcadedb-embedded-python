# Documentation Development

This guide explains how to work with the MkDocs Material documentation for ArcadeDB Python bindings.

## Documentation Structure

```text
bindings/python/
├── docs/              # Documentation source
│   ├── index.md       # Homepage
│   ├── getting-started/
│   ├── guide/
│   ├── api/
│   ├── examples/
│   └── development/
├── mkdocs.yml         # MkDocs configuration
└── site/              # Built documentation (gitignored)
```

## Local Development

### Preview Documentation

Run a local development server with live reload:

```bash
# Normalize Markdown formatting for proper MkDocs rendering
python scripts/fix_markdown.py
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

The built site will be in `site/` directory.

### Check for Issues

```bash
# Check for broken links
uv run mkdocs build --strict -f bindings/python/mkdocs.yml

# Validate configuration
uv run mkdocs --version
```

## Versioned Documentation

Documentation is versioned using [mike](https://github.com/jimporter/mike) and automatically deployed when you create release tags.

### How It Works

1. **Create a GitHub Release** with tag like `X.Y.Z`
2. **GitHub Actions** automatically:
    - Builds documentation with MkDocs
    - Deploys version `X.Y.Z` under `arcadedb/` on the `main` branch of
      [humemai/humemai-docs](https://github.com/humemai/humemai-docs), which serves docs.humem.ai
    - Sets it as the `latest` version
    - Updates version selector

3. **Users can view**:
    - Latest stable docs: <https://docs.humem.ai/arcadedb/>
    - Specific version: <https://docs.humem.ai/arcadedb/X.Y.Z/>
    - Version selector in top-right corner

### Deployment Workflow

**Automatic deployment** (recommended):

```bash
# 1. Make documentation changes on main branch
# 2. Build and test wheels
./scripts/build.sh
pytest

# 3. Commit and push changes
git add .
git commit -m "Release version X.Y.Z"
git push origin main

# 4. Create GitHub Release (creates tag automatically)
gh release create X.Y.Z \
  --title "Python Bindings vX.Y.Z" \
  --notes "Release notes"

# ✅ Docs automatically deploy to:
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
| Example: `25.9.1` | `25.9.1` | `arcadedb-embedded==25.9.1` |

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

#### Tables

```markdown
| Feature | Current Package | Notes |
|---------|----------------|--------|
| SQL | ✅ Yes | All SQL features |
| OpenCypher | ✅ Yes | Graph queries |
| Studio UI | ✅ Yes | Web interface |
```

#### Internal Links

```markdown
See [Installation Guide](../getting-started/installation.md) for details.

Link to a specific section: [Testing](testing.md#quick-start)
```

#### External Links

```markdown
Check the [official ArcadeDB docs](https://docs.arcadedb.com) for more.
```

### API Documentation

When documenting API methods, use this structure:

````markdown
## method_name()

Brief one-line description.

**Signature:**

```python
method_name(param1: type, param2: type = default) -> ReturnType
```

**Parameters:**

- `param1` (type): Description of param1
- `param2` (type, optional): Description of param2. Defaults to `default`.

**Returns:**

- `ReturnType`: Description of return value

**Raises:**

- `ExceptionType`: When this exception occurs

**Example:**

```python
result = obj.method_name("value", param2=True)
```
````

## Testing Documentation

### Verify All Links Work

```bash
# Build with strict mode (fails on warnings)
uv run mkdocs build --strict -f bindings/python/mkdocs.yml
```

### Check Mobile Responsiveness

The Material theme is mobile-responsive by default. Test by:

1. Run `mkdocs serve`
2. Open in browser
3. Use browser DevTools responsive mode (F12 → Toggle device toolbar)
4. Test navigation, search, code blocks on mobile sizes

### Test Search

1. Run `mkdocs serve`
2. Click search icon (or press `/`)
3. Search for key terms
4. Verify results are relevant

## Continuous Integration

Documentation is automatically validated on every push via GitHub Actions:

- **Build check**: Ensures documentation builds without errors
- **Version deployment**: Deploys on tagged releases
- **Link validation**: Checks for broken links (TODO)

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
