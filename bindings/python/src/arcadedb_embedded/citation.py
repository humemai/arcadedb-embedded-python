"""Citation helpers for ArcadeDB Embedded Python."""

from __future__ import annotations

from typing import Optional

try:
    from ._version import __version__
except ModuleNotFoundError:
    __version__ = "0.0.0"
from .exceptions import ArcadeDBError

# Offline cache of released package versions -> Zenodo version DOIs. Any
# version not listed here is resolved live against Zenodo (each GitHub
# Release is auto-archived there under the concept record below), so this
# map only spares a network round trip for the versions it happens to know.
_VERSION_DOI_MAP = {
    "26.1.1.post3": "10.5281/zenodo.18399749",
    "26.7.2": "10.5281/zenodo.21373842",
}

# Zenodo concept record grouping every archived release of this package.
_ZENODO_CONCEPT_RECID = "18399208"


def _zenodo_get(url: str):
    import json
    import urllib.request

    with urllib.request.urlopen(url, timeout=10) as resp:  # nosec B310 - fixed https host
        return json.load(resp)


def _zenodo_lookup(version: str) -> Optional[str]:
    """Resolve a version DOI from Zenodo's API; None if not archived there."""
    # The concept record resolves to its latest version; that record's
    # /versions endpoint lists every archived release (25 per page for
    # unauthenticated requests).
    latest = _zenodo_get(
        f"https://zenodo.org/api/records/{_ZENODO_CONCEPT_RECID}")
    recid = latest.get("id", _ZENODO_CONCEPT_RECID)
    page = 1
    while True:
        data = _zenodo_get(
            f"https://zenodo.org/api/records/{recid}/versions"
            f"?size=25&page={page}")
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            return None
        for hit in hits:
            if hit.get("metadata", {}).get("version") == version:
                doi = hit.get("doi")
                if doi:
                    _VERSION_DOI_MAP[version] = doi  # cache for this process
                    return doi
        page += 1


def cite(version: Optional[str] = None) -> str:
    """Return the DOI URL for a given ArcadeDB Embedded Python version.

    Versions in the bundled offline cache resolve immediately; anything
    else is looked up live on Zenodo, where every GitHub Release of this
    package is archived automatically.

    Parameters
    ----------
    version : str or None
        The version to cite. If None, the current installed version is used.

    Returns
    -------
    doi_url : str
        The DOI URL for the given version.

    Raises
    ------
    ArcadeDBError
        If the version is a dev build, is not archived on Zenodo, or the
        Zenodo lookup fails (e.g. offline).

    Examples
    --------
    >>> import arcadedb_embedded as arcadedb
    >>> arcadedb.cite("26.1.1.post3")
    'https://doi.org/10.5281/zenodo.18399749'
    """

    if version is None:
        version = __version__

    doi = _VERSION_DOI_MAP.get(version)
    if doi is None:
        if "dev" in version or version == "0.0.0":
            raise ArcadeDBError(
                f"Version {version} is not a release and has no citable DOI."
            )
        try:
            doi = _zenodo_lookup(version)
        except Exception as e:
            raise ArcadeDBError(
                f"Version {version} is not in the offline citation index and "
                f"the Zenodo lookup failed: {e}"
            ) from e
        if doi is None:
            raise ArcadeDBError(
                f"Version {version} not found in the citation index or on Zenodo"
            )

    return f"https://doi.org/{doi}"
