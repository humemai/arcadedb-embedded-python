"""Portability of the `sql` arm: run the SAME generated ANSI SQL on DuckDB, SQLite and PostgreSQL and score each.

  uv run --no-project --with 'psycopg[binary]==3.3.7' python score_portability.py --run-dir DIR|auto --gold GOLD_DIR \
      --data ~/bench-data/ldbc/sf1 --out OUT_DIR [--duckdb-scored SCORED.jsonl]

No new model calls: it reads DIR/generations.jsonl (generate.py collect) and DIR/manifest.json, takes only the `sql` arm,
applies the extraction rule and the scorable-question rule of score.py (frozen-file hash check, every non-null gold verified)
and the same comparison rule and float tolerance (resultcmp.rows_equal, reference rows from GOLD_DIR/gold_rows.json).
score.py and its pre-registered DuckDB scoring are not touched; this script re-runs the `sql` generations on DuckDB (same
image, 30 s statement timeout like the other two engines) so all three legs share one timeout and one run. `--duckdb-scored`
cross-checks that leg against score.py's scored.jsonl and reports every disagreement (not fatal).

Per generation and engine: parse_ok, exec_ok, correct (definitions as in engine_runner.py). Statement timeout 30 s
(--timeout), read-only session on every engine. Before anything is scored the eight tables are fingerprinted on all three
engines and the script exits when they differ (portable.check_loaded). `--run-dir auto` takes the newest
/home/tk/build-scratch/sql-evidence/gen-* directory that holds generations.jsonl.

Writes OUT_DIR/: loaded_counts.json, scored_portability.jsonl, portability.json, portability.md, divergences.jsonl.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

import dockerrun
import ldbc_subset
import portable
import resultcmp

ENGINES = ("duckdb", "sqlite", "postgres")
CAT_ORDER = ["single", "join", "multi_join", "graph"]
RUN_ROOT = "/home/tk/build-scratch/sql-evidence"

# Failure kinds from the error text, first match wins. The same patterns run on all three engines' messages.
KIND_RULES = [
    ("timeout", r"timeout after|statement timeout|canceling statement"),
    ("syntax", r"syntax error|parser error|parse error|parserexception|incomplete input|unrecognized token"),
    ("ambiguous_column", r"ambiguous"),
    ("aggregate_or_group_by", r"group by|misuse of aggregate|aggregate functions? (are|is) not allowed|aggregate function calls cannot"),
    ("unknown_function_or_signature", r"no such function|function .{0,80}does not exist|scalar function with name|aggregate function with name|table function with name|no function matches|undefinedfunction"),
    ("type_mismatch", r"operator does not exist|invalid input syntax|conversion error|cannot cast|datatype mismatch|could not determine data type|must be type|is of type|cannot be matched|type mismatch|invalidtextrepresentation|datatypemismatch|cannot compare"),
    ("unknown_column_or_table", r"no such (column|table)|column .{0,80}does not exist|relation .{0,80}does not exist|referenced column|table with name|undefinedcolumn|undefinedtable|not found in from clause"),
]
# Query features that can make an engine return a different, non-error answer. Labelled as features PRESENT in a generation
# that is correct on DuckDB but wrong on another engine, never as a diagnosed cause.
FEATURES = {
    "slash_operator (integer division)": re.compile(r"(?<![/*])/(?![/*])"),
    "order_by_without_nulls_clause (null ordering)": re.compile(r"order\s+by(?!.*nulls\s+(first|last))", re.I | re.S),
    "order_by_with_limit (tie order)": re.compile(r"order\s+by.*\blimit\b", re.I | re.S),
    "like (case sensitivity)": re.compile(r"\blike\b", re.I),
    "round_function": re.compile(r"\bround\s*\(", re.I),
    "boolean_literal": re.compile(r"\b(true|false)\b", re.I),
}


def kind_of(rec):
    """Failure kind of one engine's record; rec is not correct."""
    err = rec.get("error") or ""
    if err.startswith("failed generation"):
        return "failed_generation"
    if err.startswith("not a ") or err.startswith("empty query"):
        return "rejected_before_running"
    if rec["exec_ok"]:
        return "wrong_result"
    low = err.split("\n")[0].lower()  # first line only: later lines echo the query text
    for kind, pat in KIND_RULES:
        if re.search(pat, low):
            return kind
    return "other"


def fmt(k, n):
    if not n:
        return "-"
    lo, hi = resultcmp.wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def resolve_run_dir(arg):
    if arg != "auto":
        return arg
    dirs = sorted(d for d in glob.glob(os.path.join(RUN_ROOT, "gen-*")) if os.path.exists(os.path.join(d, "generations.jsonl")))
    if not dirs:
        sys.exit(f"--run-dir auto: no {RUN_ROOT}/gen-*/generations.jsonl")
    return dirs[-1]


def judge(res, g, tol):
    return bool(res["exec_ok"] and resultcmp.rows_equal(
        g["rows"], res["rows"], g["ordered"], tol["float_abs"], tol["float_rel"], res["truncated"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--person-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--cpuset", default="14,15")
    ap.add_argument("--mem", default="4g", help="memory of the DuckDB container")
    ap.add_argument("--pg-mem", default="2g", help="memory of the PostgreSQL container")
    ap.add_argument("--duckdb-scored", default=None, help="score.py scored.jsonl to cross-check the DuckDB leg against")
    a = ap.parse_args()
    a.run_dir = resolve_run_dir(a.run_dir)
    os.makedirs(a.out, exist_ok=True)
    portable.pin_cpus(a.cpuset)

    manifest = json.load(open(os.path.join(a.run_dir, "manifest.json")))
    now = resultcmp.frozen_hashes()
    changed = [k for k, v in manifest["frozen_sha256"].items() if now.get(k) != v]
    if changed:
        sys.exit(f"frozen files changed since the generations were requested: {changed}. Report a changed run as a new run.")
    gold = json.load(open(os.path.join(a.gold, "gold_rows.json")))
    if gold["person_limit"] != a.person_limit:
        sys.exit(f"gold was built with person_limit {gold['person_limit']}, scoring with {a.person_limit}")
    tol = gold["tolerance"]
    gq = gold["questions"]
    scorable = {qid for qid, g in gq.items() if g["arm_verified"] and all(g["arm_verified"].values())}
    gp_path = os.path.join(a.gold, "gold_portability.json")
    gp = json.load(open(gp_path))["questions"] if os.path.exists(gp_path) else None

    gens = [json.loads(line) for line in open(os.path.join(a.run_dir, "generations.jsonl"))]
    recs, jobs = [], []
    for g in gens:
        if g["arm"] != "sql":
            continue
        key = f"{g['model']}::{g['arm']}::{g['question_id']}::{g['sample']}"
        r = {"key": key, "model": g["model"], "question_id": g["question_id"], "sample": g["sample"],
             "category": gq[g["question_id"]]["category"], "scored": g["question_id"] in scorable,
             "stop_reason": g["stop_reason"], "query": resultcmp.extract_query(g["query"]), "engines": {}}
        if g["result_type"] != "succeeded" or g["stop_reason"] in ("refusal", "max_tokens") or not r["query"]:
            msg = f"failed generation: result_type={g['result_type']} stop_reason={g['stop_reason']}"
            for e in ENGINES:
                r["engines"][e] = {"parse_ok": False, "exec_ok": False, "correct": False, "error": msg}
        elif r["scored"]:
            jobs.append({"key": key, "arm": "sql", "query": r["query"]})
        recs.append(r)
    if not recs:
        sys.exit("no sql-arm generations in generations.jsonl")
    by_key = {r["key"]: r for r in recs}
    print(f"run dir {a.run_dir}: {len(recs)} sql generations, {len(jobs)} to execute on 3 engines", flush=True)

    data = ldbc_subset.load(a.data, a.person_limit)
    duck = dockerrun.run_engine("duckdb", jobs + portable.duck_fingerprint_jobs(), a.data, a.out, "port-duckdb",
                                a.person_limit, a.timeout, a.cpuset, a.mem)
    duck_by_key = {r["key"]: r for r in duck["results"]}
    extra = portable.run_extra_engines(data, jobs, a.out, a.timeout, a.cpuset, a.pg_mem, tag="port")
    loaded = portable.check_loaded(data, duck_by_key, extra)
    versions = {"duckdb": {k: duck[k] for k in ("engine_version", "engine_versions", "image", "image_id", "restarts", "engine_killed")},
                "sqlite": {"engine_version": extra["sqlite"]["version"]},
                "postgres": {k: extra["postgres"][k] for k in ("version", "image", "image_id", "image_digest", "settings", "session")}}
    json.dump({"person_limit": a.person_limit, "counts": loaded["counts"], "fingerprints": loaded["fingerprints"],
               "engines": versions}, open(os.path.join(a.out, "loaded_counts.json"), "w"), indent=1)

    results = {"duckdb": duck_by_key, "sqlite": {r["key"]: r for r in extra["sqlite"]["results"]},
               "postgres": {r["key"]: r for r in extra["postgres"]["results"]}}
    for j in jobs:
        r = by_key[j["key"]]
        g = gq[r["question_id"]]
        for e in ENGINES:
            res = results[e][j["key"]]
            r["engines"][e] = {"parse_ok": res["parse_ok"], "exec_ok": res["exec_ok"], "correct": judge(res, g, tol),
                               "error": res["error"], "n_rows": res["n_rows"], "sqlstate": res.get("sqlstate"),
                               "rows_head": res["rows"][:5]}
    with open(os.path.join(a.out, "scored_portability.jsonl"), "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    scored = [r for r in recs if r["scored"]]
    models = list(manifest["models"])
    groups = {m: [r for r in scored if r["model"] == m] for m in models}
    groups["all models"] = scored

    def cell(rs, e):
        n = len(rs)
        k = sum(r["engines"][e]["correct"] for r in rs)
        qs = collections.defaultdict(list)
        for r in rs:
            qs[r["question_id"]].append(r["engines"][e]["correct"])
        kq = sum(any(v) for v in qs.values())
        return {"n": n, "parse_ok": sum(r["engines"][e]["parse_ok"] for r in rs),
                "exec_ok": sum(r["engines"][e]["exec_ok"] for r in rs), "correct": k, "questions": len(qs), "pass3": kq}

    table = {}
    for m, rs in groups.items():
        for e in ENGINES:
            table[f"{m}|{e}|all"] = cell(rs, e)
            for cat in CAT_ORDER:
                table[f"{m}|{e}|{cat}"] = cell([r for r in rs if r["category"] == cat], e)

    def share(rs, e):
        base = [r for r in rs if r["engines"]["duckdb"]["correct"]]
        if e == "both":
            return len(base), sum(r["engines"]["postgres"]["correct"] and r["engines"]["sqlite"]["correct"] for r in base)
        return len(base), sum(r["engines"][e]["correct"] for r in base)

    port = {}
    for m, rs in groups.items():
        for scope, sub in [("all", rs)] + [(c, [r for r in rs if r["category"] == c]) for c in CAT_ORDER]:
            port[f"{m}|{scope}"] = {e: share(sub, e) for e in ("postgres", "sqlite", "both")}

    # Failure kinds: every scored generation that is not correct on an engine, and the subset that was correct on DuckDB.
    kinds_all = {e: collections.Counter() for e in ENGINES}
    kinds_div = {e: collections.Counter() for e in ("sqlite", "postgres")}
    examples = collections.defaultdict(list)
    feats = {e: collections.Counter() for e in ("sqlite", "postgres")}
    divergent = []
    for r in scored:
        for e in ENGINES:
            if not r["engines"][e]["correct"]:
                kinds_all[e][kind_of(r["engines"][e])] += 1
        if not r["engines"]["duckdb"]["correct"]:
            continue
        row = None
        for e in ("sqlite", "postgres"):
            rec = r["engines"][e]
            if rec["correct"]:
                continue
            k = kind_of(rec)
            kinds_div[e][k] += 1
            if k == "wrong_result":
                for fname, rx in FEATURES.items():
                    if rx.search(r["query"]):
                        feats[e][fname] += 1
            txt = (rec.get("error") or "").replace("\n", " ")[:200]
            if txt and len(examples[(e, k)]) < 2 and txt not in examples[(e, k)]:
                examples[(e, k)].append(txt)
            row = row or {"key": r["key"], "query": r["query"], "engines": {}}
            row["engines"][e] = {"kind": k, "error": rec.get("error"), "got_head": rec.get("rows_head")}
        if row:
            row["expected_head"] = gq[r["question_id"]]["rows"][:5]
            divergent.append(row)
    with open(os.path.join(a.out, "divergences.jsonl"), "w") as f:
        for row in divergent:
            f.write(json.dumps(row) + "\n")

    # Cross-check of the DuckDB leg against score.py, when given.
    xcheck = None
    if a.duckdb_scored:
        ref = {}
        for line in open(a.duckdb_scored):
            d = json.loads(line)
            if d["arm"] == "sql":
                ref[d["key"]] = d["correct"]
        diffs = [r["key"] for r in scored if r["key"] in ref and ref[r["key"]] != r["engines"]["duckdb"]["correct"]]
        xcheck = {"compared": sum(1 for r in scored if r["key"] in ref), "disagree": len(diffs), "keys": diffs[:20]}

    # Sensitivity: only the questions whose sql gold reproduces on that engine.
    sens = {}
    if gp is not None:
        for e in ("sqlite", "postgres"):
            ok_q = {q for q, v in gp.items() if v[e]["status"] == "OK"}
            sub = [r for r in scored if r["question_id"] in ok_q]
            sens[e] = {"questions_ok": len(ok_q), "n": len(sub), "correct": sum(r["engines"][e]["correct"] for r in sub),
                       "duckdb_correct_same_rows": sum(r["engines"]["duckdb"]["correct"] for r in sub)}

    json.dump({"run_dir": a.run_dir, "timeout_s": a.timeout, "engines": versions, "counts": loaded["counts"], "table": table,
               "portability": port, "kinds_all_failures": {e: dict(c) for e, c in kinds_all.items()},
               "kinds_duckdb_correct_failing": {e: dict(c) for e, c in kinds_div.items()},
               "wrong_result_features": {e: dict(c) for e, c in feats.items()}, "duckdb_crosscheck": xcheck,
               "sensitivity_gold_ok_only": sens, "unscored_questions": sorted(set(gq) - scorable)},
              open(os.path.join(a.out, "portability.json"), "w"), indent=1)

    L = ["# sql arm on DuckDB, SQLite and PostgreSQL", "",
         f"run dir: `{a.run_dir}`; statement timeout {a.timeout} s; read-only sessions; {len(scored)} scored generations "
         f"({len(recs) - len(scored)} on unscored questions).", "",
         "## Loaded rows (identical on the three engines, fingerprints equal)", "", "| table | rows |", "|---|---|"]
    L += [f"| {t} | {n} |" for t, n in loaded["counts"].items()]
    L += ["", "## Correct rate per engine (Wilson 95%)", "",
          "| model | engine | category | n | parse ok | exec ok | correct | pass@3 |", "|---|---|---|---|---|---|---|---|"]
    for key, c in table.items():
        m, e, cat = key.split("|")
        if c["n"]:
            L.append(f"| {m} | {e} | {cat} | {c['n']} | {100 * c['parse_ok'] / c['n']:.0f}% | {100 * c['exec_ok'] / c['n']:.0f}% | "
                     f"{fmt(c['correct'], c['n'])} | {fmt(c['pass3'], c['questions'])} |")
    L += ["", "## Portability: generations correct on DuckDB that are also correct elsewhere (Wilson 95%)", "",
          "| model | scope | correct on DuckDB | also on PostgreSQL | also on SQLite | also on both |", "|---|---|---|---|---|---|"]
    for key, v in port.items():
        m, scope = key.split("|")
        n = v["postgres"][0]
        if n:
            L.append(f"| {m} | {scope} | {n} | {fmt(v['postgres'][1], n)} | {fmt(v['sqlite'][1], n)} | {fmt(v['both'][1], n)} |")
    for title, kinds, cols in (("Failure kinds, every scored generation not correct on the engine", kinds_all, ENGINES),
                               ("Failure kinds, generations correct on DuckDB but not on the engine", kinds_div, ("sqlite", "postgres"))):
        names = sorted({k for e in cols for k in kinds[e]})
        L += ["", f"## {title}", "", "| kind | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        L += [f"| {k} | " + " | ".join(str(kinds[e].get(k, 0)) for e in cols) + " |" for k in names]
    L += ["", "Kinds come from the error text (patterns in `score_portability.py`); `wrong_result` ran without error and returned other rows."]
    L += ["", "## Error examples (correct on DuckDB, failing on the engine)", ""]
    for (e, k), ex in sorted(examples.items()):
        L += [f"- {e}, {k}: " + " / ".join(f"`{t}`" for t in ex)]
    L += ["", "## Features present in wrong-result divergences (not a diagnosis)", "",
          "| feature | sqlite | postgres |", "|---|---|---|"]
    L += [f"| {f} | {feats['sqlite'].get(f, 0)} | {feats['postgres'].get(f, 0)} |" for f in FEATURES]
    L += ["", "Full queries, errors and the first rows each engine returned: `divergences.jsonl`."]
    if sens:
        L += ["", "## Only questions whose sql gold reproduces on the engine", "", "| engine | questions | generations | correct |", "|---|---|---|---|"]
        L += [f"| {e} | {s['questions_ok']} | {s['n']} | {fmt(s['correct'], s['n'])} |" for e, s in sens.items()]
    else:
        L += ["", f"No `gold_portability.json` in {a.gold}: the gold-reproduction sensitivity table is skipped."]
    if xcheck:
        L += ["", f"DuckDB leg against score.py: {xcheck['disagree']} of {xcheck['compared']} generations disagree {xcheck['keys']}."]
    L += ["", f"engines: {json.dumps(versions)}"]
    open(os.path.join(a.out, "portability.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
