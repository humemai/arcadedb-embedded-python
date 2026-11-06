"""Freeze-time correction for the io.stat double count (humemai/arcadedb-embedded-python#555). Pure functions, no file writes.

THE DEFECT. Until the fix, runner.read_io_stat and memory_probe.parse_io_stat summed every device line of a container's cgroup v2
io.stat. On the mini the file lists 259:0 (NVMe) and 252:0 (a device-mapper device stacked on it) with identical bytes, plus an
unrelated 8:0 with 0 bytes, so every figure derived from it was recorded at twice its value. The fixed harness counts a stacked
device once.

THE CORRECTION. The raw rows (runs.jsonl) are never edited. The freeze (make_paper_tables.freeze_paper_rows) calls `correct_rows`
on the rows it writes to runs_paper.csv: for a row that ran on a host named in `hosts` and predates the fix, every io figure is
halved in the FROZEN copy, and `report` names each corrected row with its raw values, so the recorded value is recoverable from
the freeze report (results/generated/io_stat_correction.json) and from runs.jsonl. No column is added to the CSV.

WHICH ROWS PREDATE THE FIX. A row does not record the harness commit (only `engine_commit`, the engine's), so "contains the fix"
cannot be read off the row and is not guessed. What a row does record is `manifest`, the start time of the runner invocation that
wrote it (UTC, `YYYYmmddTHHMMSSZ`), and the runner is the harness code for that whole invocation: a stage pulls main before the
runner starts and never mid-run. io_stat_fix.json holds `fixed_from_manifest`, the first runner start whose checkout contains the
fix (`git merge-base --is-ancestor <fix commit> HEAD` on the host, read when the first stage after the fix landed). A row with
`manifest` earlier than that predates the fix. While the value is null no row is fixed, which is the truth until the fix reaches
the host. A row with neither a parseable `manifest` nor `ts_utc` is treated as predating the fix.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX_FILE = HERE / "io_stat_fix.json"

# Every field the harness derives from io.stat: io_read_mib, io_write_mib, io_{read,write}_mib_sum,
# {client,server,server_container,sidecar_<name>}_io_{read,write}_mib, and the memory probe's io_<phase>_{read,write}_mib.
IO_FIELD = re.compile(r"^(?:[a-z0-9_]+_)?io_(?:read|write)_mib(?:_sum)?$|^io_[a-z0-9_]+_(?:read|write)_mib$")


def is_io_field(name):
    return bool(IO_FIELD.match(str(name)))


def load_fix(path=FIX_FILE):
    """The fix record: {"hosts": [...], "fixed_from_manifest": "YYYYmmddTHHMMSSZ" or None, "fix_commits": [...]}."""
    with open(path) as fh:
        fix = json.load(fh)
    if fix.get("fixed_from_manifest") and parse_stamp(fix["fixed_from_manifest"]) is None:
        raise ValueError(f"fixed_from_manifest {fix['fixed_from_manifest']!r} is not a UTC stamp")   # fail loudly, never skip
    return fix


def parse_stamp(text):
    """A runner `manifest` stamp (20260920T225804Z) or an ISO `ts_utc` as an aware UTC datetime; None when it is neither."""
    s = str(text or "").strip()
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def predates_fix(row, fixed_from):
    """True when the row was written by a harness without the fix. `fixed_from` is the cutoff stamp, or None (no fixed run yet)."""
    if not fixed_from:
        return True
    cut = parse_stamp(fixed_from)
    if cut is None:
        raise ValueError(f"fixed_from_manifest {fixed_from!r} is not a UTC stamp")
    when = parse_stamp(row.get("manifest")) or parse_stamp(row.get("ts_utc"))
    return when is None or when < cut


def correct_row(row, hosts, fixed_from):
    """(row or a corrected copy, {field: raw value} of what was halved). The input dict is never changed."""
    if row.get("bench_host") not in hosts or not predates_fix(row, fixed_from):
        return row, {}
    out, raw = dict(row), {}
    for k, v in row.items():
        if is_io_field(k) and isinstance(v, (int, float)) and not isinstance(v, bool):
            raw[k] = v
            out[k] = round(v / 2, 2)   # a recorded value is 0.1 MiB-quantised, so its half is exact at 0.05
    return (out, raw) if raw else (row, {})


def correct_rows(rows, fix=None):
    """(rows, report) for the freeze: `rows` in input order with the io figures of stacked-device rows halved, `report` the record
    of what changed, fit for json.dump (rule, cutoff, counts, and per corrected row its identity and raw values)."""
    fix = load_fix() if fix is None else fix
    hosts, fixed_from = tuple(fix["hosts"]), fix.get("fixed_from_manifest")
    out, corrected = [], []
    for r in rows:
        c, raw = correct_row(r, hosts, fixed_from)
        out.append(c)
        if raw:
            corrected.append({"run_id": r.get("run_id"), "lane": r.get("lane"), "backend": r.get("backend"),
                              "scale": r.get("scale"), "rep": r.get("rep"), "raw": raw})
    report = {"issue": "humemai/arcadedb-embedded-python#555",
              "rule": "io figures halved in the frozen rows of hosts that stack block devices, for rows written before the fix",
              "hosts": list(hosts), "fixed_from_manifest": fixed_from, "fix_commits": fix.get("fix_commits", []),
              "rows_frozen": len(rows), "rows_corrected": len(corrected), "corrected": corrected}
    return out, report
