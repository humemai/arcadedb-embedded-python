#!/usr/bin/env python3
"""The answers-identical gate of the PostgreSQL-wire twin (DECISIONS #166: adopt nothing the wire cannot prove; #237 (3)).

A served SQL cell also runs with its read statements on ArcadeDB's PostgreSQL wire (`arcadedb_client_wire` = pgwire, role `sensitivity`). The wire
returns the same rows with other Python types (Decimal for a number, datetime for a timestamp, a list for an array), so a latency beside the headline
means nothing unless the ANSWERS agree. The lanes already record, outside every timed section, one digest per deterministic query
(`res_<query>_digest`, `bench_common.record_result`), computed from the rows the timed call returned and under the lane's own declared coercions
(`coerce=` per query: epoch seconds, numbers, months). The twin runs the SAME lane code, so its digests are taken under the same coercions by
construction; this module compares them with the headline's, per query:

  * equal                                   -> the query is checked and passes;
  * different                               -> the twin row FAILS, the reason names the query and both digests;
  * a query the headline recorded and the twin did not (silence is not agreement) -> the twin row FAILS;
  * a query only the twin recorded          -> listed as unchecked, not a failure (nothing to compare with);
  * the headline disagrees with itself across its own rows (more than one digest for one query) -> that query is unchecked, named;
  * no headline row, or no digest on either side -> the whole row is `unchecked`, recorded, never passed.

A failed twin row is KEPT with `error` set (the reason is recorded; it is never dropped from the results file), so landing and export see a failed
sensitivity row, not a missing one. The runner applies `stamp()` as the twin cell ends (against the headline rows already in the results file);
`python3 pgwire_gate.py --rows results/runs.jsonl` applies it to a whole file, with every headline row present, and exits 1 on any failure.
"""
import argparse
import json
import re
import sys

DIGEST_RE = re.compile(r"^res_(.+)_digest$")
WIRE = "pgwire"
# THE LANES THAT RECORD NO DIGEST. l3s and l3d answer an approximate top-k and are checked against exact ground truth, row by row (`recall_at_10`,
# computed outside the timer from the ids the timed call returned); a wire that returned other ids would show as another recall. Two builds of one
# index need not be identical, so the gate compares the twin's recall with the headline's median within RECALL_TOLERANCE and says so (it is not
# a digest). l1 (the synthetic orders lane) records neither, so its wire row stays `unchecked`.
RECALL_FIELD = "recall_at_10"
RECALL_TOLERANCE = 0.01
CELL_KEY = ("lane", "scale", "workload", "backend", "durability_class", "server_build")


def is_twin(row):
    return str(row.get("arcadedb_client_wire") or "") == WIRE


def is_headline(row):
    """A headline row: no sensitivity role (the official driver's rows are `headline`; an older row carries none), and no error."""
    return str(row.get("arcadedb_http_client_role") or "") != "sensitivity" and not row.get("error")


def digests(row):
    """{query: digest} of a row's `res_<query>_digest` fields that hold a value (a declared absence, `unexpressible: ...`, is not a digest)."""
    out = {}
    for k, v in row.items():
        m = DIGEST_RE.match(k)
        if m and isinstance(v, str) and v and not v.startswith("unexpressible"):
            out[m.group(1)] = v
    return out


def cell_key(row):
    return tuple(str(row.get(k) if row.get(k) is not None else ("relaxed" if k == "durability_class" else "")) for k in CELL_KEY)


def check(twin, headline_rows):
    """The gate for one twin row against the headline rows of its cell: {"status": ok|failed|unchecked, "queries_checked", "reasons", "unchecked"}."""
    heads = [h for h in headline_rows if is_headline(h) and cell_key(h) == cell_key(twin)]
    seen = {}
    for h in heads:
        for q, d in digests(h).items():
            seen.setdefault(q, set()).add(d)
    mine = digests(twin)
    reasons, unchecked, checked = [], [], 0
    if heads and not seen:
        return _check_recall(twin, heads)
    if not heads or not seen:
        return {"status": "unchecked", "queries_checked": 0, "reasons": [], "unchecked": ["no headline row with digests for this cell"]}
    for q in sorted(seen):
        if len(seen[q]) > 1:
            unchecked.append(f"{q}: the headline has {len(seen[q])} digests across its own rows")
            continue
        (want,) = seen[q]
        if q not in mine:
            reasons.append(f"{q}: the headline recorded a digest and the pg-wire row recorded none")
        elif mine[q] != want:
            reasons.append(f"{q}: the pg-wire digest {mine[q]} is not the headline's {want}")
        else:
            checked += 1
    unchecked += [f"{q}: only the pg-wire row recorded it" for q in sorted(set(mine) - set(seen))]
    return {"status": "failed" if reasons else "ok" if checked else "unchecked", "queries_checked": checked, "reasons": reasons, "unchecked": unchecked}


def _check_recall(twin, heads):
    """The gate for a lane with no digests: the twin's recall against the headline's median (RECALL_FIELD), or `unchecked` when either side has none."""
    ref = sorted(float(h[RECALL_FIELD]) for h in heads if h.get(RECALL_FIELD) not in (None, ""))
    mine = twin.get(RECALL_FIELD)
    if not ref or mine in (None, ""):
        return {"status": "unchecked", "queries_checked": 0, "reasons": [],
                "unchecked": ["the lane records no per-query digest and no recall for this cell, so the wire's answers were not compared"]}
    med = ref[len(ref) // 2] if len(ref) % 2 else (ref[len(ref) // 2 - 1] + ref[len(ref) // 2]) / 2
    off = abs(float(mine) - med)
    note = f"{RECALL_FIELD}: compared within {RECALL_TOLERANCE} of the headline median, not by digest"
    if off > RECALL_TOLERANCE:
        return {"status": "failed", "queries_checked": 0, "unchecked": [],
                "reasons": [f"{RECALL_FIELD}: the pg-wire row has {float(mine):.4f}, the headline median is {med:.4f} (more than {RECALL_TOLERANCE} apart)"]}
    return {"status": "ok", "queries_checked": 1, "reasons": [], "unchecked": [note]}


def stamp(row, headline_rows):
    """Record the gate on the twin row; a failure also sets `error` (the row stays, marked failed, reason named). Returns the result."""
    res = check(row, headline_rows)
    row["arcadedb_pgwire_gate"] = res
    if res["status"] == "failed" and not row.get("error"):
        row["error"] = "pg-wire answers differ from the headline: " + "; ".join(res["reasons"][:5]) + (" ..." if len(res["reasons"]) > 5 else "")
    return res


def load(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def check_file(rows):
    """[(row, result)] for every twin row of a whole results file."""
    heads = [r for r in rows if not is_twin(r)]
    return [(r, check(r, heads)) for r in rows if is_twin(r) and not (r.get("error") and not r.get("arcadedb_pgwire_gate"))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", required=True, help="a results .jsonl file")
    args = ap.parse_args(argv)
    got = check_file(load(args.rows))
    bad = 0
    for r, res in got:
        print(f"{res['status']:9} {r.get('run_id')}: {res['queries_checked']} checked" + (f"; {res['reasons'][0]}" if res["reasons"] else ""))
        bad += res["status"] == "failed"
    print(f"{len(got)} pg-wire twin rows, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
