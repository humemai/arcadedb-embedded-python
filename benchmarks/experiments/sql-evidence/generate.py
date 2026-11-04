"""Produce the generations for part C through the Anthropic Message Batches API.

  ANTHROPIC_API_KEY=... uv run --no-project --with anthropic python generate.py submit [--run-dir DIR] [--dry-run]
  ANTHROPIC_API_KEY=... uv run --no-project --with anthropic python generate.py collect BATCH_ID [--run-dir DIR]

submit   builds every request from the frozen prompts/<arm>.txt templates and questions.yaml and sends them as ONE
         batch: 2 models x 4 arms x 40 questions x 3 samples = 960 requests. Writes DIR/manifest.json (batch id,
         sha256 of every frozen file, models, request parameters, the custom_id map) and DIR/requests.jsonl (the
         exact prompts). --dry-run builds and writes both without calling the API (no key needed).
collect  retrieves the batch; if processing has not ended it prints the status and exits 0 (run it again later, there
         is no polling loop). When ended, it streams the results, keys them by custom_id through the manifest map
         (results arrive in any order) and writes DIR/generations.jsonl, one line per request:
         {model, arm, question_id, sample, query, stop_reason, usage, result_type, error}
         `query` is the concatenated text blocks exactly as returned; the scorer applies the extraction rule.

Request parameters (pre-registered, README "Models and sampling"): max_tokens 16000, output_config effort medium for
both models, no temperature/top_p/top_k, no prefill, thinking at the model default, no fallbacks. The key is read by
anthropic.Anthropic() from ANTHROPIC_API_KEY only; this script never prints, logs or writes it.
custom_id is `r0000`..`r0959` because the API restricts the characters of a custom_id; the map is in the manifest.
"""
import argparse
import datetime
import json
import os
import sys

import yaml

import resultcmp

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5"]
SAMPLES = 3
PARAMS = {"max_tokens": 16000, "output_config": {"effort": "medium"}}
# USD per million tokens (input, output) at standard prices; Batches halves both. An ESTIMATE basis only.
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
DEFAULT_RUN_ROOT = "/home/tk/build-scratch/sql-evidence"


def build_requests():
    qs = yaml.safe_load(open(os.path.join(HERE, "questions.yaml")))["questions"]
    templates = {arm: open(os.path.join(HERE, "prompts", f"{arm}.txt")).read() for arm in resultcmp.ARMS}
    reqs = []
    for model in MODELS:
        for arm in resultcmp.ARMS:
            for q in qs:
                prompt = templates[arm].replace("{question}", q["text"])
                for s in range(1, SAMPLES + 1):
                    reqs.append({"custom_id": f"r{len(reqs):04d}", "model": model, "arm": arm,
                                 "question_id": q["id"], "sample": s, "prompt": prompt})
    return reqs


def cmd_submit(a):
    run_dir = a.run_dir or os.path.join(DEFAULT_RUN_ROOT, "gen-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    mpath = os.path.join(run_dir, "manifest.json")
    if os.path.exists(mpath):
        sys.exit(f"{mpath} exists: a run directory holds one batch. Use a new --run-dir (a changed run is a new run).")
    reqs = build_requests()
    manifest = {"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "models": MODELS,
                "samples": SAMPLES, "params": PARAMS, "n_requests": len(reqs), "frozen_sha256": resultcmp.frozen_hashes(),
                "map": {r["custom_id"]: [r["model"], r["arm"], r["question_id"], r["sample"]] for r in reqs},
                "batch_id": None, "dry_run": bool(a.dry_run)}
    with open(os.path.join(run_dir, "requests.jsonl"), "w") as f:
        for r in reqs:
            f.write(json.dumps(r) + "\n")
    if a.dry_run:
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(f"dry run: {len(reqs)} requests written to {run_dir}; nothing sent")
        return
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from the environment only
    manifest["anthropic_sdk"] = anthropic.__version__
    batch = client.messages.batches.create(requests=[
        Request(custom_id=r["custom_id"],
                params=MessageCreateParamsNonStreaming(model=r["model"], messages=[{"role": "user", "content": r["prompt"]}],
                                                       **PARAMS))
        for r in reqs])
    manifest["batch_id"] = batch.id
    json.dump(manifest, open(mpath, "w"), indent=1)
    print(f"batch {batch.id} submitted: {len(reqs)} requests, status {batch.processing_status}; run dir {run_dir}")


def cmd_collect(a):
    import anthropic

    run_dir = a.run_dir
    mpath = os.path.join(run_dir, "manifest.json")
    manifest = json.load(open(mpath))
    if manifest.get("batch_id") != a.batch_id:
        sys.exit(f"batch id {a.batch_id} is not the one in {mpath}")
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(a.batch_id)
    if batch.processing_status != "ended":
        c = batch.request_counts
        print(f"not ended: status {batch.processing_status}, processing {c.processing}, succeeded {c.succeeded}, "
              f"errored {c.errored}, canceled {c.canceled}, expired {c.expired}")
        return
    cmap = manifest["map"]
    seen, tok = set(), {m: [0, 0] for m in manifest["models"]}
    out_path = os.path.join(run_dir, "generations.jsonl")
    with open(out_path, "w") as f:
        for res in client.messages.batches.results(a.batch_id):
            model, arm, qid, sample = cmap[res.custom_id]
            seen.add(res.custom_id)
            rec = {"model": model, "arm": arm, "question_id": qid, "sample": sample, "query": "", "stop_reason": None,
                   "usage": None, "result_type": res.result.type, "error": None}
            if res.result.type == "succeeded":
                msg = res.result.message
                rec["query"] = "".join(b.text for b in msg.content if b.type == "text")
                rec["stop_reason"] = msg.stop_reason
                rec["usage"] = msg.usage.model_dump()
                tok[model][0] += msg.usage.input_tokens
                tok[model][1] += msg.usage.output_tokens
            elif res.result.type == "errored":
                rec["error"] = res.result.error.type
            f.write(json.dumps(rec) + "\n")
    missing = sorted(set(cmap) - seen)
    print(f"wrote {out_path}: {len(seen)} of {len(cmap)} results; missing custom_ids: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    for m, (i, o) in tok.items():
        pi, po = PRICE[m]
        print(f"{m}: input {i} tokens, output {o} tokens, batch cost {(i * pi + o * po) / 1e6 * 0.5:.2f} USD (computed from usage at the list prices in this script)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--run-dir")
    s.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("collect")
    c.add_argument("batch_id")
    c.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    {"submit": cmd_submit, "collect": cmd_collect}[a.cmd](a)


if __name__ == "__main__":
    main()
