#!/usr/bin/env python3
"""Generate the DBBench "Engines" documentation page from the benchmark's own rows.

    uv run python benchmarks/experiments/gen_engines_doc.py <path>      # from the repo root
    uv run python benchmarks/experiments/gen_engines_doc.py --check <path>

WHY A SCRIPT. The page says what we run: the version, the image, the durability
classes, the tiers, the settings, and every override of an engine's default with
its reason. A page like that typed by hand drifts from the rows the moment an
engine is re-pinned, and a number copied by hand is a number nothing checks. So
no number and no setting on the page is typed here. Every one is read from a
result row, from the override registry (`overrides.py`), or from a constant the
exporter already holds (`export_web.py`), and `test_gen_engines_doc.py` fails
when a digit appears in the output that no row carries.

WHERE EACH PART COMES FROM

  * WHICH ROWS. `make_paper_tables.load_canonical` under `BENCH_INSTRUMENT=2026-10`
    is the selection the published tables are frozen from (the October campaign,
    rc == 0, the serial 0-11 cpuset, reps 1..N, no pre-release engine, the newest
    row per cell). It is run here, not re-implemented, in a private copy of the
    module so that its import-time switches cannot leak into another importer.
  * FAILURES. `load_canonical` drops every row with rc != 0, and a failure is a
    result (methodology rule 7). The same campaign's failed attempts are read
    from the same log under the same cpuset, tier, and rep filters, and a cell is
    listed when its newest attempt is a failure newer than any clean row of that
    cell.
  * NAMES. The arm names the page spells (`DISPLAY_NAMES`, `display_name`), the
    arms kept off the result tables (`OFF_PAGE_ARMS`), the table-to-lane map
    (`_TABLE_LANE`) and the tier order (`SCALE_ORDER`) are read out of
    `export_web.py` without running it: importing it needs a campaign pin in the
    environment and fixes its mode at import.
  * LANES. `PAGE_LANES` is the order and the table ids of
    humem.ai/src/lib/dbbench/lanes.ts; the test compares the two when the file is
    on disk. A lane code (`l2`, `e2`) belongs to the page lane whose table ids
    `_TABLE_LANE` maps to it.
  * OVERRIDES. For each arm, the registry's own sentence function, called with
    that arm's rows (the rows where the override is in force, `Override.applies`),
    so the sentence carries the value the rows record. The fields a `Carrier`
    names are printed with their values beside the sentence. A sentence that fails
    its own `says` patterns, or a carrier field that no row stamps, is listed on
    the page's gap list and not hidden.

No sentence here says which way a setting moves a number: the registry says why
it does not.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime
import functools
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import overrides as OV  # noqa: E402

RUNS = HERE / "results" / "runs.jsonl"

# The lane order and table ids of humem.ai/src/lib/dbbench/lanes.ts (slug, title,
# the tableId of each of its tables, in order). The first table a lane lists is
# its headline; the order here is the order of the page. test_gen_engines_doc
# parses lanes.ts when it is on disk and fails if this drifts from it.
PAGE_LANES = (
    ("tables", "Tables", ("docs_oltp", "docs_olap")),
    ("graphs", "Graphs", ("l2", "l2olap")),
    ("vectors", "Vectors", ("l3d", "l3s")),
    ("time-series", "Time series", ("l4",)),
    ("cross-model", "Cross-model", ("e2", "e2atom", "multimodel")),
    ("lifecycle", "Lifecycle", ("lifecycle", "e4", "durability")),
)

# Row fields that carry a setting the run had, in the order the page prints them.
# Each is read from the rows; none is a constant here. Fields an override
# registers (`Carrier.field` and `Override.companions`) are added per arm.
SETTING_FIELDS = (
    "topology", "mem_cap", "client_mem_cap", "server_mem_cap",
    "heap", "server_heap", "server_pagecache", "cpuset", "server_cpuset",
    "server_jvm_gc", "server_jvm_flags", "quantization", "query_language", "store",
    "surreal_sync_mode", "memgraph_storage_mode", "memgraph_wal_enabled",
    "falkordb_appendonly", "falkordb_appendfsync", "falkordb_save",
)

BANNER = ("Generated from the result rows and the override registry; do not edit by hand. "
          "Regenerated at every landing.")

INTRO = (
    "For every engine in every lane, this page states what we run: the version, the container image "
    "digest where a row records one, the durability classes measured, the tiers, every setting a row "
    "carries, and each override of an engine's default with the reason. Everything below is read from "
    "the result rows and the override registry, so it cannot drift from what was measured. The rules "
    "these settings follow are on the [Methodology](methodology.md) page."
)

WRONG_SETTING = (
    "## How to tell us a setting is wrong\n\n"
    "If a setting we use for your engine differs from what you recommend for this task, open an issue "
    "(see [Contribute](contribute.md)) with the engine, the version, the setting, and a link to your "
    "documentation.\n"
    "A corrected configuration is re-run on the same machine and published beside the earlier result, "
    "with the reason for the change.\n"
)


# ---------------------------------------------------------------------------
# constants the exporter holds, read without running it

@functools.lru_cache(maxsize=1)
def export_web_constants():
    """DISPLAY_NAMES, OFF_PAGE_ARMS, _TABLE_LANE, SCALE_ORDER and a `display_name`
    function, taken from export_web.py by parsing it."""
    src = (HERE / "export_web.py").read_text(encoding="utf-8")
    want = {"DISPLAY_NAMES", "OFF_PAGE_ARMS", "_TABLE_LANE", "SCALE_ORDER"}
    code_names = {"_INTERNAL", "_REF_PAREN", "_REF_TAIL", "_REF_BARE", "_REF_SCAN"}   # assigned from re.compile(...)
    funcs = {"display_name", "_public_prose"}
    consts, segments = {}, []
    for node in ast.parse(src).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id
            if name in want:
                consts[name] = ast.literal_eval(node.value)
            elif name in code_names:
                segments.append((name, ast.get_source_segment(src, node)))
        elif isinstance(node, ast.FunctionDef) and node.name in funcs:
            segments.append((node.name, ast.get_source_segment(src, node)))
    missing = (want - set(consts)) | ((code_names | funcs) - {n for n, _ in segments})
    if missing:
        raise SystemExit(f"export_web.py no longer defines {sorted(missing)} in a form gen_engines_doc can "
                         "read; fix the reader, do not copy the names here.")
    ns = {"re": re, "DISPLAY_NAMES": consts["DISPLAY_NAMES"]}
    for name, seg in segments:       # the repo's own definitions, in file order
        exec(compile(seg, f"export_web.py:{name}", "exec"), ns)  # noqa: S102
    consts["display_name"] = ns["display_name"]
    consts["public_prose"] = ns["_public_prose"]    # takes our internal citations out of a row's prose
    consts["internal_ref"] = ns["_REF_SCAN"]        # what must not survive to a page
    return consts


def lane_codes_in_page_order():
    """(lane code, page lane slug) in the order lanes.ts lists the tables, through
    export_web's table-to-lane map. A table with no lane code of its own (e4, the
    durability and multimodel tables) is its own code and simply has no rows."""
    table_lane = export_web_constants()["_TABLE_LANE"]
    order, page_of = [], {}
    for slug, _title, table_ids in PAGE_LANES:
        for tid in table_ids:
            code = table_lane.get(tid, (tid, None))[0]
            if code not in page_of:
                page_of[code] = slug
                order.append(code)
    return order, page_of


# ---------------------------------------------------------------------------
# the row selection

@contextlib.contextmanager
def _env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _october_paper_tables():
    """A private copy of make_paper_tables in its October mode. It reads its mode
    from the environment when it is imported, and tests elsewhere import the real
    module in September mode, so this copy is not registered in sys.modules."""
    spec = importlib.util.spec_from_file_location("_gen_engines_mpt", HERE / "make_paper_tables.py")
    mod = importlib.util.module_from_spec(spec)
    with _env(BENCH_INSTRUMENT=OV.INSTRUMENT, BENCH_SKELETON=None, BENCH_ONLY_LANES=None):
        spec.loader.exec_module(mod)
    return mod


def _is_failure(r):
    return r.get("rc") != 0


def _cell(r):
    return (r.get("lane"), str(r.get("scale")), r.get("workload"), r.get("backend"),
            r.get("durability_class") or "relaxed")


def select_rows(runs_path):
    """(clean rows, failed cells, raw October rows) from the canonical log.

    Clean rows are exactly `make_paper_tables.load_canonical()` under the October
    instrument. A failed cell is the newest failed attempt of a cell whose clean
    rows (if any) are all older than it, among the attempts the freeze would have
    considered but for rc: this campaign, the serial cpuset, a published tier, a
    rep inside 1..N.
    """
    runs_path = Path(runs_path).resolve()
    M = _october_paper_tables()
    with _env(BENCH_RUNS_JSONL=str(runs_path)):
        saved, M._write_withheld_recall = M._write_withheld_recall, (lambda: None)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                clean = M.load_canonical()
        finally:
            M._write_withheld_recall = saved
    raw = []
    with open(runs_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    october = [r for r in raw if str(r.get("instrument") or "") == OV.INSTRUMENT]
    newest_clean = {}
    for r in clean:
        c = _cell(r)
        newest_clean[c] = max(newest_clean.get(c, ""), str(r.get("ts_utc")))
    newest_fail = {}
    for r in october:
        if not _is_failure(r):
            continue
        if str(r.get("cpuset")) not in ("0-11", "None"):
            continue
        if str(r.get("scale")) not in M.PAPER_SCALES.get(r.get("lane"), []):
            continue
        if not isinstance(r.get("rep"), int) or not 1 <= r["rep"] <= M.MAX_REP:
            continue
        c = _cell(r)
        if c not in newest_fail or str(r.get("ts_utc")) > str(newest_fail[c].get("ts_utc")):
            newest_fail[c] = r
    failed = [r for c, r in newest_fail.items() if str(r.get("ts_utc")) > newest_clean.get(c, "")]
    return clean, failed, october


def row_id(r):
    return f"{r.get('run_id')}@{r.get('ts_utc')}"


def row_set_identity(rows):
    ids = sorted({row_id(r) for r in rows})
    return len(ids), hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# small helpers for printing row values

def code(v):
    s = " ".join(export_web_constants()["public_prose"](str(v)).split())
    fence = "``" if "`" in s else "`"
    pad = " " if s.startswith("`") or s.endswith("`") else ""
    return f"{fence}{pad}{s}{pad}{fence}"


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def tier_key(scale):
    order = export_web_constants()["SCALE_ORDER"]
    s = str(scale)
    return (order.index(s) if s in order else len(order), _natural(s))


def tiers_text(scales):
    return ", ".join(code(s) for s in sorted(scales, key=tier_key))


_EXC_LINE = re.compile(r"^[\w.]*(?:error|exception|exit)\w*\b", re.I)


def error_summary(text, limit=200):
    """What a failed cell said, in one line of its own words: a one-line error as it is,
    else the last line that names an exception, else the last line, marked as such."""
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if not lines:
        return ""
    if len(lines) == 1:
        s = lines[0]
    else:
        hit = next((ln for ln in reversed(lines) if _EXC_LINE.match(ln)), None)
        s = hit if hit else "last line: " + lines[-1]
    return s if len(s) <= limit else s[:limit].rstrip() + "..."


def _present(v):
    return OV._present(v)


def row_version(r):
    for f in ("engine_version", "backend_version"):
        if _present(r.get(f)):
            return str(r[f]), f
    return None, None


def image_parts(r):
    """(reference, digest, tag) from the fields a row may carry: `server_image_ref`
    (an image@digest, or a local tag), `server_image` (the image id the engine ran
    on) and `image` (the harness image's tag, for an arm run in-process)."""
    ref = str(r.get("server_image_ref")) if _present(r.get("server_image_ref")) else None
    dig = str(r.get("server_image")) if _present(r.get("server_image")) else None
    tag = str(r.get("image")) if _present(r.get("image")) else None
    return ref, dig, tag


def image_text(ref, dig, tag):
    parts = []
    if ref:
        parts.append(code(ref))
    if dig and not (ref and dig in ref):
        parts.append(f"digest {code(dig)}")
    if not parts and tag:
        parts.append(f"{code(tag)} (a tag; no digest in the rows)")
    return "; ".join(parts) if parts else "not recorded in the rows"


def has_digest(ref, dig):
    return bool((ref and "sha256:" in ref) or (dig and "sha256:" in dig))


def value_by_tier(rows, field):
    """{value: {tiers}} for a field over these rows, blanks skipped."""
    out = defaultdict(set)
    for r in rows:
        if _present(r.get(field)):
            out[str(r[field])].add(str(r.get("scale")))
    return out


def setting_line(rows, field):
    by = value_by_tier(rows, field)
    if not by:
        return None
    if len(by) == 1:
        return f"{code(field)}: {code(next(iter(by)))}"
    shown = "; ".join(f"{code(v)} ({tiers_text(t)})"
                      for v, t in sorted(by.items(), key=lambda kv: (min(tier_key(s) for s in kv[1]), kv[0])))
    return f"{code(field)}: {shown}"


# ---------------------------------------------------------------------------
# one arm

class Gaps:
    def __init__(self):
        self.items = defaultdict(set)      # heading -> {line}

    def add(self, heading, line):
        self.items[heading].add(line)


def _overrides_for(code_, backend):
    return [o for o in OV.OVERRIDES if any(c.lane == code_ and c.backend == backend for c in o.carriers)]


def render_arm(code_, backend, rows, fails, gaps, names):
    display = names["display_name"](backend)
    off_page = backend in names["OFF_PAGE_ARMS"]
    out = [f"#### {display}: {code(backend)}", ""]
    where = f"{display} ({backend}), lane {code_}"
    if off_page:
        out += ["This arm is an ablation of one engine's image defaults. It is measured and kept in the rows, "
                "and it is not printed in the result tables.", ""]

    if not rows:
        out += ["No clean row yet; the failed cells below are all there is.", ""]
        gaps.add("Arms with a recorded failure and no clean row", f"{where}")
    else:
        # version / image groups
        groups = defaultdict(lambda: {"scales": set(), "classes": set()})
        for r in rows:
            ver, vfield = row_version(r)
            commit = str(r.get("engine_commit")) if backend.startswith("arcadedb") and _present(r.get("engine_commit")) else None
            ref, dig, tag = image_parts(r)
            g = groups[(ver, vfield, commit, ref, dig, tag)]
            g["scales"].add(str(r.get("scale")))
            g["classes"].add(str(r.get("durability_class")) if _present(r.get("durability_class")) else "not recorded")
        out += ["| Tiers | Version | Image | Durability classes |", "|---|---|---|---|"]
        glist = sorted(groups.items(), key=lambda kv: (min(tier_key(s) for s in kv[1]["scales"]), str(kv[0])))
        for (ver, vfield, commit, ref, dig, tag), g in glist:
            if ver is None:
                vtxt = "not recorded in the rows"
            else:
                vtxt = code(ver) + ("" if vfield == "engine_version" else f" (from {code(vfield)})")
            if commit:
                vtxt += f", commit {code(commit)}"
            out.append(f"| {tiers_text(g['scales'])} | {vtxt} | {image_text(ref, dig, tag)} | "
                       f"{', '.join(code(c) for c in sorted(g['classes']))} |")
        out.append("")
        if any(k[0] is None for k in groups):
            gaps.add("Rows with no version", f"{where}: no `engine_version` or `backend_version` on some of its rows")
        if any(not has_digest(k[3], k[4]) for k in groups):
            gaps.add("Rows with no image digest", f"{where}: the rows carry "
                     + ("a tag only" if any(k[5] for k in groups if not has_digest(k[3], k[4])) else "no image field"))
        by_tier = defaultdict(set)
        for k, g in groups.items():
            for s in g["scales"]:
                by_tier[s].add(k[:3])
        mixed = sorted((s for s, v in by_tier.items() if len(v) > 1), key=tier_key)
        if mixed:
            gaps.add("Tiers whose rows mix versions", f"{where}: {', '.join(mixed)}")

        # durability, per class, as the rows word it
        by_class = defaultdict(lambda: {"text": set(), "flags": set()})
        for r in rows:
            cls = str(r.get("durability_class")) if _present(r.get("durability_class")) else "not recorded"
            if _present(r.get("durability")):
                by_class[cls]["text"].add(str(r["durability"]))
            if _present(r.get("durability_server_flags")):
                by_class[cls]["flags"].add(str(r["durability_server_flags"]))
        for cls in sorted(by_class):
            d = by_class[cls]
            bits = [code(t) for t in sorted(d["text"])] or ["no `durability` text on its rows"]
            if d["flags"]:
                bits.append("server flags " + ", ".join(code(f) for f in sorted(d["flags"])))
            out.append(f"- Durability, {code(cls)}: {'; '.join(bits)}")

        # settings the rows carry
        extra = []
        for o in _overrides_for(code_, backend):
            for c in o.carriers:
                if c.lane == code_ and c.backend == backend and c.field:
                    extra.append(c.field)
            extra.extend(o.companions)
        seen = set()
        for f in list(SETTING_FIELDS) + extra:
            if f in seen:
                continue
            seen.add(f)
            line = setting_line(rows, f)
            if line:
                out.append(f"- Setting {line}")
        out.append("")

        # overrides
        sentences = []
        for o in _overrides_for(code_, backend):
            sel = [r for r in rows if o.applies is None or o.applies(r)]
            if not sel:
                continue          # not in force for any row of this arm: a sentence about it would be false
            try:
                text, _values = o.sentence(sel)
            except Exception as exc:  # noqa: BLE001 - say it on the page, do not hide the override
                gaps.add("Overrides the registry cannot render", f"{where}: `{o.key}` ({type(exc).__name__})")
                continue
            if not all(re.search(p, text) for p in o.says):
                gaps.add("Overrides the registry cannot render", f"{where}: `{o.key}` (its sentence fails its own `says` patterns)")
                continue
            fields = [c.field for c in o.carriers if c.lane == code_ and c.backend == backend and c.field]
            stamped = []
            for f in fields + list(o.companions):
                line = setting_line(sel, f)
                if line:
                    stamped.append(line)
            tail = f" Recorded on the rows: {'; '.join(stamped)}." if stamped else ""
            sentences.append(f"- {names['public_prose'](text)} Override {code(o.key)}.{tail}")
        if sentences:
            out += ["Overrides of the engine's default on this arm:", ""] + sentences + [""]
        else:
            out += ["No override from the registry applies to this arm.", ""]

        # stamps the registry expects and the rows lack or contradict
        for f in OV.stamp_findings(rows)[0]:
            scale = f["where"].split()[1]
            gaps.add("Override stamps that at least one row lacks or contradicts",
                     f"{where}: `{f['field']}` for `{f['key']}` is {'missing' if f['kind'] == 'NOT STAMPED' else 'wrong'}, tier {scale}")

    if fails:
        out += ["Failed cells (a failure is a result):", ""]
        for r in sorted(fails, key=lambda r: (tier_key(r.get("scale")), str(r.get("workload")),
                                              str(r.get("durability_class")), r.get("rep") or 0)):
            flags = ", killed for memory" if r.get("oom_killed") is True else ""
            cls = r.get("durability_class")
            out.append(f"- {code(r.get('scale'))} / {code(r.get('workload'))}"
                       + (f" / {code(cls)}" if _present(cls) else "")
                       + f" / rep {r.get('rep')}: rc {r.get('rc')}{flags}: {code(error_summary(r.get('error')))}")
        out.append("")
    return out


# ---------------------------------------------------------------------------
# the page

def render(clean, failed, registered, date):
    """The page as text. `clean` and `failed` are row lists, `registered` maps a lane
    code to the arms the runner registers for it, `date` is an ISO date string."""
    names = export_web_constants()
    order, page_of = lane_codes_in_page_order()
    gaps = Gaps()

    arms = defaultdict(lambda: {"rows": [], "fails": []})
    for r in clean:
        arms[(r.get("lane"), r.get("backend"))]["rows"].append(r)
    for r in failed:
        arms[(r.get("lane"), r.get("backend"))]["fails"].append(r)

    for lane_code in sorted({k[0] for k in arms} - set(page_of), key=str):
        gaps.add("Lane codes in the rows that no page lane shows", code(lane_code))

    n, digest = row_set_identity(list(clean) + list(failed))
    instruments = sorted({str(r.get("instrument")) for r in clean if _present(r.get("instrument"))})

    lines = ["# Engines", "", '!!! note "Generated page"', f"    {BANNER}", "",
             f"    Generated on {date}. Row set: {n} rows, sha256 {digest} "
             "(of the sorted row ids, one per line: the clean rows of the selection and the failed cells listed below).",
             "", INTRO, ""]
    if instruments:
        lines += [f"The rows are those of the campaign with instrument {', '.join(code(i) for i in instruments)}, "
                  "selected as the published tables are: the newest clean row of each cell, on the serial CPU set. "
                  "A failed attempt is listed as the result it is.", ""]
    lines += ["## What we run", ""]

    no_rows_lanes = []
    for slug, title, _tids in PAGE_LANES:
        codes = [c for c in order if page_of[c] == slug]
        lines += [f"### {title}", ""]
        lane_arms = sorted((k for k in arms if k[0] in codes),
                           key=lambda k: (codes.index(k[0]), names["display_name"](k[1]).lower(), k[1]))
        if not lane_arms:
            lines += ["No rows yet for this lane.", ""]
            no_rows_lanes.append(title)
        for k in lane_arms:
            lines += render_arm(k[0], k[1], arms[k]["rows"], arms[k]["fails"], gaps, names)
        waiting = []
        for c in codes:
            have = {k[1] for k in arms if k[0] == c}
            for b in registered.get(c, ()):
                if b not in have:
                    waiting.append((names["display_name"](b).lower(), b, c))
        if waiting:
            lines += ["Registered for this lane, no row yet: "
                      + ", ".join(f"{names['display_name'](b)} ({code(b)}, lane {code(c)})" for _n, b, c in sorted(waiting)) + ".", ""]
            for _n, b, c in waiting:
                gaps.add("Arms registered in the runner with no row yet", f"lane {c}: {b}")

    # the gap list
    lines += ["## Gaps in the rows", "",
              "What the rows do not yet say, found by reading them. An empty list would mean the rows are complete.", ""]
    if no_rows_lanes:
        lines.append("- Lanes with no rows yet: " + ", ".join(no_rows_lanes) + ".")
    else:
        lines.append("- Every lane has at least one row.")
    for heading in sorted(gaps.items):
        lines.append(f"- {heading}:")
        for item in sorted(gaps.items[heading]):
            lines.append(f"    - {item}")
    lines += [""]
    lines.append(WRONG_SETTING)
    text = "\n".join(lines).rstrip("\n") + "\n"
    leak = next((ln for ln in text.splitlines()
                 if names["internal_ref"].search(ln) or ".notes" in ln), None)
    if leak:
        raise SystemExit(f"REFUSING: an internal citation reached the page: {leak[:160]!r}. "
                         "It comes from a row value or a registry sentence; take it out at the source.")
    return text


def registered_arms():
    """{lane code: arms} the runner registers, or {} when it cannot be imported."""
    try:
        import runner
    except Exception:  # noqa: BLE001 - the page still builds from the rows alone
        return {}
    return {k: tuple(v[1]) for k, v in runner.LANES.items()}


def build(runs_path, date):
    clean, failed, _october = select_rows(runs_path)
    return render(clean, failed, registered_arms(), date)


# the first line of the generated-date note, which a check may ignore
def _strip_date(text):
    return re.sub(r"^    Generated on .*$", "    Generated on DATE.", text, flags=re.M)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", nargs="?", help="write the page here (default: stdout)")
    ap.add_argument("--runs", default=str(RUNS), help="the canonical row log (default: results/runs.jsonl)")
    ap.add_argument("--date", default=datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
                    help="the generation date written on the page (default: today, UTC)")
    ap.add_argument("--check", action="store_true",
                    help="regenerate and exit 1 when the page at `out` differs, ignoring the generation date")
    a = ap.parse_args(argv)
    text = build(a.runs, a.date)
    if a.check:
        if not a.out:
            ap.error("--check needs the page path")
        have = Path(a.out).read_text(encoding="utf-8") if Path(a.out).exists() else ""
        if _strip_date(have) != _strip_date(text):
            print(f"{a.out} is out of date: regenerate it with gen_engines_doc.py", file=sys.stderr)
            return 1
        return 0
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
