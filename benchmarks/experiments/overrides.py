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
    applies: Optional[Callable] = None       # (row) -> True when the override is in force for that row; None = every row


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


_UNIT = {"": 1, "b": 1, "k": 1 << 10, "kb": 1 << 10, "kib": 1 << 10, "m": 1 << 20, "mb": 1 << 20,
         "mib": 1 << 20, "g": 1 << 30, "gb": 1 << 30, "gib": 1 << 30, "t": 1 << 40,
         "tb": 1 << 40, "tib": 1 << 40}


def size_bytes(text):
    """'1.50GiB' and '1.5g' and '512m' as bytes, or None."""
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]*)\s*", str(text))
    if not m or m.group(2).lower() not in _UNIT:
        return None
    return float(m.group(1)) * _UNIT[m.group(2).lower()]


def duration_words(text):
    """'5s' as ('5', 'seconds'), '15m' as ('15', 'minutes'), or None."""
    m = re.fullmatch(r"\s*(\d+)\s*(ms|s|m|h|d)\s*", str(text))
    if not m:
        return None
    n, unit = m.group(1), {"ms": "millisecond", "s": "second", "m": "minute",
                           "h": "hour", "d": "day"}[m.group(2)]
    return n, unit + ("" if n == "1" else "s")


def _values(rows, field):
    """The distinct non-blank values a field takes on these rows, sorted."""
    return sorted({str(r.get(field)) for r in rows if _present(r.get(field))})


# ---------------------------------------------------------------------------
# the checks: one row's stamped value against what the sentence claims

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


def _pagecache_matches_the_cell(row, v):
    """The engine's page cache against what the runner passed: the answer is
    the cell's memory after the heap and a reserve, never the image's fixed
    default, and the two spellings ('1.50GiB' and '1.5g') must agree."""
    got = size_bytes(v)
    if got is None:
        return f"reads {v!r}, not a size"
    asked = row.get("server_pagecache")
    if not _present(asked):
        return None
    want = size_bytes(asked)
    if want is None:
        return f"the container was given {asked!r}, not a size"
    return None if abs(got - want) <= 0.01 * want else f"the engine reports {v} where the cell passed {asked}"


def _checkpoint_is_five_seconds(row, v):
    return None if str(v).strip() == "5s" else f"reads {v!r}, the cell sets 5s"


def _cap_is_the_runner_cap(row, v):
    want = runner_cap()
    got = _int(v)
    if got is None:
        return f"reads {v!r}, not a count"
    if want is None:
        return None
    return None if got == want else f"the server reports {got:,} where the runner launches it with {want:,}"


def _body_limit_is_the_runner_limit(row, v):
    want = runner_body_limit()
    got = _int(v)
    if got is None:
        return f"reads {v!r}, not a size in bytes"
    if want is not None and got != want:
        return f"the server reports {got:,} bytes where the runner launches it with {want:,}"
    src = str(row.get("server_http_body_max_source") or "")
    return None if src else "no `server_http_body_max_source`, so a reader cannot tell a read-back from a request"


# The pins measured BEFORE the limit existed (CAMPAIGN section 7 row 75): the October pin is a September commit, and a server built from it
# has no `arcadedb.server.httpBodyContentMaxSize`, so the override is not in force for its rows and no sentence about it may stand under
# a table built from them.
PRE_BODY_LIMIT_PINS = ("417314c18",)


def _body_limit_in_force(row):
    return not str(row.get("engine_commit") or "").startswith(PRE_BODY_LIMIT_PINS)


def _hierarchy_is_on(row, v):
    bad = _is_true(row, v)
    if bad:
        return bad
    src = str(row.get("arcadedb_add_hierarchy_source") or "")
    return None if src else "no `arcadedb_add_hierarchy_source`, so a reader cannot tell a read-back from a request"


def _count_at_ingest_end(row, v):
    n = _int(v)
    return None if n is not None and n >= 0 else f"reads {v!r}, not a count of samples"


# The compaction interval l4_tsbs declares on ArcadeDB's native time-series type (`COMPACTION_INTERVAL 1 HOURS`,
# CAMPAIGN section 7 row 54), in the milliseconds the engine reports back (`compactionBucketIntervalMs`).
TS_COMPACTION_MS = 3_600_000


# The pins measured BEFORE the compaction interval was declared (CAMPAIGN section 7 row 54): their l4 rows ran
# without it and carry no stamp, so the override is not in force for them, no sentence about it may stand under a
# table built from them, and the fairness gate does not ask them for the read-back.
PRE_COMPACTION_PINS = ("417314c18",)


def _compaction_in_force(row):
    return not str(row.get("engine_commit") or "").startswith(PRE_COMPACTION_PINS)


def _compaction_is_one_hour(row, v):
    n = _int(v)
    return None if n == TS_COMPACTION_MS else f"reads {v!r}, not the one-hour interval the sentence names"


# ---------------------------------------------------------------------------
# the sentences

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


def _neo4j_pagecache(rows):
    return ("Neo4j's page cache is sized from the memory the run was given, what is left after its "
            "heap and a fixed reserve, where its image would set one small fixed size whatever the "
            "container holds.", [])


def _neo4j_checkpoint(rows):
    got = _values(rows, "neo4j_checkpoint_interval")
    dflt = _values(rows, "neo4j_checkpoint_interval_default")
    a = duration_words(got[0]) if len(got) == 1 else None
    b = duration_words(dflt[0]) if len(dflt) == 1 else None
    if a and b:
        return (f"Neo4j checkpoints its store every {a[0]} {a[1]}, where its default is every {b[0]} "
                f"{b[1]}, so that the disk reading taken after a run finds the data on disk.", [a[0], b[0]])
    if a:
        return (f"Neo4j checkpoints its store every {a[0]} {a[1]} instead of at its much longer default, "
                f"so that the disk reading taken after a run finds the data on disk.", [a[0]])
    return ("Neo4j checkpoints its store at a short fixed interval instead of its much longer default, "
            "so that the disk reading taken after a run finds the data on disk.", [])


def _arcadedb_hierarchy(rows):
    return ("ArcadeDB's vector index is built as a layered graph, the structure the hnswlib family "
            "uses; the engine's own default is a single flat layer.", [])


def _arcadedb_cap(rows, constant=None):
    vals = _values(rows, "server_query_max_heap_elements")
    n = vals[0] if len(vals) == 1 else (str(constant) if constant else None)
    head = ("The ArcadeDB server is started with the limit on the records or groups that one sorting, "
            "grouping, or distinct query may hold in memory")
    tail = (", while the embedded package leaves that limit at the engine's default, which grows with "
            "the heap, so the two deployments can run different limits.")
    if n and _int(n) is not None:
        shown = f"{_int(n):,}"
        return f"{head} fixed at {shown}{tail}", [shown]
    return f"{head} fixed explicitly{tail}", []


def _bytes_text(n):
    """68719476736 as ('64', 'GiB'), 104857600 as ('100', 'MiB'); None when it is not a whole number of KiB, MiB, GiB, or TiB."""
    n = _int(n)
    if n is None or n <= 0:
        return None
    for unit, size in (("TiB", 1 << 40), ("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n % size == 0:
            return str(n // size), unit
    return None


def _arcadedb_body_limit(rows):
    got = _values(rows, "server_http_body_max_bytes")
    dflt = _values(rows, "server_http_body_max_default")
    a = _bytes_text(got[0]) if len(got) == 1 else None
    b = _bytes_text(dflt[0]) if len(dflt) == 1 else None
    head = "The ArcadeDB server that loads its data through the bulk endpoint is started with the limit on one HTTP request body raised "
    if a and b:
        lead = f"{head}to {a[0]} {a[1]}, where the engine's default is {b[0]} {b[1]}. The default"
        values = [a[0], b[0]]
    elif a:
        lead = f"{head}to {a[0]} {a[1]}, above the engine's default. That default"
        values = [a[0]]
    else:
        lead = f"{head}above the engine's default. That default"
        values = []
    return (f"{lead} refuses the single streamed request that carries the larger graph and cross-model loads (the engine's own message "
            "says to raise the limit or split the payload), so the load stays one request, as the embedded arm's is one call. The limit "
            "caps how much one request may carry and is no speed setting; the embedded arms have no HTTP body.", values)


def _arcadedb_ts_compaction(rows):
    return ("ArcadeDB's native time-series type is created with a one-hour compaction interval, the bucket of "
            "the hourly aggregate on this table, so compaction cuts its sealed blocks at the boundaries of the "
            "hourly buckets. Its default cuts them wherever they fill. No other engine on this table has "
            "such a setting.", [])


def _arcadedb_ts_acceptance(rows):
    return ("ArcadeDB's native time-series ingest rate is timed until the engine has accepted every "
            "point. The engine goes on sealing the newest points into compacted storage after that, and "
            "the benchmark waits for the sealing to finish before the first query, outside the timer, "
            "so the rate does not include it.", [])


# ---------------------------------------------------------------------------
# the registry

# The cap the runner launches every served ArcadeDB arm with, read from the
# server_env the runner itself passes, so the value cannot differ from what ran.
CAP_PROPERTY = "arcadedb.queryMaxHeapElementsAllowedPerOp"


def served_arcadedb_from_runner():
    """(lane, backend) for every runner arm whose server is launched with the
    cap. `test_overrides` holds CAP_CARRIERS equal to this, so a served arm
    added by copying one of those dicts cannot join the page without a
    sentence. Imports the runner, so it is for tests and gates only."""
    import runner
    out = []
    for lane, spec in runner.LANES.items():
        for be in spec[1]:
            env = " ".join(str(x) for x in (runner.BACKENDS.get(be) or {}).get("server_env", []))
            if f"-D{CAP_PROPERTY}=" in env:
                out.append((lane, be))
    return sorted(out)


def runner_cap():
    """The cap value the runner passes, or None when it cannot be read."""
    try:
        import runner
    except Exception:  # noqa: BLE001 - the gates must still import without a docker host
        return None
    seen = set()
    for cfg in runner.BACKENDS.values():
        env = " ".join(str(x) for x in cfg.get("server_env", []))
        seen.update(re.findall(rf"-D{re.escape(CAP_PROPERTY)}=(\d+)", env))
    return int(next(iter(seen))) if len(seen) == 1 else None


# Every served ArcadeDB arm of a lane that feeds a page table. Two lanes are
# left out on purpose: `l1` (the retired tabular lane, no table) and `e4`
# (its table is artifact-backed and takes the sentence through Override.tables).
CAP_CARRIERS = (
    ("l1tpc", "arcadedb_server"), ("l1tpc", "arcadedb_imgdefaults_server"),
    ("l2", "arcadedb_graph_server"),
    ("l3s", "arcadedb_sparse_server"), ("l3s", "arcadedb_sparse_server_fp32"),
    ("l3d", "arcadedb_dense_server"), ("l3d", "arcadedb_dense_server_int8"),
    ("l4", "arcadedb_ts_doc_server"), ("l4", "arcadedb_ts_native_server"),
    ("e2", "arcadedb_e2_server"),
    ("lifecycle", "arcadedb_server"),
    ("restart", "arcadedb_server"), ("restart", "arcadedb_graph_server"),
    ("restart", "arcadedb_dense_server"), ("restart", "arcadedb_ts_native_server"),
)

# THE HTTP BODY LIMIT (CAMPAIGN section 7 row 75): raised only on the arms whose loader POSTs to /api/v1/batch, in one streamed request.
BODY_PROPERTY = "arcadedb.server.httpBodyContentMaxSize"


def batch_arcadedb_from_runner():
    """(lane, backend) for every runner arm whose server is launched with the body limit. `test_overrides` holds BODY_LIMIT_CARRIERS equal
    to this and to the arms whose lane code reaches the batch endpoint. Imports the runner, so it is for tests and gates only."""
    import runner
    out = []
    for lane, spec in runner.LANES.items():
        for be in spec[1]:
            env = " ".join(str(x) for x in (runner.BACKENDS.get(be) or {}).get("server_env", []))
            if f"-D{BODY_PROPERTY}=" in env:
                out.append((lane, be))
    return sorted(out)


def runner_body_limit():
    """The body limit (bytes) the runner passes, or None when it cannot be read or the arms disagree."""
    try:
        import runner
    except Exception:  # noqa: BLE001 - the gates must still import without a docker host
        return None
    seen = set()
    for cfg in runner.BACKENDS.values():
        env = " ".join(str(x) for x in cfg.get("server_env", []))
        seen.update(re.findall(rf"-D{re.escape(BODY_PROPERTY)}=(\d+)", env))
    return int(next(iter(seen))) if len(seen) == 1 else None


# Every served ArcadeDB arm of a lane that feeds a page table AND loads through the batch endpoint: the graph table's served arm
# (l2_graph.ArcadeGraphServer), the restart lane's graph model (it loads through the same adapter), and the cross-model table's
# (e2_hybrid.ArcadeE2Server). Every other served arm loads through the command endpoint in requests of a few thousand rows.
BODY_LIMIT_CARRIERS = (
    ("l2", "arcadedb_graph_server"),
    ("e2", "arcadedb_e2_server"),
    ("restart", "arcadedb_graph_server"),
)

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
    Override(
        key="neo4j_pagecache",
        setting="server.memory.pagecache.size fitted to the cell",
        carriers=(Carrier("l2", "neo4j_graph", "neo4j_pagecache"),
                  Carrier("l3d", "neo4j_dense", "neo4j_pagecache"),
                  Carrier("l3d", "neo4j_dense_int8", "neo4j_pagecache"),
                  Carrier("e2", "neo4j_e2", "neo4j_pagecache"),
                  Carrier("e2", "composed_qdrant_neo4j", "neo4j_pagecache"),
                  Carrier("restart", "neo4j_graph", "neo4j_pagecache")),
        check=_pagecache_matches_the_cell, sentence=_neo4j_pagecache,
        says=(r"Neo4j", r"page cache"),
        companions=("neo4j_readback_error",)),
    Override(
        key="neo4j_checkpoint",
        setting="db.checkpoint.interval.time=5s",
        carriers=(Carrier("l2", "neo4j_graph", "neo4j_checkpoint_interval"),
                  Carrier("e2", "composed_qdrant_neo4j", "neo4j_checkpoint_interval"),
                  Carrier("restart", "neo4j_graph", "neo4j_checkpoint_interval")),
        check=_checkpoint_is_five_seconds, sentence=_neo4j_checkpoint,
        says=(r"Neo4j", r"checkpoint"),
        companions=("neo4j_checkpoint_interval_default",)),
    Override(
        key="arcadedb_hierarchy",
        setting='LSM_VECTOR METADATA {"addHierarchy": true}',
        carriers=(Carrier("l3d", "arcadedb_dense_embedded", "arcadedb_add_hierarchy"),
                  Carrier("l3d", "arcadedb_dense_embedded_int8", "arcadedb_add_hierarchy"),
                  Carrier("l3d", "arcadedb_dense_server", "arcadedb_add_hierarchy"),
                  Carrier("l3d", "arcadedb_dense_server_int8", "arcadedb_add_hierarchy"),
                  Carrier("restart", "arcadedb_dense_server", "arcadedb_add_hierarchy")),
        check=_hierarchy_is_on, sentence=_arcadedb_hierarchy,
        says=(r"ArcadeDB", r"vector index", r"layer|hierarch"),
        companions=("arcadedb_add_hierarchy_source", "arcadedb_readback_error")),
    Override(
        key="arcadedb_query_cap",
        setting=f"-D{CAP_PROPERTY}",
        carriers=tuple(Carrier(lane, be, "server_query_max_heap_elements") for lane, be in CAP_CARRIERS),
        check=_cap_is_the_runner_cap, sentence=_arcadedb_cap,
        says=(r"ArcadeDB server", r"limit", r"embedded", r"query"),     # `query`: the body-limit sentence also names a limit and the embedded arm
        tables=("e4",), constant=lambda: _arcadedb_cap([], runner_cap()),
        companions=("server_query_max_heap_source",)),
    Override(
        key="arcadedb_http_body_limit",
        setting=f"-D{BODY_PROPERTY}",
        carriers=tuple(Carrier(lane, be, "server_http_body_max_bytes") for lane, be in BODY_LIMIT_CARRIERS),
        check=_body_limit_is_the_runner_limit, sentence=_arcadedb_body_limit,
        says=(r"ArcadeDB server", r"request body", r"embedded"),
        companions=("server_http_body_max_source", "server_http_body_max_default"),
        applies=_body_limit_in_force),
    Override(
        key="arcadedb_ts_acceptance",
        setting="ingest timer stops at wait_completion()",
        carriers=(Carrier("l4", "arcadedb_ts_native", "ts_mutable_at_ingest_end"),
                  Carrier("l4", "arcadedb_ts_native_server", "ts_mutable_at_ingest_end")),
        check=_count_at_ingest_end, sentence=_arcadedb_ts_acceptance,
        says=(r"ArcadeDB", r"time-series", r"sealing")),
    Override(
        key="arcadedb_ts_compaction_interval",
        setting="COMPACTION_INTERVAL 1 HOURS",
        carriers=(Carrier("l4", "arcadedb_ts_native", "ts_compaction_interval_ms"),
                  Carrier("l4", "arcadedb_ts_native_server", "ts_compaction_interval_ms")),
        check=_compaction_is_one_hour, sentence=_arcadedb_ts_compaction,
        says=(r"ArcadeDB", r"time-series", r"compaction", r"hour"),
        companions=("ts_compaction_interval", "ts_compaction_interval_readback_error"),
        applies=_compaction_in_force),
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

def applicable(table_lane, backend_keys, rows=None):
    """The overrides whose carriers sit on this table's lane and appear among
    its entries' backends. With `rows` given, an override that is in force only for some rows
    (`applies`) counts only when at least one such row of a carrier is behind the table."""
    keys = {str(k) for k in backend_keys}
    out = []
    for o in OVERRIDES:
        mine = {c.backend for c in o.carriers if c.lane == table_lane and c.backend in keys}
        if not mine:
            continue
        if rows is not None and o.applies is not None and not any(
                r.get("lane") == table_lane and r.get("backend") in mine and o.applies(r) for r in rows):
            continue
        out.append(o)
    return out


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
        if o.applies is not None:
            sel = [r for r in sel if o.applies(r)]
            if not sel:
                continue          # every row behind this table predates the override: a sentence about it would be false
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
        hit = list(applicable(lane_of(tid), keys, rows)) if lane_of(tid) else []
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
            if o.applies is not None and not o.applies(r):
                continue
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
