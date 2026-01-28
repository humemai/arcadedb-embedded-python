#!/usr/bin/env python3
"""Generate a git log sorted by author (commit) date.

Outputs a tab-delimited file with:
    commit_hash, author_date, committer_date, author_name, author_email, subject

Usage:
    ./scripts/git_log_by_commit_date.py
    ./scripts/git_log_by_commit_date.py --output git-log-by-commit-date.tsv
    ./scripts/git_log_by_commit_date.py --repo /path/to/repo --output git-log-by-commit-date.tsv
"""
from __future__ import annotations

import argparse
import datetime
import subprocess
from pathlib import Path


def format_ts(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def build_log(repo: Path) -> list[str]:
    log = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--pretty=format:%h\t%at\t%ct\t%an\t%ae\t%s",
        ],
        text=True,
    )

    rows: list[tuple[int, str, int, str, str, str]] = []
    for line in log.splitlines():
        parts = line.split("\t", 5)
        if len(parts) < 6:
            continue
        commit_hash, author_ts, committer_ts, author_name, author_email, subject = parts
        try:
            author_ts_i = int(author_ts)
            committer_ts_i = int(committer_ts)
        except ValueError:
            continue
        rows.append((author_ts_i, commit_hash, committer_ts_i, author_name, author_email, subject))

    rows.sort(key=lambda row: row[0], reverse=True)

    output: list[str] = [
        "commit_hash\tauthor_date\tcommitter_date\tauthor_name\tauthor_email\tsubject"
    ]
    for author_ts_i, commit_hash, committer_ts_i, author_name, author_email, subject in rows:
        output.append(
            "\t".join(
                [
                    commit_hash,
                    format_ts(author_ts_i),
                    format_ts(committer_ts_i),
                    author_name,
                    f"<{author_email}>",
                    subject,
                ]
            )
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Write git log sorted by author date.")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Path to the git repository (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("git-log-by-commit-date.tsv"),
        help="Output file path (default: git-log-by-commit-date.tsv)",
    )
    args = parser.parse_args()

    lines = build_log(args.repo)
    args.output.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
