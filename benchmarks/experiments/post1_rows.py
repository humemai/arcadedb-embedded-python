#!/usr/bin/env python3
"""Rows of a wheels-only re-measure (26.11.1.post1): build-only mode, the wheel label, and the per-cell choice of ONE wheel.

WHY (DECISIONS #292 to #299, CAMPAIGN section 7 row 93, humemai/arcadedb-embedded-python#581). A wheels-only post1 changes the Python and
native glue of the ArcadeDB bindings, not the engine. The paper cells whose figures it can move are rerun on it, and the user's rule is that
the post1 rows OVERRIDE the 26.11.1 rows of the cells that are rerun, with ALL repetitions of a cell from ONE wheel. This module makes that a
property of the data instead of a thing somebody remembers:

  * BUILD-ONLY ROWS. `runner.py --build-only` (env BENCH_BUILD_ONLY=1) makes a lane stop right after `build()` and write a row stamped
    `row_kind = "build_only"`. The lane's own `main()` calls `finish_build_only()` at the one place where the load and the index are done and
    no timed workload has started. The row holds the build figures and nothing else, so it is NOT a cell and can never stand in for one.
  * THE WHEEL LABEL. A row already says `engine_version` and `engine_backend` ("native" or "jvm"). What it did not say is WHICH FILE: the
    candidate JVM wheel of the post1 glue A/B says 26.11.1 in its metadata. A stage that opts in (exports BENCH_WHEEL_LABEL and
    BENCH_WHEEL_SHA256) makes the runner stamp `wheel_label`, `wheel_name` and `wheel_sha256` on its rows. Rows without them (every 26.11.1
    row already on the mini) are labelled by their `engine_version`.
  * THE CHOICE. `resolve()` takes rows from the live pass and from the rerun and returns, for every in-process ArcadeDB cell, the rows of one
    wheel: the newest wheel that has rows for the cell, and only when that set is complete at the required repetitions. A cell that would mix
    wheels, or whose newer wheel is short of repetitions, is a PROBLEM (the caller exits nonzero), never a silent fall back.

WHAT A BUILD-ONLY ROW MAY REPLACE, and what it must not. It replaces, in the 26.11.1 row of the same cell and repetition, only BUILD_FIELDS:
the load and index seconds and the facts about the load transport. Every timed workload figure of the cell stays at its 26.11.1 value, and
the memory, disk and cpu figures of the build window are carried beside them as `build_window_*`, never over them (the full row's figures
cover the whole container life, the build-only row's only the build). The replacement is legitimate only for glue changes that do not touch a
query path (DECISIONS #299: #318, #324, #325; not #321 or #323): whether a cell qualifies is the owner's call, written in the cell list.

DEFAULTS ARE TODAY'S BEHAVIOUR. With none of the new environment variables set, nothing here changes a row, a lane or a stage.

Usage:
  python3 post1_rows.py --selftest
  python3 post1_rows.py resolve --reps 3 --out resolved.jsonl LIVE.jsonl POST1.jsonl     # prints the decision per cell, nonzero on a problem
  python3 post1_rows.py strip --label 26.11.1.post1 results/runs.jsonl                    # rollback: delete the post1 rows by wheel label
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

BUILD_ONLY_ENV = "BENCH_BUILD_ONLY"
WHEEL_LABEL_ENV = "BENCH_WHEEL_LABEL"
WHEEL_SHA256_ENV = "BENCH_WHEEL_SHA256"
WHEEL_NAME_ENV = "BENCH_WHEEL_NAME"

ROW_KIND = "row_kind"
KIND_CELL = "cell"            # the value of a row that has no row_kind: every row written before this module
KIND_BUILD_ONLY = "build_only"

# The ONLY figures a build-only row may put into a full row (see the module docstring). index_before_load says how to read index_s.
BUILD_FIELDS = ("build_s", "ingest_s", "index_s", "index_before_load", "setup_s", "gav_build_s",
                "lineitem_buckets", "async_writers", "async_sync", "load_call_rows", "columnar_insert")
# The build window's resource figures: copied under this prefix, never over the full row's own.
WINDOW_PREFIX = "build_window_"
WINDOW_KEY = re.compile(r"^(peak_|mem_|rss|cpu_usec|cpu_|disk_|io_|oom_killed|heap$|jvm_|gc_)")
# What a row must not carry over from the build-only row into the merged one under its own name.
PROVENANCE = ("build_figures_wheel", "build_figures_wheel_sha256", "build_figures_run_id", "build_figures_ts_utc",
              "build_figures_replaced", "timed_ts_utc", "timed_wheel")


# ----------------------------------------------------------------------------------------------- the lane side
def build_only():
    """True when the cell was asked to stop after build() (runner.py --build-only)."""
    return os.environ.get(BUILD_ONLY_ENV, "") == "1"


def finish_build_only(out, out_path, adapter=None):
    """Called by a lane's main() right after build() and its stamps, in place of the workload. Marks the row, writes it exactly as the lane
    writes its own, and ends the process. Does not return."""
    out[ROW_KIND] = KIND_BUILD_ONLY
    out["build_only_stopped_after"] = "build"
    gav = getattr(adapter, "gav_build_s", None)
    if gav is not None and "gav_build_s" not in out:
        out["gav_build_s"] = gav
    try:
        if adapter is not None and hasattr(adapter, "close"):
            adapter.close()     # untimed and unrecorded: the full cell's close_s belongs to the full cell
    except Exception as e:      # noqa: BLE001
        out["build_only_close_error"] = f"{type(e).__name__}: {e}"[:200]
    with open(out_path, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


# --------------------------------------------------------------------------------------------- the runner side
_SHA_CACHE: dict = {}


def sha256_file(path):
    """sha256 of a file, cached per path (the runner stamps every row of a stage, the wheel is read once)."""
    if path not in _SHA_CACHE:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        _SHA_CACHE[path] = h.hexdigest()
    return _SHA_CACHE[path]


def stamp_row(row, env=None):
    """Runner side, once per row, just before the row is written. Adds nothing unless the stage opted in, so a row of the live pass is byte for
    byte what it was. Returns the row."""
    env = os.environ if env is None else env
    if env.get(BUILD_ONLY_ENV, "") == "1":
        row.setdefault(ROW_KIND, KIND_BUILD_ONLY)   # a cell killed before the lane wrote its row still says what it was
    label = env.get(WHEEL_LABEL_ENV, "").strip()
    if label:
        row["wheel_label"] = label
        if env.get(WHEEL_NAME_ENV, "").strip():
            row["wheel_name"] = env[WHEEL_NAME_ENV].strip()
        if env.get(WHEEL_SHA256_ENV, "").strip():
            row["wheel_sha256"] = env[WHEEL_SHA256_ENV].strip().lower()
    return row


# ------------------------------------------------------------------------------------------------ the data side
def kind_of(r):
    return r.get(ROW_KIND) or KIND_CELL


def is_arcade_in_process(r):
    b = str(r.get("backend") or "")
    return b.startswith("arcadedb") and "server" not in b and "http_client" not in b and "imgdefaults" not in b


def build_of(r):
    """The build of an in-process ArcadeDB row: its engine_backend, "jvm" when it names none (every row before 26.11.1)."""
    return r.get("engine_backend") if r.get("engine_backend") in ("native", "jvm") else "jvm"


def wheel_of(r):
    """The label of the wheel a row ran on: wheel_label when the stage stamped one, else the engine_version. Version strings that name a
    server ("server:26.11.1") do not occur on in-process rows; the digits-and-suffix part is what is compared."""
    lab = str(r.get("wheel_label") or r.get("engine_version") or "").strip()
    m = re.search(r"\d+\.\d+\.\d+(?:\.(?:dev|post)\d+)?", lab)
    return m.group(0) if m else lab


def version_key(label):
    """Orders wheel labels: 26.11.1 < 26.11.1.post1 < 26.11.1.post2; a .devN sorts before its release."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:\.(dev|post)(\d+))?", label)
    if not m:
        return (0, 0, 0, -2, 0)
    a, b, c, kind, n = m.groups()
    rank = {None: 0, "post": 1, "dev": -1}[kind]
    return (int(a), int(b), int(c), rank, int(n or 0))


def cell_key(r):
    """What identifies a cell apart from its repetition and its wheel: the canonical key of merge_campaign plus the durability class, the
    GAV twin marker and the build (native and JVM are two arms of one release)."""
    return (r.get("lane"), r.get("scale"), r.get("n_docs"), r.get("workload"), r.get("backend"),
            r.get("durability_class") or "relaxed", r.get("backend_arm") or "", r.get("gav") is not False, build_of(r))


def clean(r):
    return not r.get("error") and r.get("rc") in (0, None)


def _newest_by_rep(rows):
    best = {}
    for r in rows:
        rep = r.get("rep")
        if rep not in best or str(r.get("ts_utc")) > str(best[rep].get("ts_utc")):
            best[rep] = r
    return best


def _label(key):
    return f"{key[0]}/{key[1]}/{key[3]}/{key[4]}/{key[5]}" + (f"/{key[6]}" if key[6] else "") + f"/{key[8]}"


def merge_build_only(base, bo, label_bo):
    """The 26.11.1 (or other) full row `base` with the build figures of the build-only row `bo`. Nothing else of the full row moves."""
    out = dict(base)
    replaced = []
    for k in BUILD_FIELDS:
        if k in bo:
            out[k] = bo[k]
            replaced.append(k)
    for k, v in bo.items():
        if WINDOW_KEY.match(k) and k not in BUILD_FIELDS and not isinstance(v, (dict, list)):
            out[WINDOW_PREFIX + k] = v
    out["timed_ts_utc"] = base.get("ts_utc")
    out["timed_wheel"] = wheel_of(base)
    out["build_figures_wheel"] = label_bo
    out["build_figures_wheel_sha256"] = bo.get("wheel_sha256")
    out["build_figures_run_id"] = bo.get("run_id")
    out["build_figures_ts_utc"] = bo.get("ts_utc")
    out["build_figures_replaced"] = ",".join(replaced)
    out["ts_utc"] = max(str(base.get("ts_utc")), str(bo.get("ts_utc")))   # the canonical rule is newest-wins; the timed figures keep timed_ts_utc
    return out


def resolve(rows, reps=3, orphans="refuse"):
    """(resolved rows, decisions, problems).

    `orphans` says what a complete build-only set with NO older wheel at all becomes (a cell the older chain never measured: nothing to merge the
    build figures into). "refuse" (default): a problem, nothing lands. "leave-out": the rows are left out and the decision line names the cell
    ("LEFT OUT"), because a build-only row has no timed figure and is not a cell; a short set, or a set whose base cell is short, stays a problem.

    Per in-process ArcadeDB cell: collect the CLEAN rows by wheel label and kind. The newest label that has any row for the cell must be
    complete at `reps` repetitions (1..reps), else it is a problem. A full-cell set of a newer wheel replaces the older wheel's rows whole;
    a build-only set of a newer wheel replaces the build figures of the older wheel's complete full set, repetition by repetition; a build-only
    set with no complete full set underneath is a problem, because it has no cell to belong to. Rows of anything else (comparators, served arms,
    failed cells) pass through untouched, and a build-only row never passes through on its own."""
    if orphans not in ("refuse", "leave-out"):
        raise ValueError(f"orphans must be 'refuse' or 'leave-out', not {orphans!r}")
    problems, decisions, out = [], [], []
    groups = {}
    for r in rows:
        if not is_arcade_in_process(r):
            if kind_of(r) == KIND_BUILD_ONLY:
                problems.append(f"{r.get('lane')}/{r.get('backend')}: a build-only row of a backend this tooling does not handle")
            else:
                out.append(r)
            continue
        groups.setdefault(cell_key(r), []).append(r)
    want = list(range(1, reps + 1))
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        rs = groups[key]
        tag = _label(key)
        failed = [r for r in rs if not clean(r)]
        good = [r for r in rs if clean(r)]
        by = {}
        for r in good:
            by.setdefault((wheel_of(r), kind_of(r)), []).append(r)
        labels = sorted({w for w, _k in by}, key=version_key)
        out.extend(failed)      # failed cells land as what they are, as before (the freeze skips them); they are never a repetition here
        if not labels:
            continue
        newest = labels[-1]
        full_new = _newest_by_rep(by.get((newest, KIND_CELL), []))
        bo_new = _newest_by_rep(by.get((newest, KIND_BUILD_ONLY), []))
        have_full = [x for x in want if x in full_new]
        have_bo = [x for x in want if x in bo_new]
        older = [w for w in labels if w != newest]
        if full_new and bo_new:
            problems.append(f"{tag}: wheel {newest} has both full rows and build-only rows; one kind per cell and wheel")
            continue
        if full_new:
            if have_full != want:
                problems.append(f"{tag}: wheel {newest} has reps {sorted(full_new)} of the {reps} required "
                                f"(older wheels with rows: {older or 'none'}); a cell never mixes wheels, so finish {newest} or drop its rows")
                continue
            out.extend(full_new[x] for x in want)
            decisions.append(f"{tag}: full cell, wheel {newest}, reps {want}" + (f" (replaces {', '.join(older)})" if older else ""))
            continue
        if bo_new:
            if have_bo != want:
                problems.append(f"{tag}: wheel {newest} build-only rows have reps {sorted(bo_new)} of the {reps} required")
                continue
            if not older:
                if orphans == "leave-out":
                    decisions.append(f"{tag}: LEFT OUT, build-only rows of {newest} ({len(have_bo)} rep(s), {sum(len(v) for v in by.values())} row(s)) "
                                     f"and no full cell of an older wheel to put them into")
                else:
                    problems.append(f"{tag}: build-only rows of {newest} and no full cell of an older wheel to put them into")
                continue
            base_label = older[-1]
            base = _newest_by_rep(by.get((base_label, KIND_CELL), []))
            if [x for x in want if x in base] != want:
                problems.append(f"{tag}: the full rows of {base_label} have reps {sorted(base)} of the {reps} required, so the build-only rows of "
                                f"{newest} have no complete cell to be merged into")
                continue
            out.extend(merge_build_only(base[x], bo_new[x], newest) for x in want)
            decisions.append(f"{tag}: timed figures {base_label}, build figures {newest} (build-only), reps {want}")
            continue
        problems.append(f"{tag}: no usable row at the newest wheel {newest}")
    return out, decisions, problems


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


# ---------------------------------------------------------------------------------------------------- selftest
def _row(rep, ts, label="26.11.1", kind=None, build="native", backend="arcadedb_embedded", **kw):
    r = {"lane": "l1tpc", "scale": "tpch1", "workload": "oltp", "backend": backend, "rep": rep, "ts_utc": ts, "engine_version": label,
         "engine_backend": build, "rc": 0, "durability_class": "relaxed", "build_s": 100.0 + rep, "ingest_s": 90.0, "index_s": 10.0,
         "crud_read_p50_ms": 1.5, "peak_rss_mb": 900}
    if kind == KIND_BUILD_ONLY:
        r = {k: v for k, v in r.items() if k != "crud_read_p50_ms"}
        r[ROW_KIND] = KIND_BUILD_ONLY
        r["peak_rss_mb"] = 400
    r.update(kw)
    return r


def selftest():
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)

    # 1. a build-only row is never a cell: no live row, no rerun
    live = [_row(i, f"2026-11-0{i}") for i in (1, 2, 3)]
    bo = [_row(i, f"2026-11-1{i}", label="26.11.1.post1", kind=KIND_BUILD_ONLY, build_s=50.0 + i, wheel_label="26.11.1.post1") for i in (1, 2, 3)]
    res, dec, prob = resolve(live + bo, 3)
    check("merge: no problem", not prob)
    check("merge: 3 rows", len(res) == 3)
    check("merge: build figure from post1", [r["build_s"] for r in res] == [51.0, 52.0, 53.0])
    check("merge: timed figure from 26.11.1", all(r["crud_read_p50_ms"] == 1.5 for r in res))
    check("merge: window memory kept apart", all(r["peak_rss_mb"] == 900 and r["build_window_peak_rss_mb"] == 400 for r in res))
    check("merge: provenance", all(r["build_figures_wheel"] == "26.11.1.post1" and r["timed_wheel"] == "26.11.1" for r in res))
    check("merge: not a build-only row", all(kind_of(r) == KIND_CELL for r in res))
    check("merge: newest wins the canonical rule", all(r["ts_utc"] > r["timed_ts_utc"] for r in res))
    # 2. build-only with too few reps
    _, _, prob = resolve(live + bo[:2], 3)
    check("bo short: problem", len(prob) == 1 and "reps [1, 2] of the 3" in prob[0])
    # 3. a build-only row with nothing underneath
    _, _, prob = resolve(bo, 3)
    check("bo alone: problem", len(prob) == 1 and "no full cell" in prob[0])
    # 4. a post1 full cell replaces the live rows whole; an incomplete one is a problem, never a mix
    full = [_row(i, f"2026-11-1{i}", label="26.11.1.post1", wheel_label="26.11.1.post1") for i in (1, 2, 3)]
    res, dec, prob = resolve(live + full, 3)
    check("full: replaces", not prob and [r["engine_version"] for r in res] == ["26.11.1.post1"] * 3)
    _, _, prob = resolve(live + full[:2], 3)
    check("full short: problem, no mix", len(prob) == 1 and "never mixes wheels" in prob[0])
    # 5. the rerun at n=5 against a live set of 3 reps
    _, _, prob = resolve(live, 5)
    check("live short of n: problem", len(prob) == 1)
    # 6. two builds are two cells; comparators and served arms pass through; a failed row is not a rep
    other = [_row(i, f"2026-11-0{i}", build="jvm") for i in (1, 2, 3)]
    comp = [{"lane": "l1tpc", "backend": "duckdb_embedded", "rep": 1, "ts_utc": "2026-11-01", "engine_version": "1.4.0", "rc": 0}]
    srv = [{"lane": "l1tpc", "backend": "arcadedb_server", "rep": 1, "ts_utc": "2026-11-01", "engine_version": "server:26.11.1", "rc": 0}]
    res, _, prob = resolve(live + bo + other + comp + srv, 3)
    check("builds apart", not prob and len(res) == 3 + 3 + 2)
    bad = _row(1, "2026-11-20", error="timeout_after_7200s", rc=1)
    res, _, prob = resolve(live + [bad], 3)
    check("failed row does not count", not prob and [r["rep"] for r in res if is_arcade_in_process(r) and clean(r)] == [1, 2, 3] and bad in res)
    # 7. a build-only row of a backend we do not handle is refused
    _, _, prob = resolve([{"lane": "l1tpc", "backend": "duckdb_embedded", ROW_KIND: KIND_BUILD_ONLY, "rep": 1}], 3)
    check("foreign build-only", len(prob) == 1)
    # 8. the wheel label: stamped only on opt-in, and the candidate JVM wheel (metadata 26.11.1) is told apart by it
    r0 = stamp_row({"x": 1}, env={})
    check("stamp: inert by default", r0 == {"x": 1})
    r1 = stamp_row({"engine_version": "26.11.1"}, env={WHEEL_LABEL_ENV: "26.11.1.post1", WHEEL_SHA256_ENV: "AB" * 32, WHEEL_NAME_ENV: "a.whl", BUILD_ONLY_ENV: "1"})
    check("stamp: label", r1["wheel_label"] == "26.11.1.post1" and r1["wheel_sha256"] == "ab" * 32 and r1[ROW_KIND] == KIND_BUILD_ONLY)
    check("wheel_of: label wins over metadata", wheel_of(r1) == "26.11.1.post1")
    check("wheel_of: engine_version fallback", wheel_of({"engine_version": "26.11.1"}) == "26.11.1")
    check("version order", version_key("26.11.1") < version_key("26.11.1.post1") < version_key("26.11.1.post2") and version_key("26.11.1.dev0") < version_key("26.11.1"))
    # 10. rollback by wheel label removes exactly the post1-derived rows
    import tempfile
    tf = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    tf.write("".join(json.dumps(r) + "\n" for r in res + comp + full))
    tf.close()
    main(["strip", "--label", "26.11.1.post1", tf.name])
    left = load_jsonl(tf.name)
    check("strip: post1 rows gone, others kept", comp[0] in left and not any(r.get("wheel_label") == "26.11.1.post1" or r.get("build_figures_wheel") == "26.11.1.post1" for r in left))
    os.unlink(tf.name)
    # 9. a cell with a full and a build-only set of one wheel is ambiguous
    _, _, prob = resolve(live + full + bo, 3)
    check("both kinds one wheel", len(prob) == 1)
    for f in fails:
        print("FAIL", f)
    print(f"post1_rows selftest: {'FAILED' if fails else 'ok'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    rp = sub.add_parser("resolve")
    rp.add_argument("--reps", type=int, default=3)
    rp.add_argument("--out", required=True)
    rp.add_argument("files", nargs="+")
    sp = sub.add_parser("strip", help="ROLLBACK: drop every row that carries a wheel label (a full post1 row, or a cell merged from build-only rows)")
    sp.add_argument("--label", required=True)
    sp.add_argument("file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest or a.cmd == "selftest":
        return selftest()
    if a.cmd == "resolve":
        rows = [r for f in a.files for r in load_jsonl(f)]
        res, dec, prob = resolve(rows, a.reps)
        for d in dec:
            print("  " + d)
        for p in prob:
            print("  PROBLEM " + p)
        if prob:
            print(f"REFUSING: {len(prob)} cell(s) cannot be resolved; nothing written")
            return 1
        with open(a.out + ".new", "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in res))
        os.replace(a.out + ".new", a.out)
        print(f"{len(res)} row(s) written to {a.out}")
        return 0
    if a.cmd == "strip":
        rows = load_jsonl(a.file)
        keep = [r for r in rows if r.get("wheel_label") != a.label and r.get("build_figures_wheel") != a.label]
        with open(a.file + ".new", "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in keep))
        os.replace(a.file + ".new", a.file)
        print(f"{len(rows) - len(keep)} row(s) of wheel {a.label} removed from {a.file}, {len(keep)} kept; land the live rows file again to restore the replaced rows")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
