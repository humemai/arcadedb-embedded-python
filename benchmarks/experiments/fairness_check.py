#!/usr/bin/env python3
"""Check that compared systems were actually given the same thing.

claims_check verifies a number against its own artifact. provenance_check
verifies which engine produced it. Neither asks the question that found three
defects in one afternoon on 2026-07-31: was the row NEXT TO IT given the same
resources and the same treatment?

Every number involved was correct about its own run. That is precisely why
nothing caught them:

  * T5 dense, ArcadeDB got one build and five timed passes with the table
    using passes 2-5, while every comparator got five builds and one pass
    each. Worth 4.0-6.1x.
  * T5 dense, the DEEP-10M envelope was raised from 28g/16g to 36g/24g on
    2026-07-20 and only ArcadeDB was re-measured under it. Worth 29% more
    container memory at the scale where memory decides what stays cached.
  * T5 time series, ArcadeDB's probe took a 30 s settle that no comparator
    was given. Worth 2.23x one way and 2.5x the other.

All three favoured us. The contract they violate is written down in
FAIRNESS.md; this file enforces the parts a machine can.

    python3 fairness_check.py

Exit status is 1 if any invariant fails, so it can gate a regeneration.
"""
import collections
import statistics
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FULL_CPUSET = "0-11"
# Fallback only. Every served row records its own mem_split; this is for the
# handful written before that field existed. Must match runner.py's
# SERVER_MEM_FRACTION, which is the value the containers were actually built
# with -- a mismatch here would silently misreport the envelope rather than
# fail, which is the failure mode this whole module exists to prevent.
SERVER_MEM_FRACTION_DEFAULT = 0.75

# Envelope deliberately not matched, with the reason. An entry here is a
# disclosed override; anything else that differs is a defect. Keyed by
# (lane, scale) -> {backend_substring: why}.
# EMPTY ON PURPOSE, and that is the finding. The one entry here recorded that
# DEEP-10M's int8 arm ran a 16 GiB heap against 24 GiB elsewhere, "and the row
# label names the heap". Both halves stopped being true: int8 was re-measured
# at 24 GiB like every other arm, and T5's label is "ArcadeDB (emb, int8)"
# with no heap in it. A disclosure that outlives the thing it discloses is
# worse than none, because it tells a reviewer to expect an asymmetry that is
# not there and invites them to distrust the rest.
DISCLOSED = {}


def _canonical():
    sys.path.insert(0, HERE)
    import make_paper_tables as M
    return M.load_canonical()


def _dense_rows():
    """The dense cells T5 actually prints, from the multipass artifacts.

    Each file is one build followed by five passes, so pass 0 carries the run
    conditions for the whole cell. Only pass 0 is taken: five passes over one
    build are one cell's worth of envelope, not five.
    """
    out = []
    # dense_mp5_2681: five INDEPENDENT builds per arm, so pass 0 of each file
    # is one cell's conditions and there are five cells per arm, not one. The
    # old directory held a single build per arm and needed a "_build" filter to
    # skip the two ad-hoc reproducibility extras; here every file is a first
    # class build and nothing is skipped.
    for fp in sorted(glob.glob(os.path.join(RESULTS, "dense_mp5_2681",
                                            "mp_*_b*.json"))):
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        p0 = d[0] if isinstance(d, list) and d else d
        if not isinstance(p0, dict) or not p0.get("backend"):
            continue
        r = dict(p0)
        r["lane"] = "l3d"        # the artifacts say l3d_mp; the LANE is l3d
        r["scale"] = "deep10m"
        # Served arms record the client container's cap; the split is the
        # lane's, not the row's, so name it here rather than guess later.
        if r.get("backend") in ("arcadedb_dense_server", "qdrant_dense",
                                "milvus_dense"):
            r.setdefault("role", "client")
            r.setdefault("mem_split", "0.75")
        out.append(r)
    return out


def check_cpuset(rows):
    """F1/F2: every published cell on the full cpuset, i.e. serial."""
    print("=== F1/F2: full cpuset, serial tier ===")
    bad = [r for r in rows
           if str(r.get("cpuset")) not in (FULL_CPUSET, "None")]
    seen = collections.Counter(str(r.get("cpuset")) for r in rows)
    print(f"  cpuset distribution across {len(rows)} canonical rows: {dict(seen)}")
    if bad:
        print(f"  FAIL {len(bad)} row(s) on a PARTIAL cpuset, i.e. measured as a")
        print("       parallel sweep worker and not eligible for a table:")
        for r in bad[:10]:
            print(f"         {r.get('lane')} {r.get('scale')} {r.get('backend')} "
                  f"cpuset={r.get('cpuset')}")
        return len(bad)
    print("  ok: no published row came from a parallel shard")
    return 0


def _gib(s):
    """'36g' -> 36.0. None/unparseable -> None."""
    if s is None:
        return None
    t = str(s).strip().lower().rstrip("b")
    try:
        if t.endswith("g"):
            return float(t[:-1])
        if t.endswith("m"):
            return float(t[:-1]) / 1024.0
        return float(t)
    except ValueError:
        return None


def _is_jvm(backend):
    """Does this backend run on a JVM, and therefore have a heap worth checking.

    Mirrors runner.JVM_BACKENDS. Kept as a substring match on the name so that
    adding a JVM comparator without listing it shows up as an unchecked heap
    rather than as an engine that legitimately has none.
    """
    return any(t in str(backend) for t in ("arcadedb", "arcade", "neo4j",
                                           "elasticsearch", "questdb"))


def _total_envelope(r):
    """The envelope the CELL got, normalised across topologies.

    F3 says a served backend gets the envelope SPLIT, not doubled:
    server = 0.75 * total, client = total - server. So a client container
    legitimately shows a quarter of what an embedded container shows, and
    comparing the two raw numbers reports a violation that is really the rule
    being followed.

    That is what this check did. It called five tiers FAIL because
    arcadedb_sparse_server recorded mem_cap=4g against an embedded 16g, which
    is 16 * 0.25 exactly. A fairness gate that fails on compliance is worse
    than no gate: it trains you to skim past its output, and a real violation
    then sits in the same list as the noise.

    Rows are not uniform about which number they store. A row with
    role='client' recorded ITS OWN container's cap; others recorded the total.
    mem_split says what fraction the server side took, so the total is
    recoverable either way.
    """
    # PREFER WHAT WAS OBSERVED. runner.py now reads the server container's real
    # cpuset, cap and -Xmx from the daemon and stores them as server_*, so a
    # served cell no longer has to be reconstructed from the split at all: the
    # envelope is server + client, both measured. Rows written before that
    # still fall back to the arithmetic below.
    srv_cap, srv_heap = _gib(r.get("server_mem_cap")), r.get("server_heap")
    if srv_cap is not None:
        # DERIVE THE TOTAL FROM THE SERVER SIDE ALONE, never by addition.
        # Adding mem_cap was wrong and failed five compliant tiers: runner.py
        # sets mem_cap = MEM_BY_SCALE[scale], the TOTAL, on every row, so
        # server + total reported 1.75x the envelope and l1/medium read 56g
        # against an embedded 32g. The rows were correct; this was not.
        #
        # It hid because the bug and its trigger arrived separately: preferring
        # the observed fields landed before any row carried server_mem_cap, so
        # the branch was dead until the repair chain produced the first ones.
        #
        # Addition cannot work anyway, because BOTH row shapes are in the data
        # and neither is detectable from mem_cap by itself:
        #     medium  mem_cap 32g, srv 24g   total-shaped   (runner.py:489)
        #     medium  mem_cap  8g, srv 24g   client-shaped  (run_conditions,
        #                                    reading the client's own cgroup)
        # The server's share is a known fraction of the envelope, so the total
        # is srv_cap / split -- 32g from both shapes above, no classification
        # required. This function's own docstring says a gate that fails on
        # compliance is worse than no gate; that is what it had become.
        # "full+client" means the server container got the WHOLE tier cap and
        # the driver got its own budget on top, so srv_cap already IS the
        # envelope and dividing would inflate it. Handled explicitly because
        # the fallback below silently turns any unparseable split into 0.75,
        # which for these rows reports 1.33x the true envelope and would have
        # failed compliant cells across the whole re-campaign.
        #
        # Found by PROTOCOL.md, which was assembled from the code the same day
        # the runner changed and flagged this line as stale before any row
        # under the new split had been checked.
        raw = r.get("mem_split")
        if raw == "full+client":
            return (str(srv_heap or "n/a"), f"{srv_cap:g}g") if not (
                not srv_heap and _is_jvm(r.get("backend"))) else (
                "NO-WITNESS", f"{srv_cap:g}g")
        try:
            split = float(raw or SERVER_MEM_FRACTION_DEFAULT)
        except (TypeError, ValueError):
            split = SERVER_MEM_FRACTION_DEFAULT
        if not 0 < split < 1:
            split = SERVER_MEM_FRACTION_DEFAULT
        # NO FALLING BACK TO THE REQUEST. srv_heap is the witness, read from
        # the daemon; r["heap"] is what the cell ASKED for, and it equals
        # ArcadeDB's by construction. Substituting one for the other made the
        # gate pass by definition on every served JVM row, so a comparator
        # silently running its image default was indistinguishable from a
        # compliant one. That is not hypothetical: make_paper_tables carries an
        # Elasticsearch-only rule for exactly this, added after ES ran 4g while
        # its row said 16g.
        #
        # A JVM server with no witness is reported as a witness gap. A non-JVM
        # server legitimately has no heap and is left alone.
        if not srv_heap and _is_jvm(r.get("backend")):
            return ("NO-WITNESS", f"{srv_cap / split:g}g")
        return (str(srv_heap or "n/a"), f"{srv_cap / split:g}g")

    cap = _gib(r.get("mem_cap"))
    if cap is None:
        return (str(r.get("heap")), str(r.get("mem_cap")))
    split = r.get("mem_split")
    if str(r.get("role")) == "client" and split is not None:
        try:
            frac = 1.0 - float(split)
            if 0 < frac < 1:
                cap = cap / frac
        except (TypeError, ValueError):
            pass
    return (str(r.get("heap")), f"{cap:g}g")


def check_envelope(rows):
    """F3: same memory/heap envelope across backends within a (lane, scale)."""
    print("\n=== F3: same memory envelope per (lane, scale) ===")
    # The dense lane's published rows are NOT in runs.jsonl. T5 reads
    # results/dense_mp_2681/, and runs.jsonl still holds the pre-re-measure
    # dense rows at 28g/16g. Checking those reported the deep10m envelope as
    # unmatched long after it had been matched: the comparators were re-run at
    # 36g, into artifacts this check never opened. Same defect as claims_check
    # and the figure generator had -- a consumer left pointing at the old
    # store -- so it is fixed the same way, by reading what the table reads.
    # Only deep10m moves; l3d small still lives in runs.jsonl and must keep
    # being checked. Swapping the whole lane silently dropped it.
    rows = [r for r in rows
            if not (r.get("lane") == "l3d" and r.get("scale") == "deep10m")]
    rows = rows + _dense_rows()
    g = collections.defaultdict(lambda: collections.defaultdict(set))
    noheap = collections.defaultdict(set)
    for r in rows:
        h, m = _total_envelope(r)
        # A JVM heap is only comparable between engines that HAVE one. Qdrant,
        # Milvus, LanceDB and sqlite-vec are Rust/Go/C and report heap=None;
        # calling that a mismatched envelope against ArcadeDB's 24g compares a
        # setting to its own absence. The MEMORY CAP is the cross-engine
        # quantity and is compared for everyone.
        if h == "NO-WITNESS":
            # Recorded, not excused: the engine ran a heap nobody observed.
            noheap[(r["lane"], r["scale"])].add(str(r.get("backend")) + " (no witness)")
            h = "n/a"
        elif h in ("None", "", "n/a", None):
            if _is_jvm(r.get("backend")):
                # A JVM engine with no recorded heap is a RECORDING gap,
                # not an engine property. Reported separately rather than
                # excused, because an unrecorded heap is exactly how an
                # unmatched one would hide.
                #
                # This used to test "arcade" in the backend name, so the same
                # gap on Neo4j, Elasticsearch or QuestDB was silently treated
                # as "this engine has no heap". All three are JVM engines.
                noheap[(r["lane"], r["scale"])].add(r["backend"])
            h = "n/a"
        g[(r["lane"], r["scale"])][r["backend"]].add((h, m))
    bad = 0
    for key in sorted(g, key=str):
        per_be = g[key]
        envs = {e for s in per_be.values() for e in s}
        # The two axes are judged separately: the memory cap must match across
        # EVERY engine, the heap only across the engines that have one.
        caps = {m for _, m in envs}
        heaps = {h for h, _ in envs if h != "n/a"}
        if len(caps) == 1 and len(heaps) <= 1:
            m = next(iter(caps))
            h = next(iter(heaps)) if heaps else "n/a"
            jvm = sum(1 for s in per_be.values()
                      for hh, _ in s if hh != "n/a")
            print(f"  ok   {key[0]:6} {key[1]:8} heap={h} mem={m} "
                  f"({len(per_be)} backends, {jvm} on a JVM)")
            if key in noheap:
                print(f"         note: {', '.join(sorted(noheap[key]))} is a JVM "
                      "engine but recorded no heap. The cap matches; the heap "
                      "is unverifiable from the artifact.")
            continue
        bad += 1
        print(f"  FAIL {key[0]:6} {key[1]:8} backends did NOT get the same "
              f"envelope:")
        if len(caps) > 1:
            print(f"         memory caps differ: {sorted(caps)}")
        if len(heaps) > 1:
            print(f"         JVM heaps differ: {sorted(heaps)}")
        for be, s in sorted(per_be.items()):
            for h, m in sorted(s):
                print(f"         {be:32} heap={h} mem={m}")
        note = DISCLOSED.get(key, {}).get("__note__")
        if note:
            print(f"         (disclosed override on record: {note})")
        print("         Raising a resource for one engine obliges a re-measure")
        print("         of every engine at that tier. See FAIRNESS.md.")
    return bad


def _base_degree(r):
    """Effective BASE-LAYER graph degree, in one unit, or None.

    The dense lane's engines do not agree on what "M" means. ArcadeDB's
    maxConnections is a per-layer bound, so it IS the base-layer degree.
    hnswlib-style engines (Chroma, Qdrant, Milvus, DuckDB-VSS, LanceDB) take an
    upper-layer M and double it at layer 0. Comparing the raw numbers compares
    two different quantities, which is how a shared constant of 32 could look
    matched while giving the comparators twice the degree.

    Rows written from 2026-08-01 carry degree_param/degree_family and answer
    directly. Older rows carry only `m`, so the family is inferred from the
    backend name -- inference is acceptable for a check whose failure mode is
    a warning, and it is why the newer fields exist.
    """
    fam, val = r.get("degree_family"), r.get("degree_param")
    if fam is None:
        val = r.get("m")
        be = str(r.get("backend", ""))
        if be.startswith("arcadedb"):
            fam = "arcadedb_maxconnections_per_layer"
        elif be.startswith("sqlite_vec"):
            fam = "exact_scan_no_ann"
        else:
            fam = "hnswlib_m_doubled_at_base"
    if fam == "exact_scan_no_ann" or val is None:
        return None
    return val * 2 if fam == "hnswlib_m_doubled_at_base" else val


def check_degree(rows):
    """F7: same effective base-layer degree across dense backends per scale.

    Added 2026-08-01 after finding that l3d_dense.py handed ONE constant to
    both unit systems. It was harmless while the default was 16 (every
    published comparator row records m=16, and the T5 dense block as printed
    IS matched), but the default became 32 to fix ArcadeDB and nothing had
    re-run since. The October freeze re-measures this lane, and would have
    built five comparators at twice their intended degree with ArcadeDB
    correct -- a fourth "all three favoured us" entry for the list above, found
    before it produced a number rather than after.
    """
    print("\n=== F7: same effective base-layer degree per (lane, scale) ===")
    # Same store defect F3 had, one check down: deep10m's PUBLISHED rows live
    # in results/dense_mp_2681/, and this was reading runs.jsonl's superseded
    # ones. It reported "ok, degree 32, 7 backends" for a tier whose actual
    # artifacts record degree_param=None on every arm. A check that passes on
    # rows the table does not print is not checking the table.
    rows = [r for r in rows
            if not (r.get("lane") == "l3d" and r.get("scale") == "deep10m")]
    rows = rows + _dense_rows()
    g = collections.defaultdict(dict)
    unstamped = collections.defaultdict(set)
    for r in rows:
        if r.get("lane") != "l3d":
            continue
        d = _base_degree(r)
        if d is not None:
            g[r["scale"]].setdefault(r["backend"], set()).add(d)
        elif r.get("backend") == "sqlite_vec_dense":
            # An exact scan has no graph, so it has no degree to match. That is
            # a property of the engine, like a Rust engine having no JVM heap,
            # not a recording gap. It is the recall=1.0 baseline precisely
            # because it builds no approximate structure at all.
            pass
        else:
            unstamped[r["scale"]].add(r["backend"])
    if not g and not unstamped:
        print("  (no dense rows)")
        return 0
    bad = 0
    for scale in sorted(set(g) | set(unstamped), key=str):
        per_be = g.get(scale, {})
        if scale in unstamped:
            # NOT a pass and NOT a silent skip. Degree decides recall and
            # latency together, so a row that does not record the degree it was
            # built at cannot be shown to be matched -- and F7 exists because
            # one shared constant once meant two different graphs.
            bad += 1
            print(f"  FAIL l3d    {scale:8} {len(unstamped[scale])} backend(s) "
                  "record NO degree, so the match is unverifiable:")
            for be in sorted(unstamped[scale]):
                print(f"         {be}")
            print("         The lane stamps degree_param/degree_family; the "
                  "multipass driver does not carry them through.")
            if per_be:
                print(f"         (the {len(per_be)} that do: "
                      f"{sorted({d for s in per_be.values() for d in s})})")
            continue
        degrees = {d for s in per_be.values() for d in s}
        if len(degrees) == 1:
            print(f"  ok   l3d    {scale:8} base-layer degree "
                  f"{next(iter(degrees))} ({len(per_be)} backends)")
            continue
        bad += 1
        print(f"  FAIL l3d    {scale:8} backends did NOT get the same "
              f"base-layer degree:")
        for be, s in sorted(per_be.items()):
            print(f"         {be:32} degree={sorted(s)}")
        print("         Degree decides recall and latency together, so an")
        print("         unmatched degree makes the whole row incomparable.")
    return bad


def check_protocol_overlays():
    """F4: overlays that feed tables, and whether their protocol is stated.

    This cannot be fully automated: a protocol lives in a driver, not in the
    JSON. What CAN be checked is the tell that exposed both known cases, a
    single build_s shared by every rep. Five reps of one build_s means one
    build with repeated passes; five distinct values mean independent builds.
    Neither is wrong, but a table must not mix them.
    """
    print("\n=== F4: build protocol per CELL GROUP (one build vs per-rep builds) ===")
    import re
    groups = collections.defaultdict(list)
    for sub in sorted(os.listdir(RESULTS)):
        d = os.path.join(RESULTS, sub)
        if not os.path.isdir(d):
            continue
        for fp in glob.glob(os.path.join(d, "*.json")):
            try:
                obj = json.load(open(fp))
            except Exception:
                continue
            # A cell group is one arm at one tier, so strip the trailing rep
            # index and key on n_docs too. Lumping a whole directory made
            # every multi-tier overlay look "mixed" for innocent reasons, and
            # a check that cries wolf is a check nobody reads.
            stem = re.sub(r"(_rep|_r)\d+\.json$", "", os.path.basename(fp))
            for rec in (obj if isinstance(obj, list) else [obj]):
                if isinstance(rec, dict) and isinstance(
                        rec.get("build_s"), (int, float)):
                    key = (sub, stem, rec.get("n_docs") or rec.get("scale"))
                    groups[key].append(round(rec["build_s"], 1))
    shapes = {}
    for key, builds in sorted(groups.items(), key=str):
        n, distinct = len(builds), len(set(builds))
        if n < 2:
            continue
        shape = ("one-build" if distinct == 1
                 else "per-rep-builds" if distinct == n else "mixed")
        shapes.setdefault(shape, []).append(key)
    for shape in ("one-build", "per-rep-builds", "mixed"):
        keys = shapes.get(shape, [])
        if not keys:
            continue
        print(f"  {shape:15} {len(keys):3} cell group(s)")
        for k in keys[:6]:
            print(f"      {k[0]}/{k[1]}")
        if len(keys) > 6:
            print(f"      ... and {len(keys) - 6} more")
    print("  Neither shape is wrong on its own. It IS a defect when one sits")
    print("  beside the other in a table: T5's dense row prints ArcadeDB's")
    print("  one-build passes 2-5 next to comparators' per-rep-build single")
    print("  pass (#117). queue61 is re-measuring the comparators to match.")
    return 0


def check_close_cost(rows):
    """F11: close must be O(what was written), not O(what is stored).

    DECISIONS #50. This is a REGRESSION gate rather than a fairness one, and it
    lives here because this is where the numbered invariants are. Two ways to
    fail, and they catch different defects:

      1. A clean close over 100 ms. Grounded twice: close should not cost more
         than getting started, and JVM startup on these hosts is ~160 ms; and
         it should sit under the ~100 ms at which a script stops feeling
         instant.
      2. A clean close that GROWS with row count while nothing was written.
         That is the O(stored) shape and it is always a defect, whatever the
         absolute number. This is the one that would have caught #5747 and
         #6489 while their absolute values were still small.

    The engine has produced three defects in this family (#5747, #6489 which
    was ours, #5872), which is why a number that can slide between releases
    with nobody watching gets a gate instead of a column.
    """
    # THE SESSION, not just the close. F11 originally watched clean_close alone,
    # and PR #6588 upstream is the proof that this is not enough: persisting the
    # analytical view's CSR moved its cost from close to open, 4032 -> 5.95 ms
    # closing and 4.94 -> 241.84 ms opening at a million vertices. A close-only
    # gate goes GREEN on that, and would equally go green on a change that moved
    # cost the other way and made a session slower overall. What a caller pays is
    # open plus close, so that is what gets budgeted.
    lc = [r for r in rows if r.get("lane") == "lifecycle"
          and r.get("clean_close_ms") is not None]
    for r in lc:
        r["_session_ms"] = (r["clean_close_ms"]
                            + (r.get("clean_open_ms") or 0.0))
    if not lc:
        # NOT a pass. This gate returned 0 for weeks while PAPER_SCALES was
        # silently deleting every lifecycle row upstream of it, so the one check
        # that would have caught the deletion reported success because of it.
        # A gate whose only failure mode is "I saw nothing" has to treat seeing
        # nothing as the failure.
        any_lifecycle = any(r.get("lane") == "lifecycle" for r in rows)
        print("\n== F11 session cost ==\n  NO LIFECYCLE ROWS REACHED THIS GATE.")
        if any_lifecycle:
            print("  Rows exist but none carry clean_close_ms; the lane wrote them "
                  "without the column this gate reads.")
        else:
            print("  Check PAPER_SCALES in make_paper_tables.py: a lane absent from "
                  "it is deleted by load_canonical before any gate runs.")
        return 1
    print("\n== F11 session cost (open+close): O(written), not O(stored), under 100 ms ==")
    bad = 0
    # AGGREGATE BY MEDIAN, per (situation, scale). The first version of this
    # assigned into a dict per row, so with N reps it kept whichever rep came
    # last and compared two arbitrary single measurements. On the first real
    # data it reported `sparse` growing 4.5x when the medians are 3.90 -> 3.96
    # ms, a 1.02x. A gate that fires on one noisy rep trains its reader to
    # ignore it, which is worse than not having it.
    cells = collections.defaultdict(list)
    for r in lc:
        cells[(r["workload"], r.get("scale"))].append(r["_session_ms"])
    by_sit = collections.defaultdict(dict)
    for (sit, scale), vals in sorted(cells.items()):
        med = statistics.median(vals)
        by_sit[sit][scale] = med
        if med > 100.0:
            print(f"  BAD: {sit}/{scale} clean session (open+close) {med:.1f} ms "
                  f"median of {len(vals)} exceeds the 100 ms budget "
                  f"[{min(vals):.1f}-{max(vals):.1f}]")
            bad += 1
    # The shape test. Rows are the same situation at two sizes with nothing
    # written in either, so any growth beyond noise is growth in what is
    # STORED. 1.5x over 10x the data is the tolerance: the flat situations in
    # the matrix move by well under that, and the two that scale move by 10x
    # or more, so nothing sits near the line.
    for sit, sizes in sorted(by_sit.items()):
        if "lc10k" in sizes and "lc100k" in sizes:
            small, big = sizes["lc10k"], sizes["lc100k"]
            if small > 0 and big / small > 1.5:
                print(f"  BAD: {sit} clean session grows {big / small:.1f}x "
                      f"({small:.1f} -> {big:.1f} ms medians) over 10x the "
                      f"rows, with nothing written. That is O(stored).")
                bad += 1
    if not bad:
        print(f"  ok {len(lc)} lifecycle row(s), none over budget, none scaling")
    return bad


def main():
    try:
        rows = _canonical()
    except Exception as e:
        print(f"cannot load canonical rows: {e}")
        return 2
    bad = check_cpuset(rows) + check_envelope(rows) + check_degree(rows)
    bad += check_close_cost(rows)
    check_protocol_overlays()
    bad += report_producers(rows)
    print(f"\n{bad} fairness invariant failure(s)")
    if bad:
        print("A comparison is only worth printing if both sides were given")
        print("the same thing. See FAIRNESS.md for the contract and the")
        print("standing list of known violations.")
    return 1 if bad else 0



# ---------------------------------------------------------------------------
# F6b: published cells come from lane scripts, not bespoke drivers.
#
# FAIRNESS.md's structural finding is that both known protocol violations were
# rows produced by a bespoke driver rather than the lane script, and it states
# the rule "bespoke drivers investigate, lane scripts publish". Until now that
# rule lived only in prose, so honouring it per row was an act of memory by
# whoever promoted a driver's output to a cell. run_conditions() now stamps a
# "producer" field, which makes it checkable.
#
# A row with no producer is NOT passed. Silence is how the overlays got away
# with recording no conditions at all (#113); an unstamped row predates the
# stamp, which is exactly the population that needs looking at.
LANE_SCRIPT = {
    "l1": {"l1_tabular.py"},
    "l1tpc": {"l1_tpc.py"},
    "l2": {"l2_graph.py", "ldbc_snb.py"},
    "l3s": {"l3_sparse.py"},
    "l3d": {"l3d_dense.py"},
    "l4": {"l4_tsbs.py"},
    "e2": {"e2_hybrid.py"},
    "lifecycle": {"l5_lifecycle.py"},
    "e4_decomp": {"deployment_decomp_probe.py"},
}


def check_producers(rows):
    """Return (violations, unstamped) for rows that would feed a table."""
    violations, unstamped = [], []
    for r in rows:
        lane = r.get("lane")
        if lane not in LANE_SCRIPT:
            continue
        prod = r.get("producer")
        if not prod:
            unstamped.append((lane, r.get("backend"), r.get("scale")))
        elif prod not in LANE_SCRIPT[lane]:
            violations.append((lane, r.get("backend"), r.get("scale"), prod))
    return violations, unstamped


def report_producers(rows):
    """F6b: did published rows come from the lane script or a bespoke driver?

    Was dead code until 2026-08-01. check_producers() and LANE_SCRIPT sat
    BELOW `if __name__ == "__main__": sys.exit(main())`, so running the file
    as a script exited at that line and never reached their definitions, let
    alone called them. FAIRNESS.md calls this rule the structural cause of
    both known protocol violations, and its enforcement had never executed
    once. Its lane key was also "l1_tpc" where runs.jsonl says "l1tpc", so
    every TPC-H row would have been skipped even had it run.
    """
    print("\n=== F6b: published rows come from lane scripts, not drivers ===")
    violations, unstamped = check_producers(rows)
    if violations:
        print(f"  FAIL {len(violations)} row(s) produced by a bespoke driver:")
        for lane, be, scale, prod in violations[:12]:
            print(f"         {lane:6} {str(scale):8} {str(be):30} producer={prod}")
        print("         Bespoke drivers investigate, lane scripts publish.")
    if unstamped:
        seen = collections.Counter(f"{l}/{s}" for l, _, s in unstamped)
        print(f"  {len(unstamped)} row(s) carry no producer at all "
              f"(predate the stamp): {dict(list(seen.items())[:6])}")
        print("    Not passed and not failed: unstamped is the population that")
        print("    needs looking at, which is why silence is not a pass here.")
    if not violations and not unstamped:
        print("  ok: every row names its lane script as producer")
    return len(violations)


if __name__ == "__main__":
    sys.exit(main())
