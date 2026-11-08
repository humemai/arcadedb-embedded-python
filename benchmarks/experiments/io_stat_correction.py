"""Freeze-time correction for the io.stat double count (humemai/arcadedb-embedded-python#555). Pure functions, no file writes.

THE DEFECT. Until the fix, runner.read_io_stat and memory_probe.parse_io_stat summed every device line of a container's cgroup v2
io.stat. On the mini the file lists 259:0 (NVMe) and 252:0 (a device-mapper device stacked on it) with identical bytes, plus an
unrelated 8:0 with 0 bytes, so every figure derived from it was recorded at twice its value. The fixed harness counts a stacked
device once and says so: its runner stamps `io_stat_dedup: 1` into every row it writes.

THE CORRECTION. The raw rows (runs.jsonl) are never edited. The freeze (make_paper_tables.freeze_paper_rows) calls `correct_rows`
on the rows it writes to runs_paper.csv. A row that ran on a host named in `hosts` (the row's `bench_host`) and does NOT carry
`io_stat_dedup == 1` predates the fix: every io figure in the frozen copy is halved, and the frozen row's `io_stat_dedup` reads
"halved" (a stamped row keeps its 1, a row of another host keeps whatever it had, usually blank). `report` names each corrected
row with its raw values, so the recorded value is recoverable from the freeze report (results/generated/io_stat_correction.json)
and from runs.jsonl.

WHICH ROWS PREDATE THE FIX. The row says so itself: the stamp is written by the same commit as the fix, so a row without it was
written without the fix, and no cutoff time has to be set later. A stamp that is present but is not 1 raises: a row the rule
cannot read is never silently counted either way.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX_FILE = HERE / "io_stat_fix.json"
MARKER = "io_stat_dedup"
HALVED = "halved"

# Every field the harness derives from io.stat: io_read_mib, io_write_mib, io_{read,write}_mib_sum,
# {client,server,server_container,sidecar_<name>}_io_{read,write}_mib, and the memory probe's io_<phase>_{read,write}_mib.
IO_FIELD = re.compile(r"^(?:[a-z0-9_]+_)?io_(?:read|write)_mib(?:_sum)?$|^io_[a-z0-9_]+_(?:read|write)_mib$")


def is_io_field(name):
    return bool(IO_FIELD.match(str(name)))


def load_fix(path=FIX_FILE):
    """The fix record: {"hosts": [hosts whose io.stat stacks block devices]}."""
    with open(path) as fh:
        fix = json.load(fh)
    if not fix.get("hosts"):
        raise ValueError(f"{path}: no hosts")
    return fix


def predates_fix(row):
    """True when the row was written without the fix (no stamp), False when stamped 1; ValueError for any other stamp."""
    v = row.get(MARKER)
    if v is None or v == "":
        return True
    if v == 1 and not isinstance(v, (str, bool)):
        return False
    raise ValueError(f"{MARKER}={v!r} on run_id {row.get('run_id')!r}: the stamp is 1 or absent")


def correct_row(row, hosts):
    """(row or a corrected copy, {field: raw value} of what was halved). The input dict is never changed."""
    if row.get("bench_host") not in hosts or not predates_fix(row):
        return row, {}
    out, raw = dict(row), {}
    for k, v in row.items():
        if is_io_field(k) and isinstance(v, (int, float)) and not isinstance(v, bool):
            raw[k] = v
            out[k] = round(v / 2, 2)   # a recorded value is 0.1 MiB-quantised, so its half is exact at 0.05
    if raw:
        out[MARKER] = HALVED
        return out, raw
    return row, {}


def correct_rows(rows, fix=None):
    """(rows, report) for the freeze: `rows` in input order with the io figures of stacked-device rows halved, `report` the record
    of what changed, fit for json.dump (rule, counts, and per corrected row its identity and raw values)."""
    fix = load_fix() if fix is None else fix
    hosts = tuple(fix["hosts"])
    out, corrected, stamped = [], [], 0
    for r in rows:
        c, raw = correct_row(r, hosts)
        out.append(c)
        stamped += r.get("bench_host") in hosts and r.get(MARKER) == 1
        if raw:
            corrected.append({"run_id": r.get("run_id"), "lane": r.get("lane"), "backend": r.get("backend"),
                              "scale": r.get("scale"), "rep": r.get("rep"), "raw": raw})
    report = {"issue": "humemai/arcadedb-embedded-python#555",
              "rule": f"io figures halved in the frozen rows of hosts that stack block devices unless the row carries {MARKER} == 1",
              "hosts": list(hosts), "rows_frozen": len(rows), "rows_stamped_untouched": stamped,
              "rows_corrected": len(corrected), "corrected": corrected}
    return out, report
