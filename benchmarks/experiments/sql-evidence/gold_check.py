"""Run every gold query on its engine and compare the result sets across languages.

  uv run --no-project --with pyyaml==6.0.2 python gold_check.py --data ~/bench-data/ldbc/sf1 --out DIR [--person-limit N]

Reference result per question: the ANSI SQL gold (DuckDB). Every other non-null gold must equal it under the
comparison rule in resultcmp.py (positional columns, order-insensitive unless `ordered`, float tolerance from
questions.yaml). Writes DIR/gold_report.json, DIR/gold_report.md and DIR/gold_rows.json (the reference rows plus the
per-arm verdict; score.py reads this file). Exit status 1 when any non-null gold errors or disagrees.
Also flags questions whose reference result is empty or a single zero (a weak question), without failing.
"""
import argparse
import json
import os
import sys

import yaml

import dockerrun
import resultcmp

HERE = os.path.dirname(os.path.abspath(__file__))
CATS = {"single": 10, "join": 10, "multi_join": 10, "graph": 10}


def load_questions():
    doc = yaml.safe_load(open(os.path.join(HERE, "questions.yaml")))
    qs = doc["questions"]
    ids = [q["id"] for q in qs]
    errs = []
    if len(set(ids)) != len(ids):
        errs.append("duplicate question ids")
    for cat, n in CATS.items():
        got = sum(1 for q in qs if q["category"] == cat)
        if got != n:
            errs.append(f"category {cat}: {got} questions, expected {n}")
    if len(qs) != 40:
        errs.append(f"{len(qs)} questions, expected 40")
    for q in qs:
        for arm in resultcmp.ARMS:
            if arm not in q["gold"]:
                errs.append(f"{q['id']}: no gold key {arm}")
            elif q["gold"][arm] is None and not (q.get("null_reasons") or {}).get(arm):
                errs.append(f"{q['id']}: null gold for {arm} without null_reasons")
        if q["gold"].get("sql") is None:
            errs.append(f"{q['id']}: the sql gold is the reference and cannot be null")
    if errs:
        sys.exit("questions.yaml invalid:\n  " + "\n  ".join(errs))
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--person-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--cpuset", default="14,15")
    ap.add_argument("--mem", default="4g")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    doc = load_questions()
    tol = doc["tolerance"]
    qs = doc["questions"]
    results = {}
    versions = {}
    for engine in ("duckdb", "arcadedb"):
        jobs = [{"key": f"{q['id']}::{arm}", "arm": arm, "query": q["gold"][arm]}
                for q in qs for arm in resultcmp.ARMS
                if resultcmp.ENGINE_OF_ARM[arm] == engine and q["gold"][arm] is not None]
        out = dockerrun.run_engine(engine, jobs, a.data, a.out, f"gold-{engine}", a.person_limit, a.timeout,
                                   a.cpuset, a.mem)
        versions[engine] = {k: out[k] for k in ("engine_version", "image", "image_id", "load_s", "counts")}
        for r in out["results"]:
            results[r["key"]] = r

    report, rows_out, bad = [], {}, 0
    for q in qs:
        ref = results[f"{q['id']}::sql"]
        entry = {"id": q["id"], "category": q["category"], "ordered": q["ordered"], "ref_rows": ref["n_rows"],
                 "arms": {}, "warnings": []}
        if ref["exec_ok"] and (ref["n_rows"] == 0 or ref["rows"] in ([[0]], [[0.0]])):
            entry["warnings"].append("reference result is empty or a single zero (weak question)")
        arms_ok = {}
        for arm in resultcmp.ARMS:
            if q["gold"][arm] is None:
                entry["arms"][arm] = {"status": "NULL", "reason": q["null_reasons"][arm]}
                continue
            r = results[f"{q['id']}::{arm}"]
            if not r["exec_ok"]:
                st = {"status": "ERROR", "error": r["error"]}
            elif not ref["exec_ok"]:
                st = {"status": "NO_REFERENCE"}
            elif resultcmp.rows_equal(ref["rows"], r["rows"], q["ordered"], tol["float_abs"], tol["float_rel"], r["truncated"]):
                st = {"status": "OK"}
            else:
                st = {"status": "MISMATCH", "got": r["rows"][:5], "expected": ref["rows"][:5]}
            st["ms"] = r["ms"]
            entry["arms"][arm] = st
            arms_ok[arm] = st["status"] == "OK"
            if st["status"] not in ("OK",):
                bad += 1
        report.append(entry)
        rows_out[q["id"]] = {"category": q["category"], "ordered": q["ordered"], "rows": ref["rows"],
                             "arm_verified": arms_ok}

    json.dump({"engines": versions, "tolerance": tol, "person_limit": a.person_limit, "questions": report},
              open(os.path.join(a.out, "gold_report.json"), "w"), indent=1)
    json.dump({"tolerance": tol, "person_limit": a.person_limit, "questions": rows_out},
              open(os.path.join(a.out, "gold_rows.json"), "w"))
    lines = ["| id | category | " + " | ".join(resultcmp.ARMS) + " | ref rows | notes |", "|---|---|" + "---|" * (len(resultcmp.ARMS) + 2)]
    for e in report:
        cells = [e["arms"][arm]["status"] for arm in resultcmp.ARMS]
        lines.append(f"| {e['id']} | {e['category']} | " + " | ".join(cells) + f" | {e['ref_rows']} | {'; '.join(e['warnings'])} |")
    n_null = {arm: sum(1 for e in report if e["arms"][arm]["status"] == "NULL") for arm in resultcmp.ARMS}
    lines += ["", f"engines: {json.dumps({k: v['engine_version'] for k, v in versions.items()})}",
              f"person_limit: {a.person_limit}; null golds per arm: {json.dumps(n_null)}; non-OK non-null golds: {bad}"]
    open(os.path.join(a.out, "gold_report.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
