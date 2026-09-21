#!/usr/bin/env python3
"""Republish humem.ai/projects/arcadedb from the frozen results. One command.

    BENCH_ENGINE_COMMIT=<pin> python refresh_web_page.py   # tables and figures land in results/generated

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

WHAT THIS DOES NOT DO. It will not invent a table. Every page table and figure
is generated from frozen rows, listed in the page manifest, pinned by
page_check, and carries a source link to a tracked artifact (PAGE-SPEC 6; the
paper was dropped on 2026-09-11, so the page is the only publication target).
Adding a table to the page means adding it to `arcadedb.ts` and to the
exporter, generated from frozen rows and pinned by page_check.
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

HERE = Path(__file__).resolve().parent
# repos are siblings: .../humemai/arcadedb-embedded-python and .../humemai/humem.ai
DEFAULT_SITE = HERE.parents[2] / "humem.ai"

# Two targets, one pipeline (DECISIONS #83). "live" is /projects/arcadedb;
# "preview" is /projects/arcadedb/next, the October campaign watched while it
# fills in. A preview publish touches only the preview paths; the live page is
# never written by it. The switch, when the October freeze is complete, is
# copying the preview payload, images, and prose over the live ones and
# deleting the route.
TARGETS = {
    "live": {
        "source": "src/lib/projects/items/arcadedb.ts",
        "data": "src/data/arcadedb-benchmarks.json",
        "images": "public/images/projects/arcadedb",
        "image_re": re.compile(r"/images/projects/arcadedb/([A-Za-z0-9_]+)\.svg"),
    },
    "preview": {
        "source": "src/lib/projects/items/arcadedb-next.ts",
        "data": "src/data/arcadedb-benchmarks-next.json",
        "images": "public/images/projects/arcadedb-next",
        "image_re": re.compile(r"/images/projects/arcadedb-next/([A-Za-z0-9_]+)\.svg"),
    },
}
PAGE_SOURCE = TARGETS["live"]["source"]
PAGE_DATA = TARGETS["live"]["data"]
PAGE_IMAGES = TARGETS["live"]["images"]
IMAGE_URL_RE = TARGETS["live"]["image_re"]
# STAYS UNDER results/generated ON PURPOSE, unlike the tables and figures.
# This is the preview route's table inventory, October's counterpart to
# PAGE-SPEC.md, and it is separated from September's by NAME -- the same way
# runs_paper_oct.csv sits beside runs_paper.csv. It is not written by a freeze
# and it overwrites nothing of September's, so moving it into generated_oct
# would only churn the tracked path it has been published under.
PREVIEW_INVENTORY = HERE / "results" / "generated" / "preview-tables.md"

# EQUIVALENCE RUNS BEFORE THE OTHERS (DECISIONS #88). provenance_check asks
# which engine produced a number, fairness_check asks whether the row beside it
# was given the same treatment, page_check asks whether the page says what the
# rows say. None of them asks whether the two engines answered the same
# question, which is the check that decides whether a fast number is also a
# right one, so it is the first gate a publish has to pass.
# SIX GATES. version_pin_check is the newest (2026-09-21) and is the only one
# that reads no rows: the other five ask whether the MEASUREMENTS are sound,
# and this one asks whether the four files a human edits can still disagree
# about which artifact was measured. 86 pins across runner.py, build_images.sh
# and the two Dockerfiles, with COMPARATORS.md stating them for a reader, and
# nothing compared them until dbbench:pg-age spent a campaign on PostgreSQL
# 17.11 under an instrument declaring 18.6 (BUGS F76).
GATES = ["equivalence_check", "provenance_check", "fairness_check", "page_check",
         "version_consistency_check", "version_pin_check"]

# THE SKELETON GUARDS (DECISIONS #86). A skeleton publish fills the preview
# route with placeholder cells from a one-repetition laptop run so the October
# page's shape can be read early. A skeleton that looks like a measurement is
# worse than no skeleton, so the guards below are the decision, not options:
#
#   * every frozen row must carry a bench_host that is NOT mini, and the
#     sweep tier -- a skeleton measured on the bench host would be a campaign
#     cell wearing a placeholder label;
#   * a live publish refuses a payload the exporter stamped skeleton;
#   * --skeleton implies --preview, and cannot be combined with a live target.
BENCH_HOST_FORBIDDEN = {"mini"}
FROZEN_CSV = HERE / "results" / "runs_skeleton_laptop.csv"


def _assert_skeleton_rows():
    """Every frozen row is a laptop sweep row, or nothing is published."""
    import csv
    if not FROZEN_CSV.exists():
        raise SystemExit(f"  --skeleton: no {FROZEN_CSV}; freeze the skeleton run first")
    rows = list(csv.DictReader(FROZEN_CSV.open()))
    if not rows:
        raise SystemExit("  --skeleton: the frozen set is empty")
    bad_host = [r for r in rows
                if not str(r.get("bench_host") or "").strip()
                or str(r.get("bench_host")).strip() in BENCH_HOST_FORBIDDEN]
    bad_tier = [r for r in rows if str(r.get("tier") or "") != "sweep"]
    if bad_host or bad_tier:
        def _where(r):
            return (f"{r.get('lane')}/{r.get('scale')}/{r.get('backend')} "
                    f"bench_host={r.get('bench_host')!r} tier={r.get('tier')!r}")
        print(f"  REFUSING a skeleton publish: {len(bad_host)} row(s) carry no "
              f"bench_host or name a bench host, {len(bad_tier)} row(s) are not "
              f"sweep tier.", file=sys.stderr)
        for r in (bad_host + bad_tier)[:10]:
            print(f"    {_where(r)}", file=sys.stderr)
        raise SystemExit(
            "  A skeleton is a laptop placeholder (DECISIONS #86). A row from "
            "the bench host, or a paper-tier row, is a campaign cell and does "
            "not belong on the preview route under a placeholder banner.")
    hosts = sorted({str(r.get("bench_host")) for r in rows})
    print(f"  skeleton rows: {len(rows)}, bench_host {hosts}, tier sweep")


def _refuse_skeleton_payload_on_live(exported):
    """A live publish never carries a placeholder cell."""
    import json
    payload = json.loads(exported.read_text(encoding="utf-8"))
    if payload.get("skeleton"):
        raise SystemExit(
            "  REFUSING a LIVE publish: the exported payload is stamped "
            "skeleton (DECISIONS #86), so its cells are laptop placeholders. "
            "Re-freeze from campaign rows, or publish with --skeleton to the "
            "preview route.")


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def step(n, title):
    print(f"\n[{n}] {title}")


def _rewrite_page_spec_inventory(exported: Path, spec: Path | None = None) -> None:
    """Regenerate PAGE-SPEC.md's "Published tables" block from the payload.

    The block was written by hand on 2026-09-11 and by the same evening a
    column had been renamed and a table added; a generated inventory that is
    only generated once is a typed number with extra steps. Runs on every
    publish, so the spec's table list is the payload's table list.
    """
    import json
    preview = spec is not None
    spec = spec or HERE / "PAGE-SPEC.md"
    if not preview and not spec.exists():
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
    if preview:
        # The live spec describes the live page; a preview keeps its own inventory.
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(block.replace("## Published tables", "## Preview tables", 1), encoding="utf-8")
        print(f"  {spec.name}: {len(payload['tables'])} tables")
        return
    text = spec.read_text(encoding="utf-8")
    m = re.search(r"^## Published tables.*?(?=^## |\Z)", text, flags=re.M | re.S)
    text = (text[:m.start()] + block + text[m.end():]) if m else (text.rstrip("\n") + "\n\n" + block)
    spec.write_text(text, encoding="utf-8")
    print(f"  PAGE-SPEC.md inventory: {len(payload['tables'])} tables")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=str(DEFAULT_SITE),
                    help=f"humem.ai checkout (default {DEFAULT_SITE})")
    ap.add_argument("--no-build", action="store_true",
                    help="skip the Next.js build; the build is what catches a "
                         "page referencing an asset this script did not write")
    ap.add_argument("--preview", action="store_true",
                    help="publish to /projects/arcadedb/next (its own payload, images, and "
                         "prose file; PAGE-SPEC untouched); the live page is never written. "
                         "On its own it is the October campaign: BENCH_INSTRUMENT=2026-10, "
                         "runs_paper_oct.csv, web_benchmarks_next.json (DECISIONS #84)")
    ap.add_argument("--skeleton", action="store_true",
                    help="publish the laptop micro-scale placeholder run to the preview "
                         "route (DECISIONS #86). Implies --preview. Refuses any row from "
                         "the bench host or at paper tier; stamps the payload and every "
                         "table's conditions as placeholders; waives FAIRNESS F1 and F3 "
                         "(both describe the bench host) and runs every other gate.")
    args = ap.parse_args()
    if args.skeleton:
        args.preview = True
        os.environ["BENCH_SKELETON"] = "1"
        # THE SKELETON IS AN OCTOBER RUN (BUGS F93). Every one of its 164 rows
        # is stamped `instrument: 2026-10`, because the placeholder sweep runs
        # the October lanes on the laptop -- so leaving the instrument unset
        # here put make_paper_tables in SEPTEMBER, where the first thing
        # load_canonical does is drop every row of the other campaign. All 164
        # went, the September-side campaign rows that happen to sit at a
        # skeleton scale stayed, and the freeze was rewritten from those:
        # 198 paper-tier rows over the 164 placeholders, twice on 2026-09-21.
        #
        # `if OCTOBER and not SKELETON` in make_paper_tables is the tell that
        # this was always the intent -- that clause has no meaning unless a
        # skeleton can be October, and until now it could not be.
        os.environ["BENCH_INSTRUMENT"] = "2026-10"
        print("  target: SKELETON (DECISIONS #86) -> preview route; placeholder numbers")
        print("  instrument: 2026-10; the skeleton's own rows carry it")
        _assert_skeleton_rows()
    elif args.preview:
        # THE PREVIEW ROUTE IS THE OCTOBER CAMPAIGN (DECISIONS #83, #84). Set
        # before anything is generated, because every step below inherits this
        # environment: make_paper_tables freezes October's rows to
        # runs_paper_oct.csv, export_web reads that freeze and writes
        # web_benchmarks_next.json, and the gates read the same two files.
        #
        # Without this line a preview publish regenerated from
        # runs_paper.csv -- September's freeze -- and published September's
        # numbers to October's route, gates and all, because every gate would
        # have agreed: they would all have been reading September.
        os.environ["BENCH_INSTRUMENT"] = "2026-10"
        print("  instrument: 2026-10 (DECISIONS #84); September's freeze and "
              "payload are not read or written")
    target_paths = TARGETS["preview" if args.preview else "live"]
    global PAGE_SOURCE, PAGE_DATA, PAGE_IMAGES, IMAGE_URL_RE
    PAGE_SOURCE, PAGE_DATA = target_paths["source"], target_paths["data"]
    PAGE_IMAGES, IMAGE_URL_RE = target_paths["images"], target_paths["image_re"]
    if args.preview:
        print("  target: PREVIEW (/projects/arcadedb/next); the live page is not touched")

    # 2026-09-11: no paper directory any more. The generators write under
    # results/generated by default; BENCH_PAPER_DIR overrides for a future
    # paper. The page is the only publication target.
    #
    # ONE DIRECTORY PER CAMPAIGN (make_paper_tables.GENERATED_NAME), resolved
    # here from the same two switches the steps above just set, so step 5
    # copies the figures THIS publish drew. Read after the --skeleton and
    # --preview handling above, never before it, or the preview route would be
    # given September's figures.
    _generated = ("generated_skeleton" if args.skeleton
                  else "generated_oct" if args.preview
                  else "generated")
    paper_dir = os.environ.get("BENCH_PAPER_DIR") or str(HERE / "results" / _generated)
    Path(paper_dir).mkdir(parents=True, exist_ok=True)
    figs = Path(paper_dir) / "figures"

    site = Path(args.site).resolve()
    # The gates read the page's prose out of this checkout too, and they used
    # to find it by assuming the two repositories are siblings. That is true of
    # a clone and false of a worktree, so page_check looked at a path that does
    # not exist and reported the prose as unchecked.
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
    if args.skeleton:
        # NOT RUN, rather than run and discarded (DECISIONS #86). Every figure
        # is a ratio against the best comparator or reads a pinned bench-host
        # artifact, so at one repetition on micro corpora there is nothing
        # honest to draw; the skeleton page references no figure and names the
        # summary figure as absent in its own banner. Skipped HERE and not
        # only inside the generator, because the generator imports matplotlib
        # at module scope and a guard underneath that import cannot run on a
        # machine that has no matplotlib, which is every machine that is not
        # the bench host.
        print("  figures: skipped for a skeleton publish; the page references none")
    else:
        run(py + [str(HERE / "make_paper_figures.py")], cwd=HERE.parents[1])

    step(2, "Export the page data")
    run(py + [str(HERE / "export_web.py")], cwd=HERE.parents[1])
    # export_web.OUT_NAME, in the same order of precedence. This path is what
    # step 4 copies to the site and what step 3's gates were told to read, so
    # it must name the file the exporter just wrote and not the one before it.
    exported = HERE / "results" / (
        "web_benchmarks_skeleton.json" if args.skeleton
        else "web_benchmarks_next.json" if args.preview
        else "web_benchmarks.json")
    if not args.preview:
        _refuse_skeleton_payload_on_live(exported)
    _rewrite_page_spec_inventory(exported, PREVIEW_INVENTORY if args.preview else None)

    step(3, "Gates: nothing is published until every gate agrees")
    for gate in GATES:
        extra = (["--preview"] if (args.preview and gate in
                 ("page_check", "version_consistency_check")) else [])
        proc = subprocess.run(py + [str(HERE / f"{gate}.py")] + extra,
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

    # EVERY TABLE THE PAGE ASKS FOR MUST EXIST IN THE PAYLOAD (BUGS F95). The
    # prose file names its tables by `tableId`, and the renderer shows nothing
    # at all for one the payload does not carry -- no error, no gap, just a
    # heading with nothing under it. On 2026-09-22 `l2` was filtered to a tier
    # holding none of its rows and the whole table stopped being emitted;
    # twelve became eleven in silence, and PAGE-SPEC's inventory agreed,
    # because that inventory is written FROM the payload and so cannot
    # disagree with it. The page's own prose can.
    _payload = json.loads(exported.read_text(encoding="utf-8"))
    _have = {t.get("id") for t in _payload.get("tables") or []}
    _absent = set((_payload.get("skeleton_absent_tables") or {}).keys())
    _wanted = re.findall(r'tableId:\s*"([A-Za-z0-9_]+)"',
                         (site / PAGE_SOURCE).read_text(encoding="utf-8"))
    _missing = [t for t in dict.fromkeys(_wanted) if t not in _have and t not in _absent]
    if _missing:
        print(f"  REFUSING: the page asks for {_missing} and the payload carries "
              f"{sorted(_have)}; a table the page names and the data lacks renders "
              f"as a heading with nothing under it", file=sys.stderr)
        return 1
    # AND THE OTHER DIRECTION, which is the one that bites at a landing. A
    # table the payload carries and the prose never names is generated,
    # gated, published and then not shown: the data is in the JSON and
    # invisible on the page. The October preview names neither `e4` nor
    # `pycost` today, so the first landing -- whose whole deliverable is e4 --
    # would have published it into a page with no section to render it.
    _unrendered = sorted(t for t in _have if t not in set(_wanted))
    if _unrendered:
        print(f"  REFUSING: the payload carries {_unrendered} and the page's prose "
              f"names no section for it; the table would be published and never "
              f"rendered. Add a benchmarkTable block for it, or stop building it.",
              file=sys.stderr)
        return 1
    print(f"  page asks for {len(set(_wanted))} table(s), payload carries {len(_have)}, "
          f"and the two agree")

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
        # Own dist directory (next.config.ts distDir), so the gate build never
        # replaces the .next a running dev server in the checkout serves from.
        run(["npm", "run", "build"], cwd=site, stdout=subprocess.DEVNULL,
            env=dict(os.environ, NEXT_DIST_DIR=".next-gate"))
        print("  build ok")

    step(7, "Review and commit, by hand, on purpose")
    subprocess.run(["git", "status", "--short"], cwd=site)
    print(f"\n  {len(wanted)} figure(s) published: {', '.join(sorted(wanted))}")
    print("  Read the diff before committing. A number moving is news; a "
          "number moving unnoticed is how a wrong one ships.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
