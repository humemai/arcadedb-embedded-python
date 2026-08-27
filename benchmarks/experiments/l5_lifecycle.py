"""L5: what it costs to OPEN and CLOSE a database, by what is in it.

WHY THIS IS A LANE AND NOT A PROBE. Opening and closing is the one operation
every embedded deployment performs and no benchmark measures, and this engine
has produced three defects in it: #5747 (a session that never ran a vector
search paid a full HNSW rebuild on close), #6489 (a build that orphaned any node
left the index MUTABLE, so close rebuilt the whole graph; ours, fixed by PR
#6490) and #5872 (close does not reliably cancel an in-flight build). A number
that can slide from 8 ms to 30 s between releases with nobody watching is what a
regression gate is for.

THE INVARIANT, from lifecycle-open-close.md and DECISIONS #50:

    Close should be O(what was written), not O(what is stored),
    and on the order of 100 ms.

Grounded twice: close should not cost more than getting started, and JVM startup
here is ~160 ms; and it should sit under the ~100 ms at which a script stops
feeling instant. Eight of the ten situations in the original matrix already
satisfy it, which is worth stating positively -- the multi-model substrate
closes cheaply and two optional accelerators do not.

WHAT EACH SITUATION EARNS ITS PLACE FOR:
  empty        the floor: what close costs with nothing in the database
  doc          records only, no index
  doc_idx10    the per-index cost (~0.4 ms/index, and it is I/O: it vanishes
               on tmpfs, which is how it was separated from the compute cost)
  graph        vertices and edges, no accelerator
  graph_gav    the Graph Analytical View, whose CSR is re-derived every open
  vector       the JVector HNSW graph, the worst case historically
  sparse       LSM_SPARSE_VECTOR, which is NOT affected and must be shown so
  ts           the time-series type, likewise

THREE MODES, because the read mode changes the picture completely. v1 of this
matrix measured open-then-close WITHOUT EVER QUERYING and inflated the vector
rows by up to 617x, because a session that never touches the index leaves it in
a state close then has to resolve. That is not a neutral protocol, it is one
specific case (#5747), so all three are measured and reported separately.
"""
import argparse
import json
import os
import statistics as st
import subprocess
import sys
import time

import bench_common
import pagecache

DB = "/lcdb/lc"          # a HOST directory bind-mounted here; see _assert_fs
DIM = 64
ITERS = int(os.environ.get("BENCH_LC_ITERS", "3"))
# Which scenarios to run. At very large scales the write modes trigger a full
# index rebuild PER CYCLE, which is hours; the untriggered ones still answer
# "does merely having this thing cost more as it grows".
ALL_MODES = ("clean", "read", "write", "write_read", "write_own", "write_own_read")
# The default is ALL_MODES verbatim: an unset knob must reproduce the runs that
# were collected before this knob was honoured, byte for byte, or the filter
# silently becomes an instrument change.
MODES = [m for m in os.environ.get(
    "BENCH_LC_MODES", ",".join(ALL_MODES)).split(",") if m]
_unknown = [m for m in MODES if m not in ALL_MODES]
if _unknown:
    raise SystemExit(f"BENCH_LC_MODES: unknown mode(s) {_unknown}; known: {list(ALL_MODES)}")
# clean is not optional: cold_start_penalty_ms and close_over_budget are both
# defined against it, and a filter that removed it would produce a row whose
# invariant column silently disappeared rather than failing.
if "clean" not in MODES:
    MODES.insert(0, "clean")
WARMUP = int(os.environ.get("BENCH_LC_WARMUP", "1"))

SCALE_ROWS = {"lc10k": 10_000, "lc100k": 100_000, "lc1m": 1_000_000,
              "lc10m": 10_000_000}

SITUATIONS = ["empty", "doc", "doc_idx10", "graph", "graph_gav",
              "vector", "sparse", "ts"]


def _assert_fs():
    """Refuse to report a cold column from a filesystem that cannot go cold.

    posix_fadvise cannot evict a container's overlay upper layer, and tmpfs
    pages ARE memory so there is nothing to evict. Either placement yields a
    'cold' open indistinguishable from a warm one, which is a fabricated
    number rather than a failed measurement. Both hosts run the overlayfs
    storage driver and have /tmp on tmpfs, so this is a live hazard, not a
    hypothetical one.
    """
    real = os.path.realpath(os.path.dirname(DB))
    best = ("", "")
    for line in open("/proc/mounts"):
        f = line.split()
        if real == f[1] or real.startswith(f[1].rstrip("/") + "/"):
            if len(f[1]) > len(best[0]):
                best = (f[1], f[2])
    fs = best[1]
    if fs in ("overlay", "overlayfs", "tmpfs", ""):
        sys.stderr.write(
            f"l5_lifecycle: {os.path.dirname(DB)} is {fs!r}. A cold open cannot "
            "be measured there: fadvise does not evict an overlay upper layer, "
            "and tmpfs pages are memory. The bind mount is missing or points at "
            "the wrong host directory. Refusing to fabricate a cold column.\n")
        os._exit(1)
    return fs


def _rm(p):
    import shutil
    if os.path.isdir(p):
        shutil.rmtree(p)


def build(situation, n, heap):
    """Create the database for `situation` at `n` rows, then close it.

    Returns the build session's close time in ms.
    """
    import arcadedb_embedded as arcadedb
    _rm(DB)
    db = arcadedb.create_database(
        DB, jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
    c = db.command
    # ONE scratch type in every situation, holding no rows, so the write mode
    # is the SAME operation everywhere: insert one document, commit, close.
    # That is what makes the dirty-minus-clean delta comparable across
    # situations -- it isolates the fixed commit-and-close tax (~15.6 ms in the
    # original matrix) from anything the situation itself contributes. Creating
    # the type per iteration instead would time a schema change, and would fail
    # on the second iteration with "Type Scratch already exists".
    c("sql", "CREATE DOCUMENT TYPE Scratch")
    c("sql", "CREATE PROPERTY Scratch.n INTEGER")
    if situation == "empty":
        pass
    elif situation == "doc":
        c("sql", "CREATE DOCUMENT TYPE D")
        c("sql", "CREATE PROPERTY D.id INTEGER")
        _bulk(db, "INSERT INTO D SET id = %d", n)
    elif situation == "doc_idx10":
        c("sql", "CREATE DOCUMENT TYPE D")
        for i in range(10):
            c("sql", f"CREATE PROPERTY D.p{i} INTEGER")
            c("sql", f"CREATE INDEX ON D (p{i}) NOTUNIQUE")
        _bulk(db, "INSERT INTO D SET " + ", ".join(
            f"p{i} = %d" for i in range(10)), n, nargs=10)
    elif situation in ("graph", "graph_gav"):
        c("sql", "CREATE VERTEX TYPE P")
        c("sql", "CREATE PROPERTY P.id INTEGER")
        c("sql", "CREATE EDGE TYPE E")
        # A TEMPORARY index on P.id, dropped before the measurement.
        # Without it each CREATE EDGE ... FROM (SELECT ... WHERE id = ?) is a
        # full scan, so building 4n edges is O(n^2): at 10,000 vertices that is
        # 400 million row visits and the build never finished. The index makes
        # it O(n log n) and is dropped afterwards, so what gets MEASURED is
        # still a graph with no index on it -- doc_idx10 is where index cost is
        # priced, and leaving one here would smear the two situations together.
        c("sql", "CREATE INDEX ON P (id) UNIQUE")
        _bulk(db, "CREATE VERTEX P SET id = %d", n)
        # A fanout of 4, not a ring: a ring gives one two-hop path per vertex,
        # too little work for an accelerator to matter either way.
        db.begin()
        for i in range(n):
            for f in range(1, 5):
                c("sql", f"CREATE EDGE E FROM (SELECT FROM P WHERE id = {i}) "
                         f"TO (SELECT FROM P WHERE id = {(i + f * 7919) % n})")
            if (i + 1) % 2000 == 0:
                db.commit(); db.begin()
        db.commit()
        c("sql", "DROP INDEX `P[id]`")
        if situation == "graph_gav":
            c("sql", "CREATE GRAPH ANALYTICAL VIEW lcv VERTEX TYPES (P) "
                     "EDGE TYPES (E) PROPERTIES (id) UPDATE MODE OFF")
            _await_gav(db)
    elif situation == "vector":
        c("sql", "CREATE VERTEX TYPE V")
        c("sql", "CREATE PROPERTY V.id INTEGER")
        c("sql", "CREATE PROPERTY V.emb ARRAY_OF_FLOATS")
        _vectors(db, n)
        c("sql", f'CREATE INDEX ON V (emb) LSM_VECTOR METADATA '
                 f'{{ "dimensions": {DIM}, "similarity": "COSINE" }}')
    elif situation == "sparse":
        c("sql", "CREATE DOCUMENT TYPE S")
        c("sql", "CREATE PROPERTY S.tokens ARRAY_OF_INTEGERS")
        c("sql", "CREATE PROPERTY S.weights ARRAY_OF_FLOATS")
        _sparse(db, n)
        c("sql", "CREATE INDEX ON S (tokens, weights) LSM_SPARSE_VECTOR "
                 'METADATA { "dimensions": 30000 }')
    elif situation == "ts":
        # A TIMESERIES type declares its timestamp, tags and fields inline; it
        # is not a document type with properties added afterwards, and
        # "CREATE TIMESERIES TYPE T" alone fails with "requires a TIMESTAMP
        # column". Shape taken from the engine's own tests
        # (server/src/test/.../PostTimeSeriesWriteHandlerIT).
        c("sql", "CREATE TIMESERIES TYPE T TIMESTAMP ts "
                 "TAGS (sensor STRING) FIELDS (value DOUBLE)")
        db.begin()
        for i in range(n):
            c("sql", f"INSERT INTO T SET ts = {1_700_000_000_000 + i * 1000}, "
                     f"sensor = 's0', value = 1.0")
            if (i + 1) % 5000 == 0:
                db.commit(); db.begin()
        db.commit()
    else:
        raise SystemExit(f"unknown situation {situation}")
    # The BUILD SESSION's own close, timed separately. This is the session that
    # created the structure, and it is where a close-time rebuild doubles the
    # cost of building (#6489). A reopen cannot show it: by then the structure
    # is already on disk and clean.
    _bt = time.perf_counter()
    db.close()
    return (time.perf_counter() - _bt) * 1000


def _bulk(db, tmpl, n, nargs=1):
    db.begin()
    for i in range(n):
        db.command("sql", tmpl % ((i,) * nargs if nargs > 1 else i))
        if (i + 1) % 5000 == 0:
            db.commit(); db.begin()
    db.commit()


def _vectors(db, n):
    import random
    rnd = random.Random(17)
    db.begin()
    for i in range(n):
        v = ", ".join("%.6f" % rnd.random() for _ in range(DIM))
        db.command("sql", f"CREATE VERTEX V SET id = {i}, emb = [{v}]")
        if (i + 1) % 2000 == 0:
            db.commit(); db.begin()
    db.commit()


def _sparse(db, n):
    import random
    rnd = random.Random(23)
    db.begin()
    for i in range(n):
        toks = sorted(rnd.sample(range(30000), 40))
        t = ", ".join(str(x) for x in toks)
        w = ", ".join("%.6f" % rnd.random() for _ in toks)
        db.command("sql", f"INSERT INTO S SET tokens = [{t}], weights = [{w}]")
        if (i + 1) % 2000 == 0:
            db.commit(); db.begin()
    db.commit()


def _await_gav(db, timeout_s=900):
    t0 = time.time()
    while True:
        rs = db.query("sql", "SELECT FROM schema:graphAnalyticalViews "
                             "WHERE name = 'lcv'")
        rows = list(rs)
        if rows and str(rows[0].get("status")) == "READY":
            return
        if time.time() - t0 > timeout_s:
            raise SystemExit("GAV never became READY")
        time.sleep(0.05)


# (language, query). The LANGUAGE is part of the fixture, not a detail:
#
#   graph_gav MUST be cypher. The Graph Analytical View is consumed only by the
#   openCypher executor (GAVExpandAll, GAVFusedChainOperator, MatchRelationshipStep);
#   SQL SELECT's only GAV reference is FetchFromSchemaGraphAnalyticalViewsStep,
#   which reads the schema catalogue rather than the view. The read here was SQL,
#   so every graph_gav session had the accelerator present and never consulted it,
#   and since #6633 made the CSR lazy-on-first-use a session that never uses the
#   view never loads it. That is what made graph_gav look flat at 10M, and it is
#   why "a GAV under the identical trigger" was not an identical trigger at all:
#   the vector arm hits its index and this one did not.
#
#   sparse MUST be a vector search. `SELECT count(*) FROM S LIMIT 10` plans to
#   CountFromTypeStep, which calls database.countType() and never touches the
#   index, so the sparse read measured a row count.
READS = {
    "doc":       ("sql", "SELECT count(*) FROM D"),
    "doc_idx10": ("sql", "SELECT FROM D WHERE p0 = 5 LIMIT 10"),
    "graph":     ("sql", "SELECT count(*) FROM (SELECT expand(out('E')) FROM P LIMIT 100)"),
    # BOUNDED to the same 100 seeds the SQL form used, and the same shape the
    # `graph` row asks. The first cypher version was an unbounded whole-graph
    # 2-hop: it did reach the view (1.6 ms in SQL against 234 ms in cypher at
    # lc10k is the proof) but it changed the SCOPE at the same time, so 16,087 ms
    # at 1M measured the query written rather than the view, and was comparable
    # to neither the `graph` row nor the numbers it replaced. Fixing the language
    # and the scope in one edit is rule 7 half-applied.
    "graph_gav": ("cypher",
                  "MATCH (a:P)-[:E]->()-[:E]->(c:P) WHERE a.id < 100 "
                  "RETURN count(c) AS n"),
    "vector":    None,     # filled in at runtime, needs a probe vector
    # The function is `vector.sparseNeighbors`, backticked because of the dot,
    # and it is what l3_sparse.py:190 calls. A first draft guessed
    # "sparseVectorNeighbors" and every sparse cell died on "Unknown function
    # name" -- which is exactly what the smoke run at the smallest tier is for.
    "sparse":    ("sql", "SELECT expand(`vector.sparseNeighbors`("
                         "'S[tokens,weights]', [1, 8, 15, 22], "
                         "[0.5, 0.5, 0.5, 0.5], 10))"),
    "ts":        ("sql", "SELECT count(*) FROM T"),
}


def _read(db, situation):
    if situation == "empty":
        return
    if situation == "vector":
        v = ", ".join("0.5" for _ in range(DIM))
        list(db.query("sql", f"SELECT FROM (SELECT expand(vectorNeighbors("
                             f"'V[emb]', [{v}], 10)))"))
        return
    q = READS.get(situation)
    if q:
        lang, text = q
        list(db.query(lang, text))
        # Counts reads ISSUED THROUGH CYPHER, which is necessary but not
        # sufficient for "the view served it": SQL cannot reach a Graph
        # Analytical View at all, so a zero here proves the defect is back,
        # while a non-zero does not by itself prove the view was consulted.
        # _gav_probe_plan() below is what actually settles it.
        if situation == "graph_gav":
            _gav_cypher_reads[0] += 1
            if _gav_plan[0] is None:
                _gav_plan[0] = _gav_probe_plan(db, text)


_WRITE_SEQ = [0]
_gav_cypher_reads = [0]
_gav_plan = [None]

# THE VIEW ANNOUNCES ITSELF IN THE PLAN.
#
# The engine exposes no per-query "the view served this" counter -- GraphAnalyticalView
# has getNodeCount/getEdgeCount/getBuildTimestamp and nothing that increments on use --
# so there is no counter to read and the flag sat hardcoded False.
#
# But the view has DEDICATED OPERATORS, and they print their own names into the
# execution plan along with the provider that backs them:
#
#     GAVExpandAll.java:265        return "GAVExpandAll";
#     GAVExpandAll.java:283        sb.append(" [provider=").append(provider.getName());
#     GAVFusedChainOperator:566    return "GAVFusedChain";
#
# A plan naming one of these could not have been produced by a traversal that
# walked the buckets, so EXPLAIN is a sufficient observable. This is a stronger
# claim than the cypher-reads counter: that one only says SQL was not used.
_GAV_OPERATORS = ("GAVExpandAll", "GAVExpandInto", "GAVFusedChain", "CSRCount")


def _gav_probe_plan(db, text):
    """EXPLAIN the graph_gav read once and return which GAV operator served it.

    Returns the matched operator name, or "" when the plan is readable and names
    none of them (the view exists but the planner did not use it -- a real and
    reportable outcome, not an error), or None when the plan could not be read at
    all, which must NOT be reported as a negative result.
    """
    try:
        plan = "\n".join(str(r) for r in db.query("cypher", "EXPLAIN " + text))
    except Exception:
        return None
    for op in _GAV_OPERATORS:
        if op in plan:
            return op
    return ""


def _write(db, situation):
    """One document into Scratch, in every situation.

    Deliberately NOT a write into the situation's own structure. Inserting a
    vector would make the vector row's dirty close include an index update
    while the doc row's did not, and the delta would then price two different
    things under one name. The question this mode asks is "what does committing
    ANYTHING cost at close", so the anything is held constant.
    """
    _WRITE_SEQ[0] += 1
    db.begin()
    db.command("sql", f"INSERT INTO Scratch SET n = {_WRITE_SEQ[0]}")
    db.commit()


def _write_own(db, situation):
    """Write into the situation's OWN structure, which the constant Scratch write never does.

    `_write` deliberately inserts into Scratch so every situation commits the same thing, which is the
    right control for "what does committing anything cost". But it leaves a vector index CLEAN: no
    vector was added, so nothing marks the graph mutable and no rebuild is owed. That makes the
    constant-write mode blind to the one case that actually costs seconds. This mode asks the other
    question: what does writing into the indexed structure itself cost.
    """
    _WRITE_SEQ[0] += 1
    i = 10_000_000 + _WRITE_SEQ[0]
    db.begin()
    if situation == "vector":
        v = ", ".join("0.25" for _ in range(DIM))
        db.command("sql", f"INSERT INTO V SET id = {i}, emb = [{v}]")
    elif situation in ("graph", "graph_gav"):
        db.command("sql", f"INSERT INTO P SET id = {i}")
    elif situation == "doc":
        db.command("sql", f"INSERT INTO D SET id = {i}")
    elif situation == "doc_idx10":
        # ALL TEN, because all ten are indexed. Setting p0 alone touched one of
        # the ten NOTUNIQUE indexes and the column was read as "what a write to a
        # ten-index type costs".
        cols = ", ".join(f"p{k} = {i + k}" for k in range(10))
        db.command("sql", f"INSERT INTO D SET {cols}")
    elif situation == "sparse":
        # tokens AND weights, because LSMSparseVectorIndex.put() returns early
        # when either is absent (engine LSMSparseVectorIndex.java:183-186), so an
        # id-only insert was DISCARDED by the index. write_own for sparse was
        # therefore byte-identical to the constant write it exists not to be, and
        # the lane's positive claim - that the sparse index is not affected - was
        # resting on a write the index threw away.
        toks = ", ".join(str(1 + 7 * k) for k in range(16))
        wts = ", ".join("0.25" for _ in range(16))
        db.command("sql", f"INSERT INTO S SET tokens = [{toks}], weights = [{wts}]")
    elif situation == "ts":
        db.command("sql", f"INSERT INTO T SET ts = {1_800_000_000_000 + i}, sensor = 's0', value = 1.0")
    else:
        db.command("sql", f"INSERT INTO Scratch SET n = {i}")
    db.commit()


def _drop(db, situation):
    """Drop the situation's accelerator. Only meaningful where there is one."""
    if situation == "graph_gav":
        db.command("sql", "DROP GRAPH ANALYTICAL VIEW lcv")
    elif situation == "vector":
        db.command("sql", "DROP INDEX `V[emb]`")


def cycle(situation, mode, cold=False):
    """One open/close cycle. Returns (open_ms, close_ms)."""
    import arcadedb_embedded as arcadedb
    if cold:
        # Verified eviction: evict() raises if pages survive, so a cold number
        # cannot be reported for a database that was still cached.
        pagecache.evict(DB)
    t0 = time.perf_counter()
    db = arcadedb.open_database(DB)
    t1 = time.perf_counter()
    if mode == "read":
        _read(db, situation)
    elif mode == "write":
        _write(db, situation)
    elif mode == "write_read":
        # The order that matters: a commit invalidates a persisted derived
        # structure, and the read that follows is what pays to rebuild it.
        # Neither half alone shows the cost (#6641).
        _write(db, situation)
        _read(db, situation)
    elif mode == "write_own":
        _write_own(db, situation)
    elif mode == "write_own_read":
        _write_own(db, situation)
        _read(db, situation)
    elif mode == "drop":
        _drop(db, situation)
    t2 = time.perf_counter()
    db.close()
    t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000, (t2 - t1) * 1000


def measure(situation, mode, cold=False):
    o, c, w = [], [], []
    for i in range(WARMUP + ITERS):
        a, b, act = cycle(situation, mode, cold=cold)
        if i < WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def measure_stale(situation, mode):
    """Like measure(), but RE-DIRTIES before every cycle.

    The stale block used to create the staleness once and then read it
    WARMUP + ITERS times. That is not a repeated measurement of a stale reopen,
    it is one stale reopen followed by six warm ones - and because measure()
    discards the first WARMUP cycles, the discarded ones were exactly the stale
    ones and the reported median was systematically the WARM case.

    Caught 2026-08-25 by replaying the mode sequence outside the harness at
    N=20,000: the seven stale_read actions came out 83.5, 2325.4, 63.4, 56.2,
    57.6, 54.3, 53.7 ms. The staleness is consumed in cycles 0 and 1, the two
    cycles that are thrown away, and the median of the kept cycles (56.2 ms) is
    a clean read against a graph the engine's own log reports as up to date -
    a fake 45x against the honest number.

    Whether the laundering fires depends on whether anything repairs and
    persists the derived structure between cycles, which depends on the engine
    version, the scale, and on background rebuild scheduling. That is exactly
    the kind of dependency a measurement must not have, so the fix is
    structural: every cycle pays for its own staleness, the same way
    write_own_read re-dirties at the top of each of its cycles.

    THIS IS AN INSTRUMENT CHANGE. stale_* columns produced before 2026-08-25
    are not comparable with ones produced after it.
    """
    o, c, w = [], [], []
    for i in range(WARMUP + ITERS):
        cycle(situation, "write_own")        # a separate session commits...
        a, b, act = cycle(situation, mode)   # ...and THIS one arrives to find it stale
        if i < WARMUP:
            continue
        o.append(a); c.append(b); w.append(act)
    return st.median(o), st.median(c), st.median(w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--workload", required=True, choices=SITUATIONS)
    ap.add_argument("--scale", default="lc10k", choices=list(SCALE_ROWS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    fs = _assert_fs()
    n = SCALE_ROWS[args.scale]
    # ARCADEDB_HEAP is what runner.py exports and what bench_common STAMPS on the
    # row. This lane alone read BENCH_HEAP, which the runner never sets, so it ran
    # at this 8g default at every scale while the row claimed HEAP_BY_SCALE's value:
    # a 24g label on an 8g run at lc10m, which then GC-thrashed at 8160/8192 MB and
    # managed 400 vectors in 21 seconds. That is precisely the failure runner.py's
    # own comment records for Elasticsearch, "a 4g run wearing a 16g label".
    #
    # BENCH_HEAP is still honoured, second, so a direct invocation can override.
    heap = os.environ.get("ARCADEDB_HEAP") or os.environ.get("BENCH_HEAP", "8g")

    t0 = time.perf_counter()
    build_close_ms = build(args.workload, n, heap)
    build_s = round(time.perf_counter() - t0, 3)

    # JVM BOOT, measured in a FRESH PROCESS, because it cannot be measured in this one: build()
    # above already started the JVM, so any "first open" timed here is a warm open wearing the wrong
    # name. An earlier version of this lane did exactly that and reported 18-52 ms for something that
    # is an order of magnitude larger.
    #
    # What a cold caller actually pays is the whole process: interpreter start, import, JPype's JVM
    # boot, then the open. That is what this subprocess times, from its own first line.
    _boot = subprocess.run(
        [sys.executable, "-c",
         "import time; _t0 = time.perf_counter()\n"
         "from arcadedb_embedded.jvm import start_jvm\n"
         "import arcadedb_embedded as a\n"
         "_ti = time.perf_counter()\n"
         "start_jvm()\n"
         "_tj = time.perf_counter()\n"
         "db = a.open_database(%r)\n"
         "_to = time.perf_counter()\n"
         "db.close()\n"
         "print('%%.3f %%.3f %%.3f %%.3f' %% ((_ti-_t0)*1000, (_tj-_ti)*1000, (_to-_tj)*1000, "
         "(time.perf_counter()-_t0)*1000))"
         % DB],
        capture_output=True, text=True, timeout=900)
    if _boot.returncode == 0 and _boot.stdout.strip():
        import_ms, jvm_start_ms, first_open_ms, cold_proc_ms = (
            float(x) for x in _boot.stdout.strip().split()[-4:])
    else:
        # NOT -1.0. A sentinel that is a float goes into a median, a mean and a
        # ratio without anything objecting, and cold_start_penalty_ms clamped it
        # to 0.0 with max(), so a failed boot published four impossible columns
        # and a penalty of zero while the cell exited 0. None is what a missing
        # measurement is, and it makes every downstream consumer say so.
        sys.stderr.write(
            "cold-start subprocess failed (rc=%s); cold columns will be null\n%s\n"
            % (_boot.returncode, (_boot.stderr or "")[-2000:]))
        import_ms = jvm_start_ms = first_open_ms = cold_proc_ms = None

    out = bench_common.run_conditions(
        lane="lifecycle", backend=args.backend, workload=args.workload,
        scale=args.scale, n_rows=n, dims=DIM, fs_type=fs,
        lc_iters=ITERS, lc_warmup=WARMUP, build_s=build_s)

    # Cold FIRST, while the build's pages are the only thing that could be
    # cached: running it after the warm modes would measure an eviction of a
    # database that several cycles had just re-warmed, which is the same
    # number by construction but a weaker claim.
    o, c, w = measure(args.workload, "clean", cold=True)
    out["cold_open_ms"], out["cold_close_ms"] = round(o, 3), round(c, 3)
    out["build_close_ms"] = round(build_close_ms, 3)
    # The cold start decomposed, because "JVM boot" was being used for three different things.
    # Measured on this machine: a bare JVM is ~115 ms, so jvm_start_ms above that is JPype's overhead,
    # and first_open_ms is ArcadeDB's own initialisation with the JVM already up.
    _r3 = lambda x: None if x is None else round(x, 3)
    out["import_ms"] = _r3(import_ms)                    # interpreter + module import
    out["jvm_start_ms"] = _r3(jvm_start_ms)              # start_jvm() alone, no database
    out["first_open_ms"] = _r3(first_open_ms)            # first open, JVM already up
    out["cold_process_ms"] = _r3(cold_proc_ms)           # what a CLI actually waits for
    # WHICH CACHE STATE THESE FOUR DESCRIBE. cold_open_ms above is measured after
    # a verified page-cache eviction; this subprocess is not evicted, so its
    # "cold" means a fresh PROCESS against a warm page cache. Two different
    # meanings of cold in one row, stated rather than left to the column name.
    out["cold_process_cache_state"] = "warm-page-cache"

    # MODES, not a literal tuple. This loop ignored BENCH_LC_MODES until 2026-08-25,
    # which cost a 10M vector cell 10.6 h per rep instead of the ~53 min the filter
    # was asking for. No row was WRONG (the loop ran a superset), only unaffordable.
    for mode in MODES:
        o, c, w = measure(args.workload, mode)
        out[f"{mode}_open_ms"] = round(o, 3)
        out[f"{mode}_close_ms"] = round(c, 3)
        out[f"{mode}_action_ms"] = round(w, 3)
        # The session is what a caller actually waits for. Reporting open and close
        # alone hides a rebuild triggered BETWEEN them, which is exactly where the
        # GAV and vector costs land.
        out[f"{mode}_session_ms"] = round(o + w + c, 3)

    # The invariant, evaluated where the number is produced rather than left to
    # a downstream reader: close should be O(what was written), so a clean
    # close (nothing written) over 100 ms is a finding regardless of size.
    # JVM boot is what the first open carries beyond a warm one. Recorded as a
    # first-class column so no table can quote an open() without it.
    # Kept for continuity with earlier runs, but it is a COLD START penalty, not JVM boot: it is the
    # whole cold process minus a warm session. jvm_start_ms above is the JVM boot proper.
    out["cold_start_penalty_ms"] = None if out["cold_process_ms"] is None else round(
        max(0.0, out["cold_process_ms"] - (out["clean_open_ms"] + out["clean_close_ms"])), 3)

    # A stale reopen: the PREVIOUS session committed, so any persisted derived
    # structure is invalid on this open. Measured separately because it is the
    # case #6641 is about and no other mode reaches it.
    if "write_own" in MODES:
        o, c, w = measure_stale(args.workload, "clean")
        out["stale_open_ms"], out["stale_close_ms"] = round(o, 3), round(c, 3)
        o, c, w = measure_stale(args.workload, "read")
        out["stale_read_open_ms"], out["stale_read_close_ms"] = round(o, 3), round(c, 3)
        out["stale_read_action_ms"] = round(w, 3)
        out["stale_read_session_ms"] = round(o + w + c, 3)
        # Says which instrument produced them, so a reader never has to date the
        # row against a commit to know whether the laundering above applies.
        out["stale_redirties_every_cycle"] = True

    # DROP is destructive and therefore cannot be a median: the second cycle
    # would find nothing to drop and would time an open/close instead, quietly
    # averaging a no-op into the number. One cycle, labelled as one, and last
    # because it leaves the database without the structure every other mode
    # above was measuring.
    if args.workload in ("graph_gav", "vector") and "drop" not in os.environ.get("BENCH_LC_SKIP", ""):
        o, c, w = cycle(args.workload, "drop")
        out["drop_open_ms"], out["drop_close_ms"] = round(o, 3), round(c, 3)
        out["drop_action_ms"] = round(w, 3)
        out["drop_is_single_cycle"] = True

    out["close_over_budget"] = out["clean_close_ms"] > 100.0
    if args.workload == "graph_gav":
        out["gav_cypher_reads_issued"] = _gav_cypher_reads[0]
        # NOW WIRED, via the plan rather than a counter (see _gav_probe_plan).
        # Three distinguishable outcomes, because collapsing them would put the
        # engine's failure and our own in the same bucket:
        #   True  - a GAV operator served the read, named in gav_view_operator
        #   False - the plan was read and named no GAV operator: the view did not
        #           serve it, which is a finding about the engine
        #   None  - EXPLAIN itself failed: we learned nothing, and the row must
        #           not be read as either of the above
        out["gav_view_operator"] = _gav_plan[0]
        out["gav_view_usage_verified"] = (
            None if _gav_plan[0] is None else bool(_gav_plan[0]))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)
