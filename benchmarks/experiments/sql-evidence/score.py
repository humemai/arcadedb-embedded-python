"""Execute the generated queries on each arm's engine and score them.

  uv run --no-project python score.py --run-dir DIR --gold GOLD_DIR --data ~/bench-data/ldbc/sf1 --out OUT_DIR

Reads DIR/generations.jsonl ({model, arm, question_id, sample, query, stop_reason, usage, result_type, error}, written by
generate.py collect) and DIR/manifest.json, and GOLD_DIR/gold_rows.json (gold_check.py). Refuses to run when a frozen file
(questions.yaml, prompts/*.txt) no longer matches the hashes in the manifest: a change after the first generation is a new run.
Arms are resultcmp.GEN_ARMS: arcadedb_sql_docs runs on the ArcadeDB engine as an arcadedb_sql statement and is scored against
the same reference rows (no gold of its own).
A query whose engine container is killed while it runs (see dockerrun.py: DuckPGQ out of memory on DuckDB 2.0.0, or any OOM kill) is
recorded with reason `engine_killed` and counts as a failed generation (its query is the cause: parse, exec and correct false);
the engine is restarted and every other query is scored normally. Restart counts and killed keys go to table.json `engines`.
Per generation: the extraction rule (resultcmp.extract_query), then parse_ok / exec_ok / correct. A generation that did not
succeed (result_type not succeeded, stop_reason refusal or max_tokens, empty text) is a failed generation: parse, exec and
correct all false. A question is scored only when every non-null gold of that question verified in gold_check; the rest are
listed as unscored. Questions whose gold is null for an arm are still asked and scored against the language-independent
reference rows (kind: author nulls say the author could not write the gold, not that the language cannot express it).
Writes OUT_DIR/scored.jsonl, table.json and table.md.
Statistics: correct rate with a 95% Wilson interval per model x arm x category. The three samples of a question are not
independent, so the table also gives pass@3 (a question counts when any of its samples is correct) with its own interval,
over questions.
"""
import argparse
import collections
import json
import os
import sys

import dockerrun
import resultcmp

HERE = os.path.dirname(os.path.abspath(__file__))
CAT_ORDER = ["single", "join", "multi_join", "graph"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--person-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--cpuset", default="14,15")
    ap.add_argument("--mem", default="4g")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

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

    gens = [json.loads(line) for line in open(os.path.join(a.run_dir, "generations.jsonl"))]
    recs, jobs = [], {"duckdb": [], "arcadedb": []}
    for g in gens:
        key = f"{g['model']}::{g['arm']}::{g['question_id']}::{g['sample']}"
        r = {"key": key, "model": g["model"], "arm": g["arm"], "question_id": g["question_id"], "sample": g["sample"],
             "category": gq[g["question_id"]]["category"], "scored": g["question_id"] in scorable,
             "stop_reason": g["stop_reason"], "query": resultcmp.extract_query(g["query"]),
             "parse_ok": False, "exec_ok": False, "correct": False, "error": None, "reason": None}
        if g["result_type"] != "succeeded" or g["stop_reason"] in ("refusal", "max_tokens") or not r["query"]:
            r["error"] = f"failed generation: result_type={g['result_type']} stop_reason={g['stop_reason']}"
        elif r["scored"]:
            jobs[resultcmp.ENGINE_OF_ARM[g["arm"]]].append({"key": key, "arm": resultcmp.GOLD_ARM[g["arm"]], "query": r["query"]})
        recs.append(r)
    by_key = {r["key"]: r for r in recs}
    versions = {}
    for engine, js in jobs.items():
        if not js:
            continue
        out = dockerrun.run_engine(engine, js, a.data, a.out, f"score-{engine}", a.person_limit, a.timeout, a.cpuset, a.mem)
        versions[engine] = {k: out[k] for k in ("engine_version", "engine_versions", "image", "image_id", "restarts",
                                                "engine_killed")}
        for res in out["results"]:
            r = by_key[res["key"]]
            g = gq[r["question_id"]]
            r["parse_ok"], r["exec_ok"], r["error"] = res["parse_ok"], res["exec_ok"], res["error"]
            r["reason"] = res.get("reason")
            r["correct"] = bool(res["exec_ok"] and resultcmp.rows_equal(
                g["rows"], res["rows"], g["ordered"], tol["float_abs"], tol["float_rel"], res["truncated"]))
    with open(os.path.join(a.out, "scored.jsonl"), "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    def cell(rs):
        n = len(rs)
        k = sum(r["correct"] for r in rs)
        lo, hi = resultcmp.wilson(k, n)
        qs = collections.defaultdict(list)
        for r in rs:
            qs[r["question_id"]].append(r["correct"])
        kq = sum(any(v) for v in qs.values())
        plo, phi = resultcmp.wilson(kq, len(qs))
        return {"n": n, "parse_ok": sum(r["parse_ok"] for r in rs), "exec_ok": sum(r["exec_ok"] for r in rs), "correct": k,
                "correct_lo": lo, "correct_hi": hi, "questions": len(qs), "pass3": kq, "pass3_lo": plo, "pass3_hi": phi}

    table = {}
    for model in manifest["models"]:
        for arm in resultcmp.GEN_ARMS:
            rows = [r for r in recs if r["model"] == model and r["arm"] == arm and r["scored"]]
            table[f"{model}|{arm}|all"] = cell(rows)
            for cat in CAT_ORDER:
                table[f"{model}|{arm}|{cat}"] = cell([r for r in rows if r["category"] == cat])
    unscored = sorted(set(gq) - scorable)
    json.dump({"engines": versions, "unscored_questions": unscored, "table": table}, open(os.path.join(a.out, "table.json"), "w"), indent=1)

    def pct(k, n):
        return f"{100 * k / n:.0f}%" if n else "-"

    lines = ["| model | arm | category | n | parse ok | exec ok | correct (95% Wilson) | questions | pass@3 (95% Wilson) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for key, c in table.items():
        model, arm, cat = key.split("|")
        if c["n"] == 0:
            lines.append(f"| {model} | {arm} | {cat} | 0 | - | - | - | 0 | - |")
            continue
        lines.append(f"| {model} | {arm} | {cat} | {c['n']} | {pct(c['parse_ok'], c['n'])} | {pct(c['exec_ok'], c['n'])} | "
                     f"{c['correct']}/{c['n']} = {100 * c['correct'] / c['n']:.1f}% [{100 * c['correct_lo']:.1f}, {100 * c['correct_hi']:.1f}] | "
                     f"{c['questions']} | {c['pass3']}/{c['questions']} [{100 * c['pass3_lo']:.1f}, {100 * c['pass3_hi']:.1f}] |")
    n_killed = sum(1 for r in recs if r["reason"] == "engine_killed")
    lines += ["", f"unscored questions (a gold did not verify): {unscored}", f"engines: {json.dumps(versions)}",
              f"generations recorded as engine_killed (failed generations): {n_killed}"]
    open(os.path.join(a.out, "table.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
