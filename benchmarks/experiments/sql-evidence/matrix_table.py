"""Turn matrix.jsonl into a client x step table (stdlib only): python matrix_table.py matrix.jsonl"""
import json
import sys

STEPS = ["connect", "list_tables", "list_columns", "select", "select_param", "join", "group_by"]
rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip().startswith("{")]
clients = []
for r in rows:
    if r["client"] not in clients:
        clients.append(r["client"])
print("| client | version | " + " | ".join(STEPS) + " |")
print("|---|---|" + "---|" * len(STEPS))
for c in clients:
    mine = {r["step"]: r for r in rows if r["client"] == c}
    ver = next(r["client_version"] for r in rows if r["client"] == c)
    print(f"| {c} | {ver} | " + " | ".join(("ok" if mine[s]["ok"] else "FAIL") if s in mine else "not run" for s in STEPS) + " |")
print()
for r in rows:
    if not r["ok"]:
        print(f"- {r['client']} / {r['step']}: {r['error']}")
