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
from pathlib import Path
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


def check_citations():
    """Every DECISIONS #N and BUGS F-number cited here exists over there.

    The code and the docs cite the record constantly -- "(DECISIONS #90)",
    "BUGS F98" -- and a citation to something that was never written is worse
    than none: it reads as though a decision was taken and recorded when it
    was not. Found by writing FAIRNESS F14 against "#112" and then noticing,
    four references later, that #112 did not exist.

    The record lives in a SEPARATE repository (.notes, deliberately without a
    remote), so this skips rather than fails when it is not checked out: a
    developer with only the public tree cannot be asked to verify a file they
    do not have.
    """
    notes = Path(HERE).parent.parent / ".notes" / "bench"
    if not notes.is_dir():
        print("  citations    skipped (.notes not checked out)")
        return []
    known = {}
    for name, pat in (("DECISIONS", r"^\| (#\d+[a-z]?) \|"), ("BUGS", r"^\| (F\d+[a-z]?) \|")):
        f = notes / f"{name}.md"
        known[name] = set(re.findall(pat, f.read_text(encoding="utf-8"), re.M)) if f.exists() else set()
    if not known["DECISIONS"] or not known["BUGS"]:
        print("  citations    skipped (the record's index tables did not parse)")
        return []
    cited_d, cited_b = set(), set()
    for f in sorted(Path(HERE).glob("*.py")) + sorted(Path(HERE).glob("*.md")):
        if f.name == "structure_check.py":
            continue                      # this file names the example that motivated it
        text = f.read_text(encoding="utf-8", errors="ignore")
        cited_d |= {f"#{n}" for n in re.findall(r"DECISIONS?[^\n]{0,12}?#(\d+[a-z]?)", text)}
        cited_b |= {f"F{n}" for n in re.findall(r"BUGS?[^\n]{0,12}?F(\d+[a-z]?)", text)}
    # A LETTERED ID IS A SUB-REFERENCE, NOT A MISSING ENTRY. F63's entry
    # describes four defects and labels them a. to d., so `BUGS F63c` points
    # at something a reader can find even though the index table lists only
    # F63. Resolve a lettered id against its base number; an id whose BASE is
    # absent is still a finding, which is how F73 was caught -- cited by
    # CAMPAIGN.md, fixed by a stage, and never written.
    def _resolves(cid, have):
        return cid in have or (cid[-1].isalpha() and cid[:-1] in have)

    bad = []
    for label, cited, have in (("DECISIONS", cited_d, known["DECISIONS"]),
                               ("BUGS", cited_b, known["BUGS"])):
        missing = sorted((c for c in cited if not _resolves(c, have)),
                         key=lambda x: (len(x), x))
        if missing:
            bad.append(f"cites {label} {missing} and {label}.md has no such entry; a citation "
                       f"to something never written reads as a decision that was taken")
    if not bad:
        # main() prints the ok/DRIFTED line for every check; this adds the
        # counts under it rather than printing a second verdict.
        print(f"               {len(cited_d)} decision(s) and {len(cited_b)} bug(s) cited, "
              f"all present")
    return bad


def check_ingest_sentences():
    """A fact written twice must not lose an engine on one of the copies.

    The ingest path of each arm is stated in TWO places: `INGEST_NOTES` for
    the September page and `OCT_PROSE[...]["ingest"]` for the October one.
    Two copies of one fact drift, and on 2026-09-22 they had: DuckPGQ joined
    the graph lane in September's extension, September's sentence was updated
    and October's was not, so the October graph table named ten of its eleven
    arms -- and October's is the one that page renders.

    The rule is not "the two must match". October legitimately names engines
    September never had, because October's tables have more arms. What must
    not happen is an engine that is ON the October table, named in the
    September sentence, and missing from the October one: that is a copy which
    was updated once and not twice.

    Checked against `runner.LANES` rather than against the other sentence, so
    an engine genuinely dropped in October does not read as drift.
    """
    import export_web as E
    import runner as R
    import re

    ENGINES = ("ArcadeDB", "Neo4j", "Memgraph", "FalkorDB", "LadybugDB", "DuckPGQ",
               "DuckDB", "ArangoDB", "MongoDB", "SurrealDB", "QuestDB", "SQLite",
               "TimescaleDB", "Qdrant", "Milvus", "Elasticsearch", "PostgreSQL",
               "Chroma", "LanceDB")

    def named(text):
        return {e for e in ENGINES if re.search(rf"\b{e}\b", text)}

    bad = []
    for tid in sorted(set(E.INGEST_NOTES) | set(E.OCT_PROSE)):
        oct_ = (E.OCT_PROSE.get(tid) or {}).get("ingest")
        oct_ = oct_[0] if isinstance(oct_, tuple) else oct_
        lane = (E._TABLE_LANE.get(tid) or (None,))[0]
        spec = R.LANES.get(lane) if lane else None
        if not (oct_ and spec):
            continue
        # THE LANE'S ROSTER, NOT THE OTHER SENTENCE. Comparing the two copies
        # only finds an arm that one of them happens to name; the roster finds
        # an arm nobody wrote down, and finds it on lanes that have not run
        # yet, which is where it is still cheap to fix. runner.LANES is what
        # the runner actually executes, so it cannot disagree with what ran.
        arms = set()
        for be in spec[1]:
            arms |= named(E.display_name(be) if be in E.DISPLAY_NAMES else be)
        missing = sorted(arms - named(oct_))
        if missing:
            bad.append(f"{tid}: the October ingest sentence does not name {missing}, "
                       f"which lane {lane} runs -- a reader is told how every other "
                       f"arm on that table was loaded and not that one")
        # And the older copy must not be the only one that knows an arm: that
        # is the DuckPGQ case, one copy updated and the other not.
        sep = E.INGEST_NOTES.get(tid)
        if sep:
            lost = sorted((named(sep) - named(oct_)) & arms)
            if lost and lost != missing:
                bad.append(f"{tid}: {lost} named in the September ingest sentence "
                           f"and missing from the October one")
    return bad


CHECKS = (("gates", check_gates), ("stage chain", check_stage_chain),
          ("ingest prose", check_ingest_sentences),
          ("citations", check_citations))


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
