#!/usr/bin/env python3
"""Render A/B result tables into the docs from committed result files, and fail when a table was edited by hand.

Why: a number typed into a guide drifts from its measurement (a copied "374 ms" once stood where the source
said 372.9). Every A/B figure in the docs is therefore generated: the docs hold a marked block, the numbers
live in a result file, and this script is the only thing that writes between the markers.

    <!-- ab-table: parallel-buckets -->
    ...rendered table, or the "measurement pending" line when there is no result file yet...
    <!-- /ab-table -->

Result files: bindings/python/docs/benchmarks/ab-results/<figure-id>.json, one file per figure, written from
tools/ab.py output (the laptop A/B decision: interleaved arms, a noise gate, round 0 dropped). Format 1:

    {
      "format": 1,
      "figure": "parallel-buckets",                  # one of FIGURES below; equals the file name without .json
      "environment": {                               # the default for every comparison in the file
        "engine_version": "26.10.2",                 # ArcadeDB engine inside the wheel
        "wheel_version": "26.10.2",                  # arcadedb-embedded wheel that was measured
        "cores": "2 (pinned)",                       # cores the timed program ran on
        "machine": "x86-64 laptop, 16 cores"         # public label, not a host name
      },
      "comparisons": [                               # one row of the table each
        {
          "case": "1,000,000 rows, 4 buckets",       # what was run (size, shape, option)
          "metric": "throughput", "unit": "rows/s",
          "better": "higher",                        # "higher" or "lower": which direction is better for the metric
          "a": "sync", "b": "parallel",              # the two arms
          "a_median": 100000.0, "b_median": 112000.0,  # median of each arm over the clean pairs
          "ratio": 0.893,                            # median of the per-round ratios, ab.py's convention: above 1 means B is worse
          "ci_low": 0.85, "ci_high": 0.93,           # bootstrap 95% interval of that median (null with "ratio" when under 7 clean pairs)
          "clean_pairs": 12, "dropped_pairs": 1,     # pairs kept and dropped by the noise, throttle and temperature rules
          "sign_b_better": 11, "sign_b_worse": 1, "sign_p": 0.00635,   # exact two-sided sign test on the pairs
          "environment": {"engine_version": "26.11.1"}   # optional: overrides single keys for this row
        }
      ]
    }

The verdict is never stored: it is derived here from the interval the way ab.py derives it, so a file cannot
contradict itself.

usage: render_ab_tables.py --check | --write [--docs DIR] [--results DIR]
  --check  exit 1 and name every block that differs from what the result files render, and every bad result file
  --write  rewrite the blocks (the only way to change a number in the docs)

Standard library only, ASCII output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS = ROOT / "docs"
DEFAULT_RESULTS = DEFAULT_DOCS / "benchmarks" / "ab-results"
FORMAT = 1
MIN_CLEAN_PAIRS = 7  # tools/ab.py: a verdict needs at least 7 clean pairs

# figure id -> what it measures. The id is the contract between a doc marker and a result file.
FIGURES: dict[str, str] = {
    "ingest-path": "Bulk ingest path: insert_many, insert_columns, insert_dataframe, insert_arrow",
    "parallel-buckets": "Synchronous load against parallel=True, and the bucket count",
    "async-sql-path": "Async executor SQL command path against insert_many(parallel=True)",
    "commit-size": "Commit size: commit_every of insert_many and commitEvery of IMPORT DATABASE",
    "index-before-after": "Index created before or after the load, by index type and engine version",
    "rebuild-threshold": "Vector index mutations_before_rebuild at the default against a high value",
    "materialization": "Result materialization: to_list, to_columns, to_dataframe, to_arrow, to_polars",
    "udf-cost": "Python function in SQL against the equivalent SQL expression",
    "callback-cost": "Per-record callback cost of Database.on(...)",
    "heap-pinned": "JVM heap pinned (-Xms equal to -Xmx) against unpinned",
}

OPEN = re.compile(r"<!-- ab-table: (?P<id>[A-Za-z0-9_-]+) -->")
CLOSE = "<!-- /ab-table -->"
BLOCK = re.compile(
    r"(?P<open><!-- ab-table: (?P<id>[A-Za-z0-9_-]+) -->\n)(?P<body>.*?)(?P<close>"
    + re.escape(CLOSE)
    + ")",
    re.S,
)

ENV_KEYS = ("engine_version", "wheel_version", "cores", "machine")
TOP_KEYS = {"format", "figure", "environment", "comparisons"}
CMP_KEYS = {
    "case", "metric", "unit", "better", "a", "b", "a_median", "b_median", "ratio", "ci_low", "ci_high",
    "clean_pairs", "dropped_pairs", "sign_b_better", "sign_b_worse", "sign_p", "environment",
}  # fmt: skip


class ResultError(Exception):
    """A result file that does not follow format 1."""


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _count(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def validate(data: object, name: str) -> dict:
    """Return data when it follows format 1, else raise ResultError saying what is wrong."""

    def bad(msg: str):
        raise ResultError(f"{name}: {msg}")

    if not isinstance(data, dict):
        bad("top level must be an object")
    if set(data) != TOP_KEYS:
        bad(f"top-level keys must be exactly {sorted(TOP_KEYS)}, got {sorted(data)}")
    if data["format"] != FORMAT:
        bad(f"format must be {FORMAT}")
    if data["figure"] not in FIGURES:
        bad(f"unknown figure {data['figure']!r}; known: {', '.join(FIGURES)}")
    env = data["environment"]
    if (
        not isinstance(env, dict)
        or set(env) != set(ENV_KEYS)
        or not all(isinstance(env[k], str) and env[k] for k in ENV_KEYS)
    ):
        bad(f"environment must hold exactly the non-empty strings {list(ENV_KEYS)}")
    rows = data["comparisons"]
    if not isinstance(rows, list) or not rows:
        bad("comparisons must be a non-empty list")
    for i, r in enumerate(rows):
        at = f"comparisons[{i}]"
        if not isinstance(r, dict):
            bad(f"{at} must be an object")
        missing = CMP_KEYS - {"environment"} - set(r)
        extra = set(r) - CMP_KEYS
        if missing or extra:
            bad(f"{at}: missing {sorted(missing)}, unknown {sorted(extra)}")
        for k in ("case", "metric", "unit", "a", "b"):
            if not isinstance(r[k], str) or not r[k]:
                bad(f"{at}.{k} must be a non-empty string")
        if r["better"] not in ("higher", "lower"):
            bad(f"{at}.better must be 'higher' or 'lower'")
        for k in ("a_median", "b_median"):
            if not _num(r[k]):
                bad(f"{at}.{k} must be a number")
        for k in ("clean_pairs", "dropped_pairs", "sign_b_better", "sign_b_worse"):
            if not _count(r[k]):
                bad(f"{at}.{k} must be a non-negative integer")
        if r["sign_b_better"] + r["sign_b_worse"] > r["clean_pairs"]:
            bad(f"{at}: sign counts exceed clean_pairs")
        interval = (r["ratio"], r["ci_low"], r["ci_high"])
        if all(v is None for v in interval):
            if r["clean_pairs"] >= MIN_CLEAN_PAIRS:
                bad(
                    f"{at}: ratio and interval are required with {MIN_CLEAN_PAIRS} or more clean pairs"
                )
        elif not all(_num(v) for v in interval):
            bad(f"{at}: ratio, ci_low and ci_high are all numbers or all null")
        elif not r["ci_low"] <= r["ratio"] <= r["ci_high"]:
            bad(f"{at}: ratio must lie inside its interval")
        if r["sign_p"] is not None and not (
            _num(r["sign_p"]) and 0 <= r["sign_p"] <= 1
        ):
            bad(f"{at}.sign_p must be null or a number in [0, 1]")
        over = r.get("environment", {})
        if (
            not isinstance(over, dict)
            or not set(over) <= set(ENV_KEYS)
            or not all(isinstance(v, str) and v for v in over.values())
        ):
            bad(
                f"{at}.environment may override only {list(ENV_KEYS)} with non-empty strings"
            )
    return data


def verdict(row: dict) -> str:
    """The decision tools/ab.py prints, derived from the stored interval."""
    if row["clean_pairs"] < MIN_CLEAN_PAIRS or row["ratio"] is None:
        return f"too few clean pairs (need {MIN_CLEAN_PAIRS})"
    lo, hi = row["ci_low"], row["ci_high"]
    if hi < 1.0:
        return f"B better by {(1 - hi) * 100:.0f} to {(1 - lo) * 100:.0f} percent"
    if lo > 1.0:
        return f"B worse by {(lo - 1) * 100:.0f} to {(hi - 1) * 100:.0f} percent"
    return "no detectable difference"


def fmt(x: float) -> str:
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.3g}"


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def effective_env(data: dict, row: dict) -> dict:
    return {**data["environment"], **row.get("environment", {})}


def pending(figure: str) -> str:
    return f"*Measurement pending: figure `{figure}` ({FIGURES[figure]}). No recommendation on this page changes until the A/B result for it is published.*\n"


def render(figure: str, data: dict | None) -> str:
    """The text between the markers for one figure (ends with a newline)."""
    if data is None:
        return pending(figure)
    rows = data["comparisons"]
    envs = [effective_env(data, r) for r in rows]
    distinct = []
    for e in envs:
        if e not in distinct:
            distinct.append(e)
    multi = len(distinct) > 1
    head = [
        "Case",
        "Metric",
        "A",
        "B",
        "A median",
        "B median",
        "B vs A (95% interval)",
        "Sign test (B)",
        "Verdict",
        "Clean pairs",
    ]
    if multi:
        head.insert(1, "Engine")
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r, e in zip(rows, envs):
        ratio = (
            "n/a"
            if r["ratio"] is None
            else f"{r['ratio']:.3f} ({r['ci_low']:.3f} to {r['ci_high']:.3f})"
        )
        p = "n/a" if r["sign_p"] is None else f"{r['sign_p']:.3g}"
        sign = f"{r['sign_b_better']} better, {r['sign_b_worse']} worse, p = {p}"
        pairs = f"{r['clean_pairs']}" + (
            f" ({r['dropped_pairs']} dropped)" if r["dropped_pairs"] else ""
        )
        unit = r["unit"]
        cells = [
            r["case"], f"{r['metric']} ({unit}, {r['better']} is better)", r["a"], r["b"],
            fmt(r["a_median"]), fmt(r["b_median"]), ratio, sign, verdict(r), pairs,
        ]  # fmt: skip
        if multi:
            cells.insert(1, f"engine {e['engine_version']}, wheel {e['wheel_version']}")
        lines.append("| " + " | ".join(cell(c) for c in cells) + " |")
    out = "\n".join(lines) + "\n\n"
    out += (
        "Medians are over the clean pairs of interleaved runs, one fresh process per run, round 0 dropped. "
        "B vs A is the median of the per-round ratios with its bootstrap 95% interval; above 1.000 means B is worse "
        "(B / A for a time, A / B for a rate). A verdict needs the interval to exclude 1.000 and at least "
        f"{MIN_CLEAN_PAIRS} clean pairs.\n\n"
    )
    for e in distinct:
        line = f"Engine {e['engine_version']}, wheel {e['wheel_version']}, cores {e['cores']}, machine {e['machine']}."
        out += ("- " if multi else "") + line + "\n"
    return out


def load_results(results: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not results.is_dir():
        return found
    for path in sorted(results.glob("*.json")):
        try:
            data = validate(json.loads(path.read_text(encoding="utf-8")), path.name)
        except json.JSONDecodeError as exc:
            raise ResultError(f"{path.name}: not valid JSON ({exc})") from exc
        if path.stem != data["figure"]:
            raise ResultError(f"{path.name}: file name must be {data['figure']}.json")
        found[data["figure"]] = data
    return found


FENCE = re.compile(r"^(?P<f>```|~~~).*?^(?P=f)[ \t]*$", re.S | re.M)


def mask_fences(text: str) -> str:
    """text with every fenced code block blanked out (same length), so a marker shown as an example is not a marker."""
    return FENCE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def doc_files(docs: Path):
    return sorted(docs.rglob("*.md"))


def process(docs: Path, results: Path, write: bool) -> list[str]:
    """Return the problems found; with write=True, rewrite the stale blocks."""
    problems: list[str] = []
    try:
        data = load_results(results)
    except ResultError as exc:
        return [str(exc)]
    used: set[str] = set()
    for path in doc_files(docs):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(docs).as_posix()
        masked = mask_fences(text)
        blocks = list(BLOCK.finditer(masked))
        if len(OPEN.findall(masked)) != masked.count(CLOSE) or len(
            OPEN.findall(masked)
        ) != len(blocks):
            problems.append(
                f"{rel}: an ab-table marker is not closed by {CLOSE} (or is nested)"
            )
            continue
        pieces, pos = [], 0
        for m in blocks:
            figure = m.group("id")
            pieces.append(text[pos : m.start()])
            pos = m.end()
            original = text[m.start() : m.end()]
            if figure not in FIGURES:
                problems.append(f"{rel}: unknown figure id {figure!r}")
                pieces.append(original)
                continue
            used.add(figure)
            want = render(figure, data.get(figure))
            if m.group("body") != want:
                problems.append(
                    f"{rel}: table for {figure!r} differs from the result file; run render_ab_tables.py --write"
                )
            pieces.append(m.group("open") + want + m.group("close"))
        pieces.append(text[pos:])
        new = "".join(pieces)
        if write and new != text:
            path.write_text(new, encoding="utf-8")
    for figure in data:
        if figure not in used:
            problems.append(
                f"{figure}.json: no doc carries <!-- ab-table: {figure} -->"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = ap.parse_args(argv)
    problems = process(args.docs, args.results, write=args.write)
    if args.write:
        # a second pass tells what is still wrong after the rewrite (unknown ids, orphan files)
        problems = process(args.docs, args.results, write=False)
    for p in problems:
        print(p)
    if problems:
        print(
            f"{len(problems)} problem(s). The tables between <!-- ab-table --> markers are generated; edit the result file, not the table."
        )
        return 1
    print("OK: every ab-table block matches its result file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
