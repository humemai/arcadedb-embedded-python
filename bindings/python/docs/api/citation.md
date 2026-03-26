# Citation API

The `cite()` helper returns the version-specific DOI URL for released ArcadeDB Embedded Python builds.

## Overview

Use this helper when you want a citable release URL for papers, reports, or reproducibility notes.

The helper is intentionally small:

- released versions return a Zenodo-backed DOI URL
- unreleased development versions raise `ArcadeDBError`
- unknown versions also raise `ArcadeDBError`

## Function

### `cite(version=None) -> str`

Return the DOI URL for a released package version.

**Parameters:**

- `version` (`str | None`): Version to cite. If omitted, the installed package version is used.

**Returns:**

- `str`: DOI URL such as `https://doi.org/10.5281/zenodo....`

**Raises:**

- `ArcadeDBError`: If the version is unreleased or missing from the citation map.

**Example:**

```python
import arcadedb_embedded as arcadedb

doi_url = arcadedb.cite("26.1.1.post3")
print(doi_url)
```

## Notes

- This helper only covers released versions present in the package's internal DOI map.
- Development builds intentionally do not pretend to be citable releases.
- If a new release is missing here, the release metadata needs to be updated in the Python source.
