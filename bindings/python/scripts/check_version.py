#!/usr/bin/env python3
"""Check that a release version follows the counting rule, and is the next one.

The rule (release.md, "Version Numbering"):

- a version is `X.Y.Z`, `X.Y.Z.devN` or `X.Y.Z.postN`, written without leading zeros
- `devN` counts from 0, `postN` counts from 1
- `aN`, `bN`, `rcN` and every other pre-release form are never used, previews included
- the order for one base is `X.Y.Z.dev0`, `.dev1`, ... then `X.Y.Z`, then `X.Y.Z.post1`, `.post2`, ...
- a number is never reused and never skipped: the next devN is one above the highest published
  devN of that base (0 when there is none), and likewise for postN (1 when there is none)

The same scheme applies to the native wheels (`26.10.2.dev0` is a valid native preview).

This script only checks. It never tags, uploads or edits anything, and it fails closed: any
problem reading a published-versions source exits 2, not 0.

usage:
    check_version.py VERSION                              # syntax only
    check_version.py VERSION --published-file FILE        # one version per line, "-" is stdin
    check_version.py VERSION --pypi arcadedb-embedded     # versions on PyPI
    check_version.py VERSION --git-remote origin [--tag-prefix native-v]   # versions in git tags

The sources can be combined. VERSION itself is left out of the git-tag list (the release
workflow runs after its own tag was pushed), but it counts as published when a file or PyPI
lists it.

Exit codes: 0 correct next version, 1 not the correct next version, 2 a source could not be read.
Output is ASCII only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404 - runs `git ls-remote` with a fixed argument list
import sys
import urllib.error
import urllib.request
from typing import Iterable, NamedTuple

VERSION_RE = re.compile(
    r"^(?P<base>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
    r"(?:\.(?P<kind>dev|post)(?P<n>0|[1-9][0-9]*))?$"
)


class Version(NamedTuple):
    base: str
    kind: str  # "dev", "post" or "" for the stable release
    n: int  # 0 for the stable release

    def __str__(self) -> str:
        return f"{self.base}.{self.kind}{self.n}" if self.kind else self.base


class VersionError(Exception):
    """The version breaks the rule."""


def parse_version(text: str) -> Version:
    """Parse a version, or raise VersionError naming the broken part of the rule."""
    match = VERSION_RE.match(text)
    if not match:
        raise VersionError(
            f"{text!r} is not X.Y.Z, X.Y.Z.devN or X.Y.Z.postN "
            "(no aN, bN, rcN, v prefix, leading zeros or other suffix)"
        )
    kind = match.group("kind") or ""
    n = int(match.group("n")) if kind else 0
    if kind == "post" and n < 1:
        raise VersionError(f"{text!r}: postN starts at 1, not 0")
    return Version(match.group("base"), kind, n)


def _parse_published(published: Iterable[str]) -> list[Version]:
    parsed = []
    for text in published:
        try:
            parsed.append(parse_version(text))
        except VersionError:
            # an old or foreign entry cannot take part in the counting
            continue
    return parsed


def check_next(version: str, published: Iterable[str]) -> Version:
    """Return the parsed version when it is the correct next one, else raise VersionError."""
    wanted = parse_version(version)
    seen = _parse_published(published)
    if wanted in seen:
        raise VersionError(
            f"{wanted} is already published and a number is never reused"
        )

    of_base = [v for v in seen if v.base == wanted.base]
    stable = any(v.kind == "" for v in of_base)

    if wanted.kind == "dev":
        if stable:
            raise VersionError(
                f"{wanted}: {wanted.base} is already released, so a dev version of it would sort before it"
            )
        highest = max((v.n for v in of_base if v.kind == "dev"), default=-1)
        if wanted.n != highest + 1:
            raise VersionError(
                f"{wanted}: the next dev version of {wanted.base} is dev{highest + 1}"
            )
    elif wanted.kind == "post":
        if not stable:
            raise VersionError(
                f"{wanted}: {wanted.base} has not been released, so it cannot have a post version"
            )
        highest = max((v.n for v in of_base if v.kind == "post"), default=0)
        if wanted.n != highest + 1:
            raise VersionError(
                f"{wanted}: the next post version of {wanted.base} is post{highest + 1}"
            )
    # a stable release has no counter; "already published" above is its only extra rule
    return wanted


def pypi_versions(project: str) -> list[str]:
    """Versions on PyPI, including ones with only yanked files. A project that does not exist yet has none."""
    url = f"https://pypi.org/pypi/{project}/json"
    if not url.startswith("https://pypi.org/pypi/"):
        raise OSError(f"refusing URL {url}")
    try:
        with urllib.request.urlopen(
            url, timeout=30
        ) as response:  # nosec B310 - fixed https PyPI URL
            data = json.load(response)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        raise OSError(f"PyPI answered {err.code} for {project}") from err
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise OSError(f"cannot read PyPI data for {project}: {err}") from err
    return list(data["releases"])


def git_tag_versions(remote: str, prefix: str = "") -> list[str]:
    """Tag names on a remote that start with prefix, with the prefix removed."""
    try:
        out = subprocess.run(  # nosec B603 B607 - fixed argument list
            ["git", "ls-remote", "--tags", "--refs", remote],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError) as err:
        raise OSError(f"cannot list tags of {remote}: {err}") from err
    names = [
        line.split("\t", 1)[1].removeprefix("refs/tags/")
        for line in out.splitlines()
        if "\t" in line
    ]
    return [name.removeprefix(prefix) for name in names if name.startswith(prefix)]


def read_lines(path: str) -> list[str]:
    try:
        text = (
            sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        )  # noqa: SIM115
    except OSError as err:
        raise OSError(f"cannot read {path}: {err}") from err
    return [line.strip() for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version")
    parser.add_argument("--published-file", action="append", default=[], metavar="FILE")
    parser.add_argument("--pypi", action="append", default=[], metavar="PROJECT")
    parser.add_argument("--git-remote", metavar="REMOTE")
    parser.add_argument(
        "--tag-prefix", default="", help="tag prefix of the series, e.g. native-v"
    )
    args = parser.parse_args(argv)

    try:
        parse_version(args.version)
    except VersionError as err:
        print(f"FAIL: {err}")
        return 1

    published: list[str] = []
    try:
        for path in args.published_file:
            published += read_lines(path)
        for project in args.pypi:
            published += pypi_versions(project)
        if args.git_remote:
            # the tag being released is already pushed: it is not "published" before this check
            published += [
                v
                for v in git_tag_versions(args.git_remote, args.tag_prefix)
                if v != args.version
            ]
    except OSError as err:
        print(f"ERROR: {err}")
        return 2

    try:
        wanted = check_next(args.version, published)
    except VersionError as err:
        print(f"FAIL: {err}")
        return 1
    print(
        f"OK: {wanted} is the correct next version ({len(published)} published versions read)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
