#!/usr/bin/env python3
"""Lifecycle on LadybugDB, Chroma, LanceDB, and sqlite-vec, embedded: comparator arms of l5_lifecycle.py (2026-10-02).

DECISIONS #131 item 5 (CAMPAIGN.md section 7 row 40, queued last by #133): each
embedded engine on the page runs the lifecycle workloads its model supports.
SQLite and DuckDB are l5_lifecycle_sql.py and SurrealDB embedded is
l5_lifecycle_surreal.py. This module is the other four in-process engines the
page runs, each through its own Python package, in the image its other arms
run in:

  LadybugDB   ladybug (dbbench:client): Cypher, node and rel tables, the
              official `vector` extension's HNSW
  Chroma      chromadb (dbbench:dense): a PersistentClient's collections and
              their HNSW
  LanceDB     lancedb (dbbench:dense): a directory of Lance tables, BTree
              scalar indexes and an IVF_HNSW_FLAT vector index
  sqlite-vec  sqlite-vec (dbbench:dense), loaded into SQLite under WAL with
              synchronous=NORMAL, as on its dense arm (DECISIONS #70)

WHAT IS THE SAME as the SQL and SurrealDB arms, so a row reads against the
ArcadeDB row above it: the situations, sizes, and generators (the same 7919
fan-out, the same seeded vectors), the session timed as open + action +
close, the mode set including the stale-reopen cycles, the cold column after
a verified page-cache eviction, the cold start in a fresh subprocess, and
each read's answer digested under DECISIONS #88. The build streams its input
in batches, never as one list (BUGS F161). Every vector index is cosine at
the dense lane's matched point (M 16, ef_construction 100, ef_search 100),
unquantized, as ArcadeDB's LSM_VECTOR is in this situation.

WHAT AN OPEN IS. ArcadeDB's open_database loads the schema of every type the
database holds. LadybugDB and sqlite-vec open one database file, and that is
their open. Chroma's and LanceDB's database is a directory of collections or
tables, so their open is the client or connection AND a handle on every
collection or table the database holds; a handle the session never took
would leave that work to the action. Chroma loads a collection's HNSW on its
first query and LanceDB reads an index on its first search, so that cost
lands in the action, as ArcadeDB's lazy vector graph load does.

WHAT A CLOSE IS. LadybugDB closes its connection and database; Chroma's
client.close() releases the client's system and stops it when it was the
last (chromadb 1.5.9, Client.close); sqlite-vec closes the SQLite connection.
LanceDB 0.39.0 exposes no close on the connection or on a table (each write
commits a new table version as it is made), so its session drops its handles,
which is all a caller can do, and the row says so (`close_note`).

RESOURCES (FAIRNESS F3/F6). LadybugDB sizes its thread pool and buffer pool
from the host when left at 0, so both are fitted as on its other arms
(threads from sched_getaffinity, the pool at the engine's own 0.8 of the
cgroup's memory.max) and the thread count is read back. Chroma's and
LanceDB's Rust runtimes follow the cpuset (5 tokio threads after an open
under a 4-CPU cpuset against 17 without one on the 16-CPU laptop,
2026-10-02, FAIRNESS F6), and SQLite is single-threaded, so nothing is
fitted there; every row records the threads the process holds after its
first open (`lc_threads_after_open`).

DURABILITY, read back where the engine can be asked (sqlite-vec's PRAGMAs,
Chroma's journal mode), and named from a strace where it cannot (bench_common
DURABILITY_*). None of LadybugDB, Chroma, or LanceDB has a setting for it.

WHAT EACH ENGINE CAN EXPRESS (every other situation is DECLARED with the
engine's own answer to the statement that would have built it, DECISIONS #92):
  LadybugDB   empty, doc, graph, vector, ts. A node table must have a
              primary key and LadybugDB keeps a hash index on it, so its doc,
              graph, and ts tables each carry that one index where ArcadeDB's
              carry none (disclosed on the row). doc_idx10: hash indexes on
              primary keys only. graph_gav: PROJECT_GRAPH's projected graph
              belongs to one connection and is gone at close. sparse: the
              vector index takes fixed-size arrays only.
  Chroma      empty, vector. Its only structure is a collection of embedded
              records, so doc, doc_idx10, and ts cannot be built (a record
              needs an embedding); graph and graph_gav have no traversal in
              its where filter; sparse indexing is not enabled in local mode.
              Its Scratch is a collection, so each Scratch record carries a
              one-dimensional embedding.
  LanceDB     empty, doc, doc_idx10 (ten BTree indexes), ts, vector. graph
              and graph_gav: the local connection runs no query language;
              sparse: the vector index takes fixed-size lists only.
  sqlite-vec  empty, vector. Its one structure is the vec0 virtual table,
              which needs a vector column and cannot be indexed, so doc,
              doc_idx10, and ts are the SQLite arm's plain tables, not its;
              graph and graph_gav have no graph query language; sparse: vec0
              columns are dense float, int8, or bit vectors. vec0 is an exact
              scan with no index to drop, so the drop cycle is not run.
"""
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import time

import bench_common
import pagecache

import l5_lifecycle as L
from l5_lifecycle_sql import EF_CONSTRUCTION, FANOUT, HNSW_M, _first_line, _vectors

DIM = L.DIM
EF_SEARCH = 100              # the dense lane's matched search point
COPY_BATCH = 50_000          # rows per vector COPY and per LanceDB record batch; streamed, never one list
# A LadybugDB COPY into a rel table costs more the more the table holds (a laptop probe, 2026-10-02, 4M edges:
# each 50,000-row COPY took longer than the one before it, the whole load about four times one-million-row
# batches), so the scalar tables load in larger batches. Still streamed: a batch of two integers per row is
# small, where a million 64-float vectors as Python lists would not be.
LADYBUG_SCALAR_BATCH = 1_000_000
GRAPH_SEEDS = 100 // FANOUT  # L.READS["graph"] expands 100 edges, which at FANOUT 4 is 25 source vertices


def _rm(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def _batched(rows, size):
    buf = []
    for r in rows:
        buf.append(r)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def _threads():
    """{thread name: count} for this process, the trailing digits dropped (tokio-rt-worker, lance-cpu, ...)."""
    import collections
    import re
    names = collections.Counter()
    for t in os.listdir("/proc/self/task"):
        try:
            with open(f"/proc/self/task/{t}/comm") as fh:
                names[re.sub(r"[-_ ]?\d+$", "", fh.read().strip())] += 1
        except OSError:
            continue
    return dict(sorted(names.items()))


def _probe_vec():
    return [0.5] * DIM


class Arm:
    """One engine. `path` is the directory its database lives in, evicted whole for the cold column."""
    name = "?"
    path = "?"
    drop_na = None           # why the drop cycle does not apply, for an engine with no separate index
    close_note = None
    DURABILITY = None        # the engine's string, for a declared row (nothing was built to read it back from)

    def __init__(self):
        self.row = {}            # what the engine reported, for the row

    def version(self):
        raise NotImplementedError

    def durability(self):
        raise NotImplementedError

    def declared(self, situation):
        """(statement tried, why, engine's answer) for a situation this engine cannot build, else None."""
        return None


# ---------------------------------------------------------------- LadybugDB

class Ladybug(Arm):
    name = "ladybug_lifecycle"
    path = "/lcdb/lc_ladybug"
    DURABILITY = bench_common.DURABILITY_LADYBUG
    db_file = "/lcdb/lc_ladybug/lc.lbdb"
    READS = {
        "doc": "MATCH (d:D) RETURN count(*) AS n",
        "ts": "MATCH (t:T) RETURN count(*) AS n",
        "graph": f"MATCH (a:P)-[:E]->(b:P) WHERE a.id < {GRAPH_SEEDS} RETURN count(b) AS n",
    }
    PK_NOTE = ("a LadybugDB node table must have a primary key and the engine keeps a hash index on it, so "
               "this situation's table carries that one index where ArcadeDB's carries none")

    def __init__(self):
        super().__init__()
        # The graph lane's fit (l2_graph._ladybug_fit, FAIRNESS F6, BUGS F160): left at 0 LadybugDB sizes its
        # thread pool from the host's CPUs and its buffer pool at 0.8 of the host's RAM.
        self.threads = len(os.sched_getaffinity(0))
        try:
            with open("/sys/fs/cgroup/memory.max") as fh:
                text = fh.read().strip()
        except OSError:
            text = ""
        self.pool = int(int(text) * 0.8) if text.isdigit() else None
        self.kw = {"max_num_threads": self.threads}
        if self.pool:
            self.kw["buffer_pool_size"] = self.pool

    def version(self):
        import importlib.metadata
        return f"ladybug {importlib.metadata.version('ladybug')}"

    def durability(self):
        return self.DURABILITY

    def declared(self, situation):
        import ladybug
        if situation not in ("doc_idx10", "graph_gav", "sparse"):
            return None
        _rm(self.path)
        os.makedirs(self.path)
        db = ladybug.Database(self.db_file, **self.kw)
        cx = ladybug.Connection(db)
        try:
            if situation == "doc_idx10":
                cx.execute("CREATE NODE TABLE D(id INT64, p0 INT64, PRIMARY KEY(id))")
                stmt = "CREATE INDEX d_p0 FOR (d:D) ON (d.p0)"
                why = "no secondary index: a node table's one index is the hash index on its primary key"
                try:
                    cx.execute(stmt)
                except Exception as e:  # noqa: BLE001 - the error IS the evidence
                    return stmt, why, _first_line(e)
                raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the doc_idx10 declaration is wrong")
            if situation == "sparse":
                cx.execute("CREATE NODE TABLE S(id INT64, tokens INT64[], weights FLOAT[], PRIMARY KEY(id))")
                stmt = "CALL CREATE_VECTOR_INDEX('S', 's_idx', 'weights')"
                why = ("no sparse-vector index: the vector extension indexes fixed-size FLOAT, DOUBLE, or INT8 "
                       "arrays, one dense vector per row")
                cx.execute("INSTALL vector")
                cx.execute("LOAD vector")
                try:
                    cx.execute(stmt)
                except Exception as e:  # noqa: BLE001
                    return stmt, why, _first_line(e)
                raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the sparse declaration is wrong")
            # graph_gav: the statement SUCCEEDS, and the evidence is what a reopened database holds.
            cx.execute("CREATE NODE TABLE P(id INT64, PRIMARY KEY(id))")
            cx.execute("CREATE REL TABLE E(FROM P TO P)")
            stmt = "CALL PROJECT_GRAPH('lcv', ['P'], ['E'])"
            cx.execute(stmt)
            cx.close()
            db.close()
            db = ladybug.Database(self.db_file, **self.kw)
            cx = ladybug.Connection(db)
            r = cx.execute("CALL SHOW_PROJECTED_GRAPHS() RETURN *")
            held = []
            while r.has_next():
                held.append(r.get_next())
            if held:
                raise SystemExit(f"{self.name}: a projected graph survived a reopen ({held}), so the graph_gav "
                                 f"declaration is wrong")
            return (stmt + ", closed, reopened, then CALL SHOW_PROJECTED_GRAPHS()",
                    "no persisted analytical view: PROJECT_GRAPH builds a projected graph that belongs to one "
                    "connection and is gone at close, so no session can reopen one",
                    "no projected graph after the reopen (SHOW_PROJECTED_GRAPHS returned no rows)")
        finally:
            cx.close()
            db.close()

    def _copy(self, cx, table, names, rows):
        """COPY `rows` (tuples) into `table` from Arrow batches, the engine's bulk path (l3d LadybugDense)."""
        import pyarrow as pa
        for batch in _batched(rows, COPY_BATCH if "emb" in names else LADYBUG_SCALAR_BATCH):
            cols = list(zip(*batch))
            arrays = {}
            for k, nm in enumerate(names):
                if nm == "emb":
                    flat = pa.array([x for v in cols[k] for x in v], type=pa.float32())
                    arrays[nm] = pa.FixedSizeListArray.from_arrays(flat, DIM)
                else:
                    arrays[nm] = pa.array(cols[k], type=pa.string() if nm == "sensor" else None)
            tbl = pa.table(arrays)  # noqa: F841 - COPY reads the local by name
            cx.execute(f"COPY {table} FROM tbl")

    def build(self, situation, n):
        import ladybug
        _rm(self.path)
        os.makedirs(self.path)
        db = ladybug.Database(self.db_file, **self.kw)
        cx = ladybug.Connection(db)
        q = cx.execute
        q("CREATE NODE TABLE Scratch(n INT64, PRIMARY KEY(n))")
        if situation == "doc":
            q("CREATE NODE TABLE D(id INT64, PRIMARY KEY(id))")
            self._copy(cx, "D", ["id"], ((i,) for i in range(n)))
            self.row["situation_note"] = self.PK_NOTE
        elif situation == "graph":
            q("CREATE NODE TABLE P(id INT64, PRIMARY KEY(id))")
            q("CREATE REL TABLE E(FROM P TO P)")
            self._copy(cx, "P", ["id"], ((i,) for i in range(n)))
            self._copy(cx, "E", ["src", "dst"],
                       ((i, (i + f * 7919) % n) for i in range(n) for f in range(1, FANOUT + 1)))
            self.row["situation_note"] = self.PK_NOTE
        elif situation == "vector":
            q("INSTALL vector")
            q("LOAD vector")
            q(f"CREATE NODE TABLE V(id INT64, emb FLOAT[{DIM}], PRIMARY KEY(id))")
            self._copy(cx, "V", ["id", "emb"], _vectors(n))
            # The dense arm's degree in LadybugDB's units: ml bounds the base layer, mu the upper one
            # (FAIRNESS F3), so ml = 2 x M and mu = M; cosine, as ArcadeDB's index in this situation.
            q(f"CALL CREATE_VECTOR_INDEX('V', 'v_emb', 'emb', mu := {HNSW_M}, ml := {2 * HNSW_M}, "
              f"efc := {EF_CONSTRUCTION}, metric := 'cosine')")
            self.row.update({"ladybug_ml": 2 * HNSW_M, "ladybug_mu": HNSW_M})
        elif situation == "ts":
            q("CREATE NODE TABLE T(ts INT64, sensor STRING, value DOUBLE, PRIMARY KEY(ts))")
            self._copy(cx, "T", ["ts", "sensor", "value"],
                       ((1_700_000_000_000 + i * 1000, "s0", 1.0) for i in range(n)))
            self.row["situation_note"] = self.PK_NOTE + "; the timestamp is the key"
        elif situation != "empty":
            raise SystemExit(f"unknown situation {situation}")
        self.row["ladybug_threads"] = int(cx.execute('CALL current_setting("threads") RETURN *').get_next()[0])
        self.row["ladybug_buffer_pool_mib"] = (self.pool >> 20) if self.pool else None
        t = time.perf_counter()
        cx.close()
        db.close()
        return (time.perf_counter() - t) * 1000

    def open(self, situation):
        import ladybug
        db = ladybug.Database(self.db_file, **self.kw)
        cx = ladybug.Connection(db)
        if situation == "vector":
            cx.execute("LOAD vector")      # per database instance, as DuckDB's LOAD vss
        return db, cx

    def close(self, h):
        db, cx = h
        cx.close()
        db.close()

    def read(self, h, situation):
        _, cx = h
        if situation == "vector":
            r = cx.execute(f"CALL QUERY_VECTOR_INDEX('V', 'v_emb', $q, 10, efs := {EF_SEARCH}) RETURN node.id",
                           {"q": _probe_vec()})
            while r.has_next():
                r.get_next()
            return None
        text = self.READS.get(situation)
        if not text:
            return None
        r = cx.execute(text)
        cols, rows = r.get_column_names(), []
        while r.has_next():
            rows.append(dict(zip(cols, r.get_next())))
        return rows

    def write(self, h, seq):
        h[1].execute("CREATE (:Scratch {n: $n})", {"n": seq})

    def write_own(self, h, situation, i):
        cx = h[1]
        if situation == "vector":
            cx.execute("CREATE (:V {id: $i, emb: $e})", {"i": i, "e": [0.25] * DIM})
        elif situation == "graph":
            cx.execute("CREATE (:P {id: $i})", {"i": i})
        elif situation == "doc":
            cx.execute("CREATE (:D {id: $i})", {"i": i})
        elif situation == "ts":
            cx.execute("CREATE (:T {ts: $ts, sensor: 's0', value: 1.0})", {"ts": 1_800_000_000_000 + i})
        else:
            cx.execute("CREATE (:Scratch {n: $n})", {"n": i})

    def drop(self, h, situation):
        h[1].execute("CALL DROP_VECTOR_INDEX('V', 'v_emb')")

    def cold_code(self, situation):
        load = "; cx.execute('LOAD vector')" if situation == "vector" else ""
        return ("import ladybug",
                f"db = ladybug.Database({self.db_file!r}, **{self.kw!r}); cx = ladybug.Connection(db){load}",
                "cx.close(); db.close()")


# ---------------------------------------------------------------- Chroma

class Chroma(Arm):
    name = "chroma_lifecycle"
    path = "/lcdb/lc_chroma"
    DURABILITY = bench_common.DURABILITY_CHROMA
    COLLECTIONS = {"vector": "vectors"}     # beside "scratch" in every situation
    HNSW = {"hnsw:space": "cosine", "hnsw:M": HNSW_M, "hnsw:construction_ef": EF_CONSTRUCTION,
            "hnsw:search_ef": EF_SEARCH}
    drop_na = ("Chroma's HNSW index is its collection's own structure, with no call that drops the index and "
               "keeps the records")

    def version(self):
        import importlib.metadata
        return f"chromadb {importlib.metadata.version('chromadb')}"

    def durability(self):
        # Rollback-journal SQLite under the client, the journal mode read back from the file; no setting.
        import sqlite3
        try:
            cx = sqlite3.connect(f"file:{self.path}/chroma.sqlite3?mode=ro", uri=True)
            jm = str(cx.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            cx.close()
        except Exception as e:  # noqa: BLE001
            return bench_common.DURABILITY_CHROMA + f" (journal mode not read back: {type(e).__name__})"
        self.row["chroma_sqlite_journal_mode"] = jm
        return bench_common.DURABILITY_CHROMA if jm == "delete" else (
            bench_common.DURABILITY_CHROMA + f" (but the journal mode read back is {jm})")

    def declared(self, situation):
        import chromadb
        if situation in ("empty", "vector"):
            return None
        _rm(self.path)
        c = chromadb.PersistentClient(path=self.path)
        try:
            if situation in ("doc", "doc_idx10", "ts"):
                col = c.create_collection("records")
                stmt = "collection.add(ids=['0'], metadatas=[{'id': 0}])"
                why = ("every Chroma record is an embedding in a collection: add() takes a record only with an "
                       "embedding, or with a document, image, or URI that an embedding function turns into one, "
                       "so a table of plain records cannot be built")
                try:
                    col.add(ids=["0"], metadatas=[{"id": 0}])
                except Exception as e:  # noqa: BLE001
                    return stmt, why, f"{type(e).__name__}: {_first_line(e)}"
                raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the {situation} declaration is wrong")
            if situation in ("graph", "graph_gav"):
                col = c.create_collection("records")
                stmt = "collection.get(where={'id': {'$out': 'E'}})"
                why = ("no graph model or query language: Chroma reads records by id, by metadata or document "
                       "filter, or by nearest neighbour, and its where filter has no traversal")
                try:
                    col.get(where={"id": {"$out": "E"}})
                except Exception as e:  # noqa: BLE001
                    return stmt, why, f"{type(e).__name__}: {_first_line(e)}"
                raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the {situation} declaration is wrong")
            if situation == "sparse":
                from chromadb import Schema, SparseVectorIndexConfig
                stmt = ("create_collection('sparse', schema=Schema().create_index("
                        "config=SparseVectorIndexConfig(), key='sparse'))")
                why = "no sparse-vector index in a local (embedded) Chroma"
                try:
                    s = Schema()
                    s.create_index(config=SparseVectorIndexConfig(), key="sparse")
                    c.create_collection("sparse", schema=s)
                except Exception as e:  # noqa: BLE001
                    return stmt, why, f"{type(e).__name__}: {_first_line(e)}"
                raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the sparse declaration is wrong")
        finally:
            c.close()
        raise SystemExit(f"unknown situation {situation}")

    def build(self, situation, n):
        import chromadb
        _rm(self.path)
        c = chromadb.PersistentClient(path=self.path)
        # A collection, because Chroma holds nothing else, so each Scratch record carries a one-dimensional
        # embedding: add() refuses a record without one.
        c.create_collection("scratch", metadata={"hnsw:space": "l2"})
        self.row["scratch_note"] = ("Scratch is a Chroma collection, so each Scratch record carries a "
                                    "one-dimensional embedding: add() takes no record without one")
        if situation == "vector":
            col = c.create_collection("vectors", metadata=dict(self.HNSW))
            batch = min(5_000, c.get_max_batch_size())
            for b in _batched(_vectors(n), batch):
                col.add(ids=[str(i) for i, _ in b], embeddings=[v for _, v in b])
            self.row["chroma_hnsw"] = dict(self.HNSW)
        elif situation != "empty":
            raise SystemExit(f"unknown situation {situation}")
        t = time.perf_counter()
        c.close()
        return (time.perf_counter() - t) * 1000

    def open(self, situation):
        import chromadb
        c = chromadb.PersistentClient(path=self.path)
        cols = {"scratch": c.get_collection("scratch")}
        if situation in self.COLLECTIONS:
            cols[situation] = c.get_collection(self.COLLECTIONS[situation])
        return c, cols

    def close(self, h):
        h[0].close()

    def read(self, h, situation):
        if situation == "vector":
            h[1]["vector"].query(query_embeddings=[_probe_vec()], n_results=10)
        return None

    def write(self, h, seq):
        h[1]["scratch"].add(ids=[str(seq)], embeddings=[[float(seq)]])

    def write_own(self, h, situation, i):
        if situation == "vector":
            h[1]["vector"].add(ids=[str(i)], embeddings=[[0.25] * DIM])
        else:
            h[1]["scratch"].add(ids=[str(i)], embeddings=[[float(i)]])

    def cold_code(self, situation):
        get = "; c.get_collection('scratch')" + (
            f"; c.get_collection({self.COLLECTIONS[situation]!r})" if situation in self.COLLECTIONS else "")
        return "import chromadb", f"c = chromadb.PersistentClient(path={self.path!r}){get}", "c.close()"


# ---------------------------------------------------------------- LanceDB

class Lance(Arm):
    name = "lancedb_lifecycle"
    path = "/lcdb/lc_lance"
    DURABILITY = bench_common.DURABILITY_LANCEDB
    TABLES = {"doc": "D", "doc_idx10": "D", "ts": "T", "vector": "V"}   # beside Scratch in every situation
    close_note = ("lancedb 0.39.0 exposes no close on the connection or on a table; each write commits a new "
                  "table version as it is made, so the session drops its handles, which is all a caller can do")

    def version(self):
        import importlib.metadata
        return f"lancedb {importlib.metadata.version('lancedb')}"

    def durability(self):
        return self.DURABILITY

    def declared(self, situation):
        import lancedb
        import pyarrow as pa
        if situation not in ("graph", "graph_gav", "sparse"):
            return None
        _rm(self.path)
        db = lancedb.connect(self.path)
        if situation == "sparse":
            tbl = db.create_table("S", pa.table({
                "id": pa.array([0], type=pa.int64()),
                "tokens": pa.array([[1, 8]], type=pa.list_(pa.int32())),
                "weights": pa.array([[0.5, 0.5]], type=pa.list_(pa.float32()))}))
            from lancedb.index import IvfHnswFlat
            stmt = "table.create_index('weights', config=IvfHnswFlat(distance_type='dot'))"
            why = ("no sparse-vector index: LanceDB's vector indexes take a fixed-size list column, one dense "
                   "vector per row")
            try:
                tbl.create_index("weights", config=IvfHnswFlat(distance_type="dot"))
            except Exception as e:  # noqa: BLE001
                return stmt, why, f"{type(e).__name__}: {_first_line(e)}"
            raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the sparse declaration is wrong")
        stmt = "connection.execute_query('SELECT * FROM GRAPH_TABLE (lcg MATCH (a)-[e]->(b) COLUMNS (b.id))')"
        why = ("no graph model or query language: a LanceDB table is columnar rows read through the search and "
               "filter API, and the local connection runs no query language at all")
        try:
            db.execute_query("SELECT * FROM GRAPH_TABLE (lcg MATCH (a)-[e]->(b) COLUMNS (b.id))")
        except Exception as e:  # noqa: BLE001
            return stmt, why, f"{type(e).__name__}: {_first_line(e)}"
        raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the {situation} declaration is wrong")

    @staticmethod
    def _reader(schema, rows):
        """A RecordBatchReader over `rows` (tuples in schema order), so create_table streams the input."""
        import pyarrow as pa

        def batches():
            for b in _batched(rows, COPY_BATCH):
                cols = list(zip(*b))
                arrays = []
                for k, f in enumerate(schema):
                    if pa.types.is_fixed_size_list(f.type):
                        flat = pa.array([x for v in cols[k] for x in v], type=pa.float32())
                        arrays.append(pa.FixedSizeListArray.from_arrays(flat, DIM))
                    else:
                        arrays.append(pa.array(cols[k], type=f.type))
                yield pa.RecordBatch.from_arrays(arrays, schema=schema)
        return pa.RecordBatchReader.from_batches(schema, batches())

    def build(self, situation, n):
        import lancedb
        import pyarrow as pa
        from lancedb.index import BTree, IvfHnswFlat
        _rm(self.path)
        db = lancedb.connect(self.path)
        db.create_table("Scratch", schema=pa.schema([("n", pa.int64())]))
        if situation == "doc":
            s = pa.schema([("id", pa.int64())])
            db.create_table("D", self._reader(s, ((i,) for i in range(n))), schema=s)
        elif situation == "doc_idx10":
            s = pa.schema([(f"p{k}", pa.int64()) for k in range(10)])
            t = db.create_table("D", self._reader(s, ((i,) * 10 for i in range(n))), schema=s)
            for k in range(10):
                t.create_index(f"p{k}", config=BTree())
            self.row["lance_scalar_index"] = "BTree on p0..p9"
        elif situation == "ts":
            s = pa.schema([("ts", pa.int64()), ("sensor", pa.string()), ("value", pa.float64())])
            db.create_table("T", self._reader(s, ((1_700_000_000_000 + i * 1000, "s0", 1.0) for i in range(n))),
                            schema=s)
        elif situation == "vector":
            s = pa.schema([("id", pa.int64()), ("emb", pa.list_(pa.float32(), DIM))])
            t = db.create_table("V", self._reader(s, _vectors(n)), schema=s)
            # Unquantized, as ArcadeDB's index in this situation; IVF_HNSW_SQ (the dense arm's) is int8.
            t.create_index("emb", config=IvfHnswFlat(distance_type="cosine", m=HNSW_M,
                                                     ef_construction=EF_CONSTRUCTION))
            self.row["lance_index_type"] = "IVF_HNSW_FLAT"
            self.row["lance_nprobes"] = 10
        elif situation != "empty":
            raise SystemExit(f"unknown situation {situation}")
        t0 = time.perf_counter()
        del db
        return (time.perf_counter() - t0) * 1000

    def open(self, situation):
        import lancedb
        db = lancedb.connect(self.path)
        tables = {"scratch": db.open_table("Scratch")}
        if situation in self.TABLES:
            tables[situation] = db.open_table(self.TABLES[situation])
        return [db, tables]

    def close(self, h):
        h.clear()     # the session's only references; see close_note

    def read(self, h, situation):
        t = h[1].get(situation)
        if situation == "vector":
            t.search(_probe_vec(), vector_column_name="emb").ef(EF_SEARCH).nprobes(10).limit(10).to_list()
            return None
        if situation in ("doc", "ts"):
            return [{"n": t.count_rows()}]
        if situation == "doc_idx10":
            cols = [f"p{k}" for k in range(10)]
            return t.search().where("p0 = 5").select(cols).limit(10).to_list()
        return None

    def write(self, h, seq):
        import pyarrow as pa
        h[1]["scratch"].add(pa.table({"n": pa.array([seq], type=pa.int64())}))

    def write_own(self, h, situation, i):
        import pyarrow as pa
        t = h[1].get(situation)
        if situation == "vector":
            t.add(pa.table({"id": pa.array([i], type=pa.int64()),
                            "emb": pa.FixedSizeListArray.from_arrays(pa.array([0.25] * DIM, type=pa.float32()),
                                                                     DIM)}))
        elif situation == "doc":
            t.add(pa.table({"id": pa.array([i], type=pa.int64())}))
        elif situation == "doc_idx10":
            t.add(pa.table({f"p{k}": pa.array([i + k], type=pa.int64()) for k in range(10)}))
        elif situation == "ts":
            t.add(pa.table({"ts": pa.array([1_800_000_000_000 + i], type=pa.int64()),
                            "sensor": pa.array(["s0"]), "value": pa.array([1.0])}))
        else:
            h[1]["scratch"].add(pa.table({"n": pa.array([i], type=pa.int64())}))

    def drop(self, h, situation):
        h[1]["vector"].drop_index("emb_idx")

    def cold_code(self, situation):
        opn = f"db = lancedb.connect({self.path!r}); t0 = db.open_table('Scratch')"
        if situation in self.TABLES:
            opn += f"; t1 = db.open_table({self.TABLES[situation]!r})"
        return "import lancedb", opn, "del db"


# ---------------------------------------------------------------- sqlite-vec

class SqliteVec(Arm):
    name = "sqlite_vec_lifecycle"
    path = "/lcdb/lc_sqlitevec"
    DURABILITY = bench_common.DURABILITY_SQLITE
    db_file = "/lcdb/lc_sqlitevec/lc.db"
    drop_na = "vec0 is an exact scan over its own table: there is no index to drop apart from the vectors"
    GRAPH_PROBE = "SELECT * FROM GRAPH_TABLE (g MATCH (a)-[e]->(b) COLUMNS (b.id))"

    def version(self):
        import importlib.metadata
        import sqlite3
        return f"sqlite-vec {importlib.metadata.version('sqlite-vec')} (sqlite {sqlite3.sqlite_version})"

    def durability(self):
        cx = self._connect()
        try:
            return bench_common.sqlite_durability_readback(cx)
        finally:
            cx.close()

    def _connect(self):
        import sqlite3
        import sqlite_vec
        cx = sqlite3.connect(self.db_file, isolation_level=None)
        # The PRAGMAs of every SQLite arm (DECISIONS #70), and its dense arm's extension load.
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        cx.enable_load_extension(True)
        sqlite_vec.load(cx)
        cx.enable_load_extension(False)
        return cx

    def declared(self, situation):
        probes = {
            "doc": ("CREATE VIRTUAL TABLE D USING vec0(id integer)", ()),
            "ts": ("CREATE VIRTUAL TABLE T USING vec0(ts integer, sensor text, value float)", ()),
            "doc_idx10": ("CREATE INDEX d_p0 ON D (p0)",
                          ("CREATE VIRTUAL TABLE D USING vec0(emb float[1], p0 integer)",)),
            "graph": (self.GRAPH_PROBE, ()),
            "graph_gav": (self.GRAPH_PROBE, ()),
            "sparse": ("CREATE VIRTUAL TABLE S USING vec0(id integer primary key, emb sparse[30000])", ()),
        }
        # Each reason's head, up to its first colon, is what the page prints (export_web._lc_short_reason).
        whys = {
            "doc": ("its one structure, the vec0 virtual table, needs a vector column: a table of plain records "
                    "is a SQLite table, the SQLite arm's row"),
            "doc_idx10": ("a vec0 table cannot be indexed: indexed plain records are a SQLite table, the SQLite "
                          "arm's row"),
            "graph": ("no graph query language: sqlite-vec adds vector tables to SQLite's SQL, which has none "
                      "(DECISIONS #128)"),
            "graph_gav": ("no graph query language: sqlite-vec adds vector tables to SQLite's SQL, so there is no "
                          "analytical graph view to build either (DECISIONS #128)"),
            "sparse": "no sparse-vector type: vec0 columns are dense float, int8, or bit vectors",
        }
        whys["ts"] = whys["doc"]
        if situation not in probes:
            return None
        stmt, setup = probes[situation]
        _rm(self.path)
        os.makedirs(self.path)
        cx = self._connect()
        try:
            for s in setup:
                cx.execute(s)
            try:
                cx.execute(stmt)
            except Exception as e:  # noqa: BLE001
                return stmt, whys[situation], f"{type(e).__name__}: {_first_line(e)}"
        finally:
            cx.close()
        raise SystemExit(f"{self.name}: `{stmt}` succeeded, so the {situation} declaration is wrong")

    def build(self, situation, n):
        import array
        _rm(self.path)
        os.makedirs(self.path)
        cx = self._connect()
        cx.execute("CREATE TABLE Scratch (n INTEGER)")
        if situation == "vector":
            cx.execute(f"CREATE VIRTUAL TABLE V USING vec0(id integer primary key, "
                       f"emb float[{DIM}] distance_metric=cosine)")
            for b in _batched(_vectors(n), 5_000):
                cx.execute("BEGIN")
                cx.executemany("INSERT INTO V(id, emb) VALUES (?, ?)",
                               [(i, array.array("f", v).tobytes()) for i, v in b])
                cx.execute("COMMIT")
        elif situation != "empty":
            raise SystemExit(f"unknown situation {situation}")
        t = time.perf_counter()
        cx.close()
        return (time.perf_counter() - t) * 1000

    def open(self, situation):
        return self._connect()

    def close(self, h):
        h.close()

    def read(self, h, situation):
        if situation == "vector":
            import array
            h.execute("SELECT id FROM V WHERE emb MATCH ? AND k = 10 ORDER BY distance",
                      (array.array("f", _probe_vec()).tobytes(),)).fetchall()
        return None

    def write(self, h, seq):
        h.execute("BEGIN")
        h.execute("INSERT INTO Scratch VALUES (?)", (seq,))
        h.execute("COMMIT")

    def write_own(self, h, situation, i):
        import array
        h.execute("BEGIN")
        if situation == "vector":
            h.execute("INSERT INTO V(id, emb) VALUES (?, ?)", (i, array.array("f", [0.25] * DIM).tobytes()))
        else:
            h.execute("INSERT INTO Scratch VALUES (?)", (i,))
        h.execute("COMMIT")

    def cold_code(self, situation):
        return ("import sqlite3, sqlite_vec",
                f"cx = sqlite3.connect({self.db_file!r}, isolation_level=None); "
                "cx.execute('PRAGMA journal_mode=WAL'); cx.execute('PRAGMA synchronous=NORMAL'); "
                "cx.enable_load_extension(True); sqlite_vec.load(cx); cx.enable_load_extension(False)",
                "cx.close()")


ARMS = {a.name: a for a in (Ladybug, Chroma, Lance, SqliteVec)}

# ---------------------------------------------------------------- the session, as l5_lifecycle_sql

_LAST_READ = {"rows": None, "situation": None}
_WRITE_SEQ = [0]


def cycle(arm, situation, mode, cold=False):
    """One open/close cycle: (open_ms, close_ms, action_ms), as L.cycle."""
    if cold:
        pagecache.evict(arm.path)    # raises if pages survive: no fabricated cold column
    t0 = time.perf_counter()
    h = arm.open(situation)
    t1 = time.perf_counter()
    rows = None
    if mode in ("write", "write_read"):
        _WRITE_SEQ[0] += 1
        arm.write(h, _WRITE_SEQ[0])
    elif mode in ("write_own", "write_own_read"):
        _WRITE_SEQ[0] += 1
        arm.write_own(h, situation, 10_000_000 + _WRITE_SEQ[0])
    elif mode == "drop":
        arm.drop(h, situation)
    if mode in ("read", "write_read", "write_own_read"):
        rows = arm.read(h, situation)
    t2 = time.perf_counter()
    arm.close(h)
    t3 = time.perf_counter()
    if rows is not None:
        _LAST_READ["rows"], _LAST_READ["situation"] = rows, situation
    return (t1 - t0) * 1000, (t3 - t2) * 1000, (t2 - t1) * 1000


def measure(arm, situation, mode, cold=False):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        a, b, act = cycle(arm, situation, mode, cold=cold)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def measure_stale(arm, situation, mode):
    o, c, w = [], [], []
    for i in range(L.WARMUP + L.ITERS):
        cycle(arm, situation, "write_own")
        a, b, act = cycle(arm, situation, mode)
        if i < L.WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def _cold_process(arm, situation):
    """Interpreter start, package import, first open, close, in a FRESH process (L.main's span)."""
    imp, opn, cls = arm.cold_code(situation)
    boot = subprocess.run(
        [sys.executable, "-c",
         f"import time; _t0 = time.perf_counter()\n{imp}\n_ti = time.perf_counter()\n{opn}\n"
         f"_to = time.perf_counter()\n{cls}\n"
         "print('%.3f %.3f %.3f' % ((_ti-_t0)*1000, (_to-_ti)*1000, (time.perf_counter()-_t0)*1000))"],
        capture_output=True, text=True, timeout=900)
    if boot.returncode == 0 and boot.stdout.strip():
        return tuple(float(x) for x in boot.stdout.strip().split()[-3:])
    sys.stderr.write("cold-start subprocess failed (rc=%s); cold columns will be null\n%s\n"
                     % (boot.returncode, (boot.stderr or "")[-2000:]))
    return None, None, None


def _base_row(args, arm, n, fs, build_s, durability):
    out = bench_common.run_conditions(
        lane="lifecycle", backend=args.backend, workload=args.workload,
        scale=args.scale, n_rows=n, dims=DIM, fs_type=fs,
        lc_iters=L.ITERS, lc_warmup=L.WARMUP, build_s=build_s)
    out["engine_version"] = arm.version()      # the engine, not the ArcadeDB wheel (BUGS F39)
    out["deployment"] = "embedded"
    bench_common.stamp_durability(out, durability)
    out["instrument"] = bench_common.INSTRUMENT
    out["cold_warm_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    out["cold_first_query_na"] = bench_common.NA_COLD_WARM_LIFECYCLE
    return out


def _write_row(args, out):
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


def main(args):
    fs = L._assert_fs()
    n = L.SCALE_ROWS[args.scale]
    arm = ARMS[args.backend]()
    t0 = time.perf_counter()
    decl = arm.declared(args.workload)
    if decl:
        # DECLARED, NOT SKIPPED (DECISIONS #88, #92)
        stmt, why, answer = decl
        text = f"{why}; tried `{stmt}` and the engine answered: {answer}"
        out = _base_row(args, arm, n, fs, round(time.perf_counter() - t0, 3), bench_common.at_class(arm.DURABILITY))
        out["lifecycle_situation_unexpressible"] = text
        bench_common.record_unexpressible(out, "lifecycle_read", text)
        _rm(arm.path)
        _write_row(args, out)
        return
    build_close_ms = arm.build(args.workload, n)
    build_s = round(time.perf_counter() - t0, 3)
    durability = arm.durability()
    import_ms, first_open_ms, cold_proc_ms = _cold_process(arm, args.workload)

    out = _base_row(args, arm, n, fs, build_s, durability)
    out.update(arm.row)
    if arm.close_note:
        out["close_note"] = arm.close_note
    if args.workload == "vector":
        out["hnsw_M"], out["ef_construction"], out["ef_search"], out["k"] = HNSW_M, EF_CONSTRUCTION, EF_SEARCH, 10
        out["vector_metric"] = "cosine"
    if args.workload == "ts":
        out["ts_type"] = "plain table of timestamped rows: no time-series type"
    o, c, w = measure(arm, args.workload, "clean", cold=True)
    out["cold_open_ms"], out["cold_close_ms"] = round(o, 3), round(c, 3)
    out["build_close_ms"] = round(build_close_ms, 3)
    # The pools the process holds once the engine is open (FAIRNESS F6), read after the cold cycles.
    h = arm.open(args.workload)
    out["lc_threads_after_open"] = _threads()
    out["lc_affinity_cpus"] = len(os.sched_getaffinity(0))
    arm.close(h)
    _r3 = lambda x: None if x is None else round(x, 3)   # noqa: E731
    out["import_ms"] = _r3(import_ms)
    out["jvm_start_ms"] = None
    out["runtime_start_na"] = ("no JVM: the engine is a compiled library the import loads, "
                               "so import_ms is the runtime start")
    out["first_open_ms"] = _r3(first_open_ms)
    out["cold_process_ms"] = _r3(cold_proc_ms)
    out["cold_process_cache_state"] = "warm-page-cache"

    for mode in L.MODES:
        o, c, w = measure(arm, args.workload, mode)
        out[f"{mode}_open_ms"] = round(o, 3)
        out[f"{mode}_close_ms"] = round(c, 3)
        out[f"{mode}_action_ms"] = round(w, 3)
        out[f"{mode}_session_ms"] = round(o + w + c, 3)
    out["cold_start_penalty_ms"] = None if out["cold_process_ms"] is None else round(
        max(0.0, out["cold_process_ms"] - (out["clean_open_ms"] + out["clean_close_ms"])), 3)

    if "write_own" in L.MODES:
        o, c, w = measure_stale(arm, args.workload, "clean")
        out["stale_open_ms"], out["stale_close_ms"] = round(o, 3), round(c, 3)
        o, c, w = measure_stale(arm, args.workload, "read")
        out["stale_read_open_ms"], out["stale_read_close_ms"] = round(o, 3), round(c, 3)
        out["stale_read_action_ms"] = round(w, 3)
        out["stale_read_session_ms"] = round(o + w + c, 3)
        out["stale_redirties_every_cycle"] = True

    if args.workload == "vector" and "drop" not in os.environ.get("BENCH_LC_SKIP", ""):
        if arm.drop_na:
            out["drop_na"] = arm.drop_na
        else:
            o, c, w = cycle(arm, args.workload, "drop")
            out["drop_open_ms"], out["drop_close_ms"] = round(o, 3), round(c, 3)
            out["drop_action_ms"] = round(w, 3)
            out["drop_is_single_cycle"] = True

    if args.workload == "vector":
        bench_common.record_unexpressible(
            out, "lifecycle_read",
            "the vector situation's read goes through an approximate index; "
            "it is checked by recall on the dense vector table, not by an exact digest")
    elif _LAST_READ["rows"] is not None:
        bench_common.record_result(out, "lifecycle_read", _LAST_READ["rows"])
        out["lifecycle_read_situation"] = _LAST_READ["situation"]
    else:
        bench_common.record_unexpressible(
            out, "lifecycle_read", f"situation {args.workload!r} issues no read in the modes this cell ran")
    out["close_over_budget"] = out["clean_close_ms"] > 100.0
    _write_row(args, out)
