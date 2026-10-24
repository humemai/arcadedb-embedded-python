"""CrateDB plumbing shared by the three lanes (documents analytics, dense, time series).

CrateDB 6.4.6 over the PostgreSQL wire (port 5432, user `crate`, schema `doc`), the wire the PostgreSQL arms use, through the
`psycopg` the client image already has. Nothing here is a tuning knob of ours; every setting is either the vendor's documented
recommendation or the matched value of the lane, and every one is READ BACK from the engine onto the row (F15):

  * shards: one per CPU of the cell for the scan lanes ("The general advice is to calculate with 1 shard per CPU as a starting
    point", https://cratedb.com/docs/guide/performance/sharding.html); ONE for the dense lane, so one HNSW graph answers
    each query, as Elasticsearch's one-shard index does (FAIRNESS F7, l3d_dense.CrateDense);
  * replicas: 0, the only value a one-node cluster can place;
  * translog durability: `ASYNC` (the relaxed class, fsync every `translog.sync_interval`, 5 s by default) or `REQUEST` (the
    strict class and the engine default), https://cratedb.com/docs/crate/reference/en/latest/sql/statements/create-table.html;
  * refresh: the engine default (1 s, only while the table is not idle), followed by an explicit `REFRESH TABLE` once the load
    is done, so the first timed read sees every row. The documentation: "In CrateDB new written records are not immediately
    visible. A user has to either invoke the REFRESH statement or wait for an automatic background refresh."

The load goes through multi-row `INSERT ... SELECT * FROM unnest(...)` for scalar columns (one statement per batch of
column-arrays; CrateDB's bulk idiom over the PostgreSQL wire, which has no COPY) and through prepared single-row INSERTs
batched by psycopg for `float_vector` columns, because `unnest` does not take arrays of vectors in 6.4.6 ("Arrays of
float_vector are not supported", probed 2026-10-23).
"""
import os

import bench_common

PG_PORT = int(os.environ.get("BENCH_SERVER_PORT", "5432"))
HTTP_PORT = 4200
DSN = "host={host} port=" + str(PG_PORT) + " user=crate dbname=doc"


def host():
    return os.environ.get("BENCH_SERVER_HOST", "localhost")


def connect(autocommit=True):
    import psycopg
    return psycopg.connect(DSN.format(host=host()), autocommit=autocommit)


def ncpu():
    """The cell's CPU count, from the mask (FAIRNESS F6): never os.cpu_count()."""
    return len(os.sched_getaffinity(0))


def with_clause(shards, extra=None):
    """`CLUSTERED INTO <n> SHARDS WITH (...)` for one table, at the durability class the cell asked for."""
    opts = {"number_of_replicas": 0, "translog.durability": bench_common.cratedb_expected()}
    opts.update(extra or {})
    body = ", ".join(f'"{k}" = {v if isinstance(v, int) else repr(v)}' for k, v in opts.items())
    return f"CLUSTERED INTO {int(shards)} SHARDS WITH ({body})"


def readback(cx, table, shards_asked):
    """The engine's own answer for the node and for one table: (row_extra dict, durability string).

    Node: `sys.nodes` (heap max, processors the JVM sees). Table: `information_schema.tables` (shards, replicas, the translog
    settings). A table that did not take the shards or the durability asked for raises, so the cell does not publish a label
    the engine did not run."""
    with cx.cursor() as c:
        c.execute("SELECT version()")
        version = c.fetchone()[0].split(" (")[0]
        c.execute("SELECT heap['max'], os_info['available_processors'] FROM sys.nodes")
        heap_max, procs = c.fetchone()
        c.execute("SELECT number_of_shards, number_of_replicas, settings['translog']['durability'], "
                  "settings['translog']['sync_interval'], settings['refresh_interval'] "
                  "FROM information_schema.tables WHERE table_schema = 'doc' AND table_name = %s", (table,))
        shards, replicas, dur, sync_ms, refresh = c.fetchone()
    if int(shards) != int(shards_asked):
        raise RuntimeError(f"cratedb: {table} has {shards} shards, {shards_asked} asked: the cell is not the one we specified")
    if int(replicas) != 0:
        raise RuntimeError(f"cratedb: {table} has {replicas} replicas, 0 asked")
    dur = str(dur or "REQUEST").upper()
    # an unset sync_interval reads back as NULL or 5000 ms, the engine default
    sync_ms = int(sync_ms) if sync_ms not in (None, "") else bench_common.CRATEDB_SYNC_INTERVAL_MS
    string = bench_common.cratedb_durability_string(dur, sync_ms)
    extra = {"cratedb_heap_max_mib": int(heap_max) >> 20, "cratedb_processors": int(procs),
             "cratedb_shards": int(shards), "cratedb_replicas": int(replicas),
             "cratedb_translog_durability": dur, "cratedb_translog_sync_interval_ms": sync_ms,
             "cratedb_refresh_interval_ms": None if refresh in (None, "") else int(refresh)}
    return version, extra, string


def refresh(cx, table):
    """REFRESH TABLE: makes every loaded row visible to the timed reads (inside the build timer, as PostgreSQL's ANALYZE is)."""
    with cx.cursor() as c:
        c.execute(f"REFRESH TABLE {table}")
