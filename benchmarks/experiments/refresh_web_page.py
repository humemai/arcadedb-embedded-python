#!/usr/bin/env python3
"""Republish humem.ai/projects/arcadedb from the frozen results. One command.

    BENCH_PAPER_DIR=<dir with paper.tex> python refresh_web_page.py

Run it after ANY re-measure, and after any change to the tables, the figures
or the page's own table list. It regenerates, gates, and syncs; it does not
commit, because looking at the diff before publishing is the point.

WHY THIS EXISTS. The page used to be refreshed by hand: run two generators,
copy a JSON across repos, run pdftocairo once per figure, rebuild the site.
Every step that a human repeats from memory is a step that gets skipped, and
on 2026-08-11/12 three of them did:

  * A figure the PAPER had deleted as superseded kept being generated, was
    copied across as one of "the papers' figures", and published a real 8.84M
    measurement captioned as a synthetic corpus. Copying figure-by-figure has
    no step that removes one.
  * A stale PDF from a generator retired in July sat in figures/ unnoticed.
  * The page JSON was copied by hand, so nothing forced it to match what
    export_web.py would produce today.

So this script derives what to publish instead of being told:

  the page names its figures  ->  each must be a PDF the paper includes
                              ->  those, and ONLY those, become SVGs
  the exporter writes the JSON ->  that file is the one the site gets

An SVG the page stopped referencing is DELETED, which is the step the manual
routine never had. make_paper_figures' own guard has already refused to emit
any figure no .tex cites, so "referenced by the page" transitively means "in
the paper" and the f5 class of mistake cannot be reintroduced by hand.

WHAT THIS DOES NOT DO. It will not invent a table. The page may only show what
the papers show: adapting a presentation is fine, publishing a result in a
form no reviewer saw is not, or the papers stop being the reviewed artifact.
Adding a table to the page means adding it to `arcadedb.ts`, and it should
correspond to an ICDE table (t2_tabular, t3_graph, t4_sparse, t5_dense_ts) or
a SciPy one (tbl-tabular, tbl-graph, tbl-vector, tbl-latency, tbl-transport).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# repos are siblings: .../humemai/arcadedb-embedded-python and .../humemai/humem.ai
DEFAULT_SITE = HERE.parents[2] / "humem.ai"

PAGE_SOURCE = "src/lib/projects/items/arcadedb.ts"
PAGE_DATA = "src/data/arcadedb-benchmarks.json"
PAGE_IMAGES = "public/images/projects/arcadedb"
IMAGE_URL_RE = re.compile(r"/images/projects/arcadedb/([A-Za-z0-9_]+)\.svg")

GATES = ["provenance_check", "fairness_check", "claims_check", "page_check"]


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def step(n, title):
    print(f"\n[{n}] {title}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=str(DEFAULT_SITE),
                    help=f"humem.ai checkout (default {DEFAULT_SITE})")
    ap.add_argument("--no-build", action="store_true",
                    help="skip the Next.js build; the build is what catches a "
                         "page referencing an asset this script did not write")
    args = ap.parse_args()

    paper_dir = os.environ.get("BENCH_PAPER_DIR")
    if not paper_dir or not Path(paper_dir).is_dir():
        print("BENCH_PAPER_DIR must point at the directory holding paper.tex",
              file=sys.stderr)
        return 2
    figs = Path(paper_dir) / "figures"

    site = Path(args.site).resolve()
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
    exported = HERE / "results" / "web_benchmarks.json"

    step(3, "Gates: nothing is published until all four agree")
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

    step(4, "Sync the page data")
    target = site / PAGE_DATA
    changed = (not target.exists()
               or target.read_bytes() != exported.read_bytes())
    shutil.copyfile(exported, target)
    print(f"  {PAGE_DATA}: {'updated' if changed else 'unchanged'}")

    # VERIFY THE COPY LANDED. The gates in step 3 read the exporter's own
    # output; the site serves this copy. Nothing else compares the two, so a
    # failed write, a stale checkout, or someone editing the site's copy by
    # hand would publish numbers that no gate ever saw.
    #
    # Demonstrated live on 2026-08-14: a wrong value planted in the site's
    # copy left all four gates green, because every one of them reads the
    # generated file instead. That is the same defect class as a figure and a
    # table disagreeing, one directory further downstream.
    if target.read_bytes() != exported.read_bytes():
        raise SystemExit(
            f"  the published copy does not match what the gates checked:\n"
            f"    gates read {exported}\n"
            f"    site serves {target}\n"
            "  Copy failed, or the site's copy was edited by hand. Nothing "
            "below this point should run.")
    print("  verified: the site serves exactly the file the gates checked")

    step(5, "Sync the figures the page actually references")
    wanted = set(IMAGE_URL_RE.findall(page_source.read_text(encoding="utf-8")))
    if not wanted:
        print("  page references no figures")
    images = site / PAGE_IMAGES
    images.mkdir(parents=True, exist_ok=True)

    missing = sorted(s for s in wanted if not (figs / f"{s}.pdf").exists())
    if missing:
        print(f"\n  the page references figures the paper does not produce: "
              f"{', '.join(missing)}", file=sys.stderr)
        print("  Every page figure must be a generated, paper-cited figure. "
              "Either cite it from a .tex or stop referencing it.",
              file=sys.stderr)
        return 1

    for stem in sorted(wanted):
        run(["pdftocairo", "-svg", str(figs / f"{stem}.pdf"),
             str(images / f"{stem}.svg")])

    # The step the manual routine never had.
    for svg in sorted(images.glob("*.svg")):
        if svg.stem not in wanted:
            svg.unlink()
            print(f"  removed {svg.name}: the page no longer references it")

    if not args.no_build:
        step(6, "Build the site")
        run(["npm", "run", "build"], cwd=site,
            stdout=subprocess.DEVNULL)
        print("  build ok")

    step(7, "Review and commit, by hand, on purpose")
    subprocess.run(["git", "status", "--short"], cwd=site)
    print(f"\n  {len(wanted)} figure(s) published: {', '.join(sorted(wanted))}")
    print("  Read the diff before committing. A number moving is news; a "
          "number moving unnoticed is how a wrong one ships.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
