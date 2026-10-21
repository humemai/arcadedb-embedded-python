"""The one instrument the publish side renders, and the one place that says so.

Everything that turns frozen rows into a page, a table, a figure or a release asset (make_paper_tables, export_web,
the gates, refresh_web_page, land_stage) renders rows of exactly one instrument. DBBench publishes first with the
2026-11 instrument (DECISIONS #196); no page renders a row stamped 2026-10 or older, or a row with no stamp.

`BENCH_RESULTS_DIR` moves the whole `results/` tree. It exists so a test can run the exporter on a fixture directory;
a publish never sets it.
"""
import os
from pathlib import Path

PUBLISH_INSTRUMENT = "2026-11"

HERE = Path(__file__).resolve().parent


def results_dir() -> Path:
    """results/ beside this file, or the directory BENCH_RESULTS_DIR names."""
    override = os.environ.get("BENCH_RESULTS_DIR", "").strip()
    return Path(override).resolve() if override else HERE / "results"


def instrument_of(row) -> str:
    """The instrument a row says it was measured under; empty for a row from before the stamp existed."""
    return str(row.get("instrument") or "").strip()


def refuse_other_instruments(rows, where: str) -> None:
    """SystemExit when any row is not stamped PUBLISH_INSTRUMENT, naming the stamps found and how many rows carry each."""
    seen: dict = {}
    for r in rows:
        stamp = instrument_of(r)
        if stamp != PUBLISH_INSTRUMENT:
            seen[stamp or "(no stamp)"] = seen.get(stamp or "(no stamp)", 0) + 1
    if seen:
        found = ", ".join(f"{k}: {v}" for k, v in sorted(seen.items()))
        raise SystemExit(f"REFUSING: {where} holds rows of another instrument ({found}). This tooling publishes "
                         f"{PUBLISH_INSTRUMENT} rows only; re-freeze from a {PUBLISH_INSTRUMENT} run (DECISIONS #196).")
