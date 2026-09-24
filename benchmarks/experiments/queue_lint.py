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
import os
import re
import subprocess
import sys
from pathlib import Path

CONTAINER_PATHS = ("/data/", "/lcdb", "/pout", "/work/")
# Commands that run INSIDE a cell, where container paths are correct.
CELL_RUNNERS = ("runner.py",)

# A host-side probe gets NOTHING: no bind mounts, no venv, no cpuset, no heap.
# runner.py gives each cell 0-11 and a tier-appropriate -Xmx; a probe launched
# straight from a queue script is compared against those numbers while running
# on all 20 cores with the JVM default heap. It has cost us three times: the e4
# decomposition (0-19, quarantined), qBN's 10M delta scan (no -Xmx, killed at
# rc=139 on OutOfMemoryError after an hour), and the jpype suite (0-19, and a
# July-stale class file so the Java arm never ran at all).
PROBE_INVOCATION = re.compile(
    r"""(?:\bpython3\b|/bin/python)["']?\s+-u\s+([a-z_0-9]+\.py)"""
    r"""|(?:^|\s|/|\./)(run_bench\.sh)""")
# Targets that establish their own envelope. Kept explicit rather than inferred:
# the linter cannot read the callee, so each entry is a claim someone checked.
PINS_INTERNALLY = {
    "run_bench.sh": "BENCH_CPUSET defaults to 0-11 inside run_bench.sh",
}
SETS_HEAP_INTERNALLY = {
    "run_bench.sh": "JFLAGS carries -Xmx4g",
}
PIN_TOKENS = ("taskset -c", "BENCH_CPUSET", "cpuset-cpus")

# `VAR=x taskset -c 0-11 cmd` is right; `taskset -c 0-11 VAR=x cmd` is not.
# Once taskset is the command the rest are its ARGUMENTS, so the shell never
# treats VAR=x as an assignment and taskset tries to exec a file by that name:
#   taskset: failed to execute PROBE_DB=/var/tmp/deltaprobe_1000000
# All four qBN arms died rc=127 in one second on 2026-08-29 this way.
TASKSET_THEN_ENV = re.compile(r"taskset\s+-c\s+\S+\s+(?:\\\s*)?([A-Za-z_][A-Za-z0-9_]*)=")
HEAP_TOKENS = ("-Xmx", "ARCADEDB_JVM_ARGS", "JAVA_OPTS", "PROBE_HEAP",
               "ARCADEDB_HEAP",   # ts_stride_probe
               "HEAP=")           # deployment_decomp_probe


def read_scripts(paths, host=None):
    out = {}
    if host:
        listing = subprocess.run(["ssh", host, "ls /home/tk/q[A-Z]*.sh"],
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
    # SHELL FUNCTIONS THAT WRAP A CELL RUNNER are cell-bound, and so are their
    # call sites. Without this the container-path rule cannot see through a
    # helper: October's stages call run_cell/run_overlay, which invoke
    # runner.py inside, and every BENCH_DENSE_DATA=/data/deep10m argument read
    # as a host-side command. Resolving the callee keeps the rule strong
    # rather than widening it -- a helper that does NOT contain a cell runner
    # still counts as host-side, which is the case the rule exists for.
    # Brace-DEPTH scan, not a regex: `say() { echo ...; }` closes on its own
    # line, and a non-greedy match to the next `^}` swallowed the function
    # AFTER it -- which made `say` look cell-bound and hid `run_overlay`
    # entirely. Getting this wrong in the permissive direction is the bad
    # direction, since it marks a host-side helper as safe.
    cell_fns = set()
    lines = body.splitlines()
    for idx, ln in enumerate(lines):
        m = re.match(r"^\s*([a-z_][a-z0-9_]*)\s*\(\)\s*\{", ln)
        if not m:
            continue
        depth, chunk = 0, []
        for ln2 in lines[idx:]:
            depth += ln2.count("{") - ln2.count("}")
            chunk.append(ln2)
            if depth <= 0:
                break
        if any(r in "\n".join(chunk) for r in CELL_RUNNERS):
            cell_fns.add(m.group(1))

    for i, line in logical_lines(body):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # An `export` that only sets variables executes nothing, so a container
        # path in it is not a host-side command; the line that USES it is what
        # the rule must judge, and a host-side probe is caught by its own check.
        if re.match(r"^export\s+[A-Za-z_][A-Za-z0-9_]*=", s) and "$(" not in s:
            continue
        # build_images.sh refuses a pre-release wheel unless BENCH_ALLOW_DEV=1,
        # which every commit-pinned campaign needs; qDJ aborted on its first
        # line without it (2026-09-12) and the next script in the chain
        # started at once because its wait target had vanished.
        # A PROCESS-NAME wait holds only while the predecessor's command line
        # is literally `/bin/bash /home/tk/qXX.sh`. Launched the usual way,
        # `setsid nohup bash ~/qXX.sh`, it reads `bash /home/tk/qXX.sh`, so
        # `pgrep -x -f` never matches and the loop falls straight through: the
        # stage starts at once, on top of the one it was meant to wait for
        # (BUGS F59). The ALL-DONE marker wait has no such dependency and is
        # the form every October stage uses. Still read as a wait edge by
        # check_cycles, so a cycle through it stays visible.
        if re.search(r"pgrep\s+-x\s+-f\s+[\"']/bin/bash /home/tk/q[A-Z]+[0-9]*\.sh", line):
            problems.append((i, "process-name wait (pgrep -x -f) holds only if the predecessor was launched "
                                "as exactly `/bin/bash /home/tk/qXX.sh`; wait on its ALL-DONE marker instead "
                                "(BUGS F59)"))
        if "build_images.sh" in line and "BENCH_ALLOW_DEV=1" not in line:
            problems.append((i, "build_images.sh without BENCH_ALLOW_DEV=1 refuses the commit-pinned wheel"))
        in_cell = any(r in line for r in CELL_RUNNERS) or any(
            re.search(rf"(?:^|\s|\|\||&&)\s*{re.escape(fn)}\b", line) for fn in cell_fns)
        if not in_cell:
            for cp in CONTAINER_PATHS:
                if cp in line and "=" in line:
                    problems.append((i, f"container path {cp!r} in a host-side command"))
                    break
            # a direct probe invocation on the host
            m = re.search(r"(?<!/)\bpython3\b\s+-u\s+([a-z_]+\.py)", line)
            if m and m.group(1) not in CELL_RUNNERS:
                problems.append((i, f"bare python3 runs {m.group(1)} on the host; use $VENV/bin/python"))

            # the envelope: a probe measured on a different machine shape than
            # the campaign is not comparable to it, however cleanly it exits
            te = TASKSET_THEN_ENV.search(line)
            if te:
                problems.append(
                    (i, f"taskset is followed by {te.group(1)}=...; the shell "
                        f"passes it to taskset as a filename (rc=127). Put "
                        f"every VAR=value BEFORE taskset."))

            pm = PROBE_INVOCATION.search(line)
            target = pm and (pm.group(1) or pm.group(2))
            if target and target not in CELL_RUNNERS and "lint: unpinned" not in line:
                if not any(t in line for t in PIN_TOKENS) and target not in PINS_INTERNALLY:
                    problems.append(
                        (i, f"host-side {target} carries no cpuset; runner.py cells get 0-11"))
                if not any(t in line for t in HEAP_TOKENS) and target not in SETS_HEAP_INTERNALLY:
                    problems.append(
                        (i, f"host-side {target} sets no heap; the JVM default is a quarter of RAM"))
    return problems


def check_parses(name, body):
    """Class 5: does the script parse at all?

    Added 2026-09-22 after this lint passed all seventeen stages while `bash
    -n` refused two of them. A generator change rendered a comment as a for
    loop's word list -- `for _pin in # (none); do` -- and the four classes
    below all looked at WHAT the script says rather than whether bash can read
    it. A stage that cannot parse dies on its first line, hours after the
    previous one hands over, and the lint that was supposed to catch exactly
    this said nothing.

    `bash -n` reads and parses without executing a single command, so it is
    safe to run on a queue script. It is the cheapest check here and the most
    fundamental, which is why it now runs first.
    """
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run(["bash", "-n", path],  # nosec B603 B607
                           capture_output=True, text=True, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return [(0, f"could not run `bash -n`: {exc.__class__.__name__}: {exc}")]
    finally:
        os.unlink(path)
    if r.returncode == 0:
        return []
    msg = (r.stderr or "").strip().splitlines()
    detail = msg[-1] if msg else f"bash -n exited {r.returncode}"
    ln = 0
    m = re.search(r"line (\d+):", " ".join(msg))
    if m:
        ln = int(m.group(1))
    return [(ln, f"the script does not PARSE, so it dies on its first line: {detail}")]


def check_cycles(scripts):
    """Wait edges from every form: standalone line, odd spacing, `for q in` loop."""
    edges = {}
    for name, body in scripts.items():
        stage = name[:-3]
        waits = set()
        for m in re.finditer(r"pgrep\s+-x\s+-f\s+[\"']/bin/bash /home/tk/(q[A-Z]+)\.sh[\"']", body):
            waits.add(m.group(1))
        # A stage may wait on the PREVIOUS STAGE'S MARKER instead of on its
        # process, which is the more robust form: `pgrep -f` can match the
        # waiting shell's own command line and loop forever (BUGS F59), and
        # the ALL-DONE line is the artifact that actually says a stage
        # finished. The wait graph has to see both, or a marker-waiting stage
        # reads as waiting on nothing and no cycle or orphan can be detected.
        for m in re.finditer(r"grep\s+-q\s+[\"'](q[A-Z]+[0-9]*) ALL-DONE[\"']", body):
            waits.add(m.group(1))
        for m in re.finditer(r"(?m)^\s*for q in ([^\n;]*?);\s*do", body):
            waits.update(q for q in m.group(1).split() if q.startswith("q") and q[1:2].isupper())
        waits.discard(stage)
        edges[stage] = waits

    # A wrapper that ends in `exec /bin/bash /home/tk/qXX.sh` IS qXX once it
    # starts: it holds the machine on qXX's behalf and other scripts wait on
    # the qXX name, not the wrapper's. Without this, qBNRUN -> qBH plus
    # qBH -> qBN reads as two unrelated edges when it is one deadlock.
    alias = {}
    for name, body in scripts.items():
        m = re.search(r"exec\s+/bin/bash\s+/home/tk/(q[A-Z]+)\.sh", body)
        if m and m.group(1) != name[:-3]:
            alias[name[:-3]] = m.group(1)
    for wrapper, target in alias.items():
        edges.setdefault(target, set())
        edges[target] |= edges.get(wrapper, set())

    cycles = []
    for a, waits in edges.items():
        for b in waits:
            b = alias.get(b, b)
            if b in edges and a in edges[b]:
                pair = tuple(sorted((a, b)))
                if pair not in cycles:
                    cycles.append(pair)
    return edges, cycles


def main():
    # THE LINT'S OWN TESTS RUN FIRST, on test_result_digest.py's reasoning: a
    # test that only runs when someone remembers is a comment. Twice on
    # 2026-09-19 this lint reported a queue it could not see -- a marker-waiting
    # stage read as waiting on nothing, and then a stage id with a digit did
    # the same -- and both times the scripts were correct while the lint was
    # blind, which is the worst shape a check can take.
    import test_queue_lint
    if test_queue_lint.main() != 0:
        print("REFUSING to lint: queue_lint's own tests fail", file=sys.stderr)
        return 1

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
        probs = check_parses(name, scripts[name]) + check_paths_and_python(name, scripts[name])
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
