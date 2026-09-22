#!/usr/bin/env python3
"""Is six significant digits the right canonical rounding at the campaign's size?

`bench_common.result_digest` rounds every float to six significant digits
before hashing, and `equivalence_check` compares those hashes. Two failure
modes sit on either side of that number and neither one announces itself:

  TOO LOOSE -- engines that disagree are hashed to the same string, and the
  gate prints "all agreeing" over a real defect. This gets WORSE as the corpus
  grows, because the tolerance is RELATIVE while the thing a dropped row
  contributes is ABSOLUTE.

  TOO TIGHT -- two correct engines that summed the same doubles in a different
  order are hashed differently, and the gate fails a publish over the last bits
  of a floating-point sum. This also gets worse as the corpus grows, because
  more addends means more accumulated error.

Both are answered from measurements rather than from argument. `tpc_answer_probe.py`
stores each engine's five answers as native values with no rounding; this
re-digests them at 6, 8, 10, 12 and 17 significant digits and reports where the
engines part company, alongside the observed cross-engine spread per column and
the tolerance each rounding grants.

    python3 tpc_rounding_audit.py --dir results/tpc_answers_sf1 \
                                  --rows results/runs_sf1_equiv.jsonl

The --rows file is the probe's SELF-TEST, not decoration: re-digesting the
stored answers at six digits must reproduce the lane's own `res_<q>_digest`
for the same backend. If it does not, the stored answers are not what the lane
digested and nothing below means anything.
"""
import argparse
import collections
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bench_common  # noqa: E402

DIGIT_SET = (6, 8, 10, 12, 17)


def load_answers(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "ans_*.json"))):
        with open(p) as fh:
            doc = json.load(fh)
        out[doc["backend"]] = doc
    return out


def load_lane_digests(path):
    """{(backend, query): digest} from the lane's own rows."""
    got = {}
    if not path or not os.path.exists(path):
        return got
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("workload") != "olap" or str(r.get("rc") or 0) not in ("0", "0.0"):
                continue
            for k, v in r.items():
                if str(k).startswith("res_") and str(k).endswith("_digest") and v:
                    q = str(k)[4:-7]
                    got[(r.get("backend"), q)] = v
    return got


def digest_at(ans, digits):
    """The lane's own digest pipeline over the probe's stored rows.

    `coerce` is NOT passed: the probe applied the declared coercions before
    storing, and the `coerce` marks are folded into the hashed blob, so it is
    reinstated here as the stored `coerce_applied` to keep the blob identical
    to the lane's.
    """
    rows = [tuple(r) for r in ans["rows"]]
    cols = tuple(tuple(c) if isinstance(c, list) else c for c in ans["columns"])
    kw = dict(columns=cols, float_digits=digits,
              order_matters=ans.get("order_matters", False),
              order_key=ans.get("order_key"), id_key=ans.get("id_key"))
    d = bench_common.result_digest(rows, **kw)
    if ans.get("coerce_applied"):
        # Re-hash with the coercion marks the lane records, without re-applying
        # the coercion itself (idempotent here, but not assumed).
        canon = bench_common.canonical_rows(rows, columns=cols, float_digits=digits)
        if kw["order_matters"]:
            pos = bench_common._key_positions(cols, kw["order_key"])
            idp = bench_common._key_positions(cols, kw["id_key"])
            if pos is not None:
                canon = sorted(canon, key=lambda r: (tuple(r[i] for i in pos if i < len(r)),
                                                     tuple(r[i] for i in idp if i < len(r)) if idp else r))
        else:
            canon = sorted(canon)
        names = [c[0] if isinstance(c, (tuple, list)) else str(c) for c in cols]
        marks = ",".join(f"{k}:{v if isinstance(v, str) else 'fn'}"
                         for k, v in sorted(ans["coerce_applied"].items(), key=lambda kv: str(kv[0])))
        blob = "\x1d".join([bench_common.DIGEST_VERSION, ",".join(names), marks,
                            "ordered" if kw["order_matters"] else "unordered",
                            str(digits), str(len(canon))] + ["\x1f".join(r) for r in canon])
        import hashlib
        d = dict(d, digest=hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:16])
    return d


def float_columns(docs, query):
    """Column index -> {backend: [values]} for every column that is a float
    somewhere. Ints are exact and strings are strings; only floats are rounded."""
    per = collections.defaultdict(dict)
    for be, doc in docs.items():
        a = doc["answers"].get(query) or {}
        if "rows" not in a:
            continue
        for i in range(len(a["columns"])):
            col = [r[i] for r in a["rows"]]
            if any(isinstance(v, float) for v in col):
                per[i][be] = col
    return per


def key_of(doc, query, row):
    """A row's non-float cells, which is what identifies it across engines."""
    a = doc["answers"][query]
    return tuple(str(v) for i, v in enumerate(row)
                 if not isinstance(v, float) or isinstance(v, bool))


def spread_report(docs, query, out=print):
    """Largest RELATIVE gap between two engines on one float cell, per column.

    Rows are matched on their non-float cells (the group key), so the gap is
    between two engines' answers to the same group and not between two rows.
    """
    names = None
    matched = collections.defaultdict(dict)   # (rowkey, col) -> {backend: value}
    for be, doc in docs.items():
        a = doc["answers"].get(query) or {}
        if "rows" not in a:
            continue
        names = [c[0] if isinstance(c, list) else c for c in a["columns"]]
        for row in a["rows"]:
            k = key_of(doc, query, row)
            for i, v in enumerate(row):
                if isinstance(v, float) and not isinstance(v, bool):
                    matched[(k, i)][be] = v
    worst = {}
    for (k, i), by_be in matched.items():
        if len(by_be) < 2:
            continue
        lo, hi = min(by_be.values()), max(by_be.values())
        ref = max(abs(lo), abs(hi)) or 1.0
        rel = (hi - lo) / ref
        cur = worst.get(i)
        if cur is None or rel > cur[0]:
            worst[i] = (rel, hi - lo, ref, k, by_be)
    for i in sorted(worst):
        rel, absd, ref, k, by_be = worst[i]
        nm = names[i] if names and i < len(names) else f"col{i}"
        out(f"    {query:10} {str(nm):9} magnitude {ref:.6g}  worst cross-engine "
            f"gap {absd:.6g} ({rel:.3e} relative)  across {len(by_be)} engines")
        for d in DIGIT_SET:
            if d >= 17:
                continue
            ulp = 10 ** (math.floor(math.log10(abs(ref))) - (d - 1))
            verdict = "SPLITS" if absd > ulp / 2 else "absorbed"
            out(f"        {d:2}-digit tolerance: ulp {ulp:.6g} "
                f"(half-ulp/value {ulp/2/ref:.2e})  -> the gap is {verdict}")
    return worst


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="results/tpc_answers_sf1")
    ap.add_argument("--rows", default="results/runs_sf1_equiv.jsonl")
    args = ap.parse_args()
    d = args.dir if os.path.isabs(args.dir) else os.path.join(HERE, args.dir)
    docs = load_answers(d)
    if not docs:
        print(f"no ans_*.json under {d}")
        return 2
    print(f"engines: {len(docs)} -- {', '.join(sorted(docs))}")

    for be in sorted(docs):
        doc = docs[be]
        print(f"  {be:26} {str(doc.get('engine_version'))[:38]:38} "
              f"sf={doc.get('tpch_sf')} n_lineitem={doc.get('n_lineitem')} "
              f"build_s={doc.get('build_s')}")

    # REFUSE TO AUDIT A PRE-DECLARATION ARTIFACT QUIETLY.
    #
    # On 2026-09-14 the pricing summary split seven engines to one because
    # ArangoDB types a SUM over integer-stored columns as an int while every
    # SQL engine types it as a double, and an int prints exactly where a
    # double prints to six significant digits. The fix was a per-column
    # declaration in l1_tpc.OLAP_DIGEST -- a measure is `num` and compared as
    # a number whatever the driver returned -- not a looser hash.
    #
    # Answers STORED BEFORE that fix carry no `coerce_applied`, so re-digesting
    # them here reproduces the original split faithfully and reports it as a
    # live finding. On 2026-09-22 that cost an hour: the split was rediscovered
    # from these very files, diagnosed correctly, and a "fix" was written
    # against a gate that had been correct for eight days.
    #
    # An artifact that predates the declaration cannot answer the question this
    # tool asks, so it says so first rather than printing a table that reads
    # like news.
    # PER QUERY, against the lane's CURRENT declarations. An `any()` over one
    # engine's whole answer set hides this: by_month has always carried a
    # coercion for its month key, so every engine looked declared while q1 --
    # the query that actually splits -- carried none.
    import l1_tpc
    _stale = []
    for q, spec in sorted(l1_tpc.OLAP_DIGEST.items()):
        want = spec.get("coerce")
        if not want:
            continue
        missing = sorted(be for be, doc in docs.items()
                         if ((doc.get("answers") or {}).get(q) or {}).get("coerce_applied") is None)
        if missing:
            _stale.append((q, want, missing))
    for q, want, missing in _stale:
        print(f"\n  !! {q}: {len(missing)} of {len(docs)} engines' stored answers carry NO "
              f"coerce_applied, but the lane declares {sorted(want)}")
        print(f"     ({', '.join(missing)})")
        print("     These were stored before that declaration landed "
              "(l1_tpc.OLAP_DIGEST, 2026-09-14, the int-vs-double SUM spelling).")
        print(f"     Any {q} split reported below is that ALREADY-FIXED defect "
              "being replayed, not a live finding.")
        print("     Re-run tpc_answer_probe.py to audit the current instrument.")

    print("\n=== SELF-TEST: the stored answers re-digested at 6 digits must equal "
          "the lane's own digest ===")
    lane = load_lane_digests(args.rows if os.path.isabs(args.rows)
                             else os.path.join(HERE, args.rows))
    checked = bad = 0
    for be in sorted(docs):
        for q, a in docs[be]["answers"].items():
            if "rows" not in a:
                continue
            want = lane.get((be, q))
            if not want:
                continue
            got = digest_at(a, 6)["digest"]
            checked += 1
            if got != want:
                bad += 1
                print(f"  MISMATCH {be} {q}: probe {got} vs lane {want}")
    if not checked:
        print("  no lane digests to compare against (is --rows right?)")
    elif bad:
        print(f"  {bad} of {checked} mismatched: the probe is not digesting what "
              f"the lane digested, so everything below is void")
        return 2
    else:
        print(f"  ok: {checked} (backend, query) digests reproduced exactly")

    print("\n=== AGREEMENT AS THE ROUNDING TIGHTENS ===")
    queries = sorted({q for doc in docs.values() for q in doc["answers"]})
    for digits in DIGIT_SET:
        print(f"  -- {digits} significant digits --")
        for q in queries:
            by_digest = collections.defaultdict(list)
            for be in sorted(docs):
                a = docs[be]["answers"].get(q) or {}
                if "rows" not in a:
                    continue
                by_digest[digest_at(a, digits)["digest"]].append(be)
            if not by_digest:
                continue
            n_engines = sum(len(v) for v in by_digest.values())
            if n_engines < 2:
                # One answer agrees with itself. The same rule equivalence_check
                # keeps: a group with one engine is UNCHECKED, never a pass.
                print(f"     {q:10} UNCHECKED  1 engine")
            elif len(by_digest) == 1:
                print(f"     {q:10} AGREE   {n_engines} engines")
            else:
                print(f"     {q:10} SPLIT into {len(by_digest)} answers:")
                for dg, bes in sorted(by_digest.items(), key=lambda kv: -len(kv[1])):
                    print(f"        {dg}  {', '.join(bes)}")

    print("\n=== HOW FAR APART DO THE ENGINES ACTUALLY LAND, PER COLUMN ===")
    print("  (rows matched on their non-float cells, so this is one group's "
          "answer against the same group's)")
    for q in queries:
        spread_report(docs, q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
