"""Execute every query on the arcadedb_sql_docs reference card on the pinned ArcadeDB engine.

  uv run --no-project --with pyyaml==6.0.3 python card_check.py --out DIR/card-check.jsonl [--timeout S] [--cpuset 14,15] [--mem 3g]

Host side: loads card_examples.yaml, checks that the card (prompts/arcadedb_sql_docs.txt) and the examples cannot drift
(every example query appears verbatim in the card, and the card's indented lines, the code lines, are exactly the example
queries: nothing on the card is unchecked, nothing checked is missing), then runs this same file inside the campaign image
`dbbench:arcadedb-${ARCADEDB_VERSION:-26.10.2}` (the image gold_check uses, started the way dockerrun.py starts it) with
`--inside`. A container that dies mid-run is recovered as in dockerrun.py (the example in flight is recorded as a failed
example with reason `engine_killed`, a fresh container runs the rest). Inside, it creates the toy schema and data of card_examples.yaml in ArcadeDB embedded, verifies the record counts,
runs each example and compares the result with the expected outcome (resultcmp rules).

Writes one JSON line per example, {id, ok_parse, ok_exec, rows_match, error, reason}, to --out (reason is null, or `engine_killed`). Exit status 1 when the card and the
examples drifted, or when any example fails to parse, execute or match. A failing example is fixed in the card, not waved
through (README); the failure detail is printed to the log.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CARD = os.path.join("prompts", "arcadedb_sql_docs.txt")
CODE_INDENT = "    "


def card_code_lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.startswith(CODE_INDENT) and ln.strip()]


def drift_errors(card_text, examples):
    errs = []
    queries = [e["query"] for e in examples]
    ids = [e["id"] for e in examples]
    if len(set(ids)) != len(ids):
        errs.append("duplicate example ids")
    if len(set(queries)) != len(queries):
        errs.append("duplicate example queries")
    code = card_code_lines(card_text)
    for e in examples:
        if CODE_INDENT + e["query"] + "\n" not in card_text:
            errs.append(f"{e['id']}: query not on the card as an indented line, verbatim: {e['query']}")
    for ln in code:
        if ln not in queries:
            errs.append(f"card code line without an example: {ln}")
    if len(code) != len(set(code)):
        errs.append("a code line appears twice on the card")
    return errs


# ------------------------------------------------------------------ host
def host(a):
    import yaml
    import dockerrun

    doc = yaml.safe_load(open(os.path.join(HERE, "card_examples.yaml")))
    examples = doc["examples"]
    errs = drift_errors(open(os.path.join(HERE, CARD)).read(), examples)
    if errs:
        sys.exit("card and card_examples.yaml drifted:\n  " + "\n  ".join(errs))
    out_path = os.path.abspath(a.out)
    work = os.path.splitext(out_path)[0] + "-work"
    os.makedirs(os.path.join(work, "home"), exist_ok=True)
    image = dockerrun.DEFAULT_IMAGES["arcadedb"]
    iid = dockerrun.image_id(image)
    by_id = {e["id"]: e for e in examples}

    def launch(attempt, remaining):
        sfx = "" if attempt == 0 else f".r{attempt}"
        part_path = os.path.join(work, f"part{sfx}.jsonl")
        if os.path.exists(part_path):
            os.remove(part_path)
        with open(os.path.join(work, f"examples{sfx}.json"), "w") as f:
            json.dump(dict(doc, examples=[by_id[j["key"]] for j in remaining]), f)
        name = f"sqlev-cardcheck-{os.getpid()}-{int(time.time())}-{attempt}"
        cmd = ["docker", "run", "--rm", "--name", name, "-m", a.mem, "--memory-swap", a.mem, "--cpuset-cpus", a.cpuset,
               "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/work/home",
               "-v", f"{HERE}:/s:ro", "-v", f"{work}:/work",
               image, "python", "/s/card_check.py", "--inside", "--examples", f"/work/examples{sfx}.json",
               "--out", f"/work/result{sfx}.json", "--partial", f"/work/part{sfx}.jsonl",
               "--timeout", str(a.timeout), "--heap", a.heap]
        log_path = os.path.join(work, f"container{sfx}.log")
        err_path = os.path.join(work, f"container{sfx}.err")
        with open(log_path, "w") as log, open(err_path, "w") as err:
            rc = subprocess.run(cmd, stdout=log, stderr=err).returncode
        return rc, dockerrun.tail_lines(err_path) or dockerrun.tail_lines(log_path), part_path

    def killed(job, rc, tail):
        k = dockerrun.killed_job_result(job, rc, tail)
        e = by_id[job["key"]]
        return {"key": e["id"], "id": e["id"], "query": e["query"], "ok_parse": False, "ok_exec": False, "rows_match": False,
                "error": k["error"], "expected": e["expect"], "got": None, "reason": "engine_killed"}

    header, results, stats = dockerrun.supervise([{"key": e["id"]} for e in examples], launch, "card check", killed)
    res = {"engine_version": header["engine_version"], "results": results}
    bad = 0
    with open(out_path, "w") as f:
        for r in res["results"]:
            line = {k: r[k] for k in ("id", "ok_parse", "ok_exec", "rows_match", "error")}
            line["reason"] = r.get("reason")
            f.write(json.dumps(line) + "\n")
            if not (r["ok_parse"] and r["ok_exec"] and r["rows_match"]):
                bad += 1
                print(f"FAIL {r['id']}: parse={r['ok_parse']} exec={r['ok_exec']} match={r['rows_match']} "
                      f"error={r['error']}\n  query: {r['query']}\n  expected: {r['expected']}\n  got: {r['got']}")
    print(f"engine {res['engine_version']} image {image} {iid}: {len(res['results'])} examples, {bad} failed, "
          f"{stats['restarts']} container restarts, {len(stats['engine_killed'])} killed; wrote {out_path}")
    sys.exit(1 if bad else 0)


# ------------------------------------------------------------------ inside the container
def inside(a):
    import tempfile

    import arcadedb_embedded as arcadedb
    import engine_runner
    import resultcmp

    doc = json.load(open(a.examples))
    db = arcadedb.create_database(os.path.join(tempfile.mkdtemp(prefix="sqlev_card_"), "db"),
                                  jvm_kwargs={"heap_size": a.heap})
    version = f"arcadedb {arcadedb.__version__}"
    for stmt in doc["schema"]:
        db.command("sql", stmt)
    with db.transaction():
        for stmt in doc["data"]:
            db.command("sql", stmt)
    for t, n in doc["setup_counts"].items():
        got = db.query("sql", f"SELECT count(*) AS n FROM {t}").to_json_list()[0]["n"]
        if got != n:
            sys.exit(f"setup: {t} has {got} records, expected {n}")

    def run(e):
        q, p = e["query"], e.get("params")
        if isinstance(p, list):
            return db.query("sql", q, *p).to_json_list()
        if isinstance(p, dict):
            return db.query("sql", q, p).to_json_list()
        return db.query("sql", q).to_json_list()

    results = []
    part = open(a.partial, "w") if a.partial else None

    def emit(obj):
        if part:
            part.write(json.dumps(obj) + "\n")
            part.flush()
            os.fsync(part.fileno())

    def record(r):
        results.append(r)
        emit(r)

    emit({"header": {"engine_version": version}})
    for e in doc["examples"]:
        r = {"id": e["id"], "key": e["id"], "query": e["query"], "ok_parse": False, "ok_exec": False, "rows_match": False, "error": None,
             "expected": e["expect"], "got": None}
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(run, e)
        try:
            recs = fut.result(timeout=a.timeout)
        except concurrent.futures.TimeoutError:
            r["ok_parse"], r["error"] = True, f"timeout after {a.timeout}s"
            ex.shutdown(wait=False)
            record(r)
            continue
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:600]
            r["ok_parse"] = not engine_runner.PARSE_RE.search(r["error"])
            ex.shutdown(wait=False)
            record(r)
            continue
        ex.shutdown(wait=False)
        r["ok_parse"] = r["ok_exec"] = True
        rows = []
        for rec in recs:
            if isinstance(rec, dict):
                rows.append([engine_runner.jsonable(v) for k, v in rec.items() if not str(k).startswith("@")])
            else:
                rows.append([engine_runner.jsonable(rec)])
        ex_ = e["expect"]
        if "n_rows" in ex_:
            r["got"] = len(recs)
            r["rows_match"] = len(recs) == ex_["n_rows"]
        elif "rows" in ex_:
            r["got"] = rows
            r["rows_match"] = resultcmp.rows_equal(ex_["rows"], rows, ex_.get("ordered", False))
        else:
            vals = [[engine_runner.jsonable(rec.get(ex_["field"]))] for rec in recs if isinstance(rec, dict)]
            r["got"] = [v[0] for v in vals]
            r["rows_match"] = len(vals) == len(recs) and resultcmp.rows_equal(
                [[v] for v in ex_["values"]], vals, ex_.get("ordered", False))
        record(r)
    with open(a.out, "w") as f:
        json.dump({"engine_version": version, "results": results}, f)
    sys.stdout.flush()
    os._exit(0)  # abandoned worker threads must not keep the container alive


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--cpuset", default="14,15")
    ap.add_argument("--mem", default="3g")
    ap.add_argument("--heap", default="1g")
    ap.add_argument("--inside", action="store_true")
    ap.add_argument("--examples")
    ap.add_argument("--partial", default=None)
    a = ap.parse_args()
    if a.inside:
        inside(a)
    else:
        host(a)


if __name__ == "__main__":
    main()
