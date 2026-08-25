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


READS = {
    "doc":       "SELECT count(*) FROM D",
    "doc_idx10": "SELECT FROM D WHERE p0 = 5 LIMIT 10",
    "graph":     "SELECT count(*) FROM (SELECT expand(out('E')) FROM P LIMIT 100)",
    "graph_gav": "SELECT count(*) FROM (SELECT expand(out('E').out('E')) FROM P LIMIT 100)",
    "vector":    None,     # filled in at runtime, needs a probe vector
    "sparse":    "SELECT count(*) FROM S LIMIT 10",
    "ts":        "SELECT count(*) FROM T",
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
        list(db.query("sql", q))


_WRITE_SEQ = [0]


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
    elif situation in ("doc", "doc_idx10"):
        db.command("sql", f"INSERT INTO D SET p0 = {i}")
    elif situation == "sparse":
        db.command("sql", f"INSERT INTO S SET id = {i}")
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
        import_ms = jvm_start_ms = first_open_ms = cold_proc_ms = -1.0

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
    out["import_ms"] = round(import_ms, 3)               # interpreter + module import
    out["jvm_start_ms"] = round(jvm_start_ms, 3)         # start_jvm() alone, no database
    out["first_open_ms"] = round(first_open_ms, 3)       # first open, JVM already up
    out["cold_process_ms"] = round(cold_proc_ms, 3)      # what a CLI actually waits for

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
    out["cold_start_penalty_ms"] = round(
        max(0.0, out["cold_process_ms"] - (out["clean_open_ms"] + out["clean_close_ms"])), 3)

    # A stale reopen: the PREVIOUS session committed, so any persisted derived
    # structure is invalid on this open. Measured separately because it is the
    # case #6641 is about and no other mode reaches it.
    if "write_own" in MODES:
        _sw = cycle(args.workload, "write_own")
        o, c, w = measure(args.workload, "clean")
        out["stale_open_ms"], out["stale_close_ms"] = round(o, 3), round(c, 3)
        o, c, w = measure(args.workload, "read")
        out["stale_read_open_ms"], out["stale_read_close_ms"] = round(o, 3), round(c, 3)
        out["stale_read_action_ms"] = round(w, 3)
        out["stale_read_session_ms"] = round(o + w + c, 3)

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
