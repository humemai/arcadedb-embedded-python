#!/usr/bin/env python3
"""The overrides a reader meets on a page table, and the three places each is held.

PROTOCOL.md section 7 lists every default this benchmark overrides and where a
reader can find out. An override nobody can find is a defect whichever way it
moves the number, and until CAMPAIGN.md section 7 row 21 the section's last
column said NOWHERE for the ones below: the inventory was the only record, and
no artifact, row, or page sentence carried it.

One record here per override, three consumers, so a disclosure cannot be lost
by editing one of them:

  * the ADAPTER (or the runner, for the served ArcadeDB cap) stamps a row
    field, read back from the engine where the engine can be asked, so the
    artifact records what the engine ran with and not the string we passed;
  * `export_web` appends the generated sentence to every October table that
    shows one of the override's backends, derived from the rows behind the
    table (`notes_for_table`);
  * `page_check` fails a table that shows such a backend and prints no sentence
    saying it (`sentence_findings`), and `fairness_check` fails a 2026-10 row of
    such a backend that lacks the stamp or carries another value
    (`stamp_findings`).

`test_overrides.py` holds the fourth leg: it reads PROTOCOL.md section 7 and
fails when a row says NOWHERE for an override this module registers, when a
registry key is cited by no row, or when an override row is neither registered
nor on the test's explicit list of rows not done.

A sentence is generated from the rows behind the table, or from a constant the
runner itself launches with, never typed with a digit nothing checks. Where the
digit adds nothing (a thread count the setup section prints already) the
sentence has none. No sentence says which way an override moves a number: that
needs a measurement this module does not take.
"""
from __future__ import annotations

import re
from typing import Callable, NamedTuple, Optional

# The rows of an October campaign carry this instrument stamp; a September row
# predates every field below and is not judged.
INSTRUMENT = "2026-10"


class Carrier(NamedTuple):
    """One arm that runs the override, on one lane.

    `field` is the row field that proves it ran, stamped by the adapter or the
    runner; None means the arm is on the table but its rows cannot carry the
    stamp, so the table still gets the sentence and the stamp check skips it
    (no carrier needs that today).
    """
    lane: str
    backend: str
    field: Optional[str] = None


class Override(NamedTuple):
    key: str                                 # the id PROTOCOL.md cites as `override: <key>`
    setting: str                             # what is set, for the manifest and the findings
    carriers: tuple                          # Carrier...
    check: Callable                          # (row, stamped value) -> problem text or None
    sentence: Callable                       # (rows behind the table) -> (text, [values])
    says: tuple                              # regexes one printed sentence must all satisfy
    tables: tuple = ()                       # artifact-backed tables that get the sentence from a constant
    constant: Optional[Callable] = None      # () -> (text, [values]) for those tables, from no rows
    companions: tuple = ()                   # other fields the stamp writes: a source, a default, a failed read's reason


# ---------------------------------------------------------------------------
# reading a row, typed (the canonical jsonl) or stringly (the frozen csv)

def _bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    return None


def _int(v):
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else None


def _present(v):
    return v not in (None, "", "None", "nan")


def cpuset_size(cpuset):
    """How many CPUs a docker cpuset string names ('0-11', '0-5,8-11', '3')."""
    n = 0
    for part in str(cpuset).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            n += int(b) - int(a) + 1
        else:
            n += 1
    return n


def _is_false(row, v):
    return None if _bool(v) is False else f"reads {v!r}, the sentence says it is off"


def _is_true(row, v):
    return None if _bool(v) is True else f"reads {v!r}, the sentence says it is on"


def _is_zero(row, v):
    return None if _int(v) == 0 else f"reads {v!r}, the sentence says none"


def _threads_are_the_cpuset(row, v):
    """The claim is 'one thread per CPU the cell may use', so the engine's own
    answer is held against the size of the row's own cpuset."""
    got = _int(v)
    if got is None:
        return f"reads {v!r}, not a thread count"
    cpus = row.get("cpuset")
    if not _present(cpus):
        return None          # a row with no cpuset cannot be compared; F1 refuses it elsewhere
    want = cpuset_size(cpus)
    return None if got == want else f"the engine runs {got} threads in a {want}-CPU cell"


def _es_security(rows):
    return ("Elasticsearch runs with its security features switched off, so none of its requests pays "
            "for authentication or encryption; its image turns both on unless told otherwise.", [])


def _es_replicas(rows):
    return ("Elasticsearch's index is created with no replica, because a single-node cluster has "
            "nowhere to place one and the index would otherwise stay yellow.", [])


def _duckdb_threads(rows):
    return ("DuckDB is given one thread for each CPU the run may use; left alone it sizes its pool "
            "from the machine's cores and not from the CPUs the run was given.", [])


def _duckdb_vss(rows):
    return ("DuckDB's vector rows keep their HNSW index in the database through a persistence feature "
            "that its vector extension still labels experimental and that has to be switched on for "
            "the index to be stored at all.", [])


OVERRIDES = (
    Override(
        key="es_security",
        setting="xpack.security.enabled=false",
        carriers=(Carrier("l3s", "elasticsearch_sparse", "es_security_enabled"),
                  Carrier("l3d", "elasticsearch_dense", "es_security_enabled"),
                  Carrier("l3d", "elasticsearch_dense_int8", "es_security_enabled"),
                  Carrier("restart", "elasticsearch_dense", "es_security_enabled")),
        check=_is_false, sentence=_es_security,
        says=(r"Elasticsearch", r"security", r"authentication|encryption|TLS"),
        companions=("es_readback_error",)),
    Override(
        key="es_replicas",
        setting="number_of_replicas=0",
        carriers=(Carrier("l3s", "elasticsearch_sparse", "es_replicas"),
                  Carrier("l3d", "elasticsearch_dense", "es_replicas"),
                  Carrier("l3d", "elasticsearch_dense_int8", "es_replicas"),
                  Carrier("restart", "elasticsearch_dense", "es_replicas")),
        check=_is_zero, sentence=_es_replicas,
        says=(r"Elasticsearch", r"replica")),
    Override(
        key="duckdb_threads",
        setting="PRAGMA threads = len(sched_getaffinity(0))",
        carriers=(Carrier("l1tpc", "duckdb", "duckdb_threads"),
                  Carrier("l4", "duckdb", "duckdb_threads"),
                  Carrier("l3d", "duckdb_vss_dense", "duckdb_threads"),
                  Carrier("l2", "duckpgq_graph", "duckpgq_threads"),
                  Carrier("e2", "duckdb_e2", "duckdb_threads")),
        check=_threads_are_the_cpuset, sentence=_duckdb_threads,
        says=(r"DuckDB", r"thread", r"CPU|cpuset"),
        companions=("duckdb_readback_error",)),
    Override(
        key="duckdb_vss",
        setting="hnsw_enable_experimental_persistence=true",
        carriers=(Carrier("l3d", "duckdb_vss_dense", "duckdb_hnsw_persistence"),
                  Carrier("e2", "duckdb_e2", "duckdb_hnsw_persistence")),
        check=_is_true, sentence=_duckdb_vss,
        says=(r"DuckDB", r"experimental")),
)

BY_KEY = {o.key: o for o in OVERRIDES}

# Every field an adapter or the runner stamps for an override, with the
# companions that explain one (a source, a default, a failed read-back's reason).
STAMP_FIELDS = frozenset({c.field for o in OVERRIDES for c in o.carriers if c.field}
                         | {x for o in OVERRIDES for x in o.companions})


def keys_for_backend(backend):
    """The override keys that apply to a runner backend, for the manifest."""
    return sorted({o.key for o in OVERRIDES for c in o.carriers if c.backend == backend})


# ---------------------------------------------------------------------------
# consumer 1: export_web

def applicable(table_lane, backend_keys):
    """The overrides whose carriers sit on this table's lane and appear among
    its entries' backends."""
    keys = {str(k) for k in backend_keys}
    return [o for o in OVERRIDES
            if any(c.lane == table_lane and c.backend in keys for c in o.carriers)]


def notes_for_table(table_id, table_lane, backend_keys, rows):
    """[(text, values)] for each override this table meets, in registry order.

    `rows` are the frozen rows; the sentence reads those of the carriers on
    this table's lane. An artifact-backed table (`e4`) takes the sentence from
    the runner's own constant instead.
    """
    out = []
    for o in OVERRIDES:
        if table_id in o.tables:
            out.append(o.constant())
            continue
        if table_lane is None:
            continue
        mine = {c.backend for c in o.carriers if c.lane == table_lane}
        if not mine & {str(k) for k in backend_keys}:
            continue
        sel = [r for r in rows if r.get("lane") == table_lane and r.get("backend") in mine]
        out.append(o.sentence(sel))
    return out


# ---------------------------------------------------------------------------
# consumer 2: page_check

def sentence_findings(tables, lane_of, rows):
    """Findings for a payload: a table that shows an override's backend and
    prints no sentence that says it. `tables` is the payload's table list,
    `lane_of` maps a table id to its lane (or None)."""
    bad = []
    for t in tables:
        tid = t.get("id")
        conds = [str(c) for c in (t.get("conditions") or [])]
        keys = [str(e.get("backend_key")) for e in t.get("entries") or [] if e.get("backend_key")]
        hit = list(applicable(lane_of(tid), keys)) if lane_of(tid) else []
        hit += [o for o in OVERRIDES if tid in o.tables and o not in hit]
        for o in hit:
            if not any(all(re.search(p, c) for p in o.says) for c in conds):
                bad.append(f"MISSING {tid}: shows a backend that runs `{o.key}` ({o.setting}) "
                           f"and no sentence says so")
    return bad


# ---------------------------------------------------------------------------
# consumer 3: fairness_check

def stamp_findings(rows):
    """Findings for 2026-10 rows: a row of a carrier arm that lacks the field
    its override stamps, or carries a value the sentence does not claim.
    Returns (findings, how many rows were judged); a finding is a dict with
    `kind` (NOT STAMPED or WRONG), `key`, `field`, `where`, and `text`."""
    index = {}
    for o in OVERRIDES:
        for c in o.carriers:
            if c.field:
                index.setdefault((c.lane, c.backend), []).append((o, c))
    bad, judged = [], 0
    for r in rows:
        if str(r.get("instrument") or "") != INSTRUMENT:
            continue
        for o, c in index.get((r.get("lane"), r.get("backend")), ()):
            judged += 1
            where = f"{r.get('lane')} {r.get('scale')} {r.get('workload')} {r.get('backend')}"
            v = r.get(c.field)
            if not _present(v):
                err = next((r.get(k) for k in sorted(r) if str(k).endswith("_readback_error") and _present(r.get(k))), None)
                why = f" ({err})" if err else ""
                bad.append({"kind": "NOT STAMPED", "key": o.key, "field": c.field, "where": where,
                            "text": f"NOT STAMPED {where}: no `{c.field}` for `{o.key}` ({o.setting}){why}"})
                continue
            problem = o.check(r, v)
            if problem:
                bad.append({"kind": "WRONG", "key": o.key, "field": c.field, "where": where,
                            "text": f"WRONG {where}: `{c.field}` {problem} (`{o.key}`)"})
    return bad, judged
