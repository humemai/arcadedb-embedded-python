#!/usr/bin/env python3
"""Did the engines we compare actually answer the same question? (DECISIONS #88)

fairness_check asks whether the row next to this one was given the same
resources and the same treatment. This asks the question underneath it: was it
given the same QUESTION, and did it come back with the same ANSWER?

Nothing asked that until 2026-09-14. The harness checked recall against ground
truth on the vector lanes and torn state in the cross-model trial; every other
lane recorded latency, throughput, and for a few queries a row count. An
adapter that dropped a filter, a group, or a join condition would have printed
a lead, not a bug, and the September rows are built on those adapters.

So every timed query whose answer is deterministic now records a canonical
digest (bench_common.result_digest) computed OUTSIDE its timed section from the
object the timed call returned, plus a short readable sample. This gate groups
those digests by lane, scale, workload and query, compares them across
backends, and refuses the publish when two engines disagree.

    python3 equivalence_check.py                       # the canonical frozen set
    python3 equivalence_check.py --rows results/runs_smoke_oct.jsonl
    python3 equivalence_check.py --rows results/runs_skeleton_laptop.csv

Three rules this file exists to keep, each of which is a way to pass while
proving nothing:

  * A GROUP WITH ONE ENGINE IS UNCHECKED, NOT PASSED. One digest agrees with
    itself. Those groups are counted and listed under their own heading, never
    folded into the ok count.
  * SILENCE IS NOT AGREEMENT. Under the 2026-10 instrument, a backend that
    records no digest for a query its neighbours do record fails: either it
    answered and did not say what it answered, or it never ran the query.
    An engine that CANNOT ask the question records
    "unexpressible: <reason>" and is listed, with its reason, as a declared
    absence.
  * AN ENGINE MUST AGREE WITH ITSELF. Repetitions of one cell are the same
    database asked the same question, and since DECISIONS #90 so are its two
    durability classes: a strict commit changes when a write becomes durable,
    not what the answer is. Two digests from one backend within a group mean
    the digest is not a property of the cell, and that is its own failure
    class.

Exit status is 1 if any group disagrees, so it can gate a publish. It is
wired into refresh_web_page.py's GATES.
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = os.path.join(HERE, "results")

import bench_common  # noqa: E402
import test_result_digest  # noqa: E402

DIGEST_RE = re.compile(r"^res_(.+)_digest$")
# The instrument that is required to carry digests. Rows from the September
# campaign predate #88 and are reported as skipped, by count, rather than
# failed: the decision is that October does not start without them, not that
# history is retroactively broken.
REQUIRED_INSTRUMENT = "2026-10"
ARCADE = "arcadedb"

# WHICH LANES ARE CHECKED BY SOMETHING ELSE, and why, so that "this lane
# records no digest" is a declared fact rather than an omission nobody
# noticed. DECISIONS #88: "The vector lanes keep recall against ground truth,
# which is the stronger check for an approximate index; the cross-model lane
# keeps its torn-state comparison." Any lane NOT named here whose 2026-10 rows
# carry no digest at all fails E6 -- which is the case a per-query comparison
# cannot catch, because with nothing recorded there is nothing to compare.
LANES_CHECKED_OTHERWISE = {
    "l3d": "approximate index: recall against exact ground truth, per row",
    "l3s": "approximate index: recall against exact ground truth, per row",
    ("e2", "atomicity"): "checked by the torn-state comparison, not by a digest",
}

# TWO ARMS THAT ARE NOT LIKE FOR LIKE, named with the reason rather than left
# to fail every publish. The lifecycle lane's embedded and served halves are
# two different scripts running two different mode sets -- the embedded one
# also runs the drop and stale-reopen cycles -- so their databases hold
# different numbers of records by construction and their reads answer
# different questions. The digest is still worth recording per arm (it catches
# an arm disagreeing with itself across repetitions, which E2 reports), but
# comparing the two arms to each other would be comparing two workloads.
# AN ANSWER THAT IS WRONG, NAMED RATHER THAN EXCUSED.
#
# NOT_COMPARABLE below is for groups that ask different questions. This is the
# other case: one engine answers the SAME question differently from every other
# engine, the disagreement has been reproduced and understood, and the cell it
# affects is WITHHELD FROM THE PAGE (export_web.WITHHELD_CELLS) instead of
# being published beside answers it does not match. The gate keeps printing it,
# as KNOWN rather than FAIL, because a publish that cannot proceed until an
# upstream fix lands is a publish that will be forced through by deleting the
# check.
#
# Each entry names the engine, what it returns instead, and what is being done
# about it. Remove the entry when the engine is re-pinned with the fix, which
# re-arms the gate for that query.
KNOWN_DISAGREEMENTS = {
    ("l4", "q_groupby"): {
        "arcadedb_ts_native_server": (
            "the served SQL path returns a CONSTANT bucket for the "
            "function-derived grouping key when a second grouping key is "
            "present: 100 hosts x 1 bucket where the embedded arm on the same "
            "build, and DuckDB, SQLite, MongoDB, QuestDB and TimescaleDB, all "
            "return 100 x 12. The single-key form of the same expression "
            "(q_global, GROUP BY the bucket alone) agrees exactly between the "
            "two ArcadeDB arms, so it is the two-key group-by that is wrong "
            "and not the bucket function. The cell is withheld from the page "
            "rather than published as a latency for a different answer"),
    },
}

NOT_COMPARABLE = {
    ("lifecycle", "lifecycle_read"):
        "the embedded and served lifecycle arms run different mode sets, so "
        "their post-state record counts differ by construction",
}


def _is_arcade(backend):
    return ARCADE in str(backend)


def newest_per_cell(rows):
    """One row per run_id, the newest by ts_utc.

    A results file is append-only, so a re-run of a fixed cell leaves the old
    row in place beside the new one. Without this the gate reads the two as one
    backend giving two answers and fails E2 on a defect that has been fixed --
    which is exactly what it did the first time a cell was re-run here. The
    canonical set applies the same rule; this is it for a raw file.
    """
    best = {}
    for r in rows:
        rid = r.get("run_id")
        if not rid:
            best[id(r)] = r
            continue
        if rid not in best or str(r.get("ts_utc")) > str(best[rid].get("ts_utc")):
            best[rid] = r
    return list(best.values())


def load_rows(path=None):
    """Rows to check: a named file, or the canonical frozen set the tables use."""
    if not path:
        import make_paper_tables as M
        return M.load_canonical(), "canonical frozen set"
    p = path if os.path.isabs(path) else os.path.join(HERE, path)
    if p.endswith(".csv"):
        with open(p) as fh:
            return list(csv.DictReader(fh)), os.path.relpath(p, HERE)
    rows = []
    with open(p) as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    rows = newest_per_cell(rows)
    return rows, os.path.relpath(p, HERE)


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def collect(rows):
    """(groups, skipped, queries) where a group is one question at one size.

    groups[(lane, scale, workload, query)][backend] = {digest: [(rep, sample, n)]}
    """
    groups = collections.defaultdict(lambda: collections.defaultdict(dict))
    seen_backends = collections.defaultdict(set)
    skipped = collections.Counter()
    silent_lanes = collections.defaultdict(set)   # lane -> backends with no digest at all
    for r in rows:
        if str(r.get("rc") or "0") not in ("0", "0.0"):
            skipped["the cell failed (rc != 0)"] += 1
            continue
        if str(r.get("instrument") or "") != REQUIRED_INSTRUMENT:
            skipped[f"instrument {r.get('instrument') or '(none)'}, which predates #88"] += 1
            continue
        key0 = (r.get("lane"), str(r.get("scale")), r.get("workload"))
        seen_backends[key0].add(r.get("backend"))
        got = 0
        for field, val in list(r.items()):
            m = DIGEST_RE.match(str(field))
            if not m or _blank(val):
                continue
            got += 1
            q = m.group(1)
            entry = groups[key0 + (q,)][r.get("backend")]
            entry.setdefault(str(val), []).append(
                (r.get("rep"), str(r.get(f"res_{q}_sample") or ""), r.get(f"res_{q}_n"),
                 r.get("durability_class") or "relaxed"))
        if not got:
            silent_lanes[(r.get("lane"), r.get("workload"))].add(r.get("backend"))
    return groups, skipped, seen_backends, silent_lanes


def report_silent_lanes(silent_lanes, out=print):
    """E6: a lane whose rows carry no digest at all, and is not declared.

    The per-query comparison cannot catch this: with nothing recorded there is
    nothing to compare, and the gate would print "all agreeing" over a lane
    that checked nothing.
    """
    bad = 0

    def _decl(key):
        lane, workload = key
        return LANES_CHECKED_OTHERWISE.get((lane, workload)) or LANES_CHECKED_OTHERWISE.get(lane)

    declared = {k: bes for k, bes in silent_lanes.items() if _decl(k)}
    missing = {k: bes for k, bes in silent_lanes.items() if not _decl(k)}
    out("\n=== E6: every lane records a digest, or is declared checked otherwise ===")
    for k, bes in sorted(declared.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        out(f"  declared {k[0]:8} {str(k[1]):10} {_decl(k)} ({len(bes)} backend(s))")
    for k, bes in sorted(missing.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        bad += 1
        out(f"  FAIL {k[0]} {k[1]}: {len(bes)} backend(s) recorded no result digest "
            f"on any query: {', '.join(sorted(str(b) for b in bes))}")
    if not missing and not declared:
        out("  ok: every 2026-10 row carries at least one digest")
    elif not missing:
        out("  ok: every other lane carries digests")
    return bad


def _fmt_sample(text, width=150):
    t = (text or "").replace("\n", " ")
    return t if len(t) <= width else t[:width - 1] + "…"


def report(groups, seen_backends, out=print):
    agreed = disagreed = unchecked = 0
    failures = []          # (arcade_involved, key, lines)
    absences = []          # (key, backend, reason)
    unstable = []          # (key, backend, digests)
    silent = []            # (key, backend) -- ran the cell, recorded no digest
    not_comparable = []    # (key, reason, backends) -- declared not like for like
    known_disagreements = []  # (key, backends, reasons) -- wrong, named, withheld

    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        lane, scale, workload, query = key
        per_backend = groups[key]
        # Declared absences first: they are not disagreements, but they are
        # the thing #88 says must never be silent, so they are always printed.
        real = {}
        for be, digests in per_backend.items():
            expressed = {d: v for d, v in digests.items() if not bench_common.is_unexpressible(d)}
            for d in digests:
                if bench_common.is_unexpressible(d):
                    absences.append((key, be, d[len(bench_common.UNEXPRESSIBLE_PREFIX):]))
            if len(expressed) > 1:
                # WHERE THE TWO ANSWERS CAME FROM. Since #90 a backend appears
                # in a group twice, once per durability class, and a strict
                # commit must not change the ANSWER, only its latency. Naming
                # the reps and classes behind each digest is what turns "this
                # engine disagrees with itself" into something actionable.
                where = {d: sorted({f"{o[3]}/r{o[0]}" for o in occ})
                         for d, occ in expressed.items()}
                unstable.append((key, be, where))
            if expressed:
                # The newest rep wins the display; the instability is reported
                # separately above rather than hidden by this choice.
                d = sorted(expressed)[0]
                real[be] = (d, expressed[d][0][1], expressed[d][0][2])

        # SILENCE IS NOT AGREEMENT. A backend that ran this lane/scale/workload
        # and recorded neither a digest nor a declared absence for a query its
        # neighbours answered has not been checked and does not say why.
        for be in sorted(seen_backends.get((lane, scale, workload), set())):
            if be not in per_backend:
                silent.append((key, be))

        if len(real) < 2:
            unchecked += 1
            continue
        by_digest = collections.defaultdict(list)
        for be, (d, _s, _n) in real.items():
            by_digest[d].append(be)
        if len(by_digest) == 1:
            agreed += 1
            continue
        why = NOT_COMPARABLE.get((lane, query))
        if why:
            not_comparable.append((key, why, sorted(real)))
            continue
        # A DISAGREEMENT THAT IS ALREADY UNDERSTOOD, and whose cell the page
        # withholds. Counted as known only when the engines that disagree with
        # the rest are EXACTLY the ones the entry names: a new engine drifting
        # onto the wrong side must still fail.
        _known = KNOWN_DISAGREEMENTS.get((lane, query))
        if _known:
            _majority = max(by_digest.values(), key=len)
            _odd = sorted(b for bes in by_digest.values() if bes is not _majority
                          for b in bes)
            if _odd and set(_odd) <= set(_known):
                known_disagreements.append((key, _odd, _known))
                continue
        disagreed += 1
        # WHICH SIDE IS ARCADEDB ON, and is it alone there? The first version
        # printed "ArcadeDB disagrees with the other engines" whenever any
        # ArcadeDB arm was in a disagreeing group, which labelled a LadybugDB
        # outlier as an ArcadeDB failure. Alone means: every digest an ArcadeDB
        # arm produced is held by ArcadeDB arms only.
        arcade_side = {d for d, bes in by_digest.items() if any(_is_arcade(b) for b in bes)}
        others = set(by_digest) - arcade_side
        arcade_involved = bool(arcade_side and others)
        arcade_alone = arcade_involved and all(
            all(_is_arcade(b) for b in by_digest[d]) for d in arcade_side)
        lines = [f"FAIL {lane} {scale} {workload} :: {query} -- "
                 f"{len(by_digest)} different answers from {len(real)} engines"]
        for d in sorted(by_digest, key=lambda x: (not any(_is_arcade(b) for b in by_digest[x]), x)):
            bes = sorted(by_digest[d])
            n = real[bes[0]][2]
            lines.append(f"    {d}  n={n}  {', '.join(bes)}")
            lines.append(f"        {_fmt_sample(real[bes[0]][1])}")
        failures.append((arcade_alone, arcade_involved, key, lines))

    # ARCADEDB AGAINST EVERYONE, FIRST. If our own engine is the odd one out,
    # that is the finding that decides whether a published number is wrong,
    # and it must not be read after forty comparator rows.
    out("=== E1: equivalent queries, equivalent answers (DECISIONS #88) ===")
    if failures:
        for alone, involved, _key, lines in sorted(failures, key=lambda f: (not f[0], not f[1], f[2])):
            if alone:
                out("  [ArcadeDB is the odd one out]")
            elif involved:
                out("  [ArcadeDB is on one side of this; the outlier is another engine]")
            for line in lines:
                out("  " + line)
            out("")
    elif agreed:
        out(f"  ok: {agreed} group(s) where two or more engines answered, all agreeing")
    else:
        out("  no group had two engines answering the same question; see E5 and E6")

    if unstable:
        out("\n=== E2: an engine must agree with itself across repetitions ===")
        for key, be, where in unstable:
            out(f"  FAIL {key[0]} {key[1]} {key[2]} :: {key[3]} -- {be} gave "
                f"{len(where)} different answers across its own repetitions and "
                f"durability classes:")
            for d, tags in sorted(where.items()):
                out(f"         {d}  {', '.join(tags)}")
            out("         A strict commit changes when a write is durable, not "
                "what the answer is (DECISIONS #90).")

    if silent:
        out("\n=== E3: a backend that recorded no digest for a query its neighbours answered ===")
        by_be = collections.Counter((k[0], k[1], k[2], be) for k, be in silent)
        for (lane, scale, workload, be), n in sorted(by_be.items()):
            qs = sorted(k[3] for k, b in silent if b == be and k[:3] == (lane, scale, workload))
            out(f"  FAIL {lane} {scale} {workload} -- {be} recorded no digest for "
                f"{n} query/queries: {', '.join(qs)}")
        out("  Silence is indistinguishable from agreement. An engine that")
        out("  cannot ask the question records unexpressible:<reason>.")

    if absences:
        out("\n=== E4: declared absences (an engine that cannot ask the question) ===")
        seen = set()
        for key, be, reason in sorted(absences, key=lambda a: (str(a[1]), str(a[0]))):
            tag = (key[0], key[2], key[3], be, reason)
            if tag in seen:
                continue
            seen.add(tag)
            out(f"  {key[0]:8} {key[2]:10} {key[3]:24} {be:32} {reason}")

    if known_disagreements:
        out("\n=== E8: KNOWN disagreements: one engine is wrong, and its cell is "
            "withheld from the page ===")
        for key, odd, reasons in known_disagreements:
            for be in odd:
                out(f"  KNOWN {key[0]} {key[1]} {key[2]} :: {key[3]} -- {be}: "
                    f"{reasons[be]}.")
        out("  Printed on every run, and counted as a failure again the moment "
            "any OTHER engine joins that side.")

    if not_comparable:
        out("\n=== E7: groups declared NOT COMPARABLE, with the reason ===")
        for key, why, bes in not_comparable:
            out(f"  {key[0]} {key[1]} {key[2]} :: {key[3]} -- {why}")
            out(f"         ({', '.join(bes)}; each arm's own digest is still checked "
                f"across its repetitions by E2)")

    if unchecked:
        out(f"\n=== E5: {unchecked} group(s) UNCHECKED: only one engine answered ===")
        singles = collections.Counter()
        for key in sorted(groups):
            real = [be for be, ds in groups[key].items()
                    if any(not bench_common.is_unexpressible(d) for d in ds)]
            if len(real) < 2:
                singles[(key[0], key[1], key[2])] += 1
        for (lane, scale, workload), n in sorted(singles.items()):
            out(f"  {lane:8} {str(scale):8} {workload:10} {n} query/queries, one engine")
        out("  One digest agrees with itself. These are not passes.")

    bad = len(failures) + len(unstable) + len(silent)
    return bad, agreed, disagreed, unchecked


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", default="",
                    help="a results .jsonl or .csv to check instead of the canonical set")
    ap.add_argument("--no-selftest", action="store_true",
                    help="skip the result_digest unit tests (they are the gate's own instrument)")
    args = ap.parse_args()

    if not args.no_selftest:
        print("=== E0: the digest's own unit tests ===")
        if test_result_digest.main() != 0:
            print("\nrefusing to compare anything: result_digest is broken, so every")
            print("digest on every row was produced by an instrument that fails its")
            print("own tests.")
            return 2

    try:
        rows, where = load_rows(args.rows or None)
    except Exception as e:  # noqa: BLE001
        print(f"cannot load rows: {e}")
        return 2
    print(f"\nrows: {len(rows)} from {where}")

    groups, skipped, seen, silent_lanes = collect(rows)
    if skipped:
        for reason, n in sorted(skipped.items()):
            print(f"  skipped: {n} row(s), {reason}")
    if not groups and not silent_lanes:
        print("\n=== E1: equivalent queries, equivalent answers (DECISIONS #88) ===")
        print("  no 2026-10 rows at all; nothing to check yet")
        return 0

    bad, agreed, _dis, unchecked = report(groups, seen)
    bad += report_silent_lanes(silent_lanes)
    print(f"\n{bad} equivalence failure(s); {agreed} group(s) checked and agreeing, "
          f"{unchecked} unchecked")
    if bad:
        print("A benchmark that never checks the answer measures how fast an")
        print("engine can be wrong. See DECISIONS #88.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
