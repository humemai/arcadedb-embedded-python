#!/usr/bin/env python3
"""Emit the stage scripts of the wheels-only post1 re-measure of the paper's ArcadeDB EMBEDDED cells (DECISIONS #293 to #306, CAMPAIGN section 7
row 93, humemai/arcadedb-embedded-python#581): the embedded arms only, build-only where the cell list says so, the post1 wheel pinned by name and
sha256, and nothing of it touching the live pass.

It does not template anything itself. Every stage is what make_2611_stages.stage_script writes (the TEMP GATE, the guards, the cap rule, the rep
gate), on a stage table narrowed to the embedded arms (the served arms never use the wheels: DECISIONS #297), then four exact-string changes
that each assert their anchor count, the way fourarm/run.sh patches its stages:

  1. the rows go to `runs_page_<pin>_2611_post1.jsonl` and the rep state to `rep-state-<instrument>-<pin>[-<build>]-post1.tsv`, so no row or
     state of the live pass is read, skipped or shadowed (rep_done would skip every cell already `ok`);
  2. `--build-only` is passed to the runner for the build-only cells (the runner refuses it for any other results file);
  3. BENCH_WHEEL_LABEL, BENCH_WHEEL_NAME and BENCH_WHEEL_SHA256 are exported, which makes the runner stamp them on every row (post1_rows.py);
  4. with --tree and --harness-sha, the live chain's own patches: run from a worktree at a pinned commit (no git pull), the idle-state hold, the
     turbo gate, and a deadline on every predecessor wait.

A wheel stage `<prefix>00` per chain puts the wheel into the worktree's dist/ by URL and sha256 and builds the arm image from it. The pair (the
server image, the engine) is NOT reinstalled: the engine is byte-identical (DECISIONS #297), and the stages read the pair that the pass installed.

THE CELL LIST is a TSV: lane workload scale backend class arm kind mode. `--write-cells FILE` writes the default (every embedded cell of the paper
profile: lane cells `build-only`, overlays `skip`); edit the mode column (build-only, full, skip) to say which cells are rerun and how. A
`build-only` row may replace only post1_rows.BUILD_FIELDS; a glue change that touches a query path (#321, #323) needs `full`.

Usage:
  python3 make_post1_rerun_stages.py --selftest
  python3 make_post1_rerun_stages.py --write-cells post1_cells.tsv
  python3 make_post1_rerun_stages.py --dry-run [--cells post1_cells.tsv] [--hours HOURS.tsv] --chains jvm,native --reps 3
  python3 make_post1_rerun_stages.py --out DIR --chains jvm,native --reps 3 --engine-commit <40 hex> \\
      --wheel-label 26.11.1.post1 --jvm-wheel-name arcadedb_jvm-26.11.1.post1-<tags>.whl --jvm-wheel-sha256 <64 hex> --jvm-wheel-url <https url> \\
      --native-wheel-name arcadedb-26.11.1.post1-<tags>.whl --native-wheel-sha256 <64 hex> --native-wheel-url <https url> \\
      --native-image-digest sha256:<64 hex> --tree-root ~/post1-wt --harness-sha <40 hex> [--cells post1_cells.tsv] [--after none]
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_2611_stages as M   # noqa: E402

POST_TAG = "post1"   # follows --wheel-label (set_post_tag): 26.11.1.post2 -> post2. The rows file, the rep state, the go file and the markers carry it.
ROWS_SUFFIX_POST1 = "_2611_post1"
STATE_SUFFIX = "-post1"


def set_post_tag(label):
    """The wheel label 26.11.1.postN names the rerun: rows go to runs_page_<pin>_2611_postN.jsonl, the rep state ends in -postN.tsv, so a postN rerun never
    reads or writes the files of another one (a reused rep-state file makes the rerun a no-op)."""
    global POST_TAG, ROWS_SUFFIX_POST1, STATE_SUFFIX
    m = re.search(r"\.(post\d+)$", label or "")
    if not m:
        raise SystemExit(f"REFUSING: --wheel-label {label!r} must end in .postN (26.11.1.post2)")
    POST_TAG, ROWS_SUFFIX_POST1, STATE_SUFFIX = m.group(1), f"_2611_{m.group(1)}", f"-{m.group(1)}"
MODES = ("build-only", "full", "skip")
CHAINS = ("jvm", "native")
DEFAULT_PREFIX = {"jvm": "qPV", "native": "qPN"}
CELL_HEADER = ["lane", "workload", "scale", "backend", "class", "arm", "kind", "mode"]


# ------------------------------------------------------------------------------------------------------ the cells
def embedded(backend):
    return "server" not in backend and "http_client" not in backend and "imgdefaults" not in backend


def base_specs():
    """The paper profile's ArcadeDB stage pieces (as the live chain's generator builds them), narrowed to the embedded arms."""
    profile = M.DEFAULT_PROFILE
    specs = M.subset_specs(["arcadedb"], list(M.profile_lanes(profile)), "biggest-last", M.profile_skip(profile), False)
    out = []
    for s in specs:
        arms = [b for b in s[8] if embedded(b)]
        if arms:
            p = M._piece(M._spec10(s), s[1], arms, s[4])
            out.append(p)
    return out


def default_cells():
    """[(Cell, mode)] for every embedded cell of the profile: lane cells build-only, overlays skip (an overlay times queries)."""
    cells = []
    for spec in base_specs():
        for c in M.stage_cells(spec):
            cells.append((c, "skip" if c.kind == "overlay" else "build-only"))
    return cells


def cell_row(c, mode):
    return [c.lane, c.workload, c.scale, c.backend, c.cls, c.arm or "-", c.kind, mode]


def write_cells(path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# post1 rerun cell list: mode is build-only, full or skip (make_post1_rerun_stages.py)\n")
        fh.write("\t".join(CELL_HEADER) + "\n")
        for c, mode in default_cells():
            fh.write("\t".join(cell_row(c, mode)) + "\n")


def read_cells(path):
    """{(lane, workload, scale, backend, class, arm, kind): mode}; every default cell must be named, none may be invented."""
    rows = [ln.rstrip("\n").split("\t") for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    if rows[0] != CELL_HEADER:
        raise SystemExit(f"{path}: header {rows[0]}, expected {CELL_HEADER}")
    got = {}
    for r in rows[1:]:
        if len(r) != 8 or r[7] not in MODES:
            raise SystemExit(f"{path}: bad row {r} (mode must be one of {MODES})")
        got[tuple(r[:7])] = r[7]
    want = {tuple(cell_row(c, "x")[:7]) for c, _m in default_cells()}
    if set(got) - want:
        raise SystemExit(f"{path}: cells the paper profile does not run as embedded cells: {sorted(set(got) - want)[:3]}")
    if want - set(got):
        raise SystemExit(f"{path}: {len(want - set(got))} cell(s) missing (name every cell, set mode skip to leave one out): {sorted(want - set(got))[:3]}")
    return got


def plan_pieces(modes):
    """[(piece spec, mode)] covering exactly the cells whose mode is not skip, one mode per piece. A stage piece keeps the table's shape
    (one lane, several workloads and one or more scales) when its cells are all wanted in one mode, else it is split down to (scale, workload,
    class) pieces, and the pieces' cells are proven equal to the wanted ones."""
    want = {k: m for k, m in modes.items() if m != "skip"}
    out, covered = [], set()
    for spec in base_specs():
        cells = M.stage_cells(spec)
        keys = [tuple(cell_row(c, "x")[:7]) for c in cells]
        used = {modes[k] for k in keys if modes[k] != "skip"}
        if not used:
            continue
        lane_cells_skipped = [k for k in keys if modes[k] == "skip" and k[6] == "lane"]
        if len(used) == 1 and not lane_cells_skipped:
            out.append((spec, next(iter(used))))
            covered |= {k for k in keys if modes[k] != "skip"}
            continue
        for mode in sorted(used):
            for sc in spec[4]:
                for wl in spec[3]:
                    for dur in (None, "relaxed", "strict"):
                        p = list(spec)
                        p[3], p[4], p[9] = [wl], [sc], dur
                        ks = [tuple(cell_row(c, "x")[:7]) for c in M.stage_cells(p)]
                        if dur is None and not ks:
                            continue
                        if ks and all(modes[k] == mode for k in ks):
                            if dur is None and any(k in covered for k in ks):
                                continue
                            if not any(k in covered for k in ks):
                                out.append((p, mode))
                                covered |= set(ks)
    # the overlay is part of a piece of an overlay lane unless the piece runs build-only: the stage text drops it for build-only pieces
    have = {tuple(cell_row(c, "x")[:7]) for p, m in out for c in M.stage_cells(p) if not (m == "build-only" and c.kind == "overlay")}
    if not set(want) <= have:
        raise SystemExit(f"internal: the pieces cover {len(have)} cells, the list wants {len(want)}: {sorted(set(want) - have)[:3]}")
    extra = {k for k in have if k not in want}
    if extra:
        raise SystemExit(f"internal: the pieces would also run {sorted(extra)[:3]}, which the cell list skips; split the list differently")
    return out


# --------------------------------------------------------------------------------------------------- the patches
def _sub(text, old, new, must=1, what=""):
    n = text.count(old)
    if n != must:
        raise SystemExit(f"generator drift: anchor {what or old[:60]!r} found {n}x, expected {must}; make_2611_stages.py changed, fix this script")
    return text.replace(old, new)


def post1_patch(text, label, wheel_name, wheel_sha, build_only, chain):
    text = _sub(text, "#!/bin/bash\n", "#!/bin/bash\n# " + POST_TAG.upper() + " RERUN (make_post1_rerun_stages.py): embedded arms only, wheel " + label + ", "
                + ("BUILD-ONLY cells" if build_only else "full cells") + ", rows in runs_page_<pin>" + ROWS_SUFFIX_POST1 + ".jsonl\n", what="shebang")
    text, n = re.subn(r"(REPSTATE=\$HOME/rep-state-[^\n]*?)\.tsv", r"\1" + STATE_SUFFIX + ".tsv", text)
    if n != 1:
        raise SystemExit(f"generator drift: REPSTATE line matched {n}x, expected 1")
    text = _sub(text, 'say "$ID START:', f'BUILD_ONLY_FLAG="{"--build-only" if build_only else ""}"   # post1_rows.py; the runner refuses it for any results file not named _postN\nsay "$ID START:', what="START")
    text = _sub(text, '--only-reps "$PASS" --reps "$REPS" --results-file "$RF" >> "$S" 2>&1',
                '--only-reps "$PASS" --reps "$REPS" --results-file "$RF" $BUILD_ONLY_FLAG >> "$S" 2>&1', what="run_cell runner line")
    text = _sub(text, "export BENCH_CPUSET=0-11 BENCH_GRAPH_SOURCE=ldbc\n",
                "export BENCH_CPUSET=0-11 BENCH_GRAPH_SOURCE=ldbc\n"
                f"export BENCH_WHEEL_LABEL={label} BENCH_WHEEL_NAME={wheel_name} BENCH_WHEEL_SHA256={wheel_sha}   # every row says which wheel it ran on (post1_rows.stamp_row)\n",
                what="cpuset export")
    return text


def tree_patch(text, tree, hsha, wheel_stage=False):
    """The live chain's patches (fourarm/run.sh patch_stage), for a stage run from a worktree at a pinned commit."""
    text = _sub(text, "REPO=$HOME/repos/humemai/arcadedb-embedded-python", f"REPO={tree}", what="REPO")
    pull = 'cd "$REPO" && git pull -q --ff-only || { say "$ID ABORT: pull"; exit 1; }'
    text = _sub(text, pull, f'cd "$REPO" && [ "$(git rev-parse HEAD)" = "{hsha}" ] || {{ say "$ID ABORT: worktree is not at the harness pin {hsha}"; exit 1; }}', what="git pull")
    text = _sub(text, "set -u\n", "set -u\nexport BENCH_CPU_DMA_LATENCY_US=${BENCH_CPU_DMA_LATENCY_US:-10}  # DECISIONS #234: unset = 0 us in the runner\n", what="set -u") \
        if not wheel_stage else text
    if not wheel_stage:
        trap = "trap 'echo \"$ID ALL-DONE\" >> \"$S\"' EXIT\n"
        text = _sub(text, trap, trap + '# TURBO GATE (the user, 2026-10-24; same text as fourarm/run.sh)\n'
                    '. "${AB2610:-$HOME/ab-2610}/lanes/turbo_gate.sh" 2>/dev/null || { say "$ID ABORT: ab-2610/lanes/turbo_gate.sh missing"; exit 1; }\n'
                    'turbo_gate "$ID" || exit 0\n', what="ALL-DONE trap")
    text = re.sub(r'while ! grep -qx "(q[A-Z]+\d+) ALL-DONE" "\$S" 2>/dev/null; do sleep 300; done',
                  r'_w0=$SECONDS; while ! grep -qx "\1 ALL-DONE" "$S" 2>/dev/null; do [ $((SECONDS - _w0)) -lt 600 ] || { say "$ID ABORT: marker \1 missing after 600 s"; exit 1; }; sleep 5; done', text)
    for leak in ("git pull", "$HOME/repos/humemai/arcadedb-embedded-python", "sleep 300; done"):
        if leak in text:
            raise SystemExit(f"{leak!r} still in a patched stage")
    return text


WHEEL_STAGE = '''#!/bin/bash
# {id}. {tag_up} wheel stage ({chain}): {wheel_name} into {tree}/bindings/python/dist by sha256, and the arm image built from it.
#
# GENERATED by make_post1_rerun_stages.py. The pair (server image, engine) is NOT reinstalled: the engine is byte-identical to 26.11.1
# (DECISIONS #297) and the lane stages read the pair the pass installed. Nothing here is found, everything is named.
set -u
ID={id}; S=$HOME/STATUS.txt; REPO={tree}; R=$REPO/benchmarks/experiments
say() {{ echo "[$(date -Is)] $*" >> "$S"; }}
{wait}
trap 'echo "$ID ALL-DONE" >> "$S"' EXIT
SHA={sha}; IMG=arcadedb-c25:${{SHA:0:9}}
WN={wheel_name}; WSHA={wheel_sha256}; WURL={wheel_url}
say "$ID START: {tag} wheel $WN ({chain}), pin ${{SHA:0:9}}"
cd "$REPO" && [ "$(git rev-parse HEAD)" = "{hsha}" ] || {{ say "$ID ABORT: worktree is not at the harness pin {hsha}"; exit 1; }}
docker image inspect "$IMG" > /dev/null 2>&1 || {{ say "$ID ABORT: no pair image $IMG (the pass installs it; this stage does not)"; exit 1; }}
mkdir -p "$REPO/bindings/python/dist"
[ -z "$(ls "$REPO"/bindings/python/dist/*.whl 2>/dev/null)" ] || {{ say "$ID ABORT: dist/ of this worktree is not empty; one wheel, or say which"; exit 1; }}
T=$(mktemp -d); curl -sfL -o "$T/$WN" "$WURL" && [ "$(sha256sum "$T/$WN" | cut -c1-64)" = "$WSHA" ] || {{ say "$ID ABORT: wheel download or sha256"; exit 1; }}
mv "$T/$WN" "$REPO/bindings/python/dist/" || {{ say "$ID ABORT: dist move"; exit 1; }}
say "$ID: dist/ holds $WN only"
cd "$R" && ARCADEDB_WHEEL="$REPO/bindings/python/dist/$WN" ARCADEDB_SERVER_IMAGE="$IMG" BENCH_ALLOW_DEV=0 bash build_images.sh arcadedb >> "$S" 2>&1 || {{ say "$ID ABORT: build_images.sh arcadedb"; exit 1; }}
say "$ID finished: the {chain} arm image carries $WN; the lane stages start"
'''


DRIVER = '''#!/usr/bin/env bash
# Sequential driver of the post1 rerun (make_post1_rerun_stages.py). One timed job at a time: each stage of ORDER.txt runs after the one before it.
# Needs the user's go as a FILE ($POST1_GO, default ~/POST1.go); removing it stops the run at the next stage boundary. Restartable: stages that
# finished are in done.list, and a restarted stage skips every repetition its rep-state file holds as clean.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); S=${POST1_STATUS:-$HOME/STATUS.txt}; GO=${POST1_GO:-$HOME/POST1.go}; DONE=$HERE/done.list
say() { echo "[$(date -Is)] $*" >> "$S"; }
[ -e "$GO" ] || { echo "no $GO: the go is a file only the user writes" >&2; exit 2; }
touch "$DONE"
while IFS=$'\\t' read -r item pass mode n; do
  [ -n "$item" ] || continue
  grep -qxF "$item" "$DONE" && continue
  [ -e "$GO" ] || { say "POST1 STOPPED before $item: $GO removed"; exit 3; }
  say "POST1 driver: $item (pass $pass, $mode)"
  bash "$HERE/$item.sh"
  tail -200 "$S" | grep -q "\\] ${item#*/} finished" || { say "POST1 STOPPED at $item: no finished line (see STATUS)"; exit 4; }
  echo "$item" >> "$DONE"
done < "$HERE/ORDER.txt"
say "POST1 driver finished: every stage of ORDER.txt ran"
'''


# ------------------------------------------------------------------------------------------------------ generation
def chain_pins(a, chain):
    name = getattr(a, f"{chain}_wheel_name")
    sha = getattr(a, f"{chain}_wheel_sha256")
    url = getattr(a, f"{chain}_wheel_url")
    if not (name and sha and url):
        raise SystemExit(f"REFUSING: the {chain} chain needs --{chain}-wheel-name, --{chain}-wheel-sha256 and --{chain}-wheel-url")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise SystemExit(f"REFUSING: --{chain}-wheel-sha256 must be 64 hex characters")
    pre = "arcadedb_jvm" if chain == "jvm" else "arcadedb"
    if not name.startswith(f"{pre}-{a.wheel_label}-") or not name.endswith(".whl"):
        raise SystemExit(f"REFUSING: {name} is not a {pre} wheel of {a.wheel_label} (the file name carries the version the stage pins)")
    if not (url.startswith("https://") or url.startswith("file:///")) or not url.endswith(name):
        raise SystemExit("REFUSING: the wheel URL must be https (or file:///) and end in the wheel's file name")
    pins = {"ARCADEDB_WHEEL": os.path.join("bindings", "python", "dist", name), "ARCADEDB_WHEEL_SHA256": sha,
            "ARCADEDB_SERVER_IMAGE": f"arcadedb-c25:{a.engine_commit[:9]}", "ARCADEDB_ENGINE_COMMIT": a.engine_commit,
            "wheel_name": name, "wheel_sha256": sha}
    if chain == "native":
        if not a.native_image_digest:
            raise SystemExit("REFUSING: the native chain needs --native-image-digest (the pass's own pin; the stage re-verifies the image)")
        pins["ARCADEDB_NATIVE_SERVER_IMAGE"] = f"arcadedata/arcadedb@{a.native_image_digest}"
    return pins, url


def emit_chain(a, chain, modes, out, first_after, start_index=0):
    """Write the chain's wheel stage and lane stages. Returns [(stage id, pass, mode, [cells])] in run order."""
    pins, url = chain_pins(a, chain)
    if chain == "native":
        if not hasattr(M, "CHAIN_BUILD"):
            raise SystemExit("REFUSING: this tree's make_2611_stages.py has no native chain (the four-arm generator, PR #554); generate from a tree that has it")
        M.CHAIN_BUILD = "native"
    elif hasattr(M, "CHAIN_BUILD"):
        M.CHAIN_BUILD = ""
    pieces = plan_pieces(modes)
    prefix = a.id_prefix_jvm if chain == "jvm" else a.id_prefix_native
    os.makedirs(out, exist_ok=True)
    order = []
    wid = f"{prefix}00"
    tree = os.path.join(a.tree_root or f"$HOME/{POST_TAG}-wt", chain)
    with open(os.path.join(out, f"{wid}.sh"), "w", encoding="utf-8") as fh:
        fh.write(WHEEL_STAGE.format(id=wid, chain=chain, tree=tree, wait=M._wait(first_after), sha=a.engine_commit, wheel_name=pins["wheel_name"],
                                    wheel_sha256=pins["wheel_sha256"], wheel_url=url, hsha=a.harness_sha or "UNPINNED", tag=POST_TAG, tag_up=POST_TAG.upper()))
    os.chmod(os.path.join(out, f"{wid}.sh"), 0o755)
    order.append((wid, 0, "wheel", []))
    total = len(pieces) * a.reps
    after = wid
    idx = 0
    saved_overlay, saved_suffix = dict(M.OVERLAY), M.ROWS_SUFFIX
    M.ROWS_SUFFIX = ROWS_SUFFIX_POST1
    try:
        for pass_no in range(1, a.reps + 1):
            for spec, mode in pieces:
                idx += 1
                sid = f"{prefix}{idx:02d}"
                title = (POST_TAG.upper() + " build-only, " if mode == "build-only" else POST_TAG.upper() + " ") + spec[1]
                s = list(spec)
                s[0], s[1] = sid, title
                M.OVERLAY.clear()
                if mode == "full":
                    M.OVERLAY.update(saved_overlay)
                params = dict(M.stage_params(a.reps), pass_no=pass_no)
                text = M.stage_script(idx - 1, total, tuple(s), after, pins, params)
                text = post1_patch(text, a.wheel_label, pins["wheel_name"], pins["wheel_sha256"], mode == "build-only", chain)
                if a.tree_root:
                    text = tree_patch(text, tree, a.harness_sha)
                p = os.path.join(out, f"{sid}.sh")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
                os.chmod(p, 0o755)
                order.append((sid, pass_no, mode, [c for c in M.stage_cells(tuple(s)) if not (mode == "build-only" and c.kind == "overlay")]))
                after = sid
    finally:
        M.OVERLAY.clear()
        M.OVERLAY.update(saved_overlay)
        M.ROWS_SUFFIX = saved_suffix
    return order


# ----------------------------------------------------------------------------------------------------- the estimate
def load_hours(path):
    """{(chain, lane, workload, scale, backend, class, arm, kind): (full hours per rep, build-only hours per rep)} from a TSV with the header
    chain lane workload scale backend class arm kind h_full h_build. ESTIMATES: scheduling facts from the mini's STATUS file, never timings."""
    rows = [ln.rstrip("\n").split("\t") for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    if rows[0][:10] != ["chain"] + CELL_HEADER[:7] + ["h_full", "h_build"]:
        raise SystemExit(f"{path}: header {rows[0]}")
    return {tuple(r[:8]): (float(r[8]), float(r[9])) for r in rows[1:]}


def estimate(order, chain, reps, hours):
    """[(stage id, pass, mode, hours, priced, unpriced)]; hours for ONE pass of a stage, so n repetitions are the sum over passes."""
    out = []
    for sid, pass_no, mode, cells in order:
        if mode == "wheel":
            continue
        h, n, miss = 0.0, 0, []
        for c in cells:
            v = hours.get((chain, c.lane, c.workload, c.scale, c.backend, c.cls, c.arm or "-", c.kind))
            if v is None:
                miss.append(c.label)
                continue
            h += v[1] if mode == "build-only" else v[0]
            n += 1
        out.append((sid, pass_no, mode, h, n, miss))
    return out


def print_dry_run(a, modes, hours):
    for chain in a.chains:
        order = emit_chain(a, chain, modes, tempfile.mkdtemp(prefix="post1dry-"), M._after_arg(a.after) if hasattr(M, "_after_arg") else None) \
            if a.wheel_label and a.engine_commit and getattr(a, f"{chain}_wheel_name") else dry_order(a, chain, modes)
        print(f"\n== {chain} chain: {len(order) - 1} lane stage(s), reps {a.reps}")
        est = estimate(order, chain, a.reps, hours) if hours else []
        by_id = {e[0]: e for e in est}
        for sid, pass_no, mode, cells in order:
            if mode == "wheel":
                print(f"  {sid}  wheel stage (download by sha256, build the arm image)")
                continue
            e = by_id.get(sid)
            print(f"  {sid}  pass {pass_no}  {mode:10s} {len(cells):2d} job(s)  " + (f"{e[3]:6.2f} h" if e else "") + "  " + ", ".join(sorted({f'{c.lane}/{c.scale}/{c.workload}' for c in cells}))[:90])
        if est:
            tot = sum(e[3] for e in est)
            miss = sorted({m for e in est for m in e[5]})
            print(f"  ESTIMATE {chain}: {tot:.1f} h for {a.reps} repetition(s), summed over the stages above (setup excluded; not a measurement)"
                  + (f"; {len(miss)} unpriced: {miss[:3]}" if miss else ""))


def dry_order(a, chain, modes):
    """The run order without writing any script (no pins needed): [(id, pass, mode, cells)]."""
    prefix = a.id_prefix_jvm if chain == "jvm" else a.id_prefix_native
    pieces = plan_pieces(modes)
    order, idx = [(f"{prefix}00", 0, "wheel", [])], 0
    for pass_no in range(1, a.reps + 1):
        for spec, mode in pieces:
            idx += 1
            order.append((f"{prefix}{idx:02d}", pass_no, mode, [c for c in M.stage_cells(tuple(spec)) if not (mode == "build-only" and c.kind == "overlay")]))
    return order


# ---------------------------------------------------------------------------------------------------------- selftest
def selftest():
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)

    modes = {tuple(cell_row(c, "x")[:7]): m for c, m in default_cells()}
    check("22 default cells", len(modes) == 22)
    check("2 overlays skipped", sum(1 for k, m in modes.items() if m == "skip") == 2 and all(k[6] == "overlay" for k, m in modes.items() if m == "skip"))
    check("embedded arms only", all(embedded(k[3]) for k in modes))
    pieces = plan_pieces(modes)
    jobs = [c for p, m in pieces for c in M.stage_cells(p) if c.kind == "lane"]
    check("20 build-only lane jobs per pass", len(jobs) == 20 and all(m == "build-only" for _p, m in pieces))
    a = argparse.Namespace(reps=2, wheel_label="26.11.1.post1", engine_commit="a" * 40, harness_sha="b" * 40, tree_root="/home/x/post1-wt", after="none",
                           id_prefix_jvm="qPV", id_prefix_native="qPN", jvm_wheel_name="arcadedb_jvm-26.11.1.post1-py3-none-manylinux_2_28_x86_64.whl",
                           jvm_wheel_sha256="c" * 64, jvm_wheel_url="https://example.invalid/arcadedb_jvm-26.11.1.post1-py3-none-manylinux_2_28_x86_64.whl",
                           native_wheel_name="arcadedb-26.11.1.post1-py3-none-manylinux_2_28_x86_64.whl", native_wheel_sha256="d" * 64,
                           native_wheel_url="https://example.invalid/arcadedb-26.11.1.post1-py3-none-manylinux_2_28_x86_64.whl",
                           native_image_digest="sha256:" + "e" * 64)
    d = tempfile.mkdtemp(prefix="post1sf-")
    order = emit_chain(a, "jvm", modes, d, None)
    check("jvm: wheel stage + 8 pieces x 2 passes", len(order) == 1 + len(pieces) * 2)
    for sid, pass_no, mode, cells in order:
        text = open(os.path.join(d, sid + ".sh"), encoding="utf-8").read()
        rc = subprocess.run(["bash", "-n", os.path.join(d, sid + ".sh")], capture_output=True).returncode
        check(f"bash -n {sid}", rc == 0)
        if mode == "wheel":
            check("wheel stage names the sha", "c" * 64 in text and "arcadedb_jvm-26.11.1.post1" in text)
            continue
        m = re.search(r'^BACKENDS="([^"]*)"', text, re.M)
        check(f"{sid}: embedded arms only", bool(m) and all(embedded(b) for b in m.group(1).split()))
        check(f"{sid}: build-only flag", 'BUILD_ONLY_FLAG="--build-only"' in text and "$BUILD_ONLY_FLAG" in text)
        check(f"{sid}: post1 rows file", "_2611_post1.jsonl" in text and 'RF="runs_page_${PIN}_2611.jsonl"' not in text)
        check(f"{sid}: post1 rep state", "-post1.tsv" in text)
        check(f"{sid}: wheel label exported", "BENCH_WHEEL_LABEL=26.11.1.post1" in text and "BENCH_WHEEL_SHA256=" + "c" * 64 in text)
        check(f"{sid}: no overlay in a build-only stage", "run_overlay \"" not in text)
        check(f"{sid}: temp gate and rep gate kept", "temp_gate " in text and "rep_gate " in text)
        check(f"{sid}: worktree, no pull", "git pull" not in text and ("REPO=/home/x/post1-wt/jvm" in text) and "turbo_gate" in text)
        check(f"{sid}: pass {pass_no}", f"PASS={pass_no} " in text or f"PASS={pass_no}\n" in text)
    dr = os.path.join(d, "run_post1.sh")
    with open(dr, "w", encoding="utf-8") as fh:
        fh.write(DRIVER)
    check("driver: bash -n", subprocess.run(["bash", "-n", dr], capture_output=True).returncode == 0)
    check("driver: reads a tab", "IFS=$'\\t'" in DRIVER)
    # the tag follows the label: a post2 rerun writes post2 names and no post1 name (a reused rep-state file would make it a no-op)
    set_post_tag("26.11.1.post2")
    a2 = argparse.Namespace(**{**vars(a), "wheel_label": "26.11.1.post2", "tree_root": "/home/x/post2-wt",
                               "jvm_wheel_name": a.jvm_wheel_name.replace("post1", "post2"), "jvm_wheel_url": a.jvm_wheel_url.replace("post1", "post2")})
    d2 = tempfile.mkdtemp(prefix="post2sf-")
    emit_chain(a2, "jvm", modes, d2, None)
    t2 = {f: open(os.path.join(d2, f), encoding="utf-8").read() for f in sorted(os.listdir(d2)) if f.endswith(".sh")}
    check("post2: no post1 name in any stage", len(t2) == 1 + len(pieces) * 2 and not any("post1" in t.lower().replace("post1_rows", "").replace("make_post1_rerun_stages", "") for t in t2.values()))   # module names, not tags
    check("post2: rows file, rep state, label", all("_2611_post2.jsonl" in t and "-post2.tsv" in t and "BENCH_WHEEL_LABEL=26.11.1.post2" in t for f, t in t2.items() if f != "qPV00.sh"))
    check("post2: names and tree", POST_TAG == "post2" and "REPO=/home/x/post2-wt/jvm" in t2["qPV01.sh"] and "POST2 wheel stage" in t2["qPV00.sh"])
    set_post_tag("26.11.1.post1")
    import engine_pin
    check("engine_pin.jar_pin", engine_pin.jar_pin("26.11.1.post1") == "26.11.1" and engine_pin.jar_pin("26.11.1") == "26.11.1" and engine_pin.jar_pin("26.11.1.dev0") == "26.11.1.dev0")
    # a cell list with one full cell and a skipped lane cell is split exactly
    m2 = dict(modes)
    k1 = next(k for k in m2 if k[0] == "l1tpc" and k[2] == "tpch1" and k[1] == "oltp" and k[4] == "strict")
    m2[k1] = "skip"
    k2 = next(k for k in m2 if k[0] == "l2" and k[2] == "sf1" and k[1] == "oltp" and k[4] == "relaxed")
    m2[k2] = "full"
    p2 = plan_pieces(m2)
    got = collections.Counter()
    for p, m in p2:
        for c in M.stage_cells(p):
            if not (m == "build-only" and c.kind == "overlay"):
                got[(tuple(cell_row(c, "x")[:7]), m)] += 1
    check("split: no skipped cell runs", all(k != k1 for (k, _m) in got))
    check("split: the full cell runs full, once", got[(k2, "full")] == 1)
    check("split: every other lane cell build-only once", sum(1 for (k, m), n in got.items() if m == "build-only" and n == 1 and k[6] == "lane") == 18)
    # a drifted anchor is refused, not silently skipped
    try:
        post1_patch("#!/bin/bash\nnothing\n", "26.11.1.post1", "x.whl", "0" * 64, True, "jvm")
        check("drift refused", False)
    except SystemExit:
        pass
    # the cost table: a priced and an unpriced cell
    hrs = {("jvm", c.lane, c.workload, c.scale, c.backend, c.cls, c.arm or "-", c.kind): (1.0, 0.25) for c, _m in default_cells()}
    est = estimate(order, "jvm", 2, hrs)
    check("estimate: build-only priced at h_build", abs(sum(e[3] for e in est) - 0.25 * 20 * 2) < 1e-9 and all(not e[5] for e in est))
    for f in fails:
        print("FAIL", f)
    print(f"make_post1_rerun_stages selftest: {'FAILED' if fails else 'ok'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write-cells", metavar="FILE", help="write the default cell list and stop")
    ap.add_argument("--cells", metavar="FILE", help="the cell list (default: every embedded cell, build-only)")
    ap.add_argument("--dry-run", action="store_true", help="print the stage list and the estimate; write nothing")
    ap.add_argument("--hours", metavar="TSV", help="per-cell hours for the estimate (chain lane workload scale backend class arm kind h_full h_build)")
    ap.add_argument("--chains", default="jvm,native")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out")
    ap.add_argument("--after", default="none")
    ap.add_argument("--engine-commit", default="")
    ap.add_argument("--wheel-label", default="", help="the release the wheels carry, e.g. 26.11.1.post2; its .postN names the rows file, the rep state, the go file and the driver")
    for ch in CHAINS:
        ap.add_argument(f"--{ch}-wheel-name", default="")
        ap.add_argument(f"--{ch}-wheel-sha256", default="")
        ap.add_argument(f"--{ch}-wheel-url", default="")
    ap.add_argument("--native-image-digest", default="")
    ap.add_argument("--tree-root", default="", help="directory of the pinned worktrees (<root>/jvm, <root>/native); without it the stages keep git pull")
    ap.add_argument("--harness-sha", default="")
    ap.add_argument("--id-prefix-jvm", default=DEFAULT_PREFIX["jvm"])
    ap.add_argument("--id-prefix-native", default=DEFAULT_PREFIX["native"])
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.wheel_label:
        set_post_tag(a.wheel_label)
    if a.selftest:
        return selftest()
    if a.write_cells:
        write_cells(a.write_cells)
        print(f"wrote {a.write_cells}")
        return 0
    a.chains = [c for c in a.chains.split(",") if c]
    if any(c not in CHAINS for c in a.chains) or not 1 <= a.reps <= 3:
        raise SystemExit("--chains is jvm and/or native; --reps is 1 to 3 (the n=4 and n=5 passes are dropped, 2026-11-14)")
    modes = read_cells(a.cells) if a.cells else {tuple(cell_row(c, "x")[:7]): m for c, m in default_cells()}
    hours = load_hours(a.hours) if a.hours else None
    if a.dry_run:
        print_dry_run(a, modes, hours)
        return 0
    if not (a.out and a.engine_commit and a.wheel_label and re.fullmatch(r"[0-9a-f]{40}", a.engine_commit)):
        raise SystemExit("REFUSING: --out, --wheel-label and the full 40-character --engine-commit are required")
    if a.tree_root and not re.fullmatch(r"[0-9a-f]{40}", a.harness_sha):
        raise SystemExit("REFUSING: --tree-root needs the full 40-character --harness-sha the worktrees are at")
    after = M._after_arg(a.after)
    allorder = []
    for chain in a.chains:   # one chain after the other, each stage waiting for its predecessor's marker: one timed job at a time
        d = os.path.join(a.out, chain)
        order = emit_chain(a, chain, modes, d, after)
        allorder.append((chain, order))
        after = order[-1][0]
    with open(os.path.join(a.out, "ORDER.txt"), "w", encoding="utf-8") as fh:
        for chain, order in allorder:
            for sid, pass_no, mode, cells in order:
                fh.write(f"{chain}/{sid}\t{pass_no}\t{mode}\t{len(cells)}\n")
    drv = f"run_{POST_TAG}.sh"
    with open(os.path.join(a.out, drv), "w", encoding="utf-8") as fh:
        fh.write(DRIVER.replace("POST1", POST_TAG.upper()).replace("post1 rerun", POST_TAG + " rerun"))
    os.chmod(os.path.join(a.out, drv), 0o755)
    print(f"wrote {sum(len(o) for _c, o in allorder)} stage script(s) under {a.out}; run order in ORDER.txt, driver {drv} (needs the go file ~/{POST_TAG.upper()}.go)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
