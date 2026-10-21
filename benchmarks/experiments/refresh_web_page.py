#!/usr/bin/env python3
"""Republish the DBBench lane pages' data from the frozen 2026-11 results. One command.

    BENCH_ENGINE_COMMIT=<pin> python refresh_web_page.py   # tables and figures land in results/generated

Run it after ANY re-measure, and after any change to the tables or the lane
page's own table list. It regenerates, gates, and syncs; it does not commit,
because looking at the diff before publishing is the point.

WHY THIS EXISTS. A page refreshed by hand skips steps: on 2026-08-11/12 a
figure the paper had deleted kept being copied across and published a real
measurement under a synthetic corpus's caption, and the page JSON was copied
by hand, so nothing forced it to match what export_web.py would produce today.
So this script derives what to publish instead of being told:

  the exporter writes the JSON         ->  that file is the one the site gets
  the lane page names its tables       ->  each must be in the payload, and the
                                           payload carries no table the page
                                           does not name

WHAT THIS DOES NOT DO. It will not invent a table. Every table is generated
from frozen rows and pinned by page_check. Adding a table to the page means
adding it to `src/lib/dbbench/lanes.ts` and to the exporter. The lane pages
reference no figure, so there is no figure sync.
"""

from __future__ import annotations

import argparse
import os
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from publish_instrument import PUBLISH_INSTRUMENT, results_dir

HERE = Path(__file__).resolve().parent
# repos are siblings: .../humemai/arcadedb-embedded-python and .../humemai/humem.ai
DEFAULT_SITE = HERE.parents[2] / "humem.ai"

# One target: the DBBench lane pages. The payload is synced to PAGE_DATA and
# the tables the lane pages ask for are read from PAGE_SOURCE.
PAGE_SOURCE = "src/lib/dbbench/lanes.ts"
PAGE_DATA = "src/data/dbbench-benchmarks.json"

# EQUIVALENCE RUNS BEFORE THE OTHERS (DECISIONS #88). provenance_check asks
# which engine produced a number, fairness_check asks whether the row beside it
# was given the same treatment, page_check asks whether the page says what the
# rows say. None of them asks whether the two engines answered the same
# question, which is the check that decides whether a fast number is also a
# right one, so it is the first gate a publish has to pass.
# SEVEN GATES. resource_check (issue #349) is the newest: it asks whether a disk
# or memory value can be right at all. version_pin_check is the only one
# that reads no rows: the other six ask whether the MEASUREMENTS are sound,
# and this one asks whether the four files a human edits can still disagree
# about which artifact was measured. The pins across runner.py, build_images.sh
# and the three Dockerfiles, with COMPARATORS.md stating them for a reader, and
# nothing compared them until dbbench:pg-age spent a campaign on PostgreSQL
# 17.11 under an instrument declaring 18.6 (BUGS F76).
GATES = ["equivalence_check", "resource_check", "provenance_check", "fairness_check", "page_check",
         "version_consistency_check", "version_pin_check"]


def _refuse_wrong_payload(exported):
    """The site gets a 2026-11 payload cut from measured rows, nothing else."""
    payload = json.loads(exported.read_text(encoding="utf-8"))
    if payload.get("instrument") != PUBLISH_INSTRUMENT or payload.get("skeleton"):
        raise SystemExit(
            f"  REFUSING to publish: the exported payload is stamped instrument "
            f"{payload.get('instrument')!r}, skeleton={payload.get('skeleton')!r}; the lane pages "
            f"take {PUBLISH_INSTRUMENT} measured rows only. Re-freeze from {PUBLISH_INSTRUMENT} runs.")


def run(cmd, **kw):
    """Run a step, and let a step that refuses do its own explaining.

    `check=True` turns a child's clean, deliberate `SystemExit("REFUSING: ...")`
    into a CalledProcessError traceback here, so the last thing printed is this
    file's call stack rather than the reason the child gave -- which it already
    printed, several lines up, where nobody looks after a traceback. Exit with
    the child's own code instead and say nothing more.
    """
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    proc = subprocess.run(cmd, **kw)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc


def step(n, title):
    print(f"\n[{n}] {title}")


def _rewrite_page_spec_inventory(exported: Path, spec: Path | None = None) -> None:
    """Regenerate PAGE-SPEC.md's "Published tables" block from the payload.

    A table list typed by hand is a typed number with extra steps. Runs on
    every publish, so the spec's table list is the payload's table list.
    """
    spec = spec or HERE / "PAGE-SPEC.md"
    if not spec.exists():
        return
    payload = json.loads(exported.read_text(encoding="utf-8"))

    def size_key(label: str):
        m = re.match(r"^\s*([\d.,]+)\s*([kKmM]?)", label)
        if not m:
            return (float("inf"), label)
        n = float(m.group(1).replace(",", ""))
        n *= {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1)
        return (n, label)

    lines = ["## Published tables (generated by refresh_web_page.py from results/web_benchmarks.json on every publish; do not edit by hand)",
             "",
             "Every table carries a Size column and direction arrows; the best value per column within a size is bold on the page; ingest is a pair of columns where the lane records it. Rows: ArcadeDB first, comparators alphabetical, embedded before server, int8 before fp32.",
             "",
             "| id | title | rows | sizes | columns |",
             "|---|---|---|---|---|"]
    for t in payload["tables"]:
        e = t.get("entries", [])
        rows = sorted(set(x["backend"] for x in e))
        sizes = sorted(set(str(x.get("scale_label") or x.get("scale")) for x in e), key=size_key)
        cols = list(e[0]["metrics"].keys()) if e else []
        lines.append(f"| `{t.get('id')}` | {t.get('title', '')} | {', '.join(rows)} | {', '.join(sizes)} | {', '.join(cols)} |")
    block = "\n".join(lines) + "\n"
    text = spec.read_text(encoding="utf-8")
    m = re.search(r"^## Published tables.*?(?=^## |\Z)", text, flags=re.M | re.S)
    text = (text[:m.start()] + block + text[m.end():]) if m else (text.rstrip("\n") + "\n\n" + block)
    spec.write_text(text, encoding="utf-8")
    print(f"  PAGE-SPEC.md inventory: {len(payload['tables'])} tables")


def check_table_coverage(exported: Path, page_source: Path, only_lanes: set) -> int:
    """The lane pages and the payload must agree on the table list, in both directions.

    EVERY TABLE THE PAGE ASKS FOR MUST EXIST IN THE PAYLOAD (BUGS F95). The page
    source names its tables by `tableId`, and the renderer shows nothing at all
    for one the payload does not carry -- no error, no gap, just a heading with
    nothing under it. PAGE-SPEC's inventory cannot catch that, because it is
    written FROM the payload.

    A STAGED LANDING (BENCH_ONLY_LANES) is the one legitimate way to be missing
    tables, and it says so: the payload DECLARES `pending_tables` with a reason,
    the page renders that in the table's place, and this guard is satisfied by
    the declaration rather than by an exemption. Computed here because both
    lists are in hand here; the exporter would need a second copy of the page's
    table list.

    Returns 0 when the two agree, 1 after printing why not.
    """
    payload = json.loads(exported.read_text(encoding="utf-8"))
    have = {t.get("id") for t in payload.get("tables") or []}
    wanted = re.findall(r'tableId:\s*"([A-Za-z0-9_]+)"', page_source.read_text(encoding="utf-8"))
    missing = [t for t in dict.fromkeys(wanted) if t not in have]
    if missing and only_lanes:
        pending = {}
        for t in missing:
            if t == "multimodel":
                pending[t] = ("The capability summary is built from the tables "
                              "above it, so it appears once enough of them have "
                              "been measured at this version.")
            else:
                pending[t] = ("Still being measured at this version. This table "
                              "appears here when its run finishes.")
        payload["pending_tables"] = pending
        exported.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"  {len(pending)} table(s) not yet measured at this pin are declared "
              f"pending, and the page renders that in their place: {missing}")
        missing = []
    if missing:
        print(f"  REFUSING: the page asks for {missing} and the payload carries "
              f"{sorted(have)}; a table the page names and the data lacks renders "
              f"as a heading with nothing under it", file=sys.stderr)
        return 1
    # AND THE OTHER DIRECTION: a table the payload carries and the page never
    # names is generated, gated, published and then not shown.
    unrendered = sorted(t for t in have if t not in set(wanted))
    if unrendered:
        print(f"  REFUSING: the payload carries {unrendered} and the page names no "
              f"section for it; the table would be published and never rendered. "
              f"Add it to the lane page, or stop building it.", file=sys.stderr)
        return 1
    pending = payload.get("pending_tables") or {}
    print(f"  page asks for {len(set(wanted))} table(s), payload carries {len(have)}"
          f"{f' and declares {len(pending)} pending' if pending else ''}, and the two agree")
    return 0


def sync_payload(exported: Path, target: Path) -> None:
    """Copy the payload to the site and verify the copy is byte-identical.

    The gates read the exporter's own output; the site serves this copy.
    Nothing else compares the two, so a failed write, a stale checkout, or
    someone editing the site's copy by hand would publish numbers that no gate
    saw (demonstrated live on 2026-08-14: a wrong value planted in the site's
    copy left every gate green).
    """
    changed = (not target.exists()
               or target.read_bytes() != exported.read_bytes())
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exported, target)
    print(f"  {PAGE_DATA}: {'updated' if changed else 'unchanged'}")
    if target.read_bytes() != exported.read_bytes():
        raise SystemExit(
            f"  the published copy does not match what the gates checked:\n"
            f"    gates read {exported}\n"
            f"    site serves {target}\n"
            "  Copy failed, or the site's copy was edited by hand. Nothing "
            "below this point should run.")
    print("  verified: the site serves exactly the file the gates checked")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=str(DEFAULT_SITE),
                    help=f"humem.ai checkout (default {DEFAULT_SITE})")
    ap.add_argument("--no-build", action="store_true",
                    help="skip the Next.js build; the build is what catches a "
                         "page referencing an asset this script did not write")
    args = ap.parse_args()
    if os.environ.get("BENCH_INSTRUMENT", PUBLISH_INSTRUMENT) != PUBLISH_INSTRUMENT:
        raise SystemExit(f"REFUSING: BENCH_INSTRUMENT={os.environ['BENCH_INSTRUMENT']!r}; this tooling "
                         f"publishes {PUBLISH_INSTRUMENT} rows only (DECISIONS #196).")

    site = Path(args.site).resolve()
    # The gates read the site checkout too (page_check compares the payload the
    # site serves with the one just exported), and a worktree is not a sibling
    # of the other repository, so the path is passed down rather than guessed.
    os.environ["BENCH_SITE_DIR"] = str(site)
    page_source = site / PAGE_SOURCE
    if not page_source.exists():
        print(f"no page source at {page_source}; pass --site", file=sys.stderr)
        return 2

    py = [sys.executable]

    step(1, "Regenerate tables and figures from the frozen rows")
    # make_paper_figures refuses to emit a figure no .tex includes, so this
    # step is also what fails if a retired figure is still being drawn.
    run(py + [str(HERE / "make_paper_tables.py")], cwd=HERE.parents[1])
    run(py + [str(HERE / "make_paper_figures.py")], cwd=HERE.parents[1])

    step(2, "Export the page data")
    run(py + [str(HERE / "export_web.py")], cwd=HERE.parents[1])
    # This path is what step 4 copies to the site and what step 3's gates read,
    # so it must name the file the exporter just wrote and not the one before it.
    exported = results_dir() / "web_benchmarks.json"
    _refuse_wrong_payload(exported)
    _rewrite_page_spec_inventory(exported)

    step(3, "Gates: nothing is published until every gate agrees")
    for gate in GATES:
        proc = subprocess.run(py + [str(HERE / f"{gate}.py")],
                              cwd=HERE.parents[1], capture_output=True,
                              text=True)
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:]
        print(f"  {gate:<18} {'ok  ' if proc.returncode == 0 else 'FAIL'} "
              f"{tail[0] if tail else ''}")
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            print("\nrefusing to publish: a gate failed", file=sys.stderr)
            return 1
    only_lanes = {x.strip() for x in
                  os.environ.get("BENCH_ONLY_LANES", "").split(",") if x.strip()}
    if check_table_coverage(exported, page_source, only_lanes):
        return 1

    step(4, "Sync the page data")
    sync_payload(exported, site / PAGE_DATA)

    if not args.no_build:
        step(5, "Build the site")
        # Own dist directory (next.config.ts distDir), so the gate build never
        # replaces the .next a running dev server in the checkout serves from.
        run(["npm", "run", "build"], cwd=site, stdout=subprocess.DEVNULL,
            env=dict(os.environ, NEXT_DIST_DIR=".next-gate"))
        print("  build ok")

    step(6, "Review and commit, by hand, on purpose")
    subprocess.run(["git", "status", "--short"], cwd=site)
    print("\n  Read the diff before committing. A number moving is news; a "
          "number moving unnoticed is how a wrong one ships.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
