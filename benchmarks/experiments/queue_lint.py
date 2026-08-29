#!/usr/bin/env python3
"""Lint campaign queue scripts for the four ways they failed on 2026-08-29.

Every one of these cost a stage that reported ALL-DONE having done nothing, or
an idle machine with every script alive. They are mechanical and a reader cannot
be relied on to spot them, so they are checked instead of documented.

    python3 queue_lint.py ~/qB*.sh
    python3 queue_lint.py --host mini        # lint the scripts on the bench host

Exit 1 if anything is found.

THE FOUR CLASSES, and why each is not obvious:

1. CONTAINER PATH IN A HOST-SIDE COMMAND. /data, /lcdb, /pout and /work exist
   only inside a cell. runner.py bind-mounts them; a probe invoked directly on
   the host sees none of them. qBM used BENCH_SPARSE_DATA=/data/bigann and qBN
   used PROBE_DB=/lcdb/..., both copied from a runner.py line two stages up
   where they were correct.

2. BARE python3 FOR A DIRECT PROBE. runner.py cells carry their own deps; the
   host does not. Three stages called the system interpreter and died on
   ModuleNotFoundError in under two seconds, rc=1, stage ALL-DONE.

3. A WAIT CYCLE. Moving a stage to the end of the queue while others still wait
   ON it deadlocks the whole chain with every script alive, which reads as
   healthy from a distance. Three times, because each fix knew only one way of
   writing a wait: a standalone line, a line with two spaces before the
   redirect, and a name inside a `for q in ...` loop.

4. A PROBE WHOSE ARTIFACTS SAY "container". If results/<x>/*.json records
   host="container:...", that probe was designed to run inside the bench image
   with servers reachable. Running it host-side produces a DIFFERENT experiment
   -- e4 came back with 2 arms of 3, cpuset 0-19 instead of 0-11, 9 reps
   instead of 15 -- which is worse than not running it, because it looks like a
   result.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

CONTAINER_PATHS = ("/data/", "/lcdb", "/pout", "/work/")
# Commands that run INSIDE a cell, where container paths are correct.
CELL_RUNNERS = ("runner.py",)


def read_scripts(paths, host=None):
    out = {}
    if host:
        listing = subprocess.run(["ssh", host, "ls /home/tk/qB*.sh"],
                                 capture_output=True, text=True, timeout=60)
        for p in listing.stdout.split():
            body = subprocess.run(["ssh", host, f"cat {p}"],
                                  capture_output=True, text=True, timeout=60)
            out[Path(p).name] = body.stdout
    else:
        for p in paths:
            out[Path(p).name] = Path(p).read_text()
    return out


def logical_lines(body):
    """Join backslash continuations, keeping the FIRST physical line number.

    A runner.py invocation spans several lines, with the env vars above and the
    command below. Checking physically flags BENCH_SPARSE_DATA=/data/bigann as a
    host-side container path when the very next line is `python3 -u runner.py`,
    where it is correct. A linter that cries wolf is one people pass --skip to.
    """
    out, buf, start = [], "", 1
    for i, line in enumerate(body.splitlines(), 1):
        if not buf:
            start = i
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        out.append((start, buf + stripped))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def check_paths_and_python(name, body):
    problems = []
    for i, line in logical_lines(body):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        in_cell = any(r in line for r in CELL_RUNNERS)
        if not in_cell:
            for cp in CONTAINER_PATHS:
                if cp in line and "=" in line:
                    problems.append((i, f"container path {cp!r} in a host-side command"))
                    break
            # a direct probe invocation on the host
            m = re.search(r"(?<!/)\bpython3\b\s+-u\s+([a-z_]+\.py)", line)
            if m and m.group(1) not in CELL_RUNNERS:
                problems.append((i, f"bare python3 runs {m.group(1)} on the host; use $VENV/bin/python"))
    return problems


def check_cycles(scripts):
    """Wait edges from every form: standalone line, odd spacing, `for q in` loop."""
    edges = {}
    for name, body in scripts.items():
        stage = name[:-3]
        waits = set()
        for m in re.finditer(r"pgrep\s+-x\s+-f\s+[\"']/bin/bash /home/tk/(qB[A-Z]*)\.sh[\"']", body):
            waits.add(m.group(1))
        for m in re.finditer(r"(?m)^\s*for q in ([^\n;]*?);\s*do", body):
            waits.update(q for q in m.group(1).split() if q.startswith("qB"))
        waits.discard(stage)
        edges[stage] = waits
    cycles = []
    for a, waits in edges.items():
        for b in waits:
            if b in edges and a in edges[b]:
                pair = tuple(sorted((a, b)))
                if pair not in cycles:
                    cycles.append(pair)
    return edges, cycles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="*")
    ap.add_argument("--host")
    args = ap.parse_args()
    scripts = read_scripts(args.scripts, args.host)
    if not scripts:
        print("no scripts to lint", file=sys.stderr)
        return 2
    bad = 0
    for name in sorted(scripts):
        probs = check_paths_and_python(name, scripts[name])
        if probs:
            print(f"  {name}")
            for ln, msg in probs:
                print(f"    line {ln}: {msg}")
            bad += len(probs)
    edges, cycles = check_cycles(scripts)
    if cycles:
        print("\n  WAIT CYCLES (the chain will idle with every script alive):")
        for a, b in cycles:
            print(f"    {a} <-> {b}")
        bad += len(cycles)
    print(f"\n  {len(scripts)} scripts linted, {bad} problem(s)")
    if not bad:
        print("  wait graph:")
        for s in sorted(edges):
            print(f"    {s:<5} waits on: {' '.join(sorted(edges[s])) or '(nothing)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
