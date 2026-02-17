#!/usr/bin/env python3
"""Generate CFF-style authors from git commit history.

Default behavior:
- Uses the entire repository history (all contributors, including bots)
- Prints CFF-ready YAML lines for the `authors:` section

Optional behavior:
- `--write-citation` updates the `authors:` block in `CITATION.cff`
"""
from __future__ import annotations

import argparse
import re
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Author:
    name: str
    email: str
    lines_changed: int


def detect_repo_root() -> Path:
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )


def collect_authors(repo: Path) -> list[Author]:
    log_output = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--all",
            "--numstat",
            "--pretty=format:@@@%aN <%aE>",
        ],
        text=True,
    )

    merged: "OrderedDict[str, Author]" = OrderedDict()
    current_name = ""
    current_email = ""
    for line in log_output.splitlines():
        if line.startswith("@@@"):
            author_match = re.match(r"^@@@(.+?)\s+<(.+)>\s*$", line)
            if not author_match:
                current_name = ""
                current_email = ""
                continue

            current_name = author_match.group(1).strip()
            current_email = author_match.group(2).strip()
            key = current_name.lower()
            if key not in merged:
                merged[key] = Author(name=current_name, email=current_email, lines_changed=0)
            continue

        if current_name == "":
            continue

        stats_match = re.match(r"^(\d+|-)\t(\d+|-)\t", line)
        if not stats_match:
            continue

        added_token = stats_match.group(1)
        deleted_token = stats_match.group(2)
        added = int(added_token) if added_token.isdigit() else 0
        deleted = int(deleted_token) if deleted_token.isdigit() else 0
        delta = added + deleted

        if delta == 0:
            continue

        key = current_name.lower()
        existing = merged[key]
        merged[key] = Author(
            name=existing.name,
            email=existing.email,
            lines_changed=existing.lines_changed + delta,
        )

    authors = list(merged.values())
    authors.sort(key=lambda author: (-author.lines_changed, author.name.lower()))
    return authors


def render_cff(authors: list[Author]) -> list[str]:
    lines = ["authors:"]
    for author in authors:
        escaped_name = author.name.replace("'", "''")
        lines.append(f"  - name: '{escaped_name}'")
    return lines


def update_citation_authors(citation_file: Path, author_lines: list[str]) -> None:
    lines = citation_file.read_text().splitlines()

    start = -1
    for index, line in enumerate(lines):
        if line.strip() == "authors:":
            start = index
            break

    if start == -1:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(author_lines)
    else:
        end = start + 1
        while end < len(lines):
            current = lines[end]
            if current.startswith("  -") or current.startswith("    ") or current.strip() == "":
                end += 1
                continue
            break
        lines = lines[:start] + author_lines + lines[end:]

    citation_file.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CFF author entries from repository git history.")
    parser.add_argument(
        "--write-citation",
        action="store_true",
        help="Replace the authors block inside CITATION.cff",
    )
    args = parser.parse_args()

    repo = detect_repo_root()
    authors = collect_authors(repo=repo)
    lines = render_cff(authors)

    if args.write_citation:
        citation_file = repo / "CITATION.cff"
        update_citation_authors(citation_file, lines)
        print(f"Updated {citation_file} with {len(authors)} authors")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
