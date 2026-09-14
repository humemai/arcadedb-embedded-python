#!/usr/bin/env python3
"""The TPC lane's five analytical answers, per engine, with no rounding at all.

WHY THIS EXISTS AND WHY IT IS NOT THE LANE. equivalence_check compares
`res_<q>_digest`, which is `bench_common.result_digest` at SIX significant
digits. Six is a CHOICE, and the question a digest cannot answer about itself
is whether that choice is right: engines that agree at six digits are proved
to agree at six digits and nothing is said about the seventh. At SF0.01 the
distinction is academic, because every aggregate this lane computes fits inside
six digits. At the campaign's own SF1 it is not: `sum(l_quantity)` is
74,476,040 in the largest Q1 group -- an EXACT integer sum, computed in doubles
that represent it exactly -- and six-digit rounding prints it 7.4476e+07,
discarding two digits of exactness that every engine had right.

So this driver runs the same five queries through the same adapters, with the
same declared columns and the same declared coercions, and records each cell as
a NATIVE value (int as int, double as a double that JSON round-trips) instead
of as a rounded string. Nothing here is timed and nothing here is published:
the stored answers are re-digested offline at 6, 8, 10, 12 and 17 significant
digits, and where the engines part company as the rounding tightens is what
decides whether six is too loose, too tight, or right. FAIRNESS F6b: bespoke
drivers investigate, lane scripts publish.

The stored rows are the input `result_digest` would have received, so offline
`result_digest(rows, columns=..., float_digits=6)` on them must reproduce the
lane's own `res_<q>_digest` exactly. That equality is the probe's self-test: if
it does not hold, the re-rounding says nothing about the lane.

Run through runner.py --driver so the cell envelope is the lane's own:

    BENCH_DRIVER_OUT_FMT='ans_{label}.json' python3 -u runner.py \
        --lanes l1tpc --backends duckdb --workloads olap --scale tpch1 \
        --reps 1 --tier sweep --workers 1 --driver tpc_answer_probe.py \
        --driver-out-dir tpc_answers_sf1 --results-file <scratch>.jsonl
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bench_common  # noqa: E402
import l1_tpc  # noqa: E402


def _native(v):
    """One cell, as something JSON holds without losing a double.

    Everything `_fmt_value` would turn into a string here (a date, a
    timedelta, a nested document) is turned into that same string now, so an
    offline `_fmt_value` over the stored value is the identity on it. Only
    ints, floats, bools and None survive as themselves, and those are exactly
    the types whose rendering depends on `float_digits`.
    """
    if v is None:
        return None
    if isinstance(v, bool) or isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    try:
        import decimal
        if isinstance(v, decimal.Decimal):
            return float(v)
    except Exception:  # noqa: BLE001
        pass
    item = getattr(v, "item", None)   # numpy scalar
    if callable(item):
        try:
            return _native(item())
        except Exception:  # noqa: BLE001
            pass
    return bench_common._fmt_value(v, 17)


def main():
    backend = os.environ.get("BENCH_MP_BACKEND") or ""
    out_path = os.environ.get("PROBE_OUT") or ""
    if not backend or not out_path:
        print("BENCH_MP_BACKEND and PROBE_OUT are both required", file=sys.stderr)
        return 2
    li, part = l1_tpc.load_frames()
    b = l1_tpc.BACKENDS[backend]()
    b.connect()
    t0 = time.perf_counter()
    b.build(li, part)
    build_s = round(time.perf_counter() - t0, 2)
    doc = {"backend": backend, "engine_version": getattr(b, "version", None),
           "tpch_sf": l1_tpc.SF, "n_lineitem": len(li), "n_part": len(part),
           "build_s": build_s, "instrument": bench_common.INSTRUMENT,
           "answers": {}}
    for which in l1_tpc.OLAP_QUERIES:
        spec = dict(l1_tpc.OLAP_DIGEST[which])
        columns = spec.get("columns") or ()
        coerce = spec.get("coerce")
        try:
            rows = b.olap(which)
        except Exception as e:  # noqa: BLE001
            doc["answers"][which] = {"error": f"{e.__class__.__name__}: {e}"}
            print(f"PROBE {backend} {which} FAILED {e.__class__.__name__}", flush=True)
            continue
        if rows is None:
            rows = []
        if bench_common._is_mapping(rows) or not hasattr(rows, "__iter__"):
            rows = [rows]
        names = [c[0] if isinstance(c, (tuple, list)) else str(c) for c in columns]
        out_rows = []
        for row in rows:
            if bench_common._is_mapping(row):
                vals = [bench_common._lookup(row, c) for c in columns]
            elif isinstance(row, (list, tuple)):
                vals = list(row)          # a positional row already IS this order
            else:
                vals = [row] + [bench_common._MISSING] * (len(columns) - 1)
            if coerce:
                for i in range(len(vals)):
                    how = coerce.get(i)
                    if how is None and i < len(names):
                        how = coerce.get(names[i])
                    if how is not None:
                        vals[i] = bench_common._coerce(vals[i], how)
            out_rows.append([_native(v) for v in vals])
        doc["answers"][which] = {
            "rows": out_rows, "n": len(out_rows),
            "order_matters": bool(spec.get("order_matters")),
            "order_key": spec.get("order_key"), "id_key": spec.get("id_key"),
            "columns": [list(c) if isinstance(c, (tuple, list)) else c for c in columns],
            # Declared coercions are applied HERE, so the offline re-digest
            # must not apply them a second time.
            "coerce_applied": coerce,
        }
        print(f"PROBE {backend} {which} n={len(out_rows)}", flush=True)
    try:
        b.close()
    except Exception:  # noqa: BLE001
        pass
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(doc, fh)
    print(f"PROBE wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
