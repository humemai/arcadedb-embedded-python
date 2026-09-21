#!/usr/bin/env python3
"""Every LIST a document states must match the list the code derives.

`prose_check.py` closes the same loop for result NUMBERS: a figure in the page
or the paper must trace to a pinned claim. Nothing closed it for the STRUCTURAL
lists -- which gates run, which stages run and in what order -- and those drift
the same way and are read the same way, as fact.

The week of 2026-09-21 produced six instances of one shape, something written
once beside the thing it describes and never revisited when the thing changed:

  F76  every stage built a typed list of three images, so two arms ran against
       images nobody was rebuilding
  F77  a version gate's typed family spellings missed 23 of 191 live rows
  F76b the capability table's legend was a typed tuple of three kinds, so a
       fourth printed in the cells with nothing defining it
  --   my own STRICT_WORKLOADS, typed, drifted inside an hour
  F91  comparator_pins_check's backend map covers 14 of 69 backends
  F92  CAMPAIGN.md and HANDOFF.md both stated the stage chain in the wrong
       order, putting `qOI` -- the only producer of the e4 table, and therefore
       the first landing's only blocker -- four stages later than it runs

F92 is the one this file would have caught, and it is worth being concrete
about the cost: nobody would have published a wrong number, they would have
waited hours for a stage that was already next. A document that is wrong about
the schedule is wrong about the plan.

WHAT THIS DOES NOT DO. It does not check prose ABOUT a list -- "nine engines",
"twelve tables" -- because a count in a sentence is a number and prose_check's
argument applies: a checker that rewrites sentences produces fluent false ones.
It checks that the list itself, where a document spells one out, is the list the
code holds.

Usage:  python structure_check.py        # exit 1 on any drift
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def check_gates():
    """PAGE-SPEC.md names the gates; refresh_web_page.GATES runs them."""
    import refresh_web_page

    doc = _read("PAGE-SPEC.md")
    # the sentence that spells the list out: `a`, `b`, `c`, ... backticked
    m = re.search(r"`refresh_web_page\.GATES` is ((?:`[a-z_]+`(?:, | and )?)+)", doc)
    if not m:
        return ["PAGE-SPEC.md no longer spells out `refresh_web_page.GATES`; either the "
                "sentence moved or this check has gone blind, and a blind check is worse "
                "than none"]
    stated = re.findall(r"`([a-z_]+)`", m.group(1))
    actual = list(refresh_web_page.GATES)
    if stated != actual:
        return [f"PAGE-SPEC.md names gates {stated}; refresh_web_page.GATES runs {actual}"]
    return []


def check_stage_chain():
    """CAMPAIGN.md draws the chain; make_october_stages.STAGES holds it.

    The doc legitimately names stages the generator does not -- `qOAR` was made
    by hand -- so the test is not equality. Every generated stage must appear,
    and the generated stages must appear in the generator's relative order. That
    tolerates a hand-made stage anywhere and still catches F92 exactly: `qOI`
    out of place, and `qOA4` missing altogether.
    """
    import make_october_stages

    doc = _read("CAMPAIGN.md")
    # ANCHOR ON THE OCTOBER HEADING. The first version searched the whole file
    # and matched SEPTEMBER's chain, which is drawn identically earlier in the
    # document, then reported all fifteen October stages missing. A checker that
    # reads the wrong list is worse than one that reads none: it is confidently
    # wrong about the thing it exists to be right about.
    anchor = doc.find("**The October chain on mini")
    if anchor < 0:
        return ["CAMPAIGN.md no longer has a section headed \"The October chain on "
                "mini\"; either it moved or this check has gone blind"]
    m = re.search(r"((?:`q[A-Z0-9]+` -> )+`q[A-Z0-9]+`\.)", doc[anchor:])
    if not m:
        return ["CAMPAIGN.md's October section no longer draws a `qX` -> `qY` chain; "
                "either it moved or this check has gone blind"]
    drawn = re.findall(r"`(q[A-Z0-9]+)`", m.group(1))
    generated = [s[0] for s in make_october_stages.STAGES]

    bad = []
    missing = [s for s in generated if s not in drawn]
    if missing:
        bad.append(f"CAMPAIGN.md's chain omits {missing}, which make_october_stages "
                   f"generates and mini therefore runs")
    # relative order of the stages the doc and the generator share
    shared = [s for s in drawn if s in generated]
    expected = [s for s in generated if s in shared]
    if shared != expected:
        first = next((a for a, b in zip(shared, expected) if a != b), None)
        bad.append(f"CAMPAIGN.md's chain orders the generated stages {shared}; "
                   f"make_october_stages.STAGES orders them {expected}"
                   + (f" -- they first differ at {first}" if first else ""))
    return bad


CHECKS = (("gates", check_gates), ("stage chain", check_stage_chain))


def main() -> int:
    bad = []
    for name, fn in CHECKS:
        try:
            found = fn()
        except Exception as exc:  # a check that cannot run has not passed
            found = [f"the {name} check could not run: {exc.__class__.__name__}: {exc}"]
        print(f"  {name:<12} {'ok' if not found else 'DRIFTED'}")
        bad.extend(found)

    for line in bad:
        print(f"  DRIFT    {line}")
    print(f"\n{len(bad)} document(s) stating a list the code does not hold")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
